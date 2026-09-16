"""Structured logging with secret redaction (security rule S2)."""

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

REDACTED = "[REDACTED]"
_SENSITIVE_EXACT = frozenset(
    {
        "api_key",
        "authorization",
        "ocp-apim-subscription-key",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "csrf_token",
        "cookie",
        "set-cookie",
        "encrypted_key",
    }
)
_SENSITIVE_SUFFIXES = ("_api_key", "_password", "_secret")


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return lowered in _SENSITIVE_EXACT or lowered.endswith(_SENSITIVE_SUFFIXES)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: REDACTED if _is_sensitive(str(k)) else _redact(v) for k, v in value.items()}
    return value


def redact_sensitive(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        event_dict[key] = REDACTED if _is_sensitive(key) else _redact(event_dict[key])
    return event_dict


def configure_logging(level: str, *, json: bool) -> None:
    renderer: Any = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_sensitive,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        cache_logger_on_first_use=True,
    )
