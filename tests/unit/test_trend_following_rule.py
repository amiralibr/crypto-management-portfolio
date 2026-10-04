"""Unit tests for deterministic Trend Following rule in Phase F3 (§4.3 & §12.1)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.errors import InvalidRequestError
from app.services.trend_following_rule import (
    REQUIRED_EXPLANATION_KEYS,
    CandleBar,
    TrendFollowingRule,
    calculate_ema,
    filter_closed_candles,
)


def make_trend_candles(
    *,
    symbol: str = "BTC/USDT",
    bull_4h: bool = True,
    breakout_1h: bool = True,
    volume_surge_1h: bool = True,
    above_ema20_1h: bool = True,
    latest_1h_closed: bool = True,
) -> tuple[list[CandleBar], list[CandleBar]]:
    """Build deterministic 4H (210 bars) and 1H (30 bars) candle series."""
    base_time = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)

    candles_4h: list[CandleBar] = []
    for i in range(210):
        open_t = base_time + timedelta(hours=4 * i)
        close_t = open_t + timedelta(hours=4)
        # Rising prices produce EMA(50) > EMA(200); falling prices produce EMA(50) < EMA(200)
        step = Decimal(i) * (Decimal("20") if bull_4h else Decimal("-20"))
        close_p = Decimal("55000") + step
        candles_4h.append(
            CandleBar(
                symbol=symbol,
                timeframe="4H",
                open_time=open_t,
                close_time=close_t,
                open=close_p - Decimal("10"),
                high=close_p + Decimal("25"),
                low=close_p - Decimal("25"),
                close=close_p,
                volume=Decimal("100"),
                is_closed=True,
            )
        )

    candles_1h: list[CandleBar] = []
    for j in range(29):
        open_t = base_time + timedelta(hours=j)
        close_t = open_t + timedelta(hours=1)
        close_p = Decimal("60000") + (Decimal(j) * Decimal("5"))
        candles_1h.append(
            CandleBar(
                symbol=symbol,
                timeframe="1H",
                open_time=open_t,
                close_time=close_t,
                open=close_p - Decimal("5"),
                high=close_p + Decimal("10"),
                low=close_p - Decimal("10"),
                close=close_p,
                volume=Decimal("100"),
                is_closed=True,
            )
        )

    last_open = base_time + timedelta(hours=29)
    last_close = last_open + timedelta(hours=1)
    if not above_ema20_1h:
        final_close = Decimal("59800")
        final_high = Decimal("59850")
        final_low = Decimal("59750")
    elif breakout_1h:
        # Previous 20 highest high is 60000 + 28*5 + 10 = 60150; 60300 > 60150
        final_close = Decimal("60300")
        final_high = Decimal("60320")
        final_low = Decimal("60100")
    else:
        # Above EMA(20) (~60095) but not above previous 20 highest high (60150)
        final_close = Decimal("60140")
        final_high = Decimal("60145")
        final_low = Decimal("60080")

    final_vol = Decimal("160") if volume_surge_1h else Decimal("120")
    candles_1h.append(
        CandleBar(
            symbol=symbol,
            timeframe="1H",
            open_time=last_open,
            close_time=last_close,
            open=Decimal("60120") if above_ema20_1h else Decimal("59820"),
            high=final_high,
            low=final_low,
            close=final_close,
            volume=final_vol,
            is_closed=latest_1h_closed,
        )
    )
    return candles_4h, candles_1h


def test_trend_following_requires_all_conditions() -> None:
    """Verify Trend Following emits a signal only when all 6 §4.3 conditions hold."""
    rule = TrendFollowingRule()

    # 1. All conditions satisfied -> emits valid LONG signal candidate
    c4h, c1h = make_trend_candles()
    candidate = rule.evaluate(
        symbol="BTC/USDT",
        candles_4h=c4h,
        candles_1h=c1h,
        data_quality_score=Decimal("0.92"),
        confidence_score=Decimal("0.78"),
    )
    assert candidate is not None
    assert candidate.symbol == "BTC/USDT"
    assert candidate.direction == "LONG"
    assert candidate.reference_price == Decimal("60300")
    assert REQUIRED_EXPLANATION_KEYS.issubset(candidate.explanation_json.keys())

    # 2. Condition 1 fails: 4H EMA(50) <= EMA(200)
    c4h_bear, c1h_ok = make_trend_candles(bull_4h=False)
    assert (
        rule.evaluate(
            symbol="BTC/USDT",
            candles_4h=c4h_bear,
            candles_1h=c1h_ok,
        )
        is None
    )

    # 3. Condition 2 fails: 1H Close <= EMA(20)
    c4h_ok, c1h_below_ema = make_trend_candles(above_ema20_1h=False)
    assert (
        rule.evaluate(
            symbol="BTC/USDT",
            candles_4h=c4h_ok,
            candles_1h=c1h_below_ema,
        )
        is None
    )

    # 4. Condition 3 fails: 1H Close <= highest high of previous 20 closed 1H candles
    c4h_ok, c1h_no_breakout = make_trend_candles(breakout_1h=False)
    assert (
        rule.evaluate(
            symbol="BTC/USDT",
            candles_4h=c4h_ok,
            candles_1h=c1h_no_breakout,
        )
        is None
    )


def test_trend_following_rejects_insufficient_volume() -> None:
    """Verify Trend Following returns None when 1H volume < 1.5x 20-bar average (§4.3 #4)."""
    rule = TrendFollowingRule()
    c4h, c1h_low_vol = make_trend_candles(volume_surge_1h=False)
    candidate = rule.evaluate(
        symbol="BTC/USDT",
        candles_4h=c4h,
        candles_1h=c1h_low_vol,
        data_quality_score=Decimal("0.95"),
        confidence_score=Decimal("0.85"),
    )
    assert candidate is None


def test_ema_and_candle_validation_guards() -> None:
    """Verify EMA calculation and CandleBar validation guards reject invalid inputs."""
    with pytest.raises(InvalidRequestError):
        calculate_ema([Decimal("100")], period=0)
    with pytest.raises(InvalidRequestError):
        calculate_ema([Decimal("100"), Decimal("101")], period=5)

    now = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    with pytest.raises(InvalidRequestError):
        # Naive datetime rejected
        CandleBar(
            symbol="BTC/USDT",
            timeframe="1H",
            open_time=datetime(2026, 10, 1, 0, 0),
            close_time=now,
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("10"),
        )

    c4h, c1h_open = make_trend_candles(latest_1h_closed=False)
    with pytest.raises(InvalidRequestError):
        filter_closed_candles(c1h_open, reject_open_candles=True)
    assert len(filter_closed_candles(c1h_open, reject_open_candles=False)) == len(c1h_open) - 1

    # Additional CandleBar, explanation, and rule validation branches
    from app.services.trend_following_rule import (
        ensure_utc_datetime,
        validate_explanation_json,
        validate_market_and_scores,
    )

    with pytest.raises(TypeError):
        ensure_utc_datetime("not-a-dt", "dt")  # type: ignore[arg-type]
    with pytest.raises(InvalidRequestError):
        CandleBar(
            symbol="BTC/USDT",
            timeframe="1H",
            open_time=now,
            close_time=now,
            open=Decimal("0"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("10"),
        )
    with pytest.raises(InvalidRequestError):
        CandleBar(
            symbol="BTC/USDT",
            timeframe="1H",
            open_time=now,
            close_time=now,
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("-1"),
        )
    with pytest.raises(InvalidRequestError):
        CandleBar(
            symbol="BTC/USDT",
            timeframe="1H",
            open_time=now,
            close_time=now,
            open=Decimal("100"),
            high=Decimal("95"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("10"),
        )
    with pytest.raises(InvalidRequestError):
        CandleBar(
            symbol="BTC/USDT",
            timeframe="1H",
            open_time=now,
            close_time=now,
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("102"),
            close=Decimal("105"),
            volume=Decimal("10"),
        )
    with pytest.raises(InvalidRequestError):
        validate_explanation_json("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(InvalidRequestError):
        validate_explanation_json(
            {
                "entry_reason": "",
                "risk_reason": "ok",
                "confluence_score": "0.8",
                "regime": "BULL",
                "factors": {"a": 1},
            }
        )
    with pytest.raises(InvalidRequestError):
        validate_explanation_json(
            {
                "entry_reason": "ok",
                "risk_reason": "ok",
                "confluence_score": "0.8",
                "regime": "BULL",
                "factors": {},
            }
        )
    with pytest.raises(InvalidRequestError):
        validate_market_and_scores(
            symbol="BTC/USDT",
            timeframe="5M",
            data_quality_score=Decimal("0.9"),
            confidence_score=Decimal("0.8"),
        )

    rule = TrendFollowingRule()
    assert rule.evaluate(symbol="BTC/USDT", candles_4h=c4h[:10], candles_1h=c1h_open[:5]) is None
