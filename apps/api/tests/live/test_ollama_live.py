"""Tests against a real local Ollama server. Run with `make test-live` (Ollama must be running).

Excluded by default (`addopts = "-m 'not live'"`); never run in CI or `make check`.
"""

import pytest
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.pydantic_ai_service import PydanticAILLMService

pytestmark = pytest.mark.live


class Echo(BaseModel):
    word: str


def _ollama_service() -> PydanticAILLMService:
    from pydantic_ai.models.ollama import OllamaModel
    from pydantic_ai.providers.ollama import OllamaProvider

    settings = get_settings()
    model = OllamaModel(
        settings.ollama_model,
        provider=OllamaProvider(base_url=f"{settings.ollama_base_url}/v1"),
    )
    return PydanticAILLMService(
        model=model, provider="ollama", output_mode="native", timeout_seconds=30.0
    )


async def test_stream_chat_streams_a_one_sentence_reply() -> None:
    service = _ollama_service()

    deltas = [
        d
        async for d in service.stream_chat(
            system="You are a helpful assistant. Reply in exactly one short sentence.",
            history=[],
            user_message="Say hello.",
        )
    ]

    assert deltas
    assert "".join(deltas).strip()


async def test_generate_structured_returns_a_validated_echo() -> None:
    service = _ollama_service()

    result, usage = await service.generate_structured(
        system="Echo back exactly the single word 'ping' in the `word` field.",
        prompt="ping",
        output_type=Echo,
    )

    assert result.word
    assert usage.latency_ms >= 0
