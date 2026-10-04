"""Signal list, approve, and reject API v1 endpoints for Phase F3 (§8 & §9)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session
from app.core.enums import ApiRole
from app.core.errors import InvalidRequestError, get_request_id
from app.core.security import require_operational_role
from app.db.models.order import Order
from app.db.models.signal import Signal
from app.db.repositories.signal_repository import SignalRepository
from app.integrations.exchange.base import ExchangeAdapter
from app.schemas.signals import (
    SignalActionRequest,
    SignalListResponse,
    SignalOrderHandoffSummary,
    SignalResponse,
)
from app.services.signal_lifecycle import SignalLifecycleService

router = APIRouter(prefix="/signals", tags=["signals"])


def _format_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _serialize_signal(
    signal: Signal,
    *,
    request_id: str,
    order: Order | None = None,
) -> SignalResponse:
    order_summary: SignalOrderHandoffSummary | None = None
    if order is not None:
        order_summary = SignalOrderHandoffSummary(
            order_id=str(order.id),
            client_order_id=order.client_order_id,
            status=order.status,
            state_machine_state=order.state_machine_state,
            risk_decision=order.risk_decision,
            risk_reason_codes=[str(c) for c in (order.risk_reason_codes or [])],
            quantity=str(order.quantity),
            limit_price=str(order.limit_price) if order.limit_price is not None else None,
        )

    return SignalResponse(
        id=str(signal.id),
        signal_id=signal.signal_id,
        strategy_id=str(signal.strategy_id),
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        direction=signal.direction,
        reference_price=str(signal.reference_price),
        entry_range_min=str(signal.entry_range_min),
        entry_range_max=str(signal.entry_range_max),
        stop_loss_price=str(signal.stop_loss_price),
        take_profit_price=(
            str(signal.take_profit_price) if signal.take_profit_price is not None else None
        ),
        risk_reward_ratio=str(signal.risk_reward_ratio),
        data_quality_score=str(signal.data_quality_score),
        confidence_score=str(signal.confidence_score),
        rule_version=signal.rule_version,
        approval_status=signal.approval_status,
        approval_expires_at=_format_dt(signal.approval_expires_at),
        explanation_json=dict(signal.explanation_json),
        created_at=_format_dt(signal.created_at),
        updated_at=_format_dt(signal.updated_at),
        version=signal.version,
        order=order_summary,
        request_id=request_id,
    )


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if idempotency_key is None or not idempotency_key.strip():
        raise InvalidRequestError(
            "Missing required Idempotency-Key header",
            details={"header": "Idempotency-Key"},
        )
    return idempotency_key.strip()


@router.get("", response_model=SignalListResponse)
async def list_signals(
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    approval_status: Annotated[str | None, Query()] = None,
    symbol: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> SignalListResponse:
    """List signals (`GET /api/v1/signals`, OPERATIONAL or ADMIN role) (§8.1)."""
    repo = SignalRepository(session)
    signals = await repo.list_signals(
        approval_status=approval_status,
        symbol=symbol,
        limit=limit,
    )
    req_id = get_request_id(request)
    items = [_serialize_signal(sig, request_id=req_id) for sig in signals]
    return SignalListResponse(
        items=items,
        total=len(items),
        request_id=req_id,
    )


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SignalResponse:
    """Retrieve a single signal by UUID or signal_id string."""
    repo = SignalRepository(session)
    signal = await repo.get_by_id_or_raise(signal_id, for_update=False)
    return _serialize_signal(signal, request_id=get_request_id(request))


@router.post("/{signal_id}/approve", response_model=SignalResponse)
async def approve_signal_endpoint(
    signal_id: str,
    payload: SignalActionRequest,
    request: Request,
    role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SignalResponse:
    """Approve a PENDING_APPROVAL signal and hand off to Risk Engine (§8.2 & §9)."""
    resolved_idem = _require_idempotency_key(idempotency_key)
    exchange_adapter: ExchangeAdapter | None = getattr(request.app.state, "exchange_adapter", None)
    service = SignalLifecycleService(exchange_adapter=exchange_adapter)
    outcome = await service.approve_signal(
        session,
        signal_id=signal_id,
        reason=payload.reason,
        actor_role=role.value,
        idempotency_key=resolved_idem,
    )
    await session.commit()
    return _serialize_signal(
        outcome.signal,
        request_id=get_request_id(request),
        order=outcome.order,
    )


@router.post("/{signal_id}/reject", response_model=SignalResponse)
async def reject_signal_endpoint(
    signal_id: str,
    payload: SignalActionRequest,
    request: Request,
    role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SignalResponse:
    """Reject a PENDING_APPROVAL signal (`POST /api/v1/signals/{signal_id}/reject`) (§8.3)."""
    resolved_idem = _require_idempotency_key(idempotency_key)
    service = SignalLifecycleService()
    outcome = await service.reject_signal(
        session,
        signal_id=signal_id,
        reason=payload.reason,
        actor_role=role.value,
        idempotency_key=resolved_idem,
    )
    await session.commit()
    return _serialize_signal(
        outcome.signal,
        request_id=get_request_id(request),
        order=None,
    )
