"""M004 — risk_and_synthetic_stops: risk_rules, synthetic_stops."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_risk_and_synthetic_stops"
down_revision: str | None = "0003_positions_and_trades"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create risk_rules and synthetic_stops tables."""
    op.create_table(
        "risk_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column(
            "max_risk_per_trade",
            sa.Numeric(precision=10, scale=6),
            server_default="0.005000",
            nullable=False,
        ),
        sa.Column(
            "max_daily_loss",
            sa.Numeric(precision=10, scale=6),
            server_default="0.020000",
            nullable=False,
        ),
        sa.Column(
            "max_weekly_loss",
            sa.Numeric(precision=10, scale=6),
            server_default="0.050000",
            nullable=False,
        ),
        sa.Column(
            "max_asset_weight",
            sa.Numeric(precision=10, scale=6),
            server_default="0.150000",
            nullable=False,
        ),
        sa.Column(
            "max_total_exposure",
            sa.Numeric(precision=10, scale=6),
            server_default="0.700000",
            nullable=False,
        ),
        sa.Column(
            "min_cash_reserve",
            sa.Numeric(precision=10, scale=6),
            server_default="0.150000",
            nullable=False,
        ),
        sa.Column(
            "soft_drawdown_limit",
            sa.Numeric(precision=10, scale=6),
            server_default="0.080000",
            nullable=False,
        ),
        sa.Column(
            "hard_drawdown_limit",
            sa.Numeric(precision=10, scale=6),
            server_default="0.120000",
            nullable=False,
        ),
        sa.Column(
            "kill_switch_drawdown_limit",
            sa.Numeric(precision=10, scale=6),
            server_default="0.150000",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_code"),
    )

    op.create_table(
        "synthetic_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("stop_price", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("execution_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "status IN ("
            "'ARMED', 'TRIGGERED', 'SUBMITTING', 'SUBMITTED', "
            "'EXECUTED', 'FAILED', 'MANUAL_REVIEW', 'CANCELLED'"
            ")",
            name="ck_synthetic_stops_status",
        ),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )


def downgrade() -> None:
    """Drop synthetic_stops and risk_rules tables."""
    op.drop_table("synthetic_stops")
    op.drop_table("risk_rules")
