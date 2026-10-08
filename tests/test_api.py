"""
tests/test_api.py
==================
Integration-style tests for the FastAPI app using TestClient.
Uses mocking for bias_detector, causal_inference, and market_data.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """TestClient with mocked heavy dependencies."""
    from fastapi.testclient import TestClient

    # Mock the bias detector model loading
    with (
        patch("bias_detector._model_cache", MagicMock()),
        patch("bias_detector._feature_cache", ["unrealized_gain_loss", "crowd_action_ratio"]),
        patch("bias_detector.detect_bias_realtime", return_value={
            "bias_type"       : "loss_aversion",
            "confidence"      : 0.87,
            "probabilities"   : {"disposition": 0.05, "herd": 0.03, "loss_aversion": 0.87, "rational": 0.05},
            "is_biased"       : True,
            "explanation"     : "Loss Aversion Detected",
            "shap_explanation": [
                {"feature": "unrealized_gain_loss", "value": -0.18, "shap_impact": 0.31, "direction": "increases_bias"}
            ],
            "inference_ms"    : 5.2,
        }),
        patch("integration.analyze_decision_realtime", return_value={
            "bias_type"       : "loss_aversion",
            "bias_label"      : "Loss Aversion",
            "confidence"      : 0.87,
            "all_probabilities": {"disposition": 0.05, "herd": 0.03, "loss_aversion": 0.87, "rational": 0.05},
            "causal_chain"    : ["loss_aversion → decision: +0.30"],
            "intervention"    : "Reframe losses via cognitive therapy",
            "causal_effects"  : None,
            "risk_score"      : 0.72,
            "explanation"     : "Loss Aversion Detected",
            "shap_explanation": [],
            "timestamp_ms"    : 1700000000000,
        }),
        patch("market_data.MarketDataFetcher.get_market_context", return_value={
            "market_return"    : -0.03,
            "market_volatility": 0.018,
            "crowd_ratio"      : 0.55,
            "last_updated"     : "2026-04-01T12:00:00+00:00",
            "data_source"      : "live",
        }),
        patch("market_data.MarketDataFetcher.is_market_hours", return_value=True),
    ):
        from api import app
        from database import DatabaseManager
        # Use in-memory DB for tests
        app.state.db      = DatabaseManager(":memory:")
        app.state.fetcher = MagicMock()
        app.state.fetcher.get_market_context.return_value = {
            "market_return": -0.03, "market_volatility": 0.018,
            "crowd_ratio": 0.55, "last_updated": "2026-04-01T12:00:00+00:00",
            "data_source": "live",
        }
        app.state.fetcher.is_market_hours.return_value = True

        with TestClient(app) as c:
            yield c


# ─────────────────────────────────────────────
# HEALTH & STATUS TESTS
# ─────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_has_timestamp(self, client):
        resp = client.get("/health")
        assert "timestamp_ms" in resp.json()


# ─────────────────────────────────────────────
# USER REGISTRATION TESTS
# ─────────────────────────────────────────────

class TestUserRegistration:
    def test_register_returns_201_or_200(self, client):
        resp = client.post("/user/register", json={
            "name": "Arjun", "age": 32,
            "monthly_income": 80000, "risk_tolerance": 0.6,
            "investment_horizon": 15, "has_emergency_fund": 1,
        })
        assert resp.status_code == 200

    def test_register_response_has_user_id(self, client):
        resp = client.post("/user/register", json={
            "name": "Priya", "age": 28,
            "monthly_income": 60000, "risk_tolerance": 0.4,
            "investment_horizon": 10, "has_emergency_fund": 0,
        })
        body = resp.json()
        assert "user_id" in body
        assert len(body["user_id"]) == 36   # UUID4

    def test_register_returns_onboarding_questions(self, client):
        resp = client.post("/user/register", json={
            "name": "Ravi", "age": 45,
            "monthly_income": 150000, "risk_tolerance": 0.7,
            "investment_horizon": 20, "has_emergency_fund": 1,
        })
        body = resp.json()
        assert "onboarding_questions" in body
        assert len(body["onboarding_questions"]) == 5


# ─────────────────────────────────────────────
# USER PROFILE TESTS
# ─────────────────────────────────────────────

class TestUserProfile:
    def _register(self, client) -> str:
        resp = client.post("/user/register", json={
            "name": "Test", "age": 30,
            "monthly_income": 70000, "risk_tolerance": 0.5,
            "investment_horizon": 12, "has_emergency_fund": 1,
        })
        return resp.json()["user_id"]

    def test_get_profile_returns_200(self, client):
        uid  = self._register(client)
        resp = client.get(f"/user/{uid}/profile")
        assert resp.status_code == 200

    def test_get_profile_has_bias_profile(self, client):
        uid  = self._register(client)
        resp = client.get(f"/user/{uid}/profile")
        body = resp.json()
        assert "bias_profile" in body

    def test_get_unknown_user_returns_404(self, client):
        resp = client.get("/user/nonexistent-user-id/profile")
        assert resp.status_code == 404

    def test_get_decisions_empty_initially(self, client):
        uid  = self._register(client)
        resp = client.get(f"/user/{uid}/decisions")
        assert resp.status_code == 200
        assert resp.json()["decision_count"] == 0


# ─────────────────────────────────────────────
# ANALYZE DECISION TESTS
# ─────────────────────────────────────────────

DECISION_PAYLOAD = {
    "unrealized_gl"        : -0.18,
    "age"                  : 35,
    "risk_tolerance"       : 0.5,
    "investment_horizon"   : 10,
    "monthly_income"       : 60000,
    "monthly_expense"      : 45000,
    "holding_period_months": 6,
    "position_size_pct"    : 0.10,
}


class TestAnalyzeDecision:
    def test_analyze_returns_200(self, client):
        resp = client.post("/analyze/decision", json=DECISION_PAYLOAD)
        assert resp.status_code == 200

    def test_analyze_has_required_fields(self, client):
        resp = client.post("/analyze/decision", json=DECISION_PAYLOAD)
        body = resp.json()
        assert "bias_type"       in body
        assert "confidence"      in body
        assert "risk_score"      in body
        assert "intervention"    in body

    def test_analyze_returns_decision_id(self, client):
        """DB logging should assign a decision_id."""
        resp = client.post("/analyze/decision", json=DECISION_PAYLOAD)
        body = resp.json()
        assert "decision_id" in body
        assert len(body["decision_id"]) == 36

    def test_analyze_returns_audit_hash(self, client):
        resp = client.post("/analyze/decision", json=DECISION_PAYLOAD)
        body = resp.json()
        assert "audit_hash"  in body
        assert len(body["audit_hash"]) > 0


# ─────────────────────────────────────────────
# AUDIT TRAIL TESTS
# ─────────────────────────────────────────────

class TestAuditTrail:
    def test_audit_for_valid_decision(self, client):
        # Submit a decision first
        resp = client.post("/analyze/decision", json=DECISION_PAYLOAD)
        did  = resp.json()["decision_id"]

        # Fetch audit trail
        audit_resp = client.get(f"/audit/{did}")
        assert audit_resp.status_code == 200
        body = audit_resp.json()
        assert body["decision_id"] == did
        assert "tamper_detected"   in body
        assert body["tamper_detected"] is False

    def test_audit_unknown_decision_returns_404(self, client):
        resp = client.get("/audit/nonexistent-decision-id")
        assert resp.status_code == 404


# ─────────────────────────────────────────────
# MARKET CONTEXT TESTS
# ─────────────────────────────────────────────

class TestMarketContext:
    def test_market_context_returns_200(self, client):
        resp = client.get("/market/context")
        assert resp.status_code == 200

    def test_market_context_has_required_keys(self, client):
        resp = client.get("/market/context")
        body = resp.json()
        assert "market_return"     in body
        assert "market_volatility" in body
        assert "crowd_ratio"       in body


# ─────────────────────────────────────────────
# GAP 3 — EXPLANATION ENDPOINTS
# ─────────────────────────────────────────────

class TestExplainEndpoint:
    """
    The explanation must survive anything the optional LLM layer does. A user
    asking why they are being told to hold gets an answer, not a 500.
    """

    PAYLOAD = {"user_id": 42, "current_wealth": 75_000, "unrealized_gl": -0.15,
               "n_simulations": 200}

    def test_explain_returns_all_six_sections(self, client):
        resp = client.post("/explain", json=self.PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sections"]) == 6
        assert all(s["text"].strip() for s in body["sections"])

    def test_explain_supports_hindi(self, client):
        resp = client.post("/explain", json={**self.PAYLOAD, "lang": "hi"})
        assert resp.status_code == 200
        assert resp.json()["lang"] == "hi"

    def test_explain_survives_a_failing_llm_key(self, client, monkeypatch):
        """
        The whole point of the fallback: a dead key costs the wording, never
        the explanation, and never surfaces as an error.
        """
        import llm_polish

        monkeypatch.setenv("EXPLAINER_LLM", "on")
        monkeypatch.setenv("GEMINI_API_KEY", "definitely-not-a-valid-key")
        monkeypatch.setenv("EXPLAINER_LLM_PROVIDER", "stub")
        monkeypatch.setattr(llm_polish, "_env_loaded", True, raising=False)
        monkeypatch.setitem(
            llm_polish._PROVIDERS, "stub",
            lambda prompt, timeout: (_ for _ in ()).throw(RuntimeError("401 API_KEY_INVALID")))
        llm_polish.clear_cache()

        resp = client.post("/explain", json=self.PAYLOAD)
        assert resp.status_code == 200, f"a bad key surfaced as {resp.status_code}"
        body = resp.json()
        assert len(body["sections"]) == 6
        assert body["polished"] is False
        assert all(s["text"].strip() for s in body["sections"])

    def test_report_download_survives_a_failing_llm_key(self, client, monkeypatch):
        import llm_polish

        monkeypatch.setenv("EXPLAINER_LLM", "on")
        monkeypatch.setenv("GEMINI_API_KEY", "definitely-not-a-valid-key")
        monkeypatch.setenv("EXPLAINER_LLM_PROVIDER", "stub")
        monkeypatch.setattr(llm_polish, "_env_loaded", True, raising=False)
        monkeypatch.setitem(
            llm_polish._PROVIDERS, "stub",
            lambda prompt, timeout: (_ for _ in ()).throw(ConnectionError("no network")))
        llm_polish.clear_cache()

        resp = client.post("/explain/report", json={**self.PAYLOAD, "format": "html"})
        assert resp.status_code == 200
        assert b"<table>" in resp.content

    def test_status_reports_llm_configuration(self, client):
        body = client.get("/explain/status").json()
        assert set(body["languages"]) == {"en", "hi"}
        assert "llm_polish" in body
        assert "key_set" in body["llm_polish"]
        assert "GEMINI" not in str(body), "configuration must never echo a key"
