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


# --------------------------------------------------------------------------- #
# MFA helpers (Milestone 2)
# --------------------------------------------------------------------------- #
def totp_now(secret: str) -> str:
    import pyotp

    return pyotp.TOTP(secret).now()


def wrong_totp(secret: str) -> str:
    """A 6-digit code guaranteed NOT to verify within the ±1 window."""
    import time

    import pyotp

    totp = pyotp.TOTP(secret)
    now = time.time()
    valid = {totp.at(now - 30), totp.at(now), totp.at(now + 30)}
    for candidate in ("000000", "123456", "999999", "111111", "222222"):
        if candidate not in valid:
            return candidate
    raise AssertionError("could not find an invalid TOTP candidate")


async def enable_mfa(client: httpx.AsyncClient) -> tuple[str, list[str]]:
    """Run setup -> verify-setup for the logged-in client.

    Returns (totp_secret, backup_codes). Requires an authenticated session
    (login already done) — both endpoints are CSRF-protected.
    """
    setup = await client.post("/v1/auth/mfa/setup", headers=csrf_header(client))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    assert setup.json()["qr_code_url"].startswith("otpauth://")

    verify = await client.post(
        "/v1/auth/mfa/verify-setup",
        json={"totp_code": totp_now(secret)},
        headers=csrf_header(client),
    )
    assert verify.status_code == 200, verify.text
    codes = verify.json()["backup_codes"]
    assert len(codes) == 8
    return secret, codes


async def login_with_mfa(
    client: httpx.AsyncClient, email: str, secret: str,
    password: str = STRONG_PASSWORD,
) -> httpx.Response:
    """Full two-step login for an MFA-enabled account."""
    first = await client.post(
        "/v1/auth/login", json={"email": email, "password": password}
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body.get("mfa_required") is True, body
    return await client.post(
        "/v1/auth/login/mfa",
        json={"temp_token": body["temp_token"], "totp_code": totp_now(secret)},
    )
