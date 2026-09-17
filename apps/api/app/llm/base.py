"""The `LLMService` contract every adapter implements (ai-layer.md §1, binding)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class LLMService(Protocol):
    provider: str  # "ollama" | "fake" | "anthropic" | "openai" | "google"
    model: str

    def stream_chat(
        self,
        *,
        system: str,
        history: list[ChatTurn],
        user_message: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield text deltas. Raises LLMUnavailableError / LLMRateLimitedError / LLMAuthError."""
        ...

    async def complete_text(
        self, *, system: str, prompt: str, max_chars: int, temperature: float = 0.7
    ) -> str:
        """Single short completion (hints). Output is stripped and truncated to max_chars."""
        ...

    async def generate_structured(
        self, *, system: str, prompt: str, output_type: type[T], temperature: float = 0.0
    ) -> tuple[T, LLMUsage]:
        """Return a validated instance of output_type.

        Retries (max 2) on validation failure, then raises LLMInvalidOutputError.
        """
        ...

    def last_usage(self) -> LLMUsage | None:
        """Usage of the most recent stream_chat/complete_text call (for usage_events)."""
        ...
