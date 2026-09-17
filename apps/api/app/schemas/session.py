from datetime import datetime
from uuid import UUID

from app.domain.enums import MessageRole, MessageSource, PracticeMode, SessionStatus
from app.schemas.common import RequestModel, ResponseModel


class CreateSessionIn(RequestModel):
    scenario_id: UUID
    mode: PracticeMode


class ScenarioRef(ResponseModel):
    slug: str
    title: str


class MessageOut(ResponseModel):
    id: UUID
    seq: int
    role: MessageRole
    content: str
    source: MessageSource
    created_at: datetime


class SessionSummary(ResponseModel):
    id: UUID
    scenario: ScenarioRef
    mode: PracticeMode
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    user_turns: int
    overall_score: int | None = None  # always null in Phase 1 (Phase 2 adds reports)


class SessionLimits(ResponseModel):
    max_user_turns: int
    max_message_chars: int


class SessionDetail(SessionSummary):
    messages: list[MessageOut]
    limits: SessionLimits


class EndSessionOut(ResponseModel):
    status: SessionStatus
    report_status: str | None = None  # always null in Phase 1 (Phase 2 adds reports)
