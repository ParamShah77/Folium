"""/v1/users/me/* — profile management with §4I re-verification.

Endpoints (Milestone 2 scope):
    GET  /v1/users/me/profile            profile + bias_profiles scores
    PUT  /v1/users/me/profile            non-sensitive fields (no re-verification)
    PUT  /v1/users/me/profile/sensitive  sensitive fields (§4I verification)

Sensitive rules (§4I / Security Summary):
    email change            password + 6-digit OTP emailed to the OLD address
                            (Redis ``otp:{user_id}``, TTL 300 — §2B)
    income / expense /
    emergency fund          password
    (+ TOTP additionally whenever the account has MFA enabled)

Every applied change is appended to profile_change_log (RLS transaction) with a
SHA-256 hash of the old value — never plaintext.

NOTE: no ``from __future__ import annotations`` in route modules (see
auth/routes.py for the slowapi/PEP 563 body-inference reason).
"""
import secrets

import structlog
from fastapi import APIRouter, Depends, Request, Response

from ...auth import mfa_handler
from ...auth.dependencies import get_current_user
from ...db import Database, RedisService
from ...errors import AppError
from ...models import User
from ...schemas.users import AiConsentRequest, DeleteAccountRequest, ProfileUpdateRequest, SensitiveProfileUpdateRequest
from ...services import account_deletion
from ...auth.cookies import clear_auth_cookies
from ...auth.csrf import revoke_csrf_token
from ...auth.dependencies import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from ...auth.jwt_handler import TokenError, decode_token, seconds_until_expiry
from ...services.email_service import EmailService
from ...services.profile_log import log_profile_change
from ...state import get_db, get_redis_service
from ...auth.password import verify_password
from ..serialization import jsonable as _jsonable

logger = structlog.get_logger(__name__)
router = APIRouter()

_email_service = EmailService()

_OTP_TTL = 300  # 5 minutes (§2B: otp:{user_id})
_ALLOWED_STRATEGIES = {"conservative", "moderate", "aggressive"}
# Sensitive (§4I) fields that PUT /me/profile may set only while still NULL.
_FIRST_FILL_FIELDS = (
    "monthly_income", "monthly_expense", "has_emergency_fund",
    "monthly_emi", "rent_paid", "education_monthly",
)
_OUTFLOW_FIELDS = ("monthly_emi", "rent_paid", "education_monthly")

# §10: committed outflow = EMIs + rent paid + education. Re-derived after any
# change so the bias model's monthly_expense always matches what was entered.
_DERIVE_EXPENSE_SQL = """
    UPDATE users
       SET monthly_expense = COALESCE(monthly_emi, 0) + COALESCE(rent_paid, 0)
                             + COALESCE(education_monthly, 0)
     WHERE user_id = $1
       AND (monthly_emi IS NOT NULL OR rent_paid IS NOT NULL OR education_monthly IS NOT NULL)
"""


def _differs(old, new) -> bool:
    """Compare a DB value (Decimal/int/bool/None) with a request value."""
    if old is None or new is None:
        return old is not new
    if isinstance(old, bool) or isinstance(new, bool):
        return bool(old) != bool(new)
    try:
        return float(old) != float(new)
    except (TypeError, ValueError):
        return old != new

# users columns exposed on GET /me/profile (no hashes/secrets).
_PROFILE_FIELDS = (
    "user_id", "email", "email_verified", "name", "role", "mfa_enabled",
    "oauth_provider", "profile_picture", "phone",
    "age", "monthly_income", "monthly_expense", "risk_tolerance",
    "investment_horizon", "has_emergency_fund", "financial_strategy", "goal",
    "monthly_emi", "rent_paid", "education_monthly", "education_end_year",
    "created_at", "last_login_at", "ai_consent",
)


# --------------------------------------------------------------------------- #
# GET /v1/users/me/profile
# --------------------------------------------------------------------------- #
@router.get("/me/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    record = await db.fetchrow("SELECT * FROM users WHERE user_id = $1", user.user_id)
    profile = {k: _jsonable(record[k]) for k in _PROFILE_FIELDS}

    # bias_profiles: auto-create a zeros row on first read (not RLS-protected).
    await db.execute(
        "INSERT INTO bias_profiles (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
        user.user_id,
    )
    bias = await db.fetchrow(
        """
        SELECT disposition_score, herd_score, loss_aversion_score,
               rational_score, total_decisions, last_updated
        FROM bias_profiles WHERE user_id = $1
        """,
        user.user_id,
    )
    return {
        "profile": profile,
        "bias_profile": {k: _jsonable(v) for k, v in dict(bias).items()},
    }


# --------------------------------------------------------------------------- #
# PUT /v1/users/me/profile — non-sensitive (§4I: save immediately)
# --------------------------------------------------------------------------- #
@router.put("/me/profile")
async def update_profile(
    request: Request,
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    if payload.financial_strategy is not None and payload.financial_strategy not in _ALLOWED_STRATEGIES:
        raise AppError(
            status_code=422,
            error="VALIDATION_ERROR",
            message="financial_strategy must be conservative, moderate, or aggressive.",
        )

    old = await db.fetchrow(
        """
        SELECT name, goal, financial_strategy, age, risk_tolerance,
               investment_horizon, monthly_income, monthly_expense,
               has_emergency_fund, monthly_emi, rent_paid, education_monthly,
               education_end_year
        FROM users WHERE user_id = $1
        """,
        user.user_id,
    )

    # Sensitive fields: first-time fill only. A value that already exists can
    # only be changed via /me/profile/sensitive (password re-verification).
    for field in _FIRST_FILL_FIELDS:
        new_value = getattr(payload, field)
        if new_value is None or old[field] is None:
            continue
        if _differs(old[field], new_value):
            raise AppError(
                status_code=403,
                error="REVERIFICATION_REQUIRED",
                message="Changing this needs your password. Use the secure update form.",
                extra={"field": field},
            )

    updates: dict = {
        "name": payload.name,
        "goal": payload.goal,
        "financial_strategy": payload.financial_strategy,
    }
    for field in ("age", "risk_tolerance", "investment_horizon", "education_end_year", *_FIRST_FILL_FIELDS):
        value = getattr(payload, field)
        if value is not None:
            updates[field] = value

    assignments = ", ".join(f"{col} = ${i}" for i, col in enumerate(updates, start=1))
    await db.execute(
        f"UPDATE users SET {assignments}, updated_at = NOW() "
        f"WHERE user_id = ${len(updates) + 1}",
        *updates.values(),
        user.user_id,
    )

    if any(f in updates for f in _OUTFLOW_FIELDS):
        await db.execute(_DERIVE_EXPENSE_SQL, user.user_id)

    for field, new_value in updates.items():
        if _differs(old[field], new_value):
            await log_profile_change(
                db, str(user.user_id), field, verified_via="session",
                old_value=old[field],
            )

    logger.info("profile_updated", user_id=str(user.user_id))
    return {"message": "Changes saved."}


# --------------------------------------------------------------------------- #
# PUT /v1/users/me/profile/sensitive — §4I re-verification
# --------------------------------------------------------------------------- #
@router.put("/me/profile/sensitive")
async def update_sensitive_profile(
    request: Request,
    payload: SensitiveProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    record = await db.fetchrow("SELECT * FROM users WHERE user_id = $1", user.user_id)

    # 1. Password is ALWAYS required for sensitive changes (§4I).
    if not verify_password(payload.password, record["password_hash"] or ""):
        raise AppError(status_code=401, error="INVALID_CREDENTIALS", message="Invalid credentials")

    # 2. TOTP additionally required when MFA is enabled.
    if user.mfa_enabled:
        if not payload.totp_code:
            raise AppError(
                status_code=400,
                error="TOTP_REQUIRED",
                message="TOTP code is required for sensitive changes.",
            )
        if not mfa_handler.verify_user_totp(record["mfa_secret_enc"], payload.totp_code):
            raise AppError(
                status_code=401,
                error="INVALID_MFA_CODE",
                message="Invalid code. Please try again.",
            )

    verified_via = "password+totp" if user.mfa_enabled else "password"
    applied: list[str] = []

    # 3. Non-email sensitive fields apply immediately after verification.
    if payload.monthly_income is not None and payload.monthly_income != _as_float(record["monthly_income"]):
        await db.execute(
            "UPDATE users SET monthly_income = $1, updated_at = NOW() WHERE user_id = $2",
            payload.monthly_income, user.user_id,
        )
        await log_profile_change(
            db, str(user.user_id), "monthly_income", verified_via=verified_via,
            old_value=record["monthly_income"],
        )
        applied.append("monthly_income")

    if payload.monthly_expense is not None and payload.monthly_expense != _as_float(record["monthly_expense"]):
        await db.execute(
            "UPDATE users SET monthly_expense = $1, updated_at = NOW() WHERE user_id = $2",
            payload.monthly_expense, user.user_id,
        )
        await log_profile_change(
            db, str(user.user_id), "monthly_expense", verified_via=verified_via,
            old_value=record["monthly_expense"],
        )
        applied.append("monthly_expense")

    if payload.has_emergency_fund is not None and payload.has_emergency_fund != record["has_emergency_fund"]:
        await db.execute(
            "UPDATE users SET has_emergency_fund = $1, updated_at = NOW() WHERE user_id = $2",
            payload.has_emergency_fund, user.user_id,
        )
        await log_profile_change(
            db, str(user.user_id), "has_emergency_fund", verified_via=verified_via,
            old_value=record["has_emergency_fund"],
        )
        applied.append("has_emergency_fund")

    # 3b. Tier 1 outflows (§10) — expenses, so the same re-verification rule.
    for field in _OUTFLOW_FIELDS:
        new_value = getattr(payload, field)
        if new_value is None or new_value == _as_float(record[field]):
            continue
        await db.execute(
            f"UPDATE users SET {field} = $1, updated_at = NOW() WHERE user_id = $2",
            new_value, user.user_id,
        )
        await log_profile_change(
            db, str(user.user_id), field, verified_via=verified_via, old_value=record[field],
        )
        applied.append(field)
    if any(f in applied for f in _OUTFLOW_FIELDS):
        await db.execute(_DERIVE_EXPENSE_SQL, user.user_id)

    # 4. Email change — two-step: OTP to the OLD address (§4I), then apply.
    if payload.email is not None and payload.email != record["email"]:
        taken = await db.fetchval(
            "SELECT 1 FROM users WHERE email = $1 AND user_id != $2",
            payload.email, user.user_id,
        )
        if taken:
            raise AppError(status_code=409, error="EMAIL_EXISTS", message="Email already registered")

        otp_key = f"otp:{user.user_id}"
        if payload.otp is None:
            # Step 1: issue the OTP to the CURRENT (old) address. No change yet.
            otp = f"{secrets.randbelow(1_000_000):06d}"
            await redis.set_with_ttl(otp_key, otp, _OTP_TTL)
            await _email_service.send_email_change_otp(record["email"], otp)
            logger.info("email_change_otp_sent", user_id=str(user.user_id))
            return {
                "otp_required": True,
                "message": "A 6-digit code was sent to your current email. "
                           "Submit it in the 'otp' field to confirm the change.",
                "applied": applied,
            }

        # Step 2: verify + apply.
        stored = await redis.get(otp_key)
        if not stored or stored != payload.otp.strip():
            raise AppError(
                status_code=400,
                error="INVALID_OTP",
                message="Invalid or expired code. Request the change again.",
            )
        await redis.delete(otp_key)  # single-use
        await db.execute(
            "UPDATE users SET email = $1, updated_at = NOW() WHERE user_id = $2",
            payload.email, user.user_id,
        )
        # NOTE(v2): could additionally re-verify the NEW address via link-token;
        # §4I only requires proving ownership of the OLD one.
        await log_profile_change(
            db, str(user.user_id), "email", verified_via="email_code",
            old_value=record["email"],
        )
        applied.append("email")

    logger.info("sensitive_profile_updated", user_id=str(user.user_id), fields=applied)
    return {"message": "Changes saved.", "applied": applied}


def _as_float(value):
    return float(value) if value is not None else None



# --------------------------------------------------------------------------- #
# GET /v1/users/me/export — download my data (Phase B2)
# --------------------------------------------------------------------------- #
@router.get("/me/export")
async def export_my_data(
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    import json
    from datetime import date

    data = await account_deletion.export_user_data(db, str(user.user_id))
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="folium-my-data-{date.today().isoformat()}.json"'},
    )


# --------------------------------------------------------------------------- #
# POST /v1/users/me/delete — delete my account, with a grace period (Phase B2)
# --------------------------------------------------------------------------- #
@router.post("/me/delete")
async def delete_my_account(
    request: Request,
    response: Response,
    payload: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    record = await db.fetchrow("SELECT password_hash, mfa_secret_enc FROM users WHERE user_id = $1", user.user_id)
    if not verify_password(payload.password, record["password_hash"] or ""):
        raise AppError(status_code=401, error="INVALID_CREDENTIALS", message="Invalid credentials")
    if user.mfa_enabled:
        if not payload.totp_code:
            raise AppError(status_code=400, error="TOTP_REQUIRED", message="TOTP code is required for sensitive changes.")
        if not mfa_handler.verify_user_totp(record["mfa_secret_enc"], payload.totp_code):
            raise AppError(status_code=401, error="INVALID_MFA_CODE", message="Invalid code. Please try again.")

    purge_after = await account_deletion.schedule_deletion(db, str(user.user_id), payload.reason)

    # Signed out here too: the current tokens die now, not when they expire.
    for cookie, kind in ((ACCESS_COOKIE_NAME, "access"), (REFRESH_COOKIE_NAME, "refresh")):
        raw = request.cookies.get(cookie)
        if raw:
            try:
                p = decode_token(raw, expected_type=kind)
                await redis.blacklist_jti(p.get("jti", ""), seconds_until_expiry(p))
            except TokenError:
                pass
    await revoke_csrf_token(redis, str(user.user_id))
    clear_auth_cookies(response)
    return {
        "message": "Your account is scheduled for deletion.",
        "purge_after": purge_after.isoformat(),
        "grace_days": account_deletion.GRACE_DAYS,
    }



# --------------------------------------------------------------------------- #
# PUT /v1/users/me/ai-consent — Gemini help on or off (Phase B3)
# --------------------------------------------------------------------------- #
@router.put("/me/ai-consent")
async def set_ai_consent(
    payload: AiConsentRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Let Gemini read this investor's comments and word the two cases.

    Off by default. Turning it on sends the comment and the analysis's numbers
    to Google for future analyses; nothing already done is resent.
    """
    enabled = payload.enabled
    await db.execute("UPDATE users SET ai_consent = $1, updated_at = NOW() WHERE user_id = $2", enabled, user.user_id)
    from ...core.ai_help import available

    return {"ai_consent": enabled, "ai_help_available": available()}
