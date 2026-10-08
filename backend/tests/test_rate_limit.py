"""Rate-limit tests (§3H) — 429 on excess, and no 500 from the limiter itself.

Rate limiting is disabled globally for the suite (RATE_LIMIT_ENABLED=false) so
the other tests can loop freely. These rebuild the app with limiting ON.

The smoke test matters as much as the 429 one: with ``headers_enabled=True``
slowapi injects X-RateLimit-* headers by looking for a handler parameter named
``response``, and 500s if it is absent. Because the rest of the suite runs with
the limiter disabled, a limited endpoint missing that parameter passes every
other test and then fails on the first real production request. That is exactly
how /v1/auth/register and /v1/auth/forgot-password shipped broken in M1.
"""
from __future__ import annotations

import importlib

import httpx
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def rate_limited_client(monkeypatch):
    """A client whose app has rate limiting enabled.

    We flip the env var, clear the settings cache, and rebuild the limiter +
    rate_limiter module so the new @limiter.limit decorators pick up enabled=True,
    then build a fresh app. Everything is restored on teardown.
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

    from backend.config import get_settings

    get_settings.cache_clear()

    # Rebuild the rate_limiter module so `limiter` is enabled, then rebuild the
    # modules that captured the old limiter reference at import time.
    import backend.middleware.rate_limiter as rl

    importlib.reload(rl)
    import backend.auth.routes as routes

    importlib.reload(routes)
    import backend.api.v1 as v1

    importlib.reload(v1)
    import backend.main as main

    importlib.reload(main)

    application = main.create_app()
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as ac:
            yield ac

    # Restore default (disabled) state for subsequent tests.
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    importlib.reload(rl)
    importlib.reload(routes)
    importlib.reload(v1)
    importlib.reload(main)


async def test_login_rate_limit_returns_429(rate_limited_client):
    # /v1/auth/login is limited to 5/minute per IP. The 6th call should 429.
    saw_429 = False
    for _ in range(8):
        resp = await rate_limited_client.post(
            "/v1/auth/login",
            json={"email": "rl@example.com", "password": "whatever-not-real"},
        )
        if resp.status_code == 429:
            saw_429 = True
            break
        # before the limit trips, unknown creds yield 401
        assert resp.status_code in (401, 429)
    assert saw_429, "expected a 429 after exceeding the login rate limit"


async def test_every_limited_endpoint_declares_a_response_parameter():
    """Static guard for the whole class of bug, present or future.

    (``async`` only to match the module's ``pytestmark``; it awaits nothing.)

    slowapi records each decorated handler at import time (independently of
    ``enabled``), so every limited route can be checked without a live limiter.
    A limited handler with no ``response`` parameter 500s on every call in any
    environment where rate limiting is on — see this module's docstring.
    """
    import inspect

    from backend.main import create_app
    from backend.middleware.rate_limiter import limiter

    marked = getattr(limiter, "_Limiter__marked_for_limiting", None)
    assert marked, "slowapi no longer exposes __marked_for_limiting — update this test"

    app = create_app()
    offenders = []
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        if f"{endpoint.__module__}.{endpoint.__name__}" not in marked:
            continue
        params = inspect.signature(inspect.unwrap(endpoint)).parameters
        if "response" not in params:
            offenders.append(f"{route.path} ({endpoint.__name__})")

    assert not offenders, (
        "rate-limited endpoints missing a `response: Response` parameter "
        f"(they 500 whenever RATE_LIMIT_ENABLED=true): {offenders}"
    )


async def test_limited_endpoint_returns_normally_with_the_limiter_enabled(
    rate_limited_client,
):
    """End-to-end counterpart: register really works, and gets its headers.

    ``register`` is the one limited endpoint that returns 2xx without a prior
    session, and slowapi only injects headers on a normal return (a handler
    that raises skips the injection entirely). It is the case that was broken.
    """
    resp = await rate_limited_client.post(
        "/v1/auth/register",
        json={
            "email": "rl-smoke@example.com",
            "password": "Tr0ub4dour&3xplosion!parrot",
            "name": "RL Smoke",
        },
    )
    assert resp.status_code == 201, resp.text
    assert "x-ratelimit-limit" in resp.headers
