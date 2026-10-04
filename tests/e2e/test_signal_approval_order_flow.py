"""End-to-end F3 signal approval, order handoff, protection, and rollback tests."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    OrderState,
    OutboxEventType,
    PositionStatus,
    RiskDecisionStatus,
    SignalApprovalStatus,
    SyntheticStopStatus,
)
from app.db.models.audit_log import AuditLog
from app.db.models.order import Order
from app.db.models.outbox_event import OutboxEvent
from app.db.models.position import Position
from app.db.models.signal import Signal
from app.db.models.synthetic_stop import SyntheticStop
from app.db.models.system_state import SystemState
from app.db.models.trade import Trade
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.services.outbox import OutboxService
from app.services.signal_engine import SignalEngine
from app.services.signal_lifecycle import _build_idempotency_state_key
from app.services.state_machine import StateMachineService
from app.services.synthetic_stop import SyntheticStopService
from tests.unit.test_mean_reversion_rule import make_mean_reversion_candles
from tests.unit.test_trend_following_rule import make_trend_candles


async def _generate_trend_signal(session: AsyncSession, *, now: datetime) -> Signal:
    """Persist one valid Signal Engine trend candidate for API-level E2E tests."""
    c4h, c1h = make_trend_candles(symbol="BTC/USDT")
    signal = await SignalEngine().generate_trend_following_signal(
        session,
        symbol="BTC/USDT",
        candles_4h=c4h,
        candles_1h=c1h,
        data_quality_score=Decimal("0.96"),
        confidence_score=Decimal("0.84"),
        now=now,
    )
    assert signal is not None
    return signal


async def _no_op_sleep(_seconds: float) -> None:
    """Avoid real retry delays in deterministic simulated-exchange tests."""
    return None


@pytest.mark.asyncio
async def test_signal_to_approval_to_order_flow(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Exercise Signal Engine -> API approval -> Risk Engine order -> read-only history."""
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()

    c4h, c1h_trend = make_trend_candles(symbol="BTC/USDT")
    c1h_mr = make_mean_reversion_candles(symbol="ETH/USDT")

    async with factory() as session:
        tf_signal = await engine.generate_trend_following_signal(
            session,
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h_trend,
            data_quality_score=Decimal("0.96"),
            confidence_score=Decimal("0.84"),
            now=now,
        )
        mr_signal = await engine.generate_mean_reversion_signal(
            session,
            symbol="ETH/USDT",
            candles_1h=c1h_mr,
            data_quality_score=Decimal("0.92"),
            confidence_score=Decimal("0.78"),
            now=now,
        )
        assert tf_signal is not None
        assert mr_signal is not None
        await session.commit()
        tf_id = tf_signal.id
        mr_id = mr_signal.id

    await dispose_db()

    list_resp = await async_client.get(
        "/api/v1/signals?approval_status=PENDING_APPROVAL",
        headers=operational_headers,
    )
    assert list_resp.status_code == 200
    listed_ids = {item["id"] for item in list_resp.json()["items"]}
    assert str(tf_id) in listed_ids
    assert str(mr_id) in listed_ids

    approve_idem = str(uuid.uuid4())
    app_resp = await async_client.post(
        f"/api/v1/signals/{tf_id}/approve",
        headers={**operational_headers, "Idempotency-Key": approve_idem},
        json={"reason": "Approved based on 4H bull trend and 1H breakout"},
    )
    assert app_resp.status_code == 200
    app_body = app_resp.json()
    assert app_body["approval_status"] == SignalApprovalStatus.APPROVED.value
    assert app_body["order"] is not None
    assert app_body["order"]["risk_decision"] == RiskDecisionStatus.APPROVE.value
    assert app_body["order"]["state_machine_state"] == OrderState.SUBMITTED.value
    created_order_id = app_body["order"]["order_id"]

    orders_resp = await async_client.get(
        f"/api/v1/orders?signal_id={tf_id}",
        headers=operational_headers,
    )
    assert orders_resp.status_code == 200
    assert orders_resp.json()["total"] == 1
    assert orders_resp.json()["items"][0]["id"] == created_order_id

    single_ord_resp = await async_client.get(
        f"/api/v1/orders/{created_order_id}",
        headers=operational_headers,
    )
    assert single_ord_resp.status_code == 200
    assert single_ord_resp.json()["signal_id"] == str(tf_id)

    rej_resp = await async_client.post(
        f"/api/v1/signals/{mr_id}/reject",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Operator skipped counter-trend setup"},
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["approval_status"] == SignalApprovalStatus.REJECTED.value
    assert rej_resp.json()["order"] is None

    tf_dec_resp = await async_client.get(
        f"/api/v1/decisions/{tf_id}",
        headers=operational_headers,
    )
    assert tf_dec_resp.status_code == 200
    tf_dec = tf_dec_resp.json()
    assert tf_dec["approval_status"] == SignalApprovalStatus.APPROVED.value
    assert len(tf_dec["orders"]) == 1
    tf_actions = [ev["action"] for ev in tf_dec["events"]]
    assert OutboxEventType.SIGNAL_CREATED.value in tf_actions
    assert OutboxEventType.SIGNAL_APPROVED.value in tf_actions
    assert OutboxEventType.ORDER_CREATED.value in tf_actions

    mr_dec_resp = await async_client.get(
        f"/api/v1/decisions/{mr_id}",
        headers=operational_headers,
    )
    assert mr_dec_resp.status_code == 200
    mr_dec = mr_dec_resp.json()
    assert mr_dec["approval_status"] == SignalApprovalStatus.REJECTED.value
    mr_actions = [ev["action"] for ev in mr_dec["events"]]
    assert OutboxEventType.SIGNAL_CREATED.value in mr_actions
    assert OutboxEventType.SIGNAL_REJECTED.value in mr_actions


@pytest.mark.asyncio
async def test_signal_to_approval_to_partial_fill_to_protection(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Protect the partial fill before the Fake adapter is asked to cancel its remainder."""
    factory = get_session_factory()
    async with factory() as session:
        signal = await _generate_trend_signal(session, now=datetime.now(UTC))
        await session.commit()
        signal_id = signal.id

    response = await async_client.post(
        f"/api/v1/signals/{signal_id}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approve partial-fill protection E2E"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_status"] == SignalApprovalStatus.APPROVED.value
    assert body["order"] is not None
    assert body["order"]["state_machine_state"] == OrderState.SUBMITTED.value
    order_id = uuid.UUID(body["order"]["order_id"])

    fake_exchange = FakeExchangeAdapter()
    fake_exchange.partial_fill_ratio = Decimal("0.40")
    state_machine = StateMachineService()
    cancellation_observations: list[tuple[Decimal, str]] = []

    async with factory() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        signal_row = await session.scalar(select(Signal).where(Signal.id == signal_id))
        assert order is not None
        assert signal_row is not None

        receipt = await fake_exchange.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=Decimal(str(order.quantity)),
            client_order_id=order.client_order_id,
            limit_price=order.limit_price,
        )
        assert receipt.status == "PARTIALLY_FILLED"
        assert Decimal("0") < receipt.filled_quantity < order.quantity
        order.filled_quantity = receipt.filled_quantity
        order.average_fill_price = receipt.average_fill_price
        await state_machine.transition_order_state(
            session,
            order_id=order.id,
            target_state=OrderState.PARTIALLY_FILLED,
            expected_from_state=OrderState.SUBMITTED,
            reason_code="E2E_PARTIAL_FILL_RECEIVED",
        )

        original_cancel = fake_exchange.cancel_order

        async def assert_protection_precedes_cancellation(client_order_id: str) -> bool:
            assert client_order_id == order.client_order_id
            position = await session.scalar(select(Position).where(Position.order_id == order.id))
            assert position is not None
            stop = await session.scalar(
                select(SyntheticStop).where(SyntheticStop.position_id == position.id)
            )
            assert stop is not None
            assert position.status == PositionStatus.OPEN.value
            assert position.size == receipt.filled_quantity
            assert stop.status == SyntheticStopStatus.ARMED.value
            assert stop.quantity == receipt.filled_quantity
            cancellation_observations.append((position.size, stop.status))
            return await original_cancel(client_order_id)

        monkeypatch.setattr(fake_exchange, "cancel_order", assert_protection_precedes_cancellation)
        result_order, position, stop = await state_machine.handle_partial_fill_timeout(
            session,
            order_id=order.id,
            exchange_adapter=fake_exchange,
            stop_price=Decimal(str(signal_row.stop_loss_price)),
            now=datetime.now(UTC),
        )
        await session.commit()

        assert result_order.state_machine_state == OrderState.CANCEL_REMAINDER.value
        assert position.status == PositionStatus.OPEN.value
        assert position.size == receipt.filled_quantity
        assert stop.status == SyntheticStopStatus.ARMED.value
        assert cancellation_observations == [
            (receipt.filled_quantity, SyntheticStopStatus.ARMED.value)
        ]

    cancelled_receipt = await fake_exchange.get_order_status(body["order"]["client_order_id"])
    assert cancelled_receipt is not None
    assert cancelled_receipt.status == "CANCELLED"
    assert cancelled_receipt.filled_quantity == receipt.filled_quantity


@pytest.mark.asyncio
async def test_signal_to_approval_to_synthetic_stop_execution(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Approve a Signal, fill its Paper order, trigger its stop, and verify position closure."""
    factory = get_session_factory()
    async with factory() as session:
        signal = await _generate_trend_signal(session, now=datetime.now(UTC))
        await session.commit()
        signal_id = signal.id

    response = await async_client.post(
        f"/api/v1/signals/{signal_id}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approve synthetic-stop execution E2E"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_status"] == SignalApprovalStatus.APPROVED.value
    assert body["order"] is not None
    assert body["order"]["risk_decision"] == RiskDecisionStatus.APPROVE.value
    order_id = uuid.UUID(body["order"]["order_id"])

    fake_exchange = FakeExchangeAdapter()
    state_machine = StateMachineService()
    stop_service = SyntheticStopService(exchange_adapter=fake_exchange)

    async with factory() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        signal_row = await session.scalar(select(Signal).where(Signal.id == signal_id))
        assert order is not None
        assert signal_row is not None

        entry_receipt = await fake_exchange.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=Decimal(str(order.quantity)),
            client_order_id=order.client_order_id,
            limit_price=order.limit_price,
        )
        assert entry_receipt.status == "FILLED"
        order.filled_quantity = entry_receipt.filled_quantity
        order.average_fill_price = entry_receipt.average_fill_price
        await state_machine.transition_order_state(
            session,
            order_id=order.id,
            target_state=OrderState.FILLED,
            expected_from_state=OrderState.SUBMITTED,
            reason_code="E2E_PAPER_FILL_RECEIVED",
        )

        position = Position(
            id=uuid.uuid4(),
            order_id=order.id,
            strategy_id=order.strategy_id,
            exchange_account_id=order.exchange_account_id,
            symbol=order.symbol,
            side="LONG",
            size=entry_receipt.filled_quantity,
            entry_price=entry_receipt.average_fill_price or Decimal(str(order.limit_price)),
            mark_price=entry_receipt.average_fill_price or Decimal(str(order.limit_price)),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status=PositionStatus.OPEN.value,
            stop_price=Decimal(str(signal_row.stop_loss_price)),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=1,
        )
        session.add(position)
        await session.flush()
        session.add(
            Trade(
                id=uuid.uuid4(),
                order_id=order.id,
                position_id=position.id,
                exchange_trade_id=entry_receipt.exchange_order_id,
                fill_price=entry_receipt.average_fill_price or Decimal(str(order.limit_price)),
                fill_quantity=entry_receipt.filled_quantity,
                fee=entry_receipt.fee,
                executed_at=entry_receipt.executed_at,
                created_at=datetime.now(UTC),
            )
        )
        stop = await stop_service.register_stop(
            session,
            position_id=position.id,
            stop_price=Decimal(str(signal_row.stop_loss_price)),
            timeframe=signal_row.timeframe,
        )
        await session.commit()
        stop_id = stop.id
        position_id = position.id
        position_quantity = position.size
        stop_price = Decimal(str(stop.stop_price))

    trigger_price = stop_price - Decimal("1")
    assert trigger_price > Decimal("0")
    fake_exchange.set_ticker("BTC/USDT", price=trigger_price)

    async with factory() as session:
        result = await stop_service.evaluate_and_execute_stop(
            session,
            stop_id=stop_id,
            current_price=trigger_price,
            sleep_fn=_no_op_sleep,
        )
        await session.commit()

        assert result.triggered is True
        assert result.status == SyntheticStopStatus.EXECUTED.value
        assert result.execution_order_id is not None

        closed_position = await session.scalar(select(Position).where(Position.id == position_id))
        assert closed_position is not None
        assert closed_position.status == PositionStatus.CLOSED.value
        assert closed_position.realized_pnl is not None

        execution_order = await session.scalar(
            select(Order).where(Order.id == result.execution_order_id)
        )
        assert execution_order is not None
        assert execution_order.side == "SELL"
        assert execution_order.filled_quantity == position_quantity
        assert execution_order.status == OrderState.FILLED.value

        stop_audit_actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.target_type == "SYNTHETIC_STOP",
                        AuditLog.target_id == stop_id,
                    )
                )
            ).all()
        )
        assert "STOP_TRIGGERED" in stop_audit_actions
        assert "STOP_EXECUTED" in stop_audit_actions

    assert await fake_exchange.get_positions() == {}


@pytest.mark.asyncio
async def test_approval_rolls_back_when_outbox_insert_fails(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ORDER_CREATED Outbox insert failure rolls back API approval and every related row."""
    factory = get_session_factory()
    async with factory() as session:
        signal = await _generate_trend_signal(session, now=datetime.now(UTC))
        await session.commit()
        signal_id = signal.id

    idempotency_key = f"outbox-failure-{uuid.uuid4()}"
    failed_order_ids: list[uuid.UUID] = []
    original_enqueue = OutboxService.enqueue_event

    async def fail_order_created_insert(
        self: OutboxService,
        session: AsyncSession,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        payload: dict[str, Any],
        event_version: int = 1,
        event_id: uuid.UUID | None = None,
    ) -> OutboxEvent:
        if event_type == OutboxEventType.ORDER_CREATED.value:
            failed_order_ids.append(aggregate_id)
            raise RuntimeError("injected ORDER_CREATED Outbox insert failure")
        return await original_enqueue(
            self,
            session,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            event_version=event_version,
            event_id=event_id,
        )

    monkeypatch.setattr(OutboxService, "enqueue_event", fail_order_created_insert)
    try:
        response = await async_client.post(
            f"/api/v1/signals/{signal_id}/approve",
            headers={**operational_headers, "Idempotency-Key": idempotency_key},
            json={"reason": "Exercise transaction rollback on Outbox failure"},
        )
    except RuntimeError as exc:
        assert "injected ORDER_CREATED Outbox insert failure" in str(exc)
    else:
        assert response.status_code == 500
        assert response.json()["code"] == "INTERNAL_ERROR"
    assert len(failed_order_ids) == 1
    failed_order_id = failed_order_ids[0]

    async with factory() as session:
        persisted_signal = await session.scalar(select(Signal).where(Signal.id == signal_id))
        assert persisted_signal is not None
        assert persisted_signal.approval_status == SignalApprovalStatus.PENDING_APPROVAL.value

        order_count = await session.scalar(
            select(func.count()).select_from(Order).where(Order.signal_id == signal_id)
        )
        approval_audit_count = await session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.target_type == "SIGNAL",
                AuditLog.target_id == signal_id,
                AuditLog.action == OutboxEventType.SIGNAL_APPROVED.value,
            )
        )
        approval_event_count = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.aggregate_type == "SIGNAL",
                OutboxEvent.aggregate_id == signal_id,
                OutboxEvent.event_type == OutboxEventType.SIGNAL_APPROVED.value,
            )
        )
        order_audit_count = await session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.target_type == "ORDER",
                AuditLog.target_id == failed_order_id,
                AuditLog.action == OutboxEventType.ORDER_CREATED.value,
            )
        )
        order_event_count = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.aggregate_type == "ORDER",
                OutboxEvent.aggregate_id == failed_order_id,
                OutboxEvent.event_type == OutboxEventType.ORDER_CREATED.value,
            )
        )
        idempotency_record = await session.scalar(
            select(SystemState).where(
                SystemState.state_key == _build_idempotency_state_key(idempotency_key)
            )
        )
        assert order_count == 0
        assert approval_audit_count == 0
        assert approval_event_count == 0
        assert order_audit_count == 0
        assert order_event_count == 0
        assert idempotency_record is None
