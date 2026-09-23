"""Feedback report generation (ai-layer.md §4.2, §7; overview.md §4.2).

`generate_report` runs in the worker (`app/worker/tasks/feedback.py`) and never holds a DB
session across the LLM call: each numbered step below opens and closes its own session.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.content.rubrics import Rubric, get_rubric
from app.core.config import Settings
from app.core.errors import NotFoundError, ReportNotReadyError
from app.domain.enums import MessageRole, PracticeMode, ReportStatus, ScoreSource, UsageKind
from app.llm.base import LLMService
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMInvalidOutputError,
    LLMRateLimitedError,
    LLMUnavailableError,
)
from app.llm.factory import get_llm_service
from app.llm.generation import TEMPERATURE
from app.llm.outputs import FeedbackAnalysis
from app.llm.prompts import RenderedPrompt, render_prompt
from app.models import FeedbackReport, Message, PracticeSession, Profile, Scenario, SkillScore, User
from app.schemas.json_types import DimensionScoreOut, SpeechData
from app.schemas.report import ReportOut, RetryOut
from app.services.scoring import (
    filter_grammar_fixes,
    filter_highlights,
    overall_score,
    to_score_100,
)
from app.services.transcript import build_transcript, format_transcript
from app.services.usage import record_usage
from app.voice.metrics import compute_voice_metrics, fluency_reason
from app.voice.metrics import speaking_summary as summarise_speaking

FLUENCY_SCORER = "metrics:v1"

log = structlog.get_logger(__name__)

STALE_AFTER = timedelta(minutes=5)

_ERROR_CODES: dict[type[LLMError], str] = {
    LLMUnavailableError: "llm_unavailable",
    LLMInvalidOutputError: "llm_invalid_output",
    LLMRateLimitedError: "llm_rate_limited",
    LLMAuthError: "llm_auth_failed",
}


def _scenario_context(scenario: Scenario) -> dict[str, object]:
    return {
        "title": scenario.title,
        "user_objective": scenario.user_objective,
        "success_criteria": scenario.success_criteria,
    }


def _learner_context(profile: Profile) -> dict[str, str]:
    return {
        "seniority": profile.seniority.value,
        "english_level": profile.english_level.value,
    }


def build_feedback_prompts(
    *,
    scenario: Scenario,
    profile: Profile,
    rubric: Rubric,
    transcript_text: str,
    speaking_summary: str | None,
    is_voice_session: bool = False,
) -> tuple[RenderedPrompt, RenderedPrompt]:
    system = render_prompt("feedback_system", learner=_learner_context(profile), rubric=rubric)
    user = render_prompt(
        "feedback_user",
        scenario=_scenario_context(scenario),
        transcript_text=transcript_text,
        speaking_summary=speaking_summary,
        is_voice_session=is_voice_session,
    )
    return system, user


async def create_pending_report(db: AsyncSession, session: PracticeSession) -> FeedbackReport:
    """A `pending` report for `session`. Doesn't commit or enqueue — the caller does both."""
    rubric_version = await db.scalar(
        select(Scenario.rubric_version).where(Scenario.id == session.scenario_id)
    )
    report = FeedbackReport(
        session_id=session.id,
        user_id=session.user_id,
        status=ReportStatus.PENDING,
        rubric_version=rubric_version,
        prompt_version="",
    )
    db.add(report)
    await db.flush()
    return report


def _is_stale(updated_at: datetime) -> bool:
    return datetime.now(UTC) - updated_at >= STALE_AFTER


async def get_report(db: AsyncSession, user_id: UUID, session_id: UUID) -> ReportOut:
    report = await db.scalar(
        select(FeedbackReport).where(
            FeedbackReport.session_id == session_id, FeedbackReport.user_id == user_id
        )
    )
    if report is None:
        raise NotFoundError()
    return ReportOut.model_validate(report)


async def retry_report(db: AsyncSession, user_id: UUID, session_id: UUID) -> RetryOut:
    # Deferred import: `app.worker.tasks.feedback` imports `generate_report` from this module,
    # so importing it back at module level here would create a circular import.
    from app.worker.tasks.feedback import enqueue_report

    report = await db.scalar(
        select(FeedbackReport)
        .where(FeedbackReport.session_id == session_id, FeedbackReport.user_id == user_id)
        .with_for_update()
    )
    if report is None:
        raise NotFoundError()
    stuck = report.status in (ReportStatus.PENDING, ReportStatus.RUNNING) and _is_stale(
        report.updated_at
    )
    retryable = report.status in (ReportStatus.FAILED, ReportStatus.READY) or stuck
    if not retryable:
        raise ReportNotReadyError()

    report.status = ReportStatus.PENDING
    report.error_code = None
    await db.commit()
    await enqueue_report(report.id)
    return RetryOut(status=ReportStatus.PENDING)


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession], report_id: UUID, error_code: str
) -> None:
    async with session_factory() as db:
        report = await db.get(FeedbackReport, report_id)
        if report is None:
            return  # session (and report) deleted meanwhile; discard quietly
        report.status = ReportStatus.FAILED
        report.error_code = error_code
        await db.commit()


async def generate_report(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    report_id: UUID,
    *,
    llm_override: LLMService | None = None,
) -> ReportStatus | None:
    # Step 1: claim the report (or bail out if it's gone, ready, or another worker has it).
    async with session_factory() as db:
        report = await db.scalar(
            select(FeedbackReport).where(FeedbackReport.id == report_id).with_for_update()
        )
        if report is None:
            log.info("feedback_report_missing", report_id=str(report_id))
            return None
        if report.status == ReportStatus.READY:
            return ReportStatus.READY
        if report.status == ReportStatus.RUNNING and not _is_stale(report.updated_at):
            return ReportStatus.RUNNING
        report.status = ReportStatus.RUNNING
        report.attempts += 1
        await db.commit()
        session_id = report.session_id
        user_id = report.user_id

    # Step 2-4: load context and build prompts, then release the connection before the LLM call.
    async with session_factory() as db:
        session = await db.scalar(
            select(PracticeSession)
            .where(PracticeSession.id == session_id)
            .options(selectinload(PracticeSession.scenario))
        )
        if session is None:
            return None  # deleted between steps 1 and 2; report was cascaded away too
        user = await db.scalar(
            select(User).where(User.id == user_id).options(selectinload(User.profile))
        )
        if user is None:
            return None  # deleted between steps 1 and 2 (cascades from the session)
        messages = list(
            await db.scalars(
                select(Message).where(Message.session_id == session_id).order_by(Message.seq)
            )
        )
        llm = llm_override or await get_llm_service(user, db, settings)

        scenario = session.scenario
        rubric = get_rubric(scenario.rubric_version)
        lines, truncated = build_transcript(messages)
        transcript_text = format_transcript(lines, scenario.persona["name"], truncated)

        speech_by_message: dict[UUID, SpeechData] = {
            m.id: SpeechData.model_validate(m.speech)
            for m in messages
            if m.role == MessageRole.USER and m.speech is not None
        }
        voice_metrics = (
            compute_voice_metrics(list(speech_by_message.values())) if speech_by_message else None
        )
        is_voice_session = session.mode == PracticeMode.VOICE

        system_prompt, user_prompt = build_feedback_prompts(
            scenario=scenario,
            profile=user.profile,
            rubric=rubric,
            transcript_text=transcript_text,
            speaking_summary=summarise_speaking(voice_metrics) if voice_metrics else None,
            is_voice_session=is_voice_session,
        )
        session_purpose = session.purpose

    # Step 5: the LLM call itself, with no DB session held.
    try:
        analysis, usage = await llm.generate_structured(
            system=system_prompt.text,
            prompt=user_prompt.text,
            output_type=FeedbackAnalysis,
            temperature=TEMPERATURE["feedback"],
        )
    except LLMError as exc:
        error_code = _ERROR_CODES.get(type(exc), "internal_error")
        log.warning("feedback_generation_failed", report_id=str(report_id), error_code=error_code)
        await _mark_failed(session_factory, report_id, error_code)
        return ReportStatus.FAILED
    except Exception:
        log.exception("feedback_generation_unexpected_error", report_id=str(report_id))
        await _mark_failed(session_factory, report_id, "internal_error")
        return ReportStatus.FAILED

    # Step 6: deterministic post-processing (code, not the LLM — ai-layer.md §7).
    scores_by_dimension = {s.dimension: s for s in analysis.scores}
    ordered_scores = [
        DimensionScoreOut(dimension=s.dimension, score=s.score, reason=s.reason)
        for s in (scores_by_dimension[d.key] for d in rubric.dimensions)
    ]
    if voice_metrics is not None:
        ordered_scores.append(
            DimensionScoreOut(
                dimension="fluency",
                score=voice_metrics.fluency_score,
                reason=fluency_reason(voice_metrics),
            )
        )
    user_messages = [m for m in messages if m.role == MessageRole.USER]
    highlights = filter_highlights(analysis.highlights, user_messages)
    grammar_fixes = filter_grammar_fixes(
        analysis.grammar_fixes, user_messages, speech_by_message=speech_by_message
    )
    overall = overall_score([s.score for s in ordered_scores])
    scorer = f"{llm.provider}:{llm.model}"

    # Step 7: save the report and skill scores.
    async with session_factory() as db:
        report = await db.get(FeedbackReport, report_id)
        if report is None:
            return None  # session (and report) deleted meanwhile; discard quietly

        report.status = ReportStatus.READY
        report.overall_score = overall
        report.objective_met = analysis.objective_met
        report.summary = analysis.summary
        report.dimension_scores = [s.model_dump(mode="json") for s in ordered_scores]
        report.strengths = analysis.strengths
        report.improvements = analysis.improvements
        report.highlights = [h.model_dump(mode="json") for h in highlights]
        report.grammar_fixes = [g.model_dump(mode="json") for g in grammar_fixes]
        report.voice_metrics = voice_metrics.model_dump(mode="json") if voice_metrics else None
        report.rubric_version = rubric.version
        report.prompt_version = system_prompt.version
        report.llm_provider = llm.provider
        report.llm_model = llm.model
        report.error_code = None
        report.completed_at = datetime.now(UTC)

        await db.execute(delete(SkillScore).where(SkillScore.session_id == session_id))
        for dimension_score in ordered_scores:
            is_fluency = dimension_score.dimension == "fluency"
            db.add(
                SkillScore(
                    user_id=user_id,
                    dimension=dimension_score.dimension,
                    score=to_score_100(dimension_score.score),
                    source=ScoreSource.SESSION,
                    purpose=session_purpose,
                    session_id=session_id,
                    scorer=FLUENCY_SCORER if is_fluency else scorer,
                    rubric_version=None if is_fluency else rubric.version,
                )
            )
        await record_usage(
            db,
            user_id=user_id,
            kind=UsageKind.LLM,
            feature="feedback",
            provider=llm.provider,
            model=llm.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
        )
        await db.commit()

    return ReportStatus.READY
