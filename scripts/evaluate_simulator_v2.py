"""
Evaluate simulation v2 (Phase A3) and compare it with v1.

    D:/FolioEnv/venv313/Scripts/python.exe scripts/evaluate_simulator_v2.py

Writes results/reports/simulator_v2_evaluation.json (every number in
results/reports/SIMULATOR_V2.md).

1. Realism   — simulated NIFTY paths against real rolling returns, 2007-2026.
2. Horizon   — how the answer moves with the investor's horizon (v1 was fixed at 20).
3. v1 vs v2  — the same positions through both engines.
4. Stock vs fund, short- vs long-term tax.
5. Sensitivity — growth rates, stock-specific risk, where the sale goes,
   and replaying history exactly.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import simulator_v2 as S  # noqa: E402

REPORT = os.path.join(ROOT, "results", "reports", "simulator_v2_evaluation.json")

# A typical investor: ₹18 lakh a year (20.8% slab on interest), ₹11 lakh liquid.
BASE = dict(position_value=100_000.0, cost_basis=120_000.0, months_held=18, asset_type="equity",
            horizon_years=20, annual_income=1_800_000.0, other_equity=350_000.0, gold=150_000.0,
            fixed_deposits=350_000.0, savings=150_000.0, monthly_sip=15_000.0)


def run(**kw) -> dict:
    return S.simulate(S.SimInputs(**{**BASE, **kw}))


def brief(r: dict) -> dict:
    c = r["comparison"]
    return {"horizon": r["horizon_years"], "prob_hold_better": round(c["prob_hold_better"], 3),
            "typical_gap": round(c["opportunity_cost_inr"]), "hold_median": round(r["hold"]["p50"]),
            "sell_median": round(r["sell"]["p50"]), "hold_bad_case": round(r["hold"]["p10"]),
            "sell_bad_case": round(r["sell"]["p10"])}


def realism(hist: pd.DataFrame) -> dict:
    """Index-only paths (no stock-specific risk) against real rolling windows."""
    rng = np.random.default_rng(1)
    out = {}
    for basis in ("long-run assumptions", "historical"):
        eq, _ = S._log_returns(hist, basis == "historical")
        idx = S._bootstrap(rng, 4000, 120, len(hist))
        cum = np.cumsum(eq[idx], axis=1)
        one = np.exp(cum[:, 11]) - 1
        ten = np.exp(cum[:, 119] / 10) - 1
        dd = (np.exp(cum - np.maximum.accumulate(np.maximum(cum, 0), axis=1)) - 1).min(axis=1)
        out[f"simulated ({basis})"] = {
            "1y_return_p10": round(float(np.percentile(one, 10)), 3),
            "1y_return_median": round(float(np.median(one)), 3),
            "1y_return_p90": round(float(np.percentile(one, 90)), 3),
            "share_of_years_below_minus_20pct": round(float((one < -0.20).mean()), 3),
            "10y_growth_a_year_p10": round(float(np.percentile(ten, 10)), 3),
            "10y_growth_a_year_median": round(float(np.median(ten)), 3),
            "10y_growth_a_year_p90": round(float(np.percentile(ten, 90)), 3),
            "worst_fall_in_10y_median": round(float(np.median(dd)), 3),
        }
    lr = np.log1p(hist["equity"].to_numpy())
    roll1 = np.exp(pd.Series(lr).rolling(12).sum().dropna().to_numpy()) - 1
    roll10 = np.exp(pd.Series(lr).rolling(120).sum().dropna().to_numpy() / 10) - 1
    out["real NIFTY (rolling windows)"] = {
        "1y_return_p10": round(float(np.percentile(roll1, 10)), 3),
        "1y_return_median": round(float(np.median(roll1)), 3),
        "1y_return_p90": round(float(np.percentile(roll1, 90)), 3),
        "share_of_years_below_minus_20pct": round(float((roll1 < -0.20).mean()), 3),
        "10y_growth_a_year_p10": round(float(np.percentile(roll10, 10)), 3),
        "10y_growth_a_year_median": round(float(np.median(roll10)), 3),
        "10y_growth_a_year_p90": round(float(np.percentile(roll10, 90)), 3),
        "windows": {"1y": int(len(roll1)), "10y": int(len(roll10))},
    }
    v1 = np.load(os.path.join(ROOT, "synthetic_market_paths.npy"))
    v1_one = np.clip(v1[:, 0], -0.99, 2.0)
    out["v1 synthetic paths"] = {
        "1y_return_p10": round(float(np.percentile(v1_one, 10)), 3),
        "1y_return_median": round(float(np.median(v1_one)), 3),
        "1y_return_p90": round(float(np.percentile(v1_one, 90)), 3),
        "share_of_years_below_minus_20pct": round(float((v1_one < -0.20).mean()), 3),
    }
    return out


def v1_compare(position: float, cost: float, horizon_note: str = "fixed 20 years") -> dict:
    """The old engine on the same position (backend/core/simulator.py's v1 path)."""
    from src.simulator import LongHorizonSimulator

    profile = {"age": 38, "risk_tolerance": 0.55, "investment_horizon": 20,
               "monthly_income": 150_000, "monthly_expense": 40_000, "goal": "wealth growth"}

    class _Sim(LongHorizonSimulator):
        def _get_user_profile(self, user_id):
            return dict(profile)

        def _get_stock_allocation(self, risk_tolerance, age, horizon):
            return 0.40   # this investor's equity share (see BASE)

    gl = position / cost - 1
    r = _Sim(n_simulations=1000).compare_hold_vs_sell("app", cost, gl)
    return {"horizon": f"20 ({horizon_note})", "prob_hold_better": round(r["comparison"]["prob_hold_better"], 3),
            "average_gap": round(r["comparison"]["opportunity_cost_inr"]), "hold_median": round(r["hold"]["p50"]),
            "sell_median": round(r["sell"]["p50"]), "sell_start": round(r["sell"]["starting_wealth"])}


NIFTY_NAMES = ("HDFCBANK INFY RELIANCE ITC ASIANPAINT SBIN TCS ICICIBANK LT HINDUNILVR BHARTIARTL KOTAKBANK "
               "AXISBANK MARUTI SUNPHARMA TITAN BAJFINANCE WIPRO NTPC TATASTEEL ONGC M&M ULTRACEMCO NESTLEIND").split()


def measured_stocks() -> dict:
    """Beta and specific volatility for 24 NIFTY 50 stocks, and what each means for the base case."""
    from backend.services.prices import _yf_risk

    rows = []
    for name in NIFTY_NAMES:
        risk = _yf_risk(f"{name}.NS")
        if not risk:
            continue
        r = brief(run(beta=risk["beta"], specific_vol=risk["specific_vol"]))
        rows.append({"stock": name, "beta": risk["beta"], "specific_vol": risk["specific_vol"],
                     "prob_hold_better_20y": r["prob_hold_better"], "hold_median": r["hold_median"]})
    vols = sorted(x["specific_vol"] for x in rows)
    return {"stocks": rows, "median_specific_vol": vols[len(vols) // 2] if vols else None,
            "median_beta": sorted(x["beta"] for x in rows)[len(rows) // 2] if rows else None}


def main() -> int:
    t0 = time.time()
    hist = S.load_history()
    report: dict = {"generated": time.strftime("%Y-%m-%d"),
                    "history": {"months": len(hist), "from": str(hist.month.min().date()), "to": str(hist.month.max().date()),
                                "equity_growth_a_year": round(float(np.exp(np.log1p(hist.equity).mean() * 12) - 1), 4),
                                "equity_volatility": round(float(hist.equity.std() * 12 ** 0.5), 4),
                                "gold_growth_a_year": round(float(np.exp(np.log1p(hist.gold).mean() * 12) - 1), 4),
                                "gold_volatility": round(float(hist.gold.std() * 12 ** 0.5), 4),
                                "equity_gold_correlation": round(float(hist.equity.corr(hist.gold)), 3)},
                    "assumptions": S.ASSUMPTIONS, "tax": {k: v for k, v in S.TAX.items() if k != "slabs"},
                    "base_case": {k: v for k, v in BASE.items()}}

    report["realism"] = realism(hist)

    # Horizon: a stock down 17% (₹1 lakh, bought for ₹1.2 lakh), and a fund up 30%.
    report["horizon_effect"] = {
        "stock_down_17pct": [brief(run(horizon_years=h)) for h in (1, 3, 5, 10, 20, 30)],
        "fund_up_30pct": [brief(run(asset_type="mf", cost_basis=100_000 / 1.3, horizon_years=h)) for h in (1, 3, 5, 10, 20, 30)],
    }

    # v1 vs v2 on the same positions.
    cases = {
        "stock_down_17pct": dict(),
        "stock_up_30pct_long_term": dict(cost_basis=100_000 / 1.3),
        "stock_up_30pct_short_term": dict(cost_basis=100_000 / 1.3, months_held=8),
        "fund_up_30pct": dict(asset_type="mf", cost_basis=100_000 / 1.3),
    }
    report["v1_vs_v2"] = {}
    for name, kw in cases.items():
        r20 = run(**kw)
        r5 = run(horizon_years=5, **kw)
        report["v1_vs_v2"][name] = {
            "v1": v1_compare(100_000.0, kw.get("cost_basis", BASE["cost_basis"])),
            "v2_20y": {**brief(r20), "sale": r20["sale"]},
            "v2_5y": brief(r5),
        }

    # Sensitivity on the base case (stock down 17%, 20 years).
    base = brief(run())
    sens = {"base": base}
    sens["history_replayed_exactly"] = brief(run(historical_growth=True))
    for label, a in (("equity_9pct", {"equity_growth": 0.09}), ("equity_13pct", {"equity_growth": 0.13}),
                     ("stock_risk_15pct", {"stock_specific_vol": 0.15}), ("stock_risk_35pct", {"stock_specific_vol": 0.35}),
                     ("gold_6pct", {"gold_growth": 0.06})):
        sens[label] = brief(run(assumptions={**S.ASSUMPTIONS, **a}))
    sens["sale_all_to_fd"] = brief(run(gold=0.0, savings=0.0))
    sens["sale_all_to_gold"] = brief(run(fixed_deposits=0.0, savings=0.0))
    sens["low_income_no_slab_tax"] = brief(run(annual_income=900_000.0))
    report["sensitivity"] = sens

    # Each stock's own risk, measured the way the app measures it at submission.
    report["measured_stocks"] = measured_stocks()

    # Monthly investing: the SIP sets the portfolio, not the decision gap.
    no_sip, sip = run(monthly_sip=0.0), run()
    edu = run(education_monthly=20_000.0, years_until_education_ends=6)
    report["portfolio_context"] = {
        "no_sip": no_sip["portfolio"], "sip_15000": sip["portfolio"], "sip_plus_fees_freed_in_6y": edu["portfolio"],
        "gap_unchanged_by_sip": abs(no_sip["comparison"]["opportunity_cost_inr"] - sip["comparison"]["opportunity_cost_inr"]) < 1,
    }

    t = time.perf_counter()
    for _ in range(5):
        run(horizon_years=30)
    report["runtime_ms_30y_1000_paths"] = round((time.perf_counter() - t) / 5 * 1000, 1)
    report["runtime_seconds"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps({k: report[k] for k in ("realism", "horizon_effect", "v1_vs_v2", "sensitivity")}, indent=1))
    print("runtime per 30y simulation:", report["runtime_ms_30y_1000_paths"], "ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
