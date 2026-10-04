"""Integration tests for Signal-to-Order Handoff and F2 Regressions in Phase F"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import (
    OrderState,
    OutboxEventType,
    OutboxStatus,
    RiskDecisionStatus,
    SignalApprovalStatus,
)
from app.core.errors import ConflictError, InvalidStateError
from app.core.redis import RedisClient
from app.db.models.audit_log import AuditLog
from app.db.models.dead_letter_event import DeadLetterEvent
from app.db.models.order import Order
from app.db.models.outbox_event import OutboxEvent
from app.db.models.signal import Signal
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.paper import PaperTradingAdapter
from app.services.kill_switch import KillSwitchService
from app.services.outbox import OutboxService
from app.services.signal_engine import SignalEngine
from app.services.signal_lifecycle import SignalLifecycleService


async def _seed_signal(*, reference_price: Decimal = Decimal("60000.00")) -> uuid.UUID:
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()
    async with factory() as session:
        sig = await engine.create_signal(
            session,
            symbol="BTC/USDT",
            timeframe="1H",
            reference_price=reference_price,
            entry_range_min=reference_price - Decimal("50"),
            entry_range_max=reference_price + Decimal("50"),
            stop_loss_price=reference_price - Decimal("600"),
            take_profit_price=reference_price + Decimal("1200"),
            risk_reward_ratio=Decimal("2.0"),
            data_quality_score=Decimal("0.95"),
            confidence_score=Decimal("0.85"),
            explanation_json={
                "entry_reason": "4H bull trend + 1H breakout",
                "risk_reason": "1% stop distance",
                "confluence_score": "0.85",
                "regime": "BULL_TREND",
                "factors": {"ema_50_4h": "60100"},
            },
            now=now,
        )
        await session.commit()
        return sig.id


@pytest.mark.asyncio
async def test_approved_signal_creates_order_draft(migrated_db: None) -> None:
    """Verify approving a signal produces an OrderDraft linked to signal_id (§9 & §12.5)."""
    sig_id = await _seed_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve and create order draft",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()
        assert outcome.order_draft is not None
        assert outcome.order_draft.signal_id == sig_id
        assert outcome.order_draft.symbol == "BTC/USDT"
        assert outcome.order_draft.side == "BUY"
        assert outcome.order_draft.direction == "LONG"

        # Unapproved signal cannot create an OrderDraft
        pending_id = await _seed_signal()
        init_db()
        factory = get_session_factory()
        async with factory() as s2:
            pending_sig = await s2.scalar(select(Signal).where(Signal.id == pending_id))
            assert pending_sig is not None
            with pytest.raises(InvalidStateError):
                lifecycle.create_order_draft(
                    pending_sig,
                    exchange_account_id=uuid.uuid4(),
                )
    await dispose_db()


@pytest.mark.asyncio
async def test_risk_approved_signal_creates_submitted_order(migrated_db: None) -> None:
    """Verify Risk Engine APPROVE creates a SUBMITTED Paper Order with ORDER_CREAT"""
    sig_id = await _seed_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve risk-valid signal",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()

        assert outcome.signal.approval_status == SignalApprovalStatus.APPROVED.value
        assert outcome.order is not None
        assert outcome.order.signal_id == sig_id
        assert outcome.order.risk_decision == RiskDecisionStatus.APPROVE.value
        assert outcome.order.state_machine_state == OrderState.SUBMITTED.value
        assert outcome.order.status == OrderState.SUBMITTED.value
        assert outcome.order.quantity > Decimal("0")

        outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == outcome.order.id,
                OutboxEvent.event_type == OutboxEventType.ORDER_CREATED.value,
            )
        )
        assert outbox is not None
    await dispose_db()


@pytest.mark.asyncio
async def test_risk_rejected_signal_creates_rejected_order(migrated_db: None) -> None:
    """Verify Risk Engine REJECT retains APPROVED signal and creates a risk-reject"""
    sig_id = await _seed_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        # Force risk rejection via daily_loss_pct > 2.0% hard cap
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Operator approved signal; Risk Engine is final authority",
            idempotency_key=f"idem-{uuid.uuid4()}",
            risk_input_overrides={"daily_loss_pct": Decimal("0.03")},
        )
        await session.commit()

        # §9.5: Retain APPROVED signal and create a risk-rejected order record
        assert outcome.signal.approval_status == SignalApprovalStatus.APPROVED.value
        assert outcome.order is not None
        assert outcome.order.signal_id == sig_id
        assert outcome.order.risk_decision == RiskDecisionStatus.REJECT.value
        assert outcome.order.state_machine_state == OrderState.REJECTED.value
        assert outcome.order.status == OrderState.REJECTED.value
        assert outcome.order.quantity == Decimal("0")
        assert len(outcome.order.risk_reason_codes) >= 1
    await dispose_db()


@pytest.mark.asyncio
async def test_risk_rejection_creates_audit_event(migrated_db: None) -> None:
    """Verify Risk Engine rejection creates an immutable ORDER_REJECTED_BY_RISK au"""
    sig_id = await _seed_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve signal that exceeds risk limit",
            idempotency_key=f"idem-{uuid.uuid4()}",
            risk_input_overrides={"risk_fraction": Decimal("0.01")},
        )
        await session.commit()
        assert outcome.order is not None

        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.target_id == outcome.order.id,
                AuditLog.action == OutboxEventType.ORDER_REJECTED_BY_RISK.value,
            )
        )
        assert audit is not None
        assert audit.detail_json is not None
        assert audit.detail_json["signal_id"] == str(sig_id)
    await dispose_db()


@pytest.mark.asyncio
async def test_risk_rejection_creates_outbox_event(migrated_db: None) -> None:
    """Verify Risk Engine rejection creates a versioned ORDER_REJECTED_BY_RISK Out"""
    sig_id = await _seed_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve signal that exceeds weekly loss cap",
            idempotency_key=f"idem-{uuid.uuid4()}",
            risk_input_overrides={"weekly_loss_pct": Decimal("0.06")},
        )
        await session.commit()
        assert outcome.order is not None

        outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == outcome.order.id,
                OutboxEvent.event_type == OutboxEventType.ORDER_REJECTED_BY_RISK.value,
            )
        )
        assert outbox is not None
        assert outbox.event_version == 1
        assert outbox.payload_json["signal_id"] == str(sig_id)
    await dispose_db()


@pytest.mark.asyncio
async def test_one_active_order_per_signal(migrated_db: None) -> None:
    """Verify at most one active order can exist per approved signal (§9 & §12.5)."""
    sig_id = await _seed_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve signal once",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()
        assert outcome.order is not None

        # Attempting a second handoff on the same APPROVED signal is blocked
        with pytest.raises(ConflictError) as exc_info:
            await lifecycle.handoff_signal_to_order(
                session,
                signal=outcome.signal,
                client_order_id=f"ord-second-{uuid.uuid4().hex[:8]}",
                idempotency_key=f"idem-second-{uuid.uuid4().hex[:8]}",
            )
        assert exc_info.value.code == "DUPLICATE_ORDER"
    await dispose_db()


@pytest.mark.asyncio
async def test_duplicate_order_creation_is_prevented(migrated_db: None) -> None:
    """Verify duplicate client_order_id or idempotency_key is prevented across ord"""
    sig1_id = await _seed_signal()
    sig2_id = await _seed_signal()
    shared_idem = f"shared-ord-idem-{uuid.uuid4().hex[:8]}"

    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        await lifecycle.approve_signal(
            session,
            signal_id=sig1_id,
            reason="Approve first signal",
            idempotency_key=shared_idem,
        )
        await session.commit()

        # Approve second signal without handoff, then attempt handoff reusing shared_idem
        sig2 = await lifecycle.transition_signal(
            session,
            signal_id=sig2_id,
            target_status=SignalApprovalStatus.APPROVED,
            reason="Approve second signal",
        )
        with pytest.raises(ConflictError) as exc_info:
            await lifecycle.handoff_signal_to_order(
                session,
                signal=sig2,
                idempotency_key=shared_idem,
            )
        assert exc_info.value.code == "DUPLICATE_ORDER"
    await dispose_db()


@pytest.mark.asyncio
async def test_no_real_exchange_call_is_made(migrated_db: None) -> None:
    """Verify Signal-to-Order handoff makes zero real or outbound exchange order c"""
    sig_id = await _seed_signal()
    paper_adapter = PaperTradingAdapter()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService(exchange_adapter=paper_adapter)
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve in Paper-only F3 handoff",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()
        assert outcome.order is not None
        # F3 handoff stops at Risk Engine decision + Order record creation; zero exch
        open_exchange_orders = await paper_adapter.get_open_orders("BTC/USDT")
        assert len(open_exchange_orders) == 0
    await dispose_db()


@pytest.mark.asyncio
async def test_outbox_dead_letter_after_max_retries(migrated_db: None) -> None:
    """F2 Regression (§12.6): Outbox event moves to dead_letter_events after OUTBOX_MAX_RETRIES."""
    from sqlalchemy import delete

    init_db()
    factory = get_session_factory()
    outbox_svc = OutboxService()
    now = datetime.now(UTC)

    async def _always_fail(_ev: OutboxEvent) -> None:
        raise RuntimeError("Simulated consumer failure")

    async with factory() as session:
        await session.execute(
            delete(OutboxEvent).where(OutboxEvent.status == OutboxStatus.PENDING.value)
        )
        await session.commit()

        ev = await outbox_svc.enqueue_event(
            session,
            event_type=OutboxEventType.SIGNAL_CREATED.value,
            aggregate_type="SIGNAL",
            aggregate_id=uuid.uuid4(),
            payload={"signal_id": "SIG-DLQ-REG"},
        )
        await session.commit()
        ev_id = ev.id

        for attempt in range(1, 6):
            await outbox_svc.process_pending_events(
                session,
                handler=_always_fail,
                now=now + timedelta(minutes=attempt * 10),
                batch_size=200,
            )
            await session.commit()

        updated_ev = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == ev_id))
        assert updated_ev is not None
        assert updated_ev.status == OutboxStatus.DEAD_LETTER.value

        dlq = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == ev_id)
        )
        assert dlq is not None
        assert dlq.retry_count == 5
    await dispose_db()


@pytest.mark.asyncio
async def test_redis_unavailable_does_not_lose_postgres_state(migrated_db: None) -> None:
    """F2 Regression (§12.6): Redis unavailability loses zero PostgreSQL Signal/Or"""
    from app.core.errors import InvalidRequestError

    sig_id = await _seed_signal()
    down_redis = RedisClient("redis://127.0.0.1:6399/0")
    assert await down_redis.ping() is False
    await down_redis.close()

    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    ks = KillSwitchService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approve while Redis is unreachable",
            idempotency_key=f"idem-redis-down-{uuid.uuid4()}",
        )
        await ks.activate(session, reason="Kill switch durable in PostgreSQL while Redis down")
        await session.commit()

        persisted_sig = await session.scalar(select(Signal).where(Signal.id == sig_id))
        assert persisted_sig is not None
        assert persisted_sig.approval_status == SignalApprovalStatus.APPROVED.value
        assert outcome.order is not None
        persisted_ord = await session.scalar(select(Order).where(Order.id == outcome.order.id))
        assert persisted_ord is not None
        assert await ks.is_active(session) is True

        state = await ks.get_or_create_state(session, for_update=True)
        state.is_active = False
        await session.commit()

        with pytest.raises(InvalidRequestError):
            await lifecycle.approve_signal(session, signal_id=sig_id, reason="")
        with pytest.raises(InvalidRequestError):
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="ok",
                idempotency_key="   ",
            )
        with pytest.raises(InvalidRequestError):
            await lifecycle.reject_signal(session, signal_id=sig_id, reason="")
        with pytest.raises(InvalidRequestError):
            await lifecycle.reject_signal(
                session,
                signal_id=sig_id,
                reason="ok",
                idempotency_key="   ",
            )
        with pytest.raises(InvalidRequestError):
            await lifecycle.handoff_signal_to_order(
                session,
                signal=persisted_sig,
                approved_order_state=OrderState.FILLED,
            )

        sig_no_handoff_id = await _seed_signal()
        sig_rej_no_idem_id = await _seed_signal()
        init_db()
        factory = get_session_factory()
        async with factory() as s2:
            idem_nh = f"idem-nh-{uuid.uuid4()}"
            out_no_handoff = await lifecycle.approve_signal(
                s2,
                signal_id=sig_no_handoff_id,
                reason="Approve without handoff",
                idempotency_key=idem_nh,
                perform_handoff=False,
            )
            assert out_no_handoff.order is None
            replay_nh = await lifecycle.approve_signal(
                s2,
                signal_id=sig_no_handoff_id,
                reason="Approve without handoff",
                idempotency_key=idem_nh,
                perform_handoff=False,
            )
            assert replay_nh.idempotent_replay is True

            idem_rj = f"idem-rj-{uuid.uuid4()}"
            await lifecycle.reject_signal(
                s2,
                signal_id=sig_rej_no_idem_id,
                reason="Reject with idempotency key",
                idempotency_key=idem_rj,
            )
            replay_rj = await lifecycle.reject_signal(
                s2,
                signal_id=sig_rej_no_idem_id,
                reason="Reject with idempotency key",
                idempotency_key=idem_rj,
            )
            assert replay_rj.idempotent_replay is True
            await s2.commit()
    await dispose_db()
