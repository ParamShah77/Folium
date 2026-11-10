"""Result charts for the LaTeX report, as vector PDFs in the report's font.

Every chart is plotted directly from the evaluation files committed in the
repository (results/reports/*.json, results/causal_v4.json, data/v4/*.csv);
the plotting code is shared with blackbook/make_figures.py.

Run from the repository root:  python blackbook_latex/make_charts.py
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "blackbook"))
import make_figures as mf  # noqa: E402

OUT = os.path.join(ROOT, "blackbook_latex", "figures", "charts")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    "font.family": ["Latin Modern Roman", "DejaVu Sans"],
    "mathtext.fontset": "cm",
    "font.size": 10,
    "pdf.fonttype": 42,
})

# file written by make_figures -> name used in the report
CHARTS = {
    mf.fig_labels: ("fig4_2_dataset_distribution.png", "dataset_distribution"),
    mf.fig_confusion: ("fig8_1_confusion.png", "confusion"),
    mf.fig_reliability: ("fig8_3_reliability.png", "reliability"),
    mf.fig_baselines_ci: ("fig8_5_baselines_ci.png", "baselines_ci"),
    mf.fig_generators: ("fig9_2_generators.png", "generators"),
    mf.fig_horizon: ("fig9_3_horizon.png", "horizon"),
    mf.fig_convergence: ("fig9_4_convergence.png", "convergence"),
    mf.fig_population: ("fig9_5_population.png", "population"),
    mf.fig_sensitivity_verdicts: ("fig9_6_sensitivity.png", "sensitivity"),
    mf.fig_stocks: ("fig9_7_stocks.png", "stocks"),
    mf.fig_causal: ("fig9_8_causal.png", "causal"),
}


def main():
    target = {}

    def save(fig, name):
        fig.savefig(os.path.join(OUT, target[name] + ".pdf"), bbox_inches="tight")
        plt.close(fig)

    mf.save = save
    for fn, (png, pdf) in CHARTS.items():
        target[png] = pdf
        fn()
    print("charts written to", OUT)


if __name__ == "__main__":
    main()
