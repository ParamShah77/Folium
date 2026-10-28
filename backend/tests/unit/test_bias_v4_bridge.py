"""Bias model v4 in the app — input assembly, disclosure and wording, no datastore.

``build_v4_inputs`` decides what the model sees for a real decision: which
values come from the decision row, the profile and the portfolio snapshot, and
which are filled in. Each fill must be disclosed, or a confidence figure built
on standard values would read as if it were built on the user's own.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.core.bias_detector import _resolve_profile, build_v4_inputs
from backend.core.explainer import _V4_MEANING, _driver_factors, bias_copy, driver_label

MEDIANS = {
    "holding_period_months": 14.0, "position_share": 0.12, "equity_share": 0.55, "gold_share": 0.17,
    "liquid_assets": 970_000.0, "age": 38.0, "investment_horizon": 22.0, "risk_tolerance": 0.53,
    "monthly_income": 75_000.0, "monthly_outflow": 13_000.0, "has_emergency_fund": 1,
}
MARKET = {"nifty_1m_return": 0.0104, "vix": 16.89, "nifty_volatility_30d": 0.00885}
PROFILE_ROW = {
    "age": 34, "risk_tolerance": Decimal("0.60"), "investment_horizon": 20,
    "monthly_income": Decimal("90000"), "monthly_expense": Decimal("30000"),
    "has_emergency_fund": True, "financial_strategy": "moderate", "goal": "Wealth growth",
}
CONTEXT = {
    "position_share": 0.09, "equity_share": 0.6, "gold_share": 0.15, "liquid": 1_500_000,
    "real_estate": 6_000_000, "liabilities": 2_500_000, "monthly_income": 90_000,
    "rent_received": 12_000, "committed_outflow": 30_000,
}


def decision(**kw):
    d = {
        "decision_intent": "sell", "unrealized_pnl_pct": Decimal("0.3400"), "holding_period_days": 400,
        "nifty_1m_return": Decimal("-0.0568"), "vix_value": Decimal("14.780"),
        "nifty_volatility_30d": Decimal("0.00663"), "portfolio_context": dict(CONTEXT),
    }
    d.update(kw)
    return d


def build(d, row=PROFILE_ROW):
    profile, assumed = _resolve_profile(row)
    inputs, fixed = build_v4_inputs(d, profile, assumed, MEDIANS, MARKET)
    return inputs, fixed, assumed


def test_full_portfolio_needs_no_standard_values():
    inputs, fixed, assumed = build(decision())
    assert fixed == [] and assumed == []
    assert inputs["action"] == "sell"
    assert inputs["unrealized_gl"] == pytest.approx(0.34)
    assert inputs["holding_period_months"] == 13
    assert inputs["vix"] == pytest.approx(14.78)
    assert inputs["position_share"] == pytest.approx(0.09)
    assert inputs["gold_share"] == pytest.approx(0.15)
    assert inputs["real_estate_value"] == 6_000_000 and inputs["loans_outstanding"] == 2_500_000


def test_cash_flow_follows_section_10():
    """Income and committed outflow from the snapshot; rent received counted."""
    inputs, _, _ = build(decision())
    assert inputs["monthly_income"] == 90_000
    assert inputs["rent_received"] == 12_000
    assert inputs["monthly_outflow"] == 30_000


def test_no_portfolio_snapshot_is_disclosed():
    inputs, fixed, _ = build(decision(portfolio_context=None))
    assert set(fixed) == {"position_share", "asset_mix", "liquid_assets", "property_loans"}
    assert inputs["position_share"] == MEDIANS["position_share"]
    assert inputs["real_estate_value"] == 0.0 and inputs["loans_outstanding"] == 0.0
    # Cash flow falls back to the profile.
    assert inputs["monthly_income"] == 90_000 and inputs["monthly_outflow"] == 30_000


def test_a_pre_v4_snapshot_discloses_only_what_it_lacks():
    old = {k: v for k, v in CONTEXT.items() if k not in ("gold_share", "real_estate", "liabilities")}
    _, fixed, _ = build(decision(portfolio_context=old))
    assert set(fixed) == {"asset_mix", "property_loans"}


def test_missing_profile_fields_use_v4_medians_not_v3_cohort_values():
    """v3's 45,000-on-60,000 default is a 25% surplus, below v4's training range."""
    inputs, _, assumed = build(decision(portfolio_context=None), row=None)
    assert {"monthly_income", "monthly_expense", "age"} <= set(assumed)
    assert inputs["monthly_income"] == MEDIANS["monthly_income"]
    assert inputs["monthly_outflow"] == MEDIANS["monthly_outflow"]
    assert inputs["age"] == 38


def test_missing_market_uses_the_median_real_day():
    inputs, _, _ = build(decision(nifty_1m_return=None, vix_value=None, nifty_volatility_30d=None))
    assert inputs["nifty_1m_return"] == MARKET["nifty_1m_return"]
    assert inputs["vix"] == MARKET["vix"]
    assert inputs["nifty_volatility_30d"] == MARKET["nifty_volatility_30d"]


def test_missing_volatility_is_implied_from_vix():
    inputs, _, _ = build(decision(nifty_volatility_30d=None, vix_value=Decimal("15.87")))
    assert inputs["nifty_volatility_30d"] == pytest.approx(0.01, abs=1e-4)


def test_unknown_holding_period_is_disclosed():
    inputs, fixed, _ = build(decision(holding_period_days=None))
    assert "holding_period" in fixed
    assert inputs["holding_period_months"] == 14


# ── Wording ─────────────────────────────────────────────────────────────

def test_every_v4_driver_has_plain_words():
    src_v4 = pytest.importorskip("src.bias_model_v4", reason="ML extras not installed")
    for driver in src_v4.DRIVERS:
        label = driver_label(driver, {}, "sell")
        assert label and "_" not in label, driver


@pytest.mark.parametrize("action, label", [
    ("sell", "Your choice to sell"), ("hold", "Your choice to hold"), ("buy_more", "Your choice to buy more"),
])
def test_action_driver_reads_as_a_sentence(action, label):
    # Regression: a second ``_ACTION_WORDS`` (gerunds, for the causal text)
    # once overrode this, giving "Your choice to holding on".
    assert driver_label("action", {}, action) == label


@pytest.mark.parametrize("bias, action", [
    ("loss_aversion", "sell"), ("loss_aversion", "hold"), ("herd_behavior", "sell"),
    ("herd_behavior", "buy_more"), ("disposition_effect", "sell"), ("disposition_effect", "hold"),
])
def test_every_allowed_bias_and_action_pair_has_its_own_meaning(bias, action):
    assert (bias, action) in _V4_MEANING
    headline, meaning = bias_copy(bias, action, "bias_v4")
    assert headline.startswith("This looks like") and meaning == _V4_MEANING[(bias, action)]


def test_v3_decisions_keep_situation_wording():
    _, meaning = bias_copy("disposition_effect", "sell", "xgboost_v3")
    assert "situation" in meaning


def test_pattern_fit_labels_name_the_action():
    f = {"allows_disposition": 1}
    assert driver_label("fits_disposition", f, "sell") == "Selling a winner in a calm market"
    assert driver_label("fits_disposition", f, "hold") == "Holding a loser in a calm market"
    assert driver_label("fits_disposition", {"allows_disposition": 0}, "sell") == "Doesn't fit the disposition effect"
    assert driver_label("gain_loss", {"unrealized_gl": -0.18}, "sell") == "Your loss on this holding (-18%)"


def test_driver_factors_keep_direction_and_skip_bad_rows():
    drivers = [
        {"driver": "fits_disposition", "impact": 2.1, "share": 0.5, "direction": "toward",
         "inputs": {"allows_disposition": 1}},
        {"error": "boom"},
        {"driver": "position_size", "impact": -0.3, "share": 0.07, "direction": "against",
         "inputs": {"position_share": 0.45}},
    ]
    out = _driver_factors(drivers, "sell")
    assert [f["feature"] for f in out] == ["fits_disposition", "position_size"]
    assert out[0]["label"] == "Selling a winner in a calm market"
    assert out[1]["direction"] == "against" and out[1]["shap_impact"] == -0.3


def test_cash_need_is_not_stated_unless_the_comment_says_so():
    inputs, _, _ = build(decision())
    assert inputs["cash_need_stated"] == 0
    inputs, _, _ = build(decision(comment_facts={"cash_need": True, "quote": "need it for fees"}))
    assert inputs["cash_need_stated"] == 1
