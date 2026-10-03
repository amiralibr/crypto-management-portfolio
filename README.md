# MVP-0 Crypto Risk Management System — Phase F1 (Approved) & Phase F2 (Data and Risk Core)

**F1 Baseline Status:** `APPROVED` (`release/f1-candidate` @ `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`)  
**Current Active Phase:** `F2 — Data and Risk Core` (`F2 READY FOR REVIEW`)  
**Phase F3 Status:** `FROZEN / NOT STARTED`  
**Trading Mode:** `PAPER ONLY` (`LIVE_TRADING=false`, `PAPER_TRADING=true` — immutable)  
**Evidence Documents:**
- [`MVP0_F1_Completion_Evidence_v1.0.md`](./MVP0_F1_Completion_Evidence_v1.0.md)
- [`MVP0_F1_Gate_Evidence_Addendum_v1.0.md`](./MVP0_F1_Gate_Evidence_Addendum_v1.0.md)
- [`MVP0_F2_Completion_Evidence_v1.0.md`](./MVP0_F2_Completion_Evidence_v1.0.md)

---

## 1. Architecture & Safety Invariants (F1 + F2)

- **Runtime:** Python 3.12, FastAPI, Uvicorn locked to `--workers 1`
- **Independent Kill Switch Service & Container:** `app/kill_switch_service.py` (`docker/Dockerfile.kill-switch`, `kill_switch` in `docker-compose.yml` on port `8001`, and `paper_kill_switch` in `docker-compose.paper.yml`), monitoring Risk Engine heartbeats and automatically activating Kill Switch if heartbeat age exceeds `60` seconds (`RISK_ENGINE_HEARTBEAT_TIMEOUT_SECONDS=60`).
- **Risk Engine (`app/services/risk_engine.py`):**
  - Strictly `Decimal`-only arithmetic and `floor_to_step` (`ROUND_DOWN`).
  - Hard ceiling on risk per trade: **`0.005` (`0.5%`)** (`MAX_RISK_PER_TRADE_PCT=0.005`); `0.01` (`1.0%`) or higher is rejected fail-closed.
  - Durable heartbeat persisted in PostgreSQL (`SystemState` key `RISK_ENGINE_HEARTBEAT`).
- **Kill Switch & Two-Person Resume (`app/services/kill_switch.py`):**
  - 7-step ordered activation, idempotent repeat calls, and `MANUAL_REVIEW` on adapter failure.
  - Two-Person Approval (`ADMIN` + `OPERATIONAL`, distinct actors), **`86400` seconds (`24h`)** resume request expiry (`KILL_SWITCH_RESUME_REQUEST_EXPIRY_SECONDS=86400`), reconciliation gate, and `30%` reduced exposure (`0.3000`) on resume.
- **Central Redis Scope Policy (`app/core/config.py` & `app/core/redis.py`):**
  - `FORBIDDEN_DURABLE_PREFIXES` defined centrally in `app/core/config.py`, blocking all durable domain prefixes (`order:`, `position:`, `trade:`, `signal:`, `approval:`, `audit:`, `outbox:`, `dead_letter:`, `kill_switch:`, `resume:`, `durable:`, `sot:`) from Redis.
- **Transactional Outbox & Dead-Letter Queue (`app/services/outbox.py`):**
  - `SELECT ... FOR UPDATE SKIP LOCKED`, exponential backoff (`2s, 4s, 8s, 16s, 32s`), `dead_letter_events`, tiered alerting, and **Admin-only Replay** (`POST /api/v1/system/dead-letters/{id}/replay`).
- **E2E (`TestSignalFactory`) & Chaos Test Suites:**
  - `tests/factories.py` & `tests/e2e/test_signal_lifecycle_e2e.py`
  - `tests/chaos/test_f2_chaos.py` (API outage, Risk Engine heartbeat timeout >60s, Kill Switch container restart, DB disconnect, Redis restart)
