# MVP-0 Phase F2 Data and Risk Core — Official Completion Evidence Bundle (`v1.0`)

- **Document ID:** `MVP0_F2_Completion_Evidence_v1.0`
- **Repository:** `amiralibr/crypto-management-portfolio`
- **Branch:** `arena/01a0fca1-crypto-management-portfolio`
- **Approved F1 Baseline:** `release/f1-candidate` @ `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`Status: APPROVED BY AUDITOR`)
- **Evaluated F2 Tag & Commit:** `release/f2-candidate` @ `532cec3` (`532cec34d73a20909ec1a3b014a9796d0e819d7d`; code commit `676a0ed47c6259074483272cd06ec132e7b10334`)
- **Primary CI Run ID on `532cec34d73a20909ec1a3b014a9796d0e819d7d`:** `37142297231` (`completed / success`)
- **Security Scan Run ID on `532cec34d73a20909ec1a3b014a9796d0e819d7d`:** `37142297122` (`completed / success`)
- **Docker & Compose Run ID on `532cec34d73a20909ec1a3b014a9796d0e819d7d`:** `37142297137` (`completed / success`)
- **Phase F3 Status:** `FROZEN / BLOCKED` (Strictly prohibited until official F1 and F2 Auditor sign-off)

---

## 1. Distinction Between Project Phase F2 and Master Package "F2"

In accordance with the governing document hierarchy (`MVP0_Implementation_Contract_v1.2_FINAL.md` [Rank 1] -> `MVP0_F1_Foundation_Implementation_Package_v1.0.md` [Rank 2] -> `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md` [Rank 3]), the label **`F2`** has two distinct meanings that must not be conflated:

| Dimension | **Project Phase F2 (`Data and Risk Core`)** — *Binding for this Repository* | **Master Package v4.3 `Post-MVP (F2)` & Roadmap** — *Reference Context Only* |
|---|---|---|
| **Governing Source** | `MVP0_F1_Foundation_Implementation_Package_v1.0.md` (`§3.3`, `§17`) & `MVP0_Implementation_Contract_v1.2_FINAL.md` (`§8–§13`, `§19`, `§21.1–§21.4`) + Auditor F2 Directives | `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md` (`§۱۲.۱` lines `1441–1485` & `§۲۳.۲` lines `2753–2772`) |
| **Definition of `F2`** | **MVP-0 Phase F2 (`Data and Risk Core` / `Core Safety`)**: Deterministic Risk Engine (`0.005` cap + durable heartbeat), Independent Kill Switch Service & Container (`>60s` heartbeat timeout + `86400s` Two-Person Resume), Persistent Synthetic Stop-Loss (`0s/5s/15s`), Dynamic Approval Timeout & `0.20%` Price Drift Expiry, Order/Signal State Machine, Outbox/Dead-Letter & Admin-only Replay, Paper/Fake Exchange Adapters, `TestSignalFactory` E2E tests, and the 5 minimal F2 Chaos tests. | 1. In `§۲۳.۲` (`line 2763`), **`Post-MVP (F2)`** refers to **JEV (Joint Ensemble Voting / ML) Shadow Mode**, which is **strictly Post-MVP and forbidden in MVP-0** (`Contract §2.2`).<br>2. In `§۱۲.۱` (`lines 1441–1485`), the MVP-0 work breakdown is labeled `MVP-A` through `MVP-E` (`MVP-B: Data + Risk`, `MVP-D: Paper Trading + Independent Kill Switch + Chaos`). |
| **Signal Engine Scope** | **Excluded from F2:** Real Signal Engine (`Trend Following` / `Mean Reversion`) is deferred to Phase F3; F2 E2E tests use `TestSignalFactory` (`tests/factories.py`). | Listed under `MVP-C (Signal + Approval)` in Master Package `§۱۲.۱`. |
| **Chaos Testing Scope** | **Minimal 5 F2 Chaos Scenarios Only (`tests/chaos/test_f2_chaos.py`):** (1) API disconnection, (2) Risk Engine heartbeat timeout `>60s`, (3) Independent Kill Switch restart, (4) PostgreSQL disconnection, (5) Redis outage/restart. | Master Package `§۹.۴` (`lines 1160–1205`) defines a 7-test staging Chaos suite prior to live/controlled execution (`Phase E`), and Contract `§21.6` defines the full F3 Chaos suite. |

---

## 2. Direct Output of GitHub Actions CI Run `37142297231` (`release/f2-candidate @ 532cec3`)

### 2.1 GitHub Actions API Metadata for Commit `532cec34d73a20909ec1a3b014a9796d0e819d7d`

```json
{
  "headSha": "532cec34d73a20909ec1a3b014a9796d0e819d7d",
  "runs": [
    {
      "workflowName": "CI",
      "databaseId": 37142297231,
      "jobId": 111259077065,
      "name": "Lint, Typecheck, Migrate, and Test (Python 3.12)",
      "status": "completed",
      "conclusion": "success",
      "startedAt": "2026-10-03T17:55:42Z",
      "completedAt": "2026-10-03T17:57:08Z",
      "url": "https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37142297231/job/111259077065"
    },
    {
      "workflowName": "Security & Paper Isolation Scan",
      "databaseId": 37142297122,
      "jobId": 111259076495,
      "name": "Secret, Live-Trading, and Paper Isolation Checks",
      "status": "completed",
      "conclusion": "success",
      "startedAt": "2026-10-03T17:55:41Z",
      "completedAt": "2026-10-03T17:56:22Z",
      "url": "https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37142297122/job/111259076495"
    },
    {
      "workflowName": "Docker Build & Compose Validation",
      "databaseId": 37142297137,
      "jobId": 111259076728,
      "name": "Build Docker Images & Verify Single Worker + Compose Startup",
      "status": "completed",
      "conclusion": "success",
      "startedAt": "2026-10-03T17:55:41Z",
      "completedAt": "2026-10-03T17:58:22Z",
      "url": "https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37142297137/job/111259076728"
    }
  ]
}
```

### 2.2 Step Execution Table — CI Run `37142297231` (`.github/workflows/ci.yml`)

```text
Step 1  [completed / success] Set up job
Step 2  [completed / success] Initialize containers (postgres:16-alpine, redis:7-alpine)
Step 3  [completed / success] Checkout repository
Step 4  [completed / success] Set up Python 3.12
Step 5  [completed / success] Install Poetry (poetry==2.5.1)
Step 6  [completed / success] Install dependencies from poetry.lock
Step 7  [completed / success] Run Ruff lint and format checks
Step 8  [completed / success] Run mypy --strict app
Step 9  [completed / success] Run alembic upgrade head
Step 10 [completed / success] Run alembic downgrade base
Step 11 [completed / success] Run alembic upgrade head again
Step 12 [completed / success] Run Dead-Letter, Admin-only Replay, E2E (TestSignalFactory), and Chaos tests
Step 13 [completed / success] Run pytest with coverage gates
Step 14 [completed / success] Upload coverage report (coverage.xml)
Step 26 [completed / success] Post Set up Python 3.12
Step 27 [completed / success] Post Checkout repository
Step 28 [completed / success] Stop containers
Step 29 [completed / success] Complete job
```

### 2.3 Direct Command Outputs for Steps 7, 8, 9–11, 12, and 13 of CI Run `37142297231`

#### Step 7 (`Run Ruff lint and format checks` — `.github/workflows/ci.yml:69–72`):
```text
$ poetry run ruff check .
All checks passed!

$ poetry run ruff format --check .
97 files already formatted
```

#### Step 8 (`Run mypy --strict app` — `.github/workflows/ci.yml:74–75`):
```text
$ poetry run mypy --strict app
Success: no issues found in 65 source files
```

#### Steps 9–11 (`Alembic upgrade head -> downgrade base -> upgrade head` — `.github/workflows/ci.yml:77–84`):
```text
$ poetry run alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_foundation_tables, foundation_tables
INFO  [alembic.runtime.migration] Running upgrade 0001_foundation_tables -> 0002_signals_and_orders, signals_and_orders
INFO  [alembic.runtime.migration] Running upgrade 0002_signals_and_orders -> 0003_positions_and_trades, positions_and_trades
INFO  [alembic.runtime.migration] Running upgrade 0003_positions_and_trades -> 0004_risk_and_synthetic_stops, risk_and_synthetic_stops
INFO  [alembic.runtime.migration] Running upgrade 0004_risk_and_synthetic_stops -> 0005_outbox_and_audit, outbox_and_audit
INFO  [alembic.runtime.migration] Running upgrade 0005_outbox_and_audit -> 0006_kill_switch_dual_approval, kill_switch_dual_approval

$ poetry run alembic downgrade base
INFO  [alembic.runtime.migration] Running downgrade 0006_kill_switch_dual_approval -> 0005_outbox_and_audit, kill_switch_dual_approval
INFO  [alembic.runtime.migration] Running downgrade 0005_outbox_and_audit -> 0004_risk_and_synthetic_stops, outbox_and_audit
INFO  [alembic.runtime.migration] Running downgrade 0004_risk_and_synthetic_stops -> 0003_positions_and_trades, risk_and_synthetic_stops
INFO  [alembic.runtime.migration] Running downgrade 0003_positions_and_trades -> 0002_signals_and_orders, positions_and_trades
INFO  [alembic.runtime.migration] Running downgrade 0002_signals_and_orders -> 0001_foundation_tables, signals_and_orders
INFO  [alembic.runtime.migration] Running downgrade 0001_foundation_tables -> , foundation_tables

$ poetry run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 0006_kill_switch_dual_approval, kill_switch_dual_approval
```

#### Step 12 (`Run Dead-Letter, Admin-only Replay, E2E (TestSignalFactory), and Chaos tests` — `.github/workflows/ci.yml:85–91`):
```text
$ poetry run pytest -v tests/integration/test_outbox_and_workers.py tests/e2e/test_signal_lifecycle_e2e.py tests/chaos/test_f2_chaos.py --no-cov
============================= test session starts ==============================
configfile: pyproject.toml
collected 13 items

tests/integration/test_outbox_and_workers.py::test_outbox_delivery_retry_dead_letter_and_replay PASSED [  7%]
tests/integration/test_outbox_and_workers.py::test_paper_trading_adapter_and_registry_constraints PASSED [ 15%]
tests/integration/test_outbox_and_workers.py::test_workers_and_supervisor_crash_fail_closed PASSED [ 23%]
tests/integration/test_outbox_and_workers.py::test_system_and_risk_api_endpoints PASSED [ 30%]
tests/integration/test_outbox_and_workers.py::test_dead_letter_admin_only_replay_via_api PASSED [ 38%]
tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory PASSED [ 46%]
tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher PASSED [ 53%]
tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_expired_by_price_drift_with_test_signal_factory PASSED [ 61%]
tests/chaos/test_f2_chaos.py::test_chaos_api_disconnection_and_recovery PASSED [ 69%]
tests/chaos/test_f2_chaos.py::test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch PASSED [ 76%]
tests/chaos/test_f2_chaos.py::test_chaos_kill_switch_service_restart_preserves_state PASSED [ 84%]
tests/chaos/test_f2_chaos.py::test_chaos_database_disconnection_fails_closed PASSED [ 92%]
tests/chaos/test_f2_chaos.py::test_chaos_redis_restart_preserves_durable_domain_state PASSED [100%]

============================== 13 passed in 1.16s ==============================
```

---

## 3. Real Coverage Output (CI Run `37142297231`, Step 13 — `.github/workflows/ci.yml:93–102`)

### 3.1 Full 65-File Coverage Table (`107 passed`)

```text
$ poetry run pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=80
============================= test session starts ==============================
configfile: pyproject.toml
testpaths: tests
collected 107 items

tests/chaos/test_f2_chaos.py .....                                       [  4%]
tests/e2e/test_signal_lifecycle_e2e.py ...                               [  7%]
tests/integration/test_database.py ...                                   [ 10%]
tests/integration/test_health_and_readiness.py ......                    [ 15%]
tests/integration/test_kill_switch.py ...............                    [ 29%]
tests/integration/test_migrations.py .....                               [ 34%]
tests/integration/test_outbox_and_workers.py .....                       [ 39%]
tests/integration/test_redis.py ....                                     [ 42%]
tests/integration/test_state_machine.py ......                           [ 48%]
tests/integration/test_synthetic_stop.py .......                         [ 55%]
tests/security/test_authentication.py .........                          [ 63%]
tests/security/test_paper_isolation.py .......                           [ 70%]
tests/unit/test_approval_timeout.py ........                             [ 77%]
tests/unit/test_config.py ..........                                     [ 86%]
tests/unit/test_logging.py ...                                           [ 89%]
tests/unit/test_risk_engine.py ...........                               [100%]

Name                                         Stmts   Miss Branch BrPart  Cover   Missing
----------------------------------------------------------------------------------------
app/__init__.py                                  0      0      0      0   100%
app/api/__init__.py                              0      0      0      0   100%
app/api/v1/__init__.py                          10      0      0      0   100%
app/api/v1/dependencies.py                      13      2      2      1    80%   17-18
app/api/v1/orders.py                             2      0      0      0   100%
app/api/v1/positions.py                          2      0      0      0   100%
app/api/v1/risk.py                              18      2      0      0    89%   39-40
app/api/v1/system.py                            98     12      6      1    88%   55-58, 156, 175-176, 213, 237, 264, 281, 306
app/core/__init__.py                             0      0      0      0   100%
app/core/config.py                             167      5     44      5    95%   173, 183, 194, 259, 266
app/core/enums.py                              101      0      0      0   100%
app/core/errors.py                              78     15      6      1    79%   117, 166-169, 216, 253-265, 279-280, 292-293
app/core/logging.py                             88      0     22      1    99%   53->exit
app/core/metrics.py                             22      0      0      0   100%
app/core/redis.py                               61      2      8      0    97%   101-102
app/core/security.py                            35      0     12      0   100%
app/db/__init__.py                               0      0      0      0   100%
app/db/models/__init__.py                       14      0      0      0   100%
app/db/models/approval_request.py               28      0      0      0   100%
app/db/models/audit_log.py                      25      0      0      0   100%
app/db/models/dead_letter_event.py              29      0      0      0   100%
app/db/models/exchange_account.py               17      0      0      0   100%
app/db/models/order.py                          31      0      0      0   100%
app/db/models/outbox_event.py                   23      0      0      0   100%
app/db/models/position.py                       26      0      0      0   100%
app/db/models/risk_rule.py                      25      0      0      0   100%
app/db/models/signal.py                         32      0      0      0   100%
app/db/models/strategy.py                       19      0      0      0   100%
app/db/models/synthetic_stop.py                 28      0      0      0   100%
app/db/models/system_state.py                   26      0      0      0   100%
app/db/models/trade.py                          18      0      0      0   100%
app/db/repositories/__init__.py                  0      0      0      0   100%
app/db/session.py                               70      3     14      2    94%   76, 86, 132
app/integrations/__init__.py                     0      0      0      0   100%
app/integrations/exchange/__init__.py            5      0      0      0   100%
app/integrations/exchange/base.py               85      4     10      4    92%   130, 139, 145, 152
app/integrations/exchange/errors.py              6      0      0      0   100%
app/integrations/exchange/fake.py              102     13     28      7    85%   106-107, 122, 137, 144, 168, 171, 173, 175, 222, 264-266
app/integrations/exchange/paper.py              19      1      2      1    90%   25
app/integrations/notifications/__init__.py       3      0      0      0   100%
app/integrations/notifications/base.py          14      0      0      0   100%
app/integrations/notifications/telegram.py      15      0      0      0   100%
app/kill_switch_service.py                     104     12      6      2    85%   52-54, 69->exit, 72-75, 79-80, 107, 112-113
app/main.py                                    109     14     10      5    84%   46, 48, 65, 74-84, 90, 92, 177-178, 219-222
app/schemas/__init__.py                          0      0      0      0   100%
app/schemas/common.py                            7      0      0      0   100%
app/schemas/orders.py                            0      0      0      0   100%
app/schemas/positions.py                         0      0      0      0   100%
app/schemas/risk.py                             16      0      0      0   100%
app/schemas/signals.py                           0      0      0      0   100%
app/schemas/system.py                           90      0      0      0   100%
app/services/__init__.py                         8      0      0      0   100%
app/services/approval_timeout.py               100      4     28      4    94%   54, 71, 109, 215
app/services/kill_switch.py                    308     18     74     12    92%   63, 68, 152, 289-297, 306-313, 438->439, 469, 539->554, 563, 627->638, 712, 742, 783
app/services/outbox.py                         177      4     42      5    96%   38, 42-43, 132->135, 217->219, 351->331, 430
app/services/reconciliation.py                  47      3     12      3    90%   65->62, 67-73, 101->109
app/services/risk_engine.py                    299      8     96      3    97%   41, 332-333, 380-382, 512, 540
app/services/state_machine.py                  160      4     38      9    93%   212, 360, 424, 470, 472->480, 563->575, 575->581, 594->600, 612->623
app/services/synthetic_stop.py                 226      7     50     10    94%   104, 130, 241, 253->256, 357, 359->368, 418, 544, 609, 619->645
app/workers/__init__.py                          6      0      0      0   100%
app/workers/approval_timeout.py                 29     10      2      0    61%   45-63
app/workers/outbox_publisher.py                 26      8      2      0    64%   46-58
app/workers/supervisor.py                       64     14      8      1    71%   70-71, 107->114, 122-130, 134-139
app/workers/synthetic_stop.py                   27      9      2      0    62%   51-69
app/workers/watchdog.py                         20      3      2      1    82%   19->29, 25-27
----------------------------------------------------------------------------------------
TOTAL                                         3178    177    526     78    93%
Coverage XML written to file coverage.xml

Required test coverage of 80% reached. Total coverage: 92.68%
============================= 107 passed in 7.17s ==============================
```

### 3.2 Mandatory Safety Module Coverage Gates (`.github/workflows/ci.yml:95–102`)

| Command Executed in CI Step 13 | Minimum Gate | Measured Coverage | Stmts | Miss | Branch | BrPart | Result |
|---|---|---|---|---|---|---|---|
| `coverage report --include="app/core/*" --fail-under=90` | `>= 90%` | **`95%`** | `552` | `22` | `92` | `7` | **PASS** |
| `coverage report --include="app/db/*" --fail-under=90` | `>= 90%` | **`99%`** | `411` | `3` | `14` | `2` | **PASS** |
| `coverage report --include="app/services/risk_engine.py" --fail-under=90` | `>= 90%` | **`97%`** | `299` | `8` | `96` | `3` | **PASS** |
| `coverage report --include="app/services/state_machine.py" --fail-under=90` | `>= 90%` | **`93%`** | `160` | `4` | `38` | `9` | **PASS** |
| `coverage report --include="app/services/kill_switch.py" --fail-under=90` | `>= 90%` | **`92%`** | `308` | `18` | `74` | `12` | **PASS** |
| `coverage report --include="app/core/security.py" --fail-under=90` | `>= 90%` | **`100%`** | `35` | `0` | `12` | `0` | **PASS** |
| `coverage report --include="app/services/synthetic_stop.py" --fail-under=90` | `>= 90%` | **`94%`** | `226` | `7` | `50` | `10` | **PASS** |
| `coverage report --include="app/services/outbox.py" --fail-under=90` | `>= 90%` | **`96%`** | `177` | `4` | `42` | `5` | **PASS** |

---

## 4. Exact Code Path, Docker Service, Test, and CI Step Matrix for Every F2 Claim

### 4.1 Independent Kill Switch Service & Container + >60s Heartbeat Timeout

- **Code Paths & Line Numbers:**
  - `app/kill_switch_service.py:1–205`:
    - `run_heartbeat_monitor_once()` (`lines 29–46`)
    - `_heartbeat_monitor_loop(interval_seconds)` (`lines 49–65`)
    - `kill_switch_lifespan(app)` (`lines 68–115`)
    - `create_kill_switch_app()` (`lines 118–202`), mounting `/healthz` (`:147`), `/readyz` (`:158`), `/metrics` (`:141`), `POST /api/v1/kill-switch/heartbeat-check` (`:181`), and `system_router.router` under `prefix="/api/v1"` (`:196`).
  - `app/services/risk_engine.py:18,492–569`:
    - `RISK_ENGINE_HEARTBEAT_STATE_KEY = "RISK_ENGINE_HEARTBEAT"` (`line 18`)
    - `RiskEngine.record_heartbeat(session, *, now=None)` (`lines 492–532`)
    - `RiskEngine.get_last_heartbeat(session)` (`lines 534–541`)
    - `RiskEngine.evaluate_with_heartbeat(session, data, *, now=None)` (`lines 543–569`)
  - `app/workers/watchdog.py:15–33`: `check_system_watchdog(session)` records Risk Engine heartbeat on each watchdog cycle.
  - `app/services/kill_switch.py:52,417–448`: `KillSwitchService.check_risk_engine_heartbeat(session, *, timeout_seconds=60, now=None)` activates Kill Switch when `RISK_ENGINE_HEARTBEAT` is missing or `elapsed_seconds > 60`.
  - `app/core/config.py:47,90,189–197`: `DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS = 60` and validator enforcing `0 < value <= 60`.
- **Docker Service Definitions:**
  - `docker/Dockerfile.kill-switch:1–56`: Multi-stage `python:3.12.8-slim-bookworm`, `USER 10001` (`line 52`), `EXPOSE 8001` (`line 54`), `CMD ["uvicorn", "app.kill_switch_service:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]` (`line 56`).
  - `docker-compose.yml:90–145`: Service `kill_switch` (`build.dockerfile: docker/Dockerfile.kill-switch`, port `8001:8001`, healthcheck `http://127.0.0.1:8001/readyz`).
  - `docker-compose.paper.yml:87–140`: Service `paper_kill_switch` (`build.dockerfile: docker/Dockerfile.kill-switch`, attached solely to `paper_network` / `mvp0_paper_network` with `internal: true` at `lines 146–150`, zero host ports).
- **Test Evidence:**
  - `tests/chaos/test_f2_chaos.py:143–205` (`test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`)
  - `tests/chaos/test_f2_chaos.py:208–263` (`test_chaos_kill_switch_service_restart_preserves_state`)
  - `tests/security/test_paper_isolation.py:72–97` (`test_paper_services_only_attach_to_paper_network`)
- **CI Step Evidence:**
  - `CI` Run `37142297231` Step 12 & Step 13 (`.github/workflows/ci.yml:85–102`)
  - `Docker Build & Compose Validation` Run `37142297137` Step 5 (`Build Independent Kill Switch Docker image`), Step 6 (`Verify runtime command uses exactly one worker and non-root UID 10001`), Step 7 (`Validate Development Docker Compose startup (API + Independent Kill Switch)`), Step 8 (`Validate Paper Docker Compose startup and isolation (Paper API + Paper Kill Switch)`).

### 4.2 Max Risk Per Trade Ceiling (`0.005` / `0.5%`, Rejecting `>= 0.01`)

- **Code Paths & Line Numbers:**
  - `app/core/config.py:45,86,168–176`: `MAX_RISK_PER_TRADE_PCT_CEILING = Decimal("0.005")`, `MAX_RISK_PER_TRADE_PCT = Decimal("0.005")`, validator rejecting `<= 0` or `> Decimal("0.005")`.
  - `app/services/risk_engine.py:12,17,75–81,226–236,368–377`: `MAX_RISK_PER_TRADE = Decimal("0.005")` enforced in `InvestmentPolicySnapshot.validate()`, `RiskEngine.evaluate()`, and `RiskEngine.calculate_position_size()`.
  - `.env.example:34`, `docker-compose.yml:65,123`, `docker-compose.paper.yml:65,121`, `.github/workflows/ci.yml:50`: `MAX_RISK_PER_TRADE_PCT: "0.005"`.
- **Test Evidence:**
  - `tests/unit/test_risk_engine.py:25–48` (`test_max_risk_per_trade_is_0_5_percent`)
  - `tests/unit/test_risk_engine.py:245–282` (`test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01`)
  - `tests/e2e/test_signal_lifecycle_e2e.py:232–267` (`test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`)
  - `tests/unit/test_config.py:121–165` (`test_f2_risk_and_kill_switch_settings_validation`)
- **CI Step Evidence:** `CI` Run `37142297231` Step 12 & Step 13.

### 4.3 Kill Switch Resume Request 24-Hour Expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400`) & Dynamic Signal Approval Timeout

- **Code Paths & Line Numbers:**
  - `app/core/config.py:46,87–89,178–186`: `REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS = 86400`; validator rejects any value `!= 86400`.
  - `app/services/kill_switch.py:14,50,486,541–554`: `KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS = 86400`; `create_resume_request` sets `expires_at = current_time + timedelta(seconds=86400)`; `approve_resume_request` marks expired requests `EXPIRED` and raises `KillSwitchConflictError`.
  - `app/services/approval_timeout.py:25–30,50–74,116–205`: `DYNAMIC_TIMEOUT_BY_TIMEFRAME_SECONDS = {"1H": 300, "4H": 900, "1D": 1800}` and `PRICE_DRIFT_THRESHOLD = Decimal("0.002")` (`0.20%`).
- **Test Evidence:**
  - `tests/integration/test_kill_switch.py:487–521` (`test_expired_resume_request_cannot_be_approved`)
  - `tests/chaos/test_f2_chaos.py:224–255` (`test_chaos_kill_switch_service_restart_preserves_state`)
  - `tests/unit/test_approval_timeout.py:79–229` (8 unit/integration tests for timeframe timeout and `0.20%` price drift)
- **CI Step Evidence:** `CI` Run `37142297231` Step 12 & Step 13.

### 4.4 Dead-Letter Persistence & Admin-Only Replay

- **Code Paths & Line Numbers:**
  - `app/services/outbox.py:222–288`: `record_delivery_failure()` moves events exceeding `OUTBOX_MAX_RETRIES = 5` to `dead_letter_events` (`DeadLetterEvent`) with `OutboxStatus.DEAD_LETTER`.
  - `app/services/outbox.py:404–473`: `replay_dead_letter()` enforces `norm_role == "ADMIN"` (`ForbiddenError` for `OPERATIONAL`), resets `OutboxEvent` to `PENDING`, marks `DeadLetterEvent` as `REPLAYED`, and records `AuditLog(action="DEAD_LETTER_REPLAYED")`.
  - `app/schemas/system.py:85–112`: `DeadLetterReplayRequest` & `DeadLetterReplayResponse`.
  - `app/api/v1/system.py:282–315`: `POST /api/v1/system/dead-letters/{dead_letter_id}/replay` with `Depends(require_admin_role)`.
- **Test Evidence:**
  - `tests/integration/test_outbox_and_workers.py:37–156` (`test_outbox_delivery_retry_dead_letter_and_replay`)
  - `tests/integration/test_outbox_and_workers.py:391–446` (`test_dead_letter_admin_only_replay_via_api`)
- **CI Step Evidence:** `CI` Run `37142297231` Step 12 & Step 13.

### 4.5 E2E Tests Driven by `TestSignalFactory` (Without Real Signal Engine)

- **Code Paths & Line Numbers:**
  - `tests/factories.py:1–152`: `SignalBundle` (`:26`), `TestSignalFactory.ensure_strategy_and_account` (`:41`), `TestSignalFactory.create_signal` (`:82`).
  - `tests/e2e/test_signal_lifecycle_e2e.py:1–295`:
    - `test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory` (`:34–229`)
    - `test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher` (`:232–267`)
    - `test_e2e_signal_expired_by_price_drift_with_test_signal_factory` (`:270–295`)
- **CI Step Evidence:** `CI` Run `37142297231` Step 12 & Step 13.

### 4.6 Minimal 5 F2 Chaos Tests (`tests/chaos/test_f2_chaos.py`)

Only the 5 minimal F2 Chaos scenarios requested for Phase F2 are implemented and executed in `tests/chaos/test_f2_chaos.py:1–334`:

1. **Scenario 1 — API / Exchange Disconnection (`tests/chaos/test_f2_chaos.py:42–140`):** `test_chaos_api_disconnection_and_recovery`
2. **Scenario 2 — Risk Engine Heartbeat Timeout > 60s (`tests/chaos/test_f2_chaos.py:143–205`):** `test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`
3. **Scenario 3 — Independent Kill Switch Service Restart (`tests/chaos/test_f2_chaos.py:208–263`):** `test_chaos_kill_switch_service_restart_preserves_state`
4. **Scenario 4 — PostgreSQL Database Disconnection (`tests/chaos/test_f2_chaos.py:266–286`):** `test_chaos_database_disconnection_fails_closed`
5. **Scenario 5 — Redis Outage & Restart (`tests/chaos/test_f2_chaos.py:289–334`):** `test_chaos_redis_restart_preserves_durable_domain_state`

- **CI Step Evidence:** `CI` Run `37142297231` Step 12 & Step 13.

---

## 5. Classification of `FORBIDDEN_DURABLE_PREFIXES` as a Defensive Runtime Implementation Control

- **Contractual Requirement (`MVP0_Implementation_Contract_v1.2_FINAL.md §5.2` & `F1 Package §7`):**
  - The governing contract mandates the architectural invariant that **Redis must be used strictly for transient operational state and must never store durable domain state** (Orders, Positions, Trades, Signals, Approvals, Audit Logs, Outbox, Dead-Letter, Kill Switch, or Resume Approval).
- **Defensive Runtime Implementation Control (`کنترل اجرایی دفاعی`):**
  - The tuple `FORBIDDEN_DURABLE_PREFIXES` in `app/core/config.py:23–43,74` (imported by `RedisClient` in `app/core/redis.py:6,19,43–49`) is an **internal defensive runtime guard** implemented by engineering (and centralized into `app/core/config.py` per Auditor F2 Directive #9) to programmatically reject accidental writes of domain-prefixed keys (`durable:`, `sot:`, `order:`, `orders:`, `position:`, `positions:`, `trade:`, `trades:`, `signal:`, `signals:`, `approval:`, `approvals:`, `audit:`, `outbox:`, `dead_letter:`, `dlq:`, `kill_switch:`, `resume:`) with `RedisOperationError`.
  - It is documented here explicitly as a **defensive runtime implementation control** rather than a literal named constant from the original contract text.

---

## 6. Honest Inventory of `NOT IMPLEMENTED` Items and Target Phases (`release/f2-candidate @ 532cec3`)

In strict adherence to audit transparency, every item from the governing specifications that is **not implemented** at `release/f2-candidate @ 532cec3` is listed below with its current state and target phase:

| # | Item & Governing Reference | Current State in `release/f2-candidate @ 532cec3` | Status | Target Phase |
|---|---|---|---|---|
| **1** | **Automatic Startup Registration of `WorkerSupervisor`, Synthetic Stop Recovery, and Position Reconciliation inside Main API `lifespan` (`Contract §17.1` Steps 7–12)** | `WorkerSupervisor` (`app/workers/supervisor.py`), `SyntheticStopService.reconcile_stops_on_startup` (`app/services/synthetic_stop.py:600`), and `ReconciliationService.reconcile_positions` (`app/services/reconciliation.py:31`) are implemented and tested in `tests/integration/`, and `_heartbeat_monitor_loop` runs automatically in `app/kill_switch_service.py:kill_switch_lifespan`. However, `app/main.py:lifespan` (`lines 51–98`) currently initializes PostgreSQL/Redis and `app.state.background_tasks = []` without automatically starting `WorkerSupervisor` or invoking startup stop/position reconciliation during main API startup. | **`NOT IMPLEMENTED` in `app/main.py:lifespan`** | **Phase F2 Follow-up / Phase F3 Entry** (Minimal wiring in `app/main.py:lifespan`) |
| **2** | **Real Signal Engine (`Trend Following` + `Mean Reversion` — `Contract §8` / `Master Package §۱۲.۱ MVP-C`)** | Per Auditor F2 Directive #5 (*"تست‌های E2E با استفاده از TestSignalFactory اضافه شوند، بدون پیاده‌سازی Signal Engine واقعی"*), no real Signal Engine is implemented in F2; signals in E2E tests are generated via `TestSignalFactory` (`tests/factories.py`). | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F1 & F2 approval) |
| **3** | **Operational HTTP Endpoints for Signals, Orders, and Positions (`Contract §16.3`)** | `GET /api/v1/signals`, `POST /api/v1/signals/{id}/approve`, `POST /api/v1/signals/{id}/reject`, `GET /api/v1/orders`, `GET /api/v1/orders/{id}` (`app/api/v1/orders.py` is a 6-line router stub), and `GET /api/v1/positions` (`app/api/v1/positions.py` is a 6-line router stub) are not implemented yet. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F1 & F2 approval) |
| **4** | **Read-Only Decision Log HTTP Endpoints (`Contract §16.3`, `§16.4`, `§21.5`)** | `GET /api/v1/decisions` and `GET /api/v1/decisions/{signal_id}` (`test_decision_history_is_queryable`, `test_decision_history_is_read_only`) are not implemented yet. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F1 & F2 approval) |
| **5** | **Minimal Operator Dashboard / UI Shell (`app/dashboard/` — `F1 Package §3.3` & `Master Package §۱۲.۱ MVP-E`)** | `app/dashboard/` contains only package placeholders (`__init__.py`). | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F1 & F2 approval) |
| **6** | **Full Phase F3 End-to-End HTTP & Full F3 Chaos Test Matrix (`Contract §21.5` & `§21.6`)** | Phase F2 implements the 3 `TestSignalFactory` E2E tests (`tests/e2e/test_signal_lifecycle_e2e.py`) and the 5 minimal F2 Chaos scenarios (`tests/chaos/test_f2_chaos.py`). The remaining F3 HTTP workflow tests (`test_order_idempotency_across_duplicate_requests`, etc.) and full F3 chaos injection suite (`§21.6`) are deferred to Phase F3. | **`NOT IMPLEMENTED`** | **Phase F3** (Blocked until F1 & F2 approval) |
