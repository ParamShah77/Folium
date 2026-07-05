"""FastAPI auth dependencies: ``get_current_user`` and ``require_admin``.

Flow (§3C, corrected by Amendment 9):
    cookie -> RS256 verify (type=access) -> Redis blacklist check
           -> load users row -> is_active / email_verified / deleted_at checks
           -> return User

Note on RLS: ``users`` is NOT an RLS-protected table, so the lookup here is a
direct pool query. Access to RLS-protected tables (decisions, audit_logs,
portfolios, sip_registrations, profile_change_log) must be done by the route
inside ``db.rls_transaction(user.id)`` (Amendment 9) — the GUC cannot be set
here because it only lives for the duration of a single transaction.
"""
from __future__ import annotations

from fastapi import Depends, Request

from ..db import Database, RedisService
from ..errors import AppError
from ..models import User
from ..state import get_db, get_redis_service
from .jwt_handler import TokenError, decode_token

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"


async def get_current_user(
    request: Request,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
) -> User:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        raise AppError(status_code=401, error="NOT_AUTHENTICATED", message="Not authenticated")

    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise AppError(status_code=401, error="INVALID_TOKEN", message=str(exc)) from exc

    jti = payload.get("jti", "")
    if await redis.is_blacklisted(jti):
        raise AppError(status_code=401, error="TOKEN_REVOKED", message="Token revoked")

    record = await db.fetchrow(
        "SELECT * FROM users WHERE user_id = $1", payload["sub"]
    )
    if record is None:
        raise AppError(status_code=401, error="NOT_AUTHENTICATED", message="Not authenticated")

    user = User.from_record(record)
    if user.deleted_at is not None:
        raise AppError(
            status_code=403,
            error="ACCOUNT_DELETED",
            message="This account has been scheduled for deletion.",
        )
    if not user.is_active or not user.email_verified:
        raise AppError(status_code=401, error="ACCOUNT_INACTIVE", message="Account not active")

    # Expose the authenticated id so routes can open an RLS transaction.
    request.state.user_id = str(user.user_id)
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise AppError(status_code=403, error="FORBIDDEN", message="Admin access required")
    return current_user
