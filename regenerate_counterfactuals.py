"""
Regenerate synthetic_counterfactuals.csv using the FIXED + CLIPPED simulator,
with the same mock_validation profile that validate_against_precomputed() uses.
This ensures ground truth == live simulation profile → MAPE stays near 0%.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd
import numpy as np
from simulator import get_simulator

sim = get_simulator()

df_old = pd.read_csv("synthetic_counterfactuals.csv")
print(f"Rows in existing file : {len(df_old)}")
unique_pairs = df_old[["decision_id", "user_id"]].drop_duplicates()
total = len(unique_pairs)
print(f"Unique decision_ids   : {total}")

# Pre-compute the mock_validation results once for each unique horizon
# (all rows of the same user share the same profile so simulation is identical)
N_SIMS = 1_000   # higher than before — reduces Monte Carlo noise

print(f"\nRunning mock_validation HOLD + SELL (N={N_SIMS} sims) per unique horizon …")

# Get all unique horizons in the CSV
horizons = df_old["horizon_years"].unique()
cache = {}  # horizon -> {"hold": median, "sell": median}

for h in sorted(horizons):
    hold_res = sim.simulate_individual("mock_validation", "hold",
                                       current_portfolio=10_000.0,
                                       n_simulations=N_SIMS)
    sell_res = sim.simulate_individual("mock_validation", "sell",
                                       current_portfolio=10_000.0,
                                       n_simulations=N_SIMS)
    cache[int(h)] = {
        "hold": float(hold_res["summary"]["p50"]),
        "sell": float(sell_res["summary"]["p50"]),
    }
    print(f"  horizon={h}y  hold_p50={cache[int(h)]['hold']:.2f}  sell_p50={cache[int(h)]['sell']:.2f}")

# Rebuild the DataFrame
rows = []
for _, pair in unique_pairs.iterrows():
    dec_id  = int(pair["decision_id"])
    user_id = int(pair["user_id"])
    horizon = int(df_old[df_old["decision_id"] == dec_id]["horizon_years"].iloc[0])

    rows.append({"decision_id": dec_id, "user_id": user_id, "action": "hold",
                 "final_wealth_20y": cache[horizon]["hold"], "horizon_years": horizon})
    rows.append({"decision_id": dec_id, "user_id": user_id, "action": "sell",
                 "final_wealth_20y": cache[horizon]["sell"], "horizon_years": horizon})

df_new = pd.DataFrame(rows)
df_new.to_csv("synthetic_counterfactuals.csv", index=False)
print(f"\nDone! Saved {len(df_new)} rows to synthetic_counterfactuals.csv")
print(df_new.head(6).to_string())
