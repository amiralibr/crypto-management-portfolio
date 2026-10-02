"""Domain and infrastructure enumerations for MVP-0."""

from enum import StrEnum

ALLOWED_SYMBOLS: frozenset[str] = frozenset({"BTC/USDT", "ETH/USDT", "BNB/USDT"})
ALLOWED_TIMEFRAMES: frozenset[str] = frozenset({"1H", "4H", "1D"})


class Environment(StrEnum):
    """Supported application runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PAPER = "paper"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported structured logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ApiRole(StrEnum):
    """Static Bearer API key authorization roles."""

    OPERATIONAL = "OPERATIONAL"
    ADMIN = "ADMIN"


class SignalApprovalStatus(StrEnum):
    """Signal approval lifecycle states."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PRICE_DRIFT_EXPIRED = "PRICE_DRIFT_EXPIRED"


class OrderState(StrEnum):
    """Order state machine states."""

    SIGNAL_CREATED = "SIGNAL_CREATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PRE_TRADE_VALIDATION = "PRE_TRADE_VALIDATION"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED_PARTIAL = "FILLED_PARTIAL"
    CANCEL_REMAINDER = "CANCEL_REMAINDER"
    FILLED = "FILLED"
    PROTECTED = "PROTECTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCEL_POSITION = "CANCEL_POSITION"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    PROTECTION_FAILED = "PROTECTION_FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class SyntheticStopStatus(StrEnum):
    """Synthetic stop-loss lifecycle states."""

    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    EXECUTED = "EXECUTED"
    RECONCILED = "RECONCILED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    CANCELLED = "CANCELLED"


class PositionStatus(StrEnum):
    """Spot position lifecycle states."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class RiskDecisionStatus(StrEnum):
    """Risk Engine decision outcomes."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"


class OutboxStatus(StrEnum):
    """Transactional outbox event states."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxEventType(StrEnum):
    """Supported transactional outbox event types (§19.1)."""

    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_APPROVED = "SIGNAL_APPROVED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
    SIGNAL_PRICE_DRIFT_EXPIRED = "SIGNAL_PRICE_DRIFT_EXPIRED"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    POSITION_CREATED = "POSITION_CREATED"
    STOP_REGISTERED = "STOP_REGISTERED"
    STOP_TRIGGERED = "STOP_TRIGGERED"
    STOP_EXECUTED = "STOP_EXECUTED"
    POSITION_CLOSED = "POSITION_CLOSED"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    KILL_SWITCH_RESUMED = "KILL_SWITCH_RESUMED"


class DeadLetterFailureClass(StrEnum):
    """Dead-letter event failure classification."""

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    SCHEMA = "SCHEMA"
    CONSUMER = "CONSUMER"
    UNKNOWN = "UNKNOWN"


class DeadLetterResolutionStatus(StrEnum):
    """Dead-letter event resolution lifecycle states."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REPLAYED = "REPLAYED"
    DISCARDED = "DISCARDED"
    ESCALATED = "ESCALATED"


class ApprovalRequestStatus(StrEnum):
    """Two-person approval request states for Kill Switch resume."""

    PENDING_FIRST_APPROVAL = "PENDING_FIRST_APPROVAL"
    PENDING_SECOND_APPROVAL = "PENDING_SECOND_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
