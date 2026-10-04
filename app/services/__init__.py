"""Domain and safety services package for MVP-0."""

from app.services.approval_timeout import (
    DYNAMIC_TIMEOUT_BY_TIMEFRAME,
    ApprovalTimeoutService,
    calculate_price_drift,
    compute_effective_timeout,
    validate_ips_timeout_minutes,
)
from app.services.decision_log import (
    DecisionAuditEventRecord,
    DecisionLogEntryRecord,
    DecisionLogService,
    DecisionOrderSummaryRecord,
    sanitize_decision_payload,
)
from app.services.kill_switch import (
    REDUCED_EXPOSURE_MULTIPLIER,
    KillSwitchActivationResult,
    KillSwitchService,
)
from app.services.mean_reversion_rule import (
    MeanReversionRule,
    calculate_bollinger_bands,
    calculate_rsi_series,
)
from app.services.outbox import OutboxService, record_audit_log
from app.services.reconciliation import ReconciliationReport, ReconciliationService
from app.services.risk_engine import (
    HARD_DRAWDOWN,
    KILL_SWITCH_DRAWDOWN,
    MAX_ASSET_WEIGHT,
    MAX_DAILY_LOSS,
    MAX_RISK_PER_TRADE,
    MAX_TOTAL_EXPOSURE,
    MAX_WEEKLY_LOSS,
    MIN_CASH_RESERVE,
    SOFT_DRAWDOWN,
    InvestmentPolicySnapshot,
    PositionSizingResult,
    RiskEngine,
    RiskEvaluationDecision,
    RiskEvaluationInput,
    ensure_decimal,
    floor_to_step,
)
from app.services.signal_engine import SignalEngine
from app.services.signal_lifecycle import (
    OrderDraft,
    SignalDecisionOutcome,
    SignalLifecycleService,
)
from app.services.state_machine import (
    ALLOWED_ORDER_TRANSITIONS,
    ALLOWED_SIGNAL_TRANSITIONS,
    PARTIAL_FILL_TIMEOUT_SECONDS,
    PROTECTION_RETRY_SCHEDULE_SECONDS,
    ProtectionRetryOutcome,
    StateMachineService,
)
from app.services.synthetic_stop import (
    POLL_INTERVAL_SECONDS_BY_TIMEFRAME,
    STOP_RETRY_SCHEDULE_SECONDS,
    StopExecutionResult,
    SyntheticStopService,
)
from app.services.trend_following_rule import (
    CandleBar,
    SignalCandidate,
    TrendFollowingRule,
    calculate_ema,
    filter_closed_candles,
)

__all__ = [
    "ALLOWED_ORDER_TRANSITIONS",
    "ALLOWED_SIGNAL_TRANSITIONS",
    "ApprovalTimeoutService",
    "CandleBar",
    "DYNAMIC_TIMEOUT_BY_TIMEFRAME",
    "DecisionAuditEventRecord",
    "DecisionLogEntryRecord",
    "DecisionLogService",
    "DecisionOrderSummaryRecord",
    "HARD_DRAWDOWN",
    "InvestmentPolicySnapshot",
    "KILL_SWITCH_DRAWDOWN",
    "KillSwitchActivationResult",
    "KillSwitchService",
    "MAX_ASSET_WEIGHT",
    "MAX_DAILY_LOSS",
    "MAX_RISK_PER_TRADE",
    "MAX_TOTAL_EXPOSURE",
    "MAX_WEEKLY_LOSS",
    "MIN_CASH_RESERVE",
    "MeanReversionRule",
    "OrderDraft",
    "OutboxService",
    "PARTIAL_FILL_TIMEOUT_SECONDS",
    "POLL_INTERVAL_SECONDS_BY_TIMEFRAME",
    "PROTECTION_RETRY_SCHEDULE_SECONDS",
    "PositionSizingResult",
    "ProtectionRetryOutcome",
    "REDUCED_EXPOSURE_MULTIPLIER",
    "ReconciliationReport",
    "ReconciliationService",
    "RiskEngine",
    "RiskEvaluationDecision",
    "RiskEvaluationInput",
    "SOFT_DRAWDOWN",
    "STOP_RETRY_SCHEDULE_SECONDS",
    "SignalCandidate",
    "SignalDecisionOutcome",
    "SignalEngine",
    "SignalLifecycleService",
    "StateMachineService",
    "StopExecutionResult",
    "SyntheticStopService",
    "TrendFollowingRule",
    "calculate_bollinger_bands",
    "calculate_ema",
    "calculate_price_drift",
    "calculate_rsi_series",
    "compute_effective_timeout",
    "ensure_decimal",
    "filter_closed_candles",
    "floor_to_step",
    "record_audit_log",
    "sanitize_decision_payload",
    "validate_ips_timeout_minutes",
]
