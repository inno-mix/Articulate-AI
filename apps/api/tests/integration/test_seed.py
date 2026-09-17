import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import SCENARIOS_DIR, seed
from app.content.loader import load_scenario_files
from app.core.config import Settings
from app.domain.constants import LOCAL_USER_EMAIL, LOCAL_USER_ID
from app.models import Profile, Scenario, User, UserSettings
from tests.support.db import LockedSessionFactory


async def test_seed_creates_local_user_profile_and_settings(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings
) -> None:
    await seed(session_factory, settings)

    user = await db.get(User, LOCAL_USER_ID)
    profile = await db.get(Profile, LOCAL_USER_ID)
    user_settings = await db.get(UserSettings, LOCAL_USER_ID)
    assert user is not None
    assert user.email == LOCAL_USER_EMAIL
    assert user.is_local is True
    assert profile is not None
    assert (profile.display_name, profile.english_level, profile.timezone) == ("You", "B2", "UTC")
    assert profile.seniority == "mid"
    assert user_settings is not None
    assert user_settings.default_mode == "text"
    assert user_settings.voice_input_mode == "push_to_talk"
    assert user_settings.tts_voice == settings.deepgram_tts_voice


async def test_seed_is_idempotent(
    db: AsyncSession, session_factory: LockedSessionFactory, settings: Settings
) -> None:
    await seed(session_factory, settings)
    await seed(session_factory, settings)

    count = await db.scalar(select(func.count()).select_from(User))
    assert count == 1


async def test_seed_loads_all_scenarios(
    db: AsyncSession,
    session_factory: LockedSessionFactory,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await seed(session_factory, settings)

    count = await db.scalar(select(func.count()).select_from(Scenario))
    assert count == 17
    assert "scenarios: created=17 updated=0 unchanged=0" in capsys.readouterr().out


async def test_seed_upserts_scenarios_idempotently(
    db: AsyncSession,
    session_factory: LockedSessionFactory,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await seed(session_factory, settings)
    capsys.readouterr()

    await seed(session_factory, settings)

    count = await db.scalar(select(func.count()).select_from(Scenario))
    assert count == 17
    assert "scenarios: created=0 updated=0 unchanged=17" in capsys.readouterr().out


async def test_seed_updates_changed_scenario(
    db: AsyncSession,
    session_factory: LockedSessionFactory,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await seed(session_factory, settings)
    capsys.readouterr()

    files = load_scenario_files(SCENARIOS_DIR)
    changed = [
        f.model_copy(update={"title": f.title + " (v2)"}) if f.slug == "standup-update" else f
        for f in files
    ]
    monkeypatch.setattr("app.cli.load_scenario_files", lambda _dir: changed)

    await seed(session_factory, settings)

    scenario = await db.scalar(select(Scenario).where(Scenario.slug == "standup-update"))
    assert scenario is not None
    assert scenario.title.endswith("(v2)")
    assert "scenarios: created=0 updated=1 unchanged=16" in capsys.readouterr().out
