"""F1 Alembic migration integration tests (§13.4)."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.db.models import Base
from app.db.session import dispose_db, get_engine, init_db

EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "exchange_accounts",
        "strategies",
        "system_states",
        "signals",
        "orders",
        "positions",
        "trades",
        "risk_rules",
        "synthetic_stops",
        "outbox_events",
        "dead_letter_events",
        "audit_logs",
        "approval_requests",
    }
)


async def test_all_migrations_apply_clean(alembic_config: Config) -> None:
    """All migrations M001-M006 apply cleanly on an empty database."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    init_db()
    engine = get_engine()
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    assert EXPECTED_TABLES.issubset(table_names)
    await dispose_db()


async def test_all_migrations_rollback_clean(alembic_config: Config) -> None:
    """All migrations roll back cleanly to base and reapply to head."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    init_db()
    engine = get_engine()
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    assert EXPECTED_TABLES.isdisjoint(table_names)

    command.upgrade(alembic_config, "head")
    async with engine.connect() as conn:
        table_names_after = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    assert EXPECTED_TABLES.issubset(table_names_after)
    await dispose_db()


async def test_schema_matches_sqlalchemy_models(alembic_config: Config) -> None:
    """Database schema produced by M001-M006 matches SQLAlchemy Base.metadata."""
    command.upgrade(alembic_config, "head")
    init_db()
    engine = get_engine()

    def _compare(sync_conn: Connection) -> list[object]:
        mc = MigrationContext.configure(sync_conn)
        return list(compare_metadata(mc, Base.metadata))

    async with engine.connect() as conn:
        diffs = await conn.run_sync(_compare)

    assert diffs == []
    await dispose_db()


async def test_dead_letter_events_table_exists(migrated_db: None) -> None:
    """dead_letter_events table exists with required columns and constraints."""
    init_db()
    engine = get_engine()
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {
                col["name"] for col in inspect(sync_conn).get_columns("dead_letter_events")
            }
        )
    required_cols = {
        "id",
        "original_outbox_event_id",
        "event_id",
        "event_type",
        "event_version",
        "aggregate_type",
        "aggregate_id",
        "payload_json",
        "failure_reason",
        "failure_class",
        "retry_count",
        "first_failed_at",
        "dead_lettered_at",
        "resolution_status",
        "resolved_at",
        "resolved_by",
        "resolution_note",
        "created_at",
        "updated_at",
    }
    assert required_cols.issubset(columns)
    await dispose_db()


async def test_approval_requests_table_exists(migrated_db: None) -> None:
    """approval_requests table exists with required columns for Two-Person Approval."""
    init_db()
    engine = get_engine()
    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {
                col["name"] for col in inspect(sync_conn).get_columns("approval_requests")
            }
        )
        version_row = await conn.execute(text("SELECT version_num FROM alembic_version"))
        versions = [r[0] for r in version_row.fetchall()]

    required_cols = {
        "id",
        "request_type",
        "target_type",
        "target_id",
        "status",
        "requested_by",
        "requested_by_role",
        "first_approver_id",
        "first_approver_role",
        "first_approved_at",
        "second_approver_id",
        "second_approver_role",
        "second_approved_at",
        "reason",
        "expires_at",
        "completed_at",
        "created_at",
        "updated_at",
        "version",
    }
    assert required_cols.issubset(columns)
    assert "0006_kill_switch_dual_approval" in versions
    await dispose_db()
