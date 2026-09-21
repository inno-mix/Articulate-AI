from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ReportStatus, ScoreSource, SessionPurpose
from app.models.base import Base
from app.models.types import text_enum


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"
    __table_args__ = (UniqueConstraint("session_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[ReportStatus] = mapped_column(
        text_enum(ReportStatus, "status"),
        default=ReportStatus.PENDING,
        server_default=ReportStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    overall_score: Mapped[int | None] = mapped_column(SmallInteger)
    objective_met: Mapped[bool | None] = mapped_column()
    summary: Mapped[str | None] = mapped_column(Text)
    dimension_scores: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    strengths: Mapped[list[str] | None] = mapped_column(JSONB)
    improvements: Mapped[list[str] | None] = mapped_column(JSONB)
    highlights: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    grammar_fixes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    voice_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    rubric_version: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SkillScore(Base):
    __tablename__ = "skill_scores"
    __table_args__ = (Index(None, "user_id", "dimension", "recorded_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    dimension: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[ScoreSource] = mapped_column(text_enum(ScoreSource, "source"))
    purpose: Mapped[SessionPurpose] = mapped_column(text_enum(SessionPurpose, "purpose"))
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE")
    )
    scorer: Mapped[str] = mapped_column(Text)
    rubric_version: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
