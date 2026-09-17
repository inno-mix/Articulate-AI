from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.sse import sse_response
from app.deps import CurrentUser, DbDep, LLMDep, RedisDep, SessionFactoryDep
from app.domain.enums import SessionStatus
from app.schemas.common import Page
from app.schemas.session import (
    CreateSessionIn,
    EndSessionOut,
    HintOut,
    SendMessageIn,
    SessionDetail,
    SessionSummary,
)
from app.services import chat as chat_service
from app.services import sessions as sessions_service

router = APIRouter(tags=["sessions"])


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionIn, user: CurrentUser, db: DbDep, llm: LLMDep
) -> SessionDetail:
    return await sessions_service.create_session(db, user, body.scenario_id, body.mode, llm)


@router.get("/sessions")
async def list_sessions(
    user: CurrentUser,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
    status: SessionStatus | None = None,
) -> Page[SessionSummary]:
    return await sessions_service.list_sessions(
        db, user.id, limit=limit, cursor=cursor, status=status
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, user: CurrentUser, db: DbDep) -> SessionDetail:
    return await sessions_service.get_session_detail(db, user.id, session_id)


@router.post("/sessions/{session_id}/messages")
async def stream_session_message(
    session_id: UUID,
    body: SendMessageIn,
    user: CurrentUser,
    db: DbDep,
    llm: LLMDep,
    redis: RedisDep,
    session_factory: SessionFactoryDep,
    request: Request,
) -> StreamingResponse:
    prepared = await chat_service.prepare_user_turn(db, user, session_id, body.content)

    generator = chat_service.stream_reply(
        session_factory, redis, llm, prepared, request.is_disconnected
    )
    # Drive the generator up to (and including) its first yield now, before the
    # StreamingResponse exists: this is where the reply lock is acquired, so a
    # `ReplyInProgressError` here is still a normal JSON error (api-contract.md §4).
    first_event = await anext(generator)

    async def primed() -> AsyncIterator[str]:
        yield first_event
        async for event in generator:
            yield event

    return sse_response(primed())


@router.post("/sessions/{session_id}/hint")
async def get_hint(session_id: UUID, user: CurrentUser, db: DbDep, llm: LLMDep) -> HintOut:
    hint = await chat_service.generate_hint(db, user, session_id, llm)
    return HintOut(hint=hint)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: UUID, user: CurrentUser, db: DbDep) -> EndSessionOut:
    return await sessions_service.end_session(db, user.id, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: UUID, user: CurrentUser, db: DbDep) -> None:
    await sessions_service.delete_session(db, user.id, session_id)
