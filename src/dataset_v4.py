"""
═══════════════════════════════════════════════════════════════════════════
 dataset_v4.py — real-market, portfolio-aware investor decisions (Phase A1)
═══════════════════════════════════════════════════════════════════════════
Why a new dataset
-----------------
The v1–v3 bias models were trained on synthetic decisions whose market
conditions were roughly 3–4x more volatile than the real NIFTY, with no
"buy more" action, no portfolio context, and the investor's action excluded
from the features. Fed live data, v3 therefore mostly answers "disposition
effect" or "rational". v4 fixes this at the data:

1. **Real market conditions.** Every case is anchored to a real trading day
   between 2008 and today. Its 1-month NIFTY return, 30-day volatility,
   India VIX level and 52-week drawdown are the real values for that day —
   the 2008 crash, the 2020 COVID crash, rallies and quiet years included.
   A holding's gain or loss is derived from the real NIFTY move over its
   holding period (plus stock-specific noise), so P&L and market agree.

2. **Whole households.** Investors carry the FOLIUM_MASTER.md §4 inputs:
   income, EMIs, rent paid, education fees, emergency fund, risk tolerance,
   horizon, and a portfolio of shares, mutual funds, gold, deposits, savings,
   property, a home loan, other loans and rent received.

3. **The action is part of the case** — sell, hold or buy more — because in
   the app the investor states it before the analysis runs.

Version 4.1 (Phase A1.1, 2026-10-08): stretched households and cash shocks
------------------------------------------------------------------------
v4.0 never produced a household whose fixed payments came near its income,
so the "needs the cash" reason for selling never occurred and a forced sale
could only be read as a bias. v4.1 adds, anchored to published figures:

  * stretched borrowers — RBI's Financial Stability Report treats EMIs above
    60% of income as the zone of negative monthly margin; a minority of
    borrowers here carry that much, and some pay more than they earn;
  * fewer emergency funds — surveys find about three in four Indians have
    none; investors are better off, so about four in ten here have none
    (v4.0: two in ten);
  * cash shocks — a job loss, a medical bill or fees falling due, likelier
    without a fund or with little left each month. An emergency fund absorbs
    most of them; the rest force a sale ("needs cash");
  * a stated cash need — about two in three people who need the cash say so
    (a few say so without a real need). This is what the app can observe,
    from the decision's comment (Phase B3), and the bias model's input.

How labels are made — motives, not rules
----------------------------------------
If a bias label were a fixed function of what the model can see, the model
would simply memorise the rule. Instead each case is generated the way a
real decision happens:

  * the investor has hidden tendencies (loss aversion, herd sensitivity,
    disposition tendency) that are only partly reflected in what the app can
    observe — experience, financial stress, age;
  * the situation decides which motives *can* apply (the table below);
  * the motives compete, weighted by those tendencies; a rational motive
    always competes too;
  * the winning motive sets the action, and **the label is the motive**.

So the same sale in the same market can be rational (rebalancing, needing
cash, nearing a goal) or biased — the model has to infer which, as a person
would.

Label definitions (agreed 2026-10-07, "both, by context")
---------------------------------------------------------
  loss_aversion  panic:   SELL at a loss while the market is falling and fear is high
                 refusal: HOLD a deep loser (down >= 25%) to avoid "making the loss real"
  disposition    SELL a winner early, or HOLD a moderate loser (down 5–25%),
                 in a normal or rising market
  herd           SELL into widespread fear, or BUY MORE into a frenzy
  rational       everything else — the action follows the investor's own
                 situation (liquidity needs, rebalancing, goal timing, value)

Public API
----------
    load_market_history(refresh=False)  -> DataFrame   (cached CSV)
    build_dataset(n_cases, seed)        -> DataFrame
    LABEL_RULES                          — the table above, machine-checkable
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "v4")
MARKET_CSV = os.path.join(DATA_DIR, "market_history.csv")
DATASET_CSV = os.path.join(DATA_DIR, "decisions_v4.csv")

SEED = 2026
N_CASES = 20_000
REFERENCE_YEAR = 2026            # "now" for education end years

# ── Thresholds shared by regimes, label rules and tests ──────────────────
DEEP_LOSS = -0.25                # loss-aversion "refusal" starts here
MODERATE_LOSS = -0.05            # disposition "holding a loser" starts here
EARLY_WIN = 0.08                 # disposition "selling a winner early" from here
FALLING_1M = -0.02               # market falling over the past month
FEAR_VIX = 20.0                  # elevated fear
HERD_FEAR_VIX = 22.0
HERD_FEAR_1M = -0.05
FRENZY_1M = 0.04                 # strong 1-month rally

# ── v4.1: stretched households and cash shocks ───────────────────────────
STRETCHED_SHARE = 0.14           # borrowers carrying EMIs past ~60% of income
FUND_COVERS_SHOCK = 0.70         # an emergency fund absorbs most shocks
NEEDS_CASH_WEIGHT = 3.0          # extra pull of a sale the money forces
STATED_IF_NEEDED = 0.65          # people who need the cash and say so
STATED_IF_NOT = 0.03             # people who mention a cash need without one
SHOCK_KINDS = ("job_loss", "medical", "fees_due")


# ═════════════════════════════════════════════════════════════════════════
# MARKET HISTORY
# ═════════════════════════════════════════════════════════════════════════

def _regime(ret_1m: float, vix: float, drawdown: float) -> str:
    """Market regime of a real trading day."""
    if ret_1m <= -0.10 or (drawdown <= -0.20 and vix >= 30):
        return "crash"
    if ret_1m <= -0.04 or vix >= 24:
        return "correction"
    if ret_1m >= 0.06 and vix < 18:
        return "euphoria"
    if ret_1m >= 0.02:
        return "bull"
    return "normal"


def load_market_history(refresh: bool = False) -> pd.DataFrame:
    """Daily NIFTY 50 + India VIX features, cached to data/v4/market_history.csv.

    The cache makes the dataset reproducible offline: rebuilding with the
    same seed and cache gives byte-identical output.
    """
    if os.path.exists(MARKET_CSV) and not refresh:
        return pd.read_csv(MARKET_CSV, parse_dates=["date"])

    import logging
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(logging.WARNING)
    nifty = yf.Ticker("^NSEI").history(start="2007-01-01", auto_adjust=True)["Close"]
    vix = yf.Ticker("^INDIAVIX").history(start="2007-01-01", auto_adjust=True)["Close"]
    df = pd.DataFrame({"nifty": nifty, "vix": vix}).dropna()
    df.index = df.index.tz_localize(None).normalize()

    daily = df["nifty"].pct_change()
    df["ret_1m"] = df["nifty"].pct_change(21)
    df["ret_3m"] = df["nifty"].pct_change(63)
    df["vol_30d"] = daily.rolling(21).std()
    df["drawdown_52w"] = df["nifty"] / df["nifty"].rolling(252, min_periods=60).max() - 1
    df = df.dropna().reset_index().rename(columns={"Date": "date", "index": "date"})
    df["regime"] = [_regime(r, v, d) for r, v, d in zip(df.ret_1m, df.vix, df.drawdown_52w)]

    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(MARKET_CSV, index=False)
    return df


# Over-weight rare stress days so every motive has enough examples; the
# real regime of each sampled day is still recorded as-is.
_REGIME_WEIGHT = {"normal": 1.0, "bull": 1.0, "correction": 2.0, "euphoria": 3.0, "crash": 6.0}


# ═════════════════════════════════════════════════════════════════════════
# INVESTORS AND PORTFOLIOS
# ═════════════════════════════════════════════════════════════════════════

def _round_to(x: float, step: float) -> float:
    return float(round(x / step) * step)


def _investor(rng: np.random.Generator) -> dict:
    age = int(np.clip(22 + rng.gamma(4.0, 4.5), 22, 70))
    income = _round_to(float(np.clip(rng.lognormal(math.log(75_000), 0.65), 20_000, 800_000)), 1_000)
    experience = int(np.clip(rng.gamma(2.0, 0.22 * (age - 21)), 0, min(age - 21, 35)))
    risk = float(np.clip(rng.beta(2.4, 2.4) - 0.006 * (age - 35) + 0.008 * experience, 0.05, 0.95))
    horizon = int(np.clip(round(60 - age + rng.normal(0, 4)), 1, 35))

    owns_home = rng.random() < np.clip(0.10 + 0.017 * (age - 22), 0.10, 0.80)
    rent_paid = 0.0
    if not owns_home and rng.random() < 0.75:
        rent_paid = _round_to(income * rng.uniform(0.12, 0.40), 500)

    home_loan_emi = _round_to(income * rng.uniform(0.15, 0.45), 500) if owns_home and rng.random() < np.clip(1.2 - 0.02 * age, 0.15, 0.75) else 0.0
    has_other_loan = rng.random() < 0.35
    other_emi = _round_to(income * rng.uniform(0.04, 0.20), 500) if has_other_loan else 0.0
    # Stretched borrowers (v4.1): a minority carry far more debt — personal
    # loans, cards, consumer EMIs on top — taking total EMIs past 60% of income.
    if (home_loan_emi or other_emi) and rng.random() < STRETCHED_SHARE:
        other_emi += _round_to(income * rng.uniform(0.25, 0.65), 500)
    monthly_emi = home_loan_emi + other_emi

    has_kids_fees = 30 <= age <= 56 and rng.random() < 0.42
    education = _round_to(income * rng.uniform(0.03, 0.20), 500) if has_kids_fees else 0.0
    edu_end = REFERENCE_YEAR + int(rng.integers(1, 16)) if has_kids_fees else None

    outflow = monthly_emi + rent_paid + education
    surplus_ratio = (income - outflow) / income
    efund_p = np.clip(0.02 + 0.62 * surplus_ratio + 0.012 * experience, 0.03, 0.92)
    has_efund = bool(rng.random() < efund_p)

    stress = float(np.clip((0.45 - surplus_ratio) + (0.0 if has_efund else 0.35), 0, 1))

    # Hidden tendencies. Partly explained by what the app can observe
    # (experience, stress, age), partly personal — the noise term.
    def trait(base: float) -> float:
        return float(np.clip(base + rng.normal(0, 0.18), 0.0, 1.0))

    loss_aversion = trait(0.45 + 0.35 * stress - 0.012 * experience - 0.25 * (risk - 0.5))
    herd = trait(0.45 - 0.015 * experience + 0.006 * (40 - age) - 0.20 * (risk - 0.5))
    disposition = trait(0.50 - 0.010 * experience)

    return {
        "age": age,
        "monthly_income": income,
        "years_investing": experience,
        "risk_tolerance": round(risk, 3),
        "investment_horizon": horizon,
        "owns_home": owns_home,
        "rent_paid": rent_paid,
        "monthly_emi": monthly_emi,
        "home_loan_emi": home_loan_emi,
        "other_loan_emi": other_emi,
        "education_monthly": education,
        "education_end_year": edu_end,
        "has_emergency_fund": int(has_efund),
        "latent_loss_aversion": round(loss_aversion, 4),
        "latent_herd": round(herd, 4),
        "latent_disposition": round(disposition, 4),
    }


def _portfolio(rng: np.random.Generator, inv: dict) -> dict:
    income = inv["monthly_income"]
    months_saved = float(np.clip(rng.lognormal(math.log(4 + 1.6 * inv["years_investing"]), 0.7), 2, 240))
    liquid = income * months_saved

    equity = float(np.clip(0.15 + 0.75 * inv["risk_tolerance"] + rng.normal(0, 0.08), 0.05, 0.92))
    gold = float(np.clip(rng.beta(2, 9) + 0.002 * (inv["age"] - 30) + 0.10 * (0.5 - inv["risk_tolerance"]), 0.0, 0.40))
    gold = min(gold, 1 - equity - 0.03)
    rest = max(0.0, 1 - equity - gold)
    fd_part = rng.uniform(0.3, 0.8)
    mf_part = rng.uniform(0.2, 0.7)

    real_estate = 0.0
    home_loan = 0.0
    rent_received = 0.0
    if inv["owns_home"]:
        real_estate = _round_to(income * rng.uniform(40, 160), 10_000)
        if inv["home_loan_emi"] > 0:
            home_loan = _round_to(inv["home_loan_emi"] * rng.uniform(60, 150), 10_000)
            home_loan = min(home_loan, real_estate * 0.85)
        if rng.random() < 0.15:
            rent_received = _round_to(income * rng.uniform(0.08, 0.35), 500)
    other_loans = _round_to(inv["other_loan_emi"] * rng.uniform(10, 40), 1_000) if inv["other_loan_emi"] else 0.0

    position_share = float(np.clip(rng.beta(1.6, 10.0), 0.01, 0.6))   # median ~12% of liquid

    stocks = liquid * equity * (1 - mf_part)
    funds = liquid * equity * mf_part
    gold_value = liquid * gold
    fds = liquid * rest * fd_part
    savings = liquid * rest * (1 - fd_part)
    net_worth = liquid + real_estate - home_loan - other_loans
    return {
        "liquid_assets": round(liquid, 2),
        "stocks_value": round(stocks, 2),
        "mf_value": round(funds, 2),
        "gold_value": round(gold_value, 2),
        "fixed_deposits": round(fds, 2),
        "savings_balance": round(savings, 2),
        "real_estate_value": real_estate,
        "home_loan_outstanding": home_loan,
        "other_loans_outstanding": other_loans,
        "rent_received": rent_received,
        "net_worth": round(net_worth, 2),
        "equity_share": round(equity, 4),
        "gold_share": round(gold, 4),
        "position_share": round(position_share, 4),
    }


# ═════════════════════════════════════════════════════════════════════════
# SITUATION, MOTIVES, ACTION
# ═════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Motive:
    name: str          # sub-motive, e.g. "loss_aversion_panic"
    label: str         # bias label
    action: str        # sell | hold | buy_more


def _situation(rng: np.random.Generator, market: pd.DataFrame, probs: np.ndarray) -> dict:
    i = int(rng.choice(len(market), p=probs))
    day = market.iloc[i]
    months = int(np.clip(rng.lognormal(math.log(14), 0.8), 1, 84))
    start = max(0, i - months * 21)
    market_move = float(day.nifty / market.iloc[start].nifty - 1)
    beta = float(np.clip(rng.normal(1.0, 0.3), 0.4, 1.8))
    idio = rng.normal(0, 0.22 * math.sqrt(months / 12))
    gl = float(np.clip((1 + market_move) ** beta * math.exp(idio) - 1, -0.85, 3.0))
    return {
        "date": day.date.date() if hasattr(day.date, "date") else day.date,
        "regime": day.regime,
        "nifty_1m_return": round(float(day.ret_1m), 4),
        "nifty_3m_return": round(float(day.ret_3m), 4),
        "nifty_volatility_30d": round(float(day.vol_30d), 5),
        "vix": round(float(day.vix), 2),
        "drawdown_52w": round(float(day.drawdown_52w), 4),
        "holding_period_months": months,
        "unrealized_gl": round(gl, 4),
    }


def shock_probability(surplus_ratio: float, has_efund: int) -> float:
    """Chance a cash shock lands around this decision: likelier when stretched."""
    return float(0.04 + 0.06 * (not has_efund) + 0.12 * np.clip((0.30 - surplus_ratio) / 0.30, 0.0, 1.0))


def needs_cash(surplus: float, has_efund: int, cash_shock: int, shock_u: float) -> bool:
    """Is a sale forced by money? Fixed payments above income with no fund to
    fall back on, or a shock the emergency fund doesn't cover."""
    if surplus < 0 and not has_efund:
        return True
    return bool(cash_shock) and not (has_efund and shock_u < FUND_COVERS_SHOCK)


def cash_need_stated(needs: bool, stated_u: float) -> int:
    """What the app can observe: whether a cash need was mentioned."""
    return int(stated_u < STATED_IF_NEEDED) if needs else int(stated_u > 1 - STATED_IF_NOT)


def crowd_ratio_from_vix(vix: float) -> float:
    """Same VIX -> crowd-fear proxy the app uses (backend/core/ml_bridge.py)."""
    return float(max(0.05, min((vix - 10.0) / 40.0, 1.0)))


def applicable_bias_motives(s: dict) -> list[Motive]:
    """The bias motives the situation allows — LABEL_RULES in code form."""
    gl, r1m, vix, regime = s["unrealized_gl"], s["nifty_1m_return"], s["vix"], s["regime"]
    falling_fear = gl < -0.03 and r1m <= FALLING_1M and (vix >= FEAR_VIX or regime in ("crash", "correction"))
    calm = regime in ("normal", "bull")
    out: list[Motive] = []
    if falling_fear:
        out.append(Motive("loss_aversion_panic", "loss_aversion", "sell"))
    if gl <= DEEP_LOSS:
        out.append(Motive("loss_aversion_refusal", "loss_aversion", "hold"))
    if calm and gl >= EARLY_WIN:
        out.append(Motive("disposition_sell_winner", "disposition", "sell"))
    if calm and DEEP_LOSS < gl <= MODERATE_LOSS:
        out.append(Motive("disposition_hold_loser", "disposition", "hold"))
    if vix >= HERD_FEAR_VIX or r1m <= HERD_FEAR_1M:
        out.append(Motive("herd_sell_fear", "herd", "sell"))
    if r1m >= FRENZY_1M:
        out.append(Motive("herd_buy_frenzy", "herd", "buy_more"))
    return out


def allowed_labels(unrealized_gl: float, nifty_1m_return: float, vix: float, action: str) -> set[str]:
    """Labels the definitions allow for this situation *and* this action.

    The bias model (src/bias_model_v4.py) uses this both as an input and as a
    guard, so the label table lives in exactly one place. The 52-week drawdown
    is not needed: it only separates "crash" from "correction", and every rule
    treats the two alike.
    """
    s = {
        "unrealized_gl": unrealized_gl,
        "nifty_1m_return": nifty_1m_return,
        "vix": vix,
        "regime": _regime(nifty_1m_return, vix, 0.0),
    }
    return {"rational"} | {m.label for m in applicable_bias_motives(s) if m.action == action}


def rational_action(rng: np.random.Generator, s: dict, inv: dict, pf: dict) -> tuple[str, str]:
    """What a level-headed investor in this situation would do, and why."""
    surplus = inv["monthly_income"] + pf["rent_received"] - (inv["monthly_emi"] + inv["rent_paid"] + inv["education_monthly"])
    surplus_ratio = surplus / inv["monthly_income"]
    if inv.get("needs_cash", surplus < 0 and not inv["has_emergency_fund"]):
        return "sell", "rational_needs_cash"
    if pf["position_share"] > 0.35:
        return "sell", "rational_rebalance"
    if inv["investment_horizon"] <= 3 and s["unrealized_gl"] > 0:
        return "sell", "rational_goal_near"
    if (s["nifty_1m_return"] <= -0.06 and inv["has_emergency_fund"] and surplus_ratio > 0.25
            and inv["investment_horizon"] >= 10 and pf["position_share"] < 0.25):
        return "buy_more", "rational_buy_value"
    if surplus_ratio > 0.35 and inv["investment_horizon"] >= 8 and pf["position_share"] < 0.12 and rng.random() < 0.35:
        return "buy_more", "rational_add_regularly"
    # Cutting a loss because the reason for owning it has changed — a sound
    # sale of a loser that no bias explains (the opposite of the disposition
    # effect). Without it, "selling at a loss in a calm market" would never
    # appear in the data and the model would meet it blind.
    if s["unrealized_gl"] <= -0.12 and rng.random() < 0.30:
        return "sell", "rational_cut_loss"
    # Averaging down deliberately: spare cash, long horizon, small position.
    if (s["unrealized_gl"] <= -0.10 and surplus_ratio > 0.30 and inv["has_emergency_fund"]
            and inv["investment_horizon"] >= 10 and pf["position_share"] < 0.15 and rng.random() < 0.30):
        return "buy_more", "rational_average_down"
    return "hold", "rational_stay_course"


_TRAIT = {"loss_aversion": "latent_loss_aversion", "herd": "latent_herd", "disposition": "latent_disposition"}
_STRENGTH = {"loss_aversion": 3.4, "herd": 2.0, "disposition": 2.8}


def _choose(rng: np.random.Generator, s: dict, inv: dict, pf: dict) -> tuple[Motive, float]:
    action, why = rational_action(rng, s, inv, pf)
    candidates = [Motive(why, "rational", action)]
    # A rational decision gets steadier with experience and an emergency fund.
    # When the money is genuinely needed, necessity dominates: it is a
    # constraint, not a preference, so it outweighs a typical bias urge.
    weights = [0.7 + 0.025 * inv["years_investing"] + 0.25 * inv["has_emergency_fund"]
               + (NEEDS_CASH_WEIGHT if inv.get("needs_cash") else 0.0)]
    for m in applicable_bias_motives(s):
        trait = inv[_TRAIT[m.label]]
        intensity = 1.0
        if m.name == "loss_aversion_panic":
            intensity = 1.0 + min(abs(s["unrealized_gl"]) * 3, 1.5)
        elif m.name == "loss_aversion_refusal":
            intensity = 1.0 + min((abs(s["unrealized_gl"]) - 0.25) * 3, 1.0)
        elif m.name == "disposition_sell_winner":
            intensity = 1.0 + min((s["unrealized_gl"] - EARLY_WIN) * 2, 1.0)
        elif m.name == "disposition_hold_loser":
            intensity = 1.4 + min(abs(s["unrealized_gl"]) * 2, 0.6)
        elif m.name == "herd_sell_fear":
            intensity = 1.0 + crowd_ratio_from_vix(s["vix"])
        elif m.name == "herd_buy_frenzy":
            intensity = 1.0 + min(s["nifty_1m_return"] * 6, 1.0)
        candidates.append(m)
        weights.append(_STRENGTH[m.label] * trait ** 1.5 * intensity)
    w = np.array(weights)
    k = int(rng.choice(len(candidates), p=w / w.sum()))
    return candidates[k], float(w[k] / w.sum())


# ═════════════════════════════════════════════════════════════════════════
# BUILD
# ═════════════════════════════════════════════════════════════════════════

def build_dataset(n_cases: int = N_CASES, seed: int = SEED, market: pd.DataFrame | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    market = load_market_history() if market is None else market
    market = market.reset_index(drop=True)
    w = market["regime"].map(_REGIME_WEIGHT).to_numpy(dtype=float)
    probs = w / w.sum()

    rows = []
    for case in range(n_cases):
        inv = _investor(rng)
        pf = _portfolio(rng, inv)
        s = _situation(rng, market, probs)
        surplus = inv["monthly_income"] + pf["rent_received"] - (inv["monthly_emi"] + inv["rent_paid"] + inv["education_monthly"])
        shock = int(rng.random() < shock_probability(surplus / inv["monthly_income"], inv["has_emergency_fund"]))
        kind = SHOCK_KINDS[int(rng.integers(len(SHOCK_KINDS)))] if shock else ""
        shock_u, stated_u = float(rng.random()), float(rng.random())
        inv["needs_cash"] = needs_cash(surplus, inv["has_emergency_fund"], shock, shock_u)
        motive, share = _choose(rng, s, inv, pf)
        rows.append({
            "case_id": case,
            **s,
            "crowd_ratio": round(crowd_ratio_from_vix(s["vix"]), 4),
            "action": motive.action,
            **{k: v for k, v in inv.items() if k not in ("owns_home", "home_loan_emi", "other_loan_emi", "needs_cash")},
            "cash_need_stated": cash_need_stated(inv["needs_cash"], stated_u),
            # The truth behind it — hidden, like the tendencies (never a feature).
            "latent_cash_shock": shock,
            "latent_shock_kind": kind,
            "latent_shock_u": shock_u,
            "latent_stated_u": stated_u,
            "latent_needs_cash": int(inv["needs_cash"]),
            **pf,
            "monthly_outflow": inv["monthly_emi"] + inv["rent_paid"] + inv["education_monthly"],
            "motive": motive.name,
            "motive_share": round(share, 4),
            "bias_type": motive.label,
        })
    return pd.DataFrame(rows)


# Machine-checkable form of the label table (used by tests and the dataset card).
LABEL_RULES: dict[str, dict] = {
    "loss_aversion_panic": {"action": "sell", "rule": "loss and falling market with high fear"},
    "loss_aversion_refusal": {"action": "hold", "rule": f"holding a loser down {abs(DEEP_LOSS):.0%} or more"},
    "disposition_sell_winner": {"action": "sell", "rule": f"selling a winner up {EARLY_WIN:.0%}+ in a calm or rising market"},
    "disposition_hold_loser": {"action": "hold", "rule": f"holding a loser down {abs(MODERATE_LOSS):.0%}-{abs(DEEP_LOSS):.0%} in a calm or rising market"},
    "herd_sell_fear": {"action": "sell", "rule": f"selling into fear (VIX >= {HERD_FEAR_VIX:.0f} or NIFTY 1m <= {HERD_FEAR_1M:.0%})"},
    "herd_buy_frenzy": {"action": "buy_more", "rule": f"buying more into a rally (NIFTY 1m >= {FRENZY_1M:.0%})"},
}


if __name__ == "__main__":
    df = build_dataset()
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(DATASET_CSV, index=False)
    print(f"wrote {len(df)} cases to {DATASET_CSV}")
    print(df["bias_type"].value_counts().to_string())
