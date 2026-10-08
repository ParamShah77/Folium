"""Simulation v2 (Phase A3) — tax rules by hand, horizon, destination, determinism.

Uses the cached monthly history (data/sim_v2/monthly_history.csv); skips without it.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import simulator_v2 as S  # noqa: E402

needs_history = pytest.mark.skipif(not os.path.exists(S.HISTORY_CSV), reason="history cache not built")

BASE = dict(position_value=100_000.0, cost_basis=120_000.0, months_held=18, horizon_years=10,
            annual_income=1_800_000.0, other_equity=300_000.0, gold=100_000.0,
            fixed_deposits=300_000.0, savings=100_000.0, n_paths=400)


def sim(**kw):
    return S.simulate(S.SimInputs(**{**BASE, **kw}))


# ── Tax, worked by hand (FY 2025-26, new regime, 4% cess) ────────────────

@pytest.mark.parametrize("income, rate", [
    (900_000, 0.0),            # taxable 8.25 L: under the 12 L rebate
    (1_275_000, 0.0),          # taxable exactly 12 L
    (1_375_000, 0.15 * 1.04),  # taxable 13 L: 12-16 L slab
    (2_200_000, 0.25 * 1.04),  # taxable 21.25 L: 20-24 L slab
    (3_000_000, 0.30 * 1.04),
])
def test_marginal_slab_rate(income, rate):
    assert S.marginal_slab_rate(income) == pytest.approx(rate)


def test_short_term_equity_gain_pays_20_percent_plus_cess():
    assert float(S.equity_gains_tax(23_076.92, 8)) == pytest.approx(23_076.92 * 0.20 * 1.04)


def test_twelve_months_is_still_short_term():
    """Long-term needs *more than* 12 months."""
    assert float(S.equity_gains_tax(10_000, 12)) == pytest.approx(10_000 * 0.20 * 1.04)


def test_long_term_equity_gain_is_exempt_up_to_125000():
    assert float(S.equity_gains_tax(100_000, 18)) == 0.0
    assert float(S.equity_gains_tax(200_000, 18)) == pytest.approx(75_000 * 0.125 * 1.04)


def test_losses_pay_no_tax():
    assert float(S.equity_gains_tax(-50_000, 3)) == 0.0
    assert float(S.gold_gains_tax(-5_000, 30, 0.3)) == 0.0


def test_gold_is_long_term_after_24_months():
    assert float(S.gold_gains_tax(100_000, 30, 0.208)) == pytest.approx(100_000 * 0.125 * 1.04)
    assert float(S.gold_gains_tax(100_000, 10, 0.208)) == pytest.approx(100_000 * 0.208)


def test_sale_today_is_value_minus_costs_minus_tax():
    inp = S.SimInputs(**{**BASE, "cost_basis": 100_000 / 1.3, "months_held": 8})
    s = S.sale_today(inp)
    assert s["tax_kind"] == "short_term"
    assert s["tax"] == pytest.approx(round((100_000 - 100_000 / 1.3) * 0.208, 2))
    assert s["costs"] == pytest.approx(150.0)
    assert s["proceeds"] == pytest.approx(100_000 - s["tax"] - 150.0)


# ── Where the sale goes ──────────────────────────────────────────────────

def test_sale_goes_to_the_safer_money_in_its_current_split():
    d = S.destination(S.SimInputs(**BASE))
    assert d == {"gold": 0.2, "fixed_deposits": 0.6, "savings": 0.2}


def test_with_no_safer_money_the_sale_goes_to_an_fd():
    d = S.destination(S.SimInputs(**{**BASE, "gold": 0.0, "fixed_deposits": 0.0, "savings": 0.0}))
    assert d == {"gold": 0.0, "fixed_deposits": 1.0, "savings": 0.0}


@needs_history
def test_all_fd_sale_grows_at_the_after_tax_fd_rate():
    r = sim(gold=0.0, savings=0.0, annual_income=900_000.0)   # no slab tax: FD compounds at 6.75%
    p = r["sale"]["proceeds"]
    expected = [round(p * 1.0675 ** y, 2) for y in range(1, 11)]
    assert r["yearly_sell_p50"] == pytest.approx(expected, rel=1e-6)
    r_taxed = sim(gold=0.0, savings=0.0)
    assert r_taxed["yearly_sell_p50"][-1] == pytest.approx(p * (1 + 0.0675 * (1 - 0.208)) ** 10, rel=1e-6)


# ── Horizon and shape ────────────────────────────────────────────────────

@needs_history
@pytest.mark.parametrize("asked, used", [(0, 1), (3, 3), (20, 20), (45, 30)])
def test_horizon_is_the_investors_within_1_to_30_years(asked, used):
    r = sim(horizon_years=asked)
    assert r["horizon_years"] == used
    assert r["years"] == list(range(1, used + 1))
    assert len(r["yearly_hold_p50"]) == used


@needs_history
def test_same_inputs_same_answer():
    assert sim()["comparison"] == sim()["comparison"]


@needs_history
def test_a_fund_is_less_spread_out_than_a_single_stock():
    stock, fund = sim(asset_type="equity"), sim(asset_type="mf")
    assert fund["hold"]["p90"] - fund["hold"]["p10"] < stock["hold"]["p90"] - stock["hold"]["p10"]
    assert fund["sell"] == stock["sell"]   # the sale side doesn't depend on what was sold


@needs_history
def test_paying_short_term_tax_makes_selling_worse():
    lt = sim(cost_basis=100_000 / 1.3, months_held=18)
    st = sim(cost_basis=100_000 / 1.3, months_held=8)
    assert st["sale"]["proceeds"] < lt["sale"]["proceeds"]
    assert st["comparison"]["prob_hold_better"] >= lt["comparison"]["prob_hold_better"]


@needs_history
def test_monthly_investing_sizes_the_portfolio_not_the_decision():
    no_sip, sip = sim(monthly_sip=0.0), sim(monthly_sip=20_000.0)
    assert no_sip["comparison"]["opportunity_cost_inr"] == pytest.approx(sip["comparison"]["opportunity_cost_inr"])
    assert sip["portfolio"]["hold_median_end"] > no_sip["portfolio"]["hold_median_end"]


@needs_history
def test_education_fees_are_invested_once_they_end():
    base = sim(monthly_sip=10_000.0)
    freed = sim(monthly_sip=10_000.0, education_monthly=15_000.0, years_until_education_ends=4)
    assert freed["portfolio"]["education_freed_from_year"] == 4
    assert freed["portfolio"]["hold_median_end"] > base["portfolio"]["hold_median_end"]


@needs_history
def test_growth_assumptions_are_respected():
    low = sim(assumptions={**S.ASSUMPTIONS, "equity_growth": 0.08})
    high = sim(assumptions={**S.ASSUMPTIONS, "equity_growth": 0.14})
    assert low["hold"]["p50"] < high["hold"]["p50"]


@needs_history
def test_simulated_years_resemble_real_nifty():
    """Typical 1-year index return within 2 points of the target growth rate."""
    hist = S.load_history()
    eq, _ = S._log_returns(hist, False)
    idx = S._bootstrap(np.random.default_rng(0), 4000, 12, len(hist))
    one_year = np.exp(eq[idx].sum(axis=1)) - 1
    assert abs(np.median(one_year) - S.ASSUMPTIONS["equity_growth"]) < 0.02
    assert 0.02 < (one_year < -0.20).mean() < 0.08


def test_bad_inputs_are_rejected():
    with pytest.raises(ValueError):
        S.SimInputs(**{**BASE, "asset_type": "crypto"})
    with pytest.raises(ValueError):
        S.SimInputs(**{**BASE, "position_value": 0})


# ── A stock's own risk ───────────────────────────────────────────────────

@needs_history
def test_lower_specific_risk_narrows_the_outcomes_and_raises_the_typical_one():
    calm, jumpy = sim(specific_vol=0.12), sim(specific_vol=0.30)
    assert calm["hold"]["p90"] - calm["hold"]["p10"] < jumpy["hold"]["p90"] - jumpy["hold"]["p10"]
    assert calm["hold"]["p50"] > jumpy["hold"]["p50"]


@needs_history
def test_beta_sets_typical_growth_the_standard_way():
    """FD rate + beta x (share growth - FD rate): low beta, lower typical growth."""
    low, one = sim(beta=0.5, specific_vol=0.0001), sim(beta=1.0, specific_vol=0.0001)
    assert low["hold"]["p50"] < one["hold"]["p50"]
