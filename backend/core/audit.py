"""Phase B1 — the tamper-evident audit chain, replacing ``stub_steps._audit``.

Every completed analysis appends one entry to the investor's own chain in
``audit_logs`` (append-only: migration 0004's rules turn UPDATE and DELETE into
no-ops). An entry records:

* ``inputs_hash``   — a fingerprint of what the analysis was given: the holding,
  prices, the stated action and reason, the market snapshot and the portfolio
  snapshot;
* ``analysis_hash`` — a fingerprint of what it concluded: the pattern and
  confidence, the projection, the explanation and the recommendation;
* a readable summary and the engines that produced it.

``payload_hash = sha256(canonical(payload))`` and
``chain_hash = sha256(previous_hash + payload_hash)``: each entry seals the one
before it, back to a genesis value derived from the investor's id and sign-up
time (``sha256("GENESIS:{user_id}:{created_at}")``, as GAP 4 specifies), which
anyone holding those two facts can recompute.

**Verification** (:func:`verify_chain`, :func:`verify_decision`) answers two
questions:

1. *Is the chain intact?* It is walked by following the links from the
   genesis, not by timestamp, so an altered entry (its hashes no longer
   recompute), a removed one (the next link points at nothing), a forged one
   (it doesn't link in) and a fork (two entries claim the same predecessor)
   are all caught.
2. *Does the analysis on screen still match its record?* Both fingerprints
   are recomputed from the current ``decisions`` row; a mismatch names the
   part that changed.

Entries written by the Milestone 3 placeholder (``chain_version`` absent) used
a zero genesis and a short summary; they are accepted as the start of a chain
and labelled as the earlier format, since the table can't be rewritten.

Appends take a per-investor advisory lock, so two analyses finishing together
can't both claim the same predecessor.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .steps import PipelineContext, StepResult, register_step

CHAIN_VERSION = 2
LEGACY_GENESIS = "0" * 64

#: What the analysis was given.
INPUT_FIELDS: tuple[str, ...] = (
    "decision_id", "user_id", "symbol", "exchange", "holding_quantity", "avg_buy_price",
    "current_price", "unrealized_pnl_pct", "decision_intent", "user_reasoning",
    "holding_period_days", "market_trend", "tax_category", "nifty_1m_return",
    "nifty_volatility_30d", "nifty_1d_change", "vix_value", "market_data_source",
    "holding_id", "portfolio_context", "comment_facts",
)
#: The input fields of records written before B3 (no comment reading yet).
_INPUT_FIELDS_B1 = tuple(f for f in INPUT_FIELDS if f != "comment_facts")
#: What it concluded.
ANALYSIS_FIELDS: tuple[str, ...] = (
    "bias_detected", "bias_confidence", "causal_effect", "opportunity_cost_inr",
    "hold_median_20y", "hold_p10_20y", "hold_p90_20y",
    "sell_median_20y", "sell_p10_20y", "sell_p90_20y",
    "explainer_output", "simulation_curves", "debate_transcript", "recommendation",
)
_JSON_FIELDS = frozenset({"portfolio_context", "explainer_output", "simulation_curves", "debate_transcript",
                          "comment_facts"})

#: Plain names for the parts of a record, for the verification message.
PART_LABELS = {"inputs": "what you entered and the market and portfolio at the time",
               "analysis": "the pattern found, the projection, the explanation and the recommendation"}


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(payload: Any) -> str:
    """One byte-exact text for a value: sorted keys, no spaces."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def _normalise(field: str, value: Any) -> Any:
    """The same value however it arrives (asyncpg Decimal/UUID/datetime, JSONB as text or dict)."""
    if value is None:
        return None
    if field in _JSON_FIELDS and isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")      # 1600.00 and 1600 read the same
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.loads(canonical(value))   # nested Decimals/UUIDs -> plain text, keys sorted
    return value


def section_hash(row: Mapping[str, Any], fields: Iterable[str]) -> str:
    return sha256(canonical({f: _normalise(f, row.get(f)) for f in fields}))


def fingerprints(row: Mapping[str, Any], input_fields: Iterable[str] = INPUT_FIELDS,
                 analysis_fields: Iterable[str] = ANALYSIS_FIELDS) -> dict[str, str]:
    return {"inputs": section_hash(row, input_fields), "analysis": section_hash(row, analysis_fields)}


def genesis_hash(user_id: str, created_at: datetime) -> str:
    """GAP 4's anchor: recomputable by anyone who knows the user id and sign-up time."""
    return sha256(f"GENESIS:{user_id}:{created_at.isoformat()}")


def build_payload(row: Mapping[str, Any], recorded_at: datetime) -> dict[str, Any]:
    explainer = _normalise("explainer_output", row.get("explainer_output")) or {}
    curves = _normalise("simulation_curves", row.get("simulation_curves")) or {}
    debate = _normalise("debate_transcript", row.get("debate_transcript")) or {}
    fp = fingerprints(row)
    return {
        "chain_version": CHAIN_VERSION,
        "event": "analysis_recorded",
        "decision_id": str(row["decision_id"]),
        "recorded_at": recorded_at.isoformat(),
        "inputs_hash": fp["inputs"],
        "analysis_hash": fp["analysis"],
        # Which columns each fingerprint covers, so the set can grow later
        # without older records failing verification.
        "fields": {"inputs": list(INPUT_FIELDS), "analysis": list(ANALYSIS_FIELDS)},
        "engines": {
            "pattern": (explainer.get("bias") or {}).get("model"),
            "projection": curves.get("engine"),
            "recommendation": debate.get("engine"),
        },
        "summary": {
            "symbol": row.get("symbol"),
            "intent": row.get("decision_intent"),
            "pattern": row.get("bias_detected"),
            "confidence": _normalise("bias_confidence", row.get("bias_confidence")),
            "recommendation": row.get("recommendation"),
            "horizon_years": curves.get("horizon_years"),
        },
    }


# --------------------------------------------------------------------------- #
# Verification (pure)
# --------------------------------------------------------------------------- #

def _payload_dict(entry: Mapping[str, Any]) -> dict[str, Any]:
    p = entry["payload"]
    return json.loads(p) if isinstance(p, str) else dict(p)


def verify_chain(entries: list[Mapping[str, Any]], genesis: str) -> dict[str, Any]:
    """Walk a user's entries from the genesis by their links.

    Returns ``valid``, how many entries there are and how many link in, the
    anchor ("current" genesis, "earlier format" zero genesis, or none), the
    chain order of entry ids, and each problem found.
    """
    problems: list[dict[str, Any]] = []
    by_prev: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for e in entries:
        by_prev[e["previous_hash"]].append(e)
        payload_hash = sha256(canonical(_payload_dict(e)))
        if payload_hash != e["payload_hash"]:
            problems.append({"kind": "altered", "log_id": str(e["log_id"]),
                             "detail": "the entry's contents no longer match its fingerprint"})
        elif sha256(e["previous_hash"] + e["payload_hash"]) != e["chain_hash"]:
            problems.append({"kind": "altered", "log_id": str(e["log_id"]),
                             "detail": "the entry's seal no longer matches"})

    if not entries:
        return {"valid": True, "entries": 0, "linked": 0, "anchor": None, "order": [], "problems": []}

    anchor, start = None, None
    if genesis in by_prev:
        anchor, start = "current", genesis
    elif LEGACY_GENESIS in by_prev:
        anchor, start = "earlier format", LEGACY_GENESIS
    else:
        problems.append({"kind": "unanchored", "log_id": None,
                         "detail": "no entry links back to the start of the chain"})

    order: list[str] = []
    seen: set[str] = set()
    cur = start
    while cur is not None and cur in by_prev:
        nxt = by_prev[cur]
        if len(nxt) > 1:
            problems.append({"kind": "fork", "log_id": str(nxt[1]["log_id"]),
                             "detail": "two entries claim the same predecessor"})
        e = nxt[0]
        if str(e["log_id"]) in seen:      # a loop can't happen with real hashes; guard anyway
            break
        seen.add(str(e["log_id"]))
        order.append(str(e["log_id"]))
        cur = e["chain_hash"]

    for e in entries:
        if str(e["log_id"]) not in seen and not any(p["kind"] == "fork" and p["log_id"] == str(e["log_id"]) for p in problems):
            problems.append({"kind": "unlinked", "log_id": str(e["log_id"]),
                             "detail": "the entry doesn't link into the chain (an entry before it is missing, or it was added from outside)"})

    return {"valid": not problems, "entries": len(entries), "linked": len(order),
            "anchor": anchor, "order": order, "problems": problems}


def verify_decision(row: Mapping[str, Any], entries: list[Mapping[str, Any]], chain: Mapping[str, Any]) -> dict[str, Any]:
    """Does this analysis still match its most recent record in the chain?"""
    decision_id = str(row["decision_id"])
    position = {log_id: i for i, log_id in enumerate(chain.get("order", []))}
    mine = [e for e in entries if str(e.get("decision_id")) == decision_id]
    if not mine:
        return {"status": "missing", "detail": "No secure record was found for this analysis."}
    # Latest in chain order (an analysis that was re-run is recorded again).
    mine.sort(key=lambda e: (position.get(str(e["log_id"]), -1), e.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)))
    entry = mine[-1]
    payload = _payload_dict(entry)
    base = {"log_id": str(entry["log_id"]), "fingerprint": entry["chain_hash"],
            "recorded_at": payload.get("recorded_at") or _normalise("created_at", entry.get("created_at")),
            "times_recorded": len(mine)}

    if payload.get("chain_version") != CHAIN_VERSION:
        # Earlier-format entries kept only a summary; check what they kept.
        same = (payload.get("bias_detected") == row.get("bias_detected")
                and payload.get("recommendation") == row.get("recommendation"))
        return {**base, "status": "matches_earlier_format" if same else "changed",
                "parts": {"analysis": "unchanged" if same else "changed"},
                "detail": "Recorded in the earlier format, which kept only the pattern and recommendation."}

    fields = payload.get("fields") or {"inputs": list(_INPUT_FIELDS_B1), "analysis": list(ANALYSIS_FIELDS)}
    now = fingerprints(row, fields["inputs"], fields["analysis"])
    parts = {k: ("unchanged" if now[k] == payload.get(f"{k}_hash") else "changed") for k in ("inputs", "analysis")}
    status = "verified" if all(v == "unchanged" for v in parts.values()) else "changed"
    return {**base, "status": status, "parts": parts,
            "changed": [PART_LABELS[k] for k, v in parts.items() if v == "changed"]}


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #

_ENTRIES_SQL = """
    SELECT log_id, decision_id, event_type, payload_hash, previous_hash, chain_hash, payload, created_at
    FROM audit_logs WHERE user_id = $1
"""


async def load_chain(conn, user_id: str) -> tuple[list[dict[str, Any]], str]:
    entries = [dict(r) for r in await conn.fetch(_ENTRIES_SQL, user_id)]
    created = await conn.fetchval("SELECT created_at FROM users WHERE user_id = $1", user_id)
    return entries, genesis_hash(str(user_id), created)


def chain_head(entries: list[Mapping[str, Any]], genesis: str) -> str:
    """The hash a new entry must link to: the end of the chain walked from its start."""
    if not entries:
        return genesis
    result = verify_chain(entries, genesis)
    if result["order"]:
        last = {str(e["log_id"]): e for e in entries}[result["order"][-1]]
        return last["chain_hash"]
    return genesis


async def append_entry(conn, user_id: str, decision_id: str, row: Mapping[str, Any],
                       recorded_at: datetime | None = None) -> dict[str, Any]:
    """Append one entry under a per-investor lock. ``conn`` must be inside a transaction."""
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))", str(user_id))
    entries, genesis = await load_chain(conn, user_id)
    previous = chain_head(entries, genesis)
    payload = build_payload(row, recorded_at or datetime.now(timezone.utc))
    payload_hash = sha256(canonical(payload))
    chain_hash = sha256(previous + payload_hash)
    await conn.execute(
        """
        INSERT INTO audit_logs (decision_id, user_id, event_type, payload_hash, previous_hash, chain_hash, payload)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        """,
        decision_id, user_id, payload["event"], payload_hash, previous, chain_hash, canonical(payload),
    )
    return {"chain_hash": chain_hash, "previous_hash": previous, "payload": payload}


async def record(ctx: PipelineContext) -> StepResult:
    async with ctx.db.rls_transaction(ctx.user_id) as conn:
        out = await append_entry(conn, ctx.user_id, ctx.decision_id, ctx.decision)
    return StepResult(event={"chain_hash": out["chain_hash"], "fingerprint": out["chain_hash"]})


register_step("audit", record)
