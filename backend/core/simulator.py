"""Phase 5B — HOLD vs SELL Monte Carlo, replacing ``stub_steps._simulation``.

``SIMULATOR_VERSION`` picks the engine:

* **v2** (default, Phase A3) — ``src/simulator_v2.py``: the investor's own
  horizon (1-30 years), futures resampled from real NIFTY and gold history,
  single-stock risk, real costs and tax, the sale going into the investor's
  own FDs, savings and gold, and monthly investing in both futures. See
  ``results/reports/SIMULATOR_V2.md``. Its inputs come from
  :func:`build_sim_inputs`; everything it had to fill in is disclosed.
* **v1** — the research engine described below, kept as a rollback.

v1 notes follow.

Runs ``src/simulator.py::LongHorizonSimulator.compare_hold_vs_sell`` — the
Objective 2 engine — for the real investor behind the decision.

**The one correction the bridge makes.** ``compare_hold_vs_sell(user_id=...)``
resolves the investor from ``synthetic_users.csv``. Called with an app user's
UUID it finds no match and silently simulates a generic 40-year-old, so every
user would get the same projection. :class:`_InvestorSimulator` overrides only
the profile lookup to return the real profile (age and risk tolerance drive the
stock allocation); the simulation itself is untouched.

**Horizon.** The ``decisions`` columns and the product promise a 20-year view
(``hold_median_20y`` …), so the horizon is fixed at 20 years rather than the
investor's own horizon. The 10 000 pre-generated market paths are 30 years
long, so 20 is always available.

**Money in, money out.** ``compare_hold_vs_sell`` takes the *invested* amount
and applies the unrealised gain/loss itself (HOLD starts at
``invested × (1 + gl)``), so it is passed ``quantity × avg_buy_price`` — not the
current market value, which would count the gain or loss twice.

**Opportunity cost** is the research definition: mean(HOLD) − mean(SELL) final
wealth. The medians are stored alongside it.

**Portfolio-aware allocation.** When the decision came from the portfolio,
``portfolio_context.equity_share`` (stocks + mutual funds over liquid assets)
replaces the research formula's risk-based stock allocation for the HOLD leg,
so the projection reflects the mix the investor actually holds. It is clipped
to [0.20, 0.95], the band the research formula itself spans. The SELL leg
still keeps 30% of that allocation, as in the research model.

The research output is also kept, trimmed of per-path outcomes, under
``simulation_curves.research`` so the explanation step (GAP 3) can narrate it.

Seeds 42/43 are fixed in the research code, so a decision re-run reproduces its
numbers exactly.
"""
from __future__ import annotations

import threading
from decimal import Decimal
from datetime import date
from typing import Any, Mapping

from ..config import get_settings
from .bias_detector import load_investor_profile
from .ml_bridge import MLUnavailableError, ensure_src_importable, run_blocking
from .steps import PipelineContext, StepResult, register_step

HORIZON_YEARS = 20          # v1 only
DEFAULT_HORIZON = 20        # v2, when the profile has no horizon

_shared_paths = None
_paths_lock = threading.Lock()


def _q(value: float, places: str = "0.01") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places))


def _round_list(values: list[float]) -> list[float]:
    return [round(float(v), 2) for v in values]


def _market_paths():
    """Load the 2.3 MB market-path matrix once per process, not per decision."""
    global _shared_paths
    with _paths_lock:
        if _shared_paths is None:
            ensure_src_importable()
            from src.simulator import get_simulator

            _shared_paths = get_simulator().market_paths
        return _shared_paths


def _simulate(profile: dict[str, Any], invested: float, unrealized_gl: float,
              n_paths: int, equity_share: float | None = None) -> dict[str, Any]:
    """Synchronous and CPU-bound — call through ``run_blocking`` only."""
    ensure_src_importable()
    try:
        from src.simulator import LongHorizonSimulator
    except ImportError as exc:
        raise MLUnavailableError(
            "simulation needs the Phase 5 ML extras: "
            "pip install -r backend/requirements-ml.txt"
        ) from exc

    class _InvestorSimulator(LongHorizonSimulator):
        def _get_user_profile(self, user_id):  # noqa: D401 — research override
            return dict(profile)

        def _get_stock_allocation(self, risk_tolerance, age, horizon):
            if equity_share is None:
                return super()._get_stock_allocation(risk_tolerance, age, horizon)
            return float(min(max(equity_share, 0.20), 0.95))

    sim = _InvestorSimulator(n_simulations=n_paths)
    try:
        sim._market_paths = _market_paths()
    except FileNotFoundError as exc:
        raise MLUnavailableError(
            f"market path artefact not found: {exc}. "
            "synthetic_market_paths.npy must be present at the repo root."
        ) from exc
    return sim.compare_hold_vs_sell(
        user_id="app", current_wealth=invested, unrealized_gl=unrealized_gl,
        n_simulations=n_paths,
    )


async def _simulate_v1(ctx: PipelineContext, profile: dict[str, Any], assumed: list[str]) -> StepResult:
    d = ctx.decision

    invested = float(d["holding_quantity"]) * float(d["avg_buy_price"])
    unrealized_gl = float(d["unrealized_pnl_pct"])
    sim_profile = {
        "age": int(profile["age"]),
        "risk_tolerance": float(profile["risk_tolerance"]),
        "investment_horizon": HORIZON_YEARS,
        "monthly_income": float(profile["monthly_income"]),
        "monthly_expense": float(profile["monthly_expense"]),
        "has_emergency_fund": int(profile["has_emergency_fund"]),
        "goal": profile["goal"],
    }
    n_paths = get_settings().SIMULATION_PATHS
    context = d.get("portfolio_context") or {}
    equity_share = context.get("equity_share") or None

    r = await run_blocking(_simulate, sim_profile, invested, unrealized_gl, n_paths, equity_share)

    hold, sell, cmp_ = r["hold"], r["sell"], r["comparison"]
    # Year 0 is the starting position, so charts begin where the investor is today.
    curves = {
        "engine": "monte_carlo_v1",
        "horizon_years": HORIZON_YEARS,
        "n_paths": n_paths,
        "years": [0, *r["years"]],
        "hold_p10": _round_list([hold["starting_wealth"], *r["yearly_hold_p10"]]),
        "hold_p50": _round_list([hold["starting_wealth"], *r["yearly_hold_p50"]]),
        "hold_p90": _round_list([hold["starting_wealth"], *r["yearly_hold_p90"]]),
        "sell_p10": _round_list([sell["starting_wealth"], *r["yearly_sell_p10"]]),
        "sell_p50": _round_list([sell["starting_wealth"], *r["yearly_sell_p50"]]),
        "sell_p90": _round_list([sell["starting_wealth"], *r["yearly_sell_p90"]]),
        "invested": round(invested, 2),
        "hold_start": round(hold["starting_wealth"], 2),
        "sell_start": round(sell["starting_wealth"], 2),
        "hold_stock_allocation": round(hold["stock_allocation"], 4),
        "sell_stock_allocation": round(sell["stock_allocation"], 4),
        "hold_mean": round(hold["mean"], 2),
        "sell_mean": round(sell["mean"], 2),
        "prob_hold_better": round(cmp_["prob_hold_better"], 4),
        "wealth_gap_pct": round(cmp_["wealth_gap_pct"], 2),
        "opportunity_cost_basis": "mean(HOLD) - mean(SELL) final wealth",
        "allocation_basis": "portfolio" if equity_share else "risk_profile",
        "assumed_defaults": assumed,
        # The research result minus per-path outcomes, for GAP 3's narrative.
        "research": {
            "horizon_years": r["horizon_years"],
            "inputs": r["inputs"],
            "user_profile": r["user_profile"],
            "assumptions": r.get("assumptions", {}),
            "hold": {k: v for k, v in hold.items() if k != "outcomes"},
            "sell": {k: v for k, v in sell.items() if k != "outcomes"},
            "comparison": cmp_,
            "years": r["years"],
            **{k: _round_list(r[k]) for k in (
                "yearly_hold_p10", "yearly_hold_p50", "yearly_hold_p90",
                "yearly_sell_p10", "yearly_sell_p50", "yearly_sell_p90",
            )},
        },
    }

    return StepResult(
        updates={
            "hold_median_20y": _q(hold["median"]),
            "hold_p10_20y": _q(hold["p10"]),
            "hold_p90_20y": _q(hold["p90"]),
            "sell_median_20y": _q(sell["median"]),
            "sell_p10_20y": _q(sell["p10"]),
            "sell_p90_20y": _q(sell["p90"]),
            "opportunity_cost_inr": _q(cmp_["opportunity_cost_inr"]),
            "simulation_curves": curves,
        },
        event={
            "hold_median_20y": round(hold["median"], 2),
            "sell_median_20y": round(sell["median"], 2),
            "prob_hold_better": round(cmp_["prob_hold_better"], 4),
        },
    )


# --------------------------------------------------------------------------- #
# v2 — the investor's horizon, real-history futures, tax (Phase A3)
# --------------------------------------------------------------------------- #

def build_sim_inputs(
    d: Mapping[str, Any],
    profile: Mapping[str, Any],
    assumed: list[str],
    today: date | None = None,
) -> tuple[dict[str, Any], list[str], str]:
    """Simulation v2 inputs for one decision, what was filled in, and the horizon's source.

    Pure — no I/O. ``fixed`` lists the portfolio inputs that used standard
    values; profile gaps are already in ``assumed``.
    """
    today = today or date.today()
    context = d.get("portfolio_context") or {}
    fixed: list[str] = []

    qty, avg = float(d["holding_quantity"]), float(d["avg_buy_price"])
    price = d.get("current_price")
    cost_basis = qty * avg
    position_value = qty * float(price) if price is not None else cost_basis * (1 + float(d["unrealized_pnl_pct"]))

    days = d.get("holding_period_days")
    if days is None:
        months_held = 13          # unknown: assume long-term (the common case) and say so
        fixed.append("holding_period")
    else:
        months_held = max(0, int(float(days) // 30))

    if "investment_horizon" in assumed or not profile.get("investment_horizon"):
        horizon, source = DEFAULT_HORIZON, "default"
    else:
        horizon, source = int(profile["investment_horizon"]), "profile"

    income = context.get("monthly_income")
    income = float(income if income is not None else profile["monthly_income"])
    rent_received = float(context.get("rent_received") or 0.0)

    allocation = context.get("allocation")
    if allocation:
        equity_total = float(allocation.get("stocks", 0.0)) + float(allocation.get("mutual_funds", 0.0))
        other_equity = max(equity_total - position_value, 0.0)
        gold = float(allocation.get("gold", 0.0))
        fds = float(allocation.get("fixed_deposits", 0.0))
        savings = float(allocation.get("savings", 0.0))
    else:
        other_equity = gold = fds = savings = 0.0
        fixed.append("portfolio")

    sip = context.get("monthly_sip")
    if sip is None:
        fixed.append("monthly_sip")

    asset_type = context.get("asset_type") if context.get("asset_type") in ("equity", "mf") else "equity"
    risk = context.get("stock_risk") or {}
    if asset_type == "equity" and not risk:
        fixed.append("stock_risk")

    edu = float(context.get("education_monthly") or 0.0)
    edu_end = context.get("education_end_year")
    years_left = max(int(edu_end) - today.year, 0) if edu and edu_end else None

    inputs = {
        "position_value": round(position_value, 2),
        "cost_basis": round(cost_basis, 2),
        "months_held": months_held,
        "asset_type": asset_type,
        # The stock's measured beta and own volatility; the engine's defaults otherwise.
        "beta": float(risk.get("beta", 1.0)),
        "specific_vol": float(risk["specific_vol"]) if risk.get("specific_vol") is not None else None,
        "horizon_years": horizon,
        # Slab rate on interest: salary plus 70% of rent (30% standard deduction).
        "annual_income": round(12 * (income + 0.7 * rent_received), 2),
        "other_equity": round(other_equity, 2),
        "gold": round(gold, 2),
        "fixed_deposits": round(fds, 2),
        "savings": round(savings, 2),
        "monthly_sip": float(sip or 0.0),
        "education_monthly": edu,
        "years_until_education_ends": years_left,
    }
    return inputs, fixed, source


def _simulate_v2(inputs: dict[str, Any], n_paths: int) -> dict[str, Any]:
    """Synchronous and CPU-bound — call through ``run_blocking`` only."""
    ensure_src_importable()
    try:
        from src import simulator_v2
    except ImportError as exc:
        raise MLUnavailableError(
            "simulation needs the Phase 5 ML extras: "
            "pip install -r backend/requirements-ml.txt"
        ) from exc
    try:
        return simulator_v2.simulate(simulator_v2.SimInputs(**inputs, n_paths=n_paths))
    except FileNotFoundError as exc:
        raise MLUnavailableError(
            f"market history not found: {exc}. data/sim_v2/monthly_history.csv must be present."
        ) from exc


async def _simulate_v2_step(ctx: PipelineContext, profile: dict[str, Any], assumed: list[str]) -> StepResult:
    d = ctx.decision
    inputs, fixed, source = build_sim_inputs(d, profile, assumed)
    n_paths = get_settings().SIMULATION_PATHS
    r = await run_blocking(_simulate_v2, inputs, n_paths)

    hold, sell, cmp_ = r["hold"], r["sell"], r["comparison"]
    start_h, start_s = inputs["position_value"], r["sale"]["proceeds"]
    a = r["assumptions"]
    curves = {
        "engine": r["engine"],
        "horizon_years": r["horizon_years"],
        "horizon_source": source,
        "n_paths": n_paths,
        # Year 0 is today: what the holding is worth, against cash in hand after selling.
        "years": [0, *r["years"]],
        **{f"{side}_{q}": _round_list([start, *r[f"yearly_{side}_{q}"]])
           for side, start in (("hold", start_h), ("sell", start_s)) for q in ("p10", "p50", "p90")},
        "values_basis": "in hand after tax and costs if cashed in that year",
        "invested": inputs["cost_basis"],
        "hold_start": start_h,
        "sell_start": start_s,
        "hold_stock_allocation": hold["stock_allocation"],
        "sell_stock_allocation": sell["stock_allocation"],
        "hold_mean": round(hold["mean"], 2),
        "sell_mean": round(sell["mean"], 2),
        "prob_hold_better": round(cmp_["prob_hold_better"], 4),
        "wealth_gap_pct": round(cmp_["wealth_gap_pct"], 2),
        "opportunity_cost_basis": cmp_["opportunity_cost_basis"],
        "sale": r["sale"],
        "portfolio": r["portfolio"],
        "growth": {
            "shares": a["equity_growth"], "gold": a["gold_growth"],
            "fixed_deposits": a["fd_rate"], "savings": a["savings_rate"],
            "slab_rate_on_interest": a["slab_rate_on_interest"], "history": a["history"],
            "tax_rules": a["tax_rules"],
        },
        "holding_risk": {
            "asset_type": inputs["asset_type"],
            "beta": inputs["beta"],
            "specific_vol": inputs["specific_vol"] if inputs["specific_vol"] is not None
            else a["stock_specific_vol" if inputs["asset_type"] == "equity" else "fund_tracking_vol"],
            "source": "measured" if inputs["specific_vol"] is not None else "typical",
        },
        "allocation_basis": "portfolio" if "portfolio" not in fixed else "assumed",
        "assumed_defaults": assumed,
        "fixed_inputs": fixed,
        # The engine's result minus nothing large, for GAP 3's narrative.
        "research": {k: r[k] for k in (
            "engine", "horizon_years", "years", "hold", "sell", "sale", "comparison", "portfolio",
            "assumptions", "inputs",
            "yearly_hold_p10", "yearly_hold_p50", "yearly_hold_p90",
            "yearly_sell_p10", "yearly_sell_p50", "yearly_sell_p90",
        )},
    }

    # The *_20y columns predate per-investor horizons; they hold the values at
    # the end of the investor's horizon (curves.horizon_years says which).
    return StepResult(
        updates={
            "hold_median_20y": _q(hold["median"]),
            "hold_p10_20y": _q(hold["p10"]),
            "hold_p90_20y": _q(hold["p90"]),
            "sell_median_20y": _q(sell["median"]),
            "sell_p10_20y": _q(sell["p10"]),
            "sell_p90_20y": _q(sell["p90"]),
            "opportunity_cost_inr": _q(cmp_["opportunity_cost_inr"]),
            "simulation_curves": curves,
        },
        event={
            "horizon_years": r["horizon_years"],
            "hold_median_20y": round(hold["median"], 2),
            "sell_median_20y": round(sell["median"], 2),
            "prob_hold_better": round(cmp_["prob_hold_better"], 4),
        },
    )


async def simulate(ctx: PipelineContext) -> StepResult:
    profile, assumed = await load_investor_profile(ctx)
    if get_settings().SIMULATOR_VERSION.strip().lower() == "v1":
        return await _simulate_v1(ctx, profile, assumed)
    return await _simulate_v2_step(ctx, profile, assumed)


register_step("simulation", simulate)
