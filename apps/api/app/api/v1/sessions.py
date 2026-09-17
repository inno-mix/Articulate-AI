from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbDep, LLMDep
from app.domain.enums import SessionStatus
from app.schemas.common import Page
from app.schemas.session import CreateSessionIn, EndSessionOut, SessionDetail, SessionSummary
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


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: UUID, user: CurrentUser, db: DbDep) -> EndSessionOut:
    return await sessions_service.end_session(db, user.id, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: UUID, user: CurrentUser, db: DbDep) -> None:
    await sessions_service.delete_session(db, user.id, session_id)
