"""Run Alembic programmatically (CLI and tests)."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

API_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


async def upgrade_head(database_url: str) -> None:
    # env.py calls asyncio.run(), so Alembic must run outside this event loop.
    await asyncio.to_thread(command.upgrade, alembic_config(database_url), "head")


async def downgrade_base(database_url: str) -> None:
    await asyncio.to_thread(command.downgrade, alembic_config(database_url), "base")
