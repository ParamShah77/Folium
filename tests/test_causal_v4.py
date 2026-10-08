"""Causal analysis v4 (Phase A4) — the mechanism replica, do-operations, and the saved results."""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import causal_v4 as C  # noqa: E402
from src import dataset_v4 as D  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(D.DATASET_CSV), reason="dataset v4 not built")


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return C.prepare(pd.read_csv(D.DATASET_CSV))


@pytest.fixture(scope="module")
def results() -> dict:
    if not os.path.exists(C.RESULTS_PATH):
        pytest.skip("results/causal_v4.json not generated (python -m src.causal_v4)")
    return C.load_results()


# ── The replica of the decision rules ────────────────────────────────────

def test_replica_reproduces_every_stored_motive_share(df):
    check = C.consistency_with_stored_data(df)
    assert check["cases"] == 20_000
    assert check["max_abs_error"] == 0.0


def test_rational_action_distribution_matches_the_generator(df):
    rng = np.random.default_rng(0)
    for r in df.sample(150, random_state=3).itertuples(index=False):
        s, inv, pf = C._row_dicts(r)
        dist = C.rational_action_distribution(s, inv, pf)
        draws = [D.rational_action(rng, s, inv, pf)[0] for _ in range(600)]
        for a in C.ACTIONS:
            assert abs(draws.count(a) / 600 - dist[a]) < 0.07


def test_true_action_rates_match_the_data(df):
    p = C.true_probabilities(df).mean(axis=0)
    observed = df[["is_sell", "is_hold", "is_buy_more"]].mean().to_numpy()
    assert np.allclose(p, observed, atol=0.01)
    assert np.allclose(C.true_probabilities(df.head(50)).sum(axis=1), 1.0)


def test_changing_market_fear_recomputes_the_regime(df):
    calm = df[(df.regime == "normal")].head(200)
    feared = C.do(vix=40.0)(calm)
    assert feared.attrs.get("market_changed")
    # At VIX 40 herd selling becomes possible, so selling gets likelier.
    assert C.true_probabilities(feared)[:, 0].mean() > C.true_probabilities(calm)[:, 0].mean()


def test_a_habit_never_raises_the_biased_action(df):
    for (bias, action), spec in C.SITUATIONS.items():
        mask = C.situation_mask(df, spec["motive"])
        sub = df[mask].head(400)
        k = C.ACTIONS.index(action)
        for h in spec["habits"]:
            before = C.true_probabilities(sub)[:, k].mean()
            after = C.true_probabilities(C.HABITS[h]["do"](sub))[:, k].mean()
            assert after <= before + 1e-9, (bias, action, h)


# ── Saved results ────────────────────────────────────────────────────────

def test_results_cover_every_situation(results):
    assert results["version"] == "v4"
    assert set(results["situations"]) == {f"{b}:{a}" for b, a in C.SITUATIONS}


def test_estimates_from_data_recover_the_true_effects(results):
    acc = results["accuracy"]
    assert acc["g_computation_mean_abs_error"] < 0.01
    assert acc["g_computation_sign_agreement"] >= 0.95


def test_negative_control_has_no_effect(results):
    gold = results["causal_effects"]["gold_share"]
    assert gold["negative_control"]
    assert gold["true"]["sell"] == 0.0
    assert abs(gold["g_computation"]["sell"]) < 0.005


def test_habit_estimates_point_the_right_way(results):
    """The habit offered for each situation lowers the biased action, in truth and in the estimate.

    The combined bundle is not offered: its parts can work against each other
    (calming crowd-following removes some panic-selling, so more people end up
    holding a deep loser), and its estimate can be off in direction there.
    """
    for key, situ in results["situations"].items():
        for h, v in situ["habits"].items():
            assert v["after_true"] <= v["before_true"], (key, h)
            if h != "combined":
                assert v["after_estimated"] < v["before_estimated"], (key, h)
