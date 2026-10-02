"""Unit and integration tests for MVP-0 Approval Timeout and Price Drift (§11 & §21.3)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import SignalApprovalStatus
from app.core.errors import InvalidRequestError
from app.db.models.audit_log import AuditLog
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
            explanation_json={"entry_reason": "trend breakout"},
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
    """Verify dynamic timeout defaults: 1H=5m, 4H=30m, 1D=4h (§11.1)."""
    assert compute_effective_timeout("1H") == timedelta(minutes=5)
    assert compute_effective_timeout("4H") == timedelta(minutes=30)
    assert compute_effective_timeout("1D") == timedelta(hours=4)


def test_ips_timeout_can_only_reduce_timeout() -> None:
    """Verify IPS approval_timeout_minutes can only reduce dynamic timeout, never extend (§11.2)."""
    # 4H default is 30m; IPS cap of 10m reduces it to 10m
    assert compute_effective_timeout("4H", ips_timeout_minutes=10) == timedelta(minutes=10)
    # 1H default is 5m; IPS cap of 60m does NOT extend it beyond 5m
    assert compute_effective_timeout("1H", ips_timeout_minutes=60) == timedelta(minutes=5)
    # 1D default is 240m; IPS cap of 120m reduces it to 120m
    assert compute_effective_timeout("1D", ips_timeout_minutes=120) == timedelta(minutes=120)


def test_invalid_ips_timeout_rejected() -> None:
    """Verify IPS approval_timeout_minutes outside [3, 240] is rejected (§11.2)."""
    for invalid in (0, 2, 241, -5, True):
        with pytest.raises(InvalidRequestError):
            validate_ips_timeout_minutes(invalid)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_price_drift_expires_signal() -> None:
    """Verify signal transitions to PRICE_DRIFT_EXPIRED when drift > 0.2% before timeout (§11.3)."""
    now = datetime.now(UTC)
    sig_id = await _create_test_signal(
        timeframe="4H",
        reference_price=Decimal("60000.00"),
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    fake_exchange = FakeExchangeAdapter()
    # 60000 * 1.003 = 60180 (0.3% drift > 0.2% threshold)
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


def test_price_drift_threshold_is_0_2_percent() -> None:
    """Verify default PRICE_DRIFT_EXPIRY_THRESHOLD is exactly 0.002 (0.2%) (§11.3)."""
    service = ApprovalTimeoutService()
    assert service.price_drift_threshold == Decimal("0.002")


def test_price_drift_calculation_uses_decimal() -> None:
    """Verify calculate_price_drift uses Decimal and rejects float inputs (§11.4)."""
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


@pytest.mark.asyncio
async def test_timeout_transition_is_atomic() -> None:
    """Verify time-based expiry transitions signal atomically and increments version (§11.4)."""
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

        # Second check is idempotent and does not re-transition
        sig_again = await service.check_signal_timeout(session, signal_id=sig_id)
        assert sig_again.approval_status == SignalApprovalStatus.EXPIRED.value
        assert sig_again.version == 2
    await dispose_db()


@pytest.mark.asyncio
async def test_timeout_audit_record_created() -> None:
    """Verify both time expiry and price-drift expiry write required audit records (§11.4)."""
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
        assert audit.detail_json["threshold"] == "0.002"

        # Also test check_pending_signals with notifier
        from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter

        notifier = PaperTelegramNotificationAdapter()
        sweep_service = ApprovalTimeoutService(notifier=notifier)
        exp_sig_id = await _create_test_signal(
            timeframe="1H",
            created_at=now - timedelta(minutes=15),
            expires_at=now - timedelta(minutes=10),
        )
        processed = await sweep_service.check_pending_signals(session, now=now)
        await session.commit()
        assert any(s.id == exp_sig_id for s in processed)
        assert len(notifier.sent_messages) >= 1
    await dispose_db()
