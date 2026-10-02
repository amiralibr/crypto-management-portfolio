"""Notification adapter interface and value objects for MVP-0."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class NotificationMessage:
    """Immutable operator/admin notification event."""

    severity: str
    title: str
    message: str
    metadata: dict[str, Any]
    created_at: datetime


class NotificationAdapter(ABC):
    """Abstract base interface for operator/admin notifications."""

    @abstractmethod
    async def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationMessage:
        """Send an operational or security alert without leaking secrets."""
