"""Deterministic Signal Engine service for MVP-0 Phase F3 (§4 & §11)."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OutboxEventType, SignalApprovalStatus
from app.core.errors import InvalidRequestError
from app.db.models.signal import Signal
from app.db.models.strategy import Strategy
from app.db.repositories.signal_repository import SignalRepository
from app.services.approval_timeout import compute_effective_timeout
from app.services.mean_reversion_rule import MeanReversionRule
from app.services.outbox import OutboxService, record_audit_log
from app.services.risk_engine import ensure_decimal
from app.services.trend_following_rule import (
    CandleBar,
    SignalCandidate,
    TrendFollowingRule,
    ensure_utc_datetime,
    validate_explanation_json,
    validate_market_and_scores,
)


class SignalEngine:
    """Deterministic Spot-LONG Signal Engine for MVP-0 Phase F3 (§4)."""

    def __init__(
        self,
        *,
        trend_rule: TrendFollowingRule | None = None,
        mean_reversion_rule: MeanReversionRule | None = None,
        outbox_service: OutboxService | None = None,
    ) -> None:
        self._trend_rule = trend_rule or TrendFollowingRule()
        self._mean_reversion_rule = mean_reversion_rule or MeanReversionRule()
        self._outbox = outbox_service or OutboxService()

    def evaluate_trend_following(
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
        """Evaluate Trend Following rule on closed candles (§4.3)."""
        return self._trend_rule.evaluate(
            symbol=symbol,
            candles_4h=candles_4h,
            candles_1h=candles_1h,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )

    def evaluate_mean_reversion(
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
        """Evaluate Mean Reversion rule on closed candles (§4.4)."""
        return self._mean_reversion_rule.evaluate(
            symbol=symbol,
            candles_1h=candles_1h,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )

    async def ensure_strategy(
        self,
        session: AsyncSession,
        *,
        strategy_code: str,
        timeframe: str = "1H",
    ) -> Strategy:
        """Get or create an active Strategy record for the given strategy_code."""
        stmt = select(Strategy).where(Strategy.strategy_code == strategy_code)
        existing = await session.scalar(stmt)
        if existing is not None:
            return existing

        strategy = Strategy(
            id=uuid.uuid4(),
            strategy_code=strategy_code,
            name=strategy_code.replace("_", " ").title(),
            timeframe=timeframe,
            is_active=True,
            config_json={"rule": strategy_code, "timeframe": timeframe},
        )
        session.add(strategy)
        await session.flush()
        return strategy

    async def create_signal(
        self,
        session: AsyncSession,
        *,
        symbol: str,
        timeframe: str,
        reference_price: Decimal,
        entry_range_min: Decimal,
        entry_range_max: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Decimal | None,
        risk_reward_ratio: Decimal,
        data_quality_score: Decimal,
        confidence_score: Decimal,
        explanation_json: dict[str, Any],
        strategy_id: uuid.UUID | None = None,
        strategy_code: str = "TREND_FOLLOWING",
        direction: str = "LONG",
        market: str = "SPOT",
        leverage: Decimal | None = None,
        rule_version: str = "1.0.0",
        signal_id: str | None = None,
        ips_timeout_minutes: int | None = None,
        actor_role: str = "SYSTEM",
        now: datetime | None = None,
    ) -> Signal:
        """Validate all §4 constraints and persist a PENDING_APPROVAL Signal with Audit + Outbox."""
        current_time = ensure_utc_datetime(now or datetime.now(UTC), "now")
        validate_market_and_scores(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
        )
        validate_explanation_json(explanation_json)

        for field_name, val in (
            ("reference_price", reference_price),
            ("entry_range_min", entry_range_min),
            ("entry_range_max", entry_range_max),
            ("stop_loss_price", stop_loss_price),
            ("risk_reward_ratio", risk_reward_ratio),
        ):
            ensure_decimal(val, field_name)
        if take_profit_price is not None:
            ensure_decimal(take_profit_price, "take_profit_price")

        if reference_price <= Decimal("0") or stop_loss_price <= Decimal("0"):
            raise InvalidRequestError("reference_price and stop_loss_price must be positive")
        if stop_loss_price >= reference_price:
            raise InvalidRequestError("LONG signal stop_loss_price must be below reference_price")
        if entry_range_min <= Decimal("0") or entry_range_min > entry_range_max:
            raise InvalidRequestError("entry_range_min must be positive and <= entry_range_max")
        if risk_reward_ratio <= Decimal("0"):
            raise InvalidRequestError("risk_reward_ratio must be positive")

        resolved_strategy_id = strategy_id
        if resolved_strategy_id is None:
            strategy = await self.ensure_strategy(
                session,
                strategy_code=strategy_code,
                timeframe=timeframe,
            )
            resolved_strategy_id = strategy.id

        effective_timeout = compute_effective_timeout(
            timeframe=timeframe,
            ips_timeout_minutes=ips_timeout_minutes,
        )
        expires_at = current_time + effective_timeout
        resolved_signal_id = signal_id or f"SIG-{uuid.uuid4().hex[:12].upper()}"

        signal = Signal(
            id=uuid.uuid4(),
            signal_id=resolved_signal_id,
            strategy_id=resolved_strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            reference_price=reference_price,
            entry_range_min=entry_range_min,
            entry_range_max=entry_range_max,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            risk_reward_ratio=risk_reward_ratio,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            rule_version=rule_version,
            approval_status=SignalApprovalStatus.PENDING_APPROVAL.value,
            approval_expires_at=expires_at,
            explanation_json=dict(explanation_json),
            created_at=current_time,
            updated_at=current_time,
            version=1,
        )

        repo = SignalRepository(session)
        await repo.add(signal)

        detail_payload = {
            "signal_id": signal.signal_id,
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "direction": signal.direction,
            "reference_price": str(signal.reference_price),
            "stop_loss_price": str(signal.stop_loss_price),
            "take_profit_price": (
                str(signal.take_profit_price) if signal.take_profit_price is not None else None
            ),
            "data_quality_score": str(signal.data_quality_score),
            "confidence_score": str(signal.confidence_score),
            "rule_version": signal.rule_version,
            "approval_status": signal.approval_status,
            "approval_expires_at": signal.approval_expires_at.isoformat(),
        }

        await record_audit_log(
            session,
            actor_role=actor_role,
            action=OutboxEventType.SIGNAL_CREATED.value,
            target_type="SIGNAL",
            target_id=signal.id,
            before_json=None,
            after_json={"approval_status": signal.approval_status, "version": signal.version},
            reason_code=strategy_code,
            detail_json=detail_payload,
        )

        await self._outbox.enqueue_event(
            session,
            event_type=OutboxEventType.SIGNAL_CREATED.value,
            aggregate_type="SIGNAL",
            aggregate_id=signal.id,
            payload=detail_payload,
        )
        return signal

    async def persist_candidate(
        self,
        session: AsyncSession,
        candidate: SignalCandidate,
        *,
        strategy_id: uuid.UUID | None = None,
        signal_id: str | None = None,
        ips_timeout_minutes: int | None = None,
        now: datetime | None = None,
    ) -> Signal:
        """Persist a validated SignalCandidate in PostgreSQL with Audit and Outbox records."""
        return await self.create_signal(
            session,
            symbol=candidate.symbol,
            timeframe=candidate.timeframe,
            reference_price=candidate.reference_price,
            entry_range_min=candidate.entry_range_min,
            entry_range_max=candidate.entry_range_max,
            stop_loss_price=candidate.stop_loss_price,
            take_profit_price=candidate.take_profit_price,
            risk_reward_ratio=candidate.risk_reward_ratio,
            data_quality_score=candidate.data_quality_score,
            confidence_score=candidate.confidence_score,
            explanation_json=candidate.explanation_json,
            strategy_id=strategy_id,
            strategy_code=candidate.strategy_code,
            direction=candidate.direction,
            rule_version=candidate.rule_version,
            signal_id=signal_id,
            ips_timeout_minutes=ips_timeout_minutes,
            now=now,
        )

    async def generate_trend_following_signal(
        self,
        session: AsyncSession,
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
        ips_timeout_minutes: int | None = None,
        evaluation_time: datetime | None = None,
        reject_open_candles: bool = False,
        now: datetime | None = None,
    ) -> Signal | None:
        """Evaluate Trend Following rule and persist signal if all conditions hold."""
        candidate = self.evaluate_trend_following(
            symbol=symbol,
            candles_4h=candles_4h,
            candles_1h=candles_1h,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )
        if candidate is None:
            return None
        return await self.persist_candidate(
            session,
            candidate,
            ips_timeout_minutes=ips_timeout_minutes,
            now=now or evaluation_time,
        )

    async def generate_mean_reversion_signal(
        self,
        session: AsyncSession,
        *,
        symbol: str,
        candles_1h: Sequence[CandleBar],
        data_quality_score: Decimal = Decimal("0.95"),
        confidence_score: Decimal = Decimal("0.75"),
        timeframe: str = "1H",
        direction: str = "LONG",
        market: str = "SPOT",
        leverage: Decimal | None = None,
        ips_timeout_minutes: int | None = None,
        evaluation_time: datetime | None = None,
        reject_open_candles: bool = False,
        now: datetime | None = None,
    ) -> Signal | None:
        """Evaluate Mean Reversion rule and persist signal if all conditions hold."""
        candidate = self.evaluate_mean_reversion(
            symbol=symbol,
            candles_1h=candles_1h,
            data_quality_score=data_quality_score,
            confidence_score=confidence_score,
            timeframe=timeframe,
            direction=direction,
            market=market,
            leverage=leverage,
            evaluation_time=evaluation_time,
            reject_open_candles=reject_open_candles,
        )
        if candidate is None:
            return None
        return await self.persist_candidate(
            session,
            candidate,
            ips_timeout_minutes=ips_timeout_minutes,
            now=now or evaluation_time,
        )
