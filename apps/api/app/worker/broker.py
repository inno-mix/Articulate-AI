"""Taskiq broker (ADR-0006). Tests get an in-memory broker; everything else uses Redis.

Worker processes open their own database engine on startup and keep it on `broker.state`
(`settings`, `engine`, `session_factory`); tasks use that, never the API's engine.
"""

import taskiq_fastapi
from taskiq import AsyncBroker, InMemoryBroker, TaskiqEvents, TaskiqState
from taskiq_redis import ListQueueBroker

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_session_factory
from app.core.logging import configure_logging


def build_broker(settings: Settings) -> AsyncBroker:
    if settings.app_env == "test":
        return InMemoryBroker()
    # redis-py 8 defaults to a 5 s socket timeout; taskiq-redis waits for jobs with a
    # blocking BRPOP, so the broker's connections must not time out while idle.
    return ListQueueBroker(settings.redis_url, socket_timeout=None)


broker: AsyncBroker = build_broker(get_settings())
taskiq_fastapi.init(broker, "app.main:app")


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _worker_startup(state: TaskiqState) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.app_env != "development")
    state.settings = settings
    state.engine = create_engine(settings.database_url)
    state.session_factory = create_session_factory(state.engine)


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _worker_shutdown(state: TaskiqState) -> None:
    await state.engine.dispose()
