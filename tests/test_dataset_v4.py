"""Dataset v4 — every label must follow the agreed definitions (2026-10-07).

These tests run on a 4,000-case build from the cached real market history
(data/v4/market_history.csv), so they need no network.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import dataset_v4 as D  # noqa: E402

pytestmark = pytest.mark.skipif(not os.path.exists(D.MARKET_CSV), reason="market history cache not built")


@pytest.fixture(scope="module")
def market() -> pd.DataFrame:
    return D.load_market_history()


@pytest.fixture(scope="module")
def df(market) -> pd.DataFrame:
    return D.build_dataset(n_cases=4_000, seed=7, market=market)


# ── Definitions ──────────────────────────────────────────────────────────

def test_loss_aversion_is_panic_selling_or_refusing_a_deep_loser(df):
    la = df[df.bias_type == "loss_aversion"]
    panic = la[la.motive == "loss_aversion_panic"]
    refusal = la[la.motive == "loss_aversion_refusal"]
    assert len(panic) + len(refusal) == len(la)
    assert (panic.action == "sell").all()
    assert (panic.unrealized_gl < -0.03).all()
    assert (panic.nifty_1m_return <= D.FALLING_1M).all()
    assert ((panic.vix >= D.FEAR_VIX) | panic.regime.isin(["crash", "correction"])).all()
    assert (refusal.action == "hold").all()
    assert (refusal.unrealized_gl <= D.DEEP_LOSS).all()


def test_disposition_is_selling_winners_or_holding_moderate_losers_in_calm_markets(df):
    dis = df[df.bias_type == "disposition"]
    assert dis.regime.isin(["normal", "bull"]).all()
    win = dis[dis.motive == "disposition_sell_winner"]
    lose = dis[dis.motive == "disposition_hold_loser"]
    assert len(win) + len(lose) == len(dis)
    assert (win.action == "sell").all() and (win.unrealized_gl >= D.EARLY_WIN).all()
    assert (lose.action == "hold").all()
    assert ((lose.unrealized_gl > D.DEEP_LOSS) & (lose.unrealized_gl <= D.MODERATE_LOSS)).all()


def test_herd_is_selling_into_fear_or_buying_into_a_rally(df):
    herd = df[df.bias_type == "herd"]
    fear = herd[herd.motive == "herd_sell_fear"]
    frenzy = herd[herd.motive == "herd_buy_frenzy"]
    assert len(fear) + len(frenzy) == len(herd)
    assert (fear.action == "sell").all()
    assert ((fear.vix >= D.HERD_FEAR_VIX) | (fear.nifty_1m_return <= D.HERD_FEAR_1M)).all()
    assert (frenzy.action == "buy_more").all() and (frenzy.nifty_1m_return >= D.FRENZY_1M).all()


def test_rational_label_means_a_rational_motive(df):
    assert (df[df.bias_type == "rational"].motive.str.startswith("rational_")).all()
    assert (df[df.bias_type != "rational"].motive.isin(D.LABEL_RULES)).all()


def test_label_rules_table_matches_the_generator(df):
    for motive, rule in D.LABEL_RULES.items():
        rows = df[df.motive == motive]
        assert len(rows) > 0, f"{motive} never occurs"
        assert (rows.action == rule["action"]).all()


# ── Realism and coverage ─────────────────────────────────────────────────

def test_market_features_are_the_real_values_for_that_day(df, market):
    by_date = market.set_index(market.date.dt.date)
    sample = df.sample(200, random_state=0)
    for _, row in sample.iterrows():
        real = by_date.loc[row.date]
        assert row.nifty_1m_return == pytest.approx(real.ret_1m, abs=1e-4)
        assert row.vix == pytest.approx(real.vix, abs=0.01)
        assert row.regime == real.regime


def test_every_class_and_action_is_well_represented(df):
    shares = df.bias_type.value_counts(normalize=True)
    assert set(shares.index) == {"rational", "herd", "disposition", "loss_aversion"}
    assert shares.min() >= 0.06
    assert set(df.action) == {"sell", "hold", "buy_more"}


def test_sell_at_a_loss_in_a_calm_market_is_covered(df):
    calm_loss_sell = df[df.regime.isin(["normal", "bull"]) & (df.action == "sell") & (df.unrealized_gl < -0.05)]
    assert len(calm_loss_sell) > 0


def test_hidden_traits_are_marked_so_they_never_become_features(df):
    hidden = [c for c in df.columns if c.startswith("latent_")]
    assert sorted(hidden) == ["latent_cash_shock", "latent_disposition", "latent_herd", "latent_loss_aversion",
                              "latent_needs_cash", "latent_shock_kind", "latent_shock_u", "latent_stated_u"]


def test_build_is_reproducible(market):
    a = D.build_dataset(n_cases=300, seed=11, market=market)
    b = D.build_dataset(n_cases=300, seed=11, market=market)
    pd.testing.assert_frame_equal(a, b)


def test_portfolio_figures_are_consistent(df):
    parts = df.stocks_value + df.mf_value + df.gold_value + df.fixed_deposits + df.savings_balance
    assert (parts - df.liquid_assets).abs().max() < 1.0
    nw = df.liquid_assets + df.real_estate_value - df.home_loan_outstanding - df.other_loans_outstanding
    assert (nw - df.net_worth).abs().max() < 1.0
    assert (df.home_loan_outstanding <= df.real_estate_value + 1).all()



# ── v4.1: stretched households and cash shocks ───────────────────────────

def test_stretched_households_and_missing_funds_are_covered(df):
    surplus = (df.monthly_income + df.rent_received - df.monthly_outflow) / df.monthly_income
    emi = df.monthly_emi / df.monthly_income
    assert (surplus < 0).sum() > 0                                   # paying out more than they earn
    assert (emi[df.monthly_emi > 0] > 0.6).mean() > 0.03             # RBI's at-risk zone
    assert 0.3 < (df.has_emergency_fund == 0).mean() < 0.6


def test_needs_cash_follows_its_definition(df):
    surplus = df.monthly_income + df.rent_received - df.monthly_outflow
    expected = [D.needs_cash(s, f, c, u) for s, f, c, u in
                zip(surplus, df.has_emergency_fund, df.latent_cash_shock, df.latent_shock_u)]
    assert (df.latent_needs_cash.astype(bool) == expected).all()
    # An emergency fund absorbs most shocks.
    shocked = df[df.latent_cash_shock == 1]
    with_fund = shocked[shocked.has_emergency_fund == 1].latent_needs_cash.mean()
    without = shocked[shocked.has_emergency_fund == 0].latent_needs_cash.mean()
    assert without > 0.95 and with_fund < 0.5


def test_a_forced_sale_is_rational_and_only_happens_when_cash_is_needed(df):
    forced = df[df.motive == "rational_needs_cash"]
    assert len(forced) > 50
    assert (forced.action == "sell").all()
    assert (forced.latent_needs_cash == 1).all()


def test_stated_need_is_a_noisy_signal_of_the_real_one(df):
    needed = df[df.latent_needs_cash == 1].cash_need_stated.mean()
    not_needed = df[df.latent_needs_cash == 0].cash_need_stated.mean()
    assert 0.5 < needed < 0.8
    assert not_needed < 0.06
