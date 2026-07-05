"""Small helpers shared by the auth tests."""
from __future__ import annotations

from typing import Any

import httpx

STRONG_PASSWORD = "Tr0ub4dour&3xplosion!parrot"


def csrf_header(client: httpx.AsyncClient) -> dict[str, str]:
    """Build the X-CSRF-Token header from the client's csrf_token cookie.

    The double-submit pattern (§1H) requires the header to equal the cookie on
    CSRF-protected mutating requests (logout, change-password, ...).
    """
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


async def register_user(
    client: httpx.AsyncClient,
    email: str,
    password: str = STRONG_PASSWORD,
    name: str = "Test User",
    **profile: Any,
) -> httpx.Response:
    body = {"email": email, "password": password, "name": name, **profile}
    return await client.post("/v1/auth/register", json=body)


async def verify_user_via_redis(
    client: httpx.AsyncClient, redis_conn, email: str
) -> httpx.Response:
    """Pull the email_verify token from Redis and hit the verify endpoint."""
    keys = await redis_conn.keys("email_verify:*")
    assert keys, "expected an email_verify token in Redis after registration"
    # There may be several; find the one whose value maps to this user's id.
    # Simplest: registration created exactly one in a clean test — use it.
    token = keys[0].split("email_verify:", 1)[1]
    return await client.get(f"/v1/auth/verify-email?token={token}")


async def register_and_verify(
    client: httpx.AsyncClient,
    redis_conn,
    email: str,
    password: str = STRONG_PASSWORD,
    name: str = "Test User",
) -> None:
    resp = await register_user(client, email, password, name)
    assert resp.status_code == 201, resp.text
    vr = await verify_user_via_redis(client, redis_conn, email)
    assert vr.status_code == 200, vr.text


async def login_user(
    client: httpx.AsyncClient, email: str, password: str = STRONG_PASSWORD
) -> httpx.Response:
    return await client.post(
        "/v1/auth/login", json={"email": email, "password": password}
    )
