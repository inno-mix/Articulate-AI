"""One real call to the eval reference model (ADR-0015). Run with `make test-live` — costs a small
amount on the owner's account. Skipped unless an `EVAL_*_API_KEY` is configured.

Excluded by default (`addopts = "-m 'not live'"`); never run in CI or `make check`.
"""

import pytest

from app.core.config import get_settings
from app.llm.outputs import FeedbackAnalysis
from app.llm.providers import build_model
from app.llm.pydantic_ai_service import PydanticAILLMService

pytestmark = pytest.mark.live

# Small, current models per provider (verified against Context7 `/pydantic/pydantic-ai`,
# 2026-09-21) — used only for this smoke test, not `evals/run.py`'s user-chosen model.
_SMOKE_MODELS = {
    "anthropic": "claude-3-5-haiku-latest",
    "openai": "gpt-4o-mini",
    "google": "gemini-3.7-flash",
}


def _configured_provider() -> tuple[str, str] | None:
    settings = get_settings()
    for provider, secret in (
        ("anthropic", settings.eval_anthropic_api_key),
        ("openai", settings.eval_openai_api_key),
        ("google", settings.eval_google_api_key),
    ):
        if secret is not None:
            return provider, secret.get_secret_value()
    return None


async def test_reference_model_returns_a_validated_feedback_analysis() -> None:
    configured = _configured_provider()
    if configured is None:
        pytest.skip("no EVAL_*_API_KEY configured")
    provider, api_key = configured

    model, output_mode = build_model(provider, _SMOKE_MODELS[provider], api_key)
    service = PydanticAILLMService(
        model=model, provider=provider, output_mode=output_mode, timeout_seconds=30.0
    )

    result, usage = await service.generate_structured(
        system=(
            "You are an expert communication coach. Score every one of these dimensions from 1 "
            "to 5 with a one-sentence reason each: clarity, conciseness, structure, audience_fit, "
            "tone, confidence, grammar_vocabulary. Write a short summary, one strength, one "
            "improvement. The user said exactly: 'Hi team, the deploy is done and everything "
            "looks healthy.' Quote only from that sentence if you cite it."
        ),
        prompt="Score the user's message above.",
        output_type=FeedbackAnalysis,
    )

    assert len(result.scores) == 7
    assert result.summary
    assert usage.latency_ms >= 0
