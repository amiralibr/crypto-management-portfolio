# MVP-0 F4 Paper Execution & Reconciliation Implementation Package

**Document ID:** MVP0-F4-IMP-001  
**Phase:** F4 — Paper Execution & Reconciliation  
**Version:** 1.0  
**Status:** Approved for Implementation  
**Date:** 2026-10-05  
**Parent Contract:** `MVP0_Implementation_Contract_v1.2_FINAL.md`  
**Master Reference:** `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`  
**Prerequisite Gates:** F1 ACCEPTED, F2 ACCEPTED, F3 ACCEPTED  

---

## 0. Authorization and Document Control

### 0.1 Program Status

```text
F1 Foundation: ACCEPTED
F2 Data & Risk Core: ACCEPTED
F3 Signal & Approval: ACCEPTED — CLOSED
F4 Paper Execution & Reconciliation: AUTHORIZED — READY FOR IMPLEMENTATION
F5 Safety Hardening: NOT AUTHORIZED
F6 Dashboard: NOT AUTHORIZED
F7 Final Acceptance: NOT AUTHORIZED
```

### 0.2 Approved Baselines

```text
F1 baseline:
release/f1-candidate @ bdff565d1b46222bd15340a0fe0ba3e76dd7411b

F2 baseline:
release/f2-candidate @ 5e7758846169614daeb39e3f5346037f245af856

F3 technical baseline:
f3-accepted @ 9cf204d88fbcc1af0428331f866348a013f6aec0

F3 administrative documentation HEAD:
c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4
```

### 0.3 Document Precedence

In case of conflict, the following order applies:

1. Written auditor decision.
2. `MVP0_Implementation_Contract_v1.2_FINAL.md`.
3. This F4 implementation package.
4. `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`.
5. Implementer reports, examples, comments, or prior chat summaries.

A conflict must be reported before implementation. The implementer must not infer, widen, or replace a requirement.

### 0.4 F4 Exit Authority

F5 remains blocked until the auditor issues exactly:

```text
F4 ACCEPTED — F5 AUTHORIZED
```

---

## 1. F4 Objective

Implement and validate the **Paper-only execution and reconciliation lifecycle** for the approved F1/F2/F3 foundation.

F4 begins at the approved F3 handoff and makes the following Paper lifecycle durable, idempotent, observable, and reconcilable:

```text
Approved Signal
  → Risk-Approved Order Draft
  → Submitted to PaperTradingAdapter
  → Partially Filled | Filled | Cancelled | Failed
  → Position Created or Updated
  → Protection Registered
  → Synthetic Stop / Take-Profit lifecycle
  → Position Closed
  → Reconciliation Complete
```

F4 must resolve the carried limitations below only within the Paper environment:

```text
L-02: Kill Switch partial-fill handling was incomplete in F3.
L-03: Full Position lifecycle management was incomplete in F3.
```

F4 does **not** authorize Live Trading, Direct Mode, real exchange connectivity, real API credentials, or any external order submission.

---

## 2. Scope Boundaries

### 2.1 In Scope

- `PaperTradingAdapter` completion and deterministic behavior.
- `FakeExchangeAdapter` test behavior completion.
- Paper order submission, cancellation, fill, partial-fill, and status polling.
- Order idempotency and `client_order_id` handling.
- Position creation, aggregation, update, protection, and close lifecycle.
- Trade/fill persistence and duplicate fill prevention.
- Partial-fill protection and remainder cancellation after 60 seconds.
- Synthetic Stop registration, monitoring integration, execution, retry, and reconciliation.
- Take-profit and trailing-state persistence only where already supported by the approved state model.
- Paper reconciliation of orders, trades, positions, stops, and balances.
- Deterministic Kill Switch behavior for open orders, partial fills, protected positions, and unresolved states.
- Transactional Outbox events and immutable audit records for all F4 financial transitions.
- F4 Paper-only integration, reconciliation, failure-recovery, and regression tests.
- F4 evidence package and audit-ready artifacts.

### 2.2 Explicitly Out of Scope

The following are forbidden in F4:

- Live Trading.
- Direct Mode.
- Real exchange API endpoint, adapter, credential, secret, API key, signing, or withdrawal permission.
- Any external exchange network connection.
- Futures, margin, leverage, derivatives, short selling, or withdrawal.
- New strategy types, ML, JEV, Shadow Mode, A/B testing, Go, Vault, TimescaleDB, RLS, or multi-tenancy.
- Dashboard or PWA implementation.
- OS-level `SIGKILL` / container-kill production fire drills; these belong to F5.
- New user-facing workflow outside Paper execution/reconciliation.
- Full portfolio allocation, rebalancing, on-chain or sentiment modules.
- Any F5/F6/F7 feature not explicitly listed in this package.

### 2.3 Non-Negotiable Safety Constraints

```text
LIVE_TRADING=false
PAPER_TRADING=true
```

- These values must remain immutable after application startup.
- Only `PaperTradingAdapter` and `FakeExchangeAdapter` may be instantiated.
- All durable business state must remain in PostgreSQL.
- Redis must remain transient-only; Redis loss must not cause loss or reconstruction of durable domain state.
- Financial quantities, prices, fees, and PnL use `Decimal` in code and `NUMERIC` in PostgreSQL.
- All timestamps are UTC-aware.
- A real network route or credential must never enter the execution path.

---

## 3. F4 Architecture

### 3.1 Execution Components

```text
F3 Signal Approval API
        │
        ▼
F2 Risk Engine (final authority)
        │
        ▼
F4 Order Execution Service
        │
        ├── PaperTradingAdapter
        ├── FakeExchangeAdapter (tests only)
        │
        ▼
PostgreSQL 16 (source of truth)
  ├── orders
  ├── positions
  ├── trades
  ├── synthetic_stops
  ├── outbox_events
  ├── dead_letter_events
  ├── audit_logs
  └── system_states
        │
        ├── Synthetic Stop Worker
        ├── Reconciliation Service / Worker
        └── Kill Switch Service (independent F2 component)
```

### 3.2 Authoritative State Rules

| Domain | Source of Truth | Prohibited Source of Truth |
|---|---|---|
| Order state | PostgreSQL | Redis / adapter memory |
| Position state | PostgreSQL | Redis / adapter memory |
| Trade/fill state | PostgreSQL | Redis / adapter memory |
| Synthetic Stop state | PostgreSQL | Process memory |
| Kill Switch state | PostgreSQL | Redis / process memory |
| Reconciliation result | PostgreSQL + audit | Redis / logs only |
| Outbox / Dead Letter | PostgreSQL | Redis |

### 3.3 Paper Adapter Rules

`PaperTradingAdapter` must:

- Be the only F4 execution adapter in non-test Paper mode.
- Have no real exchange hostname, HTTP client call, signing flow, or credential dependency.
- Persist adapter-visible order state through the application’s PostgreSQL records.
- Accept deterministic test controls for full fill, partial fill, rejection, cancellation, and delayed response.
- Support `client_order_id` idempotency.
- Return normalized adapter errors.
- Be restart-safe; application recovery must derive state from PostgreSQL, not adapter memory.

`FakeExchangeAdapter` may only be used for unit/integration tests and must never be selected in a deployed Paper runtime unless explicitly configured as a test mode.

---

## 4. Order Execution Contract

### 4.1 Permitted Inputs

An order may be handed to F4 only when all are true:

```text
1. Related signal is APPROVED.
2. Risk Engine has approved the exact order parameters.
3. Kill Switch is inactive.
4. Symbol is BTC/USDT, ETH/USDT, or BNB/USDT.
5. Direction is LONG / Spot BUY for opening position.
6. Trading mode is Paper-only.
7. Order has unique client_order_id and idempotency_key.
8. Data required by F2 risk validation is valid and not stale.
```

### 4.2 Submission Lifecycle

```text
PRE_TRADE_VALIDATION
  → SUBMITTED
  → PARTIALLY_FILLED | FILLED | CANCELLED | FAILED

PARTIALLY_FILLED
  → PROTECTED_PARTIAL
  → CANCEL_REMAINDER
  → FILLED_PARTIAL | CLOSED

FILLED
  → PROTECTED
  → CLOSED
```

Existing approved state names may be retained if they map exactly to the above semantics. Any mapping must be documented in the F4 Evidence Bundle.

### 4.3 Order Submission Rules

- Generate `client_order_id` once before submission.
- Persist the order draft and submission intent before invoking `PaperTradingAdapter`.
- Reusing the same idempotency key with the same payload returns the original result.
- Reusing the same idempotency key with a different payload returns `409 IDEMPOTENCY_CONFLICT`.
- A retry after uncertain adapter outcome must reconcile by `client_order_id` before creating a new order.
- No second active order may be created for the same signal unless the first order is terminal and auditable.
- Each transition creates an audit record and a transactional Outbox event.

### 4.4 Cancellation Rules

- Open unfilled remainder of a partially filled order must be cancelled after 60 seconds.
- Cancellation is idempotent.
- If the adapter reports already cancelled/filled, reconcile rather than fail blindly.
- Cancellation failure must be recorded; if safety cannot be determined, state becomes `MANUAL_REVIEW`.

---

## 5. Fill, Trade, and Position Contract

### 5.1 Fill Rules

- Every accepted fill creates exactly one durable `trades` record.
- Duplicate fills are prevented by unique `exchange_trade_id` where present and by idempotent fill identity where absent.
- `filled_quantity` cannot exceed order `quantity`.
- `average_fill_price` is calculated with Decimal weighted average.
- Fees are persisted with each fill.
- A fill never exists only in adapter memory.

### 5.2 Position Lifecycle

```text
NO_POSITION
  → OPEN
  → PROTECTED
  → CLOSING
  → CLOSED

Alternative states:
MANUAL_REVIEW
RECONCILIATION_FAILED
```

### 5.3 Position Creation / Update Rules

- Create or update a position in the same database transaction that persists its fill/trade representation.
- Position size equals the sum of net durable fills.
- Entry price is Decimal weighted average of opening fills.
- A partial fill creates a position only for the actually filled quantity.
- `mark_price`, realized/unrealized PnL, and status must remain consistent with persisted trades.
- A closed position has size zero and immutable historical trade records.

### 5.4 Protection Requirement

Any non-zero open Paper position must reach protection state before new discretionary execution proceeds.

```text
Filled quantity > 0
  → Synthetic Stop registered
  → Position becomes PROTECTED / PROTECTED_PARTIAL
```

If protection cannot be established:

```text
PROTECTION_FAILED
  → retry at 0s, 5s, 15s
  → MANUAL_REVIEW or cancellation/close policy
```

The retry schedule is fixed and must not be changed:

```text
Attempt 1: 0 seconds
Attempt 2: 5 seconds
Attempt 3: 15 seconds
```

---

## 6. Partial Fill Contract

### 6.1 Required Behavior

For a partially filled Paper order:

```text
1. Persist the fill and trade.
2. Create/update position only for filled quantity.
3. Register Synthetic Stop immediately for filled quantity.
4. Mark order/position as protected partial state.
5. Wait at most 60 seconds for remainder.
6. Cancel remaining unfilled quantity.
7. Reconcile final adapter order status.
8. Audit and Outbox every material transition.
```

### 6.2 Kill Switch During Partial Fill

F4 resolves carried limitation L-02 with this deterministic policy:

```text
1. Immediately freeze creation of new orders.
2. Attempt to cancel the unfilled remainder.
3. Reconcile actual filled quantity with Paper adapter.
4. Persist/update position for all filled quantity.
5. Ensure Synthetic Stop is armed for non-zero open quantity.
6. If protection is absent or uncertain, transition to MANUAL_REVIEW.
7. Do not silently close a position without a documented F4 policy decision.
8. Do not claim that an open position is closed unless a durable closing fill exists.
```

F4 default position policy under Kill Switch:

```text
OPEN PROTECTED POSITION → retain and monitor under Paper safety policy
OPEN UNPROTECTED OR UNCERTAIN POSITION → MANUAL_REVIEW + critical audit/notification
```

Automatic forced close of open positions is not introduced in F4. Any future automatic close policy requires explicit ADR and gate.

### 6.3 Acceptance Mapping

| Condition | Required Result |
|---|---|
| Partial fill | Position contains filled quantity only |
| Stop registration succeeds | Position protected |
| Remainder time reaches 60 seconds | Remainder cancellation requested |
| Cancel succeeds | Order terminal/reconciled |
| Cancel uncertain | Reconciliation + MANUAL_REVIEW if unresolved |
| Kill Switch active during partial fill | Freeze + cancel remainder + protect filled amount |
| Protection fails | Exact 0/5/15 retry then escalate |

---

## 7. Synthetic Stop Integration Contract

### 7.1 State Machine

```text
ARMED
  → TRIGGERED
  → SUBMITTING
  → SUBMITTED
  → EXECUTED
  → RECONCILED

Failure paths:
TRIGGERED → FAILED
SUBMITTING → FAILED
FAILED → MANUAL_REVIEW
FAILED → CANCELLED
```

### 7.2 F4 Integration Requirements

- Stop is created only after durable position/fill persistence.
- Stop quantity exactly equals protectable open position quantity.
- At startup, active stops are recovered from PostgreSQL.
- Stop monitoring uses approved intervals: 1H=30s, 4H=60s, 1D=300s.
- Stop trigger processing is compare-and-set / idempotent.
- Closing order uses deterministic idempotency identity.
- After stop close fill, position becomes CLOSED and stop becomes RECONCILED.
- Worker restart must not duplicate a stop close order.
- Any uncertain close is reconciled by durable IDs and adapter state.

### 7.3 Take-Profit / Trailing Boundary

F4 may persist and reconcile existing TP/trailing states only if already represented by approved schema/state-machine behavior.

F4 must not introduce a new discretionary trading algorithm, trailing model, or scaling strategy.

---

## 8. Reconciliation Contract

### 8.1 Purpose

Reconciliation confirms that PostgreSQL durable state and Paper adapter state agree for:

```text
- Orders
- Fills / trades
- Positions
- Synthetic Stops
- Available Paper balance where applicable
```

### 8.2 Reconciliation Triggers

Run reconciliation:

```text
1. Application startup
2. Kill Switch activation
3. Partial-fill timeout/cancellation completion
4. Synthetic Stop restart recovery
5. Adapter uncertainty or error
6. Before Kill Switch Resume request can be created
7. Explicit internal test/reconciliation invocation
```

### 8.3 Reconciliation Outcomes

| Result | Required System State |
|---|---|
| Fully matched | `RECONCILED` / continue according to policy |
| Recoverable mismatch | Correct from adapter-confirmed Paper state, audit correction |
| Unknown or material mismatch | `RECONCILIATION_FAILED` + `MANUAL_REVIEW` |
| Adapter unavailable | Fail closed; no new execution; `MANUAL_REVIEW` if open exposure uncertain |

### 8.4 Reconciliation Rules

- Never overwrite durable state based on uncertain adapter response.
- Every correction requires an audit record with before/after values and reason code.
- Every material reconciliation result emits an Outbox event.
- Kill Switch Resume remains blocked when any critical reconciliation mismatch exists.
- Reconciliation must be idempotent.

### 8.5 Required Reconciliation Events

```text
RECONCILIATION_STARTED
RECONCILIATION_SUCCEEDED
RECONCILIATION_CORRECTED
RECONCILIATION_FAILED
ORDER_RECONCILED
POSITION_RECONCILED
STOP_RECONCILED
```

---

## 9. Kill Switch Integration Contract

### 9.1 Existing Architecture Must Remain Intact

- Public `POST /api/v1/system/emergency-stop` remains served only by `mvp0_api:8000`.
- The independent `kill_switch` service remains internal on port 8001 and does not expose the public endpoint.
- API writes Kill Switch state to PostgreSQL.
- Kill Switch service reads state and risk heartbeat from PostgreSQL.
- Redis must not store Kill Switch durable state.

### 9.2 F4 Behavior on Activation

```text
1. Set durable Kill Switch active state.
2. Freeze new order creation.
3. Find all non-terminal Paper orders.
4. Request cancellation for open remainders.
5. Reconcile partially filled orders.
6. Ensure filled quantity has protection.
7. Reconcile all open Paper positions and active stops.
8. Mark unknown/unprotected exposure MANUAL_REVIEW.
9. Create audit and Outbox records.
10. Notify through existing approved notification abstraction if configured.
```

### 9.3 Explicit Prohibitions

- Do not assume cancellation succeeded without adapter-confirmed state.
- Do not delete active stop state because Kill Switch is active.
- Do not close positions automatically unless a durable Paper closing order/fill is produced under an approved policy.
- Do not resume while reconciliation has any critical unresolved mismatch.

---

## 10. API Scope for F4

F4 may complete existing protected API contracts only when required for Paper execution/reconciliation. No new user workflow outside this scope is allowed.

### 10.1 Permitted API Operations

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/orders` | OPERATIONAL | List Paper orders |
| GET | `/api/v1/orders/{id}` | OPERATIONAL | Get Paper order details |
| GET | `/api/v1/positions` | OPERATIONAL | List Paper positions |
| GET | `/api/v1/positions/{id}` | OPERATIONAL | Get Paper position details |
| GET | `/api/v1/system/reconciliation/status` | ADMIN | Read reconciliation status |
| POST | `/api/v1/system/reconciliation/run` | ADMIN | Trigger internal Paper reconciliation, idempotently |
| GET | `/api/v1/system/emergency-stop` | ADMIN | Existing Kill Switch state |

### 10.2 API Rules

- All protected endpoints require Bearer authentication.
- Admin-only operations reject `MVP0_API_KEY` with `403`.
- No endpoint accepts exchange credentials.
- No endpoint enables Live Trading.
- No endpoint changes `LIVE_TRADING` or `PAPER_TRADING`.
- Reconciliation run is idempotent and auditable.
- Read responses never expose secrets or credentials.

### 10.3 Error Contract

```json
{
  "code": "RECONCILIATION_FAILED",
  "message": "Paper state could not be reconciled",
  "request_id": "uuid",
  "details": {}
}
```

Expected status codes include:

| Condition | HTTP |
|---|---:|
| Missing/invalid token | 401 |
| Insufficient role | 403 |
| Order/position not found | 404 |
| Invalid state | 409 |
| Kill Switch conflict | 409 |
| Adapter or dependency unavailable | 503 |

---

## 11. Transactional Outbox and Audit Contract

### 11.1 Required F4 Audit Actions

```text
ORDER_SUBMITTED
ORDER_PARTIALLY_FILLED
ORDER_FILLED
ORDER_REMAINDER_CANCEL_REQUESTED
ORDER_CANCELLED
ORDER_RECONCILED
POSITION_CREATED
POSITION_UPDATED
POSITION_PROTECTED
POSITION_CLOSING
POSITION_CLOSED
STOP_REGISTERED
STOP_TRIGGERED
STOP_EXECUTED
STOP_RECONCILED
PROTECTION_FAILED
RECONCILIATION_STARTED
RECONCILIATION_SUCCEEDED
RECONCILIATION_CORRECTED
RECONCILIATION_FAILED
KILL_SWITCH_PARTIAL_FILL_HANDLED
```

### 11.2 Required Outbox Events

```text
ORDER_SUBMITTED
ORDER_PARTIALLY_FILLED
ORDER_FILLED
ORDER_CANCELLED
POSITION_CREATED
POSITION_UPDATED
POSITION_PROTECTED
POSITION_CLOSED
STOP_REGISTERED
STOP_TRIGGERED
STOP_EXECUTED
POSITION_CLOSED
RECONCILIATION_STARTED
RECONCILIATION_SUCCEEDED
RECONCILIATION_CORRECTED
RECONCILIATION_FAILED
KILL_SWITCH_PARTIAL_FILL_HANDLED
```

### 11.3 Transaction Rule

For every material F4 transition, all of the following must commit atomically:

```text
domain state change
+ audit record
+ outbox event
```

If any part fails, the transaction must roll back with no partial durable state.

---

## 12. F4 Test Plan

All new tests must run against PostgreSQL and Redis test infrastructure where applicable. No test may contact an external endpoint.

### 12.1 Paper Adapter Tests

```text
test_paper_adapter_never_reads_live_credentials
test_paper_adapter_never_calls_external_http
test_paper_adapter_rejects_live_mode
test_paper_adapter_accepts_unique_client_order_id
test_paper_adapter_returns_existing_order_for_duplicate_client_order_id
test_paper_adapter_full_fill_is_deterministic
test_paper_adapter_partial_fill_is_deterministic
test_paper_adapter_cancel_is_idempotent
test_paper_adapter_status_is_restart_safe
```

### 12.2 Order and Fill Tests

```text
test_risk_approved_order_submits_to_paper_adapter
test_order_submission_creates_audit_and_outbox_atomically
test_duplicate_idempotency_key_returns_original_result
test_different_payload_with_same_idempotency_key_returns_409
test_partial_fill_creates_trade_for_filled_quantity_only
test_duplicate_fill_is_not_persisted_twice
test_filled_quantity_never_exceeds_order_quantity
test_weighted_average_fill_price_uses_decimal
test_order_remainder_is_cancelled_after_60_seconds
test_cancel_uncertainty_enters_manual_review
test_order_reconciliation_corrects_recoverable_adapter_mismatch
```

### 12.3 Position and Protection Tests

```text
test_partial_fill_creates_position_for_filled_quantity_only
test_nonzero_position_requires_protection
test_protection_registration_creates_stop_and_audit_and_outbox
test_protection_failure_retries_at_0_5_15_seconds
test_protection_failure_after_third_attempt_enters_manual_review
test_position_entry_price_is_decimal_weighted_average
test_position_close_sets_size_zero_and_preserves_trade_history
test_position_cannot_be_marked_closed_without_closing_fill
test_stop_close_transitions_position_to_closed
test_worker_restart_does_not_duplicate_stop_close_order
```

### 12.4 Partial Fill and Kill Switch Tests

```text
test_partial_fill_is_protected_before_remainder_cancel
test_partial_fill_remainder_cancelled_after_60_seconds
test_kill_switch_during_partial_fill_freezes_new_orders
test_kill_switch_during_partial_fill_cancels_unfilled_remainder
test_kill_switch_during_partial_fill_protects_filled_quantity
test_kill_switch_during_partial_fill_unprotected_quantity_enters_manual_review
test_kill_switch_does_not_claim_position_closed_without_fill
test_kill_switch_keeps_active_stop_state_persistent
```

### 12.5 Reconciliation Tests

```text
test_reconciliation_runs_on_startup
test_reconciliation_matches_order_position_trade_and_stop_state
test_reconciliation_repairs_recoverable_paper_state_mismatch
test_reconciliation_material_mismatch_enters_manual_review
test_reconciliation_failure_blocks_kill_switch_resume
test_reconciliation_is_idempotent
test_reconciliation_creates_audit_and_outbox_events
test_reconciliation_run_endpoint_requires_admin
test_reconciliation_run_endpoint_is_idempotent
test_adapter_unavailable_during_reconciliation_fails_closed
```

### 12.6 API Tests

```text
test_list_orders_requires_operational_key
test_get_order_requires_operational_key
test_list_positions_requires_operational_key
test_get_position_requires_operational_key
test_reconciliation_status_requires_admin_key
test_reconciliation_run_requires_admin_key
test_operational_key_rejected_for_reconciliation_run
test_reconciliation_response_has_no_secret
test_order_and_position_not_found_return_404
```

### 12.7 Mandatory Regression Tests

All F1/F2/F3 tests must remain green. The following tests are explicitly mandatory:

```text
test_redis_unavailable_does_not_lose_postgres_state
test_paper_environment_has_no_live_exchange_endpoint
test_kill_switch_persists_after_restart
test_kill_switch_blocks_new_orders
test_resume_requires_admin_and_operator_roles
test_synthetic_stop_triggers_only_once
test_protection_failure_retry_schedule_is_0_5_15_seconds
test_outbox_dead_letter_after_max_retries
test_dead_letter_replay_creates_admin_audit_record
test_signal_engine_uses_closed_candles_only
test_price_drift_expires_signal
test_decision_log_is_read_only
test_no_live_order_is_submitted_in_any_failure_scenario
```

### 12.8 F4 Failure-Recovery Tests

The following are F4-level integration/recovery tests, not F5 OS-level chaos drills:

```text
test_execution_service_recovers_after_adapter_timeout
test_uncertain_submission_reconciles_by_client_order_id
test_restart_recovers_pending_cancellation
test_restart_recovers_protection_failed_state
test_restart_recovers_active_position_and_stop
test_database_reconnect_preserves_paper_order_and_position_state
test_redis_reconnect_does_not_change_execution_or_kill_switch_state
```

---

## 13. Quality Gates

| Area | Minimum Requirement |
|---|---:|
| Whole `app/` line coverage | ≥ 80% |
| Whole `app/` branch coverage | ≥ 80% |
| `paper.py` / PaperTradingAdapter | ≥ 90% |
| `order` execution service | ≥ 90% |
| `position` service | ≥ 90% |
| `synthetic_stop.py` | ≥ 90% |
| `reconciliation.py` | ≥ 90% |
| `kill_switch.py` | ≥ 90% |
| `outbox.py` | ≥ 90% |
| `ruff check .` | zero errors |
| `ruff format --check .` | zero diffs |
| `mypy --strict app` | zero errors |
| F4 tests | 100% pass |
| F1/F2/F3 regression tests | 100% pass |
| Security scan | zero HIGH and CRITICAL dependency vulnerabilities |
| Docker image scan | zero CRITICAL vulnerabilities |
| Paper isolation tests | 100% pass |
| Real exchange / credential scan | zero findings |

---

## 14. F4 Required Deliverables

The implementer must provide:

1. F4 source implementation limited to this package.
2. Any required Alembic migration, with apply/rollback evidence.
3. All F4 unit, integration, API, reconciliation, and recovery tests.
4. Updated API documentation and runbooks.
5. CI, Security, Docker, and Paper isolation evidence.
6. Line and branch coverage reports.
7. `MVP0_F4_Completion_Evidence_v1.0.md` as a self-contained Evidence Bundle.
8. `F4_REMEDIATION_MANIFEST.md` in repository root.
9. A candidate branch/tag and full commit SHA.
10. Explicit list of `NOT IMPLEMENTED` items and their target phase.

---

## 15. F4 Evidence Bundle Protocol

The Evidence Bundle must be self-contained. No claim is auditable without:

```text
- Full commit SHA
- Branch and tag
- File path and line range or function name
- Test ID
- PASS/FAIL result
- CI Run ID, Job ID, and step name
- Actual log excerpt or linked included artifact
```

Required file:

```text
MVP0_F4_Completion_Evidence_v1.0.md
```

### 15.1 Required Evidence Structure

```markdown
# MVP-0 F4 Completion Evidence v1.0

## 0. Metadata

| Field | Value |
|---|---|
| Phase | F4 — Paper Execution & Reconciliation |
| Implementation Package | MVP0_F4_Paper_Execution_Reconciliation_Implementation_Package_v1.0.md |
| Parent Contract | MVP0_Implementation_Contract_v1.2_FINAL.md |
| F1 Gate | ACCEPTED |
| F2 Gate | ACCEPTED |
| F3 Gate | ACCEPTED |
| Branch | |
| Tag | |
| Code Commit SHA | |
| Evidence Commit SHA | |
| CI Run ID | |
| CI Job ID | |
| Security Run ID | |
| Docker / Compose Run ID | |
| Date | |
| Implementer | |

## 1. Scope Delivered

| Requirement | Source path/function | Test ID | CI step | Result |
|---|---|---|---|---|

## 2. Scope Not Delivered

| Requirement | Status | Reason | Target phase |
|---|---|---|---|

## 3. CI and Coverage

| Gate | Command | Exit code | Result | Log excerpt |
|---|---|---:|---|---|

| Coverage scope | Required | Actual | Result | Artifact evidence |
|---|---:|---:|---|---|

## 4. Paper Execution Mapping

| Contract behavior | Actual test ID | Result | Evidence |
|---|---|---|---|
| Paper-only adapter | | | |
| Unique client order identity | | | |
| Full fill | | | |
| Partial fill | | | |
| Duplicate fill prevention | | | |
| 60-second remainder cancellation | | | |
| Protection registration | | | |
| Protection retry 0/5/15 | | | |
| Stop-triggered close | | | |
| Restart recovery | | | |

## 5. Reconciliation Mapping

| Contract behavior | Actual test ID | Result | Evidence |
|---|---|---|---|
| Startup reconciliation | | | |
| Order reconciliation | | | |
| Trade reconciliation | | | |
| Position reconciliation | | | |
| Stop reconciliation | | | |
| Recoverable correction | | | |
| Material mismatch/manual review | | | |
| Resume blocked on mismatch | | | |
| Idempotent reconciliation | | | |

## 6. Kill Switch / Partial Fill Mapping

| Contract behavior | Actual test ID | Result | Evidence |
|---|---|---|---|
| Freeze new orders | | | |
| Cancel unfilled remainder | | | |
| Protect filled quantity | | | |
| Unknown/unprotected → manual review | | | |
| Persistent active stop | | | |
| No false closed-position claim | | | |

## 7. Safety and Environment

| Control | Result | Evidence |
|---|---|---|
| LIVE_TRADING=false | | |
| PAPER_TRADING=true | | |
| No real adapter | | |
| No real credential | | |
| No external execution endpoint | | |
| Redis transient-only | | |
| Paper network isolation | | |
| No secret in logs | | |

## 8. Open Items / Carried Limitations

| ID | Item | Severity | Status | Target phase |
|---|---|---|---|---|
| L-01 | OS-level SIGKILL validation | Medium | NOT IMPLEMENTED | F5 |
| L-02 | [resolved / remaining policy] | | | |
| L-03 | [resolved / remaining position policy] | | | |

## 9. Implementer Declaration

All claims in this Evidence Bundle are supported by source paths, tests,
CI run IDs, and log excerpts: YES / NO

No F5/F6/F7 or Live Trading feature was introduced: YES / NO

Ready for auditor review: YES / NO
```

---

## 16. F4 Acceptance Criteria

F4 is complete only when all criteria below are satisfied:

```text
1. All execution is Paper-only.
2. No real endpoint, adapter, credential, or Live path exists.
3. Every order has durable idempotency identity.
4. Duplicate submissions and fills are prevented.
5. Full and partial fills create durable trades and consistent positions.
6. Partial fill is protected immediately.
7. Unfilled remainder is cancelled after 60 seconds.
8. Protection failure follows exactly 0s, 5s, 15s retry schedule.
9. Synthetic Stop close is idempotent and reconcilable.
10. Position cannot be marked CLOSED without durable closing fill.
11. Kill Switch partial-fill handling follows F4 policy.
12. Reconciliation covers order, trade, position, and stop state.
13. Reconciliation failure blocks Kill Switch Resume.
14. All F1/F2/F3 regressions remain green.
15. All F4 tests pass.
16. Quality, security, Docker, and Paper-isolation gates pass.
17. Evidence Bundle and Manifest are complete and self-contained.
18. Auditor issues F4 ACCEPTED — F5 AUTHORIZED.
```

---

## 17. Implementation Rules for Developer

- Begin only from the approved F3 baseline/tag.
- Work in a dedicated F4 branch, for example `feature/f4-paper-execution-reconciliation`.
- Do not alter the `f3-accepted` tag or F3 Evidence.
- Do not start F5/F6/F7.
- Do not use or create a Live network, Live container, Live adapter, external exchange URL, or credentials.
- Keep Paper network isolated.
- Use PostgreSQL for all durable transitions.
- Use Redis only transiently.
- Prefer existing F2/F3 services and models; add migrations only when required and documented.
- If a requirement conflicts with existing schema or state names, stop and document the discrepancy before coding.
- Never claim a safety action succeeded without durable adapter-confirmed state.

---

## 18. F4 Exit Gate

F4 is accepted only when the auditor receives and accepts:

```text
MVP0_F4_Completion_Evidence_v1.0.md
F4_REMEDIATION_MANIFEST.md
candidate branch/tag and full commit SHA
CI / Security / Docker / Coverage evidence
all F4 tests and F1/F2/F3 regressions
```

The exact authorization required before F5 is:

```text
F4 ACCEPTED — F5 AUTHORIZED
```

Until that written decision:

```text
F5 remains BLOCKED.
F6 remains BLOCKED.
Live Trading remains forbidden.
```
