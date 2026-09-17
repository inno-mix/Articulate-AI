"""One Redis client per app process, created in `lifespan` and shared via `app.state.redis`
(tests override `app.state.redis` directly — see `tests/conftest.py`)."""

from fastapi import Request
from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url)


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis
