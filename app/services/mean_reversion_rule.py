"""Deterministic Mean Reversion rule for MVP-0 Phase F3 (§4.1–§4.2, §4.4 & §4.5)."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from app.core.errors import InvalidRequestError
from app.services.risk_engine import ensure_decimal
from app.services.trend_following_rule import (
    CandleBar,
    SignalCandidate,
    filter_closed_candles,
    validate_explanation_json,
    validate_market_and_scores,
)

RSI_PERIOD: int = 14
RSI_OVERSOLD_THRESHOLD: Decimal = Decimal("30")
BOLLINGER_PERIOD: int = 20
BOLLINGER_STD_MULT: Decimal = Decimal("2")
MEAN_REVERSION_RULE_VERSION: str = "1.0.0"


def calculate_rsi_series(closes: Sequence[Decimal], period: int = RSI_PERIOD) -> list[Decimal]:
    """Compute Wilder's RSI series using Decimal arithmetic only."""
    if period <= 0:
        raise InvalidRequestError("RSI period must be positive")
    if len(closes) < period + 1:
        raise InvalidRequestError(f"Insufficient closed candles for RSI({period}): {len(closes)}")

    for idx, val in enumerate(closes):
        ensure_decimal(val, f"closes[{idx}]")

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    period_dec = Decimal(period)
    prev_weight = Decimal(period - 1)

    gains = [max(d, Decimal("0")) for d in deltas[:period]]
    losses = [max(-d, Decimal("0")) for d in deltas[:period]]

    avg_gain = sum(gains, Decimal("0")) / period_dec
    avg_loss = sum(losses, Decimal("0")) / period_dec

    def _to_rsi(g: Decimal, l_val: Decimal) -> Decimal:
        if l_val == Decimal("0"):
            return Decimal("100") if g > Decimal("0") else Decimal("50")
        if g == Decimal("0"):
            return Decimal("0")
        rs = g / l_val
        return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    rsi_values: list[Decimal] = [_to_rsi(avg_gain, avg_loss)]
    for d in deltas[period:]:
        gain = max(d, Decimal("0"))
        loss = max(-d, Decimal("0"))
        avg_gain = ((avg_gain * prev_weight) + gain) / period_dec
        avg_loss = ((avg_loss * prev_weight) + loss) / period_dec
        rsi_values.append(_to_rsi(avg_gain, avg_loss))

    return rsi_values


def calculate_bollinger_bands(
    closes: Sequence[Decimal],
    period: int = BOLLINGER_PERIOD,
    std_mult: Decimal = BOLLINGER_STD_MULT,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (lower_band, middle_band, upper_band) over the last `period` closed candles."""
    if period <= 0:
        raise InvalidRequestError("Bollinger Band period must be positive")
    ensure_decimal(std_mult, "std_mult")
    if len(closes) < period:
        raise InvalidRequestError(
            f"Insufficient closed candles for BollingerBand({period}): {len(closes)}"
        )

    window = closes[-period:]
    for idx, val in enumerate(window):
        ensure_decimal(val, f"window[{idx}]")

    period_dec = Decimal(period)
    middle = sum(window, Decimal("0")) / period_dec
    variance = sum(((x - middle) * (x - middle) for x in window), Decimal("0")) / period_dec
    std_dev = variance.sqrt()
    lower = middle - (std_mult * std_dev)
    upper = middle + (std_mult * std_dev)
    return lower, middle, upper


class MeanReversionRule:
    """Deterministic Mean Reversion rule evaluator (§4.4).

    Conditions required to emit a Spot LONG Mean Reversion signal:
    1. RSI(14) was below 30 and crosses back above 30 on closed 1H candles
    2. Close was at or below Lower Bollinger Band(20, 2)
    3. Close returns inside the Bollinger Band
    4. Data quality score >= 0.8
    5. Confidence score >= 0.6
    """

    rule_version: str = MEAN_REVERSION_RULE_VERSION
    strategy_code: str = "MEAN_REVERSION"

    def evaluate(
        self,
        *,
        symbol: str,
        candles_1h: Sequence[CandleBar],
        data_quality_score: Decimal = Decimal("0.95"),
        confidence_score: Decimal = Decimal("0.75"),
        timeframe: str = "1H",
        direction: str = "LONG",
        market: str = "SPOT",
        leverage: Decimal | None = None,
        evaluation_time: datetime | None = None,
        reject_open_candles: bool = False,
    ) -> SignalCandidate | None:
        """Evaluate Mean Reversion rule on closed 1H candles."""
        validate_market_and_scores(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
        )

        closed_1h = filter_closed_candles(
            candles_1h,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )
        if len(closed_1h) < BOLLINGER_PERIOD + 1:
            return None

        if any(c.symbol != symbol for c in closed_1h):
            raise InvalidRequestError("Candle symbol mismatch with requested symbol")

        closes = [c.close for c in closed_1h]
        rsi_series = calculate_rsi_series(closes, period=RSI_PERIOD)
        if len(rsi_series) < 2:
            return None

        prev_rsi = rsi_series[-2]
        curr_rsi = rsi_series[-1]

        # Condition 1: RSI(14) was below 30 and crosses back above 30 on closed 1H candles
        if not (prev_rsi < RSI_OVERSOLD_THRESHOLD and curr_rsi > RSI_OVERSOLD_THRESHOLD):
            return None

        prev_lower, _prev_mid, _prev_upper = calculate_bollinger_bands(
            closes[:-1],
            period=BOLLINGER_PERIOD,
            std_mult=BOLLINGER_STD_MULT,
        )
        curr_lower, curr_mid, curr_upper = calculate_bollinger_bands(
            closes,
            period=BOLLINGER_PERIOD,
            std_mult=BOLLINGER_STD_MULT,
        )

        prev_close = closed_1h[-2].close
        curr_close = closed_1h[-1].close

        # Condition 2: Close was at or below Lower Bollinger Band(20, 2)
        if prev_close > prev_lower:
            return None

        # Condition 3: Close returns inside the Bollinger Band
        if not (curr_close > curr_lower and curr_close < curr_upper):
            return None

        ref_price = curr_close
        entry_min = (ref_price * Decimal("0.999")).quantize(Decimal("0.00000001"))
        entry_max = (ref_price * Decimal("1.001")).quantize(Decimal("0.00000001"))
        stop_loss = (ref_price * Decimal("0.985")).quantize(Decimal("0.00000001"))
        take_profit = max(curr_mid, (ref_price * Decimal("1.03"))).quantize(Decimal("0.00000001"))
        rr_ratio = ((take_profit - ref_price) / (ref_price - stop_loss)).quantize(
            Decimal("0.000001")
        )

        explanation = validate_explanation_json(
            {
                "entry_reason": (
                    "1H RSI(14) crossed back above 30 after oversold excursion and "
                    "close returned inside Bollinger Band(20, 2) on closed candles"
                ),
                "risk_reason": "1.5% stop distance below reference price targeting mean reversion",
                "confluence_score": str(confidence_score),
                "regime": "RANGE_MEAN_REVERSION",
                "factors": {
                    "prev_rsi_14": str(prev_rsi.quantize(Decimal("0.0001"))),
                    "curr_rsi_14": str(curr_rsi.quantize(Decimal("0.0001"))),
                    "prev_close_1h": str(prev_close),
                    "prev_lower_bb": str(prev_lower.quantize(Decimal("0.00000001"))),
                    "curr_close_1h": str(curr_close),
                    "curr_lower_bb": str(curr_lower.quantize(Decimal("0.00000001"))),
                    "curr_middle_bb": str(curr_mid.quantize(Decimal("0.00000001"))),
                },
            }
        )

        return SignalCandidate(
            strategy_code=self.strategy_code,
            symbol=symbol,
            timeframe=timeframe,
            direction="LONG",
            reference_price=ref_price,
            entry_range_min=entry_min,
            entry_range_max=entry_max,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_reward_ratio=rr_ratio,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            rule_version=self.rule_version,
            explanation_json=explanation,
        )
