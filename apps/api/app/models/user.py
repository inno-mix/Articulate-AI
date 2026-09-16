from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Text, Time, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import EnglishLevel, PracticeMode, Seniority, VoiceInputMode
from app.models.base import Base, TimestampMixin
from app.models.types import text_enum


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_local: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    profile: Mapped["Profile"] = relationship(
        back_populates="user", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(Text, default="You", server_default="You")
    seniority: Mapped[Seniority] = mapped_column(
        text_enum(Seniority, "seniority"), default=Seniority.MID, server_default=Seniority.MID
    )
    native_language: Mapped[str | None] = mapped_column(Text)
    english_level: Mapped[EnglishLevel] = mapped_column(
        text_enum(EnglishLevel, "english_level"),
        default=EnglishLevel.B2,
        server_default=EnglishLevel.B2,
    )
    goals: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"))
    focus_areas: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )
    timezone: Mapped[str] = mapped_column(Text, default="UTC", server_default="UTC")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="profile", lazy="raise")


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    default_mode: Mapped[PracticeMode] = mapped_column(
        text_enum(PracticeMode, "default_mode"),
        default=PracticeMode.TEXT,
        server_default=PracticeMode.TEXT,
    )
    voice_input_mode: Mapped[VoiceInputMode] = mapped_column(
        text_enum(VoiceInputMode, "voice_input_mode"),
        default=VoiceInputMode.PUSH_TO_TALK,
        server_default=VoiceInputMode.PUSH_TO_TALK,
    )
    tts_voice: Mapped[str] = mapped_column(Text)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    reminder_time: Mapped[time | None] = mapped_column(Time)
    weekly_summary_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )

    user: Mapped[User] = relationship(back_populates="settings", lazy="raise")
