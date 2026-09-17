import pytest

from app.llm.errors import LLMInvalidOutputError
from app.llm.fake import FakeLLMService
from app.llm.outputs import DrillFeedback


async def test_stream_chat_yields_documented_deltas() -> None:
    fake = FakeLLMService()

    deltas = [d async for d in fake.stream_chat(system="sys", history=[], user_message="Hi Dana")]

    assert deltas == ["Fake reply ", "to: ", "Hi Dana"]


async def test_stream_chat_truncates_user_message_to_40_chars() -> None:
    fake = FakeLLMService()
    long_message = "x" * 60

    deltas = [
        d async for d in fake.stream_chat(system="sys", history=[], user_message=long_message)
    ]

    assert deltas[-1] == "x" * 40


async def test_complete_text_returns_fixed_hint() -> None:
    fake = FakeLLMService()

    result = await fake.complete_text(system="sys", prompt="p", max_chars=100)

    assert result == "Try saying: fake hint."


async def test_generate_structured_returns_fake_output() -> None:
    fake = FakeLLMService()

    result, usage = await fake.generate_structured(
        system="sys", prompt="p", output_type=DrillFeedback
    )

    assert isinstance(result, DrillFeedback)
    assert result.score == 4
    assert usage.latency_ms >= 0


async def test_generate_structured_override_and_fail_times() -> None:
    fake = FakeLLMService(
        structured={
            "DrillFeedback": {"score": 1, "feedback": "Try again.", "better_version": None}
        },
        fail_times=1,
    )

    with pytest.raises(LLMInvalidOutputError):
        await fake.generate_structured(system="sys", prompt="p", output_type=DrillFeedback)

    result, _usage = await fake.generate_structured(
        system="sys", prompt="p", output_type=DrillFeedback
    )
    assert result.score == 1
    assert result.feedback == "Try again."


async def test_last_usage_is_recorded() -> None:
    fake = FakeLLMService()

    assert fake.last_usage() is None

    await fake.complete_text(system="sys", prompt="p", max_chars=100)

    assert fake.last_usage() is not None


async def test_calls_record_temperature() -> None:
    fake = FakeLLMService()

    await fake.complete_text(system="sys", prompt="hint me", max_chars=10, temperature=0.9)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call.method == "complete_text"
    assert call.temperature == 0.9
    assert call.system == "sys"
    assert call.prompt == "hint me"
