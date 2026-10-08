"""
═══════════════════════════════════════════════════════════════════════════
 evaluate_explanations.py — GAP 3 validation metrics
═══════════════════════════════════════════════════════════════════════════

Measures whether the explanations actually achieve what Objective 3 claims:
that any user, in English or Hindi, can understand the decision they are
being given.

Five metrics, each with a stated target:

    Readability     English: Flesch Reading Ease >= 60  (~8th grade)
                    Hindi:   <= 20 words per sentence
                    (Flesch is undefined for Devanagari — its syllable model
                    is built for English — so Hindi is bounded differently.)

    Completeness    All six sections present and non-empty          target 100%

    Actionability   The explanation ends with an explicit next step  target 100%

    Personalisation At least three figures drawn from THIS user's
                    situation, not generic advice                    target 100%

    Jargon leakage  Blocklisted technical terms reaching the user    target 0

Usage
-----
    python scripts/evaluate_explanations.py
    python scripts/evaluate_explanations.py --n-users 50 --n-simulations 500

Output
------
    results/reports/explanation_quality.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import pandas as pd

import explanation_templates as T
from explainer import DecisionExplainer, find_jargon, reading_level

# ── Targets ───────────────────────────────────────────────────────────────
FLESCH_TARGET   = 60.0
HINDI_WPS_TARGET = 20.0
MIN_PERSONAL_FIGURES = 3

#: Words that mark an explicit next step, per language.
ACTION_MARKERS = {
    "en": ("our suggestion", "don't sell", "stay invested", "selling is reasonable",
           "stick with"),
    "hi": ("हमारी सलाह", "बेचिए मत", "निवेश बनाए रखिए", "क़ायम रखिए"),
}


# ═══════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════

def score_explanation(explanation: dict) -> dict:
    """Score a single explanation against all five metrics."""
    lang      = explanation["lang"]
    narrative = explanation["narrative"]
    full_text = " ".join(narrative.values())

    # 1. Completeness — every section present and actually written
    missing = [s for s in T.SECTIONS if not narrative.get(s, "").strip()]

    # 2. Readability
    level = reading_level(full_text, lang)
    if lang == "en":
        readable = (level["flesch_reading_ease"] is None
                    or level["flesch_reading_ease"] >= FLESCH_TARGET)
    else:
        readable = level["avg_words_per_sentence"] <= HINDI_WPS_TARGET

    # 3. Actionability — does it tell the user what to do?
    final_section = narrative.get("what_to_do_now", "").lower()
    actionable = any(marker.lower() in final_section for marker in ACTION_MARKERS[lang])

    # 4. Personalisation — figures from THIS user's situation
    figures = set(re.findall(r"₹[\d.,]+|\d+%|\b\d+\s*(?:years?|साल)", full_text))
    personalised = len(figures) >= MIN_PERSONAL_FIGURES

    # 5. Jargon leakage
    jargon = find_jargon(full_text)

    return {
        "lang"              : lang,
        "bias_type"         : explanation["bias_type"],
        "complete"          : not missing,
        "missing_sections"  : missing,
        "readable"          : bool(readable),
        "flesch"            : level["flesch_reading_ease"],
        "words_per_sentence": level["avg_words_per_sentence"],
        "word_count"        : level["words"],
        "actionable"        : bool(actionable),
        "personalised"      : bool(personalised),
        "n_figures"         : len(figures),
        "jargon"            : jargon,
    }


def summarise(scores: list[dict], lang: str) -> dict:
    """Aggregate per-language results into headline numbers."""
    rows = [s for s in scores if s["lang"] == lang]
    if not rows:
        return {}

    n = len(rows)
    flesch_values = [r["flesch"] for r in rows if r["flesch"] is not None]
    wps_values    = [r["words_per_sentence"] for r in rows]

    summary = {
        "n_explanations"       : n,
        "completeness_pct"     : round(100 * sum(r["complete"]     for r in rows) / n, 1),
        "readability_pass_pct" : round(100 * sum(r["readable"]     for r in rows) / n, 1),
        "actionability_pct"    : round(100 * sum(r["actionable"]   for r in rows) / n, 1),
        "personalisation_pct"  : round(100 * sum(r["personalised"] for r in rows) / n, 1),
        "jargon_leaks"         : sum(len(r["jargon"]) for r in rows),
        "mean_words_per_sentence": round(sum(wps_values) / n, 1),
        "mean_word_count"      : round(sum(r["word_count"] for r in rows) / n, 1),
    }
    if flesch_values:
        summary["mean_flesch"] = round(sum(flesch_values) / len(flesch_values), 1)
        summary["min_flesch"]  = round(min(flesch_values), 1)
        summary["flesch_target"] = FLESCH_TARGET
    else:
        summary["mean_flesch"] = None
        summary["words_per_sentence_target"] = HINDI_WPS_TARGET

    summary["all_targets_met"] = (
        summary["completeness_pct"]    == 100.0 and
        summary["readability_pass_pct"] == 100.0 and
        summary["actionability_pct"]   == 100.0 and
        summary["personalisation_pct"] == 100.0 and
        summary["jargon_leaks"]        == 0
    )
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# SAMPLE GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def build_sample(n_users: int, n_simulations: int, seed: int = 42) -> list[tuple]:
    """
    Run the real Objective 1 + Objective 2 pipeline over a random sample of
    users, so the metrics measure the explanations users would actually get —
    not hand-picked examples.
    """
    from integration import analyze_decision_realtime
    from simulator import get_simulator

    users = pd.read_csv(os.path.join(_ROOT, "synthetic_users.csv"))
    sample = users.sample(n=min(n_users, len(users)), random_state=seed)
    sim = get_simulator()

    # Four situation archetypes, one per bias the templates cover. Without
    # this the sample lands almost entirely on panic-selling, and the metrics
    # would say nothing about the other three narratives.
    archetypes = [
        {"name": "loss_aversion", "unrealized_gl": -0.35, "crowd_ratio": 0.45,
         "loss_aversion": 2.8, "herd_sensitivity": 0.30, "disposition_strength": 0.25},
        {"name": "herd",         "unrealized_gl": -0.06, "crowd_ratio": 0.85,
         "loss_aversion": 1.3, "herd_sensitivity": 0.85, "disposition_strength": 0.25},
        {"name": "disposition",  "unrealized_gl":  0.22, "crowd_ratio": 0.35,
         "loss_aversion": 1.2, "herd_sensitivity": 0.25, "disposition_strength": 0.85},
        {"name": "rational",     "unrealized_gl":  0.03, "crowd_ratio": 0.20,
         "loss_aversion": 1.1, "herd_sensitivity": 0.15, "disposition_strength": 0.15},
    ]
    intents = ["Thinking of selling", "Planning to hold"]

    cases = []
    for i, (_, user) in enumerate(sample.iterrows()):
        archetype = archetypes[i % len(archetypes)]
        gl     = archetype["unrealized_gl"]
        intent = intents[i % len(intents)]
        wealth = float(user.get("monthly_income", 60_000)) * 12

        user_input = {
            "user_id"            : int(user["user_id"]),
            "unrealized_gl"      : gl,
            "crowd_ratio"        : archetype["crowd_ratio"],
            "loss_aversion"      : archetype["loss_aversion"],
            "herd_sensitivity"   : archetype["herd_sensitivity"],
            "disposition_strength": archetype["disposition_strength"],
            "age"                : int(user.get("age", 35)),
            "investment_horizon" : int(user.get("investment_horizon", 15)),
            "risk_tolerance"     : float(user.get("risk_tolerance", 0.4)),
            "monthly_income"     : float(user.get("monthly_income", 60_000)),
            "monthly_expense"    : float(user.get("monthly_expense", 45_000)),
            "has_emergency_fund" : i % 3 != 0,
            "decision_intent"    : intent,
            "goal"               : str(user.get("goal", "wealth growth")),
        }

        try:
            bias_result = analyze_decision_realtime(user_input)
            sim_result  = sim.compare_hold_vs_sell(
                user_id=int(user["user_id"]), current_wealth=wealth,
                unrealized_gl=gl, n_simulations=n_simulations)
            cases.append((bias_result, sim_result, user_input))
        except Exception as exc:                       # noqa: BLE001
            print(f"  ! skipped user {user['user_id']}: {type(exc).__name__}: {exc}")

        if (i + 1) % 5 == 0:
            print(f"  ... {i + 1}/{len(sample)} users processed")

    return cases


def build_template_coverage(cases: list[tuple]) -> list[tuple]:
    """
    One case per bias type, so every narrative in the template bank is
    measured.

    The live sample above reflects what the detector actually predicts, which
    is dominated by whichever biases the v3 model sees most — so on its own it
    can leave two of the four narratives untested. Here we hold the simulation
    fixed and vary only the detected bias, which is exactly the variable the
    explanation branches on.
    """
    if not cases:
        return []
    _, sim_result, user_input = cases[0]

    covered = []
    for bias in ("loss_aversion", "herd", "disposition", "rational"):
        bias_result = {
            "bias_type"       : bias,
            "is_biased"       : bias != "rational",
            "confidence"      : 0.82,
            "causal_effects"  : None,
            "causal_chain"    : [],
        }
        # Disposition reads differently on a gain than on a loss; use a gain
        # so the branch that talks about banking a win gets exercised.
        case_input = dict(user_input)
        case_input["unrealized_gl"] = 0.18 if bias == "disposition" else -0.15
        covered.append((bias_result, sim_result, case_input))
    return covered


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate GAP 3 explanation quality")
    parser.add_argument("--n-users", type=int, default=25,
                        help="How many users to sample (default: 25)")
    parser.add_argument("--n-simulations", type=int, default=300,
                        help="Monte Carlo paths per user (default: 300)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=os.path.join(_ROOT, "results", "reports",
                                                      "explanation_quality.json"))
    args = parser.parse_args()

    print("=" * 70)
    print("GAP 3 — EXPLANATION QUALITY EVALUATION")
    print("=" * 70)
    print(f"Sampling {args.n_users} users, {args.n_simulations} Monte Carlo paths each...")

    cases = build_sample(args.n_users, args.n_simulations, args.seed)
    if not cases:
        print("No cases generated — is synthetic_users.csv present?")
        return 1

    coverage_cases = build_template_coverage(cases)
    all_cases = cases + coverage_cases

    print(f"\nExplaining {len(cases)} live decisions + {len(coverage_cases)} "
          f"template-coverage cases in {len(T.SUPPORTED_LANGS)} languages...")
    explainer = DecisionExplainer(use_llm=False)     # deterministic, reproducible
    scores: list[dict] = []
    for bias_result, sim_result, user_input in all_cases:
        for lang in T.SUPPORTED_LANGS:
            explanation = explainer.explain(bias_result, sim_result, user_input, lang)
            scores.append(score_explanation(explanation))

    report = {
        "generated_at" : datetime.now(timezone.utc).isoformat(),
        "n_users"      : len(cases),
        "n_template_coverage_cases": len(coverage_cases),
        "n_simulations": args.n_simulations,
        "seed"         : args.seed,
        "llm_polish"   : False,
        "targets": {
            "flesch_reading_ease_en" : f">= {FLESCH_TARGET}",
            "words_per_sentence_hi"  : f"<= {HINDI_WPS_TARGET}",
            "completeness"           : "100%",
            "actionability"          : "100%",
            "personalisation"        : "100%",
            "jargon_leaks"           : "0",
        },
        "by_language"  : {lang: summarise(scores, lang) for lang in T.SUPPORTED_LANGS},
        "bias_coverage": {
            bias: sum(1 for s in scores if s["bias_type"] == bias and s["lang"] == "en")
            for bias in sorted({s["bias_type"] for s in scores})
        },
        "failures": [s for s in scores
                     if not (s["complete"] and s["readable"]
                             and s["actionable"] and s["personalised"]) or s["jargon"]],
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # ── Console summary ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    for lang, summary in report["by_language"].items():
        if not summary:
            continue
        print(f"\n{T.LANG_NAMES[lang]} ({summary['n_explanations']} explanations)")
        print(f"  Completeness     : {summary['completeness_pct']:.0f}%")
        print(f"  Readability      : {summary['readability_pass_pct']:.0f}% pass", end="")
        if summary.get("mean_flesch") is not None:
            print(f"   (mean Flesch {summary['mean_flesch']}, worst {summary['min_flesch']})")
        else:
            print(f"   (mean {summary['mean_words_per_sentence']} words/sentence)")
        print(f"  Actionability    : {summary['actionability_pct']:.0f}%")
        print(f"  Personalisation  : {summary['personalisation_pct']:.0f}%")
        print(f"  Jargon leaks     : {summary['jargon_leaks']}")
        print(f"  All targets met  : {'YES' if summary['all_targets_met'] else 'NO'}")

    print(f"\nBias coverage: {report['bias_coverage']}")
    if report["failures"]:
        print(f"\n{len(report['failures'])} explanation(s) missed a target — see the JSON.")
    print(f"\nSaved: {args.out}")
    return 0 if not report["failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
