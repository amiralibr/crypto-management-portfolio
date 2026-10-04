"""Orders read-only / handoff inspection API v1 endpoints for Phase F3 (§3 & §9)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session
from app.core.enums import ApiRole
from app.core.errors import NotFoundError, get_request_id
from app.core.security import require_operational_role
from app.db.models.order import Order
from app.schemas.orders import OrderListResponse, OrderResponse

router = APIRouter(prefix="/orders", tags=["orders"])


def _format_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _serialize_order(order: Order, *, request_id: str) -> OrderResponse:
    return OrderResponse(
        id=str(order.id),
        client_order_id=order.client_order_id,
        signal_id=str(order.signal_id) if order.signal_id is not None else None,
        strategy_id=str(order.strategy_id),
        exchange_account_id=str(order.exchange_account_id),
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=str(order.quantity),
        limit_price=str(order.limit_price) if order.limit_price is not None else None,
        filled_quantity=str(order.filled_quantity),
        average_fill_price=(
            str(order.average_fill_price) if order.average_fill_price is not None else None
        ),
        status=order.status,
        state_machine_state=order.state_machine_state,
        risk_decision=order.risk_decision,
        risk_reason_codes=[str(c) for c in (order.risk_reason_codes or [])],
        idempotency_key=order.idempotency_key,
        expires_at=_format_dt(order.expires_at),
        created_at=_format_dt(order.created_at) or "",
        updated_at=_format_dt(order.updated_at) or "",
        version=order.version,
        request_id=request_id,
    )


@router.get("", response_model=OrderListResponse)
async def list_orders(
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    signal_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> OrderListResponse:
    """List orders (`GET /api/v1/orders`, F3 handoff/read scope only)."""
    stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
    if signal_id is not None:
        stmt = stmt.where(Order.signal_id == signal_id)
    stmt = stmt.limit(limit)
    orders = list((await session.scalars(stmt)).all())
    req_id = get_request_id(request)
    items = [_serialize_order(o, request_id=req_id) for o in orders]
    return OrderListResponse(items=items, total=len(items), request_id=req_id)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderResponse:
    """Retrieve a single order by UUID (`GET /api/v1/orders/{order_id}`, F3 read scope)."""
    order = await session.scalar(select(Order).where(Order.id == order_id))
    if order is None:
        raise NotFoundError(f"Order '{order_id}' not found", details={"order_id": str(order_id)})
    return _serialize_order(order, request_id=get_request_id(request))
