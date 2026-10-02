"""Standardized error hierarchy and FastAPI exception handlers for MVP-0."""

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application exception conforming to the MVP-0 error contract."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details: dict[str, Any] = details or {}


class UnauthorizedError(AppError):
    """Raised when Bearer authentication is missing or invalid (HTTP 401)."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=401,
            details=details,
        )


class ForbiddenError(AppError):
    """Raised when caller lacks required role permissions (HTTP 403)."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=403,
            details=details,
        )


class InvalidRequestError(AppError):
    """Raised when request validation fails (HTTP 400)."""

    def __init__(
        self,
        message: str = "Invalid request",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="INVALID_REQUEST",
            message=message,
            status_code=400,
            details=details,
        )


class NotFoundError(AppError):
    """Raised when a requested domain entity does not exist (HTTP 404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=404,
            details=details,
        )


class InvalidStateError(AppError):
    """Raised when a state machine or approval transition is invalid (HTTP 409)."""

    def __init__(
        self,
        message: str = "Invalid transition",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="INVALID_STATE",
            message=message,
            status_code=409,
            details=details,
        )


class ConflictError(AppError):
    """Raised on concurrency or business state conflicts (HTTP 409)."""

    def __init__(
        self,
        message: str = "State conflict",
        code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details=details,
        )


class KillSwitchConflictError(AppError):
    """Raised when Kill Switch state or resume action conflicts (HTTP 409)."""

    def __init__(
        self,
        message: str = "Kill Switch conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="KILL_SWITCH_CONFLICT",
            message=message,
            status_code=409,
            details=details,
        )


class KillSwitchActiveError(AppError):
    """Raised when new order or signal execution is blocked by Kill Switch (HTTP 409)."""

    def __init__(
        self,
        message: str = "Kill Switch is active; new orders are blocked",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="KILL_SWITCH_ACTIVE",
            message=message,
            status_code=409,
            details=details,
        )


class RiskRejectedError(AppError):
    """Raised when the Risk Engine rejects a signal or order (HTTP 422)."""

    def __init__(
        self,
        message: str = "Order rejected by Risk Engine",
        reason_codes: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if reason_codes is not None:
            merged_details["reason_codes"] = reason_codes
        super().__init__(
            code="RISK_REJECTED",
            message=message,
            status_code=422,
            details=merged_details,
        )


class ServiceUnavailableError(AppError):
    """Raised when a critical backing dependency is unavailable (HTTP 503)."""

    def __init__(
        self,
        message: str = "System unavailable",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="SYSTEM_UNAVAILABLE",
            message=message,
            status_code=503,
            details=details,
        )


class RedisOperationError(AppError):
    """Raised on transient Redis client errors."""

    def __init__(
        self,
        message: str = "Redis operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="REDIS_ERROR",
            message=message,
            status_code=503,
            details=details,
        )


def get_request_id(request: Request) -> str:
    """Extract or generate a request_id for the given HTTP request."""
    req_id = getattr(request.state, "request_id", None)
    if isinstance(req_id, str) and req_id:
        return req_id
    header_id = request.headers.get("X-Request-ID")
    if header_id:
        return header_id
    return str(uuid.uuid4())


def build_error_payload(
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build standard error response dictionary."""
    return {
        "code": code,
        "message": message,
        "request_id": request_id,
        "details": details or {},
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register standardized JSON exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = get_request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                details=exc.details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = get_request_id(request)
        status_to_code = {
            400: "INVALID_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            429: "RATE_LIMITED",
            503: "SYSTEM_UNAVAILABLE",
        }
        code = status_to_code.get(exc.status_code, "HTTP_ERROR")
        message = str(exc.detail) if exc.detail else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(
                code=code,
                message=message,
                request_id=request_id,
                details={},
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = get_request_id(request)
        return JSONResponse(
            status_code=400,
            content=build_error_payload(
                code="INVALID_REQUEST",
                message="Request validation failed",
                request_id=request_id,
                details={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        request_id = get_request_id(request)
        return JSONResponse(
            status_code=500,
            content=build_error_payload(
                code="INTERNAL_ERROR",
                message="An unexpected internal error occurred",
                request_id=request_id,
                details={},
            ),
        )
