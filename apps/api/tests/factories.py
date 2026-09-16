"""Plain factory functions for test data."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, User, UserSettings

DEFAULT_TTS_VOICE = "aura-2-thalia-en"


async def make_user(db: AsyncSession, email: str, *, is_local: bool = False) -> User:
    user = User(email=email.lower(), is_local=is_local)
    db.add(user)
    await db.flush()
    db.add_all(
        [Profile(user_id=user.id), UserSettings(user_id=user.id, tts_voice=DEFAULT_TTS_VOICE)]
    )
    await db.flush()
    return user
