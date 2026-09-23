"""Voice session WebSocket endpoint (voice-and-pronunciation.md §2).

Dependencies are read straight off `websocket.app.state` rather than via the usual `Depends()`
helpers in `app/deps.py`. Two reasons:
- `get_stt`/`get_tts` raise `SpeechUnavailableError` when no key is configured; FastAPI has no
  exception-to-close-code translation for errors raised while solving WebSocket dependencies (it
  propagates unhandled), so calling them as plain functions here — inside our own try/except —
  is what makes the graceful `WS_CLOSE_SPEECH_UNAVAILABLE` close actually happen.
- `app.state.stt_factory` / `app.state.tts_factory` / `app.state.llm_factory` /
  `app.state.voice_clock` (optional, test-only) let integration tests inject fakes configured per
  test case (custom script, `open_delay_s`, `silent=True`, a broken LLM, …) and a controllable
  clock — something `STT_PROVIDER=fake`/`get_stt` alone can't express, since it only ever builds
  the *default* fake, and `get_llm` similarly can't be swapped via `app.dependency_overrides`
  here (the endpoint never uses `Depends()` for `user`/`db`/`llm`, for the same reason as above:
  a generator-based `Depends()` stays open for the WebSocket's whole lifetime).
"""

import time
from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, WebSocket
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.db import SessionFactory
from app.core.errors import SpeechUnavailableError
from app.deps import get_stt, get_tts
from app.domain.constants import LOCAL_USER_ID
from app.llm.base import LLMService
from app.llm.factory import get_llm_service
from app.models import User
from app.voice.base import SpeechToText, TextToSpeech
from app.voice.relay import VoiceDeps, VoiceSessionRelay

router = APIRouter(tags=["voice"])

WS_CLOSE_NO_LOCAL_USER = 1011
WS_CLOSE_SPEECH_UNAVAILABLE = 1011


async def _load_local_user(session_factory: SessionFactory) -> User | None:
    async with session_factory() as db:
        user: User | None = await db.scalar(
            select(User)
            .where(User.id == LOCAL_USER_ID)
            .options(selectinload(User.profile), selectinload(User.settings))
        )
        return user


@router.websocket("/sessions/{session_id}/voice")
async def voice_session_ws(websocket: WebSocket, session_id: UUID) -> None:
    settings: Settings = websocket.app.state.settings
    redis = websocket.app.state.redis
    session_factory: SessionFactory = websocket.app.state.session_factory
    stt_factory: Callable[[], SpeechToText] | None = getattr(
        websocket.app.state, "stt_factory", None
    )
    tts_factory: Callable[[], TextToSpeech] | None = getattr(
        websocket.app.state, "tts_factory", None
    )
    clock: Callable[[], float] = getattr(websocket.app.state, "voice_clock", time.monotonic)
    llm_factory: Callable[[], LLMService] | None = getattr(websocket.app.state, "llm_factory", None)

    user = await _load_local_user(session_factory)
    if user is None:
        await websocket.accept()
        await websocket.close(code=WS_CLOSE_NO_LOCAL_USER)
        return

    try:
        stt = stt_factory() if stt_factory is not None else get_stt(settings)
        tts = tts_factory() if tts_factory is not None else get_tts(settings)
    except SpeechUnavailableError:
        await websocket.accept()
        await websocket.close(code=WS_CLOSE_SPEECH_UNAVAILABLE)
        return

    if llm_factory is not None:
        llm = llm_factory()
    else:
        async with session_factory() as db:
            llm = await get_llm_service(user, db, settings)

    deps = VoiceDeps(
        session_factory=session_factory,
        redis=redis,
        settings=settings,
        stt=stt,
        tts=tts,
        llm=llm,
        clock=clock,
    )
    relay = VoiceSessionRelay(websocket, user=user, session_id=session_id, deps=deps)
    await relay.run()
