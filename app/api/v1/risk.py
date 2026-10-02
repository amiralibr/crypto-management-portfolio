"""Risk Engine status router for API v1 (§10 & §16.3)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session
from app.core.enums import ALLOWED_SYMBOLS, ApiRole
from app.core.errors import get_request_id
from app.core.security import require_operational_role
from app.schemas.risk import RiskStatusResponse
from app.services.kill_switch import KillSwitchService
from app.services.risk_engine import (
    HARD_DRAWDOWN,
    KILL_SWITCH_DRAWDOWN,
    MAX_ASSET_WEIGHT,
    MAX_DAILY_LOSS,
    MAX_RISK_PER_TRADE,
    MAX_TOTAL_EXPOSURE,
    MAX_WEEKLY_LOSS,
    MIN_CASH_RESERVE,
    SOFT_DRAWDOWN,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status", response_model=RiskStatusResponse)
async def get_risk_status(
    request: Request,
    _role: Annotated[ApiRole, Depends(require_operational_role)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RiskStatusResponse:
    """Return hard-capped Risk Engine parameters and current Kill Switch exposure status."""
    ks_service = KillSwitchService()
    state = await ks_service.get_or_create_state(session, for_update=False)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return RiskStatusResponse(
        allowed_symbols=sorted(ALLOWED_SYMBOLS),
        max_risk_per_trade=str(MAX_RISK_PER_TRADE),
        max_daily_loss=str(MAX_DAILY_LOSS),
        max_weekly_loss=str(MAX_WEEKLY_LOSS),
        max_asset_weight=str(MAX_ASSET_WEIGHT),
        max_total_exposure=str(MAX_TOTAL_EXPOSURE),
        min_cash_reserve=str(MIN_CASH_RESERVE),
        soft_drawdown=str(SOFT_DRAWDOWN),
        hard_drawdown=str(HARD_DRAWDOWN),
        kill_switch_drawdown=str(KILL_SWITCH_DRAWDOWN),
        kill_switch_active=state.is_active,
        exposure_multiplier=str(state.exposure_multiplier),
        timestamp=now_iso,
        request_id=get_request_id(request),
    )
