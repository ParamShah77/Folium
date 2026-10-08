"""Phase B3 — the case for each side, built from the analysis's own numbers.

The recommendation step (``recommendation.py``) decides Hold / Sell / Buy more
from the evidence. This module only *argues*: one case for each choice, so the
investor sees the strongest reasons on both sides before they act.

* **Built from numbers, always.** Every point is a sentence filled in from the
  stored analysis: how often holding won, the typical gap, tax on selling
  today, the bad-case outcomes, the size of the holding, the stock's own
  swings, the horizon, the pattern found, and a cash need the investor stated.
* **Worded by Gemini, sometimes.** With the investor's consent and a key, Gemini
  may rewrite each case in plainer prose. The rewrite is kept only if it adds
  no number or rupee amount that wasn't in the original (the explanation
  engine's guard, ``src/llm_polish.guard_ok``); otherwise the number-built
  text stands.
* **It cannot change the verdict.** The cases are produced after the verdict
  and are never read by it.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from .explainer import inr
from .ml_bridge import ensure_src_importable

_BIAS_NAMES = {"loss_aversion": "loss aversion", "herd_behavior": "following the crowd",
               "disposition_effect": "the disposition effect"}


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def build_cases(d: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Two cases, each a title and its points, from the stored analysis."""
    curves = d.get("simulation_curves") or {}
    if isinstance(curves, str):
        curves = json.loads(curves)
    facts = d.get("comment_facts") or {}
    if isinstance(facts, str):
        facts = json.loads(facts)
    intent = d.get("decision_intent")
    bias = d.get("bias_detected") or "rational"
    p = curves.get("prob_hold_better")
    horizon = curves.get("horizon_years") or 20
    years = f"{horizon}-year" if horizon != 1 else "1-year"
    gap = float(d.get("opportunity_cost_inr") or 0.0)
    sale = curves.get("sale") or {}
    risk = curves.get("holding_risk") or {}
    context = d.get("portfolio_context") or {}
    if isinstance(context, str):
        context = json.loads(context)
    hold_bad, sell_bad = d.get("hold_p10_20y"), d.get("sell_p10_20y")

    stay: list[str] = []
    leave: list[str] = []
    if p is not None:
        if p >= 0.5:
            stay.append(f"Holding came out ahead in {_pct(p)} of {years} futures"
                        + (f", typically by {inr(gap)} after tax." if gap > 0 else "."))
        if p < 1:
            leave.append(f"Selling came out ahead in {_pct(1 - p)} of {years} futures"
                         + (f", typically by {inr(-gap)} after tax." if gap < 0 else "."))
    if float(sale.get("tax") or 0) >= 1:
        kind = "short-term" if sale.get("tax_kind") == "short_term" else "long-term"
        stay.append(f"Selling today costs {inr(float(sale['tax']))} in {kind} capital-gains tax straight away.")
    if horizon >= 7:
        stay.append(f"You have {horizon} years before you need the money, time for a fall to recover.")
    elif horizon <= 3:
        leave.append(f"You need the money within {horizon} year{'s' if horizon != 1 else ''}, little time to recover from a fall.")
    if bias in _BIAS_NAMES and intent in ("sell", "buy_more"):
        stay.append(f"The urge to {'sell' if intent == 'sell' else 'add'} shows signs of {_BIAS_NAMES[bias]}.")
    if bias in _BIAS_NAMES and intent == "hold":
        leave.append(f"Holding on shows signs of {_BIAS_NAMES[bias]}.")
    if hold_bad is not None and sell_bad is not None and float(hold_bad) < float(sell_bad):
        leave.append(f"If things go badly, holding leaves about {inr(float(hold_bad))} against "
                     f"{inr(float(sell_bad))} after selling.")
    if risk.get("asset_type") == "equity" and risk.get("specific_vol"):
        leave.append(f"A single company's shares swing more than the market: about "
                     f"{round(float(risk['specific_vol']) * 100)}% a year of their own.")
    share = context.get("position_share")
    if share is not None and float(share) >= 0.2:
        leave.append(f"This holding is {round(float(share) * 100)}% of your savings and investments; "
                     "selling some would spread the risk.")
    if facts.get("cash_need") and facts.get("cash_need_quote"):
        leave.append(f'You said you need the money: "{facts["cash_need_quote"]}"')

    if intent == "buy_more":
        titles = ("The case for adding", "The case for holding off")
        stay = [s.replace("Holding came out ahead", "Staying invested came out ahead") for s in stay]
        leave = [s.replace("Selling came out ahead", "Exiting came out ahead") for s in leave]
    else:
        titles = ("The case for holding", "The case for selling")
    return [{"side": "stay", "title": titles[0], "points": stay},
            {"side": "leave", "title": titles[1], "points": leave}]


_PROMPT = """Rewrite each case below as 2 or 3 plain, friendly sentences for an Indian retail investor.
Keep every fact. Do not add, remove or change any number, percentage or rupee amount.
Do not give advice beyond what is written. Return JSON only: {{"stay": "...", "leave": "..."}}

stay ({stay_title}): {stay}
leave ({leave_title}): {leave}"""


def word_with_ai(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Gemini's wording, case by case, kept only where it passes the number guard."""
    ensure_src_importable()
    try:
        from src import llm_polish
    except ImportError:
        return cases, False
    original = {c["side"]: " ".join(c["points"]) for c in cases}
    if not any(original.values()):
        return cases, False
    reply = llm_polish.complete(_PROMPT.format(
        stay_title=cases[0]["title"], stay=original["stay"] or "(nothing)",
        leave_title=cases[1]["title"], leave=original["leave"] or "(nothing)"), timeout=20)
    if not reply:
        return cases, False
    try:
        data = json.loads(reply)
    except ValueError:
        return cases, False
    used = False
    out = []
    for c in cases:
        text = data.get(c["side"]) if isinstance(data, dict) else None
        if isinstance(text, str) and original[c["side"]] and llm_polish.guard_ok(original[c["side"]], text):
            out.append({**c, "text": text.strip(), "worded_by": "gemini"})
            used = True
        else:
            out.append(c)
    return out, used


def debate(d: Mapping[str, Any], use_ai: bool) -> dict[str, Any]:
    cases = build_cases(d)
    used = False
    if use_ai:
        cases, used = word_with_ai(cases)
    for c in cases:
        c.setdefault("text", " ".join(c["points"]))
        c.setdefault("worded_by", "numbers")
    return {"cases": cases, "llm_debate": used}
