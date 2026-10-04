"""Pydantic schemas for Orders read endpoints in Phase F3 (§3 & §9)."""

from pydantic import BaseModel


class OrderResponse(BaseModel):
    """Read-only serialized representation of a Paper Order."""

    id: str
    client_order_id: str
    signal_id: str | None
    strategy_id: str
    exchange_account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: str
    limit_price: str | None
    filled_quantity: str
    average_fill_price: str | None
    status: str
    state_machine_state: str
    risk_decision: str
    risk_reason_codes: list[str]
    idempotency_key: str
    expires_at: str | None
    created_at: str
    updated_at: str
    version: int
    request_id: str


class OrderListResponse(BaseModel):
    """Response for `GET /api/v1/orders`."""

    items: list[OrderResponse]
    total: int
    request_id: str
