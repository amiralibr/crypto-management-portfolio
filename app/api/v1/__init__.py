"""API v1 router registration for MVP-0."""

from fastapi import APIRouter

from app.api.v1.orders import router as orders_router
from app.api.v1.positions import router as positions_router
from app.api.v1.risk import router as risk_router
from app.api.v1.system import router as system_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(system_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(positions_router)
api_v1_router.include_router(risk_router)
