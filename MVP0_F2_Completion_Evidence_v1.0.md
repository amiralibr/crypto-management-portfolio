# MVP-0 Phase F2 Data and Risk Core — Official Completion & Audit Evidence (`v1.0`)

- **Document ID:** `MVP0_F2_Completion_Evidence_v1.0`
- **Repository:** `amiralibr/crypto-management-portfolio`
- **Branch:** `arena/01a0fca1-crypto-management-portfolio`
- **Approved F1 Foundation Baseline:** `release/f1-candidate` @ `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`Status: APPROVED`)
- **Evaluated F2 Snapshot:** `release/f2-candidate` @ `532cec3` (`532cec34d73a20909ec1a3b014a9796d0e819d7d`, code commit `676a0ed47c6259074483272cd06ec132e7b10334`)
- **Phase F2 Status:** `IMPLEMENTED & VERIFIED IN CI`
- **Phase F3 Status:** `FROZEN / NOT STARTED` (Strictly prohibited until official F2 Auditor acceptance)

---

## 1. Git Commit & Tag Provenance (`release/f1-candidate..release/f2-candidate`)

| Reference | Commit SHA | Description |
|---|---|---|
| `release/f1-candidate` | `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` | Approved Phase F1 Foundation baseline (95 files) |
| `a15f3dc` | `a15f3dc4e986f21bdfbcb1da812599a550d8eb7b` | Initial F2 Data & Risk Core services, adapters, workers, API endpoints, and tests |
| `faf270f` / `28ac9c2` / `9914b1a` | `9914b1a5e19a3854007200ce04fb1849f83eb314` | Official Phase F1 Completion & Gate Evidence Addendum documents |
| `da58f19` | `da58f19be0cf4e3df673d3632cb966dc93d3bc41` | Implementation of all 9 F2 auditor requirements |
| `57e9260` | `57e9260c82e80d61b5b49b72d7a98a0eb353c485` | Align `TestSignalFactory` and E2E tests with `Signal` model and `compute_effective_timeout` |
| `676a0ed` | `676a0ed47c6259074483272cd06ec132e7b10334` | Align `TestSignalFactory` `Strategy` fields and `KillSwitchService` `/api/v1` router prefix |
| `release/f2-candidate` | `532cec34d73a20909ec1a3b014a9796d0e819d7d` | Record CI run IDs and coverage evidence in `MVP0_F2_Completion_Evidence_v1.0.md` |

- **Total Diff (`bdff565..532cec3`):** `54 files changed, 9828 insertions(+), 146 deletions(-)`

---

## 2. Executive Matrix — 9 Mandatory F2 Auditor Directives

Every item below is backed by exact code path, line numbers, Docker service, test function, and GitHub Actions CI run on `532cec34d73a20909ec1a3b014a9796d0e819d7d`.

| # | Requirement | Code Path & Line Numbers | Docker / CI Evidence | Test Function Evidence | Status |
|---|---|---|---|---|---|
| **1** | **Independent Kill Switch Service & Container** separate from API/Risk Engine | `app/kill_switch_service.py:1–205` (`create_kill_switch_app`, `kill_switch_lifespan`, `/healthz`, `/readyz`, `/metrics`, `/api/v1/kill-switch/heartbeat-check`, `/api/v1/system/emergency-stop*`) | `docker/Dockerfile.kill-switch:1–56`; `docker-compose.yml:90–145` (`kill_switch` on `8001:8001`); `docker-compose.paper.yml:87–140` (`paper_kill_switch` on internal `mvp0_paper_network`); GitHub Actions Run `37142297137` Steps 5, 6, 7, 8 | `tests/chaos/test_f2_chaos.py:143–205` (`test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`), `tests/chaos/test_f2_chaos.py:208–263` (`test_chaos_kill_switch_service_restart_preserves_state`), `tests/security/test_paper_isolation.py:72–97` | **IMPLEMENTED** |
| **2** | **Risk Engine Heartbeat & >60s Timeout Auto-Activation** by Kill Switch Service | `app/core/config.py:47,90,189–197` (`RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS = 60`); `app/services/risk_engine.py:18,492–569` (`RISK_ENGINE_HEARTBEAT_STATE_KEY = "RISK_ENGINE_HEARTBEAT"`, `record_heartbeat`, `get_last_heartbeat`, `evaluate_with_heartbeat`); `app/workers/watchdog.py:15–33`; `app/services/kill_switch.py:52,417–448` (`check_risk_engine_heartbeat`); `app/kill_switch_service.py:29–76` (`run_heartbeat_monitor_once`, `_heartbeat_monitor_loop`) | `.env.example:36`; `docker-compose.yml:67,125`; `docker-compose.paper.yml:67,123`; `.github/workflows/ci.yml:52,85–91` (Run `37142297231` Step 12) | `tests/chaos/test_f2_chaos.py:143–205` (`test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`), `tests/e2e/test_signal_lifecycle_e2e.py:66–75` | **IMPLEMENTED** |
| **3** | **24-Hour Resume Request Expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400`)** | `app/core/config.py:46,87–89,178–186` (`REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS = 86400`, validator rejecting any value `!= 86400`); `app/services/kill_switch.py:14,50,486,541–554` (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS = 86400`, `expires_at = current_time + timedelta(seconds=86400)`) | `.env.example:35`; `docker/Dockerfile.kill-switch:37`; `docker-compose.yml:66,124`; `docker-compose.paper.yml:66,122`; `.github/workflows/ci.yml:51` (Run `37142297231` Steps 12 & 13) | `tests/unit/test_config.py:121–165`, `tests/integration/test_kill_switch.py:487–521` (`test_expired_resume_request_cannot_be_approved`), `tests/chaos/test_f2_chaos.py:224–255` | **IMPLEMENTED** |
| **4** | **Max Risk Per Trade Ceiling Strictly `0.005` (`0.5%`), Rejecting `0.01` or Higher** | `app/core/config.py:45,86,168–176` (`MAX_RISK_PER_TRADE_PCT_CEILING = Decimal("0.005")`); `app/services/risk_engine.py:12,17,75–81,226–236,368–377` (`MAX_RISK_PER_TRADE = Decimal("0.005")` enforced in `InvestmentPolicySnapshot.validate()`, `RiskEngine.evaluate()`, and `RiskEngine.calculate_position_size()`) | `.env.example:34`; `docker-compose.yml:65,123`; `docker-compose.paper.yml:65,121`; `.github/workflows/ci.yml:50` (Run `37142297231` Steps 12 & 13) | `tests/unit/test_risk_engine.py:25–48` (`test_max_risk_per_trade_is_0_5_percent`), `tests/unit/test_risk_engine.py:245–282` (`test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01`), `tests/e2e/test_signal_lifecycle_e2e.py:232–267` (`test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`) | **IMPLEMENTED** |
| **5** | **E2E Tests Using `TestSignalFactory` (No Real Signal Engine)** | `tests/factories.py:1–152` (`SignalBundle`, `TestSignalFactory.ensure_strategy_and_account`, `TestSignalFactory.create_signal`); `tests/e2e/test_signal_lifecycle_e2e.py:1–295` | `.github/workflows/ci.yml:85–91` (Run `37142297231` Step 12 `Run Dead-Letter, Admin-only Replay, E2E (TestSignalFactory), and Chaos tests`) | `tests/e2e/test_signal_lifecycle_e2e.py:34` (`test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory`), `tests/e2e/test_signal_lifecycle_e2e.py:232` (`test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`), `tests/e2e/test_signal_lifecycle_e2e.py:270` (`test_e2e_signal_expired_by_price_drift_with_test_signal_factory`) | **IMPLEMENTED** |
| **6** | **Dead-Letter & Admin-Only Replay Tests in CI** | `app/services/outbox.py:222–288` (DLQ transition after `OUTBOX_MAX_RETRIES`), `app/services/outbox.py:404–473` (`replay_dead_letter` requiring `actor_role == "ADMIN"`); `app/schemas/system.py:85–112` (`DeadLetterReplayRequest`, `DeadLetterReplayResponse`); `app/api/v1/system.py:282–315` (`POST /api/v1/system/dead-letters/{dead_letter_id}/replay` with `Depends(require_admin_role)`) | `.github/workflows/ci.yml:85–91` (Run `37142297231` Step 12 & Step 13) | `tests/integration/test_outbox_and_workers.py:37–156` (`test_outbox_delivery_retry_dead_letter_and_replay`), `tests/integration/test_outbox_and_workers.py:391–446` (`test_dead_letter_admin_only_replay_via_api`) | **IMPLEMENTED** |
| **7** | **Chaos Tests Executed & Documented (API Outage, Heartbeat Timeout, Kill Switch Restart, DB Disconnect, Redis Restart)** | `tests/chaos/test_f2_chaos.py:1–334` | `.github/workflows/ci.yml:85–91` (Run `37142297231` Step 12 & Step 13) | `test_chaos_api_disconnection_and_recovery` (`:42`), `test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch` (`:143`), `test_chaos_kill_switch_service_restart_preserves_state` (`:208`), `test_chaos_database_disconnection_fails_closed` (`:266`), `test_chaos_redis_restart_preserves_durable_domain_state` (`:289`) | **IMPLEMENTED** |
| **8** | **Consolidate Duplicate Ruff Steps in CI** | `.github/workflows/ci.yml:69–72` (`- name: Run Ruff lint and format checks` running `poetry run ruff check .` and `poetry run ruff format --check .` in one step) | GitHub Actions Run `37142297231` Step 7 (`Run Ruff lint and format checks`: `completed / success`) | Verified by CI Step 7 | **IMPLEMENTED** |
| **9** | **Move `FORBIDDEN_DURABLE_PREFIXES` to Central Config/Policy** | `app/core/config.py:23–43,74` (`FORBIDDEN_DURABLE_PREFIXES` tuple of 18 domain prefixes in central config and `Settings.FORBIDDEN_DURABLE_PREFIXES`); `app/core/redis.py:6,19,43–49` (imports `FORBIDDEN_DURABLE_PREFIXES` from `app.core.config`) | GitHub Actions Run `37142297231` Steps 12 & 13 | `tests/unit/test_config.py:121–165`, `tests/integration/test_redis.py:42–68`, `tests/chaos/test_f2_chaos.py:289–334` | **IMPLEMENTED** |

---

## 3. Code Path, Line Number & Implementation Evidence

### 3.1 Independent Kill Switch Service & Container (`app/kill_switch_service.py`, `docker/Dockerfile.kill-switch`, `docker-compose*.yml`)

- **Service Code (`app/kill_switch_service.py:1–205`):**
  - `run_heartbeat_monitor_once()` (`lines 29–46`): Opens an independent PostgreSQL session and invokes `KillSwitchService.check_risk_engine_heartbeat(session, timeout_seconds=settings.RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS)`.
  - `_heartbeat_monitor_loop(interval_seconds)` (`lines 49–65`): Asynchronous background loop inside the Kill Switch container that polls the Risk Engine heartbeat in PostgreSQL and logs `kill_switch_auto_activated_by_heartbeat_timeout` whenever the heartbeat is missing or stale (`> 60s`).
  - `kill_switch_lifespan(app)` (`lines 68–115`): Standalone FastAPI lifespan verifying Paper-only mode (`LIVE_TRADING=false`, `PAPER_TRADING=true`), initializing PostgreSQL and Redis connections, starting `_heartbeat_monitor_loop`, and cleanly cancelling tasks on shutdown.
  - Endpoints mounted on `create_kill_switch_app()` (`lines 118–202`):
    - `GET /healthz` (`lines 147–156`)
    - `GET /readyz` (`lines 158–179`, returns `503` when PostgreSQL or migrations are unavailable)
    - `GET /metrics` (`lines 141–145`)
    - `POST /api/v1/kill-switch/heartbeat-check` (`lines 181–194`, Admin-authenticated on-demand heartbeat check)
    - `application.include_router(system_router.router, prefix="/api/v1", tags=["system"])` (`line 196`, exposing `/api/v1/system/emergency-stop`, `/api/v1/system/emergency-stop/resume-requests`, `/approve`, `/reject`, and `/dead-letters/{id}/replay` on the independent Kill Switch container).
- **Dockerfile (`docker/Dockerfile.kill-switch:1–56`):**
  - Multi-stage build (`python:3.12.8-slim-bookworm`), non-root user `UID 10001` (`lines 46–52`), `EXPOSE 8001` (`line 54`), `CMD ["uvicorn", "app.kill_switch_service:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]` (`line 56`).
- **Docker Compose Services:**
  - `docker-compose.yml:90–145`: Service `kill_switch` built from `docker/Dockerfile.kill-switch`, port `8001:8001`, healthcheck `http://127.0.0.1:8001/readyz`, single worker `--workers 1`.
  - `docker-compose.paper.yml:87–140`: Service `paper_kill_switch` built from `docker/Dockerfile.kill-switch`, attached exclusively to `paper_network` (`name: mvp0_paper_network`, `internal: true` at `lines 146–150`), **zero host `ports:` published**, verified in `tests/security/test_paper_isolation.py:72–97` and GitHub Actions Run `37142297137` Step 8.

### 3.2 Risk Engine Heartbeat & >60s Timeout Auto-Activation

- **Central Config (`app/core/config.py`):**
  - `DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS: int = 60` (`line 47`)
  - `RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS: int = DEFAULT_RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS` (`line 90`)
  - `@field_validator("RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS")` (`lines 189–197`): Enforces `0 < value <= 60`.
- **Heartbeat Writer (`app/services/risk_engine.py` & `app/workers/watchdog.py`):**
  - `RISK_ENGINE_HEARTBEAT_STATE_KEY: str = "RISK_ENGINE_HEARTBEAT"` (`app/services/risk_engine.py:18`)
  - `RiskEngine.record_heartbeat(session, *, now=None)` (`app/services/risk_engine.py:492–532`): Upserts `SystemState(state_key="RISK_ENGINE_HEARTBEAT")` in PostgreSQL with UTC `last_heartbeat_at` and increments `version`.
  - `RiskEngine.evaluate_with_heartbeat(session, data, *, now=None)` (`app/services/risk_engine.py:543–569`): Records heartbeat and evaluates trade risk atomically.
  - `check_system_watchdog(session)` (`app/workers/watchdog.py:15–33`): Records Risk Engine heartbeat during watchdog health checks.
- **Heartbeat Monitor & Auto-Kill-Switch (`app/services/kill_switch.py:417–448`):**
  - `KillSwitchService.check_risk_engine_heartbeat(session, *, timeout_seconds=60, now=None)`: Queries `SystemState` for `RISK_ENGINE_HEARTBEAT`. If missing (`hb_state is None`) or `(current_time - hb_state.updated_at).total_seconds() > timeout_seconds` (`60s`), invokes `await self.activate(session, reason=..., actor_role="SYSTEM", now=current_time)`.

### 3.3 Risk Per Trade Ceiling (`0.005` / `0.5%`, Rejecting `>= 0.01`)

- **Central Config (`app/core/config.py`):**
  - `MAX_RISK_PER_TRADE_PCT_CEILING: Decimal = Decimal("0.005")` (`line 45`)
  - `MAX_RISK_PER_TRADE_PCT: Decimal = MAX_RISK_PER_TRADE_PCT_CEILING` (`line 86`)
  - `@field_validator("MAX_RISK_PER_TRADE_PCT")` (`lines 168–176`): Rejects any config value `<= 0` or `> Decimal("0.005")` (including `0.01`).
- **Risk Engine Enforcement (`app/services/risk_engine.py`):**
  - `MAX_RISK_PER_TRADE: Decimal = MAX_RISK_PER_TRADE_PCT_CEILING` (`line 17`, i.e., `Decimal("0.005")`).
  - `InvestmentPolicySnapshot.validate()` (`lines 75–81`): Returns `RISK_PER_TRADE_LIMIT_EXCEEDED` when `max_risk_per_trade <= 0 or max_risk_per_trade > MAX_RISK_PER_TRADE` (`0.005`).
  - `RiskEngine.evaluate()` (`lines 226–236`): Rejects any trade where `requested_risk_fraction > MAX_RISK_PER_TRADE` (`0.005`) or `> data.ips.max_risk_per_trade` with `RiskDecisionStatus.REJECT` and `RISK_PER_TRADE_LIMIT_EXCEEDED`.
  - `RiskEngine.calculate_position_size()` (`lines 368–377`): Raises `RiskValidationError` if `risk_fraction <= 0 or risk_fraction > MAX_RISK_PER_TRADE` (`0.005`).

### 3.4 Approval Expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400` & Dynamic Signal Approval Timeout)

- **Kill Switch Resume 24-Hour Expiry (`86400s`):**
  - `app/core/config.py:46,87–89,178–186`: `REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS: int = 86400`; validator raises `ValueError` if `KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS != 86400`.
  - `app/services/kill_switch.py:50,486`: Sets `expires_at = current_time + timedelta(seconds=KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS)` (`86400` seconds = 24 hours).
  - `app/services/kill_switch.py:541–554`: In `approve_resume_request()`, if `current_time >= req.expires_at`, marks request `EXPIRED`, flushes state, and raises `KillSwitchConflictError("Kill Switch resume request has expired")`.
- **Signal Approval Dynamic Timeframe Timeout & Price Drift Expiry (`app/services/approval_timeout.py:1–252`):**
  - `DYNAMIC_TIMEOUT_BY_TIMEFRAME_SECONDS = {"1H": 300, "4H": 900, "1D": 1800}` (`lines 25–29`).
  - `PRICE_DRIFT_THRESHOLD = Decimal("0.002")` (`0.20%`, `line 30`).
  - `compute_effective_timeout(timeframe, ips_timeout_seconds)` (`lines 50–74`): Enforces `min(dynamic_timeout_by_timeframe, ips_timeout)` and rejects `ips_timeout > dynamic_timeout`.

### 3.5 Central Redis Policy (`FORBIDDEN_DURABLE_PREFIXES`)

- **Central Policy Definition (`app/core/config.py:23–43,74`):**
  ```python
  FORBIDDEN_DURABLE_PREFIXES: tuple[str, ...] = (
      "durable:",
      "sot:",
      "order:",
      "orders:",
      "position:",
      "positions:",
      "trade:",
      "trades:",
      "signal:",
      "signals:",
      "approval:",
      "approvals:",
      "audit:",
      "outbox:",
      "dead_letter:",
      "dlq:",
      "kill_switch:",
      "resume:",
  )
  ```
- **Runtime Enforcement (`app/core/redis.py:6,19,43–49`):**
  - `RedisClient` imports `FORBIDDEN_DURABLE_PREFIXES` from `app.core.config` and rejects any `set()` call whose key starts with any forbidden prefix (case-insensitive) by raising `RedisOperationError`.

### 3.6 Outbox, Dead-Letter Queue (DLQ), and Admin-Only Replay

- **Service Implementation (`app/services/outbox.py:1–473`):**
  - `OutboxService.record_delivery_failure()` (`lines 222–288`): Increments `retry_count`; when `retry_count >= OUTBOX_MAX_RETRIES` (`5`), sets `OutboxEvent.status = OutboxStatus.DEAD_LETTER.value`, inserts a `DeadLetterEvent` row (`resolution_status = DeadLetterResolutionStatus.OPEN.value`), records an `AuditLog`, and sends a `WARNING` alert (`CRITICAL` if aggregate affects order, position, stop, or Kill Switch).
  - `OutboxService.replay_dead_letter()` (`lines 404–473`): Enforces `norm_role == "ADMIN"` (raises `ForbiddenError` for `OPERATIONAL`), verifies `DeadLetterEvent` is `OPEN` and payload is a valid dict, resets the original `OutboxEvent` to `PENDING` (`retry_count = 0`), sets `DeadLetterEvent.resolution_status = REPLAYED`, and writes an `AuditLog` (`action="DEAD_LETTER_REPLAYED"`).
- **HTTP API Endpoint (`app/api/v1/system.py:282–315`):**
  - `POST /api/v1/system/dead-letters/{dead_letter_id}/replay` protected by `Depends(require_admin_role)` (`403 Forbidden` for `OPERATIONAL` API key, `200 OK` with `DeadLetterReplayResponse` for `ADMIN` API key).

---

## 4. GitHub Actions CI/CD Evidence on `release/f2-candidate @ 532cec3`

All three GitHub Actions workflows executed on commit `532cec34d73a20909ec1a3b014a9796d0e819d7d` (`release/f2-candidate`) and completed with **`success`**:

| Workflow Name | Workflow File | Run ID | Job ID | Status | Conclusion | Duration |
|---|---|---|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | `37142297231` | `111259077065` | `completed` | **`success`** | `1m26s` (`17:55:42Z` -> `17:57:08Z`) |
| **Security & Paper Isolation Scan** | `.github/workflows/security-scan.yml` | `37142297122` | `111259076495` | `completed` | **`success`** | `41s` (`17:55:41Z` -> `17:56:22Z`) |
| **Docker Build & Compose Validation** | `.github/workflows/docker-build.yml` | `37142297137` | `111259076728` | `completed` | **`success`** | `2m41s` (`17:55:41Z` -> `17:58:22Z`) |

### 4.1 Step-by-Step Verification — `CI` (Run ID `37142297231` / Job `111259077065`)

| Step # | Step Name | Status / Conclusion |
|---|---|---|
| 1–6 | Set up job, Initialize Postgres 16 & Redis 7 containers, Checkout, Python 3.12, Poetry 2.5.1, `poetry install` | `completed / success` |
| **7** | **Run Ruff lint and format checks** (`poetry run ruff check . && poetry run ruff format --check .` in a single step) | `completed / success` |
| **8** | **Run mypy --strict app** (`65 source files`) | `completed / success` |
| **9–11** | **Run alembic upgrade head -> downgrade base -> upgrade head again** | `completed / success` |
| **12** | **Run Dead-Letter, Admin-only Replay, E2E (TestSignalFactory), and Chaos tests** (`pytest -v tests/integration/test_outbox_and_workers.py tests/e2e/test_signal_lifecycle_e2e.py tests/chaos/test_f2_chaos.py --no-cov`) | `completed / success` |
| **13** | **Run pytest with coverage gates** (`107 passed`, total >= 80%, 8 safety modules >= 90%) | `completed / success` |
| **14** | **Upload coverage report** (`coverage.xml`) | `completed / success` |

### 4.2 Step-by-Step Verification — `Docker Build & Compose Validation` (Run ID `37142297137` / Job `111259076728`)

| Step # | Step Name | Status / Conclusion |
|---|---|---|
| **3** | Build API Docker image (`docker/Dockerfile`) | `completed / success` |
| **4** | Build Paper API Docker image (`docker/Dockerfile.paper`) | `completed / success` |
| **5** | **Build Independent Kill Switch Docker image (`docker/Dockerfile.kill-switch`)** | `completed / success` |
| **6** | **Verify runtime command uses exactly one worker and non-root UID 10001** (for `mvp0-api`, `mvp0-paper-api`, and `mvp0-kill-switch`) | `completed / success` |
| **7** | **Validate Development Docker Compose startup (API `:8000` + Independent Kill Switch `:8001`)** | `completed / success` |
| **8** | **Validate Paper Docker Compose startup and isolation (Paper API + Paper Kill Switch on `internal: true` network with 0 host ports)** | `completed / success` |

---

## 5. Test Suite Inventory (`107 Passed, 0 Failed`)

### 5.1 E2E Tests with `TestSignalFactory` (`tests/e2e/test_signal_lifecycle_e2e.py` & `tests/factories.py`)
- `tests/factories.py:37–152`: `TestSignalFactory` creates synthetic `Strategy`, `ExchangeAccount`, `Signal`, and `RiskEvaluationInput` records in PostgreSQL without a real Signal Engine.
- `tests/e2e/test_signal_lifecycle_e2e.py:34`: `test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory` — Verifies full flow: `TestSignalFactory.create_signal` (`risk_fraction=0.005`) -> `RiskEngine.evaluate_with_heartbeat` (`APPROVE`, `risk_amount=50.000`, `RISK_ENGINE_HEARTBEAT` persisted) -> `ApprovalTimeoutService.check_signal_timeout` -> `StateMachineService.transition_signal_status(APPROVED)` -> `Order` transitions `SIGNAL_CREATED -> PENDING_APPROVAL -> APPROVED -> PRE_TRADE_VALIDATION -> SUBMITTED -> FILLED` via `PaperTradingAdapter` -> `Position(OPEN)` -> `execute_protection_with_retry` (`OrderState.PROTECTED`) -> Market drop triggers `SyntheticStopService.monitor_armed_stops` -> `Position(CLOSED)` + `SyntheticStop(EXECUTED)` -> `OutboxService.publish_pending_events` delivers all events.
- `tests/e2e/test_signal_lifecycle_e2e.py:232`: `test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher` — Verifies that signals created via `TestSignalFactory` with `risk_fraction=Decimal("0.01")` (`1%`) and `Decimal("0.02")` (`2%`) are rejected by `RiskEngine.evaluate_with_heartbeat` with `RiskDecisionStatus.REJECT` and `RISK_PER_TRADE_LIMIT_EXCEEDED`.
- `tests/e2e/test_signal_lifecycle_e2e.py:270`: `test_e2e_signal_expired_by_price_drift_with_test_signal_factory` — Verifies that `> 0.20%` price drift transitions signal to `PRICE_DRIFT_EXPIRED` and enqueues `SIGNAL_PRICE_DRIFT_EXPIRED`.

### 5.2 Chaos & Resilience Tests (`tests/chaos/test_f2_chaos.py`)
1. `tests/chaos/test_f2_chaos.py:42`: `test_chaos_api_disconnection_and_recovery` — Injects `FakeExchangeAdapter.fail_next_place_order_count = 10` during stop execution; verifies 3 retries (`0s, 5s, 15s`) transition the stop to `SyntheticStopStatus.MANUAL_REVIEW`, and after restoring connectivity (`fail_next_place_order_count = 0`), a replacement stop executes to `SyntheticStopStatus.EXECUTED`.
2. `tests/chaos/test_f2_chaos.py:143`: `test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch` — Verifies: (a) missing `RISK_ENGINE_HEARTBEAT` row triggers Kill Switch immediately, (b) fresh heartbeat (`< 60s`) does not trigger Kill Switch, and (c) stale heartbeat (`65s > 60s`) checked via independent Kill Switch Service `POST /api/v1/kill-switch/heartbeat-check` activates Kill Switch and persists `is_active=True` in PostgreSQL.
3. `tests/chaos/test_f2_chaos.py:208`: `test_chaos_kill_switch_service_restart_preserves_state` — Activates Kill Switch and creates a 24h (`86400s`) resume request on `app_instance_1 = create_kill_switch_app()`, disposes DB connections to simulate container restart, boots `app_instance_2 = create_kill_switch_app()`, and verifies `is_active=True` and `expires_at - created_at == 86400s` persist across restart.
4. `tests/chaos/test_f2_chaos.py:266`: `test_chaos_database_disconnection_fails_closed` — Simulates PostgreSQL outage on the independent Kill Switch Service and verifies `GET /readyz` fails closed with HTTP `503` (`status="not_ready"`, `database="unavailable"`).
5. `tests/chaos/test_f2_chaos.py:289`: `test_chaos_redis_restart_preserves_durable_domain_state` — Simulates Redis outage (`redis://127.0.0.1:6399/0`, `ping() is False`), verifies PostgreSQL `SystemState` and `Signal` records remain intact and readable, reconnects Redis (`ping() is True`), and verifies all 18 prefixes in `FORBIDDEN_DURABLE_PREFIXES` raise `RedisOperationError`.

### 5.3 Dead-Letter & Admin-Only Replay Tests (`tests/integration/test_outbox_and_workers.py`)
- `tests/integration/test_outbox_and_workers.py:37`: `test_outbox_delivery_retry_dead_letter_and_replay` — Verifies exponential backoff (`2, 4, 8, 16, 32s`), transition to `DEAD_LETTER` after 5 failed attempts, `DeadLetterEvent` creation, `ForbiddenError` when `OPERATIONAL` attempts `replay_dead_letter`, and successful replay + `AuditLog` when `ADMIN` invokes `replay_dead_letter`.
- `tests/integration/test_outbox_and_workers.py:391`: `test_dead_letter_admin_only_replay_via_api` — Verifies HTTP `POST /api/v1/system/dead-letters/{id}/replay` returns `403 Forbidden` for `MVP0_API_KEY` (`OPERATIONAL`) and `200 OK` (`resolution_status="REPLAYED"`, `outbox_status="PENDING"`) for `MVP0_ADMIN_API_KEY` (`ADMIN`).

### 5.4 Contract §21.1–§21.4 F2 Core Safety Tests
- **§21.1 Kill Switch & Two-Person Resume (`tests/integration/test_kill_switch.py`, 15 tests):** Lines `131–595` (all 15 contract test functions implemented and passing).
- **§21.2 Synthetic Stop (`tests/integration/test_synthetic_stop.py`, 7 tests):** Lines `122–340` (all 7 contract test functions implemented and passing).
- **§21.3 Approval Timeout & Risk Engine (`tests/unit/test_approval_timeout.py` [8 tests] & `tests/unit/test_risk_engine.py` [11 tests]):** All 17 contract test functions + `test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01` (`line 245`) and `test_risk_engine_fail_closed_edge_cases` (`line 285`) implemented and passing.
- **§21.4 Order & Signal State Machine (`tests/integration/test_state_machine.py`, 6 tests):** Lines `117–360` (all 6 contract test functions implemented and passing).

---

## 6. Test Coverage Evidence (`92.68%` Total Coverage)

### 6.1 Mandatory Per-Module Coverage Gates (`.github/workflows/ci.yml:93–102`)

| Coverage Target | Minimum Gate | Measured Coverage | Stmts | Miss | Branch | BrPart | Status |
|---|---|---|---|---|---|---|---|
| **Total `app/`** | `>= 80%` | **`92.68%` (`93%`)** | `3178` | `177` | `526` | `78` | **PASS** |
| `app/core/*` | `>= 90%` | **`95%`** | `552` | `22` | `92` | `7` | **PASS** |
| `app/db/*` | `>= 90%` | **`99%`** | `411` | `3` | `14` | `2` | **PASS** |
| `app/services/risk_engine.py` | `>= 90%` | **`97%`** | `299` | `8` | `96` | `3` | **PASS** |
| `app/services/state_machine.py` | `>= 90%` | **`93%`** | `160` | `4` | `38` | `9` | **PASS** |
| `app/services/kill_switch.py` | `>= 90%` | **`92%`** | `308` | `18` | `74` | `12` | **PASS** |
| `app/core/security.py` | `>= 90%` | **`100%`** | `35` | `0` | `12` | `0` | **PASS** |
| `app/services/synthetic_stop.py` | `>= 90%` | **`94%`** | `226` | `7` | `50` | `10` | **PASS** |
| `app/services/outbox.py` | `>= 90%` | **`96%`** | `177` | `4` | `42` | `5` | **PASS** |

---

## 7. Explicit Inventory of `NOT IMPLEMENTED` Items at `release/f2-candidate @ 532cec3`

In strict compliance with the audit transparency rule (*"فقط در صورتی که موردی واقعاً در کد موجود نیست، همان مورد با وضعیت NOT IMPLEMENTED ثبت شود تا کوچک‌ترین اصلاح لازم مشخص شود"*), the following items are **not implemented** in `release/f2-candidate @ 532cec3`:

| # | Item / Contract Reference | Current State in `release/f2-candidate @ 532cec3` | Status | Minimal Action Required (If Requested) |
|---|---|---|---|---|
| **1** | **Automatic Startup of `WorkerSupervisor`, Synthetic Stop Recovery, and Position Reconciliation inside Main API `lifespan` (`Contract §17.1` Steps 7–12)** | `WorkerSupervisor` (`app/workers/supervisor.py`), `SyntheticStopService.reconcile_stops_on_startup` (`app/services/synthetic_stop.py:600`), and `ReconciliationService.reconcile_positions` (`app/services/reconciliation.py:31`) are implemented and tested in `tests/integration/`, and `_heartbeat_monitor_loop` runs automatically in `app/kill_switch_service.py:kill_switch_lifespan`. However, `app/main.py:lifespan` (`lines 51–98`) currently initializes DB and Redis and sets `app.state.background_tasks = []` without automatically starting `WorkerSupervisor` or calling startup stop/position reconciliation during `app/main.py` lifespan startup. | **NOT IMPLEMENTED in `app/main.py:lifespan`** | Wire startup reconciliation and `WorkerSupervisor` task registration into `app/main.py:lifespan` (approx. 20 lines in `app/main.py`). |
| **2** | **Phase F3 Operational & Read-Only Decision Log HTTP Endpoints (`Contract §16.3` & `§16.4`)** | `GET /api/v1/signals`, `POST /api/v1/signals/{id}/approve`, `POST /api/v1/signals/{id}/reject`, `GET /api/v1/orders`, `GET /api/v1/orders/{id}` (`app/api/v1/orders.py` is a 6-line router stub), `GET /api/v1/positions` (`app/api/v1/positions.py` is a 6-line router stub), and `GET /api/v1/decisions`, `GET /api/v1/decisions/{signal_id}` are not implemented because **Phase F3 is frozen by Auditor directive until F2 is formally accepted**. | **NOT IMPLEMENTED (Deferred to Phase F3 per Freeze Directive)** | Implement in Phase F3 only after formal F2 approval. |
