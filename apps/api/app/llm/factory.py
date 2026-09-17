"""Chooses the `LLMService` implementation from settings (ai-layer.md §2).

Phase 9 adds `user_credentials` (decrypt the user's key, build a per-request cloud provider);
`user`/`db` are already part of the signature so that addition doesn't change call sites.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.llm.base import LLMService
from app.llm.fake import FakeLLMService
from app.llm.pydantic_ai_service import PydanticAILLMService
from app.models import User


async def get_llm_service(user: User, db: AsyncSession, settings: Settings) -> LLMService:
    if settings.llm_provider == "fake":
        return FakeLLMService()
    if settings.llm_provider == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider

        model = OllamaModel(
            settings.ollama_model,
            provider=OllamaProvider(base_url=f"{settings.ollama_base_url}/v1"),
        )
        return PydanticAILLMService(
            model=model,
            provider="ollama",
            output_mode="native",
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise NotImplementedError(f"llm_provider={settings.llm_provider!r} is not supported yet")
