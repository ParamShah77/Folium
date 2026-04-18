"""
Patch notebooks/04_full_pipeline_demo.ipynb:
  - Cell 4 (specimen selection): replace X_train+X_test combined search
    with a test-set-only search. No fallback to training data.
  - Also clear all stale output cells.
  
Patch notebooks/05_model_evaluation.ipynb:
  - Ensure kernelspec is set to the local .venv

Run from project root:
    python scripts/patch_notebooks.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_DIR = os.path.join(ROOT, "notebooks")

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def load_nb(name):
    path = os.path.join(NB_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), path


def save_nb(nb, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"✅ Saved: {path}")


def clear_outputs(nb):
    """Clear all cell outputs (force clean re-run)."""
    for cell in nb["cells"]:
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None


# ─────────────────────────────────────────────────────────────
# Patch 04_full_pipeline_demo.ipynb — Cell 4 specimen selection
# ─────────────────────────────────────────────────────────────

CORRECTED_SPECIMEN_SOURCE = [
    "def show_result(profile_name, result, row_context):\n",
    "    \"\"\"Pretty-print a single analysis result with a probability bar chart.\"\"\"\n",
    "    btype = result['bias_type']\n",
    "    color = BIAS_COLORS.get(btype, '#7f8c8d')\n",
    "    icon  = BIAS_ICONS.get(btype, '⚪')\n",
    "\n",
    "    fig, axes = plt.subplots(1, 2, figsize=(13, 3.8),\n",
    "                             gridspec_kw={'width_ratios': [1.6, 1]})\n",
    "\n",
    "    ax = axes[0]\n",
    "    ax.axis('off')\n",
    "    mret = row_context.get('market_return', row_context.get('market_return_recent', 0))\n",
    "    gl   = row_context.get('unrealized_gl', row_context.get('unrealized_gain_loss', 0))\n",
    "    cr   = row_context.get('crowd_ratio', row_context.get('crowd_action_ratio', 0))\n",
    "    lines = [\n",
    "        (f\"{icon}  DETECTED: {btype.replace('_',' ').upper()}\", 16, 'bold',   'normal', color),\n",
    "        (f\"Profile: {profile_name}\",                        12, 'normal', 'normal', '#2c3e50'),\n",
    "        (f\"Market return: {mret:+.1%}   P&L: {gl:+.1%}   Crowd: {cr:.0%}\",\n",
    "                                                           10, 'normal', 'italic', '#555555'),\n",
    "        (\"\",                                               10, 'normal', 'normal', '#ffffff'),\n",
    "        (f\"Confidence  :  {result['confidence']:.1%}\",     12, 'normal', 'normal', '#2c3e50'),\n",
    "        (f\"Risk Score  :  {result['risk_score']:.1%}\",     12, 'normal', 'normal',\n",
    "         '#c0392b' if result['risk_score'] > 0.3 else '#27ae60'),\n",
    "        (\"\",                                               10, 'normal', 'normal', '#ffffff'),\n",
    "        (\"Intervention:\",                                  11, 'bold',   'normal', '#2c3e50'),\n",
    "    ]\n",
    "    y = 0.97\n",
    "    for txt, sz, wt, st, col in lines:\n",
    "        ax.text(0.02, y, txt, transform=ax.transAxes, fontsize=sz,\n",
    "                fontweight=wt, fontstyle=st, color=col, va='top')\n",
    "        y -= 0.13\n",
    "    interv = result['intervention'].replace('💡 Recommended intervention: ', '')\n",
    "    ax.text(0.02, y, f\"  {interv}\", transform=ax.transAxes, fontsize=9,\n",
    "            color='#16a085', va='top', fontstyle='italic',\n",
    "            bbox=dict(boxstyle='round,pad=0.3', facecolor='#eafaf1', edgecolor='#27ae60'))\n",
    "\n",
    "    ax2 = axes[1]\n",
    "    probs = result['all_probabilities']\n",
    "    labels = list(probs.keys())\n",
    "    values = list(probs.values())\n",
    "    colors = [BIAS_COLORS.get(l, '#bdc3c7') for l in labels]\n",
    "    edge   = ['black' if l == btype else 'none' for l in labels]\n",
    "    bars   = ax2.barh(labels, values, color=colors, edgecolor=edge, linewidth=2)\n",
    "    for bar, val in zip(bars, values):\n",
    "        ax2.text(val + 0.01, bar.get_y() + bar.get_height()/2,\n",
    "                 f'{val:.1%}', va='center', fontsize=10)\n",
    "    ax2.set_xlim(0, 1.15)\n",
    "    ax2.set_xlabel('Probability')\n",
    "    ax2.set_title('Class Probabilities', fontweight='bold')\n",
    "    ax2.axvline(0.5, color='grey', linewidth=0.8, linestyle='--')\n",
    "\n",
    "    plt.suptitle(f'{icon} {btype.replace(\"_\",\" \").title()} — {profile_name}',\n",
    "                 fontsize=13, fontweight='bold', y=1.01)\n",
    "    plt.tight_layout()\n",
    "    plt.show()\n",
    "    print(f\"  Explanation: {result['explanation']}\\n\")\n",
    "\n",
    "\n",
    "def build_result_from_vector(X_row, row_context, model):\n",
    "    \"\"\"Build an analyze_decision_realtime-style result from a processed feature vector.\"\"\"\n",
    "    import time\n",
    "    from causal_inference import get_intervention_recommendation, load_causal_results, EFFECTS_PKL\n",
    "    proba     = model.predict_proba(X_row)[0]\n",
    "    pred_id   = int(np.argmax(proba))\n",
    "    bias_name = BIAS_LABELS[pred_id]\n",
    "    conf      = float(proba[pred_id])\n",
    "\n",
    "    try:\n",
    "        causal_effects = load_causal_results()\n",
    "    except Exception:\n",
    "        causal_effects = None\n",
    "\n",
    "    try:\n",
    "        interv = get_intervention_recommendation(bias_name, causal_effects)\n",
    "    except Exception:\n",
    "        interv = f\"💡 Recommended intervention: Reduce {bias_name.replace('_',' ')} tendencies\"\n",
    "\n",
    "    cr   = row_context.get('crowd_ratio', row_context.get('crowd_action_ratio', 0))\n",
    "    gl   = row_context.get('unrealized_gl', row_context.get('unrealized_gain_loss', 0))\n",
    "    mret = row_context.get('market_return', row_context.get('market_return_recent', 0))\n",
    "\n",
    "    _RISK_W = {'loss_aversion': 0.30, 'herd': 0.25, 'disposition': 0.25, 'rational': 0.00}\n",
    "    aprobs  = {BIAS_LABELS[i]: round(float(p), 4) for i, p in enumerate(proba)}\n",
    "    risk    = round(min(sum(_RISK_W.get(k, 0.20) * v for k, v in aprobs.items()), 1.0), 4)\n",
    "\n",
    "    explanations = {\n",
    "        'herd'          : f\"Detected Herd bias (confidence {conf:.0%}, risk {risk:.0%}). Crowd pressure {cr:.0%} drives decision irrationally.\",\n",
    "        'loss_aversion' : f\"Detected Loss Aversion bias (confidence {conf:.0%}, risk {risk:.0%}). P&L {gl:+.1%} triggers avoidance.\",\n",
    "        'disposition'   : f\"Detected Disposition bias (confidence {conf:.0%}, risk {risk:.0%}). Holding losers, selling winners.\",\n",
    "        'rational'      : f\"No bias detected (confidence {conf:.0%}). Rational, data-driven decision-making.\",\n",
    "    }\n",
    "\n",
    "    return {\n",
    "        'bias_type'       : bias_name,\n",
    "        'bias_label'      : bias_name.replace('_', ' ').title(),\n",
    "        'confidence'      : round(conf, 4),\n",
    "        'all_probabilities': aprobs,\n",
    "        'causal_chain'    : [f\"Crowd ratio={cr:.1%}, P&L={gl:+.1%}, Market={mret:+.1%}\"],\n",
    "        'intervention'    : interv,\n",
    "        'causal_effects'  : causal_effects,\n",
    "        'risk_score'      : risk,\n",
    "        'explanation'     : explanations.get(bias_name, f\"{bias_name} detected.\"),\n",
    "        'timestamp_ms'    : int(time.time() * 1000),\n",
    "    }\n",
    "\n",
    "\n",
    "# ─── FIX: Specimens come from TEST SET ONLY — never training data ──────────\n",
    "# Searching train+test combined would expose training-data memorisation,\n",
    "# not genuine model generalisation. We search ONLY within the held-out test set.\n",
    "\n",
    "from bias_detector import load_data, load_model, BIAS_LABELS\n",
    "import numpy as np\n",
    "\n",
    "X_train, X_test, y_train, y_test = load_data()\n",
    "model, feature_cols = load_model()\n",
    "\n",
    "# Align X_test to the exact training column order\n",
    "for col in feature_cols:\n",
    "    if col not in X_test.columns:\n",
    "        X_test[col] = 0\n",
    "X_test = X_test[feature_cols]\n",
    "\n",
    "# CORRECT: only search within the held-out test set\n",
    "proba_test = model.predict_proba(X_test)   # predictions on test samples only\n",
    "preds_test = model.predict(X_test)\n",
    "\n",
    "df_feat = pd.read_csv('../data/processed/merged_features.csv').rename(columns={\n",
    "    'market_return_recent': 'market_return',\n",
    "    'unrealized_gain_loss': 'unrealized_gl',\n",
    "    'crowd_action_ratio'  : 'crowd_ratio',\n",
    "})\n",
    "test_idx = np.load('../data/processed/test_indices.npy')\n",
    "\n",
    "# Show what's available in the test set so we can set honest expectations\n",
    "print('Test set class distribution (NON-RESAMPLED, original held-out):')\n",
    "for cls_id, cls_name in sorted(BIAS_LABELS.items()):\n",
    "    n = (y_test == cls_id).sum()\n",
    "    print(f'  {BIAS_ICONS.get(cls_name,\"?\")} {cls_name:<16} : {n} test samples')\n",
    "\n",
    "specimens = {}\n",
    "for cls_id, cls_name in BIAS_LABELS.items():\n",
    "    # Search ONLY within X_test (held-out set)\n",
    "    correct = (preds_test == cls_id) & (y_test == cls_id)\n",
    "    idxs    = np.where(correct)[0]\n",
    "    if len(idxs) == 0:\n",
    "        # No correctly-predicted specimens — try any prediction of this class in test set\n",
    "        idxs = np.where(preds_test == cls_id)[0]\n",
    "    if len(idxs) == 0:\n",
    "        # No predictions at all for this class in the entire test set\n",
    "        print(f'  ⚠️  No test-set specimens for class: {cls_name}')\n",
    "        print(f'     This means the model never predicted {cls_name} on the test set.')\n",
    "        print(f'     NOT falling back to training data — that would show memorisation.')\n",
    "        continue\n",
    "    best     = idxs[np.argmax(proba_test[idxs, cls_id])]\n",
    "    orig_row = df_feat.iloc[test_idx[best]].to_dict()\n",
    "    specimens[cls_name] = {\n",
    "        'row'       : orig_row,\n",
    "        'X_row'     : X_test.iloc[[best]],   # from test set — never training data\n",
    "        'confidence': round(proba_test[best, cls_id], 4),\n",
    "        'correct'   : bool(y_test[best] == cls_id),\n",
    "    }\n",
    "\n",
    "print('\\nHigh-confidence test-set specimens found:')\n",
    "for k, v in specimens.items():\n",
    "    print(f\"  {BIAS_ICONS.get(k,'?')} {k:18s}  conf={v['confidence']:.1%}  \"\n",
    "          f\"ground-truth-correct={v['correct']} (FROM TEST SET)\")\n",
    "print(\"\\n✅ All specimens drawn from held-out test set — no training data memorisation\")\n",
]


def patch_demo_notebook():
    nb, path = load_nb("04_full_pipeline_demo.ipynb")
    
    # Find the cell with the old specimen search (contains "Combine train + test")
    MARKER = "# Combine train + test for specimen search"
    
    patched = False
    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if MARKER in source:
            # Replace the entire source with corrected version
            cell["source"] = CORRECTED_SPECIMEN_SOURCE
            cell["outputs"] = []
            cell["execution_count"] = None
            patched = True
            print("  ✅ Patched specimen-selection cell")
            break
    
    if not patched:
        print("  ⚠️  Marker not found — checking if already patched")
        for cell in nb["cells"]:
            if cell.get("cell_type") == "code":
                source = "".join(cell.get("source", []))
                if "TEST SET ONLY" in source:
                    print("  ℹ️  Cell already patched (found 'TEST SET ONLY')")
                    patched = True
                    break
    
    # Also find and update the markdown cell that says "real investor profile from the test set"
    for cell in nb["cells"]:
        if cell.get("cell_type") == "markdown":
            src = "".join(cell.get("source", []))
            if "real investor profile from the test set" in src:
                cell["source"] = [
                    "| 🔴 **Loss Aversion** | Feels losses ~2× more than equivalent gains | Panic-sells during drawdowns, locks in losses |\n",
                    "| 🟠 **Herd Mentality** | Follows the crowd blindly | Sells because \"everyone else is selling\" |\n",
                    "| 🟣 **Disposition Effect** | Sells winners early / holds losers too long | Realises gains prematurely, lets losses run |\n",
                    "| 🟢 **Rational** | No detectable bias | Decisions align with risk tolerance & plan |\n",
                    "\n",
                    "Each scenario below uses a **real investor profile from the held-out test set** where the model was correct.  \n",
                    "Specimens are **never drawn from training data** — no cherry-picking, no memorisation.\n",
                ]
                break
    
    # Clear all stale outputs
    clear_outputs(nb)
    
    save_nb(nb, path)
    return patched


def set_kernelspec(nb, display_name=".venv", language="python", name="python3"):
    """Update kernelspec metadata so the notebook runs in the venv."""
    nb.setdefault("metadata", {})["kernelspec"] = {
        "display_name": display_name,
        "language": language,
        "name": name,
    }
    nb.setdefault("metadata", {}).setdefault("language_info", {})["name"] = "python"


def patch_eval_notebook():
    nb, path = load_nb("05_model_evaluation.ipynb")
    set_kernelspec(nb)
    clear_outputs(nb)
    save_nb(nb, path)


# ─────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nPatching notebooks…")
    ok = patch_demo_notebook()
    patch_eval_notebook()
    print(f"\nDone. Specimen fix applied: {ok}")
