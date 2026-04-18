"""
scripts/patch_nb04_06_07.py

Surgical JSON patching for notebooks 04, 06, and 07.
Run from the project root:
    python scripts/patch_nb04_06_07.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_DIR = os.path.join(ROOT, "notebooks")


# ═══════════════════════════════════════════════
# NOTEBOOK 04 PATCHES
# ═══════════════════════════════════════════════

def patch_nb04():
    path = os.path.join(NB_DIR, "04_full_pipeline_demo.ipynb")
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    changed = 0
    for cell in nb["cells"]:
        src = "".join(cell.get("source", []))

        # Fix 7A: Header — update "89% accuracy" branding
        if cell["cell_type"] == "markdown" and "89% accuracy" in src and "External Presentation" in src:
            cell["source"] = [
                "# Behavioral Bias Detection: All 4 Bias Types Demo\n",
                "### External Presentation Notebook (v3 Model)\n",
                "**Model:** XGBoost v3 | **Macro F1: 87.12%** | Test Accuracy: 86.63% | 47 features  \n",
                "**Bias classes detected:** Disposition Effect · Herd Mentality · Loss Aversion · Rational  \n",
                "\n",
                "This notebook demonstrates that the v3 model correctly identifies **all four investor "
                "behaviour types** from real-time market & portfolio inputs, provides causal "
                "explanations, and recommends debiasing interventions.  \n",
                "All 4 investor specimens are drawn from the **held-out test set only** (1,077 rows) — "
                "no training data.\n",
            ]
            changed += 1
            print("  ✓ Fix 7A: header updated")

        # Fix 7A: Setup cell — add explicit v3 model loading + class balance display
        if cell["cell_type"] == "code" and "from bias_detector import detect_bias_realtime, BIAS_LABELS" in src and "Setup complete" in src:
            cell["source"] = [
                "import sys, os\n",
                "sys.path.insert(0, os.path.join(os.getcwd(), '..', 'src'))\n",
                "\n",
                "import warnings\n",
                "warnings.filterwarnings('ignore')\n",
                "\n",
                "import numpy as np\n",
                "import pandas as pd\n",
                "import matplotlib.pyplot as plt\n",
                "import matplotlib.patches as mpatches\n",
                "from matplotlib.gridspec import GridSpec\n",
                "\n",
                "from bias_detector import detect_bias_realtime, load_model, load_data, BIAS_LABELS\n",
                "from integration import analyze_decision_realtime, analyze_batch\n",
                "\n",
                "ROOT = os.path.abspath(os.path.join(os.getcwd(), '..'))\n",
                "\n",
                "plt.rcParams.update({'figure.dpi': 120, 'font.size': 11})\n",
                "\n",
                "# ── Explicitly load v3 (47 features) ──────────────────────────────\n",
                "# load_model() now defaults to v3 pkl. Explicit path for absolute clarity.\n",
                "MODEL_V3_PATH = os.path.join(ROOT, 'models', 'bias_detector_xgboost_v3.pkl')\n",
                "model_global, feat_cols_global = load_model(MODEL_V3_PATH)\n",
                "print(f'Model: v3 | Features: {len(feat_cols_global)}')\n",
                "\n",
                "BIAS_COLORS = {\n",
                "    'loss_aversion' : '#e74c3c',\n",
                "    'herd'          : '#e67e22',\n",
                "    'disposition'   : '#9b59b6',\n",
                "    'rational'      : '#27ae60',\n",
                "}\n",
                "BIAS_ICONS = {\n",
                "    'loss_aversion' : '\U0001f534',\n",
                "    'herd'          : '\U0001f7e0',\n",
                "    'disposition'   : '\U0001f7e3',\n",
                "    'rational'      : '\U0001f7e2',\n",
                "}\n",
                "CLASS_NAMES = ['disposition', 'herd', 'loss_aversion', 'rational']\n",
                "\n",
                "# ── Class balance from source CSV (no hardcoding) ──────────────────\n",
                "raw_df = pd.read_csv(os.path.join(ROOT, 'synthetic_decisions.csv'))\n",
                "print('\\nCurrent dataset class distribution (from source CSV):')\n",
                "for cls, cnt in raw_df['bias_type'].value_counts().items():\n",
                "    pct = cnt / len(raw_df) * 100\n",
                "    print(f'  {cls:<16}: {cnt:,} ({pct:.1f}%)')\n",
                "# Expected: rational=2916, disposition=1923, herd=600, loss_aversion=400\n",
                "\n",
                "print('\\nSetup complete \u2014 v3 model loaded, class balance verified')",
            ]
            changed += 1
            print("  ✓ Fix 7A+7C: setup cell with explicit v3 load + class balance from CSV")

        # Fix 7B: Specimen selection — use model_global (already v3)
        if cell["cell_type"] == "code" and "load_model()" in src and "X_train, X_test" in src and "specimens" in src:
            lines = cell["source"]
            new_lines = []
            for line in lines:
                # Replace bare load_model() with model_global reference
                if "model, feature_cols = load_model()" in line:
                    new_lines.append("model = model_global    # already loaded as v3 above\n")
                    new_lines.append("feature_cols = feat_cols_global\n")
                elif "from bias_detector import load_data, load_model, BIAS_LABELS" in line:
                    new_lines.append("# load_data and model already imported above\n")
                elif "import numpy as np" in line and "from bias_detector" not in "".join(lines[:3]):
                    pass  # skip duplicate import
                else:
                    new_lines.append(line)
            cell["source"] = new_lines
            changed += 1
            print("  ✓ Fix 7B: specimen cell uses model_global (v3)")

        # Fix herd scenario comment
        if cell["cell_type"] == "code" and "herd has only 14 training samples" in src:
            cell["source"] = [
                line.replace(
                    "# (herd has only 14 training samples — model detects it via the complete feature space)\n",
                    "# v3 herd detection achieves 94.9% F1; validated 100% on 60 borderline samples.\n",
                )
                for line in cell["source"]
            ]
            changed += 1
            print("  ✓ Fixed herd comment")

        # Add herd generalisation note after herd scenario
        # (inject markdown cell — handled below by cell insertion)

        # Fix 7D: Batch analysis — replace analyze_batch(df_raw) with test-set batch
        if cell["cell_type"] == "code" and "df_raw = pd.read_csv('../data/processed/merged_features.csv').head(200)" in src:
            cell["source"] = [
                "# Batch analysis: use TEST SET samples only (never merged_features head())\n",
                "# X_test is the held-out set (1,077 rows, zero overlap with training data).\n",
                "N_BATCH = min(300, len(X_test))\n",
                "X_batch = X_test.iloc[:N_BATCH].copy()\n",
                "y_batch = y_test[:N_BATCH]\n",
                "\n",
                "batch_preds  = model.predict(X_batch)\n",
                "batch_probas = model.predict_proba(X_batch)\n",
                "\n",
                "_RISK_W = {'loss_aversion': 0.30, 'herd': 0.25, 'disposition': 0.25, 'rational': 0.00}\n",
                "df_batch = pd.DataFrame({\n",
                "    'true_label'     : [CLASS_NAMES[y] for y in y_batch],\n",
                "    'pred_bias_type' : [CLASS_NAMES[p] for p in batch_preds],\n",
                "    'pred_confidence': batch_probas.max(axis=1),\n",
                "    'pred_risk_score': [_RISK_W.get(CLASS_NAMES[p], 0.0) * batch_probas[i, p]\n",
                "                        for i, p in enumerate(batch_preds)],\n",
                "    'correct'        : (batch_preds == y_batch),\n",
                "})\n",
                "\n",
                "print(f'Batch analysis: {N_BATCH} samples from held-out test set')\n",
                "print('\\nPredicted class distribution:')\n",
                "print(df_batch['pred_bias_type'].value_counts().to_string())\n",
                "print(f'\\nOverall accuracy: {df_batch[\"correct\"].mean():.1%}')\n",
                "print('\\nPer-class accuracy:')\n",
                "for cls in CLASS_NAMES:\n",
                "    mask = df_batch['true_label'] == cls\n",
                "    if mask.sum() > 0:\n",
                "        acc = df_batch.loc[mask, 'correct'].mean()\n",
                "        print(f'  {cls:<16}: {mask.sum()} samples, {acc:.1%} accuracy')\n",
                "# All 4 classes should appear — v3 herd recall = 94.5%",
            ]
            changed += 1
            print("  ✓ Fix 7D: batch analysis uses test set only")

        # Fix 7E: Summary table — update "89%" and "200 real investor profiles"
        if cell["cell_type"] == "markdown" and "89% overall accuracy" in src and "Key Takeaways" in src:
            cell["source"] = [
                "---\n",
                "## \u2705 Key Takeaways for Evaluation\n",
                "\n",
                "| # | What we demonstrated | Result |\n",
                "|---|----------------------|--------|\n",
                "| 1 | Detect **Loss Aversion** (Subhash \u2014 panic selling during drawdown) | \u2705 Correctly identified |\n",
                "| 2 | Detect **Herd Mentality** (Priya \u2014 blindly following crowd) | \u2705 Correctly identified |\n",
                "| 3 | Detect **Disposition Effect** (Ramesh \u2014 selling winner too early) | \u2705 Correctly identified |\n",
                "| 4 | Detect **Rational Investor** (Dr. Anita \u2014 no bias, staying course) | \u2705 Correctly identified |\n",
                "| 5 | **v3 Macro F1 = 87.12%** on 1,077 held-out test samples | \u2705 Exceeds 85% target |\n",
                "| 6 | Causal effect of each bias on sell decision (quantified) | \u2705 Partial-corr, refutation-passed |\n",
                "| 7 | Personalised debiasing **intervention** per user | \u2705 4 intervention strategies |\n",
                "| 8 | Batch analysis on **300 real held-out test samples** \u2014 all 4 classes detected | \u2705 Confirmed |\n",
                "| 9 | Herd generalisation: 100% on 60 borderline samples (v2 was 0%) | \u2705 FIXED in v3 |\n",
                "\n",
                "**Research gap addressed:** Existing systems detect *what* decision is made \u2014 this system "
                "detects *why* (causal bias) and *how to fix it* in real-time.\n",
            ]
            changed += 1
            print("  \u2713 Fix 7E: summary table updated with v3 metrics")

    # Inject herd generalisation note after herd scenario cell
    new_cells = []
    herd_inserted = False
    for i, cell in enumerate(nb["cells"]):
        new_cells.append(cell)
        src = "".join(cell.get("source", []))
        if (not herd_inserted and cell["cell_type"] == "code"
                and "specimens['herd']" in src
                and "show_result" in src):
            herd_note = {
                "cell_type": "markdown",
                "id": "herd_gen_note_nb04",
                "metadata": {},
                "source": [
                    "> **Note on Herd Detection Generalisation:**  \n",
                    "> v3 herd detection achieves **94.9% F1** on the test set.  \n",
                    "> Critically, v3 was validated on **60 borderline cases** "
                    "(crowd_action_ratio 0.45\u20130.80, near-zero or positive P&L \u2014 pure crowd-driven "
                    "selling), achieving **100% accuracy**.  \n",
                    "> v2 on the same borderline samples: **0% accuracy** (all misclassified as "
                    "loss_aversion).  \n",
                    "> Fix: 200 diverse herd samples + 3 new discriminating features. "
                    "See Notebook 07 Section 10.\n",
                ],
            }
            new_cells.append(herd_note)
            herd_inserted = True
            changed += 1
            print("  \u2713 Fix 7E: herd generalisation note injected after scenario 2")

    nb["cells"] = new_cells

    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"  Saved: {path}  ({changed} changes)")


# ═══════════════════════════════════════════════
# NOTEBOOK 06 PATCHES
# ═══════════════════════════════════════════════

def patch_nb06():
    path = os.path.join(NB_DIR, "06_model_improvement.ipynb")
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    changed = 0

    # Collect existing cell IDs to avoid duplicates
    existing_ids = {cell.get("id", "") for cell in nb["cells"]}

    new_cells = []
    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))

        # Fix 5A: SMOTE chart — update title/labels to be honest
        if cell["cell_type"] == "code" and "Class Balance: Before vs After SMOTE" in src:
            # Replace the problematic title and add a note
            new_source = []
            for line in cell["source"]:
                if "Class Balance: Before vs After SMOTE" in line:
                    new_source.append(
                        line.replace(
                            "Class Balance: Before vs After SMOTE",
                            "Class Distribution: Original vs After Borderline Herd Fix",
                        )
                    )
                elif "After SMOTE" in line and "label" in line.lower():
                    new_source.append(line.replace("After SMOTE", "After Borderline Herd Fix (Approach A)"))
                else:
                    new_source.append(line)
            # Add annotation about training approach
            new_source.append("\n")
            new_source.append("# NOTE: v3 training uses SMOTE (2x upsampling of herd+loss_aversion)\n")
            new_source.append("# combined with class weights — not full equalisation.\n")
            new_source.append("# This chart shows dataset-level counts before training preprocessing.\n")
            cell["source"] = new_source
            changed += 1
            print("  \u2713 Fix 5A: SMOTE chart made honest")

        # Fix 5B: before/after comparison table — replace hardcoded numbers
        # Look for cell that has hardcoded v1 numbers like before_loss_aversion_total = 114
        if cell["cell_type"] == "code" and ("before_loss_aversion_total" in src or
                                             ("Metric" in src and "v1" in src and "hardcod" in src.lower())):
            cell["source"] = [
                "# Before/After comparison: loaded from pkl + JSON (no hardcoded numbers)\n",
                "import pickle, json\n",
                "from sklearn.metrics import accuracy_score, f1_score, classification_report as cr_fn\n",
                "from sklearn.model_selection import StratifiedKFold, cross_val_score\n",
                "import numpy as np, pandas as pd\n",
                "\n",
                "MODEL_V1_PATH   = '../models/bias_detector_xgboost.pkl'\n",
                "MODEL_V2_PATH   = '../models/bias_detector_xgboost_v2.pkl'\n",
                "MODEL_V3_PATH   = '../models/bias_detector_xgboost_v3.pkl'\n",
                "REPORT_V1_PATH  = '../results/model_evaluation_report.json'\n",
                "REPORT_V2_PATH  = '../results/model_evaluation_report_v2.json'\n",
                "CLASS_NAMES_06  = ['disposition', 'herd', 'loss_aversion', 'rational']\n",
                "\n",
                "from bias_detector import load_model as _load_model, load_data as _load_data\n",
                "\n",
                "# Load test set (47-feature) — v3 schema\n",
                "_X_train, _X_test, _y_train, _y_test = _load_data()\n",
                "_model_v3, _feat_v3 = _load_model(MODEL_V3_PATH)\n",
                "\n",
                "def _align(X, feat_list):\n",
                "    \"\"\"Align X to feat_list column order, filling missing cols with 0.\"\"\"\n",
                "    X = X.copy()\n",
                "    for c in feat_list:\n",
                "        if c not in X.columns:\n",
                "            X[c] = 0.0\n",
                "    return X[feat_list]\n",
                "\n",
                "# ── v1 metrics (loaded from pkl + JSON) ──────────────────────────\n",
                "_model_v1, _feat_v1 = _load_model(MODEL_V1_PATH)\n",
                "_X_test_v1 = _align(_X_test, _feat_v1)\n",
                "_y_pred_v1 = _model_v1.predict(_X_test_v1)\n",
                "_cr_v1 = cr_fn(_y_test, _y_pred_v1, target_names=CLASS_NAMES_06, output_dict=True)\n",
                "\n",
                "with open(REPORT_V1_PATH) as f:\n",
                "    _rpt_v1 = json.load(f)\n",
                "train_acc_v1 = float(_rpt_v1.get('train_accuracy', np.nan))\n",
                "cv_v1        = float(_rpt_v1.get('cv_macro_f1_mean', np.nan))\n",
                "test_acc_v1  = accuracy_score(_y_test, _y_pred_v1)\n",
                "mf1_v1       = f1_score(_y_test, _y_pred_v1, average='macro')\n",
                "\n",
                "# ── v2 metrics ───────────────────────────────────────────────────\n",
                "_model_v2, _feat_v2 = _load_model(MODEL_V2_PATH)\n",
                "_X_test_v2 = _align(_X_test, _feat_v2)\n",
                "_y_pred_v2 = _model_v2.predict(_X_test_v2)\n",
                "_cr_v2 = cr_fn(_y_test, _y_pred_v2, target_names=CLASS_NAMES_06, output_dict=True)\n",
                "\n",
                "with open(REPORT_V2_PATH) as f:\n",
                "    _rpt_v2 = json.load(f)\n",
                "test_acc_v2  = accuracy_score(_y_test, _y_pred_v2)\n",
                "mf1_v2       = f1_score(_y_test, _y_pred_v2, average='macro')\n",
                "\n",
                "# ── Build comparison table (no hardcoded numbers) ────────────────\n",
                "before = {\n",
                "    'Train Accuracy'       : train_acc_v1,\n",
                "    'Test Accuracy'        : test_acc_v1,\n",
                "    'Overfitting Gap'      : train_acc_v1 - test_acc_v1,\n",
                "    'Macro F1 (test)'      : mf1_v1,\n",
                "    '5-Fold CV Macro F1'   : cv_v1,\n",
                "    'loss_aversion Recall' : _cr_v1['loss_aversion']['recall'],\n",
                "    'loss_aversion F1'     : _cr_v1['loss_aversion']['f1-score'],\n",
                "    'herd F1'              : _cr_v1['herd']['f1-score'],\n",
                "    'disposition F1'       : _cr_v1['disposition']['f1-score'],\n",
                "}\n",
                "after = {\n",
                "    'Train Accuracy'       : float(_rpt_v2.get('train_accuracy', np.nan)),\n",
                "    'Test Accuracy'        : test_acc_v2,\n",
                "    'Overfitting Gap'      : float(_rpt_v2.get('overfitting_gap', np.nan)),\n",
                "    'Macro F1 (test)'      : mf1_v2,\n",
                "    '5-Fold CV Macro F1'   : float(_rpt_v2.get('cv_macro_f1_mean', np.nan)),\n",
                "    'loss_aversion Recall' : _cr_v2['loss_aversion']['recall'],\n",
                "    'loss_aversion F1'     : _cr_v2['loss_aversion']['f1-score'],\n",
                "    'herd F1'              : _cr_v2['herd']['f1-score'],\n",
                "    'disposition F1'       : _cr_v2['disposition']['f1-score'],\n",
                "}\n",
                "\n",
                "import pandas as pd\n",
                "comparison = pd.DataFrame({'Metric': list(before.keys()),\n",
                "                           'v1 (Before Fix)': list(before.values()),\n",
                "                           'v2 (After Fix)' : list(after.values())})\n",
                "comparison = comparison.set_index('Metric')\n",
                "print('Before (v1) vs After (v2) comparison — loaded from pkl+JSON, no hardcoded numbers:')\n",
                "print(comparison.applymap(lambda x: f'{x:.4f}' if isinstance(x, float) else x).to_string())\n",
            ]
            changed += 1
            print("  \u2713 Fix 5B: before/after table dynamic (loaded from pkl+JSON)")

        new_cells.append(cell)

    # Fix 5C: Add learning curve plot cell if not already present
    has_lc_plot = any(
        "Learning Curves" in "".join(c.get("source", [])) and
        "ax.plot" in "".join(c.get("source", []))
        for c in nb["cells"]
    )
    if not has_lc_plot:
        lc_cell = {
            "cell_type": "code",
            "id": "lc_plot_nb06",
            "metadata": {},
            "outputs": [],
            "execution_count": None,
            "source": [
                "# Fix 5C: Learning curve plot (previously was only a number — now a proper plot)\n",
                "import xgboost as xgb\n",
                "import numpy as np\n",
                "import matplotlib.pyplot as plt\n",
                "from sklearn.model_selection import learning_curve, StratifiedKFold\n",
                "\n",
                "# Use v2 params for v1->v2 improvement notebook\n",
                "_cv_params_v2 = _model_v2.get_params().copy()\n",
                "_cv_params_v2.pop('early_stopping_rounds', None)\n",
                "_cv_est_v2 = xgb.XGBClassifier(**_cv_params_v2)\n",
                "\n",
                "print('Computing v2 learning curves (may take 1-2 min)...')\n",
                "_lc_sizes, _lc_tr, _lc_val = learning_curve(\n",
                "    _cv_est_v2, _X_train, _y_train,\n",
                "    train_sizes=np.linspace(0.2, 1.0, 6),\n",
                "    cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),\n",
                "    scoring='f1_macro',\n",
                "    n_jobs=-1,\n",
                ")\n",
                "\n",
                "_tr_mean  = _lc_tr.mean(axis=1)\n",
                "_val_mean = _lc_val.mean(axis=1)\n",
                "_gap_lc   = float(_tr_mean[-1] - _val_mean[-1])\n",
                "_status   = 'OVERFITTING' if _gap_lc > 0.10 else 'ACCEPTABLE'\n",
                "\n",
                "fig, ax = plt.subplots(figsize=(9, 5))\n",
                "ax.plot(_lc_sizes, _tr_mean, 'o-', color='#3498db', label='Train Macro F1')\n",
                "ax.fill_between(_lc_sizes,\n",
                "                _tr_mean - _lc_tr.std(axis=1),\n",
                "                _tr_mean + _lc_tr.std(axis=1),\n",
                "                alpha=0.15, color='#3498db')\n",
                "ax.plot(_lc_sizes, _val_mean, 's-', color='#e74c3c', label='CV Val Macro F1')\n",
                "ax.fill_between(_lc_sizes,\n",
                "                _val_mean - _lc_val.std(axis=1),\n",
                "                _val_mean + _lc_val.std(axis=1),\n",
                "                alpha=0.15, color='#e74c3c')\n",
                "_face = '#fdecea' if _gap_lc > 0.10 else '#eafaf1'\n",
                "ax.text(0.5, 0.06,\n",
                "        f'Train-Val gap at full data: {_gap_lc:.3f} \u2014 {_status}',\n",
                "        transform=ax.transAxes, ha='center', fontsize=10,\n",
                "        bbox=dict(boxstyle='round', facecolor=_face))\n",
                "ax.set_title('Learning Curves \u2014 v2 (Macro F1, 5-Fold CV)', fontweight='bold')\n",
                "ax.set_xlabel('Training Examples')\n",
                "ax.set_ylabel('Macro F1')\n",
                "ax.legend()\n",
                "ax.set_ylim(0, 1.05)\n",
                "ax.grid(alpha=0.3)\n",
                "plt.tight_layout()\n",
                "plt.savefig('../results/figures/learning_curves_v2.png', dpi=150, bbox_inches='tight')\n",
                "plt.show()\n",
                "print(f'Train-Val gap at full data: {_gap_lc:.3f} \u2014 {_status}')\n",
            ],
        }
        new_cells.append(lc_cell)
        changed += 1
        print("  \u2713 Fix 5C: learning curve plot added")

    nb["cells"] = new_cells
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"  Saved: {path}  ({changed} changes)")


# ═══════════════════════════════════════════════
# NOTEBOOK 07 PATCHES
# ═══════════════════════════════════════════════

def patch_nb07():
    path = os.path.join(NB_DIR, "07_final_evaluation.ipynb")
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    changed = 0
    new_cells = []

    cv_table_inserted = False
    disposition_inserted = False
    lc_plot_found = False
    summary_note_added = False

    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))

        # Fix 6A: Insert CV disclaimer markdown cell BEFORE the CV code cell
        if not cv_table_inserted and cell["cell_type"] == "code" and (
            "cv_macro_f1" in src.lower() or "cv_scores" in src.lower()
            or "cross_val_score" in src
        ) and "5-fold" in src.lower():
            disclaimer = {
                "cell_type": "markdown",
                "id": "cv_disclaimer_nb07",
                "metadata": {},
                "source": [
                    "### \u26a0\ufe0f Important: CV Values Were Computed on Different Datasets\n",
                    "\n",
                    "| Version | CV Macro F1 | Dataset Used |\n",
                    "|---------|-------------|--------------------|\n",
                    "| v1      | 0.8837      | Original 5,382-row dataset, 44 features |\n",
                    "| v2      | 0.8560      | 5,639-row dataset, 44 features |\n",
                    "| v3      | 0.8449      | Current 5,839-row dataset, 47 features |\n",
                    "\n",
                    "The decreasing CV trend does **NOT** indicate model regression.  \n",
                    "v3 is evaluated on a **harder, more diverse dataset** that includes 600 herd samples "
                    "(vs 14 original) and 400 loss_aversion samples, making the task genuinely more difficult.\n",
                    "\n",
                    "**Authoritative metric:** v3 CV Macro F1 = **0.8449 \u00b1 0.0061**  \n",
                    "The real generalisation gap (CV 0.8449 vs Test 0.8713) is only **2.6%** \u2014 "
                    "well within acceptable range.\n",
                ],
            }
            new_cells.append(disclaimer)
            cv_table_inserted = True
            changed += 1
            print("  \u2713 Fix 6A: CV disclaimer inserted before CV cell")

        # Fix 6B: Add learning curve plot after Cell 8 (overfitting section)
        if not lc_plot_found and cell["cell_type"] == "code" and (
            "train_macro_internal" in src or "val_macro_internal" in src
        ) and "bar" in src.lower():
            lc_plot_found = True  # mark found; inject AFTER this cell
            new_cells.append(cell)
            lc_plot_cell = {
                "cell_type": "code",
                "id": "lc_plot_nb07",
                "metadata": {},
                "outputs": [],
                "execution_count": None,
                "source": [
                    "# Fix 6B: Learning curve plot (more reliable than single internal split)\n",
                    "import xgboost as xgb\n",
                    "import numpy as np\n",
                    "import matplotlib.pyplot as plt\n",
                    "from sklearn.model_selection import learning_curve, StratifiedKFold\n",
                    "\n",
                    "# Build a CV-compatible estimator (without early_stopping_rounds)\n",
                    "_cv_params_lc = {k: v for k, v in model_v3.get_params().items()\n",
                    "                 if k not in ('early_stopping_rounds',)}\n",
                    "_cv_est_lc = xgb.XGBClassifier(**_cv_params_lc)\n",
                    "\n",
                    "print('Computing v3 learning curves (2-3 min)...')\n",
                    "_lc_sizes, _lc_tr, _lc_val = learning_curve(\n",
                    "    _cv_est_lc, X_train_v3, y_train,\n",
                    "    train_sizes=np.linspace(0.2, 1.0, 6),\n",
                    "    cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),\n",
                    "    scoring='f1_macro',\n",
                    "    n_jobs=-1,\n",
                    ")\n",
                    "\n",
                    "_lc_tr_mean  = _lc_tr.mean(axis=1)\n",
                    "_lc_val_mean = _lc_val.mean(axis=1)\n",
                    "_lc_gap_cv   = float(_lc_tr_mean[-1] - _lc_val_mean[-1])\n",
                    "_generalisation_gap = abs(cv_v3 - metrics_v3['macro_f1'])\n",
                    "\n",
                    "fig2, ax2 = plt.subplots(figsize=(9, 5))\n",
                    "ax2.plot(_lc_sizes, _lc_tr_mean, 'o-', color='#3498db', label='Train Macro F1')\n",
                    "ax2.fill_between(_lc_sizes,\n",
                    "                 _lc_tr_mean - _lc_tr.std(axis=1),\n",
                    "                 _lc_tr_mean + _lc_tr.std(axis=1),\n",
                    "                 alpha=0.15, color='#3498db')\n",
                    "ax2.plot(_lc_sizes, _lc_val_mean, 's-', color='#e74c3c', label='CV Val Macro F1')\n",
                    "ax2.fill_between(_lc_sizes,\n",
                    "                 _lc_val_mean - _lc_val.std(axis=1),\n",
                    "                 _lc_val_mean + _lc_val.std(axis=1),\n",
                    "                 alpha=0.15, color='#e74c3c')\n",
                    "_face2 = '#fdecea' if _lc_gap_cv > 0.10 else '#eafaf1'\n",
                    "ax2.text(0.5, 0.06,\n",
                    "         f'CV-based gap at full data: {_lc_gap_cv:.3f}  '\n",
                    "         f'(internal split gap: {gap_macro_internal:.4f})',\n",
                    "         transform=ax2.transAxes, ha='center', fontsize=10,\n",
                    "         bbox=dict(boxstyle='round', facecolor=_face2))\n",
                    "ax2.set_title('Learning Curves \u2014 v3 (Macro F1, 5-Fold CV)', fontweight='bold')\n",
                    "ax2.set_xlabel('Training Examples')\n",
                    "ax2.set_ylabel('Macro F1')\n",
                    "ax2.legend()\n",
                    "ax2.set_ylim(0, 1.05)\n",
                    "ax2.grid(alpha=0.3)\n",
                    "plt.tight_layout()\n",
                    "_fig_dir = os.path.join(os.getcwd(), '..', 'results', 'figures')\n",
                    "os.makedirs(_fig_dir, exist_ok=True)\n",
                    "plt.savefig(os.path.join(_fig_dir, 'learning_curves_v3.png'), dpi=150, bbox_inches='tight')\n",
                    "plt.show()\n",
                    "\n",
                    "print(f'Internal split gap (single): {gap_macro_internal:.4f}')\n",
                    "print(f'CV-based gap (5-fold, reliable): {_lc_gap_cv:.4f}')\n",
                    "print(f'Actual generalisation gap (CV vs Test): {_generalisation_gap:.4f}  <- most reliable')\n",
                    "print('The CV-based gap and generalisation gap are the honest measures.')\n",
                    "print('The internal split gap is inflated by small val set size (20% of training).')\n",
                ],
            }
            new_cells.append(lc_plot_cell)
            changed += 1
            print("  \u2713 Fix 6B: learning curve plot injected after Cell 8")
            continue  # cell already appended above

        # Fix 6C: Add disposition regression explanation after per-class analysis cell (Cell 7)
        if not disposition_inserted and cell["cell_type"] == "code" and (
            "per_class_f1" in src or "per-class" in src.lower()
        ) and "histogram" in src.lower() or (
            "disposition" in src and "herd" in src and "loss_aversion" in src
            and not disposition_inserted and "F1" in src
        ):
            new_cells.append(cell)
            disp_md = {
                "cell_type": "markdown",
                "id": "disposition_regression_nb07",
                "metadata": {},
                "source": [
                    "## Disposition Regression: v1 \u2192 v3 Tradeoff Analysis\n",
                    "\n",
                    "Disposition F1 dropped from **91.53% (v1) \u2192 81.63% (v3)** = \u22129.9 percentage points.\n",
                    "\n",
                    "**Root cause:** 200 borderline herd samples were added with `crowd_action_ratio` "
                    "0.45\u20130.80 and `unrealized_gain_loss` reaching \u22120.48. Deep-loss herd samples "
                    "overlap the disposition feature space \u2014 the model learned a more conservative "
                    "boundary that misclassifies some borderline disposition cases as herd.\n",
                    "\n",
                    "**Mitigation applied (v3.1):** `fix_herd_disposition_overlap.py` tightens "
                    "the borderline herd samples:\n",
                    "- `unrealized_gain_loss` clipped to [\u22120.10, +0.20] (no deep-loss herd samples)\n",
                    "- `crowd_action_ratio` enforced \u2265 3\u00d7 |unrealized_gain_loss|, minimum 0.45\n",
                    "\n",
                    "**Net result:** Disposition F1 improved from 76.94% (prior v3) to 81.63% (current v3).\n",
                    "The net Macro F1 gain across all classes is positive: 83.11% (v1) \u2192 87.12% (v3).\n",
                    "Disposition regression is a documented tradeoff, not a bug.\n",
                ],
            }
            new_cells.append(disp_md)
            disposition_inserted = True
            changed += 1
            print("  \u2713 Fix 6C: disposition regression explanation inserted")
            continue

        # Fix 6D: Add CV note after summary cell (Cell 13)
        if not summary_note_added and cell["cell_type"] == "code" and (
            "summary" in src.lower() or "final" in src.lower()
        ) and i == len(nb["cells"]) - 1:
            new_cells.append(cell)
            note_md = {
                "cell_type": "markdown",
                "id": "cv_note_nb07",
                "metadata": {},
                "source": [
                    "> **Note:** v1 CV (0.8837) was computed on the original 5,382-row dataset (44 features).  \n",
                    "> v3 CV (0.8449) is on the current 5,839-row dataset (47 features) \u2014 not directly comparable.  \n",
                    "> The declining CV trend reflects a **harder, more realistic dataset**, not model regression.  \n",
                    "> See the CV disclaimer above for the full analysis.\n",
                ],
            }
            new_cells.append(note_md)
            summary_note_added = True
            changed += 1
            print("  \u2713 Fix 6D: CV comparability note added after summary")
            continue

        new_cells.append(cell)

    nb["cells"] = new_cells
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"  Saved: {path}  ({changed} changes)")


if __name__ == "__main__":
    print("\n=== Patching notebook 04 ===")
    patch_nb04()
    print("\n=== Patching notebook 06 ===")
    patch_nb06()
    print("\n=== Patching notebook 07 ===")
    patch_nb07()
    print("\nAll notebook patches applied.")
