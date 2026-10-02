"""F1 Paper Environment Isolation security tests (§13.8 & Contract §7.3)."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.core.config import Settings, get_settings

FORBIDDEN_EXCHANGE_HOSTS: tuple[str, ...] = (
    "api.binance.com",
    "fapi.binance.com",
    "api.bybit.com",
    "api.okx.com",
    "api.kucoin.com",
    "api.coinbase.com",
    "api.kraken.com",
)


def _load_compose(filename: str) -> dict[str, Any]:
    path = Path(filename)
    assert path.exists(), f"Missing compose file: {filename}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_paper_network_is_internal() -> None:
    """mvp0_paper_network must be configured with internal: true."""
    paper_compose = _load_compose("docker-compose.paper.yml")
    networks = paper_compose.get("networks", {})
    assert "paper_network" in networks
    paper_net = networks["paper_network"]
    assert paper_net.get("name") == "mvp0_paper_network"
    assert paper_net.get("internal") is True


def test_paper_services_only_attach_to_paper_network() -> None:
    """All services in docker-compose.paper.yml must attach only to paper_network."""
    paper_compose = _load_compose("docker-compose.paper.yml")
    services = paper_compose.get("services", {})
    assert set(services.keys()) == {"paper_postgres", "paper_redis", "paper_api"}

    for service_name, service_cfg in services.items():
        attached_networks = service_cfg.get("networks", [])
        assert attached_networks == ["paper_network"], (
            f"Service {service_name} attached to non-paper networks: {attached_networks}"
        )


def test_paper_environment_has_no_live_exchange_endpoint() -> None:
    """Paper configuration and codebase must not contain live exchange endpoints."""
    files_to_scan = [
        Path("docker-compose.paper.yml"),
        Path("docker-compose.yml"),
        Path(".env.example"),
        *Path("app").rglob("*.py"),
    ]
    for file_path in files_to_scan:
        content = file_path.read_text(encoding="utf-8").lower()
        for host in FORBIDDEN_EXCHANGE_HOSTS:
            assert host not in content, f"Forbidden host {host} found in {file_path}"


def test_paper_environment_has_no_real_api_key() -> None:
    """Paper compose and .env.example must contain only placeholder credentials."""
    paper_compose = _load_compose("docker-compose.paper.yml")
    env = paper_compose["services"]["paper_api"]["environment"]
    assert "placeholder" in env["MVP0_API_KEY"]
    assert "placeholder" in env["MVP0_ADMIN_API_KEY"]

    env_example = Path(".env.example").read_text(encoding="utf-8")
    assert "MVP0_API_KEY=replace_with_32_char_random_hex" in env_example
    assert "MVP0_ADMIN_API_KEY=replace_with_32_char_random_hex" in env_example
    assert "LIVE_TRADING=false" in env_example
    assert "PAPER_TRADING=true" in env_example


def test_paper_live_trading_flag_is_immutable() -> None:
    """LIVE_TRADING=false and PAPER_TRADING=true are immutable after startup."""
    settings = get_settings()
    assert settings.LIVE_TRADING is False
    assert settings.PAPER_TRADING is True

    with pytest.raises(ValidationError):
        settings.LIVE_TRADING = True  # type: ignore[misc]

    with pytest.raises(ValidationError):
        settings.PAPER_TRADING = False  # type: ignore[misc]

    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="paper", LIVE_TRADING=True)


def test_paper_postgres_and_redis_are_separate() -> None:
    """Paper environment uses separate PostgreSQL/Redis services, volumes, and credentials."""
    dev_compose = _load_compose("docker-compose.yml")
    paper_compose = _load_compose("docker-compose.paper.yml")

    dev_services = set(dev_compose["services"].keys())
    paper_services = set(paper_compose["services"].keys())
    assert dev_services.isdisjoint(paper_services)

    dev_volumes = set(dev_compose.get("volumes", {}).keys())
    paper_volumes = set(paper_compose.get("volumes", {}).keys())
    assert "paper_postgres_data" in paper_volumes
    assert dev_volumes.isdisjoint(paper_volumes)

    paper_pg_env = paper_compose["services"]["paper_postgres"]["environment"]
    assert paper_pg_env["POSTGRES_DB"] == "mvp0_paper"
    assert paper_pg_env["POSTGRES_USER"] == "mvp0paper"


def test_paper_api_has_no_outbound_internet_access() -> None:
    """Paper services publish no host ports and use only an internal: true network."""
    paper_compose = _load_compose("docker-compose.paper.yml")
    networks = paper_compose.get("networks", {})
    assert list(networks.keys()) == ["paper_network"]
    assert networks["paper_network"].get("internal") is True

    for service_name, service_cfg in paper_compose["services"].items():
        assert "ports" not in service_cfg, (
            f"Paper service {service_name} must not publish host ports"
        )
        assert service_cfg.get("network_mode") != "host"
