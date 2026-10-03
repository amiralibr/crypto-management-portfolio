# MVP-0 API & Service Routing Documentation (F1 Foundation & F2 Data/Risk Core)

## 1. Public Probes (`mvp0_api` on Port 8000)

- `GET /healthz`: Liveness probe (returns HTTP 200 when application process is alive).
- `GET /readyz`: Readiness probe (validates PostgreSQL, Redis, migrations, and configuration; returns HTTP 200 or HTTP 503).
- `GET /metrics`: Prometheus metrics endpoint.

## 2. Authenticated Foundation & Risk Endpoints (`mvp0_api` on Port 8000)

- `GET /api/v1/system/health`: Detailed authenticated health status (`OPERATIONAL` or `ADMIN` key).
- `GET /api/v1/system/status`: Administrative foundation status (`ADMIN` key required).
- `GET /api/v1/risk/status`: Current risk engine limits, Kill Switch state, and exposure multiplier (`OPERATIONAL` or `ADMIN` key).
- `POST /api/v1/system/dead-letters/{dead_letter_id}/replay`: Admin-only Dead-Letter replay endpoint (`ADMIN` key required; `403 Forbidden` for `OPERATIONAL`).

## 3. Kill Switch Routing & Container Architecture (`mvp0_api:8000` vs `kill_switch:8001`)

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
