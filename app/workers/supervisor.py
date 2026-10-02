"""Supervisor for background worker lifecycle, crash detection, and startup recovery."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import WORKER_ALIVE_GAUGE, WORKER_RESTARTS_TOTAL
from app.db.session import get_session_factory
from app.integrations.exchange.base import ExchangeAdapter
from app.integrations.notifications.base import NotificationAdapter
from app.services.kill_switch import KillSwitchService
from app.services.outbox import record_audit_log
from app.services.reconciliation import ReconciliationReport, ReconciliationService
from app.services.synthetic_stop import SyntheticStopService

logger = get_logger(__name__)


class WorkerSupervisor:
    """Supervises background worker tasks and enforces fail-closed crash handling (v4.3 §1.4)."""

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        notifier: NotificationAdapter | None = None,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    ) -> None:
        self._exchange = exchange_adapter
        self._notifier = notifier
        self._session_factory = session_factory or get_session_factory()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self.execution_frozen: bool = False

    async def recover_and_reconcile_on_startup(
        self,
        *,
        sync_missing_to_exchange: bool = False,
    ) -> tuple[int, ReconciliationReport]:
        """Load active Synthetic Stops from PostgreSQL and reconcile open positions (§17.1)."""
        stop_service = SyntheticStopService(
            exchange_adapter=self._exchange,
            notifier=self._notifier,
        )
        recon_service = ReconciliationService(
            exchange_adapter=self._exchange,
            notifier=self._notifier,
        )
        async with self._session_factory() as session:
            stops = await stop_service.reconcile_stops_after_restart(session)
            report = await recon_service.reconcile_open_positions(
                session,
                sync_missing_to_exchange=sync_missing_to_exchange,
            )
            await session.commit()
        return len(stops), report

    async def run_supervised_worker(
        self,
        worker_name: str,
        worker_coro_fn: Callable[[], Awaitable[None]],
    ) -> None:
        """Run a worker coroutine and trigger fail-closed Kill Switch freeze on abnormal crash."""
        WORKER_ALIVE_GAUGE.labels(worker_name=worker_name).set(1.0)
        try:
            await worker_coro_fn()
        except asyncio.CancelledError:
            WORKER_ALIVE_GAUGE.labels(worker_name=worker_name).set(0.0)
            raise
        except Exception as exc:
            WORKER_ALIVE_GAUGE.labels(worker_name=worker_name).set(0.0)
            WORKER_RESTARTS_TOTAL.labels(worker_name=worker_name).inc()
            self.execution_frozen = True
            err_msg = str(exc) or type(exc).__name__
            logger.error(
                "worker_crashed_fail_closed",
                worker_name=worker_name,
                error=err_msg,
            )
            async with self._session_factory() as session:
                await record_audit_log(
                    session,
                    actor_role="SYSTEM",
                    action="WORKER_FAILURE",
                    target_type="WORKER",
                    reason_code="WORKER_CRASHED",
                    detail_json={
                        "worker_name": worker_name,
                        "error": err_msg,
                        "execution_frozen": True,
                    },
                )
                ks_service = KillSwitchService(
                    exchange_adapter=self._exchange,
                    notifier=self._notifier,
                )
                await ks_service.activate(
                    session,
                    reason=f"Worker crash detected in {worker_name}: {err_msg}",
                    actor_role="SYSTEM",
                    activated_by="supervisor",
                    activation_source="WORKER_CRASH",
                )
                await session.commit()
            if self._notifier is not None:
                await self._notifier.send_alert(
                    severity="CRITICAL",
                    title=f"Worker Failure: {worker_name}",
                    message=f"Worker {worker_name} terminated abnormally: {err_msg}",
                    metadata={"worker_name": worker_name, "error": err_msg},
                )
            raise

    def start_worker(
        self,
        worker_name: str,
        worker_coro_fn: Callable[[], Awaitable[None]],
    ) -> asyncio.Task[None]:
        """Start a single instance of a named worker task if not already running."""
        existing = self._tasks.get(worker_name)
        if existing is not None and not existing.done():
            return existing
        task = asyncio.create_task(
            self.run_supervised_worker(worker_name, worker_coro_fn),
            name=worker_name,
        )
        self._tasks[worker_name] = task
        return task

    async def stop_all(self) -> None:
        """Cancel all supervised worker tasks and await graceful shutdown (§17.2)."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
