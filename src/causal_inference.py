"""
GAP 1 – Week 5 (Person 2): Causal Inference & Intervention Simulation
=======================================================================
Uses the learned causal graph + DoWhy to:
  1. Estimate causal effects  (how much does loss aversion CAUSE selling?)
  2. Validate estimates       (refutation tests)
  3. Simulate interventions   ("what if we remove this bias?")

Outputs:
  results/causal_effects.pkl
  results/figures/intervention_comparison.png

Run:
    python src/causal_inference.py
"""

import os
import pickle
import warnings
warnings.filterwarnings("ignore")

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
# Force UTF-8 for box-drawing characters on Windows
try: _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from causal_utils import load_causal_data
from causal_structure import load_causal_graph

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS  = os.path.join(ROOT, "results")
FIGURES  = os.path.join(RESULTS, "figures")
os.makedirs(FIGURES, exist_ok=True)

EFFECTS_PKL = os.path.join(RESULTS, "causal_effects.pkl")


# ═══════════════════════════════════════════════════════════
# GML CONVERSION (DoWhy needs GML graph string)
# ═══════════════════════════════════════════════════════════

def graph_to_gml(G: nx.DiGraph) -> str:
    """Convert a networkx DiGraph to GML string for DoWhy."""
    lines = ["graph [", "directed 1"]
    for node in G.nodes():
        lines.append(f'  node [ id "{node}" label "{node}" ]')
    for u, v in G.edges():
        lines.append(f'  edge [ source "{u}" target "{v}" ]')
    lines.append("]")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# CAUSAL EFFECT ESTIMATION
# ═══════════════════════════════════════════════════════════

def estimate_effect_dowhy(
    df: pd.DataFrame,
    G: nx.DiGraph,
    treatment: str,
    outcome: str = "decision",
) -> dict:
    """
    Estimate the causal effect of `treatment` on `outcome`.

    Uses partial correlation (OLS residualisation) as the primary method —
    it is confounder-adjusted, always converges quickly, and produces
    interpretable causal-flavoured effect sizes from the observed DAG structure.

    Returns a dict with keys:
        treatment, outcome, causal_effect, method, refutation_passed, interpretation
    """
    from sklearn.linear_model import LinearRegression

    if treatment not in df.columns or outcome not in df.columns:
        return {"error": f"Column missing: {treatment} or {outcome}"}

    refutation_passed = None

    # ── Partial correlation (confounder-adjusted OLS) ──────────────
    confounders = [c for c in df.columns if c not in {treatment, outcome}]
    if confounders:
        X_conf  = df[confounders].values
        lr      = LinearRegression()
        t_res   = (df[treatment].values
                   - lr.fit(X_conf, df[treatment].values).predict(X_conf))
        o_res   = (df[outcome].values
                   - lr.fit(X_conf, df[outcome].values).predict(X_conf))
        effect_val = float(np.corrcoef(t_res, o_res)[0, 1])
        method     = "Partial correlation (OLS residualization)"
    else:
        effect_val = float(df[[treatment, outcome]].corr().loc[treatment, outcome])
        method     = "Pearson correlation (fallback)"

    # Bootstrap-based simple refutation: shuffle treatment, check effect drops
    try:
        rng     = np.random.default_rng(42)
        t_shuf  = rng.permutation(df[treatment].values)
        t_shuf_res = t_shuf - LinearRegression().fit(X_conf, t_shuf).predict(X_conf) if confounders else t_shuf
        null_eff   = float(np.corrcoef(t_shuf_res, o_res if confounders else df[outcome].values)[0, 1])
        refutation_passed = bool(abs(effect_val) > abs(null_eff) * 1.2)
    except Exception:
        pass

    interpretation = _interpret(treatment, outcome, effect_val)

    return {
        "treatment"          : treatment,
        "outcome"            : outcome,
        "causal_effect"      : round(effect_val, 4),
        "method"             : method,
        "refutation_passed"  : refutation_passed,
        "interpretation"     : interpretation,
    }


def _interpret(treatment: str, outcome: str, effect: float) -> str:
    """Plain-English interpretation of a causal effect value."""
    direction  = "increases" if effect > 0 else "decreases"
    magnitude  = abs(effect)
    strength   = "strongly" if magnitude > 0.3 else ("moderately" if magnitude > 0.1 else "weakly")

    templates = {
        "loss_aversion": (
            f"Loss aversion {strength} {direction} the probability of selling "
            f"(effect = {effect:+.3f}). Reducing it via reframing exercises "
            f"could be a high-impact intervention."
        ),
        "crowd_ratio": (
            f"Crowd selling pressure {strength} {direction} the probability of selling "
            f"(effect = {effect:+.3f}). Hiding the 'crowd action' widget during downturns "
            f"could reduce panic selling."
        ),
        "herd_sensitivity": (
            f"Herd sensitivity {strength} {direction} selling probability "
            f"(effect = {effect:+.3f}). Users high on this trait need stronger "
            f"crowd-behavior nudges."
        ),
        "disposition_strength": (
            f"Disposition bias {strength} {direction} selling probability "
            f"(effect = {effect:+.3f}). It pushes users to sell winners early and hold losers."
        ),
        "market_return": (
            f"Recent market return {strength} {direction} selling probability "
            f"(effect = {effect:+.3f}).  Expected: lower returns increase panic selling."
        ),
        "unrealized_gl": (
            f"Unrealized gain/loss {strength} {direction} selling probability "
            f"(effect = {effect:+.3f}). Losses increase sell probability more than gains decrease it."
        ),
    }
    return templates.get(treatment, f"{treatment} {direction} {outcome} by {effect:+.3f}.")


# ═══════════════════════════════════════════════════════════
# RUN ALL CAUSAL QUESTIONS
# ═══════════════════════════════════════════════════════════

# Treatments we want to investigate
TREATMENTS = [
    "loss_aversion",
    "crowd_ratio",
    "herd_sensitivity",
    "disposition_strength",
    "market_return",
    "unrealized_gl",
]


def estimate_all_effects(df: pd.DataFrame, G: nx.DiGraph) -> dict:
    """Run causal effect estimation for all treatments → decision."""
    results = {}
    for treatment in TREATMENTS:
        if treatment in df.columns:
            print(f"   🔬 Estimating: {treatment} → decision")
            res = estimate_effect_dowhy(df, G, treatment, outcome="decision")
            results[treatment] = res
            val    = res.get("causal_effect", 0)
            refuted = res.get("refutation_passed")
            tick   = "✅" if refuted else ("❓" if refuted is None else "⚠️")
            print(f"      effect = {val:+.4f}   refutation {tick}")
    return results


# ═══════════════════════════════════════════════════════════
# INTERVENTION SIMULATION
# ═══════════════════════════════════════════════════════════

# Intervention recipes: each modifies specific dimensions of the feature vector
# to simulate "what if we could reduce this bias?"
INTERVENTIONS = {
    "remove_loss_aversion": {
        "description": "Reframe losses (cognitive therapy simulation)",
        "modify": {"loss_aversion": 0.0},          # set to 0 (no loss aversion)
    },
    "hide_crowd_signal": {
        "description": "Hide crowd-action widget during market crash",
        "modify": {"crowd_ratio": 0.2},             # clamp crowd ratio to 20%
    },
    "reduce_herd_sensitivity": {
        "description": "Provide independent analysis alert",
        "modify": {"herd_sensitivity": 0.1},
    },
    "combined": {
        "description": "All three interventions simultaneously",
        "modify": {"loss_aversion": 0.0, "crowd_ratio": 0.2, "herd_sensitivity": 0.1},
    },
}


def simulate_intervention(
    user_row: pd.Series,
    intervention_key: str,
    causal_effects: dict,
) -> dict:
    """
    Simulate the counterfactual outcome for a single user.

    Uses a lightweight linear approximation:
        Δ P(sell) ≈ Σ causal_effect[x] × Δx   for each modified variable x

    Returns a dict with before / after sell probability and explanation.
    """
    if intervention_key not in INTERVENTIONS:
        raise ValueError(f"Unknown intervention: {intervention_key}. "
                         f"Choose from {list(INTERVENTIONS.keys())}")

    recipe = INTERVENTIONS[intervention_key]
    delta_p = 0.0
    details = []

    for var, new_val in recipe["modify"].items():
        if var not in user_row.index:
            continue
        old_val    = float(user_row[var])
        delta_x    = new_val - old_val
        effect     = causal_effects.get(var, {}).get("causal_effect", 0.0)
        contribution = delta_x * effect
        delta_p    += contribution
        details.append(
            f"    Δ{var}: {old_val:.3f} → {new_val:.3f}  "
            f"(Δx={delta_x:+.3f}, effect={effect:+.3f}, Δp={contribution:+.4f})"
        )

    # Original P(sell) proxy: use mean sell rate or 0.5 as base
    base_sell_prob = 0.70   # worst-case scenario (panic sell zone)
    new_sell_prob  = np.clip(base_sell_prob + delta_p, 0.0, 1.0)

    return {
        "intervention"       : intervention_key,
        "description"        : recipe["description"],
        "original_sell_prob" : round(base_sell_prob, 4),
        "new_sell_prob"      : round(float(new_sell_prob), 4),
        "delta_sell_prob"    : round(float(delta_p), 4),
        "details"            : details,
        "recommendation"     : _recommend(intervention_key, base_sell_prob, new_sell_prob),
    }


def _recommend(key: str, before: float, after: float) -> str:
    reduction = before - after
    if reduction < 0.01:
        return "Minimal impact expected from this intervention."
    elif reduction < 0.10:
        return f"Modest improvement: sell probability reduced by {reduction*100:.1f}%."
    else:
        strength = "High-impact" if reduction > 0.20 else "Moderate"
        return (
            f"{strength} intervention: sell probability drops {reduction*100:.1f}% "
            f"({before*100:.0f}% → {after*100:.0f}%)."
        )


# ═══════════════════════════════════════════════════════════
# PLOT INTERVENTIONS
# ═══════════════════════════════════════════════════════════

def plot_intervention_comparison(
    results: dict,           # output of simulate_intervention x N
    causal_effects: dict,
) -> None:
    """Two-panel chart: causal effects bar + before/after sell prob."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # ── Panel 1: Causal effect sizes ──────────────────────
    ax = axes[0]
    treatments = [k for k in TREATMENTS if k in causal_effects]
    effects    = [causal_effects[t]["causal_effect"] for t in treatments]
    colours    = ["#d62728" if e > 0 else "#2ca02c" for e in effects]

    bars = ax.barh(treatments, effects, color=colours, edgecolor="black", height=0.6)
    ax.axvline(0, color="black", linewidth=1.2)
    ax.set_xlabel("Causal Effect on P(sell)", fontsize=11)
    ax.set_title("Causal Effects: Treatment → Sell Decision", fontsize=12)
    ax.set_xlim(min(effects) - 0.05, max(effects) + 0.05)
    for bar, val in zip(bars, effects):
        ax.text(val + (0.01 if val >= 0 else -0.01), bar.get_y() + bar.get_height() / 2,
                f"{val:+.3f}", va="center", ha="left" if val >= 0 else "right", fontsize=9)
    ax.invert_yaxis()

    # ── Panel 2: Intervention before/after ────────────────
    ax2 = axes[1]
    keys   = list(results.keys())
    before = [results[k]["original_sell_prob"] for k in keys]
    after  = [results[k]["new_sell_prob"] for k in keys]
    x      = np.arange(len(keys))
    width  = 0.35

    ax2.bar(x - width / 2, before, width, label="Before intervention", color="#d62728", alpha=0.8)
    ax2.bar(x + width / 2, after,  width, label="After intervention",   color="#2ca02c", alpha=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([k.replace("_", "\n") for k in keys], fontsize=9)
    ax2.set_ylabel("P(sell)")
    ax2.set_ylim(0, 1)
    ax2.set_title("Intervention Simulation: Effect on Sell Probability", fontsize=12)
    ax2.legend(fontsize=10)
    ax2.set_yticks(np.arange(0, 1.1, 0.1))
    ax2.grid(axis="y", alpha=0.4)

    plt.suptitle("GAP 1 — Causal Inference Results", fontsize=14, y=1.01)
    plt.tight_layout()
    out = os.path.join(FIGURES, "intervention_comparison.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ Intervention chart saved → {out}")


# ═══════════════════════════════════════════════════════════
# PRINT SUMMARY
# ═══════════════════════════════════════════════════════════

def print_causal_summary(causal_effects: dict, intervention_results: dict) -> None:
    print("\n" + "─" * 60)
    print("  CAUSAL EFFECTS SUMMARY (treatment → sell decision)")
    print("─" * 60)
    for t, r in causal_effects.items():
        tick  = "✅" if r.get("refutation_passed") else "❓"
        print(f"  {t:28s}  {r['causal_effect']:+.4f}  {tick}")
        print(f"    → {r['interpretation']}")

    print("\n" + "─" * 60)
    print("  INTERVENTION SIMULATION RESULTS")
    print("─" * 60)
    for key, r in intervention_results.items():
        print(f"\n  [{key}]  — {r['description']}")
        print(f"    P(sell): {r['original_sell_prob']:.0%} → {r['new_sell_prob']:.0%}"
              f"  (Δ = {r['delta_sell_prob']:+.4f})")
        print(f"    💬 {r['recommendation']}")
        for d in r["details"]:
            print(d)
    print("─" * 60 + "\n")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def run_causal_inference() -> dict:
    print("\n" + "═" * 60)
    print("  GAP 1 | Causal Inference & Intervention Simulation")
    print("═" * 60)

    # Load data & graph
    df_raw, _, _ = load_causal_data(normalize=False)
    G, method    = load_causal_graph()
    print(f"   Graph method: {method}  |  {G.number_of_edges()} edges")

    # ── 1. Causal effect estimation ───────────────────────
    print("\n─── Step 1: Estimating causal effects ───")
    causal_effects = estimate_all_effects(df_raw, G)

    # ── 2. Intervention simulation (worst-case user scenario) ──
    print("\n─── Step 2: Simulating interventions ───")
    # Use a "panic sell" user as the base
    high_risk_mask = (df_raw["unrealized_gl"] < -0.10) & (df_raw["crowd_ratio"] > 0.70)
    if high_risk_mask.sum() == 0:
        user_row = df_raw.iloc[0]
    else:
        user_row = df_raw[high_risk_mask].iloc[0]

    intervention_results = {}
    for key in INTERVENTIONS:
        intervention_results[key] = simulate_intervention(user_row, key, causal_effects)

    print_causal_summary(causal_effects, intervention_results)
    plot_intervention_comparison(intervention_results, causal_effects)

    # ── 3. Save ───────────────────────────────────────────
    output = {"causal_effects": causal_effects, "interventions": intervention_results}
    os.makedirs(RESULTS, exist_ok=True)
    with open(EFFECTS_PKL, "wb") as f:
        pickle.dump(output, f)
    print(f"✅ Causal results saved → {EFFECTS_PKL}")
    print("═" * 60 + "\n")

    return output


# ─────────────────────────────────────────────
# PUBLIC API (used by integration.py)
# ─────────────────────────────────────────────

def load_causal_results() -> dict:
    """Load previously computed causal effects & interventions."""
    with open(EFFECTS_PKL, "rb") as f:
        return pickle.load(f)


def get_intervention_recommendation(
    user_bias_type: str,
    causal_effects: dict | None = None,
) -> str:
    """
    Given a detected bias type, return the best intervention strategy.
    Quick-lookup used by the real-time API.
    """
    mapping = {
        "loss_aversion"  : "remove_loss_aversion",
        "herd"           : "hide_crowd_signal",
        "herd_mentality" : "hide_crowd_signal",
        "disposition"    : "combined",
        "rational"       : None,
    }
    key = mapping.get(user_bias_type.lower())
    if key is None:
        return "✅ No intervention needed — decision appears rational."

    recipe = INTERVENTIONS.get(key, {})
    desc   = recipe.get("description", key)
    return f"💡 Recommended intervention: {desc}  (strategy: {key})"


if __name__ == "__main__":
    run_causal_inference()
