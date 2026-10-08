"""Live prices for the portfolio: NSE/BSE stocks, mutual-fund NAVs, gold.

Sources
-------
* Stocks — yfinance, ``SYMBOL.NS`` / ``SYMBOL.BO``, latest daily close.
* Mutual funds — MFAPI.in (``/mf/{scheme_code}/latest``), the free public
  mirror of AMFI's daily NAV file that FOLIUM_MASTER.md §4 names.
* Gold — international spot, ``GC=F`` (USD per troy ounce) x ``INR=X``
  (rupees per dollar) / 31.1035 g. This is an exact conversion. It does NOT
  include Indian import duty or GST, so retail jewellery prices run higher;
  the UI says so wherever the figure appears. (GOLDBEES was considered, but
  turning a unit price into rupees per gram needs the ETF's grams-per-unit
  ratio, which drifts with expenses — a guess would be worse than a clearly
  labelled spot price.)

Every lookup is cached for 15 minutes, bounded by a timeout, and returns
``None`` instead of raising: a missing price shows as "price unavailable" in
the app, it never breaks a page.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)
for _noisy in ("yfinance", "peewee"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_TTL = 15 * 60
_TIMEOUT = 8.0
_MFAPI = "https://api.mfapi.in"
_TROY_OUNCE_GRAMS = 31.1034768

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def _cached(key: str, fetch: Callable[[], Any]) -> Any:
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    value = fetch()
    if value is not None:
        with _lock:
            _cache[key] = (now, value)
    return value


async def _run(fn: Callable[[], Any], what: str) -> Any:
    # Same switch as market context: off in the test suite, so no test ever
    # depends on Yahoo Finance or MFAPI being reachable.
    if not get_settings().MARKET_DATA_ENABLED:
        return None
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn), timeout=_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — every failure degrades to "unavailable"
        logger.warning("price_unavailable", what=what, error=f"{type(exc).__name__}: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Stocks
# --------------------------------------------------------------------------- #

def _yf_last(ticker: str) -> Optional[dict[str, float]]:
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
    closes = hist["Close"].dropna() if not hist.empty else []
    if len(closes) == 0:
        return None
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) > 1 else last
    return {"price": round(last, 2), "change_pct": round((last / prev - 1) * 100, 2) if prev else 0.0}


async def stock_quote(symbol: str, exchange: str = "NSE") -> Optional[dict[str, Any]]:
    suffix = ".BO" if exchange.upper() == "BSE" else ".NS"
    ticker = f"{symbol.strip().upper()}{suffix}"
    quote = await _run(lambda: _cached(f"stock:{ticker}", lambda: _yf_last(ticker)), ticker)
    if quote:
        quote = {**quote, "source": "live", "as_of": datetime.now(timezone.utc).isoformat()}
    return quote


# --------------------------------------------------------------------------- #
# A stock's own risk, for simulation v2
# --------------------------------------------------------------------------- #

#: Used when a stock's history can't be fetched: the median NIFTY 50 stock,
#: measured over 2016-2026 (results/reports/SIMULATOR_V2.md).
DEFAULT_STOCK_RISK = {"beta": 1.0, "specific_vol": 0.21}
_MIN_MONTHS = 36


def estimate_stock_risk(stock_returns, market_returns) -> Optional[dict[str, float]]:
    """Beta to NIFTY and the stock's own (company-specific) yearly volatility.

    Monthly simple returns, aligned. Beta is cov/var; the specific volatility
    is the standard deviation of what the market doesn't explain, annualised.
    Clipped to plausible ranges so one odd series can't drive a projection.
    """
    import numpy as np

    s = np.asarray(stock_returns, dtype=float)
    m = np.asarray(market_returns, dtype=float)
    ok = np.isfinite(s) & np.isfinite(m)
    s, m = s[ok], m[ok]
    if len(s) < _MIN_MONTHS or m.var() == 0:
        return None
    beta = float(np.cov(s, m)[0, 1] / m.var(ddof=1))
    resid = s - beta * m
    return {
        "beta": round(min(max(beta, 0.3), 2.0), 3),
        "specific_vol": round(min(max(float(resid.std(ddof=1)) * 12 ** 0.5, 0.05), 0.60), 4),
        "months": int(len(s)),
    }


def _yf_risk(ticker: str) -> Optional[dict[str, Any]]:
    import yfinance as yf

    def monthly(t: str):
        h = yf.Ticker(t).history(period="10y", interval="1mo", auto_adjust=True)
        if h.empty:
            return None
        r = h["Close"].pct_change().dropna()
        r.index = r.index.tz_localize(None).to_period("M")
        return r

    stock, market = monthly(ticker), monthly("^NSEI")
    if stock is None or market is None:
        return None
    joined = stock.to_frame("s").join(market.to_frame("m"), how="inner")
    est = estimate_stock_risk(joined["s"].to_numpy(), joined["m"].to_numpy())
    return {**est, "source": "measured", "period": "10 years, monthly"} if est else None


async def stock_risk(symbol: str, exchange: str = "NSE") -> Optional[dict[str, Any]]:
    """Measured beta and specific volatility, or None (the caller discloses the default)."""
    suffix = ".BO" if exchange.upper() == "BSE" else ".NS"
    ticker = f"{symbol.strip().upper()}{suffix}"
    return await _run(lambda: _cached(f"risk:{ticker}", lambda: _yf_risk(ticker)), f"risk:{ticker}")


# --------------------------------------------------------------------------- #
# Mutual funds (MFAPI.in)
# --------------------------------------------------------------------------- #

def _mf_latest(code: str) -> Optional[dict[str, Any]]:
    r = httpx.get(f"{_MFAPI}/mf/{code}/latest", timeout=_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    data = (body.get("data") or [None])[0]
    if not data:
        return None
    return {
        "price": round(float(data["nav"]), 4),
        "as_of": data.get("date"),
        "name": (body.get("meta") or {}).get("scheme_name"),
    }


async def mf_nav(scheme_code: str) -> Optional[dict[str, Any]]:
    code = str(scheme_code).strip()
    if not code.isdigit():
        return None
    nav = await _run(lambda: _cached(f"mf:{code}", lambda: _mf_latest(code)), f"mf:{code}")
    if nav:
        nav = {**nav, "source": "live"}
    return nav


def _mf_search(query: str) -> list[dict[str, Any]]:
    r = httpx.get(f"{_MFAPI}/mf/search", params={"q": query}, timeout=_TIMEOUT)
    r.raise_for_status()
    return [
        {"scheme_code": str(item["schemeCode"]), "name": item["schemeName"]}
        for item in r.json()[:20]
    ]


async def mf_search(query: str) -> list[dict[str, Any]]:
    q = query.strip()
    if len(q) < 3:
        return []
    found = await _run(lambda: _cached(f"mfsearch:{q.lower()}", lambda: _mf_search(q)), "mf_search")
    return found or []


# --------------------------------------------------------------------------- #
# Gold
# --------------------------------------------------------------------------- #

def _gold_per_gram() -> Optional[float]:
    usd_oz = _yf_last("GC=F")
    usd_inr = _yf_last("INR=X")
    if not usd_oz or not usd_inr:
        return None
    return round(usd_oz["price"] * usd_inr["price"] / _TROY_OUNCE_GRAMS, 2)


async def gold_price_per_gram() -> Optional[dict[str, Any]]:
    price = await _run(lambda: _cached("gold:inr_per_gram", _gold_per_gram), "gold")
    if price is None:
        return None
    return {
        "price": price,
        "source": "live",
        "basis": "International spot price, excluding Indian import duty and GST",
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
