"""Prometheus metrics definitions and instrumentation for MVP-0."""

from prometheus_client import Counter, Gauge, Histogram

FORBIDDEN_METRIC_LABELS: frozenset[str] = frozenset({"order_id", "signal_id", "position_id"})

HTTP_REQUESTS_TOTAL = Counter(
    "mvp0_http_requests_total",
    "Total number of HTTP requests processed by MVP-0 API",
    labelnames=("method", "path", "status"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "mvp0_http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=("method", "path"),
)

DB_HEALTH_GAUGE = Gauge(
    "mvp0_db_health",
    "PostgreSQL database connectivity health (1=healthy, 0=unhealthy)",
)

REDIS_HEALTH_GAUGE = Gauge(
    "mvp0_redis_health",
    "Redis connectivity health (1=healthy, 0=unhealthy)",
)

WORKER_ALIVE_GAUGE = Gauge(
    "mvp0_worker_alive",
    "Background worker liveness status (1=alive, 0=stopped)",
    labelnames=("worker_name",),
)

WORKER_RESTARTS_TOTAL = Counter(
    "mvp0_worker_restarts_total",
    "Total number of background worker restarts",
    labelnames=("worker_name",),
)

ORDERS_TOTAL = Counter(
    "mvp0_orders_total",
    "Total number of orders processed by status",
    labelnames=("symbol", "side", "status"),
)

ORDER_STATE_TRANSITIONS_TOTAL = Counter(
    "mvp0_order_state_transitions_total",
    "Total number of order state machine transitions",
    labelnames=("from_state", "to_state"),
)

RISK_REJECTIONS_TOTAL = Counter(
    "mvp0_risk_rejections_total",
    "Total number of signals/orders rejected by the Risk Engine",
    labelnames=("reason_code",),
)

APPROVAL_TIMEOUTS_TOTAL = Counter(
    "mvp0_approval_timeouts_total",
    "Total number of signals expired due to approval timeout",
    labelnames=("timeframe",),
)

PRICE_DRIFT_EXPIRIES_TOTAL = Counter(
    "mvp0_price_drift_expiries_total",
    "Total number of signals expired due to price drift threshold breach",
    labelnames=("symbol",),
)

SYNTHETIC_STOP_FAILURES_TOTAL = Counter(
    "mvp0_synthetic_stop_failures_total",
    "Total number of synthetic stop execution failures",
    labelnames=("symbol",),
)

KILL_SWITCH_ACTIVE_GAUGE = Gauge(
    "mvp0_kill_switch_active",
    "Kill Switch active state (1=active, 0=inactive)",
)

OUTBOX_PENDING_EVENTS_GAUGE = Gauge(
    "mvp0_outbox_pending_events",
    "Number of pending transactional outbox events",
)

OUTBOX_DEAD_LETTER_EVENTS_TOTAL = Counter(
    "mvp0_outbox_dead_letter_events",
    "Total number of events moved to dead-letter storage",
    labelnames=("failure_class",),
)

OUTBOX_DEAD_LETTER_OPEN_EVENTS_GAUGE = Gauge(
    "mvp0_outbox_dead_letter_open_events",
    "Number of unresolved OPEN dead-letter events",
)

OUTBOX_DEAD_LETTER_ESCALATED_EVENTS_GAUGE = Gauge(
    "mvp0_outbox_dead_letter_escalated_events",
    "Number of ESCALATED dead-letter events",
)

KILL_SWITCH_RESUME_REQUESTS_PENDING_GAUGE = Gauge(
    "mvp0_kill_switch_resume_requests_pending",
    "Number of pending Two-Person Kill Switch resume requests",
)

KILL_SWITCH_RESUME_REQUESTS_APPROVED_TOTAL = Counter(
    "mvp0_kill_switch_resume_requests_approved",
    "Total number of approved Two-Person Kill Switch resume requests",
)

ALL_REQUIRED_METRIC_NAMES: tuple[str, ...] = (
    "mvp0_http_requests_total",
    "mvp0_http_request_duration_seconds",
    "mvp0_db_health",
    "mvp0_redis_health",
    "mvp0_worker_alive",
    "mvp0_worker_restarts_total",
    "mvp0_orders_total",
    "mvp0_order_state_transitions_total",
    "mvp0_risk_rejections_total",
    "mvp0_approval_timeouts_total",
    "mvp0_price_drift_expiries_total",
    "mvp0_synthetic_stop_failures_total",
    "mvp0_kill_switch_active",
    "mvp0_outbox_pending_events",
    "mvp0_outbox_dead_letter_events",
    "mvp0_outbox_dead_letter_open_events",
    "mvp0_outbox_dead_letter_escalated_events",
    "mvp0_kill_switch_resume_requests_pending",
    "mvp0_kill_switch_resume_requests_approved",
)
