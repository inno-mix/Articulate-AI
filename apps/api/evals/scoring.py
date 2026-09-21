"""Pure scoring for feedback evals (ai-layer.md §8). No I/O — `evals/run.py` does that."""

import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from app.domain.enums import EnglishLevel, PracticeMode
from app.llm.outputs import FeedbackAnalysis, LLMDimension
from app.schemas.json_types import Highlight


class EvalTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scenario_slug: str
    mode: PracticeMode
    learner_level: EnglishLevel
    transcript: list[EvalTurn]
    expected: dict[LLMDimension, tuple[int, int]]
    must_flag_quote_containing: list[str] = []
    objective_met: bool | None = None
    foreign_words: list[str] = []


@dataclass
class CaseResult:
    case_id: str
    in_range: dict[str, bool]
    objective_ok: bool | None
    quote_flag_ok: bool | None
    english_ok: bool | None
    schema_failed: bool
    latency_ms: int


@dataclass
class EvalSummary:
    total: int
    in_range_rate: float
    schema_failure_rate: float
    quote_survival_rate: float | None
    objective_accuracy: float | None
    english_ok_rate: float | None
    p50_latency_ms: float
    p95_latency_ms: float


def _prose_fields(analysis: FeedbackAnalysis, highlights: list[Highlight]) -> list[str]:
    """Fields the model wrote itself — never a verbatim user quote (ai-layer.md §8)."""
    return [
        analysis.summary,
        *analysis.strengths,
        *analysis.improvements,
        *(h.issue for h in highlights),
        *(h.better_version for h in highlights),
        *(g.explanation for g in analysis.grammar_fixes),
    ]


def score_case(
    case: EvalCase, analysis: FeedbackAnalysis | None, highlights: list[Highlight], latency_ms: int
) -> CaseResult:
    if analysis is None:
        return CaseResult(
            case_id=case.id,
            in_range={},
            objective_ok=None,
            quote_flag_ok=None,
            english_ok=None,
            schema_failed=True,
            latency_ms=latency_ms,
        )

    scores_by_dimension = {s.dimension: s.score for s in analysis.scores}
    in_range = {
        dimension: lo <= scores_by_dimension[dimension] <= hi
        for dimension, (lo, hi) in case.expected.items()
    }

    objective_ok = (
        None if case.objective_met is None else analysis.objective_met == case.objective_met
    )

    quote_flag_ok = None
    if case.must_flag_quote_containing:
        quote_flag_ok = any(
            needle in h.quote for h in highlights for needle in case.must_flag_quote_containing
        )

    english_ok = None
    if case.foreign_words:
        combined = " ".join(_prose_fields(analysis, highlights)).lower()
        english_ok = not any(
            re.search(rf"\b{re.escape(word.lower())}\b", combined) for word in case.foreign_words
        )

    return CaseResult(
        case_id=case.id,
        in_range=in_range,
        objective_ok=objective_ok,
        quote_flag_ok=quote_flag_ok,
        english_ok=english_ok,
        schema_failed=False,
        latency_ms=latency_ms,
    )


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def _rate(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return sum(flags) / len(flags)


def summarise(results: list[CaseResult]) -> EvalSummary:
    total = len(results)
    all_in_range = [ok for r in results for ok in r.in_range.values()]
    latencies = [r.latency_ms for r in results]
    quote_flags = [r.quote_flag_ok for r in results if r.quote_flag_ok is not None]
    objective_flags = [r.objective_ok for r in results if r.objective_ok is not None]
    english_flags = [r.english_ok for r in results if r.english_ok is not None]

    return EvalSummary(
        total=total,
        in_range_rate=_rate(all_in_range) or 0.0,
        schema_failure_rate=sum(r.schema_failed for r in results) / total if total else 0.0,
        quote_survival_rate=_rate(quote_flags),
        objective_accuracy=_rate(objective_flags),
        english_ok_rate=_rate(english_flags),
        p50_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
    )
