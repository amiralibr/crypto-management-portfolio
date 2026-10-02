"""Background worker for periodic Synthetic Stop-Loss monitoring."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import WORKER_ALIVE_GAUGE
from app.db.session import get_session_factory
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.synthetic_stop import (
    POLL_INTERVAL_SECONDS_BY_TIMEFRAME,
    StopExecutionResult,
    SyntheticStopService,
)

logger = get_logger(__name__)
WORKER_NAME = "synthetic_stop_worker"


async def run_synthetic_stop_step(
    session: AsyncSession,
    exchange_adapter: ExchangeAdapter,
    notifier: NotificationAdapter | None = None,
    timeframe: str = "1H",
) -> list[StopExecutionResult]:
    """Execute one polling cycle over all active ARMED synthetic stops."""
    service = SyntheticStopService(
        exchange_adapter=exchange_adapter,
        notifier=notifier,
        current_timeframe=timeframe,
    )
    results = await service.monitor_armed_stops(session)
    await session.commit()
    return results


async def synthetic_stop_worker_loop(
    *,
    exchange_adapter: ExchangeAdapter,
    notifier: NotificationAdapter | None = None,
    timeframe: str = "1H",
    interval_seconds: float | None = None,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Periodic loop polling active synthetic stops by timeframe (30s/60s/300s) (§12.3)."""
    interval = (
        interval_seconds
        if interval_seconds is not None
        else float(POLL_INTERVAL_SECONDS_BY_TIMEFRAME.get(timeframe, 30))
    )
    factory = session_factory or get_session_factory()
    WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(1.0)
    try:
        while stop_event is None or not stop_event.is_set():
            async with factory() as session:
                await run_synthetic_stop_step(
                    session=session,
                    exchange_adapter=exchange_adapter,
                    notifier=notifier,
                    timeframe=timeframe,
                )
            await asyncio.sleep(interval)
    finally:
        WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(0.0)
