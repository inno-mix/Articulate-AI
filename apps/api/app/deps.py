"""Shared FastAPI dependencies. Provider implementations are chosen here."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.db import get_db
from app.core.errors import LocalUserMissingError, UnauthorizedError
from app.domain.constants import LOCAL_USER_ID
from app.llm.base import LLMService
from app.llm.factory import get_llm_service
from app.models import User


def get_app_settings(request: Request) -> Settings:
    """Settings of the running app (tests can swap them via app.state.settings)."""
    settings: Settings = request.app.state.settings
    return settings


DbDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def get_current_user(db: DbDep, settings: SettingsDep) -> User:
    if settings.auth_mode == "local_single_user":
        user = await db.scalar(
            select(User)
            .where(User.id == LOCAL_USER_ID)
            .options(selectinload(User.profile), selectinload(User.settings))
        )
        if user is None:
            raise LocalUserMissingError()
        return user
    raise UnauthorizedError()  # accounts mode arrives in Phase 7


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_llm(user: CurrentUser, db: DbDep, settings: SettingsDep) -> LLMService:
    return await get_llm_service(user, db, settings)


LLMDep = Annotated[LLMService, Depends(get_llm)]
