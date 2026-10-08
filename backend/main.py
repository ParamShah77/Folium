"""FastAPI application factory (§3A/§3B/§3E).

Responsibilities:
  * ``lifespan`` — open the asyncpg pool + Redis client on startup, close on
    shutdown, publishing both into ``backend.state`` for dependencies to read.
  * middleware registration (order matters — see below),
  * global exception handlers (§3D),
  * Sentry init behind ``SENTRY_DSN`` (empty = disabled),
  * router wiring (health + /v1),
  * OpenAPI docs disabled when ENV=production (§6).

Middleware execution order (Starlette runs the LAST-added middleware
OUTERMOST). We add, in order: SecurityHeaders, CSRF, RequestLogger — so at
runtime a request flows RequestLogger -> CSRF -> SecurityHeaders -> route.
RequestLogger is therefore outermost and assigns ``request_id`` before anything
else needs it (CSRF/handlers read it).
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import AsyncIterator

import sentry_sdk
import structlog
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

from .config import configure_logging, get_settings
from .db import create_db_pool, create_redis_client
from .db.pool import Database
from .db.redis_client import RedisService
from .errors import register_error_handlers
from .middleware.csrf import CSRFMiddleware
from .middleware.rate_limiter import limiter
from .middleware.request_logger import RequestLoggerMiddleware
from .middleware.security_headers import SecurityHeadersMiddleware
from . import state

logger = structlog.get_logger(__name__)


async def _purge_loop(database: Database, interval: int) -> None:
    """Phase B2: anonymise accounts whose deletion grace period has ended."""
    from .services.account_deletion import purge_due_accounts

    while True:
        await asyncio.sleep(interval)
        try:
            n = await purge_due_accounts(database)
            if n:
                logger.info("accounts_purged", count=n)
        except Exception as exc:  # noqa: BLE001 — never take the API down over housekeeping
            logger.error("account_purge_failed", error=str(exc))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    pool = await create_db_pool(settings.DATABASE_URL)
    database = Database(pool)
    redis_client = create_redis_client(settings.REDIS_URL)
    redis_service = RedisService(redis_client, settings.BLACKLIST_CACHE_TTL_SECONDS)

    state.set_database(database)
    state.set_redis(redis_service)
    app.state.db = database
    app.state.redis = redis_service
    logger.info("app_startup_complete", env=settings.ENV)

    purge_task = None
    if settings.ACCOUNT_PURGE_INTERVAL_SECONDS > 0:
        purge_task = asyncio.create_task(_purge_loop(database, settings.ACCOUNT_PURGE_INTERVAL_SECONDS))

    try:
        yield
    finally:
        if purge_task:
            purge_task.cancel()
        await database.close()
        await redis_service.close()
        state.set_database(None)
        state.set_redis(None)
        logger.info("app_shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.ENV)

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=settings.ENV,
            send_default_pii=False,
        )
        logger.info("sentry_enabled", environment=settings.ENV)

    docs_enabled = not settings.is_production
    app = FastAPI(
        title="FinAI Decision Intelligence API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs" if docs_enabled else None,
        redoc_url="/api/v1/redoc" if docs_enabled else None,
        openapi_url="/api/v1/openapi.json" if docs_enabled else None,
    )

    # slowapi wiring
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware (added inner -> outer; see module docstring).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_error_handlers(app)

    # Routers — imported here to avoid import cycles at module load.
    from .api.health import router as health_router
    from .api.v1 import v1_router

    app.include_router(health_router, tags=["Health"])
    app.include_router(v1_router)

    return app


app = create_app()
