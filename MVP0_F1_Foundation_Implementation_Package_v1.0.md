# MVP-0 F1 Foundation Implementation Package

**Phase:** F1 — Foundation  
**Version:** 1.0  
**Status:** Ready for Implementation  
**Date:** 2026-10-02  
**Parent Contract:** `MVP0_Implementation_Contract_v1.2_FINAL.md`  
**Master Reference:** `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`  

---

## 0. Document Hierarchy

In case of conflict, the following order applies:

1. `MVP0_Implementation_Contract_v1.2_FINAL.md`
2. This F1 Foundation Implementation Package
3. `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`

The Implementation Contract and this package are binding for coding.  
The Master Package is the source of product intent, architecture rationale, risk principles, and traceability.

---

## 1. Phase Objective

Implement the minimum safe, observable, testable foundation for MVP-0.

F1 does **not** implement trading logic, signal generation, exchange integration, portfolio management, or dashboard business features.

At the end of F1, the repository must provide:

- A runnable FastAPI application.
- PostgreSQL-backed database session and migrations.
- Redis connectivity for transient operational use.
- Structured JSON logging.
- Bearer API key authentication.
- Health and readiness endpoints.
- Prometheus metrics.
- CI pipeline.
- Docker Compose development environment.
- Isolated Paper environment definition.
- Foundation tests and quality gates.

---

## 2. F1 Scope

### 2.1 In Scope

- Python 3.12 project structure.
- FastAPI application skeleton.
- Pydantic Settings configuration.
- Structured logging with `structlog`.
- PostgreSQL 16 connection using SQLAlchemy 2 async engine.
- Alembic migration infrastructure.
- Redis 7 connection.
- Bearer API key authentication.
- `/healthz`, `/readyz`, and `/metrics`.
- Prometheus instrumentation.
- Dockerfile and Docker Compose.
- Paper environment Compose definition.
- CI workflow.
- Unit, integration, security, and foundation tests.
- Repository skeleton for later phases.

### 2.2 Out of Scope

The following must not be implemented in F1:

- Signal generation.
- Order creation or execution.
- Position management.
- Risk Engine business logic.
- Synthetic Stop execution.
- Portfolio management.
- Dashboard pages beyond a minimal shell.
- Real exchange adapter.
- Live trading.
- Direct Mode.
- Real exchange credentials.
- TimescaleDB.
- Vault.
- Go services.
- ML, JEV, Shadow Mode, or A/B Testing.
- Multi-tenancy or Row-Level Security.
- Full PWA offline mode.

---

## 3. Required Repository Structure

Create the following repository structure exactly:

```text
mvp0/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── docker-build.yml
│       └── security-scan.yml
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── dependencies.py
│   │       ├── orders.py
│   │       ├── positions.py
│   │       ├── risk.py
│   │       └── system.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── enums.py
│   │   ├── errors.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── repositories/
│   │   │   └── __init__.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── signal.py
│   │       ├── order.py
│   │       ├── position.py
│   │       ├── trade.py
│   │       ├── risk_rule.py
│   │       ├── synthetic_stop.py
│   │       ├── strategy.py
│   │       ├── exchange_account.py
│   │       ├── audit_log.py
│   │       ├── outbox_event.py
│   │       ├── dead_letter_event.py
│   │       ├── approval_request.py
│   │       └── system_state.py
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── exchange/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── fake.py
│   │   │   ├── paper.py
│   │   │   └── errors.py
│   │   └── notifications/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── telegram.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── orders.py
│   │   ├── signals.py
│   │   ├── positions.py
│   │   ├── risk.py
│   │   └── system.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── risk_engine.py
│   │   ├── state_machine.py
│   │   ├── kill_switch.py
│   │   ├── approval_timeout.py
│   │   ├── synthetic_stop.py
│   │   ├── outbox.py
│   │   └── reconciliation.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── supervisor.py
│   │   ├── approval_timeout.py
│   │   ├── synthetic_stop.py
│   │   ├── outbox_publisher.py
│   │   └── watchdog.py
│   └── main.py
├── dashboard/
│   ├── src/
│   ├── package.json
│   └── tsconfig.json
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── chaos/
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.paper
│   ├── prometheus.yml
│   └── .dockerignore
├── docs/
│   ├── adr/
│   │   └── 0001-mvp0-scope-and-stack.md
│   ├── api/
│   ├── state-machines/
│   └── runbooks/
├── scripts/
│   ├── seed_dev.py
│   ├── migrate.sh
│   └── wait-for-postgres.sh
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.paper.yml
├── Makefile
├── poetry.lock
└── pyproject.toml
```

Empty module files are allowed in F1 only when they represent reserved extension points for later phases. They must not contain business logic.

---

## 4. Configuration Requirements

### 4.1 `.env.example`

```dotenv
# ── Application ──────────────────────────────────────────
ENVIRONMENT=development
LOG_LEVEL=INFO
APP_NAME=mvp0

# ── Database ─────────────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=mvp0
POSTGRES_USER=mvp0
POSTGRES_PASSWORD=change_me_local_only

DATABASE_URL=postgresql+asyncpg://mvp0:change_me_local_only@postgres:5432/mvp0

# ── Redis ────────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=change_me_local_only
REDIS_URL=redis://:change_me_local_only@redis:6379/0

# ── Authentication ───────────────────────────────────────
MVP0_API_KEY=replace_with_32_char_random_hex
MVP0_ADMIN_API_KEY=replace_with_32_char_random_hex

# ── Workers ──────────────────────────────────────────────
UVICORN_WORKERS=1
SUPERVISOR_TASKS=1
APPROVAL_TIMEOUT_INTERVAL_SECONDS=5

# ── Trading Safety ───────────────────────────────────────
LIVE_TRADING=false
PAPER_TRADING=true
PRICE_DRIFT_EXPIRY_THRESHOLD=0.002

# ── Outbox ───────────────────────────────────────────────
OUTBOX_MAX_RETRIES=5
OUTBOX_RETRY_BASE_SECONDS=2

# ── Observability ────────────────────────────────────────
GRAFANA_PASSWORD=change_me_local_only

# ── Paper Environment ────────────────────────────────────
PAPER_DATABASE_URL=postgresql+asyncpg://mvp0paper:change_me@paper_postgres:5432/mvp0_paper
PAPER_REDIS_URL=redis://:change_me@paper_redis:6379/0
```

### 4.2 Startup Validation Rules

The application must fail startup if:

- `UVICORN_WORKERS != 1`
- `SUPERVISOR_TASKS != 1`
- `LIVE_TRADING != false`
- `PAPER_TRADING != true`
- `DATABASE_URL` is missing
- `REDIS_URL` is missing
- `MVP0_API_KEY` is missing or shorter than 32 characters
- `MVP0_ADMIN_API_KEY` is missing or shorter than 32 characters
- `MVP0_API_KEY == MVP0_ADMIN_API_KEY`
- `LOG_LEVEL` is invalid
- `ENVIRONMENT` is not one of `development`, `staging`, `paper`, or `production`
- `PRICE_DRIFT_EXPIRY_THRESHOLD` is outside `0.0001` through `0.01`
- `OUTBOX_MAX_RETRIES` is outside `1` through `10`

---

## 5. Application Runtime Requirements

### 5.1 FastAPI Application

Implement `app/main.py` with:

- FastAPI application instance.
- Lifespan management.
- Structured logging initialization.
- Database engine initialization.
- Redis client initialization.
- Prometheus instrumentation.
- Authentication dependency registration.
- API router registration.
- Health and readiness routes.

### 5.2 Lifespan Startup Sequence

```text
1. Load settings
2. Initialize structured logging
3. Validate trading mode
4. Create async database engine
5. Ping PostgreSQL
6. Ping Redis
7. Initialize Prometheus instrumentation
8. Mark service ready
```

### 5.3 Lifespan Shutdown Sequence

```text
1. Stop accepting new work
2. Cancel background tasks if any
3. Await graceful completion
4. Close Redis connection
5. Dispose database engine
```

### 5.4 Runtime Constraints

- The API must run with exactly one Uvicorn worker.
- PostgreSQL is the only durable source of truth.
- Redis is only for transient state, cache, and locks.
- Redis failure must not corrupt PostgreSQL state.
- Database failure must cause fail-closed behavior.
- All timestamps must be UTC and timezone-aware.
- Financial values must use Decimal, but F1 does not yet implement financial calculations.

---

## 6. Database Requirements

### 6.1 SQLAlchemy Session

Implement `app/db/session.py` with:

- Async SQLAlchemy engine.
- Async session factory.
- Connection pool settings.
- Graceful engine disposal.
- Session dependency for FastAPI.

### 6.2 Migration Requirements

Alembic must be configured for async PostgreSQL.

F1 must include migration infrastructure and the following migration plan:

```text
M001 — foundation_tables
  exchange_accounts
  strategies
  system_states

M002 — signals_and_orders
  signals
  orders

M003 — positions_and_trades
  positions
  trades

M004 — risk_and_synthetic_stops
  risk_rules
  synthetic_stops

M005 — outbox_and_audit
  outbox_events
  dead_letter_events
  audit_logs

M006 — kill_switch_dual_approval
  approval_requests
```

### 6.3 Database Model Rules

- All IDs are UUID v4.
- All timestamps use `TIMESTAMPTZ` and UTC.
- All prices, quantities, fees, and PnL fields use `NUMERIC`.
- Mutable financial records include `version`.
- All tables include `created_at`.
- Mutable tables include `updated_at`.
- Audit logs are append-only.
- No hard delete is allowed for domain and audit records.

### 6.4 F1 Migration Acceptance

- All migrations apply cleanly on an empty PostgreSQL database.
- All migrations roll back cleanly in CI.
- Migrations can be applied again after rollback.
- SQLAlchemy models and database schema are consistent.

---

## 7. Redis Requirements

Implement a Redis client wrapper with:

- Connection from `REDIS_URL`.
- Ping capability.
- Get/set capability.
- Graceful shutdown.
- Clear error taxonomy.

Redis must not be used as the source of truth for:

- Orders
- Positions
- Trades
- Signals
- Approvals
- Audit events
- Outbox events
- Dead-Letter events
- Kill Switch state

---

## 8. Authentication Requirements

### 8.1 Authentication Scheme

Use static Bearer API keys:

```http
Authorization: Bearer <API_KEY>
```

No JWT, OAuth, session cookie, or external identity provider is allowed in F1.

### 8.2 API Key Roles

| Key | Role | Access |
|---|---|---|
| `MVP0_API_KEY` | OPERATIONAL | Normal `/api/v1/*` operations |
| `MVP0_ADMIN_API_KEY` | ADMIN | Admin-only `/api/v1/system/*` operations |

### 8.3 Authorization Rules

- Missing token: `401`
- Invalid token: `401`
- Operational key on admin-only route: `403`
- Admin key on operational route: allowed
- Comparison must use constant-time comparison
- Keys must never be logged
- Keys must never appear in audit payloads, error messages, or stack traces

### 8.4 Public Endpoints

```text
GET /healthz
GET /readyz
GET /metrics
```

These endpoints must not expose secrets, credentials, stack traces, or sensitive financial details.

---

## 9. API Requirements

### 9.1 Required Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | Public | Liveness |
| GET | `/readyz` | Public | Readiness |
| GET | `/metrics` | Public/internal | Prometheus metrics |
| GET | `/api/v1/system/health` | OPERATIONAL | Detailed authenticated health status |

F1 may create route modules for future domains, but they must not expose business endpoints unless explicitly required by this package.

### 9.2 `/healthz`

`/healthz` is liveness-only.

Expected response:

```json
{
  "status": "ok",
  "timestamp": "2026-10-02T08:00:00Z",
  "request_id": "uuid"
}
```

It must not fail because PostgreSQL or Redis is temporarily unavailable.

### 9.3 `/readyz`

`/readyz` checks actual readiness.

It must check:

- PostgreSQL connectivity
- Redis connectivity
- Migration status
- Application configuration validity

Expected response when ready:

```json
{
  "status": "ready",
  "database": "ok",
  "redis": "ok",
  "migrations": "ok",
  "timestamp": "2026-10-02T08:00:00Z",
  "request_id": "uuid"
}
```

Expected response when a dependency is unavailable:

```json
{
  "status": "not_ready",
  "database": "ok",
  "redis": "unavailable",
  "migrations": "ok",
  "timestamp": "2026-10-02T08:00:00Z",
  "request_id": "uuid"
}
```

HTTP status:

- `200` when ready
- `503` when not ready

### 9.4 Error Contract

All API errors must use this structure:

```json
{
  "code": "UNAUTHORIZED",
  "message": "Authentication failed",
  "request_id": "uuid",
  "details": {}
}
```

---

## 10. Logging and Observability Requirements

### 10.1 Structured Logging

Use `structlog` with JSON output.

Every log entry must include:

```text
timestamp
level
message
environment
service
request_id
correlation_id
```

### 10.2 Forbidden Log Data

Never log:

- API keys
- Exchange credentials
- Authorization headers
- Full request bodies containing secrets
- Stack traces containing secrets
- Raw database connection strings

### 10.3 Required Metrics

Implement or reserve the following metrics:

```text
mvp0_http_requests_total
mvp0_http_request_duration_seconds
mvp0_db_health
mvp0_redis_health
mvp0_worker_alive
mvp0_worker_restarts_total
mvp0_orders_total
mvp0_order_state_transitions_total
mvp0_risk_rejections_total
mvp0_approval_timeouts_total
mvp0_price_drift_expiries_total
mvp0_synthetic_stop_failures_total
mvp0_kill_switch_active
mvp0_outbox_pending_events
mvp0_outbox_dead_letter_events
mvp0_outbox_dead_letter_open_events
mvp0_outbox_dead_letter_escalated_events
mvp0_kill_switch_resume_requests_pending
mvp0_kill_switch_resume_requests_approved
```

F1 must expose HTTP metrics and dependency health metrics. Business metrics may be registered but must not be emitted until their owning phase is implemented.

Do not use `order_id`, `signal_id`, or `position_id` as Prometheus labels.

---

## 11. Docker Requirements

### 11.1 Development Compose

`docker-compose.yml` must include:

- PostgreSQL 16
- Redis 7
- API service
- Prometheus
- Grafana
- Named volumes
- Healthchecks
- Single-worker API command

### 11.2 API Command

```bash
./scripts/wait-for-postgres.sh && \
alembic upgrade head && \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 11.3 Dockerfile Requirements

- Base image: `python:3.12-slim`
- Multi-stage build
- Non-root runtime user
- Poetry dependency installation
- No secrets copied into image
- `CMD` uses exactly one Uvicorn worker

### 11.4 Paper Compose

`docker-compose.paper.yml` must define:

- `paper_postgres`
- `paper_redis`
- `paper_api`
- `paper_postgres_data` volume
- `mvp0_paper_network`
- `internal: true`
- Separate credentials
- `LIVE_TRADING=false`
- `PAPER_TRADING=true`
- No host-published PostgreSQL or Redis ports
- No external exchange endpoint
- No real API key

### 11.5 Paper Network Policy

```yaml
networks:
  paper_network:
    name: mvp0_paper_network
    internal: true
```

Paper services must attach only to `mvp0_paper_network`.

---

## 12. CI/CD Requirements

### 12.1 CI Pipeline

`.github/workflows/ci.yml` must run:

```text
1. Checkout
2. Install Poetry
3. Install dependencies from poetry.lock
4. Run ruff check
5. Run ruff format --check
6. Run mypy app
7. Start PostgreSQL and Redis through testcontainers
8. Run alembic upgrade head
9. Run alembic downgrade base
10. Run alembic upgrade head again
11. Run pytest
12. Upload coverage report
```

### 12.2 Docker Build Pipeline

`.github/workflows/docker-build.yml` must:

- Build the API Docker image.
- Verify the image builds successfully.
- Verify the runtime command uses exactly one worker.

### 12.3 Security Pipeline

`.github/workflows/security-scan.yml` must run:

```text
1. Secret scanning
2. Dependency vulnerability scan
3. Docker image vulnerability scan
4. Check for real exchange credential patterns
5. Check for forbidden live-trading code patterns
6. Verify Paper configuration uses LIVE_TRADING=false
7. Verify Paper services use only the Paper network
```

### 12.4 Required CI Gates

- `ruff check` passes
- `ruff format --check` passes
- `mypy --strict` passes
- All tests pass
- Coverage thresholds pass
- Migrations apply and roll back cleanly
- Docker image builds successfully
- No secret is detected
- No live-trading pattern is detected
- Paper isolation checks pass

---

## 13. F1 Test Plan

### 13.1 Configuration Tests

```text
test_required_env_vars_missing_raises_validation_error
test_database_url_constructed_correctly
test_worker_count_locked_to_1
test_invalid_log_level_raises
test_live_trading_must_be_false
test_paper_trading_must_be_true
test_api_keys_must_differ
test_price_drift_threshold_within_allowed_range
test_outbox_retry_settings_within_allowed_range
```

### 13.2 Logging Tests

```text
test_json_output_contains_required_fields
test_request_id_propagated_in_log
test_no_secret_values_in_log_output
```

### 13.3 Database Tests

```text
test_async_session_connects_to_postgres
test_session_rolls_back_on_exception
test_connection_pool_within_limits
```

### 13.4 Migration Tests

```text
test_all_migrations_apply_clean
test_all_migrations_rollback_clean
test_schema_matches_sqlalchemy_models
test_dead_letter_events_table_exists
test_approval_requests_table_exists
```

### 13.5 Health and Readiness Tests

```text
test_healthz_returns_200
test_readyz_returns_200_when_dependencies_up
test_readyz_returns_503_when_db_down
test_readyz_returns_503_when_redis_down
test_healthz_excluded_from_auth
test_readyz_excluded_from_auth
```

### 13.6 Authentication Tests

```text
test_missing_bearer_token_returns_401
test_invalid_token_returns_401
test_valid_operational_key_passes
test_admin_key_required_for_admin_routes
test_operational_key_rejected_on_admin_routes
test_healthz_bypasses_auth
test_readyz_bypasses_auth
test_api_key_not_logged
test_old_key_rejected_after_rotation
```

### 13.7 Redis Tests

```text
test_redis_ping_succeeds
test_redis_set_get_round_trip
test_redis_unavailable_does_not_crash_startup
test_redis_unavailable_does_not_lose_postgres_state
```

### 13.8 Paper Isolation Tests

```text
test_paper_network_is_internal
test_paper_services_only_attach_to_paper_network
test_paper_environment_has_no_live_exchange_endpoint
test_paper_environment_has_no_real_api_key
test_paper_live_trading_flag_is_immutable
test_paper_postgres_and_redis_are_separate
test_paper_api_has_no_outbound_internet_access
```

---

## 14. Quality Gates

| Area | Minimum Requirement |
|---|---|
| Python version | 3.12 |
| Uvicorn workers | Exactly 1 |
| Overall test coverage | At least 80% |
| `app/core/` coverage | At least 90% |
| `app/db/` coverage | At least 90% |
| `ruff check` | Zero errors |
| `ruff format --check` | Zero diffs |
| `mypy --strict` | Zero errors |
| F1 tests | 100% pass |
| Migrations | Apply and roll back cleanly |
| Docker Compose | Starts successfully |
| Paper Compose | Starts successfully and remains isolated |
| Secrets | Zero leaked secrets |
| Live trading code | Zero occurrences |

---

## 15. F1 Deliverables

The implementer must deliver:

1. Complete repository structure.
2. `pyproject.toml` and `poetry.lock`.
3. `.env.example`, `.gitignore`, and `Makefile`.
4. FastAPI application with lifespan.
5. PostgreSQL async session and Alembic setup.
6. Redis client wrapper.
7. Bearer API key authentication.
8. `/healthz`, `/readyz`, and `/metrics`.
9. Structured JSON logging.
10. Prometheus instrumentation.
11. Dockerfile and Docker Compose files.
12. Isolated Paper Compose file.
13. CI, Docker build, and security workflows.
14. All F1 tests.
15. Migration files M001 through M006.
16. ADR-0001.
17. README with local setup and commands.
18. Coverage report.
19. CI run evidence.
20. Docker Compose startup evidence.

---

## 16. F1 Acceptance Criteria

F1 is complete only when all of the following are true:

```text
1. Repository structure matches this package.
2. Application starts with exactly one Uvicorn worker.
3. PostgreSQL and Redis healthchecks pass.
4. Alembic migrations M001-M006 apply and roll back cleanly.
5. /healthz returns 200.
6. /readyz returns 200 when dependencies are healthy.
7. /readyz returns 503 when PostgreSQL or Redis is unavailable.
8. /metrics is exposed for Prometheus.
9. All /api/v1/* routes require authentication.
10. Operational and Admin API keys are separated.
11. Admin-only routes reject operational keys.
12. Logs are structured JSON and contain no secrets.
13. Paper environment is isolated and has no live exchange dependency.
14. CI passes all lint, type, test, migration, Docker, and security gates.
15. Overall coverage is at least 80%.
16. app/core and app/db coverage is at least 90%.
17. No live trading, real exchange adapter, or real exchange credential exists.
```

---

## 17. F1 Exit Gate

F1 exits to F2 only when:

```text
All F1 acceptance criteria are met
AND CI is green
AND Docker Compose starts successfully
AND Paper Compose is isolated
AND migrations apply and roll back cleanly
AND auditor approves the F1 evidence
```

The next phase is:

```text
F2 — Data and Risk Core
```

F2 must not begin before F1 exit approval.

---

## 18. Implementation Notes for Developer

- Do not implement business logic ahead of schedule.
- Do not connect to a real exchange.
- Do not add real API keys to the repository.
- Do not use Redis as a durable store.
- Do not use float for financial values.
- Do not use naive datetime values.
- Do not bypass authentication for `/api/v1/*`.
- Do not expose PostgreSQL or Redis ports in Paper environment.
- Do not add TimescaleDB, Vault, Go, ML, or multi-tenancy.
- Do not start F2 before F1 acceptance.

---

## 19. Final F1 Status Definition

```text
F1 NOT STARTED
F1 IN PROGRESS
F1 READY FOR REVIEW
F1 REQUIRES CHANGES
F1 ACCEPTED — READY FOR F2
```

The implementer must update the repository README or phase status file with the current F1 status before requesting review.
