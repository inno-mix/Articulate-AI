from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import MessageRole, PracticeMode, ReportStatus, SessionStatus
from app.llm.fake import FakeLLMService
from app.models import FeedbackReport, SkillScore, User
from app.schemas.json_types import SpeechData
from app.services.feedback import create_pending_report, generate_report
from app.services.scoring import overall_score
from app.voice.metrics import compute_voice_metrics, fluency_reason
from tests.factories import make_message, make_scenario, make_session
from tests.support.db import LockedSessionFactory

_SEVEN_DIMENSIONS = (
    "clarity",
    "conciseness",
    "structure",
    "audience_fit",
    "tone",
    "confidence",
    "grammar_vocabulary",
)

_ANALYSIS = {
    "summary": "Solid.",
    "objective_met": True,
    "scores": [{"dimension": d, "score": 3, "reason": "ok"} for d in _SEVEN_DIMENSIONS],
    "strengths": ["Clear opening."],
    "improvements": ["Cut filler."],
    "highlights": [],
    "grammar_fixes": [],
}

_SPEECH = {
    "words": [
        {"word": "hi", "start": 0.0, "end": 0.2, "confidence": 0.95, "is_filler": False},
        {"word": "sam", "start": 0.2, "end": 0.4, "confidence": 0.95, "is_filler": False},
        {"word": "um", "start": 0.4, "end": 0.5, "confidence": 0.9, "is_filler": True},
        {"word": "thanks", "start": 0.5, "end": 0.7, "confidence": 0.92, "is_filler": False},
    ],
    "duration_s": 0.7,
    "stt_model": "nova-3",
}
_SPEECH_DATA = SpeechData.model_validate(_SPEECH)


async def _skill_scores(
    session_factory: LockedSessionFactory, session_id: object
) -> list[SkillScore]:
    async with session_factory() as fresh:
        return list(
            await fresh.scalars(select(SkillScore).where(SkillScore.session_id == session_id))
        )


async def _setup(
    db: AsyncSession,
    user_id: object,
    *,
    mode: PracticeMode = PracticeMode.TEXT,
    with_speech: bool = False,
) -> FeedbackReport:
    scenario = await make_scenario(db, slug=f"feedback-voice-{uuid4().hex[:8]}")
    session = await make_session(
        db,
        user_id=user_id,
        scenario_id=scenario.id,
        mode=mode,
        status=SessionStatus.ENDED,
        user_turns=1,
    )
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await make_message(
        db,
        session,
        role=MessageRole.USER,
        content="Hi Sam, thanks for the PR.",
        speech=_SPEECH if with_speech else None,
    )
    report = await create_pending_report(db, session)
    await db.commit()
    return report


async def test_voice_session_with_speech_adds_fluency_dimension(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id, mode=PracticeMode.VOICE, with_speech=True)
    llm = FakeLLMService(structured={"FeedbackAnalysis": _ANALYSIS})

    status = await generate_report(session_factory, settings, report.id, llm_override=llm)

    assert status == ReportStatus.READY
    expected_metrics = compute_voice_metrics([_SPEECH_DATA])
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.voice_metrics is not None
        assert len(saved.dimension_scores) == 8
        assert saved.dimension_scores[-1]["dimension"] == "fluency"
        assert saved.dimension_scores[-1]["score"] == expected_metrics.fluency_score
        assert saved.dimension_scores[-1]["reason"] == fluency_reason(expected_metrics)
        assert saved.overall_score == overall_score([s["score"] for s in saved.dimension_scores])

    scores = await _skill_scores(session_factory, report.session_id)
    assert len(scores) == 8


async def test_voice_session_speaking_summary_in_prompt(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id, mode=PracticeMode.VOICE, with_speech=True)
    llm = FakeLLMService(structured={"FeedbackAnalysis": _ANALYSIS})

    await generate_report(session_factory, settings, report.id, llm_override=llm)

    generate_calls = [c for c in llm.calls if c.method == "generate_structured"]
    assert len(generate_calls) == 1
    prompt = generate_calls[0].prompt
    assert "Speaking stats" in prompt
    assert "Fluency score" in prompt
    assert "transcribed from speech" in prompt


async def test_text_session_unchanged_at_seven_dimensions(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id, mode=PracticeMode.TEXT, with_speech=False)
    llm = FakeLLMService(structured={"FeedbackAnalysis": _ANALYSIS})

    status = await generate_report(session_factory, settings, report.id, llm_override=llm)

    assert status == ReportStatus.READY
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.voice_metrics is None
        assert len(saved.dimension_scores) == 7
        assert all(s["dimension"] != "fluency" for s in saved.dimension_scores)

    scores = await _skill_scores(session_factory, report.session_id)
    assert len(scores) == 7

    generate_calls = [c for c in llm.calls if c.method == "generate_structured"]
    assert "transcribed from speech" not in generate_calls[0].prompt


async def test_voice_session_without_speech_data_has_no_fluency(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id, mode=PracticeMode.VOICE, with_speech=False)
    llm = FakeLLMService(structured={"FeedbackAnalysis": _ANALYSIS})

    status = await generate_report(session_factory, settings, report.id, llm_override=llm)

    assert status == ReportStatus.READY
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.voice_metrics is None
        assert len(saved.dimension_scores) == 7

    generate_calls = [c for c in llm.calls if c.method == "generate_structured"]
    # still a voice session, so the transcription-error note is present even with no speech data
    assert "transcribed from speech" in generate_calls[0].prompt


async def test_fluency_skill_score_has_metrics_scorer_and_no_rubric_version(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings, local_user: User
) -> None:
    report = await _setup(db, local_user.id, mode=PracticeMode.VOICE, with_speech=True)
    llm = FakeLLMService(structured={"FeedbackAnalysis": _ANALYSIS})

    await generate_report(session_factory, settings, report.id, llm_override=llm)

    scores = await _skill_scores(session_factory, report.session_id)
    fluency = next(s for s in scores if s.dimension == "fluency")
    assert fluency.scorer == "metrics:v1"
    assert fluency.rubric_version is None
    others = [s for s in scores if s.dimension != "fluency"]
    assert all(s.scorer == "fake:fake" for s in others)
    assert all(s.rubric_version == "v1" for s in others)
