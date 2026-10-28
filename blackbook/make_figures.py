"""Generate every figure used in the Folium blackbook.

Charts are plotted directly from the evaluation files committed in the
repository (results/reports/*.json, results/causal_v4.json, data/v4/*.csv),
so no number is typed by hand. Diagrams are drawn from the module structure
of backend/ and src/.

Run from the repository root:  python blackbook/make_figures.py
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Ellipse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "blackbook", "figures")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})
TEAL, BLUSH, GREY, DARK = "#2a7f7a", "#d98c7a", "#9aa5ab", "#24323a"


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


BIAS = load("results/reports/bias_v4_evaluation.json")
SIM = load("results/reports/simulator_v2_evaluation.json")
CAUSAL = load("results/causal_v4.json")
EXPL = load("results/reports/explanation_quality.json")


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight")
    plt.close(fig)


# ───────────────────────────── diagram helpers ─────────────────────────────

def box(ax, x, y, w, h, text, fc="#eef6f5", ec=TEAL, fs=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            weight="bold" if bold else "normal", wrap=True)


def arrow(ax, p, q, text=None, style="-|>", color=DARK, fs=7.5, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, color=color, lw=1.0,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 0.12, text, fontsize=fs, ha="center",
                va="bottom", color=DARK, bbox=dict(fc="white", ec="none", pad=0.5))


def canvas(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


# ───────────────────────────── diagrams ─────────────────────────────

def fig_architecture():
    fig, ax = canvas(7.5, 6.2, 10, 10)
    box(ax, 0.3, 8.6, 9.4, 1.1, "Presentation tier — React 19 SPA (Vite, TypeScript, Tailwind)\n"
        "Landing · Auth pages · Dashboard · Portfolio · New analysis · Result page · History · Settings",
        fc="#fbefe9", ec=BLUSH)
    box(ax, 0.3, 5.0, 9.4, 3.0, "", fc="#f6faf9")
    ax.text(5, 7.75, "Application tier — FastAPI backend (backend/)", ha="center", fontsize=9, weight="bold")
    box(ax, 0.5, 6.2, 2.1, 1.2, "api/v1 routes\nauth · users\nportfolio · decisions\nmarket · meta · admin", fs=7.5)
    box(ax, 2.8, 6.2, 2.1, 1.2, "middleware\nCSRF · rate limit\nsecurity headers\nrequest logger", fs=7.5)
    box(ax, 5.1, 6.2, 2.1, 1.2, "auth\nRS256 JWT · bcrypt\nTOTP MFA · OAuth\nFernet crypto", fs=7.5)
    box(ax, 7.4, 6.2, 2.1, 1.2, "services\nportfolio · prices\nmarket data · email\naccount deletion", fs=7.5)
    box(ax, 0.5, 5.2, 9.0, 0.8, "core/pipeline.py — background analysis: bias → simulation → explanation →\n"
        "recommendation → audit (progress published as SSE events)", fs=7.8, fc="#e3f1ef")
    box(ax, 0.3, 2.6, 5.6, 1.9, "Analytics tier — research modules (src/),\nreached only via core/ml_bridge.py\n"
        "dataset_v4 · bias_model_v4 (XGBoost+SHAP)\nsimulator_v2 (block bootstrap)\n"
        "causal_v4 (DoWhy, g-computation) · explainer (EN/HI)", fs=7.6, fc="#eef3fb", ec="#5a7bb0")
    box(ax, 6.2, 2.6, 3.5, 1.9, "Artefacts\nmodels/bias_detector_v4.json\nresults/causal_v4.json\n"
        "data/sim_v2/monthly_history.csv", fs=7.6, fc="#f3f3f3", ec=GREY)
    box(ax, 0.3, 0.3, 3.0, 1.6, "PostgreSQL\nusers · decisions\nportfolios · audit_logs\nrow-level security",
        fs=7.6, fc="#f3f3f3", ec=GREY)
    box(ax, 3.6, 0.3, 2.8, 1.6, "Redis / Memurai\ntoken blacklist\nrate-limit counters\nSSE event backlog",
        fs=7.6, fc="#f3f3f3", ec=GREY)
    box(ax, 6.7, 0.3, 3.0, 1.6, "External services\nYahoo Finance · MFAPI.in\nGemini (optional, consent)\n"
        "Resend e-mail (optional)", fs=7.6, fc="#fdf6e7", ec="#c49a3a")
    arrow(ax, (5, 8.6), (5, 8.0), "HTTPS JSON / cookies, /v1/*", style="<|-|>")
    arrow(ax, (3.1, 5.0), (3.1, 4.5), "in-process calls", style="<|-|>")
    arrow(ax, (5.9, 3.5), (6.2, 3.5), style="<|-")
    arrow(ax, (1.8, 5.0), (1.8, 1.9), style="<|-|>")
    arrow(ax, (5.0, 5.0), (5.0, 1.9), style="<|-|>")
    arrow(ax, (8.2, 5.0), (8.2, 1.9), style="<|-|>")
    save(fig, "fig5_1_architecture.png")


def fig_components():
    fig, ax = canvas(7.5, 5.2, 10, 8)
    items = [
        (0.2, 6.3, "decisions.py\nPOST /analyze (202)\nGET /stream (SSE)"),
        (0.2, 4.6, "pipeline.py\norchestrator"),
        (0.2, 2.9, "events.py\nRedis pub/sub +\nbacklog replay"),
    ]
    for x, y, t in items:
        box(ax, x, y, 2.4, 1.2, t, fs=7.6)
    steps = [("bias_detector.py\n+ comment_reader.py", 6.6), ("simulator.py", 5.3), ("explainer.py", 4.0),
             ("recommendation.py\n+ debate.py", 2.7), ("audit.py", 1.4)]
    for t, y in steps:
        box(ax, 3.4, y, 2.4, 1.0, t, fs=7.6, fc="#e3f1ef")
        arrow(ax, (2.6, 5.2), (3.4, y + 0.5), style="-|>", color=GREY)
    box(ax, 6.6, 3.0, 1.4, 3.2, "ml_bridge.py\n(lazy import,\nthread pool,\nlabel map)", fs=7.4, fc="#eef3fb", ec="#5a7bb0")
    for y in (7.1, 5.8, 4.5):
        arrow(ax, (5.8, y), (6.6, 4.6), color="#5a7bb0")
    srcs = [("bias_model_v4", 6.7), ("simulator_v2", 5.4), ("causal_v4", 4.1), ("explainer\n+ llm_polish", 2.8)]
    for t, y in srcs:
        box(ax, 8.4, y, 1.5, 0.9, "src/" + t, fs=7.2, fc="#eef3fb", ec="#5a7bb0")
        arrow(ax, (8.0, 4.6), (8.4, y + 0.45), color="#5a7bb0")
    box(ax, 3.4, 0.1, 2.4, 0.9, "PostgreSQL audit_logs", fs=7.4, fc="#f3f3f3", ec=GREY)
    arrow(ax, (4.6, 1.4), (4.6, 1.0))
    arrow(ax, (1.4, 6.3), (1.4, 5.8), "schedules")
    arrow(ax, (1.4, 4.6), (1.4, 4.1), "publishes")
    save(fig, "fig5_2_components.png")


def fig_dfd0():
    fig, ax = canvas(7.2, 3.6, 10, 5)
    box(ax, 0.2, 1.9, 1.8, 1.0, "Investor", fc="#fbefe9", ec=BLUSH, bold=True)
    ax.add_patch(Ellipse((5, 2.4), 3.4, 2.2, fc="#e3f1ef", ec=TEAL, lw=1.4))
    ax.text(5, 2.4, "0\nFolium\nDecision-Support\nSystem", ha="center", va="center", fontsize=9, weight="bold")
    box(ax, 8.0, 3.4, 1.8, 0.9, "Market data\nproviders", fc="#fdf6e7", ec="#c49a3a")
    box(ax, 8.0, 0.6, 1.8, 0.9, "Gemini API\n(optional)", fc="#fdf6e7", ec="#c49a3a")
    arrow(ax, (2.0, 2.65), (3.3, 2.75), "profile, holdings,\naction, comment")
    arrow(ax, (3.3, 2.05), (2.0, 2.15), "verdict, projections,\nexplanation, record")
    arrow(ax, (8.0, 3.8), (6.6, 3.0), "prices, NIFTY, VIX")
    arrow(ax, (6.6, 1.8), (8.0, 1.05), "comment + numbers", rad=0.1)
    arrow(ax, (8.0, 1.3), (6.7, 2.0), "checked wording", rad=0.1)
    save(fig, "fig5_3_dfd0.png")


def fig_dfd1():
    fig, ax = canvas(7.5, 5.4, 10, 8)
    procs = [(1.3, 6.6, "1.0\nCapture\ncontext"), (4.0, 6.6, "2.0\nRead comment\n& detect bias"),
             (6.8, 6.6, "3.0\nSimulate\nhold vs sell"), (6.8, 3.6, "4.0\nExplain\n(EN/HI)"),
             (4.0, 3.6, "5.0\nRecommend\n+ both sides"), (1.3, 3.6, "6.0\nSeal audit\nrecord")]
    for x, y, t in procs:
        ax.add_patch(Ellipse((x + 0.9, y + 0.5), 2.1, 1.3, fc="#e3f1ef", ec=TEAL))
        ax.text(x + 0.9, y + 0.5, t, ha="center", va="center", fontsize=7.6)
    stores = [(0.3, 0.6, "D3 audit_logs"), (3.6, 0.6, "D2 decisions"), (6.9, 0.6, "D1 users / financial_profiles")]
    for x, y, t in stores:
        ax.plot([x, x + 2.9], [y + 0.8, y + 0.8], color=DARK, lw=1)
        ax.plot([x, x + 2.9], [y, y], color=DARK, lw=1)
        ax.text(x + 1.45, y + 0.4, t, ha="center", va="center", fontsize=7.6)
    arrow(ax, (3.25, 7.1), (3.85, 7.1), "snapshot")
    arrow(ax, (6.05, 7.1), (6.65, 7.1), "bias, conf.")
    arrow(ax, (7.7, 5.95), (7.7, 4.25), "curves, p")
    arrow(ax, (6.65, 4.1), (6.05, 4.1), "narrative")
    arrow(ax, (3.85, 4.1), (3.25, 4.1), "verdict")
    arrow(ax, (2.2, 2.95), (1.8, 1.4), "append entry")
    arrow(ax, (4.9, 2.95), (5.05, 1.4), "write step outputs")
    arrow(ax, (9.75, 1.4), (8.95, 6.9), rad=0.45)
    ax.text(9.55, 4.1, "read\nprofile", fontsize=7.5, ha="center", bbox=dict(fc="white", ec="none", pad=0.5))
    box(ax, 0.1, 5.0, 1.0, 0.8, "Investor", fc="#fbefe9", ec=BLUSH, fs=7.5)
    arrow(ax, (0.6, 5.8), (1.6, 6.5), "request")
    save(fig, "fig5_4_dfd1.png")


def actor(ax, x, y, label):
    ax.add_patch(plt.Circle((x, y + 0.9), 0.18, fc="white", ec=DARK))
    ax.plot([x, x], [y + 0.72, y + 0.3], color=DARK)
    ax.plot([x - 0.25, x + 0.25], [y + 0.58, y + 0.58], color=DARK)
    ax.plot([x, x - 0.2], [y + 0.3, y], color=DARK)
    ax.plot([x, x + 0.2], [y + 0.3, y], color=DARK)
    ax.text(x, y - 0.2, label, ha="center", va="top", fontsize=8)


def fig_usecase():
    fig, ax = canvas(7.5, 6.0, 10, 10)
    ax.add_patch(FancyBboxPatch((2.2, 0.3), 5.6, 9.4, boxstyle="round,pad=0.02", fc="#fbfdfc", ec=GREY))
    ax.text(5, 9.45, "Folium system boundary", ha="center", fontsize=8.5, style="italic")
    cases = ["Register / verify e-mail / log in", "Set up two-step verification", "Maintain financial profile",
             "Manage portfolio holdings", "Request decision analysis", "Watch live progress",
             "Read explanation (EN / HI)", "Download report (HTML / PDF)", "Verify audit record",
             "Export data / delete account", "Reset a user's two-step (admin)"]
    ys = [8.7 - i * 0.78 for i in range(len(cases))]
    for t, y in zip(cases, ys):
        ax.add_patch(Ellipse((5, y), 4.9, 0.6, fc="#e3f1ef", ec=TEAL))
        ax.text(5, y, t, ha="center", va="center", fontsize=7.6)
    actor(ax, 0.9, 5.0, "Investor")
    actor(ax, 9.1, 0.9, "Administrator")
    actor(ax, 9.1, 5.6, "Market data\nservice")
    for y in ys[:-1]:
        ax.plot([1.15, 2.55], [5.6, y], color=GREY, lw=0.7)
    ax.plot([8.85, 7.45], [1.5, ys[-1]], color=GREY, lw=0.7)
    ax.plot([8.85, 7.45], [6.2, ys[4]], color=GREY, lw=0.7)
    ax.plot([8.85, 7.45], [6.2, ys[3]], color=GREY, lw=0.7)
    save(fig, "fig5_5_usecase.png")


def fig_activity():
    fig, ax = canvas(6.4, 8.4, 10, 14)
    ax.add_patch(plt.Circle((5, 13.4), 0.25, color=DARK))
    seq = ["Investor selects holding, action,\nmonths held, optional reason",
           "POST /v1/decisions/analyze: validate input,\ncapture market + portfolio + stock risk",
           "Insert decision (status = pending),\nreturn 202 + decision id",
           "Step 1: read comment, run bias model v4.1",
           "Step 2: simulate hold vs sell (simulator v2)",
           "Step 3: cause-and-effect + explanation EN/HI",
           "Step 4: evidence rules → verdict; build both sides",
           "Step 5: append hash-chained audit entry",
           "Mark complete, publish final SSE event"]
    y = 12.4
    prev = (5, 13.15)
    for i, t in enumerate(seq):
        box(ax, 2.0, y, 6.0, 0.85, t, fs=7.6, fc="#e3f1ef" if 3 <= i <= 7 else "#f6faf9")
        arrow(ax, prev, (5, y + 0.85))
        prev = (5, y)
        y -= 1.3
    ax.add_patch(plt.Circle((5, y + 0.5), 0.25, fc="white", ec=DARK, lw=2))
    ax.add_patch(plt.Circle((5, y + 0.5), 0.14, color=DARK))
    arrow(ax, prev, (5, y + 0.75))
    box(ax, 8.4, 6.0, 1.5, 1.3, "Any step\nraises →\nstatus =\nfailed", fs=7, fc="#fbefe9", ec=BLUSH)
    arrow(ax, (8.0, 6.6), (8.4, 6.6), ls="--", color=BLUSH)
    save(fig, "fig5_6_activity.png")


def fig_sequence():
    fig, ax = canvas(7.6, 6.2, 12, 11)
    parts = ["Browser", "FastAPI\ndecisions.py", "Pipeline\n(background)", "Redis", "PostgreSQL", "src/ models"]
    xs = [1, 3.1, 5.2, 7.2, 9.1, 11]
    for x, p in zip(xs, parts):
        box(ax, x - 0.85, 9.8, 1.7, 0.9, p, fs=7.4)
        ax.plot([x, x], [0.3, 9.8], color=GREY, lw=0.8, ls="--")
    msgs = [(0, 1, "POST /analyze"), (1, 4, "INSERT decision"), (1, 0, "202 {decision_id}"),
            (0, 1, "GET /stream (SSE)"), (1, 3, "replay backlog + subscribe"), (1, 2, "BackgroundTask"),
            (2, 4, "SELECT decision (RLS)"), (2, 5, "predict / simulate / explain"),
            (2, 4, "UPDATE step columns"), (2, 3, "publish {step, done}"), (3, 1, "event"),
            (1, 0, "data: {step, status}"), (2, 4, "INSERT audit_logs"), (2, 3, "publish complete"),
            (0, 1, "GET /result")]
    y = 9.3
    for a, b, t in msgs:
        arrow(ax, (xs[a], y), (xs[b], y), style="-|>", color=DARK if a < b else TEAL)
        ax.text((xs[a] + xs[b]) / 2, y + 0.06, t, ha="center", va="bottom", fontsize=6.8)
        y -= 0.6
    save(fig, "fig5_7_sequence.png")


def fig_er():
    fig, ax = canvas(7.6, 6.6, 12, 10.4)

    def ent(x, y, name, cols, w=3.2):
        h = 0.42 * (len(cols) + 1)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0", fc="white", ec=DARK))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.42), w, 0.42, boxstyle="square,pad=0", fc="#e3f1ef", ec=DARK))
        ax.text(x + w / 2, y + h - 0.21, name, ha="center", va="center", fontsize=8, weight="bold")
        for i, c in enumerate(cols):
            ax.text(x + 0.1, y + h - 0.63 - 0.42 * i, c, fontsize=6.9, va="center")
        return (x, y, w, h)

    u = ent(4.4, 4.8, "users", ["PK user_id (uuid)", "email (unique)", "password_hash, mfa_secret_enc",
                                "age, monthly_income", "emi, rent, education fees", "risk_tolerance, horizon",
                                "ai_consent, purge_after", "created_at"])
    d = ent(0.2, 0.3, "decisions", ["PK decision_id", "FK user_id", "symbol, quantity, prices", "decision_intent, user_reasoning",
                                    "vix, nifty_1m_return, volatility", "portfolio_context (jsonb)", "comment_facts (jsonb)",
                                    "bias_detected, bias_confidence", "simulation_curves (jsonb)", "recommendation, status"])
    a = ent(8.6, 0.3, "audit_logs", ["PK log_id", "FK user_id, FK decision_id", "payload_hash", "previous_hash",
                                     "chain_hash", "payload (jsonb)", "created_at"])
    p = ent(0.2, 6.6, "portfolios", ["PK holding_id", "FK user_id", "symbol, exchange", "quantity, avg_buy_price",
                                     "asset_type"])
    f = ent(8.6, 6.6, "financial_profiles", ["PK/FK user_id", "gold_grams, fixed_deposits", "savings_balance",
                                             "real_estate_value", "loans, rent_received", "monthly_sip"])
    r = ent(4.4, 0.3, "refresh_tokens / mfa_*", ["FK user_id", "token_hash, jti", "code_hash, used"])
    pc = ent(4.3, 9.3, "profile_change_log", ["FK user_id, field, old_value_hash"], w=3.4)

    def link(p1, p2, t):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=GREY, lw=1)
        ax.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, t, fontsize=7, ha="center",
                bbox=dict(fc="white", ec="none", pad=0.4))
    link((4.4, 5.5), (3.4, 4.6), "1 : N")
    link((7.6, 5.5), (8.6, 3.4), "1 : N")
    link((4.4, 7.4), (3.4, 7.6), "1 : N")
    link((7.6, 7.4), (8.6, 7.6), "1 : 1")
    link((6.0, 4.8), (6.0, 1.98), "1 : N")
    link((6.0, 8.58), (6.0, 9.3), "1 : N")
    link((3.4, 2.5), (8.6, 2.5), "1 : N (decision → entries)")
    save(fig, "fig5_8_er.png")


def fig_deployment():
    fig, ax = canvas(7.4, 4.2, 10, 6)
    ax.add_patch(FancyBboxPatch((0.2, 0.2), 9.6, 5.5, boxstyle="round,pad=0.02", fc="#fbfdfc", ec=GREY))
    ax.text(0.4, 5.45, "«device» Developer / demo laptop (Windows, Python 3.13 venv)", fontsize=8, style="italic")
    box(ax, 0.5, 3.3, 2.8, 1.6, "«process»\nVite dev server :3000\nReact SPA\n(proxy /v1 → :8000)", fs=7.5, fc="#fbefe9", ec=BLUSH)
    box(ax, 3.7, 3.3, 2.8, 1.6, "«process»\nUvicorn :8000\nFastAPI app\n+ background pipeline", fs=7.5)
    box(ax, 6.9, 3.3, 2.6, 1.6, "«artefacts»\nmodels/ results/\ndata/ (on disk)", fs=7.5, fc="#eef3fb", ec="#5a7bb0")
    box(ax, 2.0, 0.6, 2.8, 1.6, "«service»\nPostgreSQL 18 :5432\nroles: finai (owner),\napp_user (RLS)", fs=7.5, fc="#f3f3f3", ec=GREY)
    box(ax, 5.4, 0.6, 2.8, 1.6, "«service»\nMemurai / Redis :6379", fs=7.5, fc="#f3f3f3", ec=GREY)
    arrow(ax, (3.3, 4.1), (3.7, 4.1), style="<|-|>")
    arrow(ax, (6.5, 4.1), (6.9, 4.1), style="<|-|>")
    arrow(ax, (4.7, 3.3), (3.6, 2.2), style="<|-|>")
    arrow(ax, (5.5, 3.3), (6.6, 2.2), style="<|-|>")
    ax.text(5, -0.15, "Dockerfile.backend and docker-compose.yml exist for a later deployment but are not used locally.",
            ha="center", fontsize=7, style="italic")
    save(fig, "fig5_9_deployment.png")


def fig_dataset_pipeline():
    fig, ax = canvas(7.5, 2.6, 14, 4)
    steps = ["Real trading day\n(NIFTY, VIX;\nstress over-sampled)", "Household\n(income, EMIs,\nrent, fees, fund)",
             "Portfolio\n(shares, funds,\ngold, FD, loans)", "Hidden tendencies\n+ possible\ncash shock",
             "Motives compete\n(bias vs rational)", "Action + label\n= winning motive"]
    for i, t in enumerate(steps):
        box(ax, 0.1 + i * 2.33, 1.0, 2.0, 2.0, t, fs=7.4, fc="#e3f1ef" if i >= 4 else "#f6faf9")
        if i:
            arrow(ax, (i * 2.33 - 0.23, 2.0), (0.1 + i * 2.33, 2.0))
    ax.text(7, 0.4, "Hidden truth is stored in latent_* columns and is never a model input.", ha="center",
            fontsize=7.5, style="italic")
    save(fig, "fig4_1_dataset_pipeline.png")


# ───────────────────────────── charts from JSON ─────────────────────────────

def fig_labels():
    import csv
    counts, regimes = {}, {}
    with open(os.path.join(ROOT, "data/v4/decisions_v4.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counts[row["bias_type"]] = counts.get(row["bias_type"], 0) + 1
    real = BIAS["data"]["regime_real_share"]
    samp = BIAS["data"]["regime_sample_share"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.2))
    order = ["rational", "herd", "disposition", "loss_aversion"]
    a1.bar([o.replace("_", "\n") for o in order], [counts[o] for o in order], color=[TEAL, BLUSH, "#c49a3a", "#5a7bb0"])
    for i, o in enumerate(order):
        a1.text(i, counts[o] + 150, f"{counts[o]:,}", ha="center", fontsize=8)
    a1.set_title("(a) Labels in dataset v4.1 (n = 20,000)", fontsize=9)
    regs = ["normal", "bull", "correction", "crash", "euphoria"]
    x = range(len(regs))
    a2.bar([i - 0.2 for i in x], [real[r] * 100 for r in regs], 0.4, label="Real trading days", color=GREY)
    a2.bar([i + 0.2 for i in x], [samp[r] * 100 for r in regs], 0.4, label="Sampled cases", color=TEAL)
    a2.set_xticks(list(x), regs)
    a2.set_ylabel("% of total")
    a2.set_title("(b) Market regimes: real vs sampled", fontsize=9)
    a2.legend(fontsize=7.5, frameon=False)
    save(fig, "fig4_2_dataset_distribution.png")
    return counts


def fig_confusion():
    cm = BIAS["test"]["confusion_matrix_real_freq"]
    labs = ["Disposition", "Herd", "Loss aversion", "Rational"]
    fig, ax = plt.subplots(figsize=(4.6, 3.9))
    im = ax.imshow(cm, cmap="BuGn", vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{cm[i][j]:.2f}", ha="center", va="center", fontsize=9,
                    color="white" if cm[i][j] > 0.6 else DARK)
    ax.set_xticks(range(4), labs, rotation=20)
    ax.set_yticks(range(4), labs)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True label")
    fig.colorbar(im, fraction=0.046)
    save(fig, "fig8_1_confusion.png")


def fig_perclass():
    pc = BIAS["test"]["per_class_real_freq"]
    labs = ["disposition", "herd", "loss_aversion", "rational"]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for k, (m, c) in enumerate((("precision", GREY), ("recall", TEAL), ("f1", BLUSH))):
        ax.bar([i + (k - 1) * 0.26 for i in range(4)], [pc[l][m] for l in labs], 0.26, label=m.capitalize() if m != "f1" else "F1", color=c)
    ax.set_xticks(range(4), [l.replace("_", " ").title() for l in labs])
    ax.set_ylim(0, 1.05)
    ax.legend(ncol=3, fontsize=8, frameon=False, loc="lower center")
    save(fig, "fig8_2_per_class.png")


def fig_reliability():
    rel = BIAS["test"]["reliability_after"]
    fig, ax = plt.subplots(figsize=(4.4, 4.0))
    ax.plot([0, 1], [0, 1], ls="--", color=GREY, label="Perfect calibration")
    ax.plot([r["mean_confidence"] for r in rel], [r["share_right"] for r in rel], "o-", color=TEAL,
            label="Bias model v4.1 (calibrated)")
    for r in rel:
        ax.annotate(f"n={r['n']}", (r["mean_confidence"], r["share_right"]), fontsize=6.5,
                    xytext=(4, -10), textcoords="offset points")
    ax.set_xlabel("Mean stated confidence")
    ax.set_ylabel("Share correct")
    ax.legend(fontsize=7.5, frameon=False)
    save(fig, "fig8_3_reliability.png")


def fig_baselines():
    b = BIAS["baselines"]
    names = ["Always\n\"rational\"", "Definitions\nonly", "v3 model", "v4.1 without\nallows_*", "v4.1", "Ceiling\n(hidden traits)"]
    vals = [b["always_rational"]["accuracy_real_freq"], b["rules_only"]["accuracy_real_freq"],
            BIAS["v3_comparison"]["v3_on_v4_test"]["accuracy_real_freq"], b["without_rule_inputs"]["accuracy_real_freq"],
            BIAS["test"]["with_guard_calibrated"]["accuracy_real_freq"], b["ceiling_with_hidden_tendencies"]["accuracy_real_freq"]]
    fig, ax = plt.subplots(figsize=(6.8, 3.0))
    cols = [GREY, GREY, BLUSH, GREY, TEAL, "#5a7bb0"]
    ax.bar(names, [v * 100 for v in vals], color=cols)
    for i, v in enumerate(vals):
        ax.text(i, v * 100 + 1, f"{v * 100:.1f}%", ha="center", fontsize=8)
    ax.set_ylabel("Accuracy (real-frequency test set, %)")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", labelsize=7.5)
    save(fig, "fig8_4_baselines.png")


def fig_realism():
    r = SIM["realism"]
    keys = [("real NIFTY (rolling windows)", "Real NIFTY"), ("simulated (long-run assumptions)", "Simulator v2"),
            ("v1 synthetic paths", "Simulator v1")]
    qs = [("1y_return_p10", "Bad year (10th pct)"), ("1y_return_median", "Typical year"), ("1y_return_p90", "Good year (90th pct)")]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for k, ((key, lab), c) in enumerate(zip(keys, (GREY, TEAL, BLUSH))):
        vals = [r[key][q] * 100 for q, _ in qs]
        ax.bar([i + (k - 1) * 0.26 for i in range(3)], vals, 0.26, label=lab, color=c)
        for i, v in enumerate(vals):
            ax.text(i + (k - 1) * 0.26, v + (1 if v >= 0 else -3.2), f"{v:.1f}", ha="center", fontsize=7)
    ax.axhline(0, color=DARK, lw=0.6)
    ax.set_xticks(range(3), [l for _, l in qs])
    ax.set_ylabel("12-month return (%)")
    ax.legend(fontsize=7.5, frameon=False)
    save(fig, "fig9_1_realism.png")


def fig_horizon():
    h = SIM["horizon_effect"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.1))
    for key, lab, c in (("stock_down_17pct", "Stock down 17%", BLUSH), ("fund_up_30pct", "Fund up 30%", TEAL)):
        hs = [p["horizon"] for p in h[key]]
        a1.plot(hs, [p["prob_hold_better"] * 100 for p in h[key]], "o-", color=c, label=lab)
        a2.plot(hs, [p["typical_gap"] / 1e5 for p in h[key]], "o-", color=c, label=lab)
    a1.axhspan(40, 60, color=GREY, alpha=0.15, label="Toss-up band (40–60%)")
    a1.set_xlabel("Horizon (years)")
    a1.set_ylabel("Futures where holding wins (%)")
    a1.legend(fontsize=7, frameon=False)
    a2.set_xlabel("Horizon (years)")
    a2.set_ylabel("Typical gap, hold − sell (₹ lakh)")
    a1.set_title("(a) Probability holding wins", fontsize=9)
    a2.set_title("(b) Median paired gap", fontsize=9)
    save(fig, "fig9_2_horizon.png")


def fig_sensitivity():
    s = SIM["sensitivity"]
    base = s["base"]["prob_hold_better"] * 100
    names = {"equity_9pct": "Shares grow 9%", "equity_13pct": "Shares grow 13%", "stock_risk_15pct": "Own swings 15%",
             "stock_risk_35pct": "Own swings 35%", "gold_6pct": "Gold grows 6%", "sale_all_to_fd": "Sale all to FD",
             "sale_all_to_gold": "Sale all to gold", "low_income_no_slab_tax": "No slab tax on interest",
             "history_replayed_exactly": "History replayed exactly"}
    items = [(names[k], s[k]["prob_hold_better"] * 100) for k in names if k in s]
    items.sort(key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.barh([n for n, _ in items], [v - base for _, v in items], left=base,
            color=[TEAL if v >= base else BLUSH for _, v in items])
    ax.axvline(base, color=DARK, lw=0.8)
    ax.text(base, len(items) - 0.4, f" base {base:.1f}%", fontsize=7.5)
    ax.set_xlabel("Futures where holding wins (%), stock down 17%, 20 years")
    save(fig, "fig9_3_sensitivity.png")


def fig_stocks():
    st = SIM["measured_stocks"]["stocks"]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    sc = ax.scatter([s["specific_vol"] * 100 for s in st], [s["prob_hold_better_20y"] * 100 for s in st],
                    c=[s["beta"] for s in st], cmap="viridis", s=36)
    for s in st:
        ax.annotate(s["stock"], (s["specific_vol"] * 100, s["prob_hold_better_20y"] * 100), fontsize=6,
                    xytext=(3, 2), textcoords="offset points")
    fig.colorbar(sc, label="Measured beta")
    ax.set_xlabel("Company-specific yearly swings (%)")
    ax.set_ylabel("Holding wins over 20 years (%)")
    save(fig, "fig9_4_stocks.png")


def fig_causal():
    ce = CAUSAL["causal_effects"]
    rows = []
    for k, v in ce.items():
        rows.append((v["label"], v["true"]["sell"] * 100, v["g_computation"]["sell"] * 100))
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    y = range(len(rows))
    ax.barh([i + 0.2 for i in y], [r[1] for r in rows], 0.4, color=GREY, label="True effect (generator)")
    ax.barh([i - 0.2 for i in y], [r[2] for r in rows], 0.4, color=TEAL, label="Estimated (g-computation)")
    ax.set_yticks(list(y), [r[0] for r in rows], fontsize=7)
    ax.axvline(0, color=DARK, lw=0.6)
    ax.set_xlabel("Change in chance of selling (percentage points)")
    ax.legend(fontsize=7.5, frameon=False, loc="lower right")
    save(fig, "fig9_5_causal.png")
    return rows


def fig_explanations():
    e = EXPL["by_language"]
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    metrics = ["completeness_pct", "actionability_pct", "personalisation_pct", "readability_pass_pct"]
    labs = ["Completeness", "Actionability", "Personalisation", "Readability target met"]
    for k, (lang, c) in enumerate((("en", TEAL), ("hi", BLUSH))):
        ax.bar([i + (k - 0.5) * 0.36 for i in range(4)], [e[lang][m] for m in metrics], 0.36,
               label="English" if lang == "en" else "Hindi", color=c)
    ax.set_xticks(range(4), labs, fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("% of 32 explanations")
    ax.legend(fontsize=7.5, frameon=False, ncol=2)
    save(fig, "fig9_6_explanations.png")


if __name__ == "__main__":
    for fn in (fig_architecture, fig_components, fig_dfd0, fig_dfd1, fig_usecase, fig_activity, fig_sequence,
               fig_er, fig_deployment, fig_dataset_pipeline, fig_labels, fig_confusion, fig_perclass,
               fig_reliability, fig_baselines, fig_realism, fig_horizon, fig_sensitivity, fig_stocks,
               fig_causal, fig_explanations):
        out = fn()
        if out is not None:
            print(fn.__name__, out)
    print("figures written to", OUT)
