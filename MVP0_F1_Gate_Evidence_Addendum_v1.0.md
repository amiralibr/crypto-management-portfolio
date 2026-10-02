# MVP0 F1 Gate Evidence Addendum v1.0

## Baseline

- Git tag: release/f1-candidate
- Commit SHA: bdff565d1b46222bd15340a0fe0ba3e76dd7411b
- CI Run ID: 37017716033
- Security Scan Run ID: 37017715313

## Gate 1 — Mypy Strict

- CI workflow file: .github/workflows/ci.yml
- Step name: Run mypy --strict app
- Exact command: poetry run mypy --strict app
- Exit code: 0
- Output excerpt:
  ```text
  $ poetry run mypy --strict app
  Success: no issues found in 64 source files
  ```
- Result: PASS

## Gate 2 — Ruff

### Ruff Lint

- Step name: Run ruff check
- Exact command: ruff check .
- Exit code: 0
- Output excerpt:
  ```text
  $ ruff check .
  All checks passed!

  $ poetry run ruff check app tests scripts alembic
  All checks passed!
  ```
- Result: PASS

### Ruff Format

- Step name: Run ruff format --check
- Exact command: ruff format --check .
- Exit code: 0
- Output excerpt:
  ```text
  $ ruff format --check .
  86 files already formatted

  $ poetry run ruff format --check app tests scripts alembic
  86 files already formatted
  ```
- Result: PASS

## Gate 3 — Redis Scope

### Redis usage inventory

| File | Operation | Purpose | Persistent domain data? |
|---|---|---|---|
| `app/core/config.py` (lines 43–46, 178–202) | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_URL`, `settings.redis_url` | Validate and construct Redis connection string at startup | No |
| `app/core/errors.py` (lines 92–103) | `RedisOperationError(AppError)` | Error taxonomy class for transient Redis failures (`REDIS_ERROR`, HTTP 503) | No |
| `app/core/logging.py` (lines 27, 34, 36, 42) | Sensitive key & URI redaction (`redis_password`, `redis_url`, `paper_redis_url`, `redis://...`) | Redact Redis credentials/URIs from structured JSON logs | No |
| `app/core/metrics.py` (lines 24–26, 117) | `REDIS_HEALTH_GAUGE` (`mvp0_redis_health`) | Prometheus gauge tracking Redis connectivity (`1=healthy`, `0=unhealthy`) | No |
| `app/core/redis.py` (lines 34–46) | `RedisClient.ping()` | Connectivity check (`PING`) updating `REDIS_HEALTH_GAUGE` | No |
| `app/core/redis.py` (lines 48–72) | `RedisClient.set(key, value, ttl_seconds=300)` | Ephemeral key-value cache write with default 300s TTL; rejects `FORBIDDEN_DURABLE_PREFIXES = ("durable:", "sot:")` with `RedisOperationError("Redis must not be used as durable source of truth")` | No |
| `app/core/redis.py` (lines 74–88) | `RedisClient.get(key)` | Ephemeral key-value cache read | No |
| `app/core/redis.py` (lines 90–97) | `RedisClient.close()` | Gracefully close async Redis connection pool on shutdown | No |
| `app/api/v1/dependencies.py` (lines 12–18) | `get_redis_client(request)` | FastAPI dependency returning `request.app.state.redis_client` for health probes | No |
| `app/api/v1/system.py` (lines 25–41) | `await redis_client.ping()` in `GET /api/v1/system/health` | Check Redis reachability for authenticated system health endpoint | No |
| `app/main.py` (lines 68–95, 118, 181–194) | `RedisClient(settings.redis_url)`, `await redis_client.ping()`, `await redis_client.close()` | Lifespan connection initialization/teardown and `GET /readyz` readiness probe | No |
| `app/schemas/system.py` (lines 19, 33) | `redis: str` field on `ReadinessResponse` and `SystemHealthResponse` | Response schema field reporting `"ok"` or `"unavailable"` | No |
| `tests/integration/test_redis.py` (lines 14–88) | `test_redis_ping_succeeds`, `test_redis_set_get_round_trip`, `test_redis_unavailable_does_not_crash_startup`, `test_redis_unavailable_does_not_lose_postgres_state` | Integration tests verifying transient cache round-trip, forbidden durable prefix rejection, startup resilience when Redis is down, and PostgreSQL durability | No |
| `tests/integration/test_health_and_readiness.py` (lines 22–28, 54–73) | `test_readyz_returns_200_when_dependencies_healthy`, `test_readyz_returns_503_when_redis_down` | Integration tests verifying `/readyz` returns `200` when Redis is up and `503` when Redis is down | No |

### Prohibited domain data confirmation

- Orders in Redis: No
- Positions in Redis: No
- Trades in Redis: No
- Signals in Redis: No
- Approvals in Redis: No
- Audit logs in Redis: No
- Outbox events in Redis: No
- Dead-Letter events in Redis: No
- Kill Switch state in Redis: No
- Resume approval state in Redis: No

All 10 domain entities above are persisted exclusively in PostgreSQL 16 tables (`orders`, `positions`, `trades`, `signals`, `approval_requests`, `audit_logs`, `outbox_events`, `dead_letter_events`, `system_state`) defined in `app/db/models/*` and Alembic migrations `0001_foundation_tables.py` through `0006_kill_switch_dual_approval.py`.

### PostgreSQL durability test

- Test file: tests/integration/test_redis.py
- Test name: test_redis_unavailable_does_not_lose_postgres_state
- Result: PASS
- Evidence:
  ```python
  # tests/integration/test_redis.py (lines 56-90 at commit bdff565d1b46222bd15340a0fe0ba3e76dd7411b)
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

## Conclusion

- Mypy strict: PASS
- Ruff check: PASS
- Ruff format: PASS
- Redis scope: PASS
- F1 ready for auditor decision: YES
