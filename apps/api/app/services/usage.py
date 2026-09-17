"""Usage tracking (ai-layer.md §9, data-model.md `usage_events`)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import UsageKind
from app.models import UsageEvent


async def record_usage(
    db: AsyncSession,
    *,
    user_id: UUID,
    kind: UsageKind,
    feature: str,
    provider: str,
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    audio_seconds: float | None = None,
    characters: int | None = None,
    latency_ms: int | None = None,
) -> None:
    db.add(
        UsageEvent(
            user_id=user_id,
            kind=kind,
            feature=feature,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            audio_seconds=audio_seconds,
            characters=characters,
            latency_ms=latency_ms,
        )
    )
    await db.flush()
