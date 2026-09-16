from taskiq import InMemoryBroker
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from app.core.config import Settings
from app.worker.broker import RESULT_TTL_SECONDS, broker, build_broker
from app.worker.tasks.system import ping


async def test_tests_use_the_in_memory_broker() -> None:
    assert isinstance(broker, InMemoryBroker)


async def test_ping_task_runs_in_memory_broker() -> None:
    task = await ping.kiq("x")

    result = await task.wait_result(timeout=2)

    assert not result.is_err
    assert result.return_value == "pong:x"


def test_redis_broker_waits_for_jobs_without_socket_timeout(settings: Settings) -> None:
    # redis-py 8 defaults to a 5 s socket timeout, which breaks taskiq-redis's blocking BRPOP.
    dev_settings = settings.model_copy(update={"app_env": "development"})

    redis_broker = build_broker(dev_settings)

    assert isinstance(redis_broker, ListQueueBroker)
    assert redis_broker.connection_pool.connection_kwargs["socket_timeout"] is None


def test_redis_broker_keeps_results_for_an_hour(settings: Settings) -> None:
    dev_settings = settings.model_copy(update={"app_env": "development"})

    redis_broker = build_broker(dev_settings)

    backend = redis_broker.result_backend
    assert isinstance(backend, RedisAsyncResultBackend)
    assert backend.result_ex_time == RESULT_TTL_SECONDS == 3600
