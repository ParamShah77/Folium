"""Phase B1 against the real database: record, verify, then tamper.

The pure verifier is covered in tests/unit/test_audit_chain.py; these tests
prove the pieces around it — the pipeline writes the entry, the append-only
rules hold, RLS keeps chains apart, and the verify endpoint reports tampering
done directly in Postgres.
"""
from __future__ import annotations

import pytest

from .helpers import csrf_header, login_user, register_and_verify
from .test_decisions import submit

pytestmark = pytest.mark.asyncio


async def _authed(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    assert (await login_user(client, email)).status_code == 200


async def _analyse(client) -> str:
    decision_id = (await submit(client)).json()["decision_id"]
    d = (await client.get(f"/v1/decisions/{decision_id}/result")).json()["decision"]
    assert d["status"] == "complete", d.get("error_message")
    return decision_id


async def test_a_completed_analysis_is_recorded_and_verifies(client, redis_conn):
    await _authed(client, redis_conn, "audit-ok@example.com")
    first = await _analyse(client)
    second = await _analyse(client)
    body = (await client.get(f"/v1/decisions/{second}/verify")).json()
    assert body["verified"] is True
    assert body["record"]["status"] == "verified"
    assert body["chain"] == {"valid": True, "entries": 2, "linked": 2, "anchor": "current", "problems": []}
    assert len(body["record"]["fingerprint"]) == 64
    assert (await client.get(f"/v1/decisions/{first}/verify")).json()["verified"] is True


async def test_editing_the_analysis_in_the_database_is_caught(client, redis_conn, db_conn):
    await _authed(client, redis_conn, "audit-edit@example.com")
    decision_id = await _analyse(client)
    await db_conn.execute("UPDATE decisions SET recommendation = 'SELL' WHERE decision_id = $1", decision_id)
    body = (await client.get(f"/v1/decisions/{decision_id}/verify")).json()
    assert body["verified"] is False
    assert body["record"]["status"] == "changed"
    assert body["record"]["parts"] == {"inputs": "unchanged", "analysis": "changed"}
    assert body["chain"]["valid"] is True          # the record itself is untouched


async def test_audit_entries_cannot_be_edited_or_deleted(client, redis_conn, db_conn):
    await _authed(client, redis_conn, "audit-rules@example.com")
    decision_id = await _analyse(client)
    before = await db_conn.fetchrow("SELECT payload_hash, chain_hash FROM audit_logs WHERE decision_id = $1", decision_id)
    await db_conn.execute("UPDATE audit_logs SET payload_hash = 'x' WHERE decision_id = $1", decision_id)
    await db_conn.execute("DELETE FROM audit_logs WHERE decision_id = $1", decision_id)
    after = await db_conn.fetchrow("SELECT payload_hash, chain_hash FROM audit_logs WHERE decision_id = $1", decision_id)
    assert dict(after) == dict(before)              # the append-only rules turned both into no-ops


async def test_a_forged_entry_breaks_the_chain(client, redis_conn, db_conn):
    await _authed(client, redis_conn, "audit-forge@example.com")
    decision_id = await _analyse(client)
    user_id = await db_conn.fetchval("SELECT user_id FROM decisions WHERE decision_id = $1", decision_id)
    await db_conn.execute(
        """INSERT INTO audit_logs (decision_id, user_id, event_type, payload_hash, previous_hash, chain_hash, payload)
           VALUES ($1, $2, 'analysis_recorded', $3, $4, $5, '{"forged": true}'::jsonb)""",
        decision_id, user_id, "a" * 64, "b" * 64, "c" * 64,
    )
    body = (await client.get(f"/v1/decisions/{decision_id}/verify")).json()
    assert body["verified"] is False
    kinds = {p["kind"] for p in body["chain"]["problems"]}
    assert "altered" in kinds or "unlinked" in kinds


async def test_one_investors_chain_is_invisible_to_another(client, redis_conn):
    await _authed(client, redis_conn, "audit-a@example.com")
    decision_id = await _analyse(client)
    await client.post("/v1/auth/logout", headers=csrf_header(client))
    await _authed(client, redis_conn, "audit-b@example.com")
    assert (await client.get(f"/v1/decisions/{decision_id}/verify")).status_code == 404
