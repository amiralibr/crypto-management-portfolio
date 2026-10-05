# MVP-0 F3 Completion Evidence v1.1

**Prepared:** 2026-10-05
**Contract authority:** `MVP0_Implementation_Contract_v1.2_FINAL.md`
**Status:** `ACCEPTED`
**Auditor Decision:** `F3 ACCEPTED — F4 AUTHORIZED`
**Decision Date:** `2026-10-05`
**Baseline Commit:** `9cf204d88fbcc1af0428331f866348a013f6aec0`
**F4 implementation:** Authorized by the decision above, but not started; it remains pending the formal F4 execution document from the consultant.
**F5/F6:** **NOT AUTHORIZED**.
**Validated Commit 1:** `ea8041fb65d645979a60ca18577c2b4ea71fcbd8` — `test(f3): add missing E2E contract coverage`
**Validated Commit 2:** `c2fff0221aeb25b0af4bc5e1b53212b14fde49a8` — `test(f3): add F3 chaos recovery and isolation coverage`
**Validated Commit 3:** `9cf204d88fbcc1af0428331f866348a013f6aec0` — `test(f3): add explicit rollback metric and replay audit tests`
**Source-test CI run (before this evidence refresh):** [37272810591](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591)
**CI job:** [111643231479 — Lint, Typecheck, Migrate, and Test (Python 3.12)](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591/job/111643231479)
**Final package commit/CI run:** declared in the accompanying `F3_REMEDIATION_MANIFEST.md`.
**Evidence documentation commit SHA:** reported after the administrative update is committed.

## 1. Scope and safety boundary

This evidence covers F3 remediation tests, test-scoped failure injection, CI result reporting, and coverage evidence only. No application/product capability, new API, Live Adapter, real exchange connection, or F4/F5/F6 feature was added. Decision Log stays read-only. Signal approvals use `POST /api/v1/signals/{signal_id}/approve`. All executed exchange-side tests use `FakeExchangeAdapter` or `PaperTradingAdapter`; CI sets `LIVE_TRADING=false` and `PAPER_TRADING=true`.

The Paper-isolation chaos test uses a reserved `.invalid` URL and a clearly fake test-only credential through an in-memory `httpx.MockTransport`; injected failure is asserted, no network request is made, and non-loopback socket connections are blocked. It does not configure or enable live trading or use real credentials.

PostgreSQL and Redis restart scenarios use the real GitHub Actions service containers and invoke Docker `restart`. They fail in CI rather than silently skip when the expected service container is unavailable. PostgreSQL tests dispose/recreate the SQLAlchemy engine around restart and verify committed database rows after reconnect. Redis is treated as transient infrastructure; after restart a new Redis client reconnects and the authoritative Kill Switch state is verified in PostgreSQL.

## 2. CI provenance and coverage artifact

| Workflow | Run / job | Result | Evidence |
|---|---|---|---|
| CI — Python 3.12 (original 16/13 contract evidence) | [Run 37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / [Job 111516792419](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669/job/111516792419) | **PASS** | Ruff, mypy, Alembic upgrade/downgrade/upgrade, mandatory F2/F3 suite, acceptance-log publication, full pytest with coverage gates, artifact upload, and post-upload metrics all passed. |
| CI — Python 3.12 (source-test validation before evidence refresh) | [Run 37272810591](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591) / [Job 111643231479](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591/job/111643231479) | **PASS** | The run head contains code commit `9cf204d88fbcc1af0428331f866348a013f6aec0` unchanged; steps 7–16, including full pytest, all coverage gates, upload, and metrics publication, passed. Final package-head CI is identified in the accompanying manifest. |
| Security & Paper Isolation Scan | [Run 37229765673](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765673) / Job `111516792263` | **PASS** | Security/Paper isolation suite and forbidden Live-trading/real-exchange-pattern check passed. |
| Docker Build & Compose Validation | [Run 37229765664](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765664) / Job `111516792373` | **PASS** | API/Paper/independent Kill Switch images, single-worker/non-root checks, and Development/Paper Compose checks passed. |

| CI step | Result | Evidence |
|---|---|---|
| Step 7 — Ruff lint and format | **PASS** | CI job succeeded. |
| Step 8 — `mypy --strict app` | **PASS** | CI job succeeded. |
| Steps 9–11 — Alembic upgrade, downgrade, upgrade | **PASS** | All migration round-trip steps succeeded. |
| Step 12 — F2/F3 unit, integration, E2E and Chaos suite | **PASS** | The test-result excerpts in §§4–5 are from this CI step. |
| Step 13 — Publish acceptance results | **PASS** | Required F3 test markers were found and all required result lines were `PASSED`. |
| Step 14 — Full pytest suite and coverage gates | **PASS** | Full suite, global `--cov-fail-under=80`, and configured critical-module `--fail-under=90` gates succeeded. |
| Step 15 — Upload coverage report | **PASS** | `coverage-report` artifact `11312952922` uploaded and is not expired. |
| Step 16 — Publish uploaded coverage metrics | **PASS** | Post-upload CI step reported the coverage XML values and both content/archive digests. |

The actual uploaded `coverage-report` artifact is [available here](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669/artifacts/11312952922). GitHub artifact metadata: ID `11312952922`, name `coverage-report`, size `11,445` bytes, digest `sha256:9068c60c2e463214bbad5e2dfd4f112a98079aa981608a6c9b0a3c4f70b39986`, not expired. The post-upload CI step parsed the exact `coverage.xml` just uploaded and reported:

- **Line coverage: 95.22% (4,003 / 4,204 lines)**
- **Branch coverage: 84.07% (649 / 772 branches)**
- `coverage.xml` SHA-256: `dcf37ac39e188b942a8f2ead8f07be3c24050eebd71b3559439e439ce1040e05`
- Uploaded artifact digest: `sha256:9068c60c2e463214bbad5e2dfd4f112a98079aa981608a6c9b0a3c4f70b39986`

These are CI-reported artifact values, not locally replayed or inferred coverage numbers.

## 3. Twelve F3 remediation items

The five previously un-evidenced §21.5 behaviors and seven previously un-evidenced §21.6 scenarios are all covered in Commit 1/Commit 2 and report **PASS** in CI Run `37229765669`, Step 12. The full contract tables in §§4–5 also include the other §21.5 and §21.6 cases, for a complete 16/16 and 13/13 mapping.

| Remediation | Contract test ID | Result | Expected outcome | Observed outcome / test |
|---|---|---|---|---|
| E2E 1/5 | `test_signal_to_approval_to_partial_fill_to_protection` | **PASS** | API approval produces a partial fill; filled quantity is protected before the remainder is canceled. | The test observes an OPEN Position and ARMED stop inside the cancellation hook, then asserts the remainder is CANCELLED. |
| E2E 2/5 | `test_signal_to_approval_to_synthetic_stop_execution` | **PASS** | API-approved order fills; triggered Synthetic Stop closes the Position. | The stop executes a filled SELL for the Position quantity; Position is CLOSED. |
| E2E 3/5 | `test_outbox_event_created_in_same_transaction` | **PASS** | Approval, Order, audit, and Outbox records commit or roll back atomically when `ORDER_CREATED` insertion fails. | Rollback/fault-injection assertions verify PENDING approval remains and Order, approval audit, approval/Order Outbox rows, and idempotency state are absent. |
| E2E 4/5 | `test_dead_letter_metric_is_incremented` | **PASS** | Exhausting retries for the target event increments the Dead-Letter counter exactly once. | Before/after metric assertion observes `counter_after == counter_before + 1`. |
| E2E 5/5 | `test_dead_letter_replay_is_audited` | **PASS** | Admin replay writes the schema-correct audit action, role, and Dead-Letter target ID. | Persisted audit asserts `action=DEAD_LETTER_EVENT_REPLAYED`, `actor_role=ADMIN`, and `target_id == dead_letter.id`. |
| Chaos 1/7 | `test_worker_kill_during_order_processing` | **PASS** | Injected worker failure rolls back in-flight work and fails closed. | Test asserts rollback, Kill Switch/audit state, worker restart metric, and cancellation. |
| Chaos 2/7 | `test_database_restart_during_outbox_delivery` | **PASS** | A real PostgreSQL restart during delivery is recovered without losing the committed event. | Container restart occurs in the handler; after reconnect delivery reaches PUBLISHED. |
| Chaos 3/7 | `test_database_restart_does_not_lose_committed_order` | **PASS** | A committed Order remains readable after a real PostgreSQL restart and engine recreation. | Order ID, client ID, idempotency key, state, and filled quantity match after reconnect. |
| Chaos 4/7 | `test_database_restart_does_not_lose_dead_letter_event` | **PASS** | Dead-Letter row and original Outbox link survive a real PostgreSQL restart. | ID, event ID, payload, OPEN resolution, link, and DEAD_LETTER Outbox status match after reconnect. |
| Chaos 5/7 | `test_redis_restart_does_not_corrupt_kill_switch_state` | **PASS** | After real Redis restart/reconnect, durable Kill Switch state remains in PostgreSQL. | A fresh Redis client pings successfully; PostgreSQL still reports active state and the activation reason. |
| Chaos 6/7 | `test_stale_market_data_blocks_order_submission` | **PASS** | Stale market data is rejected by the Risk Engine before Paper submission. | `STALE_MARKET_DATA` is observed; Paper adapter records no placement attempt or open order. |
| Chaos 7/7 | `test_paper_network_isolation_under_chaos` | **PASS** | A simulated endpoint/credential attempt fails under injection with no external egress while Live Trading remains disabled. | MockTransport records the fake request and raises injected `ConnectError`; non-loopback socket attempts remain zero; `LIVE_TRADING=false`, no Paper order is persisted. |

## 4. Contract §21.5 — all 16 E2E/integration behaviors

Every row records the contract test ID, PASS/FAIL, actual CI run/step, expected outcome, observed outcome, and a genuine pytest result line from CI Step 12. `PASS` means the described assertion passed; the final Auditor acceptance decision is recorded in §8.

| Contract test ID | Result | CI run / step | Expected outcome | Observed outcome | Genuine CI log excerpt |
|---|---|---|---|---|---|
| `test_signal_to_approval_to_order_flow` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Correct Signal is approved via `/api/v1/signals/{signal_id}/approve`; Risk Engine creates one approved SUBMITTED Order; Decision history remains read-only. | API approval, Order lookup, and GET-only Decision history assertions passed. | `tests/e2e/test_signal_approval_order_flow.py::test_signal_to_approval_to_order_flow PASSED [ 80%]` |
| `test_signal_to_approval_to_partial_fill_to_protection` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Filled quantity receives an ARMED Synthetic Stop before canceling the unfilled remainder. | Cancellation hook observed OPEN Position and ARMED stop at the moment cancellation was requested; remainder then became CANCELLED. | `tests/e2e/test_signal_approval_order_flow.py::test_signal_to_approval_to_partial_fill_to_protection PASSED [ 81%]` |
| `test_signal_to_approval_to_synthetic_stop_execution` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | API approval and fill lead to a stop trigger, SELL execution, and closed Position. | Synthetic Stop executed; SELL filled for the Position quantity and Position became CLOSED. | `tests/e2e/test_signal_approval_order_flow.py::test_signal_to_approval_to_synthetic_stop_execution PASSED [ 82%]` |
| `test_order_idempotency_across_duplicate_requests` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Duplicate approval/order requests with one idempotency key do not create duplicate Orders. | Duplicate calls return the same Order ID and exactly one Order is persisted. | `tests/integration/test_signal_api.py::test_order_idempotency_across_duplicate_requests PASSED [ 38%]` |
| `test_outbox_event_created_in_same_transaction` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Order and approval state/audit/Outbox writes share the transaction; injected Order Outbox failure leaves none of those partial writes committed. | Explicit rollback test observes PENDING Signal, zero Order/audit/Outbox rows for the failed approval, and no idempotency record. | `tests/integration/test_signal_to_order_handoff.py::test_outbox_event_created_in_same_transaction PASSED [ 53%]`<br>`tests/e2e/test_signal_approval_order_flow.py::test_approval_rolls_back_when_outbox_insert_fails PASSED [ 83%]` |
| `test_outbox_publisher_delivers_event` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Publisher delivers a pending event and marks it PUBLISHED. | Consumer received the replayed event and it reached PUBLISHED. | `tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [ 71%]` |
| `test_outbox_retry_on_delivery_failure` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Failed consumer delivery is retried to the configured maximum and then Dead-Lettered. | Injected consumer failure exhausted five retries and created the Dead-Letter row. | `tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [ 71%]` |
| `test_outbox_dead_letter_after_max_retries` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Event reaches DEAD_LETTER after the configured maximum retry count. | Integration assertion observed DEAD_LETTER after five attempts. | `tests/integration/test_signal_to_order_handoff.py::test_outbox_dead_letter_after_max_retries PASSED [ 59%]` |
| `test_dead_letter_event_is_persistent` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Committed Dead-Letter row is readable and remains linked to its original Outbox event. | Row and link are read after commit; the separate §21.6 DB-restart test verifies survival after container restart. | `tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [ 71%]`<br>`tests/chaos/test_f3_chaos.py::test_database_restart_does_not_lose_dead_letter_event PASSED [ 93%]` |
| `test_dead_letter_event_is_linked_to_original_event` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Dead-Letter row references the original Outbox event ID. | Query by `original_outbox_event_id` found the expected row. | `tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [ 71%]` |
| `test_dead_letter_metric_is_incremented` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | The target event's retry exhaustion increments the Dead-Letter metric by exactly one. | Before/after counter assertion passed with an increment of one. | `tests/integration/test_outbox_and_workers.py::test_dead_letter_metric_is_incremented PASSED [ 71%]` |
| `test_dead_letter_alert_is_triggered` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Dead-Letter alerting emits an alert and notification. | Test observed at least one alert and one notification. | `tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [ 71%]` |
| `test_dead_letter_replay_requires_admin_approval` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Operational replay is forbidden; Admin replay succeeds and creates a pending replay event. | Operational API call returned 403; Admin API call returned 200 and a PENDING Outbox event. | `tests/integration/test_outbox_and_workers.py::test_dead_letter_admin_only_replay_via_api PASSED [ 75%]` |
| `test_dead_letter_replay_is_audited` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Audit row has `action=DEAD_LETTER_EVENT_REPLAYED`, `actor_role=ADMIN`, and `target_id` equal to the Dead-Letter row ID. | Test finds the persisted row by those real schema values and explicitly asserts action, role, and `target_id == dlq.id`. | `tests/integration/test_outbox_and_workers.py::test_dead_letter_admin_only_replay_via_api PASSED [ 75%]` |
| `test_decision_history_is_queryable` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | GET by Signal UUID/code returns the same decision record and associated history. | Both queries returned the Signal, explanation, and `SIGNAL_CREATED` event. | `tests/integration/test_decision_log.py::test_decision_history_is_queryable_by_signal_id PASSED [ 62%]` |
| `test_decision_history_is_read_only` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Decision Log permits reads and rejects create/write operations; approval mutations stay on the Signal endpoint. | GET returned history; POST `/api/v1/decisions` returned 405. Signal approval tests use only `/api/v1/signals/{signal_id}/approve`. | `tests/integration/test_decision_log.py::test_decision_log_is_read_only PASSED [ 61%]` |

**§21.5 result: 16/16 behaviors PASS in CI.**

## 5. Contract §21.6 — all 13 Chaos and Failure Injection scenarios

Every row records the Contract ID, PASS/FAIL, actual CI run/step, expected outcome, observed outcome, and a genuine pytest line from CI Step 12. The three DB scenarios and the Redis scenario operate on real GitHub Actions service containers; `AsyncMock`-only persistence claims are not used.

| Contract scenario ID | Result | CI run / step | Expected outcome | Observed outcome | Genuine CI log excerpt |
|---|---|---|---|---|---|
| `test_worker_kill_during_order_processing` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Injected worker failure rolls back the in-flight order mutation and leaves the system fail-closed. | Database rollback, Kill Switch/audit state, worker restart metric, and cancellation assertions passed. This is controlled exception injection, not an OS `SIGKILL`. | `tests/chaos/test_f3_chaos.py::test_worker_kill_during_order_processing PASSED [ 88%]` |
| `test_worker_restart_recovers_synthetic_stop` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | A persisted SUBMITTING stop is recovered, re-armed, executed, and closes its Position. | Fresh supervisor recovered and executed the stop; Position closed. Restart is modeled at supervisor/service boundary, not OS process termination. | `tests/chaos/test_f3_chaos.py::test_worker_restart_recovers_synthetic_stop PASSED [ 89%]` |
| `test_worker_restart_does_not_duplicate_stop_order` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Recovery after an accepted adapter receipt must not create a duplicate stop Order or placement. | Reconciliation persisted exactly one Order and observed exactly one idempotency-key placement attempt. | `tests/chaos/test_f3_chaos.py::test_worker_restart_does_not_duplicate_stop_order PASSED [ 90%]` |
| `test_database_restart_during_outbox_delivery` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Actual PostgreSQL service restart interrupts delivery; reconnection/recovery publishes the committed event. | Docker restarted the PostgreSQL service from inside the handler; after database recovery the event reached PUBLISHED. | `tests/chaos/test_f3_chaos.py::test_database_restart_during_outbox_delivery PASSED [ 91%]` |
| `test_database_restart_does_not_lose_committed_order` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Committed Order survives a real PostgreSQL service restart and engine recreation. | Reconnected query returned the same Order ID, client order ID, idempotency key, FILLED state, and quantity. | `tests/chaos/test_f3_chaos.py::test_database_restart_does_not_lose_committed_order PASSED [ 92%]` |
| `test_database_restart_does_not_lose_dead_letter_event` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Dead-Letter record and its Outbox relationship survive real PostgreSQL restart and engine recreation. | Reconnected queries matched the Dead-Letter ID, event ID, payload, OPEN resolution status, original-event link, and DEAD_LETTER Outbox status. | `tests/chaos/test_f3_chaos.py::test_database_restart_does_not_lose_dead_letter_event PASSED [ 93%]` |
| `test_redis_restart_does_not_corrupt_kill_switch_state` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Real Redis restart/reconnect must not corrupt PostgreSQL-backed Kill Switch state. | Test restarted the Actions Redis container, created a fresh client that pinged successfully, and read the still-active Kill Switch/reason from PostgreSQL. | `tests/chaos/test_f3_chaos.py::test_redis_restart_does_not_corrupt_kill_switch_state PASSED [ 94%]` |
| `test_kill_switch_activation_during_partial_fill` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Reconcile the filled amount, cancel the remainder, and disable active Synthetic Stop monitoring safely. | Remainder was canceled and the stop was persisted as CANCELLED while Position remained OPEN. This does **not** claim Position closure or continued ARMED-stop protection. | `tests/chaos/test_f3_chaos.py::test_kill_switch_activation_during_partial_fill PASSED [ 95%]` |
| `test_kill_switch_activation_during_active_order` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Cancel active Paper order and reject new order handoff while Kill Switch is active. | Order was canceled; subsequent approval was rejected with `KILL_SWITCH_ACTIVE`, with no exchange placement attempt. | `tests/chaos/test_f3_chaos.py::test_kill_switch_activation_during_active_order PASSED [ 96%]` |
| `test_exchange_connector_failure_causes_fail_closed` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Bounded connector failure stops unsafe execution and enters MANUAL_REVIEW without persisting a stop Order. | Three Fake-adapter attempts were observed; stop/Position ended in MANUAL_REVIEW and no stop Order was persisted. | `tests/chaos/test_f3_chaos.py::test_exchange_connector_failure_causes_fail_closed PASSED [ 97%]` |
| `test_stale_market_data_blocks_order_submission` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Risk Engine rejects stale quote before Paper Order submission. | `STALE_MARKET_DATA` was asserted; Paper placement attempts and open orders were empty. | `tests/chaos/test_f3_chaos.py::test_stale_market_data_blocks_order_submission PASSED [ 98%]` |
| `test_paper_network_isolation_under_chaos` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | A simulated live-style endpoint/fake credential request is failure-injected without external egress while `LIVE_TRADING=false`. | `.invalid` request was observed only by MockTransport, injected `ConnectError` was asserted, non-loopback socket attempts stayed at zero, and Paper mode/order assertions passed. No real endpoint or credential was used. | `tests/chaos/test_f3_chaos.py::test_paper_network_isolation_under_chaos PASSED [ 99%]` |
| `test_no_live_order_is_submitted_in_any_failure_scenario` | **PASS** | [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669) / Step 12 | Failure scenarios remain restricted to Fake/Paper adapters and create no live order. | `LIVE_TRADING=false`, `PAPER_TRADING=true`, allowed adapter set, injected Paper failure, and empty Paper order registry were asserted. | `tests/chaos/test_f3_chaos.py::test_no_live_order_is_submitted_in_any_failure_scenario PASSED [100%]` |

**§21.6 result: 13/13 scenarios PASS in CI.** No F4 execution is implied by these tests. F3 acceptance is recorded in §8. The Kill Switch partial-fill limitation is recorded exactly as observed above.

## 6. Commit structure and acceptance boundary

| Sequence | Commit / message | Scope |
|---|---|---|
| 1 | `ea8041fb65d645979a60ca18577c2b4ea71fcbd8` — `test(f3): add missing E2E contract coverage` | Five previously un-evidenced §21.5 behaviors and transaction rollback/metric/audit checks. |
| 2 | `c2fff0221aeb25b0af4bc5e1b53212b14fde49a8` — `test(f3): add F3 chaos recovery and isolation coverage` | Seven previously un-evidenced §21.6 scenarios; complete 13-scenario file. |
| 3 | `0862e345cba37fdc2a36c4ba6cf704f6cea98875` — `docs(f3): add completion evidence v1.1` | Initial Evidence v1.1 and byte-identical implementation mirror. |
| 4 | `9cf204d88fbcc1af0428331f866348a013f6aec0` — `test(f3): add explicit rollback metric and replay audit tests` | Three additional, directly selectable integration tests. |
| 5 | `d717c4fbbc411833a87dc3e88765d17a4838fb84` — `docs(f3): update v1.1 evidence for named regressions` | Evidence supplement and byte-identical mirror. |
| 6 | `3af59a4bcb61eeea4cfb8dc33c43e95ac4ef84c1` — `docs(f3): align evidence with final package CI` | Audit-package evidence refresh. |
| 7 | `docs(f3): record F3 acceptance and F4 authorization` | This administrative disposition update and byte-identical mirror only; no code or test changes. |

`PASS` in the tables records test outcomes; the Auditor's written F3 acceptance is recorded in §8. F4 is authorized by that decision, but implementation has not started and must wait for the formal F4 execution document from the consultant. F5 and F6 remain unauthorized.

## 7. Audit package supplement — 2026-10-05

This supplement records the additional named regression tests and the passing source-test CI run. It supplements, and does not replace or renumber, the §21.5 16/16 and §21.6 13/13 contract mappings above. The final package commit and its exact CI run are declared in the accompanying `F3_REMEDIATION_MANIFEST.md`.

| Item | Verified value |
|---|---|
| Code commit containing the additional integration tests | `9cf204d88fbcc1af0428331f866348a013f6aec0` |
| Branch | `arena/01a0fca1-crypto-management-portfolio` |
| CI run | [37272810591](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591) — **PASS**, validates the code commit above unchanged; this source-test run's head SHA is the preceding evidence commit, not the final refreshed package commit |
| CI job | [111643231479 — Lint, Typecheck, Migrate, and Test (Python 3.12)](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591/job/111643231479) — **PASS** |
| Test/coverage steps | Step 12 mandatory F2/F3 suites **PASS**; Step 14 full pytest with coverage gates **PASS**; Steps 15–16 coverage upload/metrics **PASS** |
| Coverage artifact | [`coverage-report`, ID 11329675678](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591/artifacts/11329675678), 11,425 bytes, not expired (expires 2027-01-03) |
| Current CI-reported overall coverage | **95.27% line (4,005 / 4,204)**; **84.33% branch (651 / 772)** |
| `coverage.xml` SHA-256 | `080827249b7c9bd4ea646ed527b5116af3945e76b51fba797c90aa27c92afb5a` |
| Artifact digest | `sha256:ae4b92f80aac7f40788a82707807874e210bce5ed9680f8b6a1f7a879a167bb5` |

### Additional directly selectable integration tests

All three tests below are in the committed `tests/integration/test_outbox_and_workers.py`. They are additional F3 regression checks and do not replace a §21.5 or §21.6 scenario. The final full-pytest coverage step passed on Run `37272810591`; the test IDs were collected by the full suite. No approval-timeout recovery test was substituted for any Chaos contract scenario.

| Test ID | Expected outcome | Observed/asserted outcome | CI result |
|---|---|---|---|
| `test_signal_approval_rolls_back_when_outbox_insert_fails` | A failure inserting `ORDER_CREATED` during `POST /api/v1/signals/{signal_id}/approve` rolls back approval, Order, audit, Outbox, and idempotency writes. | Injected insert failure is observed; Signal remains `PENDING_APPROVAL`; Order, approval/Order audit and Outbox rows, and idempotency state are absent. | **PASS**, Run `37272810591`, Step 14 full pytest |
| `test_dead_letter_event_increments_metric` | Exhausting retries for the target Outbox event creates an OPEN Dead-Letter record and increments the labeled Dead-Letter counter exactly once. | Test asserts retry count `5`, resolution `OPEN`, and `counter_after == counter_before + 1`. | **PASS**, Run `37272810591`, Step 14 full pytest |
| `test_dead_letter_replay_creates_admin_audit_record` | An Admin replay creates a pending replay event and a schema-correct audit row. | Test asserts `action=DEAD_LETTER_EVENT_REPLAYED`, `actor_role=ADMIN`, and `target_id == dead_letter_event.id`. | **PASS**, Run `37272810591`, Step 14 full pytest |

### Per-module and state-machine coverage availability

CI Step 14 passed the configured `--fail-under=90` per-module coverage gates, including `app/services/state_machine.py`; the state-machine module therefore passed its 90% minimum gate. The precise per-file percentages are contained in the linked `coverage.xml` artifact. The sandbox could not retrieve the artifact payload from GitHub's signed blob URL (the download returned `EOF`), so no per-module or state-machine numeric percentage is guessed or restated here. The Auditor can inspect those exact values directly in artifact `11329675678`.

### Implementer declaration

I confirm that the committed 13-scenario file remains `tests/chaos/test_f3_chaos.py`, that all 13 §21.6 rows remain separately mapped and passing, and that the three directly selectable integration tests above were added in code commit `9cf204d88fbcc1af0428331f866348a013f6aec0`. The Signal approval route remains `POST /api/v1/signals/{signal_id}/approve`; Decision API remains read-only. Database-restart scenarios use real PostgreSQL service restarts and check committed state after reconnect; the Redis restart scenario checks the authoritative Kill Switch state in PostgreSQL after reconnect. No Live Trading environment, real adapter, real credential, exchange connectivity, or F4-or-higher feature was introduced. F3 acceptance is recorded in §8; F4 implementation remains unstarted pending the formal F4 execution document, and F5/F6 remain unauthorized.

## 8. Final Auditor decision and phase handoff

**Status:** `ACCEPTED`
**Auditor Decision:** `F3 ACCEPTED — F4 AUTHORIZED`
**Decision Date:** `2026-10-05`
**Baseline Commit:** `9cf204d88fbcc1af0428331f866348a013f6aec0`
**Accepted baseline tag:** `f3-accepted` → `9cf204d88fbcc1af0428331f866348a013f6aec0`

### Decision basis

- Contract §21.5: **16/16 E2E tests PASS**.
- Contract §21.6: **13/13 Chaos scenarios PASS**.
- Original CI Run [37229765669](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765669): **PASS**.
- Corrective CI Run [37272810591](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37272810591): **PASS**.
- Security Scan [37229765673](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765673): **PASS**.
- Docker Build / Compose Validation [37229765664](https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37229765664): **PASS**.
- Line coverage: **95.27%**; branch coverage: **84.33%**.
- The Auditor's final basis records critical modules `state_machine` and `signal_lifecycle` above **90%**.
- No F4/F5/F6 scope creep was identified.

**Administrative status updated after final auditor decision.**
**No production code changed as part of this status update.**

### Authorization boundary and carried limitations

F4 is authorized by the decision above, but implementation **must not start** until the formal F4 execution document is received from the consultant. F5 and F6 remain unauthorized. `LIVE_TRADING=false` remains required. Live Trading, Direct Mode, real exchange adapters, real API keys, and real credentials remain prohibited.

The following limitations are explicitly transferred to later phase gates and are not represented as solved by F3:

1. Worker-kill behavior in F3 is exercised with exception injection, not an operating-system `SIGKILL`; deeper failure-mode analysis is deferred to F5.
2. During a partial fill, the F3 Kill Switch cancels the remaining order and stops Synthetic Stop monitoring. It does not implement complete position handling. The policy must be determined in the applicable formal F4/F5 execution planning; no such implementation is included here.
