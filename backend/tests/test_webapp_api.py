"""Endpoints added for the web app: config, dev mailbox, market, stats, the
decoded result payload, and the extended profile update.

Market data is disabled for the suite (conftest), so these tests also pin the
"market unavailable" path — the one a demo hits when Yahoo Finance is down.
"""
from __future__ import annotations

import pytest

from .helpers import csrf_header, login_user, register_and_verify
from .test_decisions import DECISION_BODY, submit

pytestmark = pytest.mark.asyncio


async def _authed(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    resp = await login_user(client, email)
    assert resp.status_code == 200, resp.text


# --------------------------------------------------------------------------- #
# Config + development mailbox
# --------------------------------------------------------------------------- #
async def test_config_reports_sign_in_options(client):
    resp = await client.get("/v1/meta/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["google_oauth"] is False       # conftest blanks the OAuth ids
    assert body["dev_mailbox"] is True         # development + no Resend key
    assert body["environment"] == "development"


async def test_dev_mailbox_captures_the_verification_link(client, redis_conn):
    await client.post(
        "/v1/auth/register",
        json={"email": "mailbox@example.com", "password": "Correct-Horse-Battery-9", "name": "Mailbox"},
    )
    resp = await client.get("/v1/dev/mailbox")
    assert resp.status_code == 200
    mine = [m for m in resp.json()["messages"] if m["to"] == "mailbox@example.com"]
    assert mine, "registration email should be in the dev mailbox"
    assert "/auth/verify-email?token=" in mine[0]["link"]


# --------------------------------------------------------------------------- #
# Market
# --------------------------------------------------------------------------- #
async def test_market_endpoints_require_a_session(client):
    assert (await client.get("/v1/market/ribbon")).status_code == 401
    assert (await client.get("/v1/market/context")).status_code == 401


async def test_market_degrades_to_unavailable(client, redis_conn):
    await _authed(client, redis_conn, "market@example.com")
    ribbon = (await client.get("/v1/market/ribbon")).json()
    assert ribbon == {"data_source": "unavailable", "indices": []}
    ctx = (await client.get("/v1/market/context")).json()
    assert ctx["market_data_source"] == "unavailable"
    assert ctx["nifty_1m_return"] is None


async def test_analyze_stores_market_source_and_keeps_stated_trend(client, redis_conn, db_conn):
    await _authed(client, redis_conn, "trend@example.com")
    decision_id = (await submit(client, market_trend="bear")).json()["decision_id"]
    row = await db_conn.fetchrow(
        "SELECT market_trend, market_data_source, nifty_1m_return FROM decisions WHERE decision_id = $1",
        decision_id,
    )
    assert row["market_trend"] == "bear"
    assert row["market_data_source"] == "unavailable"
    assert row["nifty_1m_return"] is None


# --------------------------------------------------------------------------- #
# Result payload + stats
# --------------------------------------------------------------------------- #
async def test_result_returns_decoded_real_outputs(client, redis_conn):
    await _authed(client, redis_conn, "result-real@example.com")
    decision_id = (await submit(client)).json()["decision_id"]
    body = (await client.get(f"/v1/decisions/{decision_id}/result")).json()
    d = body["decision"]

    assert d["status"] == "complete", d.get("error_message")
    # JSONB arrives as objects, not JSON-in-a-string.
    assert isinstance(d["explainer_output"], dict)
    assert isinstance(d["simulation_curves"], dict)
    assert isinstance(d["debate_transcript"], dict)

    curves = d["simulation_curves"]
    assert curves["years"][0] == 0 and curves["years"][-1] == 20
    assert len(curves["hold_p50"]) == 21
    # Year 0 is today's position: invested x (1 + unrealised gain/loss).
    expected_start = DECISION_BODY["holding_quantity"] * DECISION_BODY["avg_buy_price"] * (
        1 + DECISION_BODY["unrealized_pnl_pct"]
    )
    assert curves["hold_p50"][0] == pytest.approx(expected_start, rel=1e-6)
    # Simulation v2: no horizon on this profile, so the standard 20 years, disclosed.
    assert curves["engine"] == "monte_carlo_v2"
    assert curves["horizon_source"] == "default"
    assert curves["sell_p50"][0] == pytest.approx(curves["sale"]["proceeds"])
    assert curves["sale"]["tax"] == 0   # a loss pays no capital-gains tax

    explainer = d["explainer_output"]
    assert explainer["bias"]["model"] == "bias_v4"
    assert explainer["bias"]["market_context"] == "unavailable"
    assert explainer["bias"]["bias_type"] == d["bias_detected"]
    assert all("label" in f for f in explainer["factors"])
    # "What weighed most" explains the pattern actually chosen, with a direction.
    assert explainer["factors"] and all(f["direction"] in ("toward", "against") for f in explainer["factors"])
    assert d["debate_transcript"]["engine"] == "evidence_rules_v1"
    assert d["debate_transcript"]["llm_debate"] is False
    # Every step is real now (B1 replaced the audit placeholder).
    assert body["stubbed_steps"] == []


async def test_stats_aggregate_only_the_callers_decisions(client, redis_conn):
    await _authed(client, redis_conn, "stats-a@example.com")
    await submit(client, decision_intent="sell")
    await submit(client, decision_intent="hold")

    stats = (await client.get("/v1/decisions/stats")).json()
    assert stats["total"] == 2
    assert stats["completed"] == 2
    assert sum(stats["by_bias"].values()) == 2
    assert stats["wealth_at_stake_inr"] >= 0

    await client.post("/v1/auth/logout", headers=csrf_header(client))
    await _authed(client, redis_conn, "stats-b@example.com")
    other = (await client.get("/v1/decisions/stats")).json()
    assert other["total"] == 0
    assert other["dominant_bias"] is None
    assert other["rational_share"] is None


# --------------------------------------------------------------------------- #
# Profile update: investor fields + first-fill of sensitive fields
# --------------------------------------------------------------------------- #
async def test_profile_update_sets_investor_fields(client, redis_conn):
    await _authed(client, redis_conn, "profile-investor@example.com")
    resp = await client.put(
        "/v1/users/me/profile",
        json={"name": "Investor", "goal": "Retirement", "financial_strategy": "moderate",
              "age": 41, "risk_tolerance": 0.65, "investment_horizon": 18},
        headers=csrf_header(client),
    )
    assert resp.status_code == 200, resp.text
    profile = (await client.get("/v1/users/me/profile")).json()["profile"]
    assert profile["age"] == 41
    assert profile["risk_tolerance"] == pytest.approx(0.65)
    assert profile["investment_horizon"] == 18


async def test_sensitive_fields_fill_once_then_need_reverification(client, redis_conn):
    await _authed(client, redis_conn, "profile-first-fill@example.com")
    base = {"name": "Filler", "goal": None, "financial_strategy": None}

    first = await client.put(
        "/v1/users/me/profile",
        json={**base, "monthly_income": 90000, "monthly_expense": 40000},
        headers=csrf_header(client),
    )
    assert first.status_code == 200, first.text

    change = await client.put(
        "/v1/users/me/profile",
        json={**base, "monthly_income": 150000},
        headers=csrf_header(client),
    )
    assert change.status_code == 403
    assert change.json()["error"] == "REVERIFICATION_REQUIRED"

    same = await client.put(
        "/v1/users/me/profile",
        json={**base, "monthly_income": 90000},
        headers=csrf_header(client),
    )
    assert same.status_code == 200, "re-sending the stored value is not a change"
