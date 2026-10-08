"""Phase B1 audit chain — hashing and verification, no datastore.

Each test tampers with a chain in one way GAP 4 says must be caught: an edited
entry, a removed entry, a forged insertion, a fork, an edited analysis.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.core import audit

USER = "8b1c2c1e-6c1a-4c39-9f43-5ce1f1d0a001"
CREATED = datetime(2026, 10, 6, 18, 30, tzinfo=timezone.utc)
GENESIS = audit.genesis_hash(USER, CREATED)


def decision(n: int, **kw) -> dict:
    row = {
        "decision_id": uuid.UUID(int=n), "user_id": uuid.UUID(USER), "symbol": "HDFCBANK", "exchange": "NSE",
        "holding_quantity": Decimal("120.0000"), "avg_buy_price": Decimal("867.62"),
        "current_price": Decimal("711.45"), "unrealized_pnl_pct": Decimal("-0.1800"),
        "decision_intent": "sell", "user_reasoning": "It keeps falling.", "holding_period_days": 426,
        "market_trend": "bear", "tax_category": "LTCG", "nifty_1m_return": Decimal("-0.0460"),
        "nifty_volatility_30d": Decimal("0.00663"), "nifty_1d_change": None, "vix_value": Decimal("13.610"),
        "market_data_source": "live", "holding_id": None,
        "portfolio_context": json.dumps({"position_share": 0.063, "allocation": {"gold": 516000.0}}),
        "bias_detected": "loss_aversion", "bias_confidence": Decimal("0.8600"), "causal_effect": Decimal("0.0169"),
        "opportunity_cost_inr": Decimal("229306.19"),
        "hold_median_20y": Decimal("631052.59"), "hold_p10_20y": Decimal("163000.00"), "hold_p90_20y": Decimal("2600000.00"),
        "sell_median_20y": Decimal("377362.51"), "sell_p10_20y": Decimal("216000.00"), "sell_p90_20y": Decimal("500000.00"),
        "explainer_output": json.dumps({"bias": {"model": "bias_v4", "confidence": 0.86}}),
        "simulation_curves": json.dumps({"engine": "monte_carlo_v2", "horizon_years": 22}),
        "debate_transcript": json.dumps({"engine": "evidence_rules_v1"}),
        "recommendation": "HOLD",
    }
    row.update(kw)
    return row


def chain(n: int) -> tuple[list[dict], list[dict]]:
    """A valid chain of n entries, built the way append_entry builds them."""
    rows, entries, previous = [], [], GENESIS
    for i in range(n):
        row = decision(i + 1)
        payload = audit.build_payload(row, CREATED + timedelta(minutes=i))
        payload_hash = audit.sha256(audit.canonical(payload))
        chain_hash = audit.sha256(previous + payload_hash)
        entries.append({"log_id": uuid.UUID(int=1000 + i), "decision_id": row["decision_id"], "event_type": "analysis_recorded",
                        "payload_hash": payload_hash, "previous_hash": previous, "chain_hash": chain_hash,
                        "payload": audit.canonical(payload), "created_at": CREATED + timedelta(minutes=i)})
        rows.append(row)
        previous = chain_hash
    return rows, entries


# ── An intact chain ──────────────────────────────────────────────────────

def test_an_intact_chain_verifies():
    rows, entries = chain(5)
    result = audit.verify_chain(entries, GENESIS)
    assert result["valid"] and result["linked"] == 5 and result["anchor"] == "current"
    assert audit.verify_decision(rows[2], entries, result)["status"] == "verified"


def test_order_comes_from_the_links_not_the_timestamps():
    rows, entries = chain(4)
    for e in entries:
        e["created_at"] = CREATED          # identical timestamps
    shuffled = [entries[2], entries[0], entries[3], entries[1]]
    result = audit.verify_chain(shuffled, GENESIS)
    assert result["valid"] and result["order"] == [str(e["log_id"]) for e in entries]


def test_the_genesis_is_recomputable_from_user_id_and_signup_time():
    assert audit.genesis_hash(USER, CREATED) == audit.sha256(f"GENESIS:{USER}:{CREATED.isoformat()}")


# ── Tampering ────────────────────────────────────────────────────────────

def test_an_edited_entry_is_caught():
    _, entries = chain(4)
    p = json.loads(entries[1]["payload"])
    p["summary"]["recommendation"] = "SELL"
    entries[1]["payload"] = audit.canonical(p)
    result = audit.verify_chain(entries, GENESIS)
    assert not result["valid"]
    assert {"kind": "altered", "log_id": str(entries[1]["log_id"])}.items() <= result["problems"][0].items()


def test_a_removed_entry_is_caught():
    _, entries = chain(4)
    del entries[1]
    result = audit.verify_chain(entries, GENESIS)
    assert not result["valid"]
    assert any(p["kind"] == "unlinked" for p in result["problems"])


def test_a_forged_insertion_is_caught():
    rows, entries = chain(3)
    forged_payload = audit.build_payload(decision(99, recommendation="SELL"), CREATED)
    ph = audit.sha256(audit.canonical(forged_payload))
    entries.append({"log_id": uuid.uuid4(), "decision_id": uuid.UUID(int=99), "payload_hash": ph,
                    "previous_hash": "f" * 64, "chain_hash": audit.sha256("f" * 64 + ph),
                    "payload": audit.canonical(forged_payload), "created_at": CREATED})
    result = audit.verify_chain(entries, GENESIS)
    assert not result["valid"] and any(p["kind"] == "unlinked" for p in result["problems"])


def test_a_fork_is_caught():
    _, entries = chain(3)
    twin = dict(entries[2], log_id=uuid.uuid4())   # a second entry claiming the same predecessor
    result = audit.verify_chain(entries + [twin], GENESIS)
    assert not result["valid"] and any(p["kind"] == "fork" for p in result["problems"])


def test_an_edited_analysis_is_caught_and_named():
    rows, entries = chain(3)
    chain_ok = audit.verify_chain(entries, GENESIS)
    edited = dict(rows[1], recommendation="SELL")
    out = audit.verify_decision(edited, entries, chain_ok)
    assert out["status"] == "changed"
    assert out["parts"] == {"inputs": "unchanged", "analysis": "changed"}
    edited_inputs = dict(rows[1], current_price=Decimal("900.00"))
    assert audit.verify_decision(edited_inputs, entries, chain_ok)["parts"]["inputs"] == "changed"


def test_an_analysis_without_a_record_is_reported_missing():
    rows, entries = chain(2)
    out = audit.verify_decision(decision(42), entries, audit.verify_chain(entries, GENESIS))
    assert out["status"] == "missing"


# ── Stability: the same row hashes the same however it arrives ───────────

def test_fingerprints_survive_database_round_trips():
    row = decision(1)
    as_dicts = dict(row, portfolio_context=json.loads(row["portfolio_context"]),
                    explainer_output=json.loads(row["explainer_output"]),
                    simulation_curves=json.loads(row["simulation_curves"]),
                    debate_transcript=json.loads(row["debate_transcript"]),
                    holding_quantity=Decimal("120"), avg_buy_price=Decimal("867.620"))
    assert audit.fingerprints(row) == audit.fingerprints(as_dicts)


def test_status_fields_are_not_part_of_the_record():
    """Status and timestamps change after the record is written; they mustn't break it."""
    row = decision(1)
    later = dict(row, status="complete", completed_at=CREATED, submitted_at=CREATED - timedelta(days=3))
    assert audit.fingerprints(row) == audit.fingerprints(later)


# ── Earlier-format entries ───────────────────────────────────────────────

def test_a_chain_started_by_the_placeholder_still_verifies():
    stub_payload = {"stub": True, "event": "decision_complete", "decision_id": str(uuid.UUID(int=1)),
                    "bias_detected": "loss_aversion", "recommendation": "HOLD"}
    ph = audit.sha256(audit.canonical(stub_payload))
    first = {"log_id": uuid.UUID(int=1), "decision_id": uuid.UUID(int=1), "payload_hash": ph,
             "previous_hash": audit.LEGACY_GENESIS, "chain_hash": audit.sha256(audit.LEGACY_GENESIS + ph),
             "payload": audit.canonical(stub_payload), "created_at": CREATED}
    payload = audit.build_payload(decision(2), CREATED)
    ph2 = audit.sha256(audit.canonical(payload))
    second = {"log_id": uuid.UUID(int=2), "decision_id": uuid.UUID(int=2), "payload_hash": ph2,
              "previous_hash": first["chain_hash"], "chain_hash": audit.sha256(first["chain_hash"] + ph2),
              "payload": audit.canonical(payload), "created_at": CREATED}
    result = audit.verify_chain([second, first], GENESIS)
    assert result["valid"] and result["anchor"] == "earlier format"
    assert audit.verify_decision(decision(1), [first, second], result)["status"] == "matches_earlier_format"
    assert audit.chain_head([first, second], GENESIS) == second["chain_hash"]
