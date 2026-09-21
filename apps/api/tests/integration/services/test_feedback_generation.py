from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import MessageRole, ReportStatus, SessionPurpose, SessionStatus
from app.llm.base import LLMUsage
from app.llm.errors import LLMUnavailableError
from app.llm.fake import FakeLLMService
from app.models import FeedbackReport, PracticeSession, SkillScore, UsageEvent, User
from app.services.feedback import create_pending_report, generate_report
from tests.factories import make_message, make_scenario, make_session
from tests.support.db import LockedSessionFactory


class _RuntimeErrorLLM:
    provider = "fake"
    model = "fake"

    async def generate_structured(self, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    def last_usage(self) -> LLMUsage | None:
        return None


async def _skill_scores(
    session_factory: LockedSessionFactory, session_id: object
) -> list[SkillScore]:
    async with session_factory() as fresh:
        return list(
            await fresh.scalars(select(SkillScore).where(SkillScore.session_id == session_id))
        )


async def _setup(
    db: AsyncSession, user_id, *, purpose: SessionPurpose = SessionPurpose.PRACTICE
) -> FeedbackReport:
    scenario = await make_scenario(db, slug=f"feedback-{uuid4().hex[:8]}")
    session = await make_session(
        db,
        user_id=user_id,
        scenario_id=scenario.id,
        status=SessionStatus.ENDED,
        purpose=purpose,
        user_turns=1,
    )
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    report = await create_pending_report(db, session)
    await db.commit()
    return report


async def test_generates_ready_report_with_scores_and_filtered_highlights(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)
    llm = FakeLLMService(
        structured={
            "FeedbackAnalysis": {
                "summary": "Solid.",
                "objective_met": True,
                "scores": [
                    {"dimension": d, "score": 3, "reason": "ok"}
                    for d in (
                        "clarity",
                        "conciseness",
                        "structure",
                        "audience_fit",
                        "tone",
                        "confidence",
                        "grammar_vocabulary",
                    )
                ],
                "strengths": ["Clear opening."],
                "improvements": ["Cut filler."],
                "highlights": [
                    {
                        "quote": "thanks for the PR",
                        "issue": "vague",
                        "better_version": "be specific",
                    },
                    {
                        "quote": "this was never said by anyone",
                        "issue": "invented",
                        "better_version": "n/a",
                    },
                ],
                "grammar_fixes": [],
            }
        }
    )

    status = await generate_report(session_factory, settings, report.id, llm_override=llm)

    assert status == ReportStatus.READY
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.status == ReportStatus.READY
        assert len(saved.highlights) == 1
        assert saved.highlights[0]["quote"] == "thanks for the PR"
        assert saved.highlights[0]["message_id"] is not None


async def test_writes_one_skill_score_per_dimension(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)

    await generate_report(session_factory, settings, report.id, llm_override=FakeLLMService())

    scores = await _skill_scores(session_factory, report.session_id)
    assert len(scores) == 7
    for score in scores:
        assert 0 <= score.score <= 100


async def test_is_idempotent_when_ready(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)
    await generate_report(session_factory, settings, report.id, llm_override=FakeLLMService())

    status = await generate_report(
        session_factory, settings, report.id, llm_override=FakeLLMService()
    )

    assert status == ReportStatus.READY
    scores = await _skill_scores(session_factory, report.session_id)
    assert len(scores) == 7


async def test_regeneration_replaces_skill_scores(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)
    await generate_report(session_factory, settings, report.id, llm_override=FakeLLMService())

    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        saved.status = ReportStatus.PENDING
        await fresh.commit()

    status = await generate_report(
        session_factory, settings, report.id, llm_override=FakeLLMService()
    )

    assert status == ReportStatus.READY
    scores = await _skill_scores(session_factory, report.session_id)
    assert len(scores) == 7


async def test_invalid_output_marks_failed_with_code(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)
    llm = FakeLLMService(fail_times=99)

    status = await generate_report(session_factory, settings, report.id, llm_override=llm)

    assert status == ReportStatus.FAILED
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.status == ReportStatus.FAILED
        assert saved.error_code == "llm_invalid_output"


class _UnavailableLLM:
    provider = "fake"
    model = "fake"

    async def generate_structured(self, **_kwargs: object) -> object:
        raise LLMUnavailableError()

    def last_usage(self) -> LLMUsage | None:
        return None


async def test_unavailable_marks_failed_with_code(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)

    status = await generate_report(
        session_factory, settings, report.id, llm_override=_UnavailableLLM()
    )

    assert status == ReportStatus.FAILED
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.error_code == "llm_unavailable"


async def test_unexpected_exception_marks_internal_error(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)

    status = await generate_report(
        session_factory, settings, report.id, llm_override=_RuntimeErrorLLM()
    )

    assert status == ReportStatus.FAILED
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.error_code == "internal_error"


async def test_records_usage_event_with_feature_feedback(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)

    await generate_report(session_factory, settings, report.id, llm_override=FakeLLMService())

    async with session_factory() as fresh:
        event = await fresh.scalar(
            select(UsageEvent).where(
                UsageEvent.user_id == local_user.id, UsageEvent.feature == "feedback"
            )
        )
    assert event is not None


async def test_assessment_session_scores_have_purpose_assessment(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id, purpose=SessionPurpose.ASSESSMENT)

    await generate_report(session_factory, settings, report.id, llm_override=FakeLLMService())

    scores = await _skill_scores(session_factory, report.session_id)
    assert all(s.purpose == SessionPurpose.ASSESSMENT for s in scores)


async def test_skill_scores_record_scorer_and_rubric_version(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)

    await generate_report(session_factory, settings, report.id, llm_override=FakeLLMService())

    scores = await _skill_scores(session_factory, report.session_id)
    assert all(s.scorer == "fake:fake" for s in scores)
    assert all(s.rubric_version == "v1" for s in scores)


async def test_feedback_call_uses_temperature_zero(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)
    llm = FakeLLMService()

    await generate_report(session_factory, settings, report.id, llm_override=llm)

    generate_calls = [c for c in llm.calls if c.method == "generate_structured"]
    assert len(generate_calls) == 1
    assert generate_calls[0].temperature == 0.0


async def test_job_for_deleted_session_exits_quietly(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id)
    report_id = report.id

    async with session_factory() as fresh:
        session = await fresh.get(PracticeSession, report.session_id)
        assert session is not None
        await fresh.delete(session)
        await fresh.commit()

    status = await generate_report(
        session_factory, settings, report_id, llm_override=FakeLLMService()
    )

    assert status is None
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report_id)
        assert saved is None
