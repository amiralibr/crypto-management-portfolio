"""Watchdog worker monitoring database health and recording Risk Engine heartbeat in MVP-0."""

from datetime import UTC, datetime

from app.core.metrics import DB_HEALTH_GAUGE, WORKER_ALIVE_GAUGE
from app.db.session import get_session_factory, ping_database
from app.services.risk_engine import RiskEngine

WORKER_NAME = "watchdog_worker"


async def check_system_watchdog(*, now: datetime | None = None) -> dict[str, object]:
    """Verify PostgreSQL connectivity and record durable Risk Engine heartbeat."""
    current_time = now or datetime.now(UTC)
    db_ok = await ping_database()
    DB_HEALTH_GAUGE.set(1.0 if db_ok else 0.0)
    WORKER_ALIVE_GAUGE.labels(worker_name=WORKER_NAME).set(1.0 if db_ok else 0.0)

    if db_ok:
        try:
            factory = get_session_factory()
            async with factory() as session:
                await RiskEngine().record_heartbeat(session, now=current_time)
                await session.commit()
        except Exception:
            db_ok = False
            DB_HEALTH_GAUGE.set(0.0)

    return {
        "db_ok": db_ok,
        "timestamp": current_time.isoformat(),
    }
