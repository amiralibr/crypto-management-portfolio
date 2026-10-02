# MVP0 F1 Gate Evidence Addendum v1.0

## Baseline

- Git tag: `release/f1-candidate`
- Commit SHA: `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`
- CI Run ID: `37017716033` (Job ID: `110872608616` — `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017716033`)
- Security Scan Run ID: `37017715313` (Job ID: `110872606059` — `https://github.com/amiralibr/crypto-management-portfolio/actions/runs/37017715313`)

---

## Gate 1 — Mypy Strict

- CI workflow file: `.github/workflows/ci.yml` (lines 71–72)
- Step name: `Run mypy --strict app` (Step `#9` in Job `110872608616`, executed `2026-10-02T14:08:29Z -> 2026-10-02T14:08:40Z`)
- Exact command:
  - CI command: `poetry run mypy --strict app`
  - Direct verification on `release/f1-candidate` (`bdff565d1b46222bd15340a0fe0ba3e76dd7411b`): `mypy --strict app`
- Exit code: `0`
- Output excerpt:
  ```text
  $ poetry run mypy --strict app
  Success: no issues found in 64 source files
  EXIT_CODE=0
  ```
- Result: **PASS**

---

## Gate 2 — Ruff

### Ruff Lint

- Step name: `Run ruff check` (Step `#7` in `.github/workflows/ci.yml`, Job `110872608616`, executed `2026-10-02T14:08:28Z -> 2026-10-02T14:08:29Z`)
- Exact command:
  - Direct repository-wide command on `release/f1-candidate` (`bdff565d1b46222bd15340a0fe0ba3e76dd7411b`): `ruff check .`
  - CI workflow command on `release/f1-candidate`: `poetry run ruff check app tests scripts alembic`
- Exit code: `0`
- Output excerpt:
  ```text
  $ ruff check .
  All checks passed!
  EXIT_CODE=0

  $ poetry run ruff check app tests scripts alembic
  All checks passed!
  EXIT_CODE=0
  ```
- Result: **PASS**

### Ruff Format

- Step name: `Run ruff format --check` (Step `#8` in `.github/workflows/ci.yml`, Job `110872608616`, executed `2026-10-02T14:08:29Z -> 2026-10-02T14:08:29Z`)
- Exact command:
  - Direct repository-wide command on `release/f1-candidate` (`bdff565d1b46222bd15340a0fe0ba3e76dd7411b`): `ruff format --check .`
  - CI workflow command on `release/f1-candidate`: `poetry run ruff format --check app tests scripts alembic`
- Exit code: `0`
- Output excerpt:
  ```text
  $ ruff format --check .
  86 files already formatted
  EXIT_CODE=0

  $ poetry run ruff format --check app tests scripts alembic
  86 files already formatted
  EXIT_CODE=0
  ```
- Result: **PASS**

---

## Gate 3 — Redis Scope

### Redis usage inventory

Exhaustive `git grep -n -i "redis" bdff565d1b46222bd15340a0fe0ba3e76dd7411b -- app/ tests/ scripts/ alembic/` audit across the entire `release/f1-candidate` tree confirms that Redis is referenced **only** in the following files and operations:

| File | Operation | Purpose | Persistent domain data? |
|---|---|---|---|
| `app/core/config.py` (lines 43–46, 178–202) | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_URL`, `settings.redis_url` | Validate and construct the Redis connection URL at startup | **No** |
| `app/core/errors.py` (lines 92–103) | `RedisOperationError(AppError)` | Error taxonomy class for transient Redis failures (`REDIS_ERROR`, HTTP 503) | **No** |
| `app/core/logging.py` (lines 27, 34, 36, 42) | Sensitive key & URI regex redaction (`redis_password`, `redis_url`, `paper_redis_url`, `redis://...`) | Redact Redis credentials/URIs from structured JSON logs | **No** |
| `app/core/metrics.py` (lines 24–26, 117) | `REDIS_HEALTH_GAUGE` (`mvp0_redis_health`) | Prometheus gauge tracking Redis connectivity (`1=healthy`, `0=unhealthy`) | **No** |
| `app/core/redis.py` (lines 34–46) | `RedisClient.ping()` | Connectivity check (`PING`) updating `REDIS_HEALTH_GAUGE` | **No** |
| `app/core/redis.py` (lines 48–72) | `RedisClient.set(key, value, ttl_seconds=300)` | Ephemeral key-value cache write with default 300s TTL; explicitly rejects `FORBIDDEN_DURABLE_PREFIXES = ("durable:", "sot:")` with `RedisOperationError("Redis must not be used as durable source of truth")` | **No** |
| `app/core/redis.py` (lines 74–88) | `RedisClient.get(key)` | Ephemeral key-value cache read | **No** |
| `app/core/redis.py` (lines 90–97) | `RedisClient.close()` | Gracefully close async Redis connection pool on shutdown | **No** |
| `app/api/v1/dependencies.py` (lines 12–18) | `get_redis_client(request)` | FastAPI dependency returning `request.app.state.redis_client` for health probes | **No** |
| `app/api/v1/system.py` (lines 25–41) | `await redis_client.ping()` in `GET /api/v1/system/health` | Check Redis reachability for authenticated system health endpoint | **No** |
| `app/main.py` (lines 68–95, 118, 181–194) | `RedisClient(settings.redis_url)`, `await redis_client.ping()`, `await redis_client.close()` in lifespan and `GET /readyz` | Lifespan connection initialization/teardown and `/readyz` readiness probe | **No** |
| `app/schemas/system.py` (lines 19, 33) | `redis: str` field on `ReadinessResponse` and `SystemHealthResponse` | Response schema field reporting `"ok"` or `"unavailable"` | **No** |
| `tests/integration/test_redis.py` (lines 14–88) | `test_redis_ping_succeeds`, `test_redis_set_get_round_trip`, `test_redis_unavailable_does_not_crash_startup`, `test_redis_unavailable_does_not_lose_postgres_state` | Integration tests verifying transient cache round-trip, forbidden durable prefix rejection, startup resilience when Redis is down, and PostgreSQL durability | **No** |
| `tests/integration/test_health_and_readiness.py` (lines 22–28, 54–73) | `test_readyz_returns_200_when_dependencies_healthy`, `test_readyz_returns_503_when_redis_down` | Integration tests verifying `/readyz` returns `200` when Redis is up and `503` when Redis is down | **No** |

### Prohibited domain data confirmation

All domain entities are persisted **exclusively in PostgreSQL 16** via SQLAlchemy 2 ORM models (`app/db/models/*`) and Alembic migrations (`M001`–`M006`), with zero Redis usage:

- Orders in Redis: **No** (Stored exclusively in PostgreSQL table `orders` — `app/db/models/order.py`, migration `0002_signals_and_orders.py`)
- Positions in Redis: **No** (Stored exclusively in PostgreSQL table `positions` — `app/db/models/position.py`, migration `0003_positions_and_trades.py`)
- Trades in Redis: **No** (Stored exclusively in PostgreSQL table `trades` — `app/db/models/trade.py`, migration `0003_positions_and_trades.py`)
- Signals in Redis: **No** (Stored exclusively in PostgreSQL table `signals` — `app/db/models/signal.py`, migration `0002_signals_and_orders.py`)
- Approvals in Redis: **No** (Stored exclusively in PostgreSQL table `approval_requests` — `app/db/models/approval_request.py`, migration `0006_kill_switch_dual_approval.py`)
- Audit logs in Redis: **No** (Stored exclusively in PostgreSQL table `audit_logs` — `app/db/models/audit_log.py`, migration `0005_outbox_and_audit.py`)
- Outbox events in Redis: **No** (Stored exclusively in PostgreSQL table `outbox_events` — `app/db/models/outbox_event.py`, migration `0005_outbox_and_audit.py`)
- Dead-Letter events in Redis: **No** (Stored exclusively in PostgreSQL table `dead_letter_events` — `app/db/models/dead_letter_event.py`, migration `0005_outbox_and_audit.py`)
- Kill Switch state in Redis: **No** (Stored exclusively in PostgreSQL table `system_state` — `app/db/models/system_state.py`, migration `0001_foundation_tables.py`)
- Resume approval state in Redis: **No** (Stored exclusively in PostgreSQL tables `approval_requests` and `system_state` — migrations `0001_foundation_tables.py` & `0006_kill_switch_dual_approval.py`)

### PostgreSQL durability test

- Test file: `tests/integration/test_redis.py` (lines 56–90 at commit `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`)
- Test name: `test_redis_unavailable_does_not_lose_postgres_state` (plus companion tests `test_redis_set_get_round_trip` verifying `RedisOperationError` on `durable:order:123`, and `test_redis_unavailable_does_not_crash_startup`)
- Result: **PASS** (Executed in CI Run `37017716033` / Job `110872608616` and local pytest suite: `tests/integration/test_redis.py .... [100%]`)
- Evidence:
  ```python
  # From tests/integration/test_redis.py (commit bdff565d1b46222bd15340a0fe0ba3e76dd7411b, lines 56-90)
  async def test_redis_unavailable_does_not_lose_postgres_state(
      migrated_db: None,
  ) -> None:
      """PostgreSQL durable state remains intact when Redis is unavailable."""
      init_db()
      factory = get_session_factory()
      account_name = "paper-durable-account"

      async with factory() as session:
          existing = await session.scalar(
              select(ExchangeAccount).where(ExchangeAccount.name == account_name)
          )
          if existing is None:
              session.add(
                  ExchangeAccount(
                      name=account_name,
                      exchange_name="paper_sim",
                      mode="PAPER",
                      is_active=True,
                  )
              )
              await session.commit()

      unreachable_redis = RedisClient("redis://127.0.0.1:6399/0")
      assert await unreachable_redis.ping() is False
      await unreachable_redis.close()

      async with factory() as verify_session:
          persisted = await verify_session.scalar(
              select(ExchangeAccount).where(ExchangeAccount.name == account_name)
          )
          assert persisted is not None
          assert persisted.mode == "PAPER"

      await dispose_db()
  ```
  Additionally, `app/core/redis.py` (lines 10–13 and 55–60 at `bdff565d1b46222bd15340a0fe0ba3e76dd7411b`) enforces at runtime that durable prefixes (`durable:`, `sot:`) are rejected with `RedisOperationError("Redis must not be used as durable source of truth")`, verified in `test_redis_set_get_round_trip` (`await client.set("durable:order:123", "forbidden")`).

---

## Conclusion

- Mypy strict: **PASS**
- Ruff check: **PASS**
- Ruff format: **PASS**
- Redis scope: **PASS**
- F1 ready for auditor decision: **YES**
