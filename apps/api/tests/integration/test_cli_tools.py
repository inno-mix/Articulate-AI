from collections.abc import Awaitable, Callable

import pytest
from redis.asyncio import Redis

from app.cli import flush_redis, ping_worker
from app.core.config import Settings


async def test_ping_worker_prints_the_worker_reply(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    await ping_worker(settings)

    # The in-memory broker runs the task inline, so its log line is printed first.
    assert capsys.readouterr().out.splitlines()[-1] == "pong:cli"


async def test_flush_redis_empties_only_the_configured_database(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    target = settings.model_copy(update={"redis_url": "redis://localhost:6379/14"})
    neighbour = Redis.from_url("redis://localhost:6379/15")
    client = Redis.from_url(target.redis_url)
    try:
        await client.set("leftover", "1")
        await neighbour.set("keep", "1")

        await flush_redis(target)

        assert await client.dbsize() == 0
        assert await neighbour.get("keep") == b"1"
        assert "redis db 14 flushed" in capsys.readouterr().out
    finally:
        await neighbour.delete("keep")
        await client.aclose()
        await neighbour.aclose()


@pytest.mark.parametrize("command", [ping_worker, flush_redis])
async def test_dev_tools_refuse_in_production(
    command: Callable[[Settings], Awaitable[None]], settings: Settings
) -> None:
    production = settings.model_copy(update={"app_env": "production"})

    with pytest.raises(SystemExit, match="production"):
        await command(production)
