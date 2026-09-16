from typing import Any

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.request_guard import RequestGuardMiddleware

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "test"]
ALLOWED_ORIGINS = ["http://localhost:3000"]


async def ok(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def build_client(base_url: str = "http://test") -> httpx.AsyncClient:
    inner = Starlette(routes=[Route("/thing", ok, methods=["GET", "POST"])])
    app = RequestGuardMiddleware(
        inner, allowed_hosts=ALLOWED_HOSTS, allowed_origins=ALLOWED_ORIGINS
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base_url)


async def test_rejects_unknown_host() -> None:
    async with build_client("http://evil.example") as client:
        response = await client.get("/thing")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_host"


async def test_allows_localhost_with_port() -> None:
    async with build_client("http://localhost:8000") as client:
        response = await client.get("/thing")

    assert response.status_code == 200


async def test_rejects_cross_origin_post() -> None:
    async with build_client() as client:
        response = await client.post("/thing", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"


async def test_allows_post_from_allowed_origin() -> None:
    async with build_client() as client:
        response = await client.post("/thing", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200


async def test_allows_post_without_origin() -> None:
    async with build_client() as client:
        response = await client.post("/thing")

    assert response.status_code == 200


async def test_allows_cross_origin_get() -> None:
    async with build_client() as client:
        response = await client.get("/thing", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200


async def run_websocket(headers: list[tuple[bytes, bytes]]) -> list[dict[str, Any]]:
    reached_app = False

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        nonlocal reached_app
        reached_app = True
        await receive()
        await send({"type": "websocket.accept"})

    guard = RequestGuardMiddleware(
        inner, allowed_hosts=ALLOWED_HOSTS, allowed_origins=ALLOWED_ORIGINS
    )
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "websocket", "path": "/ws", "headers": headers}
    await guard(scope, receive, send)
    sent.append({"reached_app": reached_app})
    return sent


@pytest.mark.parametrize(
    ("headers", "expected_close"),
    [
        ([(b"host", b"localhost:8000"), (b"origin", b"https://evil.example")], 4403),
        ([(b"host", b"evil.example")], 4400),
    ],
)
async def test_closes_bad_websocket_handshakes(
    headers: list[tuple[bytes, bytes]], expected_close: int
) -> None:
    sent = await run_websocket(headers)

    assert sent[0] == {"type": "websocket.accept"}
    assert sent[1]["type"] == "websocket.close"
    assert sent[1]["code"] == expected_close
    assert sent[-1] == {"reached_app": False}


async def test_allows_websocket_without_origin() -> None:
    sent = await run_websocket([(b"host", b"localhost:8000")])

    assert sent[-1] == {"reached_app": True}
