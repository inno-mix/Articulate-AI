"""Error envelope: every non-2xx response is {"error": {"code", "message", "details"}}."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    429: "rate_limited",
}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"
    message: str = "Something went wrong."

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        self.message = message or type(self).message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "This conflicts with the current state."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "A required service is unavailable. Please try again."


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Please log in to continue."


class LocalUserMissingError(AppError):
    status_code = 500
    code = "local_user_missing"
    message = "Run `make seed` to create the local user."


class ValidationAppError(AppError):
    """Validation that happens outside Pydantic, e.g. a malformed pagination cursor."""

    status_code = 422
    code = "validation_error"
    message = "Some fields are invalid."


class SessionNotActiveError(AppError):
    status_code = 409
    code = "session_not_active"
    message = "This session has already ended."


class TurnLimitReachedError(AppError):
    status_code = 409
    code = "turn_limit_reached"
    message = "This session has reached its turn limit."


class ReplyInProgressError(AppError):
    status_code = 409
    code = "reply_in_progress"
    message = "A reply is already being generated."


# The five codes below mirror `app/llm/errors.py`'s LLMError subclasses (api-contract.md's error
# table) — the "AppError" suffix keeps them distinct where both are imported together, e.g. in
# app/services/chat.py's LLMError -> AppError mapping.
class LLMUnavailableAppError(AppError):
    status_code = 503
    code = "llm_unavailable"
    message = "The AI model is unavailable right now. Please try again."


class LLMInvalidOutputAppError(AppError):
    status_code = 502
    code = "llm_invalid_output"
    message = "The AI model returned something we couldn't use. Please try again."


class LLMRateLimitedAppError(AppError):
    status_code = 429
    code = "llm_rate_limited"
    message = "Too many requests right now. Please wait a moment and try again."


class LLMAuthFailedAppError(AppError):
    status_code = 400
    code = "llm_auth_failed"
    message = "There's a problem with the configured AI provider's credentials."


class LLMNotConfiguredAppError(AppError):
    status_code = 409
    code = "llm_not_configured"
    message = "No AI provider is configured yet."


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Only location and message: never echo submitted values (they may be secrets).
    fields = [{"loc": list(err["loc"]), "msg": err["msg"]} for err in exc.errors()]
    return JSONResponse(
        error_body("validation_error", "Some fields are invalid.", {"fields": fields}),
        status_code=422,
    )


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=exc.headers)


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error", path=request.url.path, exc_info=exc)
    return JSONResponse(
        error_body("internal_error", "Something went wrong on our side. Please try again."),
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
