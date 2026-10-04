"""Pydantic schemas for Signal & Approval API v1 endpoints (Phase F3 §8)."""

from typing import Any

from pydantic import BaseModel, Field


class SignalActionRequest(BaseModel):
    """Request body for signal approval or rejection (§8.2 & §8.3)."""

    reason: str = Field(..., min_length=1, max_length=512)


class SignalOrderHandoffSummary(BaseModel):
    """Summary of the Order created or risk-rejected during Signal-to-Order handoff (§9)."""

    order_id: str
    client_order_id: str
    status: str
    state_machine_state: str
    risk_decision: str
    risk_reason_codes: list[str]
    quantity: str
    limit_price: str | None


class SignalResponse(BaseModel):
    """Serialized representation of a persisted Signal (§4.5 & §8)."""

    id: str
    signal_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    direction: str
    reference_price: str
    entry_range_min: str
    entry_range_max: str
    stop_loss_price: str
    take_profit_price: str | None
    risk_reward_ratio: str
    data_quality_score: str
    confidence_score: str
    rule_version: str
    approval_status: str
    approval_expires_at: str
    explanation_json: dict[str, Any]
    created_at: str
    updated_at: str
    version: int
    order: SignalOrderHandoffSummary | None = None
    request_id: str


class SignalListResponse(BaseModel):
    """Paginated list of Signals returned by `GET /api/v1/signals` (§8.1)."""

    items: list[SignalResponse]
    total: int
    request_id: str
