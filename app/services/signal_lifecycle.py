"""Signal Lifecycle State Machine and Signal-to-Order Handoff service for Phase F3 (§5, §8 & §9)."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import (
    OrderState,
    OutboxEventType,
    RiskDecisionStatus,
    SignalApprovalStatus,
)
from app.core.errors import (
    ConflictError,
    IdempotencyConflictError,
    InvalidRequestError,
    InvalidStateError,
    PriceDriftExpiredError,
    SignalExpiredError,
)
from app.db.models.exchange_account import ExchangeAccount
from app.db.models.order import Order
from app.db.models.signal import Signal
from app.db.models.system_state import SystemState
from app.db.repositories.signal_repository import SignalRepository
from app.integrations.exchange.base import ExchangeAdapter
from app.services.approval_timeout import (
    calculate_price_drift,
    compute_effective_timeout,
)
from app.services.kill_switch import KillSwitchService
from app.services.outbox import OutboxService, record_audit_log
from app.services.risk_engine import (
    MAX_RISK_PER_TRADE,
    RiskEngine,
    RiskEvaluationDecision,
    RiskEvaluationInput,
)
from app.services.state_machine import ALLOWED_SIGNAL_TRANSITIONS
from app.services.trend_following_rule import ensure_utc_datetime

TERMINAL_ORDER_STATES: frozenset[str] = frozenset(
    {
        OrderState.REJECTED.value,
        OrderState.EXPIRED.value,
        OrderState.CANCELLED.value,
        OrderState.FAILED.value,
        OrderState.CLOSED.value,
    }
)


@dataclass(frozen=True)
class OrderDraft:
    """Deterministic order draft created from an APPROVED Signal prior to Risk Engine validation."""

    signal_id: uuid.UUID
    signal_code: str
    strategy_id: uuid.UUID
    exchange_account_id: uuid.UUID
    client_order_id: str
    idempotency_key: str
    symbol: str
    side: str
    direction: str
    order_type: str
    entry_price: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal | None
    atr_14: Decimal


@dataclass(frozen=True)
class SignalDecisionOutcome:
    """Result of an atomic signal approval/rejection and optional order handoff."""

    signal: Signal
    order: Order | None = None
    order_draft: OrderDraft | None = None
    risk_decision: RiskEvaluationDecision | None = None
    idempotent_replay: bool = False


def _build_idempotency_state_key(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.strip().encode("utf-8")).hexdigest()[:56]
    return f"IDEMP:{digest}"


def _build_request_fingerprint(
    *,
    action: str,
    signal_id: str,
    reason: str,
) -> str:
    canonical = json.dumps(
        {
            "action": action,
            "signal_id": signal_id,
            "reason": reason.strip(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SignalLifecycleService:
    """Transactional Signal Lifecycle and Signal-to-Order Handoff service (§5, §8, §9)."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        exchange_adapter: ExchangeAdapter | None = None,
        risk_engine: RiskEngine | None = None,
        outbox_service: OutboxService | None = None,
        kill_switch_service: KillSwitchService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._exchange = exchange_adapter
        self._risk_engine = risk_engine or RiskEngine()
        self._outbox = outbox_service or OutboxService(settings=self._settings)
        self._kill_switch = kill_switch_service or KillSwitchService()

    async def ensure_paper_exchange_account(
        self,
        session: AsyncSession,
    ) -> ExchangeAccount:
        """Return an active PAPER ExchangeAccount, creating the default one if none exists."""
        stmt = (
            select(ExchangeAccount)
            .where(
                ExchangeAccount.mode == "PAPER",
                ExchangeAccount.is_active.is_(True),
            )
            .order_by(ExchangeAccount.created_at.asc())
            .limit(1)
        )
        account = await session.scalar(stmt)
        if account is not None:
            return account

        account = ExchangeAccount(
            id=uuid.uuid4(),
            name=f"paper-default-{uuid.uuid4().hex[:8]}",
            exchange_name="paper_simulated",
            mode="PAPER",
            is_active=True,
        )
        session.add(account)
        await session.flush()
        return account

    def create_order_draft(
        self,
        signal: Signal,
        *,
        exchange_account_id: uuid.UUID,
        client_order_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> OrderDraft:
        """Create an OrderDraft linked to an APPROVED Signal (§9.1–§9.2)."""
        if signal.approval_status != SignalApprovalStatus.APPROVED.value:
            raise InvalidStateError(
                f"Cannot create order draft for signal in status '{signal.approval_status}'; "
                "signal must be APPROVED",
                details={
                    "signal_id": str(signal.id),
                    "approval_status": signal.approval_status,
                },
            )
        ref_price = Decimal(str(signal.reference_price))
        stop_price = Decimal(str(signal.stop_loss_price))
        stop_distance = max(Decimal("0.00000001"), ref_price - stop_price)
        atr_14 = max(Decimal("0.00000001"), stop_distance / Decimal("2"))

        resolved_idem = idempotency_key or f"ord-idem-{signal.id}"
        resolved_client_id = client_order_id or f"ord-{signal.id}"

        return OrderDraft(
            signal_id=signal.id,
            signal_code=signal.signal_id,
            strategy_id=signal.strategy_id,
            exchange_account_id=exchange_account_id,
            client_order_id=resolved_client_id,
            idempotency_key=resolved_idem,
            symbol=signal.symbol,
            side="BUY",
            direction=signal.direction,
            order_type="MARKET",
            entry_price=ref_price,
            stop_loss_price=stop_price,
            take_profit_price=(
                Decimal(str(signal.take_profit_price))
                if signal.take_profit_price is not None
                else None
            ),
            atr_14=atr_14,
        )

    async def handoff_signal_to_order(
        self,
        session: AsyncSession,
        *,
        signal: Signal,
        actor_role: str = "OPERATIONAL",
        actor_id: uuid.UUID | None = None,
        client_order_id: str | None = None,
        idempotency_key: str | None = None,
        approved_order_state: OrderState = OrderState.SUBMITTED,
        risk_input_overrides: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> tuple[Order, OrderDraft, RiskEvaluationDecision]:
        """Hand off an APPROVED Signal to the F2 Risk Engine and persist the resulting Order (§9).

        Rules enforced:
        - Signal must be APPROVED.
        - At most one active order per approved signal.
        - `client_order_id` and `idempotency_key` are unique.
        - Creation and risk decision are transactional.
        - Risk Engine remains final authority.
        - No real exchange call is made.
        """
        current_time = ensure_utc_datetime(now or datetime.now(UTC), "now")
        if signal.approval_status != SignalApprovalStatus.APPROVED.value:
            raise InvalidStateError(
                f"Signal {signal.id} must be APPROVED before order handoff",
                details={"signal_id": str(signal.id), "status": signal.approval_status},
            )

        if approved_order_state not in (OrderState.PRE_TRADE_VALIDATION, OrderState.SUBMITTED):
            raise InvalidRequestError(
                "approved_order_state must be PRE_TRADE_VALIDATION or SUBMITTED"
            )

        # Lock existing orders for this signal to prevent concurrent duplicate order creation
        existing_orders_stmt = select(Order).where(Order.signal_id == signal.id).with_for_update()
        existing_orders = list((await session.scalars(existing_orders_stmt)).all())
        active_orders = [
            o for o in existing_orders if o.state_machine_state not in TERMINAL_ORDER_STATES
        ]
        if active_orders:
            raise ConflictError(
                f"Signal '{signal.signal_id}' already has an active order",
                code="DUPLICATE_ORDER",
                details={
                    "signal_id": str(signal.id),
                    "active_order_id": str(active_orders[0].id),
                },
            )

        resolved_idem = idempotency_key or f"ord-idem-{signal.id}"
        resolved_client_id = client_order_id or f"ord-{signal.id}"

        dup_key_stmt = (
            select(Order)
            .where(
                (Order.idempotency_key == resolved_idem)
                | (Order.client_order_id == resolved_client_id)
            )
            .with_for_update()
        )
        dup_order = await session.scalar(dup_key_stmt)
        if dup_order is not None:
            raise ConflictError(
                "Duplicate order client_order_id or idempotency_key is prevented",
                code="DUPLICATE_ORDER",
                details={
                    "existing_order_id": str(dup_order.id),
                    "client_order_id": resolved_client_id,
                    "idempotency_key": resolved_idem,
                },
            )

        account = await self.ensure_paper_exchange_account(session)
        draft = self.create_order_draft(
            signal,
            exchange_account_id=account.id,
            client_order_id=resolved_client_id,
            idempotency_key=resolved_idem,
        )

        ks_state = await self._kill_switch.get_or_create_state(session, for_update=False)
        risk_kwargs: dict[str, Any] = {
            "symbol": draft.symbol,
            "direction": draft.direction,
            "entry_price": draft.entry_price,
            "atr_14": draft.atr_14,
            "equity": Decimal("10000.00"),
            "portfolio_value": Decimal("10000.00"),
            "available_cash": Decimal("10000.00"),
            "market_data_timestamp": current_time,
            "evaluation_timestamp": current_time,
            "risk_fraction": MAX_RISK_PER_TRADE,
            "exposure_multiplier": Decimal(str(ks_state.exposure_multiplier)),
            "kill_switch_active": ks_state.is_active,
        }
        if risk_input_overrides:
            risk_kwargs.update(risk_input_overrides)

        risk_input = RiskEvaluationInput(**risk_kwargs)
        decision = await self._risk_engine.evaluate_with_heartbeat(
            session,
            risk_input,
            now=current_time,
        )

        if decision.decision == RiskDecisionStatus.APPROVE and decision.sizing is not None:
            final_state = approved_order_state.value
            order = Order(
                id=uuid.uuid4(),
                client_order_id=draft.client_order_id,
                signal_id=signal.id,
                strategy_id=draft.strategy_id,
                exchange_account_id=draft.exchange_account_id,
                symbol=draft.symbol,
                side=draft.side,
                order_type=draft.order_type,
                quantity=decision.sizing.final_quantity,
                limit_price=draft.entry_price,
                filled_quantity=Decimal("0"),
                average_fill_price=None,
                status=final_state,
                state_machine_state=final_state,
                risk_decision=RiskDecisionStatus.APPROVE.value,
                risk_reason_codes=[],
                idempotency_key=draft.idempotency_key,
                expires_at=None,
                created_at=current_time,
                updated_at=current_time,
                version=1,
            )
            session.add(order)
            await session.flush()

            approved_payload = {
                "order_id": str(order.id),
                "client_order_id": order.client_order_id,
                "signal_id": str(signal.id),
                "signal_code": signal.signal_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": str(order.quantity),
                "limit_price": str(order.limit_price) if order.limit_price is not None else None,
                "status": order.status,
                "state_machine_state": order.state_machine_state,
                "risk_decision": order.risk_decision,
            }
            await record_audit_log(
                session,
                actor_id=actor_id,
                actor_role=actor_role,
                action=OutboxEventType.ORDER_CREATED.value,
                target_type="ORDER",
                target_id=order.id,
                before_json=None,
                after_json={
                    "status": order.status,
                    "state_machine_state": order.state_machine_state,
                    "risk_decision": order.risk_decision,
                },
                reason_code="RISK_APPROVED",
                detail_json=approved_payload,
            )
            await self._outbox.enqueue_event(
                session,
                event_type=OutboxEventType.ORDER_CREATED.value,
                aggregate_type="ORDER",
                aggregate_id=order.id,
                payload=approved_payload,
            )
            return order, draft, decision

        # Risk Engine rejected: retain APPROVED signal and create risk-rejected order (§9.5)
        rejected_order = Order(
            id=uuid.uuid4(),
            client_order_id=draft.client_order_id,
            signal_id=signal.id,
            strategy_id=draft.strategy_id,
            exchange_account_id=draft.exchange_account_id,
            symbol=draft.symbol,
            side=draft.side,
            order_type=draft.order_type,
            quantity=Decimal("0"),
            limit_price=draft.entry_price,
            filled_quantity=Decimal("0"),
            average_fill_price=None,
            status=OrderState.REJECTED.value,
            state_machine_state=OrderState.REJECTED.value,
            risk_decision=RiskDecisionStatus.REJECT.value,
            risk_reason_codes=list(decision.reason_codes),
            idempotency_key=draft.idempotency_key,
            expires_at=None,
            created_at=current_time,
            updated_at=current_time,
            version=1,
        )
        session.add(rejected_order)
        await session.flush()

        rejected_payload = {
            "order_id": str(rejected_order.id),
            "client_order_id": rejected_order.client_order_id,
            "signal_id": str(signal.id),
            "signal_code": signal.signal_id,
            "symbol": rejected_order.symbol,
            "status": rejected_order.status,
            "state_machine_state": rejected_order.state_machine_state,
            "risk_decision": rejected_order.risk_decision,
            "reason_codes": list(decision.reason_codes),
        }
        primary_reason = decision.reason_codes[0] if decision.reason_codes else "RISK_REJECTED"
        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=actor_role,
            action=OutboxEventType.ORDER_REJECTED_BY_RISK.value,
            target_type="ORDER",
            target_id=rejected_order.id,
            before_json=None,
            after_json={
                "status": rejected_order.status,
                "state_machine_state": rejected_order.state_machine_state,
                "risk_decision": rejected_order.risk_decision,
                "risk_reason_codes": list(decision.reason_codes),
            },
            reason_code=primary_reason,
            detail_json=rejected_payload,
        )
        await self._outbox.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_REJECTED_BY_RISK.value,
            aggregate_type="ORDER",
            aggregate_id=rejected_order.id,
            payload=rejected_payload,
        )
        return rejected_order, draft, decision

    async def transition_signal(
        self,
        session: AsyncSession,
        *,
        signal_id: uuid.UUID | str,
        target_status: SignalApprovalStatus,
        reason: str,
        actor_role: str = "OPERATIONAL",
        actor_id: uuid.UUID | None = None,
        current_price: Decimal | None = None,
        ips_timeout_minutes: int | None = None,
        now: datetime | None = None,
    ) -> Signal:
        """Atomically transition a Signal state with SELECT ... FOR UPDATE (§5.1–§5.3).

        If any validation fails, no state change, audit record, or Outbox event is written.
        """
        current_time = ensure_utc_datetime(now or datetime.now(UTC), "now")
        repo = SignalRepository(session)
        signal = await repo.get_by_id_or_raise(signal_id, for_update=True)

        current_status = SignalApprovalStatus(signal.approval_status)

        if target_status == SignalApprovalStatus.APPROVED:
            if current_status == SignalApprovalStatus.EXPIRED:
                raise SignalExpiredError(
                    f"Signal '{signal.signal_id}' is already EXPIRED and cannot be approved",
                    details={
                        "signal_id": str(signal.id),
                        "approval_status": current_status.value,
                    },
                )
            if current_status == SignalApprovalStatus.PRICE_DRIFT_EXPIRED:
                raise PriceDriftExpiredError(
                    f"Signal '{signal.signal_id}' is already PRICE_DRIFT_EXPIRED",
                    details={
                        "signal_id": str(signal.id),
                        "approval_status": current_status.value,
                    },
                )

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

        if target_status == SignalApprovalStatus.APPROVED:
            effective_timeout = compute_effective_timeout(
                timeframe=signal.timeframe,
                ips_timeout_minutes=ips_timeout_minutes,
            )
            effective_expires_at = min(
                signal.approval_expires_at,
                signal.created_at + effective_timeout,
            )
            elapsed = current_time - signal.created_at
            if current_time >= effective_expires_at or elapsed > effective_timeout:
                raise SignalExpiredError(
                    f"Signal '{signal.signal_id}' has expired and cannot be approved",
                    details={
                        "signal_id": str(signal.id),
                        "approval_expires_at": effective_expires_at.isoformat(),
                        "current_time": current_time.isoformat(),
                    },
                )

            resolved_price = current_price
            if resolved_price is None and self._exchange is not None:
                try:
                    ticker = await self._exchange.get_ticker(signal.symbol)
                    resolved_price = ticker.price
                except Exception:
                    resolved_price = None

            if resolved_price is not None:
                drift = calculate_price_drift(
                    current_price=resolved_price,
                    reference_price=Decimal(str(signal.reference_price)),
                )
                threshold = self._settings.PRICE_DRIFT_EXPIRY_THRESHOLD
                if drift > threshold:
                    raise PriceDriftExpiredError(
                        f"Signal '{signal.signal_id}' drift {drift} > threshold {threshold}",
                        details={
                            "signal_id": str(signal.id),
                            "reference_price": str(signal.reference_price),
                            "current_price": str(resolved_price),
                            "price_drift": str(drift),
                            "threshold": str(threshold),
                        },
                    )

        before_status = signal.approval_status
        signal.approval_status = target_status.value
        signal.version += 1
        signal.updated_at = current_time
        await session.flush()

        event_map = {
            SignalApprovalStatus.APPROVED: OutboxEventType.SIGNAL_APPROVED.value,
            SignalApprovalStatus.REJECTED: OutboxEventType.SIGNAL_REJECTED.value,
            SignalApprovalStatus.EXPIRED: OutboxEventType.SIGNAL_EXPIRED.value,
            SignalApprovalStatus.PRICE_DRIFT_EXPIRED: (
                OutboxEventType.SIGNAL_PRICE_DRIFT_EXPIRED.value
            ),
        }
        event_type = event_map[target_status]

        detail_payload: dict[str, Any] = {
            "signal_id": str(signal.id),
            "signal_code": signal.signal_id,
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "from_status": before_status,
            "to_status": signal.approval_status,
            "reason": reason,
            "version": signal.version,
        }
        if current_price is not None:
            detail_payload["current_price"] = str(current_price)
            detail_payload["reference_price"] = str(signal.reference_price)

        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=actor_role,
            action=event_type,
            target_type="SIGNAL",
            target_id=signal.id,
            before_json={"approval_status": before_status, "version": signal.version - 1},
            after_json={"approval_status": signal.approval_status, "version": signal.version},
            reason_code=target_status.value,
            detail_json=detail_payload,
        )

        await self._outbox.enqueue_event(
            session,
            event_type=event_type,
            aggregate_type="SIGNAL",
            aggregate_id=signal.id,
            payload=detail_payload,
        )
        return signal

    async def approve_signal(
        self,
        session: AsyncSession,
        *,
        signal_id: uuid.UUID | str,
        reason: str,
        actor_role: str = "OPERATIONAL",
        actor_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        current_price: Decimal | None = None,
        ips_timeout_minutes: int | None = None,
        perform_handoff: bool = True,
        approved_order_state: OrderState = OrderState.SUBMITTED,
        risk_input_overrides: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> SignalDecisionOutcome:
        """Approve a PENDING_APPROVAL Signal and hand off to F2 Risk Engine atomically."""
        if not reason or not reason.strip():
            raise InvalidRequestError("Approval reason is required")

        repo = SignalRepository(session)
        signal_peek = await repo.get_by_id_or_raise(signal_id, for_update=True)
        fingerprint = _build_request_fingerprint(
            action="APPROVE",
            signal_id=str(signal_peek.id),
            reason=reason,
        )

        if idempotency_key is not None:
            if not idempotency_key.strip():
                raise InvalidRequestError("Idempotency-Key header cannot be empty")
            state_key = _build_idempotency_state_key(idempotency_key)
            existing_idem = await session.scalar(
                select(SystemState).where(SystemState.state_key == state_key).with_for_update()
            )
            if existing_idem is not None:
                stored_fp = existing_idem.metadata_json.get("fingerprint")
                if stored_fp != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used with a different request payload",
                        details={
                            "idempotency_key": idempotency_key,
                            "signal_id": str(signal_peek.id),
                        },
                    )
                existing_order: Order | None = None
                stored_order_id = existing_idem.metadata_json.get("order_id")
                if stored_order_id:
                    existing_order = await session.scalar(
                        select(Order).where(Order.id == uuid.UUID(str(stored_order_id)))
                    )
                return SignalDecisionOutcome(
                    signal=signal_peek,
                    order=existing_order,
                    order_draft=None,
                    risk_decision=None,
                    idempotent_replay=True,
                )

        signal = await self.transition_signal(
            session,
            signal_id=signal_peek.id,
            target_status=SignalApprovalStatus.APPROVED,
            reason=reason,
            actor_role=actor_role,
            actor_id=actor_id,
            current_price=current_price,
            ips_timeout_minutes=ips_timeout_minutes,
            now=now,
        )

        order: Order | None = None
        draft: OrderDraft | None = None
        decision: RiskEvaluationDecision | None = None

        if perform_handoff:
            order, draft, decision = await self.handoff_signal_to_order(
                session,
                signal=signal,
                actor_role=actor_role,
                actor_id=actor_id,
                idempotency_key=idempotency_key or f"ord-idem-{signal.id}",
                approved_order_state=approved_order_state,
                risk_input_overrides=risk_input_overrides,
                now=now,
            )

        if idempotency_key is not None:
            state_key = _build_idempotency_state_key(idempotency_key)
            idem_record = SystemState(
                id=uuid.uuid4(),
                state_key=state_key,
                metadata_json={
                    "idempotency_key": idempotency_key,
                    "action": "APPROVE",
                    "signal_id": str(signal.id),
                    "reason": reason.strip(),
                    "fingerprint": fingerprint,
                    "order_id": str(order.id) if order is not None else None,
                },
                version=1,
            )
            session.add(idem_record)
            await session.flush()

        return SignalDecisionOutcome(
            signal=signal,
            order=order,
            order_draft=draft,
            risk_decision=decision,
            idempotent_replay=False,
        )

    async def reject_signal(
        self,
        session: AsyncSession,
        *,
        signal_id: uuid.UUID | str,
        reason: str,
        actor_role: str = "OPERATIONAL",
        actor_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        now: datetime | None = None,
    ) -> SignalDecisionOutcome:
        """Reject a PENDING_APPROVAL Signal atomically with idempotency support."""
        if not reason or not reason.strip():
            raise InvalidRequestError("Rejection reason is required")

        repo = SignalRepository(session)
        signal_peek = await repo.get_by_id_or_raise(signal_id, for_update=True)
        fingerprint = _build_request_fingerprint(
            action="REJECT",
            signal_id=str(signal_peek.id),
            reason=reason,
        )

        if idempotency_key is not None:
            if not idempotency_key.strip():
                raise InvalidRequestError("Idempotency-Key header cannot be empty")
            state_key = _build_idempotency_state_key(idempotency_key)
            existing_idem = await session.scalar(
                select(SystemState).where(SystemState.state_key == state_key).with_for_update()
            )
            if existing_idem is not None:
                stored_fp = existing_idem.metadata_json.get("fingerprint")
                if stored_fp != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used with a different request payload",
                        details={
                            "idempotency_key": idempotency_key,
                            "signal_id": str(signal_peek.id),
                        },
                    )
                return SignalDecisionOutcome(
                    signal=signal_peek,
                    order=None,
                    order_draft=None,
                    risk_decision=None,
                    idempotent_replay=True,
                )

        signal = await self.transition_signal(
            session,
            signal_id=signal_peek.id,
            target_status=SignalApprovalStatus.REJECTED,
            reason=reason,
            actor_role=actor_role,
            actor_id=actor_id,
            now=now,
        )

        if idempotency_key is not None:
            state_key = _build_idempotency_state_key(idempotency_key)
            idem_record = SystemState(
                id=uuid.uuid4(),
                state_key=state_key,
                metadata_json={
                    "idempotency_key": idempotency_key,
                    "action": "REJECT",
                    "signal_id": str(signal.id),
                    "reason": reason.strip(),
                    "fingerprint": fingerprint,
                    "order_id": None,
                },
                version=1,
            )
            session.add(idem_record)
            await session.flush()

        return SignalDecisionOutcome(
            signal=signal,
            order=None,
            order_draft=None,
            risk_decision=None,
            idempotent_replay=False,
        )
