"""SSE progress stream (§3F) — replay, live delivery, ownership, termination.

The replay-then-subscribe design is the thing under test here: §3F's sketch
subscribes only, which drops every event published between the 202 and the
client's connect. ``test_stream_replays_events_published_before_connect``
pins that behaviour.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.core.events import publish_event

from .helpers import csrf_header, login_user, register_and_verify

pytestmark = pytest.mark.asyncio

DECISION_BODY = {
    "symbol": "INFY",
    "exchange": "NSE",
    "holding_quantity": 50,
    "avg_buy_price": 1500.0,
    "current_price": 1200.0,
    "unrealized_pnl_pct": -0.20,
    "decision_intent": "hold",
    "market_trend": "bear",
}


async def _authed(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    assert (await login_user(client, email)).status_code == 200


async def _read_stream(client, decision_id: str, timeout: float = 20.0) -> list[dict]:
    """Consume the stream to its terminal event and return the parsed events."""
    collected: list[dict] = []

    async def consume():
        async with client.stream(
            "GET", f"/v1/decisions/{decision_id}/stream"
        ) as response:
            assert response.status_code == 200, response
            assert response.headers["content-type"].startswith("text/event-stream")
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    if not frame.startswith("data: "):
                        continue  # heartbeat
                    collected.append(json.loads(frame[len("data: "):]))
                if collected and collected[-1]["step"] in ("complete", "failed", "timeout"):
                    return

    await asyncio.wait_for(consume(), timeout=timeout)
    return collected


# --------------------------------------------------------------------------- #
# Replay
# --------------------------------------------------------------------------- #
async def test_stream_replays_events_published_before_connect(client, redis_conn):
    """The whole run happens before the client connects; it must still see it.

    Under the ASGI test transport the background pipeline finishes inside the
    POST, so this is exactly the race §3F's subscribe-only sketch would lose.
    """
    await _authed(client, redis_conn, "sse-replay@example.com")
    submit = await client.post(
        "/v1/decisions/analyze", json=DECISION_BODY, headers=csrf_header(client)
    )
    assert submit.status_code == 202
    decision_id = submit.json()["decision_id"]

    events = await _read_stream(client, decision_id)

    steps = [(e["step"], e["status"]) for e in events]
    assert ("bias_detection", "running") in steps
    assert ("audit", "done") in steps
    assert steps[-1] == ("complete", "done")


async def test_stream_closes_on_terminal_event(client, redis_conn):
    """The generator returns after `complete` — no events follow it."""
    await _authed(client, redis_conn, "sse-terminal@example.com")
    decision_id = (
        await client.post(
            "/v1/decisions/analyze", json=DECISION_BODY, headers=csrf_header(client)
        )
    ).json()["decision_id"]

    events = await _read_stream(client, decision_id)
    assert [e["step"] for e in events].count("complete") == 1
    assert events[-1]["step"] == "complete"


async def test_replayed_events_are_not_duplicated_by_the_subscription(
    client, redis_conn
):
    """Backlog + live subscription overlap; `seq` de-duplicates the overlap."""
    await _authed(client, redis_conn, "sse-dedupe@example.com")
    decision_id = (
        await client.post(
            "/v1/decisions/analyze", json=DECISION_BODY, headers=csrf_header(client)
        )
    ).json()["decision_id"]

    events = await _read_stream(client, decision_id)
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


# --------------------------------------------------------------------------- #
# Live delivery
# --------------------------------------------------------------------------- #
async def test_stream_delivers_events_published_while_connected(app, client, redis_conn):
    """Connect on a pending decision, then publish — the event must arrive live."""
    await _authed(client, redis_conn, "sse-live@example.com")

    # Seed a decision that no pipeline will touch, so the stream stays open.
    db = app.state.db
    user_id = await db.fetchval(
        "SELECT user_id FROM users WHERE email = $1", "sse-live@example.com"
    )
    async with db.rls_transaction(str(user_id)) as conn:
        decision_id = str(
            await conn.fetchval(
                """
                INSERT INTO decisions (user_id, status, symbol, holding_quantity,
                                       avg_buy_price, current_price,
                                       unrealized_pnl_pct, decision_intent)
                VALUES ($1, 'pending', 'TCS', 10, 3000, 3200, 0.0667, 'hold')
                RETURNING decision_id
                """,
                user_id,
            )
        )

    async def publish_later():
        # Give the stream a moment to subscribe and drain the (empty) backlog.
        await asyncio.sleep(0.3)
        await publish_event(
            app.state.redis, decision_id, {"step": "bias_detection", "status": "running"}
        )
        await publish_event(app.state.redis, decision_id, {"step": "complete", "status": "done"})

    publisher = asyncio.create_task(publish_later())
    try:
        events = await _read_stream(client, decision_id, timeout=15.0)
    finally:
        await publisher

    assert [(e["step"], e["status"]) for e in events] == [
        ("bias_detection", "running"),
        ("complete", "done"),
    ]


# --------------------------------------------------------------------------- #
# Ownership
# --------------------------------------------------------------------------- #
async def test_stream_requires_authentication(client, redis_conn):
    await _authed(client, redis_conn, "sse-authed@example.com")
    decision_id = (
        await client.post(
            "/v1/decisions/analyze", json=DECISION_BODY, headers=csrf_header(client)
        )
    ).json()["decision_id"]

    await client.post("/v1/auth/logout", headers=csrf_header(client))
    resp = await client.get(f"/v1/decisions/{decision_id}/stream")
    assert resp.status_code == 401


async def test_stream_of_another_users_decision_is_404(client, redis_conn):
    await _authed(client, redis_conn, "sse-victim@example.com")
    decision_id = (
        await client.post(
            "/v1/decisions/analyze", json=DECISION_BODY, headers=csrf_header(client)
        )
    ).json()["decision_id"]

    await client.post("/v1/auth/logout", headers=csrf_header(client))
    await _authed(client, redis_conn, "sse-attacker@example.com")

    resp = await client.get(f"/v1/decisions/{decision_id}/stream")
    assert resp.status_code == 404
    assert resp.json()["error"] == "DECISION_NOT_FOUND"


# --------------------------------------------------------------------------- #
# Timeout
# --------------------------------------------------------------------------- #
async def test_stream_times_out_instead_of_hanging_forever(
    app, client, redis_conn, monkeypatch
):
    """A stalled pipeline must end the stream with a `timeout` event (§3F)."""
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SSE_STREAM_TIMEOUT_SECONDS", 1)

    await _authed(client, redis_conn, "sse-timeout@example.com")
    db = app.state.db
    user_id = await db.fetchval(
        "SELECT user_id FROM users WHERE email = $1", "sse-timeout@example.com"
    )
    async with db.rls_transaction(str(user_id)) as conn:
        decision_id = str(
            await conn.fetchval(
                """
                INSERT INTO decisions (user_id, status, symbol, holding_quantity,
                                       avg_buy_price, current_price,
                                       unrealized_pnl_pct, decision_intent)
                VALUES ($1, 'processing', 'WIPRO', 10, 400, 380, -0.05, 'hold')
                RETURNING decision_id
                """,
                user_id,
            )
        )

    events = await _read_stream(client, decision_id, timeout=15.0)
    assert events[-1]["step"] == "timeout"
