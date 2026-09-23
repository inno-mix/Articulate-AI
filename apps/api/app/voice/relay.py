"""Voice session WebSocket relay (voice-and-pronunciation.md §2, binding).

DB sessions are opened only to load context or save a message, never held across an STT/LLM/TTS
await (testing-strategy.md §2 event-loop rule; same discipline as app/services/chat.py).
"""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionFactory
from app.core.errors import (
    AppError,
    LLMAuthFailedAppError,
    LLMInvalidOutputAppError,
    LLMNotConfiguredAppError,
    LLMRateLimitedAppError,
    LLMUnavailableAppError,
    SpeechUnavailableError,
)
from app.domain.enums import (
    MessageRole,
    MessageSource,
    SessionStatus,
    UsageKind,
    VoiceInputMode,
)
from app.domain.limits import (
    HANDS_FREE_IDLE_SECONDS,
    MAX_USER_TURNS,
    VOICE_SESSION_MAX_SECONDS,
    VOICE_TURN_MAX_SECONDS,
)
from app.llm.base import LLMService
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMInvalidOutputError,
    LLMNotConfiguredError,
    LLMRateLimitedError,
    LLMUnavailableError,
)
from app.llm.generation import TEMPERATURE
from app.llm.prompts import render_prompt
from app.models import Message, PracticeSession, Scenario, User
from app.schemas.json_types import SpeechData, SpeechWord
from app.schemas.session import MessageOut
from app.services import sessions as sessions_service
from app.services import usage as usage_service
from app.services.chat import build_history
from app.services.locks import voice_session_lock_key
from app.voice.base import SpeechToText, SpeechToTextSession, TextToSpeech
from app.voice.protocol import (
    AssistantDelta,
    AssistantTurn,
    AudioEnd,
    CancelTurn,
    EndSession,
    Error,
    Limit,
    Paused,
    Ping,
    Pong,
    ProtocolError,
    PttDown,
    PttUp,
    Ready,
    Resume,
    ServerEvent,
    SessionEnded,
    Start,
    State,
    Transcript,
    UserTurn,
    parse_client_message,
)
from app.voice.sentences import SentenceSplitter

log = structlog.get_logger(__name__)

WS_CLOSE_SESSION_NOT_FOUND = 4404
WS_CLOSE_SESSION_UNAVAILABLE = 4409

LOCK_TTL_S = 30
LOCK_REFRESH_S = 10
TICK_S = 0.1
PTT_UP_FINAL_WAIT_S = 2.0
MAX_BUFFERED_CHUNKS = 50  # ~5s at the documented ~100ms/chunk mic cadence
BYTES_PER_SECOND_16K_MONO_PCM16 = 32_000
MAX_KEYTERMS = 20

_LLM_APP_ERRORS: dict[type[LLMError], type[AppError]] = {
    LLMUnavailableError: LLMUnavailableAppError,
    LLMRateLimitedError: LLMRateLimitedAppError,
    LLMAuthError: LLMAuthFailedAppError,
    LLMInvalidOutputError: LLMInvalidOutputAppError,
    LLMNotConfiguredError: LLMNotConfiguredAppError,
}


def _to_app_error(exc: LLMError) -> AppError:
    return _LLM_APP_ERRORS.get(type(exc), LLMUnavailableAppError)()


@dataclass
class VoiceDeps:
    session_factory: SessionFactory
    redis: Redis
    settings: Settings
    stt: SpeechToText
    tts: TextToSpeech
    llm: LLMService
    clock: Callable[[], float] = time.monotonic


async def _sentence_source(queue: asyncio.Queue[str | None]) -> AsyncIterator[str]:
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item


@dataclass
class _TurnState:
    words: list[SpeechWord] = field(default_factory=list)
    audio_bytes: int = 0
    started_at: float = 0.0


class VoiceSessionRelay:
    def __init__(self, ws: WebSocket, *, user: User, session_id: UUID, deps: VoiceDeps) -> None:
        self.ws = ws
        self.user = user
        self.session_id = session_id
        self.deps = deps

        self._send_lock = asyncio.Lock()
        self._state: Literal["idle", "listening", "thinking", "speaking"] = "idle"
        self._input_mode: VoiceInputMode | None = None
        self._started = False
        self._paused = False
        self._closed = False
        self._finalizing = False
        self._turn_limit_reached = False
        self._lock_acquired = False

        self._stt_session: SpeechToTextSession | None = None
        self._audio_buffer: list[bytes] = []
        self._turn = _TurnState()
        self._turn_finalized_event: asyncio.Event | None = None
        self._ptt_up_requested = False

        self._keyterms: list[str] = []
        self._user_turns = 0
        self._session_start_monotonic = 0.0
        self._last_transcript_at = 0.0
        self._last_lock_refresh = 0.0

        self._tg: asyncio.TaskGroup | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._background_tasks: list[asyncio.Task[None]] = []

    # -- lifecycle -----------------------------------------------------

    async def run(self) -> None:
        await self.ws.accept()
        if not await self._validate():
            return
        if not await self._acquire_lock():
            await self.ws.close(code=WS_CLOSE_SESSION_UNAVAILABLE)
            return
        self._lock_acquired = True
        self._session_start_monotonic = self.deps.clock()
        self._last_lock_refresh = self.deps.clock()

        try:
            async with asyncio.TaskGroup() as tg:
                self._tg = tg
                self._receive_task = tg.create_task(self._receive_loop())
                self._heartbeat_task = tg.create_task(self._heartbeat_loop())
        except* Exception as eg:  # defensive: never crash the ASGI worker
            for exc in eg.exceptions:
                log.error("voice_relay_error", session_id=str(self.session_id), exc_info=exc)
        finally:
            if self._stt_session is not None:
                with contextlib.suppress(Exception):
                    await self._stt_session.close()
            await self._release_lock()

    async def _validate(self) -> bool:
        async with self.deps.session_factory() as db:
            session = await db.get(PracticeSession, self.session_id)
            if session is None or session.user_id != self.user.id:
                await self.ws.close(code=WS_CLOSE_SESSION_NOT_FOUND)
                return False
            if session.mode.value != "voice" or session.status != SessionStatus.ACTIVE:
                await self.ws.close(code=WS_CLOSE_SESSION_UNAVAILABLE)
                return False
            scenario = await db.get(Scenario, session.scenario_id)
            self._keyterms = list((scenario.keyterms if scenario else [])[:MAX_KEYTERMS])
            self._user_turns = session.user_turns
        return True

    async def _acquire_lock(self) -> bool:
        key = voice_session_lock_key(self.session_id)
        acquired = await self.deps.redis.set(key, "1", nx=True, ex=LOCK_TTL_S)
        return bool(acquired)

    async def _release_lock(self) -> None:
        if self._lock_acquired:
            await self.deps.redis.delete(voice_session_lock_key(self.session_id))
            self._lock_acquired = False

    def _spawn(self, coro: Coroutine[object, object, None]) -> asyncio.Task[None]:
        """Track every dynamically-spawned task so `_stop()` can cancel stragglers.

        Without this, a task left waiting on something that will never happen (e.g. a hands-free
        STT session opened just before the client disconnects, still waiting on its next event)
        keeps `asyncio.TaskGroup.__aexit__` — and so `run()` — from ever returning.
        """
        if self._tg is None:
            raise RuntimeError("_spawn() called before the relay's TaskGroup exists")
        task = self._tg.create_task(coro)
        self._background_tasks.append(task)
        return task

    def _stop(self) -> None:
        self._closed = True
        current = asyncio.current_task()
        if self._heartbeat_task is not None and self._heartbeat_task is not current:
            self._heartbeat_task.cancel()
        if self._receive_task is not None and self._receive_task is not current:
            self._receive_task.cancel()
        for task in self._background_tasks:
            if task is not current and not task.done():
                task.cancel()

    # -- sending ---------------------------------------------------------

    async def _send(self, event: ServerEvent) -> None:
        async with self._send_lock:
            if self._closed:
                return
            await self.ws.send_text(event.model_dump_json())

    async def _send_bytes(self, data: bytes) -> None:
        async with self._send_lock:
            if self._closed:
                return
            await self.ws.send_bytes(data)

    # -- receive loop ------------------------------------------------------

    async def _receive_loop(self) -> None:
        try:
            while not self._closed:
                message = await self.ws.receive()
                if message["type"] == "websocket.disconnect":
                    self._closed = True
                    return
                if message.get("bytes") is not None:
                    await self._on_audio(message["bytes"])
                elif message.get("text") is not None:
                    await self._on_text(message["text"])
        except asyncio.CancelledError:
            pass
        finally:
            self._stop()

    async def _on_text(self, raw: str) -> None:
        try:
            msg = parse_client_message(raw)
        except ProtocolError:
            await self._send(
                Error(code="bad_message", message="Could not parse that message.", fatal=False)
            )
            return

        match msg:
            case Start():
                await self._handle_start(msg)
            case PttDown():
                await self._handle_ptt_down()
            case PttUp():
                await self._handle_ptt_up()
            case CancelTurn():
                await self._handle_cancel_turn()
            case Resume():
                await self._handle_resume()
            case EndSession():
                await self._handle_end_session()
            case Ping():
                await self._send(Pong())

    async def _on_audio(self, chunk: bytes) -> None:
        if self._state != "listening" or self._paused:
            return
        self._turn.audio_bytes += len(chunk)
        if self._stt_session is None:
            self._audio_buffer.append(chunk)
            if len(self._audio_buffer) > MAX_BUFFERED_CHUNKS:
                self._audio_buffer.pop(0)
            return
        await self._stt_session.send_audio(chunk)

    # -- client message handlers -----------------------------------------

    async def _handle_start(self, msg: Start) -> None:
        if self._started:
            return
        self._started = True
        self._input_mode = msg.input_mode
        initial_state: Literal["idle", "listening"] = (
            "listening" if msg.input_mode == VoiceInputMode.HANDS_FREE else "idle"
        )
        await self._send(Ready(state=initial_state, stt_model=self.deps.stt.model))
        if msg.input_mode == VoiceInputMode.HANDS_FREE:
            await self._enter_listening()

    async def _handle_ptt_down(self) -> None:
        if self._input_mode != VoiceInputMode.PUSH_TO_TALK or self._state != "idle" or self._paused:
            return
        await self._enter_listening()

    async def _handle_ptt_up(self) -> None:
        if self._input_mode != VoiceInputMode.PUSH_TO_TALK or self._state != "listening":
            return
        event = asyncio.Event()
        self._turn_finalized_event = event
        if self._stt_session is not None:
            await self._stt_session.finalize()
        else:
            # STT is still opening (open_session() hasn't resolved yet): _open_stt_session()
            # finalizes on our behalf as soon as the session is ready, so send_audio() isn't the
            # only thing racing the open — see `_ptt_up_requested`.
            self._ptt_up_requested = True
        try:
            await asyncio.wait_for(event.wait(), timeout=PTT_UP_FINAL_WAIT_S)
        except TimeoutError:
            await self._finalize_turn()

    async def _handle_cancel_turn(self) -> None:
        if self._state != "listening":
            return
        self._finalizing = True
        session, self._stt_session = self._stt_session, None
        if session is not None:
            await session.close()
        self._turn = _TurnState()
        self._audio_buffer.clear()
        self._finalizing = False
        if self._input_mode == VoiceInputMode.HANDS_FREE:
            await self._enter_listening()
        else:
            await self._enter_idle()

    async def _handle_resume(self) -> None:
        if self._input_mode != VoiceInputMode.HANDS_FREE or not self._paused:
            return
        await self._enter_listening()

    async def _handle_end_session(self) -> None:
        await self._end_session_and_close()

    # -- state transitions -------------------------------------------------

    async def _enter_idle(self) -> None:
        self._state = "idle"
        self._paused = False
        await self._send(State(value="idle"))

    async def _enter_listening(self) -> None:
        if self._turn_limit_reached or self._closed:
            return
        self._state = "listening"
        self._paused = False
        await self._send(State(value="listening"))
        self._turn = _TurnState(started_at=self.deps.clock())
        self._last_transcript_at = self.deps.clock()
        self._audio_buffer.clear()
        self._stt_session = None
        self._ptt_up_requested = False
        if self._tg is None:
            return
        self._spawn(self._open_stt_session())

    async def _open_stt_session(self) -> None:
        try:
            session = await self.deps.stt.open_session(keyterms=self._keyterms)
        except SpeechUnavailableError:
            await self._send(
                Error(
                    code="speech_unavailable",
                    message="The speech service is unavailable right now.",
                    fatal=False,
                )
            )
            await self._back_to_resting_state()
            return

        if self._state != "listening":
            await session.close()
            return

        self._stt_session = session
        buffered, self._audio_buffer = self._audio_buffer, []
        for chunk in buffered:
            await session.send_audio(chunk)

        if self._tg is None:
            return
        self._spawn(self._consume_stt_events(session))

        if self._ptt_up_requested:
            self._ptt_up_requested = False
            await session.finalize()

    async def _consume_stt_events(self, session: SpeechToTextSession) -> None:
        try:
            async for event in session.events():
                if session is not self._stt_session:
                    return
                if event.kind == "interim":
                    self._last_transcript_at = self.deps.clock()
                    await self._send(Transcript(text=event.text, is_final=False))
                elif event.kind == "final":
                    self._last_transcript_at = self.deps.clock()
                    self._turn.words.extend(event.words)
                elif event.kind == "end_of_turn":
                    await self._finalize_turn()
                    return
        except SpeechUnavailableError:
            await self._send(
                Error(
                    code="speech_unavailable",
                    message="The speech service is unavailable right now.",
                    fatal=False,
                )
            )
            await self._back_to_resting_state()

    async def _back_to_resting_state(self) -> None:
        self._stt_session = None
        if self._input_mode == VoiceInputMode.HANDS_FREE:
            await self._enter_listening()
        else:
            await self._enter_idle()

    # -- turn finalisation ---------------------------------------------------

    async def _finalize_turn(self) -> None:
        if self._finalizing or self._state != "listening":
            return
        self._finalizing = True
        if self._turn_finalized_event is not None:
            self._turn_finalized_event.set()

        session, self._stt_session = self._stt_session, None
        if session is not None:
            await session.close()

        turn = self._turn
        self._turn = _TurnState()
        if turn.audio_bytes > 0:
            await self._record_stt_usage(turn.audio_bytes)

        non_filler = [w for w in turn.words if not w.is_filler]
        if not non_filler:
            self._finalizing = False
            if self._input_mode == VoiceInputMode.HANDS_FREE:
                await self._enter_listening()
            else:
                await self._enter_idle()
            return

        if self._user_turns >= MAX_USER_TURNS:
            self._finalizing = False
            self._turn_limit_reached = True
            await self._send(Limit(reason="turn_limit_reached"))
            await self._enter_idle()
            return

        content = " ".join(word.word for word in turn.words)
        duration_s = max(turn.words[-1].end - turn.words[0].start, 0.0)
        speech = SpeechData(words=turn.words, duration_s=duration_s, stt_model=self.deps.stt.model)

        async with self.deps.session_factory() as db:
            session_row = await db.get(PracticeSession, self.session_id)
            if session_row is None:
                return
            message = await sessions_service.add_message(
                db,
                session_row,
                role=MessageRole.USER,
                content=content,
                source=MessageSource.VOICE,
                speech=speech.model_dump(mode="json"),
            )
            message_out = MessageOut.model_validate(message)
            self._user_turns = session_row.user_turns
            prior_messages = list(
                await db.scalars(
                    select(Message)
                    .where(Message.session_id == self.session_id, Message.id != message.id)
                    .order_by(Message.seq)
                )
            )
            await db.commit()

        await self._send(UserTurn(message=message_out))
        self._state = "thinking"
        await self._send(State(value="thinking"))
        self._finalizing = False

        if self._tg is None:
            return
        self._spawn(self._process_assistant_reply(content, prior_messages))

    async def _record_stt_usage(self, audio_bytes: int) -> None:
        async with self.deps.session_factory() as db:
            await usage_service.record_usage(
                db,
                user_id=self.user.id,
                kind=UsageKind.STT,
                feature="voice_turn",
                provider=self.deps.settings.stt_provider,
                model=self.deps.stt.model,
                audio_seconds=audio_bytes / BYTES_PER_SECOND_16K_MONO_PCM16,
            )
            await db.commit()

    # -- assistant reply: LLM -> sentence splitter -> TTS --------------------

    async def _process_assistant_reply(
        self, user_content: str, prior_messages: list[Message]
    ) -> None:
        async with self.deps.session_factory() as db:
            session_row = await db.get(PracticeSession, self.session_id)
            if session_row is None:
                return
            scenario = await db.get(Scenario, session_row.scenario_id)
            if scenario is None:
                return
            rendered = render_prompt(
                "roleplay_system",
                persona=scenario.persona,
                scenario=_scenario_context(scenario),
                learner=_learner_context(self.user),
                mode="voice",
                coach_notes=[],
            )

        history = build_history(prior_messages)
        sentence_queue: asyncio.Queue[str | None] = asyncio.Queue()
        splitter = SentenceSplitter()
        llm_error: LLMError | None = None
        collected: list[str] = []

        async def produce() -> None:
            nonlocal llm_error
            try:
                async for delta in self.deps.llm.stream_chat(
                    system=rendered.text,
                    history=history,
                    user_message=user_content,
                    temperature=TEMPERATURE["roleplay"],
                ):
                    collected.append(delta)
                    await self._send(AssistantDelta(text=delta))
                    for chunk in splitter.push(delta):
                        await sentence_queue.put(chunk)
                for chunk in splitter.flush():
                    await sentence_queue.put(chunk)
            except LLMError as exc:
                llm_error = exc
            finally:
                await sentence_queue.put(None)

        tts_error: SpeechUnavailableError | None = None
        speaking_started = False

        async def consume() -> None:
            nonlocal tts_error, speaking_started
            try:
                async for audio_chunk in self.deps.tts.synthesize(
                    voice=self.user.settings.tts_voice,
                    sentences=_sentence_source(sentence_queue),
                ):
                    if not speaking_started:
                        speaking_started = True
                        self._state = "speaking"
                        await self._send(State(value="speaking"))
                    await self._send_bytes(audio_chunk)
            except SpeechUnavailableError as exc:
                tts_error = exc

        await asyncio.gather(produce(), consume())

        if llm_error is not None:
            app_error = _to_app_error(llm_error)
            await self._send(Error(code=app_error.code, message=app_error.message, fatal=False))
            await self._back_to_resting_state()
            return
        if tts_error is not None:
            await self._send(
                Error(code="speech_unavailable", message="Couldn't play the reply.", fatal=False)
            )
            await self._back_to_resting_state()
            return

        await self._send(AudioEnd())
        full_text = "".join(collected)

        async with self.deps.session_factory() as db:
            session_row = await db.get(PracticeSession, self.session_id)
            if session_row is None:
                return
            message = await sessions_service.add_message(
                db,
                session_row,
                role=MessageRole.ASSISTANT,
                content=full_text,
                source=MessageSource.VOICE,
            )
            message_out = MessageOut.model_validate(message)
            llm_usage = self.deps.llm.last_usage()
            await usage_service.record_usage(
                db,
                user_id=self.user.id,
                kind=UsageKind.LLM,
                feature="voice_turn",
                provider=self.deps.llm.provider,
                model=self.deps.llm.model,
                input_tokens=llm_usage.input_tokens if llm_usage else None,
                output_tokens=llm_usage.output_tokens if llm_usage else None,
                latency_ms=llm_usage.latency_ms if llm_usage else None,
            )
            await usage_service.record_usage(
                db,
                user_id=self.user.id,
                kind=UsageKind.TTS,
                feature="voice_turn",
                provider=self.deps.settings.tts_provider,
                model=self.user.settings.tts_voice,
                characters=len(full_text),
            )
            await db.commit()

        await self._send(AssistantTurn(message=message_out))
        await self._back_to_resting_state()

    # -- ending the session --------------------------------------------------

    async def _end_session_and_close(self) -> None:
        async with self.deps.session_factory() as db:
            result = await sessions_service.end_session(db, self.user.id, self.session_id)
        await self._send(SessionEnded(status=result.status, report_status=result.report_status))
        await self.ws.close(code=1000)
        self._stop()

    # -- heartbeat: lock refresh + timeouts -----------------------------------

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(TICK_S)
                if self._closed:
                    return
                await self._maybe_refresh_lock()
                await self._check_session_too_long()
                if self._closed:
                    return
                await self._check_turn_too_long()
                await self._check_hands_free_idle()
        except asyncio.CancelledError:
            pass

    async def _maybe_refresh_lock(self) -> None:
        now = self.deps.clock()
        if now - self._last_lock_refresh >= LOCK_REFRESH_S:
            await self.deps.redis.expire(voice_session_lock_key(self.session_id), LOCK_TTL_S)
            self._last_lock_refresh = now

    async def _check_session_too_long(self) -> None:
        if self.deps.clock() - self._session_start_monotonic <= VOICE_SESSION_MAX_SECONDS:
            return
        await self._send(Limit(reason="session_too_long"))
        await self._end_session_and_close()

    async def _check_turn_too_long(self) -> None:
        if self._state != "listening" or self._turn.started_at <= 0:
            return
        if self.deps.clock() - self._turn.started_at <= VOICE_TURN_MAX_SECONDS:
            return
        await self._send(Limit(reason="turn_too_long"))
        await self._finalize_turn()

    async def _check_hands_free_idle(self) -> None:
        if (
            self._input_mode != VoiceInputMode.HANDS_FREE
            or self._state != "listening"
            or self._paused
        ):
            return
        if self.deps.clock() - self._last_transcript_at <= HANDS_FREE_IDLE_SECONDS:
            return
        session, self._stt_session = self._stt_session, None
        if session is not None:
            await session.close()
        self._paused = True
        self._state = "idle"
        await self._send(State(value="idle"))
        await self._send(Paused())


def _scenario_context(scenario: Scenario) -> dict[str, str]:
    return {
        "title": scenario.title,
        "summary": scenario.summary,
        "user_objective": scenario.user_objective,
    }


def _learner_context(user: User) -> dict[str, str]:
    return {
        "seniority": user.profile.seniority.value,
        "english_level": user.profile.english_level.value,
    }
