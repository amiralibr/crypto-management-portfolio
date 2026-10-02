"""Background worker for periodic Signal Approval Timeout & Price Drift evaluation."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import WORKER_ALIVE_GAUGE
from app.db.session import get_session_factory
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.approval_timeout import ApprovalTimeoutService

logger = get_logger(__name__)
WORKER_NAME = "approval_timeout_worker"


async def run_approval_timeout_step(
    session: AsyncSession,
    exchange_adapter: ExchangeAdapter | None = None,
    notifier: NotificationAdapter | None = None,
) -> int:
    """Execute one sweep of pending signals for timeout and price drift."""
    service = ApprovalTimeoutService(
        exchange_adapter=exchange_adapter,
        notifier=notifier,
    )
    processed = await service.check_pending_signals(session)
    await session.commit()
    return len(processed)


async def approval_timeout_worker_loop(
    *,
    exchange_adapter: ExchangeAdapter | None = None,
    notifier: NotificationAdapter | None = None,
    interval_seconds: float | None = None,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Periodic loop running check_pending_signals every 5 seconds (§11.4 & v4.3 §1.2)."""
    settings = get_settings()
    interval = (
        interval_seconds
        if interval_seconds is not None
        else float(settings.APPROVAL_TIMEOUT_INTERVAL_SECONDS)
    )
    factory = session_factory or get_session_factory()
    WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(1.0)
    try:
        while stop_event is None or not stop_event.is_set():
            async with factory() as session:
                await run_approval_timeout_step(
                    session=session,
                    exchange_adapter=exchange_adapter,
                    notifier=notifier,
                )
            await asyncio.sleep(interval)
    finally:
        WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(0.0)
