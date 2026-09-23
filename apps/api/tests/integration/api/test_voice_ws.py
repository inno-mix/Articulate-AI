"""Voice session WebSocket integration tests (voice-and-pronunciation.md §2, Task 3.4)."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
import wsproto.events
from fastapi import FastAPI
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MessageRole, PracticeMode, SessionStatus
from app.domain.limits import HANDS_FREE_IDLE_SECONDS, MAX_USER_TURNS, VOICE_TURN_MAX_SECONDS
from app.llm.base import LLMUsage
from app.llm.errors import LLMUnavailableError
from app.models import Message, PracticeSession, UsageEvent, User
from app.schemas.json_types import SpeechWord
from app.services.locks import voice_session_lock_key
from app.voice.base import TranscriptEvent
from app.voice.fake import FakeSpeechToText, FakeTextToSpeech
from tests.factories import make_scenario, make_session, make_user


class FakeClock:
    def __init__(self) -> None:
        self.value = 1_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _FailingLLM:
    provider = "fake"
    model = "fake"

    async def stream_chat(self, **_kwargs: object):
        raise LLMUnavailableError()
        yield ""  # pragma: no cover -- makes this an async generator function

    async def complete_text(self, **_kwargs: object) -> str:
        raise LLMUnavailableError()

    async def generate_structured(self, **_kwargs: object):  # type: ignore[no-untyped-def]
        raise LLMUnavailableError()

    def last_usage(self) -> LLMUsage | None:
        return None


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(autouse=True)
def _wire_voice_clock(app: FastAPI, clock: FakeClock) -> None:
    app.state.voice_clock = clock


@asynccontextmanager
async def voice_ws_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """A client that can open voice WebSockets against `app`.

    Deliberately NOT a pytest fixture: `ASGIWebSocketTransport`'s internal anyio task group must
    be entered and exited in the same asyncio Task, and pytest-asyncio runs an async-generator
    fixture's setup and teardown in different tasks — tripping anyio's cancel-scope check on
    teardown. Used as `async with voice_ws_client(app) as ws_client:` directly in each test.
    """
    transport = ASGIWebSocketTransport(app)
    async with transport, httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _set_stt(app: FastAPI, stt: FakeSpeechToText) -> None:
    app.state.stt_factory = lambda: stt


def _set_tts(app: FastAPI, tts: FakeTextToSpeech) -> None:
    app.state.tts_factory = lambda: tts


async def _make_voice_session(db: AsyncSession, user_id: object) -> PracticeSession:
    scenario = await make_scenario(db, slug=f"voice-{uuid4().hex[:8]}")
    session = await make_session(
        db, user_id=user_id, scenario_id=scenario.id, mode=PracticeMode.VOICE
    )
    await db.commit()
    return session


def _ws_url(session_id: object) -> str:
    return f"/api/v1/sessions/{session_id}/voice"


async def _recv_json(ws: object) -> dict:
    """Receive the next *text* frame, skipping any binary (audio) frames in between."""
    while True:
        event = await ws.receive()  # type: ignore[attr-defined]
        if isinstance(event, wsproto.events.TextMessage):
            return json.loads(event.data)  # type: ignore[no-any-return]


async def _drain_until(ws: object, event_type: str, *, max_events: int = 50) -> list[dict]:
    """Receive text events (skipping binary/audio frames) until one of type `event_type`."""
    events = []
    for _ in range(max_events):
        event = await _recv_json(ws)
        events.append(event)
        if event["type"] == event_type:
            return events
    raise AssertionError(f"never saw {event_type!r}; got {events}")


async def _drain_until_with_audio(
    ws: object, event_type: str, *, max_events: int = 50
) -> tuple[list[dict], list[bytes]]:
    """Like `_drain_until`, but also returns any binary (audio) frames seen along the way."""
    events: list[dict] = []
    audio: list[bytes] = []
    for _ in range(max_events):
        event = await ws.receive()  # type: ignore[attr-defined]
        if isinstance(event, wsproto.events.BytesMessage):
            audio.append(event.data)
            continue
        assert isinstance(event, wsproto.events.TextMessage)
        parsed = json.loads(event.data)
        events.append(parsed)
        if parsed["type"] == event_type:
            return events, audio
    raise AssertionError(f"never saw {event_type!r}; got {events}")


async def _connect_and_expect_close(
    ws_client: httpx.AsyncClient, session_id: object, expected_code: int
) -> None:
    seen_code: int | None = None
    try:
        async with aconnect_ws(_ws_url(session_id), ws_client) as ws:
            await ws.receive_text()
    except* WebSocketDisconnect as eg:
        seen_code = eg.exceptions[0].code
    assert seen_code == expected_code


# -- handshake -----------------------------------------------------------------------------


async def test_rejects_text_mode_session_with_4409(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="text-mode-voice-ws")
    session = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, mode=PracticeMode.TEXT
    )
    await db.commit()

    async with voice_ws_client(app) as ws_client:
        await _connect_and_expect_close(ws_client, session.id, 4409)


async def test_rejects_other_users_session_with_4404(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    other = await make_user(db, "other-voice@example.com")
    session = await _make_voice_session(db, other.id)

    async with voice_ws_client(app) as ws_client:
        await _connect_and_expect_close(ws_client, session.id, 4404)


async def test_second_connection_is_rejected_with_4409(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client):
        await _connect_and_expect_close(ws_client, session.id, 4409)


async def test_start_returns_ready_with_stt_model(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        ready = await _recv_json(ws)
        assert ready == {"type": "ready", "state": "idle", "stt_model": "fake"}


# -- turns -----------------------------------------------------------------------------------


async def test_ptt_turn_saves_user_message_with_speech_and_streams_reply(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText())
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        await ws.send_text(json.dumps({"type": "ptt_down"}))
        state = await _recv_json(ws)
        assert state == {"type": "state", "value": "listening"}
        for _ in range(3):
            await ws.send_bytes(b"\x00\x01" * 1600)
        await ws.send_text(json.dumps({"type": "ptt_up"}))

        events, audio_chunks = await _drain_until_with_audio(ws, "audio_end")
        assert {"type": "state", "value": "thinking"} in events
        user_turn = next(e for e in events if e["type"] == "user_turn")
        assert user_turn["message"]["content"] == "hello um there"
        assert any(e["type"] == "assistant_delta" for e in events)
        assert {"type": "state", "value": "speaking"} in events
        assert audio_chunks == [b"\x00" * 2400]

        assistant_turn = await _drain_until(ws, "assistant_turn")
        assert assistant_turn[-1]["message"]["role"] == "assistant"
        idle = await _recv_json(ws)
        assert idle == {"type": "state", "value": "idle"}

    speech = await db.scalar(
        select(Message.speech).where(
            Message.session_id == session.id, Message.role == MessageRole.USER
        )
    )
    assert speech is not None
    assert [w["word"] for w in speech["words"]] == ["hello", "um", "there"]
    assert speech["words"][1]["is_filler"] is True


async def test_hands_free_turn_ends_on_end_of_turn(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText())
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "hands_free"}))
        ready = await _recv_json(ws)
        assert ready["state"] == "listening"
        await _recv_json(ws)  # state: listening (from _enter_listening)
        for _ in range(5):
            await ws.send_bytes(b"\x00\x01" * 1600)

        events = await _drain_until(ws, "user_turn")
        assert events[-1]["message"]["content"] == "hello um there"


async def test_audio_ignored_while_idle_in_ptt_mode(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText())
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        for _ in range(5):
            await ws.send_bytes(b"\x00\x01" * 1600)
        await ws.send_text(json.dumps({"type": "ping"}))
        pong = await _recv_json(ws)
        assert pong == {"type": "pong"}

    count = await db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session.id)
    )
    assert count == 0


async def test_filler_only_turn_is_not_saved(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    script = [
        TranscriptEvent(
            kind="final",
            text="um",
            words=[SpeechWord(word="um", start=0.0, end=0.2, confidence=0.9, is_filler=True)],
        ),
        TranscriptEvent(kind="end_of_turn", text=""),
    ]
    _set_stt(app, FakeSpeechToText(script=script))
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "hands_free"}))
        await _recv_json(ws)  # ready
        await _recv_json(ws)  # state listening
        for _ in range(5):
            await ws.send_bytes(b"\x00\x01" * 1600)
        # back to listening, no user_turn in between
        state = await _recv_json(ws)
        assert state == {"type": "state", "value": "listening"}

    count = await db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session.id)
    )
    assert count == 0


async def test_llm_error_sends_nonfatal_error_and_returns_to_idle(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText())
    _set_tts(app, FakeTextToSpeech())
    app.state.llm_factory = lambda: _FailingLLM()

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        await ws.send_text(json.dumps({"type": "ptt_down"}))
        await _recv_json(ws)  # state listening
        for _ in range(3):
            await ws.send_bytes(b"\x00\x01" * 1600)
        await ws.send_text(json.dumps({"type": "ptt_up"}))

        events = await _drain_until(ws, "error")
        assert events[-1]["code"] == "llm_unavailable"
        assert events[-1]["fatal"] is False
        idle = await _recv_json(ws)
        assert idle == {"type": "state", "value": "idle"}

    count = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.session_id == session.id, Message.role == MessageRole.USER)
    )
    assert count == 1
    assistant_count = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.session_id == session.id, Message.role == MessageRole.ASSISTANT)
    )
    assert assistant_count == 0


async def test_turn_limit_sends_limit_event(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    session.user_turns = MAX_USER_TURNS
    await db.commit()
    _set_stt(app, FakeSpeechToText())
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        await ws.send_text(json.dumps({"type": "ptt_down"}))
        await _recv_json(ws)  # state listening
        for _ in range(3):
            await ws.send_bytes(b"\x00\x01" * 1600)
        await ws.send_text(json.dumps({"type": "ptt_up"}))

        events = await _drain_until(ws, "limit")
        assert events[-1] == {"type": "limit", "reason": "turn_limit_reached"}


async def test_end_session_message_ends_and_queues_report(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    session.user_turns = 2
    await db.commit()

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        await ws.send_text(json.dumps({"type": "end_session"}))
        ended = await _recv_json(ws)
        assert ended["type"] == "session_ended"
        assert ended["status"] == "ended"
        assert ended["report_status"] == "pending"

    await db.refresh(session)
    assert session.status == SessionStatus.ENDED


async def test_bad_message_sends_error_and_keeps_socket_open(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        await ws.send_text("not json at all")
        error = await _recv_json(ws)
        assert error == {
            "type": "error",
            "code": "bad_message",
            "message": "Could not parse that message.",
            "fatal": False,
        }
        await ws.send_text(json.dumps({"type": "ping"}))
        pong = await _recv_json(ws)
        assert pong == {"type": "pong"}


async def test_turn_too_long_is_finalized(
    app: FastAPI, db: AsyncSession, local_user: User, clock: FakeClock
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText(silent=True))
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)  # ready
        await ws.send_text(json.dumps({"type": "ptt_down"}))
        await _recv_json(ws)  # state listening

        clock.advance(VOICE_TURN_MAX_SECONDS + 1)
        events = await _drain_until(ws, "limit")
        assert events[-1] == {"type": "limit", "reason": "turn_too_long"}
        idle = await _recv_json(ws)
        assert idle == {"type": "state", "value": "idle"}


async def test_usage_events_recorded_for_stt_tts_llm(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText())
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)
        await ws.send_text(json.dumps({"type": "ptt_down"}))
        await _recv_json(ws)
        for _ in range(3):
            await ws.send_bytes(b"\x00\x01" * 1600)
        await ws.send_text(json.dumps({"type": "ptt_up"}))
        await _drain_until(ws, "assistant_turn")
        await _recv_json(ws)  # state idle

    kinds = await db.scalars(select(UsageEvent.kind).where(UsageEvent.user_id == local_user.id))
    assert {"stt", "tts", "llm"} <= {k.value for k in kinds}


async def test_audio_sent_while_stt_is_opening_is_not_lost(
    app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    session = await _make_voice_session(db, local_user.id)
    stt = FakeSpeechToText(open_delay_s=0.2)
    _set_stt(app, stt)
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "push_to_talk"}))
        await _recv_json(ws)
        await ws.send_text(json.dumps({"type": "ptt_down"}))
        await _recv_json(ws)  # state listening
        chunks = [f"chunk-{i}".encode() for i in range(3)]
        for chunk in chunks:
            await ws.send_bytes(chunk)
        await ws.send_text(json.dumps({"type": "ptt_up"}))
        await _drain_until(ws, "assistant_turn")
        await _recv_json(ws)

    assert stt.sessions, "expected a session to have been opened"
    assert stt.sessions[0].received_chunks[:3] == chunks


async def test_hands_free_pauses_after_idle_and_resumes(
    app: FastAPI, db: AsyncSession, local_user: User, clock: FakeClock
) -> None:
    session = await _make_voice_session(db, local_user.id)
    _set_stt(app, FakeSpeechToText(silent=True))
    _set_tts(app, FakeTextToSpeech())

    async with voice_ws_client(app) as ws_client, aconnect_ws(_ws_url(session.id), ws_client) as ws:
        await ws.send_text(json.dumps({"type": "start", "input_mode": "hands_free"}))
        await _recv_json(ws)  # ready
        await _recv_json(ws)  # state listening

        clock.advance(HANDS_FREE_IDLE_SECONDS + 1)
        idle = await _drain_until(ws, "paused")
        assert {"type": "state", "value": "idle"} in idle
        assert idle[-1] == {"type": "paused", "reason": "no_speech"}

        await ws.send_text(json.dumps({"type": "resume"}))
        listening = await _recv_json(ws)
        assert listening == {"type": "state", "value": "listening"}


async def test_delete_session_with_open_voice_socket_returns_409(
    client: httpx.AsyncClient, app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    # Exercises delete_session()'s real check (the voice:session:<id> Redis key), the same key
    # VoiceSessionRelay._acquire_lock() sets — without a live concurrent WS connection: that
    # combination (an always-on relay task using its own `session_factory` sessions at the same
    # time as this test's HTTP call uses the request-scoped `db` session, both bound to the one
    # shared test connection) leaves this test's own `session` ORM object with expired attributes
    # after the request's own rollback — a test-harness limitation unrelated to delete_session()'s
    # own logic, which this still exercises directly. `session_id` is captured up front (a plain
    # UUID, not a lazy-loadable ORM attribute) to sidestep that entirely.
    session = await _make_voice_session(db, local_user.id)
    session_id = session.id
    redis: Redis = app.state.redis
    await redis.set(voice_session_lock_key(session_id), "1", nx=True, ex=30)
    try:
        response = await client.delete(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "session_in_use"
    finally:
        await redis.delete(voice_session_lock_key(session_id))
