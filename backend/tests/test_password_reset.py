"""Forgot / reset / change password tests (§1G)."""
from __future__ import annotations

import pytest

from .helpers import (
    STRONG_PASSWORD,
    csrf_header,
    login_user,
    register_and_verify,
)

pytestmark = pytest.mark.asyncio


async def _reset_token(redis_conn) -> str:
    keys = await redis_conn.keys("pw_reset:*")
    assert keys, "expected a pw_reset token in Redis"
    return keys[0].split("pw_reset:", 1)[1]


async def test_forgot_password_always_200_and_creates_token(client, redis_conn):
    email = "reset@example.com"
    await register_and_verify(client, redis_conn, email)

    resp = await client.post("/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert "you'll receive a reset link" in resp.json()["message"].lower()
    assert await redis_conn.keys("pw_reset:*")


async def test_forgot_password_unknown_email_still_200_no_token(client, redis_conn):
    resp = await client.post("/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert await redis_conn.keys("pw_reset:*") == []


async def test_reset_password_updates_and_invalidates_sessions(client, redis_conn, db_conn):
    email = "reset2@example.com"
    await register_and_verify(client, redis_conn, email)

    # Establish a live session (a refresh row).
    await login_user(client, email)
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id WHERE u.email=$1",
        email,
    )
    assert n == 1

    # Request + perform reset with a new strong password.
    await client.post("/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token(redis_conn)
    new_password = "Zebra$Rainbow7!maple"
    resp = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": new_password}
    )
    assert resp.status_code == 200

    # All refresh tokens invalidated (§1G) and reset token consumed.
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id WHERE u.email=$1",
        email,
    )
    assert n == 0
    assert await redis_conn.keys("pw_reset:*") == []

    # profile_change_log recorded the change (RLS transaction path).
    logged = await db_conn.fetchval(
        "SELECT COUNT(*) FROM profile_change_log p JOIN users u ON u.user_id=p.user_id "
        "WHERE u.email=$1 AND p.field_changed='password' AND p.verified_via='email_token'",
        email,
    )
    assert logged == 1

    # Old password no longer works; new one does.
    old = await login_user(client, email, password=STRONG_PASSWORD)
    assert old.status_code == 401
    new = await login_user(client, email, password=new_password)
    assert new.status_code == 200


async def test_reset_password_invalid_token_is_400(client):
    resp = await client.post(
        "/v1/auth/reset-password",
        json={"token": "bogus", "new_password": "Zebra$Rainbow7!maple"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_TOKEN"


async def test_reset_password_weak_new_password_rejected(client, redis_conn):
    email = "resetweak@example.com"
    await register_and_verify(client, redis_conn, email)
    await client.post("/v1/auth/forgot-password", json={"email": email})
    token = await _reset_token(redis_conn)
    resp = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": "password"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "WEAK_PASSWORD"


async def test_change_password_success_rotates_sessions(client, redis_conn, db_conn):
    email = "change@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)

    new_password = "Kettle$Drum9!avocado"
    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": STRONG_PASSWORD, "new_password": new_password},
        headers=csrf_header(client),
    )
    assert resp.status_code == 200

    # Sessions rotated away.
    n = await db_conn.fetchval(
        "SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id WHERE u.email=$1",
        email,
    )
    assert n == 0

    # New password logs in.
    assert (await login_user(client, email, password=new_password)).status_code == 200
