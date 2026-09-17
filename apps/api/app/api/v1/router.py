from fastapi import APIRouter

from app.api.v1 import health, me, scenarios, sessions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(scenarios.router)
api_router.include_router(sessions.router)
