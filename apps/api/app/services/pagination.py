"""Cursor pagination (api-contract.md §1): base64url of `"<iso-timestamp>|<uuid>"`."""

import base64
from datetime import datetime
from uuid import UUID

from app.core.errors import ValidationAppError

MAX_LIMIT = 50


def encode_cursor(ts: datetime, id: UUID) -> str:
    raw = f"{ts.isoformat()}|{id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(id_str)
    except Exception as exc:
        raise ValidationAppError("The page cursor is invalid.") from exc
