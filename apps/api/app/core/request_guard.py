"""Rejects unknown hosts and cross-site origins (security rule S15).

Protects the local API from other websites open in the same browser: DNS rebinding,
cross-site form posts and cross-site WebSockets. Requests without an Origin header
(curl, tests, server-to-server) are allowed.
"""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_body

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
WS_CLOSE_INVALID_HOST = 4400
WS_CLOSE_ORIGIN_NOT_ALLOWED = 4403


def _host_name(host_header: str) -> str:
    if host_header.startswith("["):  # IPv6 literal, e.g. [::1]:8000
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0] if ":" in host_header else host_header


class RequestGuardMiddleware:
    def __init__(
        self, app: ASGIApp, *, allowed_hosts: list[str], allowed_origins: list[str]
    ) -> None:
        self.app = app
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        host_ok = _host_name(headers.get("host", "")).lower() in self.allowed_hosts
        origin = headers.get("origin")
        origin_ok = origin is None or origin in self.allowed_origins

        if scope["type"] == "websocket":
            if host_ok and origin_ok:
                await self.app(scope, receive, send)
                return
            # Accept, then close, so browsers see a meaningful close code.
            await receive()  # websocket.connect
            await send({"type": "websocket.accept"})
            code = WS_CLOSE_INVALID_HOST if not host_ok else WS_CLOSE_ORIGIN_NOT_ALLOWED
            await send({"type": "websocket.close", "code": code})
            return

        if not host_ok:
            response = JSONResponse(
                error_body("invalid_host", "This host name is not allowed."), status_code=400
            )
            await response(scope, receive, send)
            return
        if scope["method"] in UNSAFE_METHODS and not origin_ok:
            response = JSONResponse(
                error_body("origin_not_allowed", "Requests from this site are not allowed."),
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
