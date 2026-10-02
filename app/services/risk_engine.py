"""Deterministic Risk Engine and Position Sizing service for MVP-0 (§10)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal

from app.core.enums import ALLOWED_SYMBOLS, RiskDecisionStatus
from app.core.metrics import RISK_REJECTIONS_TOTAL

MAX_RISK_PER_TRADE: Decimal = Decimal("0.005")  # 0.50%
MAX_DAILY_LOSS: Decimal = Decimal("0.02")  # 2.00%
MAX_WEEKLY_LOSS: Decimal = Decimal("0.05")  # 5.00%
MAX_ASSET_WEIGHT: Decimal = Decimal("0.15")  # 15.00%
MAX_TOTAL_EXPOSURE: Decimal = Decimal("0.70")  # 70.00%
MIN_CASH_RESERVE: Decimal = Decimal("0.15")  # 15.00%
SOFT_DRAWDOWN: Decimal = Decimal("0.08")  # 8.00%
HARD_DRAWDOWN: Decimal = Decimal("0.12")  # 12.00%
KILL_SWITCH_DRAWDOWN: Decimal = Decimal("0.15")  # 15.00%

MAX_VOLUME_24H_SHARE: Decimal = Decimal("0.01")  # 1.00% of 24h volume
MAX_ORDER_BOOK_DEPTH_SHARE: Decimal = Decimal("0.10")  # 10.00% of 0.5% depth
MAX_SPREAD_PCT: Decimal = Decimal("0.001")  # 0.10% max spread
MAX_MARKET_DATA_AGE_SECONDS: Decimal = Decimal("5")  # 5 seconds freshness SLA
MIN_INITIAL_CAPITAL_USDT: Decimal = Decimal("500")  # Minimum IPS capital
MIN_VOLATILITY_BARS: int = 14


def ensure_decimal(value: object, field_name: str) -> Decimal:
    """Validate that a financial input is a Decimal (never a float)."""
    if isinstance(value, float):
        raise TypeError(f"Field '{field_name}' must be Decimal, not float")
    if not isinstance(value, Decimal):
        raise TypeError(f"Field '{field_name}' must be Decimal, got {type(value).__name__}")
    return value


def floor_to_step(quantity: Decimal, step_size: Decimal) -> Decimal:
    """Floor a Decimal quantity down to the exchange step size using ROUND_DOWN."""
    ensure_decimal(quantity, "quantity")
    ensure_decimal(step_size, "step_size")
    if step_size <= Decimal("0"):
        raise ValueError("step_size must be positive")
    if quantity <= Decimal("0"):
        return Decimal("0")
    steps = (quantity / step_size).to_integral_value(rounding=ROUND_DOWN)
    return (steps * step_size).quantize(step_size, rounding=ROUND_DOWN)


@dataclass(frozen=True)
class InvestmentPolicySnapshot:
    """Immutable Investment Policy Statement (IPS) configuration snapshot (§10 & Master §10.2)."""

    initial_capital: Decimal = Decimal("10000")
    max_risk_per_trade: Decimal = MAX_RISK_PER_TRADE
    max_daily_loss: Decimal = MAX_DAILY_LOSS
    max_weekly_loss: Decimal = MAX_WEEKLY_LOSS
    max_drawdown_hard: Decimal = HARD_DRAWDOWN
    max_asset_weight: Decimal = MAX_ASSET_WEIGHT
    max_total_exposure: Decimal = MAX_TOTAL_EXPOSURE
    min_cash_reserve: Decimal = MIN_CASH_RESERVE
    user_max_notional: Decimal = Decimal("1000000")
    allowed_assets: tuple[str, ...] = ("BTC/USDT", "ETH/USDT", "BNB/USDT")
    approval_timeout_minutes: int | None = None
    default_action_on_timeout: str = "EXPIRED"

    def validate(self) -> list[str]:
        """Validate IPS constraints and return list of violation codes."""
        errors: list[str] = []
        try:
            ensure_decimal(self.initial_capital, "initial_capital")
            ensure_decimal(self.max_risk_per_trade, "max_risk_per_trade")
            ensure_decimal(self.max_daily_loss, "max_daily_loss")
            ensure_decimal(self.max_weekly_loss, "max_weekly_loss")
            ensure_decimal(self.max_drawdown_hard, "max_drawdown_hard")
            ensure_decimal(self.max_asset_weight, "max_asset_weight")
            ensure_decimal(self.max_total_exposure, "max_total_exposure")
            ensure_decimal(self.min_cash_reserve, "min_cash_reserve")
            ensure_decimal(self.user_max_notional, "user_max_notional")
        except TypeError:
            errors.append("IPS_NON_DECIMAL_VALUE")
            return errors

        if self.initial_capital < MIN_INITIAL_CAPITAL_USDT:
            errors.append("IPS_INITIAL_CAPITAL_BELOW_MINIMUM")
        if self.max_risk_per_trade <= Decimal("0") or self.max_risk_per_trade > MAX_RISK_PER_TRADE:
            errors.append("IPS_MAX_RISK_PER_TRADE_EXCEEDS_HARD_CAP")
        if self.max_daily_loss <= Decimal("0") or self.max_daily_loss > MAX_DAILY_LOSS:
            errors.append("IPS_MAX_DAILY_LOSS_EXCEEDS_HARD_CAP")
        if self.max_weekly_loss <= Decimal("0") or self.max_weekly_loss > MAX_WEEKLY_LOSS:
            errors.append("IPS_MAX_WEEKLY_LOSS_EXCEEDS_HARD_CAP")
        if self.max_drawdown_hard <= Decimal("0") or self.max_drawdown_hard > HARD_DRAWDOWN:
            errors.append("IPS_MAX_DRAWDOWN_HARD_EXCEEDS_HARD_CAP")
        if self.max_asset_weight <= Decimal("0") or self.max_asset_weight > MAX_ASSET_WEIGHT:
            errors.append("IPS_MAX_ASSET_WEIGHT_EXCEEDS_HARD_CAP")
        if self.max_total_exposure <= Decimal("0") or self.max_total_exposure > MAX_TOTAL_EXPOSURE:
            errors.append("IPS_MAX_TOTAL_EXPOSURE_EXCEEDS_HARD_CAP")
        if self.min_cash_reserve < MIN_CASH_RESERVE or self.min_cash_reserve >= Decimal("1"):
            errors.append("IPS_MIN_CASH_RESERVE_BELOW_HARD_FLOOR")
        if self.user_max_notional <= Decimal("0"):
            errors.append("IPS_INVALID_USER_MAX_NOTIONAL")
        if not self.allowed_assets or not set(self.allowed_assets).issubset(ALLOWED_SYMBOLS):
            errors.append("IPS_DISALLOWED_ASSETS")
        if self.approval_timeout_minutes is not None and (
            not isinstance(self.approval_timeout_minutes, int)
            or isinstance(self.approval_timeout_minutes, bool)
            or self.approval_timeout_minutes < 3
            or self.approval_timeout_minutes > 240
        ):
            errors.append("IPS_INVALID_APPROVAL_TIMEOUT")
        if self.default_action_on_timeout not in ("EXPIRED", "REJECTED", "EXPIRE", "REJECT"):
            errors.append("IPS_INVALID_TIMEOUT_ACTION")
        return errors


@dataclass(frozen=True)
class RiskEvaluationInput:
    """All safety, market, and portfolio inputs required for fail-closed Risk Engine evaluation."""

    symbol: str
    direction: str
    entry_price: Decimal | None
    atr_14: Decimal | None
    equity: Decimal | None
    portfolio_value: Decimal | None = None
    available_cash: Decimal | None = None
    daily_volume_24h: Decimal | None = Decimal("500000000")
    order_book_depth_0_5pct: Decimal | None = Decimal("2000000")
    spread_pct: Decimal | None = Decimal("0.0005")
    market_data_timestamp: datetime | None = None
    evaluation_timestamp: datetime | None = None
    volatility_bars_count: int = 14
    atr_multiplier: Decimal = Decimal("2.0")
    risk_fraction: Decimal = MAX_RISK_PER_TRADE
    fee_round_trip_pct: Decimal = Decimal("0.004")
    slippage_pct: Decimal = Decimal("0.0005")
    user_max_notional: Decimal = Decimal("1000000")
    exchange_step_size: Decimal = Decimal("0.00001")
    daily_loss_pct: Decimal = Decimal("0")
    weekly_loss_pct: Decimal = Decimal("0")
    current_drawdown_pct: Decimal = Decimal("0")
    existing_asset_exposure: Decimal = Decimal("0")
    existing_total_exposure: Decimal = Decimal("0")
    exposure_multiplier: Decimal = Decimal("1.0")
    leverage: Decimal = Decimal("1.0")
    kill_switch_active: bool = False
    ips: InvestmentPolicySnapshot | None = None


@dataclass(frozen=True)
class PositionSizingResult:
    """Detailed Decimal breakdown of the §10.3 Position Sizing calculation."""

    risk_amount: Decimal
    stop_loss_distance: Decimal
    round_trip_cost_per_unit: Decimal
    effective_loss_per_unit: Decimal
    quantity_by_risk: Decimal
    notional_by_risk: Decimal
    asset_exposure_limit: Decimal
    portfolio_exposure_limit: Decimal
    volume_limit: Decimal
    depth_limit: Decimal
    cash_reserve_limit: Decimal
    user_max_notional: Decimal
    final_notional: Decimal
    final_quantity: Decimal
    stop_loss_price: Decimal


@dataclass(frozen=True)
class RiskEvaluationDecision:
    """Fail-closed Risk Engine evaluation result."""

    decision: RiskDecisionStatus
    reason_codes: list[str] = field(default_factory=list)
    sizing: PositionSizingResult | None = None
    recommend_kill_switch: bool = False


class RiskEngine:
    """Deterministic, fail-closed Risk Engine for MVP-0 (§10)."""

    def calculate_position_size(
        self,
        *,
        equity: Decimal,
        portfolio_value: Decimal,
        entry_price: Decimal,
        atr_14: Decimal,
        atr_multiplier: Decimal = Decimal("2.0"),
        risk_fraction: Decimal = MAX_RISK_PER_TRADE,
        fee_round_trip_pct: Decimal = Decimal("0.004"),
        slippage_pct: Decimal = Decimal("0.0005"),
        max_asset_weight: Decimal = MAX_ASSET_WEIGHT,
        max_total_exposure: Decimal = MAX_TOTAL_EXPOSURE,
        min_cash_reserve: Decimal = MIN_CASH_RESERVE,
        daily_volume_24h: Decimal = Decimal("500000000"),
        order_book_depth_0_5pct: Decimal = Decimal("2000000"),
        user_max_notional: Decimal = Decimal("1000000"),
        exchange_step_size: Decimal = Decimal("0.00001"),
        existing_asset_exposure: Decimal = Decimal("0"),
        existing_total_exposure: Decimal = Decimal("0"),
        available_cash: Decimal | None = None,
        exposure_multiplier: Decimal = Decimal("1.0"),
    ) -> PositionSizingResult:
        """Compute deterministic Spot LONG position size strictly using Decimal (§10.3)."""
        for name, val in (
            ("equity", equity),
            ("portfolio_value", portfolio_value),
            ("entry_price", entry_price),
            ("atr_14", atr_14),
            ("atr_multiplier", atr_multiplier),
            ("risk_fraction", risk_fraction),
            ("fee_round_trip_pct", fee_round_trip_pct),
            ("slippage_pct", slippage_pct),
            ("max_asset_weight", max_asset_weight),
            ("max_total_exposure", max_total_exposure),
            ("min_cash_reserve", min_cash_reserve),
            ("daily_volume_24h", daily_volume_24h),
            ("order_book_depth_0_5pct", order_book_depth_0_5pct),
            ("user_max_notional", user_max_notional),
            ("exchange_step_size", exchange_step_size),
            ("existing_asset_exposure", existing_asset_exposure),
            ("existing_total_exposure", existing_total_exposure),
            ("exposure_multiplier", exposure_multiplier),
        ):
            ensure_decimal(val, name)

        effective_risk_fraction = min(risk_fraction, MAX_RISK_PER_TRADE)
        effective_asset_weight = min(max_asset_weight, MAX_ASSET_WEIGHT)
        effective_total_exposure = min(max_total_exposure, MAX_TOTAL_EXPOSURE)
        effective_cash_reserve = max(min_cash_reserve, MIN_CASH_RESERVE)

        risk_amount = equity * effective_risk_fraction
        stop_loss_distance = atr_14 * atr_multiplier
        round_trip_cost_per_unit = entry_price * (fee_round_trip_pct + slippage_pct)
        effective_loss_per_unit = stop_loss_distance + round_trip_cost_per_unit
        quantity_by_risk = risk_amount / effective_loss_per_unit
        notional_by_risk = quantity_by_risk * entry_price

        asset_cap = max(
            Decimal("0"),
            (equity * effective_asset_weight) - existing_asset_exposure,
        )
        portfolio_cap = max(
            Decimal("0"),
            (portfolio_value * effective_total_exposure) - existing_total_exposure,
        )
        volume_cap = daily_volume_24h * MAX_VOLUME_24H_SHARE
        depth_cap = order_book_depth_0_5pct * MAX_ORDER_BOOK_DEPTH_SHARE

        cash_pool = (
            ensure_decimal(available_cash, "available_cash")
            if available_cash is not None
            else (portfolio_value - existing_total_exposure)
        )
        required_reserve_amount = portfolio_value * effective_cash_reserve
        cash_reserve_cap = max(Decimal("0"), cash_pool - required_reserve_amount)

        unscaled_notional = min(
            notional_by_risk,
            asset_cap,
            portfolio_cap,
            volume_cap,
            depth_cap,
            cash_reserve_cap,
            user_max_notional,
        )
        final_notional = max(Decimal("0"), unscaled_notional * exposure_multiplier)
        final_quantity = floor_to_step(final_notional / entry_price, exchange_step_size)
        stop_loss_price = max(Decimal("0"), entry_price - stop_loss_distance)

        return PositionSizingResult(
            risk_amount=risk_amount,
            stop_loss_distance=stop_loss_distance,
            round_trip_cost_per_unit=round_trip_cost_per_unit,
            effective_loss_per_unit=effective_loss_per_unit,
            quantity_by_risk=quantity_by_risk,
            notional_by_risk=notional_by_risk,
            asset_exposure_limit=asset_cap,
            portfolio_exposure_limit=portfolio_cap,
            volume_limit=volume_cap,
            depth_limit=depth_cap,
            cash_reserve_limit=cash_reserve_cap,
            user_max_notional=user_max_notional,
            final_notional=final_notional,
            final_quantity=final_quantity,
            stop_loss_price=stop_loss_price,
        )

    def evaluate(self, risk_input: RiskEvaluationInput) -> RiskEvaluationDecision:
        """Evaluate all §10.4 fail-closed rules and compute position size if approved."""
        reasons: list[str] = []
        recommend_kill_switch = False

        if risk_input.kill_switch_active:
            reasons.append("KILL_SWITCH_ACTIVE")

        ips = risk_input.ips or InvestmentPolicySnapshot(
            user_max_notional=risk_input.user_max_notional
            if isinstance(risk_input.user_max_notional, Decimal)
            else Decimal("1000000")
        )
        ips_errors = ips.validate()
        if ips_errors:
            reasons.append("INVALID_IPS")
            reasons.extend(ips_errors)

        if risk_input.symbol not in ALLOWED_SYMBOLS or risk_input.symbol not in ips.allowed_assets:
            reasons.append("UNKNOWN_OR_DISALLOWED_SYMBOL")

        if risk_input.direction != "LONG":
            reasons.append("NON_LONG_DIRECTION")

        try:
            leverage = ensure_decimal(risk_input.leverage, "leverage")
            if leverage != Decimal("1.0"):
                reasons.append("LEVERAGE_FORBIDDEN")
        except TypeError:
            reasons.append("NON_DECIMAL_INPUT")

        # Validate required Decimal safety inputs
        try:
            equity = (
                ensure_decimal(risk_input.equity, "equity")
                if risk_input.equity is not None
                else None
            )
            atr_14 = (
                ensure_decimal(risk_input.atr_14, "atr_14")
                if risk_input.atr_14 is not None
                else None
            )
            entry_price = (
                ensure_decimal(risk_input.entry_price, "entry_price")
                if risk_input.entry_price is not None
                else None
            )
            daily_vol = (
                ensure_decimal(risk_input.daily_volume_24h, "daily_volume_24h")
                if risk_input.daily_volume_24h is not None
                else None
            )
            ob_depth = (
                ensure_decimal(risk_input.order_book_depth_0_5pct, "order_book_depth_0_5pct")
                if risk_input.order_book_depth_0_5pct is not None
                else None
            )
            spread_pct = (
                ensure_decimal(risk_input.spread_pct, "spread_pct")
                if risk_input.spread_pct is not None
                else None
            )
            risk_fraction = ensure_decimal(risk_input.risk_fraction, "risk_fraction")
            atr_multiplier = ensure_decimal(risk_input.atr_multiplier, "atr_multiplier")
            daily_loss_pct = ensure_decimal(risk_input.daily_loss_pct, "daily_loss_pct")
            weekly_loss_pct = ensure_decimal(risk_input.weekly_loss_pct, "weekly_loss_pct")
            current_dd_pct = ensure_decimal(risk_input.current_drawdown_pct, "current_drawdown_pct")
            existing_asset_exp = ensure_decimal(
                risk_input.existing_asset_exposure, "existing_asset_exposure"
            )
            existing_total_exp = ensure_decimal(
                risk_input.existing_total_exposure, "existing_total_exposure"
            )
            exposure_mult = ensure_decimal(risk_input.exposure_multiplier, "exposure_multiplier")
            step_size = ensure_decimal(risk_input.exchange_step_size, "exchange_step_size")
        except TypeError:
            reasons.append("NON_DECIMAL_INPUT")
            return self._reject(reasons, recommend_kill_switch=False)

        if equity is None or equity <= Decimal("0"):
            reasons.append("INVALID_EQUITY")

        if atr_14 is None or atr_14 <= Decimal("0"):
            reasons.append("MISSING_OR_INVALID_ATR")

        if entry_price is None or entry_price <= Decimal("0"):
            reasons.append("INVALID_ENTRY_PRICE")

        if risk_input.volatility_bars_count < MIN_VOLATILITY_BARS or atr_multiplier <= Decimal("0"):
            reasons.append("INSUFFICIENT_VOLATILITY_DATA")

        if ob_depth is None or ob_depth <= Decimal("0"):
            reasons.append("UNAVAILABLE_ORDER_BOOK_DEPTH")

        if daily_vol is None or daily_vol <= Decimal("0"):
            reasons.append("INSUFFICIENT_LIQUIDITY")

        if spread_pct is None or spread_pct < Decimal("0") or spread_pct > MAX_SPREAD_PCT:
            reasons.append("INSUFFICIENT_LIQUIDITY")

        # Market data freshness check (if market_data_timestamp is provided or explicitly checked)
        now = risk_input.evaluation_timestamp or datetime.now(UTC)
        if risk_input.market_data_timestamp is not None:
            age_seconds = Decimal(str((now - risk_input.market_data_timestamp).total_seconds()))
            if age_seconds > MAX_MARKET_DATA_AGE_SECONDS or age_seconds < Decimal("-1"):
                reasons.append("STALE_MARKET_DATA")

        # Hard cap checks (§10.2)
        if risk_fraction <= Decimal("0") or risk_fraction > MAX_RISK_PER_TRADE:
            reasons.append("RISK_PER_TRADE_EXCEEDED")

        if daily_loss_pct >= min(MAX_DAILY_LOSS, ips.max_daily_loss):
            reasons.append("DAILY_LOSS_LIMIT_EXCEEDED")

        if weekly_loss_pct >= min(MAX_WEEKLY_LOSS, ips.max_weekly_loss):
            reasons.append("WEEKLY_LOSS_LIMIT_EXCEEDED")

        if current_dd_pct >= KILL_SWITCH_DRAWDOWN:
            reasons.append("KILL_SWITCH_DRAWDOWN_EXCEEDED")
            recommend_kill_switch = True
        elif current_dd_pct >= min(HARD_DRAWDOWN, ips.max_drawdown_hard):
            reasons.append("HARD_DRAWDOWN_EXCEEDED")

        if reasons:
            return self._reject(reasons, recommend_kill_switch=recommend_kill_switch)

        assert equity is not None
        assert atr_14 is not None
        assert entry_price is not None
        assert daily_vol is not None
        assert ob_depth is not None

        portfolio_val = (
            ensure_decimal(risk_input.portfolio_value, "portfolio_value")
            if risk_input.portfolio_value is not None
            else equity
        )

        # Apply soft drawdown 50% exposure reduction if drawdown >= 8%
        effective_exp_mult = exposure_mult
        if current_dd_pct >= SOFT_DRAWDOWN:
            effective_exp_mult = min(effective_exp_mult, Decimal("0.50"))

        sizing = self.calculate_position_size(
            equity=equity,
            portfolio_value=portfolio_val,
            entry_price=entry_price,
            atr_14=atr_14,
            atr_multiplier=atr_multiplier,
            risk_fraction=min(risk_fraction, ips.max_risk_per_trade),
            fee_round_trip_pct=ensure_decimal(risk_input.fee_round_trip_pct, "fee_round_trip_pct"),
            slippage_pct=ensure_decimal(risk_input.slippage_pct, "slippage_pct"),
            max_asset_weight=min(MAX_ASSET_WEIGHT, ips.max_asset_weight),
            max_total_exposure=min(MAX_TOTAL_EXPOSURE, ips.max_total_exposure),
            min_cash_reserve=max(MIN_CASH_RESERVE, ips.min_cash_reserve),
            daily_volume_24h=daily_vol,
            order_book_depth_0_5pct=ob_depth,
            user_max_notional=min(
                ensure_decimal(risk_input.user_max_notional, "user_max_notional"),
                ips.user_max_notional,
            ),
            exchange_step_size=step_size,
            existing_asset_exposure=existing_asset_exp,
            existing_total_exposure=existing_total_exp,
            available_cash=risk_input.available_cash,
            exposure_multiplier=effective_exp_mult,
        )

        if sizing.asset_exposure_limit <= Decimal("0"):
            reasons.append("ASSET_WEIGHT_LIMIT_EXCEEDED")
        if sizing.portfolio_exposure_limit <= Decimal("0"):
            reasons.append("TOTAL_EXPOSURE_LIMIT_EXCEEDED")
        if sizing.cash_reserve_limit <= Decimal("0"):
            reasons.append("CASH_RESERVE_BREACHED")
        if sizing.final_quantity <= Decimal("0"):
            reasons.append("POSITION_SIZE_ROUNDS_TO_ZERO")

        if reasons:
            return self._reject(reasons, recommend_kill_switch=recommend_kill_switch)

        return RiskEvaluationDecision(
            decision=RiskDecisionStatus.APPROVE,
            reason_codes=[],
            sizing=sizing,
            recommend_kill_switch=False,
        )

    @staticmethod
    def _reject(
        reason_codes: list[str],
        *,
        recommend_kill_switch: bool = False,
    ) -> RiskEvaluationDecision:
        unique_reasons = list(dict.fromkeys(reason_codes))
        for code in unique_reasons:
            RISK_REJECTIONS_TOTAL.labels(reason_code=code).inc()
        return RiskEvaluationDecision(
            decision=RiskDecisionStatus.REJECT,
            reason_codes=unique_reasons,
            sizing=None,
            recommend_kill_switch=recommend_kill_switch,
        )
