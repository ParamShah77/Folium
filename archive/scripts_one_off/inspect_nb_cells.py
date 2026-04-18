import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_DIR = os.path.join(ROOT, "notebooks")

for nb_name in ["06_model_improvement.ipynb", "07_final_evaluation.ipynb"]:
    path = os.path.join(NB_DIR, nb_name)
    nb = json.load(open(path, encoding="utf-8"))
    print(f"\n=== {nb_name} ({len(nb['cells'])} cells) ===")
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))[:120].replace("\n", " ")
        print(f"  {i}: [{c['cell_type']}] {src!r}")
