from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.domain.enums import MessageRole, MessageSource, PracticeMode, ReportStatus, SessionStatus
from app.schemas.common import RequestModel, ResponseModel


class CreateSessionIn(RequestModel):
    scenario_id: UUID
    mode: PracticeMode


class SendMessageIn(RequestModel):
    content: Annotated[str, Field(min_length=1, max_length=1000)]


class HintOut(ResponseModel):
    hint: str


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
    overall_score: int | None = None  # set once the session's report is ready


class SessionLimits(ResponseModel):
    max_user_turns: int
    max_message_chars: int


class SessionDetail(SessionSummary):
    messages: list[MessageOut]
    limits: SessionLimits


class EndSessionOut(ResponseModel):
    status: SessionStatus
    report_status: ReportStatus | None = None  # null only when the session was abandoned
