# MVP-0 Phase F3 (Signal & Approval) — Completion Evidence v1.0

**Document Version:** v1.0
**Date:** 2026-10-04
**Phase:** F3 — Signal & Approval (Rule-Based Signal Engine, Approval API, Decision Log API, and Risk Engine Order Handoff)
**Target Status:** Submitted for F3 Gate Review (`F1: ACCEPTED`, `F2: ACCEPTED`, `F3: SUBMITTED FOR ACCEPTANCE`, `F4: BLOCKED`)
**Branch:** `arena/01a0fca1-crypto-management-portfolio`
**Code Commit SHA:** `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (F3 feature commit `27e01ff7ce33da6c31199fe5d256b1ccd5b9f1c7` + fixture/format fix `f5f4192f83679cf167d0cd24d17a52bbc38dcc72`)
**Release Tag:** `release/f3-candidate` (`38f41ec` -> `f5f4192f83679cf167d0cd24d17a52bbc38dcc72`)
**Baseline F1 Accepted Tag:** `release/f1-candidate` (`bdff565d1b46222bd15340a0fe0ba3e76dd7411b`)
**Baseline F2 Accepted Tag:** `release/f2-candidate` (`77a042ca6f61f27bfcad1a41497c626807bc4361` / code `5e7758846169614daeb39e3f5346037f245af856`)
**GitHub Actions Run IDs on `f5f4192f83679cf167d0cd24d17a52bbc38dcc72`:**
- **CI (Python 3.12 Lint, Typecheck, Migrate, F2/F3 Unit/Integration/E2E/Chaos & Coverage Gates):** Run ID `37176837120` (Job ID `111361102612`) — `conclusion: "success"` (`2026-10-04T04:22:53Z` -> `2026-10-04T04:25:01Z`)
- **Security & Paper Isolation Scan:** Run ID `37176837087` (Job ID `111361102389`) — `conclusion: "success"` (`2026-10-04T04:22:53Z` -> `2026-10-04T04:23:39Z`)
- **Docker Build & Compose Validation:** Run ID `37176837077` (Job ID `111361102354`) — `conclusion: "success"` (`2026-10-04T04:22:53Z` -> `2026-10-04T04:26:17Z`)

---

## 1. Document Hierarchy & Scope Governance

This F3 implementation and evidence bundle strictly obeys the Auditor-mandated document hierarchy:
1. **Written Auditor Decision:** `F1: ACCEPTED`, `F2: ACCEPTED`, `F3: AUTHORIZED`, `F4: BLOCKED`
2. **`MVP0_Implementation_Contract_v1.2_FINAL.md`**
3. **`MVP0_F3_Signal_Approval_Implementation_Package_v1.0.md`** (`docs/implementation/MVP0_F3_Signal_Approval_Implementation_Package_v1.0.md`)
4. **`MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`**

### 1.1 Strictly Enforced F3 Scope Boundaries (§2 & §14)
- **Allowed F3 Scope Implemented:**
  - Deterministic Rule-Based Signal Engine (`app/services/signal_engine.py`, `L31-L379`)
  - Trend Following Rule (`app/services/trend_following_rule.py`, `L223-L356`)
  - Mean Reversion Rule (`app/services/mean_reversion_rule.py`, `L90-L219`)
  - Signal Lifecycle & Approval State Machine (`app/services/signal_lifecycle.py`, `L114-L791`)
  - Dynamic Approval Timeout & 0.2% Price Drift Expiry (`app/services/approval_timeout.py`, `L31-L251`; `app/workers/approval_timeout.py`, `L21-L63`)
  - Signal & Approval API (`app/api/v1/signals.py`, `L28-L181`; `app/schemas/signals.py`, `L8-L60`)
  - Signal-to-Order Handoff via existing F2 Risk Engine (`app/services/signal_lifecycle.py`, `L161-L444`; `app/api/v1/orders.py`, `L21-L86`; `app/schemas/orders.py`, `L6-L38`)
  - Read-Only Decision Log API (`app/services/decision_log.py`, `L36-L269`; `app/api/v1/decisions.py`, `L27-L120`; `app/schemas/decisions.py`, `L8-L68`)
  - Versioned Outbox Events (`app/core/enums.py`, `L107-L126`: `SIGNAL_CREATED`, `SIGNAL_APPROVED`, `SIGNAL_REJECTED`, `SIGNAL_EXPIRED`, `SIGNAL_PRICE_DRIFT_EXPIRED`, `ORDER_CREATED`, `ORDER_REJECTED_BY_RISK`)
- **Forbidden Items Verified Absent (F4/F5/F6 Blocked):**
  - No live trading (`LIVE_TRADING=false` and `PAPER_TRADING=true` immutable in `app/core/config.py`, `L125-L186`)
  - No Direct Mode (Semi-Auto human approval only via `POST /api/v1/signals/{signal_id}/approve`)
  - No real Exchange Adapter or CCXT/Binance/Bybit/OKX live client calls (`! grep -RInE "api\.binance\.com|api\.bybit\.com|api\.okx\.com|ccxt\." app/ docker/ scripts/` passes in Security Scan Run ID `37176837087`, Step 7)
  - No short, margin, leverage, futures, derivatives, or withdrawal support (`ALLOWED_SYMBOLS = frozenset({"BTC/USDT", "ETH/USDT", "BNB/USDT"})`, `ALLOWED_MARKET_TYPE = "SPOT"`, `ALLOWED_DIRECTION = "LONG"` in `app/services/trend_following_rule.py`, `L20-L22`)
  - No new F4 Paper Execution Engine, no Synthetic Stop redesign, no Kill Switch redesign, no Reconciliation redesign
  - No Dashboard/PWA (F6), no editable Decision Journal, no comments/tags/feedback loop (`POST`/`PUT`/`PATCH`/`DELETE` on `/api/v1/decisions*` return `405 Method Not Allowed`)
  - No ML, JEV, Shadow Mode, A/B testing, Go, Vault, TimescaleDB, multi-tenancy, or RLS

---

## 2. Requirement-by-Requirement Implementation & Test Traceability Matrix

| Spec Ref | Requirement Summary | File Path | Line Range & Function / Class Name | Test Function Name(s) (`file::test_name`) | Commit SHA / Tag | CI Run ID & Step Name |
|---|---|---|---|---|---|---|
| **§4.1** | Closed candles only (`is_closed is True` and `close_time <= evaluation_time`); unclosed candles excluded | `app/services/trend_following_rule.py` | `L39-L76` (`CandleBar`), `L99-L127` (`filter_closed_candles`) | `tests/unit/test_signal_engine.py::test_signal_engine_uses_closed_candles_only` (`L20-L56`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§4.2** | Allowed markets & direction only: `BTC/USDT`, `ETH/USDT`, `BNB/USDT`; `SPOT` only; `LONG` only; `Decimal` only; UTC-aware `datetime` only | `app/services/trend_following_rule.py`<br>`app/services/signal_engine.py` | `L20-L35` (`ensure_utc_datetime`), `L170-L220` (`validate_market_and_scores`), `L128-L266` (`SignalEngine.create_signal`) | `tests/unit/test_signal_engine.py::test_signal_rejects_disallowed_symbol` (`L87-L97`), `test_signal_rejects_non_long_direction` (`L100-L127`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§4.3** | Trend Following Rule: `EMA(50) > EMA(200)` on 4H closed candles; `Close > EMA(20)` on 1H closed candles; `Close > highest high of prev 20 closed 1H candles`; `Volume >= 1.5x avg volume of prev 20 closed 1H candles`; `data_quality_score >= 0.8`; `confidence_score >= 0.6` | `app/services/trend_following_rule.py` | `L130-L147` (`calculate_ema`), `L223-L356` (`TrendFollowingRule.evaluate`) | `tests/unit/test_trend_following_rule.py::test_trend_following_requires_all_conditions` (`L107-L157`), `test_trend_following_rejects_insufficient_volume` (`L160-L171`), `tests/unit/test_signal_engine.py::test_signal_rejects_data_quality_below_0_8` (`L59-L70`), `test_signal_rejects_confidence_below_0_6` (`L73-L84`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§4.4** | Mean Reversion Rule: `RSI(14)` on closed 1H candles was `< 30` and crosses back `> 30`; `Close` was `<= Lower Bollinger Band(20, 2)` and returns inside Bollinger Band (`> lower_band`); `data_quality_score >= 0.8`; `confidence_score >= 0.6` | `app/services/mean_reversion_rule.py` | `L24-L60` (`calculate_rsi_series`), `L63-L87` (`calculate_bollinger_bands`), `L90-L219` (`MeanReversionRule.evaluate`) | `tests/unit/test_mean_reversion_rule.py::test_mean_reversion_requires_rsi_cross` (`L86-L114`), `test_mean_reversion_requires_bollinger_return` (`L117-L135`), `test_rsi_and_bollinger_validation_guards` (`L138-L147`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§4.5** | Mandatory `explanation_json` schema (`entry_reason`, `risk_reason`, `confluence_score`, `regime`, `factors` list) validated before persistence | `app/services/trend_following_rule.py`<br>`app/services/signal_engine.py` | `L150-L167` (`validate_explanation_json`), `L128-L266` (`SignalEngine.create_signal`) | `tests/unit/test_signal_engine.py::test_signal_contains_explanation` (`L131-L197`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§4.6** | `reference_price` set to closed signal candle close price and strictly immutable at both ORM attribute level and SQL `before_flush` level | `app/db/models/signal.py` | `L26-L78` (`Signal`), `L82-L99` (`_prevent_reference_price_mutation`), `L103-L117` (`_prevent_reference_price_db_update`) | `tests/unit/test_signal_engine.py::test_signal_reference_price_is_immutable` (`L201-L270`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§5.1–§5.3** | Signal Lifecycle State Machine (`PENDING_APPROVAL -> APPROVED \| REJECTED \| EXPIRED \| PRICE_DRIFT_EXPIRED`), terminal state enforcement (`409 INVALID_STATE` / `SIGNAL_EXPIRED` / `PRICE_DRIFT_EXPIRED`), row-level `SELECT ... FOR UPDATE`, atomic DB transaction with `audit_logs` + `outbox_events` | `app/services/signal_lifecycle.py`<br>`app/db/repositories/signal_repository.py` | `L446-L594` (`SignalLifecycleService.transition_signal`), `L596-L707` (`approve_signal`), `L709-L791` (`reject_signal`), `L25-L64` (`SignalRepository.get_by_id` / `get_by_id_or_raise`) | `tests/integration/test_signal_approval.py::test_pending_signal_can_be_approved` (`L63-L94`) through `test_invalid_transition_returns_409` (`L340-L364`) — all 10 tests | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§6.1–§6.3** | Dynamic Approval Timeout (`1H=5m`, `4H=30m`, `1D=4h`), IPS timeout override `min(dynamic_timeout, ips_timeout)` in `[3, 240]` minutes (can only reduce timeout), background worker running every `5s` | `app/services/approval_timeout.py`<br>`app/workers/approval_timeout.py` | `L23-L27` (`TIMEFRAME_DYNAMIC_TIMEOUT_MINUTES`), `L31-L45` (`validate_ips_timeout_minutes`), `L48-L59` (`compute_effective_timeout`), `L95-L251` (`ApprovalTimeoutService`), `L21-L63` (`approval_timeout_worker_loop`) | `tests/unit/test_approval_timeout.py::test_dynamic_timeout_for_1h_is_5_minutes` (`L96-L98`) through `test_timeout_creates_outbox_event` (`L315-L336`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§7.1–§7.3** | Price Drift Expiry: `abs(current_price - reference_price) / reference_price > Decimal("0.002")` transitions signal to `PRICE_DRIFT_EXPIRED`, rejects approval with `409 PRICE_DRIFT_EXPIRED`, writes `SIGNAL_PRICE_DRIFT_EXPIRED` audit log (`reference_price`, `current_price`, `price_drift`, `threshold`) and outbox event | `app/services/approval_timeout.py`<br>`app/services/signal_lifecycle.py` | `L62-L72` (`calculate_price_drift`), `L125-L185` (`ApprovalTimeoutService.check_signal_timeout`), `L630-L654` (`SignalLifecycleService.approve_signal`) | `tests/unit/test_approval_timeout.py::test_price_drift_expiry_occurs_before_timeout` (`L190-L212`), `test_price_drift_threshold_is_0_2_percent` (`L221-L224`), `test_price_drift_calculation_uses_decimal` (`L243-L245`), `test_price_drift_expiry_creates_audit_event` (`L340-L374`), `test_price_drift_expiry_creates_outbox_event` (`L378-L410`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§8.1–§8.6** | Signal & Approval API (`GET /api/v1/signals`, `POST /api/v1/signals/{signal_id}/approve`, `POST /api/v1/signals/{signal_id}/reject`), Bearer auth (`MVP0_API_KEY` / `MVP0_ADMIN_API_KEY`), `Idempotency-Key` enforcement (`409 IDEMPOTENCY_CONFLICT` on payload mismatch), standard error codes (`401`, `403`, `404`, `409`) | `app/api/v1/signals.py`<br>`app/schemas/signals.py`<br>`app/core/errors.py` | `L82-L181` (`list_signals`, `get_signal`, `approve_signal_endpoint`, `reject_signal_endpoint`), `L8-L60` (`SignalResponse`), `L92-L185` (`SignalNotFoundError`, `SignalExpiredError`, `PriceDriftExpiredError`, `IdempotencyConflictError`) | `tests/integration/test_signal_api.py::test_list_signals_requires_operational_key` (`L49-L74`) through `test_invalid_state_returns_409` (`L250-L304`) — all 9 tests | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§9.1–§9.4** | Signal-to-Order Handoff: approved signal creates `OrderDraft` linked to `signal_id`, evaluates via F2 `RiskEngine.evaluate()`, creates `SUBMITTED` order + `ORDER_CREATED` outbox event if risk-approved, or `REJECTED` order + `ORDER_REJECTED_BY_RISK` outbox event if risk-rejected while keeping signal `APPROVED`; at most one active order per signal; unique `client_order_id` and `idempotency_key`; no real exchange call | `app/services/signal_lifecycle.py`<br>`app/api/v1/orders.py`<br>`app/core/enums.py` | `L62-L78` (`OrderDraft`), `L161-L206` (`create_order_draft`), `L208-L444` (`handoff_signal_to_order`), `L57-L86` (`list_orders`, `get_order`), `L121` (`OutboxEventType.ORDER_REJECTED_BY_RISK`) | `tests/integration/test_signal_to_order_handoff.py::test_approved_signal_creates_order_draft` (`L64-L96`) through `test_redis_unavailable_does_not_lose_postgres_state` (`L362-L460`) — all 10 tests; `tests/e2e/test_signal_approval_order_flow.py::test_e2e_signal_approval_and_rejection_order_handoff_flow` (`L18-L132`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§10.1–§10.3** | Read-Only Decision Log API (`GET /api/v1/decisions`, `GET /api/v1/decisions/{signal_id}`), reconstructs decision history from `signals.explanation_json`, `approval_requests`, `orders`, and `audit_logs`; sanitizes secret keys/values; exposes no create/update/delete endpoints | `app/services/decision_log.py`<br>`app/api/v1/decisions.py`<br>`app/schemas/decisions.py` | `L36-L63` (`sanitize_decision_payload`), `L123-L269` (`DecisionLogService`), `L85-L120` (`list_decisions_endpoint`, `get_decision_by_signal_id_endpoint`) | `tests/integration/test_decision_log.py::test_decision_log_is_read_only` (`L60-L77`) through `test_decision_log_has_no_delete_endpoint` (`L307-L318`) — all 10 tests | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |
| **§11.1–§11.2** | Outbox & Notification Integration: versioned (`v1`) transactional outbox events for `SIGNAL_CREATED`, `SIGNAL_APPROVED`, `SIGNAL_REJECTED`, `SIGNAL_EXPIRED`, `SIGNAL_PRICE_DRIFT_EXPIRED`, `ORDER_CREATED`, `ORDER_REJECTED_BY_RISK`; dead-letter transition after max retries | `app/core/enums.py`<br>`app/services/outbox.py`<br>`app/services/signal_lifecycle.py` | `L107-L126` (`OutboxEventType`), `L66-L115` (`OutboxService.enqueue_event`), `L318-L390` (`process_pending_events`) | `tests/integration/test_signal_to_order_handoff.py::test_outbox_dead_letter_after_max_retries` (`L312-L358`), `tests/integration/test_outbox_and_workers.py` (`6 passed`) | `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`) | Run `37176837120`, Step 12 (`Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites`) |

---

## 3. Complete 72/72 Mandatory Test Inventory (§12.1–§12.6)

All **72 mandatory test functions** specified in `MVP0_F3_Signal_Approval_Implementation_Package_v1.0.md` (§12.1–§12.6) exist verbatim by exact function name and pass in both local pytest execution and GitHub Actions CI Run ID `37176837120` (177 total tests passing, 0 failed, 0 skipped).

### 3.1 Signal Engine Unit Tests (§12.1 — 11/11 Passing)
| # | Mandatory Test Function Name | File Path & Line Range | Status |
|---|---|---|---|
| 1 | `test_signal_engine_uses_closed_candles_only` | `tests/unit/test_signal_engine.py:L20-L56` | `PASSED` |
| 2 | `test_trend_following_requires_all_conditions` | `tests/unit/test_trend_following_rule.py:L107-L157` | `PASSED` |
| 3 | `test_trend_following_rejects_insufficient_volume` | `tests/unit/test_trend_following_rule.py:L160-L171` | `PASSED` |
| 4 | `test_mean_reversion_requires_rsi_cross` | `tests/unit/test_mean_reversion_rule.py:L86-L114` | `PASSED` |
| 5 | `test_mean_reversion_requires_bollinger_return` | `tests/unit/test_mean_reversion_rule.py:L117-L135` | `PASSED` |
| 6 | `test_signal_rejects_data_quality_below_0_8` | `tests/unit/test_signal_engine.py:L59-L70` | `PASSED` |
| 7 | `test_signal_rejects_confidence_below_0_6` | `tests/unit/test_signal_engine.py:L73-L84` | `PASSED` |
| 8 | `test_signal_rejects_disallowed_symbol` | `tests/unit/test_signal_engine.py:L87-L97` | `PASSED` |
| 9 | `test_signal_rejects_non_long_direction` | `tests/unit/test_signal_engine.py:L100-L127` | `PASSED` |
| 10 | `test_signal_contains_explanation` | `tests/unit/test_signal_engine.py:L131-L197` | `PASSED` |
| 11 | `test_signal_reference_price_is_immutable` | `tests/unit/test_signal_engine.py:L201-L270` | `PASSED` |

### 3.2 Approval Timeout & Price Drift Tests (§12.2 — 15/15 Passing)
| # | Mandatory Test Function Name | File Path & Line Range | Status |
|---|---|---|---|
| 12 | `test_dynamic_timeout_for_1h_is_5_minutes` | `tests/unit/test_approval_timeout.py:L96-L98` | `PASSED` |
| 13 | `test_dynamic_timeout_for_4h_is_30_minutes` | `tests/unit/test_approval_timeout.py:L101-L103` | `PASSED` |
| 14 | `test_dynamic_timeout_for_1d_is_4_hours` | `tests/unit/test_approval_timeout.py:L106-L108` | `PASSED` |
| 15 | `test_ips_timeout_can_only_reduce_timeout` | `tests/unit/test_approval_timeout.py:L111-L115` | `PASSED` |
| 16 | `test_ips_timeout_rejects_below_3_minutes` | `tests/unit/test_approval_timeout.py:L118-L122` | `PASSED` |
| 17 | `test_ips_timeout_rejects_above_240_minutes` | `tests/unit/test_approval_timeout.py:L125-L129` | `PASSED` |
| 18 | `test_approval_timeout_worker_runs_every_5_seconds` | `tests/unit/test_approval_timeout.py:L140-L159` | `PASSED` |
| 19 | `test_price_drift_expiry_occurs_before_timeout` | `tests/unit/test_approval_timeout.py:L190-L212` | `PASSED` |
| 20 | `test_price_drift_threshold_is_0_2_percent` | `tests/unit/test_approval_timeout.py:L221-L224` | `PASSED` |
| 21 | `test_price_drift_calculation_uses_decimal` | `tests/unit/test_approval_timeout.py:L243-L245` | `PASSED` |
| 22 | `test_price_drift_rejects_zero_or_negative_price` | `tests/unit/test_approval_timeout.py:L248-L260` | `PASSED` |
| 23 | `test_timeout_creates_audit_event` | `tests/unit/test_approval_timeout.py:L290-L311` | `PASSED` |
| 24 | `test_timeout_creates_outbox_event` | `tests/unit/test_approval_timeout.py:L315-L336` | `PASSED` |
| 25 | `test_price_drift_expiry_creates_audit_event` | `tests/unit/test_approval_timeout.py:L340-L374` | `PASSED` |
| 26 | `test_price_drift_expiry_creates_outbox_event` | `tests/unit/test_approval_timeout.py:L378-L410` | `PASSED` |

### 3.3 Signal Lifecycle & Approval API Tests (§12.3 — 19/19 Passing)
| # | Mandatory Test Function Name | File Path & Line Range | Status |
|---|---|---|---|
| 27 | `test_pending_signal_can_be_approved` | `tests/integration/test_signal_approval.py:L63-L94` | `PASSED` |
| 28 | `test_pending_signal_can_be_rejected` | `tests/integration/test_signal_approval.py:L98-L129` | `PASSED` |
| 29 | `test_pending_signal_can_expire` | `tests/integration/test_signal_approval.py:L133-L148` | `PASSED` |
| 30 | `test_pending_signal_can_price_drift_expire` | `tests/integration/test_signal_approval.py:L152-L168` | `PASSED` |
| 31 | `test_approved_signal_cannot_be_approved_again` | `tests/integration/test_signal_approval.py:L172-L202` | `PASSED` |
| 32 | `test_rejected_signal_cannot_be_approved` | `tests/integration/test_signal_approval.py:L206-L228` | `PASSED` |
| 33 | `test_expired_signal_cannot_be_approved` | `tests/integration/test_signal_approval.py:L232-L265` | `PASSED` |
| 34 | `test_price_drift_expired_signal_cannot_be_approved` | `tests/integration/test_signal_approval.py:L269-L308` | `PASSED` |
| 35 | `test_concurrent_approval_is_serialized` | `tests/integration/test_signal_approval.py:L312-L336` | `PASSED` |
| 36 | `test_approve_signal_is_idempotent` | `tests/integration/test_signal_api.py:L172-L202` | `PASSED` |
| 37 | `test_duplicate_idempotency_key_with_different_payload_returns_409` | `tests/integration/test_signal_api.py:L206-L229` | `PASSED` |
| 38 | `test_list_signals_requires_operational_key` | `tests/integration/test_signal_api.py:L49-L74` | `PASSED` |
| 39 | `test_approve_signal_requires_operational_key` | `tests/integration/test_signal_api.py:L78-L101` | `PASSED` |
| 40 | `test_reject_signal_requires_operational_key` | `tests/integration/test_signal_api.py:L105-L127` | `PASSED` |
| 41 | `test_admin_key_can_access_operational_routes` | `tests/integration/test_signal_api.py:L131-L148` | `PASSED` |
| 42 | `test_operational_key_cannot_access_admin_routes` | `tests/integration/test_signal_api.py:L152-L168` | `PASSED` |
| 43 | `test_signal_not_found_returns_404` | `tests/integration/test_signal_api.py:L233-L246` | `PASSED` |
| 44 | `test_invalid_state_returns_409` | `tests/integration/test_signal_api.py:L250-L304` | `PASSED` |
| 45 | `test_invalid_transition_returns_409` | `tests/integration/test_signal_approval.py:L340-L364` | `PASSED` |

### 3.4 Signal-to-Order Handoff Tests (§12.4 — 10/10 Passing)
| # | Mandatory Test Function Name | File Path & Line Range | Status |
|---|---|---|---|
| 46 | `test_approved_signal_creates_order_draft` | `tests/integration/test_signal_to_order_handoff.py:L64-L96` | `PASSED` |
| 47 | `test_risk_approved_signal_creates_submitted_order` | `tests/integration/test_signal_to_order_handoff.py:L100-L130` | `PASSED` |
| 48 | `test_risk_rejected_signal_creates_rejected_order` | `tests/integration/test_signal_to_order_handoff.py:L134-L160` | `PASSED` |
| 49 | `test_risk_rejection_creates_audit_event` | `tests/integration/test_signal_to_order_handoff.py:L164-L190` | `PASSED` |
| 50 | `test_risk_rejection_creates_outbox_event` | `tests/integration/test_signal_to_order_handoff.py:L194-L220` | `PASSED` |
| 51 | `test_one_active_order_per_signal` | `tests/integration/test_signal_to_order_handoff.py:L224-L249` | `PASSED` |
| 52 | `test_duplicate_order_creation_is_prevented` | `tests/integration/test_signal_to_order_handoff.py:L253-L285` | `PASSED` |
| 53 | `test_no_real_exchange_call_is_made` | `tests/integration/test_signal_to_order_handoff.py:L289-L308` | `PASSED` |
| 54 | `test_outbox_dead_letter_after_max_retries` | `tests/integration/test_signal_to_order_handoff.py:L312-L358` | `PASSED` |
| 55 | `test_redis_unavailable_does_not_lose_postgres_state` | `tests/integration/test_signal_to_order_handoff.py:L362-L460` | `PASSED` |

### 3.5 Decision Log Tests (§12.5 — 10/10 Passing)
| # | Mandatory Test Function Name | File Path & Line Range | Status |
|---|---|---|---|
| 56 | `test_decision_log_is_read_only` | `tests/integration/test_decision_log.py:L60-L77` | `PASSED` |
| 57 | `test_decision_history_is_queryable_by_signal_id` | `tests/integration/test_decision_log.py:L81-L105` | `PASSED` |
| 58 | `test_decision_history_includes_approval_event` | `tests/integration/test_decision_log.py:L109-L132` | `PASSED` |
| 59 | `test_decision_history_includes_rejection_event` | `tests/integration/test_decision_log.py:L136-L157` | `PASSED` |
| 60 | `test_decision_history_includes_timeout_event` | `tests/integration/test_decision_log.py:L161-L188` | `PASSED` |
| 61 | `test_decision_history_includes_price_drift_event` | `tests/integration/test_decision_log.py:L192-L220` | `PASSED` |
| 62 | `test_decision_history_does_not_expose_secrets` | `tests/integration/test_decision_log.py:L224-L265` | `PASSED` |
| 63 | `test_decision_log_has_no_create_endpoint` | `tests/integration/test_decision_log.py:L269-L280` | `PASSED` |
| 64 | `test_decision_log_has_no_update_endpoint` | `tests/integration/test_decision_log.py:L284-L303` | `PASSED` |
| 65 | `test_decision_log_has_no_delete_endpoint` | `tests/integration/test_decision_log.py:L307-L318` | `PASSED` |

### 3.6 F2 Regression Tests (§12.6 — 7/7 Passing)
| # | Mandatory Test Function Name | File Path & Line Range | Status |
|---|---|---|---|
| 66 | `test_max_risk_per_trade_is_0_5_percent` | `tests/unit/test_risk_engine.py:L25-L48` | `PASSED` |
| 67 | `test_risk_engine_rejects_when_kill_switch_active` | `tests/unit/test_risk_engine.py:L133-L147` | `PASSED` |
| 68 | `test_kill_switch_blocks_new_orders` | `tests/integration/test_kill_switch.py:L157-L170` | `PASSED` |
| 69 | `test_kill_switch_resume_requires_two_person_approval` | `tests/integration/test_kill_switch.py:L344-L384` | `PASSED` |
| 70 | `test_resume_requires_admin_and_operator_roles` | `tests/integration/test_kill_switch.py:L451-L483` | `PASSED` |
| 71 | `test_synthetic_stop_triggers_only_once` | `tests/integration/test_synthetic_stop.py:L406-L409` (`L141-L165`) | `PASSED` |
| 72 | `test_protection_failure_retry_schedule_is_0_5_15_seconds` | `tests/integration/test_state_machine.py:L567-L572` (`L271-L329`) | `PASSED` |

---

## 4. Quality Gates & Module Coverage Verification (§13)

All quality gates from `MVP0_F3_Signal_Approval_Implementation_Package_v1.0.md` §13 and `.github/workflows/ci.yml` (`L88-L119`) were executed and verified on Commit SHA `f5f4192f83679cf167d0cd24d17a52bbc38dcc72` (`release/f3-candidate`), CI Run ID `37176837120`:

| Gate / Module Scope | Required Threshold | Actual Result | Verification Command / CI Step |
|---|---|---|---|
| `ruff check .` | `0` errors | `All checks passed!` (`0` errors) | CI Run `37176837120`, Step 7 (`Run Ruff lint and format checks`) |
| `ruff format --check .` | `0` diffs | `114 files already formatted` | CI Run `37176837120`, Step 7 (`Run Ruff lint and format checks`) |
| `mypy --strict app` | `0` errors | `Success: no issues found in 74 source files` | CI Run `37176837120`, Step 8 (`Run mypy --strict app`) |
| `alembic upgrade head` -> `downgrade base` -> `upgrade head` | Clean round-trip | `0` errors across all 6 migrations (`0001`–`0006`) | CI Run `37176837120`, Steps 9–11 |
| Full Pytest Suite (`177` tests) | `100%` pass | `177 passed in 15.39s` (`0 failed`) | CI Run `37176837120`, Steps 12–13 |
| **Overall Branch Coverage (`app/`)** | `>= 80%` | **`93.29%`** (`4204` stmts, `772` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Signal Engine (`signal_engine.py`, `trend_following_rule.py`, `mean_reversion_rule.py`)** | `>= 90%` | **`96%`** (`signal_engine.py` `98%`, `trend_following_rule.py` `98%`, `mean_reversion_rule.py` `92%`) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Approval Timeout (`app/services/approval_timeout.py`)** | `>= 90%` | **`95%`** (`100` stmts, `28` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Signal Lifecycle (`app/services/signal_lifecycle.py`)** | `>= 90%` | **`93%`** (`222` stmts, `64` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Risk Engine (`app/services/risk_engine.py`)** | `>= 90%` | **`98%`** (`299` stmts, `96` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Order State Machine (`app/services/state_machine.py`)** | `>= 90%` | **`93%`** (`160` stmts, `38` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Kill Switch (`app/services/kill_switch.py`)** | `>= 90%` | **`92%`** (`308` stmts, `74` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Security (`app/core/security.py`)** | `>= 90%` | **`100%`** (`35` stmts, `12` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Synthetic Stop (`app/services/synthetic_stop.py`)** | `>= 90%` | **`94%`** (`226` stmts, `50` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Outbox (`app/services/outbox.py`)** | `>= 90%` | **`96%`** (`177` stmts, `42` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Core (`app/core/*`)** | `>= 90%` | **`95%`** (`572` stmts, `92` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |
| **Database (`app/db/*`)** | `>= 90%` | **`97%`** (`470` stmts, `34` branches) | CI Run `37176837120`, Step 13 (`Run pytest with coverage gates`) |

---

## 5. GitHub Actions CI & Verification Log Excerpts

### 5.1 Workflow Run Summary (`headSha: f5f4192f83679cf167d0cd24d17a52bbc38dcc72`, Tag: `release/f3-candidate`)

```json
[
  {
    "conclusion": "success",
    "createdAt": "2026-10-04T04:22:53Z",
    "databaseId": 37176837120,
    "headSha": "f5f4192f83679cf167d0cd24d17a52bbc38dcc72",
    "status": "completed",
    "updatedAt": "2026-10-04T04:25:01Z",
    "workflowName": "CI"
  },
  {
    "conclusion": "success",
    "createdAt": "2026-10-04T04:22:53Z",
    "databaseId": 37176837087,
    "headSha": "f5f4192f83679cf167d0cd24d17a52bbc38dcc72",
    "status": "completed",
    "updatedAt": "2026-10-04T04:23:39Z",
    "workflowName": "Security & Paper Isolation Scan"
  },
  {
    "conclusion": "success",
    "createdAt": "2026-10-04T04:22:53Z",
    "databaseId": 37176837077,
    "headSha": "f5f4192f83679cf167d0cd24d17a52bbc38dcc72",
    "status": "completed",
    "updatedAt": "2026-10-04T04:26:17Z",
    "workflowName": "Docker Build & Compose Validation"
  }
]
```

### 5.2 Step Execution Breakdown Across All 3 Workflows

- **CI Workflow (`Run ID: 37176837120`, `Job ID: 111361102612` — `Lint, Typecheck, Migrate, and Test (Python 3.12)`):**
  - Step 6: `Install dependencies from poetry.lock` (`04:23:24Z` -> `04:23:31Z`) — `success`
  - Step 7: `Run Ruff lint and format checks` (`04:23:31Z` -> `04:23:32Z`) — `success`
  - Step 8: `Run mypy --strict app` (`04:23:32Z` -> `04:23:44Z`) — `success`
  - Step 9: `Run alembic upgrade head` (`04:23:44Z` -> `04:23:47Z`) — `success`
  - Step 10: `Run alembic downgrade base` (`04:23:47Z` -> `04:23:49Z`) — `success`
  - Step 11: `Run alembic upgrade head again` (`04:23:49Z` -> `04:23:51Z`) — `success`
  - Step 12: `Run F2 and F3 mandatory unit, integration, E2E, and Chaos suites` (`04:23:51Z` -> `04:24:10Z`) — `success`
  - Step 13: `Run pytest with coverage gates` (`04:24:10Z` -> `04:24:55Z`) — `success`
  - Step 14: `Upload coverage report` (`04:24:55Z` -> `04:24:57Z`) — `success`
- **Security & Paper Isolation Scan (`Run ID: 37176837087`, `Job ID: 111361102389` — `Secret, Live-Trading, and Paper Isolation Checks`):**
  - Step 6: `Run security and Paper isolation test suite` (`04:23:25Z` -> `04:23:30Z`) — `success` (`16 passed`)
  - Step 7: `Check for forbidden live-trading or real exchange patterns` (`04:23:30Z` -> `04:23:30Z`) — `success`
- **Docker Build & Compose Validation (`Run ID: 37176837077`, `Job ID: 111361102354` — `Build Docker Images & Verify Single Worker + Compose Startup`):**
  - Step 3: `Build API Docker image` (`04:22:58Z` -> `04:23:27Z`) — `success`
  - Step 4: `Build Paper API Docker image` (`04:23:27Z` -> `04:23:30Z`) — `success`
  - Step 5: `Build Independent Kill Switch Docker image` (`04:23:30Z` -> `04:24:02Z`) — `success`
  - Step 6: `Verify runtime command uses exactly one worker and non-root UID 10001` (`04:24:02Z` -> `04:24:04Z`) — `success`
  - Step 7: `Validate Development Docker Compose startup (API + Independent Kill Switch)` (`04:24:04Z` -> `04:24:56Z`) — `success`
  - Step 8: `Validate Paper Docker Compose startup and isolation (Paper API + Paper Kill Switch)` (`04:24:56Z` -> `04:25:45Z`) — `success`

### 5.3 Actual Verification Log Excerpt (Ruff, Mypy, Full 177-Test Suite & Module Coverage Gates)

```text
$ ruff check . && ruff format --check . && mypy --strict app
All checks passed!
114 files already formatted
Success: no issues found in 74 source files

$ pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80
============================= test session starts ==============================
collected 177 items

tests/chaos/test_f2_chaos.py .....                                       [  2%]
tests/e2e/test_signal_approval_order_flow.py .                           [  3%]
tests/e2e/test_signal_lifecycle_e2e.py ...                               [  5%]
tests/integration/test_database.py ...                                   [  6%]
tests/integration/test_decision_log.py ..........                        [ 12%]
tests/integration/test_health_and_readiness.py ......                    [ 15%]
tests/integration/test_kill_switch.py ...............                    [ 24%]
tests/integration/test_migrations.py .....                               [ 27%]
tests/integration/test_outbox_and_workers.py ......                      [ 30%]
tests/integration/test_redis.py ....                                     [ 32%]
tests/integration/test_signal_api.py .........                           [ 37%]
tests/integration/test_signal_approval.py ..........                     [ 43%]
tests/integration/test_signal_to_order_handoff.py ..........             [ 49%]
tests/integration/test_state_machine.py .......                          [ 53%]
tests/integration/test_synthetic_stop.py ........                        [ 57%]
tests/security/test_authentication.py .........                          [ 62%]
tests/security/test_paper_isolation.py .......                           [ 66%]
tests/unit/test_approval_timeout.py ......................               [ 79%]
tests/unit/test_config.py ..........                                     [ 84%]
tests/unit/test_logging.py ...                                           [ 86%]
tests/unit/test_mean_reversion_rule.py ...                               [ 88%]
tests/unit/test_risk_engine.py ...........                               [ 94%]
tests/unit/test_signal_engine.py .......                                 [ 98%]
tests/unit/test_trend_following_rule.py ...                              [100%]

TOTAL                                         4204    206    772    112    93%
Required test coverage of 80% reached. Total coverage: 93.29%
============================= 177 passed in 15.39s =============================
```

---

## 6. F3 Gate Checklist (§15)

- [x] **Rule-based Signal Engine implemented (`Trend Following` + `Mean Reversion`)** — `app/services/signal_engine.py:L31-L379`, `app/services/trend_following_rule.py:L223-L356`, `app/services/mean_reversion_rule.py:L90-L219`
- [x] **Closed-candle-only rule enforced** — `app/services/trend_following_rule.py:L99-L127` (`filter_closed_candles`), verified by `tests/unit/test_signal_engine.py::test_signal_engine_uses_closed_candles_only`
- [x] **Signal Explanation (`explanation_json`) implemented** — `app/services/trend_following_rule.py:L150-L167` (`validate_explanation_json`), verified by `tests/unit/test_signal_engine.py::test_signal_contains_explanation`
- [x] **`reference_price` immutability enforced** — `app/db/models/signal.py:L82-L117` (`_prevent_reference_price_mutation`, `_prevent_reference_price_db_update`), verified by `tests/unit/test_signal_engine.py::test_signal_reference_price_is_immutable`
- [x] **Dynamic Approval Timeout (`1H=5m`, `4H=30m`, `1D=4h`) implemented** — `app/services/approval_timeout.py:L23-L59`, verified by `tests/unit/test_approval_timeout.py::test_dynamic_timeout_for_1h_is_5_minutes`, `test_dynamic_timeout_for_4h_is_30_minutes`, `test_dynamic_timeout_for_1d_is_4_hours`
- [x] **IPS timeout override (`min(dynamic_timeout, ips_timeout)`, `3..240` minutes) implemented** — `app/services/approval_timeout.py:L31-L59`, verified by `tests/unit/test_approval_timeout.py::test_ips_timeout_can_only_reduce_timeout`, `test_ips_timeout_rejects_below_3_minutes`, `test_ips_timeout_rejects_above_240_minutes`
- [x] **Price Drift Expiry (`0.2%` / `Decimal("0.002")`) implemented** — `app/services/approval_timeout.py:L62-L185` and `app/services/signal_lifecycle.py:L630-L654`, verified by `tests/unit/test_approval_timeout.py::test_price_drift_expiry_occurs_before_timeout` and `tests/integration/test_signal_approval.py::test_price_drift_expired_signal_cannot_be_approved`
- [x] **Signal Approval / Rejection API implemented** — `app/api/v1/signals.py:L92-L181`, verified by `tests/integration/test_signal_api.py` (`9 passed`) and `tests/integration/test_signal_approval.py` (`10 passed`)
- [x] **Idempotency key enforcement implemented** — `app/services/signal_lifecycle.py:L92-L111, L608-L625, L721-L738`, verified by `tests/integration/test_signal_api.py::test_approve_signal_is_idempotent` and `test_duplicate_idempotency_key_with_different_payload_returns_409`
- [x] **Signal-to-Order handoff through F2 Risk Engine implemented** — `app/services/signal_lifecycle.py:L161-L444`, verified by `tests/integration/test_signal_to_order_handoff.py` (`10 passed`) and `tests/e2e/test_signal_approval_order_flow.py` (`1 passed`)
- [x] **Read-only Decision Log API implemented** — `app/services/decision_log.py:L36-L269` and `app/api/v1/decisions.py:L27-L120`, verified by `tests/integration/test_decision_log.py` (`10 passed`)
- [x] **Outbox events (`SIGNAL_*`, `ORDER_CREATED`, `ORDER_REJECTED_BY_RISK`) implemented** — `app/core/enums.py:L107-L126` and `app/services/signal_lifecycle.py:L376-L443, L553-L588`, verified by `tests/integration/test_signal_to_order_handoff.py` and `tests/integration/test_outbox_and_workers.py`
- [x] **All F1/F2 safety controls and regression tests remain green** — `177 passed, 0 failed` in CI Run ID `37176837120`, Security Scan Run ID `37176837087`, and Docker Compose Validation Run ID `37176837077`
