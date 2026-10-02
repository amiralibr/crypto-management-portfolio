"""Simulated Telegram/in-memory notification adapter for Paper-only MVP-0."""

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger, redact_sensitive_value
from app.integrations.notifications.base import NotificationAdapter, NotificationMessage

logger = get_logger(__name__)


class PaperTelegramNotificationAdapter(NotificationAdapter):
    """Paper-mode notification adapter that logs structured alerts and stores them in memory."""

    def __init__(self) -> None:
        self.sent_messages: list[NotificationMessage] = []

    async def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationMessage:
        """Record and log an operator notification with secret redaction."""
        safe_meta_raw = redact_sensitive_value(metadata or {})
        safe_meta = safe_meta_raw if isinstance(safe_meta_raw, dict) else {}
        notification = NotificationMessage(
            severity=severity.upper(),
            title=title,
            message=message,
            metadata=safe_meta,
            created_at=datetime.now(UTC),
        )
        self.sent_messages.append(notification)
        logger.info(
            "operator_notification_sent",
            severity=notification.severity,
            title=notification.title,
            alert_message=notification.message,
            metadata=notification.metadata,
        )
        return notification
