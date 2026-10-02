# MVP-0 Implementation Contract — v1.2 FINAL

**Status:** Approved for Implementation  
**Date:** 2026-10-02  
**Supersedes:** Revision 1.1  
**Source of Truth:** `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`  
**Auditor Decision:** Approved, conditional on explicit definitions of Dead-Letter persistence/monitoring and Two-Person Approval for Kill Switch Resume. Both conditions are incorporated in this version.  
**Implementation Rule:** No implementation outside this contract may begin without a new ADR and auditor approval.

---

## 0. Final Change Log

| # | Change | Reason |
|---|---|---|
| 1 | Added persistent `dead_letter_events` table | Auditor condition: Dead-Letter must be schema-backed |
| 2 | Added Dead-Letter metrics, alerts, and operational policy | Auditor condition: Dead-Letter must be observable |
| 3 | Added Two-Person Approval workflow for Kill Switch Resume | Auditor condition: Resume requires a technical dual-approval mechanism |
| 4 | Added `approval_requests` table | Supports auditable Two-Person Approval |
| 5 | Added API endpoints for approval request and final resume | Makes dual approval executable |
| 6 | Added tests for Dead-Letter and Two-Person Approval | Ensures both auditor conditions are verifiable |
| 7 | Confirmed Paper-only scope and PostgreSQL-only durable state | Prevents scope drift |

---

## 1. Scope Freeze

MVP-0 is a **single-user, single-strategy, single-exchange abstraction, Spot-only, Paper-only implementation**.

### 1.1 In Scope

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Redis 7
- One application process with `uvicorn --workers 1`
- PostgreSQL as the only durable source of truth
- Redis only for transient operational state, cache, and distributed locks
- Paper Trading only
- Deterministic Risk Engine
- Explicit user approval for every order
- Persistent, independent Kill Switch
- PostgreSQL-backed Synthetic Stop-Loss
- Transactional Outbox with persistent Dead-Letter handling
- Two-Person Approval for Kill Switch Resume
- Audit logging
- Prometheus metrics and JSON structured logs
- React + TypeScript dashboard shell
- Read-only Decision Log API and minimal Visual Audit UI data model

### 1.2 Explicitly Out of Scope

The following are forbidden in MVP-0 code, configuration, dependencies, and CI:

- Live trading
- Real exchange API credentials
- Real exchange order submission
- Direct Mode execution
- Short positions
- Margin, leverage, futures, derivatives, and withdrawal
- Multi-tenancy and Row-Level Security
- ML, JEV, Shadow Mode, and A/B Testing
- Go services
- TimescaleDB
- HashiCorp Vault
- Consul
- Portfolio allocation engine, rebalancing, on-chain data, and sentiment analysis
- Full PWA offline mode
- Offline approval or offline trade execution
- Decision feedback loop, model retraining, and prediction accuracy reporting

### 1.3 Decision Log Boundary

MVP-0 includes only a **minimal, read-only Decision Log**:

- Every signal decision, approval, rejection, expiry, risk rejection, Kill Switch action, and Synthetic Stop action is written to `audit_logs`
- The dashboard can display the latest decision history for a signal
- The API exposes read-only decision history
- No editable Decision Journal, user-written commentary, feedback loop, ML evaluation, or prediction-accuracy reporting is allowed

### 1.4 PWA Boundary

MVP-0 includes only a responsive web dashboard:

- Static assets may be cached
- Read-only dashboard data may use stale-while-revalidate
- Trade, approval, authentication, and Kill Switch endpoints are network-only
- No offline approval, offline order creation, or queued trade action is allowed
- Full PWA offline strategy is Post-MVP

### 1.5 Trading Mode Rule

```text
LIVE_TRADING=false
PAPER_TRADING=true
```

These values are immutable after startup. Paper mode must use a separate Docker network, separate PostgreSQL instance, separate Redis instance, and no external exchange endpoint.

Any code path that can submit a real order, use a real exchange credential, or connect to a live exchange endpoint is prohibited in MVP-0.

---

## 2. Traceability Matrix

| Contract Section | Master Package v4.3 Section | Coverage Purpose | G0 Blocker? |
|---|---|---|---|
| §1 Scope Freeze | §1.3; §2.1; §12.3 | Defines active and forbidden scope | Yes |
| §3 ADR-0001 | §2.1; §12.3; Appendix G0 Checklist | Locks stack and constraints | Yes |
| §4 Dependencies | §2.1; §9.1 | Reproducible dependency set | Yes |
| §5 Configuration | §3.3; §12.3 | Safe runtime configuration | Yes |
| §6 Docker Runtime | §12.3; §13.7 | Startup, migration, runtime | Yes |
| §7 Paper Environment | §12.3 | Isolated Paper environment | Yes |
| §8 Database Contract | Appendix Database Contract; §13 | Durable schema and financial rules | Yes |
| §9 State Machine | §7.1; v3.2 State Machine Closure | Order lifecycle and protection failure | Yes |
| §10 Risk Engine | §5.1; §11 | Sizing and hard caps | Yes |
| §11 Approval Timeout | §13.6 | Dynamic timeout and price drift | Yes |
| §12 Synthetic Stop | §5.2; Appendix Synthetic Stop Contract | Persistent, idempotent stop execution | Yes |
| §13 Kill Switch | §11.3; §11.4; v4.3 Kill Switch Contract | Persistent Kill Switch and recovery | Yes |
| §14 Authentication | v4.3 Authentication Contract; §13.5 | API key access and leak response | Yes |
| §15 Runbooks | §13.4; §13.5; §13.7 | Operational recovery | Yes |
| §16 API Contract | Appendix API Contract; v4.3 API Contract | Endpoints, auth, errors, idempotency | Yes |
| §17 Decision Log API | §21.5; §4.3 | Minimal audit/decision visibility | No |
| §18 Observability | §2.1; §13.1 | Logs, metrics, dashboards | Yes |
| §19 Worker Lifecycle | v4.3 Worker Lifecycle Contract | Startup, shutdown, recovery | Yes |
| §20 Outbox | Appendix Event Model; Appendix Outbox Contract | Reliable event delivery and Dead-Letter | Yes |
| §21 Test Plan | §9.1; §9.4 | F1–F3 validation | Yes |
| §22 CI/CD | §9.3; §12 | Automated quality gates | Yes |
| §23 Security Controls | §3.3; §13.5; §14 | Secrets, audit, data protection | Yes |
| §24 G0 Exit Criteria | §9.2; Appendix G0 Checklist | Measurable acceptance criteria | Yes |
| §25 Auditor Decision Record | v4.3 G0 Closure | Final approved decisions | Yes |

---

## 3. ADR-0001 — MVP-0 Scope and Stack

```markdown
# ADR-0001: MVP-0 Scope, Stack, and Architectural Constraints

## Status

Accepted for MVP-0 implementation.

## Date

2026-10-02

## Decision

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| API | FastAPI |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Primary database | PostgreSQL 16 |
| Cache / locks | Redis 7 |
| Packaging | Poetry + pyproject.toml |
| Containers | Docker Compose |
| Frontend | React + TypeScript |
| Observability | Prometheus, Grafana, structlog JSON |

## Hard Constraints

1. The API process MUST run with `--workers 1`.
2. PostgreSQL is the only durable source of truth.
3. Redis MUST NOT be the source of truth for orders, positions, stops, approvals, audit events, Dead-Letter events, or Kill Switch state.
4. Redis loss must not cause data loss.
5. MVP-0 MUST NOT contain live trading code, real exchange credentials, or real exchange order submission.
6. Paper Trading MUST use an isolated Docker network, separate PostgreSQL, and separate Redis.
7. TimescaleDB, Vault, Go, ML, JEV, RLS, and multi-tenancy are Post-MVP.
8. Every financial amount, price, quantity, fee, and PnL MUST use Decimal.
9. Every timestamp MUST be UTC and timezone-aware.
10. Any state transition affecting an order, position, stop, approval, Dead-Letter event, or Kill Switch MUST be transactional and auditable.
11. The MVP-0 dashboard MUST NOT allow offline trade or approval actions.
12. The MVP-0 Decision Log is read-only and audit-backed.
13. Kill Switch Resume MUST require Two-Person Approval.
```

---

## 4. Dependency and Quality Contract

```toml
[tool.poetry]
name = "mvp0"
version = "0.1.0"
description = "Crypto risk management system — MVP-0"
authors = []
readme = "README.md"
packages = [{ include = "app" }]

[tool.poetry.dependencies]
python = ">=3.12,<3.13"
fastapi = "^0.115.5"
uvicorn = { extras = ["standard"], version = "^0.32.1" }
sqlalchemy = { extras = ["asyncio"], version = "^2.0.36" }
alembic = "^1.14.0"
asyncpg = "^0.30.0"
redis = { extras = ["hiredis"], version = "^5.2.0" }
pydantic = "^2.9.2"
pydantic-settings = "^2.6.1"
structlog = "^24.4.0"
prometheus-fastapi-instrumentator = "^7.0.0"
httpx = "^0.27.2"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.3"
pytest-asyncio = "^0.24.0"
pytest-cov = "^6.0.0"
pytest-mock = "^3.14.0"
anyio = { extras = ["trio"], version = "^4.6.0" }
ruff = "^0.8.1"
mypy = "^1.13.0"
testcontainers = "^4.9.0"
factory-boy = "^3.3.1"
freezegun = "^1.5.1"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "ANN"]
ignore = ["ANN101", "ANN102"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80"
```

| Area | Minimum Coverage |
|---|---:|
| Whole `app/` | 80% |
| `app/services/risk_engine.py` | 90% |
| `app/services/state_machine.py` | 90% |
| `app/services/kill_switch.py` | 90% |
| `app/core/security.py` | 90% |
| `app/services/synthetic_stop.py` | 90% |
| `app/services/outbox.py` | 90% |

---

## 5. Configuration Contract

### 5.1 `.env.example`

```dotenv
ENVIRONMENT=development
LOG_LEVEL=INFO
APP_NAME=mvp0

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=mvp0
POSTGRES_USER=mvp0
POSTGRES_PASSWORD=change_me_local_only
DATABASE_URL=postgresql+asyncpg://mvp0:change_me_local_only@postgres:5432/mvp0

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=change_me_local_only
REDIS_URL=redis://:change_me_local_only@redis:6379/0

MVP0_API_KEY=replace_with_32_char_random_hex
MVP0_ADMIN_API_KEY=replace_with_32_char_random_hex

UVICORN_WORKERS=1
SUPERVISOR_TASKS=1
APPROVAL_TIMEOUT_INTERVAL_SECONDS=5

LIVE_TRADING=false
PAPER_TRADING=true
PRICE_DRIFT_EXPIRY_THRESHOLD=0.002

OUTBOX_MAX_RETRIES=5
OUTBOX_RETRY_BASE_SECONDS=2

GRAFANA_PASSWORD=change_me_local_only

PAPER_DATABASE_URL=postgresql+asyncpg://mvp0paper:change_me@paper_postgres:5432/mvp0_paper
PAPER_REDIS_URL=redis://:change_me@paper_redis:6379/0
```

### 5.2 Startup Validation Rules

Application startup must fail if:

- `UVICORN_WORKERS != 1`
- `SUPERVISOR_TASKS != 1`
- `LIVE_TRADING != false`
- `PAPER_TRADING != true`
- Database URL or Redis URL is missing
- API keys are missing, shorter than 32 characters, or identical
- Log level is invalid
- Environment is not `development`, `staging`, `paper`, or `production`
- `PRICE_DRIFT_EXPIRY_THRESHOLD` is outside `0.0001` through `0.01`
- `OUTBOX_MAX_RETRIES` is outside `1` through `10`

---

## 6. Docker and Runtime Contract

### 6.1 Runtime Rules

- API container runs as a non-root user
- Migrations run before API startup
- `--workers 1` is enforced in Dockerfile and Compose
- PostgreSQL and Redis are not exposed to host in staging or production
- Docker healthcheck uses `/readyz`, not `/healthz`
- Secrets are never copied into images

### 6.2 API Startup Command

```bash
./scripts/wait-for-postgres.sh && \
alembic upgrade head && \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 6.3 Required Dockerfile Properties

```text
Base image: python:3.12-slim
Runtime user: non-root user with UID 10001
Entrypoint: uvicorn app.main:app
Worker count: exactly 1
```

---

## 7. Paper Environment Contract

### 7.1 Mandatory Network Isolation Policy

1. `paper_api`, `paper_postgres`, and `paper_redis` attach only to `mvp0_paper_network`
2. `mvp0_paper_network` must use `internal: true`
3. Paper services must not attach to `mvp0_network`, `live_network`, or an external bridge network
4. Paper PostgreSQL and Redis must not publish ports to host
5. Paper API must not have outbound internet access
6. Paper environment must not contain real exchange credentials, secrets, or endpoints
7. `LIVE_TRADING=false` and `PAPER_TRADING=true` are immutable at startup
8. Only `PaperTradingAdapter` and `FakeExchangeAdapter` are permitted execution adapters
9. CI fails if Paper services attach to a non-Paper network
10. CI fails if Paper configuration contains live exchange hostname, adapter, or credential pattern

### 7.2 Mandatory Compose Network

```yaml
networks:
  paper_network:
    name: mvp0_paper_network
    internal: true
```

### 7.3 Isolation Acceptance Tests

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

## 8. Database Contract

### 8.1 General Rules

- IDs: UUID v4
- Timestamps: `TIMESTAMPTZ`, UTC, timezone-aware
- Financial values: `NUMERIC`, mapped to `Decimal`; never `float`
- Mutable financial records: optimistic-locking `version`
- No hard delete for orders, positions, trades, stops, approvals, Dead-Letter events, or audit logs
- Audit logs: append-only

### 8.2 Migration Plan

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

### 8.3 Required Table Contracts

#### `signals`

```text
id UUID PK
signal_id VARCHAR(64) UNIQUE NOT NULL
strategy_id UUID FK NOT NULL
symbol VARCHAR(32) NOT NULL
timeframe VARCHAR(8) NOT NULL
direction VARCHAR(8) NOT NULL
reference_price NUMERIC(30,12) NOT NULL
entry_range_min NUMERIC(30,12) NOT NULL
entry_range_max NUMERIC(30,12) NOT NULL
stop_loss_price NUMERIC(30,12) NOT NULL
take_profit_price NUMERIC(30,12) NULL
risk_reward_ratio NUMERIC(12,6) NOT NULL
data_quality_score NUMERIC(6,4) NOT NULL
confidence_score NUMERIC(6,4) NOT NULL
rule_version VARCHAR(32) NOT NULL
approval_status VARCHAR(32) NOT NULL
approval_expires_at TIMESTAMPTZ NOT NULL
explanation_json JSONB NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

Constraints:

```text
symbol IN ('BTC/USDT', 'ETH/USDT', 'BNB/USDT')
direction = 'LONG'
approval_status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXPIRED', 'PRICE_DRIFT_EXPIRED')
reference_price > 0
entry_range_min <= entry_range_max
```

#### `orders`

```text
id UUID PK
client_order_id VARCHAR(128) UNIQUE NOT NULL
signal_id UUID FK NULL
strategy_id UUID FK NOT NULL
exchange_account_id UUID FK NOT NULL
symbol VARCHAR(32) NOT NULL
side VARCHAR(8) NOT NULL
order_type VARCHAR(16) NOT NULL
quantity NUMERIC(30,12) NOT NULL
limit_price NUMERIC(30,12) NULL
filled_quantity NUMERIC(30,12) NOT NULL DEFAULT 0
average_fill_price NUMERIC(30,12) NULL
status VARCHAR(32) NOT NULL
state_machine_state VARCHAR(32) NOT NULL
risk_decision VARCHAR(32) NOT NULL
risk_reason_codes JSONB NOT NULL DEFAULT '[]'
idempotency_key VARCHAR(128) UNIQUE NOT NULL
expires_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

#### `positions`

```text
id UUID PK
order_id UUID FK NOT NULL
strategy_id UUID FK NOT NULL
exchange_account_id UUID FK NOT NULL
symbol VARCHAR(32) NOT NULL
side VARCHAR(8) NOT NULL
size NUMERIC(30,12) NOT NULL
entry_price NUMERIC(30,12) NOT NULL
mark_price NUMERIC(30,12) NULL
unrealized_pnl NUMERIC(30,12) NOT NULL DEFAULT 0
realized_pnl NUMERIC(30,12) NOT NULL DEFAULT 0
status VARCHAR(32) NOT NULL
stop_price NUMERIC(30,12) NULL
take_profit_state VARCHAR(32) NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

#### `trades`

```text
id UUID PK
order_id UUID FK NOT NULL
position_id UUID FK NULL
exchange_trade_id VARCHAR(128) UNIQUE NULL
fill_price NUMERIC(30,12) NOT NULL
fill_quantity NUMERIC(30,12) NOT NULL
fee NUMERIC(30,12) NOT NULL
executed_at TIMESTAMPTZ NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

#### `synthetic_stops`

```text
id UUID PK
position_id UUID FK NOT NULL
symbol VARCHAR(32) NOT NULL
side VARCHAR(8) NOT NULL
quantity NUMERIC(30,12) NOT NULL
stop_price NUMERIC(30,12) NOT NULL
timeframe VARCHAR(8) NOT NULL
status VARCHAR(32) NOT NULL
idempotency_key VARCHAR(128) UNIQUE NOT NULL
execution_order_id UUID NULL
attempt_count INTEGER NOT NULL DEFAULT 0
last_error TEXT NULL
last_checked_at TIMESTAMPTZ NULL
triggered_at TIMESTAMPTZ NULL
executed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

Required statuses:

```text
ARMED
TRIGGERED
SUBMITTING
SUBMITTED
EXECUTED
FAILED
MANUAL_REVIEW
CANCELLED
```

#### `outbox_events`

```text
id UUID PK
event_id UUID UNIQUE NOT NULL
event_type VARCHAR(128) NOT NULL
event_version INTEGER NOT NULL
aggregate_type VARCHAR(64) NOT NULL
aggregate_id UUID NOT NULL
payload_json JSONB NOT NULL
status VARCHAR(32) NOT NULL
retry_count INTEGER NOT NULL DEFAULT 0
next_retry_at TIMESTAMPTZ NULL
published_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Allowed statuses:

```text
PENDING
PROCESSING
PUBLISHED
FAILED
DEAD_LETTER
```

#### `dead_letter_events`

```text
id UUID PK
original_outbox_event_id UUID FK UNIQUE NOT NULL
event_id UUID UNIQUE NOT NULL
event_type VARCHAR(128) NOT NULL
event_version INTEGER NOT NULL
aggregate_type VARCHAR(64) NOT NULL
aggregate_id UUID NOT NULL
payload_json JSONB NOT NULL
failure_reason TEXT NOT NULL
failure_class VARCHAR(64) NOT NULL
retry_count INTEGER NOT NULL
first_failed_at TIMESTAMPTZ NOT NULL
dead_lettered_at TIMESTAMPTZ NOT NULL
resolution_status VARCHAR(32) NOT NULL DEFAULT 'OPEN'
resolved_at TIMESTAMPTZ NULL
resolved_by UUID NULL
resolution_note TEXT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Constraints:

```text
failure_class IN ('TRANSIENT', 'PERMANENT', 'SCHEMA', 'CONSUMER', 'UNKNOWN')
resolution_status IN ('OPEN', 'ACKNOWLEDGED', 'REPLAYED', 'DISCARDED', 'ESCALATED')
```

Rules:

- Dead-Letter records are never deleted
- A Dead-Letter event must remain linked to its original Outbox event
- Replay is audited and requires Admin approval
- Replay creates a new Outbox event or safely resets the original event through an audited administrative action

#### `audit_logs`

```text
id UUID PK
request_id UUID NULL
correlation_id UUID NULL
actor_id UUID NULL
actor_key_id VARCHAR(64) NULL
actor_role VARCHAR(32) NOT NULL
action VARCHAR(128) NOT NULL
target_type VARCHAR(64) NOT NULL
target_id UUID NULL
before_json JSONB NULL
after_json JSONB NULL
reason_code VARCHAR(128) NULL
detail_json JSONB NULL
ip_address INET NULL
user_agent TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

#### `approval_requests`

```text
id UUID PK
request_type VARCHAR(64) NOT NULL
target_type VARCHAR(64) NOT NULL
target_id UUID NOT NULL
status VARCHAR(32) NOT NULL
requested_by UUID NOT NULL
requested_by_role VARCHAR(32) NOT NULL
first_approver_id UUID NULL
first_approver_role VARCHAR(32) NULL
first_approved_at TIMESTAMPTZ NULL
second_approver_id UUID NULL
second_approver_role VARCHAR(32) NULL
second_approved_at TIMESTAMPTZ NULL
reason TEXT NOT NULL
expires_at TIMESTAMPTZ NOT NULL
completed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

Constraints:

```text
request_type = 'KILL_SWITCH_RESUME'
status IN ('PENDING_FIRST_APPROVAL', 'PENDING_SECOND_APPROVAL', 'APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED')
requested_by, first_approver_id, and second_approver_id are distinct actors
same actor cannot provide both approvals
at least one approval is ADMIN
at least one approval is OPERATOR
```

---

## 9. State Machine Contract

### 9.1 Signal Approval State Machine

```text
PENDING_APPROVAL
  ├── APPROVED
  ├── REJECTED
  ├── EXPIRED
  └── PRICE_DRIFT_EXPIRED
```

Rules:

- Transitions use `SELECT ... FOR UPDATE`
- Expired or price-drift-expired signals cannot be approved
- Every transition creates an audit record

### 9.2 Order State Machine

```text
SIGNAL_CREATED
  → PENDING_APPROVAL
  → APPROVED
  → PRE_TRADE_VALIDATION
  → SUBMITTED
  → PARTIALLY_FILLED
  → FILLED
  → PROTECTED
  → CLOSED

Alternative terminal states:
REJECTED
EXPIRED
CANCELLED
FAILED
PROTECTION_FAILED
MANUAL_REVIEW
```

### 9.3 Protection Failure Retry

```text
Attempt 1: t=0s
Attempt 2: t=5s
Attempt 3: t=15s
```

Rules:

- Retry is idempotent
- Duplicate protection order is prohibited
- Every attempt is audited
- After third failure, transition to `CANCEL_POSITION` or `MANUAL_REVIEW` according to safety policy

### 9.4 Partial Fill Rule

```text
PARTIALLY_FILLED → FILLED_PARTIAL → CANCEL_REMAINDER
```

The filled portion must be protected immediately. The remainder must be cancelled after 60 seconds.

---

## 10. Risk Engine Contract

### 10.1 Allowed Universe

```text
BTC/USDT
ETH/USDT
BNB/USDT
```

Only Spot, LONG, leverage-free trades are allowed.

### 10.2 Hard Caps

| Control | MVP-0 Limit |
|---|---:|
| Max risk per trade | 0.50% |
| Max daily loss | 2.00% |
| Max weekly loss | 5.00% |
| Max asset weight | 15.00% |
| Max total exposure | 70.00% |
| Min cash reserve | 15.00% |
| Soft drawdown | 8.00% |
| Hard drawdown | 12.00% |
| Kill Switch drawdown | 15.00% |

### 10.3 Position Sizing Formula

```text
risk_amount = equity * risk_fraction
stop_loss_distance = ATR_14 * ATR_multiplier
round_trip_cost_per_unit = entry_price * (fee_round_trip_pct + slippage_pct)
effective_loss_per_unit = stop_loss_distance + round_trip_cost_per_unit
quantity_by_risk = risk_amount / effective_loss_per_unit
notional_by_risk = quantity_by_risk * entry_price

final_notional = min(
    notional_by_risk,
    equity * max_asset_weight,
    portfolio_value * max_total_exposure,
    daily_volume_24h * 0.01,
    user_max_notional
)

final_quantity = floor_to_step(final_notional / entry_price, exchange_step_size)
```

### 10.4 Fail-Closed Rules

Risk Engine returns `REJECT` if any required safety input is missing or invalid, including:

- Missing, zero, or negative equity
- Missing, zero, or negative ATR
- Missing, zero, or negative entry price
- Insufficient volatility data
- Unavailable order-book depth
- Stale market data
- Insufficient liquidity
- Disallowed symbol or non-LONG direction
- Exceeded risk limits
- Active Kill Switch
- Invalid IPS

---

## 11. Approval Timeout and Price Drift Contract

### 11.1 Dynamic Timeout

| Signal Timeframe | Default Timeout |
|---|---:|
| 1H | 5 minutes |
| 4H | 30 minutes |
| 1D | 4 hours |

### 11.2 IPS Override

```text
effective_timeout = min(dynamic_timeout, ips_timeout)
```

`approval_timeout_minutes` is optional, may only reduce the dynamic timeout, and must be between 3 and 240 minutes.

### 11.3 Price Drift Expiry Threshold

```text
price_drift = abs(current_price - signal.reference_price) / signal.reference_price

if price_drift > PRICE_DRIFT_EXPIRY_THRESHOLD:
    signal.approval_status = PRICE_DRIFT_EXPIRED
```

```text
PRICE_DRIFT_EXPIRY_THRESHOLD = 0.002
```

This is a 0.2% absolute price drift from `signal.reference_price`.

### 11.4 Calculation Rules

- Uses `Decimal`
- `current_price` is latest valid ticker price
- `reference_price` is immutable signal creation price
- Both values must be positive
- Evaluated every 5 seconds by approval-timeout worker
- May expire before normal timeout
- Audit action: `SIGNAL_PRICE_DRIFT_EXPIRED`
- Audit payload includes reference price, current price, price drift, and threshold; no secrets

---

## 12. Synthetic Stop-Loss Contract

### 12.1 State Machine

```text
ARMED
  → TRIGGERED
  → SUBMITTING
  → SUBMITTED
  → EXECUTED
  → RECONCILED

Failure paths:
TRIGGERED → FAILED
SUBMITTING → FAILED
FAILED → MANUAL_REVIEW
FAILED → CANCELLED
```

### 12.2 Execution Rules

- Stops load from PostgreSQL on worker startup
- Only active positions with `ARMED` stops are polled
- Trigger condition for LONG: `current_price <= stop_price`
- Trigger occurs exactly once using transactional compare-and-set
- Unique idempotency key is created before submission
- Failed submission follows `0s`, `5s`, `15s` retry schedule
- Final failure becomes `MANUAL_REVIEW`
- Restart must not create duplicate stop order

### 12.3 Polling Intervals

| Timeframe | Poll Interval |
|---|---:|
| 1H | 30 seconds |
| 4H | 60 seconds |
| 1D | 300 seconds |

---

## 13. Kill Switch and Two-Person Approval Contract

### 13.1 Kill Switch Persistence

Kill Switch state is stored in PostgreSQL `system_states` and survives restart.

```text
is_active
activated_at
activated_by
activation_reason
activation_source
resume_status
resumed_at
resumed_by
resume_reason
```

### 13.2 Kill Switch Activation Endpoint

```http
POST /api/v1/system/emergency-stop
Authorization: Bearer <MVP0_ADMIN_API_KEY>
Content-Type: application/json

{
  "reason": "manual emergency stop"
}
```

### 13.3 Activation Procedure

```text
1. Freeze new order creation
2. Cancel open orders if connector is available
3. Reconcile partially filled orders
4. Apply position policy
5. Disable active stop monitoring safely
6. Create audit record
7. Notify operator
```

If any step cannot be completed due to connector failure, system enters `MANUAL_REVIEW`.

### 13.4 Two-Person Approval Workflow for Resume

```text
1. Admin creates Kill Switch Resume request.
2. System creates approval_requests record in PENDING_FIRST_APPROVAL.
3. First approver approves:
   - Admin or Operator
   - Not requester
4. System moves request to PENDING_SECOND_APPROVAL.
5. Second approver approves:
   - Complementary role
   - Not requester or first approver
   - One approver must be ADMIN
   - One approver must be OPERATOR
6. System marks request APPROVED.
7. System resumes with reduced exposure.
8. System records audit events for request, approvals, resume, and final state.
```

### 13.5 Resume Rules

- One approval is insufficient
- Requester cannot approve own request
- Same actor cannot approve twice
- Request expires after 24 hours
- Expired request cannot be approved
- Resume requires root-cause documentation and completed reconciliation
- Resume uses reduced exposure

### 13.6 Resume API Contract

Create request:

```http
POST /api/v1/system/emergency-stop/resume-requests
Authorization: Bearer <MVP0_ADMIN_API_KEY>
Content-Type: application/json

{
  "reason": "Root cause resolved and reconciliation completed"
}
```

Provide approval:

```http
POST /api/v1/system/emergency-stop/resume-requests/{id}/approve
Authorization: Bearer <MVP0_ADMIN_API_KEY or MVP0_API_KEY>
```

Reject request:

```http
POST /api/v1/system/emergency-stop/resume-requests/{id}/reject
Authorization: Bearer <MVP0_ADMIN_API_KEY or MVP0_API_KEY>
```

---

## 14. Authentication Contract

### 14.1 Scheme

```http
Authorization: Bearer <API_KEY>
```

No JWT, OAuth, session cookie, or third-party identity provider is used.

### 14.2 Key Roles

| Key | Role | Access |
|---|---|---|
| `MVP0_API_KEY` | OPERATIONAL | Normal `/api/v1/*` operations |
| `MVP0_ADMIN_API_KEY` | ADMIN | Admin-only `/api/v1/system/*` operations |

### 14.3 Validation Rules

- Missing or invalid token: `401`
- Operational key on admin-only route: `403`
- Admin key on operational route: allowed
- Constant-time comparison is mandatory
- Keys must not appear in logs, audit payloads, errors, or stack traces

### 14.4 Public Endpoints

```text
GET /healthz
GET /readyz
GET /metrics
```

### 14.5 Key Rotation

- Manual rotation through environment-secret replacement and redeployment
- Keys are at least 32 characters and must differ
- Old key becomes invalid after restart with new secret
- Rotation creates audit event without key value
- Automated rotation is Post-MVP

### 14.6 API Key Leak Response

```text
1. Rotate affected key immediately.
2. Restart API with new secret configuration.
3. Verify old key returns 401.
4. Review audit log.
5. Activate Kill Switch if unauthorized order activity exists.
6. Reconcile orders, fills, positions, and stops.
7. Record incident and recovery timing.
8. Never log or persist leaked key value.
```

---

## 15. Operational Runbook — Kill Switch Active

```markdown
# Runbook: Kill Switch Activated

## Symptoms

- Kill Switch state is active
- New orders are rejected
- Dashboard or alert indicates emergency state

## Immediate Actions

1. Confirm activation source and reason.
2. Check active orders, partial fills, positions, and Synthetic Stops.
3. Confirm new orders are blocked.
4. Cancel open orders if connector is available.
5. Mark affected items as MANUAL_REVIEW if connector is unavailable.
6. Do not resume before root-cause analysis.

## Escalation

- Operator verifies state and collects evidence.
- Admin approves recovery action.
- Admin + Operator approval is required for resume.

## Resume Criteria

- Root cause documented.
- Orders, fills, positions, and stops reconciled.
- No unresolved critical discrepancy.
- Risk limits are safe.
- Two-Person Approval completed.
- Reduced exposure applied.

## Post-Incident

- Record activation, source, reason, affected entities, and recovery time.
- Add tests or monitoring improvement for identified gaps.
```

---

## 16. API Contract

### 16.1 Common Rules

- Base path: `/api/v1`
- JSON content type
- UTC ISO-8601 timestamps
- Monetary/quantity fields serialized as Decimal strings
- Mutating endpoints require `Idempotency-Key`
- Every response includes `request_id`
- Stable machine-readable error code

### 16.2 Error Format

```json
{
  "code": "INVALID_STATE",
  "message": "Invalid transition",
  "request_id": "uuid",
  "details": {}
}
```

### 16.3 Endpoint Matrix

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | Public | Liveness |
| GET | `/readyz` | Public | Readiness |
| GET | `/metrics` | Public/internal | Prometheus metrics |
| GET | `/api/v1/signals` | OPERATIONAL | List signals |
| POST | `/api/v1/signals/{id}/approve` | OPERATIONAL | Approve signal |
| POST | `/api/v1/signals/{id}/reject` | OPERATIONAL | Reject signal |
| GET | `/api/v1/orders` | OPERATIONAL | List orders |
| GET | `/api/v1/orders/{id}` | OPERATIONAL | Get order |
| GET | `/api/v1/positions` | OPERATIONAL | List positions |
| GET | `/api/v1/risk/status` | OPERATIONAL | Risk status |
| GET | `/api/v1/decisions` | OPERATIONAL | Read-only decision history |
| GET | `/api/v1/decisions/{signal_id}` | OPERATIONAL | Decision detail |
| POST | `/api/v1/system/emergency-stop` | ADMIN | Activate Kill Switch |
| GET | `/api/v1/system/emergency-stop` | ADMIN | Get Kill Switch state |
| POST | `/api/v1/system/emergency-stop/resume-requests` | ADMIN | Create resume request |
| POST | `/api/v1/system/emergency-stop/resume-requests/{id}/approve` | ADMIN or OPERATIONAL | Provide one approval |
| POST | `/api/v1/system/emergency-stop/resume-requests/{id}/reject` | ADMIN or OPERATIONAL | Reject resume request |
| GET | `/api/v1/system/emergency-stop/resume-requests/{id}` | ADMIN or OPERATIONAL | Get approval status |

### 16.4 Decision Log Boundary

Decision Log is read-only and must not support create, edit, delete, commentary, feedback, model evaluation, or offline writes.

---

## 17. Worker Lifecycle Contract

### 17.1 Startup Sequence

```text
1. Load settings
2. Initialize structured logging
3. Validate trading mode
4. Create database engine
5. Ping PostgreSQL
6. Ping Redis
7. Recover active Synthetic Stops
8. Reconcile open positions
9. Start supervisor
10. Start approval timeout worker
11. Start Synthetic Stop worker
12. Start Outbox publisher
13. Mark service ready
```

### 17.2 Shutdown Sequence

```text
1. Stop accepting new work
2. Cancel worker tasks
3. Await graceful completion
4. Persist incomplete work state
5. Close Redis connection
6. Dispose database engine
```

### 17.3 Failure Rules

- Supervisor detects worker crash
- Exception is logged with request/correlation ID
- Restart does not duplicate work
- Redis failure cannot corrupt PostgreSQL state
- Database failure is fail-closed

---

## 18. Observability Contract

### 18.1 Required Log Fields

```text
timestamp
level
message
environment
service
request_id
correlation_id
```

### 18.2 Forbidden Log Data

```text
API keys
exchange credentials
Authorization headers
secret-bearing request bodies
raw database connection strings
secret-bearing stack traces
```

### 18.3 Required Metrics

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

Do not use `order_id`, `signal_id`, or `position_id` as Prometheus labels.

### 18.4 Dead-Letter Alert Policy

| Condition | Alert Severity | Required Action |
|---|---|---|
| Any new Dead-Letter event | WARNING | Notify operator |
| Open Dead-Letter events > 0 for 15 minutes | HIGH | Operator investigation |
| Open Dead-Letter events > 0 for 60 minutes | CRITICAL | Admin escalation |
| Dead-Letter affects order, position, stop, or Kill Switch | CRITICAL | Immediate investigation and possible Kill Switch review |

---

## 19. Outbox and Dead-Letter Contract

### 19.1 Event Types

```text
SIGNAL_CREATED
SIGNAL_APPROVED
SIGNAL_REJECTED
SIGNAL_EXPIRED
SIGNAL_PRICE_DRIFT_EXPIRED
ORDER_CREATED
ORDER_SUBMITTED
ORDER_FILLED
POSITION_CREATED
STOP_REGISTERED
STOP_TRIGGERED
STOP_EXECUTED
POSITION_CLOSED
RECONCILIATION_FAILED
KILL_SWITCH_ACTIVATED
KILL_SWITCH_RESUMED
```

### 19.2 Delivery Rules

- Event and domain change are written in same transaction
- Publisher claims pending events atomically
- Retry uses exponential backoff
- After `OUTBOX_MAX_RETRIES`, event moves to `dead_letter_events`
- Original event status becomes `DEAD_LETTER`
- Dead-Letter record persists and is observable
- Consumers are idempotent
- Duplicate delivery is tolerated; duplicate processing is forbidden

### 19.3 Dead-Letter Handling

```text
1. Publisher attempt fails.
2. Increment retry count.
3. If retry_count < OUTBOX_MAX_RETRIES, schedule next_retry_at using exponential backoff.
4. If retry_count >= OUTBOX_MAX_RETRIES:
   - create dead_letter_events row
   - set original outbox event to DEAD_LETTER
   - increment Dead-Letter metric
   - notify operator
5. Operator investigates.
6. Resolution is REPLAYED, DISCARDED, or ESCALATED.
7. Every resolution is audited.
```

### 19.4 Dead-Letter Replay

Replay requires:

- Resolved cause
- Valid payload
- Idempotent consumer support
- Admin approval
- Audit record
- New Outbox event or audited safe reset of original event

---

## 20. Test Plan — F1 Foundation

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

test_json_output_contains_required_fields
test_request_id_propagated_in_log
test_no_secret_values_in_log_output

test_async_session_connects_to_postgres
test_session_rolls_back_on_exception
test_connection_pool_within_limits

test_all_migrations_apply_clean
test_all_migrations_rollback_clean
test_schema_matches_sqlalchemy_models
test_dead_letter_events_table_exists
test_approval_requests_table_exists

test_healthz_returns_200
test_readyz_returns_200_when_dependencies_up
test_readyz_returns_503_when_db_down
test_readyz_returns_503_when_redis_down
test_healthz_excluded_from_auth
test_readyz_excluded_from_auth

test_missing_bearer_token_returns_401
test_invalid_token_returns_401
test_valid_operational_key_passes
test_admin_key_required_for_admin_routes
test_operational_key_rejected_on_admin_routes
test_healthz_bypasses_auth
test_api_key_not_logged
test_old_key_rejected_after_rotation

test_redis_ping_succeeds
test_redis_set_get_round_trip
test_redis_unavailable_does_not_crash_startup
test_redis_unavailable_does_not_lose_postgres_state
```

---

## 21. Test Plan — F2 Core Safety and F3 Integration/Chaos

### 21.1 F2 — Kill Switch and Resume Approval

```text
test_kill_switch_persists_after_restart
test_kill_switch_blocks_new_orders
test_kill_switch_requires_admin_key
test_kill_switch_is_idempotent
test_kill_switch_failure_enters_manual_review
test_kill_switch_audit_record_created
test_kill_switch_with_active_partial_fill
test_kill_switch_with_open_order
test_kill_switch_resume_requires_two_person_approval
test_resume_requester_cannot_approve_own_request
test_same_actor_cannot_approve_twice
test_resume_requires_admin_and_operator_roles
test_expired_resume_request_cannot_be_approved
test_resume_applies_reduced_exposure
test_resume_blocked_when_reconciliation_failed
```

### 21.2 F2 — Synthetic Stop

```text
test_stop_loaded_from_postgres_after_restart
test_stop_triggers_only_once
test_stop_retry_schedule_is_0_5_15_seconds
test_stop_duplicate_order_prevented
test_stop_failure_enters_manual_review
test_stop_audit_record_created
test_stop_reconciliation_after_restart
```

### 21.3 F2 — Approval Timeout and Risk

```text
test_dynamic_timeout_by_timeframe
test_ips_timeout_can_only_reduce_timeout
test_invalid_ips_timeout_rejected
test_price_drift_expires_signal
test_price_drift_threshold_is_0_2_percent
test_price_drift_calculation_uses_decimal
test_timeout_transition_is_atomic
test_timeout_audit_record_created

test_max_risk_per_trade_is_0_5_percent
test_risk_engine_rejects_missing_atr
test_risk_engine_rejects_stale_data
test_risk_engine_rejects_unknown_symbol
test_risk_engine_rejects_short_direction
test_risk_engine_rejects_when_kill_switch_active
test_position_sizing_uses_decimal
test_position_sizing_respects_hard_caps
test_position_sizing_rounds_down_to_step_size
```

### 21.4 F2 — State Machine

```text
test_valid_transitions_only
test_invalid_transition_rejected
test_concurrent_transition_is_serialized
test_partial_fill_timeout_cancels_remainder
test_protection_failure_retry_schedule
test_state_transition_creates_audit_record
```

### 21.5 F3 — End-to-End Integration

```text
test_signal_to_approval_to_order_flow
test_signal_to_approval_to_partial_fill_to_protection
test_signal_to_approval_to_synthetic_stop_execution
test_order_idempotency_across_duplicate_requests
test_outbox_event_created_in_same_transaction
test_outbox_publisher_delivers_event
test_outbox_retry_on_delivery_failure
test_outbox_dead_letter_after_max_retries
test_dead_letter_event_is_persistent
test_dead_letter_event_is_linked_to_original_event
test_dead_letter_metric_is_incremented
test_dead_letter_alert_is_triggered
test_dead_letter_replay_requires_admin_approval
test_dead_letter_replay_is_audited
test_decision_history_is_queryable
test_decision_history_is_read_only
```

### 21.6 F3 — Chaos and Failure Injection

```text
test_worker_kill_during_order_processing
test_worker_restart_recovers_synthetic_stop
test_worker_restart_does_not_duplicate_stop_order
test_database_restart_during_outbox_delivery
test_database_restart_does_not_lose_committed_order
test_database_restart_does_not_lose_dead_letter_event
test_redis_restart_does_not_corrupt_kill_switch_state
test_kill_switch_activation_during_partial_fill
test_kill_switch_activation_during_active_order
test_exchange_connector_failure_causes_fail_closed
test_stale_market_data_blocks_order_submission
test_paper_network_isolation_under_chaos
test_no_live_order_is_submitted_in_any_failure_scenario
```

---

## 22. CI/CD Contract

### 22.1 Pipeline

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
13. Build Docker image
14. Run security scan
15. Validate Paper network isolation
```

### 22.2 Security Checks

```text
Secret scanning
Dependency vulnerability scan
Docker image vulnerability scan
Forbidden live-trading code check
Real exchange credential-pattern check
Paper LIVE_TRADING=false validation
Paper-network-only validation
```

### 22.3 Required CI Gates

- `ruff check` passes
- `ruff format --check` passes
- `mypy --strict` passes
- All tests pass
- Coverage thresholds pass
- Migrations apply and roll back cleanly
- Image builds
- No secret detected
- No live adapter or endpoint present
- Paper isolation tests pass
- Dead-Letter persistence/monitoring tests pass
- Two-Person Approval tests pass

---

## 23. Security Controls

### 23.1 Secrets

- `.env` files are not committed
- `.env.example` contains only placeholders
- Secret scanning runs in CI
- API keys are injected through environment secrets
- Secrets are never logged, serialized in audit records, or returned in errors

### 23.2 Auditability

Audit record is mandatory for:

- Financial state transitions
- Kill Switch activation and resume
- Approval timeout and price-drift expiry
- Dead-Letter creation, acknowledgement, replay, discard, and escalation
- Resume request creation, approval, rejection, expiry, and completion

### 23.3 Data Protection

- Financial values use Decimal
- Timestamps use UTC
- Database accounts use least privilege
- Paper and non-Paper use separate credentials
- Real exchange credentials are forbidden

---

## 24. G0 Exit Criteria — Measurable Thresholds

### 24.1 Architecture

| Criterion | Threshold |
|---|---|
| ADR approved | ADR-0001 committed and approved |
| Scope frozen | Zero forbidden component in active path |
| Paper isolation | 100% Paper isolation tests pass |
| No live trading | Zero live adapter, endpoint, or real credential |

### 24.2 Infrastructure

| Criterion | Threshold |
|---|---|
| Development environment | `docker-compose up --build` succeeds |
| Paper environment | `docker-compose.paper.yml` succeeds |
| Database health | PostgreSQL healthcheck passes |
| Redis health | Redis healthcheck passes |
| API readiness | `/readyz` returns `200` |
| Migration integrity | M001–M006 apply and roll back successfully |

### 24.3 Security

| Criterion | Threshold |
|---|---|
| Authentication | 100% auth tests pass |
| Admin isolation | 100% authorization tests pass |
| Secret leakage | Zero secret findings |
| Dependency scan | Zero HIGH and CRITICAL vulnerabilities |
| Container scan | Zero CRITICAL vulnerabilities |
| Audit completeness | 100% audit-event tests pass |
| Two-person approval | 100% resume-approval tests pass |

### 24.4 Safety

| Criterion | Threshold |
|---|---|
| Kill Switch persistence | 100% persistence tests pass |
| Active-order Kill Switch | 100% active-order tests pass |
| Synthetic Stop idempotency | Zero duplicate stop orders in restart/retry tests |
| Protection retry | Exactly `0s`, `5s`, `15s` |
| Outbox reliability | 100% delivery/failure tests pass |
| Dead-Letter | 100% schema/replay/monitoring tests pass |
| Fail-closed | 100% failure-injection tests end at `NO_ACTION` or `MANUAL_REVIEW` |

### 24.5 Quality

| Criterion | Threshold |
|---|---|
| Lint | Zero `ruff` errors |
| Formatting | Zero format diffs |
| Type checking | Zero mypy strict errors |
| Tests | Zero failures |
| Overall coverage | At least 80% |
| Safety module coverage | At least 90% |
| F3 integration | 100% pass |
| F3 chaos | 100% pass |

---

## 25. Acceptance Decision Rule

G0 is approved only if:

```text
All mandatory CI gates pass
AND all F1, F2, and F3 tests pass
AND all quantitative G0 thresholds are met
AND Dead-Letter persistence and monitoring are implemented
AND Two-Person Approval for Kill Switch Resume is implemented
AND no live-trading or Paper-isolation violation exists
```

If any mandatory gate fails:

```text
REQUIRES CHANGES
```

---

## 26. Auditor Decision Record

The following decisions are approved for MVP-0 implementation:

1. MVP-0 is Paper-only; Direct Mode and Live Trading are excluded.
2. Only `PaperTradingAdapter` and `FakeExchangeAdapter` are permitted.
3. PostgreSQL is the sole durable source of truth.
4. Kill Switch, Synthetic Stop, approvals, orders, positions, audit events, Outbox events, and Dead-Letter events are PostgreSQL-backed.
5. Redis is only transient state, cache, and lock infrastructure.
6. Paper Compose uses internal isolated network and separate PostgreSQL/Redis.
7. TimescaleDB is excluded.
8. `/healthz` is liveness-only; `/readyz` checks dependency readiness.
9. Static Bearer keys are the MVP-0 authentication mechanism.
10. Protection retry schedule is `0s`, `5s`, `15s`.
11. Risk per trade is hard-capped at 0.50%.
12. Only BTC/USDT, ETH/USDT, and BNB/USDT Spot LONG trades are allowed.
13. No live adapter, credential, or real order submission exists before separate ADR and gate.
14. Dead-Letter events are persistent, monitored, alerted, and never silently discarded.
15. Kill Switch Resume requires `approval_requests`-backed Two-Person Approval.
16. Requester cannot approve own request; same actor cannot approve twice.
17. Resume approvals require one ADMIN and one OPERATOR.

---

## 27. Final Implementation Status

```text
Revision 1.0: Initial consultant implementation contract
Revision 1.1: Auditor findings and recommendations addressed
Revision 1.2: Final auditor conditions incorporated

Final status:
APPROVED FOR MVP-0 IMPLEMENTATION

Next step:
Begin F1 Foundation implementation using this contract as the
single source of implementation truth.
```
