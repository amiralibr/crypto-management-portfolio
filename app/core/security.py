"""Static Bearer API key authentication and role authorization for MVP-0."""

import secrets
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.enums import ApiRole
from app.core.errors import ForbiddenError, UnauthorizedError


def extract_bearer_token(authorization: str | None) -> str:
    """Extract token from 'Authorization: Bearer <token>' header."""
    if not authorization:
        raise UnauthorizedError("Authentication failed")
    parts = authorization.strip().split(" ")
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1].strip():
        raise UnauthorizedError("Authentication failed")
    return parts[1].strip()


def verify_api_key(token: str, settings: Settings) -> ApiRole:
    """Validate API key in constant time and return its associated role."""
    admin_key = settings.MVP0_ADMIN_API_KEY.get_secret_value()
    op_key = settings.MVP0_API_KEY.get_secret_value()

    is_admin = secrets.compare_digest(token.encode("utf-8"), admin_key.encode("utf-8"))
    is_operational = secrets.compare_digest(token.encode("utf-8"), op_key.encode("utf-8"))

    if is_admin:
        return ApiRole.ADMIN
    if is_operational:
        return ApiRole.OPERATIONAL

    raise UnauthorizedError("Authentication failed")


async def require_operational_role(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiRole:
    """FastAPI dependency requiring OPERATIONAL or ADMIN role."""
    if "api_key" in request.query_params or "token" in request.query_params:
        raise UnauthorizedError("API key in query parameters is forbidden")

    auth_header = request.headers.get("Authorization")
    token = extract_bearer_token(auth_header)
    role = verify_api_key(token, settings)
    request.state.actor_role = role.value
    return role


async def require_admin_role(
    role: Annotated[ApiRole, Depends(require_operational_role)],
) -> ApiRole:
    """FastAPI dependency requiring ADMIN role."""
    if role != ApiRole.ADMIN:
        raise ForbiddenError("Admin API key required")
    return role
