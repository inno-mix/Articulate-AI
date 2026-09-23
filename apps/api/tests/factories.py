"""Plain factory functions for test data."""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    MessageRole,
    MessageSource,
    PracticeMode,
    RecommendedMode,
    ScenarioCategory,
    SessionPurpose,
    SessionStatus,
)
from app.models import Message, PracticeSession, Profile, Scenario, User, UserSettings

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


async def make_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    scenario_id: UUID,
    mode: PracticeMode = PracticeMode.TEXT,
    status: SessionStatus = SessionStatus.ACTIVE,
    purpose: SessionPurpose = SessionPurpose.PRACTICE,
    user_turns: int = 0,
    llm_provider: str = "fake",
    llm_model: str = "fake",
) -> PracticeSession:
    session = PracticeSession(
        user_id=user_id,
        scenario_id=scenario_id,
        mode=mode,
        status=status,
        purpose=purpose,
        user_turns=user_turns,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    db.add(session)
    await db.flush()
    return session


async def make_message(
    db: AsyncSession,
    session: PracticeSession,
    *,
    role: MessageRole = MessageRole.USER,
    content: str = "Hello.",
    source: MessageSource = MessageSource.TEXT,
    speech: dict[str, Any] | None = None,
) -> Message:
    max_seq = await db.scalar(select(func.max(Message.seq)).where(Message.session_id == session.id))
    message = Message(
        session_id=session.id,
        seq=0 if max_seq is None else max_seq + 1,
        role=role,
        content=content,
        source=source,
        speech=speech,
    )
    db.add(message)
    await db.flush()
    return message
