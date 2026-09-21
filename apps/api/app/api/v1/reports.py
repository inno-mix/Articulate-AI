from uuid import UUID

from fastapi import APIRouter

from app.deps import CurrentUser, DbDep
from app.schemas.report import ReportOut, RetryOut
from app.services import feedback as feedback_service

router = APIRouter(tags=["reports"])


@router.get("/sessions/{session_id}/report")
async def get_report(session_id: UUID, user: CurrentUser, db: DbDep) -> ReportOut:
    return await feedback_service.get_report(db, user.id, session_id)


@router.post("/sessions/{session_id}/report/retry", status_code=202)
async def retry_report(session_id: UUID, user: CurrentUser, db: DbDep) -> RetryOut:
    return await feedback_service.retry_report(db, user.id, session_id)
