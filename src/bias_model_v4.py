"""
═══════════════════════════════════════════════════════════════════════════
 bias_model_v4.py — action-aware, portfolio-aware bias classifier (Phase A2)
═══════════════════════════════════════════════════════════════════════════
What changed from v3
--------------------
* **It sees the action.** Sell, hold or buy more is an input, so the same
  situation can read differently depending on what the investor wants to do.
  v3 could only score the situation, which is why a calm-market sale at a
  loss came back as "disposition effect".
* **It sees the portfolio.** Position size, monthly surplus (EMIs, rent and
  education fees out; rent received in), emergency fund, asset mix (equity
  and gold share), property and loans.
* **Cash needs (v4.1).** Trained on dataset 4.1, which includes stretched
  households and cash shocks; ``cash_need_stated`` (the investor said they
  need the money) lets a forced sale read as rational.
* **Real markets.** Trained on data/v4/decisions_v4.csv, whose market inputs
  are real NIFTY 50 and India VIX values for real trading days, 2008-2026.
* **The label rules are inputs.** ``allows_*`` flags say which patterns the
  agreed definitions (src/dataset_v4.py LABEL_RULES) permit for this
  situation and action. The model decides *between* the permitted patterns —
  the hard part, since the same sale can be rational or biased — and a guard
  removes any pattern the definitions rule out.
* **Calibrated confidence.** The confidence of the chosen pattern is mapped
  through an isotonic curve fitted on out-of-fold predictions, weighted to
  how often each kind of market really occurs. "90%" means right about nine
  times in ten on real-frequency test data.
* **"What weighed most" explains the chosen pattern.** Contributions are
  exact TreeSHAP values (XGBoost's ``pred_contribs``) for the predicted
  class, grouped into plain drivers. v3 ranked by the class with the largest
  total attribution, which was often not the class it predicted.

One feature builder, :func:`build_features`, serves both training and the app,
so the two cannot drift apart.

Artefacts (written by scripts/train_bias_v4.py)
-----------------------------------------------
    models/bias_detector_v4.json        XGBoost booster (native JSON, no pickle)
    models/bias_detector_v4.meta.json   features, calibration curve, input
                                        medians, training summary
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.dataset_v4 import allowed_labels

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "bias_detector_v4.json")
META_PATH = os.path.join(MODELS_DIR, "bias_detector_v4.meta.json")

VERSION = "v4"
LABELS: tuple[str, ...] = ("disposition", "herd", "loss_aversion", "rational")
ACTIONS: tuple[str, ...] = ("sell", "hold", "buy_more")

FEATURES: tuple[str, ...] = (
    # the decision
    "action_sell", "action_hold", "action_buy_more",
    "unrealized_gl", "holding_period_months",
    # the market
    "nifty_1m_return", "vix", "nifty_volatility_30d",
    # what the label definitions permit here
    "allows_disposition", "allows_herd", "allows_loss_aversion",
    # the investor
    "age", "investment_horizon", "risk_tolerance",
    # money and portfolio
    "surplus_ratio", "has_emergency_fund", "position_share",
    "equity_share", "gold_share", "owns_property", "debt_ratio",
    # v4.1: the investor said they need the money (from the comment, Phase B3)
    "cash_need_stated",
)

#: Raw inputs :func:`build_features` reads. Training rows (decisions_v4.csv
#: plus ``loans_outstanding``) and app requests use the same names.
INPUTS: tuple[str, ...] = (
    "action", "unrealized_gl", "holding_period_months",
    "nifty_1m_return", "vix", "nifty_volatility_30d",
    "age", "investment_horizon", "risk_tolerance",
    "monthly_income", "rent_received", "monthly_outflow", "has_emergency_fund",
    "position_share", "equity_share", "gold_share",
    "liquid_assets", "real_estate_value", "loans_outstanding",
    "cash_need_stated",
)

#: Model feature -> the plain driver it belongs to. SHAP values are additive,
#: so a driver's contribution is the sum of its features' contributions.
DRIVER_OF: dict[str, str] = {
    "action_sell": "action", "action_hold": "action", "action_buy_more": "action",
    "unrealized_gl": "gain_loss",
    "holding_period_months": "holding_period",
    "nifty_1m_return": "market_month",
    "vix": "market_fear",
    "nifty_volatility_30d": "market_swings",
    "allows_disposition": "fits_disposition",
    "allows_herd": "fits_herd",
    "allows_loss_aversion": "fits_loss_aversion",
    "age": "age",
    "investment_horizon": "horizon",
    "risk_tolerance": "risk_tolerance",
    "surplus_ratio": "cash_flow",
    "has_emergency_fund": "emergency_fund",
    "position_share": "position_size",
    "equity_share": "asset_mix",
    "gold_share": "asset_mix",
    "owns_property": "property_loans",
    "debt_ratio": "property_loans",
    "cash_need_stated": "cash_need",
}
DRIVERS: tuple[str, ...] = tuple(dict.fromkeys(DRIVER_OF.values()))


# ═════════════════════════════════════════════════════════════════════════
# FEATURES
# ═════════════════════════════════════════════════════════════════════════

def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    den = den.astype(float)
    return (num.astype(float) / den.where(den > 0)).fillna(0.0)


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Model features from raw inputs (:data:`INPUTS`), in :data:`FEATURES` order.

    Used for training and for every live request. Missing raw columns raise —
    filling gaps is the caller's job, so that it can disclose what it filled.
    """
    missing = [c for c in INPUTS if c not in raw.columns]
    if missing:
        raise KeyError(f"bias model v4 inputs missing: {missing}")
    bad = set(raw["action"]) - set(ACTIONS)
    if bad:
        raise ValueError(f"unknown action(s) {sorted(bad)}; expected one of {ACTIONS}")

    gl = raw["unrealized_gl"].astype(float)
    r1m = raw["nifty_1m_return"].astype(float)
    vix = raw["vix"].astype(float)
    allowed = [
        allowed_labels(g, r, v, a)
        for g, r, v, a in zip(gl, r1m, vix, raw["action"])
    ]
    income = raw["monthly_income"].astype(float)
    surplus = income + raw["rent_received"].astype(float) - raw["monthly_outflow"].astype(float)

    X = pd.DataFrame({
        "action_sell": (raw["action"] == "sell").astype(int),
        "action_hold": (raw["action"] == "hold").astype(int),
        "action_buy_more": (raw["action"] == "buy_more").astype(int),
        "unrealized_gl": gl,
        "holding_period_months": raw["holding_period_months"].astype(float),
        "nifty_1m_return": r1m,
        "vix": vix,
        "nifty_volatility_30d": raw["nifty_volatility_30d"].astype(float),
        "allows_disposition": [int("disposition" in a) for a in allowed],
        "allows_herd": [int("herd" in a) for a in allowed],
        "allows_loss_aversion": [int("loss_aversion" in a) for a in allowed],
        "age": raw["age"].astype(float),
        "investment_horizon": raw["investment_horizon"].astype(float),
        "risk_tolerance": raw["risk_tolerance"].astype(float),
        "surplus_ratio": _ratio(surplus, income).clip(-2.0, 2.0),
        "has_emergency_fund": raw["has_emergency_fund"].astype(int),
        "position_share": raw["position_share"].astype(float).clip(0.0, 1.0),
        "equity_share": raw["equity_share"].astype(float).clip(0.0, 1.0),
        "gold_share": raw["gold_share"].astype(float).clip(0.0, 1.0),
        "owns_property": (raw["real_estate_value"].astype(float) > 0).astype(int),
        "debt_ratio": _ratio(
            raw["loans_outstanding"],
            raw["liquid_assets"].astype(float) + raw["real_estate_value"].astype(float),
        ).clip(0.0, 5.0),
        "cash_need_stated": raw["cash_need_stated"].astype(int),
    }, index=raw.index)
    return X[list(FEATURES)]


def raw_from_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """decisions_v4.csv rows -> :data:`INPUTS` (adds ``loans_outstanding``)."""
    out = df.copy()
    out["loans_outstanding"] = out["home_loan_outstanding"] + out["other_loans_outstanding"]
    return out[list(INPUTS)]


def allowed_mask(raw: pd.DataFrame) -> np.ndarray:
    """(n, 4) booleans: which of :data:`LABELS` the definitions allow per row."""
    rows = [
        allowed_labels(g, r, v, a)
        for g, r, v, a in zip(raw["unrealized_gl"], raw["nifty_1m_return"], raw["vix"], raw["action"])
    ]
    return np.array([[lab in a for lab in LABELS] for a in rows], dtype=bool)


# ═════════════════════════════════════════════════════════════════════════
# CALIBRATION
# ═════════════════════════════════════════════════════════════════════════

def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def apply_guard(p: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Zero the patterns the definitions rule out, then renormalise."""
    q = p * mask
    return q / q.sum(axis=1, keepdims=True)


def calibrate_top_label(p: np.ndarray, curve_x: np.ndarray, curve_y: np.ndarray) -> np.ndarray:
    """Replace the chosen pattern's probability with its calibrated value.

    The other patterns are rescaled to fill the rest, keeping their ratios.
    The chosen pattern is never demoted: its calibrated value is floored at
    the level where it ties the runner-up, so calibration changes how sure
    the model says it is, never what it says.
    """
    p = np.asarray(p, dtype=float)
    k = p.argmax(axis=1)
    rows = np.arange(len(p))
    top = p[rows, k]
    rest = 1.0 - top
    second = np.sort(p, axis=1)[:, -2]
    c = np.interp(top, curve_x, curve_y)
    floor = np.where(rest > 0, second / np.maximum(rest + second, 1e-12) + 1e-6, top)
    c = np.clip(np.maximum(c, floor), 0.0, 1.0)
    scale = np.where(rest > 1e-12, (1.0 - c) / np.maximum(rest, 1e-12), 0.0)
    q = p * scale[:, None]
    q[rows, k] = c
    return q


# ═════════════════════════════════════════════════════════════════════════
# LOADING
# ═════════════════════════════════════════════════════════════════════════

_lock = threading.Lock()
_cache: dict[str, Any] | None = None


def load(model_path: str = MODEL_PATH, meta_path: str = META_PATH) -> dict[str, Any]:
    """Booster plus metadata, cached after the first call."""
    global _cache
    with _lock:
        if _cache is None or _cache["model_path"] != model_path:
            import xgboost as xgb

            if not (os.path.exists(model_path) and os.path.exists(meta_path)):
                raise FileNotFoundError(
                    f"{model_path} / {meta_path} — train with scripts/train_bias_v4.py"
                )
            booster = xgb.Booster()
            booster.load_model(model_path)
            meta = read_meta(meta_path)
            if tuple(meta["features"]) != FEATURES:
                raise ValueError("bias_detector_v4 metadata features differ from src.bias_model_v4.FEATURES")
            _cache = {"booster": booster, "meta": meta, "model_path": model_path}
        return _cache


def read_meta(meta_path: str = META_PATH) -> dict[str, Any]:
    """The metadata alone — no XGBoost import, so the app can read fill values cheaply."""
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"{meta_path} — train with scripts/train_bias_v4.py")
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def input_medians() -> dict[str, float]:
    """Training-set medians of the raw inputs — the documented neutral fill."""
    return dict(read_meta()["input_medians"])


def market_medians() -> dict[str, float]:
    """Median real trading day, 2008-2026 — the fill when no market data was captured.

    The training set over-samples crashes on purpose, so its own medians would
    describe a more fearful market than a typical day.
    """
    return dict(read_meta()["market_medians"])


# ═════════════════════════════════════════════════════════════════════════
# PREDICTION
# ═════════════════════════════════════════════════════════════════════════

def _margins_and_contribs(booster, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    import xgboost as xgb

    dm = xgb.DMatrix(X.to_numpy(dtype=float), feature_names=list(FEATURES))
    margins = booster.predict(dm, output_margin=True).reshape(len(X), len(LABELS))
    contribs = booster.predict(dm, pred_contribs=True)   # (n, classes, features + bias)
    return margins, contribs


def predict_frame(raw: pd.DataFrame, *, guard: bool = True, calibrated: bool = True) -> dict[str, np.ndarray]:
    """Batch prediction — used by evaluation. Returns probabilities and labels."""
    bundle = load()
    meta = bundle["meta"]
    X = build_features(raw)
    import xgboost as xgb

    dm = xgb.DMatrix(X.to_numpy(dtype=float), feature_names=list(FEATURES))
    p = softmax(bundle["booster"].predict(dm, output_margin=True).reshape(len(X), len(LABELS)))
    mask = allowed_mask(raw)
    if guard:
        p = apply_guard(p, mask)
    if calibrated:
        p = calibrate_top_label(p, np.array(meta["calibration"]["x"]), np.array(meta["calibration"]["y"]))
    return {"proba": p, "pred": p.argmax(axis=1), "mask": mask}


def _drivers(contrib_row: np.ndarray, X_row: pd.Series, top_n: int) -> list[dict[str, Any]]:
    """Per-driver contributions to the chosen pattern's score, largest first."""
    totals: dict[str, float] = {d: 0.0 for d in DRIVERS}
    for j, feat in enumerate(FEATURES):
        totals[DRIVER_OF[feat]] += float(contrib_row[j])
    grand = sum(abs(v) for v in totals.values()) or 1.0
    ranked = sorted(totals.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_n]
    out = []
    for driver, impact in ranked:
        feats = [f for f in FEATURES if DRIVER_OF[f] == driver]
        out.append({
            "driver": driver,
            "impact": round(impact, 4),
            "share": round(abs(impact) / grand, 4),
            "direction": "toward" if impact > 0 else "against",
            "inputs": {f: (round(float(X_row[f]), 4)) for f in feats},
        })
    return out


def predict(inputs: Mapping[str, Any], top_n: int = 5) -> dict[str, Any]:
    """One decision -> pattern, calibrated confidence, probabilities, drivers.

    ``inputs`` must hold every key in :data:`INPUTS`; fill gaps (and record
    that you did) before calling.
    """
    bundle = load()
    meta = bundle["meta"]
    raw = pd.DataFrame([{k: inputs[k] for k in INPUTS}])
    X = build_features(raw)

    t0 = time.perf_counter()
    margins, contribs = _margins_and_contribs(bundle["booster"], X)
    p_model = softmax(margins)
    mask = allowed_mask(raw)
    p_guarded = apply_guard(p_model, mask)
    curve = meta["calibration"]
    p = calibrate_top_label(p_guarded, np.array(curve["x"]), np.array(curve["y"]))[0]
    k = int(p.argmax())
    elapsed_ms = (time.perf_counter() - t0) * 1000

    label = LABELS[k]
    return {
        "bias_type": label,
        "confidence": round(float(p[k]), 4),
        "probabilities": {lab: round(float(v), 4) for lab, v in zip(LABELS, p)},
        "model_probabilities": {lab: round(float(v), 4) for lab, v in zip(LABELS, p_model[0])},
        "allowed": [lab for lab, ok in zip(LABELS, mask[0]) if ok],
        "guard_applied": bool(p_model[0].argmax() != p_guarded[0].argmax()),
        "is_biased": label != "rational",
        "drivers": _drivers(contribs[0, k, :-1], X.iloc[0], top_n),
        "features": {f: round(float(X.iloc[0][f]), 6) for f in FEATURES},
        "model_version": VERSION,
        "inference_ms": round(elapsed_ms, 2),
    }


def sanity_check_contributions(inputs: Mapping[str, Any]) -> float:
    """Max |sum(SHAP) + bias - margin| over classes — 0 up to float error."""
    bundle = load()
    X = build_features(pd.DataFrame([{k: inputs[k] for k in INPUTS}]))
    margins, contribs = _margins_and_contribs(bundle["booster"], X)
    return float(np.max(np.abs(contribs[0].sum(axis=1) - margins[0])))


__all__ = [
    "VERSION", "LABELS", "ACTIONS", "FEATURES", "INPUTS", "DRIVER_OF", "DRIVERS",
    "MODEL_PATH", "META_PATH", "build_features", "raw_from_dataset", "allowed_mask",
    "softmax", "apply_guard", "calibrate_top_label", "load", "read_meta", "input_medians", "market_medians",
    "predict", "predict_frame", "sanity_check_contributions",
]

if __name__ == "__main__":  # quick smoke test
    med = input_medians()
    print(json.dumps(predict({**med, "action": "sell", "unrealized_gl": 0.35}), indent=2))
    print("contribution check:", sanity_check_contributions({**med, "action": "sell", "unrealized_gl": 0.35}))
