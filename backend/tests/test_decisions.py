"""Decision submission, history and result endpoints (§3F).

Note on background tasks: Starlette runs a ``BackgroundTasks`` set inside the
same ASGI call as the response, and httpx's ASGITransport awaits that call —
so by the time ``await client.post("/v1/decisions/analyze")`` returns here, the
pipeline has already finished. That is a property of the in-process test
transport, not of production (where the client sees the 202 immediately).
"""
from __future__ import annotations

import pytest

from .helpers import csrf_header, login_user, register_and_verify

pytestmark = pytest.mark.asyncio

DECISION_BODY = {
    "symbol": "HDFCBANK",
    "exchange": "NSE",
    "holding_quantity": 100,
    "avg_buy_price": 1600.0,
    "current_price": 1300.0,
    "unrealized_pnl_pct": -0.1875,
    "decision_intent": "hold",
    "user_reasoning": "It will bounce back.",
    "holding_period_days": 400,
    "market_trend": "bear",
}


async def _authed(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    resp = await login_user(client, email)
    assert resp.status_code == 200, resp.text


async def submit(client, **overrides):
    body = {**DECISION_BODY, **overrides}
    return await client.post(
        "/v1/decisions/analyze", json=body, headers=csrf_header(client)
    )


# --------------------------------------------------------------------------- #
# Submission
# --------------------------------------------------------------------------- #
async def test_analyze_returns_202_with_stream_url(client, redis_conn):
    await _authed(client, redis_conn, "dec-submit@example.com")

    resp = await submit(client)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["stream_url"] == f"/v1/decisions/{body['decision_id']}/stream"


async def test_analyze_requires_authentication(client):
    """401 once CSRF is satisfied — the middleware would otherwise answer first.

    CSRFMiddleware runs outside the auth dependency, so an anonymous POST with
    no token pair is a 403 before ``get_current_user`` is ever reached. Sending
    a self-consistent (but session-less) double-submit pair gets past it and
    proves the endpoint itself refuses anonymous callers.
    """
    resp = await client.post(
        "/v1/decisions/analyze",
        json=DECISION_BODY,
        headers={
            "Cookie": "csrf_token=anonymous-pair",
            "X-CSRF-Token": "anonymous-pair",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "NOT_AUTHENTICATED"


async def test_analyze_requires_csrf_header(client, redis_conn):
    await _authed(client, redis_conn, "dec-csrf@example.com")
    resp = await client.post("/v1/decisions/analyze", json=DECISION_BODY)
    assert resp.status_code == 403
    assert resp.json()["error"] == "CSRF_FAILED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision_intent", "panic"),
        ("exchange", "NASDAQ"),
        ("holding_quantity", 0),
        ("current_price", -5),
        ("market_trend", "crab"),
    ],
)
async def test_analyze_rejects_values_the_db_would_reject(
    client, redis_conn, field, value
):
    """Schema validators mirror the 0003 CHECK constraints -> 422, never a 500."""
    await _authed(client, redis_conn, f"dec-invalid-{field}@example.com")
    resp = await submit(client, **{field: value})
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"] == "VALIDATION_ERROR"


async def test_analyze_normalises_case(client, redis_conn, db_conn):
    await _authed(client, redis_conn, "dec-normalise@example.com")
    resp = await submit(client, exchange="nse", decision_intent="SELL")
    assert resp.status_code == 202, resp.text

    row = await db_conn.fetchrow(
        "SELECT exchange, decision_intent FROM decisions WHERE decision_id = $1",
        resp.json()["decision_id"],
    )
    assert row["exchange"] == "NSE"
    assert row["decision_intent"] == "sell"


async def test_holding_period_sets_tax_category(client, redis_conn, db_conn):
    await _authed(client, redis_conn, "dec-tax@example.com")

    long_term = await submit(client, holding_period_days=400)
    short_term = await submit(client, holding_period_days=90)
    unknown = await submit(client, holding_period_days=None)

    async def category(resp):
        return await db_conn.fetchval(
            "SELECT tax_category FROM decisions WHERE decision_id = $1",
            resp.json()["decision_id"],
        )

    assert await category(long_term) == "LTCG"
    assert await category(short_term) == "STCG"
    assert await category(unknown) is None


# --------------------------------------------------------------------------- #
# History
# --------------------------------------------------------------------------- #
async def test_my_decisions_paginates(client, redis_conn):
    await _authed(client, redis_conn, "dec-history@example.com")
    for symbol in ("AAA", "BBB", "CCC"):
        assert (await submit(client, symbol=symbol)).status_code == 202

    first = await client.get("/v1/decisions/my?limit=2")
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2

    second = await client.get("/v1/decisions/my?limit=2&offset=2")
    assert len(second.json()["items"]) == 1


async def test_my_decisions_are_isolated_per_user(client, redis_conn):
    await _authed(client, redis_conn, "dec-owner@example.com")
    assert (await submit(client, symbol="MINE")).status_code == 202

    # Second user in the same client: log out, register + log in as someone else.
    await client.post("/v1/auth/logout", headers=csrf_header(client))
    await _authed(client, redis_conn, "dec-other@example.com")

    resp = await client.get("/v1/decisions/my")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# --------------------------------------------------------------------------- #
# Result + ownership
# --------------------------------------------------------------------------- #
async def test_result_returns_completed_decision(client, redis_conn):
    await _authed(client, redis_conn, "dec-result@example.com")
    decision_id = (await submit(client)).json()["decision_id"]

    resp = await client.get(f"/v1/decisions/{decision_id}/result")
    assert resp.status_code == 200, resp.text
    decision = resp.json()["decision"]
    assert decision["status"] == "complete"
    assert decision["bias_detected"] is not None
    assert decision["recommendation"] in ("HOLD", "SELL", "BUY_MORE")
    # The response must report exactly the steps still running placeholders.
    # Derived from the registry rather than hard-coded, because Phase 5 makes
    # steps real one at a time.
    from backend.core.events import STEP_ORDER
    from backend.core.steps import is_stubbed

    assert set(resp.json()["stubbed_steps"]) == {s for s in STEP_ORDER if is_stubbed(s)}


async def test_result_of_another_users_decision_is_404(client, redis_conn):
    await _authed(client, redis_conn, "dec-victim@example.com")
    decision_id = (await submit(client)).json()["decision_id"]

    await client.post("/v1/auth/logout", headers=csrf_header(client))
    await _authed(client, redis_conn, "dec-attacker@example.com")

    resp = await client.get(f"/v1/decisions/{decision_id}/result")
    assert resp.status_code == 404
    assert resp.json()["error"] == "DECISION_NOT_FOUND"


async def test_malformed_decision_id_is_404_not_500(client, redis_conn):
    await _authed(client, redis_conn, "dec-malformed@example.com")
    resp = await client.get("/v1/decisions/not-a-uuid/result")
    assert resp.status_code == 404
