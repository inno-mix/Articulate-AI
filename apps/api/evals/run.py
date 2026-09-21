"""Feedback eval runner (ai-layer.md §8).

    uv run python -m evals.run --provider ollama --model qwen3:4b
    uv run python -m evals.run --provider anthropic --model <verified model id>

Builds prompts with the same `app.services.feedback.build_feedback_prompts` the app uses. Ollama
runs the same `PydanticAILLMService` the app uses; cloud providers go through `build_model` with
the key from `Settings.eval_<provider>_api_key` (never printed or logged). Writes a JSON result
file per run and prints a summary table.
"""

import argparse
import asyncio
import glob
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import yaml

from app.content.loader import ContentError, ScenarioFile, load_scenario_files
from app.content.rubrics import get_rubric
from app.core.config import Settings, get_settings
from app.domain.enums import MessageRole, MessageSource, Seniority
from app.llm.base import LLMService
from app.llm.errors import LLMError
from app.llm.generation import TEMPERATURE
from app.llm.outputs import FeedbackAnalysis
from app.llm.providers import build_model
from app.llm.pydantic_ai_service import PydanticAILLMService, thinks_by_default
from app.models import Message
from app.services.feedback import build_feedback_prompts
from app.services.scoring import filter_highlights
from app.services.transcript import TranscriptLine, format_transcript
from evals.scoring import CaseResult, EvalCase, score_case, summarise

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO_ROOT / "content" / "scenarios"
DEFAULT_CASES_GLOB = str(Path(__file__).resolve().parent / "cases" / "*.yaml")
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RUBRIC_VERSION = "v1"
# Structured feedback generation is slower than a chat turn (ADR-0006: "10-90s on a local
# model") and eval runs aren't interactive, so this is far more generous than the app's
# request-time default (`Settings.llm_timeout_seconds`, 60s).
EVAL_TIMEOUT_SECONDS = 120.0


def load_cases(pattern: str) -> list[EvalCase]:
    cases = []
    for path in sorted(glob.glob(pattern)):
        raw = yaml.safe_load(Path(path).read_text())
        try:
            cases.append(EvalCase.model_validate(raw))
        except Exception as exc:  # pydantic ValidationError, wrapped with the file name
            raise ContentError(Path(path), str(exc)) from exc
    return cases


def _build_llm(provider: str, model: str, settings: Settings) -> LLMService:
    if provider == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider

        ollama_model = OllamaModel(
            model, provider=OllamaProvider(base_url=f"{settings.ollama_base_url}/v1")
        )
        return PydanticAILLMService(
            model=ollama_model,
            provider="ollama",
            model_name=model,
            output_mode="native",
            timeout_seconds=EVAL_TIMEOUT_SECONDS,
            disable_thinking=thinks_by_default(model),
        )

    key_by_provider = {
        "anthropic": settings.eval_anthropic_api_key,
        "openai": settings.eval_openai_api_key,
        "google": settings.eval_google_api_key,
    }
    secret = key_by_provider.get(provider)
    if secret is None:
        raise SystemExit(
            f"No EVAL_{provider.upper()}_API_KEY set in apps/api/.env — "
            "refusing to fall back to Ollama."
        )
    cloud_model, output_mode = build_model(  # type: ignore[arg-type]
        provider, model, secret.get_secret_value()
    )
    return PydanticAILLMService(
        model=cloud_model,
        provider=provider,
        model_name=model,
        output_mode=output_mode,
        timeout_seconds=EVAL_TIMEOUT_SECONDS,
    )


def _scenario_transcript(case: EvalCase, persona_name: str) -> tuple[list[Message], str]:
    """Eval-case turns as in-memory `Message`s (for quote filtering) plus formatted text."""
    messages = [
        Message(
            id=uuid4(),
            seq=i,
            role=MessageRole.USER if turn.role == "user" else MessageRole.ASSISTANT,
            content=turn.content,
            source=MessageSource.TEXT,
        )
        for i, turn in enumerate(case.transcript)
    ]
    lines = [
        TranscriptLine(
            index=m.seq,
            speaker="USER" if m.role == MessageRole.USER else "PERSONA",
            text=m.content,
            message_id=m.id,
        )
        for m in messages
    ]
    return messages, format_transcript(lines, persona_name=persona_name, truncated=False)


async def run_case(
    llm: LLMService, scenarios: dict[str, ScenarioFile], case: EvalCase
) -> CaseResult:
    scenario_file = scenarios.get(case.scenario_slug)
    if scenario_file is None:
        raise SystemExit(
            f"eval case {case.id!r} references unknown scenario {case.scenario_slug!r}"
        )

    messages, transcript_text = _scenario_transcript(case, scenario_file.persona.name)
    profile = SimpleNamespace(seniority=Seniority.MID, english_level=case.learner_level)

    system_prompt, user_prompt = build_feedback_prompts(
        scenario=scenario_file,  # type: ignore[arg-type]
        profile=profile,  # type: ignore[arg-type]
        rubric=get_rubric(RUBRIC_VERSION),
        transcript_text=transcript_text,
        speaking_summary=None,
    )

    start = time.monotonic()
    analysis: FeedbackAnalysis | None = None
    try:
        analysis, _usage = await llm.generate_structured(
            system=system_prompt.text,
            prompt=user_prompt.text,
            output_type=FeedbackAnalysis,
            temperature=TEMPERATURE["feedback"],
        )
    except LLMError:
        analysis = None
    latency_ms = int((time.monotonic() - start) * 1000)

    user_messages = [m for m in messages if m.role == MessageRole.USER]
    highlights = filter_highlights(analysis.highlights, user_messages) if analysis else []

    return score_case(case, analysis, highlights, latency_ms)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run feedback quality evals.")
    parser.add_argument(
        "--provider", required=True, choices=["ollama", "anthropic", "openai", "google"]
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--cases", default=DEFAULT_CASES_GLOB)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    settings = get_settings()
    cases = load_cases(args.cases)
    scenario_files = load_scenario_files(SCENARIOS_DIR)
    scenarios = {s.slug: s for s in scenario_files}

    planned = len(cases) * args.repeat
    print(f"{planned} model calls planned ({len(cases)} cases x {args.repeat} repeat)")

    llm = _build_llm(args.provider, args.model, settings)
    results: list[CaseResult] = []
    for _ in range(args.repeat):
        for case in cases:
            result = await run_case(llm, scenarios, case)
            results.append(result)
            print(f"  {case.id}: schema_failed={result.schema_failed} in_range={result.in_range}")

    summary = summarise(results)
    print("\n--- summary ---")
    for field, value in asdict(summary).items():
        print(f"{field}: {value}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"{timestamp}-{args.provider}-{args.model.replace('/', '_')}.json"
    out_path.write_text(
        json.dumps(
            {
                "provider": args.provider,
                "model": args.model,
                "timestamp": timestamp,
                "cases": [asdict(r) for r in results],
                "summary": asdict(summary),
            },
            indent=2,
        )
    )
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
