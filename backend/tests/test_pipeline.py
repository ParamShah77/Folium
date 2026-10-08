"""Analysis pipeline orchestration (§3F) — status, events, failure handling.

These drive ``run_analysis_pipeline`` directly with an explicitly seeded
``decisions`` row, so they test the orchestrator rather than the HTTP layer.
"""
from __future__ import annotations

import json

import pytest

from backend.core import pipeline as pipeline_module
from backend.core.events import STEP_ORDER, backlog_key, read_backlog
from backend.core.pipeline import run_analysis_pipeline
from backend.core import steps as steps_module

BIAS_LABELS = {"loss_aversion", "herd_behavior", "disposition_effect", "rational"}
from backend.core.steps import StepResult, resolve_step

pytestmark = pytest.mark.asyncio


async def _seed_user(db_conn, email: str = "pipeline@example.com") -> str:
    return str(
        await db_conn.fetchval(
            "INSERT INTO users (email, name, is_active, email_verified) "
            "VALUES ($1, 'Pipeline User', TRUE, TRUE) RETURNING user_id",
            email,
        )
    )


async def _seed_decision(db_conn, user_id: str, **overrides) -> str:
    values = {
        "symbol": "HDFCBANK",
        "holding_quantity": 100,
        "avg_buy_price": 1600,
        "current_price": 1300,
        "unrealized_pnl_pct": -0.1875,
        "decision_intent": "hold",
        "market_trend": "bear",
        **overrides,
    }
    return str(
        await db_conn.fetchval(
            """
            INSERT INTO decisions (
                user_id, status, symbol, holding_quantity, avg_buy_price,
                current_price, unrealized_pnl_pct, decision_intent, market_trend
            )
            VALUES ($1, 'pending', $2, $3, $4, $5, $6, $7, $8)
            RETURNING decision_id
            """,
            user_id,
            values["symbol"],
            values["holding_quantity"],
            values["avg_buy_price"],
            values["current_price"],
            values["unrealized_pnl_pct"],
            values["decision_intent"],
            values["market_trend"],
        )
    )


@pytest.fixture
async def wired(app, db_conn):
    """The app's live Database/RedisService plus a seeded user (lifespan is up)."""
    user_id = await _seed_user(db_conn)
    return app.state.db, app.state.redis, user_id


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
async def test_pipeline_completes_and_fills_every_step(wired, db_conn):
    db, redis, user_id = wired
    decision_id = await _seed_decision(db_conn, user_id)

    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    row = await db_conn.fetchrow(
        "SELECT * FROM decisions WHERE decision_id = $1", decision_id
    )
    assert row["status"] == "complete"
    assert row["pipeline_step"] is None
    assert row["completed_at"] is not None
    assert row["error_message"] is None

    # One column written by each of the five steps. Values are whatever the
    # real Phase 5 models produce, so assert the contract, not a number.
    assert row["bias_detected"] in BIAS_LABELS          # bias detection
    assert row["hold_median_20y"] is not None           # simulation
    explainer = json.loads(row["explainer_output"])     # explanation
    assert explainer["bias"]["bias_type"] == row["bias_detected"]
    assert explainer["headline"]
    # GAP 3 explanation in both languages (story is only the fallback).
    assert set(explainer["explanation"]) == {"en", "hi"}
    assert len(explainer["explanation"]["en"]["sections"]) == 6
    assert row["recommendation"] in ("HOLD", "SELL", "BUY_MORE")  # debate
    assert await db_conn.fetchval(
        "SELECT COUNT(*) FROM audit_logs WHERE decision_id = $1", decision_id
    ) == 1                                              # audit


async def test_pipeline_publishes_running_and_done_for_each_step(wired, db_conn):
    db, redis, user_id = wired
    decision_id = await _seed_decision(db_conn, user_id)

    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    events = [json.loads(raw) for raw in await read_backlog(redis, decision_id)]

    expected = []
    for step in STEP_ORDER:
        expected.append((step, "running"))
        expected.append((step, "done"))
    expected.append(("complete", "done"))
    assert [(e["step"], e["status"]) for e in events] == expected

    # seq is monotonic from 1 — this is what lets a stream de-duplicate replay
    # against live messages.
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert all(e["decision_id"] == decision_id for e in events)


async def test_step_events_carry_their_payload(wired, db_conn):
    db, redis, user_id = wired
    decision_id = await _seed_decision(db_conn, user_id)

    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)
    events = {
        (e["step"], e["status"]): e
        for e in (json.loads(raw) for raw in await read_backlog(redis, decision_id))
    }

    bias_done = events[("bias_detection", "done")]
    assert bias_done["bias"] in BIAS_LABELS
    assert 0.0 < bias_done["confidence"] <= 1.0
    sim_done = events[("simulation", "done")]
    assert sim_done["hold_median_20y"] > 0 and sim_done["sell_median_20y"] > 0
    assert 0.0 <= sim_done["prob_hold_better"] <= 1.0
    assert events[("explanation", "done")]["headline"]
    assert events[("debate", "done")]["verdict"] in ("HOLD", "SELL", "BUY_MORE")
    assert len(events[("audit", "done")]["chain_hash"]) == 64


async def test_audit_rows_form_a_chain_across_decisions(wired, db_conn):
    """Second decision's previous_hash is the first decision's chain_hash."""
    db, redis, user_id = wired
    first = await _seed_decision(db_conn, user_id)
    await run_analysis_pipeline(first, user_id, db=db, redis=redis)
    second = await _seed_decision(db_conn, user_id, symbol="TCS")
    await run_analysis_pipeline(second, user_id, db=db, redis=redis)

    rows = await db_conn.fetch(
        "SELECT decision_id, previous_hash, chain_hash FROM audit_logs "
        "WHERE user_id = $1 ORDER BY created_at, log_id",
        user_id,
    )
    assert len(rows) == 2
    # B1: the chain starts from the investor's genesis (GAP 4), not zeros.
    from backend.core.audit import genesis_hash

    created = await db_conn.fetchval("SELECT created_at FROM users WHERE user_id = $1", user_id)
    assert rows[0]["previous_hash"] == genesis_hash(str(user_id), created)
    assert rows[1]["previous_hash"] == rows[0]["chain_hash"]


# --------------------------------------------------------------------------- #
# Bias placeholder rules (these change wholesale when Phase 5A lands)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "intent,pnl,trend,expected",
    [
        ("hold", -0.20, "bear", "loss_aversion"),
        ("sell", 0.15, "bull", "disposition_effect"),
        ("buy_more", 0.02, "bull", "herd_behavior"),
        ("hold", 0.01, "sideways", "rational"),
    ],
)
async def test_stub_bias_rules(wired, db_conn, monkeypatch, intent, pnl, trend, expected):
    # Phase 5A registers the real classifier, which would otherwise win over the
    # placeholder. These cases document the *placeholder's* rules, so unregister
    # the real step for this test only; the classifier has its own coverage.
    monkeypatch.delitem(steps_module._REGISTRY, "bias_detection", raising=False)
    db, redis, user_id = wired
    decision_id = await _seed_decision(
        db_conn, user_id, decision_intent=intent, unrealized_pnl_pct=pnl,
        market_trend=trend,
    )

    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    assert await db_conn.fetchval(
        "SELECT bias_detected FROM decisions WHERE decision_id = $1", decision_id
    ) == expected


# --------------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------------- #
async def test_failing_step_marks_decision_failed_and_publishes(
    wired, db_conn, monkeypatch
):
    db, redis, user_id = wired
    decision_id = await _seed_decision(db_conn, user_id)

    async def boom(ctx):
        raise RuntimeError("simulator exploded")

    real_resolve = resolve_step

    def fake_resolve(name):
        return boom if name == "simulation" else real_resolve(name)

    monkeypatch.setattr(pipeline_module, "resolve_step", fake_resolve)
    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    row = await db_conn.fetchrow(
        "SELECT status, error_message, completed_at FROM decisions WHERE decision_id = $1",
        decision_id,
    )
    assert row["status"] == "failed"
    assert "simulator exploded" in row["error_message"]
    assert row["completed_at"] is None

    events = [json.loads(raw) for raw in await read_backlog(redis, decision_id)]
    assert events[-1]["step"] == "failed"
    assert "simulator exploded" in events[-1]["error"]
    # The first step still ran and was recorded before the failure.
    assert (events[0]["step"], events[0]["status"]) == ("bias_detection", "running")
    assert ("simulation", "done") not in [(e["step"], e["status"]) for e in events]


async def test_step_cannot_write_orchestrator_owned_columns(wired, db_conn, monkeypatch):
    """A step returning ``status`` must fail loudly, not silently corrupt state."""
    db, redis, user_id = wired
    decision_id = await _seed_decision(db_conn, user_id)

    async def sneaky(ctx):
        return StepResult(updates={"status": "complete"})

    monkeypatch.setattr(
        pipeline_module,
        "resolve_step",
        lambda name: sneaky if name == "bias_detection" else resolve_step(name),
    )
    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    row = await db_conn.fetchrow(
        "SELECT status, error_message FROM decisions WHERE decision_id = $1", decision_id
    )
    assert row["status"] == "failed"
    assert "orchestrator-owned" in row["error_message"]


async def test_missing_decision_fails_without_raising(wired):
    """A deleted decision must not leave an unhandled exception in the task."""
    db, redis, user_id = wired
    ghost = "00000000-0000-0000-0000-000000000000"

    await run_analysis_pipeline(ghost, user_id, db=db, redis=redis)

    events = [json.loads(raw) for raw in await read_backlog(redis, ghost)]
    assert events[-1]["step"] == "failed"


async def test_backlog_expires(wired, db_conn):
    """The backlog carries a TTL so completed runs don't accumulate in Redis."""
    db, redis, user_id = wired
    decision_id = await _seed_decision(db_conn, user_id)
    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    ttl = await redis.client.ttl(backlog_key(decision_id))
    assert 0 < ttl <= 3600
