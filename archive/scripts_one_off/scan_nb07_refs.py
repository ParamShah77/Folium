"""
Scan all code cells in NB07 for variables used before they are defined.
Simulates top-to-bottom execution order.
"""
import json, re

nb = json.load(open("notebooks/07_final_evaluation.ipynb", encoding="utf-8"))

# Collect code cells in order
code_cells = [(i, c) for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"]

# Variables that are "built-in" or imported and always available
BUILTINS = {
    "os", "sys", "np", "pd", "plt", "json", "pickle", "warnings",
    "train_test_split", "classification_report", "confusion_matrix",
    "f1_score", "accuracy_score", "roc_auc_score", "StratifiedKFold",
    "cross_val_score", "xgb", "calibration_curve", "label_binarize",
    "CLASS_NAMES", "True", "False", "None", "print", "len", "range",
    "enumerate", "zip", "sorted", "list", "dict", "set", "float", "int",
    "str", "abs", "min", "max", "sum", "open", "round", "isinstance",
    "ROOT", "mpatches", "GridSpec", "ticker",
}

defined = set(BUILTINS)
issues = []

# Simple assignment pattern matcher
assign_re  = re.compile(r"""^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\+=|-=)""", re.MULTILINE)
import_re  = re.compile(r"""^[ \t]*(?:import|from)\s+(\S+)""", re.MULTILINE)
for_re     = re.compile(r"""^[ \t]*for\s+([A-Za-z_][A-Za-z0-9_,\s]*)\s+in\b""", re.MULTILINE)
# Use pattern: variable used as standalone name (rough heuristic)
use_re     = re.compile(r"""\b([A-Za-z_][A-Za-z0-9_]*)\b""")

TRACKED = {
    "cv_v3", "cv_v1", "cv_v2",
    "metrics_v3", "metrics_v2", "metrics_v1",
    "model_v3", "model_v2", "model_v1",
    "X_train_v3", "X_test_v3",
    "y_train", "y_test",
    "feat_v3", "feat_v1", "feat_v2",
    "report_v3", "report_v1", "report_v2",
    "gap_macro_internal",
    "train_macro_internal", "val_macro_internal",
    "herd_v2", "herd_v3",
    "_cv_f1_from_json", "_test_f1_from_json",
}

for cell_idx, cell in code_cells:
    src = "".join(cell["source"])

    # Check for TRACKED variables used before defined
    for var in TRACKED:
        if var in src and var not in defined:
            # Check if it's being defined in this cell too
            if f"{var} =" not in src and f"{var}=" not in src:
                # Find the line using it
                for lineno, line in enumerate(cell["source"], 1):
                    if var in line and not line.strip().startswith("#"):
                        issues.append(
                            f"Cell {cell_idx}, line {lineno}: "
                            f"'{var}' used but not yet defined\n"
                            f"    {line.rstrip()}"
                        )
                        break

    # Now register everything defined in this cell
    for m in assign_re.finditer(src):
        defined.add(m.group(1))
    for m in import_re.finditer(src):
        defined.add(m.group(1).split(".")[0])
    for m in for_re.finditer(src):
        for v in m.group(1).split(","):
            defined.add(v.strip())

if issues:
    print(f"Found {len(issues)} potential forward-reference issue(s):\n")
    for issue in issues:
        print(" ", issue)
else:
    print("No forward-reference issues found. NB07 should run top-to-bottom cleanly.")
