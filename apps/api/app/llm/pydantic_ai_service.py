"""`LLMService` backed by Pydantic AI (ai-layer.md §1-2) — Ollama in dev, cloud models from
Phase 2 (evals) and Phase 9 (user keys) onward.

Context7 `/pydantic/pydantic-ai` v2 (queried 2026-09-17): `Agent.run_stream` is an async context
manager whose `stream_text(delta=True)` yields text deltas; `.usage` (property, not a method) is
only complete once the stream is drained. `openai`-compatible models (Ollama included) map
`openai.APIStatusError` with `status>=400` to `ModelHTTPError` (has `.status_code`) and
`APIConnectionError`/timeouts to the plainer `ModelAPIError`; `UnexpectedModelBehavior` is raised
once the output-validation retry budget is exhausted.
"""

import asyncio
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Literal, TypeVar

from pydantic import BaseModel
from pydantic_ai import (
    Agent,
    ModelHTTPError,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelSettings,
    TextPart,
    UnexpectedModelBehavior,
    UserPromptPart,
)
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models import Model
from pydantic_ai.output import NativeOutput

from app.llm.base import ChatTurn, LLMUsage
from app.llm.errors import (
    LLMAuthError,
    LLMInvalidOutputError,
    LLMRateLimitedError,
    LLMUnavailableError,
)

# Suppress Pydantic AI's first-use ASCII banner: it writes straight to stdout, which would
# corrupt structured JSON logs. Must be set before the first `Agent` is constructed (below, in
# each method) — import time is early enough.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

T = TypeVar("T", bound=BaseModel)
OutputMode = Literal["native", "tool"]

# generate_structured retries this many times on a validation failure before giving up
# (ai-layer.md §1).
_STRUCTURED_RETRIES = 2


def _to_model_messages(history: list[ChatTurn]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for turn in history:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return messages


def _map_http_error(
    exc: ModelHTTPError,
) -> LLMUnavailableError | LLMRateLimitedError | LLMAuthError:
    if exc.status_code == 429:
        return LLMRateLimitedError()
    if exc.status_code in (401, 403):
        return LLMAuthError()
    return LLMUnavailableError()  # 5xx and other unexpected 4xx


class PydanticAILLMService:
    """`LLMService` implementation. `model_name` overrides `model.model_name` (tests use "test")."""

    def __init__(
        self,
        *,
        model: Model,
        provider: str,
        model_name: str | None = None,
        output_mode: OutputMode = "tool",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model = model
        self.provider = provider
        self.model = model_name or model.model_name
        self._output_mode = output_mode
        self._timeout_seconds = timeout_seconds
        self._last_usage: LLMUsage | None = None

    async def stream_chat(
        self,
        *,
        system: str,
        history: list[ChatTurn],
        user_message: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        agent = Agent(self._model, system_prompt=system)
        start = time.monotonic()
        try:
            async with agent.run_stream(
                user_message,
                message_history=_to_model_messages(history),
                model_settings=ModelSettings(temperature=temperature),
            ) as result:
                # debounce_by=None: forward every delta immediately (no artificial buffering).
                stream = result.stream_text(delta=True, debounce_by=None)
                while True:
                    try:
                        delta = await asyncio.wait_for(
                            stream.__anext__(), timeout=self._timeout_seconds
                        )
                    except StopAsyncIteration:
                        break
                    yield delta
                usage = result.usage
        except TimeoutError as exc:
            raise LLMUnavailableError() from exc
        except ModelHTTPError as exc:
            raise _map_http_error(exc) from exc
        except ModelAPIError as exc:
            raise LLMUnavailableError() from exc
        self._last_usage = LLMUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    async def complete_text(
        self, *, system: str, prompt: str, max_chars: int, temperature: float = 0.7
    ) -> str:
        agent = Agent(self._model, system_prompt=system)
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                agent.run(prompt, model_settings=ModelSettings(temperature=temperature)),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMUnavailableError() from exc
        except ModelHTTPError as exc:
            raise _map_http_error(exc) from exc
        except ModelAPIError as exc:
            raise LLMUnavailableError() from exc
        self._last_usage = LLMUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
        return result.output.strip()[:max_chars]

    async def generate_structured(
        self, *, system: str, prompt: str, output_type: type[T], temperature: float = 0.0
    ) -> tuple[T, LLMUsage]:
        output_spec: Any = (
            NativeOutput(output_type) if self._output_mode == "native" else output_type
        )
        agent = Agent(self._model, system_prompt=system, output_type=output_spec)
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                agent.run(
                    prompt,
                    model_settings=ModelSettings(temperature=temperature),
                    retries=_STRUCTURED_RETRIES,
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMUnavailableError() from exc
        except UnexpectedModelBehavior as exc:
            raise LLMInvalidOutputError() from exc
        except ModelHTTPError as exc:
            raise _map_http_error(exc) from exc
        except ModelAPIError as exc:
            raise LLMUnavailableError() from exc
        usage = LLMUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
        self._last_usage = usage
        return result.output, usage

    def last_usage(self) -> LLMUsage | None:
        return self._last_usage
