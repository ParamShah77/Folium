"""/v1/auth/* endpoints (Milestones 1+2).

Implements §1B/1C/1D/1E/1F/1G/1H exactly (status codes, messages, Redis keys,
cookie flags): email/password auth, TOTP MFA (setup / verify-setup / disable /
login second step with backup codes), MFA recovery requests, and Google OAuth
(cases A–D with the MFA interaction).

Redis keys (§2B):
    email_verify:{token}   TTL 86400
    pw_reset:{token}       TTL 900
    mfa_temp:{token}       TTL 300   (login -> TOTP step)
    mfa_setup:{user_id}    TTL 600   (setup -> verify-setup)
    mfa_recovery:{email}   TTL 86400 (1-per-24h recovery cooldown)
    oauth_state:{state}    TTL 600   (OAuth CSRF state, single-use)
Blacklisting (Amendment 10): logout and refresh rotation blacklist BOTH the
refresh jti and the current access jti.

NOTE: this module deliberately does NOT use ``from __future__ import annotations``.
With PEP 563 string annotations, FastAPI cannot resolve the body-parameter type
through slowapi's ``@limiter.limit`` wrapper and misclassifies the Pydantic body
as a query parameter. Keeping real (evaluated) annotations avoids that.
"""
import secrets

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

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
    MfaDisableRequest,
    MfaLoginRequest,
    MfaRecoveryRequestInput,
    MfaVerifySetupRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from ..services.email_service import EmailService
from ..services.profile_log import log_profile_change
from ..state import get_db, get_redis_service
from . import mfa_handler, oauth_handler
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

_EMAIL_VERIFY_TTL = 86400   # 24h (§1B / §2B)
_PW_RESET_TTL = 900         # 15m (§1G / §2B)
_MFA_TEMP_TTL = 300         # 5m  (§1C / §2B)
_MFA_SETUP_TTL = 600        # 10m (§1D / §2B)
_MFA_RECOVERY_TTL = 86400   # 24h cooldown (§1E / §2B)

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
# Login (§1C — MFA users get a temp token; see /login/mfa below)
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

    await db.execute("UPDATE users SET last_login_at = NOW() WHERE user_id = $1", record["user_id"])

    if record["mfa_enabled"]:
        # §1C: hand back a short-lived temp token; the session is only issued
        # after the TOTP (or backup-code) step at POST /login/mfa.
        temp_token = secrets.token_hex(16)  # 32-char random hex (§1C)
        await redis.set_with_ttl(
            f"mfa_temp:{temp_token}", str(record["user_id"]), _MFA_TEMP_TTL
        )
        logger.info("login_mfa_required", user_id=str(record["user_id"]))
        return {"mfa_required": True, "temp_token": temp_token}

    await _issue_session(response, db, redis, str(record["user_id"]), record["role"], request)

    user = User.from_record(record)
    logger.info("user_login", user_id=str(user.user_id))
    return {"user": user.public_dict()}


# --------------------------------------------------------------------------- #
# Login — MFA second step (§1C)
# --------------------------------------------------------------------------- #
@router.post("/login/mfa")
@limiter.limit(LOGIN_LIMIT)
async def login_mfa(
    request: Request,
    response: Response,
    payload: MfaLoginRequest,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    key = f"mfa_temp:{payload.temp_token}"
    user_id = await redis.get(key)
    if not user_id:
        raise AppError(
            status_code=401,
            error="MFA_SESSION_EXPIRED",
            message="Session expired. Please log in again.",
        )

    record = await db.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    if record is None or not record["mfa_enabled"] or record["deleted_at"] is not None:
        await redis.delete(key)
        raise AppError(
            status_code=401,
            error="MFA_SESSION_EXPIRED",
            message="Session expired. Please log in again.",
        )

    warning = None
    if mfa_handler.verify_user_totp(record["mfa_secret_enc"], payload.totp_code):
        pass  # TOTP accepted
    else:
        # §1C step 5: also accept single-use backup codes.
        remaining = await mfa_handler.try_consume_backup_code(
            db, str(record["user_id"]), payload.totp_code
        )
        if remaining is None:
            raise AppError(
                status_code=401,
                error="INVALID_MFA_CODE",
                message="Invalid code. Please try again.",
            )
        warning = f"You used a backup code. {remaining} backup codes remaining."

    await redis.delete(key)  # temp token is single-use
    await _issue_session(response, db, redis, str(record["user_id"]), record["role"], request)

    user = User.from_record(record)
    logger.info("user_login_mfa", user_id=str(user.user_id), used_backup=warning is not None)
    body = {"user": user.public_dict()}
    if warning:
        body["warning"] = warning
    return body


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
    await log_profile_change(db, user_id, "password", verified_via="email_token")

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
        "SELECT password_hash, mfa_secret_enc FROM users WHERE user_id = $1", user.user_id
    )
    if not verify_password(payload.current_password, record["password_hash"] or ""):
        raise AppError(status_code=401, error="INVALID_CREDENTIALS", message="Invalid credentials")

    # §1G: when MFA is enabled, changing the password additionally requires TOTP.
    if user.mfa_enabled:
        if not payload.totp_code:
            raise AppError(
                status_code=400,
                error="TOTP_REQUIRED",
                message="TOTP code is required to change your password.",
            )
        if not mfa_handler.verify_user_totp(record["mfa_secret_enc"], payload.totp_code):
            raise AppError(
                status_code=401,
                error="INVALID_MFA_CODE",
                message="Invalid code. Please try again.",
            )

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
    verified_via = "password+totp" if user.mfa_enabled else "password"
    await log_profile_change(db, str(user.user_id), "password", verified_via=verified_via)

    logger.info("password_changed", user_id=str(user.user_id))
    return {"message": "Password updated. Please log in."}


# --------------------------------------------------------------------------- #
# MFA setup / verify-setup / disable (§1D)
# --------------------------------------------------------------------------- #
@router.post("/mfa/setup")
async def mfa_setup(
    request: Request,
    user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service),
):
    if user.mfa_enabled:
        raise AppError(
            status_code=400,
            error="MFA_ALREADY_ENABLED",
            message="MFA is already enabled on this account.",
        )

    secret = mfa_handler.generate_totp_secret()
    # Stored in Redis ONLY — nothing touches the DB until verify-setup succeeds.
    await redis.set_with_ttl(f"mfa_setup:{user.user_id}", secret, _MFA_SETUP_TTL)

    return {
        "secret": secret,
        "qr_code_url": mfa_handler.provisioning_uri(secret, user.email),
    }


@router.post("/mfa/verify-setup")
async def mfa_verify_setup(
    request: Request,
    payload: MfaVerifySetupRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    key = f"mfa_setup:{user.user_id}"
    secret = await redis.get(key)
    if not secret:
        raise AppError(
            status_code=400,
            error="MFA_SETUP_EXPIRED",
            message="Setup session expired. Start again.",
        )

    if not mfa_handler.verify_totp(secret, payload.totp_code):
        raise AppError(status_code=400, error="INVALID_MFA_CODE", message="Invalid code")

    display_codes, hashes = mfa_handler.generate_backup_codes()
    await db.execute(
        "UPDATE users SET mfa_secret_enc = $1, mfa_enabled = TRUE, updated_at = NOW() "
        "WHERE user_id = $2",
        mfa_handler.encrypt_totp_secret(secret),
        user.user_id,
    )
    await mfa_handler.store_backup_codes(db, str(user.user_id), hashes)
    await redis.delete(key)
    await log_profile_change(db, str(user.user_id), "mfa_status", verified_via="totp")

    logger.info("mfa_enabled", user_id=str(user.user_id))
    # Shown ONCE — the frontend must force the user to save these (§1D).
    return {"backup_codes": display_codes}


@router.post("/mfa/disable")
async def mfa_disable(
    request: Request,
    payload: MfaDisableRequest,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    record = await db.fetchrow(
        "SELECT password_hash, mfa_secret_enc, mfa_enabled FROM users WHERE user_id = $1",
        user.user_id,
    )
    if not record["mfa_enabled"]:
        raise AppError(
            status_code=400, error="MFA_NOT_ENABLED", message="MFA is not enabled."
        )
    if not verify_password(payload.password, record["password_hash"] or ""):
        raise AppError(status_code=401, error="INVALID_CREDENTIALS", message="Invalid credentials")
    if not mfa_handler.verify_user_totp(record["mfa_secret_enc"], payload.totp_code):
        raise AppError(
            status_code=401,
            error="INVALID_MFA_CODE",
            message="Invalid code. Please try again.",
        )

    await mfa_handler.wipe_mfa(db, str(user.user_id))
    await log_profile_change(
        db, str(user.user_id), "mfa_status", verified_via="password+totp"
    )
    # §1D step 6: force re-login everywhere.
    await db.execute("DELETE FROM refresh_tokens WHERE user_id = $1", user.user_id)
    await revoke_csrf_token(redis, str(user.user_id))

    logger.info("mfa_disabled", user_id=str(user.user_id))
    return {"message": "MFA disabled."}


# --------------------------------------------------------------------------- #
# MFA recovery request (§1E) — pre-session (user is locked out of MFA)
# --------------------------------------------------------------------------- #
@router.post("/mfa-recovery-request")
async def mfa_recovery_request(
    request: Request,
    payload: MfaRecoveryRequestInput,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    # §1E step 1: 1 request per email per 24h (single-use Redis cooldown key).
    allowed = await redis.set_if_absent(
        f"mfa_recovery:{payload.email}", "1", _MFA_RECOVERY_TTL
    )
    if not allowed:
        raise AppError(
            status_code=429,
            error="RATE_LIMITED",
            message="You can only request MFA recovery once per 24 hours.",
        )

    row = await db.fetchrow(
        "SELECT user_id FROM users WHERE email = $1", payload.email
    )
    created = await db.fetchrow(
        """
        INSERT INTO mfa_recovery_requests (user_id, email, message)
        VALUES ($1, $2, $3)
        RETURNING request_id, created_at
        """,
        row["user_id"] if row else None,
        payload.email,
        payload.message,
    )
    await _email_service.send_mfa_recovery_admin_notification(
        user_email=payload.email,
        message=payload.message,
        requested_at=created["created_at"].isoformat(),
    )

    logger.info("mfa_recovery_requested", email=payload.email)
    return {"message": "Request submitted. We'll contact you within 24 hours."}


# --------------------------------------------------------------------------- #
# Google OAuth (§1F)
# --------------------------------------------------------------------------- #
def _oauth_redirect_uri(request: Request) -> str:
    settings = get_settings()
    if settings.GOOGLE_OAUTH_REDIRECT_URI:
        return settings.GOOGLE_OAUTH_REDIRECT_URI
    return str(request.base_url).rstrip("/") + "/v1/auth/google/callback"


def _require_oauth_configured() -> None:
    if not oauth_handler.is_configured():
        raise AppError(
            status_code=503,
            error="OAUTH_NOT_CONFIGURED",
            message="Google login not configured",
        )


@router.get("/google/login")
async def google_login(
    request: Request,
    redis: RedisService = Depends(get_redis_service),
):
    _require_oauth_configured()

    state = oauth_handler.generate_state()
    await redis.set_with_ttl(f"oauth_state:{state}", "1", oauth_handler.OAUTH_STATE_TTL)
    url = oauth_handler.build_authorize_url(state, _oauth_redirect_uri(request))
    return RedirectResponse(url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: Database = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    _require_oauth_configured()

    # State CSRF check — must exist in Redis and is single-use (§1F/§1H).
    state_key = f"oauth_state:{state}"
    if not await redis.get(state_key):
        raise AppError(
            status_code=403,
            error="OAUTH_STATE_INVALID",
            message="OAuth state validation failed. Start the login again.",
        )
    await redis.delete(state_key)

    # Exchange the code for the Google profile. Module attribute access so
    # tests can monkeypatch backend.auth.oauth_handler.exchange_code.
    try:
        profile = await oauth_handler.exchange_code(code, _oauth_redirect_uri(request))
    except oauth_handler.OAuthExchangeError as exc:
        raise AppError(
            status_code=502,
            error="OAUTH_EXCHANGE_FAILED",
            message="Google login failed. Please try again.",
        ) from exc

    record = await db.fetchrow("SELECT * FROM users WHERE email = $1", profile.email)

    # CASE D — soft-deleted account (checked before anything else).
    if record is not None and record["deleted_at"] is not None:
        raise AppError(
            status_code=403,
            error="ACCOUNT_DELETED",
            message="This account has been scheduled for deletion.",
            extra={"recovery_link": "/auth/cancel-deletion"},
        )

    if record is None:
        # CASE A — new user: auto-register. Google has verified the email.
        user_id = await db.fetchval(
            """
            INSERT INTO users (email, name, profile_picture,
                               oauth_provider, oauth_id,
                               email_verified, is_active)
            VALUES ($1, $2, $3, 'google', $4, TRUE, TRUE)
            RETURNING user_id
            """,
            profile.email,
            profile.name,
            profile.picture,
            profile.sub,
        )
        record = await db.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        logger.info("oauth_registered", user_id=str(user_id))
    elif record["oauth_id"] is None:
        # CASE B — existing email/password user, first Google login: link
        # silently (same email = same person, §1F). Google also proves email
        # ownership, so an unverified local account becomes verified.
        await db.execute(
            """
            UPDATE users SET oauth_id = $1, oauth_provider = 'google',
                             email_verified = TRUE, is_active = TRUE,
                             profile_picture = COALESCE(profile_picture, $2),
                             updated_at = NOW()
            WHERE user_id = $3
            """,
            profile.sub,
            profile.picture,
            record["user_id"],
        )
        record = await db.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", record["user_id"]
        )
        logger.info("oauth_linked", user_id=str(record["user_id"]))
    elif record["oauth_id"] != profile.sub:
        # Defensive: same email but a different Google account id.
        raise AppError(
            status_code=409,
            error="OAUTH_ACCOUNT_MISMATCH",
            message="This email is linked to a different Google account.",
        )
    # else: CASE C — returning OAuth user; fall through to login.

    await db.execute(
        "UPDATE users SET last_login_at = NOW() WHERE user_id = $1", record["user_id"]
    )

    # §1F: MFA enabled = TOTP required regardless of login method.
    if record["mfa_enabled"]:
        temp_token = secrets.token_hex(16)
        await redis.set_with_ttl(
            f"mfa_temp:{temp_token}", str(record["user_id"]), _MFA_TEMP_TTL
        )
        logger.info("oauth_login_mfa_required", user_id=str(record["user_id"]))
        return {"mfa_required": True, "temp_token": temp_token}

    await _issue_session(response, db, redis, str(record["user_id"]), record["role"], request)
    user = User.from_record(record)
    logger.info("oauth_login", user_id=str(user.user_id))
    return {"user": user.public_dict()}


# --------------------------------------------------------------------------- #
# Me
# --------------------------------------------------------------------------- #
@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(**user.public_dict())
