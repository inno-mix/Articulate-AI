import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RecommendedMode, ScenarioCategory
from app.models import User
from tests.factories import make_scenario


async def test_list_excludes_assessment_scenarios(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    await make_scenario(db, slug="practice-one", is_assessment=False)
    await make_scenario(db, slug="assessment-one", is_assessment=True)
    await db.commit()

    response = await client.get("/api/v1/scenarios")

    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()}
    assert slugs == {"practice-one"}


async def test_list_filters_by_category(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    await make_scenario(db, slug="meeting-one", category=ScenarioCategory.MEETINGS)
    await make_scenario(db, slug="career-one", category=ScenarioCategory.CAREER)
    await db.commit()

    response = await client.get("/api/v1/scenarios", params={"category": "career"})

    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()}
    assert slugs == {"career-one"}


async def test_list_filters_by_difficulty(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    await make_scenario(db, slug="easy-one", difficulty=1)
    await make_scenario(db, slug="hard-one", difficulty=3)
    await db.commit()

    response = await client.get("/api/v1/scenarios", params={"difficulty": 3})

    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()}
    assert slugs == {"hard-one"}


async def test_list_mode_filter_includes_either(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    await make_scenario(db, slug="text-only", recommended_mode=RecommendedMode.TEXT)
    await make_scenario(db, slug="voice-only", recommended_mode=RecommendedMode.VOICE)
    await make_scenario(db, slug="either-mode", recommended_mode=RecommendedMode.EITHER)
    await db.commit()

    response = await client.get("/api/v1/scenarios", params={"mode": "text"})

    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()}
    assert slugs == {"text-only", "either-mode"}


async def test_list_hides_other_users_custom_scenarios(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, other_user: User
) -> None:
    await make_scenario(db, slug="builtin-one")
    await make_scenario(db, slug="others-custom", is_custom=True, owner_user_id=other_user.id)
    await db.commit()

    response = await client.get("/api/v1/scenarios")

    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()}
    assert slugs == {"builtin-one"}


async def test_list_owner_mine_returns_only_my_custom_scenarios(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, other_user: User
) -> None:
    await make_scenario(db, slug="builtin-one")
    await make_scenario(db, slug="mine-custom", is_custom=True, owner_user_id=local_user.id)
    await make_scenario(db, slug="others-custom", is_custom=True, owner_user_id=other_user.id)
    await db.commit()

    response = await client.get("/api/v1/scenarios", params={"owner": "mine"})

    assert response.status_code == 200
    slugs = {s["slug"] for s in response.json()}
    assert slugs == {"mine-custom"}


async def test_get_by_slug_returns_detail(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    await make_scenario(db, slug="detail-one", title="Detail One")
    await db.commit()

    response = await client.get("/api/v1/scenarios/detail-one")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "detail-one"
    assert body["title"] == "Detail One"
    assert body["persona"] == {
        "name": "Al",
        "role": "Tester",
        "personality": "Calm.",
        "goals": "Test things.",
    }
    assert body["user_objective"] == "Do the thing."
    assert body["opening_line"] == "Hi there."
    assert body["success_criteria"] == ["Does the thing."]


async def test_get_unknown_slug_returns_404_envelope(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.get("/api/v1/scenarios/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_other_users_custom_scenario_returns_404(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, other_user: User
) -> None:
    await make_scenario(db, slug="not-mine", is_custom=True, owner_user_id=other_user.id)
    await db.commit()

    response = await client.get("/api/v1/scenarios/not-mine")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_invalid_difficulty_query_returns_422(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.get("/api/v1/scenarios", params={"difficulty": 9})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
