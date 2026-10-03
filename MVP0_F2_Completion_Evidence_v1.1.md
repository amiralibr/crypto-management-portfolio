# MVP-0 Phase F2 Data and Risk Core — Official Completion Evidence Bundle (`v1.1`)

- **Document ID:** `MVP0_F2_Completion_Evidence_v1.1`
- **Repository:** `amiralibr/crypto-management-portfolio`
- **Branch:** `arena/01a0fca1-crypto-management-portfolio`
- **Approved Phase F1 Baseline:** `release/f1-candidate` @ `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`Status: ACCEPTED BY AUDITOR`)
- **Evaluated Phase F2 Code Commit (`v1.1`):** `5e7758846169614daeb39e3f5346037f245af856` (`release/f2-candidate`)
- **GitHub Actions CI Run ID on `5e7758846169614daeb39e3f5346037f245af856`:** `37151399699` / Job `111285878884` (`completed / success`)
- **Security & Paper Isolation Run ID on `5e7758846169614daeb39e3f5346037f245af856`:** `37151399712` / Job `111285878967` (`completed / success`)
- **Docker Build & Compose Validation Run ID on `5e7758846169614daeb39e3f5346037f245af856`:** `37151399696` / Job `111285878988` (`completed / success`)
- **Phase F2 Status:** `READY FOR FINAL AUDITOR ACCEPTANCE` (All 2 previously open F2 items are **`RESOLVED`**)
- **Phase F3 Status:** `FROZEN / BLOCKED` (Zero F3 Signal Engine, Orders API, Positions API, Decision Log API, or Dashboard code added; F3 remains strictly blocked until formal F2 acceptance)

---

## 1. Resolution of the 2 Previously Open F2 Items (`Status: RESOLVED`)

### 1.1 Open Item #1 — Kill Switch Service Routing & Internal Port Isolation (`RESOLVED`)

| Attribute | Evidence |
|---|---|
| **Status** | **`RESOLVED`** |
| **Requirement** | 1. `POST /api/v1/system/emergency-stop` is served exclusively by `mvp0_api` on port `8000`.<br>2. `kill_switch` service on port `8001` is internal and does NOT expose the public `emergency-stop` endpoint.<br>3. `mvp0_api` writes Kill Switch state into PostgreSQL.<br>4. `kill_switch` service reads Kill Switch state and Risk Engine heartbeat from PostgreSQL. |
| **File Paths & Line Ranges** | - `app/main.py:216` & `app/api/v1/__init__.py:12` & `app/api/v1/system.py:72–280`: `mvp0_api` (`port 8000`) mounts `POST /api/v1/system/emergency-stop`, `GET /api/v1/system/emergency-stop`, and `/api/v1/system/emergency-stop/resume-requests*` and persists `SystemState(state_key="KILL_SWITCH")` in PostgreSQL via `KillSwitchService.activate()` (`app/services/kill_switch.py:182–415`).<br>- `app/kill_switch_service.py:44–70`: `read_kill_switch_and_heartbeat_from_db()` reads `SystemState(state_key="KILL_SWITCH")` and `SystemState(state_key="RISK_ENGINE_HEARTBEAT")` from PostgreSQL.<br>- `app/kill_switch_service.py:72–95`: `run_heartbeat_monitor_once()` reads `RISK_ENGINE_HEARTBEAT` from PostgreSQL and invokes `KillSwitchService.check_risk_engine_heartbeat()` (`app/services/kill_switch.py:417–448`) when missing or stale (`> 60s`).<br>- `app/kill_switch_service.py:170–252`: `create_kill_switch_app()` mounts only internal probes (`/healthz` `:188–196`, `/readyz` `:198–219`, `GET /internal/kill-switch/state` `:221–232`, `POST /api/v1/kill-switch/heartbeat-check` `:234–250`) and does **not** mount `system_router` (`/api/v1/system/emergency-stop` returns `404 Not Found` on `:8001`).<br>- `docker-compose.yml:33–89`: Service `api` (`container_name: mvp0_api`) publishes `ports: ["8000:8000"]`.<br>- `docker-compose.yml:91–146`: Service `kill_switch` uses `expose: ["8001"]` (`lines 132–133`) with **zero host `ports:` bindings**.<br>- `docker-compose.paper.yml:87–140`: Service `paper_kill_switch` runs on internal `mvp0_paper_network` (`internal: true`, `lines 146–150`) with zero host `ports:` bindings.<br>- `docs/api/README.md:18–35` & `docs/runbooks/kill-switch-active.md:3–7`: Document the exact routing separation between `mvp0_api:8000` and internal `kill_switch:8001`. |
| **Test Names & Line Ranges** | - `tests/chaos/test_f2_chaos.py:144–225` (`test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch` — asserts `POST /api/v1/system/emergency-stop` on `ks_app` `:8001` returns `404` at `lines 189–194`, triggers heartbeat check via `ks_app`, reads `GET /internal/kill-switch/state` on `ks_app` at `lines 205–211`, and verifies `GET /api/v1/system/emergency-stop` on `mvp0_api` `:8000` at `lines 214–223`).<br>- `tests/chaos/test_f2_chaos.py:229–305` (`test_chaos_kill_switch_service_restart_preserves_state` — activates Kill Switch via `POST /api/v1/system/emergency-stop` on `mvp0_api` `:8000` at `lines 241–255`, asserts `GET /api/v1/system/emergency-stop` on `ks_app` `:8001` returns `404` at `lines 262–266`, and verifies `GET /internal/kill-switch/state` on `ks_app` reads `is_active=True` and `last_heartbeat_at` from PostgreSQL before and after restart at `lines 268–294`).<br>- `tests/integration/test_kill_switch.py:131–595` (15 integration tests on `mvp0_api`). |
| **CI Run IDs & Steps** | - `CI` Run `37151399699` (Job `111285878884`) Step 12 & Step 13 (`completed / success`)<br>- `Docker Build & Compose Validation` Run `37151399696` (Job `111285878988`) Step 7 (`Validate Development Docker Compose startup (API + Independent Kill Switch)`, verifying `HostConfig.PortBindings` on `kill_switch` is `{}` and `http://127.0.0.1:8001/api/v1/system/emergency-stop` returns `404`) & Step 8 (`completed / success`) |
| **Log Excerpt** | ```text
tests/chaos/test_f2_chaos.py::test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch PASSED [ 78%]
tests/chaos/test_f2_chaos.py::test_chaos_kill_switch_service_restart_preserves_state PASSED [ 85%]
Verified 404 on internal kill_switch /api/v1/system/emergency-stop
``` |

---

### 1.2 Open Item #2 — `WorkerSupervisor` & Startup Recovery Wired into `app/main.py:lifespan` (`RESOLVED`)

| Attribute | Evidence |
|---|---|
| **Status** | **`RESOLVED`** |
| **Requirement** | Wire into `app/main.py:lifespan` (`Contract §17.1` & `§17.2`):<br>1. Recover active Synthetic Stops (`reconcile_stops_after_restart`)<br>2. Reconcile open positions (`reconcile_open_positions`)<br>3. Start `WorkerSupervisor`<br>4. Start `approval_timeout_worker`, `synthetic_stop_worker`, and `outbox_publisher_worker` |
| **File Paths & Line Ranges** | - `app/main.py:74–185` (`lifespan(app: FastAPI)`):<br>  - `lines 102–110`: Instantiates `PaperTradingAdapter()` and `WorkerSupervisor(exchange_adapter=exchange_adapter, session_factory=session_factory)` and attaches `app.state.worker_supervisor = supervisor`.<br>  - `lines 112–122`: Executes `recovered_stops, recon_report = await supervisor.recover_and_reconcile_on_startup()` (which calls `SyntheticStopService.reconcile_stops_after_restart(session)` at `app/workers/supervisor.py:52` and `ReconciliationService.reconcile_open_positions(session)` at `app/workers/supervisor.py:53–56`) and records initial Risk Engine heartbeat (`RiskEngine().record_heartbeat(hb_session)`).<br>  - `lines 124–150`: Starts all 3 background workers under `WorkerSupervisor.start_worker()` (`app/workers/supervisor.py:114–129`):<br>    1. `approval_timeout_worker` (`app/main.py:127–134` -> `app/workers/approval_timeout.py:36–64`)<br>    2. `synthetic_stop_worker` (`app/main.py:135–142` -> `app/workers/synthetic_stop.py:41–70`)<br>    3. `outbox_publisher_worker` (`app/main.py:143–149` -> `app/workers/outbox_publisher.py:37–59`)<br>  - `lines 167–184`: Graceful shutdown setting `app.state.service_ready = False`, signaling `stop_event.set()`, awaiting `await supervisor.stop_all()`, closing Redis, and disposing PostgreSQL engine. |
| **Test Names & Line Ranges** | - `tests/integration/test_outbox_and_workers.py:466–487` (`test_main_lifespan_starts_supervisor_recovers_stops_and_reconciles_positions` — enters `async with lifespan(app_instance):`, verifies `app_instance.state.worker_supervisor`, `app_instance.state.reconciliation_report is not None`, `isinstance(app_instance.state.recovered_stops_count, int)`, and all 3 workers running in `supervisor._tasks`, then verifies clean shutdown on exit).<br>- `tests/integration/test_outbox_and_workers.py:273–307` (`test_workers_and_supervisor_crash_fail_closed`). |
| **CI Run ID & Steps** | - `CI` Run `37151399699` (Job `111285878884`) Step 12 & Step 13 (`completed / success`) |
| **Log Excerpt** | ```text
tests/integration/test_outbox_and_workers.py::test_workers_and_supervisor_crash_fail_closed PASSED [ 21%]
tests/integration/test_outbox_and_workers.py::test_main_lifespan_starts_supervisor_recovers_stops_and_reconciles_positions PASSED [ 42%]
app/main.py                                    140     10     14      6    90%
app/workers/supervisor.py                       64      3      8      3    92%
``` |

---

## 2. Complete Evidence Table for All Phase F2 Claims

Every claim below includes the exact **file path**, **line range**, **test name**, **CI Run ID**, and **log excerpt**:

| # | F2 Claim | File Path & Line Range | Test File, Function Name & Line Range | CI Run ID & Step | Verbatim Log Excerpt |
|---|---|---|---|---|---|
| **1** | **Independent Internal Kill Switch Service & Container (`:8001`) + Public Emergency-Stop on `mvp0_api` (`:8000`)** | `app/kill_switch_service.py:1–255`; `app/api/v1/system.py:72–280`; `docker/Dockerfile.kill-switch:1–56`; `docker-compose.yml:33–146` (`expose: ["8001"]`); `docker-compose.paper.yml:87–150` (`internal: true`) | `tests/chaos/test_f2_chaos.py:144–305` (`test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`, `test_chaos_kill_switch_service_restart_preserves_state`); `tests/security/test_paper_isolation.py:72–97` | Run `37151399699` Steps 12–13; Run `37151399696` Steps 5–8 | `tests/chaos/test_f2_chaos.py::test_chaos_kill_switch_service_restart_preserves_state PASSED [ 85%]` |
| **2** | **Risk Engine Durable Heartbeat & >60s Timeout Auto-Activation** | `app/core/config.py:47,90,189–197`; `app/services/risk_engine.py:18,492–569` (`record_heartbeat`, `get_last_heartbeat`, `evaluate_with_heartbeat`); `app/workers/watchdog.py:15–33`; `app/services/kill_switch.py:52,417–448` (`check_risk_engine_heartbeat`); `app/kill_switch_service.py:72–114` | `tests/chaos/test_f2_chaos.py:144–225` (`test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`); `tests/e2e/test_signal_lifecycle_e2e.py:66–75` | Run `37151399699` Steps 12–13 | `tests/chaos/test_f2_chaos.py::test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch PASSED [ 78%]` |
| **3** | **24-Hour Resume Request Expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400`)** | `app/core/config.py:46,87–89,178–186`; `app/services/kill_switch.py:14,50,486,541–554`; `.env.example:35`; `docker-compose.yml:67,125`; `docker-compose.paper.yml:66,122` | `tests/integration/test_kill_switch.py:487–521` (`test_expired_resume_request_cannot_be_approved`); `tests/unit/test_config.py:121–165` (`test_f2_risk_and_kill_switch_settings_validation`) | Run `37151399699` Step 13 | `tests/integration/test_kill_switch.py::test_expired_resume_request_cannot_be_approved PASSED` |
| **4** | **Max Risk Per Trade Ceiling `0.005` (`0.5%`), Rejecting `>= 0.01`** | `app/core/config.py:45,86,168–176`; `app/services/risk_engine.py:12,17,75–81,226–236,368–377` (`MAX_RISK_PER_TRADE = Decimal("0.005")`) | `tests/unit/test_risk_engine.py:25–48` (`test_max_risk_per_trade_is_0_5_percent`), `tests/unit/test_risk_engine.py:245–282` (`test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01`), `tests/e2e/test_signal_lifecycle_e2e.py:232–267` (`test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`) | Run `37151399699` Steps 12–13 | `tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher PASSED [ 57%]` |
| **5** | **E2E Tests Using `TestSignalFactory` (Without Real Signal Engine)** | `tests/factories.py:1–152` (`TestSignalFactory`); `tests/e2e/test_signal_lifecycle_e2e.py:1–295` | `test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory` (`:34–229`), `test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher` (`:232–267`), `test_e2e_signal_expired_by_price_drift_with_test_signal_factory` (`:270–295`) | Run `37151399699` Steps 12–13 | `tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory PASSED [ 50%]` |
| **6** | **Dead-Letter Persistence & Admin-Only Replay (`403` Operational / `200` Admin)** | `app/services/outbox.py:222–288,404–473` (`replay_dead_letter`); `app/schemas/system.py:85–112`; `app/api/v1/system.py:282–315` (`POST /api/v1/system/dead-letters/{dead_letter_id}/replay`) | `tests/integration/test_outbox_and_workers.py:37–156` (`test_outbox_delivery_retry_dead_letter_and_replay`), `tests/integration/test_outbox_and_workers.py:391–463` (`test_dead_letter_admin_only_replay_via_api`) | Run `37151399699` Steps 12–13 | `tests/integration/test_outbox_and_workers.py::test_dead_letter_admin_only_replay_via_api PASSED [ 35%]` |
| **7** | **Minimal 5 F2 Chaos Scenarios** | `tests/chaos/test_f2_chaos.py:1–368` | `test_chaos_api_disconnection_and_recovery` (`:42–140`), `test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch` (`:144–225`), `test_chaos_kill_switch_service_restart_preserves_state` (`:229–305`), `test_chaos_database_disconnection_fails_closed` (`:309–328`), `test_chaos_redis_restart_preserves_durable_domain_state` (`:332–368`) | Run `37151399699` Steps 12–13 | `tests/chaos/test_f2_chaos.py ..... [  4%]` (`5 passed`) |
| **8** | **Single Consolidated Ruff Step in CI** | `.github/workflows/ci.yml:69–72` (`Run Ruff lint and format checks`) | Verified in CI Step 7 | Run `37151399699` Step 7 | `All checks passed! / 97 files already formatted` |
| **9** | **`FORBIDDEN_DURABLE_PREFIXES` as Central Defensive Runtime Control** | `app/core/config.py:23–43,74`; `app/core/redis.py:6,19,43–49` (defensive runtime guard enforcing `Contract §5.2` transient-only Redis rule) | `tests/chaos/test_f2_chaos.py:332–368` (`test_chaos_redis_restart_preserves_durable_domain_state`); `tests/integration/test_redis.py:42–68` | Run `37151399699` Steps 12–13 | `tests/chaos/test_f2_chaos.py::test_chaos_redis_restart_preserves_durable_domain_state PASSED [100%]` |
| **10** | **`app/main.py:lifespan` Startup Recovery & `WorkerSupervisor` Wiring** | `app/main.py:74–185`; `app/workers/supervisor.py:37–140` | `tests/integration/test_outbox_and_workers.py:466–487` (`test_main_lifespan_starts_supervisor_recovers_stops_and_reconciles_positions`) | Run `37151399699` Steps 12–13 | `tests/integration/test_outbox_and_workers.py::test_main_lifespan_starts_supervisor_recovers_stops_and_reconciles_positions PASSED [ 42%]` |

---

## 3. Direct CI Run `37151399699` & Coverage Excerpts (`Commit 5e7758846169614daeb39e3f5346037f245af856`)

### 3.1 GitHub Actions Workflow Summary on `5e7758846169614daeb39e3f5346037f245af856`

| Workflow Name | Workflow File | Run ID | Job ID | Duration | Status / Conclusion |
|---|---|---|---|---|---|
| **CI** (`Lint, Typecheck, Migrate, and Test (Python 3.12)`) | `.github/workflows/ci.yml` | `37151399699` | `111285878884` | `1m29s` (`20:24:09Z` -> `20:25:38Z`) | **`completed / success`** |
| **Security & Paper Isolation Scan** | `.github/workflows/security-scan.yml` | `37151399712` | `111285878967` | `40s` (`20:24:08Z` -> `20:24:48Z`) | **`completed / success`** |
| **Docker Build & Compose Validation** | `.github/workflows/docker-build.yml` | `37151399696` | `111285878988` | `2m39s` (`20:24:08Z` -> `20:26:47Z`) | **`completed / success`** |

### 3.2 Verbatim Output of CI Step 12 & Step 13 (`108 passed`, `93.22%` Total Coverage)

```text
$ poetry run pytest -v tests/integration/test_outbox_and_workers.py tests/e2e/test_signal_lifecycle_e2e.py tests/chaos/test_f2_chaos.py --no-cov
collected 14 items

tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [  7%]
tests/integration/test_outbox_and_workers.py::test_paper_trading_adapter_and_registry_constraints PASSED [ 14%]
tests/integration/test_outbox_and_workers.py::test_workers_and_supervisor_crash_fail_closed PASSED [ 21%]
tests/integration/test_outbox_and_workers.py::test_system_and_risk_api_endpoints PASSED [ 28%]
tests/integration/test_outbox_and_workers.py::test_dead_letter_admin_only_replay_via_api PASSED [ 35%]
tests/integration/test_outbox_and_workers.py::test_main_lifespan_starts_supervisor_recovers_stops_and_reconciles_positions PASSED [ 42%]
tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory PASSED [ 50%]
tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher PASSED [ 57%]
tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_expired_by_price_drift_with_test_signal_factory PASSED [ 64%]
tests/chaos/test_f2_chaos.py::test_chaos_api_disconnection_and_recovery PASSED [ 71%]
tests/chaos/test_f2_chaos.py::test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch PASSED [ 78%]
tests/chaos/test_f2_chaos.py::test_chaos_kill_switch_service_restart_preserves_state PASSED [ 85%]
tests/chaos/test_f2_chaos.py::test_chaos_database_disconnection_fails_closed PASSED [ 92%]
tests/chaos/test_f2_chaos.py::test_chaos_redis_restart_preserves_durable_domain_state PASSED [100%]

============================== 14 passed in 1.80s ==============================
```

```text
$ poetry run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=80
collected 108 items

Name                                         Stmts   Miss Branch BrPart  Cover   Missing
----------------------------------------------------------------------------------------
app/api/v1/__init__.py                          10      0      0      0   100%
app/api/v1/dependencies.py                      13      2      2      1    80%   17-18
app/api/v1/orders.py                             2      0      0      0   100%
app/api/v1/positions.py                          2      0      0      0   100%
app/api/v1/risk.py                              18      2      0      0    89%   39-40
app/api/v1/system.py                            98     12      6      1    88%   55-58, 156, 175-176, 213, 237, 264, 281, 306
app/core/config.py                             167      5     44      5    95%   173, 183, 194, 259, 266
app/core/enums.py                              101      0      0      0   100%
app/core/errors.py                              78     15      6      1    79%   117, 166-169, 216, 253-265, 279-280, 292-293
app/core/logging.py                             88      0     22      1    99%   53->exit
app/core/metrics.py                             22      0      0      0   100%
app/core/redis.py                               61      2      8      0    97%   101-102
app/core/security.py                            35      0     12      0   100%
app/db/models/* (all 13 ORM models)            341      0      0      0   100%
app/db/session.py                               70      2     14      2    95%   76, 86
app/integrations/exchange/base.py               85      4     10      4    92%   130, 139, 145, 152
app/integrations/exchange/errors.py              6      0      0      0   100%
app/integrations/exchange/fake.py              102     13     28      7    85%   106-107, 122, 137, 144, 168, 171, 173, 175, 222, 264-266
app/integrations/exchange/paper.py              19      1      2      1    90%   25
app/integrations/notifications/base.py          14      0      0      0   100%
app/integrations/notifications/telegram.py      15      0      0      0   100%
app/kill_switch_service.py                     114     15      6      2    84%   86-88, 103->exit, 106-109, 113-114, 136-144
app/main.py                                    140     10     14      6    90%   68, 70, 90, 113->125, 176, 177->179, 264-265, 306-309
app/schemas/common.py                            7      0      0      0   100%
app/schemas/risk.py                             16      0      0      0   100%
app/schemas/system.py                           90      0      0      0   100%
app/services/approval_timeout.py               100      4     28      4    94%   54, 71, 109, 215
app/services/kill_switch.py                    308     18     74     13    92%   63, 68, 152, 243->248, 289-297, 306-313, 438->439, 469, 539->554, 563, 627->638, 712, 742, 783
app/services/outbox.py                         177      4     42      5    96%   38, 42-43, 132->135, 217->219, 351->331, 430
app/services/reconciliation.py                  47      3     12      3    90%   65->62, 67-73, 101->109
app/services/risk_engine.py                    299      7     96      2    98%   41, 332-333, 380-382, 540
app/services/state_machine.py                  160      4     38      9    93%   212, 360, 424, 470, 472->480, 563->575, 575->581, 594->600, 612->623
app/services/synthetic_stop.py                 226      7     50     10    94%   104, 130, 241, 253->256, 357, 359->368, 418, 544, 609, 619->645
app/workers/approval_timeout.py                 29     10      2      0    61%   45-63
app/workers/outbox_publisher.py                 26      8      2      0    64%   46-58
app/workers/supervisor.py                       64      3      8      3    92%   70-71, 107->114, 124, 137->139
app/workers/synthetic_stop.py                   27      9      2      0    62%   51-69
app/workers/watchdog.py                         20      3      2      1    82%   19->29, 25-27
----------------------------------------------------------------------------------------
TOTAL                                         3219    163    530     81    93%
Required test coverage of 80% reached. Total coverage: 93.22%
============================= 108 passed in 10.50s =============================
```

| Safety Module Coverage Gate | Minimum Gate | Measured (`v1.1`) | Result |
|---|---|---|---|
| **Total `app/`** | `>= 80%` | **`93.22%` (`93%`)** | **PASS** |
| `app/core/*` | `>= 90%` | **`95%`** | **PASS** |
| `app/db/*` | `>= 90%` | **`99%`** | **PASS** |
| `app/services/risk_engine.py` | `>= 90%` | **`98%`** | **PASS** |
| `app/services/state_machine.py` | `>= 90%` | **`93%`** | **PASS** |
| `app/services/kill_switch.py` | `>= 90%` | **`92%`** | **PASS** |
| `app/core/security.py` | `>= 90%` | **`100%`** | **PASS** |
| `app/services/synthetic_stop.py` | `>= 90%` | **`94%`** | **PASS** |
| `app/services/outbox.py` | `>= 90%` | **`96%`** | **PASS** |

---

## 4. Honest Inventory of `NOT IMPLEMENTED` Items and Target Phases

All Phase F1 and Phase F2 requirements are **100% implemented and resolved**. Every remaining unimplemented item belongs exclusively to **Phase F3** (which is blocked by Auditor directive until formal Phase F2 acceptance):

| # | Item & Governing Reference | Current State in Repository (`5e77588`) | Status | Target Phase |
|---|---|---|---|---|
| **1** | **Real Signal Engine (`Trend Following` + `Mean Reversion` — `Contract §8` / `Master Package §۱۲.۱ MVP-C`)** | Not implemented in F2 per Auditor directive (*"تست‌های E2E با استفاده از TestSignalFactory اضافه شوند، بدون پیاده‌سازی Signal Engine واقعی"*); F2 E2E tests use `TestSignalFactory` (`tests/factories.py:1–152`). | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F2 acceptance) |
| **2** | **Operational HTTP Endpoints for Signals, Orders, and Positions (`Contract §16.3`)** | `GET /api/v1/signals`, `POST /api/v1/signals/{id}/approve`, `POST /api/v1/signals/{id}/reject`, `GET /api/v1/orders`, `GET /api/v1/orders/{id}` (`app/api/v1/orders.py:1–6` is a router stub), and `GET /api/v1/positions` (`app/api/v1/positions.py:1–6` is a router stub) are not implemented yet. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F2 acceptance) |
| **3** | **Read-Only Decision Log HTTP Endpoints (`Contract §16.3`, `§16.4`, `§21.5`)** | `GET /api/v1/decisions` and `GET /api/v1/decisions/{signal_id}` (`test_decision_history_is_queryable`, `test_decision_history_is_read_only`) are not implemented yet. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F2 acceptance) |
| **4** | **Minimal Operator Dashboard / UI Shell (`app/dashboard/` — `F1 Package §3.3` & `Master Package §۱۲.۱ MVP-E`)** | `dashboard/` contains only package placeholders. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F2 acceptance) |
| **5** | **Full Phase F3 End-to-End HTTP Workflow & Full F3 Chaos Injection Suite (`Contract §21.5` & `§21.6`)** | Phase F2 implements the 3 `TestSignalFactory` E2E tests (`tests/e2e/test_signal_lifecycle_e2e.py:1–295`) and the 5 minimal F2 Chaos scenarios (`tests/chaos/test_f2_chaos.py:1–368`). The remaining F3 HTTP workflow tests (`test_order_idempotency_across_duplicate_requests`, etc.) and full F3 chaos suite (`Contract §21.6`) are deferred to Phase F3. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F2 acceptance) |
