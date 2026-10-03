"""Unit and integration tests for MVP-0 Risk Engine and Position Sizing (§10 & §21.3)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.enums import RiskDecisionStatus
from app.services.risk_engine import (
    HARD_DRAWDOWN,
    KILL_SWITCH_DRAWDOWN,
    MAX_ASSET_WEIGHT,
    MAX_DAILY_LOSS,
    MAX_RISK_PER_TRADE,
    MAX_TOTAL_EXPOSURE,
    MAX_WEEKLY_LOSS,
    MIN_CASH_RESERVE,
    InvestmentPolicySnapshot,
    RiskEngine,
    RiskEvaluationInput,
    floor_to_step,
)


def test_max_risk_per_trade_is_0_5_percent() -> None:
    """Verify hard cap MAX_RISK_PER_TRADE is 0.50% (0.005) and higher risk_fraction is rejected."""
    assert Decimal("0.005") == MAX_RISK_PER_TRADE
    assert Decimal("0.02") == MAX_DAILY_LOSS
    assert Decimal("0.05") == MAX_WEEKLY_LOSS
    assert Decimal("0.15") == MAX_ASSET_WEIGHT
    assert Decimal("0.70") == MAX_TOTAL_EXPOSURE
    assert Decimal("0.15") == MIN_CASH_RESERVE
    assert Decimal("0.12") == HARD_DRAWDOWN
    assert Decimal("0.15") == KILL_SWITCH_DRAWDOWN

    engine = RiskEngine()
    decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            risk_fraction=Decimal("0.006"),  # 0.6% > 0.5% hard cap
        )
    )
    assert decision.decision == RiskDecisionStatus.REJECT
    assert "RISK_PER_TRADE_EXCEEDED" in decision.reason_codes


def test_risk_engine_rejects_missing_atr() -> None:
    """Verify Risk Engine fails closed when ATR is missing, zero, or negative (§10.4)."""
    engine = RiskEngine()
    for invalid_atr in (None, Decimal("0"), Decimal("-10")):
        decision = engine.evaluate(
            RiskEvaluationInput(
                symbol="BTC/USDT",
                direction="LONG",
                entry_price=Decimal("60000"),
                atr_14=invalid_atr,
                equity=Decimal("10000"),
            )
        )
        assert decision.decision == RiskDecisionStatus.REJECT
        assert "MISSING_OR_INVALID_ATR" in decision.reason_codes


def test_risk_engine_rejects_stale_data() -> None:
    """Verify Risk Engine rejects stale market data (> 5 seconds old) (§10.4)."""
    engine = RiskEngine()
    now = datetime.now(UTC)
    stale_ts = now - timedelta(seconds=6)
    decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            market_data_timestamp=stale_ts,
            evaluation_timestamp=now,
        )
    )
    assert decision.decision == RiskDecisionStatus.REJECT
    assert "STALE_MARKET_DATA" in decision.reason_codes


def test_risk_engine_rejects_unknown_symbol() -> None:
    """Verify Risk Engine rejects any symbol outside BTC/USDT, ETH/USDT, BNB/USDT (§10.1)."""
    engine = RiskEngine()
    decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="DOGE/USDT",
            direction="LONG",
            entry_price=Decimal("0.15"),
            atr_14=Decimal("0.01"),
            equity=Decimal("10000"),
        )
    )
    assert decision.decision == RiskDecisionStatus.REJECT
    assert "UNKNOWN_OR_DISALLOWED_SYMBOL" in decision.reason_codes


def test_risk_engine_rejects_short_direction() -> None:
    """Verify Risk Engine rejects SHORT direction and leverage != 1 (§10.1)."""
    engine = RiskEngine()
    decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="SHORT",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
        )
    )
    assert decision.decision == RiskDecisionStatus.REJECT
    assert "NON_LONG_DIRECTION" in decision.reason_codes

    leveraged = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            leverage=Decimal("2.0"),
        )
    )
    assert leveraged.decision == RiskDecisionStatus.REJECT
    assert "LEVERAGE_FORBIDDEN" in leveraged.reason_codes


def test_risk_engine_rejects_when_kill_switch_active() -> None:
    """Verify Risk Engine fails closed when Kill Switch is active (§10.4)."""
    engine = RiskEngine()
    decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="ETH/USDT",
            direction="LONG",
            entry_price=Decimal("3000"),
            atr_14=Decimal("50"),
            equity=Decimal("10000"),
            kill_switch_active=True,
        )
    )
    assert decision.decision == RiskDecisionStatus.REJECT
    assert "KILL_SWITCH_ACTIVE" in decision.reason_codes


def test_position_sizing_uses_decimal() -> None:
    """Verify Position Sizing uses Decimal for every calculation and rejects float inputs."""
    engine = RiskEngine()
    decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000.00"),
            atr_14=Decimal("600.00"),
            equity=Decimal("20000.00"),
            portfolio_value=Decimal("20000.00"),
        )
    )
    assert decision.decision == RiskDecisionStatus.APPROVE
    assert decision.sizing is not None
    assert isinstance(decision.sizing.risk_amount, Decimal)
    assert isinstance(decision.sizing.stop_loss_distance, Decimal)
    assert isinstance(decision.sizing.round_trip_cost_per_unit, Decimal)
    assert isinstance(decision.sizing.effective_loss_per_unit, Decimal)
    assert isinstance(decision.sizing.quantity_by_risk, Decimal)
    assert isinstance(decision.sizing.notional_by_risk, Decimal)
    assert isinstance(decision.sizing.final_notional, Decimal)
    assert isinstance(decision.sizing.final_quantity, Decimal)

    # Passing float must be rejected
    with pytest.raises(TypeError, match="Decimal"):
        engine.calculate_position_size(
            equity=10000.0,  # type: ignore[arg-type]
            portfolio_value=Decimal("10000"),
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
        )


def test_position_sizing_respects_hard_caps() -> None:
    """Verify final_notional respects 15% asset cap, 70% portfolio cap, 1% volume, and user cap."""
    engine = RiskEngine()
    # Equity = 10,000 => 15% max asset weight = 1,500 USDT
    # Small ATR would give large notional_by_risk, so 1,500 USDT asset cap must bind
    sizing = engine.calculate_position_size(
        equity=Decimal("10000"),
        portfolio_value=Decimal("10000"),
        entry_price=Decimal("50000"),
        atr_14=Decimal("50"),
        atr_multiplier=Decimal("1.5"),
        risk_fraction=Decimal("0.005"),
        user_max_notional=Decimal("5000"),
        exchange_step_size=Decimal("0.00001"),
    )
    assert sizing.notional_by_risk > Decimal("1500")
    assert sizing.asset_exposure_limit == Decimal("1500.00")
    assert sizing.final_notional == Decimal("1500.00")

    # User max notional smaller than asset cap (e.g. 800 USDT) must bind
    sizing_user_cap = engine.calculate_position_size(
        equity=Decimal("10000"),
        portfolio_value=Decimal("10000"),
        entry_price=Decimal("50000"),
        atr_14=Decimal("50"),
        user_max_notional=Decimal("800"),
        exchange_step_size=Decimal("0.00001"),
    )
    assert sizing_user_cap.final_notional == Decimal("800")

    # 24h volume cap (1% of 50,000 = 500 USDT) must bind
    sizing_vol_cap = engine.calculate_position_size(
        equity=Decimal("10000"),
        portfolio_value=Decimal("10000"),
        entry_price=Decimal("50000"),
        atr_14=Decimal("50"),
        daily_volume_24h=Decimal("50000"),
        user_max_notional=Decimal("5000"),
        exchange_step_size=Decimal("0.00001"),
    )
    assert sizing_vol_cap.final_notional == Decimal("500.00")


def test_position_sizing_rounds_down_to_step_size() -> None:
    """Verify final_quantity floors down to exchange_step_size and never rounds up (§10.3)."""
    step = Decimal("0.00001")
    qty = floor_to_step(Decimal("0.123459999"), step)
    assert qty == Decimal("0.12345")

    engine = RiskEngine()
    sizing = engine.calculate_position_size(
        equity=Decimal("10000"),
        portfolio_value=Decimal("10000"),
        entry_price=Decimal("61234.56"),
        atr_14=Decimal("450"),
        exchange_step_size=Decimal("0.0001"),
    )
    assert sizing.final_quantity * Decimal("61234.56") <= sizing.final_notional
    assert sizing.final_quantity == sizing.final_quantity.quantize(Decimal("0.0001"))


def test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01() -> None:
    """Verify max risk per trade ceiling is 0.005 (0.5%) and 0.01 (1.0%) is rejected (F2 Req #4)."""
    from app.services.risk_engine import MAX_RISK_PER_TRADE

    assert Decimal("0.005") == MAX_RISK_PER_TRADE
    engine = RiskEngine()

    # 0.005 (0.5%) is accepted
    ok_ips = InvestmentPolicySnapshot(max_risk_per_trade=Decimal("0.005"))
    assert ok_ips.validate() == []

    # 0.01 (1.0%) in IPS is rejected
    bad_ips = InvestmentPolicySnapshot(max_risk_per_trade=Decimal("0.01"))
    assert "IPS_MAX_RISK_PER_TRADE_EXCEEDS_HARD_CAP" in bad_ips.validate()

    # 0.01 (1.0%) in RiskEvaluationInput is rejected by evaluate()
    bad_eval = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            risk_fraction=Decimal("0.01"),
        )
    )
    assert bad_eval.decision == RiskDecisionStatus.REJECT
    assert "RISK_PER_TRADE_EXCEEDED" in bad_eval.reason_codes

    # 0.01 (1.0%) in calculate_position_size() raises ValueError
    with pytest.raises(ValueError, match="0.005"):
        engine.calculate_position_size(
            equity=Decimal("10000"),
            portfolio_value=Decimal("10000"),
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            risk_fraction=Decimal("0.01"),
        )


def test_risk_engine_fail_closed_edge_cases() -> None:
    """Verify additional §10.4 fail-closed conditions (drawdown, loss caps, IPS, liquidity)."""
    engine = RiskEngine()
    # Hard drawdown & Kill Switch drawdown
    dd_decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            current_drawdown_pct=Decimal("0.15"),
        )
    )
    assert dd_decision.decision == RiskDecisionStatus.REJECT
    assert dd_decision.recommend_kill_switch is True
    assert "KILL_SWITCH_DRAWDOWN_EXCEEDED" in dd_decision.reason_codes

    # Soft drawdown (9%) reduces exposure by 50%
    soft_dd = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("100"),
            equity=Decimal("10000"),
            current_drawdown_pct=Decimal("0.09"),
        )
    )
    assert soft_dd.decision == RiskDecisionStatus.APPROVE
    assert soft_dd.sizing is not None
    assert soft_dd.sizing.final_notional == Decimal("750.0000")

    # Invalid IPS rejected
    bad_ips = InvestmentPolicySnapshot(
        initial_capital=Decimal("100"),
        max_risk_per_trade=Decimal("0.02"),
        max_daily_loss=Decimal("0.05"),
        max_weekly_loss=Decimal("0.10"),
        max_drawdown_hard=Decimal("0.20"),
        max_asset_weight=Decimal("0.50"),
        max_total_exposure=Decimal("0.90"),
        min_cash_reserve=Decimal("0.05"),
        user_max_notional=Decimal("0"),
        allowed_assets=("SOL/USDT",),
        approval_timeout_minutes=1,
        default_action_on_timeout="INVALID",
    )
    ips_errors = bad_ips.validate()
    assert len(ips_errors) >= 10
    ips_decision = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            ips=bad_ips,
        )
    )
    assert ips_decision.decision == RiskDecisionStatus.REJECT
    assert "INVALID_IPS" in ips_decision.reason_codes

    # Non-decimal IPS
    non_dec_ips = InvestmentPolicySnapshot(initial_capital=1000.0)  # type: ignore[arg-type]
    assert "IPS_NON_DECIMAL_VALUE" in non_dec_ips.validate()

    # Invalid equity, entry_price, volatility bars, order book depth, liquidity, losses
    multi_bad = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("0"),
            atr_14=Decimal("500"),
            equity=Decimal("-100"),
            volatility_bars_count=5,
            order_book_depth_0_5pct=Decimal("0"),
            daily_volume_24h=Decimal("0"),
            spread_pct=Decimal("0.005"),
            daily_loss_pct=Decimal("0.03"),
            weekly_loss_pct=Decimal("0.06"),
            current_drawdown_pct=Decimal("0.13"),
        )
    )
    assert multi_bad.decision == RiskDecisionStatus.REJECT
    for expected_code in (
        "INVALID_EQUITY",
        "INVALID_ENTRY_PRICE",
        "INSUFFICIENT_VOLATILITY_DATA",
        "UNAVAILABLE_ORDER_BOOK_DEPTH",
        "INSUFFICIENT_LIQUIDITY",
        "DAILY_LOSS_LIMIT_EXCEEDED",
        "WEEKLY_LOSS_LIMIT_EXCEEDED",
        "HARD_DRAWDOWN_EXCEEDED",
    ):
        assert expected_code in multi_bad.reason_codes

    # Exhausted asset exposure, total exposure, and cash reserve
    cap_breach = engine.evaluate(
        RiskEvaluationInput(
            symbol="BTC/USDT",
            direction="LONG",
            entry_price=Decimal("60000"),
            atr_14=Decimal("500"),
            equity=Decimal("10000"),
            portfolio_value=Decimal("10000"),
            existing_asset_exposure=Decimal("1500"),
            existing_total_exposure=Decimal("7000"),
            available_cash=Decimal("1000"),
        )
    )
    assert cap_breach.decision == RiskDecisionStatus.REJECT
    assert "ASSET_WEIGHT_LIMIT_EXCEEDED" in cap_breach.reason_codes
    assert "TOTAL_EXPOSURE_LIMIT_EXCEEDED" in cap_breach.reason_codes
    assert "CASH_RESERVE_BREACHED" in cap_breach.reason_codes

    # floor_to_step edge cases
    assert floor_to_step(Decimal("0"), Decimal("0.001")) == Decimal("0")
    with pytest.raises(ValueError, match="positive"):
        floor_to_step(Decimal("1"), Decimal("0"))
