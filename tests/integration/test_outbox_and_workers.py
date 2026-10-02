"""Integration tests for Outbox, Dead-Letter, Adapters, Workers, and System/Risk APIs."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.enums import (
    ApiRole,
    DeadLetterFailureClass,
    DeadLetterResolutionStatus,
    OutboxEventType,
    OutboxStatus,
)
from app.core.errors import ForbiddenError
from app.db.models.dead_letter_event import DeadLetterEvent
from app.db.models.outbox_event import OutboxEvent
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.base import ExchangeAdapter, ExchangeAdapterRegistry
from app.integrations.exchange.errors import ExchangeError
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.integrations.exchange.paper import PaperTradingAdapter
from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter
from app.services.outbox import OutboxService
from app.services.reconciliation import ReconciliationService
from app.workers.approval_timeout import run_approval_timeout_step
from app.workers.outbox_publisher import run_outbox_publisher_step
from app.workers.supervisor import WorkerSupervisor
from app.workers.synthetic_stop import run_synthetic_stop_step
from app.workers.watchdog import check_system_watchdog


@pytest.mark.asyncio
async def test_outbox_delivery_retry_dead_letter_and_replay() -> None:
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
async def test_workers_and_supervisor_crash_fail_closed() -> None:
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
