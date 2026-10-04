"""Unit and persistence tests for deterministic Signal Engine in Phase F3 (§4 & §12.1)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import OutboxEventType, SignalApprovalStatus
from app.core.errors import InvalidRequestError, SignalReferencePriceImmutableError
from app.db.models.audit_log import AuditLog
from app.db.models.outbox_event import OutboxEvent
from app.db.session import dispose_db, get_session_factory, init_db
from app.services.signal_engine import SignalEngine
from app.services.trend_following_rule import REQUIRED_EXPLANATION_KEYS
from tests.unit.test_mean_reversion_rule import make_mean_reversion_candles
from tests.unit.test_trend_following_rule import make_trend_candles


def test_signal_engine_uses_closed_candles_only() -> None:
    """Verify open/incomplete candles never generate a Trend Following or Mean Rev"""
    engine = SignalEngine()

    # 1. Trend Following: breakout bar is still OPEN (is_closed=False); prior clo
    c4h, c1h_open_breakout = make_trend_candles(latest_1h_closed=False)
    assert (
        engine.evaluate_trend_following(
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h_open_breakout,
        )
        is None
    )
    with pytest.raises(InvalidRequestError):
        engine.evaluate_trend_following(
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h_open_breakout,
            reject_open_candles=True,
        )

    # 2. Mean Reversion: rebound bar is still OPEN (is_closed=False); prior close
    mr_open_rebound = make_mean_reversion_candles(latest_closed=False)
    assert (
        engine.evaluate_mean_reversion(
            symbol="ETH/USDT",
            candles_1h=mr_open_rebound,
        )
        is None
    )
    with pytest.raises(InvalidRequestError):
        engine.evaluate_mean_reversion(
            symbol="ETH/USDT",
            candles_1h=mr_open_rebound,
            reject_open_candles=True,
        )


def test_signal_rejects_data_quality_below_0_8() -> None:
    """Verify Signal Engine rejects data_quality_score < 0.8 (§4.3 & §4.4)."""
    engine = SignalEngine()
    c4h, c1h = make_trend_candles()
    with pytest.raises(InvalidRequestError, match="data_quality_score"):
        engine.evaluate_trend_following(
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h,
            data_quality_score=Decimal("0.79"),
            confidence_score=Decimal("0.80"),
        )


def test_signal_rejects_confidence_below_0_6() -> None:
    """Verify Signal Engine rejects confidence_score < 0.6 (§4.3 & §4.4)."""
    engine = SignalEngine()
    c4h, c1h = make_trend_candles()
    with pytest.raises(InvalidRequestError, match="confidence_score"):
        engine.evaluate_trend_following(
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h,
            data_quality_score=Decimal("0.90"),
            confidence_score=Decimal("0.59"),
        )


def test_signal_rejects_disallowed_symbol() -> None:
    """Verify Signal Engine allows only BTC/USDT, ETH/USDT, BNB/USDT and rejects others (§4.1)."""
    engine = SignalEngine()
    c4h, c1h = make_trend_candles()
    for bad_symbol in ("SOL/USDT", "DOGE/USDT", "XRP/USDT", "BTC/USD"):
        with pytest.raises(InvalidRequestError, match="Symbol"):
            engine.evaluate_trend_following(
                symbol=bad_symbol,
                candles_4h=c4h,
                candles_1h=c1h,
            )


def test_signal_rejects_non_long_direction() -> None:
    """Verify Signal Engine rejects SHORT, non-SPOT market, or leverage != 1 (§4.1)."""
    engine = SignalEngine()
    c4h, c1h = make_trend_candles()
    for bad_direction in ("SHORT", "SELL", "NEUTRAL"):
        with pytest.raises(InvalidRequestError, match="Direction"):
            engine.evaluate_trend_following(
                symbol="BTC/USDT",
                candles_4h=c4h,
                candles_1h=c1h,
                direction=bad_direction,
            )

    with pytest.raises(InvalidRequestError, match="Market"):
        engine.evaluate_trend_following(
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h,
            market="FUTURES",
        )

    with pytest.raises(InvalidRequestError, match="Leverage"):
        engine.evaluate_trend_following(
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h,
            leverage=Decimal("2"),
        )


@pytest.mark.asyncio
async def test_signal_contains_explanation(migrated_db: None) -> None:
    """Verify every persisted signal contains required explanation_json fields and"""
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()
    c4h, c1h = make_trend_candles()
    mr_candles = make_mean_reversion_candles()

    async with factory() as session:
        tf_signal = await engine.generate_trend_following_signal(
            session,
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h,
            now=datetime.now(UTC),
        )
        assert tf_signal is not None
        assert tf_signal.approval_status == SignalApprovalStatus.PENDING_APPROVAL.value
        assert REQUIRED_EXPLANATION_KEYS.issubset(tf_signal.explanation_json.keys())

        mr_signal = await engine.generate_mean_reversion_signal(
            session,
            symbol="ETH/USDT",
            candles_1h=mr_candles,
            now=datetime.now(UTC),
        )
        assert mr_signal is not None
        assert mr_signal.approval_status == SignalApprovalStatus.PENDING_APPROVAL.value
        assert REQUIRED_EXPLANATION_KEYS.issubset(mr_signal.explanation_json.keys())

        # Missing explanation fields must be rejected
        with pytest.raises(InvalidRequestError, match="explanation_json"):
            await engine.create_signal(
                session,
                symbol="BTC/USDT",
                timeframe="1H",
                reference_price=Decimal("60000"),
                entry_range_min=Decimal("59950"),
                entry_range_max=Decimal("60050"),
                stop_loss_price=Decimal("58800"),
                take_profit_price=Decimal("62400"),
                risk_reward_ratio=Decimal("2.0"),
                data_quality_score=Decimal("0.95"),
                confidence_score=Decimal("0.80"),
                explanation_json={"entry_reason": "incomplete"},
            )

        await session.commit()

        # Verify SIGNAL_CREATED audit and Outbox records exist for both signals
        for sig in (tf_signal, mr_signal):
            audit = await session.scalar(
                select(AuditLog).where(
                    AuditLog.target_id == sig.id,
                    AuditLog.action == OutboxEventType.SIGNAL_CREATED.value,
                )
            )
            assert audit is not None
            outbox = await session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == sig.id,
                    OutboxEvent.event_type == OutboxEventType.SIGNAL_CREATED.value,
                )
            )
            assert outbox is not None

    await dispose_db()


@pytest.mark.asyncio
async def test_signal_reference_price_is_immutable(migrated_db: None) -> None:
    """Verify Signal.reference_price cannot be mutated after creation (§4.5, §7.2 & §12.1)."""
    init_db()
    factory = get_session_factory()
    engine = SignalEngine()
    c4h, c1h = make_trend_candles()

    async with factory() as session:
        signal = await engine.generate_trend_following_signal(
            session,
            symbol="BTC/USDT",
            candles_4h=c4h,
            candles_1h=c1h,
            now=datetime.now(UTC),
        )
        assert signal is not None
        original_ref = signal.reference_price
        await session.commit()

        with pytest.raises((SignalReferencePriceImmutableError, ValueError)):
            signal.reference_price = original_ref + Decimal("100")

        assert signal.reference_price == original_ref

        # Also test non-producing trend/mean-reversion evaluations and create_signal validations
        c4h_bear, c1h_ok = make_trend_candles(bull_4h=False)
        assert (
            await engine.generate_trend_following_signal(
                session,
                symbol="BTC/USDT",
                candles_4h=c4h_bear,
                candles_1h=c1h_ok,
            )
            is None
        )
        mr_no_cross = make_mean_reversion_candles(rsi_cross_above_30=False)
        assert (
            await engine.generate_mean_reversion_signal(
                session,
                symbol="ETH/USDT",
                candles_1h=mr_no_cross,
            )
            is None
        )

        valid_exp = dict(signal.explanation_json)
        for bad_kwargs in (
            {"reference_price": Decimal("0")},
            {"stop_loss_price": Decimal("65000")},
            {"entry_range_min": Decimal("61000"), "entry_range_max": Decimal("60000")},
            {"risk_reward_ratio": Decimal("0")},
        ):
            base_kwargs: dict[str, object] = {
                "symbol": "BTC/USDT",
                "timeframe": "1H",
                "reference_price": Decimal("60000"),
                "entry_range_min": Decimal("59950"),
                "entry_range_max": Decimal("60050"),
                "stop_loss_price": Decimal("58800"),
                "take_profit_price": Decimal("62400"),
                "risk_reward_ratio": Decimal("2.0"),
                "data_quality_score": Decimal("0.95"),
                "confidence_score": Decimal("0.80"),
                "explanation_json": valid_exp,
            }
            base_kwargs.update(bad_kwargs)
            with pytest.raises(InvalidRequestError):
                await engine.create_signal(session, **base_kwargs)  # type: ignore[arg-type]

    await dispose_db()
