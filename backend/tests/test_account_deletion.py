"""Phase B2: download my data, and delete my account with a 30-day grace period."""
from __future__ import annotations

import json

import pytest

from backend.core import audit
from backend.services.account_deletion import purge_due_accounts

from .helpers import STRONG_PASSWORD, csrf_header, login_user, register_and_verify
from .test_decisions import submit

pytestmark = pytest.mark.asyncio


async def _authed_with_analysis(client, redis_conn, email: str) -> str:
    await register_and_verify(client, redis_conn, email)
    assert (await login_user(client, email)).status_code == 200
    decision_id = (await submit(client)).json()["decision_id"]
    d = (await client.get(f"/v1/decisions/{decision_id}/result")).json()["decision"]
    assert d["status"] == "complete", d.get("error_message")
    return decision_id


async def _delete(client, password=STRONG_PASSWORD, **extra):
    return await client.post("/v1/users/me/delete", json={"password": password, **extra}, headers=csrf_header(client))


# ── Download my data ─────────────────────────────────────────────────────

async def test_export_has_everything_and_no_secrets(client, redis_conn):
    decision_id = await _authed_with_analysis(client, redis_conn, "export@example.com")
    await client.put("/v1/portfolio/assets", json={"fixed_deposits": 150000, "monthly_sip": 10000},
                     headers=csrf_header(client))
    resp = await client.get("/v1/users/me/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = json.loads(resp.text)
    assert data["account"]["email"] == "export@example.com"
    for secret in ("password_hash", "mfa_secret_enc", "oauth_id"):
        assert secret not in data["account"]
    assert data["financial_profile"]["monthly_sip"] == 10000
    assert [a["decision_id"] for a in data["analyses"]] == [decision_id]
    record = data["secure_record"]
    assert record["verification"]["valid"] is True and len(record["entries"]) == 1
    # The export is enough to check the chain by hand.
    e = record["entries"][0]
    assert e["previous_hash"] == record["genesis"]
    assert audit.sha256(e["previous_hash"] + e["payload_hash"]) == e["chain_hash"]


# ── Delete my account ────────────────────────────────────────────────────

async def test_deleting_needs_the_password(client, redis_conn):
    await _authed_with_analysis(client, redis_conn, "del-pw@example.com")
    assert (await _delete(client, password="wrong-password-1A!")).status_code == 401
    assert (await client.get("/v1/auth/me")).status_code == 200      # still signed in


async def test_deleting_signs_out_and_locks_the_account(client, redis_conn, db_conn):
    await _authed_with_analysis(client, redis_conn, "del-lock@example.com")
    resp = await _delete(client, reason="testing")
    assert resp.status_code == 200 and resp.json()["grace_days"] == 30
    assert (await client.get("/v1/auth/me")).status_code == 401
    login = await login_user(client, "del-lock@example.com")
    assert login.status_code == 403
    body = login.json()
    assert body["error"] == "ACCOUNT_DELETED" and body["purge_after"]
    sessions = await db_conn.fetchval(
        "SELECT count(*) FROM refresh_tokens r JOIN users u USING (user_id) WHERE u.email = 'del-lock@example.com'")
    assert sessions == 0


async def test_logging_back_in_during_the_grace_period_keeps_the_account(client, redis_conn):
    await _authed_with_analysis(client, redis_conn, "del-keep@example.com")
    await _delete(client)
    keep = await client.post("/v1/auth/cancel-deletion",
                             json={"email": "del-keep@example.com", "password": STRONG_PASSWORD})
    assert keep.status_code == 200 and keep.json()["kept"] is True
    assert (await login_user(client, "del-keep@example.com")).status_code == 200


async def test_after_the_grace_period_the_account_is_anonymised(app, client, redis_conn, db_conn):
    decision_id = await _authed_with_analysis(client, redis_conn, "del-purge@example.com")
    await client.put("/v1/portfolio/assets", json={"fixed_deposits": 150000}, headers=csrf_header(client))
    user_id = await db_conn.fetchval("SELECT user_id FROM users WHERE email = 'del-purge@example.com'")
    audit_before = await db_conn.fetch("SELECT log_id, chain_hash FROM audit_logs WHERE user_id = $1", user_id)
    await _delete(client)

    # Not yet due: nothing happens.
    assert await purge_due_accounts(app.state.db) == 0
    await db_conn.execute("UPDATE users SET purge_after = NOW() - INTERVAL '1 minute' WHERE user_id = $1", user_id)
    assert await purge_due_accounts(app.state.db) == 1

    u = await db_conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    assert u["email"] == f"deleted-{user_id}@deleted.invalid" and u["name"] == "Deleted user"
    assert u["password_hash"] is None and u["monthly_income"] is None and u["age"] is None
    assert u["anonymised_at"] is not None and u["created_at"] is not None   # the chain's anchor stays
    assert await db_conn.fetchval("SELECT count(*) FROM financial_profiles WHERE user_id = $1", user_id) == 0
    d = await db_conn.fetchrow("SELECT * FROM decisions WHERE decision_id = $1", decision_id)
    assert d["user_reasoning"] is None and d["portfolio_context"] is None and d["explainer_output"] is None
    # The audit record is untouched and still links up.
    audit_after = await db_conn.fetch("SELECT log_id, chain_hash FROM audit_logs WHERE user_id = $1", user_id)
    assert {tuple(r) for r in audit_after} == {tuple(r) for r in audit_before}
    entries = [dict(r) for r in await db_conn.fetch(audit._ENTRIES_SQL, user_id)]
    assert audit.verify_chain(entries, audit.genesis_hash(str(user_id), u["created_at"]))["valid"]

    # Gone for good: the grace period can't be reopened.
    keep = await client.post("/v1/auth/cancel-deletion",
                             json={"email": "del-purge@example.com", "password": STRONG_PASSWORD})
    assert keep.status_code == 401
