"""F1 Database session and pool integration tests (§13.3)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.pool import AsyncAdaptedQueuePool, QueuePool

from app.core.config import get_settings
from app.db.models import ExchangeAccount
from app.db.session import (
    create_db_engine,
    dispose_db,
    get_db_session,
    get_session_factory,
    init_db,
    ping_database,
)


async def test_async_session_connects_to_postgres(migrated_db: None) -> None:
    """AsyncSession connects to PostgreSQL and executes queries."""
    engine, _ = init_db()
    assert await ping_database(engine) is True

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    await dispose_db()


async def test_session_rolls_back_on_exception(migrated_db: None) -> None:
    """get_db_session rolls back uncommitted writes when an exception occurs."""
    init_db()
    account_name = "rollback-test-account"

    gen = get_db_session()
    session = await anext(gen)
    session.add(
        ExchangeAccount(
            name=account_name,
            exchange_name="paper_sim",
            mode="PAPER",
            is_active=True,
        )
    )
    await session.flush()

    with pytest.raises(RuntimeError, match="simulated failure"):
        await gen.athrow(RuntimeError("simulated failure"))

    factory = get_session_factory()
    async with factory() as verify_session:
        found = await verify_session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == account_name)
        )
        assert found is None
    await dispose_db()


async def test_connection_pool_within_limits() -> None:
    """Database engine enforces bounded pool_size and max_overflow settings."""
    settings = get_settings()
    engine = create_db_engine(
        database_url=settings.database_url,
        pool_size=5,
        max_overflow=10,
    )
    pool = engine.pool
    assert isinstance(pool, (QueuePool, AsyncAdaptedQueuePool))
    assert pool.size() == 5
    await engine.dispose()

    with pytest.raises(ValueError, match="pool_size"):
        create_db_engine(settings.database_url, pool_size=0, max_overflow=5)

    with pytest.raises(ValueError, match="max_overflow"):
        create_db_engine(settings.database_url, pool_size=5, max_overflow=-1)

    await dispose_db()
    lazy_engine = create_db_engine(
        "postgresql+asyncpg://mvp0:bad@127.0.0.1:5499/mvp0",
        pool_size=1,
        max_overflow=0,
    )
    from app.db.session import check_migrations_current, get_engine, get_session_factory

    assert await ping_database(lazy_engine) is False
    assert await check_migrations_current(lazy_engine) is False
    await lazy_engine.dispose()

    assert get_engine() is not None
    assert get_session_factory() is not None
    await dispose_db()
