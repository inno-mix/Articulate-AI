from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.errors import ValidationAppError
from app.services.pagination import decode_cursor, encode_cursor


def test_cursor_round_trips() -> None:
    ts = datetime(2026, 9, 17, 12, 30, 0, tzinfo=UTC)
    id_ = uuid4()

    cursor = encode_cursor(ts, id_)
    decoded_ts, decoded_id = decode_cursor(cursor)

    assert decoded_ts == ts
    assert decoded_id == id_


def test_decode_invalid_cursor_raises_validation_error() -> None:
    with pytest.raises(ValidationAppError):
        decode_cursor("not-a-valid-cursor")


def test_decode_malformed_base64_raises_validation_error() -> None:
    with pytest.raises(ValidationAppError):
        decode_cursor("!!!not-base64!!!")
