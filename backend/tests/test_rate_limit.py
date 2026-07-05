"""Rate-limit test (§3H) — a rate-limited endpoint returns 429.

Rate limiting is disabled globally for the suite (RATE_LIMIT_ENABLED=false) so
the other tests can loop freely. This test rebuilds the app with limiting ON and
hammers /v1/auth/login (5/minute per IP) until it trips 429.
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
