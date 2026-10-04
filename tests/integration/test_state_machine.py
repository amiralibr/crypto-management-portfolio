"""Integration tests for MVP-0 Signal & Order State Machines (§9 & §21.4)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import (
    OrderState,
    RiskDecisionStatus,
    SignalApprovalStatus,
    SyntheticStopStatus,
)
from app.core.errors import InvalidStateError
from app.db.models.audit_log import AuditLog
from app.db.models.exchange_account import ExchangeAccount
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.signal import Signal
from app.db.models.strategy import Strategy
from app.db.models.synthetic_stop import SyntheticStop
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.services.state_machine import (
    PROTECTION_RETRY_SCHEDULE_SECONDS,
    StateMachineService,
)


async def _seed_order_and_signal(
    *,
    initial_order_state: OrderState = OrderState.SIGNAL_CREATED,
    quantity: Decimal = Decimal("1.000000000000"),
    filled_quantity: Decimal = Decimal("0.000000000000"),
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        account = ExchangeAccount(
            id=uuid.uuid4(),
            name=f"paper-acc-{uuid.uuid4().hex[:8]}",
            exchange_name="paper_simulated",
            mode="PAPER",
            is_active=True,
        )
        strategy = Strategy(
            id=uuid.uuid4(),
            strategy_code=f"STRAT-{uuid.uuid4().hex[:8]}",
            name="State Machine Test Strategy",
            timeframe="1H",
            is_active=True,
            config_json={},
        )
        session.add_all([account, strategy])
        await session.flush()

        sig = Signal(
            id=uuid.uuid4(),
            signal_id=f"SIG-{uuid.uuid4().hex[:10]}",
            strategy_id=strategy.id,
            symbol="BTC/USDT",
            timeframe="1H",
            direction="LONG",
            reference_price=Decimal("60000.00"),
            entry_range_min=Decimal("59950.00"),
            entry_range_max=Decimal("60050.00"),
            stop_loss_price=Decimal("59000.00"),
            take_profit_price=Decimal("62000.00"),
            risk_reward_ratio=Decimal("2.0"),
            data_quality_score=Decimal("0.98"),
            confidence_score=Decimal("0.85"),
            rule_version="4.3",
            approval_status=SignalApprovalStatus.PENDING_APPROVAL.value,
            approval_expires_at=now + timedelta(minutes=5),
            explanation_json={"entry_reason": "breakout"},
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(sig)
        await session.flush()

        order = Order(
            id=uuid.uuid4(),
            client_order_id=f"cli-{uuid.uuid4().hex[:12]}",
            signal_id=sig.id,
            strategy_id=strategy.id,
            exchange_account_id=account.id,
            symbol="BTC/USDT",
            side="BUY",
            order_type="LIMIT",
            quantity=quantity,
            limit_price=Decimal("60000.00"),
            filled_quantity=filled_quantity,
            average_fill_price=Decimal("60000.00") if filled_quantity > Decimal("0") else None,
            status=initial_order_state.value,
            state_machine_state=initial_order_state.value,
            risk_decision=RiskDecisionStatus.APPROVE.value,
            risk_reason_codes=[],
            idempotency_key=f"idem-{uuid.uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(order)
        await session.commit()
        result = (order.id, sig.id, strategy.id, account.id)
    await dispose_db()
    return result


@pytest.mark.asyncio
async def test_valid_transitions_only() -> None:
    """Verify full valid Order lifecycle transitions succeed in sequence (§9.2)."""
    order_id, sig_id, _, _ = await _seed_order_and_signal(
        initial_order_state=OrderState.SIGNAL_CREATED
    )
    sm = StateMachineService()
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        sig = await sm.transition_signal_status(
            session,
            signal_id=sig_id,
            target_status=SignalApprovalStatus.APPROVED,
            actor_role="OPERATIONAL",
        )
        assert sig.approval_status == SignalApprovalStatus.APPROVED.value

        valid_chain = [
            OrderState.PENDING_APPROVAL,
            OrderState.APPROVED,
            OrderState.PRE_TRADE_VALIDATION,
            OrderState.SUBMITTED,
            OrderState.FILLED,
            OrderState.PROTECTED,
            OrderState.CLOSED,
        ]
        for next_state in valid_chain:
            order = await sm.transition_order_state(
                session,
                order_id=order_id,
                target_state=next_state,
            )
            assert order.state_machine_state == next_state.value
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_invalid_transition_rejected() -> None:
    """Verify invalid transitions (SIGNAL_CREATED->FILLED or EXPIRED->APPROVED) raise error."""
    order_id, sig_id, _, _ = await _seed_order_and_signal(
        initial_order_state=OrderState.SIGNAL_CREATED
    )
    sm = StateMachineService()
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        with pytest.raises(InvalidStateError):
            await sm.transition_order_state(
                session,
                order_id=order_id,
                target_state=OrderState.FILLED,
            )

        # Expire signal then try to approve it -> rejected
        await sm.transition_signal_status(
            session,
            signal_id=sig_id,
            target_status=SignalApprovalStatus.EXPIRED,
        )
        with pytest.raises(InvalidStateError):
            await sm.transition_signal_status(
                session,
                signal_id=sig_id,
                target_status=SignalApprovalStatus.APPROVED,
            )
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_concurrent_transition_is_serialized() -> None:
    """Verify concurrent competing transitions on the same Order are serialized by FOR UPDATE."""
    order_id, _, _, _ = await _seed_order_and_signal(
        initial_order_state=OrderState.PENDING_APPROVAL
    )
    sm = StateMachineService()
    init_db()
    factory = get_session_factory()

    async def worker_transition(target: OrderState) -> str:
        async with factory() as session:
            try:
                updated = await sm.transition_order_state(
                    session,
                    order_id=order_id,
                    target_state=target,
                    expected_from_state=OrderState.PENDING_APPROVAL,
                )
                await session.commit()
                return updated.state_machine_state
            except InvalidStateError:
                await session.rollback()
                return "CONFLICT"

    outcomes = await asyncio.gather(
        worker_transition(OrderState.APPROVED),
        worker_transition(OrderState.REJECTED),
    )
    await dispose_db()
    assert outcomes.count("CONFLICT") == 1
    assert set(outcomes) in (
        {"APPROVED", "CONFLICT"},
        {"REJECTED", "CONFLICT"},
    )


@pytest.mark.asyncio
async def test_partial_fill_timeout_cancels_remainder() -> None:
    """Verify PARTIALLY_FILLED -> FILLED_PARTIAL -> CANCEL_REMAINDER protects filled qty."""
    order_id, _, _, _ = await _seed_order_and_signal(
        initial_order_state=OrderState.PARTIALLY_FILLED,
        quantity=Decimal("1.000000000000"),
        filled_quantity=Decimal("0.400000000000"),
    )
    fake_exchange = FakeExchangeAdapter()
    sm = StateMachineService()

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        order_row = await session.scalar(select(Order).where(Order.id == order_id))
        assert order_row is not None
        # Register open order in fake exchange
        fake_exchange.partial_fill_ratio = Decimal("0.4")
        await fake_exchange.place_order(
            symbol="BTC/USDT",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("1.0"),
            client_order_id=order_row.client_order_id,
            limit_price=Decimal("60000.00"),
        )

        order, position, stop = await sm.handle_partial_fill_timeout(
            session,
            order_id=order_id,
            exchange_adapter=fake_exchange,
            stop_price=Decimal("59000.00"),
        )
        await session.commit()

        assert order.state_machine_state == OrderState.CANCEL_REMAINDER.value
        assert position.size == Decimal("0.400000000000")
        assert stop.quantity == Decimal("0.400000000000")
        assert stop.status == SyntheticStopStatus.ARMED.value

        ex_status = await fake_exchange.get_order_status(order.client_order_id)
        assert ex_status is not None
        assert ex_status.status == "CANCELLED"
    await dispose_db()


@pytest.mark.asyncio
async def test_protection_failure_retry_schedule() -> None:
    """Verify protection retry follows 0s, 5s, 15s schedule and cancels position after 3 fails."""
    assert PROTECTION_RETRY_SCHEDULE_SECONDS == (0, 5, 15)

    order_id, _, strategy_id, account_id = await _seed_order_and_signal(
        initial_order_state=OrderState.FILLED,
        quantity=Decimal("0.500000000000"),
        filled_quantity=Decimal("0.500000000000"),
    )
    fake_exchange = FakeExchangeAdapter()
    sm = StateMachineService()
    recorded_sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded_sleeps.append(seconds)

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        pos = Position(
            id=uuid.uuid4(),
            order_id=order_id,
            strategy_id=strategy_id,
            exchange_account_id=account_id,
            symbol="BTC/USDT",
            side="LONG",
            size=Decimal("0.500000000000"),
            entry_price=Decimal("60000.00"),
            mark_price=Decimal("60000.00"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="OPEN",
            stop_price=Decimal("59000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=1,
        )
        session.add(pos)
        await session.flush()

        async def always_failing_protection(_idem_key: str) -> SyntheticStop:
            raise RuntimeError("Simulated protection registration failure")

        outcome = await sm.execute_protection_with_retry(
            session,
            order_id=order_id,
            position_id=pos.id,
            register_protection_fn=always_failing_protection,
            exchange_adapter=fake_exchange,
            sleep_fn=fake_sleep,
        )
        await session.commit()

        assert outcome.attempts_executed == 3
        assert outcome.schedule_offsets_seconds == (0, 5, 15)
        # Wait deltas between 0s -> 5s -> 15s are 5.0s and 10.0s
        assert recorded_sleeps == [5.0, 10.0]
        assert outcome.final_state == OrderState.CANCELLED
    await dispose_db()


@pytest.mark.asyncio
async def test_state_transition_creates_audit_record() -> None:
    """Verify every Signal and Order state transition writes an AuditLog record (§9.1 & §9.2)."""
    order_id, sig_id, _, _ = await _seed_order_and_signal(
        initial_order_state=OrderState.SIGNAL_CREATED
    )
    sm = StateMachineService()
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        await sm.transition_signal_status(
            session,
            signal_id=sig_id,
            target_status=SignalApprovalStatus.APPROVED,
            actor_role="OPERATIONAL",
        )
        await sm.transition_order_state(
            session,
            order_id=order_id,
            target_state=OrderState.PENDING_APPROVAL,
            actor_role="OPERATIONAL",
        )
        await session.commit()

        sig_audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.target_type == "SIGNAL",
                        AuditLog.target_id == sig_id,
                    )
                )
            ).all()
        )
        order_audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.target_type == "ORDER",
                        AuditLog.target_id == order_id,
                    )
                )
            ).all()
        )
        assert len(sig_audits) == 1
        assert sig_audits[0].action == "SIGNAL_APPROVED"
        assert len(order_audits) == 1
        assert order_audits[0].action == "ORDER_STATE_TRANSITION"

        # Also test protection retry succeeding on Attempt 2 (t=5s) -> PROTECTED
        order2_id, _, strat2_id, acc2_id = await _seed_order_and_signal(
            initial_order_state=OrderState.FILLED,
            quantity=Decimal("0.200000000000"),
            filled_quantity=Decimal("0.200000000000"),
        )
        pos2 = Position(
            id=uuid.uuid4(),
            order_id=order2_id,
            strategy_id=strat2_id,
            exchange_account_id=acc2_id,
            symbol="BTC/USDT",
            side="LONG",
            size=Decimal("0.200000000000"),
            entry_price=Decimal("60000.00"),
            mark_price=Decimal("60000.00"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="OPEN",
            stop_price=Decimal("59000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=1,
        )
        session.add(pos2)
        await session.flush()

        attempt_counter = 0

        async def succeed_on_second(idem_key: str) -> SyntheticStop:
            nonlocal attempt_counter
            attempt_counter += 1
            if attempt_counter == 1:
                raise RuntimeError("First attempt transient error")
            stop = SyntheticStop(
                id=uuid.uuid4(),
                position_id=pos2.id,
                symbol="BTC/USDT",
                side="LONG",
                quantity=pos2.size,
                stop_price=Decimal("59000.00"),
                timeframe="1H",
                status=SyntheticStopStatus.ARMED.value,
                idempotency_key=idem_key,
                attempt_count=attempt_counter,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                version=1,
            )
            session.add(stop)
            await session.flush()
            return stop

        async def no_op_sleep(_s: float) -> None:
            return None

        recovered = await sm.execute_protection_with_retry(
            session,
            order_id=order2_id,
            position_id=pos2.id,
            register_protection_fn=succeed_on_second,
            sleep_fn=no_op_sleep,
        )
        await session.commit()
        assert recovered.final_state == OrderState.PROTECTED
        assert recovered.attempts_executed == 2
        assert recovered.schedule_offsets_seconds == (0, 5)

        # Also test protection retry failing position cancellation -> MANUAL_REVIEW + notifier
        from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter

        notifier = PaperTelegramNotificationAdapter()
        sm_with_notif = StateMachineService(notifier=notifier)
        order3_id, _, strat3_id, acc3_id = await _seed_order_and_signal(
            initial_order_state=OrderState.FILLED,
            quantity=Decimal("0.300000000000"),
            filled_quantity=Decimal("0.300000000000"),
        )
        pos3 = Position(
            id=uuid.uuid4(),
            order_id=order3_id,
            strategy_id=strat3_id,
            exchange_account_id=acc3_id,
            symbol="BTC/USDT",
            side="LONG",
            size=Decimal("0.300000000000"),
            entry_price=Decimal("60000.00"),
            mark_price=Decimal("60000.00"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="OPEN",
            stop_price=Decimal("59000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=1,
        )
        session.add(pos3)
        await session.flush()

        down_exchange = FakeExchangeAdapter()
        down_exchange.connection_down = True

        async def fail_prot(_k: str) -> SyntheticStop:
            raise RuntimeError("Prot fail")

        manual_res = await sm_with_notif.execute_protection_with_retry(
            session,
            order_id=order3_id,
            position_id=pos3.id,
            register_protection_fn=fail_prot,
            exchange_adapter=down_exchange,
            sleep_fn=no_op_sleep,
        )
        await session.commit()
        assert manual_res.final_state == OrderState.MANUAL_REVIEW
        assert len(notifier.sent_messages) == 1

        # Also test validation/not-found branches on StateMachineService
        from app.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await sm.transition_signal_status(
                session,
                signal_id=uuid.uuid4(),
                target_status=SignalApprovalStatus.APPROVED,
            )
        with pytest.raises(NotFoundError):
            await sm.transition_order_state(
                session,
                order_id=uuid.uuid4(),
                target_state=OrderState.APPROVED,
            )
        with pytest.raises(NotFoundError):
            await sm.handle_partial_fill_timeout(
                session,
                order_id=uuid.uuid4(),
                exchange_adapter=down_exchange,
                stop_price=Decimal("59000.00"),
            )
        with pytest.raises(InvalidStateError):
            await sm.handle_partial_fill_timeout(
                session,
                order_id=order2_id,
                exchange_adapter=down_exchange,
                stop_price=Decimal("59000.00"),
            )

        # Also test handle_partial_fill_timeout when Position already exists for order
        order4_id, _, strat4_id, acc4_id = await _seed_order_and_signal(
            initial_order_state=OrderState.PARTIALLY_FILLED,
            quantity=Decimal("1.000000000000"),
            filled_quantity=Decimal("0.400000000000"),
        )
        pos4 = Position(
            id=uuid.uuid4(),
            order_id=order4_id,
            strategy_id=strat4_id,
            exchange_account_id=acc4_id,
            symbol="BTC/USDT",
            side="LONG",
            size=Decimal("0.200000000000"),
            entry_price=Decimal("60000.00"),
            mark_price=Decimal("60000.00"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="OPEN",
            stop_price=Decimal("58000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=1,
        )
        session.add(pos4)
        await session.flush()
        up_exchange = FakeExchangeAdapter()
        _, updated_pos4, _ = await sm.handle_partial_fill_timeout(
            session,
            order_id=order4_id,
            exchange_adapter=up_exchange,
            stop_price=Decimal("59000.00"),
        )
        assert updated_pos4.size == Decimal("0.400000000000")
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_protection_failure_retry_schedule_is_0_5_15_seconds(
    migrated_db: None,
) -> None:
    """F2 Regression (§12.6): Verify protection failure retry schedule is 0s, 5s, 15s."""
    _ = migrated_db
    await test_protection_failure_retry_schedule()
