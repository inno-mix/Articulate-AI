"""Practice session lifecycle (api-contract.md §2 Sessions; security-privacy.md S3).

Every lookup is scoped by `user_id`; a session owned by someone else is `NotFoundError`, never a
403 (S3) — the caller never learns whether the id exists at all.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, SessionInUseError
from app.domain.enums import (
    MessageRole,
    MessageSource,
    PracticeMode,
    ReportStatus,
    SessionPurpose,
    SessionStatus,
)
from app.domain.limits import MAX_MESSAGE_CHARS, MAX_USER_TURNS, MIN_USER_TURNS_FOR_REPORT
from app.llm.base import LLMService
from app.models import FeedbackReport, Message, PracticeSession, User
from app.schemas.common import Page
from app.schemas.session import (
    EndSessionOut,
    MessageOut,
    ScenarioRef,
    SessionDetail,
    SessionLimits,
    SessionSummary,
)
from app.services import scenarios as scenarios_service
from app.services.feedback import create_pending_report
from app.services.locks import voice_session_lock_key
from app.services.pagination import MAX_LIMIT, decode_cursor, encode_cursor
from app.worker.tasks.feedback import enqueue_report


def _to_summary(session: PracticeSession, overall_score: int | None = None) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        scenario=ScenarioRef(slug=session.scenario.slug, title=session.scenario.title),
        mode=session.mode,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        user_turns=session.user_turns,
        overall_score=overall_score,
    )


async def get_owned_session(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, for_update: bool = False
) -> PracticeSession:
    stmt = select(PracticeSession).where(
        PracticeSession.id == session_id, PracticeSession.user_id == user_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    session = await db.scalar(stmt)
    if session is None:
        raise NotFoundError()
    return session


async def add_message(
    db: AsyncSession,
    session: PracticeSession,
    role: MessageRole,
    content: str,
    source: MessageSource,
    speech: dict[str, Any] | None = None,
) -> Message:
    # Lock the session row first so two concurrent adds can't compute the same next `seq`.
    await db.execute(
        select(PracticeSession.id).where(PracticeSession.id == session.id).with_for_update()
    )
    max_seq = await db.scalar(
        select(Message.seq)
        .where(Message.session_id == session.id)
        .order_by(Message.seq.desc())
        .limit(1)
    )
    message = Message(
        session_id=session.id,
        seq=0 if max_seq is None else max_seq + 1,
        role=role,
        content=content,
        source=source,
        speech=speech,
    )
    db.add(message)
    if role == MessageRole.USER:
        session.user_turns += 1
    await db.flush()
    return message


async def create_session(
    db: AsyncSession,
    user: User,
    scenario_id: UUID,
    mode: PracticeMode,
    llm: LLMService,
    purpose: SessionPurpose = SessionPurpose.PRACTICE,
) -> SessionDetail:
    scenario = await scenarios_service.get_scenario_by_id(db, user.id, scenario_id)
    if scenario.is_assessment:
        # Hidden in Q1: only a Phase 5 assessment_id route may start one of these.
        raise NotFoundError()

    session = PracticeSession(
        user_id=user.id,
        scenario_id=scenario.id,
        mode=mode,
        purpose=purpose,
        status=SessionStatus.ACTIVE,
        llm_provider=llm.provider,
        llm_model=llm.model,
    )
    db.add(session)
    await db.flush()
    await add_message(
        db,
        session,
        role=MessageRole.ASSISTANT,
        content=scenario.opening_line,
        source=MessageSource(mode.value),
    )
    return await get_session_detail(db, user.id, session.id)


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int,
    cursor: str | None,
    status: SessionStatus | None,
) -> Page[SessionSummary]:
    limit = min(limit, MAX_LIMIT)
    conditions = [PracticeSession.user_id == user_id]
    if status is not None:
        conditions.append(PracticeSession.status == status)
    if cursor is not None:
        cursor_ts, cursor_id = decode_cursor(cursor)
        conditions.append(
            (PracticeSession.started_at < cursor_ts)
            | ((PracticeSession.started_at == cursor_ts) & (PracticeSession.id < cursor_id))
        )

    rows = list(
        (
            await db.execute(
                select(PracticeSession, FeedbackReport.overall_score)
                .where(*conditions)
                .outerjoin(
                    FeedbackReport,
                    (FeedbackReport.session_id == PracticeSession.id)
                    & (FeedbackReport.status == ReportStatus.READY),
                )
                .options(selectinload(PracticeSession.scenario))
                .order_by(PracticeSession.started_at.desc(), PracticeSession.id.desc())
                .limit(limit + 1)
            )
        ).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last_session = rows[-1][0] if rows else None
    next_cursor = (
        encode_cursor(last_session.started_at, last_session.id)
        if has_more and last_session
        else None
    )
    items = [_to_summary(session, overall_score) for session, overall_score in rows]
    return Page(items=items, next_cursor=next_cursor)


async def get_session_detail(db: AsyncSession, user_id: UUID, session_id: UUID) -> SessionDetail:
    row = (
        await db.execute(
            select(PracticeSession, FeedbackReport.overall_score)
            .where(PracticeSession.id == session_id, PracticeSession.user_id == user_id)
            .outerjoin(
                FeedbackReport,
                (FeedbackReport.session_id == PracticeSession.id)
                & (FeedbackReport.status == ReportStatus.READY),
            )
            .options(selectinload(PracticeSession.scenario))
        )
    ).first()
    if row is None:
        raise NotFoundError()
    session, overall_score = row
    messages = await db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.seq)
    )
    return SessionDetail(
        **_to_summary(session, overall_score).model_dump(),
        messages=[MessageOut.model_validate(m) for m in messages],
        limits=SessionLimits(max_user_turns=MAX_USER_TURNS, max_message_chars=MAX_MESSAGE_CHARS),
    )


async def end_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> EndSessionOut:
    session = await get_owned_session(db, user_id, session_id, for_update=True)
    if session.status == SessionStatus.ACTIVE:
        session.status = (
            SessionStatus.ENDED
            if session.user_turns >= MIN_USER_TURNS_FOR_REPORT
            else SessionStatus.ABANDONED
        )
        session.ended_at = datetime.now(UTC)
        await db.flush()
        if session.status == SessionStatus.ENDED:
            report = await create_pending_report(db, session)
            # Commit before enqueueing: the worker may pick the job up before this transaction
            # commits otherwise (app/services/feedback.py's generate_report Pitfall).
            await db.commit()
            pending_status = report.status
            await enqueue_report(report.id)
            return EndSessionOut(status=session.status, report_status=pending_status)
        await db.commit()
        return EndSessionOut(status=session.status, report_status=None)

    report_status: ReportStatus | None = None
    if session.status == SessionStatus.ENDED:
        report_status = await db.scalar(
            select(FeedbackReport.status).where(FeedbackReport.session_id == session.id)
        )
    return EndSessionOut(status=session.status, report_status=report_status)


async def delete_session(db: AsyncSession, redis: Redis, user_id: UUID, session_id: UUID) -> None:
    session = await get_owned_session(db, user_id, session_id)
    if await redis.exists(voice_session_lock_key(session_id)):
        raise SessionInUseError()
    await db.delete(session)
    await db.flush()
