"""Bias model v4 (Phase A2) — features, label guard, calibration, drivers, sense checks.

Needs the trained artefacts (models/bias_detector_v4.json + .meta.json, written
by scripts/train_bias_v4.py) and the cached dataset; skips cleanly without them.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import bias_model_v4 as M  # noqa: E402
from src import dataset_v4 as D  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (os.path.exists(M.MODEL_PATH) and os.path.exists(M.META_PATH) and os.path.exists(D.DATASET_CSV)),
    reason="bias model v4 not trained (scripts/train_bias_v4.py)",
)

CALM = {"nifty_1m_return": 0.015, "vix": 13.0, "nifty_volatility_30d": 0.0075}
CRASH = {"nifty_1m_return": -0.25, "vix": 55.0, "nifty_volatility_30d": 0.040}
EUPHORIA = {"nifty_1m_return": 0.08, "vix": 12.5, "nifty_volatility_30d": 0.007}


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return M.raw_from_dataset(pd.read_csv(D.DATASET_CSV).head(1500))


@pytest.fixture(scope="module")
def base() -> dict:
    med = M.input_medians()
    out = {k: med[k] for k in M.INPUTS if k != "action"}
    out.update(real_estate_value=0.0, loans_outstanding=0.0, rent_received=0.0)
    return out


def case(base: dict, market: dict, **kw) -> dict:
    return {**base, **market, **kw}


# ── Features ────────────────────────────────────────────────────────────

def test_features_have_the_trained_order(raw):
    assert tuple(M.build_features(raw).columns) == M.FEATURES
    assert tuple(M.read_meta()["features"]) == M.FEATURES


def test_one_row_and_batch_build_identical_features(raw):
    """Training builds features in a batch; the app builds one row. They must agree."""
    batch = M.build_features(raw.head(50))
    for i in range(50):
        one = M.build_features(raw.iloc[[i]])
        pd.testing.assert_frame_equal(one.reset_index(drop=True), batch.iloc[[i]].reset_index(drop=True))


def test_missing_input_and_unknown_action_are_rejected(raw):
    with pytest.raises(KeyError, match="gold_share"):
        M.build_features(raw.drop(columns=["gold_share"]))
    with pytest.raises(ValueError, match="unknown action"):
        M.build_features(raw.head(1).assign(action="panic"))


def test_every_feature_belongs_to_a_driver():
    assert set(M.DRIVER_OF) == set(M.FEATURES)


# ── Label guard ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("gl, market, action, allowed", [
    (0.35, CALM, "sell", {"rational", "disposition"}),
    (-0.15, CALM, "hold", {"rational", "disposition"}),
    (-0.40, CALM, "hold", {"rational", "loss_aversion"}),
    (-0.20, CALM, "sell", {"rational"}),                    # a calm-market loss sale is never disposition
    (-0.35, CRASH, "sell", {"rational", "loss_aversion", "herd"}),
    (0.25, CRASH, "sell", {"rational", "herd"}),
    (0.10, EUPHORIA, "buy_more", {"rational", "herd"}),
    (0.10, CALM, "buy_more", {"rational"}),
])
def test_allowed_labels_follow_the_agreed_definitions(gl, market, action, allowed):
    assert D.allowed_labels(gl, market["nifty_1m_return"], market["vix"], action) == allowed


def test_the_true_label_is_allowed_for_the_whole_dataset():
    df = pd.read_csv(D.DATASET_CSV)
    mask = M.allowed_mask(M.raw_from_dataset(df))
    y = df.bias_type.map({lab: i for i, lab in enumerate(M.LABELS)}).to_numpy()
    # The only exceptions sit exactly on the -4% threshold after 4-decimal
    # rounding (the true return was a hair above it).
    bad = ~mask[np.arange(len(y)), y]
    assert bad.sum() <= 10
    assert np.allclose(df.nifty_1m_return[bad], -0.04)


def test_guard_removes_ruled_out_patterns():
    p = np.array([[0.5, 0.2, 0.2, 0.1]])
    mask = np.array([[False, True, False, True]])
    q = M.apply_guard(p, mask)
    assert q[0, 0] == 0 and q[0, 2] == 0
    assert q.sum() == pytest.approx(1.0)


# ── Calibration ─────────────────────────────────────────────────────────

def test_calibration_curve_rises_and_never_claims_certainty():
    curve = M.read_meta()["calibration"]
    x, y = np.array(curve["x"]), np.array(curve["y"])
    assert np.all(np.diff(x) >= 0) and np.all(np.diff(y) >= 0)
    assert y.max() <= 0.99


def test_calibration_never_changes_the_answer():
    rng = np.random.default_rng(0)
    p = rng.dirichlet(np.ones(4) * 0.7, size=5000)
    curve = M.read_meta()["calibration"]
    q = M.calibrate_top_label(p, np.array(curve["x"]), np.array(curve["y"]))
    assert np.array_equal(q.argmax(1), p.argmax(1))
    assert np.allclose(q.sum(1), 1.0)


# ── Prediction ──────────────────────────────────────────────────────────

def test_prediction_is_coherent(base):
    r = M.predict(case(base, CALM, action="sell", unrealized_gl=0.35))
    probs = r["probabilities"]
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-3)
    assert r["confidence"] == pytest.approx(probs[r["bias_type"]])
    assert r["bias_type"] in r["allowed"]
    assert r["is_biased"] == (r["bias_type"] != "rational")
    assert len(r["drivers"]) == 5


def test_drivers_explain_the_chosen_pattern_exactly(base):
    """TreeSHAP is additive: features + bias term reproduce each class's score."""
    x = case(base, CRASH, action="sell", unrealized_gl=-0.30)
    assert M.sanity_check_contributions(x) < 1e-4
    r = M.predict(x, top_n=len(M.DRIVERS))
    impacts = [abs(d["impact"]) for d in r["drivers"]]
    assert impacts == sorted(impacts, reverse=True)
    for d in r["drivers"]:
        assert d["direction"] == ("toward" if d["impact"] > 0 else "against")
    assert sum(d["share"] for d in r["drivers"]) == pytest.approx(1.0, abs=1e-3)


# ── Sense checks (the full set is in results/reports/bias_v4_evaluation.json) ──

@pytest.mark.parametrize("market, kw, expected", [
    (CALM, {"action": "sell", "unrealized_gl": 0.35, "position_share": 0.08}, "disposition"),
    (CALM, {"action": "hold", "unrealized_gl": -0.40}, "loss_aversion"),
    (CALM, {"action": "sell", "unrealized_gl": -0.20}, "rational"),
    (CRASH, {"action": "sell", "unrealized_gl": -0.35}, "loss_aversion"),
    (CRASH, {"action": "sell", "unrealized_gl": 0.25}, "herd"),
    (CALM, {"action": "hold", "unrealized_gl": 0.10}, "rational"),
])
def test_sense_checks(base, market, kw, expected):
    assert M.predict(case(base, market, **kw))["bias_type"] == expected


def test_the_action_changes_the_reading(base):
    """v3's blind spot: the same calm-market winner, three different decisions."""
    got = {a: M.predict(case(base, CALM, action=a, unrealized_gl=0.35, position_share=0.08))["bias_type"]
           for a in M.ACTIONS}
    assert got == {"sell": "disposition", "hold": "rational", "buy_more": "rational"}


def test_rebalancing_an_oversized_holding_reads_as_less_biased(base):
    small = M.predict(case(base, CALM, action="sell", unrealized_gl=0.35, position_share=0.08))
    big = M.predict(case(base, CALM, action="sell", unrealized_gl=0.35, position_share=0.45))
    assert big["model_probabilities"]["disposition"] < small["model_probabilities"]["disposition"]
