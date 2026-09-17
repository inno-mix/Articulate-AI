from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Text, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import RecommendedMode, ScenarioCategory
from app.models.base import Base, TimestampMixin
from app.models.types import text_enum


class Scenario(TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="difficulty_range"),
        CheckConstraint("is_custom = (owner_user_id IS NOT NULL)", name="custom_has_owner"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[ScenarioCategory] = mapped_column(text_enum(ScenarioCategory, "category"))
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    summary: Mapped[str] = mapped_column(Text)
    persona: Mapped[dict[str, Any]] = mapped_column(JSONB)
    user_objective: Mapped[str] = mapped_column(Text)
    opening_line: Mapped[str] = mapped_column(Text)
    success_criteria: Mapped[list[str]] = mapped_column(JSONB)
    recommended_mode: Mapped[RecommendedMode] = mapped_column(
        text_enum(RecommendedMode, "recommended_mode")
    )
    keyterms: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    rubric_version: Mapped[str] = mapped_column(Text, default="v1", server_default="v1")
    is_assessment: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_custom: Mapped[bool] = mapped_column(default=False, server_default=false())
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content_hash: Mapped[str | None] = mapped_column(Text)
