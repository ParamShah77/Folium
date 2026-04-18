"""
GAP 1 – Market Data Fetcher
============================
Fetches live market context using yfinance with a 15-minute in-memory
TTL cache and graceful fallback.

Indices tracked
---------------
    NIFTY50   (^NSEI)      — primary decision model input
    SENSEX    (^BSESN)     — top-ribbon display
    Bank NIFTY(^NSEBANK)   — top-ribbon display
    India VIX (^INDIAVIX)  — crowd fear proxy + top-ribbon display

Public API
----------
    fetcher = MarketDataFetcher()
    ctx     = fetcher.get_market_context()
    # → {market_return, market_volatility, crowd_ratio, last_updated, data_source}

    ribbon  = fetcher.get_indices_ribbon()
    # → {nifty50, sensex, banknifty, india_vix}  each with {price, change_pct, direction}

    fetcher.is_market_hours()  → True / False (NSE 9:15–15:30 IST)
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
NIFTY_TICKER      = "^NSEI"
SENSEX_TICKER     = "^BSESN"
BANKNIFTY_TICKER  = "^NSEBANK"
VIX_TICKER        = "^INDIAVIX"
CACHE_TTL_SEC     = 15 * 60   # 15 minutes

# NSE trading hours in IST (UTC+5:30)
IST       = timezone(timedelta(hours=5, minutes=30))
NSE_OPEN  = (9,  15)   # 09:15
NSE_CLOSE = (15, 30)   # 15:30

# Sensible defaults used when yfinance is completely unavailable
_DEFAULTS: dict[str, Any] = {
    "market_return"    : -0.005,
    "market_volatility": 0.18,
    "crowd_ratio"      : 0.50,
    "data_source"      : "default_fallback",
}

# Default ribbon when indices are unavailable
_RIBBON_DEFAULTS: dict[str, Any] = {
    "nifty50"   : {"price": None, "change_pct": None, "direction": "neutral", "label": "NIFTY 50"},
    "sensex"    : {"price": None, "change_pct": None, "direction": "neutral", "label": "SENSEX"},
    "banknifty" : {"price": None, "change_pct": None, "direction": "neutral", "label": "BANK NIFTY"},
    "india_vix" : {"price": None, "change_pct": None, "direction": "neutral", "label": "India VIX"},
}


# ═══════════════════════════════════════════════════════════
# MARKET DATA FETCHER
# ═══════════════════════════════════════════════════════════

class MarketDataFetcher:
    """
    Fetches NIFTY50 market context with a 15-minute TTL cache.

    Attributes
    ----------
    _cache : dict | None        — last successfully fetched payload
    _cache_ts : float           — Unix timestamp of last fetch
    _lock : threading.Lock      — protects cache updates (thread-safe)
    """

    def __init__(self) -> None:
        self._cache: dict | None = None
        self._cache_ts: float = 0.0
        self._ribbon_cache: dict | None = None
        self._ribbon_ts: float = 0.0
        self._lock = threading.Lock()

    # ─────────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────────

    def get_market_context(self) -> dict:
        """
        Return market context dict:
            {
              market_return:     float  — 1-month % change of NIFTY50
              market_volatility: float  — 30-day rolling std of daily returns
              crowd_ratio:       float  — VIX-derived crowd fear proxy [0, 1]
              last_updated:      str    — ISO-8601 UTC timestamp
              data_source:       str    — 'live', 'cache', or 'default_fallback'
            }

        Falls back to cached data, then to hardcoded defaults on any error.
        """
        with self._lock:
            # Return cached data if still fresh
            if self._cache and (time.time() - self._cache_ts) < CACHE_TTL_SEC:
                cached = dict(self._cache)
                cached["data_source"] = "cache"
                return cached

            # Try to fetch fresh data
            try:
                data = self._fetch_from_yfinance()
                self._cache = data
                self._cache_ts = time.time()
                return dict(data)
            except Exception as exc:                  # noqa: BLE001
                logger.warning("MarketDataFetcher: yfinance error — %s", exc)
                # Return stale cache if available
                if self._cache:
                    stale = dict(self._cache)
                    stale["data_source"] = "cache"
                    return stale
                # Last-resort: hardcoded defaults
                return _build_default_response()

    def is_market_hours(self) -> bool:
        """Return True if current IST time is within NSE trading hours."""
        now      = datetime.now(IST)
        open_dt  = now.replace(hour=NSE_OPEN[0],  minute=NSE_OPEN[1],  second=0, microsecond=0)
        close_dt = now.replace(hour=NSE_CLOSE[0], minute=NSE_CLOSE[1], second=0, microsecond=0)
        # Also skip weekends (Saturday=5, Sunday=6)
        if now.weekday() >= 5:
            return False
        return open_dt <= now <= close_dt

    # ─────────────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────────────

    def get_indices_ribbon(self) -> dict:
        """
        Return latest prices + 1-day % change for 4 indices:
            nifty50, sensex, banknifty, india_vix

        Uses the same 15-min TTL cache. Falls back to _RIBBON_DEFAULTS on error.
        """
        with self._lock:
            if self._ribbon_cache and (time.time() - self._ribbon_ts) < CACHE_TTL_SEC:
                cached = dict(self._ribbon_cache)
                cached["data_source"] = "cache"
                return cached
            try:
                data = self._fetch_ribbon_from_yfinance()
                self._ribbon_cache = data
                self._ribbon_ts = time.time()
                return dict(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("MarketDataFetcher ribbon error — %s", exc)
                if self._ribbon_cache:
                    stale = dict(self._ribbon_cache)
                    stale["data_source"] = "cache"
                    return stale
                return {**_RIBBON_DEFAULTS, "data_source": "default_fallback",
                        "last_updated": datetime.now(timezone.utc).isoformat()}

    def _fetch_ribbon_from_yfinance(self) -> dict:
        """Fetch 2-day daily OHLCV for all 4 tickers, compute 1-day change."""
        import yfinance as yf

        tickers = {
            "nifty50"   : (NIFTY_TICKER,     "NIFTY 50"),
            "sensex"    : (SENSEX_TICKER,    "SENSEX"),
            "banknifty" : (BANKNIFTY_TICKER, "BANK NIFTY"),
            "india_vix" : (VIX_TICKER,       "India VIX"),
        }
        result: dict[str, Any] = {}
        for key, (symbol, label) in tickers.items():
            try:
                hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=True)
                hist = hist.dropna(subset=["Close"])
                if len(hist) >= 2:
                    prev  = float(hist["Close"].iloc[-2])
                    curr  = float(hist["Close"].iloc[-1])
                    chg   = round((curr - prev) / prev * 100, 2)
                    direction = "up" if chg >= 0 else "down"
                elif len(hist) == 1:
                    curr  = float(hist["Close"].iloc[-1])
                    chg   = None
                    direction = "neutral"
                else:
                    result[key] = {**_RIBBON_DEFAULTS[key]}
                    continue
                result[key] = {
                    "label"     : label,
                    "price"     : round(curr, 2),
                    "change_pct": chg,
                    "direction" : direction,
                }
            except Exception:  # noqa: BLE001
                result[key] = {**_RIBBON_DEFAULTS[key]}

        result["data_source"]  = "live"
        result["last_updated"] = datetime.now(timezone.utc).isoformat()
        return result

    def _fetch_from_yfinance(self) -> dict:
        """
        Core yfinance fetch logic.
        Raises any exception so the caller can handle fallback.
        """
        import yfinance as yf  # lazy import — optional dependency

        # ── NIFTY50 ──────────────────────────────────────────
        nifty = yf.Ticker(NIFTY_TICKER)
        hist  = nifty.history(period="3mo", interval="1d", auto_adjust=True)

        if hist.empty or len(hist) < 5:
            raise ValueError("NIFTY history is empty or too short")

        close   = hist["Close"].dropna()
        daily_r = close.pct_change().dropna()

        # 1-month % return: last 21 trading days
        lookback      = min(21, len(close) - 1)
        market_return = float((close.iloc[-1] / close.iloc[-lookback - 1]) - 1)

        # 30-day rolling std of daily returns
        vol_window = min(30, len(daily_r))
        market_vol = float(daily_r.iloc[-vol_window:].std())

        # ── INDIA VIX (crowd fear proxy) ─────────────────────
        crowd_ratio = self._fetch_vix_crowd_ratio(market_vol)

        return {
            "market_return"    : round(market_return, 6),
            "market_volatility": round(market_vol,    6),
            "crowd_ratio"      : round(crowd_ratio,   4),
            "last_updated"     : datetime.now(timezone.utc).isoformat(),
            "data_source"      : "live",
        }

    def _fetch_vix_crowd_ratio(self, fallback_vol: float) -> float:
        """
        Compute crowd_ratio from India VIX in [0, 1].
        VIX = 15  → ~neutral  → crowd_ratio ≈ 0.40
        VIX = 25  → elevated  → crowd_ratio ≈ 0.65
        VIX = 40  → crash     → crowd_ratio ≈ 0.90

        Falls back to a volatility-based proxy if VIX unavailable.
        """
        try:
            import yfinance as yf
            vix_hist = yf.Ticker(VIX_TICKER).history(period="5d", interval="1d")
            if not vix_hist.empty:
                vix_val   = float(vix_hist["Close"].dropna().iloc[-1])
                # Normalise: VIX 10 → 0.20, VIX 50 → 1.0 (clamped)
                crowd     = (vix_val - 10.0) / 40.0
                return float(max(0.05, min(crowd, 1.0)))
        except Exception:  # noqa: BLE001
            pass

        # Fallback: use daily-vol as proxy (annualise roughly)
        # daily_vol * sqrt(252) ≈ annual vol → map 0→0.2 to 0.10→0.85
        ann_vol = fallback_vol * (252 ** 0.5)
        return float(max(0.10, min(ann_vol / 0.50, 0.90)))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _build_default_response() -> dict:
    """Return hardcoded safe defaults when all data sources are unavailable."""
    return {
        **_DEFAULTS,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────
# Module-level singleton (used by api.py)
# ─────────────────────────────────────────────
_fetcher_instance: MarketDataFetcher | None = None


def get_fetcher() -> MarketDataFetcher:
    """Return (or create) the module-level singleton MarketDataFetcher."""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = MarketDataFetcher()
    return _fetcher_instance


# ─────────────────────────────────────────────
# QUICK SMOKE TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import json
    f   = MarketDataFetcher()
    ctx = f.get_market_context()
    print("Market context:")
    print(json.dumps(ctx, indent=2))
    print(f"Market hours: {f.is_market_hours()}")
