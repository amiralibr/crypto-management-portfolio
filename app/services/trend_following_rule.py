"""Deterministic Trend Following rule for MVP-0 Phase F3 (§4.1–§4.3 & §4.5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.enums import ALLOWED_SYMBOLS, ALLOWED_TIMEFRAMES
from app.core.errors import InvalidRequestError
from app.services.risk_engine import ensure_decimal

MIN_DATA_QUALITY_SCORE: Decimal = Decimal("0.8")
MIN_CONFIDENCE_SCORE: Decimal = Decimal("0.6")
VOLUME_SURGE_MULTIPLIER: Decimal = Decimal("1.5")
TREND_FOLLOWING_RULE_VERSION: str = "1.0.0"

REQUIRED_EXPLANATION_KEYS: frozenset[str] = frozenset(
    {
        "entry_reason",
        "risk_reason",
        "confluence_score",
        "regime",
        "factors",
    }
)


def ensure_utc_datetime(dt: datetime, field_name: str) -> datetime:
    """Validate that a datetime is timezone-aware (never naive)."""
    if not isinstance(dt, datetime):
        raise TypeError(f"Field '{field_name}' must be datetime")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise InvalidRequestError(f"Field '{field_name}' must be timezone-aware UTC datetime")
    return dt


@dataclass(frozen=True)
class CandleBar:
    """Immutable OHLCV candle bar using Decimal arithmetic and UTC timestamps."""

    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool = True

    def __post_init__(self) -> None:
        ensure_utc_datetime(self.open_time, "open_time")
        ensure_utc_datetime(self.close_time, "close_time")
        for field_name, val in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            ensure_decimal(val, field_name)
        if (
            self.open <= Decimal("0")
            or self.high <= Decimal("0")
            or self.low <= Decimal("0")
            or self.close <= Decimal("0")
        ):
            raise InvalidRequestError("Candle OHLC prices must be positive Decimals")
        if self.volume < Decimal("0"):
            raise InvalidRequestError("Candle volume cannot be negative")
        if self.high < self.low or self.high < self.open or self.high < self.close:
            raise InvalidRequestError("Candle high must be >= open, close, and low")
        if self.low > self.open or self.low > self.close:
            raise InvalidRequestError("Candle low must be <= open and close")


@dataclass(frozen=True)
class SignalCandidate:
    """Validated deterministic signal candidate produced by a strategy rule."""

    strategy_code: str
    symbol: str
    timeframe: str
    direction: str
    reference_price: Decimal
    entry_range_min: Decimal
    entry_range_max: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    risk_reward_ratio: Decimal
    data_quality_score: Decimal
    confidence_score: Decimal
    rule_version: str
    explanation_json: dict[str, Any]


def filter_closed_candles(
    candles: Sequence[CandleBar],
    *,
    evaluation_time: datetime | None = None,
    reject_open_candles: bool = False,
) -> list[CandleBar]:
    """Return only closed candles sorted chronologically by close_time (§4.2).

    If `reject_open_candles=True`, raises InvalidRequestError when any open/incomplete
    candle is present in `candles`.
    """
    if evaluation_time is not None:
        ensure_utc_datetime(evaluation_time, "evaluation_time")

    closed: list[CandleBar] = []
    for candle in candles:
        is_complete = candle.is_closed and (
            evaluation_time is None or candle.close_time <= evaluation_time
        )
        if not is_complete:
            if reject_open_candles:
                raise InvalidRequestError(
                    "Open or incomplete candle is forbidden; Signal Engine uses closed candles only"
                )
            continue
        closed.append(candle)

    closed.sort(key=lambda c: c.close_time)
    return closed


def calculate_ema(values: Sequence[Decimal], period: int) -> Decimal:
    """Compute deterministic Exponential Moving Average (EMA) using Decimal only."""
    if period <= 0:
        raise InvalidRequestError("EMA period must be positive")
    if len(values) < period:
        raise InvalidRequestError(f"Insufficient closed candles for EMA({period}): {len(values)}")

    for idx, val in enumerate(values):
        ensure_decimal(val, f"values[{idx}]")

    period_dec = Decimal(period)
    multiplier = Decimal("2") / Decimal(period + 1)
    one_minus_mult = Decimal("1") - multiplier

    ema = sum(values[:period], Decimal("0")) / period_dec
    for price in values[period:]:
        ema = (price * multiplier) + (ema * one_minus_mult)
    return ema


def validate_explanation_json(explanation_json: dict[str, Any]) -> dict[str, Any]:
    """Validate that `explanation_json` contains all required §4.5 fields."""
    if not isinstance(explanation_json, dict):
        raise InvalidRequestError("explanation_json must be a dictionary")
    missing = REQUIRED_EXPLANATION_KEYS - set(explanation_json.keys())
    if missing:
        raise InvalidRequestError(
            f"explanation_json is missing required fields: {sorted(missing)}",
            details={"missing_fields": sorted(missing)},
        )
    for key in ("entry_reason", "risk_reason", "regime"):
        val = explanation_json.get(key)
        if not isinstance(val, str) or not val.strip():
            raise InvalidRequestError(f"explanation_json['{key}'] must be a non-empty string")
    factors = explanation_json.get("factors")
    if not isinstance(factors, dict | list) or not factors:
        raise InvalidRequestError("explanation_json['factors'] must be a non-empty dict or list")
    return explanation_json


def validate_market_and_scores(
    *,
    symbol: str,
    timeframe: str,
    direction: str = "LONG",
    market: str = "SPOT",
    leverage: Decimal | None = None,
    data_quality_score: Decimal,
    confidence_score: Decimal,
) -> None:
    """Validate §4.1 Allowed Market and §4.3/§4.4 score floors."""
    if symbol not in ALLOWED_SYMBOLS:
        raise InvalidRequestError(
            f"Symbol '{symbol}' is not allowed in MVP-0; allowed: {sorted(ALLOWED_SYMBOLS)}",
            details={"symbol": symbol},
        )
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise InvalidRequestError(
            f"Timeframe '{timeframe}' is not allowed; allowed: {sorted(ALLOWED_TIMEFRAMES)}",
            details={"timeframe": timeframe},
        )
    if direction != "LONG":
        raise InvalidRequestError(
            f"Direction '{direction}' is forbidden in MVP-0; Spot LONG only",
            details={"direction": direction},
        )
    if market != "SPOT":
        raise InvalidRequestError(
            f"Market '{market}' is forbidden in MVP-0; SPOT only",
            details={"market": market},
        )
    if leverage is not None:
        ensure_decimal(leverage, "leverage")
        if leverage != Decimal("1"):
            raise InvalidRequestError(
                "Leverage is forbidden in MVP-0; Spot 1x only",
                details={"leverage": str(leverage)},
            )

    ensure_decimal(data_quality_score, "data_quality_score")
    ensure_decimal(confidence_score, "confidence_score")
    if data_quality_score < MIN_DATA_QUALITY_SCORE or data_quality_score > Decimal("1"):
        raise InvalidRequestError(
            f"data_quality_score ({data_quality_score}) must be >= {MIN_DATA_QUALITY_SCORE}",
            details={"data_quality_score": str(data_quality_score)},
        )
    if confidence_score < MIN_CONFIDENCE_SCORE or confidence_score > Decimal("1"):
        raise InvalidRequestError(
            f"confidence_score ({confidence_score}) must be >= {MIN_CONFIDENCE_SCORE}",
            details={"confidence_score": str(confidence_score)},
        )


class TrendFollowingRule:
    """Deterministic Trend Following rule evaluator (§4.3).

    Conditions required to emit a Spot LONG Trend Following signal:
    1. EMA(50) > EMA(200) on 4H closed candles
    2. Close > EMA(20) on 1H closed candles
    3. Close > highest high of previous 20 closed 1H candles
    4. Volume >= 1.5 * average volume of previous 20 closed 1H candles
    5. Data quality score >= 0.8
    6. Confidence score >= 0.6
    """

    rule_version: str = TREND_FOLLOWING_RULE_VERSION
    strategy_code: str = "TREND_FOLLOWING"

    def evaluate(
        self,
        *,
        symbol: str,
        candles_4h: Sequence[CandleBar],
        candles_1h: Sequence[CandleBar],
        data_quality_score: Decimal = Decimal("0.95"),
        confidence_score: Decimal = Decimal("0.80"),
        timeframe: str = "1H",
        direction: str = "LONG",
        market: str = "SPOT",
        leverage: Decimal | None = None,
        evaluation_time: datetime | None = None,
        reject_open_candles: bool = False,
    ) -> SignalCandidate | None:
        """Evaluate Trend Following rule on closed 4H and 1H candles."""
        validate_market_and_scores(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
        )

        closed_4h = filter_closed_candles(
            candles_4h,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )
        closed_1h = filter_closed_candles(
            candles_1h,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )

        if len(closed_4h) < 200 or len(closed_1h) < 21:
            return None

        if any(c.symbol != symbol for c in closed_4h) or any(c.symbol != symbol for c in closed_1h):
            raise InvalidRequestError("Candle symbol mismatch with requested symbol")

        closes_4h = [c.close for c in closed_4h]
        ema_50_4h = calculate_ema(closes_4h, 50)
        ema_200_4h = calculate_ema(closes_4h, 200)

        # Condition 1: EMA(50) > EMA(200) on 4H closed candles
        if ema_50_4h <= ema_200_4h:
            return None

        closes_1h = [c.close for c in closed_1h]
        ema_20_1h = calculate_ema(closes_1h, 20)
        latest_1h = closed_1h[-1]

        # Condition 2: Close > EMA(20) on 1H closed candles
        if latest_1h.close <= ema_20_1h:
            return None

        prev_20_1h = closed_1h[-21:-1]
        highest_high_20 = max(c.high for c in prev_20_1h)

        # Condition 3: Close > highest high of previous 20 closed 1H candles
        if latest_1h.close <= highest_high_20:
            return None

        avg_volume_20 = sum((c.volume for c in prev_20_1h), Decimal("0")) / Decimal("20")
        required_volume = VOLUME_SURGE_MULTIPLIER * avg_volume_20

        # Condition 4: Volume >= 1.5 * average volume of previous 20 closed 1H candles
        if avg_volume_20 <= Decimal("0") or latest_1h.volume < required_volume:
            return None

        ref_price = latest_1h.close
        entry_min = (ref_price * Decimal("0.999")).quantize(Decimal("0.00000001"))
        entry_max = (ref_price * Decimal("1.001")).quantize(Decimal("0.00000001"))
        stop_loss = (ref_price * Decimal("0.98")).quantize(Decimal("0.00000001"))
        take_profit = (ref_price * Decimal("1.04")).quantize(Decimal("0.00000001"))
        rr_ratio = ((take_profit - ref_price) / (ref_price - stop_loss)).quantize(
            Decimal("0.000001")
        )

        explanation = validate_explanation_json(
            {
                "entry_reason": (
                    "4H EMA(50) > EMA(200) bull regime with 1H close > EMA(20), "
                    "20-bar breakout, and >= 1.5x volume surge on closed candles"
                ),
                "risk_reason": "2.0% stop distance below reference price with 2.0R target",
                "confluence_score": str(confidence_score),
                "regime": "BULL_TREND",
                "factors": {
                    "ema_50_4h": str(ema_50_4h.quantize(Decimal("0.00000001"))),
                    "ema_200_4h": str(ema_200_4h.quantize(Decimal("0.00000001"))),
                    "ema_20_1h": str(ema_20_1h.quantize(Decimal("0.00000001"))),
                    "highest_high_20_1h": str(highest_high_20),
                    "latest_close_1h": str(latest_1h.close),
                    "latest_volume_1h": str(latest_1h.volume),
                    "avg_volume_20_1h": str(avg_volume_20.quantize(Decimal("0.00000001"))),
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
