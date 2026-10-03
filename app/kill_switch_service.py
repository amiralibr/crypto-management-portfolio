"""Standalone internal Kill Switch Service entrypoint for MVP-0 (F2 Requirements #1 & #2).

Routing & Architecture Contract:
- Public `POST /api/v1/system/emergency-stop` (and related `/api/v1/system/emergency-stop*`
  endpoints) are served exclusively by `mvp0_api` (`app.main:app`) on port 8000, which writes
  Kill Switch state into PostgreSQL (`system_state` table, `state_key='KILL_SWITCH'`).
- This `kill_switch` service runs on internal container port 8001 (`expose: ["8001"]`, no host
  port binding) and does NOT expose the public `/api/v1/system/emergency-stop` route.
- This `kill_switch` service reads the Kill Switch state (`KILL_SWITCH`) and Risk Engine
  heartbeat (`RISK_ENGINE_HEARTBEAT`) from PostgreSQL, and automatically activates the Kill
  Switch in PostgreSQL if the Risk Engine heartbeat is missing or older than
  `RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS` (60s).
"""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.enums import ApiRole
from app.core.errors import get_request_id, register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.redis import RedisClient
from app.core.security import require_admin_role
from app.db.session import (
    check_migrations_current,
    dispose_db,
    get_session_factory,
    init_db,
    ping_database,
)
from app.schemas.system import EmergencyStopActivateResponse, HealthzResponse, ReadyzResponse
from app.services.kill_switch import KillSwitchService
from app.services.risk_engine import RiskEngine


async def read_kill_switch_and_heartbeat_from_db() -> dict[str, object]:
    """Read current Kill Switch state and Risk Engine heartbeat from PostgreSQL."""
    factory = get_session_factory()
    ks = KillSwitchService()
    risk_engine = RiskEngine()
    async with factory() as session:
        state = await ks.get_or_create_state(session)
        last_hb = await risk_engine.get_last_heartbeat(session)
        await session.commit()
        return {
            "is_active": state.is_active,
            "activation_reason": state.activation_reason,
            "activated_by": state.activated_by,
            "activated_at": (
                state.activated_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if state.activated_at is not None
                else None
            ),
            "resume_status": state.resume_status,
            "exposure_multiplier": str(state.exposure_multiplier),
            "last_heartbeat_at": (
                last_hb.astimezone(UTC).isoformat().replace("+00:00", "Z")
                if last_hb is not None
                else None
            ),
        }


async def run_heartbeat_monitor_once(
    *, now: datetime | None = None
) -> EmergencyStopActivateResponse | None:
    """Read Risk Engine heartbeat from PostgreSQL and activate Kill Switch if stale (>60s)."""
    settings = get_settings()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        result = await ks.check_risk_engine_heartbeat(
            session,
            timeout_seconds=settings.RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS,
            now=now,
        )
        await session.commit()
        if result is None:
            return None
        return EmergencyStopActivateResponse(
            status=result.status,
            is_active=result.is_active,
            resume_status=result.resume_status,
            timestamp=result.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            request_id=str(uuid.uuid4()),
        )


async def _heartbeat_monitor_loop(
    stop_event: asyncio.Event,
    poll_interval_seconds: float = 5.0,
) -> None:
    """Background loop inside the independent Kill Switch container monitoring heartbeats."""
    logger = get_logger("mvp0.kill_switch_service")
    while not stop_event.is_set():
        try:
            await run_heartbeat_monitor_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("kill_switch_heartbeat_monitor_error", error=str(exc))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
        except TimeoutError:
            continue


@asynccontextmanager
async def kill_switch_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan manager for the standalone internal Kill Switch Service container."""
    settings = get_settings()
    configure_logging(
        log_level=settings.LOG_LEVEL,
        environment=settings.ENVIRONMENT,
        service_name=f"{settings.APP_NAME}-kill-switch",
    )
    logger = get_logger("mvp0.kill_switch_service")

    init_db(settings)
    redis_client = RedisClient(settings.redis_url)
    app.state.redis_client = redis_client

    # Read initial persistent KILL_SWITCH state and heartbeat baseline from PostgreSQL
    try:
        snapshot = await read_kill_switch_and_heartbeat_from_db()
        if snapshot["last_heartbeat_at"] is None:
            factory = get_session_factory()
            async with factory() as session:
                await RiskEngine().record_heartbeat(
                    session,
                    metadata={"source": "kill_switch_service_boot_baseline"},
                )
                await session.commit()
    except Exception as exc:
        logger.warning("kill_switch_startup_db_seed_skipped", error=str(exc))

    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(
        _heartbeat_monitor_loop(stop_event),
        name="kill_switch_heartbeat_monitor",
    )
    app.state.service_ready = True
    logger.info(
        "kill_switch_service_started",
        heartbeat_timeout_seconds=settings.RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS,
        internal_port=8001,
    )
    try:
        yield
    finally:
        app.state.service_ready = False
        stop_event.set()
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task
        await redis_client.close()
        await dispose_db()
        logger.info("kill_switch_service_stopped")


def create_kill_switch_app() -> FastAPI:
    """Create the standalone internal Kill Switch FastAPI application (port 8001).

    Does NOT mount `/api/v1/system/emergency-stop` (which is served exclusively by
    `mvp0_api` on port 8000).
    """
    settings = get_settings()
    application = FastAPI(
        title="MVP-0 Internal Kill Switch Watchdog Service",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=kill_switch_lifespan,
    )
    application.state.redis_client = RedisClient(settings.redis_url)
    application.state.service_ready = False
    register_exception_handlers(application)

    @application.get("/healthz", response_model=HealthzResponse, tags=["health"])
    async def healthz(request: Request) -> HealthzResponse:
        """Internal liveness probe for the Kill Switch Service container."""
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return HealthzResponse(
            status="ok",
            timestamp=now_iso,
            request_id=get_request_id(request),
        )

    @application.get("/readyz", response_model=ReadyzResponse, tags=["health"])
    async def readyz(request: Request) -> JSONResponse:
        """Internal readiness probe verifying PostgreSQL connectivity for Kill Switch Service."""
        db_ok = await ping_database()
        migrations_ok = await check_migrations_current() if db_ok else False
        redis_client: RedisClient = getattr(
            request.app.state,
            "redis_client",
            RedisClient(get_settings().redis_url),
        )
        redis_ok = await redis_client.ping()
        is_ready = db_ok and migrations_ok
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        payload = ReadyzResponse(
            status="ready" if is_ready else "not_ready",
            database="ok" if db_ok else "unavailable",
            redis="ok" if redis_ok else "unavailable",
            migrations="ok" if migrations_ok else "out_of_date",
            timestamp=now_iso,
            request_id=get_request_id(request),
        )
        return JSONResponse(status_code=200 if is_ready else 503, content=payload.model_dump())

    @application.get(
        "/internal/kill-switch/state",
        tags=["kill-switch-internal"],
    )
    async def get_internal_state_endpoint(
        request: Request,
        _role: Annotated[ApiRole, Depends(require_admin_role)],
    ) -> dict[str, object]:
        """Internal endpoint reading Kill Switch state and Risk Engine heartbeat from PostgreSQL."""
        snapshot = await read_kill_switch_and_heartbeat_from_db()
        snapshot["request_id"] = get_request_id(request)
        return snapshot

    @application.post(
        "/api/v1/kill-switch/heartbeat-check",
        tags=["kill-switch-internal"],
    )
    async def check_heartbeat_endpoint(
        request: Request,
        _role: Annotated[ApiRole, Depends(require_admin_role)],
    ) -> dict[str, object]:
        """Internal endpoint checking Risk Engine heartbeat in DB and activating if stale."""
        activation = await run_heartbeat_monitor_once()
        snapshot = await read_kill_switch_and_heartbeat_from_db()
        return {
            "triggered": activation is not None,
            "activation": activation.model_dump() if activation is not None else None,
            "state": snapshot,
            "request_id": get_request_id(request),
        }

    return application


app = create_kill_switch_app()
