"""System health, Kill Switch, and Two-Person Approval endpoints for API v1."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session, get_redis_client
from app.core.config import Settings, get_settings
from app.core.enums import ApiRole
from app.core.errors import get_request_id
from app.core.redis import RedisClient
from app.core.security import require_admin_role, require_operational_role
from app.db.models.approval_request import ApprovalRequest
from app.db.models.system_state import SystemState
from app.db.session import check_migrations_current, ping_database
from app.schemas.system import (
    AdminSystemStatusResponse,
    EmergencyStopActivateRequest,
    EmergencyStopActivateResponse,
    EmergencyStopStateResponse,
    ResumeRequestCreatePayload,
    ResumeRequestDecisionPayload,
    ResumeRequestResponse,
    SystemHealthResponse,
)
from app.services.kill_switch import KillSwitchService

router = APIRouter(prefix="/system", tags=["system"])

DEFAULT_ADMIN_ACTOR_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_OPERATOR_ACTOR_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")


def _format_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _resolve_actor_id(
    request: Request,
    role: ApiRole,
    explicit_id: uuid.UUID | None = None,
) -> uuid.UUID:
    if explicit_id is not None:
        return explicit_id
    header_actor = request.headers.get("X-Actor-ID")
    if header_actor:
        try:
            return uuid.UUID(header_actor)
        except ValueError:
            pass
    return DEFAULT_ADMIN_ACTOR_ID if role == ApiRole.ADMIN else DEFAULT_OPERATOR_ACTOR_ID


def _build_resume_response(
    req: ApprovalRequest,
    state: SystemState,
    request_id: str,
) -> ResumeRequestResponse:
    return ResumeRequestResponse(
        id=str(req.id),
        request_type=req.request_type,
        target_type=req.target_type,
        target_id=str(req.target_id),
        status=req.status,
        requested_by=str(req.requested_by),
        requested_by_role=req.requested_by_role,
        first_approver_id=str(req.first_approver_id) if req.first_approver_id else None,
        first_approver_role=req.first_approver_role,
        first_approved_at=_format_dt(req.first_approved_at),
        second_approver_id=str(req.second_approver_id) if req.second_approver_id else None,
        second_approver_role=req.second_approver_role,
        second_approved_at=_format_dt(req.second_approved_at),
        reason=req.reason,
        expires_at=_format_dt(req.expires_at) or "",
        completed_at=_format_dt(req.completed_at),
        kill_switch_active=state.is_active,
        exposure_multiplier=str(state.exposure_multiplier),
        request_id=request_id,
    )


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    request: Request,
    role: Annotated[ApiRole, Depends(require_operational_role)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[RedisClient, Depends(get_redis_client)],
) -> SystemHealthResponse:
    """Return detailed authenticated health status (OPERATIONAL or ADMIN)."""
    db_ok = await ping_database()
    redis_ok = await redis_client.ping()
    migrations_ok = await check_migrations_current() if db_ok else False
    overall_ok = db_ok and redis_ok and migrations_ok

    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return SystemHealthResponse(
        status="ok" if overall_ok else "degraded",
        environment=settings.ENVIRONMENT,
        paper_trading=settings.PAPER_TRADING,
        live_trading=settings.LIVE_TRADING,
        database="ok" if db_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
        migrations="ok" if migrations_ok else "unavailable",
        role=role.value,
        timestamp=now_iso,
        request_id=get_request_id(request),
    )


@router.get("/status", response_model=AdminSystemStatusResponse)
async def get_admin_system_status(
    request: Request,
    role: Annotated[ApiRole, Depends(require_admin_role)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSystemStatusResponse:
    """Return administrative foundation configuration status (ADMIN only)."""
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return AdminSystemStatusResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        paper_trading=settings.PAPER_TRADING,
        live_trading=settings.LIVE_TRADING,
        uvicorn_workers=settings.UVICORN_WORKERS,
        supervisor_tasks=settings.SUPERVISOR_TASKS,
        role=role.value,
        timestamp=now_iso,
        request_id=get_request_id(request),
    )


@router.post("/emergency-stop", response_model=EmergencyStopActivateResponse)
async def activate_emergency_stop(
    request: Request,
    payload: EmergencyStopActivateRequest,
    role: Annotated[ApiRole, Depends(require_admin_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmergencyStopActivateResponse:
    """Activate the persistent Kill Switch (ADMIN only) (§13.2 & v4.3 §2)."""
    service = KillSwitchService()
    result = await service.activate(
        session,
        reason=payload.reason,
        actor_role=role,
        activated_by="admin",
        activation_source="MANUAL_API",
    )
    await session.commit()
    return EmergencyStopActivateResponse(
        status=result.status,
        is_active=result.is_active,
        resume_status=result.resume_status,
        timestamp=result.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        request_id=get_request_id(request),
    )


@router.get("/emergency-stop", response_model=EmergencyStopStateResponse)
async def get_emergency_stop_state(
    request: Request,
    _role: Annotated[ApiRole, Depends(require_admin_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmergencyStopStateResponse:
    """Get the current persistent Kill Switch state (ADMIN only) (§16.3)."""
    service = KillSwitchService()
    state = await service.get_or_create_state(session, for_update=False)
    await session.commit()
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return EmergencyStopStateResponse(
        is_active=state.is_active,
        activated_at=_format_dt(state.activated_at),
        activated_by=state.activated_by,
        activation_reason=state.activation_reason,
        activation_source=state.activation_source,
        resume_status=state.resume_status,
        resumed_at=_format_dt(state.resumed_at),
        resumed_by=state.resumed_by,
        resume_reason=state.resume_reason,
        exposure_multiplier=str(state.exposure_multiplier),
        timestamp=now_iso,
        request_id=get_request_id(request),
    )


@router.post(
    "/emergency-stop/resume-requests",
    response_model=ResumeRequestResponse,
)
async def create_kill_switch_resume_request(
    request: Request,
    payload: ResumeRequestCreatePayload,
    role: Annotated[ApiRole, Depends(require_admin_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeRequestResponse:
    """Create a Two-Person Approval request to resume from Kill Switch (ADMIN only) (§13.6)."""
    service = KillSwitchService()
    actor_id = _resolve_actor_id(request, role, payload.requester_id)
    req = await service.create_resume_request(
        session,
        requester_id=actor_id,
        requester_role=role,
        reason=payload.reason,
    )
    state = await service.get_or_create_state(session, for_update=False)
    await session.commit()
    return _build_resume_response(req, state, get_request_id(request))


@router.post(
    "/emergency-stop/resume-requests/{request_id}/approve",
    response_model=ResumeRequestResponse,
)
async def approve_kill_switch_resume_request(
    request: Request,
    request_id: uuid.UUID,
    role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[ResumeRequestDecisionPayload | None, Body()] = None,
) -> ResumeRequestResponse:
    """Provide first or second approval for Kill Switch Resume (ADMIN or OPERATIONAL) (§13.6)."""
    service = KillSwitchService()
    actor_id = _resolve_actor_id(request, role, payload.actor_id if payload else None)
    req, state = await service.approve_resume_request(
        session,
        request_id=request_id,
        approver_id=actor_id,
        approver_role=role,
    )
    await session.commit()
    return _build_resume_response(req, state, get_request_id(request))


@router.post(
    "/emergency-stop/resume-requests/{request_id}/reject",
    response_model=ResumeRequestResponse,
)
async def reject_kill_switch_resume_request(
    request: Request,
    request_id: uuid.UUID,
    role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: Annotated[ResumeRequestDecisionPayload | None, Body()] = None,
) -> ResumeRequestResponse:
    """Reject a pending Kill Switch Resume request (ADMIN or OPERATIONAL) (§13.6)."""
    service = KillSwitchService()
    actor_id = _resolve_actor_id(request, role, payload.actor_id if payload else None)
    reason = payload.reason if (payload and payload.reason) else "Rejected by reviewer"
    req = await service.reject_resume_request(
        session,
        request_id=request_id,
        actor_id=actor_id,
        actor_role=role,
        reason=reason,
    )
    state = await service.get_or_create_state(session, for_update=False)
    await session.commit()
    return _build_resume_response(req, state, get_request_id(request))


@router.get(
    "/emergency-stop/resume-requests/{request_id}",
    response_model=ResumeRequestResponse,
)
async def get_kill_switch_resume_request(
    request: Request,
    request_id: uuid.UUID,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeRequestResponse:
    """Get a Two-Person Approval request status (ADMIN or OPERATIONAL) (§16.3)."""
    service = KillSwitchService()
    req = await service.get_resume_request(session, request_id=request_id)
    state = await service.get_or_create_state(session, for_update=False)
    return _build_resume_response(req, state, get_request_id(request))
