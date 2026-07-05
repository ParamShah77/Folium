"""Rate limiting via slowapi backed by Redis (§3H).

Limits (§3H, with Amendment 7 for market context):
    /v1/auth/login             5/minute   per IP
    /v1/auth/register          3/hour     per IP
    /v1/auth/forgot-password   3/hour     per IP
    /v1/decisions/analyze      10/minute  per user   [Milestone 3]
    /v1/simulate               5/minute   per user   [Milestone 3]
    /v1/market/context         60/minute  per user   (Amendment 7)
    /v1/admin/*                20/minute  per admin  [Milestone 3]

Auth endpoints are keyed by client IP (brute-force / enumeration). Endpoints
that require a session are keyed by the authenticated user id when present.

The limiter storage is Redis in every environment so limits are shared across
workers; the ``rate:{endpoint}:{ip}`` keys live there (§2B). When
``RATE_LIMIT_ENABLED`` is false the limiter is disabled (used by most tests).
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from ..config import get_settings

# --- Named limit strings (single source of truth) ---
LOGIN_LIMIT = "5/minute"
REGISTER_LIMIT = "3/hour"
FORGOT_PASSWORD_LIMIT = "3/hour"
MARKET_CONTEXT_LIMIT = "60/minute"       # Amendment 7
DECISIONS_ANALYZE_LIMIT = "10/minute"    # Milestone 3
SIMULATE_LIMIT = "5/minute"              # Milestone 3
ADMIN_LIMIT = "20/minute"                # Milestone 3


def _key_func(request: Request) -> str:
    """Prefer the authenticated user id (set by get_current_user) else client IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


def build_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=_key_func,
        storage_uri=settings.REDIS_URL,
        enabled=settings.RATE_LIMIT_ENABLED,
        headers_enabled=True,
    )


# Shared instance imported by routes for the @limiter.limit(...) decorator.
limiter = build_limiter()
