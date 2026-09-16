"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_guard import RequestGuardMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.app_env != "development")

    app = FastAPI(title="Articulate AI API", version="0.1.0")
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Added last, so it runs first (outermost).
    app.add_middleware(
        RequestGuardMiddleware,
        allowed_hosts=settings.allowed_hosts,
        allowed_origins=settings.cors_origins,
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
