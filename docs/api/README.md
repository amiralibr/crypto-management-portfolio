# MVP-0 API & Service Routing Documentation (F1 Foundation, F2 Data/Risk Core & F3 Signal/Approval)

## 1. Public Probes (`mvp0_api` on Port 8000)

- `GET /healthz`: Liveness probe (returns HTTP 200 when application process is alive).
- `GET /readyz`: Readiness probe (validates PostgreSQL, Redis, migrations, and configuration; returns HTTP 200 or HTTP 503).
- `GET /metrics`: Prometheus metrics endpoint.

## 2. Authenticated Foundation & Risk Endpoints (`mvp0_api` on Port 8000)

- `GET /api/v1/system/health`: Detailed authenticated health status (`OPERATIONAL` or `ADMIN` key).
- `GET /api/v1/system/status`: Administrative foundation status (`ADMIN` key required).
- `GET /api/v1/risk/status`: Current risk engine limits, Kill Switch state, and exposure multiplier (`OPERATIONAL` or `ADMIN` key).
- `POST /api/v1/system/dead-letters/{dead_letter_id}/replay`: Admin-only Dead-Letter replay endpoint (`ADMIN` key required; `403 Forbidden` for `OPERATIONAL`).

## 3. Phase F3 Signal, Approval, Decision Log & Order Read Endpoints (`mvp0_api` on Port 8000)

All endpoints below require `Authorization: Bearer <MVP0_API_KEY>` (or `<MVP0_ADMIN_API_KEY>`). All mutating (`POST`) endpoints require `Idempotency-Key: <uuid>`:

- `GET /api/v1/signals`: List signals with optional `approval_status`, `symbol`, and `limit` query filters (`OPERATIONAL` or `ADMIN` key).
- `GET /api/v1/signals/{signal_id}`: Retrieve a single signal by UUID or `signal_id` string (`OPERATIONAL` or `ADMIN` key).
- `POST /api/v1/signals/{signal_id}/approve`: Approve a `PENDING_APPROVAL` signal and atomically hand off to the F2 Risk Engine (`OPERATIONAL` or `ADMIN` key, requires `Idempotency-Key`).
  - Error codes: `401 UNAUTHORIZED`, `404 SIGNAL_NOT_FOUND`, `409 INVALID_STATE`, `409 SIGNAL_EXPIRED`, `409 PRICE_DRIFT_EXPIRED`, `409 IDEMPOTENCY_CONFLICT`.
- `POST /api/v1/signals/{signal_id}/reject`: Reject a `PENDING_APPROVAL` signal (`OPERATIONAL` or `ADMIN` key, requires `Idempotency-Key`).
- `GET /api/v1/decisions`: Read-only Decision Log history combining signal `explanation_json`, immutable `audit_logs`, and linked order risk decisions (`OPERATIONAL` or `ADMIN` key). Strictly read-only (`POST`/`PUT`/`PATCH`/`DELETE` are forbidden and not exposed).
- `GET /api/v1/decisions/{signal_id}`: Read-only Decision Log detail for a specific signal (`OPERATIONAL` or `ADMIN` key).
- `GET /api/v1/orders`: Read-only list of orders created via Signal-to-Order handoff (`OPERATIONAL` or `ADMIN` key).
- `GET /api/v1/orders/{order_id}`: Read-only order detail (`OPERATIONAL` or `ADMIN` key).

## 4. Kill Switch Routing & Container Architecture (`mvp0_api:8000` vs `kill_switch:8001`)

1. **`POST /api/v1/system/emergency-stop` is served exclusively by `mvp0_api` (`app.main:app`) on port `8000`:**
   - `POST /api/v1/system/emergency-stop` (`ADMIN` key required): Activates the Emergency Kill Switch.
   - `GET /api/v1/system/emergency-stop` (`ADMIN` key required): Queries current Kill Switch state.
   - `POST /api/v1/system/emergency-stop/resume-requests` (`ADMIN` key required): Creates a 24-hour (`86400s`) Two-Person Resume request.
   - `POST /api/v1/system/emergency-stop/resume-requests/{id}/approve` (`ADMIN` or `OPERATIONAL` key): Submits one approval toward Two-Person Resume.
   - `POST /api/v1/system/emergency-stop/resume-requests/{id}/reject` (`ADMIN` or `OPERATIONAL` key): Rejects a pending resume request.
   - `GET /api/v1/system/emergency-stop/resume-requests/{id}` (`ADMIN` or `OPERATIONAL` key): Inspects resume request status.
2. **PostgreSQL as the Single Durable Source of Truth:**
   - `mvp0_api` (`port 8000`) writes Kill Switch state (`SystemState.state_key = "KILL_SWITCH"`) and Risk Engine heartbeats (`SystemState.state_key = "RISK_ENGINE_HEARTBEAT"`) into PostgreSQL.
3. **Internal `kill_switch` Service (`app.kill_switch_service:app`) on Internal Port `8001`:**
   - Runs in an independent container (`kill_switch` in `docker-compose.yml` with `expose: ["8001"]` and zero host port bindings; `paper_kill_switch` in `docker-compose.paper.yml` on internal `mvp0_paper_network`).
   - **Does NOT expose the public `/api/v1/system/emergency-stop` endpoint** (requests to `/api/v1/system/emergency-stop` on port `8001` return `404 Not Found`).
   - Reads Kill Switch state (`KILL_SWITCH`) and Risk Engine heartbeat (`RISK_ENGINE_HEARTBEAT`) from PostgreSQL (`GET /internal/kill-switch/state`, `POST /api/v1/kill-switch/heartbeat-check`, and background `_heartbeat_monitor_loop`), automatically activating the Kill Switch in PostgreSQL if the Risk Engine heartbeat is missing or older than `60` seconds.
