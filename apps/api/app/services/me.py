from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.models import Profile, User, UserSettings
from app.schemas.me import (
    MeOut,
    ProfileOut,
    ProfileUpdate,
    SettingsOut,
    SettingsUpdate,
    UserOut,
    VoiceOut,
)
from app.voice.voices import VOICES


async def get_me(db: AsyncSession, user_id: UUID) -> MeOut:
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.profile), selectinload(User.settings))
    )
    if user is None:
        raise NotFoundError()
    return MeOut(
        user=UserOut(
            id=user.id,
            email=user.email,
            is_local=user.is_local,
            email_verified=user.email_verified_at is not None,
        ),
        profile=ProfileOut.model_validate(user.profile),
        settings=SettingsOut.model_validate(user.settings),
    )


async def update_profile(db: AsyncSession, user_id: UUID, data: ProfileUpdate) -> ProfileOut:
    profile = await db.get(Profile, user_id)
    if profile is None:
        raise NotFoundError()
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, name, value)
    await db.flush()
    await db.refresh(profile)
    return ProfileOut.model_validate(profile)


async def get_settings_for(db: AsyncSession, user_id: UUID) -> SettingsOut:
    user_settings = await db.get(UserSettings, user_id)
    if user_settings is None:
        raise NotFoundError()
    return SettingsOut.model_validate(user_settings)


async def update_settings(db: AsyncSession, user_id: UUID, data: SettingsUpdate) -> SettingsOut:
    user_settings = await db.get(UserSettings, user_id)
    if user_settings is None:
        raise NotFoundError()
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(user_settings, name, value)
    await db.flush()
    await db.refresh(user_settings)
    return SettingsOut.model_validate(user_settings)


def list_voices() -> list[VoiceOut]:
    return [VoiceOut(id=voice.id, label=voice.label) for voice in VOICES]
