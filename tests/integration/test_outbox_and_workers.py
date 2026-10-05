"""Integration tests for Outbox, Dead-Letter, Adapters, Workers, and System/Risk APIs."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ApiRole,
    DeadLetterFailureClass,
    DeadLetterResolutionStatus,
    OutboxEventType,
    OutboxStatus,
    SignalApprovalStatus,
)
from app.core.errors import ForbiddenError
from app.core.metrics import OUTBOX_DEAD_LETTER_EVENTS_TOTAL
from app.db.models.audit_log import AuditLog
from app.db.models.dead_letter_event import DeadLetterEvent
from app.db.models.order import Order
from app.db.models.outbox_event import OutboxEvent
from app.db.models.signal import Signal
from app.db.models.system_state import SystemState
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.base import ExchangeAdapter, ExchangeAdapterRegistry
from app.integrations.exchange.errors import ExchangeError
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.integrations.exchange.paper import PaperTradingAdapter
from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter
from app.main import create_app, lifespan
from app.services.outbox import OutboxService
from app.services.reconciliation import ReconciliationService
from app.services.signal_engine import SignalEngine
from app.services.signal_lifecycle import _build_idempotency_state_key
from app.workers.approval_timeout import (
    WORKER_NAME as APPROVAL_TIMEOUT_WORKER_NAME,
)
from app.workers.approval_timeout import (
    run_approval_timeout_step,
)
from app.workers.outbox_publisher import (
    WORKER_NAME as OUTBOX_PUBLISHER_WORKER_NAME,
)
from app.workers.outbox_publisher import (
    run_outbox_publisher_step,
)
from app.workers.supervisor import WorkerSupervisor
from app.workers.synthetic_stop import (
    WORKER_NAME as SYNTHETIC_STOP_WORKER_NAME,
)
from app.workers.synthetic_stop import (
    run_synthetic_stop_step,
)
from app.workers.watchdog import check_system_watchdog
from tests.unit.test_trend_following_rule import make_trend_candles


@pytest.mark.asyncio
async def test_outbox_delivery_retry_dead_letter_and_replay(migrated_db: None) -> None:
    """Verify Outbox enqueue, retry backoff, Dead-Letter creation, and Admin replay (§19)."""
    notifier = PaperTelegramNotificationAdapter()
    service = OutboxService(notifier=notifier)
    agg_id = uuid.uuid4()

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        event = await service.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=agg_id,
            payload={"symbol": "BTC/USDT", "quantity": "0.1"},
        )
        await session.commit()
        event_db_id = event.id

    async def failing_consumer(_ev: OutboxEvent) -> None:
        raise RuntimeError("Consumer down")

    now = datetime.now(UTC)
    async with factory() as session:
        # Exhaust OUTBOX_MAX_RETRIES (5 retries)
        for i in range(5):
            await service.process_pending_events(
                session,
                handler=failing_consumer,
                now=now + timedelta(minutes=i * 10),
                failure_class=DeadLetterFailureClass.CONSUMER,
            )
        await session.commit()

        orig = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_db_id))
        assert orig is not None
        assert orig.status == OutboxStatus.DEAD_LETTER.value

        dlq = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == event_db_id)
        )
        assert dlq is not None
        assert dlq.resolution_status == DeadLetterResolutionStatus.OPEN.value
        dlq_id = dlq.id

        # Evaluate alerts
        alerts = await service.evaluate_dead_letter_alerts(
            session,
            now=now + timedelta(hours=2),
        )
        assert len(alerts) >= 1
        assert len(notifier.sent_messages) >= 1

        # Acknowledge and escalate
        await service.update_dead_letter_resolution(
            session,
            dead_letter_id=dlq_id,
            resolution_status=DeadLetterResolutionStatus.ACKNOWLEDGED,
            actor_id=uuid.uuid4(),
            actor_role=ApiRole.OPERATIONAL,
            resolution_note="Investigating consumer failure",
        )

        # Operational role cannot replay -> 403 ForbiddenError
        with pytest.raises(ForbiddenError):
            await service.replay_dead_letter(
                session,
                dead_letter_id=dlq_id,
                actor_id=uuid.uuid4(),
                actor_role=ApiRole.OPERATIONAL,
                resolution_note="Unauthorized replay attempt",
            )

        # Admin role replays Dead-Letter event and creates new OutboxEvent
        replayed_dlq, new_event = await service.replay_dead_letter(
            session,
            dead_letter_id=dlq_id,
            actor_id=uuid.uuid4(),
            actor_role=ApiRole.ADMIN,
            resolution_note="Consumer fixed; replaying event",
        )
        assert replayed_dlq.resolution_status == DeadLetterResolutionStatus.REPLAYED.value
        assert new_event.status == OutboxStatus.PENDING.value

        # Deliver the replayed event successfully
        delivered: list[uuid.UUID] = []

        async def ok_consumer(ev: OutboxEvent) -> None:
            delivered.append(ev.id)

        await service.process_pending_events(
            session,
            handler=ok_consumer,
            now=now + timedelta(hours=3),
        )
        await session.commit()
        assert new_event.id in delivered

        # Test duplicate delivery (resetting status to PENDING while in _processed_event_ids)
        new_event.status = OutboxStatus.PENDING.value
        await session.flush()
        await service.process_pending_events(
            session,
            handler=ok_consumer,
            now=now + timedelta(hours=4),
        )
        assert new_event.status == OutboxStatus.PUBLISHED.value

        # Idempotent enqueue_event with same event_id returns existing event
        dup_ev = await service.enqueue_event(
            session,
            event_type=OutboxEventType.SIGNAL_CREATED.value,
            aggregate_type="SIGNAL",
            aggregate_id=agg_id,
            payload={"signal_id": "SIG-1"},
            event_id=new_event.event_id,
        )
        assert dup_ev.id == new_event.id

        # Create another DLQ for non-critical aggregate to test WARNING & HIGH alert tiers
        sig_ev = await service.enqueue_event(
            session,
            event_type=OutboxEventType.SIGNAL_CREATED.value,
            aggregate_type="SIGNAL",
            aggregate_id=agg_id,
            payload={"signal_id": "SIG-2"},
        )
        for i in range(5):
            await service.process_pending_events(
                session,
                handler=failing_consumer,
                now=now + timedelta(hours=5, minutes=i * 10),
            )
        sig_dlq = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == sig_ev.id)
        )
        assert sig_dlq is not None
        await service.evaluate_dead_letter_alerts(
            session, now=sig_dlq.dead_lettered_at + timedelta(minutes=2)
        )
        await service.evaluate_dead_letter_alerts(
            session, now=sig_dlq.dead_lettered_at + timedelta(minutes=20)
        )
        await service.update_dead_letter_resolution(
            session,
            dead_letter_id=sig_dlq.id,
            resolution_status=DeadLetterResolutionStatus.ESCALATED,
            actor_id=uuid.uuid4(),
            actor_role=ApiRole.ADMIN,
            resolution_note="Escalating to admin",
        )

        # Validation error branches on OutboxService
        from app.core.errors import InvalidRequestError, InvalidStateError, NotFoundError

        with pytest.raises(InvalidRequestError):
            await service.update_dead_letter_resolution(
                session,
                dead_letter_id=sig_dlq.id,
                resolution_status=DeadLetterResolutionStatus.REPLAYED,
                actor_id=uuid.uuid4(),
                actor_role=ApiRole.ADMIN,
                resolution_note="Use replay instead",
            )
        with pytest.raises(NotFoundError):
            await service.update_dead_letter_resolution(
                session,
                dead_letter_id=uuid.uuid4(),
                resolution_status=DeadLetterResolutionStatus.DISCARDED,
                actor_id=uuid.uuid4(),
                actor_role=ApiRole.ADMIN,
                resolution_note="Missing",
            )
        with pytest.raises(InvalidRequestError):
            await service.replay_dead_letter(
                session,
                dead_letter_id=dlq_id,
                actor_id=uuid.uuid4(),
                actor_role=ApiRole.ADMIN,
                resolution_note="ab",
            )
        with pytest.raises(NotFoundError):
            await service.replay_dead_letter(
                session,
                dead_letter_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                actor_role=ApiRole.ADMIN,
                resolution_note="Missing DLQ",
            )
        with pytest.raises(InvalidStateError):
            await service.replay_dead_letter(
                session,
                dead_letter_id=dlq_id,
                actor_id=uuid.uuid4(),
                actor_role=ApiRole.ADMIN,
                resolution_note="Already replayed",
            )
        await session.commit()
    await dispose_db()


@pytest.mark.asyncio
async def test_dead_letter_metric_is_incremented(migrated_db: None) -> None:
    """Assert the Dead-Letter counter increments when a target event exhausts retries."""
    service = OutboxService()
    factory = get_session_factory()
    event_id: uuid.UUID | None = None
    now = datetime.now(UTC)
    counter = OUTBOX_DEAD_LETTER_EVENTS_TOTAL.labels(
        failure_class=DeadLetterFailureClass.CONSUMER.value
    )
    counter_before = counter._value.get()

    async def fail_target_event(event: OutboxEvent) -> None:
        if event.id == event_id:
            raise RuntimeError("Injected consumer failure for metric assertion")

    async with factory() as session:
        event = await service.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=uuid.uuid4(),
            payload={"metric_assertion": "dead-letter-counter"},
        )
        event_id = event.id
        await session.commit()

        for attempt in range(5):
            await service.process_pending_events(
                session,
                handler=fail_target_event,
                now=now + timedelta(minutes=10 * attempt),
                batch_size=1000,
                failure_class=DeadLetterFailureClass.CONSUMER,
            )
            await session.commit()

        dead_letter = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == event_id)
        )
        assert dead_letter is not None
        assert dead_letter.retry_count == 5
        assert dead_letter.resolution_status == DeadLetterResolutionStatus.OPEN.value

    assert counter._value.get() == counter_before + 1
    await dispose_db()


@pytest.mark.asyncio
async def test_signal_approval_rolls_back_when_outbox_insert_fails(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API approval rolls back all writes if ORDER_CREATED Outbox insertion fails."""
    init_db()
    factory = get_session_factory()
    candles_4h, candles_1h = make_trend_candles(symbol="BTC/USDT")
    async with factory() as session:
        signal = await SignalEngine().generate_trend_following_signal(
            session,
            symbol="BTC/USDT",
            candles_4h=candles_4h,
            candles_1h=candles_1h,
            data_quality_score=Decimal("0.96"),
            confidence_score=Decimal("0.84"),
            now=datetime.now(UTC),
        )
        assert signal is not None
        await session.commit()
        signal_id = signal.id
    await dispose_db()

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
            json={"reason": "Verify rollback after Outbox insert failure"},
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


@pytest.mark.asyncio
async def test_dead_letter_event_increments_metric(migrated_db: None) -> None:
    """A target event increments the Dead-Letter metric exactly once at retry exhaustion."""
    service = OutboxService()
    factory = get_session_factory()
    event_id: uuid.UUID | None = None
    now = datetime.now(UTC)
    counter = OUTBOX_DEAD_LETTER_EVENTS_TOTAL.labels(
        failure_class=DeadLetterFailureClass.CONSUMER.value
    )
    counter_before = counter._value.get()

    async def fail_target_event(event: OutboxEvent) -> None:
        if event.id == event_id:
            raise RuntimeError("Injected consumer failure for metric assertion")

    async with factory() as session:
        event = await service.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=uuid.uuid4(),
            payload={"metric_assertion": "dead-letter-event-increments-metric"},
        )
        event_id = event.id
        await session.commit()

        for attempt in range(5):
            await service.process_pending_events(
                session,
                handler=fail_target_event,
                now=now + timedelta(minutes=10 * attempt),
                batch_size=1000,
                failure_class=DeadLetterFailureClass.CONSUMER,
            )
            await session.commit()

        dead_letter = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == event_id)
        )
        assert dead_letter is not None
        assert dead_letter.retry_count == 5
        assert dead_letter.resolution_status == DeadLetterResolutionStatus.OPEN.value

    assert counter._value.get() == counter_before + 1
    await dispose_db()


@pytest.mark.asyncio
async def test_dead_letter_replay_creates_admin_audit_record(
    migrated_db: None,
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Admin replay is persisted with the schema-correct Dead-Letter audit tuple."""
    init_db()
    factory = get_session_factory()
    service = OutboxService()
    event_id: uuid.UUID | None = None
    now = datetime.now(UTC)

    async def fail_target_event(event: OutboxEvent) -> None:
        if event.id == event_id:
            raise RuntimeError("Injected failure to create a Dead-Letter record")

    async with factory() as session:
        event = await service.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=uuid.uuid4(),
            payload={"audit_assertion": "admin-replay"},
        )
        event_id = event.id
        await session.commit()

        for attempt in range(5):
            await service.process_pending_events(
                session,
                handler=fail_target_event,
                now=now + timedelta(minutes=5 * attempt),
                batch_size=1000,
                failure_class=DeadLetterFailureClass.CONSUMER,
            )
            await session.commit()

        dead_letter = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == event_id)
        )
        assert dead_letter is not None
        assert dead_letter.resolution_status == DeadLetterResolutionStatus.OPEN.value
        dead_letter_id = dead_letter.id
    await dispose_db()

    response = await async_client.post(
        f"/api/v1/system/dead-letters/{dead_letter_id}/replay",
        headers=admin_headers,
        json={"resolution_note": "Admin replay after consumer recovery"},
    )
    assert response.status_code == 200
    response_body = response.json()
    assert response_body["dead_letter_id"] == str(dead_letter_id)
    assert response_body["resolution_status"] == DeadLetterResolutionStatus.REPLAYED.value
    assert response_body["replayed_outbox_status"] == OutboxStatus.PENDING.value

    factory = get_session_factory()
    async with factory() as session:
        replay_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "DEAD_LETTER_EVENT_REPLAYED",
                AuditLog.target_type == "DEAD_LETTER_EVENT",
                AuditLog.target_id == dead_letter_id,
            )
        )
    assert replay_audit is not None
    assert replay_audit.action == "DEAD_LETTER_EVENT_REPLAYED"
    assert replay_audit.actor_role == ApiRole.ADMIN.value
    assert replay_audit.target_id == dead_letter_id
    assert replay_audit.detail_json is not None
    assert replay_audit.detail_json["replayed_outbox_event_id"]


@pytest.mark.asyncio
async def test_paper_trading_adapter_and_registry_constraints() -> None:
    """Verify PaperTradingAdapter and ExchangeAdapterRegistry forbid non-Paper adapters (§7.1)."""
    paper = PaperTradingAdapter()
    registry = ExchangeAdapterRegistry()
    registry.register("paper", paper)
    assert registry.get("paper") is paper
    assert registry.get_best() is paper
    registry.update_score("paper", Decimal("0.95"))

    ticker = await paper.get_ticker("BTC/USDT")
    assert isinstance(ticker.price, Decimal)
    ob = await paper.get_order_book("BTC/USDT")
    assert isinstance(ob.spread_pct, Decimal)
    assert paper.get_step_size("BTC/USDT") == Decimal("0.00001")

    receipt = await paper.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=Decimal("0.1"),
        client_order_id="paper-test-order-1",
    )
    assert receipt.status == "FILLED"
    positions = await paper.get_positions()
    assert "BTC/USDT" in positions

    # Defining a subclass outside PERMITTED_ADAPTER_CLASSES is forbidden
    with pytest.raises(ExchangeError, match="forbidden in MVP-0"):

        class ForbiddenLiveExchangeAdapter(ExchangeAdapter):  # type: ignore[misc]
            pass


@pytest.mark.asyncio
async def test_workers_and_supervisor_crash_fail_closed(migrated_db: None) -> None:
    """Verify worker steps, watchdog, and supervisor fail-closed crash handling (v4.3 §1.4)."""
    fake_exchange = FakeExchangeAdapter()
    notifier = PaperTelegramNotificationAdapter()

    init_db()
    factory = get_session_factory()
    async with factory() as session:
        await run_approval_timeout_step(session, exchange_adapter=fake_exchange, notifier=notifier)
        await run_synthetic_stop_step(session, exchange_adapter=fake_exchange, notifier=notifier)
        await run_outbox_publisher_step(session, notifier=notifier)
        recon = ReconciliationService(exchange_adapter=fake_exchange, notifier=notifier)
        report = await recon.reconcile_open_positions(session, sync_missing_to_exchange=True)
        assert report.success is True
        await session.commit()

    wd = await check_system_watchdog()
    assert wd["db_ok"] is True

    supervisor = WorkerSupervisor(
        exchange_adapter=fake_exchange,
        notifier=notifier,
        session_factory=factory,
    )
    await supervisor.recover_and_reconcile_on_startup(sync_missing_to_exchange=True)

    async def crashing_worker() -> None:
        raise RuntimeError("Simulated worker crash")

    with pytest.raises(RuntimeError, match="Simulated worker crash"):
        await supervisor.run_supervised_worker("test_crash_worker", crashing_worker)

    assert supervisor.execution_frozen is True
    await dispose_db()


@pytest.mark.asyncio
async def test_system_and_risk_api_endpoints(
    async_client: AsyncClient,
    operational_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    """Verify GET /api/v1/risk/status and Kill Switch resume HTTP endpoints (§13.6 & §16.3)."""
    risk_resp = await async_client.get("/api/v1/risk/status", headers=operational_headers)
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert risk_data["max_risk_per_trade"] == "0.005"
    assert "BTC/USDT" in risk_data["allowed_symbols"]

    # Activate emergency stop
    await async_client.post(
        "/api/v1/system/emergency-stop",
        headers=admin_headers,
        json={"reason": "API flow test"},
    )
    state_resp = await async_client.get(
        "/api/v1/system/emergency-stop",
        headers=admin_headers,
    )
    assert state_resp.status_code == 200
    assert state_resp.json()["is_active"] is True

    # Create resume request
    requester_id = str(uuid.uuid4())
    create_resp = await async_client.post(
        "/api/v1/system/emergency-stop/resume-requests",
        headers=admin_headers,
        json={"reason": "Root cause resolved via API", "requester_id": requester_id},
    )
    assert create_resp.status_code == 200
    req_id = create_resp.json()["id"]

    # Get resume request status
    get_resp = await async_client.get(
        f"/api/v1/system/emergency-stop/resume-requests/{req_id}",
        headers=operational_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "PENDING_FIRST_APPROVAL"

    # Reject resume request
    reject_resp = await async_client.post(
        f"/api/v1/system/emergency-stop/resume-requests/{req_id}/reject",
        headers=operational_headers,
        json={"actor_id": str(uuid.uuid4()), "reason": "Need additional verification"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    # Create a second resume request and approve via API with ADMIN + OPERATIONAL
    create_resp2 = await async_client.post(
        "/api/v1/system/emergency-stop/resume-requests",
        headers=admin_headers,
        json={"reason": "Full recovery verified", "requester_id": str(uuid.uuid4())},
    )
    assert create_resp2.status_code == 200
    req2_id = create_resp2.json()["id"]

    app1_resp = await async_client.post(
        f"/api/v1/system/emergency-stop/resume-requests/{req2_id}/approve",
        headers=admin_headers,
        json={"actor_id": str(uuid.uuid4())},
    )
    assert app1_resp.status_code == 200
    assert app1_resp.json()["status"] == "PENDING_SECOND_APPROVAL"

    app2_resp = await async_client.post(
        f"/api/v1/system/emergency-stop/resume-requests/{req2_id}/approve",
        headers=operational_headers,
        json={"actor_id": str(uuid.uuid4())},
    )
    assert app2_resp.status_code == 200
    assert app2_resp.json()["status"] == "APPROVED"
    assert app2_resp.json()["kill_switch_active"] is False
    assert app2_resp.json()["exposure_multiplier"] == "0.3000"


@pytest.mark.asyncio
async def test_dead_letter_admin_only_replay_via_api(
    async_client: AsyncClient,
    operational_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    """Verify POST /api/v1/system/dead-letters/{id}/replay is Admin-only (F2 Req #6)."""
    init_db()
    factory = get_session_factory()
    service = OutboxService()
    now = datetime.now(UTC)

    async def _fail_handler(_ev: OutboxEvent) -> None:
        raise RuntimeError("Downstream consumer failure")

    async with factory() as session:
        ev = await service.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=uuid.uuid4(),
            payload={"order_id": "DLQ-API-1"},
        )
        for i in range(5):
            await service.process_pending_events(
                session,
                handler=_fail_handler,
                now=now + timedelta(minutes=i * 5),
            )
        dlq = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.original_outbox_event_id == ev.id)
        )
        await session.commit()
        assert dlq is not None
        dlq_id = dlq.id

    await dispose_db()

    # 1. OPERATIONAL key is rejected with 403 Forbidden
    op_resp = await async_client.post(
        f"/api/v1/system/dead-letters/{dlq_id}/replay",
        headers=operational_headers,
        json={"resolution_note": "Operator attempting replay"},
    )
    assert op_resp.status_code == 403

    # 2. ADMIN key succeeds with 200 OK and creates a new PENDING Outbox event
    adm_resp = await async_client.post(
        f"/api/v1/system/dead-letters/{dlq_id}/replay",
        headers=admin_headers,
        json={"resolution_note": "Admin approved replay after fixing consumer"},
    )
    assert adm_resp.status_code == 200
    body = adm_resp.json()
    assert body["dead_letter_id"] == str(dlq_id)
    assert body["resolution_status"] == DeadLetterResolutionStatus.REPLAYED.value
    assert body["replayed_outbox_status"] == OutboxStatus.PENDING.value

    factory = get_session_factory()
    async with factory() as session:
        replay_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "DEAD_LETTER_EVENT_REPLAYED",
                AuditLog.target_type == "DEAD_LETTER_EVENT",
                AuditLog.target_id == dlq_id,
            )
        )
        assert replay_audit is not None
        assert replay_audit.action == "DEAD_LETTER_EVENT_REPLAYED"
        assert replay_audit.actor_role == ApiRole.ADMIN.value
        assert replay_audit.target_id == dlq_id
        assert replay_audit.detail_json is not None
        assert replay_audit.detail_json["replayed_outbox_event_id"]


@pytest.mark.asyncio
async def test_main_lifespan_starts_supervisor_recovers_stops_and_reconciles_positions(
    migrated_db: None,
) -> None:
    """Verify app/main.py:lifespan recovers stops, reconciles positions, and starts supervisor."""
    app_instance = create_app()
    async with lifespan(app_instance):
        assert app_instance.state.service_ready is True
        supervisor: WorkerSupervisor = app_instance.state.worker_supervisor
        assert isinstance(supervisor, WorkerSupervisor)
        assert app_instance.state.reconciliation_report is not None
        assert isinstance(app_instance.state.recovered_stops_count, int)

        for worker_name in (
            APPROVAL_TIMEOUT_WORKER_NAME,
            SYNTHETIC_STOP_WORKER_NAME,
            OUTBOX_PUBLISHER_WORKER_NAME,
        ):
            assert worker_name in supervisor._tasks
            assert not supervisor._tasks[worker_name].done()

    assert app_instance.state.service_ready is False
    assert len(app_instance.state.worker_supervisor._tasks) == 0
