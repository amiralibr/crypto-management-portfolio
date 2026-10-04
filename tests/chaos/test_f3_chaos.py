"""Contract §21.6 F3 chaos tests using real CI PostgreSQL/Redis service restarts."""

import asyncio
import ipaddress
import os
import shutil
import socket
import subprocess
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import ParamSpec, TypeVar

import asyncpg
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import (
    ApiRole,
    DeadLetterFailureClass,
    DeadLetterResolutionStatus,
    OrderState,
    OutboxEventType,
    OutboxStatus,
    PositionStatus,
    RiskDecisionStatus,
    SignalApprovalStatus,
    SyntheticStopStatus,
)
from app.core.metrics import WORKER_ALIVE_GAUGE, WORKER_RESTARTS_TOTAL
from app.core.redis import RedisClient
from app.db.models.audit_log import AuditLog
from app.db.models.dead_letter_event import DeadLetterEvent
from app.db.models.order import Order
from app.db.models.outbox_event import OutboxEvent
from app.db.models.position import Position
from app.db.models.synthetic_stop import SyntheticStop
from app.db.models.system_state import SystemState
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.base import (
    PERMITTED_ADAPTER_CLASSES,
    ExchangeAdapterRegistry,
    ExchangeOrderReceipt,
)
from app.integrations.exchange.errors import ExchangeConnectionError
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.integrations.exchange.paper import PaperTradingAdapter
from app.services.kill_switch import KILL_SWITCH_STATE_KEY, KillSwitchService
from app.services.outbox import OutboxService
from app.services.signal_lifecycle import SignalLifecycleService
from app.services.synthetic_stop import SyntheticStopService
from app.workers.supervisor import WorkerSupervisor
from tests.conftest import TEST_DB_URL, TEST_REDIS_URL
from tests.factories import SyntheticSignalBundle, TestSignalFactory

POSTGRES_SERVICE_IMAGE = "postgres:16-alpine"
REDIS_SERVICE_IMAGE = "redis:7-alpine"
_P = ParamSpec("_P")
_R = TypeVar("_R")


def _dispose_test_database_engine(
    test_function: Callable[_P, Awaitable[_R]],
) -> Callable[_P, Awaitable[_R]]:
    """Dispose SQLAlchemy's loop-bound async engine on the same loop as each test."""

    @wraps(test_function)
    async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await test_function(*args, **kwargs)
        finally:
            await dispose_db()

    return wrapped


def _docker_service_container_id(image: str) -> str:
    """Identify exactly one Actions service container; CI must not silently skip restarts."""
    if shutil.which("docker") is None:
        if os.getenv("CI", "").lower() == "true":
            pytest.fail("Docker CLI is required in CI for genuine service-restart chaos tests")
        pytest.skip("Docker CLI is unavailable; service-restart chaos test requires Docker")

    result = subprocess.run(
        ["docker", "ps", "--filter", f"ancestor={image}", "--format", "{{.ID}}"],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        message = f"Cannot inspect Docker service containers for {image}: {result.stderr.strip()}"
        if os.getenv("CI", "").lower() == "true":
            pytest.fail(message)
        pytest.skip(message)

    container_ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(container_ids) != 1:
        message = f"Expected one running {image} service container, found {len(container_ids)}"
        if os.getenv("CI", "").lower() == "true":
            pytest.fail(message)
        pytest.skip(message)
    return container_ids[0]


def _restart_service_container(image: str) -> None:
    """Restart the actual PostgreSQL or Redis Actions service container."""
    container_id = _docker_service_container_id(image)
    subprocess.run(
        ["docker", "restart", "--time", "10", container_id],
        capture_output=True,
        check=True,
        text=True,
        timeout=45,
    )


async def _wait_for_postgres(timeout_seconds: float = 60.0) -> None:
    """Wait for the restarted PostgreSQL service to accept authenticated SQL queries."""
    dsn = TEST_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_error: Exception | None = None
    while asyncio.get_running_loop().time() < deadline:
        connection: asyncpg.Connection | None = None
        try:
            connection = await asyncpg.connect(dsn, timeout=2.0)
            if await connection.fetchval("SELECT 1") == 1:
                return
        except Exception as exc:
            last_error = exc
        finally:
            if connection is not None:
                await connection.close()
        await asyncio.sleep(0.5)
    pytest.fail(f"PostgreSQL did not recover after container restart: {last_error!r}")


async def _wait_for_redis(timeout_seconds: float = 45.0) -> RedisClient:
    """Wait for a restarted Redis service and return a fresh connected wrapper."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        client = RedisClient(TEST_REDIS_URL)
        if await client.ping():
            return client
        await client.close()
        await asyncio.sleep(0.5)
    pytest.fail("Redis did not recover after container restart")


def _make_order(
    bundle: SyntheticSignalBundle,
    *,
    state: OrderState,
    quantity: Decimal = Decimal("0.250000000000"),
    filled_quantity: Decimal = Decimal("0"),
    average_fill_price: Decimal | None = None,
) -> Order:
    """Build a unique Paper-mode order row for test-scoped chaos injections."""
    now = datetime.now(UTC)
    return Order(
        id=uuid.uuid4(),
        client_order_id=f"f3-chaos-client-{uuid.uuid4().hex[:12]}",
        signal_id=bundle.signal.id,
        strategy_id=bundle.strategy.id,
        exchange_account_id=bundle.exchange_account.id,
        symbol=bundle.signal.symbol,
        side="BUY",
        order_type="LIMIT",
        quantity=quantity,
        limit_price=bundle.signal.reference_price,
        filled_quantity=filled_quantity,
        average_fill_price=average_fill_price,
        status=state.value,
        state_machine_state=state.value,
        risk_decision=RiskDecisionStatus.APPROVE.value,
        risk_reason_codes=[],
        idempotency_key=f"f3-chaos-idem-{uuid.uuid4().hex[:12]}",
        expires_at=None,
        created_at=now,
        updated_at=now,
        version=1,
    )


async def _seed_open_position_with_stop(
    session_factory: async_sessionmaker[AsyncSession],
    fake_exchange: FakeExchangeAdapter,
    *,
    quantity: Decimal = Decimal("0.250000000000"),
    entry_price: Decimal = Decimal("60000.00"),
    stop_price: Decimal = Decimal("58800.00"),
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Commit one open Paper position with an ARMED PostgreSQL Synthetic Stop."""
    now = datetime.now(UTC)
    stop_service = SyntheticStopService(exchange_adapter=fake_exchange)
    async with session_factory() as session:
        bundle = await TestSignalFactory.create_signal(
            session,
            entry_price=entry_price,
            atr_14=(entry_price - stop_price) / Decimal("2"),
            now=now,
        )
        order = _make_order(
            bundle,
            state=OrderState.PROTECTED,
            quantity=quantity,
            filled_quantity=quantity,
            average_fill_price=entry_price,
        )
        session.add(order)
        await session.flush()
        position = Position(
            id=uuid.uuid4(),
            order_id=order.id,
            strategy_id=bundle.strategy.id,
            exchange_account_id=bundle.exchange_account.id,
            symbol=bundle.signal.symbol,
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
            timeframe=bundle.signal.timeframe,
        )
        await session.commit()
        position_id = position.id
        stop_id = stop.id
        order_id = order.id

    fake_exchange.set_position(
        "BTC/USDT",
        quantity=quantity,
        entry_price=entry_price,
    )
    return position_id, stop_id, order_id


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_worker_kill_during_order_processing(migrated_db: None) -> None:
    """An injected worker death rolls back in-flight order writes and activates the Kill Switch."""
    factory = get_session_factory()
    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session)
        order = _make_order(bundle, state=OrderState.SUBMITTED)
        session.add(order)
        await session.commit()
        order_id = order.id

    fake_exchange = FakeExchangeAdapter()
    supervisor = WorkerSupervisor(exchange_adapter=fake_exchange, session_factory=factory)
    worker_name = f"f3_order_processing_{uuid.uuid4().hex[:8]}"
    processing_started = asyncio.Event()
    restarts_before = WORKER_RESTARTS_TOTAL.labels(worker_name=worker_name)._value.get()

    async def crash_while_processing_order() -> None:
        async with factory() as session:
            order = await session.scalar(
                select(Order).where(Order.id == order_id).with_for_update()
            )
            assert order is not None
            assert order.state_machine_state == OrderState.SUBMITTED.value
            order.filled_quantity = order.quantity
            await session.flush()
            processing_started.set()
            raise RuntimeError("injected worker kill while processing order")

    with pytest.raises(RuntimeError, match="injected worker kill"):
        await supervisor.run_supervised_worker(worker_name, crash_while_processing_order)

    assert processing_started.is_set()
    assert supervisor.execution_frozen is True
    assert WORKER_RESTARTS_TOTAL.labels(worker_name=worker_name)._value.get() == restarts_before + 1
    assert WORKER_ALIVE_GAUGE.labels(worker_name=worker_name)._value.get() == 0.0

    async with factory() as session:
        order = await session.scalar(select(Order).where(Order.id == order_id))
        assert order is not None
        assert order.filled_quantity == Decimal("0")
        assert order.state_machine_state == OrderState.CANCELLED.value

        state = await session.scalar(
            select(SystemState).where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
        )
        assert state is not None
        assert state.is_active is True

        worker_audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.action == "WORKER_FAILURE",
                        AuditLog.target_type == "WORKER",
                    )
                )
            ).all()
        )
        assert any(
            audit.detail_json is not None
            and audit.detail_json.get("worker_name") == worker_name
            and audit.detail_json.get("execution_frozen") is True
            for audit in worker_audits
        )

        # Restore shared test state after asserting the durable fail-closed outcome.
        state.is_active = False
        state.resume_status = None
        await session.commit()
        await KillSwitchService(exchange_adapter=fake_exchange).is_active(session)


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_worker_restart_recovers_synthetic_stop(migrated_db: None) -> None:
    """A fresh WorkerSupervisor re-arms a committed in-flight stop and it then executes."""
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    position_id, stop_id, _ = await _seed_open_position_with_stop(factory, fake_exchange)

    async with factory() as session:
        stop = await session.scalar(select(SyntheticStop).where(SyntheticStop.id == stop_id))
        assert stop is not None
        stop.status = SyntheticStopStatus.SUBMITTING.value
        await session.commit()

    restarted_supervisor = WorkerSupervisor(exchange_adapter=fake_exchange, session_factory=factory)
    recovered_stops, _report = await restarted_supervisor.recover_and_reconcile_on_startup()
    assert recovered_stops >= 1

    async with factory() as session:
        recovered_stop = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.id == stop_id)
        )
        assert recovered_stop is not None
        assert recovered_stop.status == SyntheticStopStatus.ARMED.value
        rearm_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.target_type == "SYNTHETIC_STOP",
                AuditLog.target_id == stop_id,
                AuditLog.action == "SYNTHETIC_STOP_RECONCILED",
                AuditLog.reason_code == "REARMED_AFTER_RESTART",
            )
        )
        assert rearm_audit is not None

    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58799.00"))
    stop_service = SyntheticStopService(exchange_adapter=fake_exchange)
    async with factory() as session:
        result = await stop_service.evaluate_and_execute_stop(
            session,
            stop_id=stop_id,
            current_price=Decimal("58799.00"),
            sleep_fn=lambda _seconds: asyncio.sleep(0),
        )
        await session.commit()
        assert result.status == SyntheticStopStatus.EXECUTED.value
        position = await session.scalar(select(Position).where(Position.id == position_id))
        assert position is not None
        assert position.status == PositionStatus.CLOSED.value


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_worker_restart_does_not_duplicate_stop_order(
    migrated_db: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recover an exchange-accepted stop after worker cancellation without resubmitting it."""
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    position_id, stop_id, _ = await _seed_open_position_with_stop(factory, fake_exchange)
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("58799.00"))

    async with factory() as session:
        stop = await session.scalar(select(SyntheticStop).where(SyntheticStop.id == stop_id))
        assert stop is not None
        idempotency_key = stop.idempotency_key

    stop_service = SyntheticStopService(exchange_adapter=fake_exchange)
    original_place_order = fake_exchange.place_order

    async def accept_then_kill_worker(
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        client_order_id: str,
        limit_price: Decimal | None = None,
    ) -> ExchangeOrderReceipt:
        receipt = await original_place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            client_order_id=client_order_id,
            limit_price=limit_price,
        )
        if client_order_id == idempotency_key:
            raise asyncio.CancelledError("injected worker termination after exchange acceptance")
        return receipt

    monkeypatch.setattr(fake_exchange, "place_order", accept_then_kill_worker)
    with pytest.raises(asyncio.CancelledError, match="injected worker termination"):
        async with factory() as session:
            await stop_service.evaluate_and_execute_stop(
                session,
                stop_id=stop_id,
                current_price=Decimal("58799.00"),
                sleep_fn=lambda _seconds: asyncio.sleep(0),
            )

    async with factory() as session:
        rolled_back_stop = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.id == stop_id)
        )
        assert rolled_back_stop is not None
        assert rolled_back_stop.status == SyntheticStopStatus.ARMED.value
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.idempotency_key == idempotency_key)
            )
            == 0
        )

    restarted_supervisor = WorkerSupervisor(exchange_adapter=fake_exchange, session_factory=factory)
    await restarted_supervisor.recover_and_reconcile_on_startup()

    async with factory() as session:
        recovered_stop = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.id == stop_id)
        )
        assert recovered_stop is not None
        assert recovered_stop.status == SyntheticStopStatus.EXECUTED.value
        assert recovered_stop.execution_order_id is not None
        recovered_order_count = await session.scalar(
            select(func.count()).select_from(Order).where(Order.idempotency_key == idempotency_key)
        )
        assert recovered_order_count == 1
        position = await session.scalar(select(Position).where(Position.id == position_id))
        assert position is not None
        assert position.status == PositionStatus.CLOSED.value

    accepted_attempts = [
        client_order_id
        for client_order_id, _created_at in fake_exchange.place_order_attempts
        if client_order_id == idempotency_key
    ]
    assert accepted_attempts == [idempotency_key]


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_database_restart_during_outbox_delivery(migrated_db: None) -> None:
    """Restart the real PostgreSQL service inside an Outbox handler and recover delivery."""
    _docker_service_container_id(POSTGRES_SERVICE_IMAGE)
    factory = get_session_factory()
    outbox = OutboxService()
    async with factory() as session:
        event = await outbox.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=uuid.uuid4(),
            payload={"chaos_probe": "postgres-restart-during-delivery"},
        )
        await session.commit()
        event_id = event.id

    restart_count = 0
    interrupted_delivery: list[uuid.UUID] = []

    async def restart_postgres_during_target_delivery(event: OutboxEvent) -> None:
        nonlocal restart_count
        if event.id == event_id:
            interrupted_delivery.append(event.id)
            if restart_count == 0:
                restart_count += 1
                await asyncio.to_thread(_restart_service_container, POSTGRES_SERVICE_IMAGE)
                await _wait_for_postgres()

    database_interruption_errors: list[str] = []
    try:
        async with factory() as session:
            await outbox.process_pending_events(
                session,
                handler=restart_postgres_during_target_delivery,
                now=datetime.now(UTC) + timedelta(hours=1),
                batch_size=1000,
            )
            await session.commit()
    except SQLAlchemyError as exc:
        # The in-flight PostgreSQL transaction may correctly abort when its connection is killed.
        database_interruption_errors.append(type(exc).__name__)
    finally:
        await dispose_db()

    await _wait_for_postgres()
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        event_after_restart = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        assert event_after_restart is not None
        assert event_after_restart.status in {
            OutboxStatus.PENDING.value,
            OutboxStatus.FAILED.value,
            OutboxStatus.PUBLISHED.value,
        }

        if event_after_restart.status != OutboxStatus.PUBLISHED.value:
            delivered_after_restart: list[uuid.UUID] = []
            restarted_outbox = OutboxService()

            async def recover_delivery(event: OutboxEvent) -> None:
                if event.id == event_id:
                    delivered_after_restart.append(event.id)

            await restarted_outbox.process_pending_events(
                session,
                handler=recover_delivery,
                now=datetime.now(UTC) + timedelta(hours=2),
                batch_size=1000,
            )
            await session.commit()
            assert event_id in delivered_after_restart
        else:
            await session.commit()

        final_event = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id))
        assert final_event is not None
        assert (
            final_event.status == OutboxStatus.PUBLISHED.value
        ), f"Database interruption errors: {database_interruption_errors}"

    assert restart_count == 1
    assert interrupted_delivery == [event_id]
    await dispose_db()


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_database_restart_does_not_lose_committed_order(migrated_db: None) -> None:
    """A committed order remains byte-for-byte identifiable after PostgreSQL container restart."""
    _docker_service_container_id(POSTGRES_SERVICE_IMAGE)
    factory = get_session_factory()
    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session)
        order = _make_order(
            bundle,
            state=OrderState.FILLED,
            quantity=Decimal("0.125000000000"),
            filled_quantity=Decimal("0.125000000000"),
            average_fill_price=Decimal("60000.00"),
        )
        session.add(order)
        await session.commit()
        order_id = order.id
        client_order_id = order.client_order_id
        idempotency_key = order.idempotency_key

    await dispose_db()
    await asyncio.to_thread(_restart_service_container, POSTGRES_SERVICE_IMAGE)
    await _wait_for_postgres()
    init_db()

    async with get_session_factory()() as session:
        committed_order = await session.scalar(select(Order).where(Order.id == order_id))
        assert committed_order is not None
        assert committed_order.client_order_id == client_order_id
        assert committed_order.idempotency_key == idempotency_key
        assert committed_order.state_machine_state == OrderState.FILLED.value
        assert committed_order.filled_quantity == Decimal("0.125000000000")
    await dispose_db()


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_database_restart_does_not_lose_dead_letter_event(migrated_db: None) -> None:
    """A committed Dead-Letter row and its original Outbox link survive PostgreSQL restart."""
    _docker_service_container_id(POSTGRES_SERVICE_IMAGE)
    factory = get_session_factory()
    outbox = OutboxService()
    event_id: uuid.UUID | None = None
    now = datetime.now(UTC)

    async def fail_only_target(event: OutboxEvent) -> None:
        if event.id == event_id:
            raise RuntimeError("injected consumer failure before PostgreSQL restart")

    async with factory() as session:
        event = await outbox.enqueue_event(
            session,
            event_type=OutboxEventType.ORDER_CREATED.value,
            aggregate_type="ORDER",
            aggregate_id=uuid.uuid4(),
            payload={"chaos_probe": "committed-dead-letter-survival"},
        )
        event_id = event.id
        await session.commit()

        for attempt in range(5):
            await outbox.process_pending_events(
                session,
                handler=fail_only_target,
                now=now + timedelta(minutes=10 * attempt),
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
        expected_event_id = dead_letter.event_id
        expected_payload = dict(dead_letter.payload_json)

    await dispose_db()
    await asyncio.to_thread(_restart_service_container, POSTGRES_SERVICE_IMAGE)
    await _wait_for_postgres()
    init_db()

    async with get_session_factory()() as session:
        persisted_dead_letter = await session.scalar(
            select(DeadLetterEvent).where(DeadLetterEvent.id == dead_letter_id)
        )
        assert persisted_dead_letter is not None
        assert persisted_dead_letter.original_outbox_event_id == event_id
        assert persisted_dead_letter.event_id == expected_event_id
        assert persisted_dead_letter.payload_json == expected_payload
        assert persisted_dead_letter.resolution_status == DeadLetterResolutionStatus.OPEN.value
        persisted_outbox_event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id)
        )
        assert persisted_outbox_event is not None
        assert persisted_outbox_event.status == OutboxStatus.DEAD_LETTER.value
    await dispose_db()


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_redis_restart_does_not_corrupt_kill_switch_state(migrated_db: None) -> None:
    """Restart Redis and verify PostgreSQL remains the Kill Switch source of truth."""
    _docker_service_container_id(REDIS_SERVICE_IMAGE)
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    kill_switch = KillSwitchService(exchange_adapter=fake_exchange)
    async with factory() as session:
        activation = await kill_switch.activate(
            session,
            reason="Redis restart chaos verification",
            actor_role=ApiRole.ADMIN,
            activation_source="F3_CHAOS_TEST",
        )
        await session.commit()
        assert activation.is_active is True

    redis_client = RedisClient(TEST_REDIS_URL)
    assert await redis_client.ping() is True
    transient_key = f"chaos:redis-restart:{uuid.uuid4()}"
    assert await redis_client.set(transient_key, "transient-only", ttl_seconds=60) is True
    await asyncio.to_thread(_restart_service_container, REDIS_SERVICE_IMAGE)
    await redis_client.close()

    recovered_redis = await _wait_for_redis()
    assert await recovered_redis.ping() is True
    await recovered_redis.close()

    async with factory() as session:
        state = await session.scalar(
            select(SystemState).where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
        )
        assert state is not None
        assert state.is_active is True
        assert state.activation_reason == "Redis restart chaos verification"

        state.is_active = False
        state.resume_status = None
        await session.commit()
        await kill_switch.is_active(session)


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_kill_switch_activation_during_partial_fill(migrated_db: None) -> None:
    """Kill Switch activation reconciles a partial fill, cancels the remainder, and audits state."""
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.partial_fill_ratio = Decimal("0.50")

    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session)
        order = _make_order(
            bundle,
            state=OrderState.PARTIALLY_FILLED,
            quantity=Decimal("0.200000000000"),
        )
        session.add(order)
        await session.flush()
        receipt = await fake_exchange.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            client_order_id=order.client_order_id,
            limit_price=order.limit_price,
        )
        assert receipt.status == "PARTIALLY_FILLED"
        order.filled_quantity = receipt.filled_quantity
        order.average_fill_price = receipt.average_fill_price
        await session.commit()
        order_id = order.id
        client_order_id = order.client_order_id
        filled_quantity = receipt.filled_quantity

    kill_switch = KillSwitchService(exchange_adapter=fake_exchange)
    async with factory() as session:
        result = await kill_switch.activate(
            session,
            reason="Kill Switch injected during a partial fill",
            actor_role=ApiRole.ADMIN,
            activation_source="F3_PARTIAL_FILL_CHAOS",
        )
        await session.commit()
        assert result.is_active is True
        assert result.reconciled_partial_fills_count >= 1

        reconciled_order = await session.scalar(select(Order).where(Order.id == order_id))
        assert reconciled_order is not None
        assert reconciled_order.state_machine_state == OrderState.CANCEL_REMAINDER.value
        assert reconciled_order.filled_quantity == filled_quantity

        position = await session.scalar(select(Position).where(Position.order_id == order_id))
        assert position is not None
        assert position.status == PositionStatus.OPEN.value
        assert position.size == filled_quantity
        stop = await session.scalar(
            select(SyntheticStop).where(SyntheticStop.position_id == position.id)
        )
        assert stop is not None
        assert stop.quantity == filled_quantity
        # Activation step 5 disables armed-stop polling while Kill Switch is active.
        assert stop.status == SyntheticStopStatus.CANCELLED.value

        exchange_receipt = await fake_exchange.get_order_status(client_order_id)
        assert exchange_receipt is not None
        assert exchange_receipt.status == "CANCELLED"

        state = await session.scalar(
            select(SystemState).where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
        )
        assert state is not None
        assert state.is_active is True
        state.is_active = False
        state.resume_status = None
        await session.commit()
        await kill_switch.is_active(session)


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_kill_switch_activation_during_active_order(migrated_db: None) -> None:
    """Cancel an exchange-open Paper order, then fail closed on a new Risk Engine handoff."""
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    now = datetime.now(UTC)
    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session, now=now)
        order = _make_order(bundle, state=OrderState.SUBMITTED)
        session.add(order)
        await session.flush()
        fake_exchange._orders[order.client_order_id] = ExchangeOrderReceipt(
            exchange_order_id=f"sim-active-{uuid.uuid4().hex[:8]}",
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            status="OPEN",
            quantity=order.quantity,
            filled_quantity=Decimal("0"),
            average_fill_price=None,
            fee=Decimal("0"),
            executed_at=now,
        )
        await session.commit()
        order_id = order.id
        client_order_id = order.client_order_id

    kill_switch = KillSwitchService(exchange_adapter=fake_exchange)
    lifecycle = SignalLifecycleService(exchange_adapter=fake_exchange)
    async with factory() as session:
        activation = await kill_switch.activate(
            session,
            reason="Kill Switch injected while a Paper order is open",
            actor_role=ApiRole.ADMIN,
            activation_source="F3_ACTIVE_ORDER_CHAOS",
        )
        assert activation.is_active is True
        active_order = await session.scalar(select(Order).where(Order.id == order_id))
        assert active_order is not None
        assert active_order.state_machine_state == OrderState.CANCELLED.value
        exchange_receipt = await fake_exchange.get_order_status(client_order_id)
        assert exchange_receipt is not None
        assert exchange_receipt.status == "CANCELLED"
        assert await fake_exchange.get_open_orders("BTC/USDT") == []

        blocked_bundle = await TestSignalFactory.create_signal(session)
        blocked = await lifecycle.approve_signal(
            session,
            signal_id=blocked_bundle.signal.id,
            reason="Risk must reject an approval while Kill Switch is active",
            idempotency_key=f"f3-ks-block-{uuid.uuid4()}",
        )
        await session.commit()
        assert blocked.order is not None
        assert blocked.order.risk_decision == RiskDecisionStatus.REJECT.value
        assert "KILL_SWITCH_ACTIVE" in blocked.order.risk_reason_codes
        assert fake_exchange.place_order_attempts == []

        state = await session.scalar(
            select(SystemState).where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
        )
        assert state is not None
        assert state.is_active is True
        state.is_active = False
        state.resume_status = None
        await session.commit()
        await kill_switch.is_active(session)


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_exchange_connector_failure_causes_fail_closed(migrated_db: None) -> None:
    """A disconnected Paper connector exhausts bounded attempts into MANUAL_REVIEW, not an order."""
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    position_id, stop_id, _order_id = await _seed_open_position_with_stop(factory, fake_exchange)
    fake_exchange.connection_down = True
    stop_service = SyntheticStopService(exchange_adapter=fake_exchange)

    async with factory() as session:
        result = await stop_service.evaluate_and_execute_stop(
            session,
            stop_id=stop_id,
            current_price=Decimal("58799.00"),
            sleep_fn=lambda _seconds: asyncio.sleep(0),
        )
        await session.commit()
        assert result.triggered is True
        assert result.status == SyntheticStopStatus.MANUAL_REVIEW.value
        assert result.attempts_executed == 3
        assert result.last_error is not None
        assert "connection is down" in result.last_error

        stop = await session.scalar(select(SyntheticStop).where(SyntheticStop.id == stop_id))
        position = await session.scalar(select(Position).where(Position.id == position_id))
        assert stop is not None
        assert stop.status == SyntheticStopStatus.MANUAL_REVIEW.value
        assert position is not None
        assert position.status == PositionStatus.MANUAL_REVIEW.value
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.idempotency_key == result.idempotency_key)
            )
            == 0
        )

    assert len(fake_exchange.place_order_attempts) == 3
    assert fake_exchange._orders == {}


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_stale_market_data_blocks_order_submission(migrated_db: None) -> None:
    """Risk Engine rejects a six-second stale quote before Paper order submission."""
    factory = get_session_factory()
    paper_exchange = PaperTradingAdapter()
    lifecycle = SignalLifecycleService(exchange_adapter=paper_exchange)
    now = datetime.now(UTC)
    stale_timestamp = now - timedelta(seconds=6)

    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session, now=now)
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=bundle.signal.id,
            reason="Inject stale market-data timestamp at order handoff",
            idempotency_key=f"f3-stale-{uuid.uuid4()}",
            now=now,
            risk_input_overrides={
                "market_data_timestamp": stale_timestamp,
                "evaluation_timestamp": now,
            },
        )
        await session.commit()

        assert outcome.signal.approval_status == SignalApprovalStatus.APPROVED.value
        assert outcome.order is not None
        assert outcome.order.risk_decision == RiskDecisionStatus.REJECT.value
        assert "STALE_MARKET_DATA" in outcome.order.risk_reason_codes
        assert outcome.order.state_machine_state == OrderState.REJECTED.value

    assert paper_exchange.place_order_attempts == []
    assert await paper_exchange.get_open_orders("BTC/USDT") == []


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_paper_network_isolation_under_chaos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A simulated live endpoint/credential attempt is failed locally in Paper mode."""
    settings = get_settings()
    assert settings.LIVE_TRADING is False
    assert settings.PAPER_TRADING is True

    external_connect_attempts: list[str] = []
    simulated_requests: list[tuple[str, str | None]] = []
    simulated_endpoint = "https://simulated-live.invalid/api/v1/orders"
    simulated_credential = "F3_TEST_ONLY_NOT_A_REAL_CREDENTIAL"
    original_connect = socket.socket.connect

    def block_non_loopback_connect(sock: socket.socket, address: object) -> None:
        host = str(address[0]) if isinstance(address, tuple) else str(address)
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = host.lower() == "localhost"
        if not is_loopback:
            external_connect_attempts.append(host)
            raise AssertionError(f"External network access attempted from Paper test: {host}")
        original_connect(sock, address)  # type: ignore[arg-type]

    def inject_simulated_live_endpoint_failure(request: httpx.Request) -> httpx.Response:
        simulated_requests.append((str(request.url), request.headers.get("authorization")))
        raise httpx.ConnectError("injected simulated endpoint failure", request=request)

    monkeypatch.setattr(socket.socket, "connect", block_non_loopback_connect)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(inject_simulated_live_endpoint_failure)
    ) as client:
        with pytest.raises(httpx.ConnectError, match="injected simulated endpoint failure"):
            await client.post(
                simulated_endpoint,
                headers={"Authorization": f"Bearer {simulated_credential}"},
                json={"symbol": "BTC/USDT", "mode": "simulation-only"},
            )

    assert simulated_requests == [(simulated_endpoint, f"Bearer {simulated_credential}")]
    paper_exchange = PaperTradingAdapter(settings=settings)
    paper_exchange.connection_down = True
    with pytest.raises(ExchangeConnectionError, match="connection is down"):
        await paper_exchange.place_order(
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.01"),
            client_order_id=f"paper-chaos-{uuid.uuid4()}",
        )

    assert external_connect_attempts == []
    assert paper_exchange._orders == {}
    assert settings.LIVE_TRADING is False
    assert settings.PAPER_TRADING is True


@pytest.mark.asyncio
@_dispose_test_database_engine
async def test_no_live_order_is_submitted_in_any_failure_scenario() -> None:
    """Global mode and adapter allowlist make all F3 failure injections Paper/Fake-only."""
    settings = get_settings()
    assert settings.LIVE_TRADING is False
    assert settings.PAPER_TRADING is True
    assert frozenset({"PaperTradingAdapter", "FakeExchangeAdapter"}) == PERMITTED_ADAPTER_CLASSES

    paper_exchange = PaperTradingAdapter(settings=settings)
    registry = ExchangeAdapterRegistry()
    registry.register("paper-chaos-check", paper_exchange)
    assert registry.get("paper-chaos-check") is paper_exchange
    paper_exchange.connection_down = True

    with pytest.raises(ExchangeConnectionError):
        await paper_exchange.place_order(
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.01"),
            client_order_id=f"no-live-order-{uuid.uuid4()}",
        )

    assert paper_exchange._orders == {}
    assert paper_exchange.place_order_attempts
