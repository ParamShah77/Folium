"""Pure logic of the Phase 5B–5D steps — recommendation rules, explanation
helpers, market trend. No datastore and no model needed."""
from __future__ import annotations

import pytest

from backend.core.explainer import FEATURE_LABELS, _refutations, _shap_factors, inr
from backend.core.recommendation import decide
from backend.services.market_data import trend_from_return


# --------------------------------------------------------------------------- #
# Recommendation rules (debate step until Phase 5D)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "intent, bias, conf, p, verdict",
    [
        ("sell", "loss_aversion", 0.8, 0.92, "HOLD"),     # strong case for holding
        ("sell", "rational", 0.9, 0.30, "SELL"),          # simulations favour selling
        ("sell", "loss_aversion", 0.7, 0.50, "HOLD"),     # toss-up + bias -> wait
        ("sell", "rational", 0.9, 0.50, "SELL"),          # toss-up, sound reasoning stands
        ("hold", "rational", 0.9, 0.80, "HOLD"),
        ("hold", "loss_aversion", 0.8, 0.20, "SELL"),     # holding a loser out of pain
        ("buy_more", "herd_behavior", 0.4, 0.90, "HOLD"), # herd buying is never endorsed
        ("buy_more", "disposition_effect", 0.75, 0.9, "HOLD"),
        ("buy_more", "rational", 0.9, 0.70, "BUY_MORE"),
        ("buy_more", "rational", 0.9, 0.30, "HOLD"),
    ],
)
def test_decide(intent, bias, conf, p, verdict):
    got, reasons = decide(intent, bias, conf, p)
    assert got == verdict
    assert reasons, "every verdict must carry its reasons"


def test_missing_simulation_is_disclosed_and_treated_as_even():
    verdict, reasons = decide("sell", "rational", 0.9, None)
    assert verdict == "SELL"
    assert any("No simulation" in r for r in reasons)


def test_reasons_quote_the_number_they_used():
    _, reasons = decide("sell", "loss_aversion", 0.8, 0.874)
    assert any("87%" in r for r in reasons)


# --------------------------------------------------------------------------- #
# Explanation helpers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "amount, text",
    [(82450, "₹82,450"), (385000, "₹3.85 L"), (41200000, "₹4.12 Cr"), (-150000, "-₹1.50 L")],
)
def test_inr_uses_lakh_and_crore(amount, text):
    assert inr(amount) == text


def test_refutation_p_values_are_parsed_from_pickled_reprs():
    details = {
        "random_common_cause": "{'p_value': np.float64(0.3811727570781509), 'x': 1}",
        "placebo_treatment": "{'p_value': np.float64(0.47762353983725125)}",
    }
    parsed = {r["test"]: r["p_value"] for r in _refutations(details)}
    assert parsed == {"random common cause": 0.3812, "placebo treatment": 0.4776}


def test_every_model_feature_has_a_human_label():
    """SHAP can surface any of the 52 features; none may reach the UI raw."""
    src_bias = pytest.importorskip("src.bias_detector", reason="ML extras not installed")
    _, features = src_bias.load_model()
    missing = [f for f in features if f not in FEATURE_LABELS]
    assert missing == []


def test_shap_factors_get_labels_and_skip_error_rows():
    factors = _shap_factors([
        {"feature": "loss_x_crowd", "value": -0.1, "shap_impact": 0.4},
        {"error": "shap failed"},
    ])
    assert [f["label"] for f in factors] == ["Loss combined with crowd fear"]


# --------------------------------------------------------------------------- #
# Market trend
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "ret, trend",
    [(0.05, "bull"), (-0.046, "bear"), (0.01, "sideways"), (-0.02, "sideways"), (None, None)],
)
def test_trend_from_one_month_return(ret, trend):
    assert trend_from_return(ret) == trend


@pytest.mark.parametrize(
    "label, expected",
    [("Crowd fear (India VIX)", "crowd fear (India VIX)"),
     ("NIFTY's 1-month return", "NIFTY's 1-month return"),
     ("Market volatility", "market volatility"),
     ("Age", "age")],
)
def test_sentence_case_keeps_acronyms(label, expected):
    from backend.core.explainer import _sentence_case
    assert _sentence_case(label) == expected


# --------------------------------------------------------------------------- #
# Causal v4: the block shown for a pattern and an action
# --------------------------------------------------------------------------- #

_V4 = {
    "version": "v4",
    "causal_effects": {
        "crowd_ratio": {"label": "Higher market fear (India VIX)", "unit": "VIX 10 points higher",
                        "g_computation": {"sell": 0.045}, "refutation_passed": True, "method": "g"},
        "gold_share": {"label": "More gold", "unit": "+10", "g_computation": {"sell": 0.001}},
        "has_emergency_fund": {"label": "Having an emergency fund", "unit": "having one",
                               "g_computation": {"sell": -0.036}, "refutation_passed": True, "method": "g"},
    },
    "situations": {
        "herd:buy_more": {
            "situation": "During a strong rally", "share_taking_action_observed": 0.34,
            "tendency_effect": {"unit": "+0.1", "g_computation": 0.046, "refutation_passed": True, "refutations": {}},
            "habits": {
                "pause_for_analysis": {"description": "Pausing", "before_estimated": 0.34, "after_estimated": 0.24},
                "combined": {"description": "All", "before_estimated": 0.34, "after_estimated": 0.20},
            },
        },
    },
    "assumptions": {"habits": "halving"},
}


def test_v4_causal_uses_the_situation_for_this_pattern_and_action():
    from backend.core.explainer import _v4_causal

    primary, context, iv = _v4_causal(_V4, "herd_behavior", "buy_more")
    assert primary["action"] == "buy_more" and primary["action_words"] == "buying more"
    assert primary["share_taking_action"] == 0.34 and primary["effect"] == 0.046
    assert iv["key"] == "pause_for_analysis"          # the combined bundle is not offered as advice
    assert (iv["original_sell_prob"], iv["new_sell_prob"]) == (0.34, 0.24)
    labels = [c["treatment"] for c in context]
    assert "gold_share" not in labels                  # too small to state a direction
    assert labels == ["crowd_ratio", "has_emergency_fund"]


def test_v4_causal_has_no_primary_for_a_pattern_the_action_cannot_have():
    from backend.core.explainer import _v4_causal

    primary, _, iv = _v4_causal(_V4, "herd_behavior", "hold")
    assert primary is None and iv is None
