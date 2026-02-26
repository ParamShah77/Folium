"""
GAP 1 – Week 4 (Person 2): Causal Structure Learning
=====================================================
Learns the causal DAG from data using:
  Primary  → NOTEARS via CausalNex
  Fallback → HillClimb via pgmpy  (if causalnex not installed)
  Fallback → Domain-knowledge DAG (if neither is installed)

Outputs:
  models/causal_graph.pkl
  results/figures/causal_graph.png

Run:
    python src/causal_structure.py
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

from causal_utils import load_causal_data, save_scaler, RENAME_MAP

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT, "models")
FIGURES    = os.path.join(ROOT, "results", "figures")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(FIGURES, exist_ok=True)

GRAPH_PKL = os.path.join(MODELS_DIR, "causal_graph.pkl")


# ═══════════════════════════════════════════════════════════
# ALGORITHM 1 — NOTEARS  (CausalNex)
# ═══════════════════════════════════════════════════════════

def learn_notears(df_norm: pd.DataFrame, w_threshold: float = 0.3) -> nx.DiGraph | None:
    """
    Attempt NOTEARS via CausalNex.
    Returns a networkx DiGraph, or None if causalnex is unavailable.
    """
    try:
        from causalnex.structure.notears import from_pandas  # type: ignore
        print("🧠 Running NOTEARS (CausalNex)…")
        sm = from_pandas(df_norm, max_iter=100, w_threshold=w_threshold)

        G = nx.DiGraph()
        G.add_nodes_from(df_norm.columns)
        for u, v, data in sm.edges(data=True):
            w = data.get("weight", 1.0)
            G.add_edge(u, v, weight=float(w))

        print(f"✅ NOTEARS complete — {G.number_of_edges()} edges found.")
        return G

    except ImportError:
        print("⚠️  causalnex not installed — trying fallback.")
        return None
    except Exception as e:
        print(f"⚠️  NOTEARS failed ({e}) — trying fallback.")
        return None


# ═══════════════════════════════════════════════════════════
# ALGORITHM 2 — HILL-CLIMB BIC  (pgmpy)
# ═══════════════════════════════════════════════════════════

def learn_hillclimb(df_raw: pd.DataFrame) -> nx.DiGraph | None:
    """
    Attempt Hill-Climb search with BIC score via pgmpy.
    Returns a networkx DiGraph, or None if pgmpy is unavailable.
    """
    try:
        from pgmpy.estimators import HillClimbSearch, BicScore  # type: ignore
        print("🧠 Running Hill-Climb BIC (pgmpy)…")

        # pgmpy needs discretized data for structure learning
        df_disc = df_raw.copy()
        for col in df_disc.columns:
            df_disc[col] = pd.cut(df_disc[col], bins=5, labels=False)

        hc   = HillClimbSearch(df_disc)
        best = hc.estimate(scoring_method=BicScore(df_disc), max_iter=500)

        G = nx.DiGraph(best.edges())
        G.add_nodes_from(df_raw.columns)
        for u, v in G.edges():
            G[u][v]["weight"] = 1.0   # pgmpy doesn't give edge weights directly

        print(f"✅ Hill-Climb complete — {G.number_of_edges()} edges found.")
        return G

    except ImportError:
        print("⚠️  pgmpy not installed — using domain-knowledge graph.")
        return None
    except Exception as e:
        print(f"⚠️  Hill-Climb failed ({e}) — using domain-knowledge graph.")
        return None


# ═══════════════════════════════════════════════════════════
# ALGORITHM 3 — DOMAIN-KNOWLEDGE GRAPH  (always available)
# ═══════════════════════════════════════════════════════════

def build_domain_graph(df_raw: pd.DataFrame) -> nx.DiGraph:
    """
    Builds a DAG from domain knowledge + partial-correlation edge weights.

    Causal theory:
      - Psychological traits (loss_aversion, herd_sensitivity, disposition_strength)
        CAUSE how the investor reacts to market & position state.
      - Market conditions (market_return, crowd_ratio) CAUSE the position state
        and directly influence the decision.
      - The position state (unrealized_gl) and psychological amplification
        jointly CAUSE the final decision.
    """
    print("🧠 Building domain-knowledge causal graph + correlation weights…")

    # Fixed directed edges (causal arrows we know from theory)
    directed_edges = [
        # Market → position state
        ("market_return",      "unrealized_gl"),
        # Market → decision (direct: crash triggers fear regardless of position)
        ("market_return",      "decision"),
        # Crowd → decision (herd pressure)
        ("crowd_ratio",        "decision"),
        # Position state → decision (core trigger)
        ("unrealized_gl",      "decision"),
        # Psychological traits amplify reaction to losses
        ("loss_aversion",      "unrealized_gl"),   # loss aversion makes losses feel bigger
        ("loss_aversion",      "decision"),
        ("herd_sensitivity",   "crowd_ratio"),     # sensitive people feel crowd more
        ("herd_sensitivity",   "decision"),
        ("disposition_strength", "unrealized_gl"),
        ("disposition_strength", "decision"),
        # Risk tolerance moderates loss perception
        ("risk_tolerance",     "unrealized_gl"),
        ("risk_tolerance",     "decision"),
    ]

    # Only keep edges where both nodes exist in our data
    cols = set(df_raw.columns)
    edges = [(u, v) for u, v in directed_edges if u in cols and v in cols]

    G = nx.DiGraph()
    G.add_nodes_from(df_raw.columns)

    # Compute correlation-based edge weights
    corr = df_raw.corr()
    for u, v in edges:
        w = abs(corr.loc[u, v]) if (u in corr.columns and v in corr.columns) else 0.1
        G.add_edge(u, v, weight=round(float(w), 4))

    print(f"✅ Domain graph built — {G.number_of_edges()} edges.")
    return G


# ═══════════════════════════════════════════════════════════
# VALIDATE & PRUNE
# ═══════════════════════════════════════════════════════════

def validate_dag(G: nx.DiGraph) -> nx.DiGraph:
    """
    Ensure G is a valid DAG (no cycles).
    Removes minimum edges to break cycles if found.
    """
    if nx.is_directed_acyclic_graph(G):
        print("✅ Graph is a valid DAG.")
        return G

    print("⚠️  Cycles detected — pruning…")
    # Remove cycle-causing edges one by one (lowest weight first)
    while not nx.is_directed_acyclic_graph(G):
        try:
            cycle = nx.find_cycle(G)
        except nx.NetworkXNoCycle:
            break
        # Remove lowest-weight edge in the cycle
        weakest = min(cycle, key=lambda e: G[e[0]][e[1]].get("weight", 0))
        G.remove_edge(*weakest[:2])
        print(f"   Removed edge: {weakest[0]} → {weakest[1]}")

    print(f"✅ DAG valid after pruning — {G.number_of_edges()} edges remain.")
    return G


# ═══════════════════════════════════════════════════════════
# PRINT RESULTS
# ═══════════════════════════════════════════════════════════

def print_edges(G: nx.DiGraph) -> None:
    print("\n📊 DISCOVERED CAUSAL RELATIONSHIPS:")
    edges_sorted = sorted(G.edges(data=True), key=lambda e: e[2].get("weight", 0), reverse=True)
    for i, (u, v, data) in enumerate(edges_sorted, 1):
        w = data.get("weight", 0)
        bar = "█" * int(w * 20)
        print(f"   {i:2d}. {u:25s} → {v:20s}  (strength: {w:.3f})  {bar}")


# ═══════════════════════════════════════════════════════════
# VISUALISE
# ═══════════════════════════════════════════════════════════

def plot_causal_graph(G: nx.DiGraph, method_name: str = "") -> None:
    """Save a clean visualisation of the causal graph."""
    fig, ax = plt.subplots(figsize=(16, 11))

    # Layout — hierarchical makes causality direction clear
    try:
        pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
    except Exception:
        pos = nx.spring_layout(G, k=2.5, iterations=60, seed=42)

    # Node colours: decision = gold; psychological traits = salmon; others = lightblue
    psych_nodes  = {"loss_aversion", "herd_sensitivity", "disposition_strength", "risk_tolerance"}
    market_nodes = {"market_return", "crowd_ratio"}
    outcome_node = {"decision"}

    def _colour(n):
        if n in outcome_node:  return "#FFD700"
        if n in psych_nodes:   return "#FA8072"
        if n in market_nodes:  return "#90EE90"
        return "#ADD8E6"

    node_colours = [_colour(n) for n in G.nodes()]
    weights      = [G[u][v].get("weight", 0.1) * 4 for u, v in G.edges()]

    nx.draw_networkx_nodes(G, pos, node_size=2800, node_color=node_colours, ax=ax, alpha=0.9)
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight="bold", ax=ax)
    nx.draw_networkx_edges(
        G, pos,
        width=weights,
        edge_color="gray",
        arrows=True,
        arrowsize=25,
        connectionstyle="arc3,rad=0.1",
        ax=ax,
    )
    # Edge weight labels
    edge_labels = {(u, v): f"{d.get('weight', 0):.2f}" for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=7, ax=ax)

    # Legend
    from matplotlib.patches import Patch
    legend = [
        Patch(color="#FFD700", label="Outcome (decision)"),
        Patch(color="#FA8072", label="Psychological trait"),
        Patch(color="#90EE90", label="Market condition"),
        Patch(color="#ADD8E6", label="Position state"),
    ]
    ax.legend(handles=legend, loc="lower right", fontsize=9)

    title = f"Causal Graph — What Drives Financial Decisions?"
    if method_name:
        title += f"\n(method: {method_name})"
    ax.set_title(title, fontsize=14, pad=12)
    ax.axis("off")
    plt.tight_layout()

    out = os.path.join(FIGURES, "causal_graph.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ Causal graph saved → {out}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def run_structure_learning(w_threshold: float = 0.3) -> nx.DiGraph:
    print("\n" + "═" * 55)
    print("  GAP 1 | Causal Structure Learning")
    print("═" * 55)

    df_raw, df_norm, scaler = load_causal_data(normalize=True)
    save_scaler(scaler)

    # Try algorithms in priority order
    G = learn_notears(df_norm, w_threshold=w_threshold)
    method = "NOTEARS (CausalNex)"

    if G is None or G.number_of_edges() == 0:
        G = learn_hillclimb(df_raw)
        method = "Hill-Climb BIC (pgmpy)"

    if G is None or G.number_of_edges() == 0:
        G = build_domain_graph(df_raw)
        method = "Domain-Knowledge + Correlations"

    G = validate_dag(G)
    print_edges(G)
    plot_causal_graph(G, method_name=method)

    # Save
    bundle = {"graph": G, "method": method, "nodes": list(G.nodes()), "edges": list(G.edges(data=True))}
    with open(GRAPH_PKL, "wb") as f:
        pickle.dump(bundle, f)
    print(f"\n✅ Graph saved → {GRAPH_PKL}")
    print(f"   Method used: {method}")
    print("═" * 55 + "\n")

    return G


def load_causal_graph() -> tuple[nx.DiGraph, str]:
    """Load saved causal graph. Returns (graph, method_name)."""
    with open(GRAPH_PKL, "rb") as f:
        bundle = pickle.load(f)
    return bundle["graph"], bundle["method"]


if __name__ == "__main__":
    run_structure_learning()
