"""Shared FastAPI dependencies. Provider implementations are chosen here."""

from typing import Annotated

from fastapi import Depends
from fastapi.requests import HTTPConnection
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.db import SessionFactory, get_db
from app.core.errors import LocalUserMissingError, SpeechUnavailableError, UnauthorizedError
from app.core.redis import get_redis
from app.domain.constants import LOCAL_USER_ID
from app.llm.base import LLMService
from app.llm.factory import get_llm_service
from app.models import User
from app.voice.base import SpeechToText, TextToSpeech
from app.voice.deepgram_stt import DeepgramSpeechToText
from app.voice.deepgram_tts import DeepgramTextToSpeech
from app.voice.fake import FakeSpeechToText, FakeTextToSpeech


def get_app_settings(conn: HTTPConnection) -> Settings:
    """Settings of the running app (tests can swap them via app.state.settings).

    Takes `HTTPConnection` (the common base of `Request`/`WebSocket`) so this also works as a
    dependency for WebSocket routes (voice-and-pronunciation.md §2).
    """
    settings: Settings = conn.app.state.settings
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
RedisDep = Annotated[Redis, Depends(get_redis)]


def get_session_factory(conn: HTTPConnection) -> SessionFactory:
    """The app's own session factory. Used by the SSE generator and the voice relay, which open
    their own DB sessions rather than holding the request-scoped one open across a stream
    (see `app/services/chat.py`, `app/voice/relay.py`).
    """
    factory: SessionFactory = conn.app.state.session_factory
    return factory


SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]


def get_stt(settings: SettingsDep) -> SpeechToText:
    """Created lazily: a missing key never blocks startup, only the first voice request."""
    if settings.stt_provider == "fake":
        return FakeSpeechToText()
    if settings.deepgram_api_key is None:
        raise SpeechUnavailableError("Deepgram API key is not configured.")
    return DeepgramSpeechToText(
        settings.deepgram_api_key.get_secret_value(), settings.deepgram_stt_model
    )


def get_tts(settings: SettingsDep) -> TextToSpeech:
    """Created lazily: a missing key never blocks startup, only the first voice request."""
    if settings.tts_provider == "fake":
        return FakeTextToSpeech()
    if settings.deepgram_api_key is None:
        raise SpeechUnavailableError("Deepgram API key is not configured.")
    return DeepgramTextToSpeech(settings.deepgram_api_key.get_secret_value())


STTDep = Annotated[SpeechToText, Depends(get_stt)]
TTSDep = Annotated[TextToSpeech, Depends(get_tts)]
