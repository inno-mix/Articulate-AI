"""Management commands. Run with: uv run python -m app.cli <command>."""

import argparse
import asyncio
import sys

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq.exceptions import TaskiqResultTimeoutError

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


def _refuse_in_production(settings: Settings, action: str) -> None:
    if settings.app_env == "production":
        raise SystemExit(f"refusing to {action} in production")


async def ping_worker(settings: Settings, *, timeout_s: float = 10.0) -> None:
    """Send `ping` through the queue and print the worker's reply. Used by the E2E smoke test."""
    _refuse_in_production(settings, "ping the worker")
    # Imported here so the broker is only built when this command runs.
    from app.worker.broker import broker
    from app.worker.tasks.system import ping

    await broker.startup()
    try:
        task = await ping.kiq("cli")
        result = await task.wait_result(timeout=timeout_s)
    except TaskiqResultTimeoutError:
        raise SystemExit(
            f"no reply from the worker within {timeout_s:g} s; is it running? (make dev starts it)"
        ) from None
    finally:
        await broker.shutdown()
    if result.is_err:
        raise SystemExit(f"worker task failed: {result.error}")
    print(result.return_value)


async def flush_redis(settings: Settings) -> None:
    """Delete every key in the Redis database named by REDIS_URL (queued jobs, results)."""
    _refuse_in_production(settings, "flush Redis")
    client = Redis.from_url(settings.redis_url)
    try:
        await client.flushdb()
        db = client.connection_pool.connection_kwargs.get("db", 0)
    finally:
        await client.aclose()
    print(f"redis db {db} flushed")


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
    commands.add_parser("ping-worker", help="check that a worker is consuming the queue")
    commands.add_parser("flush-redis", help="delete every key in the REDIS_URL database")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.command == "seed":
        asyncio.run(_run_seed(settings))
    elif args.command == "reset-db":
        if not args.force:
            sys.exit("reset-db deletes all data; pass --force to confirm")
        asyncio.run(reset_db(settings))
    elif args.command == "ping-worker":
        asyncio.run(ping_worker(settings))
    elif args.command == "flush-redis":
        asyncio.run(flush_redis(settings))


if __name__ == "__main__":
    main()
