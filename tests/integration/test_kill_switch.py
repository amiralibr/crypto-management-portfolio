"""Integration tests for Persistent Kill Switch and Two-Person Approval Resume (§13 & §21.1)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.enums import (
    ApiRole,
    ApprovalRequestStatus,
    OrderState,
    RiskDecisionStatus,
)
from app.core.errors import (
    ForbiddenError,
    InvalidStateError,
    KillSwitchActiveError,
    KillSwitchConflictError,
)
from app.db.models.approval_request import ApprovalRequest
from app.db.models.audit_log import AuditLog
from app.db.models.exchange_account import ExchangeAccount
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.strategy import Strategy
from app.db.models.synthetic_stop import SyntheticStop
from app.db.models.system_state import SystemState
from app.db.models.trade import Trade
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.services.kill_switch import (
    KILL_SWITCH_STATE_KEY,
    REDUCED_EXPOSURE_MULTIPLIER,
    KillSwitchService,
)


async def _reset_kill_switch_and_orders() -> None:
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(delete(ApprovalRequest))
        await session.execute(delete(Trade))
        await session.execute(delete(SyntheticStop))
        await session.execute(delete(Position))
        await session.execute(delete(Order))
        state = await session.scalar(
            select(SystemState)
            .where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
            .with_for_update()
        )
        if state is not None:
            state.is_active = False
            state.activated_at = None
            state.activated_by = None
            state.activation_reason = None
            state.activation_source = None
            state.resume_status = None
            state.resumed_at = None
            state.resumed_by = None
            state.resume_reason = None
            state.exposure_multiplier = Decimal("1.0000")
            state.metadata_json = {}
            state.version = 1
        await session.commit()
    await dispose_db()


async def _create_order_in_state(
    state: OrderState,
    *,
    quantity: Decimal = Decimal("1.000000000000"),
    filled_quantity: Decimal = Decimal("0.000000000000"),
) -> tuple[uuid.UUID, str]:
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        account = ExchangeAccount(
            id=uuid.uuid4(),
            name=f"ks-acc-{uuid.uuid4().hex[:8]}",
            exchange_name="paper_simulated",
            mode="PAPER",
            is_active=True,
        )
        strategy = Strategy(
            id=uuid.uuid4(),
            strategy_code=f"KS-STRAT-{uuid.uuid4().hex[:8]}",
            name="Kill Switch Test Strategy",
            timeframe="1H",
            is_active=True,
            config_json={},
        )
        session.add_all([account, strategy])
        await session.flush()

        client_oid = f"ks-cli-{uuid.uuid4().hex[:10]}"
        order = Order(
            id=uuid.uuid4(),
            client_order_id=client_oid,
            signal_id=None,
            strategy_id=strategy.id,
            exchange_account_id=account.id,
            symbol="BTC/USDT",
            side="BUY",
            order_type="LIMIT",
            quantity=quantity,
            limit_price=Decimal("60000.00"),
            filled_quantity=filled_quantity,
            average_fill_price=Decimal("60000.00") if filled_quantity > Decimal("0") else None,
            status=state.value,
            state_machine_state=state.value,
            risk_decision=RiskDecisionStatus.APPROVE.value,
            risk_reason_codes=[],
            idempotency_key=f"ks-idem-{uuid.uuid4().hex[:10]}",
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(order)
        await session.commit()
        oid = order.id
    await dispose_db()
    return oid, client_oid


@pytest.mark.asyncio
async def test_kill_switch_persists_after_restart() -> None:
    """Verify Kill Switch state persists in PostgreSQL across restart (§13.1)."""
    await _reset_kill_switch_and_orders()

    init_db()
    factory = get_session_factory()
    ks1 = KillSwitchService()
    async with factory() as session:
        res = await ks1.activate(session, reason="Fire drill persistence test")
        await session.commit()
        assert res.status == "activated"
        assert res.is_active is True
    await dispose_db()

    # Simulate process restart with new DB engine and new KillSwitchService instance
    init_db()
    factory2 = get_session_factory()
    ks2 = KillSwitchService()
    async with factory2() as session:
        assert await ks2.is_active(session) is True
        state = await ks2.get_or_create_state(session)
        assert state.activation_reason == "Fire drill persistence test"
    await dispose_db()


@pytest.mark.asyncio
async def test_kill_switch_blocks_new_orders() -> None:
    """Verify active Kill Switch blocks new order execution via ensure_trading_allowed (§13.3)."""
    await _reset_kill_switch_and_orders()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="Block new orders test")
        await session.commit()

        with pytest.raises(KillSwitchActiveError):
            await ks.ensure_trading_allowed(session)
    await dispose_db()


@pytest.mark.asyncio
async def test_kill_switch_requires_admin_key(
    async_client: AsyncClient,
    operational_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    """Verify emergency-stop rejects OPERATIONAL key (403) and accepts ADMIN key (200)."""
    await _reset_kill_switch_and_orders()

    resp_op = await async_client.post(
        "/api/v1/system/emergency-stop",
        headers=operational_headers,
        json={"reason": "operator attempt"},
    )
    assert resp_op.status_code == 403
    assert resp_op.json()["code"] == "FORBIDDEN"

    resp_admin = await async_client.post(
        "/api/v1/system/emergency-stop",
        headers=admin_headers,
        json={"reason": "admin emergency stop"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["status"] == "activated"
    assert resp_admin.json()["is_active"] is True


@pytest.mark.asyncio
async def test_kill_switch_is_idempotent(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Verify activating an already-active Kill Switch returns 200 already_active (v4.3 §2.1)."""
    await _reset_kill_switch_and_orders()

    resp1 = await async_client.post(
        "/api/v1/system/emergency-stop",
        headers=admin_headers,
        json={"reason": "first activation"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "activated"

    resp2 = await async_client.post(
        "/api/v1/system/emergency-stop",
        headers=admin_headers,
        json={"reason": "duplicate activation"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already_active"
    assert resp2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_kill_switch_failure_enters_manual_review() -> None:
    """Verify connector failure during Kill Switch activation enters MANUAL_REVIEW (§13.3)."""
    await _reset_kill_switch_and_orders()
    order_id, _ = await _create_order_in_state(OrderState.SUBMITTED)

    fake_exchange = FakeExchangeAdapter()
    fake_exchange.fail_cancel_order = True
    ks = KillSwitchService(exchange_adapter=fake_exchange)

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        res = await ks.activate(session, reason="connector failure during emergency stop")
        await session.commit()

        assert res.is_active is True
        assert res.status == "manual_review"
        assert res.resume_status == "MANUAL_REVIEW"

        order = await session.scalar(select(Order).where(Order.id == order_id))
        assert order is not None
        assert order.state_machine_state == OrderState.MANUAL_REVIEW.value
    await dispose_db()


@pytest.mark.asyncio
async def test_kill_switch_audit_record_created() -> None:
    """Verify Kill Switch activation writes a KILL_SWITCH_ACTIVATED AuditLog entry (§13.3)."""
    await _reset_kill_switch_and_orders()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="audit verification test")
        await session.commit()

        state = await ks.get_or_create_state(session)
        audit = await session.scalar(
            select(AuditLog)
            .where(
                AuditLog.target_type == "SYSTEM_STATE",
                AuditLog.target_id == state.id,
                AuditLog.action == "KILL_SWITCH_ACTIVATED",
            )
            .order_by(AuditLog.created_at.desc())
        )
        assert audit is not None
        assert audit.detail_json is not None
        assert audit.detail_json["reason"] == "audit verification test"
    await dispose_db()


@pytest.mark.asyncio
async def test_kill_switch_with_active_partial_fill() -> None:
    """Verify Kill Switch activation reconciles PARTIALLY_FILLED orders (§13.3)."""
    await _reset_kill_switch_and_orders()
    order_id, client_oid = await _create_order_in_state(
        OrderState.PARTIALLY_FILLED,
        quantity=Decimal("1.000000000000"),
        filled_quantity=Decimal("0.350000000000"),
    )
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.partial_fill_ratio = Decimal("0.35")
    await fake_exchange.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="LIMIT",
        quantity=Decimal("1.0"),
        client_order_id=client_oid,
        limit_price=Decimal("60000.00"),
    )

    ks = KillSwitchService(exchange_adapter=fake_exchange)
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        res = await ks.activate(session, reason="partial fill emergency stop")
        await session.commit()

        assert res.reconciled_partial_fills_count == 1
        order = await session.scalar(select(Order).where(Order.id == order_id))
        assert order is not None
        assert order.state_machine_state == OrderState.CANCEL_REMAINDER.value
    await dispose_db()


@pytest.mark.asyncio
async def test_kill_switch_with_open_order() -> None:
    """Verify Kill Switch activation cancels open SUBMITTED orders on exchange and in DB (§13.3)."""
    await _reset_kill_switch_and_orders()
    order_id, client_oid = await _create_order_in_state(OrderState.SUBMITTED)
    fake_exchange = FakeExchangeAdapter()
    await fake_exchange.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="LIMIT",
        quantity=Decimal("1.0"),
        client_order_id=client_oid,
        limit_price=Decimal("60000.00"),
    )

    ks = KillSwitchService(exchange_adapter=fake_exchange)
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        res = await ks.activate(session, reason="open order emergency stop")
        await session.commit()

        assert res.cancelled_orders_count == 1
        order = await session.scalar(select(Order).where(Order.id == order_id))
        assert order is not None
        assert order.state_machine_state == OrderState.CANCELLED.value
    await dispose_db()


@pytest.mark.asyncio
async def test_kill_switch_resume_requires_two_person_approval() -> None:
    """Verify first approval moves to PENDING_SECOND_APPROVAL and second resumes (§13.4)."""
    await _reset_kill_switch_and_orders()
    requester_id = uuid.uuid4()
    admin_approver_id = uuid.uuid4()
    operator_approver_id = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="two-person approval test")
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Root cause resolved and reconciliation completed",
        )
        assert req.status == ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value

        # First approval (ADMIN) -> still active!
        req, state = await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=admin_approver_id,
            approver_role=ApiRole.ADMIN,
        )
        assert req.status == ApprovalRequestStatus.PENDING_SECOND_APPROVAL.value
        assert state.is_active is True

        # Second approval (OPERATOR) -> resumed!
        req, state = await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=operator_approver_id,
            approver_role=ApiRole.OPERATIONAL,
        )
        await session.commit()
        assert req.status == ApprovalRequestStatus.APPROVED.value
        assert state.is_active is False
    await dispose_db()


@pytest.mark.asyncio
async def test_resume_requester_cannot_approve_own_request() -> None:
    """Verify requester cannot approve their own Kill Switch resume request (§13.5)."""
    await _reset_kill_switch_and_orders()
    requester_id = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="self-approval prevention test")
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Root cause documented",
        )
        with pytest.raises(ForbiddenError, match="Requester cannot approve"):
            await ks.approve_resume_request(
                session,
                request_id=req.id,
                approver_id=requester_id,
                approver_role=ApiRole.ADMIN,
            )
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_same_actor_cannot_approve_twice() -> None:
    """Verify the first approver cannot also provide the second approval (§13.5)."""
    await _reset_kill_switch_and_orders()
    requester_id = uuid.uuid4()
    approver1_id = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="duplicate actor prevention test")
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Root cause documented",
        )
        await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=approver1_id,
            approver_role=ApiRole.ADMIN,
        )
        with pytest.raises(ForbiddenError, match="Same actor"):
            await ks.approve_resume_request(
                session,
                request_id=req.id,
                approver_id=approver1_id,
                approver_role=ApiRole.OPERATIONAL,
            )
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_resume_requires_admin_and_operator_roles() -> None:
    """Verify two approvals with the same role (e.g. two ADMINs) are rejected (§13.5)."""
    await _reset_kill_switch_and_orders()
    requester_id = uuid.uuid4()
    admin1 = uuid.uuid4()
    admin2 = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="complementary role test")
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Root cause documented",
        )
        await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=admin1,
            approver_role=ApiRole.ADMIN,
        )
        with pytest.raises(ForbiddenError, match="complementary ADMIN and OPERATOR"):
            await ks.approve_resume_request(
                session,
                request_id=req.id,
                approver_id=admin2,
                approver_role=ApiRole.ADMIN,
            )
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_expired_resume_request_cannot_be_approved() -> None:
    """Verify resume request expires after 86400s (24 hours) and cannot be approved (§13.5)."""
    from app.services.kill_switch import KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS

    assert KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS == 86400
    await _reset_kill_switch_and_orders()
    now = datetime.now(UTC)
    requester_id = uuid.uuid4()
    approver_id = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="expiry test", now=now)
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Root cause documented",
            now=now,
        )
        assert int((req.expires_at - req.created_at).total_seconds()) == 86400
        with pytest.raises(InvalidStateError, match="Expired"):
            await ks.approve_resume_request(
                session,
                request_id=req.id,
                approver_id=approver_id,
                approver_role=ApiRole.OPERATIONAL,
                now=now + timedelta(seconds=86401),
            )
        await session.commit()
        assert req.status == ApprovalRequestStatus.EXPIRED.value
    await dispose_db()


@pytest.mark.asyncio
async def test_resume_applies_reduced_exposure() -> None:
    """Verify Kill Switch resume sets exposure_multiplier to 0.3000 (30% exposure) (§13.5)."""
    await _reset_kill_switch_and_orders()
    requester_id = uuid.uuid4()
    admin_approver = uuid.uuid4()
    operator_approver = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="reduced exposure test")
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Root cause resolved",
        )
        await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=admin_approver,
            approver_role=ApiRole.ADMIN,
        )
        _, state = await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=operator_approver,
            approver_role=ApiRole.OPERATIONAL,
        )
        await session.commit()

        assert state.is_active is False
        assert state.resume_status == "RESUMED_REDUCED_EXPOSURE"
        assert state.exposure_multiplier == REDUCED_EXPOSURE_MULTIPLIER
        assert state.metadata_json.get("reduced_exposure") is True
    await dispose_db()


@pytest.mark.asyncio
async def test_resume_blocked_when_reconciliation_failed() -> None:
    """Verify final Kill Switch resume is blocked if reconciliation failed (§13.5)."""
    await _reset_kill_switch_and_orders()
    requester_id = uuid.uuid4()
    admin_approver = uuid.uuid4()
    operator_approver = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()
    async with factory() as session:
        await ks.activate(session, reason="reconciliation block test")
        await ks.set_reconciliation_status(
            session,
            reconciliation_ok=False,
            reason="Position mismatch detected",
        )
        req = await ks.create_resume_request(
            session,
            requester_id=requester_id,
            requester_role=ApiRole.ADMIN,
            reason="Attempted resume before reconciliation fixed",
        )
        await ks.approve_resume_request(
            session,
            request_id=req.id,
            approver_id=admin_approver,
            approver_role=ApiRole.ADMIN,
        )
        with pytest.raises(KillSwitchConflictError, match="reconciliation"):
            await ks.approve_resume_request(
                session,
                request_id=req.id,
                approver_id=operator_approver,
                approver_role=ApiRole.OPERATIONAL,
            )

        # Also test ReconciliationService mismatch blocking resume + reject_resume_request
        from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter
        from app.services.reconciliation import ReconciliationService

        await ks.set_reconciliation_status(session, reconciliation_ok=True)
        fake_ex = FakeExchangeAdapter()
        notifier = PaperTelegramNotificationAdapter()
        recon_svc = ReconciliationService(exchange_adapter=fake_ex, notifier=notifier)
        ks_with_recon = KillSwitchService(
            exchange_adapter=fake_ex,
            notifier=notifier,
            reconciliation_service=recon_svc,
        )

        # Create an OPEN position in DB that is missing on fake_ex -> reconciliation fails
        oid, _ = await _create_order_in_state(
            OrderState.PROTECTED,
            quantity=Decimal("0.5"),
            filled_quantity=Decimal("0.5"),
        )
        ord_row = await session.scalar(select(Order).where(Order.id == oid))
        assert ord_row is not None
        open_pos = Position(
            id=uuid.uuid4(),
            order_id=ord_row.id,
            strategy_id=ord_row.strategy_id,
            exchange_account_id=ord_row.exchange_account_id,
            symbol="BTC/USDT",
            side="LONG",
            size=Decimal("0.5"),
            entry_price=Decimal("60000.00"),
            status="OPEN",
            stop_price=Decimal("59000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=1,
        )
        session.add(open_pos)
        await session.flush()

        with pytest.raises(KillSwitchConflictError, match="discrepancy"):
            await ks_with_recon.approve_resume_request(
                session,
                request_id=req.id,
                approver_id=operator_approver,
                approver_role=ApiRole.OPERATIONAL,
            )

        rejected = await ks_with_recon.reject_resume_request(
            session,
            request_id=req.id,
            actor_id=operator_approver,
            actor_role=ApiRole.OPERATIONAL,
            reason="Discrepancy found",
        )
        assert rejected.status == ApprovalRequestStatus.REJECTED.value

        # Additional error/guard branches on KillSwitchService
        from app.core.errors import InvalidRequestError, NotFoundError

        with pytest.raises(InvalidRequestError):
            await ks.activate(session, reason="ab")
        with pytest.raises(ForbiddenError):
            await ks.activate(
                session, reason="operator not allowed", actor_role=ApiRole.OPERATIONAL
            )
        with pytest.raises(ForbiddenError):
            await ks.create_resume_request(
                session,
                requester_id=requester_id,
                requester_role=ApiRole.OPERATIONAL,
                reason="Operator cannot create resume request",
            )
        with pytest.raises(NotFoundError):
            await ks.get_resume_request(session, request_id=uuid.uuid4())
        with pytest.raises(NotFoundError):
            await ks.approve_resume_request(
                session,
                request_id=uuid.uuid4(),
                approver_id=admin_approver,
                approver_role=ApiRole.ADMIN,
            )
        with pytest.raises(InvalidStateError):
            await ks.reject_resume_request(
                session,
                request_id=req.id,
                actor_id=operator_approver,
                actor_role=ApiRole.OPERATIONAL,
                reason="Already rejected",
            )
        await session.commit()
    await dispose_db()
