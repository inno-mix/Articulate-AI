"""Deterministic `LLMService` used when `LLM_PROVIDER=fake` (tests, E2E, offline UI work)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm.base import ChatTurn, LLMUsage
from app.llm.errors import LLMInvalidOutputError
from app.llm.fake_outputs import FAKE_OUTPUTS

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class FakeCall:
    """One call made to the fake, so tests can assert prompts and temperatures."""

    method: str
    temperature: float
    system: str
    prompt: str


class FakeLLMService:
    provider = "fake"
    model = "fake"

    def __init__(
        self,
        *,
        structured: dict[str, dict[str, Any]] | None = None,
        fail_times: int = 0,
    ) -> None:
        self.calls: list[FakeCall] = []
        self._structured_overrides = structured or {}
        self._fail_times = fail_times
        self._fail_counts: dict[str, int] = {}
        self._last_usage: LLMUsage | None = None

    async def stream_chat(
        self,
        *,
        system: str,
        history: list[ChatTurn],
        user_message: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        self.calls.append(FakeCall("stream_chat", temperature, system, user_message))
        self._last_usage = LLMUsage(input_tokens=None, output_tokens=None, latency_ms=0)
        yield "Fake reply "
        yield "to: "
        yield user_message[:40]

    async def complete_text(
        self, *, system: str, prompt: str, max_chars: int, temperature: float = 0.7
    ) -> str:
        self.calls.append(FakeCall("complete_text", temperature, system, prompt))
        self._last_usage = LLMUsage(input_tokens=None, output_tokens=None, latency_ms=0)
        return "Try saying: fake hint."[:max_chars]

    async def generate_structured(
        self, *, system: str, prompt: str, output_type: type[T], temperature: float = 0.0
    ) -> tuple[T, LLMUsage]:
        self.calls.append(FakeCall("generate_structured", temperature, system, prompt))
        name = output_type.__name__
        failed_so_far = self._fail_counts.get(name, 0)
        if failed_so_far < self._fail_times:
            self._fail_counts[name] = failed_so_far + 1
            raise LLMInvalidOutputError()
        data = self._structured_overrides.get(name, FAKE_OUTPUTS[name])
        result = output_type.model_validate(data)
        usage = LLMUsage(input_tokens=None, output_tokens=None, latency_ms=0)
        self._last_usage = usage
        return result, usage

    def last_usage(self) -> LLMUsage | None:
        return self._last_usage
