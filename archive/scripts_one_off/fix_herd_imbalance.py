"""
scripts/fix_herd_imbalance.py
================================
Fixes the herd class imbalance in synthetic_decisions.csv by generating
additional synthetic herd samples whose feature distributions match real
herd investor profiles from synthetic_users.csv.

Generation rules
----------------
  herd_sensitivity  ~ Beta(alpha=5, beta=2)  → right-skewed toward 1.0, > 0.65
  crowd_action_ratio ~ Uniform(0.65, 0.95)
  market_return      ~ Uniform(-0.05, +0.10)
  Other continuous features are sampled from existing herd user profiles
  in synthetic_users.csv (stratified random pick with replacement).

Target
------
  ~400 herd samples total (balanced with other classes at ~1000 each → total ~5400)

Usage
-----
  python scripts/fix_herd_imbalance.py
  python scripts/fix_herd_imbalance.py --target 400 --seed 42
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS  = os.path.join(ROOT, "synthetic_decisions.csv")
USERS      = os.path.join(ROOT, "synthetic_users.csv")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def fix_herd_imbalance(target: int = 400, seed: int = 42) -> None:
    """
    Load decisions CSV, generate synthetic herd samples, save updated CSV.

    Parameters
    ----------
    target : int  — desired total herd sample count (default 400)
    seed   : int  — numpy random seed for reproducibility
    """
    rng = np.random.default_rng(seed)

    # ── Load datasets ────────────────────────────────────────────────────
    print(f"Loading {DECISIONS} …")
    df_dec  = pd.read_csv(DECISIONS)
    print(f"Loading {USERS} …")
    df_usr  = pd.read_csv(USERS)

    # ── Class distribution before ────────────────────────────────────────
    print("\n📊 Class distribution BEFORE:")
    before_counts = df_dec["bias_type"].value_counts()
    print(before_counts.to_string())
    print(f"   Total rows: {len(df_dec)}\n")

    # ── Identify herd rows ───────────────────────────────────────────────
    herd_mask   = df_dec["bias_type"] == "herd"
    current_cnt = int(herd_mask.sum())
    n_to_add    = max(0, target - current_cnt)

    if n_to_add == 0:
        print(f"✅ Herd class already has {current_cnt} samples (≥ {target}). No action needed.")
        return

    print(f"ℹ️  Current herd samples: {current_cnt} | Target: {target} | Generating: {n_to_add}")

    # ── Build herd-user profile pool ─────────────────────────────────────
    # Identify users with high herd tendency (from bias profiles if available,
    # otherwise just use all users as a pool — we override the key herd features anyway)
    user_pool    = df_usr.sample(n=n_to_add, replace=True, random_state=seed).reset_index(drop=True)

    # ── Identify columns present in decisions CSV ─────────────────────────
    dec_cols = df_dec.columns.tolist()

    # ── Generate synthetic herd features ────────────────────────────────
    synthetic = pd.DataFrame()

    # KEY HERD FEATURES (override with herd-specific distributions)
    # herd_sensitivity > 0.65: Beta(5, 2), reject < 0.65
    hs_raw = beta_dist.rvs(a=5, b=2, size=n_to_add * 3, random_state=seed)
    hs_filtered = hs_raw[hs_raw > 0.65][:n_to_add]
    if len(hs_filtered) < n_to_add:
        # Top-up if not enough after filter
        extra = rng.uniform(0.65, 0.99, n_to_add - len(hs_filtered))
        hs_filtered = np.concatenate([hs_filtered, extra])
    synthetic["herd_sensitivity"] = hs_filtered[:n_to_add]

    # crowd_action_ratio ~ Uniform(0.65, 0.95)
    synthetic["crowd_action_ratio"] = rng.uniform(0.65, 0.95, n_to_add)

    # market_return ~ Uniform(-0.05, +0.10)  (herd happens in both directions)
    synthetic["market_return"] = rng.uniform(-0.05, 0.10, n_to_add)

    # bias_type
    synthetic["bias_type"] = "herd"

    # ── Fill remaining columns from user pool + small noise ─────────────
    user_numeric = ["age", "income", "risk_tolerance", "investment_horizon",
                    "monthly_income", "has_emergency_fund"]

    # Map user columns to decision columns where names match or are close
    col_map = {
        "age"               : "age",
        "income"            : "monthly_income",
        "monthly_income"    : "monthly_income",
        "risk_tolerance"    : "risk_tolerance",
        "investment_horizon": "investment_horizon",
        "has_emergency_fund": "has_emergency_fund",
    }
    for usr_col, dec_col in col_map.items():
        if usr_col in user_pool.columns and dec_col in dec_cols:
            vals = user_pool[usr_col].values[:n_to_add]
            if np.issubdtype(vals.dtype, np.floating):
                noise = rng.normal(0, 0.02 * abs(vals.mean() + 1e-6), n_to_add)
                synthetic[dec_col] = np.clip(vals + noise, 0, None)
            else:
                synthetic[dec_col] = vals

    # Fill other numeric columns from existing herd rows (sample with replacement)
    existing_herd = df_dec[herd_mask]
    for col in dec_cols:
        if col in synthetic.columns or col == "bias_type":
            continue
        if col in existing_herd.columns:
            sampled = existing_herd[col].sample(
                n=n_to_add, replace=True, random_state=seed
            ).values
            # Add small Gaussian noise to numeric columns
            if pd.api.types.is_numeric_dtype(existing_herd[col]):
                std = float(existing_herd[col].std())
                if std > 0:
                    sampled = sampled.astype(float) + rng.normal(0, 0.05 * std, n_to_add)
            synthetic[col] = sampled

    # Ensure all decision columns are present
    for col in dec_cols:
        if col not in synthetic.columns:
            synthetic[col] = np.nan

    # Reorder columns to match original
    synthetic = synthetic[dec_cols]

    # Generate unique decision_ids for new rows (if column exists)
    if "decision_id" in synthetic.columns:
        import uuid
        synthetic["decision_id"] = [str(uuid.uuid4()) for _ in range(n_to_add)]

    # ── Append and save ──────────────────────────────────────────────────
    df_out = pd.concat([df_dec, synthetic], ignore_index=True)

    # Shuffle to avoid all herd rows at the end
    df_out = df_out.sample(frac=1, random_state=seed).reset_index(drop=True)

    df_out.to_csv(DECISIONS, index=False)
    print(f"✅ Saved updated dataset → {DECISIONS}")

    # ── Class distribution after ─────────────────────────────────────────
    print("\n📊 Class distribution AFTER:")
    after_counts = df_out["bias_type"].value_counts()
    print(after_counts.to_string())
    print(f"   Total rows: {len(df_out)}\n")

    delta = after_counts.get("herd", 0) - before_counts.get("herd", 0)
    print(f"🎯 Herd samples added: {delta}  ({current_cnt} → {after_counts.get('herd', 0)})")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fix herd class imbalance in synthetic_decisions.csv"
    )
    parser.add_argument(
        "--target", type=int, default=400,
        help="Target total herd sample count (default: 400)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)"
    )
    args = parser.parse_args()
    fix_herd_imbalance(target=args.target, seed=args.seed)
