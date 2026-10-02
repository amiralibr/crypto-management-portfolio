# MVP-0 Crypto Risk Management System — Phase F1 & F2

**Current Phase:** `F2 — Data and Risk Core`  
**Phase Status:** `F1 COMPLETED / F2 READY FOR REVIEW`  
**Trading Mode:** `PAPER ONLY` (`LIVE_TRADING=false`, `PAPER_TRADING=true` — immutable)  
**Governing Contracts:**
1. `MVP0_Implementation_Contract_v1.2_FINAL.md`
2. `MVP0_F1_Foundation_Implementation_Package_v1.0.md`
3. `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`

---

## 1. Overview & Hard Constraints

- **Runtime:** Python 3.12, FastAPI, Uvicorn locked to `--workers 1`
- **Durable Store:** PostgreSQL 16 via SQLAlchemy 2 AsyncEngine + Alembic (`M001`–`M006`)
- **Transient Store:** Redis 7 (`RedisClient` restricted to cache/locks; never durable state)
- **Authentication:** Static Bearer API Keys (`MVP0_API_KEY` for `OPERATIONAL`, `MVP0_ADMIN_API_KEY` for `ADMIN`) using constant-time `secrets.compare_digest`
- **Risk & Safety Core (F2):**
  - `RiskEngine`: Fail-closed risk evaluation, `Decimal`-only position sizing, `floor_to_step`, and immutable `InvestmentPolicySnapshot`
  - `StateMachineService`: Signal & Order state machines, 60s partial-fill timeout, and 0s/5s/15s protection retry schedule
  - `ApprovalTimeoutService`: Dynamic timeframes (`15M`=3m, `1H`=10m, `4H`=30m, `1D`=120m), IPS downward cap, and `0.2%` price drift expiry
  - `SyntheticStopService`: PostgreSQL-backed recovery, timeframe-adaptive polling, single-trigger CAS, and 0s/5s/15s market-close retry schedule
  - `KillSwitchService`: Ordered 7-step fail-safe activation, idempotent handling, and Two-Person Approval (`ADMIN` + `OPERATIONAL`) with 30% reduced exposure on resume
  - `OutboxService`: Transactional Outbox with `SELECT ... FOR UPDATE SKIP LOCKED`, exponential backoff (`2s, 4s, 8s, 16s, 32s`), Dead-Letter Queue (`dead_letter_events`), and tiered alerting
  - `WorkerSupervisor`: Single-instance background workers (`approval_timeout`, `synthetic_stop`, `outbox_publisher`, `watchdog`)

---

## 2. Quickstart & Commands

### Install Dependencies
```bash
poetry install
```

### Lint, Format, and Typecheck
```bash
poetry run ruff check app tests scripts alembic
poetry run ruff format --check app tests scripts alembic
poetry run mypy --strict app
```

### Database Migrations (M001–M006)
```bash
poetry run alembic upgrade head
poetry run alembic downgrade base
poetry run alembic upgrade head
```

### Run Test Suite & Coverage Gates
```bash
poetry run pytest
poetry run coverage report --include="app/core/*" --fail-under=90
poetry run coverage report --include="app/db/*" --fail-under=90
poetry run coverage report --include="app/services/risk_engine.py" --fail-under=90
poetry run coverage report --include="app/services/state_machine.py" --fail-under=90
poetry run coverage report --include="app/services/kill_switch.py" --fail-under=90
poetry run coverage report --include="app/core/security.py" --fail-under=90
poetry run coverage report --include="app/services/synthetic_stop.py" --fail-under=90
poetry run coverage report --include="app/services/outbox.py" --fail-under=90
```

---

## 3. Endpoints Implemented (F1 + F2)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/healthz` | Public | Liveness probe (`200 OK`) |
| `GET` | `/readyz` | Public | Readiness probe (`200 OK` when DB, Redis, migrations, and config are valid; `503` otherwise) |
| `GET` | `/metrics` | Public/Internal | Prometheus metrics endpoint |
| `GET` | `/api/v1/system/health` | `OPERATIONAL` or `ADMIN` | Detailed authenticated health status |
| `GET` | `/api/v1/system/status` | `ADMIN` | Administrative foundation configuration status |
| `GET` | `/api/v1/risk/status` | `OPERATIONAL` or `ADMIN` | Current risk status, Kill Switch state, and exposure multiplier |
| `POST` | `/api/v1/system/emergency-stop` | `ADMIN` | Activate Emergency Stop / Kill Switch |
| `GET` | `/api/v1/system/emergency-stop` | `OPERATIONAL` or `ADMIN` | Inspect Emergency Stop / Kill Switch state |
| `POST` | `/api/v1/system/emergency-stop/resume-requests` | `ADMIN` | Create Kill Switch resume request (Two-Person Approval) |
| `GET` | `/api/v1/system/emergency-stop/resume-requests` | `OPERATIONAL` or `ADMIN` | List Kill Switch resume requests |
| `GET` | `/api/v1/system/emergency-stop/resume-requests/{id}` | `OPERATIONAL` or `ADMIN` | Inspect specific resume request |
| `POST` | `/api/v1/system/emergency-stop/resume-requests/{id}/approve` | `OPERATIONAL` or `ADMIN` | Approve resume request (`ADMIN` + `OPERATIONAL`, distinct actors) |
| `POST` | `/api/v1/system/emergency-stop/resume-requests/{id}/reject` | `OPERATIONAL` or `ADMIN` | Reject active resume request |
