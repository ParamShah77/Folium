"""/v1/admin/* — Milestone 2: MFA reset only (§1E, Amendment 5).

Amendment 5: the admin MFA reset endpoint is POST /v1/admin/users/{id}/reset-mfa
(the /v1/auth/mfa/admin-reset naming is removed). The rest of the admin panel
(aggregate stats etc.) arrives in Milestone 5.

The admin must verify their OWN TOTP for every reset — an admin session alone is
not enough to strip another account's second factor.

NOTE: no ``from __future__ import annotations`` in route modules that combine
@limiter.limit with Pydantic bodies (see auth/routes.py for the reason).
"""
import structlog
from fastapi import APIRouter, Depends, Request

from ...auth import mfa_handler
from ...auth.csrf import revoke_csrf_token
from ...auth.dependencies import require_admin
from ...db import Database, RedisService
from ...errors import AppError
from ...middleware.rate_limiter import ADMIN_LIMIT, limiter
from ...models import User
from ...schemas.auth import AdminMfaResetRequest
from ...services.email_service import EmailService
from ...services.profile_log import log_profile_change
from ...state import get_db, get_redis_service

logger = structlog.get_logger(__name__)
router = APIRouter()

_email_service = EmailService()


async def _verify_admin_totp(db: Database, admin: User, code: str) -> None:
    """The admin's own TOTP gate for destructive MFA actions (§1E)."""
    record = await db.fetchrow(
        "SELECT mfa_enabled, mfa_secret_enc FROM users WHERE user_id = $1",
        admin.user_id,
    )
    if not record["mfa_enabled"]:
        raise AppError(
            status_code=403,
            error="ADMIN_MFA_REQUIRED",
            message="Admin must have MFA enabled to reset user MFA.",
        )
    if not mfa_handler.verify_user_totp(record["mfa_secret_enc"], code):
        raise AppError(
            status_code=401,
            error="INVALID_MFA_CODE",
            message="Invalid code. Please try again.",
        )


@router.get("/users/{user_id}/mfa-status")
@limiter.limit(ADMIN_LIMIT)
async def mfa_status(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
    db: Database = Depends(get_db),
):
    record = await db.fetchrow(
        "SELECT user_id, email, mfa_enabled FROM users WHERE user_id = $1", user_id
    )
    if record is None:
        raise AppError(status_code=404, error="USER_NOT_FOUND", message="User not found")

    remaining = await db.fetchval(
        "SELECT COUNT(*) FROM mfa_backup_codes WHERE user_id = $1 AND used = FALSE",
        user_id,
    )
    return {
        "user_id": str(record["user_id"]),
        "mfa_enabled": record["mfa_enabled"],
        "backup_codes_remaining": int(remaining),
    }


@router.post("/users/{user_id}/reset-mfa")
@limiter.limit(ADMIN_LIMIT)
async def reset_mfa(
    request: Request,
    user_id: str,
    payload: AdminMfaResetRequest,
    admin: User = Depends(require_admin),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    await _verify_admin_totp(db, admin, payload.admin_totp_code)

    target = await db.fetchrow(
        "SELECT user_id, email, mfa_enabled FROM users WHERE user_id = $1", user_id
    )
    if target is None:
        raise AppError(status_code=404, error="USER_NOT_FOUND", message="User not found")

    # §1E steps 3-4: wipe MFA + backup codes.
    await mfa_handler.wipe_mfa(db, str(target["user_id"]))

    # Step 5: change log — the row belongs to the TARGET; changed_by = admin.
    await log_profile_change(
        db,
        str(target["user_id"]),
        "mfa_status",
        verified_via="admin_action",
        changed_by=str(admin.user_id),
    )

    # Step 6: notify the user.
    reset_at = (await db.fetchval("SELECT NOW()")).isoformat()
    await _email_service.send_mfa_reset_notice(target["email"], reset_at)

    # Step 7: invalidate all of the target's sessions.
    await db.execute("DELETE FROM refresh_tokens WHERE user_id = $1", target["user_id"])
    await revoke_csrf_token(redis, str(target["user_id"]))

    # Step 8: resolve any pending recovery requests for this user/email.
    await db.execute(
        """
        UPDATE mfa_recovery_requests
        SET status = 'resolved', resolved_by = $1, resolved_at = NOW()
        WHERE status = 'pending' AND (user_id = $2 OR email = $3)
        """,
        admin.user_id,
        target["user_id"],
        target["email"],
    )

    logger.info(
        "admin_mfa_reset",
        admin_id=str(admin.user_id),
        target_user_id=str(target["user_id"]),
    )
    return {"message": "MFA reset. The user has been notified."}
