"""Plain factory functions for test data."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RecommendedMode, ScenarioCategory
from app.models import Profile, Scenario, User, UserSettings

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


async def make_scenario(
    db: AsyncSession,
    *,
    slug: str | None = None,
    title: str = "Test scenario",
    category: ScenarioCategory = ScenarioCategory.MEETINGS,
    difficulty: int = 1,
    recommended_mode: RecommendedMode = RecommendedMode.TEXT,
    is_assessment: bool = False,
    is_custom: bool = False,
    owner_user_id: UUID | None = None,
) -> Scenario:
    scenario = Scenario(
        slug=slug or f"scenario-{uuid4().hex[:8]}",
        title=title,
        category=category,
        difficulty=difficulty,
        summary="A test scenario.",
        persona={"name": "Al", "role": "Tester", "personality": "Calm.", "goals": "Test things."},
        user_objective="Do the thing.",
        opening_line="Hi there.",
        success_criteria=["Does the thing."],
        recommended_mode=recommended_mode,
        is_assessment=is_assessment,
        is_custom=is_custom,
        owner_user_id=owner_user_id,
    )
    db.add(scenario)
    await db.flush()
    return scenario
