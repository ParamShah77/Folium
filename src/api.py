"""
GAP 1 + GAP 2 + GAP 3 – FastAPI Backend
========================================
Exposes the unified bias-detection + causal-intervention pipeline
as a REST API.  Includes user management, market data, SHAP
explanations, tamper-evident audit trails, and the Monte Carlo
long-horizon wealth simulator (GAP 2).

Endpoints
---------
  GET  /health                      → liveness probe
  GET  /model/status                → inspect loaded model artefacts
  POST /analyze/decision            → single-user real-time analysis (updated)
  POST /analyze/batch               → analyse a JSON list of decisions
  GET  /causal/effects              → pre-computed causal effect table
  GET  /causal/interventions        → pre-computed intervention simulation
  GET  /demo                        → run 4 canned scenarios, return JSON
  GET  /demo/all_biases             → highest-confidence real specimens
  POST /user/register               → register new user + onboarding
  GET  /user/{user_id}/profile      → full profile + bias history
  GET  /user/{user_id}/decisions    → decision history
  GET  /audit/{decision_id}         → audit trail + tamper detection
  GET  /market/context              → live NIFTY market data
  GET  /market/ribbon               → live indices ribbon data
  POST /simulate                    → GAP 2: HOLD vs SELL Monte Carlo
  POST /simulate/individual         → GAP 2: single-scenario simulation
  GET  /simulate/validate/{id}      → GAP 2: validate vs ground-truth
  GET  /simulate/bias_impact        → GAP 2: population-level bias cost
  POST /explain                     → GAP 3: plain-language explanation (EN/HI)
  POST /explain/report              → GAP 3: downloadable report (md/html/pdf)
  GET  /explain/status              → GAP 3: languages, formats, LLM flag

Install & Run
-------------
  pip install fastapi uvicorn[standard]
  uvicorn src.api:app --reload --port 8000
  # or from project root:
  python src/api.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
import warnings
warnings.filterwarnings("ignore")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ─── FastAPI ──────────────────────────────────────────────────────────────
try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, HTTPException, Body, Path
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    from typing import Annotated, Optional
except ImportError as exc:
    raise SystemExit(
        "FastAPI not installed. Run: pip install fastapi uvicorn[standard]"
    ) from exc

# ─── Internal pipeline ────────────────────────────────────────────────────
from integration import analyze_decision_realtime, analyze_batch
from causal_inference import load_causal_results, EFFECTS_PKL
from database import DatabaseManager, get_db
from market_data import MarketDataFetcher, get_fetcher
from simulator import get_simulator, LongHorizonSimulator

import numpy as np
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════
# LIFESPAN — initialise singletons at startup
# ══════════════════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB, market fetcher, and simulator once at startup."""
    app.state.db        = get_db()
    app.state.fetcher   = get_fetcher()
    app.state.simulator = get_simulator()   # GAP 2: lazy-loads datasets on first call
    yield
    app.state.db.close()


# ══════════════════════════════════════════════════════════════════════════
# APP SETUP
# ══════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="Behavioral Bias Detection API",
    description=(
        "Real-time bias detection (XGBoost, 89% accuracy) combined with "
        "causal intervention recommendations (DoWhy PSM causal engine). "
        "Part of the Major Project: Causal AI for Investment Decision Making."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Convenience accessors ────────────────────────────────────────────────
def _db() -> DatabaseManager:
    try:
        return app.state.db
    except AttributeError:
        return get_db()

def _fetcher() -> MarketDataFetcher:
    try:
        return app.state.fetcher
    except AttributeError:
        return get_fetcher()

def _sim() -> LongHorizonSimulator:
    try:
        return app.state.simulator
    except AttributeError:
        return get_simulator()

# ══════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════

class DecisionInput(BaseModel):
    """User decision event payload."""
    # Optional user linking
    user_id               : Optional[str] = Field(None, description="Registered user ID (optional)")
    # Market context — auto-fetched if omitted
    market_return         : Optional[float] = Field(None, description="Recent market return (fraction, e.g. -0.12)")
    unrealized_gl         : float = Field( 0.00,   description="Unrealised gain/loss fraction (e.g. -0.18 = -18%)")
    crowd_ratio           : Optional[float] = Field(None, description="Fraction of crowd currently selling [0, 1]")
    age                   : int   = Field( 35,     description="Investor age (years)")
    risk_tolerance        : float = Field( 0.5,    description="Risk tolerance score [0–1]")
    investment_horizon    : int   = Field( 10,     description="Investment horizon (years)")
    monthly_income        : float = Field(60_000.0, description="Monthly income (₹)")
    monthly_expense       : float = Field(45_000.0, description="Monthly expense (₹)")
    financial_strategy    : str   = Field("saving", description="Financial strategy: saving / investing / credit_card / family_support")
    market_volatility     : Optional[float] = Field(None, description="Current market volatility (auto-fetched if omitted)")
    position_size_pct     : float = Field(0.10,   description="Position size as % of portfolio [0, 1]")
    holding_period_months : int   = Field(6,       description="How long investor has held the position (months)")
    crash_speed           : str   = Field("normal", description="Market crash speed: normal / gradual_bear / rapid_decline")
    has_emergency_fund    : int   = Field(1,        description="1 = has emergency fund, 0 = does not")
    years_investing       : int   = Field(5,        description="Years of investing experience")
    investment_experience : str   = Field("expert", description="Experience level: expert / intermediate / novice")
    secondary_biases      : str   = Field("none",  description="Secondary bias: none / loss_aversion / overconfidence")
    age_horizon_mismatch  : str   = Field("none",  description="Age-horizon mismatch type: none / old_long")
    goal                  : str   = Field("wealth growth", description="Primary investment goal")
    loss_aversion         : float = Field(1.5,     description="Measured loss-aversion coefficient")
    herd_sensitivity      : float = Field(0.5,     description="Herd-sensitivity score [0, 1]")
    disposition_strength  : float = Field(0.3,     description="Disposition-effect score [0, 1]")
    portfolio_value       : float = Field(100_000.0, description="Portfolio value (₹)")
    recent_trades         : int   = Field(2,        description="Number of trades in the last 30 days")


class BatchInput(BaseModel):
    decisions: list[DecisionInput] = Field(..., description="List of decision events to analyse in bulk")


class UserRegistrationInput(BaseModel):
    """New user profile for registration."""
    name               : str   = Field(...,       description="Full name")
    age                : int   = Field(...,       description="Age in years", ge=18, le=100)
    monthly_income     : float = Field(...,       description="Monthly income (₹)", gt=0)
    risk_tolerance     : float = Field(0.5,       description="Risk tolerance score [0–1]", ge=0, le=1)
    investment_horizon : int   = Field(10,        description="Investment horizon (years)", ge=1, le=50)
    has_emergency_fund : int   = Field(1,         description="1 = yes, 0 = no")
    # Onboarding answers (optional — filled during onboarding flow)
    answers            : Optional[dict] = Field(None, description="5-question onboarding answers (optional)")


class UserRegistrationResponse(BaseModel):
    user_id             : str
    initial_bias_profile: dict
    onboarding_questions: list[dict]
    message             : str


# ══════════════════════════════════════════════════════════════════════════
# SWAGGER EXAMPLES  (pre-filled payloads for Try-it-out in /docs)
# ══════════════════════════════════════════════════════════════════════════
SWAGGER_EXAMPLES = {
    "loss_aversion": {
        "summary": "🔴 Loss Aversion — Real specimen (Age 56, 96.7% confidence)",
        "value": {
            "market_return": -0.1068, "unrealized_gl": -0.4143, "crowd_ratio": 0.2943,
            "age": 56, "risk_tolerance": 0.477, "investment_horizon": 19,
            "monthly_income": 126000, "monthly_expense": 75963,
            "financial_strategy": "saving",
            "market_volatility": 0.0298, "position_size_pct": 0.094,
            "holding_period_months": 33, "has_emergency_fund": 1,
            "years_investing": 15, "crash_speed": "rapid_decline",
            "secondary_biases": "none", "investment_experience": "expert",
            "age_horizon_mismatch": "normal", "goal": "retirement",
        },
    },
    "herd": {
        "summary": "🟠 Herd Mentality — Real specimen (Age 57, 90.6% confidence)",
        "value": {
            "market_return": -0.0039, "unrealized_gl": -0.1593, "crowd_ratio": 0.8143,
            "age": 57, "risk_tolerance": 0.458, "investment_horizon": 24,
            "monthly_income": 135000, "monthly_expense": 77205,
            "financial_strategy": "saving",
            "market_volatility": 0.0197, "position_size_pct": 0.326,
            "holding_period_months": 15, "has_emergency_fund": 1,
            "years_investing": 18, "crash_speed": "normal",
            "secondary_biases": "loss_aversion", "investment_experience": "expert",
            "age_horizon_mismatch": "old_long", "goal": "retirement",
        },
    },
    "disposition": {
        "summary": "🟣 Disposition Effect — Real specimen (Age 63, 99.7% confidence)",
        "value": {
            "market_return": 0.0803, "unrealized_gl": 0.2050, "crowd_ratio": 0.3354,
            "age": 63, "risk_tolerance": 0.363, "investment_horizon": 29,
            "monthly_income": 166000, "monthly_expense": 134979,
            "financial_strategy": "saving",
            "market_volatility": 0.0234, "position_size_pct": 0.135,
            "holding_period_months": 47, "has_emergency_fund": 1,
            "years_investing": 25, "crash_speed": "normal",
            "secondary_biases": "overconfidence", "investment_experience": "expert",
            "age_horizon_mismatch": "old_long", "goal": "retirement",
        },
    },
    "rational": {
        "summary": "🟢 Rational Investor — Real specimen (Age 48, 100% confidence)",
        "value": {
            "market_return": -0.0427, "unrealized_gl": -0.0054, "crowd_ratio": 0.5163,
            "age": 48, "risk_tolerance": 0.324, "investment_horizon": 12,
            "monthly_income": 72000, "monthly_expense": 84051,
            "financial_strategy": "family_support",
            "market_volatility": 0.0322, "position_size_pct": 0.041,
            "holding_period_months": 40, "has_emergency_fund": 0,
            "years_investing": 12, "crash_speed": "normal",
            "secondary_biases": "none", "investment_experience": "expert",
            "age_horizon_mismatch": "normal", "goal": "wealth growth",
        },
    },
}

# ══════════════════════════════════════════════════════════════════════════
# ONBOARDING QUESTIONS
# ══════════════════════════════════════════════════════════════════════════
ONBOARDING_QUESTIONS = [
    {
        "id": "q1",
        "question": "How do you typically react when your portfolio drops 20% in a week?",
        "options": ["Sell everything immediately", "Sell some positions", "Hold and wait", "Buy more"],
    },
    {
        "id": "q2",
        "question": "If 80% of your colleagues are selling a stock, what do you do?",
        "options": ["Follow and sell", "Research independently", "Buy if fundamentals are good", "Ignore and hold"],
    },
    {
        "id": "q3",
        "question": "You have a 30% gain on a stock. What do you do?",
        "options": ["Sell immediately to lock in profits", "Sell half", "Hold based on fundamentals", "Set a trailing stop"],
    },
    {
        "id": "q4",
        "question": "How long can you stay invested without checking your portfolio?",
        "options": ["Less than a week", "1–4 weeks", "1–6 months", "More than 6 months"],
    },
    {
        "id": "q5",
        "question": "When markets crash, what is your primary concern?",
        "options": ["Avoiding more losses", "Missing the recovery", "Whether my thesis changed", "Tax loss harvesting"],
    },
]


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _augment_with_market(payload: dict) -> dict:
    """
    If market_return / market_volatility / crowd_ratio are missing from payload,
    auto-fetch from MarketDataFetcher.
    """
    ctx = _fetcher().get_market_context()
    if payload.get("market_return") is None:
        payload["market_return"] = ctx["market_return"]
    if payload.get("market_volatility") is None:
        payload["market_volatility"] = ctx["market_volatility"]
    if payload.get("crowd_ratio") is None:
        payload["crowd_ratio"] = ctx["crowd_ratio"]
    return payload


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — existing (preserved + upgraded)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/health", summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "timestamp_ms": int(time.time() * 1000)}


@app.get("/model/status", summary="Inspect loaded model artefacts")
def model_status() -> dict:
    from bias_detector import _model_cache, _feature_cache
    bias_loaded   = _model_cache is not None
    causal_exists = os.path.exists(EFFECTS_PKL)
    return {
        "bias_model_loaded"    : bias_loaded,
        "causal_effects_ready" : causal_exists,
        "causal_effects_path"  : EFFECTS_PKL,
        "status"               : "ready" if (bias_loaded and causal_exists) else "partial",
    }


@app.post("/analyze/decision", summary="Analyse a single user decision event (with SHAP + audit)")
def analyze_decision(
    payload: Annotated[
        DecisionInput,
        Body(openapi_examples=SWAGGER_EXAMPLES),
    ]
) -> dict:
    """
    Full real-time pipeline:
    1. Auto-fetch market data if not provided
    2. Detect behavioural bias (XGBoost)
    3. SHAP per-prediction explanations (top 5 features)
    4. Causal drivers from the pre-computed causal graph
    5. Log decision + append audit entry to DB
    6. Return actionable intervention recommendation
    """
    try:
        data = payload.model_dump()

        # Fetch missing market context
        data = _augment_with_market(data)

        # Run analysis
        result = analyze_decision_realtime(data)
        result.pop("causal_effects", None)

        # ── User profile integration ────────────────────────────────────
        uid = data.get("user_id")
        if uid:
            user = _db().get_user(uid)
            if user is None:
                uid = None   # unknown user — proceed without DB
            else:
                _db().update_bias_profile(uid, result["bias_type"])

        # ── Log decision to DB ──────────────────────────────────────────
        raw_input_str  = json.dumps(data, default=str)
        raw_output_str = json.dumps(result, default=str)
        input_hash     = _sha256(raw_input_str)
        output_hash    = _sha256(raw_output_str)
        expl_hash      = _sha256(result.get("explanation", ""))

        decision_id = _db().log_decision({
            "user_id"       : uid,
            "bias_detected" : result["bias_type"],
            "confidence"    : result["confidence"],
            "recommendation": result.get("intervention", ""),
            "risk_score"    : result.get("risk_score", 0.0),
            "raw_input"     : data,
            "raw_output"    : result,
        })

        # ── Append audit log ────────────────────────────────────────────
        log_id = _db().append_audit_log({
            "decision_id"     : decision_id,
            "input_hash"      : input_hash,
            "output_hash"     : output_hash,
            "explanation_hash": expl_hash,
        })
        full_hash = _sha256(input_hash + output_hash + expl_hash)

        result["decision_id"]  = decision_id
        result["audit_log_id"] = log_id
        result["audit_hash"]   = full_hash
        result["market_auto_fetched"] = {
            "market_return"    : data["market_return"],
            "market_volatility": data["market_volatility"],
            "crowd_ratio"      : data["crowd_ratio"],
        }

        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/analyze/batch", summary="Analyse a list of decision events")
def analyze_batch_endpoint(payload: BatchInput) -> dict:
    """
    Runs the full pipeline over a list of decisions.
    Returns original fields + pred_bias_type, pred_confidence, pred_risk_score, intervention.
    """
    try:
        records = [_augment_with_market(d.model_dump()) for d in payload.decisions]
        df      = pd.DataFrame(records)
        df_out  = analyze_batch(df)
        return {"count": len(df_out), "results": df_out.to_dict(orient="records")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/causal/effects", summary="Retrieve pre-computed causal effect table")
def causal_effects() -> dict:
    """Returns the causal effects estimated during the offline training run."""
    if not os.path.exists(EFFECTS_PKL):
        raise HTTPException(
            status_code=503,
            detail="Causal effects not computed yet. Run: python src/causal_inference.py",
        )
    data = load_causal_results()
    return {"causal_effects": data["causal_effects"]}


@app.get("/causal/interventions", summary="Retrieve intervention simulation results")
def causal_interventions() -> dict:
    """Returns the intervention simulation computed during the offline training run."""
    if not os.path.exists(EFFECTS_PKL):
        raise HTTPException(
            status_code=503,
            detail="Causal results not available. Run: python src/causal_inference.py",
        )
    data = load_causal_results()
    return {"interventions": data["interventions"]}


@app.get("/demo", summary="Run 4 canned scenarios (one per bias class)")
def demo() -> dict:
    """Returns one prediction for each of the 4 bias classes using real dataset specimens."""
    scenarios = [
        {
            "name": "Loss Aversion — Real specimen (Age 56)",
            "bias_expected": "loss_aversion",
            "input": DecisionInput(
                market_return=-0.1068, unrealized_gl=-0.4143, crowd_ratio=0.2943,
                age=56, risk_tolerance=0.477, investment_horizon=19,
                monthly_income=126000, monthly_expense=75963,
                financial_strategy="saving", market_volatility=0.0298,
                position_size_pct=0.094, holding_period_months=33,
                has_emergency_fund=1, years_investing=15,
                crash_speed="rapid_decline", secondary_biases="none",
                investment_experience="expert", age_horizon_mismatch="normal",
                goal="retirement",
            ),
        },
        {
            "name": "Herd Mentality — Real specimen (Age 57)",
            "bias_expected": "herd",
            "input": DecisionInput(
                market_return=-0.0039, unrealized_gl=-0.1593, crowd_ratio=0.8143,
                age=57, risk_tolerance=0.458, investment_horizon=24,
                monthly_income=135000, monthly_expense=77205,
                financial_strategy="saving", market_volatility=0.0197,
                position_size_pct=0.326, holding_period_months=15,
                has_emergency_fund=1, years_investing=18,
                crash_speed="normal", secondary_biases="loss_aversion",
                investment_experience="expert", age_horizon_mismatch="old_long",
                goal="retirement",
            ),
        },
        {
            "name": "Disposition Effect — Real specimen (Age 63)",
            "bias_expected": "disposition",
            "input": DecisionInput(
                market_return=0.0803, unrealized_gl=0.2050, crowd_ratio=0.3354,
                age=63, risk_tolerance=0.363, investment_horizon=29,
                monthly_income=166000, monthly_expense=134979,
                financial_strategy="saving", market_volatility=0.0234,
                position_size_pct=0.135, holding_period_months=47,
                has_emergency_fund=1, years_investing=25,
                crash_speed="normal", secondary_biases="overconfidence",
                investment_experience="expert", age_horizon_mismatch="old_long",
                goal="retirement",
            ),
        },
        {
            "name": "Rational Investor — Real specimen (Age 48)",
            "bias_expected": "rational",
            "input": DecisionInput(
                market_return=-0.0427, unrealized_gl=-0.0054, crowd_ratio=0.5163,
                age=48, risk_tolerance=0.324, investment_horizon=12,
                monthly_income=72000, monthly_expense=84051,
                financial_strategy="family_support", market_volatility=0.0322,
                position_size_pct=0.041, holding_period_months=40,
                has_emergency_fund=0, years_investing=12,
                crash_speed="normal", secondary_biases="none",
                investment_experience="expert", age_horizon_mismatch="normal",
                goal="wealth growth",
            ),
        },
    ]

    results = []
    for s in scenarios:
        data = _augment_with_market(s["input"].model_dump())
        r = analyze_decision_realtime(data)
        r.pop("causal_effects", None)
        results.append({
            "scenario"       : s["name"],
            "bias_expected"  : s["bias_expected"],
            "bias_detected"  : r["bias_type"],
            "correct"        : r["bias_type"] == s["bias_expected"],
            **r,
        })
    return {
        "title"       : "4-Bias Demo — All Classes",
        "model"       : "XGBoost (89% accuracy)",
        "demo_results": results,
    }


@app.get("/demo/all_biases",
         summary="Guarantee all 4 bias classes detected — uses real dataset specimens")
def demo_all_biases() -> dict:
    """
    Loads the real investor dataset, finds the highest-confidence correctly-predicted
    specimen for each of the 4 bias classes, and returns the model's output.
    """
    from bias_detector import load_data, load_model, BIAS_LABELS
    import numpy as np

    model, _  = load_model()
    X_train, X_test, y_train, y_test = load_data()
    X_all     = pd.concat([X_train, X_test], ignore_index=True)
    y_all     = np.concatenate([y_train, y_test])
    proba_all = model.predict_proba(X_all)
    preds_all = model.predict(X_all)

    data_dir   = os.path.join(_ROOT, "data", "processed")
    train_idx  = np.load(os.path.join(data_dir, "train_indices.npy"))
    test_idx   = np.load(os.path.join(data_dir, "test_indices.npy"))
    all_df_idx = np.concatenate([train_idx, test_idx])
    df_feat    = pd.read_csv(os.path.join(data_dir, "merged_features.csv"))

    _RISK_W = {"loss_aversion": 0.30, "herd": 0.25, "disposition": 0.25, "rational": 0.00}
    _ICONS  = {"loss_aversion": "🔴 Loss Aversion",
               "herd": "🟠 Herd Mentality",
               "disposition": "🟣 Disposition Effect",
               "rational": "🟢 Rational Investor"}

    specimens = {}
    for cls_id, cls_name in BIAS_LABELS.items():
        correct = (preds_all == cls_id) & (y_all == cls_id)
        idxs    = np.where(correct)[0]
        if len(idxs) == 0:
            idxs = np.where(preds_all == cls_id)[0]
        if len(idxs) == 0:
            continue
        best   = idxs[int(np.argmax(proba_all[idxs, cls_id]))]
        orig   = df_feat.iloc[all_df_idx[best]]
        proba  = proba_all[best]
        conf   = float(proba[cls_id])
        aprobs = {BIAS_LABELS[i]: round(float(p), 4) for i, p in enumerate(proba)}
        risk   = round(min(sum(_RISK_W.get(k, 0.2) * v for k, v in aprobs.items()), 1.0), 4)

        try:
            from causal_inference import get_intervention_recommendation, load_causal_results
            interv = get_intervention_recommendation(cls_name, load_causal_results())
        except Exception:
            interv = f"Reduce {cls_name.replace('_', ' ')} tendencies"

        specimens[cls_name] = {
            "label"              : _ICONS.get(cls_name, cls_name),
            "bias_type"          : cls_name,
            "confidence"         : round(conf, 4),
            "risk_score"         : risk,
            "all_probabilities"  : aprobs,
            "intervention"       : interv,
            "ground_truth_correct": bool(y_all[best] == cls_id),
            "investor_context": {
                "market_return" : round(float(orig.get("market_return_recent", 0)), 4),
                "unrealized_gl" : round(float(orig.get("unrealized_gain_loss", 0)), 4),
                "crowd_ratio"   : round(float(orig.get("crowd_action_ratio", 0)), 4),
                "age"           : int(orig.get("age", 0)),
                "risk_tolerance": round(float(orig.get("risk_tolerance", 0)), 2),
            },
        }

    all_correct = all(v["ground_truth_correct"] for v in specimens.values())
    return {
        "title"        : "All 4 Bias Classes — Highest-Confidence Real Specimens",
        "model"        : "XGBoost multi-class classifier — 89% overall accuracy",
        "classes_found": len(specimens),
        "all_correct"  : all_correct,
        "specimens"    : specimens,
    }


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — new (user management + audit + market)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/user/register", summary="Register a new user + 5-question onboarding")
def register_user(payload: UserRegistrationInput) -> dict:
    """
    Register a new investor profile and return 5 onboarding questions
    that help characterise their behavioural tendencies.

    Steps:
    1. Persist profile in DB
    2. Compute initial (neutral) bias profile
    3. Return user_id + onboarding questions
    """
    try:
        user_data = payload.model_dump()
        user_id   = _db().register_user(user_data)
        profile   = _db().get_bias_profile(user_id)

        return {
            "user_id"             : user_id,
            "initial_bias_profile": profile,
            "onboarding_questions": ONBOARDING_QUESTIONS,
            "message"             : (
                f"Welcome {payload.name}! Please answer the 5 behavioural questions "
                "to calibrate your initial bias profile."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/user/{user_id}/profile", summary="Get full user profile + bias history")
def get_user_profile(user_id: str = Path(..., description="Registered user ID")) -> dict:
    """Returns the full user profile and live bias scores from the database."""
    profile = _db().get_user(user_id)
    if profile is None:
        if user_id.isdigit():
            try:
                sim = _sim()
                match = sim.users_df[sim.users_df["user_id"] == int(user_id)]
                if not match.empty:
                    row = match.iloc[0]
                    profile = {
                        "age": int(row.get("age", 35)),
                        "monthly_income": float(row.get("monthly_income", 50000)),
                        "risk_tolerance": float(row.get("risk_tolerance", 0.5)),
                        "investment_horizon": int(row.get("investment_horizon", 10)),
                        "has_emergency_fund": int(row.get("has_emergency_fund", 1)),
                        "name": f"User {user_id}",
                    }
            except Exception:
                pass
                
    if profile is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    bias_profile = _db().get_bias_profile(user_id)
    if bias_profile is None and user_id.isdigit():
        bias_profile = {
            "disposition_score": 0.0, "herd_score": 0.0,
            "loss_aversion_score": 0.0, "rational_score": 0.0,
            "total_decisions": 0
        }

    return {
        "user_id"          : user_id,
        "profile"          : profile,
        "bias_profile"     : bias_profile or {},
    }


@app.get("/user/{user_id}/decisions", summary="Get decision history for a user")
def get_user_decisions(user_id: str = Path(..., description="Registered user ID")) -> dict:
    """Returns the full decision history for a registered user, newest first."""
    profile = _db().get_user(user_id)
    if profile is None:
        if user_id.isdigit():
            try:
                sim = _sim()
                match = sim.users_df[sim.users_df["user_id"] == int(user_id)]
                if not match.empty:
                    profile = {"dummy": True}
            except Exception:
                pass
                
    if profile is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    decisions = _db().get_user_decision_history(user_id)
    return {"user_id": user_id, "decision_count": len(decisions), "decisions": decisions}


@app.get("/audit/{decision_id}", summary="Audit trail + tamper detection for a decision")
def get_audit(decision_id: str = Path(..., description="Decision ID to audit")) -> dict:
    """
    Returns the full audit trail for a decision.
    Recomputes the SHA-256 hash and flags any tampering.
    """
    trail = _db().get_audit_trail(decision_id)
    if trail is None:
        raise HTTPException(
            status_code=404,
            detail=f"No audit record found for decision '{decision_id}'",
        )
    return trail


@app.get("/market/context", summary="Live NIFTY50 market context")
def market_context() -> dict:
    """
    Fetches current NIFTY50 market data:
    - market_return:     1-month % return
    - market_volatility: 30-day rolling std of daily returns
    - crowd_ratio:       India VIX-derived fear proxy [0, 1]
    - last_updated:      ISO-8601 UTC timestamp
    - data_source:       'live' | 'cache' | 'default_fallback'
    """
    try:
        ctx = _fetcher().get_market_context()
        ctx["market_hours"] = _fetcher().is_market_hours()
        return ctx
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/market/ribbon", summary="Live prices + 1-day change for all 4 indices")
def market_ribbon() -> dict:
    """
    Returns current price and 1-day % change for:
      - NIFTY 50   (^NSEI)
      - SENSEX     (^BSESN)
      - Bank NIFTY (^NSEBANK)
      - India VIX  (^INDIAVIX)
    Used by the dashboard top-ribbon on every page.
    """
    try:
        return _fetcher().get_indices_ribbon()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# GAP 2 — PYDANTIC MODELS FOR SIMULATOR
# ══════════════════════════════════════════════════════════════════════════

class SimulateInput(BaseModel):
    """HOLD vs SELL Monte Carlo simulation request."""
    user_id          : int   = Field(42,        description="User ID from synthetic_users.csv")
    current_wealth   : float = Field(75_000.0,  description="Current portfolio value (₹)", gt=0)
    unrealized_gl    : float = Field(-0.18,     description="Unrealised gain/loss fraction (e.g. -0.18 = -18%)")
    n_simulations    : int   = Field(1_000,     description="Monte Carlo paths per scenario (100–5000)", ge=100, le=5000)


class SimulateIndividualInput(BaseModel):
    """Single-scenario (HOLD or SELL) individual simulation request."""
    user_id          : int   = Field(42,        description="User ID from synthetic_users.csv")
    decision         : str   = Field("hold",    description="'hold' or 'sell'")
    current_portfolio: float = Field(75_000.0,  description="Current portfolio value (₹)", gt=0)
    unrealized_gl    : float = Field(-0.18,     description="Unrealised gain/loss fraction")
    n_simulations    : int   = Field(500,       description="Monte Carlo paths (100–5000)", ge=100, le=5000)


# ══════════════════════════════════════════════════════════════════════════
# GAP 2 — ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.post("/simulate", summary="GAP 2: HOLD vs SELL — Monte Carlo wealth comparison")
def simulate_hold_vs_sell(payload: SimulateInput) -> dict:
    """
    Runs 1 000 Monte Carlo simulations (or user-specified count) for both
    HOLD and SELL decisions and returns:
    - Year-by-year median trajectories (median / P10 / P90 bands)
    - Final-wealth summary statistics (mean / median / P10 / P90 / std)
    - Opportunity cost in ₹ and %
    - Probability HOLD outperforms SELL
    - Human-readable recommendation text
    """
    try:
        sim    = _sim()
        result = sim.compare_hold_vs_sell(
            user_id       = payload.user_id,
            current_wealth= payload.current_wealth,
            unrealized_gl = payload.unrealized_gl,
            n_simulations = payload.n_simulations,
        )
        # Drop raw outcome arrays (too large for API response) — keep summaries
        for key in ("hold", "sell"):
            result[key].pop("outcomes", None)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/simulate/individual", summary="GAP 2: Single-scenario Monte Carlo (HOLD or SELL)")
def simulate_individual(payload: SimulateIndividualInput) -> dict:
    """
    Simulates a single decision scenario (HOLD or SELL) for a specific user
    and returns the wealth distribution across all Monte Carlo paths.
    Useful for building a before/after comparison on the frontend.
    """
    try:
        sim    = _sim()
        result = sim.simulate_individual(
            user_id          = payload.user_id,
            decision         = payload.decision,
            current_portfolio= payload.current_portfolio,
            unrealized_gl    = payload.unrealized_gl,
            n_simulations    = payload.n_simulations,
        )
        # Remove raw arrays (keep summary + trajectories for chart)
        result.pop("outcomes", None)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/simulate/validate/{decision_id}",
         summary="GAP 2: Validate simulator vs synthetic_counterfactuals.csv")
def validate_simulation(
    decision_id  : int   = Path(..., description="Decision ID (integer) from synthetic_decisions.csv"),
    current_wealth: float = 10_000.0,
) -> dict:
    """
    Runs the simulator for the specified decision_id and compares the result
    to the pre-computed counterfactual ground truth.
    Target: HOLD error < 20 %, SELL error < 20 %.
    """
    try:
        sim = _sim()
        return sim.validate_against_precomputed(
            decision_id   = decision_id,
            current_wealth= current_wealth,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/simulate/bias_impact", summary="GAP 2: Population-level bias cost quantification")
def simulate_bias_impact(
    n_users           : int   = 100,
    assumed_portfolio : float = 75_000.0,
) -> dict:
    """
    Experiment 2 (Research Paper): Measures the population-level financial cost
    of behavioral biases across n_users from synthetic_users.csv.
    Expected result: ~30-50% wealth gap between biased and rational investors
    over their investment horizons — targeting the 42% gap from the master blueprint.
    """
    try:
        if n_users > 500:
            raise HTTPException(
                status_code=400,
                detail="n_users > 500 is too slow for a synchronous API call. Use the notebook instead."
            )
        sim    = _sim()
        result = sim.bias_impact_quantifier(n_users=n_users, assumed_portfolio=assumed_portfolio)
        # Distribution can be large — summarise
        dist   = result.pop("distribution", [])
        result["distribution_summary"] = {
            "p10"   : float(np.percentile(dist, 10))  if dist else 0,
            "p25"   : float(np.percentile(dist, 25))  if dist else 0,
            "median": float(np.median(dist))           if dist else 0,
            "p75"   : float(np.percentile(dist, 75))  if dist else 0,
            "p90"   : float(np.percentile(dist, 90))  if dist else 0,
            "n"     : len(dist),
        }
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# GAP 3 — PYDANTIC MODELS FOR THE EXPLAINER
# ══════════════════════════════════════════════════════════════════════════

class ExplainInput(BaseModel):
    """
    Plain-language explanation request.

    Runs Objective 1 (bias detection) and Objective 2 (long-horizon
    simulation) internally, then narrates the result, so a single call gives
    a complete answer.
    """
    user_id          : int   = Field(42,        description="User ID from synthetic_users.csv")
    current_wealth   : float = Field(75_000.0,  description="Current portfolio value (₹)", gt=0)
    unrealized_gl    : float = Field(-0.15,     description="Unrealised gain/loss fraction (e.g. -0.15 = -15%)")
    n_simulations    : int   = Field(1_000,     description="Monte Carlo paths per scenario (100–5000)", ge=100, le=5000)
    lang             : str   = Field("en",      description="Explanation language: 'en' or 'hi'")
    decision_intent  : str   = Field("Thinking of selling",
                                     description="What the user says they intend to do")

    # Optional context — falls back to the same defaults Objective 1 uses
    market_return       : Optional[float] = Field(None, description="Recent market return (auto-fetched if omitted)")
    market_volatility   : Optional[float] = Field(None, description="Current volatility (auto-fetched if omitted)")
    crowd_ratio         : Optional[float] = Field(None, description="Fraction of crowd selling [0, 1]")
    age                 : Optional[int]   = Field(None, description="Investor age (defaults to the user profile)")
    investment_horizon  : Optional[int]   = Field(None, description="Years until the money is needed")
    risk_tolerance      : Optional[float] = Field(None, description="Risk tolerance [0–1]")
    monthly_income      : Optional[float] = Field(None, description="Monthly income (₹)")
    monthly_expense     : Optional[float] = Field(None, description="Monthly expense (₹)")
    has_emergency_fund  : int             = Field(1,    description="1 = has emergency fund, 0 = does not")
    position_size_pct   : float           = Field(0.10, description="Position size as a fraction of the portfolio")
    holding_period_months: int            = Field(6,    description="Months the position has been held")


class ExplainReportInput(ExplainInput):
    """Explanation request plus the download format."""
    format: str = Field("html", description="Report format: 'md', 'html', or 'pdf' (English only)")


def _explain_payload(payload: "ExplainInput") -> dict:
    """
    Build the user_input dict the explainer expects, dropping unset optional
    fields so Objective 1 and Objective 2 apply their own defaults.
    """
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data.pop("format", None)
    data.pop("lang", None)
    return {k: v for k, v in data.items() if v is not None}


# ══════════════════════════════════════════════════════════════════════════
# GAP 3 — ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.post("/explain", summary="GAP 3: Plain-language explanation of a decision (EN / HI)")
def explain_decision(payload: ExplainInput) -> dict:
    """
    The full decision story, in language anyone can read.

    Runs bias detection (Objective 1) and the long-horizon simulation
    (Objective 2), then returns six plain-language sections:

    1. **In short** — what you're about to do, and whether it's wise
    2. **What's going on right now** — the bias in human words
    3. **Your two possible futures** — HOLD vs SELL in rupees
    4. **The story of your money** — year-by-year
    5. **Why we're telling you this** — what drove the conclusion
    6. **What to do now** — one clear action, with an honest caveat

    Set `lang` to `hi` for Hindi.  The `technical` block carries the SHAP
    values, causal chain and raw statistics for anyone who wants them.
    """
    try:
        from explainer import explain_from_inputs

        lang = payload.lang if payload.lang in ("en", "hi") else "en"
        explanation = explain_from_inputs(_explain_payload(payload), lang=lang)

        # Trajectory arrays stay (they drive the charts); raw path dumps do not.
        explanation["technical"]["hold_stats"].pop("outcomes", None)
        explanation["technical"]["sell_stats"].pop("outcomes", None)
        return explanation

    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/explain/report", summary="GAP 3: Download the explanation as a report")
def explain_report(payload: ExplainReportInput):
    """
    The same explanation as a keepable document.

    - `md`   — Markdown, both languages
    - `html` — styled and print-ready, both languages (recommended)
    - `pdf`  — English only

    Hindi PDF is deliberately not offered: ReportLab cannot shape Devanagari,
    so the output would be wrong.  The HTML report prints to a correct PDF
    from any browser.
    """
    try:
        from fastapi.responses import Response

        import explanation_report as report_mod
        from explainer import explain_from_inputs

        lang = payload.lang if payload.lang in ("en", "hi") else "en"
        fmt  = (payload.format or "html").lower()

        if fmt not in report_mod.available_formats(lang):
            raise HTTPException(
                status_code=400,
                detail=(f"Format '{fmt}' is not available for language '{lang}'. "
                        f"Available: {report_mod.available_formats(lang)}"),
            )

        explanation = explain_from_inputs(_explain_payload(payload), lang=lang)
        filename    = report_mod.filename_for(explanation, fmt)

        if fmt == "pdf":
            body, media = report_mod.to_pdf(explanation), "application/pdf"
        elif fmt == "html":
            body, media = report_mod.to_html(explanation).encode("utf-8"), "text/html; charset=utf-8"
        else:
            body, media = report_mod.to_markdown(explanation).encode("utf-8"), "text/markdown; charset=utf-8"

        return Response(
            content=body,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/explain/status", summary="GAP 3: Explainer configuration and language support")
def explain_status() -> dict:
    """
    What the explainer can currently do: which languages, which report
    formats, and whether the optional LLM polish layer is switched on.
    """
    try:
        import explanation_report as report_mod
        import explanation_templates as tpl
        from llm_polish import circuit_status, provider_info

        info = provider_info()
        return {
            "languages"        : {code: tpl.LANG_NAMES[code] for code in tpl.SUPPORTED_LANGS},
            "sections"         : tpl.SECTIONS,
            "report_formats"   : {lang: report_mod.available_formats(lang)
                                  for lang in tpl.SUPPORTED_LANGS},
            "llm_polish"       : info,
            # If the key or quota fails, the layer pauses itself and
            # explanations keep coming from templates. This is where to look
            # when polishing has quietly stopped happening.
            "llm_circuit"      : circuit_status(),
            "deterministic"    : not info["enabled"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# STANDALONE RUN (development only)
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        raise SystemExit("uvicorn not installed. Run: pip install uvicorn[standard]")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
