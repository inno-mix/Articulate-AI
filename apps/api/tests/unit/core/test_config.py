from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB_URL = "postgresql+asyncpg://u:p@localhost:5432/db"


def make_settings(**values: Any) -> Settings:
    return Settings(_env_file=None, database_url=DB_URL, **values)  # type: ignore[call-arg]


def test_cors_origins_parses_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a, http://b")

    settings = make_settings()

    assert settings.cors_origins == ["http://a", "http://b"]


def test_allowed_hosts_parses_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,test")

    settings = make_settings()

    assert settings.allowed_hosts == ["localhost", "127.0.0.1", "test"]


def test_development_allows_ollama_and_fakes() -> None:
    settings = make_settings(
        app_env="development",
        llm_provider="fake",
        stt_provider="fake",
        tts_provider="fake",
        pronunciation_provider="fake",
    )

    assert settings.llm_provider == "fake"


def test_production_rejects_ollama() -> None:
    with pytest.raises(ValidationError, match="development-only"):
        make_settings(app_env="production", llm_provider="ollama", auth_mode="accounts")


def test_production_rejects_fake_speech_providers() -> None:
    with pytest.raises(ValidationError, match="development-only"):
        make_settings(
            app_env="production",
            llm_provider="user_credentials",
            auth_mode="accounts",
            stt_provider="fake",
        )


def test_production_rejects_local_single_user() -> None:
    with pytest.raises(ValidationError, match="development-only"):
        make_settings(
            app_env="production", llm_provider="user_credentials", auth_mode="local_single_user"
        )


def test_secret_values_are_not_in_repr() -> None:
    settings = make_settings(deepgram_api_key="dg-super-secret-value")

    assert "dg-super-secret-value" not in repr(settings)
    assert "dg-super-secret-value" not in str(settings.model_dump())
