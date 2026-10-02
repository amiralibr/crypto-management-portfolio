"""Approval Timeout and Price Drift service for MVP-0 (§11 & Master §13.6)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import OutboxEventType, SignalApprovalStatus
from app.core.errors import InvalidRequestError, NotFoundError
from app.core.metrics import APPROVAL_TIMEOUTS_TOTAL, PRICE_DRIFT_EXPIRIES_TOTAL
from app.db.models.signal import Signal
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.outbox import OutboxService, record_audit_log
from app.services.risk_engine import ensure_decimal

DYNAMIC_TIMEOUT_BY_TIMEFRAME: dict[str, timedelta] = {
    "1H": timedelta(minutes=5),
    "4H": timedelta(minutes=30),
    "1D": timedelta(hours=4),
}

MIN_IPS_TIMEOUT_MINUTES: int = 3
MAX_IPS_TIMEOUT_MINUTES: int = 240
DEFAULT_PRICE_DRIFT_THRESHOLD: Decimal = Decimal("0.002")


def validate_ips_timeout_minutes(ips_timeout_minutes: int | None) -> timedelta | None:
    """Validate optional IPS approval_timeout_minutes in [3, 240] (§11.2)."""
    if ips_timeout_minutes is None:
        return None
    if (
        isinstance(ips_timeout_minutes, bool)
        or not isinstance(ips_timeout_minutes, int)
        or ips_timeout_minutes < MIN_IPS_TIMEOUT_MINUTES
        or ips_timeout_minutes > MAX_IPS_TIMEOUT_MINUTES
    ):
        raise InvalidRequestError(
            f"approval_timeout_minutes must be between {MIN_IPS_TIMEOUT_MINUTES} "
            f"and {MAX_IPS_TIMEOUT_MINUTES} minutes"
        )
    return timedelta(minutes=ips_timeout_minutes)


def compute_effective_timeout(
    timeframe: str,
    ips_timeout_minutes: int | None = None,
) -> timedelta:
    """Compute effective approval timeout: min(dynamic_timeout, ips_timeout) (§11.1 & §11.2)."""
    if timeframe not in DYNAMIC_TIMEOUT_BY_TIMEFRAME:
        raise InvalidRequestError(f"Unsupported signal timeframe: {timeframe}")
    dynamic_timeout = DYNAMIC_TIMEOUT_BY_TIMEFRAME[timeframe]
    ips_delta = validate_ips_timeout_minutes(ips_timeout_minutes)
    if ips_delta is None:
        return dynamic_timeout
    return min(dynamic_timeout, ips_delta)


def calculate_price_drift(
    *,
    current_price: Decimal,
    reference_price: Decimal,
) -> Decimal:
    """Calculate absolute relative price drift using Decimal only (§11.3 & §11.4)."""
    ensure_decimal(current_price, "current_price")
    ensure_decimal(reference_price, "reference_price")
    if current_price <= Decimal("0") or reference_price <= Decimal("0"):
        raise InvalidRequestError("current_price and reference_price must be positive Decimals")
    return abs(current_price - reference_price) / reference_price


class ApprovalTimeoutService:
    """Service evaluating dynamic approval timeouts and 0.2% price drift expiry (§11)."""

    def __init__(
        self,
        settings: Settings | None = None,
        exchange_adapter: ExchangeAdapter | None = None,
        outbox_service: OutboxService | None = None,
        notifier: NotificationAdapter | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._exchange = exchange_adapter
        self._outbox = outbox_service or OutboxService(settings=self._settings, notifier=notifier)
        self._notifier = notifier

    @property
    def price_drift_threshold(self) -> Decimal:
        """Return configured PRICE_DRIFT_EXPIRY_THRESHOLD (default 0.002 = 0.2%)."""
        return self._settings.PRICE_DRIFT_EXPIRY_THRESHOLD

    async def check_signal_timeout(
        self,
        session: AsyncSession,
        *,
        signal_id: uuid.UUID,
        current_price: Decimal | None = None,
        ips_timeout_minutes: int | None = None,
        now: datetime | None = None,
    ) -> Signal:
        """Atomically evaluate time-based expiry and price-drift expiry on a signal."""
        current_time = now or datetime.now(UTC)
        stmt = select(Signal).where(Signal.id == signal_id).with_for_update()
        signal = await session.scalar(stmt)
        if signal is None:
            raise NotFoundError(f"Signal {signal_id} not found")

        if signal.approval_status != SignalApprovalStatus.PENDING_APPROVAL.value:
            return signal

        effective_timeout = compute_effective_timeout(
            timeframe=signal.timeframe,
            ips_timeout_minutes=ips_timeout_minutes,
        )
        elapsed = current_time - signal.created_at
        effective_expires_at = min(
            signal.approval_expires_at,
            signal.created_at + effective_timeout,
        )

        # 1. Check time-based timeout
        if current_time >= effective_expires_at or elapsed > effective_timeout:
            before_status = signal.approval_status
            signal.approval_status = SignalApprovalStatus.EXPIRED.value
            signal.version += 1
            signal.updated_at = current_time
            await session.flush()

            APPROVAL_TIMEOUTS_TOTAL.labels(timeframe=signal.timeframe).inc()

            detail = {
                "signal_id": signal.signal_id,
                "timeframe": signal.timeframe,
                "elapsed_seconds": str(Decimal(str(elapsed.total_seconds()))),
                "effective_timeout_seconds": str(Decimal(str(effective_timeout.total_seconds()))),
            }
            await record_audit_log(
                session,
                actor_role="SYSTEM",
                action="SIGNAL_EXPIRED",
                target_type="SIGNAL",
                target_id=signal.id,
                before_json={"approval_status": before_status},
                after_json={"approval_status": signal.approval_status},
                reason_code="APPROVAL_TIMEOUT",
                detail_json=detail,
            )
            await self._outbox.enqueue_event(
                session,
                event_type=OutboxEventType.SIGNAL_EXPIRED.value,
                aggregate_type="SIGNAL",
                aggregate_id=signal.id,
                payload=detail,
            )
            if self._notifier is not None:
                await self._notifier.send_alert(
                    severity="INFO",
                    title="Signal Expired",
                    message=f"Signal {signal.signal_id} ({signal.symbol}) expired on timeout.",
                    metadata=detail,
                )
            return signal

        # 2. Check price-drift expiry (even before timeout)
        resolved_price = current_price
        if resolved_price is None and self._exchange is not None:
            ticker = await self._exchange.get_ticker(signal.symbol)
            resolved_price = ticker.price

        if resolved_price is not None:
            drift = calculate_price_drift(
                current_price=resolved_price,
                reference_price=Decimal(str(signal.reference_price)),
            )
            threshold = self.price_drift_threshold
            if drift > threshold:
                before_status = signal.approval_status
                signal.approval_status = SignalApprovalStatus.PRICE_DRIFT_EXPIRED.value
                signal.version += 1
                signal.updated_at = current_time
                await session.flush()

                PRICE_DRIFT_EXPIRIES_TOTAL.labels(symbol=signal.symbol).inc()

                drift_detail = {
                    "signal_id": signal.signal_id,
                    "symbol": signal.symbol,
                    "reference_price": str(signal.reference_price),
                    "current_price": str(resolved_price),
                    "price_drift": str(drift),
                    "threshold": str(threshold),
                }
                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="SIGNAL_PRICE_DRIFT_EXPIRED",
                    target_type="SIGNAL",
                    target_id=signal.id,
                    before_json={"approval_status": before_status},
                    after_json={"approval_status": signal.approval_status},
                    reason_code="PRICE_DRIFT_EXCEEDED",
                    detail_json=drift_detail,
                )
                await self._outbox.enqueue_event(
                    session,
                    event_type=OutboxEventType.SIGNAL_PRICE_DRIFT_EXPIRED.value,
                    aggregate_type="SIGNAL",
                    aggregate_id=signal.id,
                    payload=drift_detail,
                )
                if self._notifier is not None:
                    await self._notifier.send_alert(
                        severity="WARNING",
                        title="Signal Price Drift Expired",
                        message=(
                            f"Signal {signal.signal_id} ({signal.symbol}) expired due to "
                            f"price drift {drift:.4%} > {threshold:.4%}."
                        ),
                        metadata=drift_detail,
                    )
                return signal

        return signal

    async def check_pending_signals(
        self,
        session: AsyncSession,
        *,
        ips_timeout_minutes: int | None = None,
        now: datetime | None = None,
    ) -> list[Signal]:
        """Sweep all PENDING_APPROVAL signals and evaluate timeout and price drift."""
        stmt = (
            select(Signal.id)
            .where(Signal.approval_status == SignalApprovalStatus.PENDING_APPROVAL.value)
            .order_by(Signal.created_at.asc())
        )
        pending_ids = list((await session.scalars(stmt)).all())
        processed: list[Signal] = []
        for sig_id in pending_ids:
            sig = await self.check_signal_timeout(
                session,
                signal_id=sig_id,
                ips_timeout_minutes=ips_timeout_minutes,
                now=now,
            )
            processed.append(sig)
        return processed
