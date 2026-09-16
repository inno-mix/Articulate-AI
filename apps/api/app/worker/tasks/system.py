import structlog

from app.worker.broker import broker

log = structlog.get_logger(__name__)


@broker.task(task_name="ping")
async def ping(value: str) -> str:
    log.info("worker_ping", value=value)
    return f"pong:{value}"
