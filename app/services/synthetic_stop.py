"""PostgreSQL-backed Synthetic Stop-Loss service for MVP-0 (§12)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ALLOWED_SYMBOLS,
    ALLOWED_TIMEFRAMES,
    OrderState,
    OutboxEventType,
    PositionStatus,
    RiskDecisionStatus,
    SyntheticStopStatus,
)
from app.core.errors import InvalidRequestError, NotFoundError
from app.core.metrics import ORDERS_TOTAL, SYNTHETIC_STOP_FAILURES_TOTAL
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.synthetic_stop import SyntheticStop
from app.db.models.trade import Trade
from app.integrations.exchange.base import ExchangeAdapter, ExchangeOrderReceipt
from app.integrations.notifications.base import NotificationAdapter
from app.services.outbox import OutboxService, record_audit_log
from app.services.risk_engine import ensure_decimal

POLL_INTERVAL_SECONDS_BY_TIMEFRAME: dict[str, int] = {
    "1H": 30,
    "4H": 60,
    "1D": 300,
}

STOP_RETRY_SCHEDULE_SECONDS: tuple[int, int, int] = (0, 5, 15)


@dataclass(frozen=True)
class StopExecutionResult:
    """Outcome of evaluating/executing a Synthetic Stop."""

    stop_id: uuid.UUID
    triggered: bool
    status: str
    attempts_executed: int
    schedule_offsets_seconds: tuple[int, ...]
    execution_order_id: uuid.UUID | None
    idempotency_key: str
    last_error: str | None


class SyntheticStopService:
    """Persistent, idempotent Synthetic Stop-Loss manager backed by PostgreSQL (§12)."""

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        outbox_service: OutboxService | None = None,
        notifier: NotificationAdapter | None = None,
        current_timeframe: str = "1H",
    ) -> None:
        if current_timeframe not in ALLOWED_TIMEFRAMES:
            raise InvalidRequestError(
                f"Invalid timeframe for SyntheticStopService: {current_timeframe}"
            )
        self.exchange_adapter = exchange_adapter
        self.current_timeframe = current_timeframe
        self._outbox = outbox_service or OutboxService(notifier=notifier)
        self._notifier = notifier

    @staticmethod
    def get_poll_interval_seconds(timeframe: str) -> int:
        """Return polling interval in seconds for the given timeframe (§12.3)."""
        if timeframe not in POLL_INTERVAL_SECONDS_BY_TIMEFRAME:
            raise InvalidRequestError(f"Unsupported timeframe: {timeframe}")
        return POLL_INTERVAL_SECONDS_BY_TIMEFRAME[timeframe]

    async def register_stop(
        self,
        session: AsyncSession,
        *,
        position_id: uuid.UUID,
        stop_price: Decimal,
        timeframe: str = "1H",
        idempotency_key: str | None = None,
    ) -> SyntheticStop:
        """Idempotently register and arm a SyntheticStop in PostgreSQL."""
        ensure_decimal(stop_price, "stop_price")
        if stop_price <= Decimal("0"):
            raise InvalidRequestError("stop_price must be positive")
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise InvalidRequestError(f"Unsupported timeframe: {timeframe}")

        position = await session.scalar(
            select(Position).where(Position.id == position_id).with_for_update()
        )
        if position is None:
            raise NotFoundError(f"Position {position_id} not found")
        if position.symbol not in ALLOWED_SYMBOLS or position.side != "LONG":
            raise InvalidRequestError("Synthetic stops only support Spot LONG allowed symbols")

        idem_key = idempotency_key or f"stop-pos-{position.id}"
        existing = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.idempotency_key == idem_key).with_for_update()
        )
        if existing is not None:
            return existing

        existing_active = await session.scalar(
            select(SyntheticStop)
            .where(
                SyntheticStop.position_id == position.id,
                SyntheticStop.status.in_(
                    [
                        SyntheticStopStatus.ARMED.value,
                        SyntheticStopStatus.TRIGGERED.value,
                        SyntheticStopStatus.SUBMITTING.value,
                        SyntheticStopStatus.SUBMITTED.value,
                        SyntheticStopStatus.EXECUTED.value,
                    ]
                ),
            )
            .with_for_update()
        )
        if existing_active is not None:
            return existing_active

        now = datetime.now(UTC)
        stop = SyntheticStop(
            id=uuid.uuid4(),
            position_id=position.id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.size,
            stop_price=stop_price,
            timeframe=timeframe,
            status=SyntheticStopStatus.ARMED.value,
            idempotency_key=idem_key,
            execution_order_id=None,
            attempt_count=0,
            last_error=None,
            last_checked_at=now,
            triggered_at=None,
            executed_at=None,
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(stop)
        position.stop_price = stop_price
        position.updated_at = now
        position.version += 1
        await session.flush()

        await record_audit_log(
            session,
            actor_role="SYSTEM",
            action=OutboxEventType.STOP_REGISTERED.value,
            target_type="SYNTHETIC_STOP",
            target_id=stop.id,
            after_json={
                "status": stop.status,
                "stop_price": str(stop.stop_price),
                "quantity": str(stop.quantity),
                "idempotency_key": stop.idempotency_key,
            },
            reason_code="STOP_ARMED",
            detail_json={"position_id": str(position.id), "timeframe": timeframe},
        )
        await self._outbox.enqueue_event(
            session,
            event_type=OutboxEventType.STOP_REGISTERED.value,
            aggregate_type="SYNTHETIC_STOP",
            aggregate_id=stop.id,
            payload={
                "stop_id": str(stop.id),
                "position_id": str(position.id),
                "symbol": stop.symbol,
                "stop_price": str(stop.stop_price),
                "quantity": str(stop.quantity),
            },
        )
        return stop

    async def load_active_stops_from_db(self, session: AsyncSession) -> list[SyntheticStop]:
        """Load all ARMED or in-flight SyntheticStops for OPEN positions from PostgreSQL (§12.2)."""
        stmt = (
            select(SyntheticStop)
            .join(Position, Position.id == SyntheticStop.position_id)
            .where(
                Position.status == PositionStatus.OPEN.value,
                SyntheticStop.status.in_(
                    [
                        SyntheticStopStatus.ARMED.value,
                        SyntheticStopStatus.TRIGGERED.value,
                        SyntheticStopStatus.SUBMITTING.value,
                        SyntheticStopStatus.SUBMITTED.value,
                    ]
                ),
            )
            .order_by(SyntheticStop.created_at.asc())
        )
        return list((await session.scalars(stmt)).all())

    async def evaluate_and_execute_stop(
        self,
        session: AsyncSession,
        *,
        stop_id: uuid.UUID,
        current_price: Decimal | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> StopExecutionResult:
        """Atomically evaluate an ARMED stop and execute idempotently with 0s/5s/15s retries."""
        now = datetime.now(UTC)
        stmt = select(SyntheticStop).where(SyntheticStop.id == stop_id).with_for_update()
        stop = await session.scalar(stmt)
        if stop is None:
            raise NotFoundError(f"SyntheticStop {stop_id} not found")

        position = await session.scalar(
            select(Position).where(Position.id == stop.position_id).with_for_update()
        )
        if position is None or position.status != PositionStatus.OPEN.value:
            return StopExecutionResult(
                stop_id=stop.id,
                triggered=False,
                status=stop.status,
                attempts_executed=0,
                schedule_offsets_seconds=(),
                execution_order_id=stop.execution_order_id,
                idempotency_key=stop.idempotency_key,
                last_error=stop.last_error,
            )

        # Compare-and-set guard: only ARMED stops can trigger (§12.2)
        if stop.status != SyntheticStopStatus.ARMED.value:
            return StopExecutionResult(
                stop_id=stop.id,
                triggered=False,
                status=stop.status,
                attempts_executed=0,
                schedule_offsets_seconds=(),
                execution_order_id=stop.execution_order_id,
                idempotency_key=stop.idempotency_key,
                last_error=stop.last_error,
            )

        resolved_price = current_price
        if resolved_price is None:
            ticker = await self.exchange_adapter.get_ticker(stop.symbol)
            resolved_price = ticker.price
        ensure_decimal(resolved_price, "current_price")

        stop.last_checked_at = now
        stop.updated_at = now
        position.mark_price = resolved_price
        position.unrealized_pnl = (resolved_price - position.entry_price) * position.size
        await session.flush()

        # Trigger condition for Spot LONG: current_price <= stop_price (§12.2)
        if resolved_price > Decimal(str(stop.stop_price)):
            return StopExecutionResult(
                stop_id=stop.id,
                triggered=False,
                status=stop.status,
                attempts_executed=0,
                schedule_offsets_seconds=(),
                execution_order_id=stop.execution_order_id,
                idempotency_key=stop.idempotency_key,
                last_error=None,
            )

        # Compare-and-set transition ARMED -> TRIGGERED
        stop.status = SyntheticStopStatus.TRIGGERED.value
        stop.triggered_at = now
        stop.version += 1
        stop.updated_at = now
        await session.flush()

        await record_audit_log(
            session,
            actor_role="SYSTEM",
            action=OutboxEventType.STOP_TRIGGERED.value,
            target_type="SYNTHETIC_STOP",
            target_id=stop.id,
            before_json={"status": SyntheticStopStatus.ARMED.value},
            after_json={"status": stop.status},
            reason_code="STOP_PRICE_BREACHED",
            detail_json={
                "symbol": stop.symbol,
                "current_price": str(resolved_price),
                "stop_price": str(stop.stop_price),
                "quantity": str(stop.quantity),
                "idempotency_key": stop.idempotency_key,
            },
        )
        await self._outbox.enqueue_event(
            session,
            event_type=OutboxEventType.STOP_TRIGGERED.value,
            aggregate_type="SYNTHETIC_STOP",
            aggregate_id=stop.id,
            payload={
                "stop_id": str(stop.id),
                "position_id": str(position.id),
                "symbol": stop.symbol,
                "current_price": str(resolved_price),
                "stop_price": str(stop.stop_price),
            },
        )

        return await self._submit_stop_with_retries(
            session=session,
            stop=stop,
            position=position,
            sleep_fn=sleep_fn,
        )

    async def _submit_stop_with_retries(
        self,
        *,
        session: AsyncSession,
        stop: SyntheticStop,
        position: Position,
        sleep_fn: Callable[[float], Awaitable[None]],
    ) -> StopExecutionResult:
        """Execute triggered stop with idempotent order check and 0s/5s/15s retry schedule."""
        executed_offsets: list[int] = []
        previous_offset = 0
        last_error: str | None = None
        client_order_id = stop.idempotency_key

        for idx, offset_seconds in enumerate(STOP_RETRY_SCHEDULE_SECONDS, start=1):
            wait_delta = offset_seconds - previous_offset
            if wait_delta > 0:
                await sleep_fn(float(wait_delta))
            previous_offset = offset_seconds
            executed_offsets.append(offset_seconds)

            attempt_time = datetime.now(UTC)
            stop.status = SyntheticStopStatus.SUBMITTING.value
            stop.attempt_count += 1
            stop.version += 1
            stop.updated_at = attempt_time
            await session.flush()

            try:
                # Duplicate prevention: check DB first, then exchange adapter
                existing_order = await session.scalar(
                    select(Order).where(Order.idempotency_key == client_order_id).with_for_update()
                )
                receipt: ExchangeOrderReceipt | None = None
                if existing_order is not None:
                    receipt = await self.exchange_adapter.get_order_status(client_order_id)

                if receipt is None:
                    receipt = await self.exchange_adapter.place_order(
                        symbol=stop.symbol,
                        side="SELL",
                        order_type="MARKET",
                        quantity=Decimal(str(stop.quantity)),
                        client_order_id=client_order_id,
                    )

                stop.status = SyntheticStopStatus.SUBMITTED.value
                stop.version += 1
                stop.updated_at = attempt_time
                await session.flush()

                fill_price = receipt.average_fill_price or Decimal(str(stop.stop_price))
                if existing_order is None:
                    exec_order = Order(
                        id=uuid.uuid4(),
                        client_order_id=client_order_id,
                        signal_id=None,
                        strategy_id=position.strategy_id,
                        exchange_account_id=position.exchange_account_id,
                        symbol=stop.symbol,
                        side="SELL",
                        order_type="MARKET",
                        quantity=Decimal(str(stop.quantity)),
                        limit_price=None,
                        filled_quantity=receipt.filled_quantity,
                        average_fill_price=fill_price,
                        status=OrderState.FILLED.value,
                        state_machine_state=OrderState.FILLED.value,
                        risk_decision=RiskDecisionStatus.APPROVE.value,
                        risk_reason_codes=[],
                        idempotency_key=client_order_id,
                        expires_at=None,
                        created_at=attempt_time,
                        updated_at=attempt_time,
                        version=1,
                    )
                    session.add(exec_order)
                    await session.flush()

                    trade = Trade(
                        id=uuid.uuid4(),
                        order_id=exec_order.id,
                        position_id=position.id,
                        exchange_trade_id=receipt.exchange_order_id,
                        fill_price=fill_price,
                        fill_quantity=receipt.filled_quantity,
                        fee=receipt.fee,
                        executed_at=receipt.executed_at,
                        created_at=attempt_time,
                    )
                    session.add(trade)
                    await session.flush()
                    ORDERS_TOTAL.labels(
                        symbol=stop.symbol, side="SELL", status=OrderState.FILLED.value
                    ).inc()
                else:
                    exec_order = existing_order

                stop.execution_order_id = exec_order.id
                stop.status = SyntheticStopStatus.EXECUTED.value
                stop.executed_at = attempt_time
                stop.last_error = None
                stop.version += 1
                stop.updated_at = attempt_time

                gross_pnl = (fill_price - Decimal(str(position.entry_price))) * Decimal(
                    str(stop.quantity)
                )
                position.realized_pnl = gross_pnl - receipt.fee
                position.unrealized_pnl = Decimal("0")
                position.mark_price = fill_price
                position.status = PositionStatus.CLOSED.value
                position.version += 1
                position.updated_at = attempt_time
                await session.flush()

                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action=OutboxEventType.STOP_EXECUTED.value,
                    target_type="SYNTHETIC_STOP",
                    target_id=stop.id,
                    before_json={"status": SyntheticStopStatus.SUBMITTED.value},
                    after_json={
                        "status": stop.status,
                        "execution_order_id": str(exec_order.id),
                    },
                    reason_code="STOP_EXECUTED",
                    detail_json={
                        "attempt_number": idx,
                        "scheduled_offset_seconds": offset_seconds,
                        "idempotency_key": client_order_id,
                        "fill_price": str(fill_price),
                        "realized_pnl": str(position.realized_pnl),
                    },
                )
                await self._outbox.enqueue_event(
                    session,
                    event_type=OutboxEventType.STOP_EXECUTED.value,
                    aggregate_type="SYNTHETIC_STOP",
                    aggregate_id=stop.id,
                    payload={
                        "stop_id": str(stop.id),
                        "position_id": str(position.id),
                        "execution_order_id": str(exec_order.id),
                        "fill_price": str(fill_price),
                    },
                )
                await self._outbox.enqueue_event(
                    session,
                    event_type=OutboxEventType.POSITION_CLOSED.value,
                    aggregate_type="POSITION",
                    aggregate_id=position.id,
                    payload={
                        "position_id": str(position.id),
                        "symbol": position.symbol,
                        "realized_pnl": str(position.realized_pnl),
                    },
                )
                return StopExecutionResult(
                    stop_id=stop.id,
                    triggered=True,
                    status=stop.status,
                    attempts_executed=idx,
                    schedule_offsets_seconds=tuple(executed_offsets),
                    execution_order_id=exec_order.id,
                    idempotency_key=client_order_id,
                    last_error=None,
                )
            except Exception as exc:
                last_error = str(exc) or type(exc).__name__
                stop.status = SyntheticStopStatus.FAILED.value
                stop.last_error = last_error
                stop.version += 1
                stop.updated_at = datetime.now(UTC)
                await session.flush()

                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="SYNTHETIC_STOP_ATTEMPT_FAILED",
                    target_type="SYNTHETIC_STOP",
                    target_id=stop.id,
                    reason_code="STOP_SUBMISSION_FAILED",
                    detail_json={
                        "attempt_number": idx,
                        "scheduled_offset_seconds": offset_seconds,
                        "idempotency_key": client_order_id,
                        "error": last_error,
                    },
                )

        # Final failure after 0s, 5s, 15s -> MANUAL_REVIEW (§12.2)
        final_time = datetime.now(UTC)
        stop.status = SyntheticStopStatus.MANUAL_REVIEW.value
        stop.last_error = last_error
        stop.version += 1
        stop.updated_at = final_time
        position.status = PositionStatus.MANUAL_REVIEW.value
        position.version += 1
        position.updated_at = final_time
        await session.flush()

        SYNTHETIC_STOP_FAILURES_TOTAL.labels(symbol=stop.symbol).inc()

        await record_audit_log(
            session,
            actor_role="SYSTEM",
            action="SYNTHETIC_STOP_MANUAL_REVIEW",
            target_type="SYNTHETIC_STOP",
            target_id=stop.id,
            before_json={"status": SyntheticStopStatus.FAILED.value},
            after_json={"status": stop.status},
            reason_code="STOP_RETRIES_EXHAUSTED",
            detail_json={
                "attempts_executed": len(executed_offsets),
                "schedule_offsets_seconds": executed_offsets,
                "idempotency_key": client_order_id,
                "last_error": last_error,
            },
        )
        if self._notifier is not None:
            await self._notifier.send_alert(
                severity="CRITICAL",
                title="Synthetic Stop Failed — Manual Review Required",
                message=(
                    f"Synthetic stop {stop.id} for position {position.id} ({stop.symbol}) "
                    f"failed after {len(executed_offsets)} attempts (0s, 5s, 15s)."
                ),
                metadata={
                    "stop_id": str(stop.id),
                    "position_id": str(position.id),
                    "last_error": last_error,
                },
            )

        return StopExecutionResult(
            stop_id=stop.id,
            triggered=True,
            status=stop.status,
            attempts_executed=len(executed_offsets),
            schedule_offsets_seconds=tuple(executed_offsets),
            execution_order_id=stop.execution_order_id,
            idempotency_key=client_order_id,
            last_error=last_error,
        )

    async def monitor_armed_stops(
        self,
        session: AsyncSession,
        *,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> list[StopExecutionResult]:
        """Poll all active positions with ARMED stops and trigger any that breached stop_price."""
        stmt = (
            select(SyntheticStop.id)
            .join(Position, Position.id == SyntheticStop.position_id)
            .where(
                Position.status == PositionStatus.OPEN.value,
                SyntheticStop.status == SyntheticStopStatus.ARMED.value,
            )
            .order_by(SyntheticStop.created_at.asc())
        )
        stop_ids = list((await session.scalars(stmt)).all())
        results: list[StopExecutionResult] = []
        for sid in stop_ids:
            res = await self.evaluate_and_execute_stop(
                session,
                stop_id=sid,
                sleep_fn=sleep_fn,
            )
            results.append(res)
        return results

    async def reconcile_stops_after_restart(
        self,
        session: AsyncSession,
    ) -> list[SyntheticStop]:
        """Recover and reconcile active Synthetic Stops from PostgreSQL on restart."""
        active_stops = await self.load_active_stops_from_db(session)
        now = datetime.now(UTC)

        for stop in active_stops:
            position = await session.scalar(
                select(Position).where(Position.id == stop.position_id).with_for_update()
            )
            if position is None or position.status != PositionStatus.OPEN.value:
                continue

            # Check if an execution order was already filled on the exchange during downtime
            receipt = await self.exchange_adapter.get_order_status(stop.idempotency_key)
            if receipt is not None and receipt.status == "FILLED":
                existing_order = await session.scalar(
                    select(Order)
                    .where(Order.idempotency_key == stop.idempotency_key)
                    .with_for_update()
                )
                if existing_order is None:
                    existing_order = Order(
                        id=uuid.uuid4(),
                        client_order_id=stop.idempotency_key,
                        signal_id=None,
                        strategy_id=position.strategy_id,
                        exchange_account_id=position.exchange_account_id,
                        symbol=stop.symbol,
                        side="SELL",
                        order_type="MARKET",
                        quantity=Decimal(str(stop.quantity)),
                        limit_price=None,
                        filled_quantity=receipt.filled_quantity,
                        average_fill_price=receipt.average_fill_price,
                        status=OrderState.FILLED.value,
                        state_machine_state=OrderState.FILLED.value,
                        risk_decision=RiskDecisionStatus.APPROVE.value,
                        risk_reason_codes=[],
                        idempotency_key=stop.idempotency_key,
                        created_at=now,
                        updated_at=now,
                        version=1,
                    )
                    session.add(existing_order)
                    await session.flush()

                stop.execution_order_id = existing_order.id
                stop.status = SyntheticStopStatus.EXECUTED.value
                stop.executed_at = receipt.executed_at
                stop.version += 1
                stop.updated_at = now

                position.status = PositionStatus.CLOSED.value
                position.version += 1
                position.updated_at = now
                await session.flush()

                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="SYNTHETIC_STOP_RECONCILED",
                    target_type="SYNTHETIC_STOP",
                    target_id=stop.id,
                    after_json={
                        "status": stop.status,
                        "reconciled_state": SyntheticStopStatus.RECONCILED.value,
                        "execution_order_id": str(existing_order.id),
                    },
                    reason_code="RECONCILED_FILLED_ON_EXCHANGE",
                )
            elif stop.status in (
                SyntheticStopStatus.TRIGGERED.value,
                SyntheticStopStatus.SUBMITTING.value,
            ):
                # Re-arm in-flight stop that was never submitted to exchange before restart
                stop.status = SyntheticStopStatus.ARMED.value
                stop.version += 1
                stop.updated_at = now
                await session.flush()
                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="SYNTHETIC_STOP_RECONCILED",
                    target_type="SYNTHETIC_STOP",
                    target_id=stop.id,
                    after_json={"status": stop.status},
                    reason_code="REARMED_AFTER_RESTART",
                )
            else:
                stop.last_checked_at = now
                stop.updated_at = now
                await session.flush()

        return active_stops
