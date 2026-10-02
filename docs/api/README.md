# MVP-0 API Documentation (F1 Foundation)

## Public Endpoints

- `GET /healthz`: Liveness probe (always returns HTTP 200 when application process is alive).
- `GET /readyz`: Readiness probe (validates PostgreSQL, Redis, migrations, and configuration; returns HTTP 200 or HTTP 503).
- `GET /metrics`: Prometheus metrics endpoint.

## Authenticated Foundation Endpoints

- `GET /api/v1/system/health`: Detailed authenticated health status (`OPERATIONAL` or `ADMIN` key).
- `GET /api/v1/system/status`: Administrative foundation status (`ADMIN` key required).
