"""Structured JSON logging with structlog and secret redaction for MVP-0."""

import logging
import re
import sys
import uuid
from collections.abc import MutableMapping
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.typing import FilteringBoundLogger

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_ctx_var: ContextVar[str] = ContextVar("correlation_id", default="")

_SENSITIVE_KEY_PATTERNS: frozenset[str] = frozenset(
    {
        "api_key",
        "mvp0_api_key",
        "mvp0_admin_api_key",
        "admin_api_key",
        "authorization",
        "password",
        "postgres_password",
        "redis_password",
        "secret",
        "token",
        "access_token",
        "credential",
        "credentials",
        "database_url",
        "redis_url",
        "paper_database_url",
        "paper_redis_url",
    }
)

_BEARER_REGEX = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.~+/]+=*", re.IGNORECASE)
_CONN_STR_REGEX = re.compile(
    r"(?:postgresql(?:\+asyncpg)?|redis|rediss)://[^\s\"']+",
    re.IGNORECASE,
)

_registered_secrets: set[str] = set()
_configured_environment: str = "development"
_configured_service: str = "mvp0"


def register_secret_for_redaction(secret_value: str | None) -> None:
    """Register a runtime secret string so it is scrubbed from all log output."""
    if secret_value and len(secret_value.strip()) >= 8:
        _registered_secrets.add(secret_value.strip())


def clear_registered_secrets() -> None:
    """Clear registered runtime secrets (used in tests)."""
    _registered_secrets.clear()


def bind_request_context(
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> tuple[str, str]:
    """Bind request_id and correlation_id into contextvars for structured logging."""
    req_id = request_id or str(uuid.uuid4())
    corr_id = correlation_id or req_id
    request_id_ctx_var.set(req_id)
    correlation_id_ctx_var.set(corr_id)
    structlog.contextvars.bind_contextvars(
        request_id=req_id,
        correlation_id=corr_id,
    )
    return req_id, corr_id


def clear_request_context() -> None:
    """Clear per-request logging context variables."""
    request_id_ctx_var.set("")
    correlation_id_ctx_var.set("")
    structlog.contextvars.clear_contextvars()


def _scrub_string(value: str) -> str:
    """Scrub Bearer tokens, connection strings, and registered secrets from a string."""
    scrubbed = _BEARER_REGEX.sub("Bearer [REDACTED]", value)
    scrubbed = _CONN_STR_REGEX.sub("[REDACTED_URI]", scrubbed)
    for secret in _registered_secrets:
        if secret in scrubbed:
            scrubbed = scrubbed.replace(secret, "[REDACTED]")
    return scrubbed


def _sanitize_value(key: str | None, value: object) -> object:
    """Recursively sanitize dictionaries, lists, and strings for forbidden log data."""
    if key is not None:
        normalized_key = key.lower().strip()
        if normalized_key in _SENSITIVE_KEY_PATTERNS or any(
            pat in normalized_key
            for pat in ("api_key", "password", "secret", "authorization", "credential")
        ):
            return "[REDACTED]"

    if isinstance(value, str):
        return _scrub_string(value)
    if isinstance(value, dict):
        return {str(k): _sanitize_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(key, item) for item in value]
    return value


def _inject_required_fields(
    _logger: object,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Ensure required MVP-0 log fields exist and secrets are redacted."""
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    event_dict.setdefault("timestamp", now_iso)

    level = str(event_dict.get("level", method_name)).upper()
    event_dict["level"] = level

    event_val = event_dict.get("event", "")
    message_val = event_dict.get("message", event_val)
    event_dict["message"] = str(message_val)

    event_dict.setdefault("environment", _configured_environment)
    event_dict.setdefault("service", _configured_service)

    req_id = event_dict.get("request_id") or request_id_ctx_var.get() or str(uuid.uuid4())
    corr_id = event_dict.get("correlation_id") or correlation_id_ctx_var.get() or req_id
    event_dict["request_id"] = req_id
    event_dict["correlation_id"] = corr_id

    for k in list(event_dict.keys()):
        event_dict[k] = _sanitize_value(k, event_dict[k])

    return event_dict


def configure_logging(
    log_level: str = "INFO",
    environment: str = "development",
    service_name: str = "mvp0",
    secrets_to_redact: list[str] | None = None,
) -> None:
    """Configure structlog for JSON structured logging."""
    global _configured_environment, _configured_service
    _configured_environment = environment
    _configured_service = service_name

    if secrets_to_redact:
        for secret in secrets_to_redact:
            register_secret_for_redaction(secret)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _inject_required_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "mvp0") -> FilteringBoundLogger:
    """Return a configured structlog bound logger."""
    logger: FilteringBoundLogger = structlog.get_logger(name)
    return logger
