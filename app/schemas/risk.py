"""Risk status and evaluation schemas for MVP-0 (§10 & §16.3)."""

from pydantic import BaseModel


class RiskStatusResponse(BaseModel):
    """Response schema for GET /api/v1/risk/status."""

    allowed_symbols: list[str]
    max_risk_per_trade: str
    max_daily_loss: str
    max_weekly_loss: str
    max_asset_weight: str
    max_total_exposure: str
    min_cash_reserve: str
    soft_drawdown: str
    hard_drawdown: str
    kill_switch_drawdown: str
    kill_switch_active: bool
    exposure_multiplier: str
    timestamp: str
    request_id: str
