"""Integration tests for PostgreSQL-backed Synthetic Stop-Loss (§12 & §21.2)."""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.enums import (
    OrderState,
    PositionStatus,
    RiskDecisionStatus,
    SyntheticStopStatus,
)
from app.db.models.audit_log import AuditLog
from app.db.models.exchange_account import ExchangeAccount
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.strategy import Strategy
from app.db.models.synthetic_stop import SyntheticStop
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.services.synthetic_stop import (
    STOP_RETRY_SCHEDULE_SECONDS,
    SyntheticStopService,
)


async def _seed_open_position_with_stop(
    *,
    entry_price: Decimal = Decimal("60000.00"),
    stop_price: Decimal = Decimal("58800.00"),
    quantity: Decimal = Decimal("0.250000000000"),
    timeframe: str = "1H",
) -> tuple[uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    stop_service = SyntheticStopService(exchange_adapter=fake_exchange)

    async with factory() as session:
        account = ExchangeAccount(
            id=uuid.uuid4(),
            name=f"stop-acc-{uuid.uuid4().hex[:8]}",
            exchange_name="paper_simulated",
            mode="PAPER",
            is_active=True,
        )
        strategy = Strategy(
            id=uuid.uuid4(),
            strategy_code=f"STRAT-{uuid.uuid4().hex[:8]}",
            name="Stop Test Strategy",
            timeframe=timeframe,
            is_active=True,
            config_json={},
        )
        session.add_all([account, strategy])
        await session.flush()

        buy_order = Order(
            id=uuid.uuid4(),
            client_order_id=f"buy-{uuid.uuid4().hex[:10]}",
            signal_id=None,
            strategy_id=strategy.id,
            exchange_account_id=account.id,
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            quantity=quantity,
            limit_price=None,
            filled_quantity=quantity,
            average_fill_price=entry_price,
            status=OrderState.PROTECTED.value,
            state_machine_state=OrderState.PROTECTED.value,
            risk_decision=RiskDecisionStatus.APPROVE.value,
            risk_reason_codes=[],
            idempotency_key=f"idem-buy-{uuid.uuid4().hex[:10]}",
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(buy_order)
        await session.flush()

        position = Position(
            id=uuid.uuid4(),
            order_id=buy_order.id,
            strategy_id=strategy.id,
            exchange_account_id=account.id,
            symbol="BTC/USDT",
            side="LONG",
            size=quantity,
            entry_price=entry_price,
            mark_price=entry_price,
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status=PositionStatus.OPEN.value,
            stop_price=stop_price,
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(position)
        await session.flush()

        stop = await stop_service.register_stop(
            session,
            position_id=position.id,
            stop_price=stop_price,
            timeframe=timeframe,
        )
        await session.commit()
        pos_id, stop_id = position.id, stop.id
    await dispose_db()
    return pos_id, stop_id


@pytest.mark.asyncio
async def test_stop_loaded_from_postgres_after_restart() -> None:
    """Verify active SyntheticStop is loaded from PostgreSQL by a fresh service after restart."""
    pos_id, stop_id = await _seed_open_position_with_stop()

    # Simulate restart with brand-new DB engine and new SyntheticStopService instance
    init_db()
    factory = get_session_factory()
    new_service = SyntheticStopService(exchange_adapter=FakeExchangeAdapter())
    async with factory() as session:
        loaded_stops = await new_service.load_active_stops_from_db(session)
        loaded_ids = {s.id for s in loaded_stops}
        assert stop_id in loaded_ids
        matching = next(s for s in loaded_stops if s.id == stop_id)
        assert matching.position_id == pos_id
        assert matching.status == SyntheticStopStatus.ARMED.value
    await dispose_db()


@pytest.mark.asyncio
async def test_stop_triggers_only_once() -> None:
    """Verify transactional compare-and-set ensures an ARMED stop triggers only once."""
    _, stop_id = await _seed_open_position_with_stop(
        entry_price=Decimal("60000.00"),
        stop_price=Decimal("58800.00"),
    )
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58500.00"))
    service = SyntheticStopService(exchange_adapter=fake_exchange)

    init_db()
    factory = get_session_factory()

    async def trigger_worker() -> bool:
        async with factory() as session:
            res = await service.evaluate_and_execute_stop(session, stop_id=stop_id)
            await session.commit()
            return res.triggered

    outcomes = await asyncio.gather(trigger_worker(), trigger_worker())
    await dispose_db()

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 1
    assert len(fake_exchange.place_order_attempts) == 1


@pytest.mark.asyncio
async def test_stop_retry_schedule_is_0_5_15_seconds() -> None:
    """Verify failed stop submission retries on 0s, 5s, 15s schedule and succeeds on recovery."""
    assert STOP_RETRY_SCHEDULE_SECONDS == (0, 5, 15)
    _, stop_id = await _seed_open_position_with_stop(
        entry_price=Decimal("60000.00"),
        stop_price=Decimal("58800.00"),
    )
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58500.00"))
    # Fail first 2 attempts (at t=0s and t=5s), succeed on 3rd attempt (at t=15s)
    fake_exchange.fail_next_place_order_count = 2

    recorded_sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded_sleeps.append(seconds)

    service = SyntheticStopService(exchange_adapter=fake_exchange)
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        res = await service.evaluate_and_execute_stop(
            session,
            stop_id=stop_id,
            sleep_fn=fake_sleep,
        )
        await session.commit()
        assert res.triggered is True
        assert res.status == SyntheticStopStatus.EXECUTED.value
        assert res.attempts_executed == 3
        assert res.schedule_offsets_seconds == (0, 5, 15)
        assert recorded_sleeps == [5.0, 10.0]
    await dispose_db()


@pytest.mark.asyncio
async def test_stop_duplicate_order_prevented() -> None:
    """Verify duplicate stop registration and duplicate stop order execution are prevented."""
    pos_id, stop_id = await _seed_open_position_with_stop()
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58000.00"))
    service = SyntheticStopService(exchange_adapter=fake_exchange)

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        # Calling register_stop again for the same position returns existing stop without duplicate
        dup_stop = await service.register_stop(
            session,
            position_id=pos_id,
            stop_price=Decimal("58800.00"),
        )
        assert dup_stop.id == stop_id

        # Trigger stop and then call evaluate again -> only 1 SELL order created in DB
        res1 = await service.evaluate_and_execute_stop(session, stop_id=stop_id)
        res2 = await service.evaluate_and_execute_stop(session, stop_id=stop_id)
        await session.commit()

        assert res1.triggered is True
        assert res2.triggered is False
        sell_order_count = await session.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.idempotency_key == res1.idempotency_key)
        )
        assert sell_order_count == 1
    await dispose_db()


@pytest.mark.asyncio
async def test_stop_failure_enters_manual_review() -> None:
    """Verify SyntheticStop transitions to MANUAL_REVIEW after 3 failed attempts (§12.2)."""
    pos_id, stop_id = await _seed_open_position_with_stop()
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58000.00"))
    fake_exchange.fail_next_place_order_count = 5

    async def no_sleep(_seconds: float) -> None:
        return None

    service = SyntheticStopService(exchange_adapter=fake_exchange)
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        res = await service.evaluate_and_execute_stop(
            session,
            stop_id=stop_id,
            sleep_fn=no_sleep,
        )
        await session.commit()

        assert res.triggered is True
        assert res.status == SyntheticStopStatus.MANUAL_REVIEW.value
        assert res.attempts_executed == 3

        pos = await session.scalar(select(Position).where(Position.id == pos_id))
        assert pos is not None
        assert pos.status == PositionStatus.MANUAL_REVIEW.value
    await dispose_db()


@pytest.mark.asyncio
async def test_stop_audit_record_created() -> None:
    """Verify SyntheticStop registration, trigger, and execution create audit records."""
    _, stop_id = await _seed_open_position_with_stop()
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58000.00"))
    service = SyntheticStopService(exchange_adapter=fake_exchange)

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        await service.evaluate_and_execute_stop(session, stop_id=stop_id)
        await session.commit()

        audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.target_type == "SYNTHETIC_STOP",
                        AuditLog.target_id == stop_id,
                    )
                )
            ).all()
        )
        actions = {a.action for a in audits}
        assert "STOP_REGISTERED" in actions
        assert "STOP_TRIGGERED" in actions
        assert "STOP_EXECUTED" in actions
    await dispose_db()


@pytest.mark.asyncio
async def test_stop_reconciliation_after_restart() -> None:
    """Verify reconcile_stops_after_restart marks stop EXECUTED if already filled on exchange."""
    pos_id, stop_id = await _seed_open_position_with_stop()
    fake_exchange = FakeExchangeAdapter()

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        stop = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.id == stop_id).with_for_update()
        )
        assert stop is not None
        stop.status = SyntheticStopStatus.SUBMITTED.value
        await session.commit()
        idem_key = stop.idempotency_key

    # Simulate that the exchange filled the order just before process restart
    await fake_exchange.place_order(
        symbol="BTC/USDT",
        side="SELL",
        order_type="MARKET",
        quantity=Decimal("0.25"),
        client_order_id=idem_key,
    )
    attempts_before = len(fake_exchange.place_order_attempts)

    service = SyntheticStopService(exchange_adapter=fake_exchange)
    async with factory() as session:
        await service.reconcile_stops_after_restart(session)
        await session.commit()

        refreshed_stop = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.id == stop_id)
        )
        refreshed_pos = await session.scalar(select(Position).where(Position.id == pos_id))
        assert refreshed_stop is not None
        assert refreshed_stop.status == SyntheticStopStatus.EXECUTED.value
        assert refreshed_stop.execution_order_id is not None
        assert refreshed_pos is not None
        assert refreshed_pos.status == PositionStatus.CLOSED.value
        # Reconciliation must NOT submit a second order
        assert len(fake_exchange.place_order_attempts) == attempts_before

        # Also test monitor_armed_stops and poll interval helper
        assert service.get_poll_interval_seconds("1H") == 30
        assert service.get_poll_interval_seconds("4H") == 60
        assert service.get_poll_interval_seconds("1D") == 300

        _, stop2_id = await _seed_open_position_with_stop()
        fake_exchange.set_ticker("BTC/USDT", price=Decimal("58000.00"))
        monitored = await service.monitor_armed_stops(session)
        await session.commit()
        assert any(r.stop_id == stop2_id and r.triggered for r in monitored)

        # Also test re-arming a TRIGGERED stop that was not submitted before restart
        _, stop3_id = await _seed_open_position_with_stop()
        stop3 = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.id == stop3_id).with_for_update()
        )
        assert stop3 is not None
        stop3.status = SyntheticStopStatus.TRIGGERED.value
        await session.flush()
        await service.reconcile_stops_after_restart(session)
        await session.commit()
        assert stop3.status == SyntheticStopStatus.ARMED.value

        # Price above stop_price -> not triggered
        _, stop4_id = await _seed_open_position_with_stop(
            entry_price=Decimal("60000.00"),
            stop_price=Decimal("58000.00"),
        )
        fake_exchange.set_ticker("BTC/USDT", price=Decimal("61000.00"))
        not_trig = await service.evaluate_and_execute_stop(session, stop_id=stop4_id)
        assert not_trig.triggered is False

        # Validation error branches
        from app.core.errors import InvalidRequestError, NotFoundError

        with pytest.raises(InvalidRequestError):
            SyntheticStopService(exchange_adapter=fake_exchange, current_timeframe="5M")
        with pytest.raises(InvalidRequestError):
            service.get_poll_interval_seconds("5M")
        with pytest.raises(InvalidRequestError):
            await service.register_stop(session, position_id=pos_id, stop_price=Decimal("0"))
        with pytest.raises(InvalidRequestError):
            await service.register_stop(
                session,
                position_id=pos_id,
                stop_price=Decimal("50000"),
                timeframe="5M",
            )
        with pytest.raises(NotFoundError):
            await service.register_stop(
                session,
                position_id=uuid.uuid4(),
                stop_price=Decimal("50000"),
            )
        with pytest.raises(NotFoundError):
            await service.evaluate_and_execute_stop(session, stop_id=uuid.uuid4())
    await dispose_db()


@pytest.mark.asyncio
async def test_synthetic_stop_triggers_only_once(migrated_db: None) -> None:
    """F2 Regression (§12.6): Verify Synthetic Stop triggers and executes at most once."""
    _ = migrated_db
    await test_stop_triggers_only_once()
