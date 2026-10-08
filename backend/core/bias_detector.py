"""Phase 5A — real bias detection, replacing ``stub_steps._bias_detection``.

Runs the bias classifier behind the ``register_step`` seam, so the
orchestrator, SSE protocol and API contract are untouched. Which classifier is
set by ``BIAS_MODEL_VERSION``:

* **v4** (default, Phase A2) — ``src/bias_model_v4.py``. Sees the action
  (sell / hold / buy more) and the portfolio, was trained on real NIFTY and
  India VIX history, and reports calibrated confidence. "What weighed most"
  is computed for the pattern it actually chose. Evaluation:
  ``results/reports/BIAS_MODEL_V4.md``.
* **v3** — ``src/bias_detector.py``'s XGBoost v3, kept for comparison and as
  a rollback. It scores the situation only and never sees the action.

Two things this step does beyond calling the model:

**It assembles the inputs from three places.** ``decisions`` holds the
decision and its market snapshot, ``users`` the investor, and the decision's
``portfolio_context`` the portfolio at submission. The profile is read inside
the same RLS transaction that guards everything else.

**It records what it had to assume.** Profile fields are nullable: a user can
analyse a decision before finishing onboarding. Rather than fail, the step falls
back to documented defaults and lists every substitution — profile gaps in
``explainer_output.bias.assumed_defaults``, portfolio gaps in ``fixed_inputs``.
A confidence figure derived partly from assumed inputs is not the same claim as
one derived from real ones, and Objective 3 is answerable only if the
difference is visible.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from .ml_bridge import (
    MLUnavailableError,
    crowd_ratio_from_vix,
    ensure_src_importable,
    map_bias_label,
    map_financial_strategy,
    map_goal,
    market_return_from_row,
    market_volatility_from_row,
    run_blocking,
)
from ..config import get_settings
from .steps import PipelineContext, StepResult, register_step

# Cohort fallbacks for an incomplete profile. These mirror the defaults already
# declared by ``src.bias_detector.detect_bias_realtime`` so a bridged call and a
# direct research call agree; they are not tuned.
_PROFILE_DEFAULTS: dict[str, Any] = {
    "age": 35,
    "risk_tolerance": 0.5,
    "investment_horizon": 10,
    "monthly_income": 60_000.0,
    "monthly_expense": 45_000.0,
    "has_emergency_fund": 1,
    "financial_strategy": "conservative",  # maps to the model's "saving" default
    "goal": "wealth growth",
}

# Inputs the classifier takes that the app does not collect yet. They are held
# at the values ``detect_bias_realtime`` itself defaults to, and disclosed.
_FIXED_MODEL_INPUTS: dict[str, Any] = {
    "position_size_pct": 0.10,
    "years_investing": 5,
    "investment_experience": "intermediate",
}

_PROFILE_SQL = """
    SELECT age, risk_tolerance, investment_horizon, monthly_income,
           monthly_expense, has_emergency_fund, financial_strategy, goal
    FROM users
    WHERE user_id = $1
"""


def _f(value: Any, default: float = 0.0) -> float:
    """Decimal/None-tolerant float coercion (asyncpg returns Decimal for NUMERIC)."""
    if value is None:
        return default
    return float(value)


def _q(value: float, places: str = "0.0001") -> Decimal:
    """Round to a NUMERIC-safe Decimal (matches the column scales in 0003)."""
    return Decimal(str(value)).quantize(Decimal(places))


def _resolve_profile(row: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Merge the user's profile over the cohort defaults.

    Returns the resolved values and the names of the fields that had to be
    defaulted, so the caller can disclose them.
    """
    resolved: dict[str, Any] = {}
    assumed: list[str] = []
    for field, fallback in _PROFILE_DEFAULTS.items():
        value = row.get(field) if row else None
        if value is None:
            resolved[field] = fallback
            assumed.append(field)
        elif isinstance(value, bool):
            resolved[field] = int(value)
        elif isinstance(value, Decimal):
            resolved[field] = float(value)
        else:
            resolved[field] = value
    return resolved, assumed


def _predict(features: dict[str, Any]) -> dict[str, Any]:
    """Call the research classifier. Synchronous and CPU-bound — thread only."""
    ensure_src_importable()
    try:
        from src.bias_detector import detect_bias_realtime
    except ImportError as exc:  # ML extras absent
        raise MLUnavailableError(
            "bias detection needs the Phase 5 ML extras: "
            "pip install -r backend/requirements-ml.txt"
        ) from exc
    try:
        return detect_bias_realtime(**features)
    except FileNotFoundError as exc:  # model artefact missing
        raise MLUnavailableError(
            f"bias model artefact not found: {exc}. "
            "models/bias_detector_xgboost_v3.pkl must be present."
        ) from exc


async def load_investor_profile(ctx: PipelineContext) -> tuple[dict[str, Any], list[str]]:
    """The decision owner's profile, merged over cohort defaults.

    Shared by every step that models the investor (5A bias, 5B simulation), so
    they all see the same person — including the same defaults for gaps.
    """
    async with ctx.db.rls_transaction(ctx.user_id) as conn:
        row = await conn.fetchrow(_PROFILE_SQL, ctx.user_id)
    return _resolve_profile(row)


# --------------------------------------------------------------------------- #
# v3 — situation-only (rollback / comparison)
# --------------------------------------------------------------------------- #

async def _detect_v3(d: Mapping[str, Any], profile: dict[str, Any], assumed: list[str]) -> StepResult:
    market_captured = d.get("market_data_source") in ("live", "cache")

    # Portfolio-aware inputs (migration 0009). With a portfolio snapshot the
    # model gets the real position size and §10's cash flow: income includes
    # rent received, and expenses are the committed outflow (EMIs + rent paid
    # + education). Without one, the profile values and fixed size are used.
    context = d.get("portfolio_context") or {}
    fixed = dict(_FIXED_MODEL_INPUTS)
    if context.get("position_share"):
        fixed["position_size_pct"] = round(min(max(float(context["position_share"]), 0.01), 1.0), 4)
    income = float(profile["monthly_income"])
    if context.get("monthly_income") is not None:
        income = float(context["monthly_income"]) + float(context.get("rent_received") or 0.0)
    expense = float(profile["monthly_expense"])
    if context.get("committed_outflow") is not None:
        expense = float(context["committed_outflow"])

    features = {
        # Decision-side signals, straight off the row (market: migration 0008).
        "unrealized_gl": _f(d["unrealized_pnl_pct"]),
        "market_return": market_return_from_row(d),
        "market_volatility": market_volatility_from_row(d),
        "crowd_ratio": crowd_ratio_from_vix(d.get("vix_value")),
        "holding_period_months": max(1, int(_f(d.get("holding_period_days"), 180) // 30)),
        # Investor-side signals, from the profile, mapped into model vocabulary.
        "age": int(profile["age"]),
        "risk_tolerance": float(profile["risk_tolerance"]),
        "investment_horizon": int(profile["investment_horizon"]),
        "monthly_income": income,
        "monthly_expense": expense,
        "has_emergency_fund": int(profile["has_emergency_fund"]),
        "financial_strategy": map_financial_strategy(profile["financial_strategy"]),
        "goal": map_goal(profile["goal"]),
        **fixed,
    }

    result = await run_blocking(_predict, features)

    bias = map_bias_label(result["bias_type"])
    confidence = float(result["confidence"])

    # SHAP belongs to Objective 3, but it is produced here — the classifier
    # computes it in the same pass. Park it under its own key so Phase 5C can
    # merge the causal narrative alongside rather than overwrite it.
    explainer_output = {
        "bias": {
            "model": "xgboost_v3",
            "bias_type": bias,
            "confidence": round(confidence, 4),
            "probabilities": result.get("probabilities"),
            "is_biased": result.get("is_biased"),
            "narrative": result.get("explanation"),
            "shap": result.get("shap_explanation"),
            "inference_ms": result.get("inference_ms"),
            "assumed_defaults": assumed,
            "market_context": "captured" if market_captured else "unavailable",
            "fixed_inputs": sorted(
                k for k in _FIXED_MODEL_INPUTS if not (k == "position_size_pct" and context.get("position_share"))
            ),
            "portfolio_aware": bool(context),
            "model_inputs": {
                k: (round(v, 6) if isinstance(v, float) else v) for k, v in features.items()
            },
        }
    }

    return StepResult(
        updates={
            "bias_detected": bias,
            "bias_confidence": _q(min(max(confidence, 0.0), 1.0)),
            "explainer_output": explainer_output,
        },
        event={
            "bias": bias,
            "confidence": round(confidence, 4),
            "assumed_defaults": assumed,
        },
    )


# --------------------------------------------------------------------------- #
# v4 — action- and portfolio-aware, calibrated (Phase A2)
# --------------------------------------------------------------------------- #

#: Profile field (``_PROFILE_DEFAULTS`` key) -> v4 input it feeds. When a field
#: was defaulted, v4 gets its own training median instead of the v3 cohort
#: value: v3's 45,000 expenses on 60,000 income is a 25% surplus, below
#: anything v4 was trained on.
_V4_FROM_PROFILE = {
    "age": "age",
    "risk_tolerance": "risk_tolerance",
    "investment_horizon": "investment_horizon",
    "monthly_income": "monthly_income",
    "monthly_expense": "monthly_outflow",
    "has_emergency_fund": "has_emergency_fund",
}


def _num(value: Any) -> float | None:
    return None if value is None else float(value)


def build_v4_inputs(
    d: Mapping[str, Any],
    profile: Mapping[str, Any],
    assumed: list[str],
    medians: Mapping[str, float],
    market: Mapping[str, float],
) -> tuple[dict[str, Any], list[str]]:
    """The v4 model's raw inputs for one decision, plus what had to be filled in.

    Pure — no I/O — so it is unit-tested without the model. ``medians`` are the
    training medians and ``market`` the median real trading day
    (``src.bias_model_v4.input_medians`` / ``market_medians``). Returns the
    inputs and the portfolio inputs that used standard values (``fixed``);
    profile gaps are already listed in ``assumed``.
    """
    context = d.get("portfolio_context") or {}
    fixed: list[str] = []

    def from_context(key: str, fallback: float, label: str) -> float:
        value = _num(context.get(key))
        if value is None:
            if label not in fixed:
                fixed.append(label)
            return float(fallback)
        return value

    # Market: the values stored at submission; else the median real day. A
    # missing 30-day volatility is implied from VIX (annualised % -> daily).
    vix = _num(d.get("vix_value"))
    r1m = _num(d.get("nifty_1m_return"))
    vol = _num(d.get("nifty_volatility_30d"))
    if vol is None:
        vol = vix / 100.0 / (252 ** 0.5) if vix is not None else market["nifty_volatility_30d"]
    days = _num(d.get("holding_period_days"))

    inputs: dict[str, Any] = {
        "action": d["decision_intent"],
        "unrealized_gl": float(d["unrealized_pnl_pct"]),
        "holding_period_months": max(1, int(days // 30)) if days is not None else int(medians["holding_period_months"]),
        "nifty_1m_return": r1m if r1m is not None else market["nifty_1m_return"],
        "vix": vix if vix is not None else market["vix"],
        "nifty_volatility_30d": vol,
    }
    if days is None:
        fixed.append("holding_period")

    for field, key in _V4_FROM_PROFILE.items():
        inputs[key] = medians[key] if field in assumed else profile[field]
    inputs["age"] = int(inputs["age"])
    inputs["investment_horizon"] = int(inputs["investment_horizon"])
    inputs["has_emergency_fund"] = int(inputs["has_emergency_fund"])
    inputs["risk_tolerance"] = float(inputs["risk_tolerance"])
    inputs["monthly_income"] = float(inputs["monthly_income"])
    inputs["monthly_outflow"] = float(inputs["monthly_outflow"])
    inputs["rent_received"] = 0.0

    # The portfolio snapshot (migration 0009) supersedes the profile for cash
    # flow: §10's surplus is income + rent received - EMIs - rent - education.
    if context.get("monthly_income") is not None:
        inputs["monthly_income"] = float(context["monthly_income"])
    if context:
        inputs["rent_received"] = float(context.get("rent_received") or 0.0)
    if context.get("committed_outflow") is not None:
        inputs["monthly_outflow"] = float(context["committed_outflow"])

    inputs["position_share"] = min(max(from_context("position_share", medians["position_share"], "position_share"), 0.0), 1.0)
    inputs["equity_share"] = from_context("equity_share", medians["equity_share"], "asset_mix")
    inputs["gold_share"] = from_context("gold_share", medians["gold_share"], "asset_mix")
    inputs["liquid_assets"] = from_context("liquid", medians["liquid_assets"], "liquid_assets")
    inputs["real_estate_value"] = from_context("real_estate", 0.0, "property_loans")
    inputs["loans_outstanding"] = from_context("liabilities", 0.0, "property_loans")
    # v4.1: did the investor say they need the money? Read from their comment
    # (Phase B3) and stored on the decision; absent means not stated.
    inputs["cash_need_stated"] = int(bool((d.get("comment_facts") or {}).get("cash_need")))
    return inputs, fixed


def _v4_module():
    ensure_src_importable()
    try:
        from src import bias_model_v4
    except ImportError as exc:  # ML extras absent
        raise MLUnavailableError(
            "bias detection needs the Phase 5 ML extras: "
            "pip install -r backend/requirements-ml.txt"
        ) from exc
    return bias_model_v4


def _predict_v4(inputs: dict[str, Any]) -> dict[str, Any]:
    """Call bias model v4. Synchronous and CPU-bound — thread only."""
    try:
        return _v4_module().predict(inputs)
    except FileNotFoundError as exc:
        raise MLUnavailableError(
            f"bias model artefact not found: {exc}. "
            "models/bias_detector_v4.json and .meta.json must be present."
        ) from exc


def _v4_fill_values() -> tuple[dict[str, float], dict[str, float]]:
    module = _v4_module()
    try:
        return module.input_medians(), module.market_medians()
    except FileNotFoundError as exc:
        raise MLUnavailableError(f"bias model metadata not found: {exc}") from exc


async def _detect_v4(d: Mapping[str, Any], profile: dict[str, Any], assumed: list[str]) -> StepResult:
    medians, market = _v4_fill_values()
    inputs, fixed = build_v4_inputs(d, profile, assumed, medians, market)
    result = await run_blocking(_predict_v4, inputs)

    bias = map_bias_label(result["bias_type"])
    confidence = float(result["confidence"])

    explainer_output = {
        "bias": {
            "model": "bias_v4",
            "bias_type": bias,
            "confidence": round(confidence, 4),
            "probabilities": result["probabilities"],
            "model_probabilities": result["model_probabilities"],
            "allowed": result["allowed"],
            "guard_applied": result["guard_applied"],
            "is_biased": result["is_biased"],
            "drivers": result["drivers"],
            "inference_ms": result["inference_ms"],
            "assumed_defaults": assumed,
            "market_context": "captured" if d.get("market_data_source") in ("live", "cache") else "unavailable",
            "fixed_inputs": fixed,
            "portfolio_aware": bool(d.get("portfolio_context")),
            "model_inputs": {
                k: (round(v, 6) if isinstance(v, float) else v) for k, v in inputs.items()
            },
        }
    }
    return StepResult(
        updates={
            "bias_detected": bias,
            "bias_confidence": _q(min(max(confidence, 0.0), 1.0)),
            "explainer_output": explainer_output,
        },
        event={"bias": bias, "confidence": round(confidence, 4), "assumed_defaults": assumed},
    )


async def _comment_facts(ctx: PipelineContext) -> dict[str, Any] | None:
    """Phase B3: read "Why? In your own words" once, before the model runs.

    A stated need for the money becomes the model's ``cash_need_stated``
    input; feelings are kept for display only. Stored on the decision, so a
    re-run reads the comment exactly as it was read the first time.
    """
    d = ctx.decision
    if d.get("comment_facts") is not None:
        return d["comment_facts"]
    if not (d.get("user_reasoning") or "").strip():
        return None
    from .ai_help import allowed_for
    from .comment_reader import read_comment

    async with ctx.db.rls_transaction(ctx.user_id) as conn:
        consent = await conn.fetchval("SELECT ai_consent FROM users WHERE user_id = $1", ctx.user_id)
    return await run_blocking(read_comment, d["user_reasoning"], allowed_for(consent))


async def detect_bias(ctx: PipelineContext) -> StepResult:
    profile, assumed = await load_investor_profile(ctx)
    facts = await _comment_facts(ctx)
    decision = {**ctx.decision, "comment_facts": facts}
    if get_settings().BIAS_MODEL_VERSION.strip().lower() == "v3":
        result = await _detect_v3(decision, profile, assumed)
    else:
        result = await _detect_v4(decision, profile, assumed)
    if facts is not None and ctx.decision.get("comment_facts") is None:
        result.updates["comment_facts"] = facts
    return result


register_step("bias_detection", detect_bias)
