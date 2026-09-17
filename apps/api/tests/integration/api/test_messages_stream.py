from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_llm
from app.domain.enums import MessageRole, SessionStatus
from app.llm.base import LLMUsage
from app.llm.errors import LLMUnavailableError
from app.models import Message, UsageEvent, User
from app.services.locks import lock_key
from tests.factories import make_message, make_scenario, make_session
from tests.helpers.sse import parse_sse


class _FailingLLM:
    provider = "fake"
    model = "fake"

    async def stream_chat(self, **_kwargs: object) -> AsyncIterator[str]:
        raise LLMUnavailableError()
        yield ""  # pragma: no cover -- makes this an async generator function

    async def complete_text(self, **_kwargs: object) -> str:
        raise LLMUnavailableError()

    async def generate_structured(self, **_kwargs: object):  # type: ignore[no-untyped-def]
        raise LLMUnavailableError()

    def last_usage(self) -> LLMUsage | None:
        return None


class _PoisonLLM:
    """Fails the test if the LLM is ever called (used for the crisis path)."""

    provider = "fake"
    model = "fake"

    async def stream_chat(self, **_kwargs: object) -> AsyncIterator[str]:
        pytest.fail("the LLM must not be called on the crisis path")
        yield ""  # pragma: no cover

    async def complete_text(self, **_kwargs: object) -> str:
        pytest.fail("the LLM must not be called on the crisis path")

    async def generate_structured(self, **_kwargs: object):  # type: ignore[no-untyped-def]
        pytest.fail("the LLM must not be called on the crisis path")

    def last_usage(self) -> LLMUsage | None:
        return None


async def test_stream_happy_path_event_order(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="stream-happy-path")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "Hi Dana, got a minute?"}
    )

    assert response.status_code == 200
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "user_message"
    assert names[-2] == "assistant_message"
    assert names[-1] == "done"
    assert "delta" in names
    done_data = events[-1][1]
    assert done_data == {"user_turns": 1, "turns_left": 19}

    count = await db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session.id)
    )
    assert count == 3


async def test_stream_llm_failure_emits_error_and_keeps_user_message(
    client: httpx.AsyncClient, app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    app.dependency_overrides[get_llm] = lambda: _FailingLLM()
    scenario = await make_scenario(db, slug="stream-llm-failure")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "hello"}
    )

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "llm_unavailable"

    count = await db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session.id)
    )
    assert count == 2  # opening line + the user's message; no assistant reply saved


async def test_stream_crisis_message_uses_safety_reply(
    client: httpx.AsyncClient, app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    app.dependency_overrides[get_llm] = lambda: _PoisonLLM()
    scenario = await make_scenario(db, slug="stream-crisis")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "I want to end my life"}
    )

    assert response.status_code == 200
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names == ["user_message", "delta", "assistant_message", "done"]
    assistant_event = events[2][1]
    assert assistant_event["source"] == "system"

    await db.refresh(session)
    assert session.safety_flag is True


async def test_message_on_ended_session_returns_409_json(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="stream-ended-session")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    session.status = SessionStatus.ENDED
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "hello"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_not_active"


async def test_message_over_1000_chars_returns_422(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="stream-too-long")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "x" * 1001}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_turn_limit_returns_409(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="stream-turn-limit")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=20)
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "hello"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "turn_limit_reached"


async def test_concurrent_message_returns_reply_in_progress(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, redis_client: Redis
) -> None:
    scenario = await make_scenario(db, slug="stream-concurrent")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await db.commit()
    await redis_client.set(lock_key(session.id), "1", nx=True, ex=120)

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "hello"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reply_in_progress"

    await redis_client.delete(lock_key(session.id))


async def test_usage_event_recorded_for_reply(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="stream-usage-event")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await db.commit()

    response = await client.post(
        f"/api/v1/sessions/{session.id}/messages", json={"content": "hello"}
    )

    assert response.status_code == 200
    event = await db.scalar(
        select(UsageEvent).where(
            UsageEvent.user_id == local_user.id, UsageEvent.feature == "roleplay"
        )
    )
    assert event is not None
    assert event.provider == "fake"
    assert event.model == "fake"
