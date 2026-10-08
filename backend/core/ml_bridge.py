"""The one place ``backend/`` is allowed to reach into ``src/`` (Phase 5, Option D).

Milestone 4 has two possible shapes. The *port* rewrites ``src/bias_detector.py``
and friends as native async, DB-backed backend modules. The *bridge* — what this
module implements — calls the research code in place, adapting its inputs and
outputs at the boundary. The bridge is chosen because the research modules are
the artefacts the committee's numbers came from: re-deriving them by hand risks
silently changing accuracy 0.840 / F1 0.858 into something else.

Everything asymmetric between the two codebases is handled here, and nowhere
else, so that the eventual port has exactly one file to delete:

  * **sys.path** — ``src`` is a top-level package at the repo root, not under
    ``backend``; :func:`ensure_src_importable` puts the root on the path.
  * **Lazy import** — ``src.bias_detector`` pulls in xgboost/shap/pandas at
    import time (~2 s, ~400 MB RSS). Importing it from ``backend.core`` at
    module scope would make the whole API unbootable without the ML extras, so
    every import here happens inside a function.
  * **Blocking** — the research functions are synchronous and CPU-bound (SHAP
    over a 47-feature vector is ~100–400 ms). A pipeline step is ``async``, so
    calling them directly would stall the event loop for every other request.
    :func:`run_blocking` moves them to a worker thread.
  * **Vocabulary** — the model emits ``disposition``/``herd``; the ``decisions``
    CHECK constraint in migration 0003 requires
    ``disposition_effect``/``herd_behavior``. :data:`BIAS_LABEL_MAP` reconciles
    them. An unmapped label is an error, not a silent pass-through — a NULL
    ``bias_detected`` would look like "no bias found".
  * **Missing features** — the model wants ``crowd_ratio``, which no
    ``decisions`` column holds. It is *derived from the stored* ``vix_value``
    rather than re-fetched live, so re-running a decision reproduces its
    original prediction. Objective 4 claims the audit trail is verifiable;
    that is only true if inference is deterministic given the row.
"""
from __future__ import annotations

import asyncio
import functools
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

T = TypeVar("T")

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

#: Repo root — ``backend/core/ml_bridge.py`` → ``backend/core`` → ``backend`` → root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"


def ensure_src_importable() -> None:
    """Put the repo root on ``sys.path`` so ``import src.*`` resolves.

    Idempotent. Prepended rather than appended so a stray ``src`` elsewhere on
    the path cannot shadow the project's own.
    """
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


class MLUnavailableError(RuntimeError):
    """The ML extras are not installed, or a model artefact is missing.

    Raised instead of letting an ``ImportError``/``FileNotFoundError`` escape,
    so ``pipeline.py`` records a legible ``error_message`` on the decision row
    rather than a stack trace mentioning xgboost.
    """


# --------------------------------------------------------------------------- #
# Blocking work
# --------------------------------------------------------------------------- #

async def run_blocking(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a synchronous research function off the event loop."""
    return await asyncio.to_thread(functools.partial(fn, *args, **kwargs))


# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

#: ``src.bias_detector.BIAS_LABELS`` values → migration 0003's CHECK values.
BIAS_LABEL_MAP: dict[str, str] = {
    "disposition": "disposition_effect",
    "herd": "herd_behavior",
    "loss_aversion": "loss_aversion",
    "rational": "rational",
}


def map_bias_label(raw: str) -> str:
    """Translate a model label into a value ``decisions.bias_detected`` accepts."""
    try:
        return BIAS_LABEL_MAP[raw]
    except KeyError:
        raise MLUnavailableError(
            f"model produced unknown bias label {raw!r}; "
            f"expected one of {sorted(BIAS_LABEL_MAP)}. "
            "BIAS_LABEL_MAP is out of sync with src.bias_detector.BIAS_LABELS."
        ) from None


# --------------------------------------------------------------------------- #
# Derived features
# --------------------------------------------------------------------------- #

def crowd_ratio_from_vix(vix_value: float | None) -> float:
    """Crowd-fear proxy in [0.05, 1.0], ported from ``MarketDataFetcher``.

    Mirrors ``src/market_data.py::_fetch_vix_crowd_ratio`` exactly — VIX 15 →
    ~0.13, VIX 25 → ~0.38, VIX 40 → ~0.75 — but reads the VIX *stored on the
    decision row* instead of calling yfinance, so the value is stable across
    re-runs. ``None`` (market context unavailable at capture time) falls back to
    the neutral 0.50 that ``src/market_data.py`` uses in its default response.
    """
    if vix_value is None:
        return 0.50
    return float(max(0.05, min((float(vix_value) - 10.0) / 40.0, 1.0)))


def market_return_from_row(decision: Mapping[str, Any]) -> float:
    """The model's ``market_return_recent``: NIFTY's **1-month** return.

    Training data used the 1-month return (5th-95th pct: -0.113 ... +0.085),
    which migration 0008 stores as ``nifty_1m_return``. The 52-week return and
    the 1-day change are deliberately *not* used as stand-ins: one is an order
    of magnitude too large, the other too small, and either would push the
    feature off the distribution the classifier learned. Missing context falls
    back to 0.0 — a flat market, near the training median of 0.0013.
    """
    value = decision.get("nifty_1m_return")
    return float(value) if value is not None else 0.0


#: Median of ``market_volatility`` in the training set (30-day std of daily
#: NIFTY returns). Used only when no market context was captured.
NEUTRAL_DAILY_VOLATILITY = 0.0282


def market_volatility_from_row(decision: Mapping[str, Any]) -> float:
    """The model's ``market_volatility``: 30-day std of daily NIFTY returns.

    Preference order: the measured value stored at submission; else one
    implied by India VIX (an annualised %, so ``vix / 100 / sqrt(252)``
    converts it to the same daily scale); else the training median. The
    research fetcher's own fallback of 0.18 is never used — it is an
    annualised figure on a daily-scale feature.
    """
    measured = decision.get("nifty_volatility_30d")
    if measured is not None:
        return float(measured)
    vix = decision.get("vix_value")
    if vix is not None:
        return float(vix) / 100.0 / (252 ** 0.5)
    return NEUTRAL_DAILY_VOLATILITY


# --------------------------------------------------------------------------- #
# Profile vocabulary
# --------------------------------------------------------------------------- #

#: The app records *risk appetite* (migration 0001 CHECK:
#: conservative | moderate | aggressive). The classifier's
#: ``financial_strategy`` instead describes how the investor manages money:
#: saving | investing | balanced | credit_card | family_support. There is no
#: exact correspondence; this is the closest honest one, and it is surfaced in
#: ``explainer_output.bias.model_inputs`` so it can be questioned.
#: Without it, every app value matched no training category and was silently
#: encoded as the baseline ("investing") for every user.
STRATEGY_MAP: dict[str, str] = {
    "conservative": "saving",
    "moderate": "balanced",
    "aggressive": "investing",
}


def map_financial_strategy(app_value: str | None) -> str:
    """App risk appetite -> the classifier's ``financial_strategy`` category."""
    if app_value is None:
        return "saving"  # the cohort default detect_bias_realtime declares
    return STRATEGY_MAP.get(app_value.strip().lower(), "saving")


def map_goal(app_value: str | None) -> str:
    """Free-text goal -> the classifier's vocabulary.

    The model has a single goal indicator, ``goal_wealth growth``; every other
    goal is the baseline. So the only distinction that reaches the model is
    whether the stated goal is wealth growth.
    """
    if app_value and "wealth" in app_value.lower():
        return "wealth growth"
    return (app_value or "wealth growth").strip().lower()
