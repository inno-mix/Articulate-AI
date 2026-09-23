"""TTS preview endpoint (api-contract.md §2 Voice). Per-user rate limit added in Phase 10."""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.errors import ValidationAppError
from app.deps import CurrentUser, TTSDep
from app.voice.voices import is_known_voice

router = APIRouter(tags=["tts"])


@router.get("/tts/preview")
async def get_tts_preview(
    user: CurrentUser,
    tts: TTSDep,
    voice: str,
    text: Annotated[str, Query(min_length=1, max_length=200)],
) -> Response:
    if not is_known_voice(voice):
        raise ValidationAppError(
            "Unknown voice.",
            details={"fields": [{"loc": ["query", "voice"], "msg": "Unknown voice"}]},
        )
    audio = await tts.synthesize_mp3(voice=voice, text=text)
    return Response(content=audio, media_type="audio/mpeg")
