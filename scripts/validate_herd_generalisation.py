"""
Validate herd generalisation on held-out boundary-shifted synthetic samples.

Usage:
  python scripts/validate_herd_generalisation.py
  python scripts/validate_herd_generalisation.py --model models/bias_detector_xgboost_v2.pkl
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.bias_detector import (
    BIAS_LABELS,
    EXCLUDE,
    MODEL_PATH,
    MODEL_PATH_V2,
    _fill_missing_values,
    load_model,
)

MERGED_FEATURES_PATH = os.path.join(ROOT, "data", "processed", "merged_features.csv")
OUT_PATH_V2 = os.path.join(ROOT, "results", "herd_generalisation_test.json")
OUT_PATH_V3 = os.path.join(ROOT, "results", "herd_generalisation_test_v3.json")


def _market_regime(values: np.ndarray) -> np.ndarray:
    out = np.full(len(values), "neutral", dtype=object)
    out[values <= -0.10] = "crash"
    out[(values > -0.10) & (values <= -0.03)] = "bear"
    out[(values > 0.03) & (values <= 0.10)] = "bull"
    out[values > 0.10] = "rally"
    return out


def _loss_magnitude(values: np.ndarray) -> np.ndarray:
    out = np.full(len(values), "gain", dtype=object)
    out[values < -0.20] = "severe_loss"
    out[(values >= -0.20) & (values < -0.10)] = "large_loss"
    out[(values >= -0.10) & (values < -0.05)] = "small_loss"
    out[(values >= -0.05) & (values < 0.0)] = "no_loss"
    return out


def _crowd_pressure(values: np.ndarray) -> np.ndarray:
    out = np.full(len(values), "contrarian", dtype=object)
    out[(values > 0.30) & (values <= 0.50)] = "mixed"
    out[(values > 0.50) & (values <= 0.70)] = "moderate_herd"
    out[values > 0.70] = "strong_herd"
    return out


def _prepare_features(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    df = _fill_missing_values(df.copy())

    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    if bool_cols:
        df[bool_cols] = df[bool_cols].astype(int)

    obj_cols = [
        c for c in df.select_dtypes(exclude=["number", "bool"]).columns
        if c not in EXCLUDE
    ]
    if obj_cols:
        df[obj_cols] = df[obj_cols].astype(str)
        df = pd.get_dummies(df, columns=obj_cols, drop_first=True)

    X = df[[c for c in df.columns if c not in EXCLUDE]].astype(float)
    X = X.loc[:, ~X.columns.duplicated()]
    for col in feature_cols:
        if col not in X.columns:
            X[col] = 0.0
    return X[feature_cols]


def validate_herd_generalisation(
    seed: int = 42,
    n_samples: int = 60,
    model_path: str | None = None,
    output_path: str | None = None,
) -> None:
    rng = np.random.default_rng(seed)

    candidate_model = model_path or (MODEL_PATH_V2 if os.path.exists(MODEL_PATH_V2) else MODEL_PATH)
    model, feature_cols = load_model(candidate_model)

    merged = pd.read_csv(MERGED_FEATURES_PATH)
    if "bias_type" not in merged.columns:
        raise RuntimeError("merged_features.csv does not contain bias_type column required for herd validation.")

    herd_rows = merged[merged["bias_type"] == "herd"]
    if herd_rows.empty:
        raise RuntimeError("No herd rows found in merged_features.csv to use as baseline template.")

    samples = herd_rows.sample(n=n_samples, replace=True, random_state=seed).copy().reset_index(drop=True)

    samples["herd_sensitivity"] = rng.uniform(0.55, 0.75, n_samples)
    samples["crowd_action_ratio"] = rng.uniform(0.55, 0.80, n_samples)
    samples["market_return_recent"] = rng.uniform(-0.08, 0.08, n_samples)
    samples["unrealized_gain_loss"] = rng.uniform(-0.10, 0.15, n_samples)
    samples["age"] = rng.integers(22, 60, n_samples)
    samples["risk_tolerance"] = rng.uniform(2, 8, n_samples)
    samples["investment_horizon"] = rng.integers(2, 30, n_samples)
    samples["monthly_income"] = rng.uniform(25000, 220000, n_samples)
    samples["position_size_pct"] = rng.uniform(0.05, 0.70, n_samples)
    samples["holding_period_months"] = rng.integers(1, 48, n_samples)
    samples["market_volatility"] = rng.uniform(0.10, 0.45, n_samples)
    samples["has_emergency_fund"] = rng.choice([0, 1], n_samples, p=[0.45, 0.55])

    samples["monthly_expense"] = np.minimum(
        samples["monthly_income"] * rng.uniform(0.45, 0.95, n_samples),
        samples["monthly_income"] * 0.98,
    )
    samples["monthly_surplus"] = samples["monthly_income"] - samples["monthly_expense"]

    samples["bias_type"] = "herd"
    samples["decision"] = "sell"
    samples["bias_present"] = "yes"

    samples["market_regime"] = _market_regime(samples["market_return_recent"].to_numpy())
    samples["loss_magnitude"] = _loss_magnitude(samples["unrealized_gain_loss"].to_numpy())
    samples["crowd_pressure"] = _crowd_pressure(samples["crowd_action_ratio"].to_numpy())

    samples["loss_x_crowd"] = samples["unrealized_gain_loss"] * samples["crowd_action_ratio"]
    samples["loss_x_market"] = samples["unrealized_gain_loss"] * samples["market_return_recent"]
    samples["loss_vs_risk_tolerance"] = samples["unrealized_gain_loss"] / samples["risk_tolerance"].replace(0, 1e-6)
    samples["age_horizon_ratio"] = samples["age"] / (samples["investment_horizon"] + 1)
    samples["financial_stress"] = ((samples["has_emergency_fund"].astype(int) == 0) & (samples["monthly_surplus"] < 0)).astype(int)
    samples["surplus_normalized"] = samples["monthly_surplus"] / samples["monthly_income"].replace(0, 1e-6)
    samples["crowd_influence_ratio"] = (
        samples["crowd_action_ratio"]
        / samples["unrealized_gain_loss"].abs().clip(lower=0.01)
    ).clip(lower=0.0, upper=50.0)
    samples["herd_pure_signal"] = (
        samples["crowd_action_ratio"]
        * (1 - samples["unrealized_gain_loss"].clip(upper=0).abs())
    )
    samples["loss_crowd_interaction"] = (
        samples["crowd_action_ratio"]
        * samples["unrealized_gain_loss"].clip(upper=0).abs()
    )

    herd_id = [k for k, v in BIAS_LABELS.items() if v == "herd"][0]
    if "bias_label" in samples.columns:
        samples["bias_label"] = herd_id

    X_val = _prepare_features(samples, feature_cols)
    y_pred = model.predict(X_val)
    y_proba = model.predict_proba(X_val)

    correct = int((y_pred == herd_id).sum())
    accuracy = float(correct / n_samples)

    if accuracy < 0.70:
        verdict = "Model memorised herd generation rule, not generalisable pattern"
    elif accuracy > 0.85:
        verdict = "Model has genuinely learned herd behaviour"
    else:
        verdict = "Borderline generalisation: partially robust but needs further stress testing"

    print(f"Herd generalisation accuracy: {accuracy:.4f} ({correct}/{n_samples})")
    print(verdict)

    records = []
    for i in range(n_samples):
        pred_id = int(y_pred[i])
        records.append(
            {
                "sample_id": i,
                "expected": "herd",
                "predicted": BIAS_LABELS.get(pred_id, str(pred_id)),
                "predicted_confidence": float(np.max(y_proba[i])),
                "herd_probability": float(y_proba[i][herd_id]),
                "correct": bool(pred_id == herd_id),
                "herd_sensitivity": float(samples.loc[i, "herd_sensitivity"]),
                "crowd_action_ratio": float(samples.loc[i, "crowd_action_ratio"]),
                "market_return_recent": float(samples.loc[i, "market_return_recent"]),
                "unrealized_gain_loss": float(samples.loc[i, "unrealized_gain_loss"]),
                "risk_tolerance": float(samples.loc[i, "risk_tolerance"]),
                "age": int(samples.loc[i, "age"]),
            }
        )

    output = {
        "n_samples": n_samples,
        "model_path": candidate_model,
        "accuracy": accuracy,
        "correct": correct,
        "verdict": verdict,
        "warning": "Model memorised herd generation rule, not generalisable pattern" if accuracy < 0.70 else None,
        "samples": records,
    }

    if output_path:
        out_path = output_path
    else:
        out_path = OUT_PATH_V3 if "_v3" in os.path.basename(candidate_model) else OUT_PATH_V2

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Saved herd generalisation report -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate herd generalisation on shifted boundary samples.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-samples", type=int, default=60)
    parser.add_argument("--model", type=str, default=None, help="Optional model path")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON path")
    args = parser.parse_args()

    validate_herd_generalisation(
        seed=args.seed,
        n_samples=args.n_samples,
        model_path=args.model,
        output_path=args.output,
    )
