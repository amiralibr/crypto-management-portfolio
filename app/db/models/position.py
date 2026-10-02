"""Position ORM model for MVP-0 (M003)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.exchange_account import Base


class Position(Base):
    """Represents an open or closed Spot LONG position in MVP-0."""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False
    )
    exchange_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exchange_accounts.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    take_profit_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
