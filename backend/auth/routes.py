"""/v1/auth/* endpoints (Milestone 1 — non-MFA, non-OAuth branches).

Implements §1B/1C/1G/1H exactly (status codes, messages, Redis keys, cookie
flags). MFA (§1D/1E) and Google OAuth (§1F) are Milestone 2 and are left as
clean ``TODO(M2)`` seams — login only handles the ``mfa_enabled=false`` branch.

Redis keys (§2B):
    email_verify:{token}  TTL 86400
    pw_reset:{token}      TTL 900
Blacklisting (Amendment 10): logout and refresh rotation blacklist BOTH the
refresh jti and the current access jti.

NOTE: this module deliberately does NOT use ``from __future__ import annotations``.
With PEP 563 string annotations, FastAPI cannot resolve the body-parameter type
through slowapi's ``@limiter.limit`` wrapper and misclassifies the Pydantic body
as a query parameter. Keeping real (evaluated) annotations avoids that.
"""
import structlog
from fastapi import APIRouter, Depends, Request, Response

from ..config import get_settings
from ..db import Database, RedisService
from ..errors import AppError
from ..middleware.rate_limiter import (
    FORGOT_PASSWORD_LIMIT,
    LOGIN_LIMIT,
    REGISTER_LIMIT,
    limiter,
)
from ..models import User
from ..schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from ..services.email_service import EmailService
from ..state import get_db, get_redis_service
from .cookies import clear_auth_cookies, set_auth_cookies
from .csrf import issue_csrf_token, revoke_csrf_token
from .dependencies import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, get_current_user
from .jwt_handler import (
    TokenError,
    create_token_pair,
    decode_token,
    generate_url_token,
    hash_refresh_token,
    seconds_until_expiry,
)
from .password import (
    WeakPasswordError,
    assert_password_strength,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

_EMAIL_VERIFY_TTL = 86400  # 24h (§1B / §2B)
_PW_RESET_TTL = 900        # 15m (§1G / §2B)

_email_service = EmailService()


def _weak_password_error(exc: WeakPasswordError) -> AppError:
    """The §3D WEAK_PASSWORD shape."""
    return AppError(
        status_code=422,
        error="WEAK_PASSWORD",
        message="Password is too weak. Try adding numbers or symbols.",
        detail={"score": exc.score, "suggestions": exc.suggestions},
    )


async def _issue_session(
    response: Response,
    db: Database,
    redis: RedisService,
    user_id: str,
    role: str,
    request: Request,
) -> None:
    """Mint tokens, persist the refresh row, set cookies + CSRF (login/refresh)."""
    settings = get_settings()
    pair = create_token_pair(user_id, role)

    await db.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, jti, expires_at, user_agent, ip_address)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user_id,
        hash_refresh_token(pair.refresh_token),
        pair.refresh_jti,
        pair.refresh_expires_at,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )

    csrf_token = await issue_csrf_token(redis, user_id)
    set_auth_cookies(
        response,
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        csrf_token=csrf_token,
        access_ttl=settings.ACCESS_TOKEN_TTL_SECONDS,
        refresh_ttl=settings.REFRESH_TOKEN_TTL_SECONDS,
    )


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
@router.post("/register", status_code=201)
@limiter.limit(REGISTER_LIMIT)
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    # 3. strength check (before hashing) — reject weak (§1B step 3)
    try:
        assert_password_strength(payload.password, user_inputs=[payload.email, payload.name])
    except WeakPasswordError as exc:
        raise _weak_password_error(exc)

    existing = await db.fetchrow("SELECT user_id, is_active, email_verified FROM users WHERE email = $1", payload.email)
    if existing is not None:
        # Edge case (§1B): unverified account re-registering — replace it.
        if not existing["is_active"] and not existing["email_verified"]:
            await db.execute("DELETE FROM users WHERE user_id = $1", existing["user_id"])
        else:
            raise AppError(status_code=409, error="EMAIL_EXISTS", message="Email already registered")

    password_hash = hash_password(payload.password)
    user_id = await db.fetchval(
        """
        INSERT INTO users (
            email, password_hash, name,
            age, monthly_income, monthly_expense, risk_tolerance,
            investment_horizon, has_emergency_fund, financial_strategy, goal, phone,
            is_active, email_verified
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12, FALSE, FALSE)
        RETURNING user_id
        """,
        payload.email,
        password_hash,
        payload.name,
        payload.age,
        payload.monthly_income,
        payload.monthly_expense,
        payload.risk_tolerance,
        payload.investment_horizon,
        payload.has_emergency_fund,
        payload.financial_strategy,
        payload.goal,
        payload.phone,
    )

    token = generate_url_token(32)  # 64 hex chars
    await redis.set_with_ttl(f"email_verify:{token}", str(user_id), _EMAIL_VERIFY_TTL)
    await _email_service.send_verification_email(payload.email, token)

    logger.info("user_registered", user_id=str(user_id), email=payload.email)
    return {"message": "Check your email to verify your account."}


# --------------------------------------------------------------------------- #
# Email verification
# --------------------------------------------------------------------------- #
@router.get("/verify-email")
async def verify_email(
    token: str,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    key = f"email_verify:{token}"
    user_id = await redis.get(key)
    if not user_id:
        raise AppError(status_code=400, error="INVALID_TOKEN", message="Invalid or expired token")

    await db.execute(
        "UPDATE users SET email_verified = TRUE, is_active = TRUE, updated_at = NOW() WHERE user_id = $1",
        user_id,
    )
    await redis.delete(key)  # one-time use
    logger.info("email_verified", user_id=user_id)
    return {"message": "Email verified. Please log in.", "verified": True}


# --------------------------------------------------------------------------- #
# Login (non-MFA branch only — Milestone 1)
# --------------------------------------------------------------------------- #
@router.post("/login")
@limiter.limit(LOGIN_LIMIT)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    record = await db.fetchrow("SELECT * FROM users WHERE email = $1", payload.email)
    # Do NOT reveal whether the email exists (§1C step 1).
    if record is None or not verify_password(payload.password, record["password_hash"] or ""):
        raise AppError(status_code=401, error="INVALID_CREDENTIALS", message="Invalid credentials")

    if record["deleted_at"] is not None:
        raise AppError(
            status_code=403,
            error="ACCOUNT_DELETED",
            message="This account has been scheduled for deletion.",
            extra={"recovery_link": "/auth/cancel-deletion"},
        )

    if not record["is_active"] or not record["email_verified"]:
        raise AppError(
            status_code=403,
            error="EMAIL_NOT_VERIFIED",
            message="Please verify your email before logging in.",
        )

    # TODO(M2): if record["mfa_enabled"] -> issue mfa_temp token + return
    #           {mfa_required: true, temp_token}. Milestone 1 handles only the
    #           mfa_enabled=false branch.

    await db.execute("UPDATE users SET last_login_at = NOW() WHERE user_id = $1", record["user_id"])
    await _issue_session(response, db, redis, str(record["user_id"]), record["role"], request)

    user = User.from_record(record)
    logger.info("user_login", user_id=str(user.user_id))
    return {"user": user.public_dict()}


# --------------------------------------------------------------------------- #
# Refresh (rotation + dual blacklist, Amendment 10)
# --------------------------------------------------------------------------- #
@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise AppError(status_code=401, error="NOT_AUTHENTICATED", message="Not authenticated")

    try:
        payload = decode_token(raw_refresh, expected_type="refresh")
    except TokenError as exc:
        raise AppError(status_code=401, error="INVALID_TOKEN", message=str(exc)) from exc

    refresh_jti = payload.get("jti", "")
    if await redis.is_blacklisted(refresh_jti):
        raise AppError(status_code=401, error="TOKEN_REVOKED", message="Token revoked")

    token_hash = hash_refresh_token(raw_refresh)
    row = await db.fetchrow(
        "SELECT token_id, user_id, revoked FROM refresh_tokens WHERE token_hash = $1",
        token_hash,
    )
    if row is None or str(row["user_id"]) != str(payload["sub"]) or row["revoked"]:
        raise AppError(status_code=401, error="INVALID_TOKEN", message="Invalid token")

    # Blacklist the OLD refresh jti for its remaining life (Amendment 10).
    await redis.blacklist_jti(refresh_jti, seconds_until_expiry(payload))
    # Also blacklist the CURRENT access jti so the outstanding access token dies too.
    access_raw = request.cookies.get(ACCESS_COOKIE_NAME)
    if access_raw:
        try:
            access_payload = decode_token(access_raw, expected_type="access")
            await redis.blacklist_jti(
                access_payload.get("jti", ""), seconds_until_expiry(access_payload)
            )
        except TokenError:
            pass  # already invalid — nothing to blacklist

    # Delete the old refresh row and issue a fresh session (rotation).
    await db.execute("DELETE FROM refresh_tokens WHERE token_id = $1", row["token_id"])
    await _issue_session(response, db, redis, str(payload["sub"]), payload["role"], request)

    logger.info("token_refreshed", user_id=str(payload["sub"]))
    return {"refreshed": True}


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #
@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    user_id: str | None = None
    if raw_refresh:
        try:
            payload = decode_token(raw_refresh, expected_type="refresh")
            user_id = str(payload["sub"])
            await redis.blacklist_jti(payload.get("jti", ""), seconds_until_expiry(payload))
            await db.execute(
                "DELETE FROM refresh_tokens WHERE token_hash = $1",
                hash_refresh_token(raw_refresh),
            )
        except TokenError:
            pass

    # Also blacklist the current access jti (Amendment 10).
    raw_access = request.cookies.get(ACCESS_COOKIE_NAME)
    if raw_access:
        try:
            ap = decode_token(raw_access, expected_type="access")
            user_id = user_id or str(ap["sub"])
            await redis.blacklist_jti(ap.get("jti", ""), seconds_until_expiry(ap))
        except TokenError:
            pass

    if user_id:
        await revoke_csrf_token(redis, user_id)

    clear_auth_cookies(response)
    return {"message": "Logged out."}


# --------------------------------------------------------------------------- #
# Forgot / reset password
# --------------------------------------------------------------------------- #
@router.post("/forgot-password")
@limiter.limit(FORGOT_PASSWORD_LIMIT)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    record = await db.fetchrow(
        "SELECT user_id, is_active FROM users WHERE email = $1", payload.email
    )
    # Only send if the account exists and is active — but always return 200 (§1G).
    if record is not None and record["is_active"]:
        token = generate_url_token(16)  # 32 hex chars
        await redis.set_with_ttl(f"pw_reset:{token}", str(record["user_id"]), _PW_RESET_TTL)
        await _email_service.send_password_reset_email(payload.email, token)
        logger.info("password_reset_requested", user_id=str(record["user_id"]))

    return {"message": "If that email is registered, you'll receive a reset link."}


@router.post("/reset-password")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    key = f"pw_reset:{payload.token}"
    user_id = await redis.get(key)
    if not user_id:
        raise AppError(status_code=400, error="INVALID_TOKEN", message="Invalid or expired reset link.")

    try:
        assert_password_strength(payload.new_password)
    except WeakPasswordError as exc:
        raise _weak_password_error(exc)

    await db.execute(
        "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE user_id = $2",
        hash_password(payload.new_password),
        user_id,
    )
    await redis.delete(key)  # one-time use

    # Invalidate ALL refresh tokens for this user (§1G: re-auth everywhere).
    await db.execute("DELETE FROM refresh_tokens WHERE user_id = $1", user_id)
    await revoke_csrf_token(redis, user_id)
    await _log_profile_change(db, user_id, "password", verified_via="email_token")

    logger.info("password_reset", user_id=user_id)
    return {"message": "Password updated. Please log in."}


# --------------------------------------------------------------------------- #
# Change password (authenticated)
# --------------------------------------------------------------------------- #
@router.post("/change-password")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    record = await db.fetchrow(
        "SELECT password_hash FROM users WHERE user_id = $1", user.user_id
    )
    if not verify_password(payload.current_password, record["password_hash"] or ""):
        raise AppError(status_code=401, error="INVALID_CREDENTIALS", message="Invalid credentials")

    # TODO(M2): if user.mfa_enabled -> require + verify payload.totp_code (§1G).

    try:
        assert_password_strength(payload.new_password, user_inputs=[user.email, user.name])
    except WeakPasswordError as exc:
        raise _weak_password_error(exc)

    await db.execute(
        "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE user_id = $2",
        hash_password(payload.new_password),
        user.user_id,
    )
    # Rotate all refresh tokens (§1G).
    await db.execute("DELETE FROM refresh_tokens WHERE user_id = $1", user.user_id)
    await revoke_csrf_token(redis, str(user.user_id))
    await _log_profile_change(db, str(user.user_id), "password", verified_via="password")

    logger.info("password_changed", user_id=str(user.user_id))
    return {"message": "Password updated. Please log in."}


# --------------------------------------------------------------------------- #
# Me
# --------------------------------------------------------------------------- #
@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(**user.public_dict())


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _log_profile_change(db: Database, user_id: str, field: str, verified_via: str) -> None:
    """Append a profile_change_log row inside an RLS transaction (Amendment 9)."""
    async with db.rls_transaction(user_id) as conn:
        await conn.execute(
            """
            INSERT INTO profile_change_log (user_id, field_changed, verified_via)
            VALUES ($1, $2, $3)
            """,
            user_id,
            field,
            verified_via,
        )
