"""System health and administrative foundation endpoints for API v1."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies import get_redis_client
from app.core.config import Settings, get_settings
from app.core.enums import ApiRole
from app.core.errors import get_request_id
from app.core.redis import RedisClient
from app.core.security import require_admin_role, require_operational_role
from app.db.session import check_migrations_current, ping_database
from app.schemas.system import AdminSystemStatusResponse, SystemHealthResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    request: Request,
    role: Annotated[ApiRole, Depends(require_operational_role)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[RedisClient, Depends(get_redis_client)],
) -> SystemHealthResponse:
    """Return detailed authenticated health status (OPERATIONAL or ADMIN)."""
    db_ok = await ping_database()
    redis_ok = await redis_client.ping()
    migrations_ok = await check_migrations_current() if db_ok else False
    overall_ok = db_ok and redis_ok and migrations_ok

    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return SystemHealthResponse(
        status="ok" if overall_ok else "degraded",
        environment=settings.ENVIRONMENT,
        paper_trading=settings.PAPER_TRADING,
        live_trading=settings.LIVE_TRADING,
        database="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
        migrations="ok" if migrations_ok else "unavailable",
        role=role.value,
        timestamp=now_iso,
        request_id=get_request_id(request),
    )


@router.get("/status", response_model=AdminSystemStatusResponse)
async def get_admin_system_status(
    request: Request,
    role: Annotated[ApiRole, Depends(require_admin_role)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSystemStatusResponse:
    """Return administrative foundation configuration status (ADMIN only)."""
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return AdminSystemStatusResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        paper_trading=settings.PAPER_TRADING,
        live_trading=settings.LIVE_TRADING,
        uvicorn_workers=settings.UVICORN_WORKERS,
        supervisor_tasks=settings.SUPERVISOR_TASKS,
        role=role.value,
        timestamp=now_iso,
        request_id=get_request_id(request),
    )
