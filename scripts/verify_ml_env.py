"""Prove the ML environment still reproduces the committee's numbers.

The Option D bridge calls ``src/`` in place, which makes the *environment* part
of the contract: a pickle written under xgboost 3.2.0 / scikit-learn 1.8.0 can
load under different versions and predict differently without raising anything.
That failure is silent, so this script makes it loud.

Three checks, in order of how early they catch a problem:

1. **Versions** — installed distributions vs. the pins in
   ``backend/requirements-ml.txt``.
2. **Artefacts** — the model files exist and unpickle.
3. **Predictions** — the four labelled specimens from ``src/api.py``'s Swagger
   examples, each a real row with a known class. If the environment has drifted,
   this is where it shows.

Also checks that ``ml_bridge.BIAS_LABEL_MAP`` covers every label the model can
emit, since an unmapped label would fail a decision at runtime.

Run:  python scripts/verify_ml_env.py     (exit 0 = good, 1 = drift)
"""
from __future__ import annotations

import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Pins that actually affect the serialised model / SHAP values.
CRITICAL_PINS = {
    "xgboost": "3.2.0",
    "scikit-learn": "1.8.0",
    "numpy": "2.4.2",
    "pandas": "3.0.1",
    "scipy": "1.17.1",
    "shap": "0.51.0",
    "dowhy": "0.14",
    "networkx": "3.6.1",
}

# (name, expected label, minimum confidence) — payloads from src/api.py
# SWAGGER_EXAMPLES.
#
# The thresholds are the *observed v3 baseline* (measured 2026-09-06), not the
# confidences quoted in those examples' summaries. Three of the four agree; the
# loss_aversion specimen's summary claims 96.7% where v3 returns 0.539
# (probabilities: loss_aversion 0.539, disposition 0.265, rational 0.195 — the
# right class, but a genuinely near-boundary row). That summary predates v3 and
# is stale in src/api.py. This gate exists to detect *drift from today*, so it
# encodes what the shipped model actually does rather than a documentation
# claim it never reproduced.
SPECIMENS = [
    ("loss_aversion", "loss_aversion", 0.50, dict(
        market_return=-0.1068, unrealized_gl=-0.4143, crowd_ratio=0.2943,
        age=56, risk_tolerance=0.477, investment_horizon=19,
        monthly_income=126000, monthly_expense=75963, financial_strategy="saving",
        market_volatility=0.0298, position_size_pct=0.094,
        holding_period_months=33, has_emergency_fund=1, years_investing=15,
        crash_speed="rapid_decline", secondary_biases="none",
        investment_experience="expert", age_horizon_mismatch="normal",
        goal="retirement")),
    ("herd", "herd", 0.95, dict(
        market_return=-0.0039, unrealized_gl=-0.1593, crowd_ratio=0.8143,
        age=57, risk_tolerance=0.458, investment_horizon=24,
        monthly_income=135000, monthly_expense=77205, financial_strategy="saving",
        market_volatility=0.0197, position_size_pct=0.326,
        holding_period_months=15, has_emergency_fund=1, years_investing=18,
        crash_speed="normal", secondary_biases="loss_aversion",
        investment_experience="expert", age_horizon_mismatch="old_long",
        goal="retirement")),
    ("disposition", "disposition", 0.95, dict(
        market_return=0.0803, unrealized_gl=0.2050, crowd_ratio=0.3354,
        age=63, risk_tolerance=0.363, investment_horizon=29,
        monthly_income=166000, monthly_expense=134979, financial_strategy="saving",
        market_volatility=0.0234, position_size_pct=0.135,
        holding_period_months=47, has_emergency_fund=1, years_investing=25,
        crash_speed="normal", secondary_biases="overconfidence",
        investment_experience="expert", age_horizon_mismatch="old_long",
        goal="retirement")),
    ("rational", "rational", 0.99, dict(
        market_return=-0.0427, unrealized_gl=-0.0054, crowd_ratio=0.5163,
        age=48, risk_tolerance=0.324, investment_horizon=12,
        monthly_income=72000, monthly_expense=84051,
        financial_strategy="family_support",
        market_volatility=0.0322, position_size_pct=0.041,
        holding_period_months=40, has_emergency_fund=0, years_investing=12,
        crash_speed="normal", secondary_biases="none",
        investment_experience="intermediate", age_horizon_mismatch="normal",
        goal="wealth growth")),
]

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
OK, BAD, WARN = f"{GREEN}PASS{RESET}", f"{RED}FAIL{RESET}", f"{YELLOW}WARN{RESET}"


def check_versions() -> bool:
    print("1. Library versions vs backend/requirements-ml.txt")
    ok = True
    for dist, pin in sorted(CRITICAL_PINS.items()):
        try:
            got = version(dist)
        except PackageNotFoundError:
            print(f"   {BAD}  {dist:<16} not installed (need {pin})")
            ok = False
            continue
        if got == pin:
            print(f"   {OK}  {dist:<16} {got}")
        else:
            print(f"   {BAD}  {dist:<16} {got}  {DIM}(pinned {pin}){RESET}")
            ok = False
    print(f"   python           {sys.version.split()[0]}")
    return ok


def check_artefacts() -> bool:
    print("\n2. Model artefacts")
    ok = True
    for name in ("bias_detector_v4.json", "bias_detector_v4.meta.json",
                 "bias_detector_xgboost_v3.pkl", "causal_graph.pkl", "causal_scaler.pkl"):
        path = ROOT / "models" / name
        if path.exists():
            print(f"   {OK}  {name:<32} {path.stat().st_size / 1024:,.0f} KB")
        else:
            print(f"   {BAD}  {name:<32} MISSING")
            ok = False
    causal = ROOT / "results" / "causal_v4.json"
    if causal.exists():
        print(f"   {OK}  {'results/causal_v4.json':<32} {causal.stat().st_size / 1024:,.0f} KB")
    else:
        print(f"   {BAD}  {'results/causal_v4.json':<32} MISSING (python -m src.causal_v4)")
        ok = False
    history = ROOT / "data" / "sim_v2" / "monthly_history.csv"
    if history.exists():
        print(f"   {OK}  {'sim_v2/monthly_history.csv':<32} {history.stat().st_size / 1024:,.0f} KB")
    else:
        print(f"   {BAD}  {'sim_v2/monthly_history.csv':<32} MISSING (python -c \"from src.simulator_v2 import load_history; load_history(refresh=True)\")")
        ok = False
    return ok


def check_label_map() -> bool:
    print("\n3. Bridge label coverage")
    from backend.core.ml_bridge import BIAS_LABEL_MAP
    from src.bias_detector import BIAS_LABELS
    from src.bias_model_v4 import LABELS as V4_LABELS

    emitted = set(BIAS_LABELS.values()) | set(V4_LABELS)
    unmapped = emitted - set(BIAS_LABEL_MAP)
    if unmapped:
        print(f"   {BAD}  unmapped model labels: {sorted(unmapped)}")
        return False
    print(f"   {OK}  all {len(emitted)} model labels map to DB values")
    return True


def check_predictions() -> bool:
    print("\n4. Labelled specimen predictions")
    from src.bias_detector import detect_bias_realtime

    ok = True
    for name, expected, min_conf, payload in SPECIMENS:
        t0 = time.perf_counter()
        try:
            res = detect_bias_realtime(**payload)
        except Exception as exc:  # noqa: BLE001
            print(f"   {BAD}  {name:<16} raised {type(exc).__name__}: {exc}")
            ok = False
            continue
        elapsed = (time.perf_counter() - t0) * 1000
        got, conf = res["bias_type"], float(res["confidence"])

        if got != expected:
            print(f"   {BAD}  {name:<16} predicted {got!r}, expected {expected!r} "
                  f"(conf {conf:.3f})")
            ok = False
        elif conf < min_conf:
            print(f"   {WARN}  {name:<16} {got} but confidence {conf:.3f} "
                  f"{DIM}(was >={min_conf}){RESET}  {elapsed:.0f} ms")
        else:
            print(f"   {OK}  {name:<16} {got}  conf {conf:.3f}  {elapsed:.0f} ms")
    return ok


def main() -> int:
    print("FinAI — ML environment verification\n" + "=" * 52)
    results = [check_versions(), check_artefacts()]
    if not results[0] or not results[1]:
        print(f"\n{RED}Environment is not usable; skipping model checks.{RESET}")
        return 1
    results.append(check_label_map())
    results.append(check_predictions())

    print("=" * 52)
    if all(results):
        print(f"{GREEN}All checks passed — bridge may be trusted.{RESET}")
        return 0
    print(f"{RED}Drift detected. Do NOT trust bridged predictions until fixed.{RESET}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
