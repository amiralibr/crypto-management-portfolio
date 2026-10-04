"""Integration tests for Signal Lifecycle State Machine in Phase F3 (§5 & §12.3)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.enums import OutboxEventType, SignalApprovalStatus
from app.core.errors import (
    InvalidStateError,
    PriceDriftExpiredError,
    SignalExpiredError,
)
from app.db.models.audit_log import AuditLog
from app.db.models.outbox_event import OutboxEvent
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.approval_timeout import ApprovalTimeoutService
from app.services.signal_engine import SignalEngine
from app.services.signal_lifecycle import SignalLifecycleService


async def _seed_pending_signal(
    *,
    reference_price: Decimal = Decimal("60000.00"),
    timeframe: str = "1H",
    now: datetime | None = None,
) -> uuid.UUID:
    current_time = now or datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()
    async with factory() as session:
        sig = await engine.create_signal(
            session,
            symbol="BTC/USDT",
            timeframe=timeframe,
            reference_price=reference_price,
            entry_range_min=reference_price - Decimal("50"),
            entry_range_max=reference_price + Decimal("50"),
            stop_loss_price=reference_price - Decimal("600"),
            take_profit_price=reference_price + Decimal("1200"),
            risk_reward_ratio=Decimal("2.0"),
            data_quality_score=Decimal("0.95"),
            confidence_score=Decimal("0.85"),
            explanation_json={
                "entry_reason": "4H bull trend + 1H breakout",
                "risk_reason": "1% stop distance",
                "confluence_score": "0.85",
                "regime": "BULL_TREND",
                "factors": {"ema_50_4h": "59500", "ema_200_4h": "58000"},
            },
            now=current_time,
        )
        await session.commit()
        return sig.id


@pytest.mark.asyncio
async def test_pending_signal_can_be_approved(migrated_db: None) -> None:
    """Verify PENDING_APPROVAL -> APPROVED transition writes Audit and Outbox atom"""
    sig_id = await _seed_pending_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Approved based on trend confirmation",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()
        assert outcome.signal.approval_status == SignalApprovalStatus.APPROVED.value
        assert outcome.signal.version == 2

        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.target_id == sig_id,
                AuditLog.action == OutboxEventType.SIGNAL_APPROVED.value,
            )
        )
        assert audit is not None
        outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == sig_id,
                OutboxEvent.event_type == OutboxEventType.SIGNAL_APPROVED.value,
            )
        )
        assert outbox is not None
    await dispose_db()


@pytest.mark.asyncio
async def test_pending_signal_can_be_rejected(migrated_db: None) -> None:
    """Verify PENDING_APPROVAL -> REJECTED transition writes Audit and Outbox atom"""
    sig_id = await _seed_pending_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        outcome = await lifecycle.reject_signal(
            session,
            signal_id=sig_id,
            reason="Rejected by operator",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()
        assert outcome.signal.approval_status == SignalApprovalStatus.REJECTED.value
        assert outcome.signal.version == 2

        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.target_id == sig_id,
                AuditLog.action == OutboxEventType.SIGNAL_REJECTED.value,
            )
        )
        assert audit is not None
        outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == sig_id,
                OutboxEvent.event_type == OutboxEventType.SIGNAL_REJECTED.value,
            )
        )
        assert outbox is not None
    await dispose_db()


@pytest.mark.asyncio
async def test_pending_signal_can_expire(migrated_db: None) -> None:
    """Verify PENDING_APPROVAL -> EXPIRED transition on time timeout (§5 & §12.3)."""
    past = datetime.now(UTC) - timedelta(minutes=10)
    sig_id = await _seed_pending_signal(timeframe="1H", now=past)
    init_db()
    factory = get_session_factory()
    timeout_svc = ApprovalTimeoutService()
    async with factory() as session:
        sig = await timeout_svc.check_signal_timeout(
            session,
            signal_id=sig_id,
            now=datetime.now(UTC),
        )
        await session.commit()
        assert sig.approval_status == SignalApprovalStatus.EXPIRED.value
    await dispose_db()


@pytest.mark.asyncio
async def test_pending_signal_can_price_drift_expire(migrated_db: None) -> None:
    """Verify PENDING_APPROVAL -> PRICE_DRIFT_EXPIRED transition when drift > 0.2% (§5 & §12.3)."""
    now = datetime.now(UTC)
    sig_id = await _seed_pending_signal(reference_price=Decimal("60000.00"), now=now)
    init_db()
    factory = get_session_factory()
    timeout_svc = ApprovalTimeoutService()
    async with factory() as session:
        sig = await timeout_svc.check_signal_timeout(
            session,
            signal_id=sig_id,
            current_price=Decimal("60200.00"),
            now=now + timedelta(seconds=10),
        )
        await session.commit()
        assert sig.approval_status == SignalApprovalStatus.PRICE_DRIFT_EXPIRED.value
    await dispose_db()


@pytest.mark.asyncio
async def test_approved_signal_cannot_be_approved_again(migrated_db: None) -> None:
    """Verify APPROVED signal cannot be transitioned to APPROVED again (§5.2, §5.3 & §12.3)."""
    sig_id = await _seed_pending_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        await lifecycle.approve_signal(
            session,
            signal_id=sig_id,
            reason="Initial approval",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()

        audit_count_before = await session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.target_id == sig_id)
        )
        with pytest.raises(InvalidStateError):
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="Second approval attempt with new key",
                idempotency_key=f"idem-{uuid.uuid4()}",
            )
        audit_count_after = await session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.target_id == sig_id)
        )
        # §5.3: Failed validation writes zero audit or Outbox records
        assert audit_count_after == audit_count_before
    await dispose_db()


@pytest.mark.asyncio
async def test_rejected_signal_cannot_be_approved(migrated_db: None) -> None:
    """Verify REJECTED signal cannot be approved (§5.2, §5.3 & §12.3)."""
    sig_id = await _seed_pending_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    async with factory() as session:
        await lifecycle.reject_signal(
            session,
            signal_id=sig_id,
            reason="Operator rejected",
            idempotency_key=f"idem-{uuid.uuid4()}",
        )
        await session.commit()

        with pytest.raises(InvalidStateError):
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="Attempted approval after rejection",
                idempotency_key=f"idem-{uuid.uuid4()}",
            )
    await dispose_db()


@pytest.mark.asyncio
async def test_expired_signal_cannot_be_approved(migrated_db: None) -> None:
    """Verify EXPIRED or past-deadline signal cannot be approved (409 SIGNAL_EXPIR"""
    past = datetime.now(UTC) - timedelta(minutes=10)
    sig_id = await _seed_pending_signal(timeframe="1H", now=past)
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    timeout_svc = ApprovalTimeoutService()

    async with factory() as session:
        # 1. Approval attempt after deadline before worker sweep raises SignalExpiredError
        with pytest.raises(SignalExpiredError) as exc_info:
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="Too late approval",
                idempotency_key=f"idem-{uuid.uuid4()}",
                now=datetime.now(UTC),
            )
        assert exc_info.value.code == "SIGNAL_EXPIRED"

        # 2. Worker transitions to EXPIRED; subsequent approval also raises SignalExpiredError
        await timeout_svc.check_signal_timeout(session, signal_id=sig_id, now=datetime.now(UTC))
        await session.commit()

        with pytest.raises(SignalExpiredError) as exc_info2:
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="Approval after EXPIRED state",
                idempotency_key=f"idem-{uuid.uuid4()}",
            )
        assert exc_info2.value.code == "SIGNAL_EXPIRED"
    await dispose_db()


@pytest.mark.asyncio
async def test_price_drift_expired_signal_cannot_be_approved(migrated_db: None) -> None:
    """Verify drift-expired signal cannot be approved (409 PRICE_DRIFT_EXPIRED, §8.4 & §12.3)."""
    now = datetime.now(UTC)
    sig_id = await _seed_pending_signal(reference_price=Decimal("60000.00"), now=now)
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()
    timeout_svc = ApprovalTimeoutService()

    async with factory() as session:
        # 1. Live price drift > 0.2% during approval attempt raises PriceDriftExpiredError
        with pytest.raises(PriceDriftExpiredError) as exc_info:
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="Approve during >0.2% price drift",
                current_price=Decimal("60200.00"),
                idempotency_key=f"idem-{uuid.uuid4()}",
                now=now + timedelta(seconds=5),
            )
        assert exc_info.value.code == "PRICE_DRIFT_EXPIRED"

        # 2. Worker marks PRICE_DRIFT_EXPIRED; subsequent approval also raises PriceD
        await timeout_svc.check_signal_timeout(
            session,
            signal_id=sig_id,
            current_price=Decimal("60200.00"),
            now=now + timedelta(seconds=10),
        )
        await session.commit()

        with pytest.raises(PriceDriftExpiredError) as exc_info2:
            await lifecycle.approve_signal(
                session,
                signal_id=sig_id,
                reason="Approve after PRICE_DRIFT_EXPIRED state",
                idempotency_key=f"idem-{uuid.uuid4()}",
            )
        assert exc_info2.value.code == "PRICE_DRIFT_EXPIRED"
    await dispose_db()


@pytest.mark.asyncio
async def test_concurrent_approval_is_serialized(migrated_db: None) -> None:
    """Verify two concurrent approval attempts on the same signal are serialized v"""
    sig_id = await _seed_pending_signal()
    init_db()
    factory = get_session_factory()
    lifecycle = SignalLifecycleService()

    async def _attempt_approve(idx: int) -> str:
        async with factory() as s:
            try:
                await lifecycle.approve_signal(
                    s,
                    signal_id=sig_id,
                    reason=f"Concurrent approval {idx}",
                    idempotency_key=f"conc-idem-{idx}-{uuid.uuid4()}",
                )
                await s.commit()
                return "SUCCESS"
            except InvalidStateError:
                await s.rollback()
                return "CONFLICT"

    results = await asyncio.gather(_attempt_approve(1), _attempt_approve(2))
    assert sorted(results) == ["CONFLICT", "SUCCESS"]
    await dispose_db()


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(
    migrated_db: None,
    async_client: AsyncClient,
    operational_headers: dict[str, str],
) -> None:
    """Verify HTTP API returns 409 INVALID_STATE on invalid signal transition (§8.4 & §12.3)."""
    sig_id = await _seed_pending_signal()

    # First reject the signal
    resp1 = await async_client.post(
        f"/api/v1/signals/{sig_id}/reject",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Initial rejection"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["approval_status"] == SignalApprovalStatus.REJECTED.value

    # Attempting to approve a REJECTED signal returns 409 INVALID_STATE
    resp2 = await async_client.post(
        f"/api/v1/signals/{sig_id}/approve",
        headers={**operational_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Cannot approve rejected signal"},
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "INVALID_STATE"
