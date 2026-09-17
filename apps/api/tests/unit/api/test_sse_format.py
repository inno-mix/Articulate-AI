from pydantic import BaseModel

from app.api.sse import format_sse, sse_response


class Foo(BaseModel):
    x: int


def test_format_sse_serialises_json_on_one_line() -> None:
    result = format_sse("delta", {"text": "hi"})

    assert result == 'event: delta\ndata: {"text": "hi"}\n\n'


def test_format_sse_accepts_a_pydantic_model() -> None:
    result = format_sse("thing", Foo(x=1))

    assert result == 'event: thing\ndata: {"x": 1}\n\n'


async def test_sse_response_has_documented_headers() -> None:
    async def generator():
        yield "event: x\ndata: {}\n\n"

    response = sse_response(generator())

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
