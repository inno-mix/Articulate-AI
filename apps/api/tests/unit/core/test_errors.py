import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.core.errors import AppError, NotFoundError, register_error_handlers


class Body(BaseModel):
    name: str


class TeapotError(AppError):
    status_code = 418
    code = "teapot"
    message = "I'm a teapot."


def build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundError()

    @app.get("/teapot")
    async def teapot() -> None:
        raise TeapotError("Short and stout.", details={"handle": True})

    @app.post("/items")
    async def create_item(body: Body) -> Body:
        return body

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_app_error_renders_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not found.", "details": {}}
    }


async def test_app_error_custom_message_and_details(client: httpx.AsyncClient) -> None:
    response = await client.get("/teapot")

    assert response.status_code == 418
    assert response.json()["error"] == {
        "code": "teapot",
        "message": "Short and stout.",
        "details": {"handle": True},
    }


async def test_validation_error_renders_envelope_with_fields(client: httpx.AsyncClient) -> None:
    response = await client.post("/items", json={"name": 123, "extra": "x"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"][0]["loc"] == ["body", "name"]
    assert "msg" in error["details"]["fields"][0]


async def test_unknown_route_renders_not_found_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_unhandled_exception_renders_internal_error(client: httpx.AsyncClient) -> None:
    response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text
