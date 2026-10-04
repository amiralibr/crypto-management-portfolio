"""Read-only Decision Log service for MVP-0 Phase F3 (§10 & §16.4)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.audit_log import AuditLog
from app.db.models.order import Order
from app.db.models.signal import Signal
from app.db.repositories.signal_repository import SignalRepository

SENSITIVE_KEY_SUBSTRINGS: tuple[str, ...] = (
    "secret",
    "password",
    "api_key",
    "apikey",
    "token",
    "authorization",
    "private_key",
    "credential",
)


def _format_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def sanitize_decision_payload(
    value: object,
    *,
    secret_literals: Sequence[str] = (),
) -> object:
    """Recursively redact any secret keys or secret literal strings from decision log data."""
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if any(sub in key_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
                cleaned[str(k)] = "[REDACTED]"
            else:
                cleaned[str(k)] = sanitize_decision_payload(v, secret_literals=secret_literals)
        return cleaned
    if isinstance(value, list):
        return [sanitize_decision_payload(item, secret_literals=secret_literals) for item in value]
    if isinstance(value, tuple):
        return [sanitize_decision_payload(item, secret_literals=secret_literals) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secret_literals:
            if secret and secret in redacted:
                redacted = redacted.replace(secret, "[REDACTED]")
        if "Bearer " in redacted:
            redacted = "[REDACTED]"
        return redacted
    return value


@dataclass(frozen=True)
class DecisionAuditEventRecord:
    """Immutable read-only view of an audit event in a Signal's decision timeline."""

    audit_id: str
    action: str
    actor_role: str
    target_type: str
    target_id: str | None
    reason_code: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    detail_json: dict[str, Any] | None
    created_at: str


@dataclass(frozen=True)
class DecisionOrderSummaryRecord:
    """Immutable read-only view of an Order linked to a Signal decision."""

    order_id: str
    client_order_id: str
    status: str
    state_machine_state: str
    risk_decision: str
    risk_reason_codes: list[str]
    quantity: str
    limit_price: str | None
    created_at: str


@dataclass(frozen=True)
class DecisionLogEntryRecord:
    """Immutable read-only Decision Log entry combining Signal, Audit trail, and Order."""

    id: str
    signal_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    direction: str
    reference_price: str
    stop_loss_price: str
    take_profit_price: str | None
    risk_reward_ratio: str
    data_quality_score: str
    confidence_score: str
    rule_version: str
    approval_status: str
    approval_expires_at: str
    explanation_json: dict[str, Any]
    events: tuple[DecisionAuditEventRecord, ...]
    orders: tuple[DecisionOrderSummaryRecord, ...]
    created_at: str
    updated_at: str


class DecisionLogService:
    """Read-only Decision Log service sourcing from `signals`, `audit_logs`, and `orders` (§10)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _collect_secret_literals(self) -> list[str]:
        literals = [
            self._settings.MVP0_API_KEY.get_secret_value(),
            self._settings.MVP0_ADMIN_API_KEY.get_secret_value(),
            self._settings.database_url,
            self._settings.redis_url,
        ]
        if self._settings.POSTGRES_PASSWORD:
            literals.append(self._settings.POSTGRES_PASSWORD)
        if self._settings.REDIS_PASSWORD:
            literals.append(self._settings.REDIS_PASSWORD)
        return [s for s in literals if s]

    async def _build_entry(
        self,
        session: AsyncSession,
        signal: Signal,
        secret_literals: Sequence[str],
    ) -> DecisionLogEntryRecord:
        orders_stmt = (
            select(Order)
            .where(Order.signal_id == signal.id)
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        orders = list((await session.scalars(orders_stmt)).all())
        target_ids: list[uuid.UUID] = [signal.id, *[o.id for o in orders]]

        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.target_id.in_(target_ids))
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )
        audit_logs = list((await session.scalars(audit_stmt)).all())

        events: list[DecisionAuditEventRecord] = []
        for log in audit_logs:
            before_clean = sanitize_decision_payload(
                log.before_json,
                secret_literals=secret_literals,
            )
            after_clean = sanitize_decision_payload(
                log.after_json,
                secret_literals=secret_literals,
            )
            detail_clean = sanitize_decision_payload(
                log.detail_json,
                secret_literals=secret_literals,
            )
            events.append(
                DecisionAuditEventRecord(
                    audit_id=str(log.id),
                    action=log.action,
                    actor_role=log.actor_role,
                    target_type=log.target_type,
                    target_id=str(log.target_id) if log.target_id is not None else None,
                    reason_code=log.reason_code,
                    before_json=before_clean if isinstance(before_clean, dict) else None,
                    after_json=after_clean if isinstance(after_clean, dict) else None,
                    detail_json=detail_clean if isinstance(detail_clean, dict) else None,
                    created_at=_format_utc(log.created_at) or "",
                )
            )

        order_records: list[DecisionOrderSummaryRecord] = []
        for ord_row in orders:
            order_records.append(
                DecisionOrderSummaryRecord(
                    order_id=str(ord_row.id),
                    client_order_id=ord_row.client_order_id,
                    status=ord_row.status,
                    state_machine_state=ord_row.state_machine_state,
                    risk_decision=ord_row.risk_decision,
                    risk_reason_codes=[str(c) for c in (ord_row.risk_reason_codes or [])],
                    quantity=str(ord_row.quantity),
                    limit_price=(
                        str(ord_row.limit_price) if ord_row.limit_price is not None else None
                    ),
                    created_at=_format_utc(ord_row.created_at) or "",
                )
            )

        sanitized_explanation = sanitize_decision_payload(
            signal.explanation_json,
            secret_literals=secret_literals,
        )

        return DecisionLogEntryRecord(
            id=str(signal.id),
            signal_id=signal.signal_id,
            strategy_id=str(signal.strategy_id),
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction,
            reference_price=str(signal.reference_price),
            stop_loss_price=str(signal.stop_loss_price),
            take_profit_price=(
                str(signal.take_profit_price) if signal.take_profit_price is not None else None
            ),
            risk_reward_ratio=str(signal.risk_reward_ratio),
            data_quality_score=str(signal.data_quality_score),
            confidence_score=str(signal.confidence_score),
            rule_version=signal.rule_version,
            approval_status=signal.approval_status,
            approval_expires_at=_format_utc(signal.approval_expires_at) or "",
            explanation_json=(
                sanitized_explanation if isinstance(sanitized_explanation, dict) else {}
            ),
            events=tuple(events),
            orders=tuple(order_records),
            created_at=_format_utc(signal.created_at) or "",
            updated_at=_format_utc(signal.updated_at) or "",
        )

    async def list_decisions(
        self,
        session: AsyncSession,
        *,
        approval_status: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[DecisionLogEntryRecord]:
        """List read-only decision records across signals."""
        repo = SignalRepository(session)
        signals = await repo.list_signals(
            approval_status=approval_status,
            symbol=symbol,
            limit=limit,
        )
        secret_literals = self._collect_secret_literals()
        return [await self._build_entry(session, sig, secret_literals) for sig in signals]

    async def get_decision_by_signal_id(
        self,
        session: AsyncSession,
        signal_id: uuid.UUID | str,
    ) -> DecisionLogEntryRecord:
        """Retrieve the read-only decision record for a specific signal (by UUID or signal_id)."""
        repo = SignalRepository(session)
        signal = await repo.get_by_id_or_raise(signal_id, for_update=False)
        secret_literals = self._collect_secret_literals()
        return await self._build_entry(session, signal, secret_literals)
