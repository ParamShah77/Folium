"""
Add diverse borderline herd samples to improve herd generalisation.

Usage:
  python scripts/fix_herd_diversity.py
  python scripts/fix_herd_diversity.py --n-borderline 200 --seed 42
"""

from __future__ import annotations

import argparse
import os
from uuid import uuid4

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS_PATH = os.path.join(ROOT, "synthetic_decisions.csv")
USERS_PATH = os.path.join(ROOT, "synthetic_users.csv")
BIAS_PROFILES_PATH = os.path.join(ROOT, "synthetic_bias_profiles.csv")


def _next_numeric_ids(series: pd.Series, n_new: int) -> np.ndarray:
    numeric_ids = pd.to_numeric(series, errors="coerce")
    max_id = int(np.nanmax(numeric_ids.to_numpy())) if numeric_ids.notna().any() else 0
    return np.arange(max_id + 1, max_id + 1 + n_new, dtype=int)


def _next_decision_ids(series: pd.Series, n_new: int) -> list:
    numeric_ids = pd.to_numeric(series, errors="coerce")
    if numeric_ids.notna().all():
        start = int(numeric_ids.max()) + 1
        return list(range(start, start + n_new))
    return [str(uuid4()) for _ in range(n_new)]


def _market_regime_from_return(values: np.ndarray) -> np.ndarray:
    regime = np.full(len(values), "normal", dtype=object)
    regime[values < -0.15] = "severe_crash"
    regime[(values >= -0.15) & (values < -0.08)] = "correction"
    return regime


def _build_new_herd_frame(n_borderline: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    new_herd = {
        "herd_sensitivity": rng.uniform(0.45, 0.80, n_borderline),
        "crowd_action_ratio": rng.uniform(0.45, 0.80, n_borderline),
        "unrealized_gain_loss": rng.uniform(-0.10, 0.15, n_borderline),
        "market_return_recent": rng.uniform(-0.08, 0.08, n_borderline),
        "loss_aversion": rng.beta(2, 5, n_borderline) * 3,
        "disposition_strength": rng.beta(2, 4, n_borderline),
        "age": rng.integers(22, 65, n_borderline),
        "risk_tolerance": rng.uniform(2.0, 8.0, n_borderline),
        "investment_horizon": rng.integers(2, 25, n_borderline),
        "monthly_income": rng.uniform(30000, 180000, n_borderline),
        "market_volatility": rng.uniform(0.08, 0.35, n_borderline),
        "position_size_pct": rng.uniform(0.05, 0.50, n_borderline),
        "holding_period_months": rng.integers(1, 36, n_borderline),
        "has_emergency_fund": rng.choice([0, 1], n_borderline, p=[0.35, 0.65]),
        "bias_type": ["herd"] * n_borderline,
        "decision": ["sell"] * n_borderline,
    }

    df_new = pd.DataFrame(new_herd)
    df_new["loss_aversion"] = np.minimum(
        df_new["loss_aversion"],
        df_new["herd_sensitivity"] * 0.8,
    )
    return df_new


def fix_herd_diversity(n_borderline: int = 200, seed: int = 42) -> None:
    print(f"Loading {DECISIONS_PATH} ...")
    decisions = pd.read_csv(DECISIONS_PATH)
    users = pd.read_csv(USERS_PATH)
    bias_profiles = pd.read_csv(BIAS_PROFILES_PATH)

    # Some legacy rows have float user IDs due to prior synthetic noise.
    # Normalize to integer keys so merges with users/profiles are lossless.
    decisions["user_id"] = pd.to_numeric(decisions["user_id"], errors="coerce").round().astype(int)
    users["user_id"] = pd.to_numeric(users["user_id"], errors="coerce").round().astype(int)
    bias_profiles["user_id"] = pd.to_numeric(bias_profiles["user_id"], errors="coerce").round().astype(int)

    print("\nClass distribution BEFORE:")
    before_counts = decisions["bias_type"].value_counts()
    print(before_counts.to_string())
    print(f"Total rows: {len(decisions)}")

    # 1) Generate diverse borderline herd rows in latent/full feature space.
    df_new = _build_new_herd_frame(n_borderline=n_borderline, seed=seed)

    # 2) Prepare linked user/profile rows so merge_datasets has complete context.
    new_user_ids = _next_numeric_ids(users["user_id"], n_borderline)
    expense_ratio = np.random.default_rng(seed + 1).uniform(0.45, 0.90, n_borderline)
    monthly_expense = df_new["monthly_income"].to_numpy() * expense_ratio
    monthly_surplus = df_new["monthly_income"].to_numpy() - monthly_expense
    years_investing = np.minimum(
        np.random.default_rng(seed + 2).integers(0, 31, n_borderline),
        np.maximum(df_new["age"].to_numpy() - 18, 0),
    )

    user_rows = pd.DataFrame(
        {
            "user_id": new_user_ids,
            "age": df_new["age"].astype(int).to_numpy(),
            "monthly_income": df_new["monthly_income"].round(2).to_numpy(),
            "monthly_expense": np.round(monthly_expense, 2),
            "monthly_surplus": np.round(monthly_surplus, 2),
            "financial_strategy": np.random.default_rng(seed + 3).choice(
                ["saving", "balanced", "family_support", "credit_card"],
                size=n_borderline,
                p=[0.45, 0.25, 0.20, 0.10],
            ),
            "has_emergency_fund": df_new["has_emergency_fund"].astype(bool).to_numpy(),
            "age_horizon_mismatch": np.where(
                (df_new["age"].to_numpy() >= 55)
                & (df_new["investment_horizon"].to_numpy() >= 15),
                "old_long",
                "normal",
            ),
            "years_investing": years_investing,
            "investment_experience": np.where(
                years_investing >= 15,
                "expert",
                np.where(years_investing >= 6, "intermediate", "novice"),
            ),
            "risk_tolerance": df_new["risk_tolerance"].round(4).to_numpy(),
            "investment_horizon": df_new["investment_horizon"].astype(int).to_numpy(),
            "goal": np.random.default_rng(seed + 4).choice(
                ["wealth growth", "retirement"],
                size=n_borderline,
                p=[0.80, 0.20],
            ),
        }
    )

    profile_rows = pd.DataFrame(
        {
            "user_id": new_user_ids,
            "disposition_strength": df_new["disposition_strength"].to_numpy(),
            "loss_aversion": df_new["loss_aversion"].to_numpy(),
            "herd_sensitivity": df_new["herd_sensitivity"].to_numpy(),
        }
    )

    # 3) Build decision rows and match synthetic_decisions.csv schema exactly.
    decisions_rows = pd.DataFrame(
        {
            "decision_id": _next_decision_ids(decisions["decision_id"], n_borderline),
            "user_id": new_user_ids,
            "market_return_recent": df_new["market_return_recent"].to_numpy(),
            "unrealized_gain_loss": df_new["unrealized_gain_loss"].to_numpy(),
            "crowd_action_ratio": df_new["crowd_action_ratio"].to_numpy(),
            "decision": ["sell"] * n_borderline,
            "bias_present": ["yes"] * n_borderline,
            "bias_type": ["herd"] * n_borderline,
            "market_regime": _market_regime_from_return(df_new["market_return_recent"].to_numpy()),
            "market_volatility": df_new["market_volatility"].to_numpy(),
            "crash_speed": np.random.default_rng(seed + 5).choice(
                ["gradual_bear", "normal", "rapid_decline"],
                size=n_borderline,
                p=[0.35, 0.30, 0.35],
            ),
            "position_size_pct": df_new["position_size_pct"].to_numpy(),
            "holding_period_months": df_new["holding_period_months"].to_numpy(),
            "secondary_biases": np.random.default_rng(seed + 6).choice(
                ["none", "loss_aversion", "overconfidence"],
                size=n_borderline,
                p=[0.70, 0.20, 0.10],
            ),
        }
    )

    for col in decisions.columns:
        if col not in decisions_rows.columns:
            decisions_rows[col] = np.nan
    decisions_rows = decisions_rows[decisions.columns]

    # 4) Append and persist.
    updated_decisions = pd.concat([decisions, decisions_rows], ignore_index=True)
    updated_decisions = updated_decisions.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    updated_users = pd.concat([users, user_rows], ignore_index=True)
    updated_profiles = pd.concat([bias_profiles, profile_rows], ignore_index=True)

    updated_decisions.to_csv(DECISIONS_PATH, index=False)
    updated_users.to_csv(USERS_PATH, index=False)
    updated_profiles.to_csv(BIAS_PROFILES_PATH, index=False)

    print("\nClass distribution AFTER:")
    after_counts = updated_decisions["bias_type"].value_counts()
    print(after_counts.to_string())
    print(f"Total rows: {len(updated_decisions)}")

    herd_count = int(after_counts.get("herd", 0))
    assert herd_count >= 580, (
        f"Herd count validation failed: {herd_count} < 580. "
        "Expected 400 original + ~200 borderline samples."
    )

    print("\nValidation checks:")
    print(f"  Added borderline herd rows: {n_borderline}")
    print(f"  Herd count: {herd_count}")
    print(
        "  Constraint satisfied: loss_aversion < herd_sensitivity for all new rows = "
        f"{bool((profile_rows['loss_aversion'] < profile_rows['herd_sensitivity']).all())}"
    )
    print("\nRun data_preparation.py next to regenerate features")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add diverse borderline herd samples.")
    parser.add_argument("--n-borderline", type=int, default=200, help="Number of new borderline herd samples.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    fix_herd_diversity(n_borderline=args.n_borderline, seed=args.seed)
