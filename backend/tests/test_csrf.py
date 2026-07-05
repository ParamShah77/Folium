"""CSRF double-submit middleware tests (§1H)."""
from __future__ import annotations

import pytest

from .helpers import csrf_header, login_user, register_and_verify

pytestmark = pytest.mark.asyncio


async def test_csrf_missing_header_is_403(client, redis_conn):
    email = "csrf-missing@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)

    # change-password is CSRF-protected and NOT exempt; omit the header.
    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "irrelevant", "new_password": "Wh4tever&Strong!x"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "CSRF_FAILED"


async def test_csrf_mismatched_header_is_403(client, redis_conn):
    email = "csrf-mismatch@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)

    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "irrelevant", "new_password": "Wh4tever&Strong!x"},
        headers={"X-CSRF-Token": "not-the-cookie-value"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "CSRF_FAILED"


async def test_csrf_matching_header_passes_middleware(client, redis_conn):
    """With the correct header, CSRF passes and we reach the handler.

    We send a wrong current_password so the handler returns 401 — proving the
    request got PAST the CSRF middleware (403 would mean it was blocked).
    """
    email = "csrf-ok@example.com"
    await register_and_verify(client, redis_conn, email)
    await login_user(client, email)

    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "definitely-wrong", "new_password": "An0ther&Strong!p"},
        headers=csrf_header(client),
    )
    assert resp.status_code == 401  # reached handler, failed on credentials
    assert resp.json()["error"] == "INVALID_CREDENTIALS"


async def test_login_endpoint_is_csrf_exempt(client, redis_conn):
    """Pre-session endpoints (login) must not require a CSRF header."""
    email = "csrf-exempt@example.com"
    await register_and_verify(client, redis_conn, email)
    # Fresh client would have no csrf cookie; login must still succeed here.
    resp = await login_user(client, email)
    assert resp.status_code == 200
