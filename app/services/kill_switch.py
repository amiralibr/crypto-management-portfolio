"""Persistent Kill Switch and Two-Person Approval Resume service for MVP-0 (§13 & v4.3 §2)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ApiRole,
    ApprovalRequestStatus,
    OrderState,
    OutboxEventType,
    PositionStatus,
    SyntheticStopStatus,
)
from app.core.errors import (
    ForbiddenError,
    InvalidRequestError,
    InvalidStateError,
    KillSwitchActiveError,
    KillSwitchConflictError,
    NotFoundError,
)
from app.core.metrics import (
    KILL_SWITCH_ACTIVE_GAUGE,
    KILL_SWITCH_RESUME_REQUESTS_APPROVED_TOTAL,
    KILL_SWITCH_RESUME_REQUESTS_PENDING_GAUGE,
)
from app.db.models.approval_request import ApprovalRequest
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.synthetic_stop import SyntheticStop
from app.db.models.system_state import SystemState
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.outbox import OutboxService, record_audit_log
from app.services.reconciliation import ReconciliationService
from app.services.state_machine import StateMachineService

KILL_SWITCH_STATE_KEY: str = "KILL_SWITCH"
RESUME_REQUEST_EXPIRY_HOURS: int = 24
REDUCED_EXPOSURE_MULTIPLIER: Decimal = Decimal("0.3000")


def _normalize_approval_role(role: ApiRole | str) -> str:
    """Normalize OPERATIONAL and OPERATOR to 'OPERATOR' and ADMIN to 'ADMIN'."""
    raw = role.value if isinstance(role, ApiRole) else str(role).upper().strip()
    if raw in ("OPERATIONAL", "OPERATOR"):
        return "OPERATOR"
    if raw == "ADMIN":
        return "ADMIN"
    raise InvalidRequestError(f"Unsupported approval role: {raw}")


def _validate_reason(reason: str, field_name: str = "reason") -> str:
    if not isinstance(reason, str):
        raise InvalidRequestError(f"{field_name} must be a string")
    cleaned = reason.strip()
    if len(cleaned) < 3 or len(cleaned) > 500:
        raise InvalidRequestError(f"{field_name} must be between 3 and 500 characters")
    return cleaned


@dataclass(frozen=True)
class KillSwitchActivationResult:
    """Result of activating the Kill Switch."""

    status: str  # "activated", "already_active", or "manual_review"
    is_active: bool
    resume_status: str | None
    timestamp: datetime
    cancelled_orders_count: int
    reconciled_partial_fills_count: int
    disabled_stops_count: int


class KillSwitchService:
    """Persistent PostgreSQL-backed Kill Switch and Two-Person Resume manager (§13)."""

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter | None = None,
        state_machine: StateMachineService | None = None,
        outbox_service: OutboxService | None = None,
        notifier: NotificationAdapter | None = None,
        reconciliation_service: ReconciliationService | None = None,
    ) -> None:
        self._exchange = exchange_adapter
        self._outbox = outbox_service or OutboxService(notifier=notifier)
        self._state_machine = state_machine or StateMachineService(
            outbox_service=self._outbox, notifier=notifier
        )
        self._notifier = notifier
        self._reconciliation = reconciliation_service

    async def get_or_create_state(
        self,
        session: AsyncSession,
        *,
        for_update: bool = False,
    ) -> SystemState:
        """Load the persistent KILL_SWITCH row from PostgreSQL (creating default if missing)."""
        stmt = select(SystemState).where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
        if for_update:
            stmt = stmt.with_for_update()
        state = await session.scalar(stmt)
        if state is None:
            now = datetime.now(UTC)
            state = SystemState(
                id=uuid.uuid4(),
                state_key=KILL_SWITCH_STATE_KEY,
                is_active=False,
                exposure_multiplier=Decimal("1.0000"),
                metadata_json={},
                created_at=now,
                updated_at=now,
                version=1,
            )
            session.add(state)
            await session.flush()
        KILL_SWITCH_ACTIVE_GAUGE.set(1.0 if state.is_active else 0.0)
        return state

    async def is_active(self, session: AsyncSession) -> bool:
        """Return True if Kill Switch is currently active in PostgreSQL."""
        state = await self.get_or_create_state(session, for_update=False)
        return bool(state.is_active)

    async def ensure_trading_allowed(self, session: AsyncSession) -> SystemState:
        """Fail-closed check blocking new order creation when Kill Switch is active."""
        state = await self.get_or_create_state(session, for_update=False)
        if state.is_active or state.resume_status == "MANUAL_REVIEW":
            raise KillSwitchActiveError(
                "Kill Switch is active; new orders are blocked",
                details={
                    "is_active": state.is_active,
                    "resume_status": state.resume_status,
                    "activation_reason": state.activation_reason,
                },
            )
        return state

    async def set_reconciliation_status(
        self,
        session: AsyncSession,
        *,
        reconciliation_ok: bool,
        reason: str | None = None,
    ) -> SystemState:
        """Record reconciliation status on persistent Kill Switch state."""
        state = await self.get_or_create_state(session, for_update=True)
        meta = dict(state.metadata_json or {})
        meta["reconciliation_ok"] = reconciliation_ok
        if reason is not None:
            meta["reconciliation_note"] = reason
        state.metadata_json = meta
        if not reconciliation_ok and state.is_active:
            state.resume_status = "RECONCILIATION_FAILED"
        state.version += 1
        state.updated_at = datetime.now(UTC)
        await session.flush()
        return state

    async def activate(
        self,
        session: AsyncSession,
        *,
        reason: str,
        actor_role: ApiRole | str = ApiRole.ADMIN,
        activated_by: str = "admin",
        activation_source: str = "MANUAL_API",
        now: datetime | None = None,
    ) -> KillSwitchActivationResult:
        """Execute ordered 7-step Kill Switch activation procedure (§13.3 & v4.3 §2.3)."""
        role_str = actor_role.value if isinstance(actor_role, ApiRole) else str(actor_role)
        if role_str not in (ApiRole.ADMIN.value, "SYSTEM"):
            raise ForbiddenError("Admin API key required to activate Kill Switch")

        clean_reason = _validate_reason(reason, "reason")
        current_time = now or datetime.now(UTC)
        state = await self.get_or_create_state(session, for_update=True)

        # Idempotent check if already active and not in MANUAL_REVIEW
        if state.is_active and state.resume_status != "MANUAL_REVIEW":
            KILL_SWITCH_ACTIVE_GAUGE.set(1.0)
            return KillSwitchActivationResult(
                status="already_active",
                is_active=True,
                resume_status=state.resume_status,
                timestamp=current_time,
                cancelled_orders_count=0,
                reconciled_partial_fills_count=0,
                disabled_stops_count=0,
            )

        # Step 1: Freeze new order creation immediately
        state.is_active = True
        state.activated_at = current_time
        state.activated_by = activated_by
        state.activation_reason = clean_reason
        state.activation_source = activation_source
        state.resume_status = "ACTIVE"
        state.version += 1
        state.updated_at = current_time
        await session.flush()
        KILL_SWITCH_ACTIVE_GAUGE.set(1.0)

        cancelled_orders_count = 0
        reconciled_partial_fills_count = 0
        disabled_stops_count = 0
        step_errors: list[str] = []

        # Step 2: Cancel open orders if connector is available
        open_order_states = [
            OrderState.SIGNAL_CREATED.value,
            OrderState.PENDING_APPROVAL.value,
            OrderState.APPROVED.value,
            OrderState.PRE_TRADE_VALIDATION.value,
            OrderState.SUBMITTED.value,
        ]
        open_orders = list(
            (
                await session.scalars(
                    select(Order)
                    .where(Order.state_machine_state.in_(open_order_states))
                    .with_for_update()
                )
            ).all()
        )
        for order in open_orders:
            try:
                if (
                    order.state_machine_state == OrderState.SUBMITTED.value
                    and self._exchange is not None
                ):
                    await self._exchange.cancel_order(order.client_order_id)
                await self._state_machine.transition_order_state(
                    session,
                    order_id=order.id,
                    target_state=OrderState.CANCELLED,
                    actor_role="SYSTEM",
                    reason_code="KILL_SWITCH_ACTIVATED",
                    now=current_time,
                )
                cancelled_orders_count += 1
            except Exception as exc:
                err_msg = str(exc) or type(exc).__name__
                step_errors.append(f"cancel_order({order.id}): {err_msg}")
                order.state_machine_state = OrderState.MANUAL_REVIEW.value
                order.status = OrderState.MANUAL_REVIEW.value
                order.version += 1
                order.updated_at = current_time
                await session.flush()

        # Step 3: Reconcile partially filled orders
        partial_orders = list(
            (
                await session.scalars(
                    select(Order)
                    .where(Order.state_machine_state == OrderState.PARTIALLY_FILLED.value)
                    .with_for_update()
                )
            ).all()
        )
        for p_order in partial_orders:
            try:
                if self._exchange is not None:
                    entry_p = p_order.average_fill_price or p_order.limit_price or Decimal("100")
                    stop_p = entry_p * Decimal("0.98")
                    await self._state_machine.handle_partial_fill_timeout(
                        session,
                        order_id=p_order.id,
                        exchange_adapter=self._exchange,
                        stop_price=stop_p,
                        now=current_time,
                    )
                else:
                    await self._state_machine.transition_order_state(
                        session,
                        order_id=p_order.id,
                        target_state=OrderState.FILLED_PARTIAL,
                        actor_role="SYSTEM",
                        reason_code="KILL_SWITCH_PARTIAL_FILL_RECONCILE",
                        now=current_time,
                    )
                    await self._state_machine.transition_order_state(
                        session,
                        order_id=p_order.id,
                        target_state=OrderState.CANCEL_REMAINDER,
                        actor_role="SYSTEM",
                        reason_code="KILL_SWITCH_REMAINDER_CANCELLED",
                        now=current_time,
                    )
                reconciled_partial_fills_count += 1
            except Exception as exc:
                err_msg = str(exc) or type(exc).__name__
                step_errors.append(f"reconcile_partial_fill({p_order.id}): {err_msg}")
                p_order.state_machine_state = OrderState.MANUAL_REVIEW.value
                p_order.status = OrderState.MANUAL_REVIEW.value
                p_order.version += 1
                p_order.updated_at = current_time
                await session.flush()

        # Step 4: Apply position policy
        open_positions = list(
            (
                await session.scalars(
                    select(Position)
                    .where(Position.status == PositionStatus.OPEN.value)
                    .with_for_update()
                )
            ).all()
        )

        # Step 5: Disable active stop monitoring safely
        armed_stops = list(
            (
                await session.scalars(
                    select(SyntheticStop)
                    .where(SyntheticStop.status == SyntheticStopStatus.ARMED.value)
                    .with_for_update()
                )
            ).all()
        )
        disabled_stop_ids: list[str] = []
        for stop in armed_stops:
            stop.status = SyntheticStopStatus.CANCELLED.value
            stop.version += 1
            stop.updated_at = current_time
            disabled_stop_ids.append(str(stop.id))
            disabled_stops_count += 1
        await session.flush()

        meta: dict[str, Any] = dict(state.metadata_json or {})
        meta.update(
            {
                "cancelled_orders_count": cancelled_orders_count,
                "reconciled_partial_fills_count": reconciled_partial_fills_count,
                "open_positions_count": len(open_positions),
                "disabled_stop_ids": disabled_stop_ids,
                "reconciliation_ok": len(step_errors) == 0,
            }
        )
        if step_errors:
            state.resume_status = "MANUAL_REVIEW"
            meta["step_errors"] = step_errors
            final_status = "manual_review"
        else:
            final_status = "activated"

        state.metadata_json = meta
        state.updated_at = current_time
        await session.flush()

        # Step 6: Create audit record and outbox event
        detail_payload = {
            "reason": clean_reason,
            "activation_source": activation_source,
            "resume_status": state.resume_status,
            "cancelled_orders_count": cancelled_orders_count,
            "reconciled_partial_fills_count": reconciled_partial_fills_count,
            "disabled_stops_count": disabled_stops_count,
            "step_errors": step_errors,
        }
        await record_audit_log(
            session,
            actor_role=role_str,
            action=OutboxEventType.KILL_SWITCH_ACTIVATED.value,
            target_type="SYSTEM_STATE",
            target_id=state.id,
            before_json={"is_active": False},
            after_json={
                "is_active": True,
                "resume_status": state.resume_status,
            },
            reason_code="MANUAL_REVIEW" if step_errors else "KILL_SWITCH_ACTIVATED",
            detail_json=detail_payload,
        )
        await self._outbox.enqueue_event(
            session,
            event_type=OutboxEventType.KILL_SWITCH_ACTIVATED.value,
            aggregate_type="KILL_SWITCH",
            aggregate_id=state.id,
            payload=detail_payload,
        )

        # Step 7: Notify operator
        if self._notifier is not None:
            await self._notifier.send_alert(
                severity="CRITICAL",
                title="Kill Switch Activated",
                message=f"Kill Switch activated ({final_status}): {clean_reason}",
                metadata=detail_payload,
            )

        return KillSwitchActivationResult(
            status=final_status,
            is_active=True,
            resume_status=state.resume_status,
            timestamp=current_time,
            cancelled_orders_count=cancelled_orders_count,
            reconciled_partial_fills_count=reconciled_partial_fills_count,
            disabled_stops_count=disabled_stops_count,
        )

    async def create_resume_request(
        self,
        session: AsyncSession,
        *,
        requester_id: uuid.UUID,
        requester_role: ApiRole | str,
        reason: str,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        """Create a Two-Person Approval request for Kill Switch Resume (§13.4 & §13.6)."""
        norm_role = _normalize_approval_role(requester_role)
        if norm_role != "ADMIN":
            raise ForbiddenError("Only ADMIN can create a Kill Switch resume request")

        clean_reason = _validate_reason(reason, "reason")
        current_time = now or datetime.now(UTC)
        state = await self.get_or_create_state(session, for_update=True)

        if not state.is_active:
            raise KillSwitchConflictError("Kill Switch is not currently active")

        approval_req = ApprovalRequest(
            id=uuid.uuid4(),
            request_type="KILL_SWITCH_RESUME",
            target_type="SYSTEM_STATE",
            target_id=state.id,
            status=ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value,
            requested_by=requester_id,
            requested_by_role="ADMIN",
            first_approver_id=None,
            first_approver_role=None,
            first_approved_at=None,
            second_approver_id=None,
            second_approver_role=None,
            second_approved_at=None,
            reason=clean_reason,
            expires_at=current_time + timedelta(hours=RESUME_REQUEST_EXPIRY_HOURS),
            completed_at=None,
            created_at=current_time,
            updated_at=current_time,
            version=1,
        )
        session.add(approval_req)
        state.resume_status = ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value
        state.version += 1
        state.updated_at = current_time
        await session.flush()

        await self._refresh_resume_metrics(session)

        await record_audit_log(
            session,
            actor_id=requester_id,
            actor_role="ADMIN",
            action="KILL_SWITCH_RESUME_REQUESTED",
            target_type="APPROVAL_REQUEST",
            target_id=approval_req.id,
            after_json={
                "status": approval_req.status,
                "expires_at": approval_req.expires_at.isoformat(),
            },
            reason_code="RESUME_REQUEST_CREATED",
            detail_json={"reason": clean_reason},
        )
        return approval_req

    async def approve_resume_request(
        self,
        session: AsyncSession,
        *,
        request_id: uuid.UUID,
        approver_id: uuid.UUID,
        approver_role: ApiRole | str,
        now: datetime | None = None,
    ) -> tuple[ApprovalRequest, SystemState]:
        """Provide first or second approval for Kill Switch Resume (§13.4 & §13.5)."""
        norm_role = _normalize_approval_role(approver_role)
        current_time = now or datetime.now(UTC)

        req = await session.scalar(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id).with_for_update()
        )
        if req is None:
            raise NotFoundError(f"ApprovalRequest {request_id} not found")

        state = await self.get_or_create_state(session, for_update=True)

        # Check expiry first (§13.5: Request expires after 24 hours; expired cannot be approved)
        if req.status == ApprovalRequestStatus.EXPIRED.value or current_time >= req.expires_at:
            if req.status != ApprovalRequestStatus.EXPIRED.value:
                req.status = ApprovalRequestStatus.EXPIRED.value
                req.version += 1
                req.updated_at = current_time
                await session.flush()
                await self._refresh_resume_metrics(session)
                await record_audit_log(
                    session,
                    actor_id=approver_id,
                    actor_role=norm_role,
                    action="KILL_SWITCH_RESUME_REQUEST_EXPIRED",
                    target_type="APPROVAL_REQUEST",
                    target_id=req.id,
                    reason_code="RESUME_REQUEST_EXPIRED",
                )
            raise InvalidStateError(
                "Expired Kill Switch resume request cannot be approved",
                details={"request_id": str(req.id), "expires_at": req.expires_at.isoformat()},
            )

        if req.status not in (
            ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value,
            ApprovalRequestStatus.PENDING_SECOND_APPROVAL.value,
        ):
            raise InvalidStateError(
                f"Cannot approve resume request in status {req.status}",
                details={"request_id": str(req.id), "status": req.status},
            )

        # Rule: Requester cannot approve own request (§13.5)
        if approver_id == req.requested_by:
            raise ForbiddenError("Requester cannot approve their own Kill Switch resume request")

        # First approval
        if req.status == ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value:
            before_status = req.status
            req.first_approver_id = approver_id
            req.first_approver_role = norm_role
            req.first_approved_at = current_time
            req.status = ApprovalRequestStatus.PENDING_SECOND_APPROVAL.value
            req.version += 1
            req.updated_at = current_time

            state.resume_status = ApprovalRequestStatus.PENDING_SECOND_APPROVAL.value
            state.version += 1
            state.updated_at = current_time
            await session.flush()

            await record_audit_log(
                session,
                actor_id=approver_id,
                actor_role=norm_role,
                action="KILL_SWITCH_RESUME_FIRST_APPROVED",
                target_type="APPROVAL_REQUEST",
                target_id=req.id,
                before_json={"status": before_status},
                after_json={"status": req.status, "first_approver_role": norm_role},
                reason_code="FIRST_APPROVAL_GRANTED",
            )
            return req, state

        # Second approval
        if approver_id == req.first_approver_id:
            raise ForbiddenError("Same actor cannot approve a Kill Switch resume request twice")

        first_role_norm = _normalize_approval_role(req.first_approver_role or "")
        if {first_role_norm, norm_role} != {"ADMIN", "OPERATOR"}:
            raise ForbiddenError(
                "Kill Switch resume requires complementary ADMIN and OPERATOR approvals",
                details={
                    "first_approver_role": first_role_norm,
                    "second_approver_role": norm_role,
                },
            )

        # Check reconciliation before final resume (§13.5)
        meta = dict(state.metadata_json or {})
        if meta.get("reconciliation_ok") is False or state.resume_status in (
            "MANUAL_REVIEW",
            "RECONCILIATION_FAILED",
        ):
            raise KillSwitchConflictError(
                "Kill Switch resume is blocked because reconciliation has not succeeded",
                details={"resume_status": state.resume_status},
            )

        if self._reconciliation is not None:
            report = await self._reconciliation.reconcile_open_positions(session)
            if not report.success:
                meta["reconciliation_ok"] = False
                state.metadata_json = meta
                state.resume_status = "RECONCILIATION_FAILED"
                state.updated_at = current_time
                await session.flush()
                raise KillSwitchConflictError(
                    "Kill Switch resume blocked due to position reconciliation discrepancy",
                    details={"discrepancies": report.discrepancies},
                )

        before_req_status = req.status
        req.second_approver_id = approver_id
        req.second_approver_role = norm_role
        req.second_approved_at = current_time
        req.status = ApprovalRequestStatus.APPROVED.value
        req.completed_at = current_time
        req.version += 1
        req.updated_at = current_time

        # Resume Kill Switch with reduced exposure (30%) (§13.4 & §13.5)
        state.is_active = False
        state.resumed_at = current_time
        state.resumed_by = str(approver_id)
        state.resume_reason = req.reason
        state.resume_status = "RESUMED_REDUCED_EXPOSURE"
        state.exposure_multiplier = REDUCED_EXPOSURE_MULTIPLIER
        meta["reduced_exposure"] = True
        meta["exposure_multiplier"] = str(REDUCED_EXPOSURE_MULTIPLIER)
        meta["approved_request_id"] = str(req.id)
        state.metadata_json = meta
        state.version += 1
        state.updated_at = current_time
        await session.flush()

        KILL_SWITCH_ACTIVE_GAUGE.set(0.0)
        KILL_SWITCH_RESUME_REQUESTS_APPROVED_TOTAL.inc()
        await self._refresh_resume_metrics(session)

        await record_audit_log(
            session,
            actor_id=approver_id,
            actor_role=norm_role,
            action="KILL_SWITCH_RESUME_APPROVED",
            target_type="APPROVAL_REQUEST",
            target_id=req.id,
            before_json={"status": before_req_status},
            after_json={"status": req.status, "second_approver_role": norm_role},
            reason_code="SECOND_APPROVAL_GRANTED",
        )

        resume_payload = {
            "approval_request_id": str(req.id),
            "requested_by": str(req.requested_by),
            "first_approver_id": str(req.first_approver_id),
            "first_approver_role": req.first_approver_role,
            "second_approver_id": str(req.second_approver_id),
            "second_approver_role": req.second_approver_role,
            "exposure_multiplier": str(state.exposure_multiplier),
            "reason": req.reason,
        }
        await record_audit_log(
            session,
            actor_id=approver_id,
            actor_role=norm_role,
            action=OutboxEventType.KILL_SWITCH_RESUMED.value,
            target_type="SYSTEM_STATE",
            target_id=state.id,
            before_json={"is_active": True},
            after_json={
                "is_active": False,
                "resume_status": state.resume_status,
                "exposure_multiplier": str(state.exposure_multiplier),
            },
            reason_code="TWO_PERSON_APPROVAL_COMPLETED",
            detail_json=resume_payload,
        )
        await self._outbox.enqueue_event(
            session,
            event_type=OutboxEventType.KILL_SWITCH_RESUMED.value,
            aggregate_type="KILL_SWITCH",
            aggregate_id=state.id,
            payload=resume_payload,
        )
        if self._notifier is not None:
            await self._notifier.send_alert(
                severity="WARNING",
                title="Kill Switch Resumed (Reduced Exposure)",
                message=(
                    f"Kill Switch resumed after Two-Person Approval with "
                    f"exposure multiplier {state.exposure_multiplier}."
                ),
                metadata=resume_payload,
            )

        return req, state

    async def reject_resume_request(
        self,
        session: AsyncSession,
        *,
        request_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: ApiRole | str,
        reason: str = "Rejected by reviewer",
        now: datetime | None = None,
    ) -> ApprovalRequest:
        """Reject a pending Kill Switch Resume request (§13.6)."""
        norm_role = _normalize_approval_role(actor_role)
        current_time = now or datetime.now(UTC)

        req = await session.scalar(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id).with_for_update()
        )
        if req is None:
            raise NotFoundError(f"ApprovalRequest {request_id} not found")

        if req.status not in (
            ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value,
            ApprovalRequestStatus.PENDING_SECOND_APPROVAL.value,
        ):
            raise InvalidStateError(f"Cannot reject resume request in status {req.status}")

        before_status = req.status
        req.status = ApprovalRequestStatus.REJECTED.value
        req.completed_at = current_time
        req.version += 1
        req.updated_at = current_time
        await session.flush()

        await self._refresh_resume_metrics(session)

        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=norm_role,
            action="KILL_SWITCH_RESUME_REJECTED",
            target_type="APPROVAL_REQUEST",
            target_id=req.id,
            before_json={"status": before_status},
            after_json={"status": req.status},
            reason_code="RESUME_REQUEST_REJECTED",
            detail_json={"reason": reason},
        )
        return req

    async def get_resume_request(
        self,
        session: AsyncSession,
        *,
        request_id: uuid.UUID,
    ) -> ApprovalRequest:
        """Fetch an ApprovalRequest by ID."""
        req = await session.scalar(select(ApprovalRequest).where(ApprovalRequest.id == request_id))
        if req is None:
            raise NotFoundError(f"ApprovalRequest {request_id} not found")
        return req

    async def _refresh_resume_metrics(self, session: AsyncSession) -> None:
        pending_count = await session.scalar(
            select(func.count())
            .select_from(ApprovalRequest)
            .where(
                ApprovalRequest.status.in_(
                    [
                        ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value,
                        ApprovalRequestStatus.PENDING_SECOND_APPROVAL.value,
                    ]
                )
            )
        )
        KILL_SWITCH_RESUME_REQUESTS_PENDING_GAUGE.set(float(pending_count or 0))
