"""Chat turns and streaming replies (api-contract.md §4; ai-layer.md §4; coding-conventions.md §2).

No DB session is held while the LLM streams: `prepare_user_turn` loads context, saves the user
message and commits (releasing the connection) before `stream_reply` starts iterating the LLM's
stream; `stream_reply` opens a fresh session only to save the result afterward. `generate_hint`
does the same, then reuses its (now-idle) session to record usage once the LLM call returns.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sse import format_sse
from app.core.db import SessionFactory
from app.core.errors import (
    AppError,
    LLMAuthFailedAppError,
    LLMInvalidOutputAppError,
    LLMNotConfiguredAppError,
    LLMRateLimitedAppError,
    LLMUnavailableAppError,
    NotFoundError,
    SessionNotActiveError,
    TurnLimitReachedError,
)
from app.domain.enums import MessageRole, MessageSource, SessionStatus, UsageKind
from app.domain.limits import MAX_USER_TURNS
from app.llm.base import ChatTurn, LLMService
from app.llm.errors import (
    LLMAuthError,
    LLMError,
    LLMInvalidOutputError,
    LLMNotConfiguredError,
    LLMRateLimitedError,
    LLMUnavailableError,
)
from app.llm.generation import TEMPERATURE
from app.llm.prompts import render_prompt, user_block
from app.models import Message, PracticeSession, Scenario, User
from app.schemas.session import MessageOut
from app.services import sessions as sessions_service
from app.services import usage as usage_service
from app.services.locks import session_reply_lock
from app.services.safety import SAFETY_MESSAGE, detect_crisis

_LLM_APP_ERRORS: dict[type[LLMError], type[AppError]] = {
    LLMUnavailableError: LLMUnavailableAppError,
    LLMRateLimitedError: LLMRateLimitedAppError,
    LLMAuthError: LLMAuthFailedAppError,
    LLMInvalidOutputError: LLMInvalidOutputAppError,
    LLMNotConfiguredError: LLMNotConfiguredAppError,
}


def _to_app_error(exc: LLMError) -> AppError:
    return _LLM_APP_ERRORS.get(type(exc), LLMUnavailableAppError)()


def build_history(messages: list[Message]) -> list[ChatTurn]:
    """Chat turns for `LLMService.stream_chat`'s `history`. Includes the opening line (seq 0) as
    an assistant turn; merges consecutive same-role messages with a blank line; drops the crisis
    safety reply (`source=system`) — the model should never see its own "stepping out" line."""
    turns: list[ChatTurn] = []
    for message in messages:
        if message.source == MessageSource.SYSTEM:
            continue
        role: Literal["user", "assistant"] = (
            "user" if message.role == MessageRole.USER else "assistant"
        )
        if turns and turns[-1].role == role:
            turns[-1] = ChatTurn(role=role, content=f"{turns[-1].content}\n\n{message.content}")
        else:
            turns.append(ChatTurn(role=role, content=message.content))
    return turns


@dataclass(frozen=True)
class PreparedTurn:
    session: PracticeSession
    user_message: Message
    history: list[ChatTurn]
    system_prompt: str
    prompt_version: str
    is_crisis: bool


def _scenario_context(scenario: Scenario) -> dict[str, str]:
    return {
        "title": scenario.title,
        "summary": scenario.summary,
        "user_objective": scenario.user_objective,
    }


def _learner_context(user: User) -> dict[str, str]:
    return {
        "seniority": user.profile.seniority.value,
        "english_level": user.profile.english_level.value,
    }


async def prepare_user_turn(
    db: AsyncSession, user: User, session_id: UUID, content: str
) -> PreparedTurn:
    session = await sessions_service.get_owned_session(db, user.id, session_id, for_update=True)
    if session.status != SessionStatus.ACTIVE:
        raise SessionNotActiveError()
    if session.user_turns >= MAX_USER_TURNS:
        raise TurnLimitReachedError()

    is_crisis = detect_crisis(content)
    user_message = await sessions_service.add_message(
        db,
        session,
        role=MessageRole.USER,
        content=content,
        source=MessageSource(session.mode.value),
    )

    prior_messages = list(
        await db.scalars(
            select(Message)
            .where(Message.session_id == session.id, Message.id != user_message.id)
            .order_by(Message.seq)
        )
    )
    history = build_history(prior_messages)

    scenario = await db.get(Scenario, session.scenario_id)
    if scenario is None:
        raise NotFoundError()
    rendered = render_prompt(
        "roleplay_system",
        persona=scenario.persona,
        scenario=_scenario_context(scenario),
        learner=_learner_context(user),
        mode=session.mode.value,
        coach_notes=[],  # Phase 5 adds coach notes
    )

    # Release the connection before streaming: no DB session is held while the LLM streams.
    await db.commit()

    return PreparedTurn(
        session=session,
        user_message=user_message,
        history=history,
        system_prompt=rendered.text,
        prompt_version=rendered.version,
        is_crisis=is_crisis,
    )


async def stream_reply(
    session_factory: SessionFactory,
    redis: Redis,
    llm: LLMService,
    prepared: PreparedTurn,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    # The lock is acquired here, on this generator's first `__anext__()` — the endpoint primes it
    # (awaits one item) before constructing the StreamingResponse, so a `ReplyInProgressError`
    # here is still a normal JSON error, never a mid-stream one. Released in this `finally`.
    async with session_reply_lock(redis, prepared.session.id):
        yield format_sse("user_message", MessageOut.model_validate(prepared.user_message))

        if prepared.is_crisis:
            async with session_factory() as db:
                session = await db.get(PracticeSession, prepared.session.id)
                if session is None:
                    return
                session.safety_flag = True
                assistant_message = await sessions_service.add_message(
                    db,
                    session,
                    role=MessageRole.ASSISTANT,
                    content=SAFETY_MESSAGE,
                    source=MessageSource.SYSTEM,
                )
                user_turns = session.user_turns
                await db.commit()
            yield format_sse("delta", {"text": SAFETY_MESSAGE})
            yield format_sse("assistant_message", MessageOut.model_validate(assistant_message))
            yield format_sse(
                "done", {"user_turns": user_turns, "turns_left": MAX_USER_TURNS - user_turns}
            )
            return

        collected: list[str] = []
        try:
            async for delta in llm.stream_chat(
                system=prepared.system_prompt,
                history=prepared.history,
                user_message=prepared.user_message.content,
                temperature=TEMPERATURE["roleplay"],
            ):
                if await is_disconnected():
                    return  # no partial assistant message is saved
                collected.append(delta)
                yield format_sse("delta", {"text": delta})
        except LLMError as exc:
            app_error = _to_app_error(exc)
            yield format_sse("error", {"code": app_error.code, "message": app_error.message})
            return

        usage = llm.last_usage()
        full_text = "".join(collected)
        async with session_factory() as db:
            session = await db.get(PracticeSession, prepared.session.id)
            if session is None:
                return
            assistant_message = await sessions_service.add_message(
                db,
                session,
                role=MessageRole.ASSISTANT,
                content=full_text,
                source=MessageSource(session.mode.value),
            )
            await usage_service.record_usage(
                db,
                user_id=session.user_id,
                kind=UsageKind.LLM,
                feature="roleplay",
                provider=llm.provider,
                model=llm.model,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                latency_ms=usage.latency_ms if usage else None,
            )
            user_turns = session.user_turns
            await db.commit()
        yield format_sse("assistant_message", MessageOut.model_validate(assistant_message))
        yield format_sse(
            "done", {"user_turns": user_turns, "turns_left": MAX_USER_TURNS - user_turns}
        )


async def generate_hint(db: AsyncSession, user: User, session_id: UUID, llm: LLMService) -> str:
    session = await sessions_service.get_owned_session(db, user.id, session_id)
    if session.status != SessionStatus.ACTIVE:
        raise SessionNotActiveError()

    scenario = await db.get(Scenario, session.scenario_id)
    if scenario is None:
        raise NotFoundError()

    messages = list(
        await db.scalars(
            select(Message).where(Message.session_id == session.id).order_by(Message.seq)
        )
    )
    transcript = "\n".join(
        f"{'USER' if m.role == MessageRole.USER else 'PERSONA'}: {m.content}"
        for m in messages
        if m.source != MessageSource.SYSTEM
    )

    rendered = render_prompt(
        "hint",
        persona=scenario.persona,
        scenario=_scenario_context(scenario),
        learner=_learner_context(user),
    )
    prompt = user_block(recent_transcript=transcript)
    user_id = session.user_id

    # Release the connection before calling the LLM.
    await db.commit()

    try:
        hint = await llm.complete_text(
            system=rendered.text, prompt=prompt, max_chars=200, temperature=TEMPERATURE["hint"]
        )
    except LLMError as exc:
        raise _to_app_error(exc) from exc

    # `db`'s connection was released by the commit above; reusing it here starts a fresh
    # transaction rather than holding one open for the whole LLM call (ai-layer.md §9).
    usage = llm.last_usage()
    await usage_service.record_usage(
        db,
        user_id=user_id,
        kind=UsageKind.LLM,
        feature="hint",
        provider=llm.provider,
        model=llm.model,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        latency_ms=usage.latency_ms if usage else None,
    )
    await db.commit()

    return hint
