"""
scripts/generate_expanded_dataset.py

Generates 1,200 diverse herd samples + 400 diverse loss_aversion samples
and appends them to synthetic_decisions.csv and synthetic_users.csv.

Design principles:
  - Herd samples: crowd_action_ratio driven, unrealized_gain_loss constrained
    per fix_herd_disposition_overlap.py rules (|gl| <= 0.10).
    Wide demographic diversity across 8 sub-profiles.
  - Loss_aversion samples: unrealized_gain_loss strongly negative (-0.05 to -0.50),
    crowd_action_ratio LOW-to-MODERATE (not herd-driven), high market_volatility.
    6 sub-profiles covering different loss magnitudes and investor types.
  - All new rows have unique UUIDs and non-overlapping user_ids (>= 1457).

Run from project root:
    python scripts/generate_expanded_dataset.py
"""
import uuid
import os
import sys
import numpy as np
import pandas as pd

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED   = 7331
rng    = np.random.default_rng(SEED)

DEC_PATH   = os.path.join(ROOT, "synthetic_decisions.csv")
USERS_PATH = os.path.join(ROOT, "synthetic_users.csv")

# ── Load existing data ────────────────────────────────────────────────
existing_dec   = pd.read_csv(DEC_PATH)
existing_users = pd.read_csv(USERS_PATH)
MAX_USER_ID    = int(existing_users["user_id"].max()) + 1
print(f"Existing decisions: {len(existing_dec)}  |  existing users: {len(existing_users)}")
print(f"New user IDs start at: {MAX_USER_ID}")

# Helper: clip to 4 decimal places
def clip4(x):
    return np.round(x, 4)

# ═══════════════════════════════════════════════════════════════════════
# HERD SAMPLES — 1,200 rows across 8 sub-profiles
# ═══════════════════════════════════════════════════════════════════════

def gen_herd(n_per_profile: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    8 sub-profiles, n_per_profile samples each = 8 × n_per_profile total.

    Key constraints (per fix_herd_disposition_overlap.py):
      - crowd_action_ratio >= 0.45 always
      - unrealized_gain_loss in [-0.10, +0.20] (no deep losses)
      - crowd_action_ratio >= 3 × |unrealized_gain_loss| if gl < 0
      - market_volatility <= 0.28 (no extreme panic)
    """
    profiles = [
        # (name, crowd_range, gl_range, mret_range, regime, crash_speed, vol_range)
        ("mild_bear_crowd",       (0.60, 0.80), (-0.05, 0.05),  (-0.08, 0.00), "normal",        "gradual_bear",  (0.02, 0.10)),
        ("strong_herd_neutral",   (0.80, 0.99), (-0.02, 0.10),  (-0.03, 0.06), "normal",        "normal",        (0.02, 0.06)),
        ("moderate_herd_bull",    (0.55, 0.75), (0.00,  0.20),  (0.02,  0.09), "bull",          "normal",        (0.02, 0.04)),
        ("high_crowd_correction", (0.75, 0.99), (-0.08, 0.02),  (-0.10, -0.01),"correction",    "gradual_bear",  (0.10, 0.25)),
        ("mixed_signal_herd",     (0.50, 0.70), (-0.04, 0.08),  (-0.05, 0.05), "normal",        "normal",        (0.02, 0.08)),
        ("panic_herd_low_loss",   (0.70, 0.99), (-0.10, -0.01), (-0.11, -0.03),"correction",    "normal",        (0.15, 0.28)),
        ("euphoria_herd",          (0.65, 0.90), (0.05,  0.20),  (0.05,  0.09), "bull",          "normal",        (0.02, 0.04)),
        ("contrarian_mild_herd",   (0.45, 0.60), (-0.03, 0.10),  (-0.05, 0.04), "normal",        "normal",        (0.02, 0.06)),
    ]

    rows = []
    for (name, cr_range, gl_range, mret_range,
         regime, crash_speed, vol_range) in profiles:

        n = n_per_profile
        cr   = clip4(rng.uniform(*cr_range,   size=n))
        gl   = clip4(rng.uniform(*gl_range,   size=n))
        mret = clip4(rng.uniform(*mret_range, size=n))
        vol  = clip4(rng.uniform(*vol_range,  size=n))

        # Enforce: crowd >= 3 × |gl| minimum 0.45 when gl < 0
        mask = gl < 0
        cr[mask] = np.maximum(cr[mask], np.minimum(3.0 * np.abs(gl[mask]), 0.99))
        cr = np.clip(cr, 0.45, 0.99)

        # Derived market_regime from mret
        def regime_from_ret(r):
            if r <= -0.10:  return "severe_crash"
            if r <= -0.03:  return "correction"
            if r <=  0.03:  return "normal"
            if r <=  0.08:  return "bull"
            return "euphoria"
        regimes = [regime_from_ret(r) for r in mret]

        # Volatility clamp
        vol = np.clip(vol, 0.015, 0.28)

        # Random secondary_biases (77% none, 15% loss_aversion, 8% overconfidence)
        sec_bias = rng.choice(
            ["none", "loss_aversion", "overconfidence"],
            size=n, p=[0.77, 0.15, 0.08]
        )
        pos_size   = clip4(rng.uniform(0.03, 0.55,  size=n))
        hold_months = np.round(rng.uniform(6, 60, size=n), 2)

        for i in range(n):
            rows.append({
                "market_return_recent"  : mret[i],
                "unrealized_gain_loss"  : gl[i],
                "crowd_action_ratio"    : cr[i],
                "decision"              : "sell",
                "bias_present"          : "yes",
                "bias_type"             : "herd",
                "market_regime"         : regimes[i],
                "market_volatility"     : vol[i],
                "crash_speed"           : crash_speed,
                "position_size_pct"     : pos_size[i],
                "holding_period_months" : hold_months[i],
                "secondary_biases"      : sec_bias[i],
            })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# LOSS_AVERSION SAMPLES — 400 rows across 6 sub-profiles
# ═══════════════════════════════════════════════════════════════════════

def gen_loss_aversion(n_per_profile: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    6 sub-profiles, n_per_profile samples each.

    Key characteristics:
      - unrealized_gain_loss strongly NEGATIVE (-0.05 to -0.55)
      - crowd_action_ratio LOW-to-MODERATE (0.05 to 0.55)
        (distinguishes from herd: herd has cr >= 0.45 with low loss)
      - market_volatility moderate-to-high (0.05 to 0.45)
      - decision: sell (panic selling due to loss aversion)
    """
    profiles = [
        # (name, gl_range, cr_range, mret_range, vol_range, crash_speed)
        ("mild_loss_low_crowd",    (-0.10, -0.05), (0.05, 0.35), (-0.12, -0.02), (0.05, 0.20), "normal"),
        ("moderate_loss_solo",     (-0.25, -0.10), (0.10, 0.45), (-0.18, -0.05), (0.10, 0.30), "gradual_bear"),
        ("severe_loss_isolated",   (-0.45, -0.25), (0.05, 0.30), (-0.25, -0.10), (0.20, 0.45), "rapid_decline"),
        ("loss_w_moderate_crowd",  (-0.20, -0.06), (0.30, 0.55), (-0.15, -0.02), (0.08, 0.30), "normal"),
        ("panic_loss_high_vol",    (-0.35, -0.15), (0.10, 0.40), (-0.22, -0.08), (0.25, 0.45), "rapid_decline"),
        ("small_loss_stubborn",    (-0.08, -0.05), (0.05, 0.25), (-0.06, 0.00),  (0.03, 0.15), "normal"),
    ]

    rows = []
    for (name, gl_range, cr_range, mret_range,
         vol_range, crash_speed) in profiles:

        n = n_per_profile
        gl   = clip4(rng.uniform(*gl_range,   size=n))
        cr   = clip4(rng.uniform(*cr_range,   size=n))
        mret = clip4(rng.uniform(*mret_range, size=n))
        vol  = clip4(rng.uniform(*vol_range,  size=n))
        vol  = np.clip(vol, 0.015, 0.45)

        def regime_from_ret(r):
            if r <= -0.10:  return "severe_crash"
            if r <= -0.03:  return "correction"
            if r <=  0.03:  return "normal"
            if r <=  0.08:  return "bull"
            return "euphoria"
        regimes = [regime_from_ret(r) for r in mret]

        sec_bias = rng.choice(
            ["none", "overconfidence", "herd"],
            size=n, p=[0.80, 0.12, 0.08]
        )
        pos_size   = clip4(rng.uniform(0.05, 0.65, size=n))
        hold_months = np.round(rng.uniform(3, 60, size=n), 2)

        for i in range(n):
            rows.append({
                "market_return_recent"  : mret[i],
                "unrealized_gain_loss"  : gl[i],
                "crowd_action_ratio"    : cr[i],
                "decision"              : "sell",
                "bias_present"          : "yes",
                "bias_type"             : "loss_aversion",
                "market_regime"         : regimes[i],
                "market_volatility"     : vol[i],
                "crash_speed"           : crash_speed,
                "position_size_pct"     : pos_size[i],
                "holding_period_months" : hold_months[i],
                "secondary_biases"      : sec_bias[i],
            })

    return pd.DataFrame(rows)


# ── Generate the new decision rows ───────────────────────────────────
print("\nGenerating herd samples (8 profiles × 150 = 1,200)...")
herd_df = gen_herd(n_per_profile=150, rng=rng)
print(f"  Generated: {len(herd_df)} herd rows")

print("Generating loss_aversion samples (6 profiles × 67 ≈ 400)...")
# 67 × 6 = 402 ≈ 400 (we'll trim to exactly 400)
la_df = gen_loss_aversion(n_per_profile=67, rng=rng)
la_df = la_df.iloc[:400]
print(f"  Generated: {len(la_df)} loss_aversion rows")

new_decisions_raw = pd.concat([herd_df, la_df], ignore_index=True)
N_NEW = len(new_decisions_raw)
print(f"\nTotal new decision rows: {N_NEW}")

# ── Assign new user IDs ───────────────────────────────────────────────
new_user_ids = np.arange(MAX_USER_ID, MAX_USER_ID + N_NEW)
new_decisions_raw["user_id"] = new_user_ids

# ── Generate matching user rows ───────────────────────────────────────
print("Generating matching user profile rows...")

fin_strategies  = ["saving", "investing", "credit_card", "family_support"]
fin_strat_p     = [0.40, 0.35, 0.15, 0.10]
experiences     = ["beginner", "novice", "intermediate", "expert"]
experience_p    = [0.20, 0.25, 0.35, 0.20]
goals           = ["retirement", "wealth growth", "education", "emergency"]
goals_p         = [0.35, 0.40, 0.15, 0.10]
mismatch_opts   = ["normal", "old_long", "young_short"]
mismatch_p      = [0.70, 0.20, 0.10]

ages             = rng.integers(22, 65, size=N_NEW)
risk_tols        = np.round(rng.uniform(0.01, 8.0, size=N_NEW), 6)
inv_horizons     = rng.integers(2, 30, size=N_NEW)
incomes          = np.round(rng.uniform(27000, 250000, size=N_NEW), 2)
expenses_pct     = rng.uniform(0.40, 0.95, size=N_NEW)
expenses         = np.round(incomes * expenses_pct, 2)
surpluses        = np.round(incomes - expenses, 2)
has_fund         = rng.choice([True, False], size=N_NEW, p=[0.55, 0.45])
years_inv        = rng.integers(0, 31, size=N_NEW)
fin_strat_arr    = rng.choice(fin_strategies, size=N_NEW, p=fin_strat_p)
exp_arr          = rng.choice(experiences, size=N_NEW, p=experience_p)
goals_arr        = rng.choice(goals, size=N_NEW, p=goals_p)
mismatch_arr     = rng.choice(mismatch_opts, size=N_NEW, p=mismatch_p)

new_users = pd.DataFrame({
    "user_id"             : new_user_ids,
    "age"                 : ages,
    "monthly_income"      : incomes,
    "monthly_expense"     : expenses,
    "monthly_surplus"     : surpluses,
    "financial_strategy"  : fin_strat_arr,
    "has_emergency_fund"  : has_fund,
    "age_horizon_mismatch": mismatch_arr,
    "years_investing"     : years_inv,
    "investment_experience": exp_arr,
    "risk_tolerance"      : risk_tols,
    "investment_horizon"  : inv_horizons,
    "goal"                : goals_arr,
})
print(f"  Generated: {len(new_users)} user rows")

# ── Assign decision_ids (UUID) ────────────────────────────────────────
new_decisions_raw["decision_id"] = [str(uuid.uuid4()) for _ in range(N_NEW)]

# ── Reorder columns to match existing CSV ────────────────────────────
DECISION_COLS = [
    "decision_id", "user_id", "market_return_recent", "unrealized_gain_loss",
    "crowd_action_ratio", "decision", "bias_present", "bias_type",
    "market_regime", "market_volatility", "crash_speed",
    "position_size_pct", "holding_period_months", "secondary_biases",
]
new_decisions = new_decisions_raw[DECISION_COLS]

# ── Validation checks ────────────────────────────────────────────────
print("\nValidating generated herd samples...")
h_check = new_decisions[new_decisions["bias_type"] == "herd"]
print(f"  crowd_action_ratio >= 0.45 for all: {(h_check['crowd_action_ratio'] >= 0.45).all()}")
print(f"  unrealized_gain_loss in [-0.10, 0.20]: "
      f"min={h_check['unrealized_gain_loss'].min():.4f}, "
      f"max={h_check['unrealized_gain_loss'].max():.4f}")
print(f"  market_volatility <= 0.28: {(h_check['market_volatility'] <= 0.28).all()}")

# Check crowd >= 3 * |gl| for gl < 0
mask_neg_gl = h_check["unrealized_gain_loss"] < 0
violated = h_check[mask_neg_gl & (
    h_check["crowd_action_ratio"] < 3.0 * h_check["unrealized_gain_loss"].abs()
)]
print(f"  Crowd >= 3x |gl| constraint violations: {len(violated)}")

print("\nValidating generated loss_aversion samples...")
la_check = new_decisions[new_decisions["bias_type"] == "loss_aversion"]
print(f"  unrealized_gain_loss < 0 for all: {(la_check['unrealized_gain_loss'] < 0).all()}")
print(f"  crowd_action_ratio <= 0.55 (mostly low): "
      f"mean={la_check['crowd_action_ratio'].mean():.3f}, "
      f"max={la_check['crowd_action_ratio'].max():.3f}")

# ── Append to existing files ──────────────────────────────────────────
print("\nAppending to synthetic_decisions.csv...")
combined_decisions = pd.concat([existing_dec, new_decisions], ignore_index=True)
combined_decisions.to_csv(DEC_PATH, index=False)
print(f"  New total: {len(combined_decisions)} rows")
print(f"  Class distribution:")
print(combined_decisions["bias_type"].value_counts().to_string())

print("\nAppending to synthetic_users.csv...")
combined_users = pd.concat([existing_users, new_users], ignore_index=True)
combined_users.to_csv(USERS_PATH, index=False)
print(f"  New total: {len(combined_users)} rows")

print("\nDone. Run python src/data_preparation.py next.")
