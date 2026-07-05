"""Process-wide singletons for the DB pool and Redis service.

Populated by the FastAPI lifespan in ``main.py`` and read by auth dependencies /
routes. Kept in a dedicated module (rather than ``app.state``) so plain modules
can import the accessors without a Request in hand.
"""
from __future__ import annotations

from typing import Optional

from .db import Database, RedisService

_db: Optional[Database] = None
_redis: Optional[RedisService] = None


def set_database(db: Optional[Database]) -> None:
    global _db
    _db = db


def set_redis(redis: Optional[RedisService]) -> None:
    global _redis
    _redis = redis


def get_database() -> Database:
    if _db is None:
        raise RuntimeError("Database pool is not initialized (lifespan not run).")
    return _db


def get_redis() -> RedisService:
    if _redis is None:
        raise RuntimeError("Redis service is not initialized (lifespan not run).")
    return _redis


# FastAPI dependency wrappers (thin — allow Depends(get_db) style usage).
def get_db() -> Database:
    return get_database()


def get_redis_service() -> RedisService:
    return get_redis()
