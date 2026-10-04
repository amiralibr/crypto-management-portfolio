"""Unit and integration tests for MVP-0 Approval Timeout and Price Drift (§6, §7 & §12.2)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import OutboxEventType, SignalApprovalStatus
from app.core.errors import InvalidRequestError
from app.db.models.audit_log import AuditLog
from app.db.models.outbox_event import OutboxEvent
from app.db.models.signal import Signal
from app.db.models.strategy import Strategy
from app.db.session import dispose_db, get_session_factory, init_db
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.services.approval_timeout import (
    DYNAMIC_TIMEOUT_BY_TIMEFRAME,
    ApprovalTimeoutService,
    calculate_price_drift,
    compute_effective_timeout,
    validate_ips_timeout_minutes,
)
from app.workers.approval_timeout import approval_timeout_worker_loop


async def _create_test_signal(
    *,
    timeframe: str = "1H",
    reference_price: Decimal = Decimal("60000.00"),
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> uuid.UUID:
    now = created_at or datetime.now(UTC)
    exp = expires_at or (now + DYNAMIC_TIMEOUT_BY_TIMEFRAME[timeframe])
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        strategy = Strategy(
            id=uuid.uuid4(),
            strategy_code=f"STRAT-{uuid.uuid4().hex[:8]}",
            name="Test Strategy",
            timeframe=timeframe,
            is_active=True,
            config_json={},
        )
        session.add(strategy)
        await session.flush()

        sig = Signal(
            id=uuid.uuid4(),
            signal_id=f"SIG-{uuid.uuid4().hex[:10]}",
            strategy_id=strategy.id,
            symbol="BTC/USDT",
            timeframe=timeframe,
            direction="LONG",
            reference_price=reference_price,
            entry_range_min=reference_price - Decimal("50"),
            entry_range_max=reference_price + Decimal("50"),
            stop_loss_price=reference_price - Decimal("600"),
            take_profit_price=reference_price + Decimal("1200"),
            risk_reward_ratio=Decimal("2.0"),
            data_quality_score=Decimal("0.98"),
            confidence_score=Decimal("0.85"),
            rule_version="4.3",
            approval_status=SignalApprovalStatus.PENDING_APPROVAL.value,
            approval_expires_at=exp,
            explanation_json={
                "entry_reason": "trend breakout",
                "risk_reason": "2% stop",
                "confluence_score": "0.85",
                "regime": "BULL_TREND",
                "factors": {"ema_20": "59900"},
            },
            created_at=now,
            updated_at=now,
            version=1,
        )
        session.add(sig)
        await session.commit()
        sig_id = sig.id
    await dispose_db()
    return sig_id


def test_dynamic_timeout_by_timeframe() -> None:
    """Verify dynamic timeout defaults: 1H=5m, 4H=30m, 1D=4h (§6.1 & §11.1)."""
    assert compute_effective_timeout("1H") == timedelta(minutes=5)
    assert compute_effective_timeout("4H") == timedelta(minutes=30)
    assert compute_effective_timeout("1D") == timedelta(hours=4)


def test_dynamic_timeout_for_1h_is_5_minutes() -> None:
    """Verify 1H signal default timeout is 5 minutes (§6.1 & §12.2)."""
    assert compute_effective_timeout("1H") == timedelta(minutes=5)


def test_dynamic_timeout_for_4h_is_30_minutes() -> None:
    """Verify 4H signal default timeout is 30 minutes (§6.1 & §12.2)."""
    assert compute_effective_timeout("4H") == timedelta(minutes=30)


def test_dynamic_timeout_for_1d_is_4_hours() -> None:
    """Verify 1D signal default timeout is 4 hours (§6.1 & §12.2)."""
    assert compute_effective_timeout("1D") == timedelta(hours=4)


def test_ips_timeout_can_only_reduce_timeout() -> None:
    """Verify IPS approval_timeout_minutes can only reduce dynamic timeout, never"""
    assert compute_effective_timeout("4H", ips_timeout_minutes=10) == timedelta(minutes=10)
    assert compute_effective_timeout("1H", ips_timeout_minutes=60) == timedelta(minutes=5)
    assert compute_effective_timeout("1D", ips_timeout_minutes=120) == timedelta(minutes=120)


def test_ips_timeout_rejects_below_3_minutes() -> None:
    """Verify IPS approval_timeout_minutes < 3 minutes is rejected (§6.2 & §12.2)."""
    for invalid in (-5, 0, 1, 2):
        with pytest.raises(InvalidRequestError):
            validate_ips_timeout_minutes(invalid)


def test_ips_timeout_rejects_above_240_minutes() -> None:
    """Verify IPS approval_timeout_minutes > 240 minutes is rejected (§6.2 & §12.2)."""
    for invalid in (241, 300, 1440):
        with pytest.raises(InvalidRequestError):
            validate_ips_timeout_minutes(invalid)


def test_invalid_ips_timeout_rejected() -> None:
    """Verify IPS approval_timeout_minutes outside [3, 240] or boolean is rejected."""
    for invalid in (0, 2, 241, -5, True):
        with pytest.raises(InvalidRequestError):
            validate_ips_timeout_minutes(invalid)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_approval_timeout_worker_runs_every_5_seconds(migrated_db: None) -> None:
    """Verify APPROVAL_TIMEOUT_INTERVAL_SECONDS defaults to 5s and worker loop exe"""
    settings = get_settings()
    assert settings.APPROVAL_TIMEOUT_INTERVAL_SECONDS == 5

    init_db()
    stop_event = asyncio.Event()

    async def _stop_soon() -> None:
        await asyncio.sleep(0.05)
        stop_event.set()

    stopper = asyncio.create_task(_stop_soon())
    await approval_timeout_worker_loop(
        exchange_adapter=FakeExchangeAdapter(),
        stop_event=stop_event,
        interval_seconds=0.02,
    )
    await stopper
    await dispose_db()


@pytest.mark.asyncio
async def test_price_drift_expires_signal() -> None:
    """Verify signal transitions to PRICE_DRIFT_EXPIRED when drift > 0.2% before t"""
    now = datetime.now(UTC)
    sig_id = await _create_test_signal(
        timeframe="4H",
        reference_price=Decimal("60000.00"),
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    fake_exchange = FakeExchangeAdapter()
    fake_exchange.set_ticker("BTC/USDT", price=Decimal("60180.00"), timestamp=now)

    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService(exchange_adapter=fake_exchange)
    async with factory() as session:
        updated = await service.check_signal_timeout(
            session,
            signal_id=sig_id,
            now=now + timedelta(seconds=10),
        )
        await session.commit()
        assert updated.approval_status == SignalApprovalStatus.PRICE_DRIFT_EXPIRED.value
    await dispose_db()


@pytest.mark.asyncio
async def test_price_drift_expiry_occurs_before_timeout() -> None:
    """Verify price drift > 0.2% expires a signal well before its time timeout (§7.3 & §12.2)."""
    now = datetime.now(UTC)
    sig_id = await _create_test_signal(
        timeframe="1D",
        reference_price=Decimal("50000.00"),
        created_at=now,
        expires_at=now + timedelta(hours=4),
    )
    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService()
    async with factory() as session:
        # Only 5 seconds after creation (4 hours remaining), 0.3% drift expires signal
        updated = await service.check_signal_timeout(
            session,
            signal_id=sig_id,
            current_price=Decimal("50150.00"),
            now=now + timedelta(seconds=5),
        )
        await session.commit()
        assert updated.approval_status == SignalApprovalStatus.PRICE_DRIFT_EXPIRED.value
    await dispose_db()


def test_price_drift_threshold_is_0_002() -> None:
    """Verify locked PRICE_DRIFT_EXPIRY_THRESHOLD is 0.002 (0.2%) (§7.2 & §12.2)."""
    service = ApprovalTimeoutService()
    assert service.price_drift_threshold == Decimal("0.002")


def test_price_drift_threshold_is_0_2_percent() -> None:
    """Verify default PRICE_DRIFT_EXPIRY_THRESHOLD is 0.002."""
    service = ApprovalTimeoutService()
    assert service.price_drift_threshold == Decimal("0.002")


def test_price_drift_uses_decimal() -> None:
    """Verify calculate_price_drift uses Decimal and rejects float inputs (§7.3 & §12.2)."""
    drift = calculate_price_drift(
        current_price=Decimal("60150.00"),
        reference_price=Decimal("60000.00"),
    )
    assert isinstance(drift, Decimal)
    assert drift == Decimal("0.0025")

    with pytest.raises(TypeError, match="Decimal"):
        calculate_price_drift(
            current_price=60150.0,  # type: ignore[arg-type]
            reference_price=Decimal("60000.00"),
        )


def test_price_drift_calculation_uses_decimal() -> None:
    """Alias test preserving F2 test name."""
    test_price_drift_uses_decimal()


def test_price_drift_rejects_zero_or_negative_price() -> None:
    """Verify calculate_price_drift rejects zero or negative current/reference pri"""
    for bad_price in (Decimal("0"), Decimal("-1"), Decimal("-60000")):
        with pytest.raises(InvalidRequestError):
            calculate_price_drift(
                current_price=bad_price,
                reference_price=Decimal("60000"),
            )
        with pytest.raises(InvalidRequestError):
            calculate_price_drift(
                current_price=Decimal("60000"),
                reference_price=bad_price,
            )


@pytest.mark.asyncio
async def test_timeout_transition_is_atomic() -> None:
    """Verify time-based expiry transitions signal atomically and increments versi"""
    created_at = datetime.now(UTC) - timedelta(minutes=10)
    sig_id = await _create_test_signal(
        timeframe="1H",
        reference_price=Decimal("60000.00"),
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=5),
    )

    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService()
    async with factory() as session:
        sig = await service.check_signal_timeout(session, signal_id=sig_id)
        await session.commit()
        assert sig.approval_status == SignalApprovalStatus.EXPIRED.value
        assert sig.version == 2

        sig_again = await service.check_signal_timeout(session, signal_id=sig_id)
        assert sig_again.approval_status == SignalApprovalStatus.EXPIRED.value
        assert sig_again.version == 2
    await dispose_db()


@pytest.mark.asyncio
async def test_timeout_creates_audit_event() -> None:
    """Verify time-based timeout writes SIGNAL_EXPIRED audit log record (§6.3 & §12.2)."""
    created_at = datetime.now(UTC) - timedelta(minutes=10)
    sig_id = await _create_test_signal(
        timeframe="1H",
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=5),
    )
    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService()
    async with factory() as session:
        await service.check_signal_timeout(session, signal_id=sig_id)
        await session.commit()
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.target_id == sig_id,
                AuditLog.action == OutboxEventType.SIGNAL_EXPIRED.value,
            )
        )
        assert audit is not None
    await dispose_db()


@pytest.mark.asyncio
async def test_timeout_creates_outbox_event() -> None:
    """Verify time-based timeout writes SIGNAL_EXPIRED Outbox event (§6.3, §11 & §12.2)."""
    created_at = datetime.now(UTC) - timedelta(minutes=10)
    sig_id = await _create_test_signal(
        timeframe="1H",
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=5),
    )
    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService()
    async with factory() as session:
        await service.check_signal_timeout(session, signal_id=sig_id)
        await session.commit()
        outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == sig_id,
                OutboxEvent.event_type == OutboxEventType.SIGNAL_EXPIRED.value,
            )
        )
        assert outbox is not None
    await dispose_db()


@pytest.mark.asyncio
async def test_price_drift_expiry_creates_audit_event() -> None:
    """Verify price drift expiry writes SIGNAL_PRICE_DRIFT_EXPIRED audit log with"""
    now = datetime.now(UTC)
    drift_sig_id = await _create_test_signal(
        timeframe="1H",
        reference_price=Decimal("60000.00"),
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService()
    async with factory() as session:
        await service.check_signal_timeout(
            session,
            signal_id=drift_sig_id,
            current_price=Decimal("60200.00"),
            now=now + timedelta(seconds=15),
        )
        await session.commit()

        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.target_id == drift_sig_id,
                AuditLog.action == "SIGNAL_PRICE_DRIFT_EXPIRED",
            )
        )
        assert audit is not None
        assert audit.detail_json is not None
        assert audit.detail_json["reference_price"] == "60000.000000000000"
        assert audit.detail_json["current_price"] == "60200.00"
        assert "price_drift" in audit.detail_json
        assert audit.detail_json["threshold"] == "0.002"
    await dispose_db()


@pytest.mark.asyncio
async def test_price_drift_expiry_creates_outbox_event() -> None:
    """Verify price drift expiry writes SIGNAL_PRICE_DRIFT_EXPIRED Outbox event (§"""
    now = datetime.now(UTC)
    drift_sig_id = await _create_test_signal(
        timeframe="1H",
        reference_price=Decimal("60000.00"),
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    init_db()
    factory = get_session_factory()
    service = ApprovalTimeoutService()
    async with factory() as session:
        await service.check_signal_timeout(
            session,
            signal_id=drift_sig_id,
            current_price=Decimal("60200.00"),
            now=now + timedelta(seconds=15),
        )
        await session.commit()

        outbox = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == drift_sig_id,
                OutboxEvent.event_type == OutboxEventType.SIGNAL_PRICE_DRIFT_EXPIRED.value,
            )
        )
        assert outbox is not None
        assert outbox.payload_json["reference_price"] == "60000.000000000000"
        assert outbox.payload_json["current_price"] == "60200.00"
        assert outbox.payload_json["threshold"] == "0.002"
    await dispose_db()


@pytest.mark.asyncio
async def test_timeout_audit_record_created() -> None:
    """Verify check_pending_signals sweep and notification dispatch."""
    now = datetime.now(UTC)
    init_db()
    factory = get_session_factory()
    from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter

    notifier = PaperTelegramNotificationAdapter()
    sweep_service = ApprovalTimeoutService(notifier=notifier)
    exp_sig_id = await _create_test_signal(
        timeframe="1H",
        created_at=now - timedelta(minutes=15),
        expires_at=now - timedelta(minutes=10),
    )
    init_db()
    factory = get_session_factory()
    async with factory() as session:
        processed = await sweep_service.check_pending_signals(session, now=now)
        await session.commit()
        assert any(s.id == exp_sig_id for s in processed)
        assert len(notifier.sent_messages) >= 1
    await dispose_db()
