"""MFA recovery request + admin reset tests (§1E, Amendment 5)."""
from __future__ import annotations

import pyotp
import pytest

from .helpers import (
    STRONG_PASSWORD,
    csrf_header,
    login_user,
    register_and_verify,
    totp_now,
    wrong_totp,
)

pytestmark = pytest.mark.asyncio


async def _seed_admin(db_conn, email: str = "admin@example.com"):
    """Insert an active admin WITH MFA enabled directly (superuser fixture).

    Returns (admin_user_id, admin_totp_secret).
    """
    from backend.auth.mfa_handler import encrypt_totp_secret
    from backend.auth.password import hash_password

    secret = pyotp.random_base32()
    admin_id = await db_conn.fetchval(
        """
        INSERT INTO users (email, name, role, password_hash,
                           is_active, email_verified, mfa_enabled, mfa_secret_enc)
        VALUES ($1, 'Admin', 'admin', $2, TRUE, TRUE, TRUE, $3)
        RETURNING user_id
        """,
        email,
        hash_password(STRONG_PASSWORD),
        encrypt_totp_secret(secret),
    )
    return str(admin_id), secret


async def _login_admin(client, email: str, secret: str) -> None:
    first = await login_user(client, email)
    assert first.json().get("mfa_required") is True
    second = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": first.json()["temp_token"], "totp_code": totp_now(secret)},
    )
    assert second.status_code == 200, second.text


async def _seed_mfa_target(db_conn, email: str):
    """A normal user with MFA on + one backup code (to assert wiping)."""
    from backend.auth.mfa_handler import encrypt_totp_secret
    from backend.auth.password import hash_password

    secret = pyotp.random_base32()
    user_id = await db_conn.fetchval(
        """
        INSERT INTO users (email, name, password_hash,
                           is_active, email_verified, mfa_enabled, mfa_secret_enc)
        VALUES ($1, 'Target', $2, TRUE, TRUE, TRUE, $3)
        RETURNING user_id
        """,
        email,
        hash_password(STRONG_PASSWORD),
        encrypt_totp_secret(secret),
    )
    await db_conn.execute(
        "INSERT INTO mfa_backup_codes (user_id, code_hash) VALUES ($1, 'x')", user_id
    )
    await db_conn.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, jti, expires_at)
        VALUES ($1, 'seed-hash', 'seed-jti', NOW() + INTERVAL '7 days')
        """,
        user_id,
    )
    return str(user_id)


async def test_recovery_request_created_and_rate_limited(client, db_conn):
    email = "locked-out@example.com"
    # Pre-session endpoint: no auth, no CSRF header needed.
    first = await client.post(
        "/v1/auth/mfa-recovery-request",
        json={"email": email, "message": "Lost my phone and my backup codes."},
    )
    assert first.status_code == 200
    assert "within 24 hours" in first.json()["message"]

    row = await db_conn.fetchrow(
        "SELECT status, email, message FROM mfa_recovery_requests WHERE email = $1",
        email,
    )
    assert row is not None and row["status"] == "pending"

    # §1E step 1: 1 request per email per 24h.
    second = await client.post(
        "/v1/auth/mfa-recovery-request",
        json={"email": email, "message": "Please hurry."},
    )
    assert second.status_code == 429
    assert second.json()["error"] == "RATE_LIMITED"
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM mfa_recovery_requests WHERE email = $1", email
    )
    assert n == 1  # no second row


async def test_admin_reset_mfa_full_flow(client, db_conn):
    admin_id, admin_secret = await _seed_admin(db_conn)
    target_email = "reset-me@example.com"
    target_id = await _seed_mfa_target(db_conn, target_email)

    # The locked-out user files a recovery request.
    resp = await client.post(
        "/v1/auth/mfa-recovery-request",
        json={"email": target_email, "message": "Authenticator gone."},
    )
    assert resp.status_code == 200

    # Admin logs in (their own MFA) and resets the target.
    await _login_admin(client, "admin@example.com", admin_secret)
    reset = await client.post(
        f"/v1/admin/users/{target_id}/reset-mfa",
        json={"admin_totp_code": totp_now(admin_secret)},
        headers=csrf_header(client),
    )
    assert reset.status_code == 200, reset.text

    # Target: MFA wiped, backup codes gone, sessions invalidated.
    row = await db_conn.fetchrow(
        "SELECT mfa_enabled, mfa_secret_enc FROM users WHERE user_id = $1", target_id
    )
    assert row["mfa_enabled"] is False and row["mfa_secret_enc"] is None
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM mfa_backup_codes WHERE user_id = $1", target_id
    ) == 0
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = $1", target_id
    ) == 0

    # Recovery request resolved by this admin.
    req = await db_conn.fetchrow(
        "SELECT status, resolved_by, resolved_at FROM mfa_recovery_requests WHERE email = $1",
        target_email,
    )
    assert req["status"] == "resolved"
    assert str(req["resolved_by"]) == admin_id
    assert req["resolved_at"] is not None

    # Change log: admin_action row for the TARGET, changed_by = admin.
    log = await db_conn.fetchrow(
        "SELECT verified_via, changed_by FROM profile_change_log "
        "WHERE user_id = $1 AND field_changed = 'mfa_status'",
        target_id,
    )
    assert log["verified_via"] == "admin_action"
    assert str(log["changed_by"]) == admin_id

    # Target can now log in with password only (no MFA step).
    login = await login_user(client, target_email)
    assert login.status_code == 200
    assert "user" in login.json()


async def test_admin_reset_requires_admin_role(client, redis_conn, db_conn):
    email = "not-admin@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)
    target_id = await _seed_mfa_target(db_conn, "victim@example.com")

    resp = await client.post(
        f"/v1/admin/users/{target_id}/reset-mfa",
        json={"admin_totp_code": "000000"},
        headers=csrf_header(client),
    )
    assert resp.status_code == 403
    # Target untouched.
    assert await db_conn.fetchval(
        "SELECT mfa_enabled FROM users WHERE user_id = $1", target_id
    ) is True


async def test_admin_reset_wrong_admin_totp_401(client, db_conn):
    _, admin_secret = await _seed_admin(db_conn)
    target_id = await _seed_mfa_target(db_conn, "safe@example.com")
    await _login_admin(client, "admin@example.com", admin_secret)

    resp = await client.post(
        f"/v1/admin/users/{target_id}/reset-mfa",
        json={"admin_totp_code": wrong_totp(admin_secret)},
        headers=csrf_header(client),
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "INVALID_MFA_CODE"
    assert await db_conn.fetchval(
        "SELECT mfa_enabled FROM users WHERE user_id = $1", target_id
    ) is True
