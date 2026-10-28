"""
═══════════════════════════════════════════════════════════════════════════
 simulator_v2.py — hold vs sell over the investor's own horizon (Phase A3)
═══════════════════════════════════════════════════════════════════════════
What changed from v1 (src/simulator.py)
----------------------------------------
* **The investor's horizon**, 1-30 years, instead of a fixed 20. A 20-year
  view almost always favours holding, so v1 tilted every recommendation
  towards HOLD, even for someone who needs the money in three years.
* **Futures built from real history.** Equity and gold move together month
  by month as they really did (NIFTY 50 and gold in rupees, Oct 2007 to
  today), resampled in 12-month blocks so crashes and recoveries stay intact.
  Typical growth is then set to stated long-run rates (:data:`ASSUMPTIONS`),
  because replaying 2007-2026 exactly would assume gold keeps compounding at
  ~15% a year. ``historical_growth=True`` replays history as it was, as a
  sensitivity check.
* **A single stock carries its own risk** — company-specific swings on top of
  the market — while a mutual fund tracks the market closely. Concentration
  costs something, and v1 ignored it.
* **Real costs and tax (FY 2025-26, new regime).** Selling pays 0.15% in
  costs plus capital-gains tax: 20% if held 12 months or less, else 12.5% on
  gains above ₹1.25 lakh (4% cess on both). FD and savings interest is taxed
  every year at the investor's slab rate. Gold held over 24 months pays
  12.5% on gains, else the slab rate. Both futures are compared on what the
  investor would have **in hand after tax** if they cashed in that year.
* **The sale goes where the investor's safer money already is** — FDs,
  savings and gold in their current proportions (all FD if they hold none) —
  instead of v1's assumed "30% of the old share allocation" after a 5% cost.
* **Both futures use the same simulated markets** (common random numbers),
  so "holding wins in X% of futures" measures the decision, not noise.
* **Monthly investing continues.** The SIP (and education fees once they
  end) keeps flowing into the investor's current mix in both futures; it
  sets the size of the whole portfolio, against which the decision is judged.

Public API
----------
    load_history(refresh=False)  -> DataFrame (monthly returns, cached CSV)
    SimInputs                    -> dataclass of everything a simulation needs
    simulate(inputs)             -> dict (curves, sale breakdown, comparison)
    equity_gains_tax / gold_gains_tax / marginal_slab_rate — tax helpers
    income_tax / gross_from_take_home — the app asks for take-home pay;
                                 the slab rate needs income before tax
"""
from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "sim_v2")
HISTORY_CSV = os.path.join(DATA_DIR, "monthly_history.csv")

ENGINE = "monte_carlo_v2"

#: Long-run assumptions. Swings come from history; these set typical growth.
ASSUMPTIONS: dict[str, float] = {
    "equity_growth": 0.11,       # NIFTY 50 incl. dividends, typical (median) year
    "gold_growth": 0.09,         # gold in rupees
    "fd_rate": 0.0675,           # 1-3 year bank FD, before tax
    "savings_rate": 0.03,        # savings account, before tax
    "dividend_yield": 0.0125,    # added to NIFTY price returns for history replay
    "stock_specific_vol": 0.21,  # median NIFTY 50 stock beyond the market, a year (2016-2026)
    "fund_tracking_vol": 0.03,   # a diversified equity fund around the market, a year
    "sale_cost": 0.0015,         # brokerage + STT + exchange charges on a sale
    "block_months": 12,
}
DEFAULT_HORIZON = 20
MAX_HORIZON = 30

#: FY 2025-26 rules, new tax regime.
TAX: dict[str, Any] = {
    "cess": 0.04,
    "equity_stcg": 0.20,
    "equity_ltcg": 0.125,
    "equity_ltcg_after_months": 12,
    "ltcg_exemption": 125_000.0,
    "gold_ltcg": 0.125,
    "gold_ltcg_after_months": 24,
    "standard_deduction": 75_000.0,
    "rebate_up_to": 1_200_000.0,     # Section 87A: no slab tax up to this taxable income
    "slabs": ((400_000, 0.0), (800_000, 0.05), (1_200_000, 0.10), (1_600_000, 0.15),
              (2_000_000, 0.20), (2_400_000, 0.25), (math.inf, 0.30)),
}


# ═════════════════════════════════════════════════════════════════════════
# TAX
# ═════════════════════════════════════════════════════════════════════════

def marginal_slab_rate(annual_income: float) -> float:
    """Marginal rate on extra interest income, new regime, cess included.

    Taxable income is gross minus the ₹75,000 standard deduction. Up to
    ₹12 lakh taxable, the 87A rebate leaves slab income untaxed.
    """
    taxable = max(0.0, float(annual_income) - TAX["standard_deduction"])
    if taxable <= TAX["rebate_up_to"]:
        return 0.0
    for upper, rate in TAX["slabs"]:
        if taxable <= upper:
            return rate * (1 + TAX["cess"])
    return TAX["slabs"][-1][1] * (1 + TAX["cess"])


def income_tax(gross_annual: float) -> float:
    """Income tax on a year's gross income, new regime, cess included.

    Standard deduction, the slabs, and the Section 87A rebate up to ₹12 lakh
    taxable with its marginal relief (just above ₹12 lakh, tax is capped at
    the income over ₹12 lakh, so nobody takes home less for earning more).
    """
    taxable = max(0.0, float(gross_annual) - TAX["standard_deduction"])
    if taxable <= TAX["rebate_up_to"]:
        return 0.0
    tax, lower = 0.0, 0.0
    for upper, rate in TAX["slabs"]:
        if taxable > lower:
            tax += (min(taxable, upper) - lower) * rate
        lower = upper
    tax = min(tax, taxable - TAX["rebate_up_to"])  # 87A marginal relief
    return tax * (1 + TAX["cess"])


def gross_from_take_home(take_home_annual: float) -> float:
    """The gross yearly income that leaves this much after income tax.

    The app collects income after tax (Tier 1); the slab rate depends on
    income before it. Take-home rises with gross everywhere except a short
    stretch of the marginal-relief band, which sits below ₹12.75 lakh
    take-home, so above that the answer is unique and found by bisection.
    """
    take_home = max(0.0, float(take_home_annual))
    if take_home - income_tax(take_home) >= take_home:  # no tax at this level
        return take_home
    lo, hi = take_home, take_home * 2.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if mid - income_tax(mid) < take_home:
            lo = mid
        else:
            hi = mid
    return hi


def equity_gains_tax(gain, months_held, exemption: float | None = None):
    """Tax on selling listed shares or equity funds (works on arrays).

    Losses pay nothing (set-off against other gains is not modelled).
    """
    gain = np.maximum(np.asarray(gain, dtype=float), 0.0)
    months = np.asarray(months_held, dtype=float)
    exempt = TAX["ltcg_exemption"] if exemption is None else exemption
    short = months <= TAX["equity_ltcg_after_months"]
    stcg = gain * TAX["equity_stcg"]
    ltcg = np.maximum(gain - exempt, 0.0) * TAX["equity_ltcg"]
    return np.where(short, stcg, ltcg) * (1 + TAX["cess"])


def gold_gains_tax(gain, months_held, slab_rate: float):
    """Tax on selling gold: 12.5% after 24 months, else the slab rate."""
    gain = np.maximum(np.asarray(gain, dtype=float), 0.0)
    months = np.asarray(months_held, dtype=float)
    long_ = months > TAX["gold_ltcg_after_months"]
    return np.where(long_, gain * TAX["gold_ltcg"] * (1 + TAX["cess"]), gain * slab_rate)


# ═════════════════════════════════════════════════════════════════════════
# HISTORY
# ═════════════════════════════════════════════════════════════════════════

def load_history(refresh: bool = False) -> pd.DataFrame:
    """Monthly NIFTY 50 and gold-in-rupee returns, cached to data/sim_v2/.

    Gold in rupees is COMEX gold (USD) times USD/INR — the international
    price, before Indian import duty and GST, matching the app's gold value.
    """
    if os.path.exists(HISTORY_CSV) and not refresh:
        return pd.read_csv(HISTORY_CSV, parse_dates=["month"])

    import logging
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(logging.ERROR)

    def closes(ticker: str) -> pd.Series:
        s = yf.Ticker(ticker).history(start="2007-01-01", auto_adjust=True)["Close"]
        s.index = s.index.tz_localize(None).normalize()
        return s

    nifty = closes("^NSEI").resample("ME").last()
    gold_inr = (closes("GC=F") * closes("INR=X")).dropna().resample("ME").last()
    df = pd.DataFrame({"nifty": nifty, "gold_inr": gold_inr}).dropna()
    df = df.iloc[:-1] if df.index[-1].month == pd.Timestamp.today().month else df   # drop the partial month
    out = pd.DataFrame({
        "month": df.index[1:],
        "equity": df["nifty"].pct_change().iloc[1:].to_numpy() + ASSUMPTIONS["dividend_yield"] / 12,
        "gold": df["gold_inr"].pct_change().iloc[1:].to_numpy(),
    })
    os.makedirs(DATA_DIR, exist_ok=True)
    out.to_csv(HISTORY_CSV, index=False)
    return out


def _log_returns(history: pd.DataFrame, historical_growth: bool,
                 assumptions: dict[str, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    a = ASSUMPTIONS if assumptions is None else assumptions
    eq = np.log1p(history["equity"].to_numpy(dtype=float))
    gd = np.log1p(history["gold"].to_numpy(dtype=float))
    if not historical_growth:
        eq = eq - eq.mean() + math.log1p(a["equity_growth"]) / 12
        gd = gd - gd.mean() + math.log1p(a["gold_growth"]) / 12
    return eq, gd


def _bootstrap(rng: np.random.Generator, n_paths: int, months: int, n_hist: int,
               block_months: int | None = None) -> np.ndarray:
    """(n_paths, months) indices into history: 12-month blocks, joined end to end.

    Circular (Politis & Romano): a block may wrap from the last month to the
    first, so every month is equally likely. Without it the first and last
    months of history are under-sampled — and October 2007 starts with the
    2008 crash. ``block_months=1`` is the plain (independent-months) bootstrap.
    """
    b = int(ASSUMPTIONS["block_months"] if block_months is None else block_months)
    n_blocks = -(-months // b)
    starts = rng.integers(0, n_hist, size=(n_paths, n_blocks))
    return ((starts[:, :, None] + np.arange(b)) % n_hist).reshape(n_paths, -1)[:, :months]


# ═════════════════════════════════════════════════════════════════════════
# SIMULATION
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class SimInputs:
    """Everything one hold-vs-sell simulation needs, in rupees and months."""

    position_value: float                 # what the holding is worth today
    cost_basis: float                     # what was paid for it
    months_held: int                      # decides short- vs long-term tax
    asset_type: str = "equity"            # "equity" (a stock) | "mf" (an equity fund)
    horizon_years: int = DEFAULT_HORIZON
    annual_income: float = 900_000.0      # gross (before tax), for the slab rate on interest
    # the rest of the liquid portfolio, today
    other_equity: float = 0.0             # other shares and funds
    gold: float = 0.0
    fixed_deposits: float = 0.0
    savings: float = 0.0
    # money added each month
    # this holding's own risk (measured per stock by the app; defaults otherwise)
    beta: float = 1.0                     # how much it moves with NIFTY
    specific_vol: float | None = None     # its own yearly swings beyond the market
    monthly_sip: float = 0.0
    education_monthly: float = 0.0        # invested too once fees end
    years_until_education_ends: int | None = None
    n_paths: int = 1000
    seed: int = 2026
    historical_growth: bool = False
    assumptions: dict[str, float] = field(default_factory=lambda: dict(ASSUMPTIONS))

    def __post_init__(self) -> None:
        if self.asset_type not in ("equity", "mf"):
            raise ValueError(f"asset_type must be 'equity' or 'mf', got {self.asset_type!r}")
        self.horizon_years = int(min(max(int(self.horizon_years), 1), MAX_HORIZON))
        if self.position_value <= 0 or self.cost_basis <= 0:
            raise ValueError("position_value and cost_basis must be positive")


def _pct(matrix: np.ndarray, q: float) -> list[float]:
    return [round(float(v), 2) for v in np.percentile(matrix, q, axis=0)]


def _summary(x: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(x.mean()), "median": float(np.median(x)), "std": float(x.std()),
        "p10": float(np.percentile(x, 10)), "p25": float(np.percentile(x, 25)),
        "p50": float(np.percentile(x, 50)), "p75": float(np.percentile(x, 75)),
        "p90": float(np.percentile(x, 90)),
    }


def sale_today(inp: SimInputs) -> dict[str, float | str]:
    """What selling today leaves in hand: value - costs - capital-gains tax."""
    a = inp.assumptions
    gain = inp.position_value - inp.cost_basis
    tax = float(equity_gains_tax(gain, inp.months_held))
    cost = inp.position_value * a["sale_cost"]
    short = inp.months_held <= TAX["equity_ltcg_after_months"]
    return {
        "value": round(inp.position_value, 2),
        "gain": round(gain, 2),
        "tax_kind": "short_term" if short else "long_term",
        "tax": round(tax, 2),
        "costs": round(cost, 2),
        "proceeds": round(inp.position_value - tax - cost, 2),
    }


def destination(inp: SimInputs) -> dict[str, float]:
    """Where sale proceeds go: the investor's safer money, in its current split."""
    safe = {"gold": inp.gold, "fixed_deposits": inp.fixed_deposits, "savings": inp.savings}
    total = sum(safe.values())
    if total <= 0:
        return {"gold": 0.0, "fixed_deposits": 1.0, "savings": 0.0}
    return {k: round(v / total, 4) for k, v in safe.items()}


def simulate(inp: SimInputs, history: pd.DataFrame | None = None,
             paths: np.ndarray | None = None, return_gaps: bool = False) -> dict[str, Any]:
    """Hold vs sell for one position, over the investor's horizon.

    Evaluation-only options (the app passes neither): ``paths`` replaces the
    resampled markets with given ones, an (n_paths, horizon months) array of
    indices into history, to replay real windows or start every future in a
    chosen kind of year; ``return_gaps`` adds ``paired_gaps``, the
    (n_paths, years) hold-minus-sell after tax, future by future.
    """
    a = inp.assumptions
    hist = load_history() if history is None else history
    H = inp.horizon_years
    m = H * 12
    rng = np.random.default_rng(inp.seed)
    slab = marginal_slab_rate(inp.annual_income)

    # ── Shared markets ───────────────────────────────────────────────────
    eq_log, gd_log = _log_returns(hist, inp.historical_growth, a)
    if paths is None:
        n = inp.n_paths
        idx = _bootstrap(rng, n, m, len(hist), int(a.get("block_months", ASSUMPTIONS["block_months"])))
    else:
        idx = np.asarray(paths, dtype=int)
        if idx.ndim != 2 or idx.shape[1] != m:
            raise ValueError(f"paths must be (n_paths, {m}), got {idx.shape}")
        n = idx.shape[0]
    eq_cum = np.exp(np.cumsum(eq_log[idx], axis=1))             # (n, m) index growth
    gd_cum = np.exp(np.cumsum(gd_log[idx], axis=1))
    # This holding: the market's ups and downs scaled by its beta, its own
    # company-specific swings, and a typical growth rate set the standard way
    # (FD rate + beta x the extra return shares earn over FDs), so a jumpy
    # stock isn't projected to compound faster just because it is jumpy.
    default_vol = a["stock_specific_vol"] if inp.asset_type == "equity" else a["fund_tracking_vol"]
    own_vol = (default_vol if inp.specific_vol is None else inp.specific_vol) / math.sqrt(12)
    beta = float(inp.beta)
    market_growth = math.expm1(eq_log.mean() * 12)   # = equity_growth unless replaying history
    growth = a["fd_rate"] + beta * (market_growth - a["fd_rate"])
    eq_shock = eq_log[idx] - eq_log.mean()
    own = rng.normal(-own_vol ** 2 / 2, own_vol, size=(n, m))
    pos_cum = np.exp(np.cumsum(math.log1p(growth) / 12 + beta * eq_shock + own, axis=1))
    fd_after_tax = (1 + a["fd_rate"] * (1 - slab)) ** (np.arange(1, m + 1) / 12)
    sav_after_tax = (1 + a["savings_rate"] * (1 - slab)) ** (np.arange(1, m + 1) / 12)
    months_ahead = np.arange(1, m + 1)

    # ── HOLD: the position stays; in hand = value - costs - tax on the gain ──
    hold_value = inp.position_value * pos_cum
    hold_gain = hold_value - inp.cost_basis
    hold_in_hand = hold_value * (1 - a["sale_cost"]) - equity_gains_tax(hold_gain, inp.months_held + months_ahead)

    # ── SELL: tax and costs now; proceeds into the safer money ──────────────
    sale = sale_today(inp)
    split = destination(inp)
    p = float(sale["proceeds"])
    gold_part = p * split["gold"] * gd_cum
    gold_in_hand = gold_part - gold_gains_tax(gold_part - p * split["gold"], months_ahead, slab)
    sell_in_hand = (gold_in_hand + p * split["fixed_deposits"] * fd_after_tax
                    + p * split["savings"] * sav_after_tax)

    # ── Year-end snapshots (year 0 = today: value held vs cash after selling) ──
    ye = np.arange(12, m + 1, 12) - 1
    hold_y, sell_y = hold_in_hand[:, ye], sell_in_hand[:, ye]
    hold_end, sell_end = hold_y[:, -1], sell_y[:, -1]

    # ── The rest of the portfolio, the same in both futures (before tax) ───
    liquid_now = inp.position_value + inp.other_equity + inp.gold + inp.fixed_deposits + inp.savings
    w_eq = (inp.position_value + inp.other_equity) / liquid_now
    w_gd, w_fd, w_sv = inp.gold / liquid_now, inp.fixed_deposits / liquid_now, inp.savings / liquid_now
    edu_from = None
    if inp.education_monthly > 0 and inp.years_until_education_ends is not None:
        edu_from = max(0, int(inp.years_until_education_ends)) * 12
    contrib = np.full(m, inp.monthly_sip, dtype=float)
    if edu_from is not None and edu_from < m:
        contrib[edu_from:] += inp.education_monthly
    # Each month's contribution grows from its month to the end, per asset.
    def grown(cum: np.ndarray) -> np.ndarray:
        end = cum[:, -1:]
        return (contrib[None, :] * (end / cum)).sum(axis=1)
    rest_end = (inp.other_equity * eq_cum[:, -1] + inp.gold * gd_cum[:, -1]
                + inp.fixed_deposits * fd_after_tax[-1] + inp.savings * sav_after_tax[-1]
                + w_eq * grown(eq_cum) + w_gd * grown(gd_cum)
                + w_fd * grown(np.broadcast_to(fd_after_tax, eq_cum.shape))
                + w_sv * grown(np.broadcast_to(sav_after_tax, eq_cum.shape)))
    port_hold, port_sell = rest_end + hold_end, rest_end + sell_end

    # The gap is measured future by future (same markets in both), and the
    # typical (median) gap is the headline. A single stock's outcomes are
    # skewed — a few huge winners — so the mean gap overstates the usual one.
    diff = hold_end - sell_end
    opp = float(np.median(diff))
    prob_hold = float((diff > 0).mean())
    extra = {"paired_gaps": hold_y - sell_y} if return_gaps else {}
    return {
        **extra,
        "engine": ENGINE,
        "horizon_years": H,
        "years": list(range(1, H + 1)),
        "yearly_hold_p10": _pct(hold_y, 10), "yearly_hold_p50": _pct(hold_y, 50), "yearly_hold_p90": _pct(hold_y, 90),
        "yearly_sell_p10": _pct(sell_y, 10), "yearly_sell_p50": _pct(sell_y, 50), "yearly_sell_p90": _pct(sell_y, 90),
        "hold": {**_summary(hold_end), "starting_wealth": round(inp.position_value, 2), "stock_allocation": 1.0},
        "sell": {**_summary(sell_end), "starting_wealth": p, "stock_allocation": 0.0},
        "sale": {**sale, "destination": split},
        "comparison": {
            "opportunity_cost_inr": opp,
            "opportunity_cost_basis": "median of hold minus sell, future by future, after tax",
            "mean_gap_inr": float(diff.mean()),
            "opportunity_cost_pct": opp / inp.position_value * 100,
            "prob_hold_better": prob_hold,
            "better_decision": "HOLD" if opp > 0 else "SELL",
            "wealth_gap_pct": float(opp / np.median(sell_end) * 100) if np.median(sell_end) else 0.0,
        },
        "portfolio": {
            "liquid_today": round(liquid_now, 2),
            "hold_median_end": round(float(np.median(port_hold)), 2),
            "sell_median_end": round(float(np.median(port_sell)), 2),
            "decision_share_of_end_wealth": round(abs(opp) / max(float(np.median(port_hold)), 1.0), 4),
            "monthly_sip": inp.monthly_sip,
            "education_freed_from_year": (edu_from // 12) if edu_from is not None and edu_from < m else None,
            "basis": "the rest of the portfolio before tax; this decision after tax",
        },
        "assumptions": {
            **{k: v for k, v in a.items()},
            "growth_basis": "historical" if inp.historical_growth else "long-run assumptions",
            "history": f"{hist['month'].min():%b %Y} to {hist['month'].max():%b %Y}",
            "slab_rate_on_interest": round(slab, 4),
            "tax_rules": "FY 2025-26, new regime",
            "n_paths": n,
            # Names the explanation engine already reads.
            "transaction_cost": round((inp.position_value - p) / inp.position_value, 4),
            "bond_mean": a["fd_rate"],
        },
        "inputs": {
            **{k: v for k, v in asdict(inp).items() if k not in ("assumptions",)},
            # Names the explanation engine already reads.
            "current_wealth": inp.cost_basis,
            "unrealized_gl": inp.position_value / inp.cost_basis - 1,
            "n_simulations": n,
        },
    }


__all__ = ["ENGINE", "ASSUMPTIONS", "TAX", "DEFAULT_HORIZON", "MAX_HORIZON", "SimInputs",
           "load_history", "simulate", "sale_today", "destination", "marginal_slab_rate",
           "income_tax", "gross_from_take_home",
           "equity_gains_tax", "gold_gains_tax"]
