"""Integration tests for Signal API endpoints in Phase F3 (§8 & §12.4)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.enums import SignalApprovalStatus
from app.db.models.order import Order
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.signal_engine import SignalEngine


async def _create_api_signal() -> tuple[uuid.UUID, str]:
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()
    async with factory() as session:
        sig = await engine.create_signal(
            session,
            symbol="BTC/USDT",
            timeframe="1H",
            reference_price=Decimal("60000.00"),
            entry_range_min=Decimal("59950.00"),
            entry_range_max=Decimal("60050.00"),
            stop_loss_price=Decimal("58800.00"),
            take_profit_price=Decimal("62400.00"),
            risk_reward_ratio=Decimal("2.0"),
            data_quality_score=Decimal("0.96"),
            confidence_score=Decimal("0.82"),
            explanation_json={
                "entry_reason": "4H bull regime + 1H breakout",
                "risk_reason": "2% stop distance",
                "confluence_score": "0.82",
                "regime": "BULL_TREND",
                "factors": {"ema_50_4h": "59500", "ema_200_4h": "58000"},
            },
            now=now,
        )
        await session.commit()
        res = (sig.id, sig.signal_id)
    await dispose_db()
    return res


@pytest.mark.asyncio
async def test_list_signals_requires_operational_key(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify GET /api/v1/signals rejects missing/invalid token (401) and accepts"""
    sig_uuid, sig_code = await _create_api_signal()

    unauth_resp = await async_client.get("/api/v1/signals")
    assert unauth_resp.status_code == 401
    assert unauth_resp.json()["code"] == "UNAUTHORIZED"

    bad_resp = await async_client.get(
        "/api/v1/signals",
        headers={"Authorization": "Bearer invalid_key_00000000"},
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["code"] == "UNAUTHORIZED"

    ok_resp = await async_client.get("/api/v1/signals", headers=operational_headers)
    assert ok_resp.status_code == 200
    body = ok_resp.json()
    assert body["total"] >= 1
    assert any(
        item["id"] == str(sig_uuid) and item["signal_id"] == sig_code for item in body["items"]
    )


@pytest.mark.asyncio
async def test_approve_signal_requires_operational_key(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify POST /api/v1/signals/{id}/approve requires OPERATIONAL key and Idemp"""
    sig_uuid, _ = await _create_api_signal()

    unauth_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approved based on trend confirmation"},
    )
    assert unauth_resp.status_code == 401
    assert unauth_resp.json()["code"] == "UNAUTHORIZED"

    ok_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approved based on trend confirmation"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["approval_status"] == SignalApprovalStatus.APPROVED.value
    assert ok_resp.json()["order"] is not None


@pytest.mark.asyncio
async def test_reject_signal_requires_operational_key(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify POST /api/v1/signals/{id}/reject requires OPERATIONAL key and Idempo"""
    sig_uuid, _ = await _create_api_signal()

    unauth_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/reject",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Rejected by user"},
    )
    assert unauth_resp.status_code == 401
    assert unauth_resp.json()["code"] == "UNAUTHORIZED"

    ok_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/reject",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Rejected by user"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["approval_status"] == SignalApprovalStatus.REJECTED.value


@pytest.mark.asyncio
async def test_admin_key_can_access_operational_routes(
    migrated_db: None,
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Verify ADMIN key is authorized on OPERATIONAL signal and decision routes (§12.4)."""
    sig_uuid, _ = await _create_api_signal()

    list_resp = await async_client.get("/api/v1/signals", headers=admin_headers)
    assert list_resp.status_code == 200

    app_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Admin approved signal"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["approval_status"] == SignalApprovalStatus.APPROVED.value


@pytest.mark.asyncio
async def test_operational_key_cannot_access_admin_routes(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify OPERATIONAL key is rejected with 403 FORBIDDEN on ADMIN-only routes (§12.4)."""
    status_resp = await async_client.get("/api/v1/system/status", headers=operational_headers)
    assert status_resp.status_code == 403
    assert status_resp.json()["code"] == "FORBIDDEN"

    ks_resp = await async_client.post(
        "/api/v1/system/emergency-stop",
        headers=operational_headers,
        json={"reason": "Operational cannot trigger emergency stop"},
    )
    assert ks_resp.status_code == 403
    assert ks_resp.json()["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_order_idempotency_across_duplicate_requests(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify repeating POST /api/v1/signals/{id}/approve with same Idempotency-Ke"""
    sig_uuid, _ = await _create_api_signal()
    idem_key = f"idem-repeat-{uuid.uuid4()}"
    headers = {**operational_headers, "Idempotency-Key": idem_key}
    payload = {"reason": "Approved based on trend confirmation"}

    resp1 = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers=headers,
        json=payload,
    )
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["approval_status"] == SignalApprovalStatus.APPROVED.value
    order_id_1 = body1["order"]["order_id"]

    # Second identical request with same Idempotency-Key returns 200 and same order_id
    resp2 = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers=headers,
        json=payload,
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["approval_status"] == SignalApprovalStatus.APPROVED.value
    assert body2["order"]["order_id"] == order_id_1

    factory = get_session_factory()
    async with factory() as session:
        order_count = await session.scalar(
            select(func.count()).select_from(Order).where(Order.signal_id == sig_uuid)
        )
        assert order_count == 1
    await dispose_db()


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_with_different_payload_returns_409(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify reusing an Idempotency-Key with a different payload returns 409 IDEM"""
    sig_uuid, _ = await _create_api_signal()
    idem_key = f"idem-conflict-{uuid.uuid4()}"
    headers = {**operational_headers, "Idempotency-Key": idem_key}

    resp1 = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers=headers,
        json={"reason": "Original approval reason"},
    )
    assert resp1.status_code == 200

    resp2 = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers=headers,
        json={"reason": "Modified approval reason with same Idempotency-Key"},
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_signal_not_found_returns_404(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify missing signal returns 404 SIGNAL_NOT_FOUND (§8.4 & §12.4)."""
    missing_id = uuid.uuid4()
    resp = await async_client.post(
        f"/api/v1/signals/{missing_id}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approve non-existent signal"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "SIGNAL_NOT_FOUND"


@pytest.mark.asyncio
async def test_invalid_state_returns_409(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify invalid transition on signal endpoint returns 409 INVALID_STATE (§8.4 & §12.4)."""
    sig_uuid, _ = await _create_api_signal()

    # Approve signal first
    resp1 = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approve first"},
    )
    assert resp1.status_code == 200

    # Attempting to reject an already APPROVED signal returns 409 INVALID_STATE
    resp2 = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/reject",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Reject after approve"},
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "INVALID_STATE"

    # Also verify idempotent reject replay and conflict on /reject, plus GET /api/v1/signals/{id}
    get_sig_resp = await async_client.get(
        f"/api/v1/signals/{sig_uuid}",
        headers=operational_headers,
    )
    assert get_sig_resp.status_code == 200
    assert get_sig_resp.json()["id"] == str(sig_uuid)

    sig2_uuid, _ = await _create_api_signal()
    rej_idem = f"idem-rej-{uuid.uuid4()}"
    rej_headers = {**operational_headers, "Idempotency-Key": rej_idem}
    r1 = await async_client.post(
        f"/api/v1/signals/{sig2_uuid}/reject",
        headers=rej_headers,
        json={"reason": "Consistent rejection"},
    )
    assert r1.status_code == 200
    r2 = await async_client.post(
        f"/api/v1/signals/{sig2_uuid}/reject",
        headers=rej_headers,
        json={"reason": "Consistent rejection"},
    )
    assert r2.status_code == 200
    r3 = await async_client.post(
        f"/api/v1/signals/{sig2_uuid}/reject",
        headers=rej_headers,
        json={"reason": "Changed rejection reason"},
    )
    assert r3.status_code == 409
    assert r3.json()["code"] == "IDEMPOTENCY_CONFLICT"
