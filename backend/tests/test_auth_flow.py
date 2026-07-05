"""End-to-end auth flow tests (Milestone 1 required coverage)."""
from __future__ import annotations

import pytest

from .helpers import (
    STRONG_PASSWORD,
    csrf_header,
    login_user,
    register_and_verify,
    register_user,
    verify_user_via_redis,
)

pytestmark = pytest.mark.asyncio


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "up"
    assert body["redis"] == "up"


async def test_full_register_verify_login_refresh_logout(client, redis_conn, db_conn):
    email = "flow@example.com"

    # 1. Register -> 201, unverified/inactive, verify token in Redis.
    resp = await register_user(client, email)
    assert resp.status_code == 201, resp.text
    assert "verify" in resp.json()["message"].lower()

    row = await db_conn.fetchrow("SELECT is_active, email_verified FROM users WHERE email=$1", email)
    assert row["is_active"] is False and row["email_verified"] is False

    # 2. Verify email -> active + verified, token consumed.
    vr = await verify_user_via_redis(client, redis_conn, email)
    assert vr.status_code == 200
    assert vr.json()["verified"] is True
    row = await db_conn.fetchrow("SELECT is_active, email_verified FROM users WHERE email=$1", email)
    assert row["is_active"] is True and row["email_verified"] is True
    assert await redis_conn.keys("email_verify:*") == []

    # 3. Login -> 200, sets access/refresh/csrf cookies.
    lr = await login_user(client, email)
    assert lr.status_code == 200, lr.text
    assert lr.json()["user"]["email"] == email
    assert lr.json()["user"]["mfa_enabled"] is False
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")
    assert client.cookies.get("csrf_token")

    # A refresh_tokens row exists for the user.
    n = await db_conn.fetchval("SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id WHERE u.email=$1", email)
    assert n == 1

    # 4. /me works with the access cookie.
    me = await client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    # 5. Refresh rotates tokens -> still exactly one refresh row.
    rr = await client.post("/v1/auth/refresh")
    assert rr.status_code == 200 and rr.json()["refreshed"] is True
    n = await db_conn.fetchval("SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id WHERE u.email=$1", email)
    assert n == 1

    # 6. Logout (CSRF-protected) clears cookies + refresh row.
    out = await client.post("/v1/auth/logout", headers=csrf_header(client))
    assert out.status_code == 200
    n = await db_conn.fetchval("SELECT COUNT(*) FROM refresh_tokens r JOIN users u ON u.user_id=r.user_id WHERE u.email=$1", email)
    assert n == 0


async def test_duplicate_email_returns_409(client, redis_conn):
    email = "dup@example.com"
    await register_and_verify(client, redis_conn, email)
    # Second registration of a verified account -> 409.
    resp = await register_user(client, email)
    assert resp.status_code == 409
    assert resp.json()["error"] == "EMAIL_EXISTS"


async def test_weak_password_rejected_with_suggestions(client):
    resp = await register_user(client, "weak@example.com", password="password123")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "WEAK_PASSWORD"
    assert "score" in body["detail"]
    assert isinstance(body["detail"]["suggestions"], list)
    assert len(body["detail"]["suggestions"]) >= 1


async def test_login_before_verification_forbidden(client):
    email = "unverified@example.com"
    r = await register_user(client, email)
    assert r.status_code == 201
    # No verification step -> login must be 403.
    lr = await login_user(client, email)
    assert lr.status_code == 403
    assert lr.json()["error"] == "EMAIL_NOT_VERIFIED"


async def test_login_wrong_password_is_401_generic(client, redis_conn):
    email = "creds@example.com"
    await register_and_verify(client, redis_conn, email)
    lr = await login_user(client, email, password="Wr0ng&Password!nope")
    assert lr.status_code == 401
    assert lr.json()["error"] == "INVALID_CREDENTIALS"
    # Same generic error for a non-existent email (no enumeration).
    lr2 = await login_user(client, "ghost@example.com", password=STRONG_PASSWORD)
    assert lr2.status_code == 401
    assert lr2.json()["error"] == "INVALID_CREDENTIALS"


async def test_refresh_rotation_invalidates_old_refresh_token(client, redis_conn):
    email = "rotate@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)

    old_refresh = client.cookies.get("refresh_token")
    old_access = client.cookies.get("access_token")
    assert old_refresh

    rr = await client.post("/v1/auth/refresh")
    assert rr.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the OLD refresh token must fail (blacklisted + row deleted).
    replay = await client.post(
        "/v1/auth/refresh", cookies={"refresh_token": old_refresh}
    )
    assert replay.status_code == 401

    # The OLD access token must also be rejected now (dual blacklist, Amdt 10).
    me = await client.get("/v1/auth/me", cookies={"access_token": old_access})
    assert me.status_code == 401
    assert me.json()["error"] == "TOKEN_REVOKED"
