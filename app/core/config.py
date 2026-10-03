"""Application configuration and central policy validation for MVP-0."""

import secrets
from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import Environment, LogLevel

ALLOWED_ENVIRONMENTS: frozenset[str] = frozenset(e.value for e in Environment)
ALLOWED_LOG_LEVELS: frozenset[str] = frozenset(level.value for level in LogLevel)
MIN_API_KEY_LENGTH: int = 32
MIN_PRICE_DRIFT_THRESHOLD: Decimal = Decimal("0.0001")
MAX_PRICE_DRIFT_THRESHOLD: Decimal = Decimal("0.01")
MIN_OUTBOX_MAX_RETRIES: int = 1
MAX_OUTBOX_MAX_RETRIES: int = 10
MIN_OUTBOX_RETRY_BASE_SECONDS: int = 1
MAX_OUTBOX_RETRY_BASE_SECONDS: int = 60

# Central policy for prohibited durable domain prefixes in Redis (F2 Requirement #9)
FORBIDDEN_DURABLE_PREFIXES: tuple[str, ...] = (
    "durable:",
    "sot:",
    "order:",
    "orders:",
    "position:",
    "positions:",
    "trade:",
    "trades:",
    "signal:",
    "signals:",
    "approval:",
    "approvals:",
    "audit:",
    "outbox:",
    "dead_letter:",
    "dlq:",
    "kill_switch:",
    "resume:",
)

# Central risk & safety policy constants (F2 Requirements #2, #3, #4)
MAX_RISK_PER_TRADE_PCT_CEILING: Decimal = Decimal("0.005")
REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS: int = 86400
DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS: int = 60


class Settings(BaseSettings):
    """Immutable runtime settings validated at application startup."""

    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=True,
        case_sensitive=True,
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "mvp0"

    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    DATABASE_URL: str | None = None

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_URL: str | None = None
    FORBIDDEN_DURABLE_PREFIXES: tuple[str, ...] = FORBIDDEN_DURABLE_PREFIXES

    MVP0_API_KEY: SecretStr
    MVP0_ADMIN_API_KEY: SecretStr

    UVICORN_WORKERS: int = 1
    SUPERVISOR_TASKS: int = 1
    APPROVAL_TIMEOUT_INTERVAL_SECONDS: int = 5

    LIVE_TRADING: bool = False
    PAPER_TRADING: bool = True
    PRICE_DRIFT_EXPIRY_THRESHOLD: Decimal = Decimal("0.002")
    MAX_RISK_PER_TRADE_PCT: Decimal = MAX_RISK_PER_TRADE_PCT_CEILING
    KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS: int = (
        REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS
    )
    RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS: int = DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS

    OUTBOX_MAX_RETRIES: int = 5
    OUTBOX_RETRY_BASE_SECONDS: int = 2

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Ensure ENVIRONMENT is one of the allowed deployment targets."""
        if value not in ALLOWED_ENVIRONMENTS:
            allowed = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
            raise ValueError(f"ENVIRONMENT must be one of: {allowed}")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure LOG_LEVEL is a valid standard logging level."""
        if value not in ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(ALLOWED_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return value

    @field_validator("UVICORN_WORKERS")
    @classmethod
    def validate_uvicorn_workers(cls, value: int) -> int:
        """Lock Uvicorn worker count to 1 to prevent duplicate background schedulers."""
        if value != 1:
            raise ValueError("UVICORN_WORKERS must be locked to 1")
        return value

    @field_validator("SUPERVISOR_TASKS")
    @classmethod
    def validate_supervisor_tasks(cls, value: int) -> int:
        """Lock supervisor task count to 1."""
        if value != 1:
            raise ValueError("SUPERVISOR_TASKS must be locked to 1")
        return value

    @field_validator("LIVE_TRADING")
    @classmethod
    def validate_live_trading(cls, value: bool) -> bool:
        """Enforce LIVE_TRADING=false in MVP-0."""
        if value is not False:
            raise ValueError("LIVE_TRADING must be false in MVP-0")
        return value

    @field_validator("PAPER_TRADING")
    @classmethod
    def validate_paper_trading(cls, value: bool) -> bool:
        """Enforce PAPER_TRADING=true in MVP-0."""
        if value is not True:
            raise ValueError("PAPER_TRADING must be true in MVP-0")
        return value

    @field_validator("MVP0_API_KEY", "MVP0_ADMIN_API_KEY")
    @classmethod
    def validate_api_key_length(cls, value: SecretStr) -> SecretStr:
        """Ensure API keys are at least 32 characters and not placeholder values."""
        secret = value.get_secret_value().strip()
        if len(secret) < MIN_API_KEY_LENGTH:
            raise ValueError(f"API key must be at least {MIN_API_KEY_LENGTH} characters")
        return value

    @field_validator("PRICE_DRIFT_EXPIRY_THRESHOLD")
    @classmethod
    def validate_price_drift_threshold(cls, value: Decimal) -> Decimal:
        """Ensure price drift expiry threshold is within [0.0001, 0.01]."""
        if value < MIN_PRICE_DRIFT_THRESHOLD or value > MAX_PRICE_DRIFT_THRESHOLD:
            raise ValueError(
                f"PRICE_DRIFT_EXPIRY_THRESHOLD must be between "
                f"{MIN_PRICE_DRIFT_THRESHOLD} and {MAX_PRICE_DRIFT_THRESHOLD}"
            )
        return value

    @field_validator("MAX_RISK_PER_TRADE_PCT")
    @classmethod
    def validate_max_risk_per_trade_pct(cls, value: Decimal) -> Decimal:
        """Enforce max risk per trade ceiling of 0.005 (0.5%)."""
        if value <= Decimal("0") or value > MAX_RISK_PER_TRADE_PCT_CEILING:
            raise ValueError(
                f"MAX_RISK_PER_TRADE_PCT must be in (0, {MAX_RISK_PER_TRADE_PCT_CEILING}]"
            )
        return value

    @field_validator("KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS")
    @classmethod
    def validate_kill_switch_resume_expiry(cls, value: int) -> int:
        """Enforce KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS == 86400 (24 hours)."""
        if value != REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS:
            raise ValueError(
                f"KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS must be exactly "
                f"{REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS}"
            )
        return value

    @field_validator("RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS")
    @classmethod
    def validate_risk_engine_heartbeat_timeout(cls, value: int) -> int:
        """Enforce RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS is positive and <= 60s."""
        if value <= 0 or value > DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS:
            raise ValueError(
                f"RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS must be in "
                f"(0, {DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS}]"
            )
        return value

    @field_validator("OUTBOX_MAX_RETRIES")
    @classmethod
    def validate_outbox_max_retries(cls, value: int) -> int:
        """Ensure OUTBOX_MAX_RETRIES is within [1, 10]."""
        if value < MIN_OUTBOX_MAX_RETRIES or value > MAX_OUTBOX_MAX_RETRIES:
            raise ValueError(
                f"OUTBOX_MAX_RETRIES must be between "
                f"{MIN_OUTBOX_MAX_RETRIES} and {MAX_OUTBOX_MAX_RETRIES}"
            )
        return value

    @field_validator("OUTBOX_RETRY_BASE_SECONDS")
    @classmethod
    def validate_outbox_retry_base_seconds(cls, value: int) -> int:
        """Ensure OUTBOX_RETRY_BASE_SECONDS is within [1, 60]."""
        if value < MIN_OUTBOX_RETRY_BASE_SECONDS or value > MAX_OUTBOX_RETRY_BASE_SECONDS:
            raise ValueError(
                f"OUTBOX_RETRY_BASE_SECONDS must be between "
                f"{MIN_OUTBOX_RETRY_BASE_SECONDS} and {MAX_OUTBOX_RETRY_BASE_SECONDS}"
            )
        return value

    @model_validator(mode="after")
    def validate_and_construct_urls_and_keys(self) -> "Settings":
        """Validate distinct API keys and construct/verify DATABASE_URL and REDIS_URL."""
        op_key = self.MVP0_API_KEY.get_secret_value()
        admin_key = self.MVP0_ADMIN_API_KEY.get_secret_value()
        if secrets.compare_digest(op_key, admin_key):
            raise ValueError("MVP0_API_KEY and MVP0_ADMIN_API_KEY must differ")

        db_url = self.DATABASE_URL
        if not db_url:
            if self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_DB:
                db_url = (
                    f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )
                object.__setattr__(self, "DATABASE_URL", db_url)
            else:
                raise ValueError("DATABASE_URL is required")
        elif not db_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg:// driver")

        redis_url = self.REDIS_URL
        if not redis_url:
            if self.REDIS_PASSWORD:
                redis_url = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
                object.__setattr__(self, "REDIS_URL", redis_url)
            else:
                raise ValueError("REDIS_URL is required")
        elif not (redis_url.startswith("redis://") or redis_url.startswith("rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")

        return self

    @property
    def database_url(self) -> str:
        """Return validated non-null PostgreSQL async connection string."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured")
        return self.DATABASE_URL

    @property
    def redis_url(self) -> str:
        """Return validated non-null Redis connection string."""
        if not self.REDIS_URL:
            raise ValueError("REDIS_URL is not configured")
        return self.REDIS_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()  # type: ignore[call-arg]
