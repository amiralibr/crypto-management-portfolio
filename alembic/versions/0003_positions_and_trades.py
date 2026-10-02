"""M003 — positions_and_trades: positions, trades."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_positions_and_trades"
down_revision: str | None = "0002_signals_and_orders"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create positions and trades tables."""
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "exchange_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("size", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("mark_price", sa.Numeric(precision=30, scale=12), nullable=True),
        sa.Column(
            "unrealized_pnl",
            sa.Numeric(precision=30, scale=12),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "realized_pnl",
            sa.Numeric(precision=30, scale=12),
            server_default="0",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stop_price", sa.Numeric(precision=30, scale=12), nullable=True),
        sa.Column("take_profit_state", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exchange_trade_id", sa.String(length=128), nullable=True),
        sa.Column("fill_price", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("fill_quantity", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("fee", sa.Numeric(precision=30, scale=12), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_trade_id"),
    )


def downgrade() -> None:
    """Drop trades and positions tables."""
    op.drop_table("trades")
    op.drop_table("positions")
