"""The app's LLM selection never reads eval keys (ADR-0015, security-privacy.md S14)."""

from app.core.config import Settings
from app.llm.factory import get_llm_service
from app.llm.fake import FakeLLMService
from app.models import User

DB_URL = "postgresql+asyncpg://u:p@localhost:5432/db"


async def test_factory_ignores_eval_keys() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=DB_URL,
        llm_provider="ollama",
        eval_anthropic_api_key="sk-eval-should-be-ignored",
    )
    user = User(email="local@articulate.localhost", is_local=True)

    llm = await get_llm_service(user, None, settings)  # type: ignore[arg-type]

    assert not isinstance(llm, FakeLLMService)
    assert llm.provider == "ollama"
