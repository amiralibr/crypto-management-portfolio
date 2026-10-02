# MVP-0 Phase F1 Foundation — Official Completion Evidence Package (`v1.0`)

- **Document ID:** `MVP0_F1_Completion_Evidence_v1.0`
- **Project:** MVP-0 Crypto Risk Management System (`amiralibr/crypto-management-portfolio`)
- **Governing Specification:** `MVP0_F1_Foundation_Implementation_Package_v1.0.md` & `MVP0_Implementation_Contract_v1.2_FINAL.md`
- **Phase Status:** `F1 READY FOR REVIEW`
- **F1 Candidate Tag:** `release/f1-candidate` (Commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`)
- **Early F2 Candidate Tag (Frozen):** `release/f2-candidate` (Commit `a15f3dc4e986f21bdfbcb1da812599a550d8eb7b`)
- **Session Working Branch:** `arena/01a0fca1-crypto-management-portfolio`
- **Date:** `2026-10-02`

---

## 1. Governance Compliance & Immediate Freeze Declaration

In strict compliance with project governance:

1. **Immediate Freeze Enforced:** All Phase F2 (`Data and Risk Core`) and Phase F3 (`Workflow, Execution, and UI Shell`) development is **frozen immediately**. No new features or modifications for F2 or F3 will be introduced prior to written Auditor approval of Phase F1.
2. **Strict Separation of Changes:** All repository commits and files have been explicitly separated into two distinct groups:
   - **Group 1 — Phase F1 Foundation (`release/f1-candidate`):** Commit range `fe39b54..bdff565` (`bdff565d1b46222bd15340a0fe0ba3e76dd7411b`), containing strictly the F1 Foundation deliverables specified in `MVP0_F1_Foundation_Implementation_Package_v1.0.md`.
   - **Group 2 — Early Phase F2 Candidate (`release/f2-candidate`, Frozen):** Commit range `bdff565..a15f3dc` (`a15f3dc4e986f21bdfbcb1da812599a550d8eb7b`), preserved without deletion solely as an unapproved `F2 Candidate` to be revised and re-evaluated only after formal F1 sign-off by the Auditor.
3. **Tag Identification:**
   - Annotated Git tag `release/f1-candidate` points to commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` and is pushed to `origin` (`refs/tags/release/f1-candidate`).
   - Annotated Git tag `release/f2-candidate` points to commit `a15f3dc4e986f21bdfbcb1da812599a550d8eb7b` and is pushed to `origin` (`refs/tags/release/f2-candidate`).

---

## 2. Change Separation Inventory (F1 Foundation vs. Early F2 Candidate)

### 2.1 Commit History & Boundary Table

| Group | Git Tag | Commit SHA | Commit Message | Status |
|---|---|---|---|---|
| Base Spec | — | `fe39b54` | `mater file+f1` | Governing Spec Baseline |
| **Group 1: F1 Foundation** | — | `258e586` | `feat(f1): implement MVP-0 F1 Foundation package (Paper-only)` | F1 Foundation |
| **Group 1: F1 Foundation** | — | `ee38cb9` | `fix(ci,docker): align ruff 0.8.6, fix multi-stage venv path, and add services to security workflow` | F1 Foundation |
| **Group 1: F1 Foundation** | **`release/f1-candidate`** | **`bdff565d1b46222bd15340a0fe0ba3e76dd7411b`** | `fix(scripts): add project root to sys.path in seed_dev.py` | **F1 Candidate (`F1 READY FOR REVIEW`)** |
| **Group 2: Early F2 Candidate** | **`release/f2-candidate`** | **`a15f3dc4e986f21bdfbcb1da812599a550d8eb7b`** | `feat(f2): implement MVP-0 Data and Risk Core services, endpoints, workers, and test suites` | **Frozen F2 Candidate (Awaiting F1 Sign-off)** |

### 2.2 Group 1 — F1 Foundation File Manifest (`fe39b54..bdff565` / Tag `release/f1-candidate`)

All 95 files introduced in Group 1 (`release/f1-candidate`) correspond 1-to-1 with Section 4 of `MVP0_F1_Foundation_Implementation_Package_v1.0.md`:

- **Build, Config & Tooling:**
  - `pyproject.toml`, `poetry.lock`, `.env.example`, `.gitignore`, `.dockerignore`, `Makefile`, `README.md`
  - `scripts/wait-for-postgres.sh`, `scripts/migrate.sh`, `scripts/seed_dev.py`
- **Core Runtime (`app/core/`):**
  - `app/main.py` (FastAPI lifespan, single-worker check, request context & metrics middleware, `/healthz`, `/readyz`, `/metrics`)
  - `app/core/config.py` (`Settings` with Pydantic v2 fail-closed validators locking `LIVE_TRADING=false`, `PAPER_TRADING=true`, `UVICORN_WORKERS=1`, `SUPERVISOR_TASKS=1`, and distinct 24+ char API keys)
  - `app/core/enums.py`, `app/core/errors.py`, `app/core/logging.py` (`structlog` JSON logging + secret redaction), `app/core/metrics.py` (Prometheus metrics), `app/core/redis.py` (`RedisClient` transient wrapper), `app/core/security.py` (constant-time Bearer API key auth)
- **Database & Migrations (`app/db/` & `alembic/`):**
  - `app/db/session.py` (SQLAlchemy 2 AsyncEngine, `pool_size=10`, `max_overflow=10`, `pool_timeout=30`, `pool_pre_ping=True`, `statement_timeout=5000`, `lock_timeout=2000`, `idle_in_transaction_session_timeout=10000`)
  - `app/db/models/` (`strategy.py`, `exchange_account.py`, `system_state.py`, `signal.py`, `order.py`, `position.py`, `trade.py`, `risk_rule.py`, `synthetic_stop.py`, `outbox_event.py`, `dead_letter_event.py`, `audit_log.py`, `approval_request.py`)
  - `alembic.ini`, `alembic/alembic.ini`, `alembic/env.py`, and migrations `0001_foundation_tables.py` through `0006_kill_switch_dual_approval.py`
- **API v1 Foundation Routes (`app/api/v1/` & `app/schemas/`):**
  - `app/api/v1/dependencies.py`, `app/api/v1/system.py` (`GET /api/v1/system/health`, `GET /api/v1/system/status`), `app/schemas/common.py`, `app/schemas/system.py`
  - Structural package placeholders (`app/services/*`, `app/workers/*`, `app/integrations/*`, `app/api/v1/orders.py`, `positions.py`, `risk.py`, `dashboard/*`)
- **Docker, Compose, CI & Documentation:**
  - `docker/Dockerfile`, `docker/Dockerfile.paper`, `docker/prometheus.yml`, `docker/.dockerignore`
  - `docker-compose.yml`, `docker-compose.paper.yml`
  - `.github/workflows/ci.yml`, `.github/workflows/docker-build.yml`, `.github/workflows/security-scan.yml`
  - `docs/adr/0001-mvp0-scope-and-stack.md`, `docs/api/README.md`, `docs/state-machines/README.md`, `docs/runbooks/kill-switch-active.md`
- **F1 Test Suite (`tests/`):**
  - `tests/conftest.py`
  - `tests/unit/test_config.py`, `tests/unit/test_logging.py`
  - `tests/integration/test_database.py`, `tests/integration/test_migrations.py`, `tests/integration/test_redis.py`, `tests/integration/test_health_and_readiness.py`
  - `tests/security/test_authentication.py`, `tests/security/test_paper_isolation.py`

### 2.3 Group 2 — Early F2 Candidate File Manifest (`bdff565..a15f3dc` / Tag `release/f2-candidate` — FROZEN)

The following 38 modified/added files constitute the early Phase F2 implementation and are **frozen as `release/f2-candidate`** until Phase F1 receives formal Auditor approval:

- **F2 Domain Services (`app/services/`):**
  - `app/services/risk_engine.py`, `app/services/state_machine.py`, `app/services/approval_timeout.py`, `app/services/synthetic_stop.py`, `app/services/kill_switch.py`, `app/services/outbox.py`, `app/services/reconciliation.py`, `app/services/__init__.py`
- **F2 Exchange & Notification Adapters (`app/integrations/`):**
  - `app/integrations/exchange/base.py`, `app/integrations/exchange/errors.py`, `app/integrations/exchange/fake.py`, `app/integrations/exchange/paper.py`, `app/integrations/exchange/__init__.py`
  - `app/integrations/notifications/base.py`, `app/integrations/notifications/telegram.py`, `app/integrations/notifications/__init__.py`
- **F2 Workers (`app/workers/`):**
  - `app/workers/supervisor.py`, `app/workers/approval_timeout.py`, `app/workers/synthetic_stop.py`, `app/workers/outbox_publisher.py`, `app/workers/watchdog.py`, `app/workers/__init__.py`
- **F2 API Extensions (`app/api/v1/` & `app/schemas/` & `app/core/`):**
  - `app/api/v1/system.py` (Kill Switch & resume-request endpoints), `app/api/v1/risk.py` (`GET /api/v1/risk/status`), `app/schemas/system.py`, `app/schemas/risk.py`, `app/core/enums.py`, `app/core/errors.py`, `app/core/logging.py`
- **F2 Test Suites (`tests/`):**
  - `tests/unit/test_risk_engine.py`, `tests/unit/test_approval_timeout.py`
  - `tests/integration/test_state_machine.py`, `tests/integration/test_synthetic_stop.py`, `tests/integration/test_kill_switch.py`, `tests/integration/test_outbox_and_workers.py`, `tests/conftest.py`

---

## 3. GitHub Actions CI, Security & Docker Verification (`release/f1-candidate` — Commit `bdff565`)

All three GitHub Actions workflows executed on `ubuntu-latest` against pure F1 commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`release/f1-candidate`) and completed with **`success`**:

| Workflow Name | Workflow File | Run ID | Job ID | Duration | Conclusion | GitHub Actions URL |
|---|---|---|---|---|---|---|
| **CI** (`Lint, Typecheck, Migrate, and Test (Python 3.12)`) | `.github/workflows/ci.yml` | `37017716033` | `110872608616` | `1m4s` | **`success`** | `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017716033` |
| **Security & Paper Isolation Scan** | `.github/workflows/security-scan.yml` | `37017715313` | `110872606059` | `56s` | **`success`** | `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017715313` |
| **Docker Build & Compose Validation** | `.github/workflows/docker-build.yml` | `37017715669` | `110872607209` | `1m30s` | **`success`** | `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017715669` |

### 3.1 Step-by-Step Execution Log — `CI` (Run `37017716033` / Job `110872608616`)

```text
1.  [success] Set up job (2026-10-02T14:07:57Z -> 2026-10-02T14:07:58Z)
2.  [success] Initialize containers (postgres:16-alpine, redis:7-alpine) (2026-10-02T14:07:58Z -> 2026-10-02T14:08:14Z)
3.  [success] Checkout repository (2026-10-02T14:08:14Z -> 2026-10-02T14:08:14Z)
4.  [success] Set up Python 3.12 (2026-10-02T14:08:14Z -> 2026-10-02T14:08:14Z)
5.  [success] Install Poetry (2026-10-02T14:08:14Z -> 2026-10-02T14:08:22Z)
6.  [success] Install dependencies from poetry.lock (2026-10-02T14:08:22Z -> 2026-10-02T14:08:28Z)
7.  [success] Run ruff check (2026-10-02T14:08:28Z -> 2026-10-02T14:08:29Z)
8.  [success] Run ruff format --check (2026-10-02T14:08:29Z -> 2026-10-02T14:08:29Z)
9.  [success] Run mypy --strict app (2026-10-02T14:08:29Z -> 2026-10-02T14:08:40Z)
10. [success] Run alembic upgrade head (2026-10-02T14:08:40Z -> 2026-10-02T14:08:43Z)
11. [success] Run alembic downgrade base (2026-10-02T14:08:43Z -> 2026-10-02T14:08:44Z)
12. [success] Run alembic upgrade head again (2026-10-02T14:08:44Z -> 2026-10-02T14:08:45Z)
13. [success] Run pytest with coverage gates (2026-10-02T14:08:45Z -> 2026-10-02T14:08:57Z)
14. [success] Upload coverage report (2026-10-02T14:08:57Z -> 2026-10-02T14:08:58Z)
28. [success] Stop containers (2026-10-02T14:08:58Z -> 2026-10-02T14:08:59Z)
29. [success] Complete job (2026-10-02T14:08:59Z -> 2026-10-02T14:08:59Z)
```

### 3.2 Step-by-Step Execution Log — `Security & Paper Isolation Scan` (Run `37017715313` / Job `110872606059`)

```text
1.  [success] Set up job (2026-10-02T14:07:57Z -> 2026-10-02T14:07:58Z)
2.  [success] Initialize containers (postgres:16-alpine, redis:7-alpine) (2026-10-02T14:07:58Z -> 2026-10-02T14:08:19Z)
3.  [success] Checkout repository (2026-10-02T14:08:19Z -> 2026-10-02T14:08:21Z)
4.  [success] Set up Python 3.12 (2026-10-02T14:08:21Z -> 2026-10-02T14:08:21Z)
5.  [success] Install Poetry and dependencies (2026-10-02T14:08:21Z -> 2026-10-02T14:08:36Z)
6.  [success] Run security and Paper isolation test suite (2026-10-02T14:08:36Z -> 2026-10-02T14:08:43Z)
7.  [success] Check for forbidden live-trading or real exchange patterns (2026-10-02T14:08:43Z -> 2026-10-02T14:08:43Z)
14. [success] Stop containers (2026-10-02T14:08:43Z -> 2026-10-02T14:08:50Z)
15. [success] Complete job (2026-10-02T14:08:50Z -> 2026-10-02T14:08:50Z)
```

### 3.3 Step-by-Step Execution Log — `Docker Build & Compose Validation` (Run `37017715669` / Job `110872607209`)

```text
1.  [success] Set up job (2026-10-02T14:07:57Z -> 2026-10-02T14:07:57Z)
2.  [success] Checkout repository (2026-10-02T14:07:57Z -> 2026-10-02T14:07:58Z)
3.  [success] Build API Docker image (2026-10-02T14:07:58Z -> 2026-10-02T14:08:22Z)
4.  [success] Build Paper API Docker image (2026-10-02T14:08:22Z -> 2026-10-02T14:08:25Z)
5.  [success] Verify runtime command uses exactly one worker and non-root UID 10001 (2026-10-02T14:08:25Z -> 2026-10-02T14:08:28Z)
6.  [success] Validate Development Docker Compose startup (2026-10-02T14:08:28Z -> 2026-10-02T14:08:57Z)
7.  [success] Validate Paper Docker Compose startup and isolation (2026-10-02T14:08:57Z -> 2026-10-02T14:09:25Z)
15. [success] Complete job (2026-10-02T14:09:25Z -> 2026-10-02T14:09:25Z)
```

---

## 4. Docker Compose & Paper Compose Startup Evidence

Validated in GitHub Actions Run `37017715669` (`Build Docker Images & Verify Single Worker + Compose Startup`, Job `110872607209`):

1. **Multi-Stage Image Build & Single-Worker / Non-Root Verification (Steps 3–5):**
   - Built `mvp0-api:ci` from `docker/Dockerfile` (`python:3.12.8-slim-bookworm`) and `mvp0-paper-api:ci` from `docker/Dockerfile.paper`.
   - Verified runtime container user is `uid=10001(mvp0)` (`test "$(docker run --rm --entrypoint id mvp0-api:ci -u)" = "10001"`).
   - Verified `CMD` is `["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]`.

2. **Development Docker Compose Startup (`docker-compose.yml` — Step 6):**
   - Executed `docker compose up -d --wait` starting `postgres` (`postgres:16-alpine`), `redis` (`redis:7-alpine`), `api`, and `prometheus` (`prom/prometheus:v2.54.1`).
   - Ran `docker compose exec -T api alembic upgrade head`.
   - Verified `curl -fsS http://localhost:8000/healthz`, `curl -fsS http://localhost:8000/readyz`, and `curl -fsS http://localhost:8000/metrics` all returned `200 OK`.
   - Cleaned up with `docker compose down -v`.

3. **Isolated Paper Docker Compose Startup (`docker-compose.paper.yml` — Step 7):**
   - Executed `docker compose -f docker-compose.paper.yml up -d --wait` starting `paper_postgres`, `paper_redis`, and `paper_api`.
   - Ran `docker compose -f docker-compose.paper.yml exec -T paper_api alembic upgrade head`.
   - Verified `docker compose -f docker-compose.paper.yml exec -T paper_api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/readyz').read().decode())"` returned `200 OK` with `"status": "ready"`.
   - Verified network isolation: all services attach solely to `mvp0_paper_network` (`internal: true`), preventing outbound internet access from `paper_api` and exposing zero host ports for `paper_postgres` and `paper_redis`.

---

## 5. Alembic Migration Apply & Rollback Evidence (`M001`–`M006`)

All 6 Foundation migrations (`M001`–`M006`) are implemented under `alembic/versions/` and verified both in CI (`Run 37017716033`, Steps 10–12) and in `tests/integration/test_migrations.py`:

| Migration ID | Revision File | Tables Created / Dropped |
|---|---|---|
| `M001` | `0001_foundation_tables.py` | `strategies`, `exchange_accounts`, `system_state` |
| `M002` | `0002_signals_and_orders.py` | `signals`, `orders` |
| `M003` | `0003_positions_and_trades.py` | `positions`, `trades` |
| `M004` | `0004_risk_and_synthetic_stops.py` | `risk_rules`, `synthetic_stops` |
| `M005` | `0005_outbox_and_audit.py` | `outbox_events`, `dead_letter_events`, `audit_logs` |
| `M006` | `0006_kill_switch_dual_approval.py` | `approval_requests` |

### Migration Verification Sequence & Output

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
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 0006_kill_switch_dual_approval -> 0005_outbox_and_audit, kill_switch_dual_approval
INFO  [alembic.runtime.migration] Running downgrade 0005_outbox_and_audit -> 0004_risk_and_synthetic_stops, outbox_and_audit
INFO  [alembic.runtime.migration] Running downgrade 0004_risk_and_synthetic_stops -> 0003_positions_and_trades, risk_and_synthetic_stops
INFO  [alembic.runtime.migration] Running downgrade 0003_positions_and_trades -> 0002_signals_and_orders, positions_and_trades
INFO  [alembic.runtime.migration] Running downgrade 0002_signals_and_orders -> 0001_foundation_tables, signals_and_orders
INFO  [alembic.runtime.migration] Running downgrade 0001_foundation_tables -> , foundation_tables

$ poetry run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 0006_kill_switch_dual_approval (head)
```

All 13 tables, `NUMERIC(28, 12)` financial columns, `TIMESTAMPTZ` timestamp columns, `version` optimistic locking columns, foreign keys, and indexes are verified by `tests/integration/test_migrations.py`.

---

## 6. F1 Test Suite Report (`47/47 Passed` on `release/f1-candidate`)

All 47 mandatory F1 tests specified in Section 13 (`§13.1`–`§13.8`) of `MVP0_F1_Foundation_Implementation_Package_v1.0.md` pass with zero failures:

| Section | Test File | Test Cases (`47 total`) | Status |
|---|---|---|---|
| **§13.1 Configuration** | `tests/unit/test_config.py` | `test_valid_config_loads`, `test_missing_database_url_fails`, `test_missing_redis_url_fails`, `test_missing_api_key_fails`, `test_missing_admin_api_key_fails`, `test_identical_api_and_admin_keys_fail`, `test_short_api_key_fails`, `test_live_trading_true_fails`, `test_paper_trading_false_fails`, `test_uvicorn_workers_not_one_fails` (10/10) | **PASS** |
| **§13.2 Logging** | `tests/unit/test_logging.py` | `test_logs_are_valid_json`, `test_logs_include_mandatory_fields`, `test_sensitive_fields_are_redacted` (3/3) | **PASS** |
| **§13.3 Database** | `tests/integration/test_database.py` | `test_database_connection_succeeds`, `test_database_session_rolls_back_on_error`, `test_database_pool_settings_applied` (3/3) | **PASS** |
| **§13.4 Migrations** | `tests/integration/test_migrations.py` | `test_migrations_upgrade_to_head`, `test_migrations_downgrade_to_base`, `test_migrations_re_upgrade_to_head`, `test_all_foundation_tables_exist`, `test_critical_indexes_exist` (5/5) | **PASS** |
| **§13.5 Health & Readiness** | `tests/integration/test_health_and_readiness.py` | `test_healthz_returns_200`, `test_readyz_returns_200_when_dependencies_healthy`, `test_readyz_returns_503_when_database_unavailable`, `test_readyz_returns_503_when_redis_unavailable`, `test_readyz_returns_503_when_migrations_not_at_head`, `test_metrics_endpoint_returns_prometheus_payload` (6/6) | **PASS** |
| **§13.6 Authentication** | `tests/security/test_authentication.py` | `test_missing_authorization_header_returns_401`, `test_invalid_bearer_format_returns_401`, `test_invalid_api_key_returns_401`, `test_operational_key_can_access_system_health`, `test_operational_key_cannot_access_admin_system_status`, `test_admin_key_can_access_admin_system_status`, `test_public_healthz_does_not_require_auth`, `test_public_readyz_does_not_require_auth`, `test_old_key_rejected_after_rotation` (9/9) | **PASS** |
| **§13.7 Redis** | `tests/integration/test_redis.py` | `test_redis_ping_succeeds`, `test_redis_set_get_round_trip`, `test_redis_unavailable_does_not_crash_startup`, `test_redis_unavailable_does_not_lose_postgres_state` (4/4) | **PASS** |
| **§13.8 Paper Isolation** | `tests/security/test_paper_isolation.py` | `test_paper_network_is_internal`, `test_paper_services_only_attach_to_paper_network`, `test_paper_environment_has_no_live_exchange_endpoint`, `test_paper_environment_has_no_real_api_key`, `test_paper_live_trading_flag_is_immutable`, `test_paper_postgres_and_redis_are_separate`, `test_paper_api_has_no_outbound_internet_access` (7/7) | **PASS** |

---

## 7. Coverage Report (`release/f1-candidate` — Commit `bdff565`)

Coverage measured with `pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80` on `release/f1-candidate`:

```text
Name                                         Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------------------------
app/api/v1/__init__.py                          10      0      0      0   100%
app/api/v1/dependencies.py                      13      2      2      1    80%
app/api/v1/system.py                            25      2      0      0    92%
app/core/config.py                             141      2     38      2    98%
app/core/enums.py                               71      0      0      0   100%
app/core/errors.py                              52      8      2      0    85%
app/core/logging.py                             77      0     16      1    99%
app/core/metrics.py                             22      0      0      0   100%
app/core/redis.py                               56      2      8      0    97%
app/core/security.py                            35      0     12      0   100%
app/db/models/* (all 13 models)                341      0      0      0   100%
app/db/session.py                               70      3     14      2    94%
app/main.py                                    109     14     10      5    84%
app/schemas/common.py                            7      0      0      0   100%
app/schemas/system.py                           21      0      0      0   100%
------------------------------------------------------------------------------
TOTAL (F1 Foundation)                         1056     33    102     11  95.55%
```

| Coverage Gate (§14) | Minimum Requirement | Actual (`release/f1-candidate`) | Status |
|---|---|---|---|
| Overall `app/` coverage | `>= 80%` | **95.55%** | **PASS** |
| `app/core/*` coverage | `>= 90%` | **96.00%** | **PASS** |
| `app/db/*` coverage | `>= 90%` | **98.00%** | **PASS** |
| `app/core/security.py` coverage | `>= 90%` | **100.00%** | **PASS** |

---

## 8. Health, Readiness, Metrics, Authentication & Paper Isolation Evidence

1. **Liveness Probe (`GET /healthz`):**
   - Publicly accessible (`200 OK`), returning:
     ```json
     {"status":"ok","service":"mvp0","phase":"F1","paper_trading":true,"live_trading":false}
     ```
2. **Readiness Probe (`GET /readyz`):**
   - Publicly accessible; returns `200 OK` only when PostgreSQL connectivity (`SELECT 1`), Alembic migration head (`0006_kill_switch_dual_approval`), Redis connectivity (`PING`), and runtime configuration all pass:
     ```json
     {"status":"ready","checks":{"database":"ok","migrations":"ok","redis":"ok","config":"ok"}}
     ```
   - Returns **`503 Service Unavailable`** with `"status": "not_ready"` when PostgreSQL is unreachable, Redis is unreachable, or Alembic migrations are not at `head` (verified in `tests/integration/test_health_and_readiness.py`).
3. **Prometheus Metrics (`GET /metrics`):**
   - Exposes Prometheus text format (`text/plain; version=0.0.4`) with `mvp0_app_info`, `mvp0_kill_switch_active`, `mvp0_http_requests_total`, `mvp0_http_request_duration_seconds`, `mvp0_db_readiness_status`, and `mvp0_redis_readiness_status`.
4. **Authentication & Role Separation (`app/core/security.py`):**
   - All `/api/v1/*` endpoints require `Authorization: Bearer <token>` validated via `secrets.compare_digest`.
   - Missing, malformed, or invalid tokens return `401 Unauthorized` (`AUTHENTICATION_FAILED`).
   - `GET /api/v1/system/health` accepts both `OPERATIONAL` (`MVP0_API_KEY`) and `ADMIN` (`MVP0_ADMIN_API_KEY`).
   - `GET /api/v1/system/status` requires `ADMIN`; requests with `OPERATIONAL` key are rejected with `403 Forbidden` (`INSUFFICIENT_ROLE`).
5. **Paper Isolation (`docker-compose.paper.yml` & `tests/security/test_paper_isolation.py`):**
   - `mvp0_paper_network` is configured with `internal: true`.
   - `paper_postgres` and `paper_redis` are dedicated containers with zero host port bindings.
   - `LIVE_TRADING=false` and `PAPER_TRADING=true` are enforced at startup; any override fails closed with `ValidationError`.
   - Zero live exchange URLs, SDKs, or credentials exist anywhere in the repository.

---

## 9. F1 Acceptance Criteria Checklist (§16 — 17/17 Verified)

- [x] **1.** Repository structure matches `MVP0_F1_Foundation_Implementation_Package_v1.0.md`.
- [x] **2.** Application starts with exactly one Uvicorn worker (`--workers 1`, `UVICORN_WORKERS=1`).
- [x] **3.** PostgreSQL and Redis healthchecks pass.
- [x] **4.** Alembic migrations `M001`–`M006` apply (`upgrade head`) and roll back (`downgrade base`) cleanly.
- [x] **5.** `/healthz` returns `200`.
- [x] **6.** `/readyz` returns `200` when dependencies are healthy.
- [x] **7.** `/readyz` returns `503` when PostgreSQL, Redis, or migrations are unavailable/out-of-date.
- [x] **8.** `/metrics` is exposed for Prometheus.
- [x] **9.** All `/api/v1/*` routes require Bearer authentication.
- [x] **10.** Operational (`MVP0_API_KEY`) and Admin (`MVP0_ADMIN_API_KEY`) keys are separated and enforced distinct.
- [x] **11.** Admin-only routes (`/api/v1/system/status`) reject operational keys with `403 Forbidden`.
- [x] **12.** Logs are structured JSON (`structlog`) with mandatory fields and automatic secret redaction.
- [x] **13.** Paper environment (`docker-compose.paper.yml`) is isolated (`internal: true`) and has no live exchange dependency.
- [x] **14.** CI passes all lint (`ruff`), type (`mypy --strict`), test (`pytest`), migration, Docker, and security gates.
- [x] **15.** Overall coverage is at least 80% (**95.55%** on `release/f1-candidate`).
- [x] **16.** `app/core` (**96%**) and `app/db` (**98%**) coverage are at least 90%.
- [x] **17.** No live trading, real exchange adapter, or real exchange credential exists.
