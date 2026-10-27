"""
Evaluations for the journal paper (Applications of Modelling and Simulation).

    D:/FolioEnv/venv313/Scripts/python.exe scripts/evaluate_for_paper.py
    D:/FolioEnv/venv313/Scripts/python.exe scripts/evaluate_for_paper.py --quick   # smaller, for a smoke test

Writes results/reports/paper_evaluation.json (every number in
results/reports/PAPER_EVALUATION.md).

1. Classifier baselines — majority, rules only, logistic regression, random
   forest and the XGBoost model on the same split, five split seeds, and
   bootstrap confidence intervals on the paper's split.
2. Market generator validation — the 12-month block bootstrap against an
   independent-months bootstrap and a lognormal (GBM) generator, all with
   the same drift, compared with real NIFTY rolling windows.
3. Monte Carlo convergence — how the answer settles as futures are added.
4. Population — the paired simulation over 1,000 investors and positions
   drawn from the v4 dataset, under the long-run assumptions and with
   history replayed exactly (where the answer flips).
5. Sensitivity — one change at a time, on the base case and on a 300-case
   sub-population: growth, stock risk, block length, tax rules, costs,
   destination of the sale, and the kind of year the future starts in.
6. Walk-forward replay — real 5- and 10-year windows of history run through
   the same accounting, and where each real outcome falls in the simulated
   distribution.
7. Paired-scenario table — Eq. (8) done properly: the median of the
   future-by-future gap next to the difference of medians.
8. Explanations — the current pipeline (bias model v4 + simulator v2 +
   template explainer) scored with scripts/evaluate_explanations.py's metrics.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))   # the explainer imports its templates flat

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src import bias_model_v4 as M  # noqa: E402
from src import dataset_v4 as D  # noqa: E402
from src import simulator_v2 as S  # noqa: E402

REPORT = os.path.join(ROOT, "results", "reports", "paper_evaluation.json")
SIM_EVAL = os.path.join(ROOT, "results", "reports", "simulator_v2_evaluation.json")

# The base case of results/reports/SIMULATOR_V2.md: a ₹1 lakh stock bought for
# ₹1.2 lakh, investor on ₹18 lakh a year with ₹11 lakh liquid, 20 years.
BASE = dict(position_value=100_000.0, cost_basis=120_000.0, months_held=18, asset_type="equity",
            horizon_years=20, annual_income=1_800_000.0, other_equity=350_000.0, gold=150_000.0,
            fixed_deposits=350_000.0, savings=150_000.0, monthly_sip=15_000.0)

# Under the app's recommendation rules a sale is a toss-up between 40% and 60%.
def verdict(p_hold: float) -> str:
    return "hold" if p_hold > 0.60 else "sell" if p_hold < 0.40 else "toss_up"


def r4(x) -> float:
    return round(float(x), 4)


# ═════════════════════════════════════════════════════════════════════════
# 1. Classifier baselines
# ═════════════════════════════════════════════════════════════════════════

def classifier_baselines(quick: bool) -> dict:
    import xgboost as xgb
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    import train_bias_v4 as T

    df = pd.read_csv(D.DATASET_CSV, parse_dates=["date"])
    market = D.load_market_history()
    raw = M.raw_from_dataset(df)
    X = M.build_features(raw)
    y = df.bias_type.map({lab: i for i, lab in enumerate(M.LABELS)}).to_numpy()
    mask = M.allowed_mask(raw)
    w = df.regime.map(market.regime.value_counts(normalize=True) / df.regime.value_counts(normalize=True)).to_numpy()
    strat = df.bias_type + "_" + df.regime
    n_trees = json.load(open(os.path.join(ROOT, "results", "reports", "bias_v4_evaluation.json")))["training"]["n_trees"]

    def rules(mt: np.ndarray) -> np.ndarray:
        pred = np.full(len(mt), 3)
        for k in reversed([2, 0, 1]):   # loss aversion, disposition, herd — as train_bias_v4.py
            pred[mt[:, k]] = k
        return pred

    def one_hot(pred: np.ndarray) -> np.ndarray:
        p = np.full((len(pred), 4), 1e-6)
        p[np.arange(len(pred)), pred] = 1.0
        return p / p.sum(1, keepdims=True)

    def models(seed: int) -> dict:
        return {
            "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0, random_state=seed)),
            "random_forest": RandomForestClassifier(n_estimators=150 if quick else 500, min_samples_leaf=2,
                                                    n_jobs=-1, random_state=seed),
            "xgboost": xgb.XGBClassifier(n_estimators=n_trees, **{**T.PARAMS, "random_state": seed}),
        }

    def evaluate(dev: np.ndarray, te: np.ndarray, seed: int) -> tuple[dict, dict]:
        yt, wt, mt = y[te], w[te], mask[te]
        probs = {"always_rational": one_hot(np.full(len(te), 3)), "rules_only": one_hot(rules(mt))}
        for name, model in models(seed).items():
            model.fit(X.iloc[dev], y[dev])
            probs[name] = M.apply_guard(model.predict_proba(X.iloc[te]), mt)
        out = {}
        for name, p in probs.items():
            pred = p.argmax(1)
            out[name] = {"accuracy": r4(accuracy_score(yt, pred, sample_weight=wt)),
                         "macro_f1": r4(f1_score(yt, pred, average="macro", sample_weight=wt)),
                         "ece": r4(T.ece(p, yt, wt))}
            if name not in ("always_rational", "rules_only"):
                from sklearn.metrics import log_loss
                out[name]["log_loss"] = r4(log_loss(yt, np.clip(p, 1e-12, 1), sample_weight=wt, labels=range(4)))
        return out, probs

    seeds = [7, 11, 23] if quick else [7, 11, 23, 42, 101]
    per_seed, paper_split = {}, None
    for s in seeds:
        dev, te = train_test_split(np.arange(len(df)), test_size=0.2, stratify=strat, random_state=s)
        res, probs = evaluate(dev, te, s)
        per_seed[s] = res
        if s == 7:   # the split the paper and the app's model use
            paper_split = (te, probs)
        print(f"  split seed {s}: " + ", ".join(f"{k} {v['accuracy']:.3f}" for k, v in res.items()))

    names = list(per_seed[seeds[0]])
    summary = {n: {m: {"mean": r4(np.mean([per_seed[s][n][m] for s in seeds])),
                       "sd": r4(np.std([per_seed[s][n][m] for s in seeds], ddof=1))}
                   for m in per_seed[seeds[0]][n]} for n in names}

    # Bootstrap CIs on the paper split, and paired differences against XGBoost.
    te, probs = paper_split
    yt, wt = y[te], w[te]
    preds = {n: p.argmax(1) for n, p in probs.items()}
    # The deployed model (guard + calibration curve) on the same rows.
    preds["xgboost_deployed"] = M.predict_frame(raw.iloc[te])["pred"]
    rng = np.random.default_rng(0)
    B = 300 if quick else 2000
    boot = {n: [] for n in preds}
    diff = {n: [] for n in preds if n != "xgboost"}
    for _ in range(B):
        i = rng.integers(0, len(te), len(te))
        acc = {n: float(np.average(preds[n][i] == yt[i], weights=wt[i])) for n in preds}
        for n in preds:
            boot[n].append(acc[n])
        for n in diff:
            diff[n].append(acc["xgboost"] - acc[n])
    ci = {n: {"accuracy": r4(np.average(preds[n] == yt, weights=wt)),
              "ci95": [r4(np.percentile(v, 2.5)), r4(np.percentile(v, 97.5))]} for n, v in boot.items()}
    paired = {f"xgboost_minus_{n}": {"mean": r4(np.mean(v)), "ci95": [r4(np.percentile(v, 2.5)), r4(np.percentile(v, 97.5))]}
              for n, v in diff.items()}
    # McNemar on the paper split, XGBoost against each baseline (unweighted counts).
    from scipy.stats import chi2
    mcnemar = {}
    for n in preds:
        if n == "xgboost":
            continue
        a = preds["xgboost"] == yt
        b = preds[n] == yt
        n01, n10 = int((a & ~b).sum()), int((~a & b).sum())
        stat = (abs(n01 - n10) - 1) ** 2 / max(n01 + n10, 1)
        mcnemar[n] = {"xgb_right_other_wrong": n01, "other_right_xgb_wrong": n10,
                      "chi2": r4(stat), "p_value": float(f"{chi2.sf(stat, 1):.3g}")}
    return {"split_seeds": seeds, "test_rows": int(len(te)), "weights": "real regime frequency, 2008-2026",
            "per_seed": per_seed, "mean_sd_over_seeds": summary,
            "paper_split_bootstrap": {"resamples": B, "accuracy_ci": ci, "paired_difference": paired},
            "mcnemar_paper_split": mcnemar,
            "note": "All learners get the same 22 features and the same definitions guard; "
                    "xgboost uses the deployed hyper-parameters without the calibration curve, "
                    "xgboost_deployed is the shipped model with it."}


# ═════════════════════════════════════════════════════════════════════════
# 2. Market generator validation
# ═════════════════════════════════════════════════════════════════════════

def _stats_from_logs(cum: np.ndarray, monthly: np.ndarray) -> dict:
    """Summary of (paths, months) cumulative log returns and the monthly log returns."""
    one = np.exp(cum[:, 11]) - 1
    ten = np.exp(cum[:, 119] / 10) - 1
    dd = (np.exp(cum - np.maximum.accumulate(np.maximum(cum, 0), axis=1)) - 1).min(axis=1)
    x = monthly - monthly.mean(axis=1, keepdims=True)
    sq = x ** 2 - (x ** 2).mean(axis=1, keepdims=True)

    def acf(z: np.ndarray, lag: int) -> float:
        return float(((z[:, :-lag] * z[:, lag:]).mean(axis=1) / (z ** 2).mean(axis=1)).mean())

    return {
        "1y_p10": r4(np.percentile(one, 10)), "1y_median": r4(np.median(one)), "1y_p90": r4(np.percentile(one, 90)),
        "1y_below_minus_20pct": r4((one < -0.20).mean()),
        "10y_a_year_p10": r4(np.percentile(ten, 10)), "10y_a_year_median": r4(np.median(ten)),
        "10y_a_year_p90": r4(np.percentile(ten, 90)),
        "max_drawdown_10y_median": r4(np.median(dd)), "max_drawdown_10y_p10": r4(np.percentile(dd, 10)),
        "acf_returns_lag1": r4(acf(x, 1)),
        "acf_squared_lag1": r4(acf(sq, 1)), "acf_squared_lag3": r4(acf(sq, 3)), "acf_squared_lag6": r4(acf(sq, 6)),
        "_one": one, "_ten": ten,
    }


def generator_validation(hist: pd.DataFrame, n: int) -> dict:
    from scipy.stats import ks_2samp

    eq, _ = S._log_returns(hist, historical_growth=True)   # same drift for every generator
    rng = np.random.default_rng(11)
    months = 120
    gens = {}
    for b in (1, 3, 6, 12, 24):
        idx = S._bootstrap(rng, n, months, len(hist), b)
        gens[f"block_bootstrap_{b}m" if b > 1 else "iid_bootstrap"] = eq[idx]
    gens["gbm_lognormal"] = rng.normal(eq.mean(), eq.std(ddof=1), size=(n, months))

    # The real record: rolling windows (overlapping), and the series' own autocorrelations.
    lr = pd.Series(eq)
    roll1 = np.exp(lr.rolling(12).sum().dropna().to_numpy()) - 1
    roll10 = np.exp(lr.rolling(120).sum().dropna().to_numpy() / 10) - 1
    cum_real = np.cumsum(eq)
    dd_real = [float((np.exp(c - np.maximum.accumulate(np.maximum(c, 0))) - 1).min())
               for c in (np.cumsum(eq[s:s + 120]) for s in range(len(eq) - 119))]
    x = eq - eq.mean()
    sq = x ** 2 - (x ** 2).mean()

    def acf1(z: np.ndarray, lag: int) -> float:
        return float((z[:-lag] * z[lag:]).mean() / (z ** 2).mean())

    real = {"1y_p10": r4(np.percentile(roll1, 10)), "1y_median": r4(np.median(roll1)), "1y_p90": r4(np.percentile(roll1, 90)),
            "1y_below_minus_20pct": r4((roll1 < -0.20).mean()),
            "10y_a_year_p10": r4(np.percentile(roll10, 10)), "10y_a_year_median": r4(np.median(roll10)),
            "10y_a_year_p90": r4(np.percentile(roll10, 90)),
            "max_drawdown_10y_median": r4(np.median(dd_real)), "max_drawdown_10y_p10": r4(np.percentile(dd_real, 10)),
            "acf_returns_lag1": r4(acf1(x, 1)),
            "acf_squared_lag1": r4(acf1(sq, 1)), "acf_squared_lag3": r4(acf1(sq, 3)), "acf_squared_lag6": r4(acf1(sq, 6)),
            "windows": {"1y": int(len(roll1)), "10y": int(len(roll10)), "independent_10y": int(len(eq) // 120)},
            "months": int(len(eq)), "from": str(hist.month.min().date()), "to": str(hist.month.max().date())}

    out = {"real_nifty": real, "paths_per_generator": n,
           "note": "All generators use the historical mean monthly log return, so only the shape and the "
                   "dependence differ. Real windows overlap, so KS distances are descriptive, not tests."}
    for name, monthly in gens.items():
        st = _stats_from_logs(np.cumsum(monthly, axis=1), monthly)
        st["ks_distance_1y"] = r4(ks_2samp(st.pop("_one"), roll1).statistic)
        st["ks_distance_10y"] = r4(ks_2samp(st.pop("_ten"), roll10).statistic)
        out[name] = st
    return out


# ═════════════════════════════════════════════════════════════════════════
# 3. Monte Carlo convergence
# ═════════════════════════════════════════════════════════════════════════

def convergence(hist: pd.DataFrame, quick: bool) -> dict:
    sizes = (250, 500, 1000, 2000) if quick else (250, 500, 1000, 2000, 5000, 10000)
    reps = 8 if quick else 20
    rows = []
    for n in sizes:
        ps, gaps = [], []
        for r in range(reps):
            c = S.simulate(S.SimInputs(**{**BASE, "n_paths": n, "seed": 1000 + r}), hist)["comparison"]
            ps.append(c["prob_hold_better"])
            gaps.append(c["opportunity_cost_inr"])
        rows.append({"n_paths": n, "repeats": reps,
                     "prob_hold_mean": r4(np.mean(ps)), "prob_hold_sd": r4(np.std(ps, ddof=1)),
                     "median_gap_mean": round(float(np.mean(gaps))), "median_gap_sd": round(float(np.std(gaps, ddof=1))),
                     "median_gap_cv": r4(np.std(gaps, ddof=1) / abs(np.mean(gaps)))})
        print(f"  {n:>6} futures: P(hold) {rows[-1]['prob_hold_mean']:.3f} ± {rows[-1]['prob_hold_sd']:.3f}, "
              f"gap ₹{rows[-1]['median_gap_mean']:,} ± {rows[-1]['median_gap_sd']:,}")
    return {"case": "base case (stock down 17%, 20 years)", "rows": rows,
            "binomial_se_at_1000": r4(np.sqrt(0.64 * 0.36 / 1000))}


# ═════════════════════════════════════════════════════════════════════════
# 4. Population
# ═════════════════════════════════════════════════════════════════════════

def population_inputs(n: int, seed: int = 2026) -> list[dict]:
    """Investors and positions from the v4 dataset, mapped to simulator inputs.

    The position is position_share of liquid money; a fund or a stock in
    proportion to the investor's fund and stock holdings; a stock's beta and
    own swings come from one of the 24 measured NIFTY 50 stocks.
    """
    df = pd.read_csv(D.DATASET_CSV).sample(n=n, random_state=seed).reset_index(drop=True)
    stocks = json.load(open(SIM_EVAL))["measured_stocks"]["stocks"]
    rng = np.random.default_rng(seed)
    out = []
    for i, r in df.iterrows():
        equity = r.stocks_value + r.mf_value
        pos = float(np.clip(r.position_share * r.liquid_assets, 10_000, equity))
        is_fund = rng.random() < r.mf_value / max(equity, 1.0)
        kw = dict(position_value=pos, cost_basis=pos / (1 + r.unrealized_gl), months_held=int(r.holding_period_months),
                  asset_type="mf" if is_fund else "equity", horizon_years=int(np.clip(r.investment_horizon, 1, 30)),
                  annual_income=S.gross_from_take_home(r.monthly_income * 12),
                  other_equity=max(equity - pos, 0.0), gold=float(r.gold_value),
                  fixed_deposits=float(r.fixed_deposits), savings=float(r.savings_balance), seed=seed + i)
        if not is_fund:
            s = stocks[rng.integers(len(stocks))]
            kw.update(beta=s["beta"], specific_vol=s["specific_vol"])
        out.append({"inputs": kw, "case_id": int(r.case_id), "action": r.action,
                    "crowd_ratio": float(r.crowd_ratio), "has_emergency_fund": int(r.has_emergency_fund)})
    return out


def _run_population(cases: list[dict], hist: pd.DataFrame, n_paths: int, **override) -> pd.DataFrame:
    """``stock_vol`` replaces each stock's measured own swings (funds keep theirs)."""
    rows = []
    for c in cases:
        kw = {**c["inputs"], "n_paths": n_paths,
              **{k: v for k, v in override.items() if k not in ("assumptions", "stock_vol")}}
        if "assumptions" in override:
            kw["assumptions"] = {**S.ASSUMPTIONS, **override["assumptions"]}
        if "stock_vol" in override and kw["asset_type"] == "equity":
            kw["specific_vol"] = override["stock_vol"]
        res = S.simulate(S.SimInputs(**kw), hist)["comparison"]
        rows.append({"p_hold": res["prob_hold_better"], "gap": res["opportunity_cost_inr"],
                     "gap_pct": res["opportunity_cost_pct"]})
    return pd.DataFrame(rows)


def _describe(res: pd.DataFrame) -> dict:
    v = res.p_hold.map(verdict)
    return {"prob_hold_mean": r4(res.p_hold.mean()), "prob_hold_median": r4(res.p_hold.median()),
            "prob_hold_p10": r4(res.p_hold.quantile(0.1)), "prob_hold_p90": r4(res.p_hold.quantile(0.9)),
            "median_gap_pct_of_position_median": r4(res.gap_pct.median()),
            "median_gap_pct_p10": r4(res.gap_pct.quantile(0.1)), "median_gap_pct_p90": r4(res.gap_pct.quantile(0.9)),
            "share_hold": r4((v == "hold").mean()), "share_toss_up": r4((v == "toss_up").mean()),
            "share_sell": r4((v == "sell").mean())}


def population(hist: pd.DataFrame, cases: list[dict], n_paths: int) -> tuple[dict, pd.DataFrame]:
    t = time.time()
    base = _run_population(cases, hist, n_paths)
    replay = _run_population(cases, hist, n_paths, historical_growth=True)
    print(f"  population of {len(cases)} run twice in {time.time() - t:.0f}s")
    info = pd.DataFrame([{"horizon": c["inputs"]["horizon_years"], "asset": c["inputs"]["asset_type"],
                          "gain": c["inputs"]["position_value"] > c["inputs"]["cost_basis"],
                          "short_term": c["inputs"]["months_held"] <= 12} for c in cases])
    base_v, replay_v = base.p_hold.map(verdict), replay.p_hold.map(verdict)

    def by(col: pd.Series) -> dict:
        return {str(k): {"n": int(m.sum()), **_describe(base[m.to_numpy()])}
                for k, m in ((k, col == k) for k in sorted(col.unique(), key=str))}

    horizon_bucket = pd.cut(info.horizon, [0, 3, 10, 20, 30], labels=["1-3y", "4-10y", "11-20y", "21-30y"]).astype(str)
    out = {
        "cases": len(cases), "futures_per_case": n_paths,
        "inputs": {"horizon_median": int(info.horizon.median()), "fund_share": r4((info.asset == "mf").mean()),
                   "gain_share": r4(info.gain.mean()), "short_term_share": r4(info.short_term.mean()),
                   "position_median_inr": round(float(np.median([c["inputs"]["position_value"] for c in cases])))},
        "long_run_assumptions": _describe(base),
        "history_replayed": _describe(replay),
        "flip": {
            "verdict_changes": r4((base_v != replay_v).mean()),
            "hold_to_sell_or_toss_up": r4(((base_v == "hold") & (replay_v != "hold")).mean()),
            "sign_of_gap_changes": r4((np.sign(base.gap) != np.sign(replay.gap)).mean()),
            "prob_hold_shift_mean": r4((replay.p_hold - base.p_hold).mean()),
        },
        "by_horizon": by(horizon_bucket), "by_asset": by(info.asset),
        "by_gain_or_loss": by(info.gain.map({True: "gain", False: "loss"})),
        "by_tax_term": by(info.short_term.map({True: "short_term", False: "long_term"})),
    }
    return out, base


# ═════════════════════════════════════════════════════════════════════════
# 5. Sensitivity
# ═════════════════════════════════════════════════════════════════════════

@contextlib.contextmanager
def tax_rules(**rules):
    saved = dict(S.TAX)
    S.TAX.update(rules)
    try:
        yield
    finally:
        S.TAX.clear()
        S.TAX.update(saved)


#: Capital-gains rules before 23 July 2024: STCG 15%, LTCG 10% above ₹1 lakh.
PRE_JULY_2024 = dict(equity_stcg=0.15, equity_ltcg=0.10, ltcg_exemption=100_000.0)


def start_year_paths(hist: pd.DataFrame, n: int, months: int, which: str, seed: int) -> np.ndarray:
    """Bootstrap paths whose first 12 months are a real bad (bottom 10%) or good (top 10%) year."""
    eq = np.log1p(hist["equity"].to_numpy())
    year = np.array([eq[(s + np.arange(12)) % len(eq)].sum() for s in range(len(eq))])
    cut = np.percentile(year, 10 if which == "bad" else 90)
    starts = np.flatnonzero(year <= cut if which == "bad" else year >= cut)
    rng = np.random.default_rng(seed)
    idx = S._bootstrap(rng, n, months, len(hist))
    first = rng.choice(starts, size=n)
    idx[:, :12] = (first[:, None] + np.arange(12)) % len(hist)
    return idx


def sensitivity(hist: pd.DataFrame, sub: list[dict], n_paths: int) -> dict:
    variants: dict[str, dict] = {
        "equity_growth_9pct": {"assumptions": {"equity_growth": 0.09}},
        "equity_growth_13pct": {"assumptions": {"equity_growth": 0.13}},
        "gold_growth_6pct": {"assumptions": {"gold_growth": 0.06}},
        "fd_rate_5_5pct": {"assumptions": {"fd_rate": 0.055}},
        "fd_rate_8pct": {"assumptions": {"fd_rate": 0.08}},
        "stock_risk_15pct": {"assumptions": {"stock_specific_vol": 0.15}},
        "stock_risk_35pct": {"assumptions": {"stock_specific_vol": 0.35}},
        "sale_cost_0_5pct": {"assumptions": {"sale_cost": 0.005}},
        "sale_cost_1pct": {"assumptions": {"sale_cost": 0.01}},
        "block_1m_iid": {"assumptions": {"block_months": 1}},
        "block_6m": {"assumptions": {"block_months": 6}},
        "block_24m": {"assumptions": {"block_months": 24}},
        "history_replayed": {"historical_growth": True},
    }
    base_case = {"base": S.simulate(S.SimInputs(**{**BASE, "n_paths": n_paths}), hist)["comparison"]}

    def one(kw: dict, ov: dict, paths=None) -> dict:
        kw = {**kw, **{k: v for k, v in ov.items() if k != "assumptions"}}
        if "assumptions" in ov:
            kw["assumptions"] = {**S.ASSUMPTIONS, **ov["assumptions"]}
        return S.simulate(S.SimInputs(**kw), hist, paths=paths)["comparison"]

    for name, ov in variants.items():
        base_case[name] = one({**BASE, "n_paths": n_paths}, ov)
    with tax_rules(**PRE_JULY_2024):
        base_case["tax_rules_before_july_2024"] = one({**BASE, "n_paths": n_paths}, {})
    for which in ("bad", "good"):
        p = start_year_paths(hist, n_paths, BASE["horizon_years"] * 12, which, 5)
        base_case[f"starts_in_a_{which}_year"] = one({**BASE, "n_paths": n_paths}, {}, paths=p)
    base_rows = {k: {"prob_hold": r4(v["prob_hold_better"]), "median_gap_inr": round(v["opportunity_cost_inr"]),
                     "verdict": verdict(v["prob_hold_better"])} for k, v in base_case.items()}

    # The same changes over a sub-population: how many verdicts move.
    t = time.time()
    ref = _run_population(sub, hist, n_paths)
    ref_v = ref.p_hold.map(verdict)
    pop_rows = {"base": {**_describe(ref), "verdict_changes_vs_base": 0.0}}
    for name, ov in variants.items():
        if name.startswith("stock_risk_"):   # each case carries its stock's measured risk
            ov = {"stock_vol": ov["assumptions"]["stock_specific_vol"]}
        r = _run_population(sub, hist, n_paths, **ov)
        pop_rows[name] = {**_describe(r), "verdict_changes_vs_base": r4((r.p_hold.map(verdict) != ref_v).mean())}
    with tax_rules(**PRE_JULY_2024):
        r = _run_population(sub, hist, n_paths)
    pop_rows["tax_rules_before_july_2024"] = {**_describe(r), "verdict_changes_vs_base": r4((r.p_hold.map(verdict) != ref_v).mean())}
    for which in ("bad", "good"):
        rows = []
        for c in sub:
            kw = {**c["inputs"], "n_paths": n_paths}
            p = start_year_paths(hist, n_paths, kw["horizon_years"] * 12, which, kw["seed"])
            res = S.simulate(S.SimInputs(**kw), hist, paths=p)["comparison"]
            rows.append({"p_hold": res["prob_hold_better"], "gap": res["opportunity_cost_inr"], "gap_pct": res["opportunity_cost_pct"]})
        r = pd.DataFrame(rows)
        pop_rows[f"starts_in_a_{which}_year"] = {**_describe(r), "verdict_changes_vs_base": r4((r.p_hold.map(verdict) != ref_v).mean())}
    print(f"  sensitivity over {len(sub)} cases in {time.time() - t:.0f}s")
    return {"base_case": base_rows, "sub_population": {"cases": len(sub), "rows": pop_rows},
            "pre_july_2024_rules": PRE_JULY_2024}


# ═════════════════════════════════════════════════════════════════════════
# 6. Walk-forward replay of real windows
# ═════════════════════════════════════════════════════════════════════════

def walk_forward(hist: pd.DataFrame, n_paths: int) -> dict:
    """Real windows through the same accounting, and their place in the simulated distribution.

    A diversified fund (no own swings, so the real window is the whole
    story), sale into the base case's FD/savings/gold split, history's own
    growth rates (the realised windows are history).
    """
    out = {}
    for horizon in (5, 10):
        m = horizon * 12
        kw = {**BASE, "asset_type": "mf", "specific_vol": 0.0, "cost_basis": 100_000.0 / 1.3,
              "horizon_years": horizon, "historical_growth": True, "n_paths": n_paths}
        sim_gap = S.simulate(S.SimInputs(**kw), hist, return_gaps=True)["paired_gaps"][:, -1]
        real_starts = np.arange(0, len(hist) - m + 1)
        real_paths = real_starts[:, None] + np.arange(m)
        real_gap = S.simulate(S.SimInputs(**kw), hist, paths=real_paths, return_gaps=True)["paired_gaps"][:, -1]
        pit = np.array([(sim_gap < g).mean() for g in real_gap])
        out[f"{horizon}y"] = {
            "real_windows": int(len(real_gap)), "independent_windows": int(len(hist) // m),
            "real_hold_wins": r4((real_gap > 0).mean()), "simulated_hold_wins": r4((sim_gap > 0).mean()),
            "real_median_gap": round(float(np.median(real_gap))), "simulated_median_gap": round(float(np.median(sim_gap))),
            "real_inside_simulated_10_90": r4(((pit >= 0.10) & (pit <= 0.90)).mean()),
            "real_below_simulated_p10": r4((pit < 0.10).mean()), "real_above_simulated_p90": r4((pit > 0.90).mean()),
            "pit_quartiles": [r4(q) for q in np.percentile(pit, [25, 50, 75])],
        }
    out["note"] = ("Windows overlap (one per start month), so they hold only about "
                   "len(history)/horizon independent observations; coverage near 80% means the "
                   "simulated 10-90% band is about as wide as the real record.")
    return out


# ═════════════════════════════════════════════════════════════════════════
# 7. Paired-scenario table (Eq. 8)
# ═════════════════════════════════════════════════════════════════════════

def paired_table(hist: pd.DataFrame, n_paths: int) -> dict:
    rows = {}
    for label, kw in (("stock_down_17pct_14y", {**BASE, "horizon_years": 14}),
                      ("fund_up_30pct_14y", {**BASE, "horizon_years": 14, "asset_type": "mf", "cost_basis": 100_000 / 1.3})):
        res = S.simulate(S.SimInputs(**{**kw, "n_paths": n_paths}), hist, return_gaps=True)
        sale = res["sale"]
        table = [{"year": 0, "hold": round(kw["position_value"]), "sell": round(sale["proceeds"]),
                  "difference_of_medians": round(kw["position_value"] - sale["proceeds"]),
                  "median_of_paired_gaps": round(kw["position_value"] - sale["proceeds"])}]
        gaps_by_year = res["paired_gaps"]
        for y in (5, 10, 14):
            h, s = res["yearly_hold_p50"][y - 1], res["yearly_sell_p50"][y - 1]
            g = gaps_by_year[:, y - 1]
            table.append({"year": y, "hold": round(h), "sell": round(s), "difference_of_medians": round(h - s),
                          "median_of_paired_gaps": round(float(np.median(g))),
                          "paired_gap_p10": round(float(np.percentile(g, 10))),
                          "paired_gap_p90": round(float(np.percentile(g, 90))),
                          "hold_wins": r4((g > 0).mean())})
        rows[label] = {"inputs": {k: v for k, v in kw.items()}, "sale_today": sale, "rows": table}
    return rows


# ═════════════════════════════════════════════════════════════════════════
# 8. Explanations on the current pipeline
# ═════════════════════════════════════════════════════════════════════════

def explanations(hist: pd.DataFrame, cases: list[dict], n_paths: int) -> dict:
    import evaluate_explanations as E
    from src.explainer import generate_complete_explanation

    df = pd.read_csv(D.DATASET_CSV).set_index("case_id")
    picked = [c for c in cases if c["action"] in ("sell", "hold")]
    raw = M.raw_from_dataset(df.loc[[c["case_id"] for c in picked]].reset_index())
    pred = M.predict_frame(raw)
    scores, by_bias = [], {}
    for c, p in zip(picked, pred["proba"]):
        k = int(p.argmax())
        bias = M.LABELS[k]
        by_bias[bias] = by_bias.get(bias, 0) + 1
        bias_result = {"bias_type": bias, "confidence": float(p[k]), "is_biased": bias != "rational",
                       "causal_effects": None, "shap_explanation": [],
                       "all_probabilities": {lab: float(v) for lab, v in zip(M.LABELS, p)}}
        sim = S.simulate(S.SimInputs(**{**c["inputs"], "n_paths": n_paths}), hist)
        user_input = {"unrealized_gl": c["inputs"]["position_value"] / c["inputs"]["cost_basis"] - 1,
                      "crowd_ratio": c["crowd_ratio"], "has_emergency_fund": c["has_emergency_fund"],
                      "decision_intent": c["action"], "current_wealth": c["inputs"]["position_value"]}
        for lang in ("en", "hi"):
            scores.append(E.score_explanation(generate_complete_explanation(bias_result, sim, user_input, lang=lang, use_llm=False)))
    failures = [s for s in scores if not (s["complete"] and s["readable"] and s["actionable"] and s["personalised"]) or s["jargon"]]
    return {"cases": len(picked), "explanations": len(scores), "pipeline": "bias model v4 + simulator v2 + template explainer, no LLM",
            "patterns": by_bias, "by_language": {lang: E.summarise(scores, lang) for lang in ("en", "hi")},
            "failures": len(failures), "failure_examples": failures[:5]}


# ═════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="smaller runs, for a smoke test")
    args = ap.parse_args()
    q = args.quick
    t0 = time.time()
    hist = S.load_history()
    n_paths = 300 if q else 1000
    report: dict = {"generated": time.strftime("%Y-%m-%d"), "quick": q,
                    "history": {"months": len(hist), "from": str(hist.month.min().date()), "to": str(hist.month.max().date())},
                    "assumptions": S.ASSUMPTIONS, "base_case": BASE}

    print("1. classifier baselines")
    report["classifier"] = classifier_baselines(q)
    print("2. generator validation")
    report["generator_validation"] = generator_validation(hist, 2000 if q else 10000)
    print("3. convergence")
    report["convergence"] = convergence(hist, q)
    print("4. population")
    cases = population_inputs(150 if q else 1000)
    report["population"], _ = population(hist, cases, n_paths)
    print("5. sensitivity")
    report["sensitivity"] = sensitivity(hist, cases[: (60 if q else 300)], 300 if q else 500)
    print("6. walk-forward")
    report["walk_forward"] = walk_forward(hist, 300 if q else 1000)
    print("7. paired table")
    report["paired_table"] = paired_table(hist, 300 if q else 1000)
    print("8. explanations")
    report["explanations"] = explanations(hist, cases[: (30 if q else 200)], 300)

    report["runtime_seconds"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    out = REPORT.replace(".json", "_quick.json") if q else REPORT
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"wrote {out} ({report['runtime_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
