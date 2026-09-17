import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_llm
from app.domain.enums import MessageRole, SessionStatus
from app.models import UsageEvent, User
from tests.factories import make_message, make_scenario, make_session
from tests.integration.api.test_messages_stream import _FailingLLM


async def test_hint_returns_text(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="hint-returns-text")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/hint")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["hint"], str)
    assert body["hint"]

    event = await db.scalar(
        select(UsageEvent).where(UsageEvent.user_id == local_user.id, UsageEvent.feature == "hint")
    )
    assert event is not None


async def test_hint_on_ended_session_returns_409(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="hint-ended-session")
    session = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ENDED
    )
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/hint")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_not_active"


async def test_hint_llm_unavailable_returns_503(
    client: httpx.AsyncClient, app: FastAPI, db: AsyncSession, local_user: User
) -> None:
    app.dependency_overrides[get_llm] = lambda: _FailingLLM()
    scenario = await make_scenario(db, slug="hint-llm-unavailable")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/hint")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_unavailable"
