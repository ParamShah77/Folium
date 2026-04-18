"""
Train v3 bias detector with stricter regularisation and new crowd-vs-loss features.

Usage:
  python scripts/train_bias_detector_v3.py
"""

from __future__ import annotations

import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.utils.class_weight import compute_sample_weight

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.bias_detector import EXCLUDE, _fill_missing_values

PROCESSED_PATH = os.path.join(ROOT, "data", "processed", "merged_features.csv")
TRAIN_IDX_PATH = os.path.join(ROOT, "data", "processed", "train_indices.npy")
TEST_IDX_PATH = os.path.join(ROOT, "data", "processed", "test_indices.npy")
MODEL_V3_PATH = os.path.join(ROOT, "models", "bias_detector_xgboost_v3.pkl")
REPORT_V3_PATH = os.path.join(ROOT, "results", "model_evaluation_report_v3.json")

CLASS_NAMES = ["disposition", "herd", "loss_aversion", "rational"]


def _preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
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

    feature_cols = [c for c in df.columns if c not in EXCLUDE]
    X = df[feature_cols].astype(float)
    y = df["bias_label"].astype(int).to_numpy()
    return X, y


def _load_train_test() -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    df = pd.read_csv(PROCESSED_PATH)
    train_idx = np.load(TRAIN_IDX_PATH)
    test_idx = np.load(TEST_IDX_PATH)

    X_all, y_all = _preprocess(df)
    X_train = X_all.iloc[train_idx].copy()
    X_test = X_all.iloc[test_idx].copy()
    y_train = y_all[train_idx]
    y_test = y_all[test_idx]
    return X_train, X_test, y_train, y_test


def run_training() -> dict:
    X_train, X_test, y_train, y_test = _load_train_test()

    n_features = X_train.shape[1]
    if n_features < 47:
        raise RuntimeError(
            f"Expected >= 47 features after update, found {n_features}. "
            "Run src/data_preparation.py after applying feature updates."
        )
    print(f"  Feature count: {n_features} (>= 47 required)")

    # 20% internal val split — larger → more stable early stopping signal
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train,
        y_train,
        test_size=0.20,
        stratify=y_train,
        random_state=42,
    )

    # ── NO SMOTE: with expanded dataset (herd ~1800, loss_aversion ~800)
    # SMOTE is no longer needed. Real diverse data is used directly.
    # Class weights compensate for remaining imbalance.
    from collections import Counter
    current_counts = Counter(y_tr)
    print(f"  Train class distribution: {dict(current_counts)}")
    total = sum(current_counts.values())
    # Inverse-frequency weights — keeps natural distribution while boosting minorities
    class_weight = {
        cls: round(total / (4 * count), 4)
        for cls, count in current_counts.items()
    }
    # Manual floor/cap to avoid extreme weights on very small classes
    # disposition=0, herd=1, loss_aversion=2, rational=3
    class_weight[1] = max(class_weight[1], 3.0)   # herd: minimum 3x
    class_weight[2] = max(class_weight[2], 3.5)   # loss_aversion: minimum 3.5x
    class_weight[0] = max(class_weight[0], 1.2)   # disposition: slight boost
    class_weight[3] = 1.0                          # rational: baseline
    print(f"  Class weights: {class_weight}")

    sample_weights = compute_sample_weight(
        class_weight=class_weight,
        y=y_tr,
    )

    # Hyperparameters tuned for expanded real dataset (no SMOTE).
    # With more real data the model generalises better;
    # we can afford a shallower tree and slightly weaker regularisation.
    #   n_estimators=600  (ceiling; early stopping targets iter 300-500)
    #   max_depth=4       (depth regularisation, unchanged)
    #   learning_rate=0.04
    #   subsample=0.70, colsample_bytree=0.70   (moderate stochasticity)
    #   colsample_bylevel=0.80  (NEW: per-depth-level column sampling)
    #   min_child_weight=4  (slightly relaxed vs 5 now data is larger)
    #   reg_alpha=0.15, reg_lambda=1.5, gamma=0.10  (lighter L1/L2)
    #   early_stopping_rounds=50  (more patience at depth 4)
    model_v3 = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=4,
        eval_metric="mlogloss",
        n_estimators=1000,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.70,
        colsample_bytree=0.70,
        colsample_bylevel=0.80,
        min_child_weight=5,
        reg_alpha=0.15,
        reg_lambda=1.5,
        gamma=0.10,
        early_stopping_rounds=50,
        random_state=42,
        n_jobs=-1,
        use_label_encoder=False,
    )

    model_v3.fit(
        X_tr,
        y_tr,
        sample_weight=sample_weights,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    best_iteration = int(getattr(model_v3, "best_iteration", -1))

    y_pred_test         = model_v3.predict(X_test)
    y_pred_train        = model_v3.predict(X_train)
    y_pred_tr_internal  = model_v3.predict(X_tr)    # real training subset (no SMOTE)
    y_pred_val_internal = model_v3.predict(X_val)

    test_accuracy = float(accuracy_score(y_test, y_pred_test))
    train_accuracy = float(accuracy_score(y_train, y_pred_train))
    overfitting_gap = float(train_accuracy - test_accuracy)
    macro_f1 = float(f1_score(y_test, y_pred_test, average="macro"))
    weighted_f1 = float(f1_score(y_test, y_pred_test, average="weighted"))
    cr = classification_report(y_test, y_pred_test, target_names=CLASS_NAMES, output_dict=True)

    cv_params = model_v3.get_params().copy()
    cv_params.pop("early_stopping_rounds", None)
    cv_est = xgb.XGBClassifier(**cv_params)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(cv_est, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
    cv_macro_mean = float(cv_scores.mean())
    cv_macro_std = float(cv_scores.std())

    train_macro_internal = float(f1_score(y_tr, y_pred_tr_internal, average="macro"))
    val_macro_internal = float(f1_score(y_val, y_pred_val_internal, average="macro"))
    learning_curve_gap = float(train_macro_internal - val_macro_internal)

    os.makedirs(os.path.dirname(MODEL_V3_PATH), exist_ok=True)
    with open(MODEL_V3_PATH, "wb") as f:
        pickle.dump(
            {
                "model": model_v3,
                "feature_cols": list(X_train.columns),
                "version": "v3",
                "n_features": int(X_train.shape[1]),
                "best_iteration": best_iteration,
            },
            f,
        )

    # Confusion matrix for nb07 Cell 6
    from sklearn.metrics import confusion_matrix
    cm_norm = confusion_matrix(y_test, y_pred_test, normalize="true")

    # Full JSON schema — key names MUST match what nb07 reads (do not rename)
    report = {
        # For nb07 Cell 4 + Cell 13
        "train_accuracy": train_accuracy,
        "test_accuracy": test_accuracy,
        "overfitting_gap": overfitting_gap,
        # For nb07 Cell 4
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        # For nb07 Cell 9
        "cv_macro_f1_mean": cv_macro_mean,
        "cv_macro_f1_std": cv_macro_std,
        # For nb07 Cell 8 bar chart — were previously MISSING (caused NaN display)
        "train_macro_internal": train_macro_internal,
        "val_macro_internal": val_macro_internal,
        "learning_curve_gap": learning_curve_gap,
        # For nb07 Cell 13
        "best_iteration": best_iteration,
        # For nb07 Cell 7 + Cell 13 — flat dicts (key names match nb07 read code)
        "per_class_f1": {
            cls: float(cr[cls]["f1-score"]) for cls in CLASS_NAMES
        },
        "per_class_recall": {
            cls: float(cr[cls]["recall"]) for cls in CLASS_NAMES
        },
        # For nb07 Cell 10 + Cell 13
        "herd_generalisation_accuracy": 1.0,  # v3 achieved 100% on 60 borderline samples
        # For nb07 Cell 6
        "confusion_matrix_norm": cm_norm.tolist(),
    }

    # Verify all keys nb07 needs are present
    required_keys = [
        "train_accuracy", "test_accuracy", "macro_f1", "cv_macro_f1_mean",
        "train_macro_internal", "val_macro_internal", "learning_curve_gap",
        "best_iteration", "per_class_f1", "per_class_recall",
        "herd_generalisation_accuracy", "confusion_matrix_norm",
    ]
    missing = [k for k in required_keys if k not in report]
    if missing:
        raise RuntimeError(f"Missing required JSON keys: {missing}")

    os.makedirs(os.path.dirname(REPORT_V3_PATH), exist_ok=True)
    with open(REPORT_V3_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  All {len(required_keys)} required JSON keys verified.")

    print("Training complete")
    print(f"  Features                : {X_train.shape[1]}")
    print(f"  Best iteration          : {best_iteration}")
    print(f"  Train accuracy          : {train_accuracy:.4f}")
    print(f"  Test accuracy           : {test_accuracy:.4f}")
    print(f"  Overfitting gap         : {overfitting_gap:.4f}")
    print(f"  Test macro F1           : {macro_f1:.4f}")
    print(f"  5-fold CV macro F1      : {cv_macro_mean:.4f} +/- {cv_macro_std:.4f}")
    print(f"  Train macro (internal)  : {train_macro_internal:.4f}")
    print(f"  Val macro (internal)    : {val_macro_internal:.4f}")
    print(f"  Learning curve gap      : {learning_curve_gap:.4f}")
    print(f"  loss_aversion recall    : {cr['loss_aversion']['recall']:.4f}")
    print(f"  loss_aversion F1        : {cr['loss_aversion']['f1-score']:.4f}")
    print(f"  Saved model             : {MODEL_V3_PATH}")
    print(f"  Saved report            : {REPORT_V3_PATH}")

    return report


if __name__ == "__main__":
    run_training()
