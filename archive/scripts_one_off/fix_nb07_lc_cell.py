"""
Targeted fix: Replace the lc_plot_nb07 cell with a corrected version
that reads cv_v3 from report_v3 JSON (already available from Cell 1)
instead of the cv_v3 variable defined later in Cell 12.
"""
import json, os

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path   = os.path.join(ROOT, "notebooks", "07_final_evaluation.ipynb")
nb     = json.load(open(path, encoding="utf-8"))

CORRECTED_LC_CELL_SOURCE = [
    "# Fix 6B: Learning curve plot -- more reliable than single internal split\n",
    "# NOTE: cv_v3 is defined in Cell 12; we read from report_v3 here to avoid\n",
    "# forward-reference NameError. report_v3 is loaded in Cell 1.\n",
    "import xgboost as xgb\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "from sklearn.model_selection import learning_curve, StratifiedKFold\n",
    "\n",
    "# Build a CV-compatible estimator (no early_stopping_rounds)\n",
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
    "\n",
    "# Read from JSON (already loaded in Cell 1) -- avoids forward-reference to cv_v3\n",
    "_cv_f1_from_json  = float(report_v3.get('cv_macro_f1_mean', 0))\n",
    "_test_f1_from_json = float(report_v3.get('macro_f1', 0))\n",
    "_generalisation_gap = abs(_cv_f1_from_json - _test_f1_from_json)\n",
    "\n",
    "_face2 = '#fdecea' if _lc_gap_cv > 0.10 else '#eafaf1'\n",
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
    "ax2.text(0.5, 0.06,\n",
    "         f'LC gap at full data: {_lc_gap_cv:.3f}  '\n",
    "         f'| Internal split gap: {gap_macro_internal:.4f}',\n",
    "         transform=ax2.transAxes, ha='center', fontsize=10,\n",
    "         bbox=dict(boxstyle='round', facecolor=_face2))\n",
    "ax2.set_title('Learning Curves -- v3 (Macro F1, 5-Fold CV)', fontweight='bold')\n",
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
    "print(f'Internal split gap (single):              {gap_macro_internal:.4f}')\n",
    "print(f'LC-based gap (5-fold learning curve):     {_lc_gap_cv:.4f}')\n",
    "print(f'Actual generalisation gap (CV vs Test):   {_generalisation_gap:.4f}  <- most reliable')\n",
    "print(f'  CV F1  = {_cv_f1_from_json:.4f}  |  Test F1 = {_test_f1_from_json:.4f}')\n",
    "print('The CV-to-Test gap is the honest measure of generalisation.')\n",
]

fixed = 0
for i, cell in enumerate(nb["cells"]):
    src = "".join(cell.get("source", []))
    if cell["cell_type"] == "code" and "Fix 6B: Learning curve plot" in src:
        cell["source"] = CORRECTED_LC_CELL_SOURCE
        fixed += 1
        print(f"  Fixed LC cell at index {i}")
        break

if fixed == 0:
    print("  ERROR: LC cell not found")

with open(path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"  Saved NB07 ({len(nb['cells'])} cells)")
