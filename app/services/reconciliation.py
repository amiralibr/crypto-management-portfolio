"""Position and Order Reconciliation service for MVP-0 (§13.5, §17.1, v4.3 §1.5)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OutboxEventType, PositionStatus
from app.db.models.position import Position
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.outbox import OutboxService, record_audit_log


@dataclass(frozen=True)
class ReconciliationReport:
    """Summary of reconciling local PostgreSQL positions against exchange adapter state."""

    success: bool
    checked_positions: int
    discrepancies: list[dict[str, str]]
    timestamp: datetime


class ReconciliationService:
    """Service comparing durable PostgreSQL positions/orders with simulated exchange state."""

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        outbox_service: OutboxService | None = None,
        notifier: NotificationAdapter | None = None,
    ) -> None:
        self._exchange = exchange_adapter
        self._outbox = outbox_service or OutboxService(notifier=notifier)
        self._notifier = notifier

    async def reconcile_open_positions(
        self,
        session: AsyncSession,
        *,
        sync_missing_to_exchange: bool = False,
    ) -> ReconciliationReport:
        """Compare all OPEN PostgreSQL positions against the exchange adapter."""
        now = datetime.now(UTC)
        stmt = select(Position).where(Position.status == PositionStatus.OPEN.value)
        open_positions = list((await session.scalars(stmt)).all())

        exchange_positions = await self._exchange.get_positions()
        discrepancies: list[dict[str, str]] = []

        # Aggregate local open position quantities by symbol
        local_by_symbol: dict[str, Decimal] = {}
        for pos in open_positions:
            local_by_symbol[pos.symbol] = local_by_symbol.get(pos.symbol, Decimal("0")) + Decimal(
                str(pos.size)
            )

        for symbol, local_qty in local_by_symbol.items():
            ex_snap = exchange_positions.get(symbol)
            ex_qty = ex_snap.quantity if ex_snap is not None else Decimal("0")
            if ex_qty != local_qty:
                if sync_missing_to_exchange and hasattr(self._exchange, "set_position"):
                    sample_pos = next(p for p in open_positions if p.symbol == symbol)
                    self._exchange.set_position(
                        symbol=symbol,
                        quantity=local_qty,
                        entry_price=Decimal(str(sample_pos.entry_price)),
                    )
                    continue

                discrepancies.append(
                    {
                        "symbol": symbol,
                        "local_quantity": str(local_qty),
                        "exchange_quantity": str(ex_qty),
                    }
                )

        if discrepancies:
            agg_id = open_positions[0].id if open_positions else uuid.uuid4()
            await record_audit_log(
                session,
                actor_role="SYSTEM",
                action=OutboxEventType.RECONCILIATION_FAILED.value,
                target_type="RECONCILIATION",
                target_id=agg_id,
                reason_code="POSITION_MISMATCH",
                detail_json={"discrepancies": discrepancies},
            )
            await self._outbox.enqueue_event(
                session,
                event_type=OutboxEventType.RECONCILIATION_FAILED.value,
                aggregate_type="POSITION",
                aggregate_id=agg_id,
                payload={"discrepancies": discrepancies},
            )
            if self._notifier is not None:
                await self._notifier.send_alert(
                    severity="CRITICAL",
                    title="Reconciliation Discrepancy Detected",
                    message="Local PostgreSQL open positions do not match exchange state.",
                    metadata={"discrepancies": discrepancies},
                )

        return ReconciliationReport(
            success=len(discrepancies) == 0,
            checked_positions=len(open_positions),
            discrepancies=discrepancies,
            timestamp=now,
        )
