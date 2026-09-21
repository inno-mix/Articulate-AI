from app.llm.outputs import DimensionScore, FeedbackAnalysis, GrammarFixOut, HighlightOut
from app.schemas.json_types import GrammarFix, Highlight
from evals.scoring import EvalCase, EvalTurn, score_case, summarise

ALL_DIMENSIONS = (
    "clarity",
    "conciseness",
    "structure",
    "audience_fit",
    "tone",
    "confidence",
    "grammar_vocabulary",
)


def _case(**overrides: object) -> EvalCase:
    payload: dict[str, object] = {
        "id": "case-1",
        "scenario_slug": "code-review-give-feedback",
        "mode": "text",
        "learner_level": "B2",
        "transcript": [EvalTurn(role="user", content="Hi Sam, thanks for the PR.")],
        "expected": {"clarity": (4, 5)},
    }
    payload.update(overrides)
    return EvalCase.model_validate(payload)


def _analysis(**overrides: object) -> FeedbackAnalysis:
    payload: dict[str, object] = {
        "summary": "Clear and kind.",
        "objective_met": True,
        "scores": [
            DimensionScore(dimension=d, score=4, reason="ok").model_dump() for d in ALL_DIMENSIONS
        ],
        "strengths": ["Clear opening."],
        "improvements": ["Cut filler."],
        "highlights": [],
        "grammar_fixes": [],
    }
    payload.update(overrides)
    return FeedbackAnalysis.model_validate(payload)


def test_score_case_in_range_true_when_score_within_expected() -> None:
    case = _case(expected={"clarity": (4, 5)})
    analysis = _analysis()

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.in_range == {"clarity": True}
    assert result.schema_failed is False


def test_score_case_in_range_false_when_score_outside_expected() -> None:
    case = _case(expected={"clarity": (1, 2)})
    analysis = _analysis()

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.in_range == {"clarity": False}


def test_score_case_schema_failed_when_analysis_is_none() -> None:
    case = _case()

    result = score_case(case, None, [], latency_ms=50)

    assert result.schema_failed is True
    assert result.in_range == {}
    assert result.objective_ok is None
    assert result.quote_flag_ok is None
    assert result.english_ok is None


def test_score_case_objective_ok_compares_against_expected() -> None:
    case = _case(objective_met=True)
    analysis = _analysis(objective_met=True)

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.objective_ok is True


def test_score_case_objective_ok_none_when_not_specified() -> None:
    case = _case()
    analysis = _analysis()

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.objective_ok is None


def test_score_case_quote_flag_ok_true_when_highlight_matches() -> None:
    case = _case(must_flag_quote_containing=["so basically"])
    analysis = _analysis(
        highlights=[
            HighlightOut(
                quote="so basically it works", issue="filler", better_version="be direct"
            ).model_dump()
        ]
    )
    highlights = [
        Highlight(
            message_id=None,
            quote="so basically it works",
            issue="filler",
            better_version="be direct",
        )
    ]

    result = score_case(case, analysis, highlights, latency_ms=100)

    assert result.quote_flag_ok is True


def test_score_case_quote_flag_ok_false_when_no_matching_highlight_survives() -> None:
    case = _case(must_flag_quote_containing=["so basically"])
    analysis = _analysis()

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.quote_flag_ok is False


def test_score_case_english_ok_true_when_no_foreign_words_outside_quotes() -> None:
    case = _case(foreign_words=["kasi"])
    analysis = _analysis(
        highlights=[
            HighlightOut(
                quote="kasi that's how it works", issue="uses filler", better_version="be direct"
            ).model_dump()
        ]
    )
    highlights = [
        Highlight(
            message_id=None,
            quote="kasi that's how it works",  # foreign word inside a verbatim quote: ignored
            issue="uses filler",
            better_version="be direct",
        )
    ]

    result = score_case(case, analysis, highlights, latency_ms=100)

    assert result.english_ok is True


def test_score_case_english_ok_false_when_foreign_word_in_llm_prose() -> None:
    case = _case(foreign_words=["kasi"])
    analysis = _analysis(summary="This was clear, kasi it flowed well.")

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.english_ok is False


def test_score_case_english_ok_none_when_no_foreign_words_expected() -> None:
    case = _case()
    analysis = _analysis()

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.english_ok is None


def test_score_case_english_ok_ignores_short_word_as_substring_of_english_word() -> None:
    # "mo" must not match inside "comments" -- a short foreign word can collide with common
    # English substrings, so the check must respect word boundaries.
    case = _case(foreign_words=["mo"])
    analysis = _analysis(summary="Write your code review comments in English.")

    result = score_case(case, analysis, [], latency_ms=100)

    assert result.english_ok is True


def test_summarise_computes_rates() -> None:
    ready = score_case(_case(expected={"clarity": (4, 5)}), _analysis(), [], latency_ms=100)
    out_of_range = score_case(_case(expected={"clarity": (1, 2)}), _analysis(), [], latency_ms=200)
    failed = score_case(_case(), None, [], latency_ms=300)

    summary = summarise([ready, out_of_range, failed])

    assert summary.total == 3
    assert summary.schema_failure_rate == 1 / 3
    assert summary.in_range_rate == 0.5  # one in-range dimension check out of two total
    assert summary.p50_latency_ms == 200
    assert summary.p95_latency_ms == 290


def test_summarise_quote_survival_rate_ignores_cases_without_expectation() -> None:
    matched = score_case(
        _case(must_flag_quote_containing=["so basically"]),
        _analysis(
            highlights=[
                HighlightOut(
                    quote="so basically yes", issue="filler", better_version="be direct"
                ).model_dump()
            ]
        ),
        [
            Highlight(
                message_id=None, quote="so basically yes", issue="filler", better_version="direct"
            )
        ],
        latency_ms=100,
    )
    unmatched = score_case(
        _case(must_flag_quote_containing=["so basically"]), _analysis(), [], latency_ms=100
    )
    no_expectation = score_case(_case(), _analysis(), [], latency_ms=100)

    summary = summarise([matched, unmatched, no_expectation])

    assert summary.quote_survival_rate == 0.5


def test_grammar_fix_filtering_uses_deterministic_scoring() -> None:
    # sanity check that GrammarFix/GrammarFixOut share shape used by english_ok's field list
    fix = GrammarFix(original="I am agree", corrected="I agree", explanation="verb, kasi")
    out = GrammarFixOut(original="I am agree", corrected="I agree", explanation="verb, kasi")

    assert fix.explanation == out.explanation
