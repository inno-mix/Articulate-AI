"""Management commands. Run with: uv run python -m app.cli <command>."""

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import SessionFactory, create_engine, create_session_factory
from app.core.migrations import upgrade_head
from app.domain.constants import LOCAL_USER_EMAIL, LOCAL_USER_ID
from app.models import Profile, User, UserSettings


async def seed_local_user(db: AsyncSession, settings: Settings) -> User:
    """Create the built-in local user (ADR-0007) with a default profile and settings."""
    user = await db.get(User, LOCAL_USER_ID)
    if user is None:
        user = User(id=LOCAL_USER_ID, email=LOCAL_USER_EMAIL, is_local=True)
        db.add(user)
        await db.flush()
    if await db.get(Profile, LOCAL_USER_ID) is None:
        db.add(Profile(user_id=LOCAL_USER_ID))
    if await db.get(UserSettings, LOCAL_USER_ID) is None:
        db.add(UserSettings(user_id=LOCAL_USER_ID, tts_voice=settings.deepgram_tts_voice))
    await db.flush()
    return user


async def seed(session_factory: SessionFactory, settings: Settings) -> None:
    """Idempotent: safe to run any number of times. Content loaders are added in later phases."""
    async with session_factory() as db:
        existed = await db.get(User, LOCAL_USER_ID) is not None
        await seed_local_user(db, settings)
        await db.commit()
    print(f"local user: {'already exists' if existed else 'created'}")


async def reset_db(settings: Settings) -> None:
    """Drop everything, migrate to head and seed. Local databases only."""
    if settings.app_env == "production":
        raise SystemExit("refusing to reset a production database")
    engine = create_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await upgrade_head(settings.database_url)
        await seed(create_session_factory(engine), settings)
    finally:
        await engine.dispose()
    print("database reset complete")


async def _run_seed(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    try:
        await seed(create_session_factory(engine), settings)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="create the local user and load content")
    reset = commands.add_parser("reset-db", help="drop, migrate and seed the local database")
    reset.add_argument("--force", action="store_true", help="required: confirms data loss")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.command == "seed":
        asyncio.run(_run_seed(settings))
    elif args.command == "reset-db":
        if not args.force:
            sys.exit("reset-db deletes all data; pass --force to confirm")
        asyncio.run(reset_db(settings))


if __name__ == "__main__":
    main()
