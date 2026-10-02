"""M002 — signals_and_orders: signals, orders."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_signals_and_orders"
down_revision: str | None = "0001_foundation_tables"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create signals and orders tables."""
    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column(
            "reference_price",
            sa.Numeric(precision=30, scale=12),
            nullable=False,
        ),
        sa.Column(
            "entry_range_min",
            sa.Numeric(precision=30, scale=12),
            nullable=False,
        ),
        sa.Column(
            "entry_range_max",
            sa.Numeric(precision=30, scale=12),
            nullable=False,
        ),
        sa.Column(
            "stop_loss_price",
            sa.Numeric(precision=30, scale=12),
            nullable=False,
        ),
        sa.Column(
            "take_profit_price",
            sa.Numeric(precision=30, scale=12),
            nullable=True,
        ),
        sa.Column(
            "risk_reward_ratio",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
        ),
        sa.Column(
            "data_quality_score",
            sa.Numeric(precision=6, scale=4),
            nullable=False,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=6, scale=4),
            nullable=False,
        ),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column(
            "approval_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "explanation_json",
            postgresql.JSONB(astext_type=sa.Text()),
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
        sa.CheckConstraint(
            "symbol IN ('BTC/USDT', 'ETH/USDT', 'BNB/USDT')",
            name="ck_signals_allowed_symbol",
        ),
        sa.CheckConstraint("direction = 'LONG'", name="ck_signals_long_only"),
        sa.CheckConstraint(
            "approval_status IN ("
            "'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXPIRED', 'PRICE_DRIFT_EXPIRED'"
            ")",
            name="ck_signals_approval_status",
        ),
        sa.CheckConstraint("reference_price > 0", name="ck_signals_positive_ref_price"),
        sa.CheckConstraint(
            "entry_range_min <= entry_range_max",
            name="ck_signals_entry_range_order",
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "exchange_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("limit_price", sa.Numeric(precision=30, scale=12), nullable=True),
        sa.Column(
            "filled_quantity",
            sa.Numeric(precision=30, scale=12),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "average_fill_price",
            sa.Numeric(precision=30, scale=12),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("state_machine_state", sa.String(length=32), nullable=False),
        sa.Column("risk_decision", sa.String(length=32), nullable=False),
        sa.Column(
            "risk_reason_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["exchange_account_id"], ["exchange_accounts.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id"),
        sa.UniqueConstraint("idempotency_key"),
    )


def downgrade() -> None:
    """Drop orders and signals tables."""
    op.drop_table("orders")
    op.drop_table("signals")
