"""
tests/test_market_data.py
==========================
Unit tests for src/market_data.py (MarketDataFetcher).
Tests use mocking to avoid real network calls.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Ensure src/ is on the path
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from market_data import MarketDataFetcher, get_fetcher, _build_default_response, CACHE_TTL_SEC


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

def _make_fake_history(n: int = 60, start_price: float = 22000.0) -> pd.DataFrame:
    """Return a fake OHLCV DataFrame mimicking yfinance output."""
    import numpy as np
    prices = start_price * (1 + np.random.default_rng(42).normal(0, 0.01, n)).cumprod()
    return pd.DataFrame({"Close": prices})


# ─────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────

class TestMarketDataFetcherDefaults:
    """Tests that don't require network access."""

    def test_default_response_has_required_keys(self):
        resp = _build_default_response()
        assert "market_return"     in resp
        assert "market_volatility" in resp
        assert "crowd_ratio"       in resp
        assert "last_updated"      in resp
        assert "data_source"       in resp
        assert resp["data_source"] == "default_fallback"

    def test_fallback_on_fetch_error(self):
        """When internal fetch fails, get_market_context() returns default values."""
        fetcher = MarketDataFetcher()
        with patch.object(fetcher, "_fetch_from_yfinance", side_effect=RuntimeError("no net")):
            ctx = fetcher.get_market_context()
        assert ctx is not None
        assert "market_return" in ctx


class TestMarketDataFetcherCache:
    """Tests for the TTL caching mechanism."""

    def test_cache_is_used_within_ttl(self):
        """Second call within TTL window should use cache, not re-fetch."""
        fetcher = MarketDataFetcher()
        # Pre-fill cache manually
        fetcher._cache    = {
            "market_return": 0.01, "market_volatility": 0.02,
            "crowd_ratio": 0.45, "last_updated": "2026-01-01T00:00:00+00:00",
            "data_source": "live",
        }
        fetcher._cache_ts = time.time()   # fresh timestamp

        ctx = fetcher.get_market_context()
        assert ctx["data_source"] == "cache"
        assert ctx["market_return"] == 0.01

    def test_stale_cache_triggers_refetch(self):
        """Cache older than TTL should attempt refetch."""
        fetcher = MarketDataFetcher()
        fetcher._cache    = {"market_return": 0.99, "market_volatility": 0.01,
                             "crowd_ratio": 0.5, "last_updated": "X", "data_source": "live"}
        fetcher._cache_ts = time.time() - CACHE_TTL_SEC - 1  # expired

        # Mock the internal fetch to fail → should fall back to stale cache
        with patch.object(fetcher, "_fetch_from_yfinance", side_effect=RuntimeError("fail")):
            ctx = fetcher.get_market_context()

        assert ctx["data_source"] == "cache"   # stale cache returned


class TestMarketDataFetcherLive:
    """Tests that mock yfinance responses."""

    def _make_ticker_mock(self, hist):
        ticker_mock = MagicMock()
        ticker_mock.history.return_value = hist
        return ticker_mock

    def test_live_fetch_returns_expected_keys(self):
        hist = _make_fake_history()
        fetcher = MarketDataFetcher()
        with patch("yfinance.Ticker", return_value=self._make_ticker_mock(hist)):
            ctx = fetcher.get_market_context()

        assert "market_return"     in ctx
        assert "market_volatility" in ctx
        assert "crowd_ratio"       in ctx
        assert ctx["data_source"]  == "live"

    def test_market_return_is_fraction(self):
        """market_return should be in fractional form (e.g. -0.05, not -5.0)."""
        hist = _make_fake_history()
        fetcher = MarketDataFetcher()
        with patch("yfinance.Ticker", return_value=self._make_ticker_mock(hist)):
            ctx = fetcher.get_market_context()

        assert -1.0 < ctx["market_return"] < 2.0   # sanity check

    def test_crowd_ratio_bounded(self):
        """crowd_ratio must be in [0, 1]."""
        hist = _make_fake_history()
        fetcher = MarketDataFetcher()
        with patch("yfinance.Ticker", return_value=self._make_ticker_mock(hist)):
            ctx = fetcher.get_market_context()
        assert 0.0 <= ctx["crowd_ratio"] <= 1.0


class TestIsMarketHours:
    """Tests for is_market_hours()."""

    def test_returns_bool(self):
        fetcher = MarketDataFetcher()
        result  = fetcher.is_market_hours()
        assert isinstance(result, bool)


class TestGetFetcherSingleton:
    """Tests that get_fetcher() returns the same instance."""

    def test_singleton(self):
        f1 = get_fetcher()
        f2 = get_fetcher()
        assert f1 is f2
