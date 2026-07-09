"""Profile management tests (§4I backend side + §10 schemas)."""
from __future__ import annotations

import pytest

from .helpers import (
    STRONG_PASSWORD,
    csrf_header,
    enable_mfa,
    login_user,
    register_and_verify,
    totp_now,
)

pytestmark = pytest.mark.asyncio


async def _login(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    resp = await login_user(client, email)
    assert resp.status_code == 200


async def test_get_profile_with_bias_zeros(client, redis_conn, db_conn):
    email = "profile-get@example.com"
    await _login(client, redis_conn, email)

    resp = await client.get("/v1/users/me/profile")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["profile"]["email"] == email
    assert body["profile"]["name"] == "Test User"
    assert "password_hash" not in body["profile"]  # never exposed
    # bias_profiles zeros row auto-created on first read.
    bias = body["bias_profile"]
    assert bias["disposition_score"] == 0.0
    assert bias["rational_score"] == 0.0
    assert bias["total_decisions"] == 0
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM bias_profiles b JOIN users u ON u.user_id=b.user_id "
        "WHERE u.email=$1", email,
    ) == 1


async def test_update_profile_non_sensitive(client, redis_conn, db_conn):
    email = "profile-basic@example.com"
    await _login(client, redis_conn, email)

    # Invalid strategy rejected before touching the DB CHECK constraint.
    bad = await client.put(
        "/v1/users/me/profile",
        json={"name": "X", "financial_strategy": "yolo"},
        headers=csrf_header(client),
    )
    assert bad.status_code == 422

    resp = await client.put(
        "/v1/users/me/profile",
        json={"name": "Renamed User", "goal": "House", "financial_strategy": "aggressive"},
        headers=csrf_header(client),
    )
    assert resp.status_code == 200, resp.text

    prof = (await client.get("/v1/users/me/profile")).json()["profile"]
    assert prof["name"] == "Renamed User"
    assert prof["goal"] == "House"
    assert prof["financial_strategy"] == "aggressive"

    # Each changed field logged (verified_via='session' for non-sensitive).
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM profile_change_log p JOIN users u ON u.user_id=p.user_id "
        "WHERE u.email=$1 AND p.verified_via='session'", email,
    )
    assert n == 3  # name, goal, financial_strategy


async def test_sensitive_wrong_password_401(client, redis_conn, db_conn):
    email = "profile-wrongpw@example.com"
    await _login(client, redis_conn, email)

    resp = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"monthly_income": 90000, "password": "not-my-password"},
        headers=csrf_header(client),
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "INVALID_CREDENTIALS"
    assert await db_conn.fetchval(
        "SELECT monthly_income FROM users WHERE email=$1", email
    ) is None  # unchanged


async def test_sensitive_income_update_with_password(client, redis_conn, db_conn):
    email = "profile-income@example.com"
    await _login(client, redis_conn, email)

    resp = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"monthly_income": 85000, "has_emergency_fund": True,
              "password": STRONG_PASSWORD},
        headers=csrf_header(client),
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["applied"]) == {"monthly_income", "has_emergency_fund"}

    row = await db_conn.fetchrow(
        "SELECT monthly_income, has_emergency_fund FROM users WHERE email=$1", email
    )
    assert float(row["monthly_income"]) == 85000.0
    assert row["has_emergency_fund"] is True

    # Logged with verified_via='password' (§4I) — one row per applied field.
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM profile_change_log p JOIN users u ON u.user_id=p.user_id "
        "WHERE u.email=$1 AND p.verified_via='password'", email,
    )
    assert n == 2


async def test_sensitive_email_change_otp_flow(client, redis_conn, db_conn):
    old_email = "profile-oldmail@example.com"
    new_email = "profile-newmail@example.com"
    await _login(client, redis_conn, old_email)

    # Step 1: no otp -> code goes to the OLD address, nothing changes yet.
    step1 = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"email": new_email, "password": STRONG_PASSWORD},
        headers=csrf_header(client),
    )
    assert step1.status_code == 200, step1.text
    assert step1.json()["otp_required"] is True
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE email=$1", old_email
    ) == 1  # unchanged

    otp_keys = await redis_conn.keys("otp:*")
    assert len(otp_keys) == 1
    otp = await redis_conn.get(otp_keys[0])
    assert otp and len(otp) == 6

    # Wrong OTP -> 400, key survives for a retry.
    wrong = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"email": new_email, "password": STRONG_PASSWORD,
              "otp": "000000" if otp != "000000" else "111111"},
        headers=csrf_header(client),
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "INVALID_OTP"

    # Step 2: correct OTP -> email changes; OTP key consumed.
    step2 = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"email": new_email, "password": STRONG_PASSWORD, "otp": otp},
        headers=csrf_header(client),
    )
    assert step2.status_code == 200, step2.text
    assert "email" in step2.json()["applied"]
    assert await redis_conn.keys("otp:*") == []
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE email=$1", new_email
    ) == 1

    # Change log row with the §2C 'email_code' verification method.
    logged = await db_conn.fetchrow(
        "SELECT old_value_hash FROM profile_change_log p JOIN users u ON u.user_id=p.user_id "
        "WHERE u.email=$1 AND p.field_changed='email' AND p.verified_via='email_code'",
        new_email,
    )
    assert logged is not None and logged["old_value_hash"]  # hashed, not plaintext

    # The new email logs in; the old one no longer exists.
    out = await client.post("/v1/auth/logout", headers=csrf_header(client))
    assert out.status_code == 200
    assert (await login_user(client, new_email)).status_code == 200
    assert (await login_user(client, old_email)).status_code == 401


async def test_sensitive_requires_totp_when_mfa_on(client, redis_conn, db_conn):
    email = "profile-mfa@example.com"
    await _login(client, redis_conn, email)
    secret, _ = await enable_mfa(client)

    missing = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"monthly_expense": 30000, "password": STRONG_PASSWORD},
        headers=csrf_header(client),
    )
    assert missing.status_code == 400
    assert missing.json()["error"] == "TOTP_REQUIRED"

    ok = await client.put(
        "/v1/users/me/profile/sensitive",
        json={"monthly_expense": 30000, "password": STRONG_PASSWORD,
              "totp_code": totp_now(secret)},
        headers=csrf_header(client),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["applied"] == ["monthly_expense"]
    # Logged with the stronger method when MFA is on.
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM profile_change_log p JOIN users u ON u.user_id=p.user_id "
        "WHERE u.email=$1 AND p.field_changed='monthly_expense' "
        "AND p.verified_via='password+totp'", email,
    )
    assert n == 1
