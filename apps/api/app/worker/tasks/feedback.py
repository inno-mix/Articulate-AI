"""Feedback report generation task (ADR-0006; overview.md §4.2)."""

from uuid import UUID

from app.services.feedback import generate_report
from app.worker.broker import broker


@broker.task(task_name="generate_feedback_report")
async def generate_feedback_report(report_id: str) -> None:
    await generate_report(broker.state.session_factory, broker.state.settings, UUID(report_id))


async def enqueue_report(report_id: UUID) -> None:
    """The only way services enqueue a report generation job (ADR-0006)."""
    await generate_feedback_report.kiq(str(report_id))
