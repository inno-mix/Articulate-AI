from typing import Literal

import httpx
import redis.asyncio as redis
import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.deps import DbDep, SettingsDep

log = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])

CheckResult = Literal["ok", "unavailable"]
CHECK_TIMEOUT_S = 2.0


class HealthChecks(BaseModel):
    database: CheckResult
    redis: CheckResult
    llm: CheckResult


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    checks: HealthChecks


async def check_database(db: AsyncSession) -> CheckResult:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        log.warning("health_database_unavailable", exc_info=True)
        return "unavailable"
    return "ok"


async def check_redis(redis_url: str) -> CheckResult:
    client = redis.from_url(redis_url, socket_connect_timeout=CHECK_TIMEOUT_S)
    try:
        await client.ping()
    except Exception:
        log.warning("health_redis_unavailable", exc_info=True)
        return "unavailable"
    finally:
        await client.aclose()
    return "ok"


async def check_llm(settings: Settings) -> CheckResult:
    if settings.llm_provider != "ollama":
        return "ok"  # fake needs nothing; user keys are checked per user (Phase 9)
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_S) as http:
            response = await http.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return "unavailable"
    return "ok"


@router.get("/health")
async def health(db: DbDep, settings: SettingsDep) -> HealthOut:
    checks = HealthChecks(
        database=await check_database(db),
        redis=await check_redis(settings.redis_url),
        llm=await check_llm(settings),
    )
    all_ok = all(value == "ok" for value in checks.model_dump().values())
    return HealthOut(status="ok" if all_ok else "degraded", checks=checks)
