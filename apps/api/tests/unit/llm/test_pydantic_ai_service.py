import json

import pytest
from pydantic_ai import ModelHTTPError, ModelResponse, TextPart, models
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.llm.base import ChatTurn
from app.llm.errors import LLMInvalidOutputError, LLMUnavailableError
from app.llm.outputs import DrillFeedback
from app.llm.pydantic_ai_service import PydanticAILLMService, thinks_by_default


@pytest.fixture(autouse=True)
def _no_real_model_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)


def _service(model: FunctionModel, *, output_mode: str = "tool") -> PydanticAILLMService:
    return PydanticAILLMService(
        model=model, provider="ollama", model_name="test", output_mode=output_mode
    )


async def test_stream_chat_yields_deltas_in_order() -> None:
    async def stream_fn(messages, info):
        yield "Hel"
        yield "lo "
        yield "there."

    service = _service(FunctionModel(stream_function=stream_fn))

    deltas = [
        d
        async for d in service.stream_chat(
            system="sys", history=[], user_message="hi", temperature=0.5
        )
    ]

    assert deltas == ["Hel", "lo ", "there."]


async def test_stream_chat_passes_history_as_messages() -> None:
    received = {}

    async def stream_fn(messages, info):
        received["messages"] = messages
        yield "ok"

    history = [
        ChatTurn(role="assistant", content="Hi! You wanted to talk?"),
        ChatTurn(role="user", content="Yes, about the deadline."),
    ]
    service = _service(FunctionModel(stream_function=stream_fn))

    async for _ in service.stream_chat(system="sys", history=history, user_message="ok?"):
        pass

    contents = [part.content for msg in received["messages"] for part in msg.parts]
    assert "Hi! You wanted to talk?" in contents
    assert "Yes, about the deadline." in contents
    assert "ok?" in contents


async def test_generate_structured_returns_validated_model() -> None:
    async def handler(messages, info):
        return ModelResponse(
            parts=[
                TextPart(
                    content=json.dumps(
                        {"score": 4, "feedback": "Good work.", "better_version": None}
                    )
                )
            ]
        )

    service = _service(FunctionModel(handler), output_mode="native")

    result, usage = await service.generate_structured(
        system="sys", prompt="p", output_type=DrillFeedback
    )

    assert isinstance(result, DrillFeedback)
    assert result.score == 4
    assert usage.latency_ms >= 0


async def test_generate_structured_retries_then_raises_invalid_output() -> None:
    async def handler(messages, info):
        return ModelResponse(parts=[TextPart(content="not valid json at all")])

    service = _service(FunctionModel(handler), output_mode="native")

    with pytest.raises(LLMInvalidOutputError):
        await service.generate_structured(system="sys", prompt="p", output_type=DrillFeedback)


async def test_connection_error_maps_to_unavailable() -> None:
    async def handler(messages, info):
        raise ModelHTTPError(status_code=500, model_name="test")

    service = _service(FunctionModel(handler))

    with pytest.raises(LLMUnavailableError):
        await service.complete_text(system="sys", prompt="p", max_chars=100)


async def test_complete_text_truncates_to_max_chars() -> None:
    async def handler(messages, info):
        return ModelResponse(parts=[TextPart(content="  This is a long hint response.  ")])

    service = _service(FunctionModel(handler))

    result = await service.complete_text(system="sys", prompt="p", max_chars=10)

    assert result == "This is a "


async def test_temperature_is_passed_as_model_setting() -> None:
    seen = {}

    async def handler(messages, info: AgentInfo):
        seen["temperature"] = (info.model_settings or {}).get("temperature")
        return ModelResponse(parts=[TextPart(content="ok")])

    service = _service(FunctionModel(handler))

    await service.complete_text(system="sys", prompt="p", max_chars=100, temperature=0.42)

    assert seen["temperature"] == 0.42


async def test_generate_structured_defaults_to_temperature_zero() -> None:
    seen = {}

    async def handler(messages, info: AgentInfo):
        seen["temperature"] = (info.model_settings or {}).get("temperature")
        return ModelResponse(
            parts=[
                TextPart(
                    content=json.dumps({"score": 5, "feedback": "Great.", "better_version": None})
                )
            ]
        )

    service = _service(FunctionModel(handler), output_mode="native")

    await service.generate_structured(system="sys", prompt="p", output_type=DrillFeedback)

    assert seen["temperature"] == 0.0


def test_thinks_by_default_detects_qwen3() -> None:
    assert thinks_by_default("qwen3:4b") is True
    assert thinks_by_default("qwen3:8b") is True
    assert thinks_by_default("llama3.2:latest") is False


def test_generation_table_has_every_feature() -> None:
    from app.llm.generation import TEMPERATURE

    assert TEMPERATURE == {
        "roleplay": 0.7,
        "hint": 0.7,
        "custom_scenario": 0.7,
        "drill_generate": 0.8,
        "rewrite": 0.3,
        "feedback": 0.0,
        "memory": 0.0,
        "drill_feedback": 0.0,
    }
