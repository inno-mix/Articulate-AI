import pytest
from pydantic_ai import models
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from app.llm.providers import build_model

models.ALLOW_MODEL_REQUESTS = False


def test_build_model_anthropic_uses_tool_output() -> None:
    model, output_mode = build_model("anthropic", "claude-3-5-haiku-latest", "fake-key")

    assert isinstance(model, AnthropicModel)
    assert output_mode == "tool"


def test_build_model_openai_uses_tool_output() -> None:
    model, output_mode = build_model("openai", "gpt-4o-mini", "fake-key")

    assert isinstance(model, OpenAIChatModel)
    assert output_mode == "tool"


def test_build_model_google_uses_tool_output() -> None:
    model, output_mode = build_model("google", "gemini-3.7-flash", "fake-key")

    assert isinstance(model, GoogleModel)
    assert output_mode == "tool"


def test_build_model_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        build_model("mistral", "some-model", "fake-key")  # type: ignore[arg-type]
