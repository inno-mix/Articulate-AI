import httpx

from app.models import User


async def test_tts_preview_returns_audio_mpeg(client: httpx.AsyncClient, local_user: User) -> None:
    response = await client.get(
        "/api/v1/tts/preview", params={"voice": "aura-2-thalia-en", "text": "Hello there"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert len(response.content) > 0


async def test_tts_preview_rejects_unknown_voice(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.get(
        "/api/v1/tts/preview", params={"voice": "not-a-real-voice", "text": "Hello"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_tts_preview_rejects_empty_text(client: httpx.AsyncClient, local_user: User) -> None:
    response = await client.get(
        "/api/v1/tts/preview", params={"voice": "aura-2-thalia-en", "text": ""}
    )

    assert response.status_code == 422


async def test_tts_preview_rejects_text_over_200_chars(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.get(
        "/api/v1/tts/preview", params={"voice": "aura-2-thalia-en", "text": "x" * 201}
    )

    assert response.status_code == 422
