from fastapi import APIRouter

from app.deps import CurrentUser, DbDep
from app.schemas.me import MeOut, ProfileOut, ProfileUpdate, SettingsOut, SettingsUpdate
from app.services import me as me_service

router = APIRouter(tags=["me"])


@router.get("/me")
async def get_me(user: CurrentUser, db: DbDep) -> MeOut:
    return await me_service.get_me(db, user.id)


@router.patch("/me/profile")
async def update_my_profile(body: ProfileUpdate, user: CurrentUser, db: DbDep) -> ProfileOut:
    return await me_service.update_profile(db, user.id, body)


@router.get("/settings")
async def get_my_settings(user: CurrentUser, db: DbDep) -> SettingsOut:
    return await me_service.get_settings_for(db, user.id)


@router.patch("/settings")
async def update_my_settings(body: SettingsUpdate, user: CurrentUser, db: DbDep) -> SettingsOut:
    return await me_service.update_settings(db, user.id, body)
