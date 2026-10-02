# MVP-0 Crypto Risk Management System — Phase F1 Foundation

**Current Phase:** `F1 — Foundation`  
**Phase Status:** `F1 READY FOR REVIEW`  
**Trading Mode:** `PAPER ONLY` (`LIVE_TRADING=false`, `PAPER_TRADING=true` — immutable)  
**Governing Contracts:**
1. `MVP0_Implementation_Contract_v1.2_FINAL.md`
2. `MVP0_F1_Foundation_Implementation_Package_v1.0.md`
3. `MVP-0_Complete_Engineering_Master_Package_v4_3_Final_G0_Implementation_Ready.md`

---

## 1. Overview & Hard Constraints

F1 Foundation implements the minimum safe, observable, testable foundation for MVP-0:

- **Runtime:** Python 3.12, FastAPI, Uvicorn locked to `--workers 1`
- **Durable Store:** PostgreSQL 16 via SQLAlchemy 2 AsyncEngine + Alembic (`M001`–`M006`)
- **Transient Store:** Redis 7 (`RedisClient` restricted to cache/locks; never durable state)
- **Authentication:** Static Bearer API Keys (`MVP0_API_KEY` for `OPERATIONAL`, `MVP0_ADMIN_API_KEY` for `ADMIN`) using constant-time `secrets.compare_digest`
- **Observability:** `structlog` JSON output with mandatory fields and secret redaction, plus Prometheus `/metrics`
- **Paper Isolation:** Dedicated `docker-compose.paper.yml` using `mvp0_paper_network` (`internal: true`), separate PostgreSQL/Redis instances, and no host-exposed database/cache ports

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

## 3. F1 Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/healthz` | Public | Liveness probe (`200 OK`) |
| `GET` | `/readyz` | Public | Readiness probe (`200 OK` when DB, Redis, migrations, and config are valid; `503` otherwise) |
| `GET` | `/metrics` | Public/Internal | Prometheus metrics endpoint |
| `GET` | `/api/v1/system/health` | `OPERATIONAL` or `ADMIN` | Detailed authenticated health status |
| `GET` | `/api/v1/system/status` | `ADMIN` | Administrative foundation configuration status |
