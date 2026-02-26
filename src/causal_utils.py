"""
GAP 1 – Week 3 (Person 2): Causal Data Utilities
==================================================
Loads Person 1's processed data, extracts causal-relevant columns,
normalises them, and provides helper functions used by both
causal_structure.py and causal_inference.py.

Run standalone to verify:
    python src/causal_utils.py
"""

import os
import pickle

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED  = os.path.join(ROOT, "data", "processed")
MODELS_DIR = os.path.join(ROOT, "models")
RESULTS    = os.path.join(ROOT, "results")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.join(RESULTS, "figures"), exist_ok=True)

# ─────────────────────────────────────────────
# COLUMNS
# ─────────────────────────────────────────────

# Variables used for causal graph learning
CAUSAL_VARS = [
    # External market forces
    "market_return_recent",
    "crowd_action_ratio",
    # User psychological traits (from bias_profiles — safe here as we
    # are doing causal analysis, not training a classifier)
    "disposition_strength_profile",
    "loss_aversion_profile",
    "herd_sensitivity_profile",
    # Current position state
    "unrealized_gain_loss",
    # Risk profile
    "risk_tolerance",
    # Outcome variable
    "decision_label",          # 0=hold, 1=sell
]

# Human-friendly column rename map (for plots)
RENAME_MAP = {
    "market_return_recent"    : "market_return",
    "crowd_action_ratio"      : "crowd_ratio",
    "disposition_strength_profile": "disposition_strength",
    "loss_aversion_profile"   : "loss_aversion",
    "herd_sensitivity_profile": "herd_sensitivity",
    "unrealized_gain_loss"    : "unrealized_gl",
    "risk_tolerance"          : "risk_tolerance",
    "decision_label"          : "decision",
}


# ═══════════════════════════════════════════════════════════
# LOAD
# ═══════════════════════════════════════════════════════════

def load_causal_data(normalize: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, StandardScaler]:
    """
    Load merged_features.csv, keep only causal variables,
    optionally normalize.

    Returns:
        df_raw   – raw (un-normalized) causal DataFrame (short column names)
        df_norm  – z-score normalized DataFrame (for NOTEARS)
        scaler   – fitted StandardScaler (inverse_transform when needed)
    """
    merged_path = os.path.join(PROCESSED, "merged_features.csv")
    if not os.path.exists(merged_path):
        raise FileNotFoundError(
            f"merged_features.csv not found at {merged_path}.\n"
            "Run  python src/data_preparation.py  first."
        )

    df = pd.read_csv(merged_path)

    # Ensure decision_label exists
    if "decision_label" not in df.columns:
        le_map = {"hold": 0, "sell": 1}
        df["decision_label"] = df["decision"].map(le_map)

    # Keep only what we need
    available = [c for c in CAUSAL_VARS if c in df.columns]
    missing   = set(CAUSAL_VARS) - set(available)
    if missing:
        print(f"⚠️  Missing causal vars (will skip): {missing}")

    df_raw = df[available].rename(columns=RENAME_MAP).dropna()
    print(f"✅ Causal dataset: {df_raw.shape}  |  columns: {list(df_raw.columns)}")

    if not normalize:
        return df_raw, df_raw.copy(), None

    scaler  = StandardScaler()
    arr     = scaler.fit_transform(df_raw)
    df_norm = pd.DataFrame(arr, columns=df_raw.columns)

    return df_raw, df_norm, scaler


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def save_scaler(scaler: StandardScaler, name: str = "causal_scaler.pkl") -> None:
    path = os.path.join(MODELS_DIR, name)
    with open(path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"✅ Scaler saved → {path}")


def load_scaler(name: str = "causal_scaler.pkl") -> StandardScaler:
    path = os.path.join(MODELS_DIR, name)
    with open(path, "rb") as f:
        return pickle.load(f)


def summarize_causal_data(df: pd.DataFrame) -> None:
    """Print a quick statistical summary relevant for causal analysis."""
    print("\n" + "─" * 55)
    print("  Causal Dataset Summary")
    print("─" * 55)
    print(df.describe().round(3).to_string())
    print("\nCorrelation with decision:")
    corr = df.corr()["decision"].drop("decision").sort_values(key=abs, ascending=False)
    for col, val in corr.items():
        bar = "█" * int(abs(val) * 20)
        sign = "+" if val > 0 else "-"
        print(f"  {col:25s}  {sign}{abs(val):.3f}  {bar}")
    print("─" * 55 + "\n")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    df_raw, df_norm, scaler = load_causal_data(normalize=True)
    summarize_causal_data(df_raw)
    save_scaler(scaler)
    print("causal_utils.py ✅ complete")
