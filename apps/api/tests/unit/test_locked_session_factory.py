from typing import Any, Self

import pytest

from tests.support.db import LockedSessionFactory


class FakeSession:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def make_factory() -> LockedSessionFactory:
    return LockedSessionFactory(connection=object(), timeout_s=0.05, session_cls=FakeSession)


async def test_nested_session_fails_with_clear_message() -> None:
    factory = make_factory()

    async with factory():
        with pytest.raises(AssertionError, match="nested"):
            async with factory():
                pass


async def test_sequential_sessions_are_fine() -> None:
    factory = make_factory()

    async with factory() as first:
        pass
    async with factory() as second:
        pass

    assert first.kwargs["join_transaction_mode"] == "create_savepoint"
    assert second is not first
