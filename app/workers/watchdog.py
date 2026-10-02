"""Watchdog worker monitoring database and worker health in MVP-0."""

from datetime import UTC, datetime

from app.core.metrics import DB_HEALTH_GAUGE, WORKER_ALIVE_GAUGE
from app.db.session import ping_database

WORKER_NAME = "watchdog_worker"


async def check_system_watchdog() -> dict[str, object]:
    """Verify PostgreSQL connectivity and report watchdog heartbeat."""
    db_ok = await ping_database()
    DB_HEALTH_GAUGE.set(1.0 if db_ok else 0.0)
    WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(1.0 if db_ok else 0.0)
    return {
        "db_ok": db_ok,
        "timestamp": datetime.now(UTC).isoformat(),
    }
