"""
Unit & integration tests for causal modules.
Run: python -m pytest tests/test_causal_inference.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
import networkx as nx
import pytest


# ── Helpers ───────────────────────────────────────────────
PROCESSED = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
MODELS    = os.path.join(os.path.dirname(__file__), "..", "models")
RESULTS   = os.path.join(os.path.dirname(__file__), "..", "results")

data_ready  = os.path.exists(os.path.join(PROCESSED, "merged_features.csv"))
graph_ready = os.path.exists(os.path.join(MODELS, "causal_graph.pkl"))
fx_ready    = os.path.exists(os.path.join(RESULTS, "causal_effects.pkl"))


# ═══════════════════════════════════════════════════════════
# causal_utils
# ═══════════════════════════════════════════════════════════
@pytest.mark.skipif(not data_ready, reason="Run data_preparation.py first")
class TestCausalUtils:
    def test_load_returns_dataframe(self):
        from causal_utils import load_causal_data
        df_raw, df_norm, scaler = load_causal_data(normalize=True)
        assert isinstance(df_raw, pd.DataFrame)
        assert len(df_raw) > 0

    def test_decision_column_exists(self):
        from causal_utils import load_causal_data
        df_raw, _, _ = load_causal_data()
        assert "decision" in df_raw.columns

    def test_normalized_mean_near_zero(self):
        from causal_utils import load_causal_data
        _, df_norm, _ = load_causal_data(normalize=True)
        # After StandardScaler each column should have ~0 mean
        means = df_norm.mean()
        assert (means.abs() < 0.01).all(), f"Means not near 0:\n{means}"

    def test_no_missing_values(self):
        from causal_utils import load_causal_data
        df_raw, _, _ = load_causal_data()
        assert df_raw.isnull().sum().sum() == 0


# ═══════════════════════════════════════════════════════════
# causal_structure  (unit tests — no file I/O)
# ═══════════════════════════════════════════════════════════
class TestDomainGraph:
    """Test the domain-knowledge DAG builder independently."""

    @pytest.fixture
    def sample_df(self):
        np.random.seed(42)
        n = 200
        return pd.DataFrame({
            "market_return"       : np.random.randn(n) * 0.05,
            "crowd_ratio"         : np.random.uniform(0, 1, n),
            "loss_aversion"       : np.random.uniform(1, 4, n),
            "herd_sensitivity"    : np.random.uniform(0, 1, n),
            "disposition_strength": np.random.uniform(0, 1, n),
            "unrealized_gl"       : np.random.randn(n) * 0.15,
            "risk_tolerance"      : np.random.uniform(0.1, 0.9, n),
            "decision"            : np.random.randint(0, 2, n),
        })

    def test_returns_digraph(self, sample_df):
        from causal_structure import build_domain_graph
        G = build_domain_graph(sample_df)
        assert isinstance(G, nx.DiGraph)

    def test_decision_is_a_node(self, sample_df):
        from causal_structure import build_domain_graph
        G = build_domain_graph(sample_df)
        assert "decision" in G.nodes()

    def test_edges_have_weights(self, sample_df):
        from causal_structure import build_domain_graph
        G = build_domain_graph(sample_df)
        for u, v, data in G.edges(data=True):
            assert "weight" in data, f"Edge {u}→{v} missing weight"

    def test_is_dag(self, sample_df):
        from causal_structure import build_domain_graph, validate_dag
        G = build_domain_graph(sample_df)
        G = validate_dag(G)
        assert nx.is_directed_acyclic_graph(G)


class TestGMLConversion:
    def test_gml_contains_nodes_and_edges(self):
        from causal_inference import graph_to_gml
        G = nx.DiGraph()
        G.add_edge("A", "B")
        gml = graph_to_gml(G)
        assert "A" in gml
        assert "B" in gml
        assert "edge" in gml


# ═══════════════════════════════════════════════════════════
# causal_inference — intervention simulation
# ═══════════════════════════════════════════════════════════
class TestInterventionSimulation:
    """Test simulate_intervention without needing real causal effects."""

    @pytest.fixture
    def mock_causal_effects(self):
        return {
            "loss_aversion"   : {"causal_effect": 0.25},
            "crowd_ratio"     : {"causal_effect": 0.18},
            "herd_sensitivity": {"causal_effect": 0.12},
        }

    @pytest.fixture
    def user_row(self):
        return pd.Series({
            "loss_aversion"   : 2.5,
            "crowd_ratio"     : 0.80,
            "herd_sensitivity": 0.70,
        })

    def test_remove_loss_aversion(self, user_row, mock_causal_effects):
        from causal_inference import simulate_intervention
        result = simulate_intervention(user_row, "remove_loss_aversion", mock_causal_effects)
        assert result["new_sell_prob"] < result["original_sell_prob"]
        assert 0.0 <= result["new_sell_prob"] <= 1.0

    def test_hide_crowd_signal(self, user_row, mock_causal_effects):
        from causal_inference import simulate_intervention
        result = simulate_intervention(user_row, "hide_crowd_signal", mock_causal_effects)
        assert 0.0 <= result["new_sell_prob"] <= 1.0

    def test_combined_greater_reduction(self, user_row, mock_causal_effects):
        from causal_inference import simulate_intervention
        r_single  = simulate_intervention(user_row, "remove_loss_aversion", mock_causal_effects)
        r_combined = simulate_intervention(user_row, "combined", mock_causal_effects)
        # Combined must reduce more (or equal) than single
        assert r_combined["new_sell_prob"] <= r_single["new_sell_prob"] + 1e-6

    def test_result_has_required_keys(self, user_row, mock_causal_effects):
        from causal_inference import simulate_intervention
        result = simulate_intervention(user_row, "remove_loss_aversion", mock_causal_effects)
        for key in ("intervention", "description", "original_sell_prob",
                    "new_sell_prob", "delta_sell_prob", "recommendation"):
            assert key in result

    def test_invalid_intervention_raises(self, user_row, mock_causal_effects):
        from causal_inference import simulate_intervention
        with pytest.raises(ValueError):
            simulate_intervention(user_row, "nonexistent_intervention", mock_causal_effects)


class TestGetRecommendation:
    def test_loss_aversion_maps_to_reframe(self):
        from causal_inference import get_intervention_recommendation
        rec = get_intervention_recommendation("loss_aversion")
        assert "reframe" in rec.lower() or "remove" in rec.lower() or "loss" in rec.lower()

    def test_rational_returns_no_intervention(self):
        from causal_inference import get_intervention_recommendation
        rec = get_intervention_recommendation("rational")
        assert "no intervention" in rec.lower() or "rational" in rec.lower()

    def test_herd_maps_to_crowd_intervention(self):
        from causal_inference import get_intervention_recommendation
        rec = get_intervention_recommendation("herd")
        assert "crowd" in rec.lower()


# ═══════════════════════════════════════════════════════════
# Integration tests — require fully run pipelines
# ═══════════════════════════════════════════════════════════
@pytest.mark.skipif(not graph_ready, reason="Run causal_structure.py first")
class TestCausalGraphLoaded:
    def test_graph_is_dag(self):
        from causal_structure import load_causal_graph
        G, _ = load_causal_graph()
        assert nx.is_directed_acyclic_graph(G)

    def test_decision_reachable_from_at_least_one_node(self):
        from causal_structure import load_causal_graph
        G, _ = load_causal_graph()
        if "decision" in G.nodes():
            preds = list(G.predecessors("decision"))
            assert len(preds) > 0, "No node has a causal path to 'decision'!"


@pytest.mark.skipif(not fx_ready, reason="Run causal_inference.py first")
class TestCausalResultsFile:
    def test_effects_file_has_treatments(self):
        from causal_inference import load_causal_results
        data = load_causal_results()
        assert "causal_effects" in data
        assert len(data["causal_effects"]) > 0

    def test_interventions_all_present(self):
        from causal_inference import load_causal_results, INTERVENTIONS
        data = load_causal_results()
        for key in INTERVENTIONS:
            assert key in data["interventions"], f"Missing intervention: {key}"
