"""
Top up loss_aversion diversity by generating broad, realistic synthetic samples.

Usage:
  python scripts/fix_loss_aversion_diversity.py
  python scripts/fix_loss_aversion_diversity.py --target 400 --seed 42
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


def _market_regime_from_return(x: np.ndarray) -> np.ndarray:
    regime = np.full(len(x), "normal", dtype=object)
    regime[x < -0.15] = "severe_crash"
    regime[(x >= -0.15) & (x < -0.08)] = "correction"
    return regime


def _next_user_ids(existing_ids: pd.Series, n_new: int) -> np.ndarray:
    numeric_ids = pd.to_numeric(existing_ids, errors="coerce")
    max_id = int(np.nanmax(numeric_ids.to_numpy())) if numeric_ids.notna().any() else 0
    return np.arange(max_id + 1, max_id + 1 + n_new, dtype=int)


def _next_decision_ids(existing_ids: pd.Series, n_new: int) -> list:
    numeric_ids = pd.to_numeric(existing_ids, errors="coerce")
    if numeric_ids.notna().all():
        start = int(numeric_ids.max()) + 1
        return list(range(start, start + n_new))
    return [str(uuid4()) for _ in range(n_new)]


def fix_loss_aversion_diversity(target: int = 400, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)

    decisions = pd.read_csv(DECISIONS_PATH)
    users = pd.read_csv(USERS_PATH)
    bias_profiles = pd.read_csv(BIAS_PROFILES_PATH)

    print("Class distribution BEFORE:")
    print(decisions["bias_type"].value_counts().to_string())

    current_loss_aversion = int((decisions["bias_type"] == "loss_aversion").sum())
    n_new = max(0, target - current_loss_aversion)

    if n_new == 0:
        print(f"No action required. Existing loss_aversion samples: {current_loss_aversion} (>= {target}).")
        return

    print(
        f"Generating {n_new} new diverse loss_aversion samples "
        f"({current_loss_aversion} -> {target})."
    )

    new_user_ids = _next_user_ids(users["user_id"], n_new)

    # Broad user profile diversity (used downstream after merge).
    age = rng.integers(25, 65, n_new)
    monthly_income = rng.uniform(25000, 200000, n_new)
    expense_ratio = rng.uniform(0.45, 0.95, n_new)
    monthly_expense = monthly_income * expense_ratio
    monthly_surplus = monthly_income - monthly_expense
    investment_horizon = rng.integers(2, 30, n_new)
    has_emergency_fund = rng.choice([False, True], n_new, p=[0.4, 0.6])
    years_investing = np.minimum(rng.integers(0, 31, n_new), np.maximum(age - 18, 0))

    new_users = pd.DataFrame(
        {
            "user_id": new_user_ids,
            "age": age,
            "monthly_income": monthly_income.round(2),
            "monthly_expense": monthly_expense.round(2),
            "monthly_surplus": monthly_surplus.round(2),
            "financial_strategy": rng.choice(
                ["saving", "balanced", "family_support", "credit_card"], n_new, p=[0.45, 0.25, 0.2, 0.1]
            ),
            "has_emergency_fund": has_emergency_fund,
            "age_horizon_mismatch": np.where((age >= 55) & (investment_horizon >= 15), "old_long", "normal"),
            "years_investing": years_investing,
            "investment_experience": np.where(
                years_investing >= 15,
                "expert",
                np.where(years_investing >= 6, "intermediate", "novice"),
            ),
            "risk_tolerance": rng.uniform(1.0, 6.0, n_new).round(4),
            "investment_horizon": investment_horizon,
            "goal": rng.choice(["wealth growth", "retirement"], n_new, p=[0.75, 0.25]),
        }
    )

    # Explicit bias profile constraints for new rows.
    loss_aversion_score = (rng.beta(6, 2, n_new) * 4 + 1)
    loss_aversion_score = np.clip(loss_aversion_score, 2.51, 5.0)
    herd_sensitivity = np.clip(rng.beta(2, 6, n_new), 0.0, 0.39)

    new_bias_profiles = pd.DataFrame(
        {
            "user_id": new_user_ids,
            "disposition_strength": rng.beta(2, 4, n_new),
            "loss_aversion": loss_aversion_score,
            "herd_sensitivity": herd_sensitivity,
        }
    )

    market_return_recent = rng.uniform(-0.25, -0.03, n_new)
    unrealized_gain_loss = rng.uniform(-0.45, -0.05, n_new)
    crowd_action_ratio = rng.uniform(0.20, 0.90, n_new)

    new_decisions = pd.DataFrame(
        {
            "decision_id": _next_decision_ids(decisions["decision_id"], n_new),
            "user_id": new_user_ids,
            "market_return_recent": market_return_recent,
            "unrealized_gain_loss": unrealized_gain_loss,
            "crowd_action_ratio": crowd_action_ratio,
            "decision": ["sell"] * n_new,
            "bias_present": ["yes"] * n_new,
            "bias_type": ["loss_aversion"] * n_new,
            "market_regime": _market_regime_from_return(market_return_recent),
            "market_volatility": rng.uniform(0.10, 0.45, n_new),
            "crash_speed": rng.choice(["gradual_bear", "normal", "rapid_decline"], n_new, p=[0.45, 0.25, 0.30]),
            "position_size_pct": rng.uniform(0.05, 0.60, n_new),
            "holding_period_months": rng.integers(1, 48, n_new),
            "secondary_biases": rng.choice(["none", "loss_aversion", "overconfidence"], n_new, p=[0.7, 0.2, 0.1]),
        }
    )

    # Keep schema/order exact.
    for col in decisions.columns:
        if col not in new_decisions.columns:
            new_decisions[col] = np.nan
    new_decisions = new_decisions[decisions.columns]

    # Match original user_id dtype in decisions file if needed.
    if pd.api.types.is_float_dtype(decisions["user_id"]):
        new_decisions["user_id"] = new_decisions["user_id"].astype(float)

    generated_preview = new_decisions.copy()

    updated_decisions = pd.concat([decisions, new_decisions], ignore_index=True)
    updated_decisions = updated_decisions.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    updated_users = pd.concat([users, new_users], ignore_index=True)
    updated_profiles = pd.concat([bias_profiles, new_bias_profiles], ignore_index=True)

    updated_decisions.to_csv(DECISIONS_PATH, index=False)
    updated_users.to_csv(USERS_PATH, index=False)
    updated_profiles.to_csv(BIAS_PROFILES_PATH, index=False)

    print("\nClass distribution AFTER:")
    after_counts = updated_decisions["bias_type"].value_counts()
    print(after_counts.to_string())

    updated_loss_aversion = int(after_counts.get("loss_aversion", 0))
    print(f"\nloss_aversion count after fix: {updated_loss_aversion}")
    if updated_loss_aversion < 350:
        raise RuntimeError(
            f"Validation failed: loss_aversion count is {updated_loss_aversion}, expected >= 350."
        )

    # Diversity checks for generated rows only.
    generated = generated_preview
    print("\nGenerated loss_aversion range checks:")
    print(f"market_return_recent: {generated['market_return_recent'].min():.4f} .. {generated['market_return_recent'].max():.4f}")
    print(f"unrealized_gain_loss: {generated['unrealized_gain_loss'].min():.4f} .. {generated['unrealized_gain_loss'].max():.4f}")
    print(f"crowd_action_ratio  : {generated['crowd_action_ratio'].min():.4f} .. {generated['crowd_action_ratio'].max():.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Top up and diversify loss_aversion samples.")
    parser.add_argument("--target", type=int, default=400, help="Target total loss_aversion samples (default: 400)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    fix_loss_aversion_diversity(target=args.target, seed=args.seed)
