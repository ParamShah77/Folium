"""
GAP 1 – Week 1: Data Preparation
=================================
Loads synthetic datasets, merges them, engineers features,
and writes train/test splits to data/processed/.

Run:
    python src/data_preparation.py
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = ROOT                      # CSVs live at project root
PROCESSED_DIR = os.path.join(ROOT, "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# STEP 1 ─ LOAD RAW DATA
# ═══════════════════════════════════════════════════════════

def load_raw_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all three synthetic datasets."""
    decisions   = pd.read_csv(os.path.join(RAW_DIR, "synthetic_decisions.csv"))
    users       = pd.read_csv(os.path.join(RAW_DIR, "synthetic_users.csv"))
    bias_profile= pd.read_csv(os.path.join(RAW_DIR, "synthetic_bias_profiles.csv"))

    print(f"✅ Loaded decisions:     {decisions.shape}")
    print(f"✅ Loaded users:         {users.shape}")
    print(f"✅ Loaded bias_profiles: {bias_profile.shape}")
    return decisions, users, bias_profile


# ═══════════════════════════════════════════════════════════
# STEP 2 ─ MERGE
# ═══════════════════════════════════════════════════════════

def merge_datasets(
    decisions: pd.DataFrame,
    users: pd.DataFrame,
    bias_profiles: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge on user_id.
    bias_profiles is validation-only → we ADD it here for EDA/causal work
    but it must NOT be used as a training feature (that would be label leakage).
    """
    df = decisions.merge(users, on="user_id", how="left")

    # Suffix causal/validation columns with _profile so they are easy to exclude
    df = df.merge(
        bias_profiles.rename(columns={
            "disposition_strength": "disposition_strength_profile",
            "loss_aversion":        "loss_aversion_profile",
            "herd_sensitivity":     "herd_sensitivity_profile",
        }),
        on="user_id",
        how="left",
    )
    print(f"✅ Merged dataset shape: {df.shape}")
    return df


# ═══════════════════════════════════════════════════════════
# STEP 3 ─ FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create ML-ready features from raw columns."""

    # ── 3a. Market regime ──────────────────────────────────
    # Classifies overall market conditions
    df["market_regime"] = pd.cut(
        df["market_return_recent"],
        bins=[-np.inf, -0.10, -0.03, 0.03, 0.10, np.inf],
        labels=["crash", "bear", "neutral", "bull", "rally"],
    ).astype(str)

    # ── 3b. Loss magnitude category ────────────────────────
    df["loss_magnitude"] = pd.cut(
        df["unrealized_gain_loss"],
        bins=[-np.inf, -0.20, -0.10, -0.05, 0.0, np.inf],
        labels=["severe_loss", "large_loss", "small_loss", "no_loss", "gain"],
    ).astype(str)

    # ── 3c. Crowd pressure level ───────────────────────────
    # crowd_action_ratio: fraction of crowd selling (1 = everyone selling)
    df["crowd_pressure"] = pd.cut(
        df["crowd_action_ratio"],
        bins=[-np.inf, 0.30, 0.50, 0.70, np.inf],
        labels=["contrarian", "mixed", "moderate_herd", "strong_herd"],
    ).astype(str)

    # ── 3d. Interaction features ───────────────────────────
    # Loss × crowd effect (key driver of panic selling)
    df["loss_x_crowd"] = df["unrealized_gain_loss"] * df["crowd_action_ratio"]

    # Loss × market (crash amplifies loss pain)
    df["loss_x_market"] = df["unrealized_gain_loss"] * df["market_return_recent"]

    # ── 3e. Risk-adjusted features ─────────────────────────
    # How loss feels relative to user's risk tolerance
    df["risk_tolerance"] = df["risk_tolerance"].fillna(df["risk_tolerance"].median())
    df["loss_vs_risk_tolerance"] = df["unrealized_gain_loss"] / (
        df["risk_tolerance"].replace(0, 1e-6)
    )

    # How much time left to recover
    df["investment_horizon"] = df["investment_horizon"].fillna(
        df["investment_horizon"].median()
    )

    # Age-time interaction: younger = more runway
    df["age_horizon_ratio"] = df["age"] / (df["investment_horizon"] + 1)

    # ── 3f. Financial stress indicator ────────────────────
    df["financial_stress"] = (
        (~df["has_emergency_fund"].astype(bool))
        .astype(int)
        * (df["monthly_surplus"] < 0).astype(int)
    )

    # ── 3g. Monthly surplus normalized ────────────────────
    df["surplus_normalized"] = df["monthly_surplus"] / (
        df["monthly_income"].replace(0, 1e-6)
    )

    print("✅ Feature engineering complete.")
    print(f"   Columns now: {list(df.columns)}")
    return df


# ═══════════════════════════════════════════════════════════
# STEP 4 ─ ENCODE CATEGORICAL TARGETS
# ═══════════════════════════════════════════════════════════

def encode_labels(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Encode:
      - bias_type  → integer label  (0=rational, 1=loss_aversion, 2=herd, 3=other)
      - decision   → binary flag 0/1
    Returns df with new columns + label mapping dict.
    """
    le_bias = LabelEncoder()
    df["bias_label"] = le_bias.fit_transform(df["bias_type"])

    le_decision = LabelEncoder()
    df["decision_label"] = le_decision.fit_transform(df["decision"])

    mappings = {
        "bias": dict(zip(le_bias.classes_, le_bias.transform(le_bias.classes_))),
        "decision": dict(
            zip(le_decision.classes_, le_decision.transform(le_decision.classes_))
        ),
    }
    print(f"✅ Label encodings: {mappings}")
    return df, mappings


# ═══════════════════════════════════════════════════════════
# STEP 5 ─ TRAIN / TEST SPLIT
# ═══════════════════════════════════════════════════════════

#  ⚠️  EXCLUDE profile columns (validation only) + raw string targets
PROFILE_COLS = [
    "disposition_strength_profile",
    "loss_aversion_profile",
    "herd_sensitivity_profile",
    "bias_type",     # raw string → use bias_label instead
    "decision",      # raw string → use decision_label instead
    "bias_present",  # direct leakage of label
    "user_id",       # identifier, not a feature
    "decision_id",
]

FEATURE_COLS = [
    "market_return_recent",
    "unrealized_gain_loss",
    "crowd_action_ratio",
    "age",
    "monthly_income",
    "monthly_expense",
    "monthly_surplus",
    "risk_tolerance",
    "investment_horizon",
    # engineered
    "loss_x_crowd",
    "loss_x_market",
    "loss_vs_risk_tolerance",
    "age_horizon_ratio",
    "financial_stress",
    "surplus_normalized",
]

CATEGORICAL_FEATURES = [
    "market_regime",
    "loss_magnitude",
    "crowd_pressure",
    "financial_strategy",
]


def prepare_train_test(
    df: pd.DataFrame,
    test_size: float = 0.20,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into train / test, save indices."""

    # One-hot encode categoricals
    df_encoded = pd.get_dummies(df, columns=CATEGORICAL_FEATURES, drop_first=True)

    # Determine available feature columns (some categoricals expand)
    available = [c for c in df_encoded.columns if c not in PROFILE_COLS]
    # Remove target columns from features
    X_cols = [c for c in available if c not in ("bias_label", "decision_label")]

    X = df_encoded[X_cols]
    y = df_encoded["bias_label"]

    X_train, X_test, _, _ = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    train_idx = X_train.index.to_numpy()
    test_idx  = X_test.index.to_numpy()

    np.save(os.path.join(PROCESSED_DIR, "train_indices.npy"), train_idx)
    np.save(os.path.join(PROCESSED_DIR, "test_indices.npy"),  test_idx)
    print(f"✅ Train size: {len(train_idx)}, Test size: {len(test_idx)}")

    return df_encoded.loc[train_idx], df_encoded.loc[test_idx]


# ═══════════════════════════════════════════════════════════
# STEP 6 ─ SAVE MERGED FEATURES
# ═══════════════════════════════════════════════════════════

def save_merged(df: pd.DataFrame) -> None:
    path = os.path.join(PROCESSED_DIR, "merged_features.csv")
    df.to_csv(path, index=False)
    print(f"✅ Saved merged_features.csv → {path}")


# ═══════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════

def run_pipeline() -> pd.DataFrame:
    """End-to-end data preparation. Returns the full engineered DataFrame."""
    print("\n" + "═" * 55)
    print("  GAP 1 | Data Preparation Pipeline")
    print("═" * 55)

    decisions, users, bias_profiles = load_raw_data()
    df = merge_datasets(decisions, users, bias_profiles)
    df = engineer_features(df)
    df, label_mappings = encode_labels(df)
    train_df, test_df = prepare_train_test(df)
    save_merged(df)

    print("\n✅ Pipeline complete!")
    print(f"   Label mappings: {label_mappings}")
    print(f"   Saved to: {PROCESSED_DIR}")
    print("═" * 55 + "\n")
    return df


if __name__ == "__main__":
    run_pipeline()
