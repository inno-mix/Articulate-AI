import pytest
from pydantic import ValidationError

from app.llm.outputs import DimensionScore, FeedbackAnalysis, GrammarFixOut, HighlightOut

VALID_SCORES = [
    {"dimension": d, "score": 3, "reason": "ok"}
    for d in (
        "clarity",
        "conciseness",
        "structure",
        "audience_fit",
        "tone",
        "confidence",
        "grammar_vocabulary",
    )
]


def _analysis(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "summary": "Solid overall.",
        "objective_met": True,
        "scores": VALID_SCORES,
        "strengths": ["Clear opening."],
        "improvements": ["Cut filler."],
        "highlights": [],
        "grammar_fixes": [],
    }
    payload.update(overrides)
    return payload


def test_feedback_analysis_accepts_one_score_per_dimension() -> None:
    analysis = FeedbackAnalysis.model_validate(_analysis())

    assert len(analysis.scores) == 7


def test_feedback_analysis_requires_each_dimension_once_duplicate() -> None:
    # "clarity" appears twice; grammar_vocabulary is missing.
    scores = [*VALID_SCORES[:-1], VALID_SCORES[0]]

    with pytest.raises(ValidationError, match="exactly once"):
        FeedbackAnalysis.model_validate(_analysis(scores=scores))


def test_feedback_analysis_requires_each_dimension_once_missing() -> None:
    scores = VALID_SCORES[:-1]  # only 6 dimensions

    with pytest.raises(ValidationError):
        FeedbackAnalysis.model_validate(_analysis(scores=scores))


def test_score_bounds() -> None:
    with pytest.raises(ValidationError):
        DimensionScore.model_validate({"dimension": "clarity", "score": 6, "reason": "x"})
    with pytest.raises(ValidationError):
        DimensionScore.model_validate({"dimension": "clarity", "score": 0, "reason": "x"})


def test_list_length_limits() -> None:
    with pytest.raises(ValidationError):
        FeedbackAnalysis.model_validate(_analysis(strengths=[]))
    with pytest.raises(ValidationError):
        FeedbackAnalysis.model_validate(_analysis(strengths=["a", "b", "c", "d"]))
    with pytest.raises(ValidationError):
        FeedbackAnalysis.model_validate(
            _analysis(highlights=[{"quote": "x", "issue": "y", "better_version": "z"}] * 6)
        )
    with pytest.raises(ValidationError):
        HighlightOut.model_validate({"quote": "x" * 301, "issue": "y", "better_version": "z"})
    with pytest.raises(ValidationError):
        GrammarFixOut.model_validate({"original": "o" * 301, "corrected": "c", "explanation": "e"})
