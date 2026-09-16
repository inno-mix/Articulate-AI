from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import seed
from app.core.config import Settings
from app.domain.constants import LOCAL_USER_EMAIL, LOCAL_USER_ID
from app.models import Profile, User, UserSettings
from tests.support.db import LockedSessionFactory


async def test_seed_creates_local_user_profile_and_settings(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings
) -> None:
    await seed(session_factory, settings)

    user = await db.get(User, LOCAL_USER_ID)
    profile = await db.get(Profile, LOCAL_USER_ID)
    user_settings = await db.get(UserSettings, LOCAL_USER_ID)
    assert user is not None
    assert user.email == LOCAL_USER_EMAIL
    assert user.is_local is True
    assert profile is not None
    assert (profile.display_name, profile.english_level, profile.timezone) == ("You", "B2", "UTC")
    assert profile.seniority == "mid"
    assert user_settings is not None
    assert user_settings.default_mode == "text"
    assert user_settings.voice_input_mode == "push_to_talk"
    assert user_settings.tts_voice == settings.deepgram_tts_voice


async def test_seed_is_idempotent(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings
) -> None:
    await seed(session_factory, settings)
    await seed(session_factory, settings)

    count = await db.scalar(select(func.count()).select_from(User))
    assert count == 1
