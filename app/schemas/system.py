"""System health, readiness, and foundation status schemas for MVP-0."""

from pydantic import BaseModel


class HealthzResponse(BaseModel):
    """Liveness probe response schema."""

    status: str
    timestamp: str
    request_id: str


class ReadyzResponse(BaseModel):
    """Readiness probe response schema."""

    status: str
    database: str
    redis: str
    migrations: str
    timestamp: str
    request_id: str


class SystemHealthResponse(BaseModel):
    """Authenticated detailed system health response schema."""

    status: str
    environment: str
    paper_trading: bool
    live_trading: bool
    database: str
    redis: str
    migrations: str
    role: str
    timestamp: str
    request_id: str


class AdminSystemStatusResponse(BaseModel):
    """Admin-only system foundation status response schema."""

    status: str
    environment: str
    paper_trading: bool
    live_trading: bool
    uvicorn_workers: int
    supervisor_tasks: int
    role: str
    timestamp: str
    request_id: str
