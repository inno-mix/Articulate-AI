from datetime import datetime

from app.domain.enums import ReportStatus
from app.schemas.common import ResponseModel
from app.schemas.json_types import DimensionScoreOut, GrammarFix, Highlight, VoiceMetrics


class ReportOut(ResponseModel):
    status: ReportStatus
    error_code: str | None
    overall_score: int | None
    objective_met: bool | None
    summary: str | None
    dimension_scores: list[DimensionScoreOut] | None
    strengths: list[str] | None
    improvements: list[str] | None
    highlights: list[Highlight] | None
    grammar_fixes: list[GrammarFix] | None
    voice_metrics: VoiceMetrics | None
    rubric_version: str
    llm_model: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class RetryOut(ResponseModel):
    status: ReportStatus
