"""TestSignalFactory for F2 E2E testing without implementing a real Signal Engine (F2 Req #5)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SignalApprovalStatus
from app.db.models.exchange_account import ExchangeAccount
from app.db.models.signal import Signal
from app.db.models.strategy import Strategy
from app.services.approval_timeout import compute_effective_timeout
from app.services.risk_engine import (
    MAX_RISK_PER_TRADE,
    InvestmentPolicySnapshot,
    RiskEvaluationInput,
)


@dataclass(frozen=True)
class SyntheticSignalBundle:
    """Bundle returned by TestSignalFactory containing persisted Signal and RiskEvaluationInput."""

    signal: Signal
    strategy: Strategy
    exchange_account: ExchangeAccount
    risk_input: RiskEvaluationInput


class TestSignalFactory:
    """Test-only factory generating deterministic synthetic signals for F2 E2E tests."""

    @staticmethod
    async def ensure_strategy_and_account(
        session: AsyncSession,
        *,
        strategy_name: str = "f2-e2e-test-strategy",
        account_name: str = "f2-e2e-paper-account",
    ) -> tuple[Strategy, ExchangeAccount]:
        """Ensure a Paper-mode Strategy and ExchangeAccount exist in PostgreSQL."""
        strategy = await session.scalar(select(Strategy).where(Strategy.name == strategy_name))
        if strategy is None:
            strategy = Strategy(
                id=uuid.uuid4(),
                name=strategy_name,
                version="1.0.0",
                description="TestSignalFactory synthetic strategy (Paper-only)",
                is_active=True,
                config_json={"timeframe": "1H", "mode": "PAPER"},
            )
            session.add(strategy)
            await session.flush()

        account = await session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == account_name)
        )
        if account is None:
            account = ExchangeAccount(
                id=uuid.uuid4(),
                name=account_name,
                exchange_name="paper",
                mode="PAPER",
                is_active=True,
            )
            session.add(account)
            await session.flush()

        return strategy, account

    @classmethod
    async def create_signal(
        cls,
        session: AsyncSession,
        *,
        symbol: str = "BTC/USDT",
        direction: str = "LONG",
        timeframe: str = "1H",
        entry_price: Decimal = Decimal("60000.00"),
        atr_14: Decimal = Decimal("600.00"),
        atr_multiplier: Decimal = Decimal("2.0"),
        equity: Decimal = Decimal("10000.00"),
        risk_fraction: Decimal = MAX_RISK_PER_TRADE,
        confidence: Decimal = Decimal("0.8500"),
        ips: InvestmentPolicySnapshot | None = None,
        now: datetime | None = None,
    ) -> SyntheticSignalBundle:
        """Create and persist a synthetic Signal in PostgreSQL with matching RiskEvaluationInput."""
        current_time = now or datetime.now(UTC)
        strategy, account = await cls.ensure_strategy_and_account(session)
        effective_ips = ips or InvestmentPolicySnapshot()

        timeout_delta = compute_effective_timeout(
            timeframe,
            effective_ips.approval_timeout_minutes,
        )
        stop_loss_price = max(Decimal("1"), entry_price - (atr_14 * atr_multiplier))
        take_profit_price = entry_price + (atr_14 * atr_multiplier * Decimal("2"))

        signal = Signal(
            id=uuid.uuid4(),
            signal_id=f"SIG-E2E-{uuid.uuid4().hex[:12].upper()}",
            strategy_id=strategy.id,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            reference_price=entry_price,
            entry_range_min=entry_price * Decimal("0.999"),
            entry_range_max=entry_price * Decimal("1.001"),
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            risk_reward_ratio=Decimal("2.000000"),
            data_quality_score=Decimal("0.9900"),
            confidence_score=confidence,
            rule_version="v1.0.0",
            approval_status=SignalApprovalStatus.PENDING_APPROVAL.value,
            approval_expires_at=current_time + timeout_delta,
            explanation_json={
                "factory": "TestSignalFactory",
                "symbol": symbol,
                "timeframe": timeframe,
                "risk_fraction": str(risk_fraction),
            },
            created_at=current_time,
            updated_at=current_time,
            version=1,
        )
        session.add(signal)
        await session.flush()

        risk_input = RiskEvaluationInput(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            atr_14=atr_14,
            atr_multiplier=atr_multiplier,
            equity=equity,
            portfolio_value=equity,
            available_cash=equity,
            risk_fraction=risk_fraction,
            market_data_timestamp=current_time,
            evaluation_timestamp=current_time,
            ips=effective_ips,
        )
        return SyntheticSignalBundle(
            signal=signal,
            strategy=strategy,
            exchange_account=account,
            risk_input=risk_input,
        )
