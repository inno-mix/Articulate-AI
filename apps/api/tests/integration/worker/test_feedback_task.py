import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import MessageRole, ReportStatus, SessionStatus
from app.models import FeedbackReport, User
from app.services.feedback import create_pending_report
from app.worker.broker import broker
from app.worker.tasks.feedback import generate_feedback_report
from tests.factories import make_message, make_scenario, make_session
from tests.support.db import LockedSessionFactory


@pytest.fixture(autouse=True)
def _broker_state(settings: Settings, session_factory: LockedSessionFactory) -> None:
    # Worker startup normally populates this (ADR-0006); InMemoryBroker never fires that event
    # for client-side `.kiq()` calls, so tests set it directly.
    broker.state.settings = settings
    broker.state.session_factory = session_factory


async def test_task_runs_generation(
    db: AsyncSession, session_factory: LockedSessionFactory, local_user: User
) -> None:
    scenario = await make_scenario(db, slug="feedback-task")
    session = await make_session(
        db,
        user_id=local_user.id,
        scenario_id=scenario.id,
        status=SessionStatus.ENDED,
        user_turns=1,
    )
    await make_message(db, session, role=MessageRole.ASSISTANT, content=scenario.opening_line)
    await make_message(db, session, role=MessageRole.USER, content="Hi Sam, thanks for the PR.")
    report = await create_pending_report(db, session)
    await db.commit()

    task = await generate_feedback_report.kiq(str(report.id))
    result = await task.wait_result(timeout=2)

    assert not result.is_err
    async with session_factory() as fresh:
        saved = await fresh.get(FeedbackReport, report.id)
        assert saved is not None
        assert saved.status == ReportStatus.READY
