# MVP0 F4 — Paper Execution & Reconciliation Implementation Package

Document ID: MVP0-F4-IMP-001
Version: 1.1
Date: 2026-10-06
Status: SUBMITTED FOR AUDITOR REVIEW — NOT A START CLEARANCE
Supersedes: MVP0_F4_Paper_Execution_Reconciliation_Implementation_Package_v1.0.md and all duplicate copies.
Parent: MVP0_Implementation_Contract_v1.2_FINAL.md
Master reference: MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md
Decision reference: MVP0-F4-PRESTART-DECISIONS-001 / Rev 1.0

This document is self-contained. The implementer must not combine conflicting instructions from v1.0 with v1.1. If the parent contract or a written auditor decision conflicts with this package, stop and request resolution. No amendment here asserts that implementation or runtime verification has occurred.

## 0. Revision control and authorization

F1/F2/F3: ACCEPTED — CLOSED.
F4: AUTHORIZED — NOT STARTED; package approval and workspace clearance remain required.
F5/F6/F7: UNAUTHORIZED.

Technical baseline: 9cf204d88fbcc1af0428331f866348a013f6aec0 (f3-accepted).
Approved working start: c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4.
Approved fixed branch exception: arena/01a0fca1-crypto-management-portfolio.
The technical baseline and working start are different intentionally: the latter includes subsequent F3 documentation. Do not change the accepted tag.

### Changelog and traceability

| Finding | Revision 1.1 resolution | Sections |
|---|---|---|
| S-01 | Explicit Position states, guards and lifecycle | 5 |
| S-02 | Persistent first-fill deadline, cancellation confirmation | 4, 6 |
| S-03 | RECONCILED aligned across enum/ORM/constraint by new migration | 7 |
| S-04 | Stable non-null fill identity and deduplication | 5 |
| S-05 | Per-entry-order Position aggregation | 5 |
| S-06 BLOCKER | Removes ambiguous cancellation/close escalation; MANUAL_REVIEW only after final protection failure | 5.4, 6, 9 |
| S-07 BLOCKER | Replaces duplicated/incomplete Outbox list with 18 unique events; explicitly distinguishes 3 Audit-only actions | 11 |
| R-1 | No CLOSED without durable closing fills and zero open quantity | 5, 12 |
| R-2 | Durable Paper adapter ledger, memory is rebuildable cache only | 3, 12 |
| R-3 | Preserve valid stops; distinguish protective exits from forced liquidation | 6, 9 |
| R-4 | Atomic DB units and failure-injection evidence | 8, 11, 12 |

Master traceability: scope and Paper isolation — §§1.3/12.3; fill and protection — §§7.1–7.3; stops — §5.2 and final engineering appendices; Kill Switch — §§11.3–11.4; tests — §§9.1/9.4; runbooks — §13.7. The phase labels here are implementation phases, not similarly named Post-MVP roadmap or test-layer labels.

## 1. Objective

Complete Paper execution, durable fills/trades, Position lifecycle, protection and reconciliation using approved F2/F3 components. Resolve carried limitations L-02 (partial-fill Kill Switch behavior) and L-03 (Position lifecycle). L-01 (OS-level SIGKILL hardening) remains assigned to F5.

Flow: approved signal → risk-approved order intent → Paper submission → partial/full fill → Position → protection → authorized protective exit → closed Position → reconciliation.

## 2. Scope and safety

In scope: Paper/Fake adapter behavior, submission/cancellation/status, fill deduplication, Position aggregation and close, partial-fill deadlines, Synthetic Stop integration, reconciliation, existing Kill Switch integration, protected read APIs, reconciliation APIs, Audit/Outbox, tests and evidence.

Forbidden: Live Trading, Direct Mode, real exchange URLs/adapters/credentials/signing/withdrawal, external exchange HTTP calls, short/margin/leverage/derivatives, ML/JEV/Go/Vault/TimescaleDB/RLS/multi-tenancy, new strategy types, Dashboard/PWA, F5 OS-level drills and F6/F7 work.

LIVE_TRADING=false and PAPER_TRADING=true are startup-validated and immutable. Runtime Paper execution has no external egress. Only PaperTradingAdapter and FakeExchangeAdapter are allowed; Fake is test-only unless explicitly selected for a declared test runtime. Prices, quantities, fees and PnL: Decimal/NUMERIC; timestamps: UTC-aware. Redis is transient cache/coordination only, never domain source of truth.

## 3. Architecture and Paper adapter durability

Public API remains on port 8000; independent Kill Switch health/service remains internal on port 8001. No public emergency-stop route is added to the internal service. PostgreSQL holds all durable domain state.

Paper adapter must provide normalized submission, lookup by client_order_id, cancellation, fill/status and deterministic test controls. Its execution intent, simulated order/fill identities and adapter-visible state required for recovery must persist in PostgreSQL. Memory is a reconstructible cache, not authoritative storage.

Reconciliation must compare independently identifiable Paper adapter ledger records with application domain projections; comparing a record to itself is not meaningful reconciliation. Reuse suitable existing records or introduce documented adapter-ledger tables through forward migrations. Specify their schema and transaction boundaries before ingestion. No independent remote exchange is needed.

Unknown submission outcome: reconcile by client_order_id before retry; never mint a new identity blindly. External network access is not required for simulation. Replay/restart must retain stable simulated fills and order identities.

## 4. Order lifecycle and idempotency

Opening submission requires: approved signal, risk approval of exact parameters, inactive Kill Switch, allowed BTC/USDT/ETH/USDT/BNB/USDT Spot LONG entry, fresh valid risk inputs and durable unique identities.

States/semantics:
PRE_TRADE_VALIDATION → SUBMITTED → PARTIALLY_FILLED or FILLED or CANCELLED or FAILED.
PARTIALLY_FILLED → PROTECTED_PARTIAL after filled quantity has valid protection.
PARTIALLY_FILLED/PROTECTED_PARTIAL → CANCEL_REMAINDER when deadline or Kill Switch requests cancellation.
After re-reading adapter: full fill → FILLED; cancelled remainder and nonzero fills → FILLED_PARTIAL; no fill and cancelled → CANCELLED; uncertain result → MANUAL_REVIEW.
A filled order may be marked PROTECTED according to its protected Position. Order terminality does not imply Position closure. Do not introduce Order CLOSED solely because entry remainder was cancelled. Existing enum mappings must be explicit and tested.

Persist first_partial_fill_at once and remainder_cancel_due_at = first_partial_fill_at + 60 seconds. Subsequent fills/restarts never extend it. An overdue recovered order is processed on the first available cycle. Poll deadline at most every second in normal operation; record requested/actual cancellation timestamps and scheduling delay. The deadline requires initiating cancellation, not guaranteeing adapter completion at an exact wall-clock instant.

Same client_order_id or request idempotency key + identical canonical payload → original result. Same identity + different payload → 409 IDEMPOTENCY_CONFLICT. Atomic uniqueness and transactional reservation must protect concurrent requests. Persist intent before adapter action, then reconcile outcome. Do not hold a long DB transaction across adapter waits.

## 5. Fills and Positions

### 5.1 Fill identity

Each fill has a non-null durable fill identity, unique within adapter/account scope. Paper adapter generates and persists it when the fill is first created, then reuses it for retries/reconciliation. Separate legitimate equal-price/equal-quantity fills remain distinguishable. Do not generate a new random identity on every retry; do not use price/quantity/timestamp alone as dedupe identity. An ambiguous fill is held for MANUAL_REVIEW, not silently ingested twice.

Document backfill and uniqueness strategy for existing rows before enforcing NOT NULL/unique constraints. exchange_trade_id may be retained as an additional identity, not the only nullable fallback.

### 5.2 Aggregation and arithmetic

One Position per entry order; fills of that entry order aggregate there. Distinct entry orders never merge solely by account/symbol. Exit orders reference the target Position; opening and closing trades reference that same Position. Application Position update and accepted domain fill persist atomically with Audit and relevant Outbox. Use Decimal weighted-average entry price, durable fees and quantities. Filled order quantity cannot exceed requested quantity; exits cannot exceed remaining open quantity. Do not silently clamp inconsistent fills.

### 5.3 Position state machine

States: OPEN, PROTECTED, CLOSING, CLOSED, MANUAL_REVIEW, RECONCILIATION_FAILED.
NO_POSITION means no row, not an additional persistent state.

OPEN → PROTECTED only with durable valid protection for open quantity.
OPEN/PROTECTED → CLOSING only with persisted authorized exit intent.
CLOSING → CLOSED only after durable closing fills and open_qty=0.
CLOSING → OPEN/PROTECTED after incomplete/failed exit reconciliation, according to actual open quantity and valid protection.
Any nonterminal state → MANUAL_REVIEW or RECONCILIATION_FAILED on uncertainty/material mismatch.
Recovery from review/failure requires documented reconciliation and destination guards.
CLOSED is final; a new entry creates a new Position.

State transitions must lock/check version, validate invariants and persist required Audit/Outbox atomically. A Position cannot be declared CLOSED by a direct state-only update.

### 5.4 Protection failure policy — S-06 corrected

Any nonzero open quantity requires protection. Failure initiates exactly three attempts at t=0s, t=5s and t=15s relative to protection-failure sequence start. Persist attempt count, next due time and outcome; restart does not reset the schedule or duplicate registration. Each attempt uses a bounded timeout; a long/hung attempt must not lead to overlapping blind duplicate attempts. Record missed deadlines and reconcile uncertain results.

After the third failed attempt: MANUAL_REVIEW, block new entry orders, persist reason/Audit/Outbox and raise a critical alert. No automatic forced close is permitted as an escalation for failed protection or Kill Switch activation. Cancellation of an unfilled remainder is not closure of a Position.

A previously valid Synthetic Stop remains available for legitimate, Paper-only, idempotent protective execution. This is not discretionary forced liquidation. Never mark CLOSED without closing fills and zero remaining open quantity.

## 6. Partial fills

Persist accepted fill → update Position for filled quantity only → register protection immediately → wait only until original durable deadline → request remainder cancellation → re-read adapter → reconcile → persist resulting state and events.

Kill Switch during partial fill: freeze new entries; request remainder cancel; reconcile all actual fills including fills racing with cancellation; protect resulting nonzero quantity; unresolved/unprotected exposure → MANUAL_REVIEW and critical alert. Preserve existing valid stops. Do not silently force-close or falsely report closure.

Protection coverage must be adjusted idempotently for additional fills. The same position must not acquire duplicate active protection records.

## 7. Synthetic Stop and migrations

States: ARMED → TRIGGERED → SUBMITTING → SUBMITTED → EXECUTED → RECONCILED. Failure paths → FAILED → MANUAL_REVIEW or safely CANCELLED where no unresolved exposure is abandoned. Reconcile uncertain submissions before retry.

Align RECONCILED in enum, ORM and PostgreSQL CHECK constraint via a new F4 migration. Do not edit accepted migrations. Derive revision identifier from actual migration head. Test upgrade/downgrade on disposable PostgreSQL. Downgrade with incompatible persisted states must explicitly refuse or use a separately approved conversion; never silently erase financial history.

Recover active stops on startup. Monitoring intervals: 1H=30s; 4H=60s; 1D=300s. Trigger LONG at price <= stop_price with valid fresh input. Stop close uses persistent idempotency identity and closes Position only through durable exit fills. No duplicate close on restart.

TP/trailing: integrate only already-approved behavior/schema; no new discretionary strategy. If unsupported, declare NOT IMPLEMENTED and identify target phase; do not invent policy to make a test pass.

## 8. Reconciliation

Compare durable application orders, trades, Positions, stops and applicable Paper balance with identifiable adapter-ledger state. Tolerance must follow stored precision/tick/step rules; material mismatches are not dismissed by arbitrary epsilon.

Triggers: startup; Kill Switch; partial-fill timeout/cancel completion; stop recovery; adapter uncertainty; before Resume eligibility; explicit internal/API invocation.

Outcomes: matched → success; recoverable adapter-confirmed difference → audited correction; material/unknown difference → RECONCILIATION_FAILED/MANUAL_REVIEW and block new entries and Resume; adapter unavailable → fail closed, preserve unresolved exposure.

Persist run identity, scope, STARTED/SUCCEEDED/FAILED state, timestamps, discrepancy details and Resume-blocking results. Add forward migration if no suitable structure exists. Long runs may use several atomic units; each domain correction commits with Audit and its Outbox event. Run completion must not be declared before all required units finish. Restart handles incomplete runs safely. Repeated reconciliation is idempotent.

## 9. Kill Switch integration

Keep existing independent service, PostgreSQL state/heartbeat and Admin-only public endpoint architecture. Freeze entries, cancel open remainders, reconcile partial fills and open Positions/stops, preserve valid protection, and escalate uncertainty. Do not delete/disable ARMED protection merely due to Kill Switch activation.

Protective exit of a valid Stop is allowed through the controlled Paper path while new entries are blocked. No forced liquidation on activation or final protection failure. Resume remains blocked by unresolved critical reconciliation differences. Existing 24-hour dual-approval policy remains unchanged.

## 10. API contracts

| Method | Path | Role |
|---|---|---|
| GET | /api/v1/orders | OPERATIONAL or ADMIN |
| GET | /api/v1/orders/{id} | OPERATIONAL or ADMIN |
| GET | /api/v1/positions | OPERATIONAL or ADMIN |
| GET | /api/v1/positions/{id} | OPERATIONAL or ADMIN |
| GET | /api/v1/system/reconciliation/status | ADMIN only |
| POST | /api/v1/system/reconciliation/run | ADMIN only |
| GET | /api/v1/system/emergency-stop | ADMIN only |

ADMIN means MVP0_ADMIN_API_KEY; operational key receives 403 on Admin-only routes. Invalid/missing token → 401; absent entity → 404; invalid state/idempotency conflict → 409; unavailable dependency → 503. Errors include stable code/message/request_id, never secrets.

Reconciliation POST requires Idempotency-Key, normalized scope and reason; same request returns original run; same key with changed payload returns 409. Persist run before processing. Return 202 with run_id/status/request_id when asynchronous, and expose run result through status endpoint with run_id filter. Read list endpoints support bounded pagination; money is serialized as Decimal strings and dates UTC ISO-8601. No credential/trading-mode enablement API.

## 11. Canonical Audit and Outbox contract — S-07 corrected

The following 18 distinct names require BOTH Audit and Outbox when the corresponding material transition occurs:

| Name | Audit | Outbox |
|---|---|---|
| ORDER_SUBMITTED | Yes | Yes |
| ORDER_PARTIALLY_FILLED | Yes | Yes |
| ORDER_FILLED | Yes | Yes |
| ORDER_REMAINDER_CANCEL_REQUESTED | Yes | Yes |
| ORDER_CANCELLED | Yes | Yes |
| POSITION_CREATED | Yes | Yes |
| POSITION_UPDATED | Yes | Yes |
| POSITION_PROTECTED | Yes | Yes |
| POSITION_CLOSED | Yes | Yes |
| STOP_REGISTERED | Yes | Yes |
| STOP_TRIGGERED | Yes | Yes |
| STOP_EXECUTED | Yes | Yes |
| PROTECTION_FAILED | Yes | Yes |
| RECONCILIATION_STARTED | Yes | Yes |
| RECONCILIATION_SUCCEEDED | Yes | Yes |
| RECONCILIATION_CORRECTED | Yes | Yes |
| RECONCILIATION_FAILED | Yes | Yes |
| KILL_SWITCH_PARTIAL_FILL_HANDLED | Yes | Yes |

Additional Audit-only actions: ORDER_RECONCILED, POSITION_CLOSING, STOP_RECONCILED. A corresponding material domain transition still requires its listed Outbox event. An Audit-only action does not waive transactional consistency. F1–F3 event contracts are retained.

POSITION_CLOSED is listed once. ORDER_REMAINDER_CANCEL_REQUESTED and PROTECTION_FAILED are included. Success name is RECONCILIATION_SUCCEEDED, not an undocumented COMPLETED alias.

Domain changes + Audit + Outbox INSERT commit in one PostgreSQL transaction. Publication is AFTER commit. Versioned event includes stable event_id, aggregate identity, timestamp and payload. Existing retry/DLQ/Admin replay contracts remain in force. Fault-injection rollback must prove no partial durable changes.

## 12. Test plan — eight groups

Counts alone do not establish compliance. Map every behavior below to an actual pytest node ID and result; different names are acceptable with equivalent assertions. Use PostgreSQL/Redis test infrastructure for persistence/connectivity tests; pure arithmetic/unit tests need not unnecessarily connect to DB. No external exchange calls. Supply fresh virtual clock/input timestamps where appropriate; OS SIGKILL drills remain F5.

### 12.1 Paper adapter

- No live credential dependency, external HTTP or live-mode selection.
- Stable client_order_id lookup; identical-payload replay and conflicting-payload rejection.
- Deterministic full/partial fill simulation.
- Idempotent cancellation.
- Restart-safe adapter ledger and identity recovery.

### 12.2 Orders and fills

- Risk-approved exact parameters required for submission.
- Domain/Audit/Outbox atomic success and injected-failure rollback.
- Concurrent duplicate request prevention and payload conflict.
- Partial fill records only actual quantity.
- Duplicate fill suppression; legitimate identical-price fills remain separate.
- No overfill; Decimal weighted-average prices and fees.
- Original 60-second cancellation deadline and re-read adapter result.
- Uncertain cancellation enters review; recoverable order mismatch corrected.

### 12.3 Position/protection

- Per-entry-order aggregation and exit linkage.
- Nonzero quantity requires valid protection; additional fills update coverage.
- Explicit allowed/forbidden transitions.
- Exact 0/5/15 retry schedule, persisted across recovery.
- Final failure goes to review, no forced close.
- Durable close fills/zero quantity required; negative closure test.
- Closing history retained; stop close idempotent after restart.

### 12.4 Partial fill/Kill Switch

- Protection immediately for filled quantity.
- Deadline not extended by later fill/restart.
- Freeze entries and cancel remainder on Kill Switch.
- Fill racing cancellation reconciled and protected.
- Uncertain exposure goes to review and blocks Resume.
- Valid ARMED stop retained and permitted protective exit.
- No state-only/falsely claimed closure.

### 12.5 Reconciliation

- All seven triggers.
- Compare order/trade/Position/stop/appropriate balance.
- Independently identified ledger/projection mismatch injection.
- Audited recoverable repair and unresolved mismatch blocking.
- Durable run state, incomplete-run restart and idempotency.
- Resume blocked on critical differences.
- Atomic correction rollback under failure.
- Adapter outage is fail-closed.

### 12.6 API

- Auth for four order/Position reads, missing-entity 404.
- Admin-only status/run/emergency-stop, operational key 403.
- Reconciliation POST idempotency, payload conflict and durable run response.
- No secrets in reads/errors; bounded pagination and serialization.

### 12.7 F1/F2/F3 regressions

Run the complete previously accepted regression suite, including Redis durability isolation, Paper isolation, Kill Switch persistence/entry blocking, dual approval, Synthetic Stop dedupe/retries, DLQ/Admin replay, closed-candle Signal rules, drift expiry, readonly Decision API, 16 E2E and 13 Chaos mappings. Retained tests must not be disabled solely to meet F4 thresholds.

### 12.8 Failure recovery

- Adapter timeout with lookup-before-retry.
- Pending cancellation restart and overdue deadline processing.
- Protection-failure schedule recovery.
- Position/Stop recovery and no duplicate protective exit.
- DB reconnect preserves durable ledger/domain/outbox.
- Redis reconnect does not determine durable state.
- Simulation level (mock/connection/process/container) disclosed honestly.

## 13. Quality gates

| Scope | Threshold |
|---|---|
| Whole app line coverage | >=80% |
| Whole app branch coverage | >=80% |
| Paper adapter, execution, Position, Synthetic Stop, reconciliation, Kill Switch, Outbox modules | each >=90% line coverage |
| ruff check / format check / mypy --strict app | zero errors |
| F4 mandatory behavior mapping and prior regressions | 100% pass |
| Dependency HIGH/CRITICAL | zero |
| Container CRITICAL | zero |
| Real exchange/credential and Paper isolation checks | zero violations |

Distinguish line, branch and combined coverage metrics; never label combined coverage as branch-only. Provide machine-readable artifacts and per-module report. Module restructuring requires explicit equivalent coverage mapping, not dropping gates.

## 14. Ten required completion deliverables

1. F4 source implementation, limited to scope.
2. New forward migration(s), schema explanation, backfill and disposable DB apply/rollback evidence.
3. All eight groups of tests and prior regression results.
4. API documentation and operational runbooks.
5. CI/security/Docker/Paper isolation logs.
6. Line/branch and per-module coverage artifacts.
7. MVP0_F4_Completion_Evidence_v1.0.md.
8. F4_REMEDIATION_MANIFEST.md in root.
9. Full code/document SHA, approved branch and candidate tag if used.
10. Explicit NOT IMPLEMENTED/carried-limitations list with target phase.

These are completion outputs, not prerequisites for authorizing initial coding.

## 15. Evidence and artifact delivery

Evidence must be actually attached/transferred to the auditor, not merely said to exist in a repository. One self-contained completion document with sections 0–9:

0 Metadata: package v1.1; gate records; technical baseline; working start; full code SHA; evidence SHA reported after commit; branch; CI/job IDs; dates.
1 Delivered scope with source/function, test node ID and raw execution evidence.
2 Not-delivered scope and target phase.
3 CI/coverage: exact commands, exit codes, excerpts, raw artifacts, line/branch distinction and module gates.
4 Paper execution mapping.
5 Reconciliation mapping.
6 Kill Switch/partial-fill mapping.
7 Safety/environment checks.
8 Open items and carried limitations.
9 Implementer declaration: truthful evidence-backed findings; ready/not-ready for review.

Use PASS/FAIL/NOT RUN, never prefill PASS. CI IDs alone are insufficient. All code/log/artifacts must identify the same tested source SHA; documentation descendants are allowed if code differences are zero and shown. Do not amend a commit repeatedly trying to embed its own SHA inside itself; report final SHA in delivery message/separate receipt.

Manifest: exact included paths, file sizes and full SHA-256, source SHA, CI mapping, exclusions and simulation limitations. Do not require .git in ZIP; use Git outputs for ref/history evidence. Inspect archive before transfer. Audit receipt must enumerate files actually received; absent input is NOT REVIEWED, not proof of absent repository code.

Keep accepted historical packages unchanged. Candidate tags must not overwrite accepted tags. Baseline readiness uses a separate Assessment, not completion artifacts.

## 16. Eighteen acceptance criteria

1. Paper-only immutable mode.
2. No real exchange path or credential.
3. Durable order idempotency identity.
4. Duplicate submission/fill prevention.
5. Durable fills, fees and consistent per-entry-order Positions.
6. Immediate protection of partial fills.
7. Durable original 60-second cancellation deadline and confirmed cancellation reconciliation.
8. Exact protection retry/escalation policy.
9. Idempotent recoverable stop close.
10. No CLOSED without durable closing fills and zero open quantity.
11. Approved partial-fill Kill Switch handling; valid protection retained.
12. Complete ledger/domain reconciliation.
13. Critical mismatch blocks Resume.
14. All accepted prior regressions remain green.
15. All F4 required behaviors tested successfully.
16. Coverage, quality, security, Docker and isolation gates pass.
17. Actual self-contained evidence and manifest delivered and inspected.
18. Written auditor decision: F4 ACCEPTED — F5 AUTHORIZED.

## 17. Implementation and pre-start rules

Package v1.1 approval is not itself completion acceptance or workspace clearance. Before code starts: approved S/R decisions plus fixed-branch exception, recovery of owner-held local-file content, safe workspace alignment to working start, and written F4 CLEARED FOR IMPLEMENTATION.

Use fixed SHA, not mutable FETCH_HEAD. Nonforce fetch allowed. No reset --hard/clean/force-push/retag. Preserve local files before narrow restore; do not pretend remote versions are original lost backups. Record unavailable temporary artifacts. A documentation-only descendant of working start is allowed and diff must prove no production change.

README: F3 ACCEPTED — CLOSED; F4 AUTHORIZED — NOT STARTED until coding actually starts. Then record IN PROGRESS truthfully. Do not silently change approved tags or F3 evidence. Stop for unresolved schema/policy conflicts; obtain specific decision, not repeated full audit of stale files.

## 18. Exit gate

Auditor reviews the ten deliverables, all eighteen acceptance criteria and evidence identity. Missing artifacts → REQUIRES EVIDENCE; proven implementation problems → REQUIRES CHANGES. F4 starts only after start clearance and closes only on written:

F4 ACCEPTED — F5 AUTHORIZED

Until then F5/F6/F7 remain unauthorized. Live Trading remains outside MVP-0 even after F4; it requires a separate scope decision, ADR and authorization.
