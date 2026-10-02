"""F1 Structured Logging unit tests (§13.2)."""

import json

import pytest

from app.core.logging import (
    bind_request_context,
    configure_logging,
    get_logger,
)


def test_json_output_contains_required_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every JSON log line must include all mandatory MVP-0 fields."""
    configure_logging(
        log_level="INFO",
        environment="development",
        service_name="mvp0",
    )
    capsys.readouterr()

    logger = get_logger("mvp0.test")
    logger.info("foundation_test_event", check="ok")

    captured = capsys.readouterr().out.strip().splitlines()
    assert len(captured) >= 1
    payload = json.loads(captured[-1])

    required_fields = {
        "timestamp",
        "level",
        "message",
        "environment",
        "service",
        "request_id",
        "correlation_id",
    }
    assert required_fields.issubset(payload.keys())
    assert payload["level"] == "INFO"
    assert payload["message"] == "foundation_test_event"
    assert payload["environment"] == "development"
    assert payload["service"] == "mvp0"
    assert payload[" timestamp" if " timestamp" in payload else "timestamp"].endswith("Z")


def test_request_id_propagated_in_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bound request_id and correlation_id must propagate into structured logs."""
    configure_logging(log_level="INFO", environment="development", service_name="mvp0")
    capsys.readouterr()

    req_id, corr_id = bind_request_context(
        request_id="req-12345-uuid",
        correlation_id="corr-67890-uuid",
    )
    logger = get_logger("mvp0.test")
    logger.info("context_propagation_check")

    captured = capsys.readouterr().out.strip().splitlines()
    payload = json.loads(captured[-1])
    assert payload["request_id"] == req_id == "req-12345-uuid"
    assert payload["correlation_id"] == corr_id == "corr-67890-uuid"


def test_no_secret_values_in_log_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """API keys, passwords, Authorization headers, and DB URIs must be redacted."""
    secret_api_key = "super_secret_operational_key_99999999"
    secret_admin_key = "super_secret_admin_api_key_8888888888"
    configure_logging(
        log_level="INFO",
        environment="development",
        service_name="mvp0",
        secrets_to_redact=[secret_api_key, secret_admin_key],
    )
    capsys.readouterr()

    logger = get_logger("mvp0.security")
    logger.info(
        f"Attempt with {secret_api_key} and Bearer {secret_admin_key}",
        api_key=secret_api_key,
        authorization=f"Bearer {secret_admin_key}",
        database_url="postgresql+asyncpg://mvp0:secretpw@postgres:5432/mvp0",
        nested={"password": "my_db_password", "items": [secret_api_key]},
    )

    output = capsys.readouterr().out
    assert secret_api_key not in output
    assert secret_admin_key not in output
    assert "my_db_password" not in output
    assert "secretpw" not in output

    payload = json.loads(output.strip().splitlines()[-1])
    assert payload["api_key"] == "[REDACTED]"
    assert payload["authorization"] == "[REDACTED]"
    assert payload["database_url"] == "[REDACTED]"
    assert payload["nested"]["password"] == "[REDACTED]"
