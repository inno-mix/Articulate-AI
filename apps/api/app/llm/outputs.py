"""Structured output models (binding) — ai-layer.md §5.

Used by `LLMService.generate_structured` from Phase 2 (feedback, memory) and Phase 6 (rewrite,
custom scenarios, drills) onward. Defined now because the contract is binding and shared by
`app/llm/fake_outputs.py`.
"""

from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.json_types import Persona

LLMDimension = Literal[
    "clarity",
    "conciseness",
    "structure",
    "audience_fit",
    "tone",
    "confidence",
    "grammar_vocabulary",
]


class DimensionScore(BaseModel):
    dimension: LLMDimension
    score: int = Field(ge=1, le=5)
    reason: str = Field(max_length=300)


class HighlightOut(BaseModel):
    quote: str = Field(max_length=300)
    issue: str = Field(max_length=200)
    better_version: str = Field(max_length=300)


class GrammarFixOut(BaseModel):
    original: str = Field(max_length=300)
    corrected: str = Field(max_length=300)
    explanation: str = Field(max_length=200)


class FeedbackAnalysis(BaseModel):
    summary: str = Field(max_length=600)
    objective_met: bool
    scores: list[DimensionScore] = Field(min_length=7, max_length=7)
    strengths: list[str] = Field(min_length=1, max_length=3)
    improvements: list[str] = Field(min_length=1, max_length=3)
    highlights: list[HighlightOut] = Field(max_length=5)
    grammar_fixes: list[GrammarFixOut] = Field(max_length=8)

    @model_validator(mode="after")
    def one_score_per_dimension(self) -> "FeedbackAnalysis":
        if {s.dimension for s in self.scores} != set(get_args(LLMDimension)):
            raise ValueError("scores must contain each dimension exactly once")
        return self


class MemoryAction(BaseModel):
    action: Literal["add", "reinforce", "resolve"]
    note_id: UUID | None = None  # required for reinforce/resolve
    dimension: LLMDimension | Literal["fluency", "pronunciation"]
    note: str = Field(max_length=160)
    evidence: str | None = Field(default=None, max_length=200)


class MemoryUpdate(BaseModel):
    actions: list[MemoryAction] = Field(max_length=5)


class RewriteChangeOut(BaseModel):
    what: str = Field(max_length=160)
    why: str = Field(max_length=240)


class RewriteResult(BaseModel):
    output_text: str = Field(max_length=6000)
    changes: list[RewriteChangeOut] = Field(min_length=1, max_length=6)
    tone_note: str = Field(max_length=200)


class ScenarioDraftOut(BaseModel):
    title: str = Field(max_length=80)
    category: Literal[
        "status_updates",
        "stakeholder_communication",
        "interviews",
        "code_review",
        "negotiation",
        "meetings",
        "career",
    ]
    difficulty: int = Field(ge=1, le=3)
    summary: str = Field(max_length=300)
    persona: Persona
    user_objective: str = Field(max_length=300)
    opening_line: str = Field(max_length=400)
    success_criteria: list[str] = Field(min_length=1, max_length=5)
    recommended_mode: Literal["text", "voice", "either"]


class DrillSpec(BaseModel):
    kind: Literal["explain_concept", "rephrase", "filler_free_minute"]
    title: str = Field(max_length=80)
    prompt: str = Field(max_length=400)
    target_dimension: str


class DrillBatch(BaseModel):
    drills: list[DrillSpec] = Field(min_length=1, max_length=3)


class DrillFeedback(BaseModel):
    score: int = Field(ge=1, le=5)
    feedback: str = Field(max_length=300)
    better_version: str | None = Field(default=None, max_length=400)
