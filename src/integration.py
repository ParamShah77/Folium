"""
GAP 1 – Week 5 (Integration): Unified Real-Time Analysis Pipeline
==================================================================
Combines the two tracks built in previous weeks:
  • Person 1 track  →  bias_detector.py   (XGBoost, 89% accuracy)
  • Person 2 track  →  causal_inference.py (partial-corr causal effects)

Public API
----------
    analyze_decision_realtime(user_input: dict) -> dict

    Full pipeline for all users in a DataFrame:
    analyze_batch(df: pd.DataFrame) -> pd.DataFrame

Run demo:
    python src/integration.py
"""

from __future__ import annotations

import os
import sys
import warnings
warnings.filterwarnings("ignore")

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# Internal imports (both tracks)
# ─────────────────────────────────────────────
from bias_detector import detect_bias_realtime, load_model as load_bias_model

from causal_inference import (
    get_intervention_recommendation,
    load_causal_results,
    EFFECTS_PKL,
)

# Lazy-load causal results (non-blocking if pkl does not exist)
_causal_cache: dict | None = None


def _get_causal_results() -> dict | None:
    global _causal_cache
    if _causal_cache is None:
        try:
            _causal_cache = load_causal_results()
        except FileNotFoundError:
            pass
    return _causal_cache


# ─────────────────────────────────────────────
# RISK SCORE
# ─────────────────────────────────────────────
_RISK_WEIGHTS = {
    "loss_aversion"  : 0.30,
    "herd"           : 0.25,
    "disposition"    : 0.25,
    "rational"       : 0.00,
}

def _compute_risk_score(
    bias_probs: dict[str, float],
    causal_effects: dict | None,
) -> float:
    """
    Weighted risk score in [0, 1].
    Combines bias class probabilities with causal effect magnitudes.
    """
    # Base: weighted sum of non-rational class probabilities
    base = sum(_RISK_WEIGHTS.get(k, 0.20) * v for k, v in bias_probs.items())

    # Boost: if causal data available, add scaled effect of top driver
    boost = 0.0
    if causal_effects:
        effects_list = [
            abs(v["causal_effect"])
            for k, v in causal_effects.items()
            if k != "decision"
        ]
        if effects_list:
            boost = min(max(effects_list) * 0.15, 0.15)  # cap at 15%

    return round(min(base + boost, 1.0), 4)


# ─────────────────────────────────────────────
# CAUSAL CHAIN EXPLANATION
# ─────────────────────────────────────────────
def _build_causal_chain(
    bias_type: str,
    user_input: dict,
    causal_effects: dict | None,
) -> list[str]:
    """
    Human-readable causal chain steps for the detected bias.
    """
    chain = []
    if not causal_effects:
        return [
            f"Bias '{bias_type}' detected from user profile.",
            "Causal effects data not available; running without causal context.",
        ]

    # Map bias → relevant treatment variables
    bias_drivers = {
        "loss_aversion"  : ["loss_aversion", "unrealized_gl"],
        "herd"           : ["crowd_ratio", "herd_sensitivity"],
        "disposition"    : ["disposition_strength", "unrealized_gl"],
        "rational"       : [],
    }
    drivers = bias_drivers.get(bias_type, list(causal_effects.keys())[:2])

    for drv in drivers:
        if drv not in causal_effects:
            continue
        eff   = causal_effects[drv]
        value = user_input.get(drv, "N/A")
        eff_v = eff["causal_effect"]
        interp = eff["interpretation"]
        chain.append(
            f"[{drv}={value}]  causal effect on decision: {eff_v:+.4f}  — {interp}"
        )

    if not chain:
        chain.append(f"No dominant causal driver identified for '{bias_type}'.")

    return chain


# ─────────────────────────────────────────────
# MAIN API
# ─────────────────────────────────────────────
def analyze_decision_realtime(user_input: dict) -> dict:
    """
    Full real-time bias analysis for a single user decision event.

    Parameters
    ----------
    user_input : dict
        Keys expected (all optional with defaults):
            age, investment_horizon, risk_tolerance, market_return,
            crowd_ratio, unrealized_gl, loss_aversion, herd_sensitivity,
            disposition_strength, volatility_index, recent_trades,
            portfolio_value

    Returns
    -------
    dict with keys:
        bias_type          : str   — detected bias class
        bias_label         : str   — human-readable label
        confidence         : float — model confidence [0, 1]
        all_probabilities  : dict  — {class: prob}
        causal_chain       : list  — ordered causal explanation steps
        intervention       : str   — recommended intervention text
        causal_effects     : dict  — raw causal effects (or None)
        risk_score         : float — combined risk score [0, 1]
        explanation        : str   — one-sentence summary for the UI
        timestamp_ms       : int   — Unix timestamp in milliseconds
    """
    import time

    # ── Step 1: Bias detection (XGBoost) ──────────────────────────────
    # detect_bias_realtime() accepts explicit keyword args, not a dict
    bias_result = detect_bias_realtime(
        market_return         = float(user_input.get("market_return",       -0.05)),
        unrealized_gl         = float(user_input.get("unrealized_gl",        0.00)),
        crowd_ratio           = float(user_input.get("crowd_ratio",           0.50)),
        age                   = int(user_input.get("age",                    35)),
        risk_tolerance        = float(user_input.get("risk_tolerance",        5.0)),
        investment_horizon    = int(user_input.get("investment_horizon",     10)),
        monthly_income        = float(user_input.get("monthly_income",   60_000)),
        monthly_expense       = float(user_input.get("monthly_expense",  45_000)),
        financial_strategy    = str(user_input.get("financial_strategy",  "saving")),
        market_volatility     = float(user_input.get("market_volatility",    0.20)),
        position_size_pct     = float(user_input.get("position_size_pct",    0.10)),
        holding_period_months = int(user_input.get("holding_period_months",    6)),
        has_emergency_fund    = int(user_input.get("has_emergency_fund",       1)),
        years_investing       = int(user_input.get("years_investing",          5)),
        crash_speed           = str(user_input.get("crash_speed",         "normal")),
        secondary_biases      = str(user_input.get("secondary_biases",     "none")),
        age_horizon_mismatch  = str(user_input.get("age_horizon_mismatch", "none")),
        investment_experience = str(user_input.get("investment_experience", "intermediate")),
        goal                  = str(user_input.get("goal",          "wealth growth")),
    )

    bias_type  = bias_result.get("bias_type", "unknown")
    confidence = bias_result.get("confidence", 0.0)
    # "probabilities" is the key in bias_detector, map to "all_probabilities"
    all_probs  = bias_result.get("probabilities", {})
    explanation_text = bias_result.get("explanation", "")

    # ── Step 2: Load pre-computed causal effects ───────────────────────
    causal_data    = _get_causal_results()
    causal_effects = causal_data["causal_effects"] if causal_data else None

    # ── Step 3: Intervention recommendation ───────────────────────────
    intervention = get_intervention_recommendation(bias_type, causal_effects)

    # ── Step 4: Causal chain ───────────────────────────────────────────
    causal_chain = _build_causal_chain(bias_type, user_input, causal_effects)

    # ── Step 5: Risk score ─────────────────────────────────────────────
    risk_score = _compute_risk_score(all_probs, causal_effects)

    # ── Step 6: Compose one-sentence UI summary ────────────────────────
    ui_explanation = (
        f"Detected {bias_type.replace('_', ' ').title()} bias "
        f"(confidence {confidence:.0%}, risk {risk_score:.0%}). "
        f"{intervention}"
    )

    return {
        "bias_type"          : bias_type,
        "bias_label"         : bias_type.replace("_", " ").title(),
        "is_biased"          : bias_result.get("is_biased", False),
        "confidence"         : round(confidence, 4),
        "all_probabilities"  : all_probs,
        "causal_chain"       : causal_chain,
        "intervention"       : intervention,
        "causal_effects"     : causal_effects,
        "risk_score"         : risk_score,
        "explanation"        : ui_explanation,
        "timestamp_ms"       : int(time.time() * 1000),
    }


# ─────────────────────────────────────────────
# BATCH PIPELINE
# ─────────────────────────────────────────────
def analyze_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run `analyze_decision_realtime` over every row in `df`.
    Appends result columns: bias_type, confidence, risk_score, intervention.

    Parameters
    ----------
    df : pd.DataFrame  — rows are individual user-decision events

    Returns
    -------
    df_out : pd.DataFrame  — original columns + 4 analysis columns
    """
    records = df.to_dict(orient="records")
    results = [analyze_decision_realtime(r) for r in records]

    df_out = df.copy()
    df_out["pred_bias_type"]   = [r["bias_type"]    for r in results]
    df_out["pred_confidence"]  = [r["confidence"]   for r in results]
    df_out["pred_risk_score"]  = [r["risk_score"]   for r in results]
    df_out["intervention"]     = [r["intervention"] for r in results]

    return df_out


# ─────────────────────────────────────────────
# DEMO / SMOKE TEST
# ─────────────────────────────────────────────
def _run_demo() -> None:
    print("\n" + "═" * 65)
    print("  GAP 1 – Integration Pipeline Demo")
    print("═" * 65)

    scenarios = [
        {
            "name": "Panic Seller (loss aversion + crowd)",
            "input": {
                "age": 35, "investment_horizon": 5, "risk_tolerance": 3,
                "market_return": -0.12, "crowd_ratio": 0.85,
                "unrealized_gl": -0.18, "loss_aversion": 3.2,
                "herd_sensitivity": 0.7, "disposition_strength": 0.5,
                "volatility_index": 0.28, "recent_trades": 6,
                "portfolio_value": 120000,
            },
        },
        {
            "name": "Herd Follower (crowd-driven sell)",
            "input": {
                "age": 28, "investment_horizon": 3, "risk_tolerance": 4,
                "market_return": -0.05, "crowd_ratio": 0.80,
                "unrealized_gl": -0.02, "loss_aversion": 1.5,
                "herd_sensitivity": 0.85, "disposition_strength": 0.3,
                "volatility_index": 0.20, "recent_trades": 3,
                "portfolio_value": 45000,
            },
        },
        {
            "name": "Rational Investor",
            "input": {
                "age": 50, "investment_horizon": 20, "risk_tolerance": 7,
                "market_return": -0.03, "crowd_ratio": 0.30,
                "unrealized_gl": 0.10, "loss_aversion": 0.8,
                "herd_sensitivity": 0.2, "disposition_strength": 0.2,
                "volatility_index": 0.15, "recent_trades": 1,
                "portfolio_value": 500000,
            },
        },
    ]

    for s in scenarios:
        print(f"\n{'─' * 65}")
        print(f"  Scenario: {s['name']}")
        print(f"{'─' * 65}")
        result = analyze_decision_realtime(s["input"])
        print(f"  Bias type    : {result['bias_type']} ({result['bias_label']})")
        print(f"  Confidence   : {result['confidence']:.1%}")
        print(f"  Risk score   : {result['risk_score']:.1%}")
        print(f"  Intervention : {result['intervention']}")
        print(f"  Causal chain :")
        for step in result["causal_chain"]:
            print(f"    • {step}")
        print(f"  Summary      : {result['explanation']}")

    print("\n" + "═" * 65 + "\n")


if __name__ == "__main__":
    _run_demo()
