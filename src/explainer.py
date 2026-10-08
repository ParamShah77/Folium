"""
═══════════════════════════════════════════════════════════════════════════
 explainer.py — GAP 3: Decision-Centric Explainability Engine
═══════════════════════════════════════════════════════════════════════════

Turns the machine output of Objective 1 (bias detection + causal effects) and
Objective 2 (long-horizon Monte Carlo simulation) into ONE plain-language
story that any user can understand — in English or Hindi.

The pipeline:

    Obj 1 result ──┐
                   ├──> build_facts() ──> DecisionExplainer.explain() ──> 6 sections
    Obj 2 result ──┘         │                        │
                             │                        └──> optional LLM polish
                       every number the                     (fluency only, never
                       user will read, in                    new facts — see
                       one auditable dict                    llm_polish.py)

Why templates and not an LLM: the rupee figures in these explanations drive
real money decisions.  A template physically cannot invent a number.  The
optional polish layer is guarded so it cannot either.

Public API
----------
    build_facts(bias_result, sim_result, user_input, lang)  -> dict
    DecisionExplainer().explain(...)                        -> dict
    generate_complete_explanation(...)                      -> dict
    explain_from_inputs(user_input, lang)                   -> dict   (runs Obj1+Obj2)
    render_markdown(explanation)                            -> str
    find_jargon(text)                                       -> list[str]

Usage
-----
    from explainer import explain_from_inputs
    exp = explain_from_inputs({"user_id": 42, "current_wealth": 75_000,
                               "unrealized_gl": -0.15}, lang="en")
    print(exp["narrative"]["headline"])
"""

from __future__ import annotations

import logging
import re
from typing import Any

from jinja2 import Environment, StrictUndefined

try:  # package-relative (src.explainer)
    from . import explanation_templates as T
except ImportError:  # flat import (explainer)
    import explanation_templates as T  # type: ignore

logger = logging.getLogger(__name__)

# ── Jinja environment ────────────────────────────────────────────────────
# StrictUndefined: a missing fact is a bug we want to see in tests, not a
# silently blank sentence in front of a user.
_env = Environment(undefined=StrictUndefined, trim_blocks=False, lstrip_blocks=False)

#: Milestone years used in the "story of your money" section.
_MILESTONE_YEARS = (1, 5, 10)

#: Horizon (years) at or above which we treat the user as long-term.
_LONG_HORIZON = 15

#: Bias -> causal drivers we consider relevant, most important first.
#: Mirrors the mapping in integration._build_causal_chain() so the plain-language
#: explanation and the technical causal chain never disagree.
_BIAS_DRIVERS: dict[str, list[str]] = {
    "loss_aversion": ["loss_aversion", "unrealized_gl", "market_return"],
    "herd"         : ["crowd_ratio", "herd_sensitivity", "market_return"],
    "disposition"  : ["disposition_strength", "unrealized_gl", "holding_period_months"],
    "rational"     : ["investment_horizon", "risk_tolerance", "age"],
    "unknown"      : ["unrealized_gl", "market_return", "crowd_ratio"],
}


# ═══════════════════════════════════════════════════════════════════════════
# FACTS — the single source of truth for every number the user reads
# ═══════════════════════════════════════════════════════════════════════════

def build_facts(
    bias_result : dict,
    sim_result  : dict,
    user_input  : dict | None = None,
    lang        : str = "en",
) -> dict[str, Any]:
    """
    Assemble every value the templates need, pre-formatted for reading.

    Parameters
    ----------
    bias_result : dict
        Output of `integration.analyze_decision_realtime()` — needs
        `bias_type`, `confidence`, `is_biased`, and optionally `causal_effects`.
    sim_result : dict
        Output of `simulator.compare_hold_vs_sell()` — needs `hold`, `sell`,
        `comparison`, `horizon_years`, `yearly_hold_p50`, `yearly_sell_p50`.
    user_input : dict, optional
        The raw decision inputs (`unrealized_gl`, `crowd_ratio`,
        `has_emergency_fund`, `decision_intent`).
    lang : {'en', 'hi'}

    Returns
    -------
    dict — flat, JSON-serialisable, and safe to hash for an audit trail.
    """
    lang       = lang if lang in T.SUPPORTED_LANGS else "en"
    user_input = user_input or {}

    comparison = sim_result.get("comparison", {})
    hold       = sim_result.get("hold", {})
    sell       = sim_result.get("sell", {})
    profile    = sim_result.get("user_profile", {})
    sim_inputs = sim_result.get("inputs", {})

    # ── Who and how long ─────────────────────────────────────────────────
    horizon_years = int(sim_result.get("horizon_years", profile.get("investment_horizon", 15)))
    n_sim         = int(sim_inputs.get("n_simulations", 1000))

    # ── Where they stand right now ───────────────────────────────────────
    gl = float(user_input.get("unrealized_gl", sim_inputs.get("unrealized_gl", 0.0)))
    current_wealth = float(sim_inputs.get("current_wealth", user_input.get("current_wealth", 0.0)))
    crowd = float(user_input.get("crowd_ratio", 0.5))

    # ── The bias read ────────────────────────────────────────────────────
    bias_type = str(bias_result.get("bias_type", "unknown"))
    if bias_type not in T.TEMPLATES[lang]:
        bias_type = "unknown"
    confidence = float(bias_result.get("confidence", 0.0))
    is_biased  = bool(bias_result.get("is_biased", bias_type not in ("rational", "unknown")))

    # ── The money ────────────────────────────────────────────────────────
    # We narrate the TYPICAL outcome (the middle path), not the average.
    # Wealth after 20 years is heavily right-skewed, so the average is pulled
    # up by a handful of extreme runs and can sit far above where most people
    # actually land.  Quoting the average here would also contradict the
    # year-by-year table below, which is a median path.  Obj 2 keeps its
    # mean-based opportunity cost — that still travels in `technical`.
    hold_mean = float(hold.get("mean", 0.0))
    sell_mean = float(sell.get("mean", 0.0))
    hold_typ  = _typical_outcome(sim_result.get("yearly_hold_p50"), hold)
    sell_typ  = _typical_outcome(sim_result.get("yearly_sell_p50"), sell)

    better    = str(comparison.get("better_decision", "HOLD" if hold_mean >= sell_mean else "SELL"))
    prob_hold = float(comparison.get("prob_hold_better", 0.5))

    # If the typical and average outcomes point at different decisions (rare,
    # and only in genuinely borderline cases), fall back to the averages the
    # recommendation is actually based on, so the story can't contradict the
    # advice it ends with.
    if (hold_typ >= sell_typ) != (better == "HOLD"):
        hold_typ, sell_typ = hold_mean, sell_mean

    gap_inr = abs(hold_typ - sell_typ)

    facts: dict[str, Any] = {
        "lang"            : lang,

        # bias
        "bias_type"       : bias_type,
        "bias_plain"      : T.BIAS_PLAIN[lang].get(bias_type, T.BIAS_PLAIN[lang]["unknown"]),
        "is_biased"       : is_biased,
        "resisted"        : _is_resisted(bias_type, user_input, gl),
        "confidence"      : round(confidence, 4),
        "confidence_pct"  : T.format_pct(confidence),
        "confidence_word" : T.confidence_word(confidence, lang),

        # position
        "gl"              : round(gl, 4),
        "gl_pct"          : T.format_pct(gl),
        "gl_is_gain"      : gl >= 0,
        "crowd_pct"       : T.format_pct(crowd),
        "horizon_years"   : horizon_years,
        "current_wealth"  : current_wealth,
        "current_wealth_str": T.format_inr(current_wealth, lang),
        "has_emergency_fund": bool(int(user_input.get("has_emergency_fund", 1))),

        # simulation
        "n_sim"           : n_sim,
        "n_sim_plain"     : T._indian_group(n_sim),
        "hold_mean"       : T.format_inr(hold_typ, lang),
        "hold_bad"        : T.format_inr(hold.get("p10", 0.0), lang),
        "hold_good"       : T.format_inr(hold.get("p90", 0.0), lang),
        "sell_mean"       : T.format_inr(sell_typ, lang),
        "sell_bad"        : T.format_inr(sell.get("p10", 0.0), lang),
        "sell_good"       : T.format_inr(sell.get("p90", 0.0), lang),
        "gap"             : T.format_inr(gap_inr, lang),
        "gap_pct"         : T.format_pct(gap_inr / current_wealth) if current_wealth else "0%",
        "better_decision" : better,
        "better_is_hold"  : better == "HOLD",
        "prob_hold_better_100": int(round(prob_hold * 100)),

        # raw numbers kept for the audit trail (never rendered directly)
        "_raw": {
            "hold_typical": hold_typ, "sell_typical": sell_typ,
            "hold_mean": hold_mean, "sell_mean": sell_mean,
            "typical_gap_inr": gap_inr,
            "opportunity_cost_inr": float(comparison.get("opportunity_cost_inr", hold_mean - sell_mean)),
            "prob_hold_better": prob_hold,
        },
    }

    facts["milestones"] = _build_milestones(sim_result, horizon_years, lang)
    facts.update(_build_mechanics(sim_result, hold, sell, current_wealth, lang))
    facts.update(_build_drivers(bias_result, bias_type, gl, lang))

    dip = _find_dip(sim_result.get("yearly_hold_p50"))
    facts["dip_year_prev"], facts["dip_year"] = dip if dip else (None, None)
    facts["gap_narrows_late"] = _gap_narrows_late(sim_result)

    facts["year_table"] = _build_year_table(sim_result, horizon_years, facts, lang)
    facts.update(_render_fragments(facts, lang))
    return facts


def _build_mechanics(sim_result: dict, hold: dict, sell: dict,
                     current_wealth: float, lang: str) -> dict:
    """
    The facts that answer "what ARE these two numbers, and how were they worked out?"

    Selling is not simply leaving one investment. In the simulation it does
    three separate things, and only the first is obvious to the user:

      1. realises the gain or loss (95% of it) and pays ~5% in costs
      2. reinvests the proceeds at 30% of the original stock allocation
      3. so the money then compounds at closer to the bond rate

    Step 2 is what actually opens the gap over a long horizon, and it was
    invisible in the explanation before. These facts make it sayable.
    """
    assumptions = sim_result.get("assumptions", {}) or {}

    hold_start = float(hold.get("starting_wealth", current_wealth))
    sell_start = float(sell.get("starting_wealth", hold_start))
    hold_alloc = float(hold.get("stock_allocation", 0.0))
    sell_alloc = float(sell.get("stock_allocation", 0.0))

    # What selling costs before a single rupee of growth happens.
    day_one_cost = max(0.0, hold_start - sell_start)

    return {
        "position_today"    : T.format_inr(hold_start, lang),
        "sell_proceeds"     : T.format_inr(sell_start, lang),
        "day_one_cost"      : T.format_inr(day_one_cost, lang),
        "has_day_one_cost"  : day_one_cost >= 1,
        "hold_stock_pct"    : T.format_pct(hold_alloc),
        "hold_bond_pct"     : T.format_pct(1 - hold_alloc),
        "sell_stock_pct"    : T.format_pct(sell_alloc),
        "sell_bond_pct"     : T.format_pct(1 - sell_alloc),
        "bond_rate_pct"     : T.format_pct(float(assumptions.get("bond_mean", 0.055)), 1),
        "sell_cost_pct"     : T.format_pct(float(assumptions.get("transaction_cost", 0.05))),
        "invested_amount"   : T.format_inr(current_wealth, lang),
        **_v2_mechanics(sim_result, lang),
    }


_DEST_WORDS = {
    "en": {"fixed_deposits": "fixed deposits", "gold": "gold", "savings": "savings"},
    "hi": {"fixed_deposits": "एफ़डी", "gold": "सोने", "savings": "बचत खाते"},
}


def _v2_mechanics(sim_result: dict, lang: str) -> dict:
    """Facts only simulation v2 has: tax on the sale, where the money goes, growth rates.

    ``v2`` is False for v1 results, and the templates then keep their v1 wording.
    """
    if sim_result.get("engine") != "monte_carlo_v2":
        return {"v2": False, "has_sale_tax": False, "sale_tax_short": False}
    a = sim_result.get("assumptions", {}) or {}
    sale = sim_result.get("sale", {}) or {}
    inputs = sim_result.get("inputs", {}) or {}
    words = _DEST_WORDS[lang]
    parts = [(k, w) for k, w in (sale.get("destination") or {}).items() if w > 0]
    parts.sort(key=lambda kv: kv[1], reverse=True)
    if lang == "hi":
        bits = [f"{T.format_pct(w)} {words[k]} में" for k, w in parts]
        joiner = " और "
    else:
        bits = [f"{T.format_pct(w)} into {words[k]}" for k, w in parts]
        joiner = " and "
    destination = (", ".join(bits[:-1]) + joiner + bits[-1]) if len(bits) > 1 else (bits[0] if bits else "")
    single_stock = inputs.get("asset_type", "equity") == "equity"
    slab = float(a.get("slab_rate_on_interest", 0.0))
    return {
        "v2": True,
        "is_single_stock": single_stock,
        "sell_destination": destination,
        "sale_tax": T.format_inr(float(sale.get("tax", 0.0)), lang),
        "has_sale_tax": float(sale.get("tax", 0.0)) >= 1,
        "sale_tax_short": sale.get("tax_kind") == "short_term",
        "equity_growth_pct": T.format_pct(float(a.get("equity_growth", 0.11))),
        "gold_growth_pct": T.format_pct(float(a.get("gold_growth", 0.09))),
        "fd_rate_pct": f"{float(a.get('fd_rate', 0.0675)) * 100:.2f}".rstrip("0").rstrip(".") + "%",
        "interest_taxed": slab > 0,
        "slab_pct": T.format_pct(slab, 1),
        "history_span": _history_span(str(a.get("history", "")), lang),
    }


_HI_MONTHS = {"Jan": "जनवरी", "Feb": "फ़रवरी", "Mar": "मार्च", "Apr": "अप्रैल", "May": "मई", "Jun": "जून",
              "Jul": "जुलाई", "Aug": "अगस्त", "Sep": "सितंबर", "Oct": "अक्टूबर", "Nov": "नवंबर", "Dec": "दिसंबर"}


def _history_span(span: str, lang: str) -> str:
    """"Oct 2007 to Sep 2026" -> "अक्टूबर 2007 से सितंबर 2026" in Hindi."""
    if lang != "hi" or " to " not in span:
        return span
    start, end = span.split(" to ", 1)
    def month(text: str) -> str:
        mon, _, year = text.partition(" ")
        return f"{_HI_MONTHS.get(mon, mon)} {year}".strip()
    return f"{month(start)} से {month(end)}"


def _year_rows(horizon: int) -> list[int]:
    """
    Which years to print.

    Every year for a horizon a person can hold in their head; for longer
    horizons, every year for the first decade and then five-year steps, so the
    table stays a table rather than a wall of numbers. The final year is
    always included — it is the one the rest of the explanation quotes.
    """
    if horizon <= 15:
        years = list(range(1, horizon + 1))
    else:
        years = list(range(1, 11)) + list(range(15, horizon, 5))
    if horizon not in years:
        years.append(horizon)
    return sorted(set(years))


def _build_year_table(sim_result: dict, horizon: int, facts: dict, lang: str) -> str:
    """
    The year-by-year table, as Markdown.

    Starts at "today" so the two paths visibly begin from different amounts —
    without that row, the reader has no idea selling already cost them
    something before any growth happened.
    """
    hold_path = sim_result.get("yearly_hold_p50") or []
    sell_path = sim_result.get("yearly_sell_p50") or []
    if not hold_path:
        return ""

    head = T.TABLE_HEADERS[lang]
    lines = [
        f"| {head['year']} | {head['hold']} | {head['sell']} | {head['gap']} |",
        "|---|---|---|---|",
    ]

    def row(label: str, hold_value: float, sell_value: float) -> str:
        # Exact amounts here, not the rounded lakh/crore form: in a table the
        # reader compares one row against the next, and rounding would print
        # two different years as the same "₹1.2 lakh".
        gap  = hold_value - sell_value
        sign = "+" if gap >= 0 else "-"
        return (f"| {label} | {T.format_inr_exact(hold_value, lang)} | "
                f"{T.format_inr_exact(sell_value, lang)} | "
                f"{sign}{T.format_inr_exact(abs(gap), lang)} |")

    # Today: the two starting positions, before any growth.
    hold_start = float(sim_result.get("hold", {}).get("starting_wealth", hold_path[0]))
    sell_start = float(sim_result.get("sell", {}).get("starting_wealth", sell_path[0] if sell_path else 0))
    lines.append(row(head["today"], hold_start, sell_start))

    for year in _year_rows(horizon):
        idx = min(year, len(hold_path)) - 1
        if idx < 0:
            continue
        hold_value = float(hold_path[idx])
        sell_value = float(sell_path[idx]) if idx < len(sell_path) else 0.0
        lines.append(row(str(year), hold_value, sell_value))

    return "\n".join(lines)


def _typical_outcome(median_path: list | None, stats: dict) -> float:
    """
    The outcome a typical person actually lands on: the final point of the
    median wealth path.  Falls back to the median of final outcomes, then the
    mean, so partial simulator output still produces a sensible number.
    """
    if median_path:
        return float(median_path[-1])
    for key in ("median", "p50", "mean"):
        if key in stats:
            return float(stats[key])
    return 0.0


def _is_resisted(bias_type: str, user_input: dict, gl: float) -> bool:
    """
    True when the user is susceptible to a bias but their stated intent goes
    against it — worth praising rather than warning about.

    Mirrors the logic already used in dashboard.page_unified_pipeline().
    """
    intent = str(user_input.get("decision_intent", "")).lower()
    if "hold" not in intent:
        return False
    if bias_type in ("herd", "loss_aversion"):
        return True
    if bias_type == "disposition" and gl > 0:
        return True
    return False


def _build_milestones(sim_result: dict, horizon_years: int, lang: str) -> list[dict]:
    """
    Year-by-year checkpoints for the "story of your money" section.

    Uses years 1 / 5 / 10 / horizon, skipping any beyond the user's horizon.
    """
    hold_path = sim_result.get("yearly_hold_p50") or []
    sell_path = sim_result.get("yearly_sell_p50") or []
    if not hold_path:
        return []

    years = [y for y in _MILESTONE_YEARS if y < horizon_years]
    years.append(horizon_years)

    milestones = []
    for year in years:
        idx = min(year, len(hold_path)) - 1
        if idx < 0:
            continue
        h = float(hold_path[idx])
        s = float(sell_path[idx]) if idx < len(sell_path) else 0.0
        diff = h - s
        frag = T.FRAGMENTS[lang]["gap_ahead" if diff >= 0 else "gap_behind"]
        milestones.append({
            "year"       : year,
            "hold"       : T.format_inr(h, lang),
            "sell"       : T.format_inr(s, lang),
            "gap"        : abs(diff) >= 1,
            "gap_phrase" : _env.from_string(frag).render(amount=T.format_inr(abs(diff), lang)),
        })
    return milestones


#: A year-on-year fall this large is worth naming rather than leaving the
#: reader to wonder why the table suddenly goes backwards.
_DIP_THRESHOLD = 0.10


def _find_dip(median_path: list | None) -> tuple[int, int] | None:
    """
    Find the sharpest year-on-year fall in the median wealth path.

    The synthetic market paths contain deliberate crashes, so a table can drop
    in the middle and then recover. Left unexplained that looks like an error;
    explained, it is the single most useful thing in the table — it shows the
    reader exactly the moment when selling feels most obviously right.

    Returns (year_before, year_of_dip) or None if nothing significant falls.
    """
    if not median_path or len(median_path) < 2:
        return None

    worst_drop, worst_index = 0.0, None
    for i in range(1, len(median_path)):
        previous = float(median_path[i - 1])
        if previous <= 0:
            continue
        drop = (previous - float(median_path[i])) / previous
        if drop > worst_drop:
            worst_drop, worst_index = drop, i

    if worst_index is None or worst_drop < _DIP_THRESHOLD:
        return None
    return worst_index, worst_index + 1        # 0-based index -> year numbers


def _gap_narrows_late(sim_result: dict) -> bool:
    """
    True when the final gap between the two paths is well below its peak.

    Used to pick an honest closing sentence: the compounding story ("small
    early, large later") is the common case, but a late crash can shrink the
    gap, and the closing must not contradict the table it follows.
    """
    hold_path = sim_result.get("yearly_hold_p50") or []
    sell_path = sim_result.get("yearly_sell_p50") or []
    if len(hold_path) < 3 or len(sell_path) < 3:
        return False

    gaps = [h - s for h, s in zip(hold_path, sell_path)]
    peak = max(gaps)
    return peak > 0 and gaps[-1] < 0.8 * peak


def _build_drivers(bias_result: dict, bias_type: str, gl: float, lang: str) -> dict:
    """
    Rank the causal drivers behind this decision and translate them into plain
    phrases for section 5.

    Falls back to a sensible per-bias ordering when causal effects are
    unavailable (e.g. results/causal_effects.pkl missing) so the explanation
    degrades in quality, never in correctness.
    """
    plain_map = T.DRIVER_PLAIN[lang]
    candidates = _BIAS_DRIVERS.get(bias_type, _BIAS_DRIVERS["unknown"])
    effects    = bias_result.get("causal_effects") or {}

    # The first entry of _BIAS_DRIVERS is the bias's signature driver, and it
    # stays first. Section 5 goes on to say "a decision driven by how much a
    # loss stings, rather than by anything that changed about the investment
    # itself" — so leading with, say, recent market movement would have the
    # narrative contradict itself one sentence later. Causal magnitude ranks
    # the supporting drivers, where it changes emphasis but not the logic.
    signature, rest = candidates[0], list(candidates[1:])
    if effects:
        rest = (sorted((d for d in rest if d in effects),
                       key=lambda d: abs(float(effects[d].get("causal_effect", 0.0))),
                       reverse=True)
                + [d for d in rest if d not in effects])
    ranked = [signature] + rest

    def _plain(name: str) -> str:
        if name == "unrealized_gl" and gl >= 0:
            return plain_map["unrealized_gl_up"]
        return plain_map.get(name, name.replace("_", " "))

    phrases = [_plain(d) for d in ranked][:3]
    if not phrases:
        phrases = [_plain("unrealized_gl")]

    top, others = phrases[0], phrases[1:]

    if len(others) >= 2:
        sentence = _env.from_string(T.FRAGMENTS[lang]["other_drivers_two"]).render(
            d1=others[0], d2=others[1])
    elif len(others) == 1:
        sentence = _env.from_string(T.FRAGMENTS[lang]["other_drivers_one"]).render(d1=others[0])
    else:
        sentence = ""

    joiner = " and " if lang == "en" else " और "
    return {
        "top_driver"            : top,
        "other_drivers"         : others,
        "other_drivers_sentence": sentence,
        "other_drivers_plain"   : joiner.join(others),
    }


def _render_fragments(facts: dict, lang: str) -> dict:
    """
    Render the code-selected sentence fragments (action line, horizon line,
    emergency-fund line, honesty line, story closing) that the shared
    templates splice in.
    """
    F = T.FRAGMENTS[lang]

    if facts["better_is_hold"] and facts["resisted"]:
        action_key = "action_hold_resisted"
    elif facts["better_is_hold"]:
        action_key = "action_hold"
    else:
        action_key = "action_sell"

    horizon_key   = "horizon_long" if facts["horizon_years"] >= _LONG_HORIZON else "horizon_short"
    emergency_key = "emergency_yes" if facts["has_emergency_fund"] else "emergency_no"

    # "Small early, large later" is the usual compounding story, but it is not
    # always what the table shows: a crash near the end can pull the invested
    # column back down and shrink the gap. Saying it anyway would have the
    # closing contradict the numbers directly above it.
    if not facts["better_is_hold"]:
        closing_key = "story_closing_sell"
    elif facts.get("gap_narrows_late"):
        closing_key = "story_closing_hold_late_dip"
    else:
        closing_key = "story_closing_hold"

    def r(key: str) -> str:
        return _env.from_string(F[key]).render(**facts)

    return {
        "action_line"     : r(action_key),
        "horizon_line"    : r(horizon_key),
        "emergency_line"  : r(emergency_key),
        "confidence_line" : r("confidence_line"),
        "story_closing"   : r(closing_key),
        "dip_note"        : r("dip_note") if facts.get("dip_year") else "",
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE EXPLAINER
# ═══════════════════════════════════════════════════════════════════════════

class DecisionExplainer:
    """
    Renders the six-section plain-language explanation.

    Parameters
    ----------
    use_llm : bool | None
        None (default) = respect the EXPLAINER_LLM environment flag.
        False          = never call an LLM (fully deterministic).
        True           = attempt polish, still falling back to templates on
                         any failure or if the numeric guard trips.
    """

    def __init__(self, use_llm: bool | None = None):
        self.use_llm = use_llm

    # ── main entry point ─────────────────────────────────────────────────
    def explain(
        self,
        bias_result : dict,
        sim_result  : dict,
        user_input  : dict | None = None,
        lang        : str = "en",
    ) -> dict[str, Any]:
        """
        Returns
        -------
        dict with keys:
            lang, bias_type, sections (ordered list of {key, title, text}),
            narrative (dict section->text), headline, recommendation,
            facts, polished (bool), reading_level (dict)
        """
        lang  = lang if lang in T.SUPPORTED_LANGS else "en"
        facts = build_facts(bias_result, sim_result, user_input, lang)

        narrative: dict[str, str] = {}
        for section in T.SECTIONS:
            template = self._template_for(section, facts["bias_type"], lang)
            narrative[section] = _env.from_string(template).render(**facts).strip()

        polished = False
        if self._llm_wanted():
            narrative, polished = _apply_polish(narrative, lang)

        return {
            "lang"          : lang,
            "lang_name"     : T.LANG_NAMES[lang],
            "bias_type"     : facts["bias_type"],
            "is_biased"     : facts["is_biased"],
            "resisted"      : facts["resisted"],
            "headline"      : narrative["headline"],
            "recommendation": facts["action_line"],
            "narrative"     : narrative,
            "sections"      : [
                {"key": s, "title": T.SECTION_TITLES[lang][s], "text": narrative[s]}
                for s in T.SECTIONS
            ],
            "facts"         : facts,
            "polished"      : polished,
            "reading_level" : reading_level(" ".join(narrative.values()), lang),
        }

    # ── helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _template_for(section: str, bias_type: str, lang: str) -> str:
        bias_templates = T.TEMPLATES[lang].get(bias_type, T.TEMPLATES[lang]["unknown"])
        if section in bias_templates:
            return bias_templates[section]
        return T.SHARED[lang][section]

    def _llm_wanted(self) -> bool:
        """
        Whether to attempt a polish pass. Any problem answering that question
        — a missing module, an unreadable .env — answers "no" rather than
        raising, because a configuration fault must never cost a user their
        explanation.
        """
        if self.use_llm is False:
            return False
        try:
            try:
                from . import llm_polish  # type: ignore
            except ImportError:
                import llm_polish  # type: ignore
            return True if self.use_llm else llm_polish.is_enabled()
        except Exception as exc:                   # noqa: BLE001
            logger.warning("Could not determine LLM availability (%s) — using templates", exc)
            return False


def _apply_polish(narrative: dict[str, str], lang: str) -> tuple[dict[str, str], bool]:
    """
    Run the optional LLM fluency pass over the whole explanation in one request.

    One request, not one per section: Gemini's free tier allows five requests a
    minute, and an explanation has six sections. Each section is still verified
    separately on the way back, so a bad rewrite costs only that section.

    Any failure returns the template text unchanged — the user never sees an
    error, and never sees an invented number.
    """
    try:
        try:
            from . import llm_polish  # type: ignore
        except ImportError:
            import llm_polish  # type: ignore

        out = llm_polish.polish_sections(narrative, lang=lang)
        return out, any(out[key] != narrative[key] for key in narrative)

    except Exception as exc:                       # noqa: BLE001 — never break the user
        logger.warning("LLM polish unavailable, using templates: %s", exc)
        return narrative, False


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE WRAPPERS
# ═══════════════════════════════════════════════════════════════════════════

def generate_complete_explanation(
    bias_result : dict,
    sim_result  : dict,
    user_input  : dict | None = None,
    lang        : str = "en",
    use_llm     : bool | None = None,
) -> dict[str, Any]:
    """
    Full explanation package: narrative + chart payloads + technical detail.

    The `technical` block holds everything the dashboard hides behind the
    "Technical details" expander — available for anyone who wants it, out of
    the way of everyone who doesn't.
    """
    explanation = DecisionExplainer(use_llm=use_llm).explain(
        bias_result, sim_result, user_input, lang)

    explanation["charts"] = {
        "years"          : sim_result.get("years", []),
        "hold_p50"       : sim_result.get("yearly_hold_p50", []),
        "hold_p10"       : sim_result.get("yearly_hold_p10", []),
        "hold_p90"       : sim_result.get("yearly_hold_p90", []),
        "sell_p50"       : sim_result.get("yearly_sell_p50", []),
        "milestones"     : explanation["facts"]["milestones"],
    }
    explanation["technical"] = {
        "confidence"        : bias_result.get("confidence"),
        "all_probabilities" : bias_result.get("all_probabilities", {}),
        "risk_score"        : bias_result.get("risk_score"),
        "causal_chain"      : bias_result.get("causal_chain", []),
        "shap_explanation"  : bias_result.get("shap_explanation", []),
        "comparison"        : sim_result.get("comparison", {}),
        "hold_stats"        : sim_result.get("hold", {}),
        "sell_stats"        : sim_result.get("sell", {}),
    }
    return explanation


#: Sections that describe the person and the bias, and so need no simulation.
BIAS_ONLY_SECTIONS = ("headline", "whats_happening", "why_we_say_this")


def explain_bias_only(
    bias_result : dict,
    user_input  : dict | None = None,
    lang        : str = "en",
    use_llm     : bool | None = None,
) -> dict[str, Any]:
    """
    The plain-language part that needs no Monte Carlo run.

    Sections 3, 4 and 6 talk about money over time, so they require Objective
    2.  Sections 1, 2 and 5 describe the person and the bias, and can be
    rendered from Objective 1 alone — which is what the Decision Analysis
    page needs, since it does no simulation.
    """
    explanation = DecisionExplainer(use_llm=use_llm).explain(
        bias_result, sim_result={}, user_input=user_input, lang=lang)

    explanation["sections"] = [s for s in explanation["sections"]
                               if s["key"] in BIAS_ONLY_SECTIONS]
    explanation["narrative"] = {k: v for k, v in explanation["narrative"].items()
                                if k in BIAS_ONLY_SECTIONS}
    explanation["partial"]   = True     # no money figures in this variant
    # The HOLD/SELL recommendation is a simulation result. Without one there
    # is nothing to recommend, and a default would be advice we didn't earn.
    explanation["recommendation"] = ""
    explanation["reading_level"] = reading_level(
        " ".join(explanation["narrative"].values()), lang)
    return explanation


def explain_from_inputs(
    user_input : dict,
    lang       : str = "en",
    use_llm    : bool | None = None,
) -> dict[str, Any]:
    """
    End-to-end convenience: runs Objective 1 and Objective 2, then explains.

    `user_input` needs at least `user_id` and `current_wealth`; everything
    else falls back to the same defaults the two engines already use.
    """
    try:
        from .integration import analyze_decision_realtime
        from .simulator import get_simulator
    except ImportError:
        from integration import analyze_decision_realtime  # type: ignore
        from simulator import get_simulator                # type: ignore

    bias_result = analyze_decision_realtime(user_input)
    sim_result  = get_simulator().compare_hold_vs_sell(
        user_id        = user_input.get("user_id", 0),
        current_wealth = float(user_input.get("current_wealth", 100_000)),
        unrealized_gl  = float(user_input.get("unrealized_gl", 0.0)),
        n_simulations  = user_input.get("n_simulations"),
    )
    return generate_complete_explanation(bias_result, sim_result, user_input, lang, use_llm)


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def render_markdown(explanation: dict, title: str | None = None) -> str:
    """
    Render an explanation as a self-contained Markdown document — used by the
    downloadable report and by the notebook.
    """
    lang = explanation.get("lang", "en")
    if title is None:
        title = ("Your Decision Explained" if lang == "en"
                 else "आपके फ़ैसले की व्याख्या")

    lines = [f"# {title}", ""]
    for section in explanation["sections"]:
        lines.append(f"## {section['title']}")
        lines.append("")
        lines.append(section["text"])
        lines.append("")

    footer = ("_Generated by the Causal Financial Decision Intelligence System. "
              "Estimates only — not financial advice._"
              if lang == "en" else
              "_कारण-आधारित वित्तीय निर्णय बुद्धिमत्ता प्रणाली द्वारा तैयार। "
              "ये केवल अनुमान हैं — वित्तीय सलाह नहीं।_")
    lines.append("---")
    lines.append(footer)
    return "\n".join(lines)


# ── jargon guard ─────────────────────────────────────────────────────────
_JARGON_PATTERNS = [
    (term, re.compile(rf"(?<![\w]){re.escape(term)}(?![\w])", re.IGNORECASE))
    for term in T.JARGON_BLOCKLIST
]


def find_jargon(text: str) -> list[str]:
    """
    Return any blocklisted technical terms found in user-facing text.
    Used by tests and by scripts/evaluate_explanations.py.
    """
    return [term for term, pattern in _JARGON_PATTERNS if pattern.search(text)]


def reading_level(text: str, lang: str = "en") -> dict[str, Any]:
    """
    Readability measurement.

    English uses Flesch Reading Ease (target >= 60, roughly 8th grade).
    Flesch is undefined for Devanagari — its syllable model is built for
    English — so Hindi uses average words per sentence instead (target <= 20).
    """
    sentences = [s for s in re.split(r"[.!?।\n]+", text) if s.strip()]
    words     = [w for w in re.split(r"\s+", text) if w.strip()]
    avg_wps   = (len(words) / len(sentences)) if sentences else 0.0

    result: dict[str, Any] = {
        "lang"               : lang,
        "words"              : len(words),
        "sentences"          : len(sentences),
        "avg_words_per_sentence": round(avg_wps, 1),
    }

    if lang == "en":
        try:
            import textstat
            score = float(textstat.flesch_reading_ease(text))
            result["flesch_reading_ease"] = round(score, 1)
            result["meets_target"] = score >= 60
        except Exception:                          # textstat not installed
            result["flesch_reading_ease"] = None
            result["meets_target"] = avg_wps <= 20
    else:
        result["flesch_reading_ease"] = None       # not meaningful for Devanagari
        result["meets_target"] = avg_wps <= 20

    return result


__all__ = [
    "DecisionExplainer", "build_facts", "generate_complete_explanation",
    "explain_from_inputs", "render_markdown", "find_jargon", "reading_level",
]
