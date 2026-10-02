"""Async SQLAlchemy 2 engine, session factory, and health utilities for MVP-0."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.metrics import DB_HEALTH_GAUGE

EXPECTED_HEAD_REVISION: str = "0006_kill_switch_dual_approval"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_logger = get_logger("mvp0.db")


def create_db_engine(
    database_url: str,
    pool_size: int = 5,
    max_overflow: int = 10,
) -> AsyncEngine:
    """Create a configured SQLAlchemy AsyncEngine with bounded connection pool."""
    if pool_size < 1 or pool_size > 20:
        raise ValueError("pool_size must be between 1 and 20")
    if max_overflow < 0 or max_overflow > 20:
        raise ValueError("max_overflow must be between 0 and 20")

    return create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def init_db(
    settings: Settings | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Initialize global async engine and session factory."""
    global _engine, _session_factory
    cfg = settings or get_settings()
    _engine = create_db_engine(
        database_url=cfg.database_url,
        pool_size=cfg.DB_POOL_SIZE,
        max_overflow=cfg.DB_MAX_OVERFLOW,
    )
    _session_factory = create_session_factory(_engine)
    return _engine, _session_factory


def get_engine() -> AsyncEngine:
    """Return active global AsyncEngine or initialize from settings."""
    global _engine
    if _engine is None:
        init_db()
    if _engine is None:
        raise RuntimeError("Database engine failed to initialize")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return active global session factory or initialize from settings."""
    global _session_factory
    if _session_factory is None:
        init_db()
    if _session_factory is None:
        raise RuntimeError("Session factory failed to initialize")
    return _session_factory


async def dispose_db() -> None:
    """Dispose global async engine gracefully."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession with rollback on exception."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def ping_database(engine: AsyncEngine | None = None) -> bool:
    """Verify PostgreSQL connectivity via SELECT 1 and update health gauge."""
    target_engine = engine or get_engine()
    try:
        async with target_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            healthy = result.scalar() == 1
            DB_HEALTH_GAUGE.set(1 if healthy else 0)
            return healthy
    except Exception as exc:
        DB_HEALTH_GAUGE.set(0)
        _logger.warning("db_ping_failed", error_type=type(exc).__name__)
        return False


async def check_migrations_current(engine: AsyncEngine | None = None) -> bool:
    """Check whether Alembic migrations are at the expected head revision."""
    target_engine = engine or get_engine()
    try:
        async with target_engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            rows = [row[0] for row in result.fetchall()]
            return EXPECTED_HEAD_REVISION in rows
    except Exception as exc:
        _logger.warning("migrations_check_failed", error_type=type(exc).__name__)
        return False
