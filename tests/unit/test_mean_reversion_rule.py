"""Unit tests for deterministic Mean Reversion rule in Phase F3 (§4.4 & §12.1)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.errors import InvalidRequestError
from app.services.mean_reversion_rule import (
    MeanReversionRule,
    calculate_bollinger_bands,
    calculate_rsi_series,
)
from app.services.trend_following_rule import REQUIRED_EXPLANATION_KEYS, CandleBar


def make_mean_reversion_candles(
    *,
    symbol: str = "ETH/USDT",
    rsi_cross_above_30: bool = True,
    prev_below_lower_bb: bool = True,
    curr_inside_bb: bool = True,
    latest_closed: bool = True,
) -> list[CandleBar]:
    """Build a deterministic 1H closed candle series for Mean Reversion evaluation."""
    base_time = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    closes: list[Decimal] = [Decimal("2600") for _ in range(18)]

    if prev_below_lower_bb:
        # Sharp drop pushes RSI(14) well below 30 and close below Lower Bollinger Band(20, 2)
        closes.extend(
            [
                Decimal("2560"),
                Decimal("2520"),
                Decimal("2480"),
                Decimal("2430"),
                Decimal("2370"),
                Decimal("2300"),
            ]
        )
    else:
        # Mild dip keeps previous close inside Bollinger Band while RSI dips below 30
        closes.extend(
            [
                Decimal("2595"),
                Decimal("2590"),
                Decimal("2585"),
                Decimal("2580"),
                Decimal("2575"),
                Decimal("2572"),
            ]
        )

    if not rsi_cross_above_30:
        # Continues dropping so RSI stays below 30 and does not cross above 30
        closes.append(Decimal("2280"))
    elif not curr_inside_bb:
        # Rebounds slightly so RSI > 30 doesn't return inside BB (or stays below lower band)
        closes.append(Decimal("2305"))
    else:
        # Strong bounce brings RSI(14) from < 30 back above 30 and close inside BB(20, 2)
        closes.append(Decimal("2440"))

    candles: list[CandleBar] = []
    for idx, close_p in enumerate(closes):
        open_t = base_time + timedelta(hours=idx)
        close_t = open_t + timedelta(hours=1)
        is_last = idx == len(closes) - 1
        candles.append(
            CandleBar(
                symbol=symbol,
                timeframe="1H",
                open_time=open_t,
                close_time=close_t,
                open=close_p - Decimal("5"),
                high=close_p + Decimal("15"),
                low=close_p - Decimal("15"),
                close=close_p,
                volume=Decimal("250"),
                is_closed=(latest_closed if is_last else True),
            )
        )
    return candles


def test_mean_reversion_requires_rsi_cross() -> None:
    """Verify Mean Reversion requires RSI(14) < 30 crossing back above 30 on closed 1H candles."""
    rule = MeanReversionRule()

    # Valid RSI cross (< 30 -> > 30) and Bollinger return produces candidate
    valid_candles = make_mean_reversion_candles(
        rsi_cross_above_30=True,
        prev_below_lower_bb=True,
        curr_inside_bb=True,
    )
    rsi_vals = calculate_rsi_series([c.close for c in valid_candles], period=14)
    assert rsi_vals[-2] < Decimal("30")
    assert rsi_vals[-1] > Decimal("30")

    candidate = rule.evaluate(
        symbol="ETH/USDT",
        candles_1h=valid_candles,
        data_quality_score=Decimal("0.90"),
        confidence_score=Decimal("0.75"),
    )
    assert candidate is not None
    assert candidate.symbol == "ETH/USDT"
    assert candidate.direction == "LONG"
    assert candidate.reference_price == Decimal("2440")
    assert REQUIRED_EXPLANATION_KEYS.issubset(candidate.explanation_json.keys())

    # Without RSI crossing back above 30 -> returns None
    no_cross_candles = make_mean_reversion_candles(rsi_cross_above_30=False)
    assert rule.evaluate(symbol="ETH/USDT", candles_1h=no_cross_candles) is None


def test_mean_reversion_requires_bollinger_return() -> None:
    """Verify Mean Reversion requires prior close <= Lower BB(20,2) and current close inside BB."""
    rule = MeanReversionRule()

    # 1. Previous close was NOT at or below Lower Bollinger Band(20, 2) -> None
    not_below_bb = make_mean_reversion_candles(
        rsi_cross_above_30=True,
        prev_below_lower_bb=False,
        curr_inside_bb=True,
    )
    assert rule.evaluate(symbol="ETH/USDT", candles_1h=not_below_bb) is None

    # 2. Current close did NOT return inside Bollinger Band(20, 2) -> None
    not_returned_inside = make_mean_reversion_candles(
        rsi_cross_above_30=True,
        prev_below_lower_bb=True,
        curr_inside_bb=False,
    )
    assert rule.evaluate(symbol="ETH/USDT", candles_1h=not_returned_inside) is None


def test_rsi_and_bollinger_validation_guards() -> None:
    """Verify RSI and Bollinger Band helper validation guards."""
    with pytest.raises(InvalidRequestError):
        calculate_rsi_series([Decimal("100")], period=0)
    with pytest.raises(InvalidRequestError):
        calculate_rsi_series([Decimal("100"), Decimal("101")], period=14)
    with pytest.raises(InvalidRequestError):
        calculate_bollinger_bands([Decimal("100")], period=0)
    with pytest.raises(InvalidRequestError):
        calculate_bollinger_bands([Decimal("100")], period=20)
