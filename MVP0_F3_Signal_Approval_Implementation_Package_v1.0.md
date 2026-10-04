# MVP-0 F3 Signal & Approval Implementation Package

**Phase:** F3 — Signal and Approval  
**Version:** 1.0  
**Status:** Approved for Implementation  
**Date:** 2026-10-04  
**Parent Contract:** `MVP0_Implementation_Contract_v1.2_FINAL.md`  
**Master Reference:** `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`  

## 0. Authorization and Hierarchy

### Gate Authorization

```text
F1: ACCEPTED
F2: ACCEPTED
F3: AUTHORIZED
F4: BLOCKED
```

F3 is authorized only because the auditor issued `F2 — ACCEPTED / F3 — AUTHORIZED`.

### Document Precedence

1. Written auditor decision
2. `MVP0_Implementation_Contract_v1.2_FINAL.md`
3. This package
4. Master Package v4.3

In a conflict, the higher-ranked document controls. Stop and report an unresolved conflict; do not infer a new requirement.

## 1. Objective

Implement the deterministic Signal and Approval layer that creates auditable Spot-LONG signals, accepts or rejects explicit user approval, expires stale signals, records decisions, and hands approved signals to the already-approved F2 Risk Engine.

The required lifecycle is:

```text
Signal Created
  → PENDING_APPROVAL
  → APPROVED | REJECTED | EXPIRED | PRICE_DRIFT_EXPIRED
  → Risk Validation
  → Paper Order Draft / Risk-Rejected Order Record
```

F3 must preserve all F1/F2 safety controls and regression tests.

## 2. Scope Boundaries

### 2.1 In Scope

- Deterministic Signal Engine
- Trend Following rule
- Mean Reversion rule
- Signal persistence and repository
- Signal list, approve, and reject API endpoints
- Dynamic Approval Timeout
- Price Drift Expiry
- Signal lifecycle state machine
- Read-only Decision Log API
- Signal-to-order handoff through existing F2 Risk Engine
- Audit and Transactional Outbox events for signal decisions
- F3 unit, integration, API, state machine, and E2E tests
- F1/F2 regression execution

### 2.2 Explicitly Out of Scope

Do not implement any of the following in F3:

- Live trading, Direct Mode, real API keys, real exchange calls, or a real exchange adapter
- Short, margin, leverage, futures, derivatives, or withdrawal
- Portfolio allocation, rebalancing, on-chain or sentiment modules
- ML, JEV, Shadow Mode, A/B testing, Go, Vault, TimescaleDB, multi-tenancy, or RLS
- Editable Decision Journal, comments, feedback loop, or model evaluation
- Full Dashboard/PWA work
- New Kill Switch logic, new Synthetic Stop execution logic, or new reconciliation design
- F4 Paper Execution changes or F5 full Chaos suite

Existing F2 Kill Switch, Synthetic Stop, Outbox, reconciliation, Paper isolation, and Redis rules must remain unchanged and green.

## 3. Repository Changes

Create or complete only the following F3-owned modules:

```text
app/
├── api/v1/
│   ├── signals.py
│   ├── decisions.py
│   └── orders.py                 # F3 handoff/read scope only
├── services/
│   ├── signal_engine.py
│   ├── trend_following_rule.py
│   ├── mean_reversion_rule.py
│   ├── signal_lifecycle.py
│   ├── approval_timeout.py
│   └── decision_log.py
├── schemas/
│   ├── signals.py
│   └── decisions.py
└── workers/
    └── approval_timeout.py

tests/
├── unit/
│   ├── test_signal_engine.py
│   ├── test_trend_following_rule.py
│   ├── test_mean_reversion_rule.py
│   └── test_approval_timeout.py
├── integration/
│   ├── test_signal_api.py
│   ├── test_signal_approval.py
│   ├── test_signal_to_order_handoff.py
│   └── test_decision_log.py
└── e2e/
    └── test_signal_approval_order_flow.py
```

No F4/F5/F6 module may be introduced under the guise of F3.

## 4. Signal Engine Contract

### 4.1 Allowed Market

```text
Symbols: BTC/USDT, ETH/USDT, BNB/USDT
Market: SPOT only
Direction: LONG only
Leverage: forbidden
Short: forbidden
```

Reject any disallowed symbol, non-LONG direction, incomplete data, stale data, or invalid price.

### 4.2 Closed Candle Rule

All indicators and all signal decisions must use **closed candles only**. An open/incomplete candle must never generate a signal.

### 4.3 Trend Following Rule

Create a LONG Trend Following signal only when all conditions are true:

```text
1. EMA(50) > EMA(200) on 4H closed candles
2. Close > EMA(20) on 1H closed candles
3. Close > highest high of previous 20 closed 1H candles
4. Volume >= 1.5 × average volume of previous 20 closed 1H candles
5. Data quality score >= 0.8
6. Confidence score >= 0.6
```

### 4.4 Mean Reversion Rule

Create a LONG Mean Reversion signal only when all conditions are true:

```text
1. RSI(14) was below 30 and crosses back above 30 on closed 1H candles
2. Close was at or below Lower Bollinger Band(20, 2)
3. Close returns inside the Bollinger Band
4. Data quality score >= 0.8
5. Confidence score >= 0.6
```

### 4.5 Required Signal Data

Every persisted signal must contain:

```text
signal_id
strategy_id
symbol
timeframe
direction
reference_price
entry_range_min
entry_range_max
stop_loss_price
take_profit_price
risk_reward_ratio
data_quality_score
confidence_score
rule_version
approval_status
approval_expires_at
explanation_json
created_at
updated_at
version
```

`explanation_json` must contain:

```text
entry_reason
risk_reason
confluence_score
regime
factors
```

All financial values must be `Decimal` in application logic and `NUMERIC` in PostgreSQL. All timestamps must be UTC-aware.

## 5. Signal Lifecycle Contract

### 5.1 States

```text
PENDING_APPROVAL
APPROVED
REJECTED
EXPIRED
PRICE_DRIFT_EXPIRED
```

### 5.2 Allowed Transitions

```text
PENDING_APPROVAL → APPROVED
PENDING_APPROVAL → REJECTED
PENDING_APPROVAL → EXPIRED
PENDING_APPROVAL → PRICE_DRIFT_EXPIRED
```

No other transition is permitted.

### 5.3 Transactional Rules

Every state transition must:

1. Use `SELECT ... FOR UPDATE`
2. Validate current state
3. Validate expiration and price drift where applicable
4. Persist the new state
5. Write an immutable audit record
6. Write a versioned Outbox event
7. Commit all domain changes, audit record, and Outbox event in the same PostgreSQL transaction

If any validation fails, no state change, audit record, or Outbox event may be written.

## 6. Dynamic Approval Timeout

### 6.1 Default Timeout

| Signal timeframe | Timeout |
|---|---:|
| 1H | 5 minutes |
| 4H | 30 minutes |
| 1D | 4 hours |

### 6.2 IPS Override

```text
effective_timeout = min(dynamic_timeout, ips_timeout)
```

Rules:

- `approval_timeout_minutes` is optional
- Valid range is 3 through 240 minutes
- `None` preserves dynamic timeout
- IPS may reduce timeout only; it may not extend timeout

### 6.3 Worker Behavior

The Approval Timeout Worker must:

1. Run every 5 seconds
2. Select only `PENDING_APPROVAL` signals
3. Apply time expiry when applicable
4. Apply price-drift expiry when applicable
5. Use transactional state changes
6. Create required audit and Outbox records

## 7. Price Drift Expiry

### 7.1 Formula

```text
price_drift = abs(current_price - signal.reference_price) / signal.reference_price

if price_drift > PRICE_DRIFT_EXPIRY_THRESHOLD:
    approval_status = PRICE_DRIFT_EXPIRED
```

### 7.2 Locked Threshold

```text
PRICE_DRIFT_EXPIRY_THRESHOLD = 0.002
```

This means a 0.2% absolute drift from immutable `reference_price`.

### 7.3 Rules

- Use Decimal arithmetic
- Both prices must be positive
- Use the latest valid ticker price
- Price drift may expire a signal before time timeout
- Audit action: `SIGNAL_PRICE_DRIFT_EXPIRED`
- Audit payload includes `reference_price`, `current_price`, `price_drift`, and `threshold`
- Never record credentials or secrets in audit payloads

## 8. API Contract

All protected endpoints require:

```http
Authorization: Bearer <MVP0_API_KEY>
```

All mutating endpoints require:

```http
Idempotency-Key: <uuid>
```

### 8.1 List Signals

```http
GET /api/v1/signals
```

### 8.2 Approve Signal

```http
POST /api/v1/signals/{signal_id}/approve
Content-Type: application/json

{
  "reason": "Approved based on trend confirmation"
}
```

### 8.3 Reject Signal

```http
POST /api/v1/signals/{signal_id}/reject
Content-Type: application/json

{
  "reason": "Rejected by user"
}
```

### 8.4 Required Error Codes

| Condition | HTTP | Code |
|---|---:|---|
| Missing/invalid token | 401 | `UNAUTHORIZED` |
| Signal missing | 404 | `SIGNAL_NOT_FOUND` |
| Invalid transition | 409 | `INVALID_STATE` |
| Approval after timeout | 409 | `SIGNAL_EXPIRED` |
| Approval after price drift | 409 | `PRICE_DRIFT_EXPIRED` |
| Same idempotency key with differing payload | 409 | `IDEMPOTENCY_CONFLICT` |

## 9. Signal-to-Order Handoff

After approval:

```text
1. Signal changes to APPROVED
2. Create order draft linked to signal_id
3. Send draft to existing F2 Risk Engine
4. If approved, create order in PRE_TRADE_VALIDATION or SUBMITTED state
5. If rejected, retain APPROVED signal and create a risk-rejected order record
6. Create audit and Outbox records for the result
```

Rules:

- At most one active order per approved signal
- `client_order_id` and `idempotency_key` are unique
- Creation and risk decision are transactional
- Risk Engine remains final authority
- No real exchange call is allowed
- Use only approved F2 Paper/Fake adapter foundation

## 10. Read-Only Decision Log API

Implement:

```http
GET /api/v1/decisions
GET /api/v1/decisions/{signal_id}
```

Rules:

- Read-only only
- Source data: `audit_logs` and signal `explanation_json`
- No create, update, delete, comment, feedback, or model-evaluation endpoint
- No secret exposure

## 11. Required Outbox Events

```text
SIGNAL_CREATED
SIGNAL_APPROVED
SIGNAL_REJECTED
SIGNAL_EXPIRED
SIGNAL_PRICE_DRIFT_EXPIRED
ORDER_CREATED
ORDER_REJECTED_BY_RISK
```

Events must be versioned and persisted transactionally with the associated domain change.

## 12. Mandatory Tests

### 12.1 Signal Engine

```text
test_signal_engine_uses_closed_candles_only
test_trend_following_requires_all_conditions
test_trend_following_rejects_insufficient_volume
test_mean_reversion_requires_rsi_cross
test_mean_reversion_requires_bollinger_return
test_signal_rejects_data_quality_below_0_8
test_signal_rejects_confidence_below_0_6
test_signal_rejects_disallowed_symbol
test_signal_rejects_non_long_direction
test_signal_contains_explanation
test_signal_reference_price_is_immutable
```

### 12.2 Timeout and Price Drift

```text
test_dynamic_timeout_for_1h_is_5_minutes
test_dynamic_timeout_for_4h_is_30_minutes
test_dynamic_timeout_for_1d_is_4_hours
test_ips_timeout_can_only_reduce_timeout
test_ips_timeout_rejects_below_3_minutes
test_ips_timeout_rejects_above_240_minutes
test_approval_timeout_worker_runs_every_5_seconds
test_timeout_transition_is_atomic
test_timeout_creates_audit_event
test_timeout_creates_outbox_event
test_price_drift_threshold_is_0_002
test_price_drift_uses_decimal
test_price_drift_expires_signal
test_price_drift_expiry_occurs_before_timeout
test_price_drift_expiry_creates_audit_event
test_price_drift_expiry_creates_outbox_event
test_price_drift_rejects_zero_or_negative_price
```

### 12.3 Signal State Machine

```text
test_pending_signal_can_be_approved
test_pending_signal_can_be_rejected
test_pending_signal_can_expire
test_pending_signal_can_price_drift_expire
test_approved_signal_cannot_be_approved_again
test_rejected_signal_cannot_be_approved
test_expired_signal_cannot_be_approved
test_price_drift_expired_signal_cannot_be_approved
test_concurrent_approval_is_serialized
test_invalid_transition_returns_409
```

### 12.4 API and Decision Log

```text
test_list_signals_requires_operational_key
test_approve_signal_requires_operational_key
test_reject_signal_requires_operational_key
test_admin_key_can_access_operational_routes
test_operational_key_cannot_access_admin_routes
test_approve_signal_is_idempotent
test_duplicate_idempotency_key_with_different_payload_returns_409
test_signal_not_found_returns_404
test_invalid_state_returns_409
test_decision_log_is_read_only
test_decision_history_is_queryable_by_signal_id
test_decision_history_includes_approval_event
test_decision_history_includes_rejection_event
test_decision_history_includes_timeout_event
test_decision_history_includes_price_drift_event
test_decision_history_does_not_expose_secrets
test_decision_log_has_no_create_endpoint
test_decision_log_has_no_update_endpoint
test_decision_log_has_no_delete_endpoint
```

### 12.5 Signal-to-Order Handoff

```text
test_approved_signal_creates_order_draft
test_risk_approved_signal_creates_submitted_order
test_risk_rejected_signal_creates_rejected_order
test_risk_rejection_creates_audit_event
test_risk_rejection_creates_outbox_event
test_one_active_order_per_signal
test_duplicate_order_creation_is_prevented
test_no_real_exchange_call_is_made
```

### 12.6 Mandatory F2 Regression

```text
test_kill_switch_blocks_new_orders
test_kill_switch_persists_after_restart
test_synthetic_stop_triggers_only_once
test_protection_failure_retry_schedule_is_0_5_15_seconds
test_outbox_dead_letter_after_max_retries
test_redis_unavailable_does_not_lose_postgres_state
test_paper_environment_has_no_live_exchange_endpoint
```

## 13. Quality Gates

| Area | Minimum |
|---|---:|
| Overall coverage | 80% |
| Signal Engine | 90% |
| Approval Timeout | 90% |
| Signal Lifecycle | 90% |
| Risk Engine regression | 90% |
| State Machine regression | 90% |
| `ruff check` | zero errors |
| `ruff format --check` | zero diffs |
| `mypy --strict app` | zero errors |
| F3 tests | 100% pass |
| F2 regression tests | 100% pass |
| Live trading code | zero occurrences |
| Real adapter/credential | zero occurrences |

## 14. Required Deliverables

1. F3 source code and migrations only if schema changes are essential
2. All mandatory tests
3. CI, security scan, Docker/Compose evidence
4. Updated API documentation
5. `MVP0_F3_Completion_Evidence_v1.0.md` self-contained evidence bundle
6. A branch/tag and commit SHA
7. Explicit list of all NOT IMPLEMENTED items and target phase

## 15. Evidence Bundle Protocol

The final Evidence Bundle must be self-contained. Every claim must include:

```text
- File path
- Line range or function name
- Test name
- CI Run ID and job/step
- Actual log excerpt or command output
- Commit SHA/tag
```

Minimum template:

```markdown
# MVP-0 F3 Completion Evidence v1.0

## 0. Metadata
| Field | Value |
|---|---|
| Phase | F3 Signal and Approval |
| Branch | |
| Tag | |
| Commit SHA | |
| CI Run ID | |
| Security Scan Run ID | |
| Docker Build Run ID | |

## 1. Delivered Scope
| Requirement | Source | Test | CI Evidence | Result |
|---|---|---|---|---|

## 2. Not Delivered
| Requirement | Reason | Target Phase |
|---|---|---|

## 3. CI and Coverage
| Gate | Command | Exit Code | Result | Log Excerpt |
|---|---|---:|---|---|

## 4. Tests
| Test | Result | Evidence |
|---|---|---|

## 5. Security and Environment
| Control | Result | Evidence |
|---|---|---|

## 6. Open Items
| ID | Severity | Action | Target Phase |
|---|---|---|---|

## 7. Declaration
All claims are evidence-backed: YES / NO
Ready for auditor review: YES / NO
```

## 16. Acceptance Criteria

F3 is complete only when all are true:

```text
1. Signals use closed candles only.
2. Only BTC/USDT, ETH/USDT, BNB/USDT Spot-LONG signals are allowed.
3. Every signal has explanation data.
4. Explicit approval is mandatory.
5. Dynamic timeout works for 1H, 4H, and 1D.
6. IPS only reduces timeout.
7. Drift above 0.2% expires a signal.
8. State transitions are atomic, auditable, and Outbox-backed.
9. Decision API is read-only.
10. Approved signal creates at most one active order.
11. Risk Engine remains final authority.
12. No real exchange call is made.
13. F2 regressions remain green.
14. All quality gates are met.
15. Evidence Bundle is self-contained.
```

## 17. Exit Gate

F4 remains blocked until the auditor issues the exact written decision:

```text
F3 ACCEPTED — F4 AUTHORIZED
```

No F4 execution, F5 hardening/chaos expansion, or F6 dashboard work may begin before that decision.

## 18. Developer Rules

- Do not infer requirements not stated in this package.
- Do not add F4/F5/F6 capabilities.
- Do not use Redis for durable domain state.
- Do not use `float` for monetary values.
- Do not use naive datetime.
- Do not bypass the Risk Engine.
- Do not approve expired or drift-expired signals.
- Do not initiate any real exchange request.
