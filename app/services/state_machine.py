"""Signal Approval and Order State Machine service for MVP-0 (§9 & v4.3 §4)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    OrderState,
    OutboxEventType,
    PositionStatus,
    SignalApprovalStatus,
    SyntheticStopStatus,
)
from app.core.errors import InvalidStateError, NotFoundError
from app.core.metrics import ORDER_STATE_TRANSITIONS_TOTAL
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.signal import Signal
from app.db.models.synthetic_stop import SyntheticStop
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.outbox import OutboxService, record_audit_log

PROTECTION_RETRY_SCHEDULE_SECONDS: tuple[int, int, int] = (0, 5, 15)
PARTIAL_FILL_TIMEOUT_SECONDS: int = 60

ALLOWED_SIGNAL_TRANSITIONS: dict[SignalApprovalStatus, frozenset[SignalApprovalStatus]] = {
    SignalApprovalStatus.PENDING_APPROVAL: frozenset(
        {
            SignalApprovalStatus.APPROVED,
            SignalApprovalStatus.REJECTED,
            SignalApprovalStatus.EXPIRED,
            SignalApprovalStatus.PRICE_DRIFT_EXPIRED,
        }
    ),
    SignalApprovalStatus.APPROVED: frozenset(),
    SignalApprovalStatus.REJECTED: frozenset(),
    SignalApprovalStatus.EXPIRED: frozenset(),
    SignalApprovalStatus.PRICE_DRIFT_EXPIRED: frozenset(),
}

ALLOWED_ORDER_TRANSITIONS: dict[OrderState, frozenset[OrderState]] = {
    OrderState.SIGNAL_CREATED: frozenset(
        {
            OrderState.PENDING_APPROVAL,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.CANCELLED,
        }
    ),
    OrderState.PENDING_APPROVAL: frozenset(
        {
            OrderState.APPROVED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.CANCELLED,
        }
    ),
    OrderState.APPROVED: frozenset(
        {
            OrderState.PRE_TRADE_VALIDATION,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.CANCELLED,
        }
    ),
    OrderState.PRE_TRADE_VALIDATION: frozenset(
        {
            OrderState.SUBMITTED,
            OrderState.REJECTED,
            OrderState.FAILED,
            OrderState.CANCELLED,
        }
    ),
    OrderState.SUBMITTED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.FAILED,
            OrderState.REJECTED,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {
            OrderState.FILLED,
            OrderState.FILLED_PARTIAL,
            OrderState.PROTECTED,
            OrderState.PROTECTION_FAILED,
            OrderState.CANCEL_REMAINDER,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.FILLED_PARTIAL: frozenset(
        {
            OrderState.CANCEL_REMAINDER,
            OrderState.PROTECTED,
            OrderState.PROTECTION_FAILED,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.CANCEL_REMAINDER: frozenset(
        {
            OrderState.PROTECTED,
            OrderState.PROTECTION_FAILED,
            OrderState.CANCELLED,
            OrderState.CLOSED,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.FILLED: frozenset(
        {
            OrderState.PROTECTED,
            OrderState.PROTECTION_FAILED,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.PROTECTED: frozenset(
        {
            OrderState.CLOSED,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.PROTECTION_FAILED: frozenset(
        {
            OrderState.PROTECTED,
            OrderState.CANCEL_POSITION,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.CANCEL_POSITION: frozenset(
        {
            OrderState.CANCELLED,
            OrderState.MANUAL_REVIEW,
        }
    ),
    OrderState.CLOSED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
    OrderState.CANCELLED: frozenset(),
    OrderState.FAILED: frozenset(),
    OrderState.MANUAL_REVIEW: frozenset(),
}


@dataclass(frozen=True)
class ProtectionRetryOutcome:
    """Result of executing the 0s/5s/15s protection failure retry schedule."""

    order_id: uuid.UUID
    final_state: OrderState
    attempts_executed: int
    schedule_offsets_seconds: tuple[int, ...]
    idempotency_key: str
    last_error: str | None


class StateMachineService:
    """Transactional state machine manager for Signals and Orders in MVP-0."""

    def __init__(
        self,
        outbox_service: OutboxService | None = None,
        notifier: NotificationAdapter | None = None,
    ) -> None:
        self._outbox = outbox_service or OutboxService(notifier=notifier)
        self._notifier = notifier

    async def transition_signal_status(
        self,
        session: AsyncSession,
        *,
        signal_id: uuid.UUID,
        target_status: SignalApprovalStatus,
        actor_role: str = "SYSTEM",
        actor_id: uuid.UUID | None = None,
        reason_code: str | None = None,
        detail_json: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> Signal:
        """Atomically transition a Signal approval status using SELECT ... FOR UPDATE."""
        current_time = now or datetime.now(UTC)
        stmt = select(Signal).where(Signal.id == signal_id).with_for_update()
        signal = await session.scalar(stmt)
        if signal is None:
            raise NotFoundError(f"Signal {signal_id} not found")

        current_status = SignalApprovalStatus(signal.approval_status)
        allowed_targets = ALLOWED_SIGNAL_TRANSITIONS.get(current_status, frozenset())
        if target_status not in allowed_targets:
            raise InvalidStateError(
                f"Invalid signal transition from {current_status.value} to {target_status.value}",
                details={
                    "signal_id": str(signal.id),
                    "from_status": current_status.value,
                    "to_status": target_status.value,
                },
            )

        if (
            target_status == SignalApprovalStatus.APPROVED
            and current_time >= signal.approval_expires_at
        ):
            raise InvalidStateError(
                "Expired signal cannot be approved",
                details={
                    "signal_id": str(signal.id),
                    "approval_expires_at": signal.approval_expires_at.isoformat(),
                },
            )

        before_status = signal.approval_status
        signal.approval_status = target_status.value
        signal.version += 1
        signal.updated_at = current_time
        await session.flush()

        action_map = {
            SignalApprovalStatus.APPROVED: OutboxEventType.SIGNAL_APPROVED.value,
            SignalApprovalStatus.REJECTED: OutboxEventType.SIGNAL_REJECTED.value,
            SignalApprovalStatus.EXPIRED: OutboxEventType.SIGNAL_EXPIRED.value,
            SignalApprovalStatus.PRICE_DRIFT_EXPIRED: (
                OutboxEventType.SIGNAL_PRICE_DRIFT_EXPIRED.value
            ),
        }
        action_name = action_map.get(target_status, f"SIGNAL_{target_status.value}")

        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action_name,
            target_type="SIGNAL",
            target_id=signal.id,
            before_json={"approval_status": before_status, "version": signal.version - 1},
            after_json={"approval_status": signal.approval_status, "version": signal.version},
            reason_code=reason_code or target_status.value,
            detail_json=detail_json,
        )

        await self._outbox.enqueue_event(
            session,
            event_type=action_name,
            aggregate_type="SIGNAL",
            aggregate_id=signal.id,
            payload={
                "signal_id": signal.signal_id,
                "symbol": signal.symbol,
                "from_status": before_status,
                "to_status": signal.approval_status,
                "version": signal.version,
            },
        )
        return signal

    async def transition_order_state(
        self,
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        target_state: OrderState,
        actor_role: str = "SYSTEM",
        actor_id: uuid.UUID | None = None,
        reason_code: str | None = None,
        detail_json: dict[str, Any] | None = None,
        expected_from_state: OrderState | None = None,
        now: datetime | None = None,
    ) -> Order:
        """Atomically transition an Order state using SELECT ... FOR UPDATE."""
        current_time = now or datetime.now(UTC)
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        order = await session.scalar(stmt)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")

        current_state = OrderState(order.state_machine_state)
        if expected_from_state is not None and current_state != expected_from_state:
            raise InvalidStateError(
                f"Concurrent state modification detected: expected {expected_from_state.value}, "
                f"found {current_state.value}",
                details={
                    "order_id": str(order.id),
                    "expected_state": expected_from_state.value,
                    "actual_state": current_state.value,
                },
            )

        allowed_targets = ALLOWED_ORDER_TRANSITIONS.get(current_state, frozenset())
        if target_state not in allowed_targets:
            raise InvalidStateError(
                f"Invalid order transition from {current_state.value} to {target_state.value}",
                details={
                    "order_id": str(order.id),
                    "from_state": current_state.value,
                    "to_state": target_state.value,
                },
            )

        before_state = order.state_machine_state
        before_version = order.version
        order.state_machine_state = target_state.value
        order.status = target_state.value
        order.version += 1
        order.updated_at = current_time
        await session.flush()

        ORDER_STATE_TRANSITIONS_TOTAL.labels(
            from_state=before_state,
            to_state=target_state.value,
        ).inc()

        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=actor_role,
            action="ORDER_STATE_TRANSITION",
            target_type="ORDER",
            target_id=order.id,
            before_json={"state_machine_state": before_state, "version": before_version},
            after_json={
                "state_machine_state": order.state_machine_state,
                "version": order.version,
            },
            reason_code=reason_code or target_state.value,
            detail_json=detail_json,
        )
        return order

    async def handle_partial_fill_timeout(
        self,
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        exchange_adapter: ExchangeAdapter,
        stop_price: Decimal,
        timeframe: str = "1H",
        now: datetime | None = None,
    ) -> tuple[Order, Position, SyntheticStop]:
        """Protect filled portion immediately and cancel remainder on 60s partial-fill timeout."""
        current_time = now or datetime.now(UTC)
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        order = await session.scalar(stmt)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")

        if OrderState(order.state_machine_state) != OrderState.PARTIALLY_FILLED:
            raise InvalidStateError(
                f"Order {order_id} is not PARTIALLY_FILLED (found {order.state_machine_state})"
            )

        if order.filled_quantity <= Decimal("0") or order.filled_quantity >= order.quantity:
            raise InvalidStateError("Order does not have a valid partial fill quantity")

        unfilled_remainder = order.quantity - order.filled_quantity
        entry_price = order.average_fill_price or order.limit_price or Decimal("1")

        # 1. Immediately protect filled portion with Position + SyntheticStop
        existing_position = await session.scalar(
            select(Position).where(Position.order_id == order.id).with_for_update()
        )
        if existing_position is None:
            position = Position(
                id=uuid.uuid4(),
                order_id=order.id,
                strategy_id=order.strategy_id,
                exchange_account_id=order.exchange_account_id,
                symbol=order.symbol,
                side=order.side,
                size=order.filled_quantity,
                entry_price=entry_price,
                mark_price=entry_price,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                status=PositionStatus.OPEN.value,
                stop_price=stop_price,
                take_profit_state=None,
                created_at=current_time,
                updated_at=current_time,
                version=1,
            )
            session.add(position)
            await session.flush()
        else:
            position = existing_position
            position.size = order.filled_quantity
            position.stop_price = stop_price
            position.updated_at = current_time
            position.version += 1
            await session.flush()

        stop_idempotency_key = f"partial-fill-stop-{position.id}"
        existing_stop = await session.scalar(
            select(SyntheticStop)
            .where(SyntheticStop.idempotency_key == stop_idempotency_key)
            .with_for_update()
        )
        if existing_stop is None:
            stop = SyntheticStop(
                id=uuid.uuid4(),
                position_id=position.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.filled_quantity,
                stop_price=stop_price,
                timeframe=timeframe,
                status=SyntheticStopStatus.ARMED.value,
                idempotency_key=stop_idempotency_key,
                attempt_count=0,
                created_at=current_time,
                updated_at=current_time,
                version=1,
            )
            session.add(stop)
            await session.flush()
        else:
            stop = existing_stop

        # 2. Transition PARTIALLY_FILLED -> FILLED_PARTIAL -> CANCEL_REMAINDER
        await self.transition_order_state(
            session,
            order_id=order.id,
            target_state=OrderState.FILLED_PARTIAL,
            reason_code="PARTIAL_FILL_60S_TIMEOUT",
            detail_json={
                "filled_quantity": str(order.filled_quantity),
                "unfilled_remainder": str(unfilled_remainder),
                "timeout_seconds": PARTIAL_FILL_TIMEOUT_SECONDS,
            },
            now=current_time,
        )

        await exchange_adapter.cancel_order(order.client_order_id)

        order = await self.transition_order_state(
            session,
            order_id=order.id,
            target_state=OrderState.CANCEL_REMAINDER,
            reason_code="REMAINDER_CANCELLED",
            detail_json={
                "filled_quantity": str(order.filled_quantity),
                "cancelled_remainder_quantity": str(unfilled_remainder),
                "protected_stop_id": str(stop.id),
            },
            now=current_time,
        )
        return order, position, stop

    async def execute_protection_with_retry(
        self,
        session: AsyncSession,
        *,
        order_id: uuid.UUID,
        position_id: uuid.UUID,
        register_protection_fn: Callable[[str], Awaitable[SyntheticStop]],
        exchange_adapter: ExchangeAdapter | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> ProtectionRetryOutcome:
        """Execute fixed 0s/5s/15s protection retry schedule (§9.3 & v4.3 §4)."""
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        order = await session.scalar(stmt)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")

        if OrderState(order.state_machine_state) != OrderState.PROTECTION_FAILED:
            order = await self.transition_order_state(
                session,
                order_id=order.id,
                target_state=OrderState.PROTECTION_FAILED,
                reason_code="INITIAL_PROTECTION_FAILURE",
            )

        idempotency_key = f"protection-retry-{order_id}-{position_id}"
        last_error: str | None = None
        executed_offsets: list[int] = []
        previous_offset = 0

        for idx, offset_seconds in enumerate(PROTECTION_RETRY_SCHEDULE_SECONDS, start=1):
            wait_delta = offset_seconds - previous_offset
            if wait_delta > 0:
                await sleep_fn(float(wait_delta))
            previous_offset = offset_seconds
            executed_offsets.append(offset_seconds)

            try:
                stop = await register_protection_fn(idempotency_key)
                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="ORDER_PROTECTION_RETRY_ATTEMPT",
                    target_type="ORDER",
                    target_id=order.id,
                    reason_code="PROTECTION_RETRY_SUCCEEDED",
                    detail_json={
                        "attempt_number": idx,
                        "scheduled_offset_seconds": offset_seconds,
                        "idempotency_key": idempotency_key,
                        "synthetic_stop_id": str(stop.id),
                        "outcome": "SUCCESS",
                    },
                )
                order = await self.transition_order_state(
                    session,
                    order_id=order.id,
                    target_state=OrderState.PROTECTED,
                    reason_code="PROTECTION_RECOVERED",
                    detail_json={
                        "attempt_number": idx,
                        "scheduled_offset_seconds": offset_seconds,
                        "idempotency_key": idempotency_key,
                    },
                )
                return ProtectionRetryOutcome(
                    order_id=order.id,
                    final_state=OrderState(order.state_machine_state),
                    attempts_executed=idx,
                    schedule_offsets_seconds=tuple(executed_offsets),
                    idempotency_key=idempotency_key,
                    last_error=None,
                )
            except Exception as exc:
                last_error = str(exc) or type(exc).__name__
                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="ORDER_PROTECTION_RETRY_ATTEMPT",
                    target_type="ORDER",
                    target_id=order.id,
                    reason_code="PROTECTION_RETRY_FAILED",
                    detail_json={
                        "attempt_number": idx,
                        "scheduled_offset_seconds": offset_seconds,
                        "idempotency_key": idempotency_key,
                        "error": last_error,
                        "outcome": "FAILED",
                    },
                )

        # All 3 attempts failed -> transition to CANCEL_POSITION -> CANCELLED (or MANUAL_REVIEW)
        order = await self.transition_order_state(
            session,
            order_id=order.id,
            target_state=OrderState.CANCEL_POSITION,
            reason_code="PROTECTION_RETRIES_EXHAUSTED",
            detail_json={
                "attempts_executed": len(executed_offsets),
                "schedule_offsets_seconds": executed_offsets,
                "last_error": last_error,
            },
        )

        position = await session.scalar(
            select(Position).where(Position.id == position_id).with_for_update()
        )
        try:
            if (
                exchange_adapter is not None
                and position is not None
                and position.size > Decimal("0")
            ):
                await exchange_adapter.place_order(
                    symbol=order.symbol,
                    side="SELL",
                    order_type="MARKET",
                    quantity=position.size,
                    client_order_id=f"cancel-pos-{order.id}",
                )
            if position is not None:
                position.status = PositionStatus.CLOSED.value
                position.updated_at = datetime.now(UTC)
                position.version += 1
                await session.flush()

            order = await self.transition_order_state(
                session,
                order_id=order.id,
                target_state=OrderState.CANCELLED,
                reason_code="POSITION_CANCELLED_AFTER_PROTECTION_FAILURE",
                detail_json={
                    "attempts_executed": len(executed_offsets),
                    "schedule_offsets_seconds": executed_offsets,
                    "last_error": last_error,
                },
            )
        except Exception as cancel_exc:
            cancel_err = str(cancel_exc) or type(cancel_exc).__name__
            if position is not None:
                position.status = PositionStatus.MANUAL_REVIEW.value
                position.updated_at = datetime.now(UTC)
                position.version += 1
                await session.flush()

            order = await self.transition_order_state(
                session,
                order_id=order.id,
                target_state=OrderState.MANUAL_REVIEW,
                reason_code="CANCEL_POSITION_FAILED",
                detail_json={
                    "attempts_executed": len(executed_offsets),
                    "schedule_offsets_seconds": executed_offsets,
                    "protection_error": last_error,
                    "cancellation_error": cancel_err,
                },
            )
            if self._notifier is not None:
                await self._notifier.send_alert(
                    severity="CRITICAL",
                    title="Protection & Position Cancellation Failed",
                    message=(
                        f"Order {order.id} entered MANUAL_REVIEW after 3 protection "
                        f"failures and position cancellation failure."
                    ),
                    metadata={"order_id": str(order.id), "position_id": str(position_id)},
                )

        return ProtectionRetryOutcome(
            order_id=order.id,
            final_state=OrderState(order.state_machine_state),
            attempts_executed=len(executed_offsets),
            schedule_offsets_seconds=tuple(executed_offsets),
            idempotency_key=idempotency_key,
            last_error=last_error,
        )
