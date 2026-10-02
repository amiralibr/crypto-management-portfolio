"""Notifications integration package for MVP-0."""

from app.integrations.notifications.base import NotificationAdapter, NotificationMessage
from app.integrations.notifications.telegram import PaperTelegramNotificationAdapter

__all__ = [
    "NotificationAdapter",
    "NotificationMessage",
    "PaperTelegramNotificationAdapter",
]
