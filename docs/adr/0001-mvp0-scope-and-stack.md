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
