"""Pytest configuration and shared fixtures for MVP-0 F1 Foundation tests."""

import os
import shutil
import socket
import subprocess
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from alembic import command

TEST_OP_KEY: str = "test_operational_api_key_00000000001"
TEST_ADMIN_KEY: str = "test_admin_secret_api_key_0000000002"
TEST_DB_URL: str = "postgresql+asyncpg://mvp0:change_me_local_only@127.0.0.1:5432/mvp0"
TEST_REDIS_URL: str = "redis://127.0.0.1:6379/0"


def _is_port_open(host: str, port: int) -> bool:
    """Return True if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _ensure_local_services() -> None:
    """Start local PostgreSQL 16 and Redis servers if not already running."""
    if not _is_port_open("127.0.0.1", 5432) and shutil.which("pg_ctl"):
        pgdata = Path("/tmp/pgdata")
        if not (pgdata / "PG_VERSION").exists():
            pgdata.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["initdb", "-D", str(pgdata), "-U", "postgres", "--auth=trust"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with (pgdata / "postgresql.conf").open("a", encoding="utf-8") as conf:
                conf.write("\nlisten_addresses = '127.0.0.1'\nport = 5432\n")
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(pgdata),
                "-l",
                str(pgdata / "logfile"),
                "start",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        create_role_sql = (
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mvp0') THEN "
            "CREATE USER mvp0 WITH PASSWORD 'change_me_local_only' SUPERUSER; "
            "END IF; END $$;"
        )
        subprocess.run(
            [
                "psql",
                "-h",
                "127.0.0.1",
                "-p",
                "5432",
                "-U",
                "postgres",
                "-c",
                create_role_sql,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        db_check = subprocess.run(
            [
                "psql",
                "-h",
                "127.0.0.1",
                "-p",
                "5432",
                "-U",
                "postgres",
                "-tc",
                "SELECT 1 FROM pg_database WHERE datname='mvp0'",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if "1" not in db_check.stdout:
            subprocess.run(
                [
                    "psql",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    "5432",
                    "-U",
                    "postgres",
                    "-c",
                    "CREATE DATABASE mvp0 OWNER mvp0;",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    if not _is_port_open("127.0.0.1", 6379) and shutil.which("redis-server"):
        redis_dir = Path("/tmp/redisdata")
        redis_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "redis-server",
                "--bind",
                "127.0.0.1",
                "--port",
                "6379",
                "--dir",
                str(redis_dir),
                "--daemonize",
                "yes",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def pytest_configure() -> None:
    """Set baseline environment variables and ensure local services are up."""
    _ensure_local_services()
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("APP_NAME", "mvp0")
    os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
    os.environ.setdefault("REDIS_URL", TEST_REDIS_URL)
    os.environ.setdefault("MVP0_API_KEY", TEST_OP_KEY)
    os.environ.setdefault("MVP0_ADMIN_API_KEY", TEST_ADMIN_KEY)
    os.environ.setdefault("UVICORN_WORKERS", "1")
    os.environ.setdefault("SUPERVISOR_TASKS", "1")
    os.environ.setdefault("LIVE_TRADING", "false")
    os.environ.setdefault("PAPER_TRADING", "true")
    os.environ.setdefault("PRICE_DRIFT_EXPIRY_THRESHOLD", "0.002")
    os.environ.setdefault("OUTBOX_MAX_RETRIES", "5")
    os.environ.setdefault("OUTBOX_RETRY_BASE_SECONDS", "2")


@pytest.fixture(autouse=True)
def reset_default_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Reset environment and clear settings cache around every test."""
    from app.core.config import get_settings
    from app.core.logging import clear_registered_secrets, clear_request_context

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("APP_NAME", "mvp0")
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("REDIS_URL", TEST_REDIS_URL)
    monkeypatch.setenv("MVP0_API_KEY", TEST_OP_KEY)
    monkeypatch.setenv("MVP0_ADMIN_API_KEY", TEST_ADMIN_KEY)
    monkeypatch.setenv("UVICORN_WORKERS", "1")
    monkeypatch.setenv("SUPERVISOR_TASKS", "1")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("PRICE_DRIFT_EXPIRY_THRESHOLD", "0.002")
    monkeypatch.setenv("OUTBOX_MAX_RETRIES", "5")
    monkeypatch.setenv("OUTBOX_RETRY_BASE_SECONDS", "2")
    get_settings.cache_clear()
    clear_registered_secrets()
    clear_request_context()
    yield
    get_settings.cache_clear()
    clear_registered_secrets()
    clear_request_context()


@pytest.fixture
def alembic_config() -> Config:
    """Return configured Alembic Config object pointing to test database."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


@pytest.fixture
def migrated_db(alembic_config: Config) -> None:
    """Ensure database schema is migrated to head."""
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def async_client(migrated_db: None) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient bound to a fresh FastAPI application."""
    from app.db.session import dispose_db, init_db
    from app.main import create_app

    init_db()
    test_app = create_app()
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await test_app.state.redis_client.close()
    await dispose_db()
