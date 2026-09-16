"""Runs last (file name): downgrades and re-upgrades the whole migration chain."""

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.migrations import downgrade_base, upgrade_head

EXPECTED_TABLES = {"users", "profiles", "user_settings"}


async def table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))


async def test_upgrade_downgrade_upgrade(engine: AsyncEngine, settings: Settings) -> None:
    await downgrade_base(settings.database_url)
    assert not (EXPECTED_TABLES & await table_names(engine))

    await upgrade_head(settings.database_url)
    assert await table_names(engine) >= EXPECTED_TABLES
