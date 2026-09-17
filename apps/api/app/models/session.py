from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    MessageRole,
    MessageSource,
    PracticeMode,
    SessionPurpose,
    SessionStatus,
)
from app.models.base import Base
from app.models.scenario import Scenario
from app.models.types import text_enum


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (Index(None, "user_id", "started_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    mode: Mapped[PracticeMode] = mapped_column(text_enum(PracticeMode, "mode"))
    purpose: Mapped[SessionPurpose] = mapped_column(
        text_enum(SessionPurpose, "purpose"),
        default=SessionPurpose.PRACTICE,
        server_default=SessionPurpose.PRACTICE,
    )
    status: Mapped[SessionStatus] = mapped_column(text_enum(SessionStatus, "status"))
    safety_flag: Mapped[bool] = mapped_column(default=False, server_default=false())
    user_turns: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    llm_provider: Mapped[str] = mapped_column(Text)
    llm_model: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scenario: Mapped[Scenario] = relationship(lazy="raise")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column()
    role: Mapped[MessageRole] = mapped_column(text_enum(MessageRole, "role"))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[MessageSource] = mapped_column(text_enum(MessageSource, "source"))
    speech: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
