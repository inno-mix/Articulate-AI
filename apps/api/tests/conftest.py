import os

# Must run before anything imports `app`: the Taskiq broker is chosen from settings at import time.
os.environ["APP_ENV"] = "test"
for _name in ("LLM_PROVIDER", "STT_PROVIDER", "TTS_PROVIDER", "PRONUNCIATION_PROVIDER"):
    os.environ[_name] = "fake"

from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.db import create_engine, get_db  # noqa: E402
from app.core.migrations import upgrade_head  # noqa: E402
from app.models import User  # noqa: E402
from tests.factories import make_user  # noqa: E402
from tests.support.db import LockedSessionFactory  # noqa: E402

DEFAULT_TEST_DB = "postgresql+asyncpg://articulate:articulate@localhost:5432/articulate_test"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return (
        os.environ.get("TEST_DATABASE_URL") or get_settings().test_database_url or DEFAULT_TEST_DB
    )


@pytest.fixture(scope="session")
def settings(test_database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=test_database_url,
        redis_url="redis://localhost:6379/1",
        cors_origins=["http://localhost:3000"],
        allowed_hosts=["test", "localhost", "127.0.0.1"],
        llm_provider="fake",
        stt_provider="fake",
        tts_provider="fake",
        pronunciation_provider="fake",
    )


@pytest.fixture(scope="session")
async def engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    await upgrade_head(settings.database_url)
    eng = create_engine(settings.database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()


@pytest.fixture
async def db(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        yield session


@pytest.fixture
def session_factory(connection: AsyncConnection) -> LockedSessionFactory:
    return LockedSessionFactory(connection)


@pytest.fixture
async def app(
    settings: Settings, db: AsyncSession, session_factory: LockedSessionFactory
) -> FastAPI:
    from app.main import create_app

    application = create_app(settings)
    application.state.session_factory = session_factory

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def local_user(settings: Settings, session_factory: LockedSessionFactory) -> User:
    from app.cli import seed_local_user

    async with session_factory() as session:
        user = await seed_local_user(session, settings)
        await session.commit()
    return user


@pytest.fixture
async def other_user(db: AsyncSession) -> User:
    user = await make_user(db, "other@example.com")
    await db.commit()
    return user
