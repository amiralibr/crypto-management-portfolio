"""System health, readiness, Kill Switch, and Two-Person Approval schemas for MVP-0."""

import uuid

from pydantic import BaseModel, Field


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


class EmergencyStopActivateRequest(BaseModel):
    """Request payload for activating the Kill Switch (§13.2 & v4.3 §2.1)."""

    reason: str = Field(..., min_length=3, max_length=500)


class EmergencyStopActivateResponse(BaseModel):
    """Response payload for activating the Kill Switch (§13.2 & v4.3 §2.1)."""

    status: str
    is_active: bool
    resume_status: str | None = None
    timestamp: str
    request_id: str


class EmergencyStopStateResponse(BaseModel):
    """Response payload for querying persistent Kill Switch state (§13.1 & §16.3)."""

    is_active: bool
    activated_at: str | None = None
    activated_by: str | None = None
    activation_reason: str | None = None
    activation_source: str | None = None
    resume_status: str | None = None
    resumed_at: str | None = None
    resumed_by: str | None = None
    resume_reason: str | None = None
    exposure_multiplier: str
    timestamp: str
    request_id: str


class ResumeRequestCreatePayload(BaseModel):
    """Request payload for creating a Two-Person Kill Switch Resume request (§13.6)."""

    reason: str = Field(..., min_length=3, max_length=500)
    requester_id: uuid.UUID | None = None


class ResumeRequestDecisionPayload(BaseModel):
    """Optional request payload for approving or rejecting a Resume request (§13.6)."""

    actor_id: uuid.UUID | None = None
    reason: str | None = None


class ResumeRequestResponse(BaseModel):
    """Response payload representing an ApprovalRequest for Kill Switch Resume (§13.6)."""

    id: str
    request_type: str
    target_type: str
    target_id: str
    status: str
    requested_by: str
    requested_by_role: str
    first_approver_id: str | None = None
    first_approver_role: str | None = None
    first_approved_at: str | None = None
    second_approver_id: str | None = None
    second_approver_role: str | None = None
    second_approved_at: str | None = None
    reason: str
    expires_at: str
    completed_at: str | None = None
    kill_switch_active: bool
    exposure_multiplier: str
    request_id: str


class DeadLetterReplayRequest(BaseModel):
    """Request payload for Admin-only replay of a Dead-Letter event (§19.4)."""

    resolution_note: str = Field(..., min_length=3, max_length=500)
    actor_id: uuid.UUID | None = None


class DeadLetterReplayResponse(BaseModel):
    """Response payload for Admin-only replay of a Dead-Letter event (§19.4)."""

    dead_letter_id: str
    resolution_status: str
    replayed_outbox_event_id: str
    replayed_outbox_status: str
    request_id: str
