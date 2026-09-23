import httpx

from app.models import User


async def test_list_voices_returns_the_six_curated_voices(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.get("/api/v1/voices")

    assert response.status_code == 200
    voices = response.json()
    assert len(voices) == 6
    assert {"id": "aura-2-thalia-en", "label": "Thalia (US, female)"} in voices
    assert all(set(voice.keys()) == {"id", "label"} for voice in voices)
