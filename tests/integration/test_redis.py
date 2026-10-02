"""F1 Redis integration tests (§13.7)."""

import pytest
from sqlalchemy import select

from app.core.errors import RedisOperationError
from app.core.redis import RedisClient
from app.db.models import ExchangeAccount
from app.db.session import dispose_db, get_session_factory, init_db
from app.main import create_app, lifespan
from tests.conftest import TEST_REDIS_URL


async def test_redis_ping_succeeds() -> None:
    """RedisClient.ping returns True when connected to Redis."""
    client = RedisClient(TEST_REDIS_URL)
    assert await client.ping() is True
    await client.close()


async def test_redis_set_get_round_trip() -> None:
    """RedisClient.set and RedisClient.get perform round-trip key operations."""
    client = RedisClient(TEST_REDIS_URL)
    assert await client.set("cache:test_key", "test_val", ttl_seconds=60) is True
    assert await client.get("cache:test_key") == "test_val"
    assert await client.get("cache:nonexistent_key") is None

    with pytest.raises(RedisOperationError):
        await client.set("durable:order:123", "forbidden")

    await client.close()


async def test_redis_unavailable_does_not_crash_startup(
    monkeypatch: pytest.MonkeyPatch,
    migrated_db: None,
) -> None:
    """Application lifespan startup completes even if Redis is unreachable."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6399/0")
    from app.core.config import get_settings

    get_settings.cache_clear()
    test_app = create_app()
    async with lifespan(test_app):
        assert test_app.state.service_ready is True

    bad_client = RedisClient("redis://127.0.0.1:6399/0")
    assert await bad_client.ping() is False
    with pytest.raises(RedisOperationError):
        await bad_client.get("cache:any")
    with pytest.raises(RedisOperationError):
        await bad_client.set("cache:any", "val")
    await bad_client.close()


async def test_redis_unavailable_does_not_lose_postgres_state(
    migrated_db: None,
) -> None:
    """PostgreSQL durable state remains intact when Redis is unavailable."""
    init_db()
    factory = get_session_factory()
    account_name = "paper-durable-account"

    async with factory() as session:
        existing = await session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == account_name)
        )
        if existing is None:
            session.add(
                ExchangeAccount(
                    name=account_name,
                    exchange_name="paper_sim",
                    mode="PAPER",
                    is_active=True,
                )
            )
            await session.commit()

    unreachable_redis = RedisClient("redis://127.0.0.1:6399/0")
    assert await unreachable_redis.ping() is False
    await unreachable_redis.close()

    async with factory() as verify_session:
        persisted = await verify_session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == account_name)
        )
        assert persisted is not None
        assert persisted.mode == "PAPER"

    await dispose_db()
