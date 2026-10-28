"""Phase 5C — causal explanation, replacing ``stub_steps._explanation``.

Objective 3 claims the system shows *how a decision causally influences
long-term outcomes*. Before this step those three facts — which bias, what it
causally does, what it costs in 20 years — lived in three separate places.
This step joins them into one ``explainer_output`` a person can read:

  bias (5A, SHAP)  ->  causal effect (DoWhy)  ->  20-year rupee consequence (5B)
                   ->  the intervention the causal model says helps most

**Causal numbers are precomputed, not re-estimated.** ``results/causal_v4.json``
(Phase A4, ``src/causal_v4.py``) holds effects estimated from dataset v4 and
checked against the true mechanism that generated it, per situation and
action: how likely people in this situation are to take this action, and how
much a habit changes that. Without it, the older ``results/causal_effects.pkl``
(population-level DoWhy estimates on the v1-v3 data) is used. Estimating DoWhy per decision would take minutes and
would not mean anything more — the effect of loss aversion on selling is a
population quantity. The per-decision part is *which* effect applies and what
it is worth to this investor.

The narrative is template-built from those numbers, not generated, so every
sentence is traceable to a stored value.
"""
from __future__ import annotations

import re
import threading
from decimal import Decimal
from typing import Any

from .ml_bridge import MLUnavailableError, crowd_ratio_from_vix, ensure_src_importable, run_blocking
from .steps import PipelineContext, StepResult, register_step

# DB bias label -> (DoWhy treatment, intervention key). The intervention keys
# mirror ``src.causal_inference.get_intervention_recommendation``'s own mapping.
_CAUSAL_LINK: dict[str, tuple[str, str | None]] = {
    "loss_aversion": ("loss_aversion", "remove_loss_aversion"),
    "herd_behavior": ("herd_sensitivity", "hide_crowd_signal"),
    "disposition_effect": ("disposition_strength", "combined"),
}

# Treatments shown as market/context drivers regardless of the bias found.
_CONTEXT_TREATMENTS = ("crowd_ratio", "market_return", "unrealized_gl")

_TREATMENT_LABELS = {
    "loss_aversion": "Loss aversion",
    "herd_sensitivity": "Sensitivity to the crowd",
    "disposition_strength": "Disposition tendency",
    "crowd_ratio": "Crowd fear (India VIX)",
    "market_return": "Recent market return",
    "unrealized_gl": "Your unrealised gain or loss",
    "position_share": "Size of the holding in your portfolio",
    "has_emergency_fund": "Having an emergency fund",
    "surplus_ratio": "Money left over each month",
}

# v3 copy. v3 scores the investor's *situation* (gain or loss, market regime,
# crowd fear, profile) and never sees the intended action, so the copy says the
# situation *resembles* a bias-prone pattern rather than claiming the action
# itself is biased. Used only when BIAS_MODEL_VERSION=v3.
_BIAS_COPY = {
    "loss_aversion": (
        "This looks like loss aversion",
        "Losses tend to feel about twice as strong as equal gains. Your situation "
        "(the size of your loss, the market's mood and your profile) most resembles "
        "investors who acted on that pain rather than on the outlook.",
    ),
    "herd_behavior": (
        "This looks like herd behaviour",
        "Your situation most resembles investors who followed the crowd, deciding "
        "while fear or excitement was running high instead of from their own plan.",
    ),
    "disposition_effect": (
        "This looks like the disposition effect",
        "Your situation most resembles investors prone to the disposition effect: "
        "selling winners too early and holding losers too long. The model reads your "
        "situation rather than this one action, so treat it as a tendency to watch for.",
    ),
    "rational": (
        "This decision looks rational",
        "Your situation doesn't resemble the bias patterns the model knows. It "
        "appears consistent with your profile and the market you're in.",
    ),
}

# v4 sees the action, so its copy can name what the investor is doing. Keyed
# by (bias, action); every pair the label definitions allow is covered
# (src/dataset_v4.py LABEL_RULES), with a per-bias fallback.
_V4_HEADLINE = {
    "loss_aversion": "This looks like loss aversion",
    "herd_behavior": "This looks like herd behaviour",
    "disposition_effect": "This looks like the disposition effect",
    "rational": "This decision looks rational",
}
_V4_MEANING = {
    ("loss_aversion", "sell"):
        "Selling at a loss while the market is falling is the classic panic of loss "
        "aversion: losses feel about twice as strong as equal gains, so the urge to stop "
        "the pain can outrun the outlook for the investment itself.",
    ("loss_aversion", "hold"):
        "Holding on to a position that is down 25% or more, so the loss never becomes real, "
        "is the other face of loss aversion: the decision protects a feeling rather than "
        "asking whether the money is best left there.",
    ("herd_behavior", "sell"):
        "Selling into a broad market sell-off looks like herd behaviour: the crowd's "
        "mood, rather than your own plan, is setting the timing.",
    ("herd_behavior", "buy_more"):
        "Buying more after a strong rally looks like herd behaviour: the crowd's excitement, "
        "rather than your own plan, is setting the pace.",
    ("disposition_effect", "sell"):
        "Selling a winner early while the market is calm is the disposition effect: locking "
        "in a gain feels good, so winners get sold while the reasons for owning them may "
        "still hold.",
    ("disposition_effect", "hold"):
        "Holding a losing position in a calm market, waiting to get back to even, is the "
        "other half of the disposition effect: the price you paid becomes the target, "
        "rather than what the investment is likely to do next.",
    ("rational", None):
        "Your choice fits your own situation (your plan, your monthly cash flow and the size "
        "of this holding) rather than a known bias pattern.",
}


def bias_copy(bias: str, action: str | None, model: str | None) -> tuple[str, str]:
    """Headline and plain meaning for the pattern found, worded for the model that found it."""
    if model != "bias_v4":
        return _BIAS_COPY.get(bias, _BIAS_COPY["rational"])
    headline = _V4_HEADLINE.get(bias, _V4_HEADLINE["rational"])
    meaning = _V4_MEANING.get((bias, action))
    if meaning is None:
        meaning = next((v for (b, _), v in _V4_MEANING.items() if b == bias), _V4_MEANING[("rational", None)])
    return headline, meaning


# Plain-English names for the classifier's 52 features (SHAP reports raw names).
FEATURE_LABELS: dict[str, str] = {
    "market_return_recent": "NIFTY's 1-month return",
    "unrealized_gain_loss": "Your unrealised gain or loss",
    "crowd_action_ratio": "Crowd fear (India VIX)",
    "market_volatility": "Market volatility",
    "position_size_pct": "Position size",
    "holding_period_months": "How long you have held it",
    "age": "Your age",
    "monthly_income": "Monthly income",
    "monthly_expense": "Monthly expenses",
    "monthly_surplus": "Monthly surplus",
    "has_emergency_fund": "Emergency fund",
    "years_investing": "Years of investing",
    "risk_tolerance": "Risk tolerance",
    "investment_horizon": "Investment horizon",
    "loss_x_crowd": "Loss combined with crowd fear",
    "loss_x_market": "Loss combined with market direction",
    "crowd_influence_ratio": "Crowd pull relative to your loss",
    "herd_pure_signal": "Crowd pressure without a loss",
    "loss_crowd_interaction": "Crowd pressure on a losing position",
    "loss_vs_risk_tolerance": "Loss relative to your risk tolerance",
    "age_horizon_ratio": "Age relative to horizon",
    "financial_stress": "Financial stress",
    "surplus_normalized": "Savings rate",
    "market_regime_bull": "Bull market",
    "market_regime_crash": "Market crash",
    "market_regime_neutral": "Neutral market",
    "market_regime_rally": "Market rally",
    "crash_speed_gradual_bear": "Gradual decline",
    "crash_speed_normal": "Normal market pace",
    "crash_speed_rapid_decline": "Rapid decline",
    "secondary_biases_loss_aversion": "Secondary loss aversion",
    "secondary_biases_none": "No secondary bias",
    "secondary_biases_overconfidence": "Overconfidence",
    "financial_strategy_credit_card": "Relies on credit",
    "financial_strategy_family_support": "Supports family",
    "financial_strategy_investing": "Investing-first approach",
    "financial_strategy_saving": "Saving-first approach",
    "age_horizon_mismatch_old_long": "Long horizon late in life",
    "age_horizon_mismatch_young_short": "Short horizon early in life",
    "investment_experience_expert": "Expert investor",
    "investment_experience_intermediate": "Intermediate investor",
    "investment_experience_novice": "Novice investor",
    "goal_emergency": "Goal: emergency fund",
    "goal_retirement": "Goal: retirement",
    "goal_wealth growth": "Goal: wealth growth",
    "loss_magnitude_large_loss": "Large loss",
    "loss_magnitude_no_loss": "Small or no loss",
    "loss_magnitude_severe_loss": "Severe loss",
    "loss_magnitude_small_loss": "Small loss",
    "crowd_pressure_mixed": "Mixed crowd mood",
    "crowd_pressure_moderate_herd": "Moderate herd pressure",
    "crowd_pressure_strong_herd": "Strong herd pressure",
}

# Plain-English names for the research interventions (their own descriptions,
# e.g. "All three interventions simultaneously", don't read as advice).
_INTERVENTION_COPY = {
    "remove_loss_aversion": "Reframing the loss as one step in a long-term plan",
    "hide_crowd_signal": "Not watching what the crowd is doing while you decide",
    "reduce_herd_sensitivity": "Pausing for an independent analysis before acting",
    "combined": "Reframing the loss, tuning out the crowd and pausing for an independent analysis, together",
}


def _sentence_case(label: str) -> str:
    """Lower-case a label for mid-sentence use without breaking acronyms
    ("Crowd fear (India VIX)" -> "crowd fear (India VIX)"; "NIFTY's ..." kept)."""
    first, _, rest = label.partition(" ")
    if first[1:] != first[1:].lower():  # NIFTY's, SHAP, ...
        return label
    return first[:1].lower() + first[1:] + (" " + rest if rest else "")


_P_VALUE = re.compile(r"'p_value':\s*(?:np\.float64\()?([0-9.eE+-]+)")

_causal_cache: dict[str, Any] | None = None
_causal_lock = threading.Lock()


def _load_causal() -> dict[str, Any]:
    global _causal_cache
    with _causal_lock:
        if _causal_cache is None:
            ensure_src_importable()
            try:
                from src.causal_v4 import load_results as load_v4

                _causal_cache = load_v4()
                return _causal_cache
            except (ImportError, FileNotFoundError):
                pass
            try:
                from src.causal_inference import load_causal_results
            except ImportError as exc:
                raise MLUnavailableError(
                    "causal explanation needs the Phase 5 ML extras: "
                    "pip install -r backend/requirements-ml.txt"
                ) from exc
            try:
                _causal_cache = load_causal_results()
            except FileNotFoundError as exc:
                raise MLUnavailableError(
                    f"causal artefact not found: {exc}. "
                    "results/causal_effects.pkl must be present."
                ) from exc
        return _causal_cache


def _refutations(details: Any) -> list[dict[str, Any]]:
    """Parse DoWhy refuter results; they were pickled as repr strings."""
    out = []
    for name, raw in (details or {}).items():
        match = _P_VALUE.search(str(raw))
        out.append({
            "test": name.replace("_", " "),
            "p_value": round(float(match.group(1)), 4) if match else None,
        })
    return out


def _effect_block(effects: dict[str, Any], treatment: str) -> dict[str, Any] | None:
    raw = effects.get(treatment)
    if not raw:
        return None
    return {
        "treatment": treatment,
        "label": _TREATMENT_LABELS.get(treatment, treatment),
        "effect": round(float(raw["causal_effect"]), 4),
        "method": raw.get("method"),
        "refutation_passed": str(raw.get("refutation_passed")).lower() == "true",
        "refutations": _refutations(raw.get("refutation_details")),
    }


def inr(amount: float) -> str:
    """Indian-style rupee figure: ₹4.12 Cr, ₹3.85 L, ₹82,450."""
    sign = "-" if amount < 0 else ""
    a = abs(amount)
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:.2f} L"
    return f"{sign}₹{a:,.0f}"


def _f(value: Any) -> float | None:
    return float(value) if value is not None else None


def _shap_factors(shap: Any) -> list[dict[str, Any]]:
    factors = []
    for item in shap or []:
        if not isinstance(item, dict) or "feature" not in item:
            continue
        factors.append({
            **item,
            "label": FEATURE_LABELS.get(item["feature"], item["feature"].replace("_", " ")),
        })
    return factors


def _pct(x: float, signed: bool = True) -> str:
    return f"{x * 100:+.0f}%" if signed else f"{x * 100:.0f}%"


#: Verbs for a driver label ("Your choice to hold"). Not ``_ACTION_WORDS``,
#: the gerunds below for the causal text: one name for both made the later
#: dict win, and the label read "Your choice to holding on".
_ACTION_VERBS = {"sell": "sell", "hold": "hold", "buy_more": "buy more"}


def driver_label(driver: str, f: dict[str, Any], action: str | None) -> str:
    """Plain words for one v4 driver, with the value that drove it.

    ``f`` is the driver's model inputs (``drivers[i].inputs``); ``action`` is the
    decision's intent. Every key in ``src.bias_model_v4.DRIVERS`` has a case.
    """
    on = lambda key: bool(f.get(key))  # noqa: E731
    if driver == "action":
        return f"Your choice to {_ACTION_VERBS.get(action or '', 'act')}"
    if driver == "fits_disposition":
        if not on("allows_disposition"):
            return "Doesn't fit the disposition effect"
        return "Selling a winner in a calm market" if action == "sell" else "Holding a loser in a calm market"
    if driver == "fits_herd":
        if not on("allows_herd"):
            return "Doesn't fit herd behaviour"
        return "Buying more into a strong rally" if action == "buy_more" else "Selling into a market sell-off"
    if driver == "fits_loss_aversion":
        if not on("allows_loss_aversion"):
            return "Doesn't fit loss aversion"
        return ("Holding on to a loss of 25% or more" if action == "hold"
                else "Selling at a loss while the market is falling")
    if driver == "gain_loss":
        gl = float(f.get("unrealized_gl", 0.0))
        return f"Your {'gain' if gl >= 0 else 'loss'} on this holding ({_pct(gl)})"
    if driver == "holding_period":
        return f"How long you've held it ({int(f.get('holding_period_months', 0))} months)"
    if driver == "market_month":
        return f"NIFTY's move over the past month ({float(f.get('nifty_1m_return', 0.0)) * 100:+.1f}%)"
    if driver == "market_fear":
        vix = float(f.get("vix", 0.0))
        level = "Low" if vix < 15 else ("Moderate" if vix < 22 else "High")
        return f"{level} market fear (India VIX {vix:.1f})"
    if driver == "market_swings":
        return "How jumpy the market has been"
    if driver == "age":
        return f"Your age ({int(f.get('age', 0))})"
    if driver == "horizon":
        return f"Your time horizon ({int(f.get('investment_horizon', 0))} years)"
    if driver == "risk_tolerance":
        return "Your comfort with risk"
    if driver == "cash_flow":
        return f"Money left over each month ({_pct(float(f.get('surplus_ratio', 0.0)), False)} of income)"
    if driver == "emergency_fund":
        return "Having an emergency fund" if on("has_emergency_fund") else "Not having an emergency fund"
    if driver == "position_size":
        return f"This holding's share of your money ({_pct(float(f.get('position_share', 0.0)), False)})"
    if driver == "asset_mix":
        return "Your mix of shares, funds and gold"
    if driver == "property_loans":
        return "Your property and loans"
    if driver == "cash_need":
        return "You said you need the money" if on("cash_need_stated") else "No stated need for the money"
    return driver.replace("_", " ").capitalize()


def _driver_factors(drivers: Any, action: str | None) -> list[dict[str, Any]]:
    """v4 drivers -> the factor list the result page draws ("What weighed most")."""
    factors = []
    for d in drivers or []:
        if not isinstance(d, dict) or "driver" not in d:
            continue
        inputs = d.get("inputs") or {}
        factors.append({
            "feature": d["driver"],
            "label": driver_label(d["driver"], inputs, action),
            "value": next(iter(inputs.values()), None),
            "shap_impact": d.get("impact", 0.0),
            "share": d.get("share"),
            "direction": d.get("direction"),
        })
    return factors


# DB bias label -> the research/GAP 3 template key.
_RESEARCH_LABEL = {
    "loss_aversion": "loss_aversion",
    "herd_behavior": "herd",
    "disposition_effect": "disposition",
    "rational": "rational",
}
_LANGS = ("en", "hi")


def _render_gap3(bias_result: dict, sim_result: dict, user_input: dict) -> dict[str, Any]:
    """GAP 3's six-section explanation in English and Hindi. Thread only.

    ``src/explainer.py`` renders from templates — every number comes from the
    facts dict, and its tests enforce a jargon blocklist (no model names, no
    "p10"). The optional LLM polish obeys EXPLAINER_LLM (off by default) and
    can only reword: a polish that changes a number is discarded.
    """
    ensure_src_importable()
    from src.explainer import generate_complete_explanation

    out: dict[str, Any] = {}
    for lang in _LANGS:
        e = generate_complete_explanation(bias_result, sim_result, user_input, lang=lang)
        # Kept whole (minus chart/technical duplicates) so the downloadable
        # report can be rebuilt later from exactly what the user read.
        out[lang] = {k: v for k, v in e.items() if k not in ("charts", "technical")}
    return out


def _fallback_story(meaning: str, hold_med, sell_med, p_hold, years: int = 20) -> list[dict[str, str]]:
    story = [{"title": "What we found", "body": meaning}]
    if hold_med is not None and sell_med is not None:
        body = (f"Over {years} years, holding is projected to reach about {inr(hold_med)} "
                f"against {inr(sell_med)} if you sell now.")
        if p_hold is not None:
            body += f" Holding came out ahead in {p_hold * 100:.0f}% of simulated futures."
        story.append({"title": f"What it means in {years} years", "body": body})
    return story


_ACTION_WORDS = {"sell": "selling", "hold": "holding on", "buy_more": "buying more"}

# Portfolio factors shown with the market context when the v4 results exist.
_V4_CONTEXT = ("crowd_ratio", "market_return", "unrealized_gl", "position_share", "has_emergency_fund", "surplus_ratio")


def _v4_causal(causal: dict[str, Any], bias: str, intent: str) -> tuple[dict | None, list[dict], dict | None]:
    """Primary effect, context effects and the best habit, for this pattern and action."""
    effects = causal.get("causal_effects", {})
    key = f"{_RESEARCH_LABEL.get(bias, bias)}:{intent}"
    situ = causal.get("situations", {}).get(key)

    primary = None
    intervention = None
    if situ:
        te = situ["tendency_effect"]
        treatment = _CAUSAL_LINK.get(bias, (None, None))[0]
        primary = {
            "treatment": treatment,
            "label": _TREATMENT_LABELS.get(treatment, treatment),
            "effect": te["g_computation"],
            "unit": te["unit"],
            "action": intent,
            "action_words": _ACTION_WORDS.get(intent, intent),
            "situation": situ["situation"],
            "share_taking_action": situ["share_taking_action_observed"],
            "method": "g-computation on dataset v4, checked against the true mechanism",
            "refutation_passed": bool(te.get("refutation_passed", True)),
            "refutations": [
                {"test": name, "p_value": None if r.get("p_value") is None else round(float(r["p_value"]), 4)}
                for name, r in (te.get("refutations") or {}).items()
            ],
        }
        # The single habit that helps most here (the combined one is a summary, not advice).
        habits = {k: v for k, v in situ["habits"].items() if k != "combined"}
        if habits:
            hk, hv = min(habits.items(), key=lambda kv: kv[1]["after_estimated"] - kv[1]["before_estimated"])
            # "Usually" is the share actually observed in this situation (the
            # same figure the card quotes above); the habit moves it by the
            # change the model estimates.
            usual = situ["share_taking_action_observed"]
            change = hv["after_estimated"] - hv["before_estimated"]
            intervention = {
                "key": hk,
                "description": hv["description"],
                "action": intent,
                "action_words": _ACTION_WORDS.get(intent, intent),
                "original_sell_prob": round(usual, 4),
                "new_sell_prob": round(min(max(usual + change, 0.0), 1.0), 4),
                "delta_sell_prob": round(change, 4),
                "recommendation": None,
                "assumption": causal.get("assumptions", {}).get("habits"),
            }

    context = []
    for t in _V4_CONTEXT:
        e = effects.get(t)
        if not e or abs(e["g_computation"]["sell"]) < 0.005:
            continue   # too small to state a direction honestly
        context.append({
            "treatment": t,
            "label": e["label"],
            "effect": e["g_computation"]["sell"],
            "unit": e["unit"],
            "method": e.get("method"),
            "refutation_passed": bool(e.get("refutation_passed")),
            "refutations": [],
        })
    return primary, context, intervention


async def explain(ctx: PipelineContext) -> StepResult:
    d = ctx.decision
    causal = await run_blocking(_load_causal)
    effects = causal.get("causal_effects", {})
    interventions = causal.get("interventions", {})

    bias = d.get("bias_detected") or "rational"
    treatment, intervention_key = _CAUSAL_LINK.get(bias, (None, None))
    is_v4 = causal.get("version") == "v4"

    if is_v4:
        primary, context, intervention = _v4_causal(causal, bias, d["decision_intent"])
    else:
        primary = _effect_block(effects, treatment) if treatment else None
        context = [b for t in _CONTEXT_TREATMENTS if (b := _effect_block(effects, t))]

    if not is_v4:
        intervention = None
    if not is_v4 and intervention_key and intervention_key in interventions:
        iv = interventions[intervention_key]
        intervention = {
            "key": intervention_key,
            "description": _INTERVENTION_COPY.get(intervention_key, iv.get("description")),
            "research_description": iv.get("description"),
            "original_sell_prob": round(float(iv["original_sell_prob"]), 4),
            "new_sell_prob": round(float(iv["new_sell_prob"]), 4),
            "delta_sell_prob": round(float(iv["delta_sell_prob"]), 4),
            "recommendation": iv.get("recommendation"),
        }

    existing = d.get("explainer_output") or {}
    bias_block = existing.get("bias", {}) if isinstance(existing, dict) else {}
    model = bias_block.get("model")
    if model == "bias_v4":
        factors = _driver_factors(bias_block.get("drivers"), d.get("decision_intent"))
    else:
        factors = _shap_factors(bias_block.get("shap"))

    curves = d.get("simulation_curves") or {}
    hold_med, sell_med = _f(d.get("hold_median_20y")), _f(d.get("sell_median_20y"))
    p_hold = curves.get("prob_hold_better")
    headline, meaning = bias_copy(bias, d.get("decision_intent"), model)

    explanation = None
    research = curves.get("research")
    if research:
        model_inputs = bias_block.get("model_inputs") or {}
        bias_result = {
            "bias_type": _RESEARCH_LABEL.get(bias, "unknown"),
            "confidence": float(d.get("bias_confidence") or 0.0),
            "is_biased": bias != "rational",
            "causal_effects": effects,
            "shap_explanation": bias_block.get("shap") or factors,
            "all_probabilities": bias_block.get("probabilities") or {},
        }
        user_input = {
            "unrealized_gl": float(d["unrealized_pnl_pct"]),
            "crowd_ratio": float(model_inputs.get("crowd_ratio", crowd_ratio_from_vix(d.get("vix_value")))),
            "has_emergency_fund": int(model_inputs.get("has_emergency_fund", 1)),
            "decision_intent": d["decision_intent"],
            "current_wealth": float(curves.get("invested") or 0.0),
        }
        try:
            explanation = await run_blocking(_render_gap3, bias_result, research, user_input)
        except Exception:  # noqa: BLE001 — an explanation fault must not fail the analysis
            explanation = None

    from .comment_reader import compare_with_reading

    explainer_output = {
        **(existing if isinstance(existing, dict) else {}),
        # Phase B3: the investor's own words against the reading.
        "own_words": compare_with_reading(d.get("comment_facts"), bias),
        "headline": headline,
        "explanation": explanation,
        "story": None if explanation else _fallback_story(
            meaning, hold_med, sell_med, p_hold, int(curves.get("horizon_years") or 20)
        ),
        "factors": factors,
        "causal": {
            "primary": primary,
            "context": context,
            "intervention": intervention,
            "source": ("results/causal_v4.json (per situation, checked against the true mechanism)" if is_v4
                       else "results/causal_effects.pkl (population-level estimates)"),
        },
    }
    causal_effect = (
        Decimal(str(primary["effect"])).quantize(Decimal("0.0001")) if primary else None
    )

    return StepResult(
        updates={"causal_effect": causal_effect, "explainer_output": explainer_output},
        event={"headline": headline, "causal_effect": primary["effect"] if primary else None},
    )


register_step("explanation", explain)
