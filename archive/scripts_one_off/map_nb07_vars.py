import json
nb = json.load(open("notebooks/07_final_evaluation.ipynb", encoding="utf-8"))
keywords = ["cv_v3", "metrics_v3", "X_train_v3", "gap_macro_internal", "model_v3", "report_v3", "feat_v3"]
print("Cell-by-cell variable definitions:")
for i, c in enumerate(nb["cells"]):
    src = "".join(c.get("source", []))
    found = [k for k in keywords if (k + " =") in src or (k + "=") in src]
    if found:
        ctype = c["cell_type"]
        print(f"  Cell {i} [{ctype}]: defines {found}")
