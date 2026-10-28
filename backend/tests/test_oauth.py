"""Google OAuth flow tests (§1F, finished in Phase C1) — cases A-D, MFA,
cancelling at Google, unverified addresses, and keeping an account that is
scheduled for deletion.

Every callback outcome is a redirect to ``/auth/google#…`` in the web app; the
fragment carries the result, never a JSON page.

No test ever contacts Google: the code->profile exchange is monkeypatched at
``backend.auth.oauth_handler.exchange_code`` (the routes resolve it via module
attribute at call time, which is exactly why it's structured that way). The
conftest force-clears GOOGLE_OAUTH_* env vars, so real credentials in .env can
never leak into the suite; the ``oauth_client`` fixture injects fake ones.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

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
                   picture: str | None = None, email_verified: bool = True):
    from backend.auth.oauth_handler import GoogleProfile

    async def _fake(code: str, redirect_uri: str) -> GoogleProfile:
        assert code, "callback must pass the code through"
        return GoogleProfile(sub=sub, email=email, name=name, picture=picture,
                             email_verified=email_verified)

    monkeypatch.setattr("backend.auth.oauth_handler.exchange_code", _fake)


async def _start_flow(client: httpx.AsyncClient, **params) -> str:
    """Hit /google/login and return the state Google would echo back."""
    query = f"?{urlencode(params)}" if params else ""
    resp = await client.get(f"/v1/auth/google/login{query}")
    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    assert location.startswith("https://accounts.google.com/")
    qs = parse_qs(urlparse(location).query)
    assert qs["client_id"] == ["test-client-id"]
    # One fixed address to register with Google, through the app's proxy.
    from backend.config import get_settings

    assert qs["redirect_uri"] == [
        get_settings().FRONTEND_URL.rstrip("/") + "/v1/auth/google/callback"
    ]
    assert "openid email profile" in qs["scope"][0]
    return qs["state"][0]


def _outcome(resp: httpx.Response) -> dict[str, str]:
    """The callback's redirect back into the app, as {key: value}."""
    from backend.config import get_settings

    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    assert location.startswith(get_settings().FRONTEND_URL.rstrip("/") + "/auth/google#")
    target = urlparse(location)
    return {k: v[0] for k, v in parse_qs(target.fragment).items()}


async def _callback(client: httpx.AsyncClient, state: str, code: str = "fake-code"):
    return await client.get(f"/v1/auth/google/callback?code={code}&state={state}")


async def test_oauth_unconfigured_returns_to_app(client):
    # Plain client: conftest cleared the GOOGLE_OAUTH_* env vars.
    resp = await client.get("/v1/auth/google/login")
    assert _outcome(resp) == {"result": "error", "code": "OAUTH_NOT_CONFIGURED"}


async def test_oauth_case_a_new_user_auto_registered(oauth_client, monkeypatch, db_conn):
    email = "oauth-new@example.com"
    _mock_exchange(monkeypatch, sub="google-sub-A", email=email,
                   picture="https://lh3.example/pic.jpg")
    state = await _start_flow(oauth_client)

    resp = await _callback(oauth_client, state)
    assert _outcome(resp) == {"result": "ok", "new": "1", "next": "/app"}
    assert oauth_client.cookies.get("access_token")  # session issued

    row = await db_conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
    assert row["oauth_provider"] == "google"
    assert row["oauth_id"] == "google-sub-A"
    assert row["email_verified"] is True and row["is_active"] is True
    assert row["password_hash"] is None  # OAuth-only user (§1F case A)
    assert row["profile_picture"] == "https://lh3.example/pic.jpg"

    me = await oauth_client.get("/v1/auth/me")
    assert me.status_code == 200 and me.json()["email"] == email
    # No password yet, and Tier 1 still to fill in: the app asks for it.
    assert me.json()["has_password"] is False
    assert me.json()["needs_profile"] is True


async def test_oauth_case_b_links_existing_password_user(
    oauth_client, monkeypatch, redis_conn, db_conn
):
    email = "oauth-link@example.com"
    await register_and_verify(oauth_client, redis_conn, email)  # password user

    _mock_exchange(monkeypatch, sub="google-sub-B", email=email)
    state = await _start_flow(oauth_client)
    resp = await _callback(oauth_client, state)
    assert _outcome(resp) == {"result": "ok", "next": "/app"}  # not new

    row = await db_conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
    assert row["oauth_id"] == "google-sub-B"          # linked silently (case B)
    assert row["oauth_provider"] == "google"
    assert row["password_hash"] is not None           # local password kept


async def test_oauth_case_c_returning_user(oauth_client, monkeypatch, db_conn):
    email = "oauth-return@example.com"
    _mock_exchange(monkeypatch, sub="google-sub-C", email=email)

    # First visit registers (case A)...
    first = await _callback(oauth_client, await _start_flow(oauth_client))
    assert _outcome(first)["new"] == "1"

    # ...second visit is a plain returning login (case C) — still one user row.
    second = await _callback(oauth_client, await _start_flow(oauth_client))
    assert _outcome(second) == {"result": "ok", "next": "/app"}
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE email = $1", email
    ) == 1


async def test_oauth_case_d_scheduled_deletion_can_be_kept(
    oauth_client, monkeypatch, db_conn
):
    email = "oauth-deleted@example.com"
    await db_conn.execute(
        """
        INSERT INTO users (email, name, is_active, email_verified, deleted_at,
                           purge_after, oauth_provider, oauth_id)
        VALUES ($1, 'Gone', TRUE, TRUE, NOW(), NOW() + INTERVAL '30 days',
                'google', 'google-sub-D')
        """,
        email,
    )
    _mock_exchange(monkeypatch, sub="google-sub-D", email=email)
    state = await _start_flow(oauth_client, remember="true")

    out = _outcome(await _callback(oauth_client, state))
    assert out["result"] == "deleted" and out["purge"] and out["remember"] == "1"
    assert not oauth_client.cookies.get("access_token")  # no session yet

    # "Keep my account": Google proved who this is, so no password is asked.
    kept = await oauth_client.post(
        "/v1/auth/google/keep-account", json={"token": out["token"], "remember_me": True}
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["user"]["email"] == email
    assert oauth_client.cookies.get("access_token")
    assert await db_conn.fetchval(
        "SELECT deleted_at FROM users WHERE email = $1", email
    ) is None

    # The token is single-use.
    again = await oauth_client.post(
        "/v1/auth/google/keep-account", json={"token": out["token"]}
    )
    assert again.status_code == 403


async def test_oauth_keep_account_after_grace_period_is_final(
    oauth_client, monkeypatch, db_conn
):
    email = "oauth-final@example.com"
    await db_conn.execute(
        """
        INSERT INTO users (email, name, is_active, email_verified, deleted_at, purge_after)
        VALUES ($1, 'Late', TRUE, TRUE, NOW() - INTERVAL '31 days', NOW() - INTERVAL '1 day')
        """,
        email,
    )
    _mock_exchange(monkeypatch, sub="google-sub-F", email=email)
    out = _outcome(await _callback(oauth_client, await _start_flow(oauth_client)))
    assert out["result"] == "deleted"
    resp = await oauth_client.post("/v1/auth/google/keep-account", json={"token": out["token"]})
    assert resp.status_code == 410
    assert resp.json()["error"] == "DELETION_FINAL"


async def test_oauth_state_invalid_or_reused(oauth_client, monkeypatch, db_conn):
    email = "oauth-state@example.com"
    _mock_exchange(monkeypatch, sub="google-sub-S", email=email)

    # Unknown state -> back to the app with an error, no user created.
    bogus = await _callback(oauth_client, "not-a-real-state")
    assert _outcome(bogus) == {"result": "error", "code": "OAUTH_STATE_INVALID"}
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE email = $1", email
    ) == 0

    # A used state cannot be replayed (single-use in Redis).
    state = await _start_flow(oauth_client)
    ok = await _callback(oauth_client, state)
    assert _outcome(ok)["result"] == "ok"
    replay = await _callback(oauth_client, state)
    assert _outcome(replay) == {"result": "error", "code": "OAUTH_STATE_INVALID"}


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
    state = await _start_flow(oauth_client, next="/app/history")

    out = _outcome(await _callback(oauth_client, state))
    assert out["result"] == "mfa" and out["token"]
    assert out["next"] == "/app/history" and out["remember"] == "0"
    assert not oauth_client.cookies.get("access_token")  # no session yet

    # The standard MFA second step completes the OAuth login.
    done = await oauth_client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": out["token"], "totp_code": totp_now(secret)},
    )
    assert done.status_code == 200, done.text
    assert done.json()["user"]["email"] == email
    assert oauth_client.cookies.get("access_token")


async def test_oauth_cancelled_at_google(oauth_client, db_conn):
    """Backing out of Google's screen returns ?error=access_denied, no code."""
    state = await _start_flow(oauth_client)
    resp = await oauth_client.get(
        f"/v1/auth/google/callback?error=access_denied&state={state}"
    )
    assert _outcome(resp) == {"result": "error", "code": "OAUTH_CANCELLED"}
    assert not oauth_client.cookies.get("access_token")


async def test_oauth_unverified_google_email_cannot_link(
    oauth_client, monkeypatch, redis_conn, db_conn
):
    """An address Google hasn't verified must not take over a local account."""
    email = "oauth-unverified@example.com"
    await register_and_verify(oauth_client, redis_conn, email)
    _mock_exchange(monkeypatch, sub="google-sub-U", email=email, email_verified=False)

    resp = await _callback(oauth_client, await _start_flow(oauth_client))
    assert _outcome(resp) == {"result": "error", "code": "OAUTH_EMAIL_UNVERIFIED"}
    assert await db_conn.fetchval(
        "SELECT oauth_id FROM users WHERE email = $1", email
    ) is None


async def test_oauth_next_must_be_an_app_path(oauth_client, monkeypatch, db_conn):
    """``next`` can't send the browser to another site after sign-in."""
    _mock_exchange(monkeypatch, sub="google-sub-N", email="oauth-next@example.com")
    for bad in ("https://evil.example", "//evil.example", "/\\evil.example"):
        state = await _start_flow(oauth_client, next=bad)
        assert _outcome(await _callback(oauth_client, state))["next"] == "/app"
    state = await _start_flow(oauth_client, next="/app/portfolio")
    assert _outcome(await _callback(oauth_client, state))["next"] == "/app/portfolio"


async def test_oauth_remember_choice_sets_persistent_cookies(oauth_client, monkeypatch, db_conn):
    """Unticked = cookies that end with the browser; ticked = lasting cookies."""
    _mock_exchange(monkeypatch, sub="google-sub-R", email="oauth-remember@example.com")

    session_only = await _callback(oauth_client, await _start_flow(oauth_client))
    persistent = await _callback(oauth_client, await _start_flow(oauth_client, remember="true"))

    def access_cookie(resp: httpx.Response) -> str:
        return next(
            h for h in resp.headers.get_list("set-cookie") if h.startswith("access_token=")
        ).lower()

    assert "max-age" not in access_cookie(session_only)
    assert "max-age" in access_cookie(persistent)
