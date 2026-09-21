import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MessageRole, SessionStatus
from app.domain.limits import MAX_MESSAGE_CHARS, MAX_USER_TURNS
from app.models import Message, PracticeSession, User
from tests.factories import make_message, make_scenario, make_session


async def test_create_text_session_adds_opening_message(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="opening-line-test", title="Opening line test")
    await db.commit()

    response = await client.post(
        "/api/v1/sessions", json={"scenario_id": str(scenario.id), "mode": "text"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "text"
    assert body["status"] == "active"
    assert body["scenario"] == {"slug": "opening-line-test", "title": "Opening line test"}
    assert len(body["messages"]) == 1
    opening = body["messages"][0]
    assert opening["seq"] == 0
    assert opening["role"] == "assistant"
    assert opening["content"] == "Hi there."
    assert body["limits"] == {
        "max_user_turns": MAX_USER_TURNS,
        "max_message_chars": MAX_MESSAGE_CHARS,
    }

    session = await db.scalar(select(PracticeSession).where(PracticeSession.id == body["id"]))
    assert session is not None
    assert session.llm_provider == "fake"
    assert session.llm_model == "fake"


async def test_create_session_unknown_scenario_returns_404(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.post(
        "/api/v1/sessions",
        json={"scenario_id": "00000000-0000-0000-0000-000000000099", "mode": "text"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_create_session_with_assessment_scenario_returns_404(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="assessment-only", is_assessment=True)
    await db.commit()

    response = await client.post(
        "/api/v1/sessions", json={"scenario_id": str(scenario.id), "mode": "text"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_list_sessions_paginates_newest_first(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="list-paginate")
    for _ in range(3):
        await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await db.commit()

    first = await client.get("/api/v1/sessions", params={"limit": 2})
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second = await client.get(
        "/api/v1/sessions", params={"limit": 2, "cursor": first_body["next_cursor"]}
    )
    second_body = second.json()
    assert len(second_body["items"]) == 1
    assert second_body["next_cursor"] is None

    all_ids = {item["id"] for item in first_body["items"] + second_body["items"]}
    assert len(all_ids) == 3


async def test_list_sessions_filters_by_status(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="list-filter-status")
    active = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ACTIVE
    )
    await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ENDED
    )
    await db.commit()

    response = await client.get("/api/v1/sessions", params={"status": "active"})

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(active.id)}


async def test_get_session_includes_messages_and_limits(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="get-detail")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content="Hi there.")
    await make_message(db, session, role=MessageRole.USER, content="Hello!")
    await db.commit()

    response = await client.get(f"/api/v1/sessions/{session.id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["messages"]) == 2
    assert [m["seq"] for m in body["messages"]] == [0, 1]
    assert body["limits"]["max_user_turns"] == MAX_USER_TURNS


async def test_get_other_users_session_returns_404(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, other_user: User
) -> None:
    scenario = await make_scenario(db, slug="not-my-session")
    session = await make_session(db, user_id=other_user.id, scenario_id=scenario.id)
    await db.commit()

    response = await client.get(f"/api/v1/sessions/{session.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_end_session_with_one_user_turn_is_abandoned(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="end-one-turn")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=1)
    await make_message(db, session, role=MessageRole.USER, content="Hi")
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/end")

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "abandoned", "report_status": None}


async def test_end_session_with_two_user_turns_is_ended(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="end-two-turns")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=2)
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/end")

    assert response.status_code == 200
    # `report_status` is "pending" at the instant `end_session` returns — it's captured before
    # the (fake, synchronous-in-tests) worker run, per api-contract.md §2 Sessions (end).
    assert response.json() == {"status": "ended", "report_status": "pending"}


async def test_end_session_is_idempotent(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="end-idempotent")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=2)
    await db.commit()

    first = await client.post(f"/api/v1/sessions/{session.id}/end")
    second = await client.post(f"/api/v1/sessions/{session.id}/end")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "ended"
    # First call: report just created ("pending"). Second call: it already ran (test broker is
    # synchronous), so ending the same session again reports its current status ("ready").
    assert first.json()["report_status"] == "pending"
    assert second.json()["report_status"] == "ready"


async def test_session_list_includes_overall_score_when_ready(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="list-overall-score")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=2)
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    await db.commit()

    # `end_session` returns "pending" (captured before enqueueing); the test broker then runs the
    # job to completion synchronously, so the report is already "ready" by the time this returns.
    await client.post(f"/api/v1/sessions/{session.id}/end")

    list_response = await client.get("/api/v1/sessions")

    body = list_response.json()
    item = next(i for i in body["items"] if i["id"] == str(session.id))
    assert isinstance(item["overall_score"], int)


async def test_delete_session_removes_it_and_its_messages(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="delete-me")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id)
    await make_message(db, session, role=MessageRole.ASSISTANT, content="Hi there.")
    await db.commit()

    response = await client.delete(f"/api/v1/sessions/{session.id}")

    assert response.status_code == 204
    get_response = await client.get(f"/api/v1/sessions/{session.id}")
    assert get_response.status_code == 404
    remaining = await db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session.id)
    )
    assert remaining == 0


async def test_delete_other_users_session_returns_404(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, other_user: User
) -> None:
    scenario = await make_scenario(db, slug="delete-not-mine")
    session = await make_session(db, user_id=other_user.id, scenario_id=scenario.id)
    await db.commit()

    response = await client.delete(f"/api/v1/sessions/{session.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
