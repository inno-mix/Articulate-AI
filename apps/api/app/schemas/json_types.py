"""Pydantic models for JSONB columns (data-model.md)."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Persona(BaseModel):
    """The AI character in a practice scenario (`scenarios.persona`)."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(max_length=40)]
    role: Annotated[str, Field(max_length=80)]
    personality: Annotated[str, Field(max_length=200)]
    goals: Annotated[str, Field(max_length=200)]


class DimensionScoreOut(BaseModel):
    """One rubric dimension's score (`feedback_reports.dimension_scores`)."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    score: int
    reason: str


class Highlight(BaseModel):
    """A quote-anchored moment to improve (`feedback_reports.highlights`)."""

    model_config = ConfigDict(extra="forbid")

    message_id: UUID | None
    quote: str
    issue: str
    better_version: str


class GrammarFix(BaseModel):
    """A quote-anchored grammar correction (`feedback_reports.grammar_fixes`)."""

    model_config = ConfigDict(extra="forbid")

    original: str
    corrected: str
    explanation: str


class SpeechWord(BaseModel):
    """One transcribed word with timing (`messages.speech` / `response_speech`)."""

    model_config = ConfigDict(extra="forbid")

    word: str
    start: float
    end: float
    confidence: float
    is_filler: bool


class SpeechData(BaseModel):
    """A voice turn's transcript with word timings (`messages.speech` / `response_speech`)."""

    model_config = ConfigDict(extra="forbid")

    words: list[SpeechWord]
    duration_s: float
    stt_model: str


class VoiceMetrics(BaseModel):
    """Speaking stats computed from a voice session (`feedback_reports.voice_metrics`)."""

    model_config = ConfigDict(extra="forbid")

    speaking_seconds: float
    words: int
    wpm: float
    pace_measured: bool
    filler_count: int
    filler_rate_per_100: float
    filler_examples: list[str]
    long_pause_count: int
    long_pauses_per_min: float
    hard_to_catch_words: list[str]
    fluency_score: int
