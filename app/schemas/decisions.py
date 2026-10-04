"""Pydantic schemas for Read-Only Decision Log API v1 endpoints (Phase F3 §10)."""

from typing import Any

from pydantic import BaseModel


class DecisionAuditEventSchema(BaseModel):
    """Read-only audit event schema inside a Signal Decision record."""

    audit_id: str
    action: str
    actor_role: str
    target_type: str
    target_id: str | None
    reason_code: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    detail_json: dict[str, Any] | None
    created_at: str


class DecisionOrderSummarySchema(BaseModel):
    """Read-only order summary schema inside a Signal Decision record."""

    order_id: str
    client_order_id: str
    status: str
    state_machine_state: str
    risk_decision: str
    risk_reason_codes: list[str]
    quantity: str
    limit_price: str | None
    created_at: str


class DecisionLogEntrySchema(BaseModel):
    """Read-only Decision Log entry returned by `/api/v1/decisions` (§10)."""

    id: str
    signal_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    direction: str
    reference_price: str
    stop_loss_price: str
    take_profit_price: str | None
    risk_reward_ratio: str
    data_quality_score: str
    confidence_score: str
    rule_version: str
    approval_status: str
    approval_expires_at: str
    explanation_json: dict[str, Any]
    events: list[DecisionAuditEventSchema]
    orders: list[DecisionOrderSummarySchema]
    created_at: str
    updated_at: str
    request_id: str | None = None


class DecisionLogListResponse(BaseModel):
    """Response for `GET /api/v1/decisions` (§10)."""

    items: list[DecisionLogEntrySchema]
    total: int
    request_id: str
