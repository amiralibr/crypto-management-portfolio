# MVP-0 Phase F2 Data and Risk Core — Official Remediation & Completion Evidence (`v1.0`)

- **Document ID:** `MVP0_F2_Completion_Evidence_v1.0`
- **Project:** MVP-0 Crypto Risk Management System (`amiralibr/crypto-management-portfolio`)
- **Approved F1 Baseline:** `release/f1-candidate` @ `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`Status: APPROVED`)
- **Current Phase:** `F2 — Data and Risk Core` (`F2 READY FOR REVIEW`)
- **Phase F3 Status:** `FROZEN / NOT STARTED` (No F3 development will begin until formal F2 Auditor acceptance)

---

## 1. Summary of the 9 Mandatory F2 Auditor Remediations

| # | Auditor Requirement | Implementation & Evidence Location | Status |
|---|---|---|---|
| **1** | **Independent Kill Switch Service & Container** decoupled from API/Risk Engine | Standalone FastAPI service `app/kill_switch_service.py` (`port 8001`), multi-stage `docker/Dockerfile.kill-switch`, `kill_switch` service in `docker-compose.yml`, and isolated `paper_kill_switch` service in `docker-compose.paper.yml`. Verified in `.github/workflows/docker-build.yml`. | **COMPLETE** |
| **2** | **Risk Engine Heartbeat & >60s Timeout Auto-Activation** by Kill Switch Service | `RiskEngine.record_heartbeat()` (`app/services/risk_engine.py`), `check_system_watchdog()` (`app/workers/watchdog.py`), and `KillSwitchService.check_risk_engine_heartbeat()` (`app/services/kill_switch.py`) + `_heartbeat_monitor_loop()` in `app/kill_switch_service.py`. Automatically triggers Kill Switch when `RISK_ENGINE_HEARTBEAT` is missing or older than `RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS=60`. | **COMPLETE** |
| **3** | **24-Hour Resume Request Expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400`)** | Enforced in `app/core/config.py` (`REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS = 86400`), `app/services/kill_switch.py` (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS = 86400`), `.env.example`, `docker-compose.yml`, `docker-compose.paper.yml`, and `tests/integration/test_kill_switch.py::test_expired_resume_request_cannot_be_approved`. | **COMPLETE** |
| **4** | **Max Risk Per Trade Ceiling Strictly `0.005` (`0.5%`), Rejecting `0.01` or Higher** | Enforced in `app/core/config.py` (`MAX_RISK_PER_TRADE_PCT_CEILING = Decimal("0.005")`) and `app/services/risk_engine.py` (`MAX_RISK_PER_TRADE = Decimal("0.005")` across `InvestmentPolicySnapshot.validate()`, `RiskEngine.evaluate()`, and `RiskEngine.calculate_position_size()`). Verified in `tests/unit/test_risk_engine.py::test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01` and `tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`. | **COMPLETE** |
| **5** | **E2E Tests with `TestSignalFactory` (Without Real Signal Engine)** | Implemented `TestSignalFactory` in `tests/factories.py` and full end-to-end lifecycle tests in `tests/e2e/test_signal_lifecycle_e2e.py` (Signal -> Risk Engine -> Price Drift Check -> Order State Machine -> Paper Fill -> Synthetic Stop Trigger & Close -> Outbox & Audit Log). | **COMPLETE** |
| **6** | **Dead-Letter & Admin-Only Replay Tests in CI** | Service-level (`OutboxService.replay_dead_letter`) and API-level (`POST /api/v1/system/dead-letters/{id}/replay` in `app/api/v1/system.py`) Admin-only replay enforcement (`403 Forbidden` for `OPERATIONAL`, `200 OK` for `ADMIN`), verified in `tests/integration/test_outbox_and_workers.py::test_dead_letter_admin_only_replay_via_api` and executed in `.github/workflows/ci.yml`. | **COMPLETE** |
| **7** | **Chaos Tests (API Outage, Heartbeat Timeout, Kill Switch Restart, DB Disconnect, Redis Restart)** | Implemented all 5 chaos scenarios in `tests/chaos/test_f2_chaos.py` and executed in `.github/workflows/ci.yml`. | **COMPLETE** |
| **8** | **Consolidate Duplicate Ruff Steps in CI** | Merged into a single step `Run Ruff lint and format checks` (`poetry run ruff check . && poetry run ruff format --check .`) in `.github/workflows/ci.yml`. | **COMPLETE** |
| **9** | **Move `FORBIDDEN_DURABLE_PREFIXES` to Central Config/Policy** | Moved `FORBIDDEN_DURABLE_PREFIXES` to `app/core/config.py` (including `durable:`, `sot:`, `order:`, `orders:`, `position:`, `positions:`, `trade:`, `trades:`, `signal:`, `signals:`, `approval:`, `approvals:`, `audit:`, `outbox:`, `dead_letter:`, `dlq:`, `kill_switch:`, `resume:`) and imported in `app/core/redis.py`. | **COMPLETE** |

---

## 2. Detailed Evidence per Requirement

### 2.1 Independent Kill Switch Service & Container (Requirements #1 & #2)
- **Standalone Application (`app/kill_switch_service.py`):**
  - Runs independently on port `8001` (`uvicorn app.kill_switch_service:app --host 0.0.0.0 --port 8001 --workers 1`).
  - Exposes `/healthz`, `/readyz`, `/api/v1/kill-switch/heartbeat-check`, and `/api/v1/system/emergency-stop*`.
  - Runs `_heartbeat_monitor_loop` checking `SystemState(state_key="RISK_ENGINE_HEARTBEAT")` in PostgreSQL; if missing or older than `RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS = 60`, automatically activates the Kill Switch.
- **Containerization (`docker/Dockerfile.kill-switch`, `docker-compose.yml`, `docker-compose.paper.yml`):**
  - `kill_switch` service in `docker-compose.yml` (`8001:8001`).
  - `paper_kill_switch` service in `docker-compose.paper.yml` attached exclusively to `mvp0_paper_network` (`internal: true`) with zero host ports published.

### 2.2 24-Hour Resume Request Expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400`) (Requirement #3)
- `app/core/config.py`: `REQUIRED_KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS: int = 86400` and `KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS: int = 86400`.
- `app/services/kill_switch.py`: `expires_at = current_time + timedelta(seconds=KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS)`.
- Verified in `tests/integration/test_kill_switch.py::test_expired_resume_request_cannot_be_approved`.

### 2.3 Max Risk Per Trade Ceiling `0.005` (`0.5%`) & Rejection of `0.01` (Requirement #4)
- `app/core/config.py`: `MAX_RISK_PER_TRADE_PCT_CEILING: Decimal = Decimal("0.005")`.
- `app/services/risk_engine.py`: `MAX_RISK_PER_TRADE: Decimal = Decimal("0.005")`.
- Any `risk_fraction >= Decimal("0.01")` (or `> Decimal("0.005")`) is rejected across `InvestmentPolicySnapshot.validate()`, `RiskEngine.evaluate()`, and `RiskEngine.calculate_position_size()`.
- Verified in `tests/unit/test_risk_engine.py::test_max_risk_per_trade_is_strictly_0_005_and_rejects_0_01` and `tests/e2e/test_signal_lifecycle_e2e.py::test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`.

### 2.4 E2E Tests with `TestSignalFactory` (Requirement #5)
- `tests/factories.py`: `TestSignalFactory` creates synthetic `Signal`, `Strategy`, `ExchangeAccount`, and `RiskEvaluationInput` records in PostgreSQL without any real Signal Engine.
- `tests/e2e/test_signal_lifecycle_e2e.py`:
  - `test_e2e_signal_to_protected_order_and_stop_execution_with_test_signal_factory`
  - `test_e2e_signal_rejected_when_risk_per_trade_is_0_01_or_higher`
  - `test_e2e_signal_expired_by_price_drift_with_test_signal_factory`

### 2.5 Dead-Letter & Admin-Only Replay Tests in CI (Requirement #6)
- `tests/integration/test_outbox_and_workers.py`:
  - `test_outbox_delivery_retry_dead_letter_and_replay` (service-level `ForbiddenError` for `OPERATIONAL` and success for `ADMIN`)
  - `test_dead_letter_admin_only_replay_via_api` (HTTP `POST /api/v1/system/dead-letters/{id}/replay` returning `403` for `OPERATIONAL` and `200` for `ADMIN`)

### 2.6 Chaos Tests Suite (`tests/chaos/test_f2_chaos.py`) (Requirement #7)
1. `test_chaos_api_disconnection_and_recovery`: Exchange/API outage during stop execution transitions to `MANUAL_REVIEW` after 3 retries (`0s, 5s, 15s`) and recovers when reconnected.
2. `test_chaos_risk_engine_heartbeat_timeout_triggers_kill_switch`: Stale Risk Engine heartbeat (`> 60s`) triggers automatic Kill Switch activation by the independent Kill Switch Service.
3. `test_chaos_kill_switch_service_restart_preserves_state`: Restarting the independent Kill Switch Service preserves `is_active=True` and the 24-hour (`86400s`) pending resume request in PostgreSQL.
4. `test_chaos_database_disconnection_fails_closed`: Database outage causes `/readyz` on the Kill Switch Service to return `503 Service Unavailable` (`not_ready`).
5. `test_chaos_redis_restart_preserves_durable_domain_state`: Redis outage and restart loses zero PostgreSQL domain state and enforces all `FORBIDDEN_DURABLE_PREFIXES` in central config.

---

## 3. CI/CD, Static Analysis & Test Coverage Evidence

- **Remediated F2 Code Commit:** `676a0ed47c6259074483272cd06ec132e7b10334`
- **GitHub Actions Workflows on `676a0ed47c6259074483272cd06ec132e7b10334` (All Green):**
  - `CI` (Run ID `37142099958`, Python 3.12 + PostgreSQL 16 + Redis 7): `completed / success`
  - `Security & Paper Isolation Scan` (Run ID `37142099978`): `completed / success`
  - `Docker Build & Compose Validation` (Run ID `37142099977`, including `Dockerfile.kill-switch`, `kill_switch`, and `paper_kill_switch`): `completed / success`
- **Static Analysis Gates:**
  - `ruff check .`: `All checks passed!` (`0` errors across `97` files)
  - `ruff format --check .`: `97 files already formatted` (`0` issues)
  - `mypy --strict app`: `Success: no issues found in 65 source files` (`0` errors)
- **Test & Coverage Summary (`107 passed`):**
  - Total `app/` coverage: `92.68%` (required `>= 80%`)
  - `app/core/*`: `95%` (required `>= 90%`)
  - `app/db/*`: `99%` (required `>= 90%`)
  - `app/services/risk_engine.py`: `97%` (required `>= 90%`)
  - `app/services/state_machine.py`: `93%` (required `>= 90%`)
  - `app/services/kill_switch.py`: `92%` (required `>= 90%`)
  - `app/core/security.py`: `100%` (required `>= 90%`)
  - `app/services/synthetic_stop.py`: `94%` (required `>= 90%`)
  - `app/services/outbox.py`: `96%` (required `>= 90%`)

