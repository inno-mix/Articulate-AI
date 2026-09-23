"""One Redis client per app process, created in `lifespan` and shared via `app.state.redis`
(tests override `app.state.redis` directly — see `tests/conftest.py`)."""

from fastapi.requests import HTTPConnection
from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url)


def get_redis(conn: HTTPConnection) -> Redis:
    """Takes `HTTPConnection` (the common base of `Request`/`WebSocket`) so this also works as a
    dependency for WebSocket routes (voice-and-pronunciation.md §2)."""
    redis: Redis = conn.app.state.redis
    return redis
