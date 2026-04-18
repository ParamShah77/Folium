"""
tests/test_database.py
=======================
Unit tests for src/database.py (DatabaseManager).
All tests use an in-memory SQLite database — no file I/O.
"""

from __future__ import annotations

import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from database import DatabaseManager, _sha256, _running_avg


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def db():
    """Fresh in-memory DatabaseManager for each test."""
    manager = DatabaseManager(":memory:")
    yield manager
    manager.close()


def _sample_user() -> dict:
    return {
        "name"              : "Ravi",
        "age"               : 35,
        "monthly_income"    : 75000.0,
        "risk_tolerance"    : 0.6,
        "investment_horizon": 15,
        "has_emergency_fund": 1,
    }


def _sample_decision(user_id: str) -> dict:
    return {
        "user_id"       : user_id,
        "bias_detected" : "loss_aversion",
        "confidence"    : 0.87,
        "recommendation": "Hold and review in 30 days",
        "risk_score"    : 0.72,
        "raw_input"     : {"market_return": -0.10},
        "raw_output"    : {"bias_type": "loss_aversion"},
    }


# ─────────────────────────────────────────────
# HELPER FUNCTION TESTS
# ─────────────────────────────────────────────

def test_sha256():
    h = _sha256("hello")
    assert len(h) == 64
    assert _sha256("hello") == _sha256("hello")
    assert _sha256("hello") != _sha256("world")


def test_running_avg_first_decision():
    """First decision: avg = new_val."""
    assert _running_avg(0.0, 1.0, 0) == pytest.approx(1.0)


def test_running_avg_accumulation():
    """Running average should converge correctly."""
    avg = 0.0
    for _ in range(10):
        avg = _running_avg(avg, 1.0, 10)   # all loss_aversion
    # avg should be close to 1.0 (biased estimation)
    assert avg > 0.5


# ─────────────────────────────────────────────
# USER MANAGEMENT TESTS
# ─────────────────────────────────────────────

class TestRegisterUser:
    def test_register_returns_uuid(self, db):
        uid = db.register_user(_sample_user())
        assert isinstance(uid, str)
        assert len(uid) == 36   # UUID4 format

    def test_register_creates_profile(self, db):
        uid  = db.register_user(_sample_user())
        user = db.get_user(uid)
        assert user is not None
        assert user["age"] == 35
        assert user["monthly_income"] == pytest.approx(75000.0)

    def test_register_creates_bias_profile(self, db):
        uid     = db.register_user(_sample_user())
        profile = db.get_bias_profile(uid)
        assert profile is not None
        assert profile["total_decisions"] == 0
        assert profile["disposition_score"] == pytest.approx(0.0)

    def test_get_unknown_user_returns_none(self, db):
        assert db.get_user("nonexistent-id") is None


# ─────────────────────────────────────────────
# BIAS PROFILE UPDATE TESTS
# ─────────────────────────────────────────────

class TestUpdateBiasProfile:
    def test_update_increments_counter(self, db):
        uid = db.register_user(_sample_user())
        db.update_bias_profile(uid, "loss_aversion")
        profile = db.get_bias_profile(uid)
        assert profile["total_decisions"] == 1

    def test_update_correct_class(self, db):
        uid = db.register_user(_sample_user())
        db.update_bias_profile(uid, "herd")
        profile = db.get_bias_profile(uid)
        assert profile["herd_score"] == pytest.approx(1.0)
        assert profile["disposition_score"] == pytest.approx(0.0)

    def test_update_multiple_decisions(self, db):
        uid = db.register_user(_sample_user())
        db.update_bias_profile(uid, "herd")
        db.update_bias_profile(uid, "rational")
        profile = db.get_bias_profile(uid)
        assert profile["total_decisions"] == 2
        # herd_score should be ~0.5 after 1 herd + 1 rational
        assert 0.4 < profile["herd_score"] < 0.6

    def test_update_unknown_user_creates_profile(self, db):
        """Should not crash for unknown user — creates fresh entry."""
        uid = db.register_user(_sample_user())
        # Manually delete bias profile to test edge case
        db._conn.execute("DELETE FROM bias_profiles_live WHERE user_id = ?", (uid,))
        db._conn.commit()
        db.update_bias_profile(uid, "disposition")
        profile = db.get_bias_profile(uid)
        assert profile is not None


# ─────────────────────────────────────────────
# DECISION LOGGING TESTS
# ─────────────────────────────────────────────

class TestLogDecision:
    def test_log_returns_uuid(self, db):
        uid = db.register_user(_sample_user())
        did = db.log_decision(_sample_decision(uid))
        assert isinstance(did, str)
        assert len(did) == 36

    def test_decision_history_populated(self, db):
        uid = db.register_user(_sample_user())
        db.log_decision(_sample_decision(uid))
        db.log_decision(_sample_decision(uid))
        history = db.get_user_decision_history(uid)
        assert len(history) == 2

    def test_decision_history_order(self, db):
        """Most recent decision should appear first."""
        import time
        uid = db.register_user(_sample_user())
        db.log_decision(_sample_decision(uid))
        time.sleep(0.01)
        db.log_decision({**_sample_decision(uid), "bias_detected": "herd"})
        history = db.get_user_decision_history(uid)
        assert history[0]["bias_detected"] == "herd"   # newest first


# ─────────────────────────────────────────────
# AUDIT LOG TESTS
# ─────────────────────────────────────────────

class TestAuditLog:
    def test_append_returns_uuid(self, db):
        uid = db.register_user(_sample_user())
        did = db.log_decision(_sample_decision(uid))
        log_id = db.append_audit_log({
            "decision_id"     : did,
            "input_hash"      : "abc123",
            "output_hash"     : "def456",
            "explanation_hash": "ghi789",
        })
        assert isinstance(log_id, str)

    def test_audit_trail_retrieved(self, db):
        uid = db.register_user(_sample_user())
        did = db.log_decision(_sample_decision(uid))
        db.append_audit_log({
            "decision_id"     : did,
            "input_hash"      : "abc123",
            "output_hash"     : "def456",
            "explanation_hash": "ghi789",
        })
        trail = db.get_audit_trail(did)
        assert trail is not None
        assert trail["decision_id"] == did

    def test_tamper_detection_clean(self, db):
        """Unmodified record should have tamper_detected = False."""
        uid = db.register_user(_sample_user())
        did = db.log_decision(_sample_decision(uid))
        db.append_audit_log({
            "decision_id"     : did,
            "input_hash"      : "abc",
            "output_hash"     : "def",
            "explanation_hash": "ghi",
        })
        trail = db.get_audit_trail(did)
        assert trail["tamper_detected"] is False
        assert trail["hash_verified"] is True

    def test_tamper_detection_dirty(self, db):
        """Manually corrupted full_hash should trigger tamper detection."""
        uid = db.register_user(_sample_user())
        did = db.log_decision(_sample_decision(uid))
        db.append_audit_log({
            "decision_id"     : did,
            "input_hash"      : "abc",
            "output_hash"     : "def",
            "explanation_hash": "ghi",
        })
        # Corrupt the hash in DB
        db._conn.execute(
            "UPDATE audit_logs SET full_hash = 'tampered_value' WHERE decision_id = ?",
            (did,),
        )
        db._conn.commit()
        trail = db.get_audit_trail(did)
        assert trail["tamper_detected"] is True

    def test_unknown_decision_returns_none(self, db):
        assert db.get_audit_trail("nonexistent-decision") is None


# ─────────────────────────────────────────────
# MARKET CACHE TESTS
# ─────────────────────────────────────────────

class TestMarketCache:
    def test_cache_and_retrieve(self, db):
        data = {"market_return": -0.03, "market_volatility": 0.02, "crowd_ratio": 0.60}
        db.cache_market_data("nifty50", data)
        cached = db.get_cached_market_data("nifty50")
        assert cached is not None
        assert cached["market_return"] == pytest.approx(-0.03)

    def test_upsert_overwrites(self, db):
        db.cache_market_data("nifty50", {"market_return": 0.01, "market_volatility": 0.01, "crowd_ratio": 0.3})
        db.cache_market_data("nifty50", {"market_return": 0.05, "market_volatility": 0.02, "crowd_ratio": 0.4})
        cached = db.get_cached_market_data("nifty50")
        assert cached["market_return"] == pytest.approx(0.05)
