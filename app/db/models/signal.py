"""Signal ORM model for MVP-0 (M002)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    event,
    func,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import LoaderCallableStatus, Mapped, mapped_column

from app.core.errors import SignalReferencePriceImmutableError
from app.db.models.exchange_account import Base


class Signal(Base):
    """Represents a trading signal requiring explicit user approval."""

    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint(
            "symbol IN ('BTC/USDT', 'ETH/USDT', 'BNB/USDT')",
            name="ck_signals_allowed_symbol",
        ),
        CheckConstraint("direction = 'LONG'", name="ck_signals_long_only"),
        CheckConstraint(
            "approval_status IN ("
            "'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXPIRED', 'PRICE_DRIFT_EXPIRED'"
            ")",
            name="ck_signals_approval_status",
        ),
        CheckConstraint("reference_price > 0", name="ck_signals_positive_ref_price"),
        CheckConstraint(
            "entry_range_min <= entry_range_max",
            name="ck_signals_entry_range_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    entry_range_min: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    entry_range_max: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    stop_loss_price: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    data_quality_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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


@event.listens_for(Signal.reference_price, "set")
def _prevent_reference_price_mutation(
    target: Signal,
    value: Decimal,
    oldvalue: object,
    _initiator: object,
) -> None:
    """Reject any in-memory mutation of Signal.reference_price once initialized (§4.5 & §7.2)."""
    if oldvalue in (None, LoaderCallableStatus.NO_VALUE, LoaderCallableStatus.NEVER_SET):
        return
    if isinstance(oldvalue, Decimal) and Decimal(str(value)) != oldvalue:
        raise SignalReferencePriceImmutableError(
            f"Signal reference_price ({oldvalue}) is immutable and cannot be changed to {value}",
            details={
                "signal_id": getattr(target, "signal_id", None),
                "original_reference_price": str(oldvalue),
                "attempted_reference_price": str(value),
            },
        )


@event.listens_for(Signal, "before_update")
def _prevent_reference_price_db_update(
    _mapper: object,
    _connection: object,
    target: Signal,
) -> None:
    """Reject any ORM flush that attempts to modify Signal.reference_price."""
    state = inspect(target)
    hist = state.attrs.reference_price.history
    if hist.has_changes() and hist.deleted:
        old_val = hist.deleted[0]
        new_val = hist.added[0] if hist.added else target.reference_price
        if old_val is not None and Decimal(str(old_val)) != Decimal(str(new_val)):
            raise SignalReferencePriceImmutableError(
                "Signal reference_price is immutable and cannot be updated in PostgreSQL"
            )
