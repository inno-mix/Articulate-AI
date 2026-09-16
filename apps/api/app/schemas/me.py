from typing import Annotated, Any, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.domain.dimensions import Dimension
from app.domain.enums import EnglishLevel, Goal, PracticeMode, Seniority, VoiceInputMode
from app.schemas.common import RequestModel, ResponseModel

NULLABLE_PROFILE_FIELDS = frozenset({"native_language"})


def _dedupe(values: list[Any] | None) -> list[Any] | None:
    return None if values is None else list(dict.fromkeys(values))


class UserOut(ResponseModel):
    id: UUID
    email: str
    is_local: bool
    email_verified: bool


class ProfileOut(ResponseModel):
    display_name: str
    seniority: Seniority
    native_language: str | None
    english_level: EnglishLevel
    goals: list[Goal]
    focus_areas: list[Dimension]
    timezone: str


class ProfileUpdate(RequestModel):
    display_name: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    seniority: Seniority | None = None
    native_language: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    english_level: EnglishLevel | None = None
    goals: Annotated[list[Goal], Field(max_length=6)] | None = None
    focus_areas: Annotated[list[Dimension], Field(max_length=3)] | None = None
    timezone: str | None = None

    _dedupe_lists = field_validator("goals", "focus_areas")(_dedupe)

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value

    @model_validator(mode="after")
    def _only_optional_fields_may_be_null(self) -> Self:
        for name in self.model_fields_set - NULLABLE_PROFILE_FIELDS:
            if getattr(self, name) is None:
                raise ValueError(f"{name} can't be null")
        return self


class SettingsOut(ResponseModel):
    default_mode: PracticeMode
    voice_input_mode: VoiceInputMode
    tts_voice: str


class SettingsUpdate(RequestModel):
    default_mode: PracticeMode | None = None
    voice_input_mode: VoiceInputMode | None = None
    tts_voice: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} can't be null")
        return self


class MeOut(ResponseModel):
    user: UserOut
    profile: ProfileOut
    settings: SettingsOut
