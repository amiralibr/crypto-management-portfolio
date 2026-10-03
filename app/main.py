"""FastAPI application entry point and lifespan management for MVP-0."""

import asyncio
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import api_v1_router
from app.core.config import Settings, get_settings
from app.core.errors import get_request_id, register_exception_handlers
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from app.core.redis import RedisClient
from app.db.session import (
    check_migrations_current,
    dispose_db,
    get_session_factory,
    init_db,
    ping_database,
)
from app.integrations.exchange.paper import PaperTradingAdapter
from app.schemas.system import HealthzResponse, ReadyzResponse
from app.services.risk_engine import RiskEngine
from app.workers.approval_timeout import (
    WORKER_NAME as APPROVAL_TIMEOUT_WORKER_NAME,
)
from app.workers.approval_timeout import (
    approval_timeout_worker_loop,
)
from app.workers.outbox_publisher import (
    WORKER_NAME as OUTBOX_PUBLISHER_WORKER_NAME,
)
from app.workers.outbox_publisher import (
    outbox_publisher_worker_loop,
)
from app.workers.supervisor import WorkerSupervisor
from app.workers.synthetic_stop import (
    WORKER_NAME as SYNTHETIC_STOP_WORKER_NAME,
)
from app.workers.synthetic_stop import (
    synthetic_stop_worker_loop,
)


def _collect_secrets(settings: Settings) -> list[str]:
    """Gather sensitive strings from settings for log redaction."""
    secrets: list[str] = [
        settings.MVP0_API_KEY.get_secret_value(),
        settings.MVP0_ADMIN_API_KEY.get_secret_value(),
        settings.database_url,
        settings.redis_url,
    ]
    if settings.POSTGRES_PASSWORD:
        secrets.append(settings.POSTGRES_PASSWORD)
    if settings.REDIS_PASSWORD:
        secrets.append(settings.REDIS_PASSWORD)
    return secrets


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown lifecycle according to Contract §17.1 and §17.2."""
    # 1. Load settings
    settings = get_settings()
    # 2. Initialize structured logging
    configure_logging(
        log_level=settings.LOG_LEVEL,
        environment=settings.ENVIRONMENT,
        service_name=settings.APP_NAME,
        secrets_to_redact=_collect_secrets(settings),
    )
    logger = get_logger("mvp0.lifecycle")

    # 3. Validate trading mode
    if settings.LIVE_TRADING or not settings.PAPER_TRADING:
        raise RuntimeError("Invalid trading mode: MVP-0 requires Paper-only mode")

    # 4. Create database engine
    engine, session_factory = init_db(settings)
    redis_client = RedisClient(settings.redis_url)
    app.state.redis_client = redis_client
    app.state.background_tasks = []

    # 5. Ping PostgreSQL & 6. Ping Redis
    db_ok = await ping_database(engine)
    redis_ok = await redis_client.ping()

    exchange_adapter = PaperTradingAdapter()
    supervisor = WorkerSupervisor(
        exchange_adapter=exchange_adapter,
        session_factory=session_factory,
    )
    app.state.exchange_adapter = exchange_adapter
    app.state.worker_supervisor = supervisor
    app.state.recovered_stops_count = 0
    app.state.reconciliation_report = None

    # 7. Recover active Synthetic Stops & 8. Reconcile open positions (+ record heartbeat)
    if db_ok and await check_migrations_current(engine):
        recovered_stops, recon_report = await supervisor.recover_and_reconcile_on_startup()
        app.state.recovered_stops_count = recovered_stops
        app.state.reconciliation_report = recon_report
        async with get_session_factory()() as hb_session:
            await RiskEngine().record_heartbeat(
                hb_session,
                metadata={"source": "mvp0_api_lifespan_startup"},
            )
            await hb_session.commit()

    # 9. Start supervisor & 10-12. Start Approval Timeout, Synthetic Stop, and Outbox workers
    stop_event = asyncio.Event()
    app.state.worker_stop_event = stop_event
    approval_task = supervisor.start_worker(
        APPROVAL_TIMEOUT_WORKER_NAME,
        lambda: approval_timeout_worker_loop(
            exchange_adapter=exchange_adapter,
            session_factory=session_factory,
            stop_event=stop_event,
        ),
    )
    stop_task = supervisor.start_worker(
        SYNTHETIC_STOP_WORKER_NAME,
        lambda: synthetic_stop_worker_loop(
            exchange_adapter=exchange_adapter,
            session_factory=session_factory,
            stop_event=stop_event,
        ),
    )
    outbox_task = supervisor.start_worker(
        OUTBOX_PUBLISHER_WORKER_NAME,
        lambda: outbox_publisher_worker_loop(
            session_factory=session_factory,
            stop_event=stop_event,
        ),
    )
    app.state.background_tasks.extend([approval_task, stop_task, outbox_task])

    # 13. Mark service ready
    app.state.service_ready = True

    logger.info(
        "application_started",
        db_ok=db_ok,
        redis_ok=redis_ok,
        paper_trading=settings.PAPER_TRADING,
        live_trading=settings.LIVE_TRADING,
        recovered_stops_count=app.state.recovered_stops_count,
        supervised_workers=list(supervisor._tasks.keys()),
    )

    try:
        yield
    finally:
        # 1. Stop accepting new work
        app.state.service_ready = False
        # 2. Cancel worker tasks & 3. Await graceful completion
        stop_event.set()
        await supervisor.stop_all()
        tasks: list[asyncio.Task[object]] = getattr(app.state, "background_tasks", [])
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        tasks.clear()

        # 5. Close Redis connection & 6. Dispose database engine
        await redis_client.close()
        await dispose_db()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging(
        log_level=settings.LOG_LEVEL,
        environment=settings.ENVIRONMENT,
        service_name=settings.APP_NAME,
        secrets_to_redact=_collect_secrets(settings),
    )

    application = FastAPI(
        title="MVP-0 Crypto Risk Management API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    application.state.redis_client = RedisClient(settings.redis_url)
    application.state.background_tasks = []
    application.state.service_ready = True

    register_exception_handlers(application)
    _ = Instrumentator()

    @application.middleware("http")
    async def request_context_and_metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id, corr_id = bind_request_context(
            request_id=request.headers.get("X-Request-ID"),
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        request.state.request_id = req_id
        request.state.correlation_id = corr_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration = time.perf_counter() - start_time
            path = request.url.path
            method = request.method
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=path,
            ).observe(duration)

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        ).inc()
        response.headers["X-Request-ID"] = req_id
        clear_request_context()
        return response

    @application.get("/healthz", response_model=HealthzResponse, tags=["public"])
    async def healthz(request: Request) -> HealthzResponse:
        """Liveness probe — always returns HTTP 200 if process is alive."""
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return HealthzResponse(
            status="ok",
            timestamp=now_iso,
            request_id=get_request_id(request),
        )

    @application.get("/readyz", response_model=ReadyzResponse, tags=["public"])
    async def readyz(request: Request) -> JSONResponse:
        """Readiness probe checking PostgreSQL, Redis, migrations, and config."""
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        req_id = get_request_id(request)

        try:
            cfg = get_settings()
            config_ok = (not cfg.LIVE_TRADING) and cfg.PAPER_TRADING
        except Exception:
            config_ok = False

        db_ok = await ping_database()
        redis_client: RedisClient = getattr(
            request.app.state,
            "redis_client",
            RedisClient(get_settings().redis_url),
        )
        redis_ok = await redis_client.ping()
        migrations_ok = await check_migrations_current() if db_ok else False

        is_ready = config_ok and db_ok and redis_ok and migrations_ok
        payload = ReadyzResponse(
            status="ready" if is_ready else "not_ready",
            database="ok" if db_ok else "unavailable",
            redis="ok" if redis_ok else "unavailable",
            migrations="ok" if migrations_ok else "unavailable",
            timestamp=now_iso,
            request_id=req_id,
        )
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content=payload.model_dump(),
        )

    @application.get("/metrics", tags=["public"])
    async def metrics() -> Response:
        """Expose Prometheus metrics in text format."""
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )

    application.include_router(api_v1_router)
    return application


def get_default_app() -> FastAPI:
    """Create default FastAPI app when environment is configured."""
    try:
        return create_app()
    except Exception:
        fallback = FastAPI(title="MVP-0 Unconfigured")
        register_exception_handlers(fallback)
        return fallback


app: FastAPI = get_default_app()
