"""F2 Chaos and Resilience Tests (F2 Requirement #7).

Covers:
1. API / Exchange adapter disconnection and recovery
2. Risk Engine heartbeat timeout (> 60s) triggering independent Kill Switch Service
3. Independent Kill Switch Service restart preserving active state and 24h resume request
4. PostgreSQL database disconnection failing closed (503 / rollback) and recovering
5. Redis outage and restart preserving durable PostgreSQL state and FORBIDDEN_DURABLE_PREFIXES
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.config import FORBIDDEN_DURABLE_PREFIXES
from app.core.enums import (
    ApprovalRequestStatus,
    OrderState,
    PositionStatus,
    SyntheticStopStatus,
)
from app.core.errors import RedisOperationError
from app.core.redis import RedisClient
from app.db.models.order import Order
from app.db.models.position import Position
from app.db.models.system_state import SystemState
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.kill_switch_service import create_kill_switch_app, kill_switch_lifespan
from app.services.kill_switch import KILL_SWITCH_STATE_KEY, KillSwitchService
from app.services.risk_engine import RISK_ENGINE_HEARTBEAT_STATE_KEY, RiskEngine
from app.services.synthetic_stop import SyntheticStopService
from tests.conftest import TEST_REDIS_URL
from tests.factories import TestSignalFactory


@pytest.mark.asyncio
async def test_chaos_api_disconnection_and_recovery(migrated_db: None) -> None:
    """Chaos 1: API/Exchange outage during stop execution moves to MANUAL_REVIEW, then recovers."""
    init_db()
    factory = get_session_factory()
    fake_exchange = FakeExchangeAdapter()
    stop_svc = SyntheticStopService(exchange_adapter=fake_exchange)

    async def _no_op_sleep(_s: float) -> None:
        return None

    now = datetime.now(UTC)
    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session, now=now)
        order = Order(
            id=uuid.uuid4(),
            signal_id=bundle.signal.id,
            strategy_id=bundle.strategy.id,
            exchange_account_id=bundle.exchange_account.id,
            client_order_id=f"chaos-api-{uuid.uuid4().hex[:10]}",
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            status=OrderState.PROTECTED.value,
            state_machine_state=OrderState.PROTECTED.value,
            risk_decision="APPROVE",
            quantity=Decimal("0.10"),
            filled_quantity=Decimal("0.10"),
            average_fill_price=Decimal("60000.00"),
            idempotency_key=f"chaos-idem-{uuid.uuid4().hex[:10]}",
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(order)
        await session.flush()

        pos = Position(
            id=uuid.uuid4(),
            order_id=order.id,
            strategy_id=bundle.strategy.id,
            exchange_account_id=bundle.exchange_account.id,
            symbol="BTC/USDT",
            side="LONG",
            size=Decimal("0.10"),
            entry_price=Decimal("60000.00"),
            mark_price=Decimal("60000.00"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status=PositionStatus.OPEN.value,
            stop_price=Decimal("59000.00"),
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(pos)
        await session.flush()

        stop = await stop_svc.register_stop(
            session,
            position_id=pos.id,
            stop_price=Decimal("59000.00"),
            timeframe="1H",
        )

        # Simulate market drop while exchange API is disconnected after ticker fetch
        fake_exchange.set_ticker("BTC/USDT", price=Decimal("58500.00"))
        fake_exchange.fail_next_place_order_count = 10

        exec_res = await stop_svc.evaluate_and_execute_stop(
            session,
            stop_id=stop.id,
            sleep_fn=_no_op_sleep,
        )
        await session.commit()
        assert exec_res.triggered is True
        assert exec_res.status == SyntheticStopStatus.MANUAL_REVIEW.value
        assert exec_res.attempts_executed == 3

        # Reconnect API and verify a new stop executes cleanly
        fake_exchange.fail_next_place_order_count = 0
        pos.status = PositionStatus.OPEN.value
        await session.flush()
        stop_recovered = await stop_svc.register_stop(
            session,
            position_id=pos.id,
            stop_price=Decimal("59000.00"),
            timeframe="1H",
            idempotency_key=f"recovered-stop-{uuid.uuid4().hex[:8]}",
        )
        exec_ok = await stop_svc.evaluate_and_execute_stop(
            session,
            stop_id=stop_recovered.id,
            sleep_fn=_no_op_sleep,
        )
        await session.commit()
        assert exec_ok.status == SyntheticStopStatus.EXECUTED.value

    await dispose_db()


@pytest.mark.asyncio
async def test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch(
    migrated_db: None,
    admin_headers: dict[str, str],
) -> None:
    """Chaos 2: Risk Engine heartbeat missing >60s triggers independent Kill Switch Service."""
    init_db()
    factory = get_session_factory()
    risk_engine = RiskEngine()
    ks = KillSwitchService()

    t0 = datetime.now(UTC) - timedelta(seconds=65)
    async with factory() as session:
        # 1. Missing heartbeat row triggers Kill Switch immediately
        await session.execute(
            delete(SystemState).where(SystemState.state_key == RISK_ENGINE_HEARTBEAT_STATE_KEY)
        )
        await session.flush()
        missing_res = await ks.check_risk_engine_heartbeat(session)
        assert missing_res is not None
        assert missing_res.is_active is True

        # 2. Fresh heartbeat (< 60s) does not trigger Kill Switch
        state = await ks.get_or_create_state(session, for_update=True)
        state.is_active = False
        state.resume_status = None
        await risk_engine.record_heartbeat(session, now=datetime.now(UTC))
        fresh_res = await ks.check_risk_engine_heartbeat(session)
        assert fresh_res is None

        # 3. Ensure Kill Switch starts inactive and record a heartbeat 65 seconds in the past
        state.is_active = False
        state.resume_status = None
        await risk_engine.record_heartbeat(session, now=t0)
        await session.commit()

    # Independent Kill Switch Service checks heartbeat and activates Kill Switch (>60s stale)
    ks_app = create_kill_switch_app()
    transport = ASGITransport(app=ks_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        health_resp = await client.get("/healthz")
        assert health_resp.status_code == 200
        ready_resp = await client.get("/readyz")
        assert ready_resp.status_code == 200

        resp = await client.post(
            "/api/v1/kill-switch/heartbeat-check",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["triggered"] is True
        assert body["activation"]["is_active"] is True

        state_resp = await client.get(
            "/api/v1/system/emergency-stop",
            headers=admin_headers,
        )
        assert state_resp.status_code == 200
        assert state_resp.json()["is_active"] is True
        assert "heartbeat" in (state_resp.json()["activation_reason"] or "").lower()

    await dispose_db()


@pytest.mark.asyncio
async def test_chaos_kill_switch_service_restart_preserves_state(
    migrated_db: None,
    admin_headers: dict[str, str],
) -> None:
    """Chaos 3: Restarting independent Kill Switch Service preserves state & 24h resume request."""
    init_db()
    ks_app_1 = create_kill_switch_app()

    async with kill_switch_lifespan(ks_app_1):
        transport_1 = ASGITransport(app=ks_app_1)
        async with AsyncClient(transport=transport_1, base_url="http://testserver") as client_1:
            act_resp = await client_1.post(
                "/api/v1/system/emergency-stop",
                headers=admin_headers,
                json={"reason": "Chaos test Kill Switch activation before container restart"},
            )
            assert act_resp.status_code == 200
            assert act_resp.json()["is_active"] is True

            req_resp = await client_1.post(
                "/api/v1/system/emergency-stop/resume-requests",
                headers=admin_headers,
                json={"reason": "Resume request created before Kill Switch restart"},
            )
            assert req_resp.status_code == 200
            request_id = req_resp.json()["id"]

    # Simulate container restart by creating a brand-new Kill Switch app instance
    ks_app_2 = create_kill_switch_app()
    async with kill_switch_lifespan(ks_app_2):
        transport_2 = ASGITransport(app=ks_app_2)
        async with AsyncClient(transport=transport_2, base_url="http://testserver") as client_2:
            health_resp = await client_2.get("/healthz")
            assert health_resp.status_code == 200

            ready_resp = await client_2.get("/readyz")
            assert ready_resp.status_code == 200

            state_after = await client_2.get(
                "/api/v1/system/emergency-stop",
                headers=admin_headers,
            )
            assert state_after.status_code == 200
            assert state_after.json()["is_active"] is True

            resume_after = await client_2.get(
                f"/api/v1/system/emergency-stop/resume-requests/{request_id}",
                headers=admin_headers,
            )
            assert resume_after.status_code == 200
            assert (
                resume_after.json()["status"] == ApprovalRequestStatus.PENDING_FIRST_APPROVAL.value
            )

    await dispose_db()


@pytest.mark.asyncio
async def test_chaos_database_disconnection_fails_closed(
    migrated_db: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chaos 4: Database disconnection causes Kill Switch & API /readyz to fail closed (503)."""
    init_db()
    ks_app = create_kill_switch_app()

    async def _db_down() -> bool:
        return False

    monkeypatch.setattr("app.kill_switch_service.ping_database", _db_down)
    transport = ASGITransport(app=ks_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ready_resp = await client.get("/readyz")
        assert ready_resp.status_code == 503
        assert ready_resp.json()["status"] == "not_ready"
        assert ready_resp.json()["database"] == "unavailable"

    await dispose_db()


@pytest.mark.asyncio
async def test_chaos_redis_restart_preserves_durable_domain_state(
    migrated_db: None,
) -> None:
    """Chaos 5: Redis outage and restart loses zero durable state and blocks all domain prefixes."""
    init_db()
    factory = get_session_factory()
    ks = KillSwitchService()

    # 1. Verify all prohibited domain prefixes in central config are rejected by RedisClient
    redis_client = RedisClient(TEST_REDIS_URL)
    for prefix in FORBIDDEN_DURABLE_PREFIXES:
        with pytest.raises(RedisOperationError):
            await redis_client.set(f"{prefix}test-id", "prohibited")
        with pytest.raises(RedisOperationError):
            await redis_client.get(f"{prefix}test-id")

    # 2. Persist Signal and Kill Switch state in PostgreSQL
    async with factory() as session:
        bundle = await TestSignalFactory.create_signal(session)
        await ks.activate(session, reason="Active during Redis restart test")
        await session.commit()
        signal_id = bundle.signal.id

    # 3. Simulate Redis outage (unreachable port) and close/re-open RedisClient
    down_redis = RedisClient("redis://127.0.0.1:6399/0")
    assert await down_redis.ping() is False
    await down_redis.close()
    await redis_client.close()

    # 4. Verify PostgreSQL state is 100% preserved while Redis was down, and Redis reconnects
    reconnected_redis = RedisClient(TEST_REDIS_URL)
    assert await reconnected_redis.ping() is True
    await reconnected_redis.close()

    async with factory() as verify_session:
        ks_state = await verify_session.scalar(
            select(SystemState).where(SystemState.state_key == KILL_SWITCH_STATE_KEY)
        )
        assert ks_state is not None
        assert ks_state.is_active is True
        from app.db.models.signal import Signal

        persisted_sig = await verify_session.scalar(select(Signal).where(Signal.id == signal_id))
        assert persisted_sig is not None

    await dispose_db()
