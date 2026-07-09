"""Google OAuth flow tests (§1F) — cases A-D + MFA interaction.

No test ever contacts Google: the code->profile exchange is monkeypatched at
``backend.auth.oauth_handler.exchange_code`` (the routes resolve it via module
attribute at call time, which is exactly why it's structured that way). The
conftest force-clears GOOGLE_OAUTH_* env vars, so real credentials in .env can
never leak into the suite; the ``oauth_client`` fixture injects fake ones.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pyotp
import pytest
import pytest_asyncio

from .helpers import STRONG_PASSWORD, register_and_verify, totp_now

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def oauth_client(monkeypatch, app):
    """Client whose app sees fake Google credentials (read at call time)."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from backend.config import get_settings

    get_settings.cache_clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac
    get_settings.cache_clear()  # next app fixture re-reads a clean env


def _mock_exchange(monkeypatch, *, sub: str, email: str, name: str = "OAuth User",
                   picture: str | None = None):
    from backend.auth.oauth_handler import GoogleProfile

    async def _fake(code: str, redirect_uri: str) -> GoogleProfile:
        assert code, "callback must pass the code through"
        return GoogleProfile(sub=sub, email=email, name=name, picture=picture)

    monkeypatch.setattr("backend.auth.oauth_handler.exchange_code", _fake)


async def _start_flow(client: httpx.AsyncClient) -> str:
    """Hit /google/login and return the state Google would echo back."""
    resp = await client.get("/v1/auth/google/login")
    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    assert location.startswith("https://accounts.google.com/")
    qs = parse_qs(urlparse(location).query)
    assert qs["client_id"] == ["test-client-id"]
    assert "openid email profile" in qs["scope"][0]
    return qs["state"][0]


async def test_oauth_unconfigured_returns_503(client):
    # Plain client: conftest cleared the GOOGLE_OAUTH_* env vars.
    resp = await client.get("/v1/auth/google/login")
    assert resp.status_code == 503
    assert resp.json()["error"] == "OAUTH_NOT_CONFIGURED"
    assert resp.json()["message"] == "Google login not configured"


async def test_oauth_case_a_new_user_auto_registered(oauth_client, monkeypatch, db_conn):
    email = "oauth-new@example.com"
    _mock_exchange(monkeypatch, sub="google-sub-A", email=email,
                   picture="https://lh3.example/pic.jpg")
    state = await _start_flow(oauth_client)

    resp = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == email
    assert oauth_client.cookies.get("access_token")  # session issued

    row = await db_conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
    assert row["oauth_provider"] == "google"
    assert row["oauth_id"] == "google-sub-A"
    assert row["email_verified"] is True and row["is_active"] is True
    assert row["password_hash"] is None  # OAuth-only user (§1F case A)
    assert row["profile_picture"] == "https://lh3.example/pic.jpg"

    me = await oauth_client.get("/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == email


async def test_oauth_case_b_links_existing_password_user(
    oauth_client, monkeypatch, redis_conn, db_conn
):
    email = "oauth-link@example.com"
    await register_and_verify(oauth_client, redis_conn, email)  # password user

    _mock_exchange(monkeypatch, sub="google-sub-B", email=email)
    state = await _start_flow(oauth_client)
    resp = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == email

    row = await db_conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
    assert row["oauth_id"] == "google-sub-B"          # linked silently (case B)
    assert row["oauth_provider"] == "google"
    assert row["password_hash"] is not None           # local password kept


async def test_oauth_case_c_returning_user(oauth_client, monkeypatch, db_conn):
    email = "oauth-return@example.com"
    _mock_exchange(monkeypatch, sub="google-sub-C", email=email)

    # First visit registers (case A)...
    state = await _start_flow(oauth_client)
    first = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert first.status_code == 200

    # ...second visit is a plain returning login (case C) — still one user row.
    state2 = await _start_flow(oauth_client)
    second = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state2}"
    )
    assert second.status_code == 200
    assert second.json()["user"]["email"] == email
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE email = $1", email
    ) == 1


async def test_oauth_case_d_soft_deleted_403(oauth_client, monkeypatch, db_conn):
    email = "oauth-deleted@example.com"
    await db_conn.execute(
        """
        INSERT INTO users (email, name, is_active, email_verified, deleted_at)
        VALUES ($1, 'Gone', TRUE, TRUE, NOW())
        """,
        email,
    )
    _mock_exchange(monkeypatch, sub="google-sub-D", email=email)
    state = await _start_flow(oauth_client)

    resp = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "ACCOUNT_DELETED"
    assert body["recovery_link"] == "/auth/cancel-deletion"


async def test_oauth_state_invalid_or_reused_403(oauth_client, monkeypatch, db_conn):
    email = "oauth-state@example.com"
    _mock_exchange(monkeypatch, sub="google-sub-S", email=email)

    # Unknown state -> 403, no user created.
    bogus = await oauth_client.get(
        "/v1/auth/google/callback?code=fake-code&state=not-a-real-state"
    )
    assert bogus.status_code == 403
    assert bogus.json()["error"] == "OAUTH_STATE_INVALID"
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE email = $1", email
    ) == 0

    # A used state cannot be replayed (single-use in Redis).
    state = await _start_flow(oauth_client)
    ok = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert ok.status_code == 200
    replay = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert replay.status_code == 403
    assert replay.json()["error"] == "OAUTH_STATE_INVALID"


async def test_oauth_mfa_interaction_requires_totp(oauth_client, monkeypatch, db_conn):
    """§1F: MFA enabled = TOTP required regardless of login method."""
    from backend.auth.mfa_handler import encrypt_totp_secret
    from backend.auth.password import hash_password

    email = "oauth-mfa@example.com"
    secret = pyotp.random_base32()
    await db_conn.execute(
        """
        INSERT INTO users (email, name, password_hash,
                           is_active, email_verified, mfa_enabled, mfa_secret_enc)
        VALUES ($1, 'MFA User', $2, TRUE, TRUE, TRUE, $3)
        """,
        email,
        hash_password(STRONG_PASSWORD),
        encrypt_totp_secret(secret),
    )
    _mock_exchange(monkeypatch, sub="google-sub-M", email=email)
    state = await _start_flow(oauth_client)

    resp = await oauth_client.get(
        f"/v1/auth/google/callback?code=fake-code&state={state}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("mfa_required") is True and body.get("temp_token")
    assert not oauth_client.cookies.get("access_token")  # no session yet

    # The standard MFA second step completes the OAuth login.
    done = await oauth_client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": body["temp_token"], "totp_code": totp_now(secret)},
    )
    assert done.status_code == 200, done.text
    assert done.json()["user"]["email"] == email
    assert oauth_client.cookies.get("access_token")
