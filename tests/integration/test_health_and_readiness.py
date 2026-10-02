"""F1 Health, Readiness, and Metrics integration tests (§13.5)."""

import pytest
from httpx import AsyncClient

from app.core.metrics import ALL_REQUIRED_METRIC_NAMES


async def test_healthz_returns_200(async_client: AsyncClient) -> None:
    """GET /healthz returns 200 with status=ok, timestamp, and request_id."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body
    assert "request_id" in body


async def test_readyz_returns_200_when_dependencies_up(
    async_client: AsyncClient,
) -> None:
    """GET /readyz returns 200 when PostgreSQL, Redis, and migrations are healthy."""
    response = await async_client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["migrations"] == "ok"
    assert "timestamp" in body
    assert "request_id" in body


async def test_readyz_returns_503_when_db_down(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /readyz returns 503 when PostgreSQL is unavailable; /healthz stays 200."""

    async def _fake_db_down() -> bool:
        return False

    monkeypatch.setattr("app.main.ping_database", _fake_db_down)
    response = await async_client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"] == "unavailable"

    health_resp = await async_client.get("/healthz")
    assert health_resp.status_code == 200


async def test_readyz_returns_503_when_redis_down(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /readyz returns 503 when Redis is unavailable."""

    async def _fake_redis_down() -> bool:
        return False

    monkeypatch.setattr(
        async_client._transport.app.state.redis_client,  # type: ignore[union-attr]
        "ping",
        _fake_redis_down,
    )
    response = await async_client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"] == "ok"
    assert body["redis"] == "unavailable"
    assert body["migrations"] == "ok"


async def test_healthz_excluded_from_auth(async_client: AsyncClient) -> None:
    """GET /healthz does not require an Authorization header."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200


async def test_readyz_excluded_from_auth(async_client: AsyncClient) -> None:
    """GET /readyz and GET /metrics do not require an Authorization header."""
    ready_response = await async_client.get("/readyz")
    assert ready_response.status_code == 200

    metrics_response = await async_client.get("/metrics")
    assert metrics_response.status_code == 200
    text_body = metrics_response.text
    for metric_name in ALL_REQUIRED_METRIC_NAMES:
        assert metric_name in text_body
