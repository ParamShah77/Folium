"""CSRF token helpers (double-submit cookie pattern, §1H).

Token generation lives here; the request-time validation is in
``middleware/csrf.py``. On login/refresh the backend:
  * generates a 32-byte hex token,
  * stores it at Redis ``csrf:{user_id}`` (TTL 7d),
  * sets a NON-httpOnly ``csrf_token`` cookie so JS can read it and echo it back
    in the ``X-CSRF-Token`` header on mutating requests.
"""
from __future__ import annotations

from ..db import RedisService
from .jwt_handler import generate_csrf_token

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
_CSRF_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days (§1H / §2B)


async def issue_csrf_token(redis: RedisService, user_id: str) -> str:
    """Generate a CSRF token and persist it at ``csrf:{user_id}``."""
    token = generate_csrf_token()
    await redis.set_with_ttl(f"csrf:{user_id}", token, _CSRF_TTL_SECONDS)
    return token


async def revoke_csrf_token(redis: RedisService, user_id: str) -> None:
    await redis.delete(f"csrf:{user_id}")
