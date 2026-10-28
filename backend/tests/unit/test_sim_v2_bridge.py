"""Simulation v2 in the app — input assembly and disclosure, no datastore."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.core.bias_detector import _resolve_profile
from backend.core.recommendation import decide
from backend.core.simulator import build_sim_inputs

PROFILE_ROW = {
    "age": 34, "risk_tolerance": Decimal("0.60"), "investment_horizon": 7,
    "monthly_income": Decimal("90000"), "monthly_expense": Decimal("30000"),
    "has_emergency_fund": True, "financial_strategy": "moderate", "goal": "Wealth growth",
}
CONTEXT = {
    "asset_type": "equity", "position_value": 130_000, "monthly_income": 90_000, "rent_received": 10_000,
    "allocation": {"stocks": 230_000, "mutual_funds": 50_000, "gold": 60_000, "fixed_deposits": 200_000, "savings": 40_000},
    "monthly_sip": 12_000, "education_monthly": 8_000, "education_end_year": 2031,
}
TODAY = date(2026, 10, 7)


def decision(**kw):
    d = {
        "holding_quantity": Decimal("100"), "avg_buy_price": Decimal("1600.00"),
        "current_price": Decimal("1300.00"), "unrealized_pnl_pct": Decimal("-0.1875"),
        "holding_period_days": 400, "portfolio_context": dict(CONTEXT),
    }
    d.update(kw)
    return d


def build(d, row=PROFILE_ROW):
    profile, assumed = _resolve_profile(row)
    return build_sim_inputs(d, profile, assumed, today=TODAY)


def test_full_inputs_need_no_standard_values():
    ctx = {**CONTEXT, "stock_risk": {"beta": 1.1, "specific_vol": 0.2}}
    inputs, fixed, source = build(decision(portfolio_context=ctx))
    assert fixed == [] and source == "profile"
    assert inputs["horizon_years"] == 7
    assert inputs["position_value"] == 130_000 and inputs["cost_basis"] == 160_000
    assert inputs["months_held"] == 13
    assert inputs["other_equity"] == 150_000          # stocks + funds minus this holding
    assert (inputs["gold"], inputs["fixed_deposits"], inputs["savings"]) == (60_000, 200_000, 40_000)
    assert inputs["monthly_sip"] == 12_000
    assert inputs["years_until_education_ends"] == 5


def test_slab_income_counts_70_percent_of_rent():
    inputs, _, _ = build(decision())
    # Take-home ₹90,000 a month is grossed up (₹10.8 L take-home is under the
    # 87A limit, so no tax: gross = take-home); rent counts at 70%.
    assert inputs["annual_income"] == pytest.approx(12 * 90_000 + 12 * 0.7 * 10_000)


def test_missing_horizon_uses_20_years_and_says_so():
    row = {**PROFILE_ROW, "investment_horizon": None}
    inputs, _, source = build(decision(), row=row)
    assert inputs["horizon_years"] == 20 and source == "default"


def test_no_portfolio_snapshot_is_disclosed():
    inputs, fixed, _ = build(decision(portfolio_context=None))
    assert {"portfolio", "monthly_sip"} <= set(fixed)
    assert inputs["fixed_deposits"] == 0 and inputs["monthly_sip"] == 0


def test_unknown_holding_period_assumes_long_term_and_says_so():
    inputs, fixed, _ = build(decision(holding_period_days=None))
    assert "holding_period" in fixed and inputs["months_held"] > 12


def test_missing_price_falls_back_to_the_stated_gain_or_loss():
    inputs, _, _ = build(decision(current_price=None))
    assert inputs["position_value"] == pytest.approx(160_000 * (1 - 0.1875))


def test_a_fund_is_simulated_as_a_fund():
    inputs, _, _ = build(decision(portfolio_context={**CONTEXT, "asset_type": "mf"}))
    assert inputs["asset_type"] == "mf"


def test_recommendation_quotes_the_investors_horizon():
    _, reasons = decide("sell", "rational", 0.9, 0.7, horizon_years=7)
    assert "7-year simulations" in reasons[0]
    _, reasons = decide("hold", "rational", 0.9, 0.7)
    assert "20-year simulations" in reasons[0]   # v1 decisions keep their 20 years


def test_measured_stock_risk_reaches_the_simulation():
    ctx = {**CONTEXT, "stock_risk": {"beta": 1.03, "specific_vol": 0.142, "months": 119, "source": "measured"}}
    inputs, fixed, _ = build(decision(portfolio_context=ctx))
    assert inputs["beta"] == 1.03 and inputs["specific_vol"] == 0.142
    assert "stock_risk" not in fixed


def test_unmeasured_stock_risk_is_disclosed():
    inputs, fixed, _ = build(decision())
    assert inputs["beta"] == 1.0 and inputs["specific_vol"] is None
    assert "stock_risk" in fixed


def test_funds_need_no_stock_risk():
    _, fixed, _ = build(decision(portfolio_context={**CONTEXT, "asset_type": "mf"}))
    assert "stock_risk" not in fixed


def test_risk_estimator_recovers_a_known_beta():
    import numpy as np

    from backend.services.prices import estimate_stock_risk

    rng = np.random.default_rng(0)
    m = rng.normal(0.01, 0.05, 120)
    s = 1.4 * m + rng.normal(0, 0.06, 120)
    est = estimate_stock_risk(s, m)
    assert est["beta"] == pytest.approx(1.4, abs=0.15)
    assert est["specific_vol"] == pytest.approx(0.06 * 12 ** 0.5, rel=0.15)
    assert estimate_stock_risk(s[:20], m[:20]) is None     # too little history


def test_a_toss_up_hold_is_not_described_as_holding_winning():
    verdict, reasons = decide("hold", "rational", 0.9, 0.44, horizon_years=22)
    assert verdict == "HOLD"
    assert "close to even" in reasons[0] and "beat" not in reasons[0]


def test_slab_rate_uses_income_before_tax():
    """Tier 1 income is take-home pay; the slab rate needs gross income.

    ₹1.3 lakh a month take-home is about ₹16.9 lakh gross, in the 16-20 L
    slab (20.8%), not the 12-16 L slab (15.6%) the take-home figure alone
    would put it in.
    """
    from src.simulator_v2 import marginal_slab_rate

    ctx = {**CONTEXT, "monthly_income": 130_000, "rent_received": 0}
    inputs, _, _ = build(decision(portfolio_context=ctx))
    assert inputs["annual_income"] > 12 * 130_000
    assert marginal_slab_rate(inputs["annual_income"]) == pytest.approx(0.20 * 1.04)
    assert marginal_slab_rate(12 * 130_000) == pytest.approx(0.15 * 1.04)
