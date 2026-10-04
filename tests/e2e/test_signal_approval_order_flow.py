"""End-to-End tests for Phase F3 Signal Creation -> Approval/Rejection -> Risk"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.enums import OrderState, OutboxEventType, RiskDecisionStatus, SignalApprovalStatus
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.signal_engine import SignalEngine
from tests.unit.test_mean_reversion_rule import make_mean_reversion_candles
from tests.unit.test_trend_following_rule import make_trend_candles


@pytest.mark.asyncio
async def test_e2e_signal_approval_and_rejection_order_handoff_flow(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify full F3 lifecycle: Signal Engine -> API List -> Approve/Reject -> Or"""
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

    # 1. List signals via GET /api/v1/signals
    list_resp = await async_client.get(
        "/api/v1/signals?approval_status=PENDING_APPROVAL",
        headers=operational_headers,
    )
    assert list_resp.status_code == 200
    listed_ids = {item["id"] for item in list_resp.json()["items"]}
    assert str(tf_id) in listed_ids
    assert str(mr_id) in listed_ids

    # 2. Approve Trend Following signal via POST /api/v1/signals/{id}/approve
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

    # 3. Inspect created order via GET /api/v1/orders and GET /api/v1/orders/{order_id}
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

    # 4. Reject Mean Reversion signal via POST /api/v1/signals/{id}/reject
    rej_resp = await async_client.post(
        f"/api/v1/signals/{mr_id}/reject",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Operator skipped counter-trend setup"},
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["approval_status"] == SignalApprovalStatus.REJECTED.value
    assert rej_resp.json()["order"] is None

    # 5. Query Read-Only Decision Log for both signals
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
