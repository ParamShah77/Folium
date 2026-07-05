"""Liveness / readiness endpoint (§6 API skeleton).

``GET /health`` checks that the Postgres pool and Redis are both reachable and
returns 200 only if both are. Mounted at the app root (not under /v1) so
platform health checks don't need the API version prefix.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..db import Database, RedisService
from ..state import get_db, get_redis_service

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health(
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    db_ok = False
    redis_ok = False

    try:
        db_ok = (await db.fetchval("SELECT 1")) == 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_db_check_failed", error=str(exc))

    try:
        redis_ok = await redis.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_redis_check_failed", error=str(exc))

    healthy = db_ok and redis_ok
    body = {
        "status": "ok" if healthy else "degraded",
        "db": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
    }
    return JSONResponse(status_code=200 if healthy else 503, content=body)
