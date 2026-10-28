"""Evidence-based recommendation — fills the ``debate`` step until Phase 5D.

The pipeline's fourth step owns ``recommendation`` (HOLD / SELL / BUY_MORE).
Its placeholder answered "HOLD" for any biased decision without looking at a
single number. Phase 5D will be an LLM bull/bear/judge debate; until then this
step derives the verdict from evidence the earlier steps actually produced:

  * 5B — how often holding beat selling across the simulated futures
    (``prob_hold_better``), and the opportunity cost;
  * 5A — whether the intent looks bias-driven, and how confidently.

It does **not** present itself as a debate. ``debate_transcript.engine`` is
``evidence_rules_v1`` with ``llm_debate: false``, and the rationale lists the
exact numbers each rule used, so the verdict can be checked by hand.

Rules (p = probability holding beats selling over the investor's horizon —
simulation v2; v1 decisions used a fixed 20 years):
  sell intent      p >= 0.60 -> HOLD;  p <= 0.40 -> SELL;
                   toss-up   -> HOLD if the sell looks biased, else SELL.
  hold intent      p <= 0.40 -> SELL;  otherwise HOLD.
  buy_more intent  biased with confidence >= 0.60, or herd -> HOLD;
                   otherwise BUY_MORE if p >= 0.50, else HOLD.
"""
from __future__ import annotations

from typing import Any

from .steps import PipelineContext, StepResult, register_step

_STRONG, _WEAK = 0.60, 0.40
_BIAS_CONFIDENT = 0.60


def confidence_band(confidence: float) -> str:
    """The words the app shows for a confidence (never a percentage):
    High at 0.85 or more, Medium at 0.65 or more, otherwise Low."""
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"

_BIAS_NAMES = {
    "loss_aversion": "loss aversion",
    "herd_behavior": "herd behaviour",
    "disposition_effect": "the disposition effect",
}


def decide(intent: str, bias: str, confidence: float, p_hold: float | None,
           horizon_years: int = 20) -> tuple[str, list[str]]:
    """Return (verdict, reasons). Pure function — unit-testable without a DB."""
    p = 0.5 if p_hold is None else p_hold
    biased = bias != "rational"
    bias_name = _BIAS_NAMES.get(bias, bias.replace("_", " "))
    pct = f"{p * 100:.0f}%"
    reasons: list[str] = []
    if p_hold is None:
        reasons.append("No simulation result was available, so the odds are treated as even.")

    if intent == "sell":
        if p >= _STRONG:
            reasons.append(f"Holding beat selling in {pct} of {horizon_years}-year simulations.")
            if biased:
                reasons.append(f"The urge to sell shows signs of {bias_name}.")
            return "HOLD", reasons
        if p <= _WEAK:
            reasons.append(f"Holding beat selling in only {pct} of simulations.")
            return "SELL", reasons
        reasons.append(f"The simulations are close to even ({pct} favour holding).")
        if biased:
            reasons.append(f"With {bias_name} detected, the cautious choice is to wait.")
            return "HOLD", reasons
        # The verdict never reads the investor's own words (Phase B3 quotes
        # them separately), so this wording must not suggest they were judged.
        reasons.append("No bias pattern showed up behind the sale, so your call stands.")
        return "SELL", reasons

    if intent == "hold":
        if p <= _WEAK:
            reasons.append(f"Holding beat selling in only {pct} of simulations.")
            if bias == "loss_aversion":
                reasons.append("Holding on to avoid realising a loss is a classic loss-aversion pattern.")
            return "SELL", reasons
        if p < 0.5:
            reasons.append(f"The simulations are close to even ({pct} favour holding), "
                           "so there's no strong case to sell.")
        else:
            reasons.append(f"Holding beat selling in {pct} of {horizon_years}-year simulations.")
        return "HOLD", reasons

    # buy_more
    if bias == "herd_behavior" or (biased and confidence >= _BIAS_CONFIDENT):
        reasons.append(f"Adding now shows signs of {bias_name} "
                       f"({confidence_band(confidence)} confidence).")
        reasons.append("Hold your current position and revisit when the signal fades.")
        return "HOLD", reasons
    if p >= 0.5:
        reasons.append(f"Staying invested beat exiting in {pct} of simulations.")
        reasons.append("No strong bias behind adding to the position.")
        return "BUY_MORE", reasons
    reasons.append(f"Staying invested beat exiting in only {pct} of simulations.")
    return "HOLD", reasons


async def recommend(ctx: PipelineContext) -> StepResult:
    d = ctx.decision
    bias = d.get("bias_detected") or "rational"
    confidence = float(d["bias_confidence"]) if d.get("bias_confidence") is not None else 0.0
    curves: dict[str, Any] = d.get("simulation_curves") or {}
    p_hold = curves.get("prob_hold_better")

    horizon = int(curves.get("horizon_years") or 20)
    verdict, reasons = decide(d["decision_intent"], bias, confidence, p_hold, horizon)
    # Phase B3: the case for each side — built after the verdict, never read by it.
    from .ai_help import allowed_for
    from .debate import debate
    from .ml_bridge import run_blocking

    async with ctx.db.rls_transaction(ctx.user_id) as conn:
        consent = await conn.fetchval("SELECT ai_consent FROM users WHERE user_id = $1", ctx.user_id)
    sides = await run_blocking(debate, d, allowed_for(consent))
    transcript = {
        "engine": "evidence_rules_v1" + ("+gemini_wording" if sides["llm_debate"] else ""),
        "llm_debate": sides["llm_debate"],
        "verdict": verdict,
        "reasons": reasons,
        "cases": sides["cases"],
        "inputs": {
            "intent": d["decision_intent"],
            "bias": bias,
            "bias_confidence": round(confidence, 4),
            "prob_hold_better": p_hold,
            "horizon_years": horizon,
            "opportunity_cost_inr": (
                float(d["opportunity_cost_inr"]) if d.get("opportunity_cost_inr") is not None else None
            ),
        },
    }
    return StepResult(
        updates={"debate_transcript": transcript, "recommendation": verdict},
        event={"verdict": verdict},
    )


register_step("debate", recommend)
