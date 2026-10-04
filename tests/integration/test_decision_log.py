"""Integration tests for Read-Only Decision Log API in Phase F3 (§10 & §12.4)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.enums import OutboxEventType
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.approval_timeout import ApprovalTimeoutService
from app.services.signal_engine import SignalEngine
from app.services.signal_lifecycle import SignalLifecycleService


async def _create_signal_with_explanation(
    *,
    now: datetime | None = None,
    extra_explanation: dict[str, object] | None = None,
) -> tuple[uuid.UUID, str]:
    current_time = now or datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()
    explanation: dict[str, object] = {
        "entry_reason": "4H EMA(50) > EMA(200) + 1H breakout",
        "risk_reason": "2.0% stop distance",
        "confluence_score": "0.86",
        "regime": "BULL_TREND",
        "factors": {"ema_50_4h": "60100", "ema_200_4h": "58900"},
    }
    if extra_explanation:
        explanation.update(extra_explanation)

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
            data_quality_score=Decimal("0.95"),
            confidence_score=Decimal("0.86"),
            explanation_json=explanation,
            now=current_time,
        )
        await session.commit()
        res = (sig.id, sig.signal_id)
    await dispose_db()
    return res


@pytest.mark.asyncio
async def test_decision_log_is_read_only(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify GET /api/v1/decisions is read-only and rejects mutating HTTP verbs (§10 & §12.4)."""
    sig_uuid, _ = await _create_signal_with_explanation()

    get_resp = await async_client.get("/api/v1/decisions", headers=operational_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["total"] >= 1

    post_resp = await async_client.post(
        "/api/v1/decisions",
        headers=operational_headers,
        json={"signal_id": str(sig_uuid)},
    )
    assert post_resp.status_code == 405


@pytest.mark.asyncio
async def test_decision_history_is_queryable_by_signal_id(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify GET /api/v1/decisions/{signal_id} returns explanation_json and audit"""
    sig_uuid, sig_code = await _create_signal_with_explanation()

    by_uuid = await async_client.get(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert by_uuid.status_code == 200
    body = by_uuid.json()
    assert body["id"] == str(sig_uuid)
    assert body["signal_id"] == sig_code
    assert body["explanation_json"]["regime"] == "BULL_TREND"
    assert any(ev["action"] == OutboxEventType.SIGNAL_CREATED.value for ev in body["events"])

    by_code = await async_client.get(
        f"/api/v1/decisions/{sig_code}",
        headers=operational_headers,
    )
    assert by_code.status_code == 200
    assert by_code.json()["id"] == str(sig_uuid)


@pytest.mark.asyncio
async def test_decision_history_includes_approval_event(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify Decision Log includes SIGNAL_APPROVED and ORDER_CREATED events after"""
    sig_uuid, _ = await _create_signal_with_explanation()

    app_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Approved for decision log test"},
    )
    assert app_resp.status_code == 200

    dec_resp = await async_client.get(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert dec_resp.status_code == 200
    actions = [ev["action"] for ev in dec_resp.json()["events"]]
    assert OutboxEventType.SIGNAL_CREATED.value in actions
    assert OutboxEventType.SIGNAL_APPROVED.value in actions
    assert OutboxEventType.ORDER_CREATED.value in actions


@pytest.mark.asyncio
async def test_decision_history_includes_rejection_event(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify Decision Log includes SIGNAL_REJECTED event after rejection (§10 & §12.4)."""
    sig_uuid, _ = await _create_signal_with_explanation()

    rej_resp = await async_client.post(
        f"/api/v1/signals/{sig_uuid}/reject",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Rejected for decision log test"},
    )
    assert rej_resp.status_code == 200

    dec_resp = await async_client.get(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert dec_resp.status_code == 200
    actions = [ev["action"] for ev in dec_resp.json()["events"]]
    assert OutboxEventType.SIGNAL_REJECTED.value in actions


@pytest.mark.asyncio
async def test_decision_history_includes_timeout_event(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify Decision Log includes SIGNAL_EXPIRED event after timeout (§10 & §12.4)."""
    past = datetime.now(UTC) - timedelta(minutes=10)
    sig_uuid, _ = await _create_signal_with_explanation(now=past)

    init_db()
    factory = get_session_factory()
    timeout_svc = ApprovalTimeoutService()
    async with factory() as session:
        await timeout_svc.check_signal_timeout(
            session,
            signal_id=sig_uuid,
            now=datetime.now(UTC),
        )
        await session.commit()
    await dispose_db()

    dec_resp = await async_client.get(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert dec_resp.status_code == 200
    actions = [ev["action"] for ev in dec_resp.json()["events"]]
    assert OutboxEventType.SIGNAL_EXPIRED.value in actions


@pytest.mark.asyncio
async def test_decision_history_includes_price_drift_event(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify Decision Log includes SIGNAL_PRICE_DRIFT_EXPIRED event after >0.2% d"""
    now = datetime.now(UTC)
    sig_uuid, _ = await _create_signal_with_explanation(now=now)

    init_db()
    factory = get_session_factory()
    timeout_svc = ApprovalTimeoutService()
    async with factory() as session:
        await timeout_svc.check_signal_timeout(
            session,
            signal_id=sig_uuid,
            current_price=Decimal("60250.00"),
            now=now + timedelta(seconds=10),
        )
        await session.commit()
    await dispose_db()

    dec_resp = await async_client.get(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert dec_resp.status_code == 200
    actions = [ev["action"] for ev in dec_resp.json()["events"]]
    assert OutboxEventType.SIGNAL_PRICE_DRIFT_EXPIRED.value in actions


@pytest.mark.asyncio
async def test_decision_history_does_not_expose_secrets(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify Decision Log redacts any secret keys or secret values (§10 & §12.4)."""
    settings = get_settings()
    op_key = settings.MVP0_API_KEY.get_secret_value()
    admin_key = settings.MVP0_ADMIN_API_KEY.get_secret_value()

    sig_uuid, _ = await _create_signal_with_explanation(
        extra_explanation={
            "api_key": op_key,
            "nested": {
                "authorization_token": f"Bearer {admin_key}",
                "note": f"leaked {op_key}",
            },
        }
    )

    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        await lifecycle.approve_signal(
            session,
            signal_id=sig_uuid,
            reason=f"Approved with accidental token {op_key}",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()
    await dispose_db()

    dec_resp = await async_client.get(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert dec_resp.status_code == 200
    raw_text = dec_resp.text
    assert op_key not in raw_text
    assert admin_key not in raw_text
    assert dec_resp.json()["explanation_json"]["api_key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_decision_log_has_no_create_endpoint(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify POST /api/v1/decisions is not allowed (405) (§10 & §12.4)."""
    resp = await async_client.post(
        "/api/v1/decisions",
        headers=operational_headers,
        json={"note": "cannot create"},
    )
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_decision_log_has_no_update_endpoint(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify PUT and PATCH on /api/v1/decisions/{signal_id} are not allowed (405) (§10 & §12.4)."""
    sig_uuid, _ = await _create_signal_with_explanation()
    put_resp = await async_client.put(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
        json={"note": "cannot update"},
    )
    assert put_resp.status_code == 405

    patch_resp = await async_client.patch(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
        json={"note": "cannot patch"},
    )
    assert patch_resp.status_code == 405


@pytest.mark.asyncio
async def test_decision_log_has_no_delete_endpoint(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify DELETE /api/v1/decisions/{signal_id} is not allowed (405) (§10 & §12.4)."""
    sig_uuid, _ = await _create_signal_with_explanation()
    del_resp = await async_client.delete(
        f"/api/v1/decisions/{sig_uuid}",
        headers=operational_headers,
    )
    assert del_resp.status_code == 405
