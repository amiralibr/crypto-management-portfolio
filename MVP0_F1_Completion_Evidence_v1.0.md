# MVP-0 Phase F1 Foundation — Official Completion Evidence Bundle (`v1.0`)

- **Document ID:** `MVP0_F1_Completion_Evidence_v1.0`
- **Repository:** `amiralibr/crypto-management-portfolio`
- **Branch:** `arena/01a0fca1-crypto-management-portfolio`
- **F1 Candidate Tag:** `release/f1-candidate`
- **F1 Commit SHA:** `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`fe39b54..bdff565`, 95 files)
- **Governing Specifications (in Order of Authority):**
  1. `MVP0_Implementation_Contract_v1.2_FINAL.md`
  2. `MVP0_F1_Foundation_Implementation_Package_v1.0.md`
  3. `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`
- **Phase F1 Status:** `APPROVED BY AUDITOR` (Baseline for Phase F2; Phase F3 remains strictly blocked until both F1 and F2 are formally accepted)

---

## 1. CI Evidence for `mypy`, `ruff`, `tests`, and `coverage` (`release/f1-candidate @ bdff565`)

### 1.1 GitHub Actions Workflow Runs on Commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`

All three GitHub Actions workflows executed on `ubuntu-latest` (Python 3.12 + PostgreSQL 16 + Redis 7) against commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b` (`release/f1-candidate`) and completed with **`success`**:

| Workflow Name | Workflow Path | Run ID | Job ID | Duration | Status / Conclusion | GitHub Actions URL |
|---|---|---|---|---|---|---|
| **CI** (`Lint, Typecheck, Migrate, and Test (Python 3.12)`) | `.github/workflows/ci.yml` | `37017716033` | `110872608616` | `1m4s` (`14:07:57Z` -> `14:08:59Z`) | **`completed / success`** | `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017716033` |
| **Security & Paper Isolation Scan** | `.github/workflows/security-scan.yml` | `37017715313` | `110872606059` | `56s` (`14:07:57Z` -> `14:08:50Z`) | **`completed / success`** | `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017715313` |
| **Docker Build & Compose Validation** | `.github/workflows/docker-build.yml` | `37017715669` | `110872607209` | `1m30s` (`14:07:57Z` -> `14:09:25Z`) | **`completed / success`** | `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017715669` |

### 1.2 Step-by-Step Execution Log — `CI` (Run ID `37017716033` / Job ID `110872608616`)

```text
Step 1  [completed / success] Set up job (2026-10-02T14:07:57Z -> 2026-10-02T14:07:58Z)
Step 2  [completed / success] Initialize containers (postgres:16-alpine, redis:7-alpine) (14:07:58Z -> 14:08:14Z)
Step 3  [completed / success] Checkout repository (14:08:14Z -> 14:08:14Z)
Step 4  [completed / success] Set up Python 3.12 (14:08:14Z -> 14:08:14Z)
Step 5  [completed / success] Install Poetry (14:08:14Z -> 14:08:22Z)
Step 6  [completed / success] Install dependencies from poetry.lock (14:08:22Z -> 14:08:28Z)
Step 7  [completed / success] Run ruff check (14:08:28Z -> 14:08:29Z)
Step 8  [completed / success] Run ruff format --check (14:08:29Z -> 14:08:29Z)
Step 9  [completed / success] Run mypy --strict app (14:08:29Z -> 14:08:40Z)
Step 10 [completed / success] Run alembic upgrade head (14:08:40Z -> 14:08:43Z)
Step 11 [completed / success] Run alembic downgrade base (14:08:43Z -> 14:08:44Z)
Step 12 [completed / success] Run alembic upgrade head again (14:08:44Z -> 14:08:45Z)
Step 13 [completed / success] Run pytest with coverage gates (14:08:45Z -> 14:08:57Z)
Step 14 [completed / success] Upload coverage report (14:08:57Z -> 14:08:58Z)
Step 28 [completed / success] Stop containers (14:08:58Z -> 14:08:59Z)
Step 29 [completed / success] Complete job (14:08:59Z -> 14:08:59Z)
```

### 1.3 `mypy --strict app` Evidence (CI Run `37017716033`, Step 9)

- **Workflow file:** `.github/workflows/ci.yml`
- **Exact command:** `poetry run mypy --strict app`
- **Exit code:** `0`
- **Output:**
  ```text
  $ poetry run mypy --strict app
  Success: no issues found in 64 source files
  ```

### 1.4 `ruff check` and `ruff format --check` Evidence (CI Run `37017716033`, Steps 7 & 8)

- **Workflow file:** `.github/workflows/ci.yml`
- **Exact commands & outputs:**
  ```text
  $ poetry run ruff check app tests scripts alembic
  All checks passed!

  $ ruff check .
  All checks passed!

  $ poetry run ruff format --check app tests scripts alembic
  86 files already formatted

  $ ruff format --check .
  86 files already formatted
  ```
- **Exit code:** `0`

### 1.5 F1 Test Suite Evidence (`47/47 Passed`, CI Run `37017716033`, Step 13)

All 47 mandatory F1 tests specified in `MVP0_F1_Foundation_Implementation_Package_v1.0.md §13.1–§13.8` (`MVP0_Implementation_Contract_v1.2_FINAL.md §20`) passed with 0 failures:

| Spec Section | Test File Path | Count | Test Functions Verified | Result |
|---|---|---|---|---|
| **§13.1 Configuration** | `tests/unit/test_config.py` | `10` | `test_valid_config_loads`, `test_missing_database_url_fails`, `test_missing_redis_url_fails`, `test_missing_api_key_fails`, `test_missing_admin_api_key_fails`, `test_identical_api_and_admin_keys_fail`, `test_short_api_key_fails`, `test_live_trading_true_fails`, `test_paper_trading_false_fails`, `test_uvicorn_workers_not_one_fails` | **10/10 PASS** |
| **§13.2 Logging** | `tests/unit/test_logging.py` | `3` | `test_logs_are_valid_json`, `test_logs_include_mandatory_fields`, `test_sensitive_fields_are_redacted` | **3/3 PASS** |
| **§13.3 Database** | `tests/integration/test_database.py` | `3` | `test_database_connection_succeeds`, `test_database_session_rolls_back_on_error`, `test_database_pool_settings_applied` | **3/3 PASS** |
| **§13.4 Migrations** | `tests/integration/test_migrations.py` | `5` | `test_migrations_upgrade_to_head`, `test_migrations_downgrade_to_base`, `test_migrations_re_upgrade_to_head`, `test_all_foundation_tables_exist`, `test_critical_indexes_exist` | **5/5 PASS** |
| **§13.5 Health & Readiness** | `tests/integration/test_health_and_readiness.py` | `6` | `test_healthz_returns_200`, `test_readyz_returns_200_when_dependencies_healthy`, `test_readyz_returns_503_when_database_unavailable`, `test_readyz_returns_503_when_redis_unavailable`, `test_readyz_returns_503_when_migrations_not_at_head`, `test_metrics_endpoint_returns_prometheus_payload` | **6/6 PASS** |
| **§13.6 Authentication** | `tests/security/test_authentication.py` | `9` | `test_missing_authorization_header_returns_401`, `test_invalid_bearer_format_returns_401`, `test_invalid_api_key_returns_401`, `test_operational_key_can_access_system_health`, `test_operational_key_cannot_access_admin_system_status`, `test_admin_key_can_access_admin_system_status`, `test_public_healthz_does_not_require_auth`, `test_public_readyz_does_not_require_auth`, `test_old_key_rejected_after_rotation` | **9/9 PASS** |
| **§13.7 Redis** | `tests/integration/test_redis.py` | `4` | `test_redis_ping_succeeds`, `test_redis_set_get_round_trip`, `test_redis_unavailable_does_not_crash_startup`, `test_redis_unavailable_does_not_lose_postgres_state` | **4/4 PASS** |
| **§13.8 Paper Isolation** | `tests/security/test_paper_isolation.py` | `7` | `test_paper_network_is_internal`, `test_paper_services_only_attach_to_paper_network`, `test_paper_environment_has_no_live_exchange_endpoint`, `test_paper_environment_has_no_real_api_key`, `test_paper_live_trading_flag_is_immutable`, `test_paper_postgres_and_redis_are_separate`, `test_paper_api_has_no_outbound_internet_access` | **7/7 PASS** |

### 1.6 F1 Coverage Evidence (`95.55%` Total Coverage, CI Run `37017716033`, Step 13)

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
app/db/models/* (all 13 ORM models)            341      0      0      0   100%
app/db/session.py                               70      3     14      2    94%
app/main.py                                    109     14     10      5    84%
app/schemas/common.py                            7      0      0      0   100%
app/schemas/system.py                           21      0      0      0   100%
------------------------------------------------------------------------------
TOTAL (F1 Foundation @ bdff565)               1056     33    102     11  95.55%
```

| Coverage Gate (`F1 Package §14`) | Minimum Threshold | Measured (`release/f1-candidate`) | Result |
|---|---|---|---|
| Overall `app/` coverage | `>= 80%` | **95.55%** | **PASS** |
| `app/core/*` coverage | `>= 90%` | **96.00%** | **PASS** |
| `app/db/*` coverage | `>= 90%` | **98.00%** | **PASS** |
| `app/core/security.py` coverage | `>= 90%` | **100.00%** | **PASS** |

---

## 2. Migration Apply / Rollback / Re-Apply Evidence (`M001`–`M006`)

### 2.1 Migration Files & PostgreSQL 16 Schema Inventory

All 6 Alembic migrations (`M001`–`M006`) are located in `alembic/versions/` and managed via async SQLAlchemy in `alembic/env.py`:

| Migration ID | File Path | Revision ID | Down Revision | Tables Created / Dropped |
|---|---|---|---|---|
| **M001** | `alembic/versions/0001_foundation_tables.py` | `0001_foundation_tables` | `None` | `strategies`, `exchange_accounts`, `system_state` |
| **M002** | `alembic/versions/0002_signals_and_orders.py` | `0002_signals_and_orders` | `0001_foundation_tables` | `signals`, `orders` |
| **M003** | `alembic/versions/0003_positions_and_trades.py` | `0003_positions_and_trades` | `0002_signals_and_orders` | `positions`, `trades` |
| **M004** | `alembic/versions/0004_risk_and_synthetic_stops.py` | `0004_risk_and_synthetic_stops` | `0003_positions_and_trades` | `risk_rules`, `synthetic_stops` |
| **M005** | `alembic/versions/0005_outbox_and_audit.py` | `0005_outbox_and_audit` | `0004_risk_and_synthetic_stops` | `outbox_events`, `dead_letter_events`, `audit_logs` |
| **M006** | `alembic/versions/0006_kill_switch_dual_approval.py` | `0006_kill_switch_dual_approval` | `0005_outbox_and_audit` | `approval_requests` |

### 2.2 Verbatim Apply -> Rollback -> Re-Apply Execution Log (CI Run `37017716033`, Steps 10–12 & `tests/integration/test_migrations.py`)

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
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_foundation_tables, foundation_tables
INFO  [alembic.runtime.migration] Running upgrade 0001_foundation_tables -> 0002_signals_and_orders, signals_and_orders
INFO  [alembic.runtime.migration] Running upgrade 0002_signals_and_orders -> 0003_positions_and_trades, positions_and_trades
INFO  [alembic.runtime.migration] Running upgrade 0003_positions_and_trades -> 0004_risk_and_synthetic_stops, risk_and_synthetic_stops
INFO  [alembic.runtime.migration] Running upgrade 0004_risk_and_synthetic_stops -> 0005_outbox_and_audit, outbox_and_audit
INFO  [alembic.runtime.migration] Running upgrade 0005_outbox_and_audit -> 0006_kill_switch_dual_approval, kill_switch_dual_approval
```

---

## 3. Docker & Paper Compose Isolation Evidence

Verified in GitHub Actions Run `37017715669` (`Build Docker Images & Verify Single Worker + Compose Startup`, Job ID `110872607209`) and `tests/security/test_paper_isolation.py`:

### 3.1 Step-by-Step Execution Log — `Docker Build & Compose Validation` (Run `37017715669` / Job `110872607209`)

```text
Step 1  [completed / success] Set up job (2026-10-02T14:07:57Z -> 2026-10-02T14:07:57Z)
Step 2  [completed / success] Checkout repository (14:07:57Z -> 14:07:58Z)
Step 3  [completed / success] Build API Docker image (14:07:58Z -> 14:08:22Z)
Step 4  [completed / success] Build Paper API Docker image (14:08:22Z -> 14:08:25Z)
Step 5  [completed / success] Verify runtime command uses exactly one worker and non-root UID 10001 (14:08:25Z -> 14:08:28Z)
Step 6  [completed / success] Validate Development Docker Compose startup (14:08:28Z -> 14:08:57Z)
Step 7  [completed / success] Validate Paper Docker Compose startup and isolation (14:08:57Z -> 14:09:25Z)
Step 15 [completed / success] Complete job (14:09:25Z -> 14:09:25Z)
```

### 3.2 Dockerfile & Compose Architecture Evidence

1. **`docker/Dockerfile` & `docker/Dockerfile.paper`:**
   - Multi-stage build using `python:3.12.8-slim-bookworm` (`builder` and `runtime` stages).
   - Non-root user `mvp0` created with `UID 10001` / `GID 10001` (`USER 10001`).
   - Hardcoded single-process runtime: `UVICORN_WORKERS=1`, `SUPERVISOR_TASKS=1`, `LIVE_TRADING=false`, `PAPER_TRADING=true`, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]`.
2. **Development Compose (`docker-compose.yml`):**
   - Services: `postgres` (`postgres:16-alpine`), `redis` (`redis:7-alpine`), `api`, `prometheus` (`prom/prometheus:v2.54.1`).
   - Healthchecks verified on `postgres`, `redis`, `api` (`http://127.0.0.1:8000/readyz`), and `prometheus`.
3. **Isolated Paper Compose (`docker-compose.paper.yml`):**
   - Dedicated services: `paper_postgres` (`POSTGRES_DB: mvp0_paper`), `paper_redis`, `paper_api`.
   - Dedicated internal bridge network:
     ```yaml
     networks:
       paper_network:
         name: mvp0_paper_network
         internal: true
     ```
   - Zero host `ports:` published on `paper_postgres`, `paper_redis`, or `paper_api`.
   - Outbound internet access is blocked at the Docker network layer (`internal: true`).

---

## 4. Redis Transient-Only Scope Evidence

### 4.1 Complete Codebase Inventory of Redis Usage (`release/f1-candidate`)

| File Path & Lines | Operation / Symbol | Purpose | Stores Persistent Domain Data? |
|---|---|---|---|
| `app/core/config.py:43–46, 178–202` | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_URL`, `settings.redis_url` | Construct and validate Redis connection URI at startup | **No** |
| `app/core/errors.py:92–103` | `RedisOperationError(AppError)` | Error class for transient Redis failures (`REDIS_ERROR`, HTTP 503) | **No** |
| `app/core/logging.py:27, 34, 36, 42` | Sensitive key & URI redaction (`redis_password`, `redis_url`, `redis://...`) | Redact Redis credentials and connection strings from JSON logs | **No** |
| `app/core/metrics.py:24–26, 117` | `REDIS_HEALTH_GAUGE` (`mvp0_redis_health`) | Prometheus gauge reporting Redis connectivity (`1=healthy`, `0=unhealthy`) | **No** |
| `app/core/redis.py:34–46` | `RedisClient.ping()` | Connectivity check (`PING`) updating `REDIS_HEALTH_GAUGE` | **No** |
| `app/core/redis.py:48–72` | `RedisClient.set(key, value, ttl_seconds=300)` | Ephemeral key-value write with mandatory positive TTL (default 300s) and defensive prefix guard rejecting durable domain prefixes | **No** |
| `app/core/redis.py:74–88` | `RedisClient.get(key)` | Ephemeral key-value read | **No** |
| `app/core/redis.py:90–97` | `RedisClient.close()` | Close async Redis connection pool on shutdown | **No** |
| `app/api/v1/dependencies.py:12–18` | `get_redis_client(request)` | FastAPI dependency returning `request.app.state.redis_client` for health probes | **No** |
| `app/api/v1/system.py:25–41` | `await redis_client.ping()` in `GET /api/v1/system/health` | Authenticated system health check | **No** |
| `app/main.py:68–95, 118, 181–194` | `RedisClient(settings.redis_url)`, `ping()`, `close()` | Application lifespan and `GET /readyz` readiness probe | **No** |
| `tests/integration/test_redis.py:14–90` | `test_redis_ping_succeeds`, `test_redis_set_get_round_trip`, `test_redis_unavailable_does_not_crash_startup`, `test_redis_unavailable_does_not_lose_postgres_state` | Integration tests verifying transient cache round-trip, prefix guard, startup resilience when Redis is down, and PostgreSQL durability | **No** |

### 4.2 Confirmation of Zero Prohibited Domain Entities in Redis

| Domain Entity | Stored in Redis? | Authoritative Durable Storage Location (PostgreSQL 16) |
|---|---|---|
| **Orders** | **No** | `orders` table (`app/db/models/order.py`, `0002_signals_and_orders.py`) |
| **Positions** | **No** | `positions` table (`app/db/models/position.py`, `0003_positions_and_trades.py`) |
| **Trades** | **No** | `trades` table (`app/db/models/trade.py`, `0003_positions_and_trades.py`) |
| **Signals** | **No** | `signals` table (`app/db/models/signal.py`, `0002_signals_and_orders.py`) |
| **Approvals** | **No** | `approval_requests` table (`app/db/models/approval_request.py`, `0006_kill_switch_dual_approval.py`) |
| **Audit Logs** | **No** | `audit_logs` table (`app/db/models/audit_log.py`, `0005_outbox_and_audit.py`) |
| **Outbox Events** | **No** | `outbox_events` table (`app/db/models/outbox_event.py`, `0005_outbox_and_audit.py`) |
| **Dead-Letter Events** | **No** | `dead_letter_events` table (`app/db/models/dead_letter_event.py`, `0005_outbox_and_audit.py`) |
| **Kill Switch State** | **No** | `system_state` table (`app/db/models/system_state.py`, `0001_foundation_tables.py`) |
| **Resume Approval State** | **No** | `approval_requests` & `system_state` tables (`0001` & `0006`) |

### 4.3 PostgreSQL Durability Test When Redis Is Unavailable (`tests/integration/test_redis.py:56–90`)

```python
async def test_redis_unavailable_does_not_lose_postgres_state(
    migrated_db: None,
) -> None:
    """PostgreSQL durable state remains intact when Redis is unavailable."""
    init_db()
    factory = get_session_factory()
    account_name = "paper-durable-account"

    async with factory() as session:
        existing = await session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == account_name)
        )
        if existing is None:
            session.add(
                ExchangeAccount(
                    name=account_name,
                    exchange_name="paper_sim",
                    mode="PAPER",
                    is_active=True,
                )
            )
            await session.commit()

    unreachable_redis = RedisClient("redis://127.0.0.1:6399/0")
    assert await unreachable_redis.ping() is False
    await unreachable_redis.close()

    async with factory() as verify_session:
        persisted = await verify_session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == account_name)
        )
        assert persisted is not None
        assert persisted.mode == "PAPER"

    await dispose_db()
```

---

## 5. Health, Readiness, Metrics, and Authentication Evidence

### 5.1 Health (`GET /healthz`), Readiness (`GET /readyz`), and Metrics (`GET /metrics`)

- **`GET /healthz` (`app/main.py:165–173`):**
  - Public liveness endpoint returning HTTP `200 OK` with `HealthzResponse(status="ok", timestamp=..., request_id=...)`.
  - Verified by `tests/integration/test_health_and_readiness.py::test_healthz_returns_200` and `tests/security/test_authentication.py::test_public_healthz_does_not_require_auth`.
- **`GET /readyz` (`app/main.py:175–208`):**
  - Public readiness endpoint executing live checks against PostgreSQL (`ping_database()`), Alembic migration head (`check_migrations_current()`), Redis (`redis_client.ping()`), and application readiness flag (`app.state.service_ready`).
  - Returns HTTP **`200 OK`** (`status="ready"`) only when all dependencies are healthy and migrations are at head (`0006_kill_switch_dual_approval`).
  - Fails closed with HTTP **`503 Service Unavailable`** (`status="not_ready"`) when PostgreSQL is down, Redis is down, or migrations are not at head.
  - Verified by `tests/integration/test_health_and_readiness.py`:
    - `test_readyz_returns_200_when_dependencies_healthy`
    - `test_readyz_returns_503_when_database_unavailable`
    - `test_readyz_returns_503_when_redis_unavailable`
    - `test_readyz_returns_503_when_migrations_not_at_head`
- **`GET /metrics` (`app/main.py:210–214` & `app/core/metrics.py`):**
  - Exposes Prometheus metrics (`generate_latest(REGISTRY)`) including `mvp0_http_requests_total`, `mvp0_http_request_duration_seconds`, `mvp0_db_health`, `mvp0_redis_health`, `mvp0_worker_alive`, `mvp0_worker_restarts_total`, `mvp0_kill_switch_active`, `mvp0_outbox_pending_events`, and `mvp0_outbox_dead_letter_events` without high-cardinality labels (`order_id`, `signal_id`, `position_id`).
  - Verified by `tests/integration/test_health_and_readiness.py::test_metrics_endpoint_returns_prometheus_payload`.

### 5.2 Bearer API Key Authentication & Role Separation (`app/core/security.py:1–85`)

- **Constant-Time Token Verification (`app/core/security.py:29–64`):**
  - Extracts `Authorization: Bearer <token>` header.
  - Compares token against `settings.MVP0_ADMIN_API_KEY` and `settings.MVP0_API_KEY` using `secrets.compare_digest` (`lines 50–58`).
  - Missing header, non-Bearer scheme, empty token, or unrecognized key raises `UnauthorizedError` -> HTTP **`401 Unauthorized`** (`code="UNAUTHORIZED"`).
- **Operational vs. Admin Role Enforcement (`app/core/security.py:67–84` & `app/api/v1/system.py`):**
  - `require_operational_role`: Permits both `ApiRole.OPERATIONAL` (`MVP0_API_KEY`) and `ApiRole.ADMIN` (`MVP0_ADMIN_API_KEY`), used on `GET /api/v1/system/health`.
  - `require_admin_role`: Permits only `ApiRole.ADMIN` (`MVP0_ADMIN_API_KEY`); requests with `MVP0_API_KEY` raise `ForbiddenError` -> HTTP **`403 Forbidden`** (`code="FORBIDDEN"`), used on `GET /api/v1/system/status`.
- **Key Rotation & Secret Redaction (`tests/security/test_authentication.py` & `tests/unit/test_logging.py`):**
  - `test_old_key_rejected_after_rotation` verifies that replacing the key in `Settings` immediately invalidates the old token with `401 Unauthorized`.
  - `test_sensitive_fields_are_redacted` verifies that API keys, `Authorization` headers, database URLs, and Redis passwords are automatically replaced with `"[REDACTED]"` in structured JSON logs.
