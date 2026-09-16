"""Session factory for tests: every session shares one connection (and its outer transaction).

A lock makes sure two tasks never use the connection at the same time (asyncpg forbids it).
Waiting longer than the timeout means a session was nested or held too long.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

LOCK_TIMEOUT_MESSAGE = "DB session held too long or nested — keep sessions short"


class LockedSessionFactory:
    def __init__(
        self, connection: Any, *, timeout_s: float = 5.0, session_cls: Any = AsyncSession
    ) -> None:
        self._connection = connection
        self._timeout_s = timeout_s
        self._session_cls = session_cls
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        try:
            await asyncio.wait_for(self._lock.acquire(), self._timeout_s)
        except TimeoutError:
            raise AssertionError(LOCK_TIMEOUT_MESSAGE) from None
        try:
            async with self._session_cls(
                bind=self._connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as session:
                yield session
        finally:
            self._lock.release()
