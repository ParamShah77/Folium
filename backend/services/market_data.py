"""Live NIFTY / India VIX context for decisions and the dashboard ribbon.

Wraps ``src/market_data.py::MarketDataFetcher`` (yfinance, 15-minute in-process
cache) through the Phase 5 bridge. Two rules shape everything here:

1. **A market outage must never block a decision.** yfinance is a scraper and
   can hang; every call is bounded by ``MARKET_DATA_TIMEOUT_SECONDS`` and any
   failure degrades to "unavailable" rather than raising.
2. **Fallback numbers are not data.** The research fetcher's last-resort
   defaults (e.g. ``market_volatility = 0.18``) are placeholders, and 0.18 is
   also on the wrong scale — training data has a median daily volatility of
   0.028. When the fetcher reports ``default_fallback``, this module stores
   NULLs so the classifier uses its documented neutral defaults and the UI can
   say plainly that market data was unavailable.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import structlog

from ..config import get_settings
from ..core.ml_bridge import ensure_src_importable

logger = structlog.get_logger(__name__)

# yfinance logs every HTTP step at DEBUG, and its timezone cache (peewee) logs
# every SQL statement; with the app's root logger at DEBUG that floods the log.
for _noisy in ("yfinance", "peewee"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# 1-month NIFTY move beyond which the market is called trending (±2%).
_TREND_THRESHOLD = 0.02

_EMPTY_CONTEXT: dict[str, Any] = {
    "nifty_1m_return": None,
    "nifty_volatility_30d": None,
    "nifty_1d_change": None,
    "vix_value": None,
    "market_trend": None,
    "market_data_source": "unavailable",
}


def trend_from_return(one_month_return: float | None) -> str | None:
    """Classify the 1-month NIFTY return as bull / bear / sideways."""
    if one_month_return is None:
        return None
    if one_month_return > _TREND_THRESHOLD:
        return "bull"
    if one_month_return < -_TREND_THRESHOLD:
        return "bear"
    return "sideways"


def _fetcher():
    ensure_src_importable()
    from src.market_data import get_fetcher

    return get_fetcher()


def _fetch_context_sync() -> dict[str, Any]:
    fetcher = _fetcher()
    ctx = fetcher.get_market_context()
    source = ctx.get("data_source")
    if source not in ("live", "cache"):
        return dict(_EMPTY_CONTEXT)

    ribbon = fetcher.get_indices_ribbon()
    nifty = ribbon.get("nifty50") or {}
    vix = ribbon.get("india_vix") or {}
    one_month = float(ctx["market_return"])
    one_day = nifty.get("change_pct")
    return {
        "nifty_1m_return": round(one_month, 4),
        "nifty_volatility_30d": round(float(ctx["market_volatility"]), 5),
        "nifty_1d_change": round(float(one_day) / 100.0, 4) if one_day is not None else None,
        "vix_value": round(float(vix["price"]), 3) if vix.get("price") is not None else None,
        "market_trend": trend_from_return(one_month),
        "market_data_source": source,
    }


async def capture_market_context() -> dict[str, Any]:
    """Market columns to store on a new decision. Never raises."""
    settings = get_settings()
    if not settings.MARKET_DATA_ENABLED:
        return dict(_EMPTY_CONTEXT)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch_context_sync),
            timeout=settings.MARKET_DATA_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 — timeout, network, parse: all degrade
        logger.warning("market_context_unavailable", error=f"{type(exc).__name__}: {exc}")
        return dict(_EMPTY_CONTEXT)


def _fetch_ribbon_sync() -> dict[str, Any]:
    return _fetcher().get_indices_ribbon()


async def get_ribbon() -> dict[str, Any]:
    """Latest price and 1-day change for NIFTY 50, SENSEX, BANK NIFTY, India VIX."""
    settings = get_settings()
    unavailable = {"data_source": "unavailable", "indices": []}
    if not settings.MARKET_DATA_ENABLED:
        return unavailable
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_fetch_ribbon_sync),
            timeout=settings.MARKET_DATA_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("market_ribbon_unavailable", error=f"{type(exc).__name__}: {exc}")
        return unavailable

    indices = []
    for key in ("nifty50", "sensex", "banknifty", "india_vix"):
        item = raw.get(key) or {}
        if item.get("price") is None:
            continue
        indices.append(
            {
                "key": key,
                "label": item.get("label", key),
                "price": item["price"],
                "change_pct": item.get("change_pct"),
                "direction": item.get("direction", "neutral"),
            }
        )
    source = raw.get("data_source", "unavailable") if indices else "unavailable"
    return {
        "data_source": source,
        "last_updated": raw.get("last_updated"),
        "indices": indices,
    }
