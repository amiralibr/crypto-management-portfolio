"""Read-Only Decision Log API v1 endpoints for Phase F3 (§10 & §16.4).

Strictly exposes read-only GET routes (`/api/v1/decisions` and `/api/v1/decisions/{signal_id}`).
No create, update, delete, comment, feedback, or model-evaluation endpoint exists.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session
from app.core.enums import ApiRole
from app.core.errors import get_request_id
from app.core.security import require_operational_role
from app.schemas.decisions import (
    DecisionAuditEventSchema,
    DecisionLogEntrySchema,
    DecisionLogListResponse,
    DecisionOrderSummarySchema,
)
from app.services.decision_log import DecisionLogEntryRecord, DecisionLogService

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _to_schema(
    record: DecisionLogEntryRecord,
    *,
    request_id: str,
) -> DecisionLogEntrySchema:
    return DecisionLogEntrySchema(
        id=record.id,
        signal_id=record.signal_id,
        strategy_id=record.strategy_id,
        symbol=record.symbol,
        timeframe=record.timeframe,
        direction=record.direction,
        reference_price=record.reference_price,
        stop_loss_price=record.stop_loss_price,
        take_profit_price=record.take_profit_price,
        risk_reward_ratio=record.risk_reward_ratio,
        data_quality_score=record.data_quality_score,
        confidence_score=record.confidence_score,
        rule_version=record.rule_version,
        approval_status=record.approval_status,
        approval_expires_at=record.approval_expires_at,
        explanation_json=record.explanation_json,
        events=[
            DecisionAuditEventSchema(
                audit_id=ev.audit_id,
                action=ev.action,
                actor_role=ev.actor_role,
                target_type=ev.target_type,
                target_id=ev.target_id,
                reason_code=ev.reason_code,
                before_json=ev.before_json,
                after_json=ev.after_json,
                detail_json=ev.detail_json,
                created_at=ev.created_at,
            )
            for ev in record.events
        ],
        orders=[
            DecisionOrderSummarySchema(
                order_id=ord_rec.order_id,
                client_order_id=ord_rec.client_order_id,
                status=ord_rec.status,
                state_machine_state=ord_rec.state_machine_state,
                risk_decision=ord_rec.risk_decision,
                risk_reason_codes=ord_rec.risk_reason_codes,
                quantity=ord_rec.quantity,
                limit_price=ord_rec.limit_price,
                created_at=ord_rec.created_at,
            )
            for ord_rec in record.orders
        ],
        created_at=record.created_at,
        updated_at=record.updated_at,
        request_id=request_id,
    )


@router.get("", response_model=DecisionLogListResponse)
async def list_decisions_endpoint(
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    approval_status: Annotated[str | None, Query()] = None,
    symbol: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> DecisionLogListResponse:
    """List read-only decision log history (`GET /api/v1/decisions`, §10)."""
    service = DecisionLogService()
    records = await service.list_decisions(
        session,
        approval_status=approval_status,
        symbol=symbol,
        limit=limit,
    )
    req_id = get_request_id(request)
    items = [_to_schema(rec, request_id=req_id) for rec in records]
    return DecisionLogListResponse(
        items=items,
        total=len(items),
        request_id=req_id,
    )


@router.get("/{signal_id}", response_model=DecisionLogEntrySchema)
async def get_decision_by_signal_id_endpoint(
    signal_id: str,
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DecisionLogEntrySchema:
    """Retrieve read-only decision log history for a specific signal (§10)."""
    service = DecisionLogService()
    record = await service.get_decision_by_signal_id(session, signal_id)
    return _to_schema(record, request_id=get_request_id(request))
