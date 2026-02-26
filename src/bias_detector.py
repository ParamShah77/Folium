"""
GAP 1 – Week 2-3: Bias Detection Model (XGBoost)
==================================================
Trains a multi-class classifier to detect 4 bias types:
  0 = rational
  1 = herd_mentality
  2 = loss_aversion
  3 = overconfidence  (or whatever labels are in synthetic_decisions.csv)

Outputs:
  models/bias_detector_xgboost.pkl
  results/figures/confusion_matrix.png
  results/figures/feature_importance.png

Run:
    python src/bias_detector.py
"""

import os
import pickle
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED    = os.path.join(ROOT, "data", "processed")
MODELS_DIR   = os.path.join(ROOT, "models")
FIGURES_DIR  = os.path.join(ROOT, "results", "figures")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

MODEL_PATH   = os.path.join(MODELS_DIR, "bias_detector_xgboost.pkl")

# Features listed in data_preparation.py (numeric + OHE expanded)
# We exclude profile cols and string targets automatically
EXCLUDE = {
    "bias_label", "decision_label", "decision", "bias_type",
    "bias_present", "user_id", "decision_id",
    "disposition_strength_profile", "loss_aversion_profile",
    "herd_sensitivity_profile",
}


# ═══════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """Load merged features and split into train/test using saved indices."""
    df        = pd.read_csv(os.path.join(PROCESSED, "merged_features.csv"))
    train_idx = np.load(os.path.join(PROCESSED, "train_indices.npy"))
    test_idx  = np.load(os.path.join(PROCESSED, "test_indices.npy"))

    # Convert boolean columns to int
    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    df[bool_cols] = df[bool_cols].astype(int)

    # One-hot encode ALL non-numeric columns that are not in EXCLUDE
    # Use select_dtypes(exclude=...) to handle both object and new StringDtype in pandas 3.x
    obj_cols = [
        c for c in df.select_dtypes(exclude=["number", "bool"]).columns
        if c not in EXCLUDE
    ]
    if obj_cols:
        # Convert to plain Python str first (handles arrow-backed StringDtype)
        df[obj_cols] = df[obj_cols].astype(str)
        df = pd.get_dummies(df, columns=obj_cols, drop_first=True)

    # Feature columns = everything except EXCLUDE set
    feature_cols = [c for c in df.columns if c not in EXCLUDE]

    X = df[feature_cols].astype(float)
    y = df["bias_label"]

    X_train = X.loc[train_idx]
    X_test  = X.loc[test_idx]
    y_train = y.loc[train_idx]
    y_test  = y.loc[test_idx]

    print(f"✅ Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"   Classes: {sorted(y.unique())}  |  "
          f"Class balance: {y_train.value_counts().to_dict()}")
    return X_train, X_test, y_train.to_numpy(), y_test.to_numpy()


# ═══════════════════════════════════════════════════════════
# TRAIN
# ═══════════════════════════════════════════════════════════

def train_model(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    tune: bool = False,
) -> xgb.XGBClassifier:
    """
    Train XGBoost classifier.
    Set tune=True to do RandomizedSearchCV (takes ~5 min).
    """
    n_classes = len(np.unique(y_train))

    base_params = {
        "n_estimators"  : 200,
        "max_depth"     : 6,
        "learning_rate" : 0.1,
        "subsample"     : 0.8,
        "colsample_bytree": 0.8,
        "objective"     : "multi:softmax",
        "num_class"     : n_classes,
        "eval_metric"   : "mlogloss",
        "random_state"  : 42,
        "n_jobs"        : -1,
    }

    if tune:
        param_grid = {
            "n_estimators"      : [100, 200, 300, 500],
            "max_depth"         : [3, 4, 5, 6, 8],
            "learning_rate"     : [0.01, 0.05, 0.1, 0.2],
            "subsample"         : [0.6, 0.8, 1.0],
            "colsample_bytree"  : [0.6, 0.8, 1.0],
            "min_child_weight"  : [1, 3, 5],
        }
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        search = RandomizedSearchCV(
            xgb.XGBClassifier(**base_params),
            param_distributions=param_grid,
            n_iter=30,
            scoring="f1_macro",
            cv=cv,
            verbose=1,
            random_state=42,
            n_jobs=-1,
        )
        print("🔍 Hyperparameter tuning (30 random configs × 5-fold CV)…")
        search.fit(X_train, y_train)
        print(f"   Best params: {search.best_params_}")
        model = search.best_estimator_
    else:
        model = xgb.XGBClassifier(**base_params)
        print("🚀 Training XGBoost with default params…")
        t0 = time.time()
        model.fit(X_train, y_train)
        print(f"   Done in {time.time()-t0:.1f}s")

    return model


# ═══════════════════════════════════════════════════════════
# EVALUATE
# ═══════════════════════════════════════════════════════════

def evaluate_model(
    model: xgb.XGBClassifier,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    label_names: list[str] | None = None,
) -> dict:
    """Print metrics, save confusion matrix + feature importance plots."""
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    print(f"\n📊 Accuracy: {acc*100:.2f}%  (target ≥ 85%)")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=label_names))

    # ── Confusion matrix ──────────────────────────────────
    cm   = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=label_names)
    fig, ax = plt.subplots(figsize=(8, 6))
    disp.plot(ax=ax, colorbar=True, cmap="Blues")
    ax.set_title("Bias Detection – Confusion Matrix", fontsize=14)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "confusion_matrix.png"), dpi=150)
    plt.close(fig)
    print(f"✅ Saved confusion_matrix.png")

    # ── Feature importance ─────────────────────────────────
    feat_imp = pd.Series(
        model.feature_importances_, index=X_test.columns
    ).sort_values(ascending=False)

    top_n = feat_imp.head(20)
    fig, ax = plt.subplots(figsize=(10, 7))
    top_n.plot(kind="barh", ax=ax, color="steelblue")
    ax.invert_yaxis()
    ax.set_title("Top 20 Feature Importances (XGBoost)", fontsize=14)
    ax.set_xlabel("Importance (gain)")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "feature_importance.png"), dpi=150)
    plt.close(fig)
    print(f"✅ Saved feature_importance.png")

    return {"accuracy": acc, "feature_importance": feat_imp, "y_pred": y_pred}


# ═══════════════════════════════════════════════════════════
# SAVE / LOAD
# ═══════════════════════════════════════════════════════════

def save_model(model: xgb.XGBClassifier, feature_cols: list[str]) -> None:
    bundle = {"model": model, "feature_cols": feature_cols}
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)
    print(f"✅ Model saved → {MODEL_PATH}")


def load_model() -> tuple[xgb.XGBClassifier, list[str]]:
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    return bundle["model"], bundle["feature_cols"]


# ═══════════════════════════════════════════════════════════
# REAL-TIME INFERENCE  ← The key API function
# ═══════════════════════════════════════════════════════════

_model_cache: xgb.XGBClassifier | None = None
_feature_cache: list[str] | None = None

BIAS_LABELS = {0: "disposition", 1: "herd", 2: "loss_aversion", 3: "rational"}


def detect_bias_realtime(
    market_return: float,
    unrealized_gl: float,
    crowd_ratio: float,
    age: int,
    risk_tolerance: float,
    investment_horizon: int,
    monthly_income: float = 60_000,
    monthly_expense: float = 45_000,
    financial_strategy: str = "saving",
    # Additional fields present in training data (optional, sensible defaults)
    market_volatility: float = 0.20,
    position_size_pct: float = 0.10,
    holding_period_months: int = 6,
    has_emergency_fund: int = 1,
    years_investing: int = 5,
    crash_speed: str = "normal",
    secondary_biases: str = "none",
    age_horizon_mismatch: str = "none",
    investment_experience: str = "intermediate",
    goal: str = "wealth growth",
) -> dict:
    """
    Real-time bias detection for a SINGLE decision moment.
    Builds the full 44-feature vector (identical to training) so OHE
    categories are correctly set rather than padded with zeros.

    Returns:
        {
          "bias_type":    "loss_aversion",
          "confidence":   0.87,
          "is_biased":    True,
          "explanation":  "...",
        }

    ⚡ Target inference time: <100 ms
    """
    global _model_cache, _feature_cache

    if _model_cache is None:
        _model_cache, _feature_cache = load_model()

    # ── 1. Numeric / engineered features ──────────────────────────────
    monthly_surplus  = monthly_income - monthly_expense
    loss_x_crowd     = unrealized_gl * crowd_ratio
    loss_x_market    = unrealized_gl * market_return
    loss_vs_risk     = unrealized_gl / max(risk_tolerance, 1e-6)
    age_horizon      = age / (investment_horizon + 1)
    surplus_norm     = monthly_surplus / max(monthly_income, 1e-6)
    financial_stress = int(not bool(has_emergency_fund)) * int(monthly_surplus < 0)

    row = {
        "market_return_recent"   : market_return,
        "unrealized_gain_loss"   : unrealized_gl,
        "crowd_action_ratio"     : crowd_ratio,
        "market_volatility"      : market_volatility,
        "position_size_pct"      : position_size_pct,
        "holding_period_months"  : holding_period_months,
        "age"                    : age,
        "monthly_income"         : monthly_income,
        "monthly_expense"        : monthly_expense,
        "monthly_surplus"        : monthly_surplus,
        "has_emergency_fund"     : int(has_emergency_fund),
        "years_investing"        : years_investing,
        "risk_tolerance"         : risk_tolerance,
        "investment_horizon"     : investment_horizon,
        "loss_x_crowd"           : loss_x_crowd,
        "loss_x_market"          : loss_x_market,
        "loss_vs_risk_tolerance" : loss_vs_risk,
        "age_horizon_ratio"      : age_horizon,
        "financial_stress"       : financial_stress,
        "surplus_normalized"     : surplus_norm,
    }

    # ── 2. OHE categorical features (match training bins exactly) ─────
    # Baseline (drop_first) categories are all-zero — only set the column
    # when the category is NOT the baseline.

    # market_regime — baseline = "bear"
    if market_return <= -0.10:
        market_regime = "crash"
    elif market_return <= -0.03:
        market_regime = "bear"      # baseline → all zeros
    elif market_return <= 0.03:
        market_regime = "neutral"
    elif market_return <= 0.10:
        market_regime = "bull"
    else:
        market_regime = "rally"
    for cat in ("bull", "crash", "neutral", "rally"):
        row[f"market_regime_{cat}"] = int(market_regime == cat)

    # loss_magnitude — baseline = "gain"
    if unrealized_gl < -0.20:
        loss_mag = "severe_loss"
    elif unrealized_gl < -0.10:
        loss_mag = "large_loss"
    elif unrealized_gl < -0.05:
        loss_mag = "small_loss"
    elif unrealized_gl < 0.0:
        loss_mag = "no_loss"
    else:
        loss_mag = "gain"           # baseline → all zeros
    for cat in ("large_loss", "no_loss", "severe_loss", "small_loss"):
        row[f"loss_magnitude_{cat}"] = int(loss_mag == cat)

    # crowd_pressure — baseline = "contrarian"
    if crowd_ratio <= 0.30:
        crowd_cat = "contrarian"    # baseline → all zeros
    elif crowd_ratio <= 0.50:
        crowd_cat = "mixed"
    elif crowd_ratio <= 0.70:
        crowd_cat = "moderate_herd"
    else:
        crowd_cat = "strong_herd"
    for cat in ("mixed", "moderate_herd", "strong_herd"):
        row[f"crowd_pressure_{cat}"] = int(crowd_cat == cat)

    # financial_strategy — baseline = "investing"
    for cat in ("credit_card", "family_support", "saving"):
        row[f"financial_strategy_{cat}"] = int(financial_strategy == cat)

    # crash_speed — baseline = first alphabetical not present in cols
    # cols present: gradual_bear, normal, rapid_decline  → baseline = (crash? or something else)
    for cat in ("gradual_bear", "normal", "rapid_decline"):
        row[f"crash_speed_{cat}"] = int(crash_speed == cat)

    # secondary_biases — baseline = disposition or overconfidence (first alpha)
    for cat in ("loss_aversion", "none", "overconfidence"):
        row[f"secondary_biases_{cat}"] = int(secondary_biases == cat)

    # age_horizon_mismatch  — single column (old_long = 1 if mismatch)
    row["age_horizon_mismatch_old_long"] = int(
        age_horizon_mismatch == "old_long" or (age >= 55 and investment_horizon >= 15)
    )

    # investment_experience — baseline = "beginner"
    for cat in ("intermediate", "novice"):
        row[f"investment_experience_{cat}"] = int(investment_experience == cat)

    # goal — single column present in model
    row["goal_wealth growth"] = int(goal == "wealth growth")

    # ── 3. Align to exact training column order ───────────────────────
    input_df = pd.DataFrame([row])
    for col in _feature_cache:
        if col not in input_df.columns:
            input_df[col] = 0
    input_df = input_df[_feature_cache]

    t0         = time.time()
    proba      = _model_cache.predict_proba(input_df)[0]
    pred_label = int(np.argmax(proba))
    elapsed_ms = (time.time() - t0) * 1000

    confidence  = float(proba[pred_label])
    bias_name   = BIAS_LABELS.get(pred_label, f"class_{pred_label}")
    is_biased   = bias_name != "rational"

    explanation = _build_explanation(bias_name, unrealized_gl, crowd_ratio, market_return)

    return {
        "bias_type"     : bias_name,
        "confidence"    : round(confidence, 4),
        "probabilities" : {BIAS_LABELS.get(i, str(i)): round(float(p), 4) for i, p in enumerate(proba)},
        "is_biased"     : is_biased,
        "explanation"   : explanation,
        "inference_ms"  : round(elapsed_ms, 2),
    }


def _build_explanation(bias_name: str, gl: float, crowd: float, market: float) -> str:
    """Human-readable explanation for detected bias."""
    if bias_name == "loss_aversion":
        return (
            f"⚠️ Loss Aversion Detected: Your portfolio is down {gl*100:.1f}%. "
            f"Research shows you feel this loss ~2× as intensely as an equivalent gain. "
            f"This emotional pain may be triggering a sell impulse — not rational analysis."
        )
    elif bias_name == "herd":
        return (
            f"⚠️ Herd Mentality Detected: {crowd*100:.0f}% of participants are selling. "
            f"You may be following the crowd instead of your own investment plan. "
            f"Markets often bottom when fear peaks."
        )
    elif bias_name == "disposition":
        return (
            f"⚠️ Disposition Effect Detected: You appear to be selling winners too early "
            f"or holding losers too long (current P&L: {gl*100:.1f}%). "
            f"This is the most common behavioral bias in retail investors."
        )
    else:
        return "✅ Rational Decision: No significant behavioral bias detected."


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def run_pipeline(tune: bool = False) -> None:
    print("\n" + "═" * 55)
    print("  GAP 1 | Bias Detection Training Pipeline")
    print("═" * 55)

    X_train, X_test, y_train, y_test = load_data()
    model = train_model(X_train, y_train, tune=tune)

    # Collect unique class names from training labels (ordered)
    label_names = [BIAS_LABELS.get(i, str(i)) for i in sorted(np.unique(y_train))]
    results     = evaluate_model(model, X_test, y_test, label_names)

    save_model(model, list(X_train.columns))
    print(f"\n🏆 Final Accuracy: {results['accuracy']*100:.2f}%")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    import sys
    tune_flag = "--tune" in sys.argv
    run_pipeline(tune=tune_flag)
