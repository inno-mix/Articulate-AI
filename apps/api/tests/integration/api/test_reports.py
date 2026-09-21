from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MessageRole, ReportStatus, SessionStatus
from app.models import User
from app.services.feedback import create_pending_report
from tests.factories import make_message, make_scenario, make_session


async def test_end_abandoned_session_has_no_report(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-abandoned")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=1)
    await db.commit()

    await client.post(f"/api/v1/sessions/{session.id}/end")
    response = await client.get(f"/api/v1/sessions/{session.id}/report")

    assert response.status_code == 404


async def test_get_report_pending_has_null_fields(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-pending")
    session = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ENDED, user_turns=2
    )
    await create_pending_report(db, session)
    await db.commit()

    response = await client.get(f"/api/v1/sessions/{session.id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["overall_score"] is None
    assert body["summary"] is None
    assert body["dimension_scores"] is None


async def test_get_report_ready_returns_full_payload(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-ready")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=2)
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    await db.commit()
    await client.post(f"/api/v1/sessions/{session.id}/end")

    response = await client.get(f"/api/v1/sessions/{session.id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert isinstance(body["overall_score"], int)
    assert body["objective_met"] in (True, False)
    assert isinstance(body["summary"], str)
    assert len(body["dimension_scores"]) == 7
    assert isinstance(body["strengths"], list)
    assert isinstance(body["improvements"], list)
    assert isinstance(body["highlights"], list)
    assert isinstance(body["grammar_fixes"], list)
    assert body["voice_metrics"] is None
    assert body["rubric_version"] == "v1"
    assert body["llm_model"] == "fake"
    assert body["created_at"]
    assert body["updated_at"]
    assert body["completed_at"]


async def test_get_other_users_report_returns_404(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User, other_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-not-mine")
    session = await make_session(
        db,
        user_id=other_user.id,
        scenario_id=scenario.id,
        status=SessionStatus.ENDED,
        user_turns=2,
    )
    await create_pending_report(db, session)
    await db.commit()

    response = await client.get(f"/api/v1/sessions/{session.id}/report")

    assert response.status_code == 404


async def test_retry_failed_report_requeues(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-retry-failed")
    session = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ENDED, user_turns=2
    )
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    report = await create_pending_report(db, session)
    report.status = ReportStatus.FAILED
    report.error_code = "llm_unavailable"
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/report/retry")

    assert response.status_code == 202
    assert response.json()["status"] == "pending"


async def test_retry_fresh_pending_report_returns_409(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-retry-fresh-pending")
    session = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ENDED, user_turns=2
    )
    await create_pending_report(db, session)
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/report/retry")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_not_ready"


async def test_retry_stale_running_report_requeues(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-retry-stale")
    session = await make_session(
        db, user_id=local_user.id, scenario_id=scenario.id, status=SessionStatus.ENDED, user_turns=2
    )
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    report = await create_pending_report(db, session)
    report.status = ReportStatus.RUNNING
    report.updated_at = datetime.now(UTC) - timedelta(minutes=6)
    await db.commit()

    response = await client.post(f"/api/v1/sessions/{session.id}/report/retry")

    assert response.status_code == 202
    assert response.json()["status"] == "pending"


async def test_retry_ready_report_regenerates(
    client: httpx.AsyncClient, db: AsyncSession, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="report-retry-ready")
    session = await make_session(db, user_id=local_user.id, scenario_id=scenario.id, user_turns=2)
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    await db.commit()
    await client.post(f"/api/v1/sessions/{session.id}/end")  # runs to "ready" synchronously

    response = await client.post(f"/api/v1/sessions/{session.id}/report/retry")

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
