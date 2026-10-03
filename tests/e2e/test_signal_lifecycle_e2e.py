"""F2 End-to-End tests using TestSignalFactory without a real Signal Engine (F2 Req #5)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import (
    OrderState,
    OutboxStatus,
    PositionStatus,
    RiskDecisionStatus,
    SignalApprovalStatus,
    SyntheticStopStatus,
)
from app.db.models.audit_log import AuditLog
from app.db.models.order import Order
from app.db.models.outbox_event import OutboxEvent
from app.db.models.position import Position
from app.db.models.synthetic_stop import SyntheticStop
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.paper import PaperTradingAdapter
from app.services.approval_timeout import ApprovalTimeoutService
from app.services.outbox import OutboxService
from app.services.risk_engine import RiskEngine
from app.services.state_machine import StateMachineService
from app.services.synthetic_stop import SyntheticStopService
from tests.factories import TestSignalFactory


@pytest.mark.asyncio
async def test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory(
    migrated_db: None,
) -> None:
    """Full F2 E2E flow driven by TestSignalFactory: Signal -> Risk -> Order -> Stop -> Outbox."""
    init_db()
    factory = get_session_factory()
    paper_exchange = PaperTradingAdapter()
    outbox = OutboxService()
    sm = StateMachineService(outbox_service=outbox)
    risk_engine = RiskEngine()
    approval_svc = ApprovalTimeoutService(state_machine=sm, outbox_service=outbox)
    stop_svc = SyntheticStopService(exchange_adapter=paper_exchange, outbox_service=outbox)

    now = datetime.now(UTC)

    async with factory() as session:
        # 1. Create synthetic signal via TestSignalFactory (0.5% risk cap = 0.005)
        bundle = await TestSignalFactory.create_signal(
            session,
            symbol="BTC/USDT",
            timeframe="1H",
            entry_price=Decimal("60000.00"),
            atr_14=Decimal("500.00"),
            equity=Decimal("10000.00"),
            risk_fraction=Decimal("0.005"),
            now=now,
        )

        # 2. Evaluate Risk Engine with durable heartbeat recording
        decision = await risk_engine.evaluate_with_heartbeat(
            session,
            bundle.risk_input,
            now=now,
        )
        assert decision.decision == RiskDecisionStatus.APPROVE
        assert decision.sizing is not None
        assert decision.sizing.risk_amount == Decimal("50.000")  # 0.5% of 10,000 USDT
        last_hb = await risk_engine.get_last_heartbeat(session)
        assert last_hb is not None

        # 3. Verify price drift (< 0.2%) and transition Signal PENDING -> APPROVED
        paper_exchange.set_ticker("BTC/USDT", price=Decimal("60030.00"), now=now)
        drift_result = await approval_svc.validate_price_drift_before_submission(
            session,
            signal_id=bundle.signal.id,
            current_price=Decimal("60030.00"),
            now=now,
        )
        assert drift_result.expired is False

        approved_sig = await sm.transition_signal_status(
            session,
            signal_id=bundle.signal.id,
            target_status=SignalApprovalStatus.APPROVED,
            actor_role="OPERATOR",
            reason_code="E2E_OPERATOR_APPROVED",
            now=now,
        )
        assert approved_sig.approval_status == SignalApprovalStatus.APPROVED.value

        # 4. Create Order and progress CREATED -> APPROVED -> SUBMITTING -> SUBMITTED -> FILLED
        order = Order(
            id=uuid.uuid4(),
            signal_id=bundle.signal.id,
            strategy_id=bundle.strategy.id,
            exchange_account_id=bundle.exchange_account.id,
            client_order_id=f"e2e-ord-{uuid.uuid4().hex[:12]}",
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            status=OrderState.CREATED.value,
            state_machine_state=OrderState.CREATED.value,
            quantity=decision.sizing.final_quantity,
            filled_quantity=Decimal("0"),
            limit_price=Decimal("60000.00"),
            idempotency_key=f"e2e-idem-{uuid.uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(order)
        await session.flush()

        for next_state in (
            OrderState.APPROVED,
            OrderState.SUBMITTING,
            OrderState.SUBMITTED,
        ):
            await sm.transition_order_state(
                session,
                order_id=order.id,
                target_state=next_state,
                now=now,
            )

        receipt = await paper_exchange.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            client_order_id=order.client_order_id,
            price=Decimal("60000.00"),
        )
        order.exchange_order_id = receipt.exchange_order_id
        order.filled_quantity = receipt.filled_quantity
        order.average_fill_price = receipt.average_fill_price
        await sm.transition_order_state(
            session,
            order_id=order.id,
            target_state=OrderState.FILLED,
            now=now,
        )

        # 5. Open Position and register Synthetic Stop with retry helper -> PROTECTED
        position = Position(
            id=uuid.uuid4(),
            order_id=order.id,
            strategy_id=bundle.strategy.id,
            exchange_account_id=bundle.exchange_account.id,
            symbol="BTC/USDT",
            side="LONG",
            size=order.filled_quantity,
            entry_price=Decimal("60000.00"),
            mark_price=Decimal("60000.00"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status=PositionStatus.OPEN.value,
            stop_price=decision.sizing.stop_loss_price,
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(position)
        await session.flush()

        async def _register_stop(idem_key: str) -> SyntheticStop:
            return await stop_svc.register_stop(
                session,
                position_id=position.id,
                stop_price=decision.sizing.stop_loss_price,
                timeframe="1H",
                idempotency_key=idem_key,
            )

        prot_outcome = await sm.execute_protection_with_retry(
            session,
            order_id=order.id,
            position_id=position.id,
            register_protection_fn=_register_stop,
            exchange_adapter=paper_exchange,
        )
        assert prot_outcome.final_state == OrderState.PROTECTED

        # 6. Simulate market drop below stop_loss_price -> Stop triggers and closes position
        paper_exchange.set_ticker(
            "BTC/USDT",
            price=decision.sizing.stop_loss_price - Decimal("100.00"),
            now=now + timedelta(seconds=10),
        )
        results = await stop_svc.monitor_armed_stops(session)
        assert any(r.position_id == position.id and r.triggered for r in results)

        updated_pos = await session.scalar(select(Position).where(Position.id == position.id))
        assert updated_pos is not None
        assert updated_pos.status == PositionStatus.CLOSED.value

        stop_row = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.position_id == position.id)
        )
        assert stop_row is not None
        assert stop_row.status == SyntheticStopStatus.EXECUTED.value

        # 7. Publish pending Outbox events and verify AuditLog entries exist
        published_ids: list[uuid.UUID] = []

        async def _consumer(ev: OutboxEvent) -> None:
            published_ids.append(ev.id)

        await outbox.process_pending_events(session, handler=_consumer, now=now)
        await session.commit()

        assert len(published_ids) > 0
        ev_row = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == published_ids[0]))
        assert ev_row is not None
        assert ev_row.status == OutboxStatus.PUBLISHED.value

        audits = list(
            (await session.scalars(select(AuditLog).where(AuditLog.target_id == order.id))).all()
        )
        assert len(audits) >= 4

    await dispose_db()


@pytest.mark.asyncio
async def test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher(
    migrated_db: None,
) -> None:
    """TestSignalFactory signal requesting 0.01 (1.0%) risk per trade is rejected fail-closed."""
    init_db()
    factory = get_session_factory()
    risk_engine = RiskEngine()
    sm = StateMachineService()

    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(
            session,
            symbol="ETH/USDT",
            timeframe="1H",
            entry_price=Decimal("3000.00"),
            atr_14=Decimal("50.00"),
            equity=Decimal("10000.00"),
            risk_fraction=Decimal("0.01"),  # 1.0% exceeds 0.005 (0.5%) hard ceiling
        )
        decision = await risk_engine.evaluate_with_heartbeat(session, bundle.risk_input)
        assert decision.decision == RiskDecisionStatus.REJECT
        assert "RISK_PER_TRADE_EXCEEDED" in decision.reason_codes
        assert decision.sizing is None

        rejected_sig = await sm.transition_signal_status(
            session,
            signal_id=bundle.signal.id,
            target_status=SignalApprovalStatus.REJECTED,
            actor_role="SYSTEM",
            reason_code="RISK_PER_TRADE_EXCEEDED",
        )
        await session.commit()
        assert rejected_sig.approval_status == SignalApprovalStatus.REJECTED.value

    await dispose_db()


@pytest.mark.asyncio
async def test_e2e_signal_expired_by_price_drift_with_test_signal_factory(
    migrated_db: None,
) -> None:
    """TestSignalFactory signal expires with EXPIRED_BY_PRICE_DRIFT when drift > 0.2%."""
    init_db()
    factory = get_session_factory()
    approval_svc = ApprovalTimeoutService()

    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(
            session,
            symbol="BTC/USDT",
            timeframe="15M",
            entry_price=Decimal("60000.00"),
            atr_14=Decimal("400.00"),
        )
        # 60000 -> 60200 is +0.333% drift (> 0.2% threshold)
        drift_res = await approval_svc.validate_price_drift_before_submission(
            session,
            signal_id=bundle.signal.id,
            current_price=Decimal("60200.00"),
        )
        await session.commit()
        assert drift_res.expired is True
        assert drift_res.status == SignalApprovalStatus.EXPIRED_BY_PRICE_DRIFT.value

    await dispose_db()
