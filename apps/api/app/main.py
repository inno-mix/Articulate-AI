"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_session_factory
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.redis import create_redis_client
from app.core.request_guard import RequestGuardMiddleware
from app.worker.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = create_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = create_redis_client(settings.redis_url)
    if not broker.is_worker_process:
        await broker.startup()
    try:
        yield
    finally:
        if not broker.is_worker_process:
            await broker.shutdown()
        await app.state.redis.aclose()
        await engine.dispose()


def _operation_id(route: APIRoute) -> str:
    # Stable, readable operation ids for the generated TypeScript client.
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.app_env != "development")

    app = FastAPI(
        title="Articulate AI API",
        version="0.1.0",
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
    )
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
