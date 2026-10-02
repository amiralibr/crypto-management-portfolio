"""Background worker for Transactional Outbox publishing and Dead-Letter alerting."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import WORKER_ALIVE_GAUGE
from app.db.session import get_session_factory
from app.integrations.notifications.base import NotificationAdapter
from app.services.outbox import OutboxConsumerHandler, OutboxService

logger = get_logger(__name__)
WORKER_NAME = "outbox_publisher_worker"


async def run_outbox_publisher_step(
    session: AsyncSession,
    handler: OutboxConsumerHandler | None = None,
    notifier: NotificationAdapter | None = None,
    batch_size: int = 50,
) -> int:
    """Process one batch of pending outbox events and evaluate Dead-Letter alerts."""
    service = OutboxService(notifier=notifier)
    events = await service.process_pending_events(
        session,
        handler=handler,
        batch_size=batch_size,
    )
    await service.evaluate_dead_letter_alerts(session)
    await session.commit()
    return len(events)


async def outbox_publisher_worker_loop(
    *,
    handler: OutboxConsumerHandler | None = None,
    notifier: NotificationAdapter | None = None,
    interval_seconds: float = 2.0,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Periodic loop claiming and delivering pending outbox events (§19.2)."""
    factory = session_factory or get_session_factory()
    WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(1.0)
    try:
        while stop_event is None or not stop_event.is_set():
            async with factory() as session:
                await run_outbox_publisher_step(
                    session=session,
                    handler=handler,
                    notifier=notifier,
                )
            await asyncio.sleep(interval_seconds)
    finally:
        WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(0.0)
