"""
Unit tests for src/bias_detector.py
Run: python -m pytest tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────
# Import module under test (only bias_detector functions
# that do NOT require a trained model file to exist)
# ─────────────────────────────────────────────────────────
from bias_detector import _build_explanation, BIAS_LABELS


class TestBuildExplanation:
    def test_loss_aversion_explanation(self):
        msg = _build_explanation("loss_aversion", -0.15, 0.4, -0.08)
        assert "Loss Aversion" in msg
        assert "15.0%" in msg

    def test_herd_explanation(self):
        msg = _build_explanation("herd", -0.05, 0.80, -0.03)
        assert "Herd" in msg
        assert "80%" in msg

    def test_disposition_explanation(self):
        msg = _build_explanation("disposition", -0.05, 0.3, 0.0)
        assert "Disposition" in msg

    def test_rational_explanation(self):
        msg = _build_explanation("rational", 0.02, 0.4, 0.01)
        assert "Rational" in msg


class TestBiasLabels:
    def test_all_keys_exist(self):
        assert 0 in BIAS_LABELS
        assert "rational" in BIAS_LABELS.values()


# ─────────────────────────────────────────────────────────
# Integration test — requires trained model
# Skip if model file doesn't exist yet
# ─────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "bias_detector_xgboost.pkl"
)

@pytest.mark.skipif(
    not os.path.exists(MODEL_PATH),
    reason="Model not trained yet — run src/bias_detector.py first",
)
class TestRealTimeDetection:
    def test_panic_sell_scenario(self):
        from bias_detector import detect_bias_realtime

        result = detect_bias_realtime(
            market_return=-0.12,   # market crash
            unrealized_gl=-0.18,   # big loss
            crowd_ratio=0.85,      # almost everyone selling
            age=45,
            risk_tolerance=0.3,
            investment_horizon=10,
        )
        assert "bias_type" in result
        assert "confidence" in result
        assert "is_biased" in result
        assert result["inference_ms"] < 500   # must be fast

    def test_rational_scenario(self):
        from bias_detector import detect_bias_realtime

        result = detect_bias_realtime(
            market_return=0.02,
            unrealized_gl=0.05,
            crowd_ratio=0.40,
            age=30,
            risk_tolerance=0.6,
            investment_horizon=20,
        )
        assert result["bias_type"] in BIAS_LABELS.values()
