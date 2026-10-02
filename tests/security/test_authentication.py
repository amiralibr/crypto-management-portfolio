"""F1 Authentication and Authorization security tests (§13.6)."""

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.conftest import TEST_ADMIN_KEY, TEST_OP_KEY


async def test_missing_bearer_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Missing Authorization header on /api/v1/* returns 401 UNAUTHORIZED."""
    response = await async_client.get("/api/v1/system/health")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHORIZED"
    assert "request_id" in body


async def test_invalid_token_returns_401(async_client: AsyncClient) -> None:
    """Invalid Bearer token or query-string token returns 401 UNAUTHORIZED."""
    response = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": "Bearer invalid_key_value_000000000000000"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"

    malformed = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert malformed.status_code == 401

    query_param_attempt = await async_client.get(f"/api/v1/system/health?api_key={TEST_OP_KEY}")
    assert query_param_attempt.status_code == 401


async def test_valid_operational_key_passes(async_client: AsyncClient) -> None:
    """Valid MVP0_API_KEY succeeds on operational /api/v1/system/health route."""
    response = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": f"Bearer {TEST_OP_KEY}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["role"] == "OPERATIONAL"


async def test_admin_key_required_for_admin_routes(
    async_client: AsyncClient,
) -> None:
    """Valid MVP0_ADMIN_API_KEY succeeds on both admin and operational routes."""
    admin_resp = await async_client.get(
        "/api/v1/system/status",
        headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
    )
    assert admin_resp.status_code == 200
    assert admin_resp.json()["role"] == "ADMIN"

    op_route_resp = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
    )
    assert op_route_resp.status_code == 200
    assert op_route_resp.json()["role"] == "ADMIN"


async def test_operational_key_rejected_on_admin_routes(
    async_client: AsyncClient,
) -> None:
    """Operational key on admin-only route returns 403 FORBIDDEN."""
    response = await async_client.get(
        "/api/v1/system/status",
        headers={"Authorization": f"Bearer {TEST_OP_KEY}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "FORBIDDEN"


async def test_healthz_bypasses_auth(async_client: AsyncClient) -> None:
    """GET /healthz bypasses Bearer authentication."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200


async def test_readyz_bypasses_auth(async_client: AsyncClient) -> None:
    """GET /readyz bypasses Bearer authentication."""
    response = await async_client.get("/readyz")
    assert response.status_code == 200


async def test_api_key_not_logged(
    async_client: AsyncClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """API keys must never appear in stdout logs or error payloads."""
    capsys.readouterr()
    valid_resp = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": f"Bearer {TEST_OP_KEY}"},
    )
    assert valid_resp.status_code == 200

    invalid_key = "leaked_candidate_key_value_1234567890"
    invalid_resp = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": f"Bearer {invalid_key}"},
    )
    assert invalid_resp.status_code == 401
    assert invalid_key not in invalid_resp.text

    logs = capsys.readouterr().out
    assert TEST_OP_KEY not in logs
    assert TEST_ADMIN_KEY not in logs
    assert invalid_key not in logs


async def test_old_key_rejected_after_rotation(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After rotating MVP0_API_KEY in environment, the old key returns 401."""
    old_key = TEST_OP_KEY
    new_key = "rotated_operational_api_key_999999999"

    monkeypatch.setenv("MVP0_API_KEY", new_key)
    get_settings.cache_clear()

    old_resp = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": f"Bearer {old_key}"},
    )
    assert old_resp.status_code == 401

    new_resp = await async_client.get(
        "/api/v1/system/health",
        headers={"Authorization": f"Bearer {new_key}"},
    )
    assert new_resp.status_code == 200
