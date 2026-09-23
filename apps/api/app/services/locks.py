"""Per-session lock so only one reply streams at a time (api-contract.md `reply_in_progress`)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from redis.asyncio import Redis

from app.core.errors import ReplyInProgressError


def lock_key(session_id: UUID) -> str:
    return f"session-reply-lock:{session_id}"


def voice_session_lock_key(session_id: UUID) -> str:
    """One active voice WebSocket per session (voice-and-pronunciation.md §2.1)."""
    return f"voice:session:{session_id}"


@asynccontextmanager
async def session_reply_lock(
    redis: Redis, session_id: UUID, ttl_s: int = 120
) -> AsyncIterator[None]:
    key = lock_key(session_id)
    acquired = await redis.set(key, "1", nx=True, ex=ttl_s)
    if not acquired:
        raise ReplyInProgressError()
    try:
        yield
    finally:
        await redis.delete(key)
