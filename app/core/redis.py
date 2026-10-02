"""Transient Redis client wrapper with strict error taxonomy for MVP-0."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.errors import RedisOperationError
from app.core.logging import get_logger
from app.core.metrics import REDIS_HEALTH_GAUGE

FORBIDDEN_DURABLE_PREFIXES: tuple[str, ...] = (
    "durable:",
    "sot:",
)


class RedisClient:
    """Wrapper around async Redis client restricted to transient operational state."""

    def __init__(self, redis_url: str, client: Redis | None = None) -> None:
        self._redis_url = redis_url
        self._client: Redis | None = client
        self._logger = get_logger("mvp0.redis")

    def _get_or_create_client(self) -> Redis:
        """Lazily create or return the underlying async Redis client."""
        if self._client is None:
            self._client = Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        return self._client

    async def ping(self) -> bool:
        """Check Redis connectivity and update Prometheus health gauge."""
        try:
            client = self._get_or_create_client()
            result = await client.ping()
            healthy = bool(result)
            REDIS_HEALTH_GAUGE.set(1 if healthy else 0)
            return healthy
        except (RedisError, OSError) as exc:
            REDIS_HEALTH_GAUGE.set(0)
            self._logger.warning("redis_ping_failed", error_type=type(exc).__name__)
            return False

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = 300,
    ) -> bool:
        """Store a transient string value in Redis."""
        normalized = key.strip().lower()
        if any(normalized.startswith(prefix) for prefix in FORBIDDEN_DURABLE_PREFIXES):
            raise RedisOperationError(
                message="Redis must not be used as durable source of truth",
                details={"key_prefix": normalized.split(":", 1)[0]},
            )
        try:
            client = self._get_or_create_client()
            result = await client.set(name=key, value=value, ex=ttl_seconds)
            REDIS_HEALTH_GAUGE.set(1)
            return bool(result)
        except (RedisError, OSError) as exc:
            REDIS_HEALTH_GAUGE.set(0)
            raise RedisOperationError(
                message="Failed to write transient key to Redis",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def get(self, key: str) -> str | None:
        """Retrieve a transient string value from Redis."""
        try:
            client = self._get_or_create_client()
            value = await client.get(name=key)
            REDIS_HEALTH_GAUGE.set(1)
            if value is None:
                return None
            return str(value)
        except (RedisError, OSError) as exc:
            REDIS_HEALTH_GAUGE.set(0)
            raise RedisOperationError(
                message="Failed to read transient key from Redis",
                details={"error_type": type(exc).__name__},
            ) from exc

    async def close(self) -> None:
        """Gracefully close the underlying Redis connection pool."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except (RedisError, OSError) as exc:
                self._logger.warning("redis_close_failed", error_type=type(exc).__name__)
            finally:
                self._client = None
