import httpx

from app.core.config import Settings
from app.domain.constants import LOCAL_USER_EMAIL, LOCAL_USER_ID
from app.models import User


async def test_get_me_returns_local_user_profile_and_settings(
    client: httpx.AsyncClient, local_user: User, settings: Settings
) -> None:
    response = await client.get("/api/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": str(LOCAL_USER_ID),
        "email": LOCAL_USER_EMAIL,
        "is_local": True,
        "email_verified": False,
    }
    assert body["profile"] == {
        "display_name": "You",
        "seniority": "mid",
        "native_language": None,
        "english_level": "B2",
        "goals": [],
        "focus_areas": [],
        "timezone": "UTC",
    }
    assert body["settings"] == {
        "default_mode": "text",
        "voice_input_mode": "push_to_talk",
        "tts_voice": settings.deepgram_tts_voice,
    }


async def test_get_me_without_seed_returns_local_user_missing(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "local_user_missing"


async def test_patch_profile_updates_only_given_fields(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch(
        "/api/v1/me/profile",
        json={"english_level": "B1", "timezone": "Asia/Manila", "goals": ["meetings", "meetings"]},
    )

    assert response.status_code == 200
    profile = response.json()
    assert profile["english_level"] == "B1"
    assert profile["timezone"] == "Asia/Manila"
    assert profile["goals"] == ["meetings"]
    assert profile["display_name"] == "You"
    assert (await client.get("/api/v1/me")).json()["profile"]["timezone"] == "Asia/Manila"


async def test_patch_profile_can_clear_native_language(
    client: httpx.AsyncClient, local_user: User
) -> None:
    await client.patch("/api/v1/me/profile", json={"native_language": "Tagalog"})

    response = await client.patch("/api/v1/me/profile", json={"native_language": None})

    assert response.json()["native_language"] is None


async def test_patch_profile_rejects_invalid_timezone(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch("/api/v1/me/profile", json={"timezone": "Mars/Olympus"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_patch_profile_rejects_unknown_field(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch("/api/v1/me/profile", json={"favourite_colour": "blue"})

    assert response.status_code == 422


async def test_patch_profile_rejects_null_for_required_field(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch("/api/v1/me/profile", json={"display_name": None})

    assert response.status_code == 422


async def test_patch_profile_rejects_more_than_three_focus_areas(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch(
        "/api/v1/me/profile",
        json={"focus_areas": ["clarity", "tone", "structure", "confidence"]},
    )

    assert response.status_code == 422


async def test_get_settings(client: httpx.AsyncClient, local_user: User) -> None:
    response = await client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json()["default_mode"] == "text"


async def test_patch_settings_updates_default_mode_and_input_mode(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch(
        "/api/v1/settings", json={"default_mode": "voice", "voice_input_mode": "hands_free"}
    )

    assert response.status_code == 200
    assert response.json()["default_mode"] == "voice"
    assert response.json()["voice_input_mode"] == "hands_free"


async def test_patch_settings_rejects_empty_voice(
    client: httpx.AsyncClient, local_user: User
) -> None:
    response = await client.patch("/api/v1/settings", json={"tts_voice": ""})

    assert response.status_code == 422
