"""TOTP MFA lifecycle tests (§1C/§1D/§1G)."""
from __future__ import annotations

import pytest

from .helpers import (
    STRONG_PASSWORD,
    csrf_header,
    enable_mfa,
    login_user,
    login_with_mfa,
    register_and_verify,
    totp_now,
    wrong_totp,
)

pytestmark = pytest.mark.asyncio


async def test_mfa_full_lifecycle(client, redis_conn, db_conn):
    """setup -> verify-setup -> logout -> login (temp token) -> TOTP step."""
    email = "mfa-life@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)

    # Setup + verify-setup: MFA on, 8 backup codes returned exactly once.
    secret, codes = await enable_mfa(client)
    row = await db_conn.fetchrow(
        "SELECT mfa_enabled, mfa_secret_enc FROM users WHERE email = $1", email
    )
    assert row["mfa_enabled"] is True
    assert row["mfa_secret_enc"] and row["mfa_secret_enc"] != secret  # encrypted at rest
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM mfa_backup_codes b JOIN users u ON u.user_id=b.user_id "
        "WHERE u.email=$1 AND b.used=FALSE", email,
    )
    assert n == 8
    # The setup Redis key is consumed.
    assert await redis_conn.keys("mfa_setup:*") == []

    me = await client.get("/v1/auth/me")
    assert me.json()["mfa_enabled"] is True

    # Fresh login now requires the TOTP step.
    await client.post("/v1/auth/logout", headers=csrf_header(client))
    first = await login_user(client, email)
    assert first.status_code == 200
    body = first.json()
    assert body == {"mfa_required": True, "temp_token": body["temp_token"]}
    assert not client.cookies.get("access_token")  # no session before step 2
    assert await redis_conn.get(f"mfa_temp:{body['temp_token']}") is not None

    second = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": body["temp_token"], "totp_code": totp_now(secret)},
    )
    assert second.status_code == 200, second.text
    assert second.json()["user"]["mfa_enabled"] is True
    assert "warning" not in second.json()
    assert client.cookies.get("access_token")
    # Temp token is single-use.
    assert await redis_conn.get(f"mfa_temp:{body['temp_token']}") is None
    replay = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": body["temp_token"], "totp_code": totp_now(secret)},
    )
    assert replay.status_code == 401
    assert replay.json()["error"] == "MFA_SESSION_EXPIRED"


async def test_mfa_wrong_code_rejected(client, redis_conn):
    email = "mfa-wrong@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)
    secret, _ = await enable_mfa(client)
    await client.post("/v1/auth/logout", headers=csrf_header(client))

    first = await login_user(client, email)
    temp = first.json()["temp_token"]
    bad = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": temp, "totp_code": wrong_totp(secret)},
    )
    assert bad.status_code == 401
    assert bad.json()["error"] == "INVALID_MFA_CODE"
    # Wrong code does NOT consume the temp token — the right code still works.
    good = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": temp, "totp_code": totp_now(secret)},
    )
    assert good.status_code == 200


async def test_backup_code_login_and_single_use(client, redis_conn, db_conn):
    email = "mfa-backup@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)
    secret, codes = await enable_mfa(client)
    await client.post("/v1/auth/logout", headers=csrf_header(client))

    # Login with a backup code instead of TOTP.
    first = await login_user(client, email)
    resp = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": first.json()["temp_token"], "totp_code": codes[0]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["warning"] == "You used a backup code. 7 backup codes remaining."
    used = await db_conn.fetchval(
        "SELECT COUNT(*) FROM mfa_backup_codes b JOIN users u ON u.user_id=b.user_id "
        "WHERE u.email=$1 AND b.used=TRUE", email,
    )
    assert used == 1

    # The same code cannot be used again.
    await client.post("/v1/auth/logout", headers=csrf_header(client))
    again = await login_user(client, email)
    reuse = await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": again.json()["temp_token"], "totp_code": codes[0]},
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"] == "INVALID_MFA_CODE"


async def test_mfa_disable(client, redis_conn, db_conn):
    email = "mfa-off@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)
    secret, _ = await enable_mfa(client)

    resp = await client.post(
        "/v1/auth/mfa/disable",
        json={"password": STRONG_PASSWORD, "totp_code": totp_now(secret)},
        headers=csrf_header(client),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "MFA disabled."

    row = await db_conn.fetchrow(
        "SELECT mfa_enabled, mfa_secret_enc FROM users WHERE email = $1", email
    )
    assert row["mfa_enabled"] is False and row["mfa_secret_enc"] is None
    left = await db_conn.fetchval(
        "SELECT COUNT(*) FROM mfa_backup_codes b JOIN users u ON u.user_id=b.user_id "
        "WHERE u.email=$1", email,
    )
    assert left == 0
    # All sessions rotated away (§1D step 6).
    sessions = await db_conn.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id "
        "WHERE u.email=$1", email,
    )
    assert sessions == 0
    # Change was logged with the strong verification method.
    logged = await db_conn.fetchval(
        "SELECT COUNT(*) FROM profile_change_log p JOIN users u ON u.user_id=p.user_id "
        "WHERE u.email=$1 AND p.field_changed='mfa_status' AND p.verified_via='password+totp'",
        email,
    )
    assert logged == 1


async def test_mfa_setup_rejected_when_already_enabled(client, redis_conn):
    email = "mfa-twice@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)
    await enable_mfa(client)

    resp = await client.post("/v1/auth/mfa/setup", headers=csrf_header(client))
    assert resp.status_code == 400
    assert resp.json()["error"] == "MFA_ALREADY_ENABLED"


async def test_change_password_requires_totp_when_mfa_on(client, redis_conn):
    email = "mfa-chpw@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)
    secret, _ = await enable_mfa(client)

    new_password = "Quartz#Lantern4!willow"
    # Missing TOTP -> 400.
    missing = await client.post(
        "/v1/auth/change-password",
        json={"current_password": STRONG_PASSWORD, "new_password": new_password},
        headers=csrf_header(client),
    )
    assert missing.status_code == 400
    assert missing.json()["error"] == "TOTP_REQUIRED"

    # Wrong TOTP -> 401.
    bad = await client.post(
        "/v1/auth/change-password",
        json={
            "current_password": STRONG_PASSWORD,
            "new_password": new_password,
            "totp_code": wrong_totp(secret),
        },
        headers=csrf_header(client),
    )
    assert bad.status_code == 401
    assert bad.json()["error"] == "INVALID_MFA_CODE"

    # Correct TOTP -> password changes; MFA login with the new password works.
    ok = await client.post(
        "/v1/auth/change-password",
        json={
            "current_password": STRONG_PASSWORD,
            "new_password": new_password,
            "totp_code": totp_now(secret),
        },
        headers=csrf_header(client),
    )
    assert ok.status_code == 200
    done = await login_with_mfa(client, email, secret, password=new_password)
    assert done.status_code == 200
