# MVP-0 Crypto Risk Management System — Phase F1 Foundation

**Current Official Phase:** `F1 — Foundation`  
**Phase Status:** `F1 READY FOR REVIEW`  
**F1 Candidate Tag:** `release/f1-candidate` (Commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`)  
**F2 Candidate Status:** `FROZEN AS F2 CANDIDATE` (`release/f2-candidate` — Commit `a15f3dc4e986f21bdfbcb1da812599a550d8eb7b`, awaiting formal F1 Auditor approval)  
**F3 Status:** `FROZEN / NOT STARTED`  
**Trading Mode:** `PAPER ONLY` (`LIVE_TRADING=false`, `PAPER_TRADING=true` — immutable)  
**Completion Evidence Document:** [`MVP0_F1_Completion_Evidence_v1.0.md`](./MVP0_F1_Completion_Evidence_v1.0.md)

---

## 1. Phase Governance & Freeze Notice

- **Phase F1 (`release/f1-candidate`)** is complete and submitted for formal Auditor review (`F1 READY FOR REVIEW`). Full evidence is documented in [`MVP0_F1_Completion_Evidence_v1.0.md`](./MVP0_F1_Completion_Evidence_v1.0.md).
- **Phase F2 (`release/f2-candidate`) and Phase F3** are **strictly frozen**. Early F2 changes (`bdff565..a15f3dc`) are retained solely as an unapproved `F2 Candidate` (`release/f2-candidate`) and will not be advanced until written Auditor sign-off of Phase F1.

---

## 2. F1 Overview & Hard Constraints

F1 Foundation implements the minimum safe, observable, testable foundation for MVP-0:

- **Runtime:** Python 3.12, FastAPI, Uvicorn locked to `--workers 1`
- **Durable Store:** PostgreSQL 16 via SQLAlchemy 2 AsyncEngine + Alembic (`M001`–`M006`)
- **Transient Store:** Redis 7 (`RedisClient` restricted to cache/locks; never durable state)
- **Authentication:** Static Bearer API Keys (`MVP0_API_KEY` for `OPERATIONAL`, `MVP0_ADMIN_API_KEY` for `ADMIN`) using constant-time `secrets.compare_digest`
- **Observability:** `structlog` JSON output with mandatory fields and secret redaction, plus Prometheus `/metrics`
- **Paper Isolation:** Dedicated `docker-compose.paper.yml` using `mvp0_paper_network` (`internal: true`), separate PostgreSQL/Redis instances, and no host-exposed database/cache ports

---

## 3. Quickstart & Commands

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
```

### Docker Compose (Development)
```bash
docker compose up --build -d
docker compose ps
docker compose down -v
```

### Docker Compose (Isolated Paper Environment)
```bash
docker compose -f docker-compose.paper.yml up --build -d
docker compose -f docker-compose.paper.yml ps
docker compose -f docker-compose.paper.yml down -v
```

---

## 4. F1 Endpoints (`release/f1-candidate`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/healthz` | Public | Liveness probe (`200 OK`) |
| `GET` | `/readyz` | Public | Readiness probe (`200 OK` when DB, Redis, migrations, and config are valid; `503` otherwise) |
| `GET` | `/metrics` | Public/Internal | Prometheus metrics endpoint |
| `GET` | `/api/v1/system/health` | `OPERATIONAL` or `ADMIN` | Detailed authenticated health status |
| `GET` | `/api/v1/system/status` | `ADMIN` | Administrative foundation configuration status |
