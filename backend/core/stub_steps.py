"""Placeholder pipeline steps — Milestone 3 only, replaced by Phase 5.

**These are not models.** Every value below comes from a small, deliberately
transparent arithmetic rule, not from XGBoost, a Monte Carlo run, or DoWhy. They exist so the §3F machinery — status transitions, SSE event
ordering, backlog replay, failure handling, the audit write — can be exercised
and tested end-to-end before Phase 5 lands.

Two guardrails against mistaking this output for real analysis:
  * every JSONB payload carries ``"stub": true`` and a ``"generated_by"`` note,
  * ``GET /v1/decisions/{id}/result`` reports ``stubbed_steps`` so the caller
    can see which steps had no real implementation.

Phase 5 replaces these one at a time via ``steps.register_step(name, fn)``;
nothing here needs deleting for that to take effect (``resolve_step`` prefers a
registered implementation), though it should be deleted once all five are real.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Mapping

from .steps import PipelineContext, StepResult, register_default_step

_STUB_NOTE = "milestone-3 placeholder; replaced by Phase 5"

# Nominal annual returns used by the placeholder projection. Chosen to be
# obviously round numbers — they are not calibrated to anything.
_HOLD_RATES = {"p10": 0.06, "median": 0.12, "p90": 0.16}
_SELL_REINVEST_RATE = 0.07  # proceeds sitting in a deposit-like instrument
_HORIZON_YEARS = 20


def _f(value: Any, default: float = 0.0) -> float:
    """Decimal/None-tolerant float coercion (asyncpg returns Decimal for NUMERIC)."""
    if value is None:
        return default
    return float(value)


def _q(value: float, places: str = "0.0001") -> Decimal:
    """Round to a NUMERIC-safe Decimal (matches the column scales in 0003)."""
    return Decimal(str(value)).quantize(Decimal(places))


# --------------------------------------------------------------------------- #
# 1. Bias detection  (Phase 5A replaces this with the XGBoost classifier)
# --------------------------------------------------------------------------- #
async def _bias_detection(ctx: PipelineContext) -> StepResult:
    d = ctx.decision
    pnl = _f(d["unrealized_pnl_pct"])
    intent = d["decision_intent"]

    # Textbook definitions, applied literally:
    #   disposition effect — realising gains early while letting losses ride
    #   loss aversion      — refusing to close a losing position
    #   herd behaviour     — adding to a position because the market is running
    if intent == "sell" and pnl > 0.05:
        bias = "disposition_effect"
    elif intent == "hold" and pnl < -0.10:
        bias = "loss_aversion"
    elif intent == "buy_more" and d.get("market_trend") == "bull":
        bias = "herd_behavior"
    else:
        bias = "rational"

    # Confidence grows with the size of the move; capped well short of certainty.
    confidence = 0.55 if bias == "rational" else min(0.90, 0.55 + abs(pnl) * 1.5)

    return StepResult(
        updates={
            "bias_detected": bias,
            "bias_confidence": _q(confidence),
        },
        event={"bias": bias, "confidence": round(confidence, 4)},
    )


# --------------------------------------------------------------------------- #
# 2. Simulation  (Phase 5B replaces this with the Monte Carlo simulator)
# --------------------------------------------------------------------------- #
def _compound(principal: float, rate: float, years: int) -> float:
    return principal * ((1.0 + rate) ** years)


def _curve(principal: float, rate: float, years: int) -> list[float]:
    return [round(_compound(principal, rate, y), 2) for y in range(years + 1)]


async def _simulation(ctx: PipelineContext) -> StepResult:
    d = ctx.decision
    position_value = _f(d["holding_quantity"]) * _f(d["current_price"])

    hold = {k: _compound(position_value, r, _HORIZON_YEARS) for k, r in _HOLD_RATES.items()}
    sell_median = _compound(position_value, _SELL_REINVEST_RATE, _HORIZON_YEARS)
    # Placeholder spread around the sell path: ±20% of the median.
    sell = {"p10": sell_median * 0.8, "median": sell_median, "p90": sell_median * 1.2}

    curves = {
        "stub": True,
        "generated_by": _STUB_NOTE,
        "years": list(range(_HORIZON_YEARS + 1)),
        "hold_median": _curve(position_value, _HOLD_RATES["median"], _HORIZON_YEARS),
        "sell_median": _curve(position_value, _SELL_REINVEST_RATE, _HORIZON_YEARS),
    }

    return StepResult(
        updates={
            "hold_median_20y": _q(hold["median"], "0.01"),
            "hold_p10_20y": _q(hold["p10"], "0.01"),
            "hold_p90_20y": _q(hold["p90"], "0.01"),
            "sell_median_20y": _q(sell["median"], "0.01"),
            "sell_p10_20y": _q(sell["p10"], "0.01"),
            "sell_p90_20y": _q(sell["p90"], "0.01"),
            "opportunity_cost_inr": _q(hold["median"] - sell["median"], "0.01"),
            "simulation_curves": curves,
        },
        event={
            "hold_median_20y": round(hold["median"], 2),
            "sell_median_20y": round(sell["median"], 2),
        },
    )


# --------------------------------------------------------------------------- #
# 3. Explanation  (Phase 5C replaces this with causal inference + explainer)
# --------------------------------------------------------------------------- #
async def _explanation(ctx: PipelineContext) -> StepResult:
    d = ctx.decision
    pnl = _f(d["unrealized_pnl_pct"])
    bias = d.get("bias_detected") or "rational"

    # Placeholder "causal effect": half the unrealised move, sign-flipped, so a
    # deep loss reads as a large positive pull toward the biased action.
    causal_effect = max(-9.9999, min(9.9999, -pnl * 0.5))

    explanation = {
        "stub": True,
        "generated_by": _STUB_NOTE,
        "headline": f"Detected {bias.replace('_', ' ')} on {d['symbol']}.",
        "factors": [
            {"name": "unrealized_pnl_pct", "value": round(pnl, 4)},
            {"name": "decision_intent", "value": d["decision_intent"]},
            {"name": "market_trend", "value": d.get("market_trend")},
        ],
        "opportunity_cost_inr": _f(d.get("opportunity_cost_inr")),
    }

    return StepResult(
        updates={
            "causal_effect": _q(causal_effect),
            "explainer_output": explanation,
        },
        event={"causal_effect": round(causal_effect, 4)},
    )


# --------------------------------------------------------------------------- #
# 4. Debate  (Phase 5D replaces this with the AutoGen debate engine)
# --------------------------------------------------------------------------- #
_VERDICT_BY_BIAS = {
    "loss_aversion": "HOLD",
    "disposition_effect": "HOLD",
    "herd_behavior": "HOLD",
    "rational": "HOLD",
}


async def _debate(ctx: PipelineContext) -> StepResult:
    d = ctx.decision
    bias = d.get("bias_detected") or "rational"
    # A rational intent is taken at face value; a biased one defaults to HOLD,
    # the conservative action. No model is consulted.
    verdict = d["decision_intent"].upper() if bias == "rational" else _VERDICT_BY_BIAS[bias]
    if verdict == "BUY_MORE" and bias != "rational":
        verdict = "HOLD"

    transcript = {
        "stub": True,
        "generated_by": _STUB_NOTE,
        "rounds": [
            {"agent": "bull", "stance": "HOLD", "argument": "Placeholder — no LLM was called."},
            {"agent": "bear", "stance": "SELL", "argument": "Placeholder — no LLM was called."},
        ],
        "judge": {"verdict": verdict, "rationale": "Placeholder verdict from the bias label."},
        "verdict": verdict,
    }

    return StepResult(
        updates={"debate_transcript": transcript, "recommendation": verdict},
        event={"verdict": verdict},
    )


# --------------------------------------------------------------------------- #
# 5. Audit  (Phase 5E replaces this with the full audit_logger hash chain)
# --------------------------------------------------------------------------- #
_GENESIS_HASH = "0" * 64


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


async def _audit(ctx: PipelineContext) -> StepResult:
    """Append one ``decision_complete`` row to the per-user hash chain.

    The chain rule here (``chain = sha256(previous_hash + payload_hash)``) is a
    simplification; Phase 5E owns the real genesis/verification design. The row
    is written directly because ``audit_logs`` is not a ``decisions`` column —
    the surrounding orchestrator only applies ``StepResult.updates``.
    """
    d = ctx.decision
    payload = {
        "stub": True,
        "generated_by": _STUB_NOTE,
        "event": "decision_complete",
        "decision_id": str(ctx.decision_id),
        "symbol": d["symbol"],
        "decision_intent": d["decision_intent"],
        "bias_detected": d.get("bias_detected"),
        "recommendation": d.get("recommendation"),
    }
    payload_hash = _sha256(_canonical(payload))

    async with ctx.db.rls_transaction(ctx.user_id) as conn:
        previous_hash = await conn.fetchval(
            """
            SELECT chain_hash FROM audit_logs
            WHERE user_id = $1
            ORDER BY created_at DESC, log_id DESC
            LIMIT 1
            """,
            ctx.user_id,
        ) or _GENESIS_HASH
        chain_hash = _sha256(previous_hash + payload_hash)
        await conn.execute(
            """
            INSERT INTO audit_logs
                (decision_id, user_id, event_type, payload_hash, previous_hash,
                 chain_hash, payload)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            ctx.decision_id,
            ctx.user_id,
            "decision_complete",
            payload_hash,
            previous_hash,
            chain_hash,
            json.dumps(payload, default=str),
        )

    return StepResult(event={"chain_hash": chain_hash})


register_default_step("bias_detection", _bias_detection)
register_default_step("simulation", _simulation)
register_default_step("explanation", _explanation)
register_default_step("debate", _debate)
register_default_step("audit", _audit)
