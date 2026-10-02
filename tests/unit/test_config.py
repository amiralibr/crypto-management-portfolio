"""F1 Configuration unit tests (§13.1)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_required_env_vars_missing_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing required API keys, DATABASE_URL, or REDIS_URL must fail startup."""
    monkeypatch.delenv("MVP0_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("MVP0_API_KEY", "a" * 32)
    monkeypatch.delenv("MVP0_ADMIN_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("MVP0_ADMIN_API_KEY", "b" * 32)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_database_url_constructed_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATABASE_URL and REDIS_URL are constructed from component vars when omitted."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "dbhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "mvp0user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mvp0pass")
    monkeypatch.setenv("POSTGRES_DB", "mvp0db")

    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "redishost")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_PASSWORD", "redispass")

    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://mvp0user:mvp0pass@dbhost:5433/mvp0db"
    assert settings.redis_url == "redis://:redispass@redishost:6380/0"

    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="mysql://user:pass@localhost/db")

    with pytest.raises(ValidationError):
        Settings(REDIS_URL="http://localhost:6379")


def test_worker_count_locked_to_1() -> None:
    """UVICORN_WORKERS and SUPERVISOR_TASKS must be locked to 1."""
    settings = get_settings()
    assert settings.UVICORN_WORKERS == 1
    assert settings.SUPERVISOR_TASKS == 1

    with pytest.raises(ValidationError):
        Settings(UVICORN_WORKERS=2)

    with pytest.raises(ValidationError):
        Settings(SUPERVISOR_TASKS=2)


def test_invalid_log_level_raises() -> None:
    """Invalid LOG_LEVEL or ENVIRONMENT values must raise ValidationError."""
    with pytest.raises(ValidationError):
        Settings(LOG_LEVEL="INVALID_LEVEL")

    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="invalid_env")


def test_live_trading_must_be_false() -> None:
    """LIVE_TRADING=true must be rejected at startup."""
    with pytest.raises(ValidationError):
        Settings(LIVE_TRADING=True)


def test_paper_trading_must_be_true() -> None:
    """PAPER_TRADING=false must be rejected at startup."""
    with pytest.raises(ValidationError):
        Settings(PAPER_TRADING=False)


def test_api_keys_must_differ() -> None:
    """Identical or too-short operational and admin API keys must be rejected."""
    identical_key = "identical_secret_key_00000000000001"
    with pytest.raises(ValidationError):
        Settings(
            MVP0_API_KEY=identical_key,
            MVP0_ADMIN_API_KEY=identical_key,
        )

    with pytest.raises(ValidationError):
        Settings(MVP0_API_KEY="short_key")


def test_price_drift_threshold_within_allowed_range() -> None:
    """PRICE_DRIFT_EXPIRY_THRESHOLD must be Decimal within [0.0001, 0.01]."""
    valid = Settings(PRICE_DRIFT_EXPIRY_THRESHOLD=Decimal("0.002"))
    assert Decimal("0.002") == valid.PRICE_DRIFT_EXPIRY_THRESHOLD

    with pytest.raises(ValidationError):
        Settings(PRICE_DRIFT_EXPIRY_THRESHOLD=Decimal("0.00005"))

    with pytest.raises(ValidationError):
        Settings(PRICE_DRIFT_EXPIRY_THRESHOLD=Decimal("0.02"))


def test_outbox_retry_settings_within_allowed_range() -> None:
    """OUTBOX_MAX_RETRIES must be in [1, 10] and OUTBOX_RETRY_BASE_SECONDS in [1, 60]."""
    valid = Settings(OUTBOX_MAX_RETRIES=5, OUTBOX_RETRY_BASE_SECONDS=2)
    assert valid.OUTBOX_MAX_RETRIES == 5
    assert valid.OUTBOX_RETRY_BASE_SECONDS == 2

    with pytest.raises(ValidationError):
        Settings(OUTBOX_MAX_RETRIES=0)

    with pytest.raises(ValidationError):
        Settings(OUTBOX_MAX_RETRIES=11)

    with pytest.raises(ValidationError):
        Settings(OUTBOX_RETRY_BASE_SECONDS=0)

    with pytest.raises(ValidationError):
        Settings(OUTBOX_RETRY_BASE_SECONDS=61)


def test_error_classes_and_schemas() -> None:
    """Error classes and common error schema construct standardized payloads."""
    from app.core.errors import (
        ForbiddenError,
        InvalidRequestError,
        ServiceUnavailableError,
        UnauthorizedError,
        build_error_payload,
    )
    from app.integrations.exchange.base import PERMITTED_ADAPTERS
    from app.schemas.common import ErrorResponse

    err1 = InvalidRequestError("bad input", details={"field": "x"})
    err2 = ServiceUnavailableError("down")
    err3 = UnauthorizedError()
    err4 = ForbiddenError()
    assert err1.status_code == 400
    assert err2.status_code == 503
    assert err3.status_code == 401
    assert err4.status_code == 403

    payload = build_error_payload(err1.code, err1.message, "req-1", err1.details)
    schema = ErrorResponse(**payload)
    assert schema.code == "INVALID_REQUEST"
    assert {"PaperTradingAdapter", "FakeExchangeAdapter"} == PERMITTED_ADAPTERS
