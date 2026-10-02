"""FastAPI dependencies for API v1 routes."""

from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.enums import ApiRole
from app.core.redis import RedisClient
from app.core.security import require_admin_role, require_operational_role
from app.db.session import get_db_session


def get_redis_client(request: Request) -> RedisClient:
    """Return the application RedisClient instance from app state."""
    client = getattr(request.app.state, "redis_client", None)
    if isinstance(client, RedisClient):
        return client
    settings: Settings = get_settings()
    return RedisClient(settings.redis_url)


__all__ = [
    "ApiRole",
    "get_db_session",
    "get_redis_client",
    "get_settings",
    "require_admin_role",
    "require_operational_role",
]
