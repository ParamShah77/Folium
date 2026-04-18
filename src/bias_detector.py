"""
GAP 1 – Week 2-3: Bias Detection Model (XGBoost)
==================================================
Trains a multi-class classifier to detect 4 bias types:
  0 = disposition
  1 = herd
  2 = loss_aversion
  3 = rational

CORRECT TRAINING ORDER (NO DATA LEAKAGE):
  Step 1: Load raw synthetic_decisions.csv  (already has 400 herd samples)
  Step 2: Feature engineering via data_preparation pipeline
  Step 3: Train/test split with stratify=y  FIRST  (test_size=0.20)
  Step 4: Apply SMOTE ONLY on (X_train, y_train)  — k_neighbors=3
  Step 5: Train XGBoost on resampled training data
  Step 6: Evaluate on ORIGINAL (non-resampled) test set
  Step 7: Save new model to models/bias_detector_xgboost.pkl
  Step 8: Save processed features and indices to data/processed/

Outputs:
  models/bias_detector_xgboost.pkl
  results/figures/confusion_matrix.png
  results/figures/feature_importance.png
  results/figures/shap_summary.png

Run:
    python src/bias_detector.py
"""

import os
import pickle
import sys
import time
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.utils.class_weight import compute_sample_weight

# ── SHAP (per-prediction explanations) ────────────────────────────────
try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:
    _SHAP_AVAILABLE = False

# ── SMOTE (fix class imbalance on training split only) ────────────────
try:
    from imblearn.over_sampling import SMOTE
    _SMOTE_AVAILABLE = True
except ImportError:
    _SMOTE_AVAILABLE = False

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED    = os.path.join(ROOT, "data", "processed")
MODELS_DIR   = os.path.join(ROOT, "models")
FIGURES_DIR  = os.path.join(ROOT, "results", "figures")
REPORTS_DIR  = os.path.join(ROOT, "results", "reports")
os.makedirs(MODELS_DIR,  exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(PROCESSED,   exist_ok=True)

MODEL_PATH    = os.path.join(MODELS_DIR, "bias_detector_xgboost.pkl")     # v1 — kept for load_model() explicit calls
MODEL_PATH_V2 = os.path.join(MODELS_DIR, "bias_detector_xgboost_v2.pkl")
MODEL_PATH_V3 = os.path.join(MODELS_DIR, "bias_detector_xgboost_v3.pkl")  # v3 — current default

# Columns to exclude from features (targets, IDs, leakage-prone profile cols)
EXCLUDE = {
    "bias_label", "decision_label", "decision", "bias_type",
    "bias_present", "user_id", "decision_id",
    "disposition_strength_profile", "loss_aversion_profile",
    "herd_sensitivity_profile",
}

BIAS_LABELS = {0: "disposition", 1: "herd", 2: "loss_aversion", 3: "rational"}

# Model hyperparameters (fixed per spec)
XGBOOST_PARAMS = dict(
    objective              = "multi:softprob",
    n_estimators           = 400,
    max_depth              = 3,
    learning_rate          = 0.03,
    subsample              = 0.8,
    colsample_bytree       = 0.8,
    min_child_weight       = 10,
    reg_alpha              = 0.5,
    reg_lambda             = 4.0,
    early_stopping_rounds  = 30,
    eval_metric            = "mlogloss",
    random_state           = 42,
    n_jobs                 = -1,
    use_label_encoder      = False,
)

# ─────────────────────────────────────────────────────────────────────
# Internal cache for loaded model (lazy)
# ─────────────────────────────────────────────────────────────────────
_model_cache:   xgb.XGBClassifier | None = None
_feature_cache: list[str]         | None = None


def _fill_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill missing values without changing feature schema.
    - numeric columns: median
    - non-numeric columns: mode (or "unknown" if mode unavailable)
    """
    df = df.copy()

    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    for col in num_cols:
        if df[col].isna().any():
            med = df[col].median()
            if pd.isna(med):
                med = 0.0
            df[col] = df[col].fillna(med)

    obj_cols = df.select_dtypes(exclude=["number", "bool"]).columns.tolist()
    for col in obj_cols:
        if df[col].isna().any():
            mode_vals = df[col].mode(dropna=True)
            fill_val = mode_vals.iloc[0] if len(mode_vals) else "unknown"
            df[col] = df[col].fillna(fill_val)

    return df

# ═══════════════════════════════════════════════════════════
# STEP 1-3: LOAD & SPLIT (called by training pipeline only)
# ═══════════════════════════════════════════════════════════

def _load_and_split_raw(
    test_size: float  = 0.20,
    random_state: int = 42,
    preserve_existing_test_indices: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, list[str]]:
    """
    Load raw synthetic_decisions.csv → feature-engineer → stratified split.

    IMPORTANT: split happens BEFORE any oversampling so there is zero
    data leakage between training and test sets.

    Returns
    -------
    X_train, X_test : DataFrames (original counts, no SMOTE yet)
    y_train, y_test : ndarrays of integer bias_label
    feature_cols    : list of feature column names
    """
    # Add data_preparation to path so we can reuse its engineering logic
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from data_preparation import (
        load_raw_data,
        merge_datasets,
        engineer_features,
        encode_labels,
        CATEGORICAL_FEATURES,
    )

    print("\n═" * 28)
    print("  Step 1-3: Load → Engineer → Split")
    print("═" * 28)

    decisions, users, bias_profiles = load_raw_data()
    df = merge_datasets(decisions, users, bias_profiles)
    df = engineer_features(df)
    df, label_mappings = encode_labels(df)

    print(f"\n   Label mappings: {label_mappings}")
    print(f"   Full dataset bias_label distribution:")
    print(f"   {df['bias_label'].value_counts().to_dict()}")

    # Convert boolean columns to int
    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    df[bool_cols] = df[bool_cols].astype(int)

    # Fill missing values before encoding / split so SMOTE can run cleanly.
    df = _fill_missing_values(df)

    # One-hot encode categorical features
    obj_cols = [
        c for c in df.select_dtypes(exclude=["number", "bool"]).columns
        if c not in EXCLUDE
    ]
    if obj_cols:
        df[obj_cols] = df[obj_cols].astype(str)
        df = pd.get_dummies(df, columns=obj_cols, drop_first=True)

    feature_cols = [c for c in df.columns if c not in EXCLUDE]
    X = df[feature_cols].astype(float)
    y = df["bias_label"].astype(int)

    test_idx_path = os.path.join(PROCESSED, "test_indices.npy")
    train_idx_path = os.path.join(PROCESSED, "train_indices.npy")

    # ── STEP 3: Split FIRST — preserve prior test indices if available ─
    if preserve_existing_test_indices and os.path.exists(test_idx_path):
        existing_test_idx = np.load(test_idx_path)
        valid_test_idx = np.array(
            sorted(set(int(i) for i in existing_test_idx if int(i) in X.index)),
            dtype=int,
        )
        if len(valid_test_idx) > 0:
            test_idx_set = set(valid_test_idx.tolist())
            train_idx = np.array([int(i) for i in X.index if int(i) not in test_idx_set], dtype=int)
            X_train, X_test = X.loc[train_idx], X.loc[valid_test_idx]
            y_train, y_test = y.loc[train_idx], y.loc[valid_test_idx]
            print(f"   ✅ Preserved existing test split: {len(valid_test_idx)} test rows")
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_size,
                random_state=random_state,
                stratify=y,
            )
            np.save(test_idx_path, X_test.index.to_numpy())
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y,
        )
        np.save(test_idx_path, X_test.index.to_numpy())

    # Always refresh train indices so new rows are included in training only.
    np.save(train_idx_path, X_train.index.to_numpy())

    # Save fresh merged features for notebooks
    df.to_csv(os.path.join(PROCESSED, "merged_features.csv"), index=False)
    print(f"   ✅ Saved merged_features.csv ({df.shape})")

    print(f"\n   Train size (before SMOTE): {X_train.shape}  |  Test size: {X_test.shape}")
    print(f"   Train class dist: {dict(pd.Series(y_train).value_counts().sort_index())}")
    print(f"   Test  class dist: {dict(pd.Series(y_test).value_counts().sort_index())}")

    return (
        X_train, X_test,
        y_train.to_numpy(), y_test.to_numpy(),
        list(X_train.columns),
    )


# ═══════════════════════════════════════════════════════════
# STEP 4: SMOTE — on training split ONLY
# ═══════════════════════════════════════════════════════════

def _apply_smote(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    k_neighbors: int = 3,
    random_state: int = 42,
) -> tuple[pd.DataFrame, np.ndarray]:
    """
    Apply SMOTE to (X_train, y_train) only.
    Balances all classes to match the majority class count.
    k_neighbors=3 is robust even for small minority classes.

    NOTE: SMOTE is NEVER applied to the test set. The test set keeps its
    original class distribution for honest evaluation.
    """
    if not _SMOTE_AVAILABLE:
        warnings.warn(
            "imbalanced-learn not installed — SMOTE skipped. "
            "Run: pip install imbalanced-learn",
            stacklevel=2,
        )
        return X_train, y_train

    counts_before = dict(zip(*np.unique(y_train, return_counts=True)))
    print(f"\n   Class counts before SMOTE: {counts_before}")

    smote = SMOTE(random_state=random_state, k_neighbors=k_neighbors)
    try:
        X_res, y_res = smote.fit_resample(X_train, y_train)
        X_res = pd.DataFrame(X_res, columns=X_train.columns)
        counts_after = dict(zip(*np.unique(y_res, return_counts=True)))
        print(f"   Class counts after  SMOTE: {counts_after}")
        herd_id = [k for k, v in BIAS_LABELS.items() if v == "herd"][0]
        print(f"   Herd samples in train:     {counts_after.get(herd_id, 0)}")
        return X_res, y_res
    except Exception as exc:
        warnings.warn(f"SMOTE failed ({exc}), using original training data", stacklevel=2)
        return X_train, y_train


# ═══════════════════════════════════════════════════════════
# LOAD DATA (for inference / notebooks — loads from processed/)
# ═══════════════════════════════════════════════════════════

def load_data(
    apply_smote: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Load processed merged_features.csv and saved train/test indices.
    Applies SMOTE on the training split only.

    Returns
    -------
    X_train : DataFrame — SMOTE-resampled training features
    X_test  : DataFrame — original test features (no oversampling)
    y_train : ndarray   — SMOTE-resampled training labels
    y_test  : ndarray   — original test labels
    """
    df        = pd.read_csv(os.path.join(PROCESSED, "merged_features.csv"))
    train_idx = np.load(os.path.join(PROCESSED, "train_indices.npy"))
    test_idx  = np.load(os.path.join(PROCESSED, "test_indices.npy"))

    # Convert boolean columns to int
    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    df[bool_cols] = df[bool_cols].astype(int)

    # Ensure no NaN values remain before optional SMOTE.
    df = _fill_missing_values(df)

    # One-hot encode non-numeric columns (not in EXCLUDE)
    obj_cols = [
        c for c in df.select_dtypes(exclude=["number", "bool"]).columns
        if c not in EXCLUDE
    ]
    if obj_cols:
        df[obj_cols] = df[obj_cols].astype(str)
        df = pd.get_dummies(df, columns=obj_cols, drop_first=True)

    feature_cols = [c for c in df.columns if c not in EXCLUDE]
    X = df[feature_cols].astype(float)
    y = df["bias_label"].astype(int)

    X_train = X.loc[train_idx]
    X_test  = X.loc[test_idx]
    y_train = y.loc[train_idx]
    y_test  = y.loc[test_idx]

    print(f"✅ Train (before SMOTE): {X_train.shape}, Test: {X_test.shape}")
    print(f"   Classes: {sorted(y.unique())}  |  "
          f"Train balance: {y_train.value_counts().to_dict()}")

    if apply_smote:
        # Optional only: use when class scarcity is severe.
        X_train, y_train = _apply_smote(X_train, y_train.to_numpy())
        y_train = np.asarray(y_train)
    else:
        y_train = y_train.to_numpy()

    return X_train, X_test, y_train, y_test.to_numpy()


# ═══════════════════════════════════════════════════════════
# STEP 5: TRAIN
# ═══════════════════════════════════════════════════════════

def train_model(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
) -> xgb.XGBClassifier:
    """
        Train XGBoost classifier with internal validation split for early stopping.
        The test set is never used during fit.
    """
    n_classes  = len(np.unique(y_train))
    params     = {**XGBOOST_PARAMS, "num_class": n_classes}
    model      = xgb.XGBClassifier(**params)

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train,
        y_train,
        test_size=0.15,
        stratify=y_train,
        random_state=42,
    )

    sample_weight = compute_sample_weight(
        class_weight={0: 1.0, 1: 1.0, 2: 4.0, 3: 1.0},
        y=y_tr,
    )

    print(f"\n   🚀 Training XGBoost  (n_estimators={params['n_estimators']}, "
          f"lr={params['learning_rate']}, max_depth={params['max_depth']}) …")
    t0 = time.time()

    fit_kwargs: dict = {
        "sample_weight": sample_weight,
        "eval_set": [(X_val, y_val)],
        "verbose": False,
    }
    try:
        model.fit(X_tr, y_tr, **fit_kwargs)
    except TypeError:
        # Backward-compatible fallback for older XGBoost sklearn wrappers.
        model.set_params(early_stopping_rounds=None)
        fit_kwargs["callbacks"] = [xgb.callback.EarlyStopping(rounds=30, save_best=True)]
        model.fit(X_tr, y_tr, **fit_kwargs)
    elapsed = time.time() - t0
    best_iteration = getattr(model, "best_iteration", None)
    print(f"   Done in {elapsed:.1f}s  |  best_iteration={best_iteration if best_iteration is not None else 'N/A'}")
    if best_iteration is not None and best_iteration >= 450:
        print("   ⚠️  Early stopping is still late (>= 450) — review regularisation/data diversity.")

    return model


# ═══════════════════════════════════════════════════════════
# STEP 6: EVALUATE — test set only
# ═══════════════════════════════════════════════════════════

def evaluate_model(
    model:       xgb.XGBClassifier,
    X_train:     pd.DataFrame,
    y_train:     np.ndarray,
    X_test:      pd.DataFrame,
    y_test:      np.ndarray,
    label_names: list[str] | None = None,
) -> dict:
    """
    Evaluate model on test set, compute proper metrics, save figures.
    Also computes train accuracy to expose the overfitting gap.
    All evaluation is on the ORIGINAL (non-resampled) test set.
    """
    if label_names is None:
        label_names = [BIAS_LABELS.get(i, str(i)) for i in sorted(np.unique(y_test))]

    y_pred_test  = model.predict(X_test)
    y_pred_train = model.predict(X_train)

    test_acc  = accuracy_score(y_test,  y_pred_test)
    train_acc = accuracy_score(y_train, y_pred_train)
    gap       = train_acc - test_acc
    macro_f1  = f1_score(y_test, y_pred_test, average="macro")

    print(f"\n{'═'*55}")
    print(f"  📊 EVALUATION RESULTS — TEST SET ONLY")
    print(f"{'═'*55}")
    print(f"  Train Accuracy   : {train_acc:.4f}")
    print(f"  Test  Accuracy   : {test_acc:.4f}")
    overfitting_flag = "⚠️  OVERFITTING" if gap > 0.05 else "✅ OK"
    print(f"  Overfitting Gap  : {gap:.4f}  {overfitting_flag}")
    print(f"  Macro F1 Score   : {macro_f1:.4f}  ← report this in paper")

    print(f"\n  Classification Report (TEST SET):")
    cr = classification_report(
        y_test, y_pred_test,
        target_names=label_names,
        digits=4,
    )
    print(cr)

    # Warn for low-recall classes
    cr_dict = classification_report(
        y_test, y_pred_test,
        target_names=label_names,
        output_dict=True,
    )
    for cls in label_names:
        if cls in cr_dict and cr_dict[cls]["recall"] < 0.60:
            print(f"  ⚠️  WARNING: {cls} recall = {cr_dict[cls]['recall']:.4f} < 0.60")
        if cls in cr_dict and cr_dict[cls]["f1-score"] < 0.50:
            print(f"  ❌  WARNING: {cls} F1 = {cr_dict[cls]['f1-score']:.4f} < 0.50 — "
                  f"insufficient for reliable detection")

    # ── Confusion matrix (normalised) ────────────────────────────────
    cm_norm = confusion_matrix(y_test, y_pred_test, normalize="true")
    cm_raw  = confusion_matrix(y_test, y_pred_test)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, cm, title, fmt in zip(
        axes,
        [cm_norm, cm_raw],
        ["Confusion Matrix (Normalised)", "Confusion Matrix (Raw Counts)"],
        [".2%", "d"],
    ):
        import seaborn as sns
        sns.heatmap(
            cm, annot=True, fmt=fmt, cmap="Blues", ax=ax,
            xticklabels=label_names, yticklabels=label_names,
        )
        ax.set_title(title, fontsize=12)
        ax.set_ylabel("True Label")
        ax.set_xlabel("Predicted Label")
    plt.suptitle("Bias Detection — Confusion Matrices", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "confusion_matrix.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ Saved confusion_matrix.png")

    # ── Feature importance ────────────────────────────────────────────
    feat_imp = pd.Series(
        model.feature_importances_, index=X_test.columns
    ).sort_values(ascending=False)
    top_n = feat_imp.head(20)
    fig, ax = plt.subplots(figsize=(10, 7))
    top_n.plot(kind="barh", ax=ax, color="steelblue")
    ax.invert_yaxis()
    ax.set_title("Top 20 Feature Importances (XGBoost — gain)", fontsize=13)
    ax.set_xlabel("Importance (gain)")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "feature_importance.png"), dpi=150)
    plt.close(fig)
    print(f"  ✅ Saved feature_importance.png")

    return {
        "train_accuracy"        : train_acc,
        "test_accuracy"         : test_acc,
        "overfitting_gap"       : gap,
        "macro_f1"              : macro_f1,
        "classification_report" : cr_dict,
        "confusion_matrix_norm" : cm_norm.tolist(),
        "confusion_matrix_raw"  : cm_raw.tolist(),
        "feature_importance"    : feat_imp,
        "y_pred"                : y_pred_test,
    }


# ═══════════════════════════════════════════════════════════
# NEW: get_train_test_metrics()
# ═══════════════════════════════════════════════════════════

def get_train_test_metrics(
    model: xgb.XGBClassifier | None = None,
    X_train: pd.DataFrame | None = None,
    y_train: np.ndarray | None = None,
    X_test: pd.DataFrame | None = None,
    y_test: np.ndarray | None = None,
) -> dict:
    """
    Returns train vs test metrics for overfitting diagnosis.
    If arguments are omitted, data/model are loaded from disk.

    Returns
    -------
    dict with keys:
        train_accuracy, test_accuracy, overfitting_gap, macro_f1
    """
    feature_cols: list[str] | None = None
    if model is None or X_train is None or y_train is None or X_test is None or y_test is None:
        model, feature_cols = load_model()
        X_train, X_test, y_train, y_test = load_data()

    y_train = np.asarray(y_train)
    y_test = np.asarray(y_test)

    # Align columns only when loaded model bundle provides canonical order.
    if feature_cols is not None:
        for col in feature_cols:
            if col not in X_train.columns:
                X_train[col] = 0
            if col not in X_test.columns:
                X_test[col] = 0
        X_train = X_train[feature_cols]
        X_test = X_test[feature_cols]

    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    train_acc = accuracy_score(y_train, y_pred_train)
    test_acc = accuracy_score(y_test, y_pred_test)
    train_macro_f1 = f1_score(y_train, y_pred_train, average="macro")
    test_macro_f1 = f1_score(y_test, y_pred_test, average="macro")
    gap_acc = train_acc - test_acc
    gap_f1 = train_macro_f1 - test_macro_f1

    return {
        "train_accuracy": float(train_acc),
        "test_accuracy": float(test_acc),
        "train_macro_f1": float(train_macro_f1),
        "test_macro_f1": float(test_macro_f1),
        "overfitting_gap_acc": float(gap_acc),
        "overfitting_gap_f1": float(gap_f1),
        # Backward-compatible aliases
        "overfitting_gap": float(gap_acc),
        "macro_f1": float(test_macro_f1),
    }


# ═══════════════════════════════════════════════════════════
# NEW: get_classification_report()
# ═══════════════════════════════════════════════════════════

def get_classification_report() -> dict:
    """
    Returns sklearn classification_report as a dict on the TEST SET ONLY.
    Loads model + test data from processed/ files.

    Returns
    -------
    dict — same structure as sklearn classification_report(output_dict=True)
    """
    model, feature_cols = load_model()
    df        = pd.read_csv(os.path.join(PROCESSED, "merged_features.csv"))
    test_idx  = np.load(os.path.join(PROCESSED, "test_indices.npy"))

    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    df[bool_cols] = df[bool_cols].astype(int)
    df = _fill_missing_values(df)
    obj_cols = [
        c for c in df.select_dtypes(exclude=["number", "bool"]).columns
        if c not in EXCLUDE
    ]
    if obj_cols:
        df[obj_cols] = df[obj_cols].astype(str)
        df = pd.get_dummies(df, columns=obj_cols, drop_first=True)

    X_test = df[[c for c in df.columns if c not in EXCLUDE]].astype(float)
    X_test = X_test.loc[test_idx]
    y_test = df["bias_label"].astype(int).loc[test_idx].to_numpy()

    for col in feature_cols:
        if col not in X_test.columns:
            X_test[col] = 0
    X_test = X_test[feature_cols]

    y_pred = model.predict(X_test)
    label_names = [BIAS_LABELS.get(i, str(i)) for i in sorted(np.unique(y_test))]

    return classification_report(
        y_test, y_pred,
        target_names=label_names,
        output_dict=True,
        digits=4,
    )


# ═══════════════════════════════════════════════════════════
# SAVE / LOAD
# ═══════════════════════════════════════════════════════════

def save_model(
    model: xgb.XGBClassifier,
    feature_cols: list[str],
    model_path: str = MODEL_PATH,
) -> None:
    bundle = {"model": model, "feature_cols": feature_cols}
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"  ✅ Model saved → {model_path}")


def load_model(model_path: str = MODEL_PATH_V3) -> tuple[xgb.XGBClassifier, list[str]]:
    """Load a saved model bundle (model + feature_cols).

    Default path is v3 (47 features). Pass MODEL_PATH or MODEL_PATH_V2
    explicitly to load an older version for comparison.
    """
    with open(model_path, "rb") as f:
        bundle = pickle.load(f)
    return bundle["model"], bundle["feature_cols"]


# ═══════════════════════════════════════════════════════════
# REAL-TIME INFERENCE  ← The key API function
# ═══════════════════════════════════════════════════════════

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
    Builds the full 47-feature vector (v3 schema) and returns
    top 5 SHAP contributions from the retrained model.

    The 3 new v3 discriminating features are computed internally:
      crowd_influence_ratio   = crowd_ratio / |unrealized_gl|, clipped (0, 50)
      herd_pure_signal        = crowd_ratio × (1 − max(−unrealized_gl, 0))
      loss_crowd_interaction  = crowd_ratio × max(−unrealized_gl, 0)

    Returns
    -------
    dict with keys:
        bias_type, confidence, probabilities, is_biased,
        explanation, shap_explanation, inference_ms
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

    # ── 1b. Three new v3 discriminating features ──────────────────────
    # These are required by the v3 model (47-feature schema) and must be
    # added to 'row' BEFORE the column-alignment step (Step 3).
    loss_abs_rt = max(abs(unrealized_gl), 0.01)          # avoid division by zero
    row["crowd_influence_ratio"]  = min(crowd_ratio / loss_abs_rt, 50.0)   # clipped (0, 50)
    row["herd_pure_signal"]       = crowd_ratio * (1.0 - max(-unrealized_gl, 0.0))
    row["loss_crowd_interaction"] = crowd_ratio * max(-unrealized_gl, 0.0)

    # ── 2. OHE categorical features (match training bins exactly) ─────
    # market_regime — baseline = "bear"
    if market_return <= -0.10:
        market_regime = "crash"
    elif market_return <= -0.03:
        market_regime = "bear"
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
        loss_mag = "gain"
    for cat in ("large_loss", "no_loss", "severe_loss", "small_loss"):
        row[f"loss_magnitude_{cat}"] = int(loss_mag == cat)

    # crowd_pressure — baseline = "contrarian"
    if crowd_ratio <= 0.30:
        crowd_cat = "contrarian"
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

    # crash_speed
    for cat in ("gradual_bear", "normal", "rapid_decline"):
        row[f"crash_speed_{cat}"] = int(crash_speed == cat)

    # secondary_biases
    for cat in ("loss_aversion", "none", "overconfidence"):
        row[f"secondary_biases_{cat}"] = int(secondary_biases == cat)

    # age_horizon_mismatch
    row["age_horizon_mismatch_old_long"] = int(
        age_horizon_mismatch == "old_long" or (age >= 55 and investment_horizon >= 15)
    )

    # investment_experience — baseline = "beginner"
    for cat in ("intermediate", "novice"):
        row[f"investment_experience_{cat}"] = int(investment_experience == cat)

    # goal
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

    confidence = float(proba[pred_label])
    bias_name  = BIAS_LABELS.get(pred_label, f"class_{pred_label}")
    is_biased  = bias_name != "rational"

    explanation = _build_explanation(bias_name, unrealized_gl, crowd_ratio, market_return)

    # ── SHAP per-prediction explanations (top 5 from retrained model) ─
    shap_explanation: list[dict] = []
    if _SHAP_AVAILABLE:
        try:
            shap_explanation = _compute_shap_explanation(
                _model_cache, input_df, _feature_cache, top_n=5
            )
        except Exception as exc:
            shap_explanation = [{"error": str(exc)}]

    return {
        "bias_type"        : bias_name,
        "confidence"       : round(confidence, 4),
        "probabilities"    : {BIAS_LABELS.get(i, str(i)): round(float(p), 4)
                               for i, p in enumerate(proba)},
        "is_biased"        : is_biased,
        "explanation"      : explanation,
        "shap_explanation" : shap_explanation,
        "inference_ms"     : round(elapsed_ms, 2),
    }


def _build_explanation(bias_name: str, gl: float, crowd: float, market: float) -> str:
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
# SHAP EXPLANATION
# ═══════════════════════════════════════════════════════════

def _compute_shap_explanation(
    model: xgb.XGBClassifier,
    input_df: pd.DataFrame,
    feature_cols: list[str],
    top_n: int = 5,
) -> list[dict]:
    """
    Compute SHAP values for a single-row input_df.
    Returns top_n features by absolute SHAP impact (across classes).
    """
    if not _SHAP_AVAILABLE:
        return []

    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(input_df)

    # Normalize SHAP outputs to class-major form: (n_classes, n_samples, n_features)
    if isinstance(shap_vals, list):
        shap_arr = np.stack(shap_vals, axis=0)
    else:
        arr = np.asarray(shap_vals)
        if arr.ndim == 2:
            shap_arr = arr[np.newaxis, :, :]
        elif arr.ndim == 3:
            # Common shapes: (samples, features, classes) or (classes, samples, features)
            if arr.shape[1] == len(feature_cols):
                shap_arr = np.transpose(arr, (2, 0, 1))
            elif arr.shape[2] == len(feature_cols):
                shap_arr = arr
            else:
                raise ValueError(
                    f"Unexpected SHAP shape {arr.shape}; cannot locate feature axis of size {len(feature_cols)}"
                )
        else:
            raise ValueError(f"Unexpected SHAP dimensions: {arr.ndim}")

    flat = shap_arr[:, 0, :]
    avg_abs = np.mean(np.abs(flat), axis=0)
    top_class_shap = flat[np.argmax(np.sum(np.abs(flat), axis=1))]

    top_indices = np.argsort(avg_abs)[::-1][:top_n]
    result = []
    for idx in top_indices:
        feat   = feature_cols[idx]
        val    = float(input_df.iloc[0, idx])
        impact = float(top_class_shap[idx])
        result.append({
            "feature"    : feat,
            "value"      : round(val,    4),
            "shap_impact": round(impact, 4),
            "direction"  : "increases_bias" if impact > 0 else "decreases_bias",
        })
    return result


def get_shap_summary(X_test: pd.DataFrame) -> None:
    """
    Generate global SHAP summary bar plot for the test set.
    Saves to results/figures/shap_summary.png.
    """
    if not _SHAP_AVAILABLE:
        print("shap not installed — run: pip install shap")
        return

    model, feature_cols = load_model()

    # Align X_test to model features
    for col in feature_cols:
        if col not in X_test.columns:
            X_test[col] = 0
    X_test = X_test[feature_cols]

    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X_test)

    # Verify SHAP feature axis matches feature count across output formats.
    shap_for_plot = shap_vals
    if isinstance(shap_vals, list):
        assert shap_vals[0].shape[1] == len(feature_cols), \
            f"SHAP feature count mismatch: {shap_vals[0].shape[1]} vs {len(feature_cols)}"
    else:
        arr = np.asarray(shap_vals)
        if arr.ndim == 2:
            assert arr.shape[1] == len(feature_cols), \
                f"SHAP feature count mismatch: {arr.shape[1]} vs {len(feature_cols)}"
        elif arr.ndim == 3:
            if arr.shape[1] == len(feature_cols):
                # (samples, features, classes) -> list[class] for plotting
                shap_for_plot = [arr[:, :, i] for i in range(arr.shape[2])]
            elif arr.shape[2] == len(feature_cols):
                # Already class-major
                shap_for_plot = [arr[i, :, :] for i in range(arr.shape[0])]
            else:
                raise AssertionError(
                    f"SHAP feature count mismatch for shape {arr.shape} and {len(feature_cols)} features"
                )
        else:
            raise AssertionError(f"Unexpected SHAP dimensions: {arr.ndim}")

    plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_for_plot, X_test, plot_type="bar",
        class_names=list(BIAS_LABELS.values()),
        show=False,
    )
    out = os.path.join(FIGURES_DIR, "shap_summary.png")
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✅ SHAP summary saved → {out}")


# ═══════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════

def run_pipeline(
    tune: bool = False,
    output_model_path: str = MODEL_PATH,
    output_report_path: str | None = None,
    apply_smote: bool = False,
) -> None:
    """
    Full correct training pipeline with NO data leakage.

    Order:
      1. Load raw synthetic_decisions.csv → feature engineering
      2. Stratified train/test split (FIRST)
      3. SMOTE on training split only (k_neighbors=3)
      4. Train XGBoost with early stopping
      5. Evaluate on original test set (no SMOTE)
      6. Save model + processed data
      7. Generate SHAP summary plot
    """
    import json

    print("\n" + "═" * 55)
    print("  GAP 1 | Bias Detection Training Pipeline")
    print("  CORRECT ORDER: Split First → SMOTE on Train → Train")
    print("═" * 55)

    # Steps 1-3: Load raw → engineer → split
    X_train_raw, X_test, y_train_raw, y_test, feature_cols = _load_and_split_raw(
        preserve_existing_test_indices=True
    )

    # Step 4: Optional SMOTE on training split only
    if apply_smote:
        print("\n  Step 4: Apply SMOTE on training split ONLY…")
        X_train, y_train = _apply_smote(X_train_raw, y_train_raw, k_neighbors=3)
    else:
        print("\n  Step 4: Skip heavy SMOTE (using root-cause data fix + cost-sensitive weighting)…")
        X_train, y_train = X_train_raw, y_train_raw

    # Step 5: Train
    print("\n  Step 5: Train XGBoost…")
    model = train_model(X_train, y_train)

    # Step 6: Evaluate on original test set
    print("\n  Step 6: Evaluate on original (non-resampled) test set…")
    label_names = [BIAS_LABELS.get(i, str(i)) for i in sorted(np.unique(y_test))]
    results = evaluate_model(model, X_train, y_train, X_test, y_test, label_names)

    # 5-fold CV on training data with a CV-safe estimator (no early-stopping requirement).
    cv_params = {k: v for k, v in {**XGBOOST_PARAMS, "num_class": len(np.unique(y_train))}.items() if k != "early_stopping_rounds"}
    cv_model = xgb.XGBClassifier(**cv_params)
    cv_scores = cross_val_score(
        cv_model,
        X_train,
        y_train,
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
        scoring="f1_macro",
        n_jobs=-1,
    )
    cv_macro_f1_mean = float(np.mean(cv_scores))
    cv_macro_f1_std = float(np.std(cv_scores))
    print(f"  📈 5-fold CV Macro F1: {cv_macro_f1_mean:.4f} ± {cv_macro_f1_std:.4f}")

    # Step 7: Save model
    print("\n  Step 7: Save model…")
    save_model(model, feature_cols, model_path=output_model_path)

    # Save evaluation report
    train_test_metrics = get_train_test_metrics(model, X_train, y_train, X_test, y_test)
    report = {
        "train_accuracy"  : results["train_accuracy"],
        "test_accuracy"   : results["test_accuracy"],
        "overfitting_gap" : results["overfitting_gap"],
        "macro_f1"        : results["macro_f1"],
        "train_macro_f1"  : train_test_metrics["train_macro_f1"],
        "test_macro_f1"   : train_test_metrics["test_macro_f1"],
        "overfitting_gap_f1": train_test_metrics["overfitting_gap_f1"],
        "best_iteration"  : getattr(model, "best_iteration", None),
        "cv_macro_f1_mean": cv_macro_f1_mean,
        "cv_macro_f1_std": cv_macro_f1_std,
        "classification_report": {
            k: v for k, v in results["classification_report"].items()
        },
        "confusion_matrix_normalised": results["confusion_matrix_norm"],
        "confusion_matrix_raw"       : results["confusion_matrix_raw"],
    }
    report_path = output_report_path or os.path.join(ROOT, "results", "model_evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  ✅ Evaluation report saved → {report_path}")

    # Step 8: SHAP summary
    print("\n  Step 8: Generate SHAP summary…")
    if _SHAP_AVAILABLE:
        try:
            get_shap_summary(X_test)
        except Exception as exc:
            print(f"  ⚠️  SHAP failed: {exc}")
    else:
        print("  ⚠️  shap not installed — skipping SHAP summary")

    print(f"\n{'═'*55}")
    print(f"  🏆 Final Test Accuracy : {results['test_accuracy']*100:.2f}%")
    print(f"  🏆 Macro F1            : {results['macro_f1']*100:.2f}%")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train bias detector model.")
    parser.add_argument(
        "--v2",
        action="store_true",
        help="Save to v2 artifacts (bias_detector_xgboost_v2.pkl and model_evaluation_report_v2.json).",
    )
    parser.add_argument(
        "--apply-smote",
        action="store_true",
        help="Enable SMOTE on training split (disabled by default for v2).",
    )
    args = parser.parse_args()

    if args.v2:
        run_pipeline(
            output_model_path=MODEL_PATH_V2,
            output_report_path=os.path.join(ROOT, "results", "model_evaluation_report_v2.json"),
            apply_smote=args.apply_smote,
        )
    else:
        run_pipeline(apply_smote=args.apply_smote)
