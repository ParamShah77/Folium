"""Phase 5A bridge translation — the parts that need no datastore.

The bridge's risk is not that the classifier is wrong; it is that the *edges*
around it are. A label the DB rejects, a VIX proxy that drifts from the
prototype's, a NULL profile field silently becoming 0 — each produces a decision
that either fails at INSERT or, worse, succeeds with a number nobody can defend.
These tests pin all three.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.core.bias_detector import _resolve_profile
from backend.core.ml_bridge import (
    BIAS_LABEL_MAP,
    NEUTRAL_DAILY_VOLATILITY,
    MLUnavailableError,
    crowd_ratio_from_vix,
    map_bias_label,
    map_financial_strategy,
    map_goal,
    market_return_from_row,
    market_volatility_from_row,
)


# --------------------------------------------------------------------------- #
# Label vocabulary
# --------------------------------------------------------------------------- #

def test_every_mapped_label_satisfies_the_0003_check_constraint():
    """Migration 0003 constrains bias_detected to exactly these four values."""
    allowed = {"loss_aversion", "herd_behavior", "disposition_effect", "rational"}
    assert set(BIAS_LABEL_MAP.values()) == allowed


def test_map_bias_label_translates_the_two_that_differ():
    assert map_bias_label("disposition") == "disposition_effect"
    assert map_bias_label("herd") == "herd_behavior"


def test_map_bias_label_passes_through_the_two_that_match():
    assert map_bias_label("loss_aversion") == "loss_aversion"
    assert map_bias_label("rational") == "rational"


def test_unknown_label_raises_rather_than_returning_none():
    """A silent None would land as NULL and read as 'no bias detected'."""
    with pytest.raises(MLUnavailableError, match="unknown bias label"):
        map_bias_label("overconfidence")


def test_label_map_covers_everything_the_model_can_emit():
    """Guards against src.bias_detector.BIAS_LABELS gaining a class."""
    src_bias_detector = pytest.importorskip(
        "src.bias_detector", reason="ML extras not installed"
    )
    assert set(src_bias_detector.BIAS_LABELS.values()) <= set(BIAS_LABEL_MAP)


# --------------------------------------------------------------------------- #
# crowd_ratio — must track src/market_data.py::_fetch_vix_crowd_ratio
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "vix, expected",
    [
        (10.0, 0.05),   # clamped at the floor, not 0.0
        (15.0, 0.125),
        (25.0, 0.375),
        (40.0, 0.75),
        (50.0, 1.0),    # clamped at the ceiling
        (80.0, 1.0),    # far beyond any real VIX; still clamped
        (0.0, 0.05),    # nonsense input must not go negative
    ],
)
def test_crowd_ratio_matches_the_prototype_formula(vix, expected):
    assert crowd_ratio_from_vix(vix) == pytest.approx(expected)


def test_crowd_ratio_stays_within_bounds_for_any_vix():
    for vix in range(0, 121):
        assert 0.05 <= crowd_ratio_from_vix(float(vix)) <= 1.0


def test_missing_vix_falls_back_to_neutral():
    """Matches src/market_data.py's default response, not 0.0."""
    assert crowd_ratio_from_vix(None) == 0.50


def test_crowd_ratio_accepts_decimal_from_asyncpg():
    """vix_value is NUMERIC(6,3); asyncpg hands back Decimal, not float."""
    assert crowd_ratio_from_vix(Decimal("25.000")) == pytest.approx(0.375)


# --------------------------------------------------------------------------- #
# market_return / market_volatility — must match the training features
# --------------------------------------------------------------------------- #

def test_market_return_uses_the_one_month_return():
    """Training's market_return_recent is NIFTY's 1-month return."""
    row = {"nifty_1m_return": Decimal("-0.0460"), "nifty_52w_return": Decimal("0.1832"),
           "nifty_1d_change": Decimal("0.0098")}
    assert market_return_from_row(row) == pytest.approx(-0.0460)


def test_market_return_never_substitutes_other_horizons():
    """A 52-week or 1-day figure is off-distribution; flat beats wrong."""
    row = {"nifty_52w_return": Decimal("0.1832"), "nifty_1d_change": Decimal("-0.0041")}
    assert market_return_from_row(row) == 0.0


def test_market_return_treats_a_genuine_zero_as_data():
    assert market_return_from_row({"nifty_1m_return": Decimal("0.0000")}) == 0.0


def test_volatility_prefers_the_measured_30_day_value():
    row = {"nifty_volatility_30d": Decimal("0.00628"), "vix_value": Decimal("40.0")}
    assert market_volatility_from_row(row) == pytest.approx(0.00628)


def test_volatility_falls_back_to_vix_on_the_daily_scale():
    """VIX is annualised %; 15.87 -> ~0.01 daily."""
    assert market_volatility_from_row({"vix_value": Decimal("15.87")}) == pytest.approx(0.01, abs=1e-4)


def test_volatility_defaults_to_the_training_median():
    assert market_volatility_from_row({}) == pytest.approx(NEUTRAL_DAILY_VOLATILITY)


# --------------------------------------------------------------------------- #
# Profile vocabulary
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "app_value, model_value",
    [("conservative", "saving"), ("moderate", "balanced"), ("aggressive", "investing"),
     ("Aggressive ", "investing"), (None, "saving"), ("unheard-of", "saving")],
)
def test_strategy_maps_risk_appetite_to_model_categories(app_value, model_value):
    assert map_financial_strategy(app_value) == model_value


@pytest.mark.parametrize(
    "goal, expected",
    [("Wealth growth", "wealth growth"), ("long-term wealth", "wealth growth"),
     ("Retirement", "retirement"), (None, "wealth growth")],
)
def test_goal_maps_to_model_vocabulary(goal, expected):
    assert map_goal(goal) == expected


# --------------------------------------------------------------------------- #
# Profile defaulting
# --------------------------------------------------------------------------- #

def test_complete_profile_is_used_verbatim_and_assumes_nothing():
    row = {
        "age": 41, "risk_tolerance": Decimal("0.625"), "investment_horizon": 15,
        "monthly_income": Decimal("180000.00"), "monthly_expense": Decimal("90000.00"),
        "has_emergency_fund": True, "financial_strategy": "investing",
        "goal": "retirement",
    }
    resolved, assumed = _resolve_profile(row)
    assert assumed == []
    assert resolved["age"] == 41
    assert resolved["risk_tolerance"] == pytest.approx(0.625)
    assert resolved["has_emergency_fund"] == 1  # bool → int for the model


def test_null_fields_are_defaulted_and_every_one_is_disclosed():
    row = {
        "age": None, "risk_tolerance": None, "investment_horizon": None,
        "monthly_income": Decimal("95000.00"), "monthly_expense": None,
        "has_emergency_fund": None, "financial_strategy": None, "goal": None,
    }
    resolved, assumed = _resolve_profile(row)
    assert set(assumed) == {
        "age", "risk_tolerance", "investment_horizon",
        "monthly_expense", "has_emergency_fund", "financial_strategy", "goal",
    }
    assert "monthly_income" not in assumed
    assert resolved["monthly_income"] == pytest.approx(95000.0)
    assert resolved["age"] == 35


def test_absent_user_row_defaults_everything():
    resolved, assumed = _resolve_profile(None)
    assert len(assumed) == 8
    assert resolved["financial_strategy"] == "conservative"
    assert map_financial_strategy(resolved["financial_strategy"]) == "saving"


def test_false_emergency_fund_is_kept_not_treated_as_missing():
    """False is a real answer; defaulting it to 1 would invert the feature."""
    row = {
        "age": 30, "risk_tolerance": Decimal("0.4"), "investment_horizon": 20,
        "monthly_income": Decimal("50000"), "monthly_expense": Decimal("40000"),
        "has_emergency_fund": False, "financial_strategy": "moderate", "goal": "x",
    }
    resolved, assumed = _resolve_profile(row)
    assert resolved["has_emergency_fund"] == 0
    assert "has_emergency_fund" not in assumed
