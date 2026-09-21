"""Application settings, loaded from environment variables and `apps/api/.env`."""

from functools import lru_cache
from typing import Annotated, Any, Literal, Self

from pydantic import BeforeValidator, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_comma(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CommaSeparated = Annotated[list[str], NoDecode, BeforeValidator(_split_comma)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str
    test_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: CommaSeparated = ["http://localhost:3000"]
    allowed_hosts: CommaSeparated = ["localhost", "127.0.0.1"]
    frontend_url: str = "http://localhost:3000"

    auth_mode: Literal["local_single_user", "accounts"] = "local_single_user"

    llm_provider: Literal["ollama", "fake", "user_credentials"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    llm_timeout_seconds: float = 60

    stt_provider: Literal["deepgram", "fake"] = "deepgram"
    tts_provider: Literal["deepgram", "fake"] = "deepgram"
    deepgram_api_key: SecretStr | None = None
    deepgram_stt_model: str = "nova-3"
    deepgram_tts_voice: str = "aura-2-thalia-en"

    pronunciation_provider: Literal["azure", "fake"] = "azure"
    azure_speech_key: SecretStr | None = None
    azure_speech_region: str | None = None
    azure_speech_max_concurrency: int = 1

    # Development-only: read by evals/ and live tests, never by the app runtime (ADR-0015, S14).
    eval_anthropic_api_key: SecretStr | None = None
    eval_openai_api_key: SecretStr | None = None
    eval_google_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _reject_development_only_values_in_production(self) -> Self:
        if self.app_env != "production":
            return self
        problems: list[str] = []
        if self.llm_provider in ("ollama", "fake"):
            problems.append(f"LLM_PROVIDER={self.llm_provider}")
        if self.stt_provider == "fake":
            problems.append("STT_PROVIDER=fake")
        if self.tts_provider == "fake":
            problems.append("TTS_PROVIDER=fake")
        if self.pronunciation_provider == "fake":
            problems.append("PRONUNCIATION_PROVIDER=fake")
        if self.auth_mode == "local_single_user":
            problems.append("AUTH_MODE=local_single_user")
        if self.eval_anthropic_api_key or self.eval_openai_api_key or self.eval_google_api_key:
            problems.append("eval keys are development-only")
        if problems:
            joined = ", ".join(problems)
            raise ValueError(
                f"{joined} are development-only and not allowed when APP_ENV=production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # database_url comes from the environment / .env
