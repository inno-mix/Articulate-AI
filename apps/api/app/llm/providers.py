"""Cloud model builders (ai-layer.md §2, binding). Used by `evals/run.py` (Phase 2, dev-only
reference runs) and reused for per-user keys in Phase 9.

Context7 `/pydantic/pydantic-ai` (queried 2026-09-21): `AnthropicModel`/`OpenAIChatModel`/
`GoogleModel` each take the model name and a `provider=` instance carrying the API key.
"""

from typing import Literal

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.llm.pydantic_ai_service import OutputMode

Provider = Literal["anthropic", "openai", "google"]


def build_model(provider: Provider, model: str, api_key: str) -> tuple[Model, OutputMode]:
    if provider == "anthropic":
        return AnthropicModel(model, provider=AnthropicProvider(api_key=api_key)), "tool"
    if provider == "openai":
        return OpenAIChatModel(model, provider=OpenAIProvider(api_key=api_key)), "tool"
    if provider == "google":
        return GoogleModel(model, provider=GoogleProvider(api_key=api_key)), "tool"
    raise ValueError(f"unknown provider {provider!r}")
