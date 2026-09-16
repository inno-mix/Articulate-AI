import httpx
import respx
from fastapi import FastAPI

from app.core.config import Settings

TAGS_URL = "http://localhost:11434/api/tags"


def use_ollama(app: FastAPI, settings: Settings) -> None:
    app.state.settings = settings.model_copy(update={"llm_provider": "ollama"})


async def test_health_ok_with_fake_llm(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok", "llm": "ok"},
    }


async def test_health_degraded_when_ollama_unreachable(
    app: FastAPI, client: httpx.AsyncClient, settings: Settings
) -> None:
    use_ollama(app, settings)

    with respx.mock(assert_all_called=True) as router:
        router.get(TAGS_URL).mock(side_effect=httpx.ConnectError("refused"))
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["llm"] == "unavailable"
    assert body["checks"]["database"] == "ok"


async def test_health_ok_when_ollama_responds(
    app: FastAPI, client: httpx.AsyncClient, settings: Settings
) -> None:
    use_ollama(app, settings)

    with respx.mock(assert_all_called=True) as router:
        router.get(TAGS_URL).mock(return_value=httpx.Response(200, json={"models": []}))
        response = await client.get("/api/v1/health")

    assert response.json()["checks"]["llm"] == "ok"
