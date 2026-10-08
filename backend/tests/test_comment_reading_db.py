"""Phase B3 end to end: the comment is read, a stated need reaches the model,
feelings are only shown, the two cases are written, and consent is respected."""
from __future__ import annotations

import pytest

from .helpers import csrf_header, login_user, register_and_verify
from .test_decisions import submit

pytestmark = pytest.mark.asyncio


async def _authed(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    assert (await login_user(client, email)).status_code == 200


async def _result(client, **body) -> dict:
    decision_id = (await submit(client, **body)).json()["decision_id"]
    d = (await client.get(f"/v1/decisions/{decision_id}/result")).json()["decision"]
    assert d["status"] == "complete", d.get("error_message")
    return d


async def test_a_stated_need_for_the_money_reaches_the_model(client, redis_conn):
    await _authed(client, redis_conn, "comment-need@example.com")
    d = await _result(client, decision_intent="sell",
                      user_reasoning="I need the money for my daughter's college fees in March.")
    assert d["comment_facts"]["cash_need"] is True
    assert "college fees" in d["comment_facts"]["cash_need_quote"]
    assert d["explainer_output"]["bias"]["model_inputs"]["cash_need_stated"] == 1
    assert d["explainer_output"]["own_words"]["cash_need"] is True


async def test_feelings_are_shown_but_not_used(client, redis_conn):
    await _authed(client, redis_conn, "comment-feel@example.com")
    d = await _result(client, decision_intent="sell", user_reasoning="Everyone is selling and I'm scared.")
    assert d["explainer_output"]["bias"]["model_inputs"]["cash_need_stated"] == 0
    kinds = {c["kind"] for c in d["explainer_output"]["own_words"]["cues"]}
    assert {"crowd", "fear"} <= kinds


async def test_both_cases_are_written_and_the_verdict_stands_alone(client, redis_conn):
    await _authed(client, redis_conn, "comment-cases@example.com")
    d = await _result(client, decision_intent="sell", user_reasoning="It will bounce back.")
    t = d["debate_transcript"]
    assert [c["side"] for c in t["cases"]] == ["stay", "leave"]
    assert all(c["text"] for c in t["cases"])
    assert t["llm_debate"] is False                       # no consent, no key: numbers only
    assert t["verdict"] == d["recommendation"]


async def test_consent_is_off_by_default_and_can_be_turned_on(client, redis_conn):
    await _authed(client, redis_conn, "comment-consent@example.com")
    profile = (await client.get("/v1/users/me/profile")).json()["profile"]
    assert profile["ai_consent"] is False
    resp = await client.put("/v1/users/me/ai-consent", json={"enabled": True}, headers=csrf_header(client))
    assert resp.status_code == 200 and resp.json()["ai_consent"] is True
    assert (await client.get("/v1/users/me/profile")).json()["profile"]["ai_consent"] is True
    # Whether Gemini is actually used also needs AI_HELP and a key on the server.
    assert resp.json()["ai_help_available"] == (await client.get("/v1/meta/config")).json()["ai_help"]
