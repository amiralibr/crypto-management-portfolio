"""Transactional Outbox, persistent Dead-Letter, and append-only Audit service for MVP-0."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.enums import (
    ApiRole,
    DeadLetterFailureClass,
    DeadLetterResolutionStatus,
    OutboxStatus,
)
from app.core.errors import ForbiddenError, InvalidRequestError, InvalidStateError, NotFoundError
from app.core.logging import get_correlation_id_ctx, get_request_id_ctx, redact_sensitive_value
from app.core.metrics import (
    OUTBOX_DEAD_LETTER_ESCALATED_EVENTS_GAUGE,
    OUTBOX_DEAD_LETTER_EVENTS_TOTAL,
    OUTBOX_DEAD_LETTER_OPEN_EVENTS_GAUGE,
    OUTBOX_PENDING_EVENTS_GAUGE,
)
from app.db.models.audit_log import AuditLog
from app.db.models.dead_letter_event import DeadLetterEvent
from app.db.models.outbox_event import OutboxEvent
from app.integrations.notifications.base import NotificationAdapter

CRITICAL_AGGREGATE_TYPES: frozenset[str] = frozenset(
    {"ORDER", "POSITION", "SYNTHETIC_STOP", "KILL_SWITCH"}
)


def _parse_optional_uuid(val: str | uuid.UUID | None) -> uuid.UUID | None:
    if isinstance(val, uuid.UUID):
        return val
    if isinstance(val, str) and val:
        try:
            return uuid.UUID(val)
        except ValueError:
            return None
    return None


def _sanitize_json_dict(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    redacted = redact_sensitive_value(payload)
    return redacted if isinstance(redacted, dict) else {"value": str(redacted)}


async def record_audit_log(
    session: AsyncSession,
    *,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    actor_key_id: str | None = None,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
    reason_code: str | None = None,
    detail_json: dict[str, Any] | None = None,
    request_id: uuid.UUID | str | None = None,
    correlation_id: uuid.UUID | str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Create an append-only AuditLog entry within the active database transaction."""
    req_uuid = _parse_optional_uuid(request_id) or _parse_optional_uuid(get_request_id_ctx())
    corr_uuid = _parse_optional_uuid(correlation_id) or _parse_optional_uuid(
        get_correlation_id_ctx()
    )

    audit = AuditLog(
        id=uuid.uuid4(),
        request_id=req_uuid,
        correlation_id=corr_uuid,
        actor_id=actor_id,
        actor_key_id=actor_key_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_json=_sanitize_json_dict(before_json),
        after_json=_sanitize_json_dict(after_json),
        reason_code=reason_code,
        detail_json=_sanitize_json_dict(detail_json),
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.now(UTC),
    )
    session.add(audit)
    await session.flush()
    return audit


OutboxConsumerHandler = Callable[[OutboxEvent], Awaitable[None]]


class OutboxService:
    """Service managing transactional outbox events, retries, and persistent dead-letters."""

    def __init__(
        self,
        settings: Settings | None = None,
        notifier: NotificationAdapter | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._notifier = notifier
        self._processed_event_ids: set[uuid.UUID] = set()

    async def enqueue_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        payload: dict[str, Any],
        event_version: int = 1,
        event_id: uuid.UUID | None = None,
    ) -> OutboxEvent:
        """Write an OutboxEvent in PENDING status in the caller's DB transaction."""
        if event_id is not None:
            existing_event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.event_id == event_id).with_for_update()
            )
            if existing_event is not None:
                return existing_event

        now = datetime.now(UTC)
        safe_payload = _sanitize_json_dict(payload) or {}
        event = OutboxEvent(
            id=uuid.uuid4(),
            event_id=event_id or uuid.uuid4(),
            event_type=event_type,
            event_version=event_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload_json=safe_payload,
            status=OutboxStatus.PENDING.value,
            retry_count=0,
            next_retry_at=None,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(event)
        await session.flush()
        await self.refresh_metrics(session)
        return event

    async def refresh_metrics(self, session: AsyncSession) -> None:
        """Update Prometheus gauges for outbox pending, open dead-letter, and escalated counts."""
        pending_count = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.status.in_([OutboxStatus.PENDING.value, OutboxStatus.FAILED.value]))
        )
        open_dlq_count = await session.scalar(
            select(func.count())
            .select_from(DeadLetterEvent)
            .where(DeadLetterEvent.resolution_status == DeadLetterResolutionStatus.OPEN.value)
        )
        escalated_dlq_count = await session.scalar(
            select(func.count())
            .select_from(DeadLetterEvent)
            .where(DeadLetterEvent.resolution_status == DeadLetterResolutionStatus.ESCALATED.value)
        )
        OUTBOX_PENDING_EVENTS_GAUGE.set(float(pending_count or 0))
        OUTBOX_DEAD_LETTER_OPEN_EVENTS_GAUGE.set(float(open_dlq_count or 0))
        OUTBOX_DEAD_LETTER_ESCALATED_EVENTS_GAUGE.set(float(escalated_dlq_count or 0))

    async def process_pending_events(
        self,
        session: AsyncSession,
        handler: OutboxConsumerHandler | None = None,
        batch_size: int = 50,
        now: datetime | None = None,
        failure_class: DeadLetterFailureClass = DeadLetterFailureClass.TRANSIENT,
    ) -> list[OutboxEvent]:
        """Claim and publish pending outbox events with exponential backoff and Dead-Lettering."""
        current_time = now or datetime.now(UTC)
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status.in_([OutboxStatus.PENDING.value, OutboxStatus.FAILED.value]),
                or_(
                    OutboxEvent.next_retry_at.is_(None),
                    OutboxEvent.next_retry_at <= current_time,
                ),
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.scalars(stmt)
        events = list(result.all())

        for event in events:
            event.status = OutboxStatus.PROCESSING.value
            event.updated_at = current_time
            await session.flush()

            if event.event_id in self._processed_event_ids:
                event.status = OutboxStatus.PUBLISHED.value
                event.published_at = current_time
                event.updated_at = current_time
                await session.flush()
                continue

            try:
                if handler is not None:
                    await handler(event)
                self._processed_event_ids.add(event.event_id)
                event.status = OutboxStatus.PUBLISHED.value
                event.published_at = current_time
                event.next_retry_at = None
                event.updated_at = current_time
                await session.flush()
            except Exception as exc:
                await self._handle_delivery_failure(
                    session=session,
                    event=event,
                    error_message=str(exc) or type(exc).__name__,
                    failure_class=failure_class,
                    now=current_time,
                )

        await self.refresh_metrics(session)
        return events

    async def _handle_delivery_failure(
        self,
        session: AsyncSession,
        event: OutboxEvent,
        error_message: str,
        failure_class: DeadLetterFailureClass,
        now: datetime,
    ) -> None:
        event.retry_count += 1
        max_retries = self._settings.OUTBOX_MAX_RETRIES
        base_seconds = self._settings.OUTBOX_RETRY_BASE_SECONDS

        if event.retry_count < max_retries:
            backoff_seconds = base_seconds * (2 ** (event.retry_count - 1))
            event.status = OutboxStatus.FAILED.value
            event.next_retry_at = now + timedelta(seconds=backoff_seconds)
            event.updated_at = now
            await session.flush()
            return

        event.status = OutboxStatus.DEAD_LETTER.value
        event.next_retry_at = None
        event.updated_at = now

        dead_letter = DeadLetterEvent(
            id=uuid.uuid4(),
            original_outbox_event_id=event.id,
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload_json=event.payload_json,
            failure_reason=error_message,
            failure_class=failure_class.value,
            retry_count=event.retry_count,
            first_failed_at=event.created_at,
            dead_lettered_at=now,
            resolution_status=DeadLetterResolutionStatus.OPEN.value,
            created_at=now,
            updated_at=now,
        )
        session.add(dead_letter)
        await session.flush()

        OUTBOX_DEAD_LETTER_EVENTS_TOTAL.labels(failure_class=failure_class.value).inc()

        await record_audit_log(
            session,
            actor_role="SYSTEM",
            action="OUTBOX_EVENT_DEAD_LETTERED",
            target_type="DEAD_LETTER_EVENT",
            target_id=dead_letter.id,
            reason_code=failure_class.value,
            detail_json={
                "original_outbox_event_id": str(event.id),
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": str(event.aggregate_id),
                "retry_count": event.retry_count,
                "failure_reason": error_message,
            },
        )

        if self._notifier is not None:
            severity = "CRITICAL" if event.aggregate_type in CRITICAL_AGGREGATE_TYPES else "WARNING"
            await self._notifier.send_alert(
                severity=severity,
                title="Outbox Event Dead-Lettered",
                message=(
                    f"Outbox event {event.event_id} ({event.event_type}) moved to "
                    f"dead_letter_events after {event.retry_count} retries."
                ),
                metadata={
                    "dead_letter_id": str(dead_letter.id),
                    "aggregate_type": event.aggregate_type,
                    "failure_class": failure_class.value,
                },
            )

    async def evaluate_dead_letter_alerts(
        self,
        session: AsyncSession,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate open Dead-Letter events against §18.4 Alert Policy thresholds."""
        current_time = now or datetime.now(UTC)
        stmt = select(DeadLetterEvent).where(
            DeadLetterEvent.resolution_status == DeadLetterResolutionStatus.OPEN.value
        )
        open_events = list((await session.scalars(stmt)).all())
        alerts: list[dict[str, Any]] = []

        for dlq in open_events:
            age = current_time - dlq.dead_lettered_at
            if dlq.aggregate_type in CRITICAL_AGGREGATE_TYPES or age >= timedelta(minutes=60):
                severity = "CRITICAL"
                action = "Admin escalation and immediate investigation"
            elif age >= timedelta(minutes=15):
                severity = "HIGH"
                action = "Operator investigation"
            else:
                severity = "WARNING"
                action = "Notify operator"

            alert_item = {
                "dead_letter_id": str(dlq.id),
                "event_type": dlq.event_type,
                "aggregate_type": dlq.aggregate_type,
                "severity": severity,
                "required_action": action,
            }
            alerts.append(alert_item)
            if self._notifier is not None:
                await self._notifier.send_alert(
                    severity=severity,
                    title=f"Dead-Letter Alert ({severity})",
                    message=f"{action} required for Dead-Letter event {dlq.id}",
                    metadata=alert_item,
                )
        return alerts

    async def update_dead_letter_resolution(
        self,
        session: AsyncSession,
        *,
        dead_letter_id: uuid.UUID,
        resolution_status: DeadLetterResolutionStatus,
        actor_id: uuid.UUID,
        actor_role: ApiRole | str,
        resolution_note: str,
    ) -> DeadLetterEvent:
        """Update resolution status (ACKNOWLEDGED, DISCARDED, ESCALATED) with audit trail."""
        role_str = actor_role.value if isinstance(actor_role, ApiRole) else str(actor_role)
        if resolution_status == DeadLetterResolutionStatus.REPLAYED:
            raise InvalidRequestError("Use replay_dead_letter() for REPLAYED resolution")

        stmt = select(DeadLetterEvent).where(DeadLetterEvent.id == dead_letter_id).with_for_update()
        dlq = await session.scalar(stmt)
        if dlq is None:
            raise NotFoundError(f"Dead-Letter event {dead_letter_id} not found")

        now = datetime.now(UTC)
        before_status = dlq.resolution_status
        dlq.resolution_status = resolution_status.value
        dlq.resolved_at = now
        dlq.resolved_by = actor_id
        dlq.resolution_note = resolution_note
        dlq.updated_at = now
        await session.flush()

        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=role_str,
            action=f"DEAD_LETTER_{resolution_status.value}",
            target_type="DEAD_LETTER_EVENT",
            target_id=dlq.id,
            before_json={"resolution_status": before_status},
            after_json={"resolution_status": dlq.resolution_status},
            reason_code=resolution_status.value,
            detail_json={"resolution_note": resolution_note},
        )
        await self.refresh_metrics(session)
        return dlq

    async def replay_dead_letter(
        self,
        session: AsyncSession,
        *,
        dead_letter_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: ApiRole | str,
        resolution_note: str,
    ) -> tuple[DeadLetterEvent, OutboxEvent]:
        """Replay a Dead-Letter event with mandatory Admin approval and audit record (§19.4)."""
        role_str = actor_role.value if isinstance(actor_role, ApiRole) else str(actor_role)
        if role_str != ApiRole.ADMIN.value:
            raise ForbiddenError("Admin approval is required to replay a Dead-Letter event")

        if not resolution_note or len(resolution_note.strip()) < 3:
            raise InvalidRequestError("Resolution note is required for Dead-Letter replay")

        stmt = select(DeadLetterEvent).where(DeadLetterEvent.id == dead_letter_id).with_for_update()
        dlq = await session.scalar(stmt)
        if dlq is None:
            raise NotFoundError(f"Dead-Letter event {dead_letter_id} not found")

        if dlq.resolution_status == DeadLetterResolutionStatus.REPLAYED.value:
            raise InvalidStateError("Dead-Letter event has already been replayed")

        if not isinstance(dlq.payload_json, dict):
            raise InvalidRequestError("Dead-Letter payload_json is invalid for replay")

        now = datetime.now(UTC)
        before_status = dlq.resolution_status
        dlq.resolution_status = DeadLetterResolutionStatus.REPLAYED.value
        dlq.resolved_at = now
        dlq.resolved_by = actor_id
        dlq.resolution_note = resolution_note.strip()
        dlq.updated_at = now

        # Allow re-processing by clearing original event_id from local idempotency set
        self._processed_event_ids.discard(dlq.event_id)

        replayed_event = await self.enqueue_event(
            session,
            event_type=dlq.event_type,
            aggregate_type=dlq.aggregate_type,
            aggregate_id=dlq.aggregate_id,
            payload=dict(dlq.payload_json),
            event_version=dlq.event_version,
        )

        await record_audit_log(
            session,
            actor_id=actor_id,
            actor_role=role_str,
            action="DEAD_LETTER_EVENT_REPLAYED",
            target_type="DEAD_LETTER_EVENT",
            target_id=dlq.id,
            before_json={"resolution_status": before_status},
            after_json={
                "resolution_status": dlq.resolution_status,
                "replayed_outbox_event_id": str(replayed_event.id),
            },
            reason_code="REPLAYED",
            detail_json={
                "original_outbox_event_id": str(dlq.original_outbox_event_id),
                "replayed_outbox_event_id": str(replayed_event.id),
                "resolution_note": dlq.resolution_note,
            },
        )
        await self.refresh_metrics(session)
        return dlq, replayed_event
