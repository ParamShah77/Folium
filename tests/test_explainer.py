"""
tests/test_explainer.py
=======================
Unit tests for GAP 3 — the decision-centric explainability engine.

Run with:
    pytest tests/test_explainer.py -v

The tests enforce the promises the explanation makes to the user:

  ✅ Every explanation has all six sections, in both languages
  ✅ No jargon reaches the user (blocklist scan)
  ✅ Every rupee figure in the story comes from the simulation, not from nowhere
  ✅ The story is internally consistent (headline figure == final year figure)
  ✅ English reads at roughly 8th-grade level (Flesch >= 60)
  ✅ The template path is deterministic — same input, same words
  ✅ The LLM numeric guard rejects invented numbers
  ✅ Reports render in md / html, and Hindi PDF is refused rather than mangled
"""

from __future__ import annotations

import os
import re
import sys

import pytest

# ── Path setup ─────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import explanation_report as report_mod
import explanation_templates as T
import llm_polish
from explainer import (BIAS_ONLY_SECTIONS, DecisionExplainer, build_facts,
                       explain_bias_only, find_jargon,
                       generate_complete_explanation, reading_level,
                       render_markdown)

#: Rupee amounts as they appear in the narrative. The fractional part must be
#: followed by digits, so a sentence-ending full stop is not swallowed into
#: the amount ("₹75,000." -> "₹75,000").
MONEY_RE = re.compile(r"₹[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|लाख|करोड़))?")

LANGS = ("en", "hi")
BIASES = ("loss_aversion", "herd", "disposition", "rational")


# ══════════════════════════════════════════════════════════════════════════
# FIXTURES — synthetic Obj 1 / Obj 2 output, so tests need no models
# ══════════════════════════════════════════════════════════════════════════

def make_bias_result(bias="loss_aversion", confidence=0.87, with_effects=True):
    effects = {
        "loss_aversion"       : {"causal_effect":  0.041, "interpretation": "raises sell probability"},
        "unrealized_gl"       : {"causal_effect": -0.120, "interpretation": "raises sell probability"},
        "crowd_ratio"         : {"causal_effect":  0.075, "interpretation": "raises sell probability"},
        "herd_sensitivity"    : {"causal_effect":  0.030, "interpretation": "raises sell probability"},
        "disposition_strength": {"causal_effect":  0.090, "interpretation": "raises sell probability"},
    }
    return {
        "bias_type"        : bias,
        "bias_label"       : bias.replace("_", " ").title(),
        "is_biased"        : bias != "rational",
        "confidence"       : confidence,
        "all_probabilities": {bias: confidence},
        "causal_chain"     : [f"[{bias}=1.0] causal effect on decision: +0.0412"],
        "causal_effects"   : effects if with_effects else None,
        "risk_score"       : 0.61,
        "shap_explanation" : [{"feature": "unrealized_gl", "impact": 0.31}],
    }


def make_sim_result(better="HOLD", horizon=20, hold_final=580_000, sell_final=255_000):
    """A simulation result whose median paths end exactly at the given values."""
    hold_path = [hold_final * (i + 1) / horizon for i in range(horizon)]
    sell_path = [sell_final * (i + 1) / horizon for i in range(horizon)]
    return {
        "user_id"      : 42,
        "user_profile" : {"age": 38, "investment_horizon": horizon,
                          "risk_tolerance": 0.35, "monthly_income": 60_000},
        "horizon_years": horizon,
        "inputs"       : {"current_wealth": 75_000, "unrealized_gl": -0.15,
                          "n_simulations": 5_000},
        "hold": {"mean": 900_000, "median": hold_final, "p10": 320_000,
                 "p50": hold_final, "p90": 1_400_000, "std": 210_000},
        "sell": {"mean": 300_000, "median": sell_final, "p10": 180_000,
                 "p50": sell_final, "p90": 420_000, "std": 60_000},
        "comparison": {"opportunity_cost_inr": 600_000 if better == "HOLD" else -600_000,
                       "opportunity_cost_pct": 800.0,
                       "prob_hold_better": 0.83 if better == "HOLD" else 0.21,
                       "better_decision": better,
                       "wealth_gap_pct": 127.0,
                       "recommendation_text": "Recommendation: HOLD."},
        "yearly_hold_p50": hold_path,
        "yearly_sell_p50": sell_path,
        "yearly_hold_p10": [v * 0.55 for v in hold_path],
        "yearly_hold_p90": [v * 2.40 for v in hold_path],
        "yearly_sell_p50_dup": None,
        "years": list(range(1, horizon + 1)),
    }


def make_user_input(gl=-0.15, crowd=0.72, emergency=1, intent="Thinking of selling"):
    return {"unrealized_gl": gl, "crowd_ratio": crowd,
            "has_emergency_fund": emergency, "decision_intent": intent}


@pytest.fixture(autouse=True)
def _isolate_llm_env(monkeypatch):
    """
    Keep the suite hermetic.

    `llm_polish` reads a real `.env`, so once a developer adds a key with
    EXPLAINER_LLM=on, tests would start making live API calls and asserting
    against whatever a model happened to return. Every test runs with the LLM
    layer off unless it explicitly opts in.
    """
    monkeypatch.setattr(llm_polish, "_env_loaded", True, raising=False)
    for var in ("EXPLAINER_LLM", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "EXPLAINER_LLM_PROVIDER", "EXPLAINER_LLM_API_KEY",
                "EXPLAINER_LLM_MODEL", "EXPLAINER_LLM_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    llm_polish.clear_cache()
    yield
    llm_polish.clear_cache()


@pytest.fixture
def explainer():
    """Deterministic explainer — the LLM layer is explicitly off."""
    return DecisionExplainer(use_llm=False)


# ══════════════════════════════════════════════════════════════════════════
# SECTION 1 — Structure: every user gets a complete explanation
# ══════════════════════════════════════════════════════════════════════════

class TestStructure:

    @pytest.mark.parametrize("lang", LANGS)
    @pytest.mark.parametrize("bias", BIASES)
    def test_all_six_sections_present(self, explainer, bias, lang):
        exp = explainer.explain(make_bias_result(bias), make_sim_result(),
                                make_user_input(), lang)
        assert [s["key"] for s in exp["sections"]] == T.SECTIONS
        for section in exp["sections"]:
            assert section["text"].strip(), f"{bias}/{lang}: {section['key']} is empty"
            assert section["title"].strip()

    @pytest.mark.parametrize("lang", LANGS)
    def test_headline_and_recommendation_set(self, explainer, lang):
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(), lang)
        assert len(exp["headline"]) > 30
        assert len(exp["recommendation"]) > 15

    def test_unknown_bias_falls_back(self, explainer):
        """An unrecognised bias must still produce a usable explanation."""
        exp = explainer.explain(make_bias_result("something_new"), make_sim_result(),
                                make_user_input(), "en")
        assert exp["bias_type"] == "unknown"
        assert len(exp["sections"]) == len(T.SECTIONS)

    def test_unsupported_language_falls_back_to_english(self, explainer):
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(), lang="fr")
        assert exp["lang"] == "en"

    def test_missing_causal_effects_still_explains(self, explainer):
        """results/causal_effects.pkl may be absent — degrade, don't crash."""
        exp = explainer.explain(make_bias_result(with_effects=False), make_sim_result(),
                                make_user_input(), "en")
        assert "top_driver" in exp["facts"]
        assert exp["narrative"]["why_we_say_this"].strip()

    def test_complete_package_has_charts_and_technical(self):
        exp = generate_complete_explanation(make_bias_result(), make_sim_result(),
                                            make_user_input(), "en", use_llm=False)
        assert exp["charts"]["hold_p50"], "chart payload missing"
        assert exp["technical"]["causal_chain"], "technical detail missing"
        assert exp["technical"]["shap_explanation"]


# ══════════════════════════════════════════════════════════════════════════
# SECTION 2 — Plain language: no jargon may reach the user
# ══════════════════════════════════════════════════════════════════════════

class TestPlainLanguage:

    @pytest.mark.parametrize("lang", LANGS)
    @pytest.mark.parametrize("bias", BIASES)
    def test_no_jargon_in_narrative(self, explainer, bias, lang):
        exp = explainer.explain(make_bias_result(bias), make_sim_result(),
                                make_user_input(), lang)
        text = " ".join(exp["narrative"].values())
        assert find_jargon(text) == [], f"{bias}/{lang} leaked jargon"

    def test_jargon_detector_actually_detects(self):
        """Guard against a blocklist that silently matches nothing."""
        assert "p10" in find_jargon("the p10 outcome is low")
        assert "shap" in [j.lower() for j in find_jargon("SHAP values say so")]
        assert find_jargon("if things go badly you would have less") == []

    @pytest.mark.parametrize("bias", BIASES)
    def test_english_is_readable(self, explainer, bias):
        """Flesch Reading Ease >= 60 — roughly 8th-grade reading level."""
        exp = explainer.explain(make_bias_result(bias), make_sim_result(),
                                make_user_input(), "en")
        level = exp["reading_level"]
        if level["flesch_reading_ease"] is None:
            pytest.skip("textstat not installed")
        assert level["flesch_reading_ease"] >= 60, \
            f"{bias}: too hard to read ({level['flesch_reading_ease']})"

    @pytest.mark.parametrize("bias", BIASES)
    def test_hindi_sentences_stay_short(self, explainer, bias):
        """Flesch is invalid for Devanagari, so we bound sentence length instead."""
        exp = explainer.explain(make_bias_result(bias), make_sim_result(),
                                make_user_input(), "hi")
        assert exp["reading_level"]["avg_words_per_sentence"] <= 20

    def test_hindi_is_actually_hindi(self, explainer):
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(), "hi")
        text = " ".join(exp["narrative"].values())
        devanagari = len(re.findall(r"[ऀ-ॿ]", text))
        assert devanagari > 200, "Hindi output is not in Devanagari"

    def test_languages_produce_different_text(self, explainer):
        en = explainer.explain(make_bias_result(), make_sim_result(), make_user_input(), "en")
        hi = explainer.explain(make_bias_result(), make_sim_result(), make_user_input(), "hi")
        assert en["headline"] != hi["headline"]


# ══════════════════════════════════════════════════════════════════════════
# SECTION 3 — Numbers: the money in the story must be the money we computed
# ══════════════════════════════════════════════════════════════════════════

class TestNumbers:

    @pytest.mark.parametrize("lang", LANGS)
    def test_every_rupee_figure_traces_to_the_facts(self, explainer, lang):
        """
        The strongest guarantee this module makes: no figure appears in the
        narrative that wasn't computed by Objective 2.
        """
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(), lang)
        facts = exp["facts"]

        allowed = {v for v in facts.values() if isinstance(v, str)}
        allowed |= {m[key] for m in facts["milestones"] for key in ("hold", "sell")}
        allowed |= {m["gap_phrase"] for m in facts["milestones"]}
        allowed_amounts = set()
        for value in allowed:
            allowed_amounts |= set(MONEY_RE.findall(value))

        text = " ".join(exp["narrative"].values())
        for amount in MONEY_RE.findall(text):
            assert amount in allowed_amounts, f"{amount} is not traceable to the facts"

    def test_headline_figure_matches_final_year(self, explainer):
        """
        The 'by year N you'd have X' figure must equal the last row of the
        year-by-year table. Quoting the mean there (which is far higher for a
        skewed wealth distribution) would contradict the table below it.
        """
        sim = make_sim_result(hold_final=580_000, sell_final=255_000)
        exp = explainer.explain(make_bias_result(), sim, make_user_input(), "en")
        facts = exp["facts"]
        assert facts["hold_mean"] == facts["milestones"][-1]["hold"]
        assert facts["sell_mean"] == facts["milestones"][-1]["sell"]

    def test_narrative_gap_direction_matches_recommendation(self, explainer):
        """A SELL recommendation must not be paired with 'selling costs you'."""
        for better in ("HOLD", "SELL"):
            sim = make_sim_result(better=better)
            if better == "SELL":            # make the typical outcome agree
                sim["yearly_hold_p50"], sim["yearly_sell_p50"] = \
                    sim["yearly_sell_p50"], sim["yearly_hold_p50"]
            exp = explainer.explain(make_bias_result(), sim, make_user_input(), "en")
            assert exp["facts"]["better_is_hold"] == (better == "HOLD")

    def test_milestones_respect_short_horizon(self, explainer):
        """A 3-year horizon must not narrate year 5 or year 10."""
        exp = explainer.explain(make_bias_result(), make_sim_result(horizon=3),
                                make_user_input(), "en")
        years = [m["year"] for m in exp["facts"]["milestones"]]
        assert max(years) == 3
        assert years == sorted(years)

    def test_confidence_is_never_overstated(self, explainer):
        low = explainer.explain(make_bias_result(confidence=0.30), make_sim_result(),
                                make_user_input(), "en")
        assert "not at all sure" in low["narrative"]["what_to_do_now"]

    def test_empty_simulation_does_not_crash(self):
        facts = build_facts(make_bias_result(), {}, make_user_input(), "en")
        assert facts["milestones"] == []
        assert facts["gap_pct"] == "0%"


class TestMoneyStory:
    """
    Section 4 has to answer "what ARE these two numbers?" — otherwise the
    reader sees two amounts with no idea what produced them.
    """

    @pytest.fixture
    def sim(self):
        """A simulation carrying the starting positions and model assumptions."""
        result = make_sim_result()
        result["hold"].update({"starting_wealth": 63_750.0, "stock_allocation": 0.56})
        result["sell"].update({"starting_wealth": 61_097.0, "stock_allocation": 0.17})
        result["assumptions"] = {"transaction_cost": 0.05, "sell_stock_ratio": 0.30,
                                 "bond_mean": 0.055, "realization_factor": 0.95}
        return result

    def test_explains_what_each_number_is(self, explainer, sim):
        story = explainer.explain(make_bias_result(), sim, make_user_input(), "en") \
                         ["narrative"]["money_story"]
        assert "₹75,000 invested" in story          # what you put in
        assert "₹63,750" in story                   # what it's worth now
        assert "₹61,097" in story                   # what you'd actually receive
        assert "56%" in story and "44%" in story    # the invested mix
        assert "17%" in story and "83%" in story    # the mix after selling
        assert "5.5%" in story                      # what the safe mix earns

    def test_names_the_immediate_cost_of_selling(self, explainer, sim):
        story = explainer.explain(make_bias_result(), sim, make_user_input(), "en") \
                         ["narrative"]["money_story"]
        assert "₹2,653" in story, "the day-one cost of selling must be stated"
        assert "5%" in story, "the cost percentage must be stated"

    def test_explains_the_reallocation_not_just_the_exit(self, explainer, sim):
        """
        The gap is driven mostly by the proceeds being reinvested far more
        conservatively — the part users never think about.
        """
        story = explainer.explain(make_bias_result(), sim, make_user_input(), "en") \
                         ["narrative"]["money_story"]
        assert "somewhere much safer" in story
        assert "bonds" in story

    def test_explains_the_calculation(self, explainer, sim):
        story = explainer.explain(make_bias_result(), sim, make_user_input(), "en") \
                         ["narrative"]["money_story"]
        assert "How these numbers were worked out" in story
        assert "middle one" in story, "must say the table is the median path"
        assert "Half of those futures" in story, "must say what the middle means"

    @pytest.mark.parametrize("lang", LANGS)
    def test_year_table_is_a_markdown_table(self, explainer, sim, lang):
        facts = explainer.explain(make_bias_result(), sim, make_user_input(), lang)["facts"]
        rows = facts["year_table"].strip().split("\n")
        assert rows[0].startswith("|") and rows[1].startswith("|---")
        assert T.TABLE_HEADERS[lang]["today"] in rows[2], "first row must be today"
        assert rows[-1].split("|")[1].strip() == str(sim["horizon_years"]), \
            "the table must end at the horizon the rest of the story quotes"

    def test_short_horizon_prints_every_single_year(self, explainer, sim):
        """A horizon a person can hold in their head gets a row per year."""
        sim = {**sim, "horizon_years": 14}
        facts = explainer.explain(make_bias_result(), sim, make_user_input(), "en")["facts"]
        rows = facts["year_table"].strip().split("\n")
        # header + separator + today + one row per year
        assert len(rows) == 3 + 14
        assert [r.split("|")[1].strip() for r in rows[3:]] == [str(y) for y in range(1, 15)]

    def test_table_starts_from_the_two_starting_positions(self, explainer, sim):
        facts = explainer.explain(make_bias_result(), sim, make_user_input(), "en")["facts"]
        today_row = facts["year_table"].split("\n")[2]
        assert "₹63,750" in today_row and "₹61,097" in today_row

    def test_table_amounts_are_exact_not_rounded(self, explainer, sim):
        """
        Rounding would print two different years as the same "₹1.2 lakh" and
        destroy the row-to-row comparison the table exists for.
        """
        facts = explainer.explain(make_bias_result(), sim, make_user_input(), "en")["facts"]
        assert "lakh" not in facts["year_table"]
        assert "crore" not in facts["year_table"]

    def test_long_horizon_table_stays_readable(self, explainer):
        """A 30-year horizon must not print 30 rows, but must still end at 30."""
        sim = make_sim_result(horizon=30)
        facts = explainer.explain(make_bias_result(), sim, make_user_input(), "en")["facts"]
        years = [r.split("|")[1].strip() for r in facts["year_table"].split("\n")[3:]]
        assert years[-1] == "30"
        assert len(years) <= 18

    def test_no_table_without_a_simulation(self):
        assert build_facts(make_bias_result(), {}, make_user_input(), "en")["year_table"] == ""


class TestCrashAndClosing:
    """
    The synthetic market paths contain deliberate crashes, so the table can go
    backwards mid-way. Left unexplained that reads as a bug; and a closing
    line promising an ever-widening gap would contradict the table above it.
    """

    def _sim_with_crash(self):
        sim = make_sim_result(horizon=14)
        hold = [63_750 * (1.08 ** i) for i in range(1, 15)]
        hold[10:] = [v * 0.80 for v in hold[10:]]       # crash between year 10 and 11
        sell = [61_097 * (1.05 ** i) for i in range(1, 15)]
        sim["yearly_hold_p50"], sim["yearly_sell_p50"] = hold, sell
        return sim

    def test_crash_is_named_not_left_unexplained(self, explainer):
        exp = explainer.explain(make_bias_result(), self._sim_with_crash(),
                                make_user_input(), "en")
        assert exp["facts"]["dip_year"] == 11
        assert exp["facts"]["dip_year_prev"] == 10
        assert "year 10 and year 11" in exp["narrative"]["money_story"]
        assert "crash" in exp["narrative"]["money_story"]

    def test_smooth_path_gets_no_crash_note(self, explainer):
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(), "en")
        assert exp["facts"]["dip_year"] is None
        assert exp["facts"]["dip_note"] == ""

    def test_closing_admits_when_the_gap_narrows(self, explainer):
        """The compounding line must not be used when the numbers contradict it."""
        exp = explainer.explain(make_bias_result(), self._sim_with_crash(),
                                make_user_input(), "en")
        assert exp["facts"]["gap_narrows_late"] is True
        closing = exp["facts"]["story_closing"]
        assert "narrows near the end" in closing
        assert "does not win in every future" in closing

    def test_closing_uses_compounding_when_the_gap_really_grows(self, explainer):
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(), "en")
        assert exp["facts"]["gap_narrows_late"] is False
        assert "compounding" in exp["facts"]["story_closing"]

    @pytest.mark.parametrize("lang", LANGS)
    def test_crash_note_and_closing_stay_jargon_free(self, explainer, lang):
        exp = explainer.explain(make_bias_result(), self._sim_with_crash(),
                                make_user_input(), lang)
        assert find_jargon(" ".join(exp["narrative"].values())) == []


class TestFormatting:

    @pytest.mark.parametrize("value,expected", [
        (850,        "₹850"),
        (45_600,     "₹45,600"),
        (1_20_000,   "₹1.2 lakh"),
        (24_50_000,  "₹24.5 lakh"),
        (-2_40_000,  "-₹2.4 lakh"),
    ])
    def test_indian_money_format(self, value, expected):
        assert T.format_inr(value, "en") == expected

    def test_crore_and_hindi_units(self):
        assert "crore" in T.format_inr(3_12_00_000, "en")
        assert "करोड़" in T.format_inr(3_12_00_000, "hi")
        assert "लाख"  in T.format_inr(12_00_000,   "hi")

    def test_percentages_are_magnitudes(self):
        assert T.format_pct(-0.153) == "15%"
        assert T.format_pct(0.87) == "87%"

    @pytest.mark.parametrize("value,expected", [
        (63_750,    "₹63,750"),
        (1_00_213,  "₹1,00,213"),
        (1_33_896,  "₹1,33,896"),
        (3_12_00_000, "₹3,12,00,000"),
    ])
    def test_exact_format_never_rounds(self, value, expected):
        """Table cells must stay comparable row to row."""
        assert T.format_inr_exact(value) == expected


# ══════════════════════════════════════════════════════════════════════════
# SECTION 4 — Tone: praise resistance, don't warn about good decisions
# ══════════════════════════════════════════════════════════════════════════

class TestTone:

    def test_bias_resisted_is_encouraging(self, explainer):
        exp = explainer.explain(
            make_bias_result("herd"), make_sim_result(),
            make_user_input(intent="Planning to hold"), "en")
        assert exp["resisted"] is True
        assert "right track" in exp["recommendation"]

    def test_selling_intent_is_not_treated_as_resistance(self, explainer):
        exp = explainer.explain(make_bias_result("herd"), make_sim_result(),
                                make_user_input(intent="Thinking of selling"), "en")
        assert exp["resisted"] is False

    def test_rational_decision_is_not_a_warning(self, explainer):
        exp = explainer.explain(make_bias_result("rational"), make_sim_result(),
                                make_user_input(), "en")
        assert exp["is_biased"] is False
        assert "clear-headed" in exp["headline"]

    @pytest.mark.parametrize("bias,expected", [
        ("loss_aversion", "losses affect you"),
        ("herd",          "other investors are selling"),
        ("disposition",   "selling winners early"),
    ])
    def test_top_driver_matches_the_bias_being_explained(self, explainer, bias, expected):
        """
        Section 5 names the top driver and then reasons about it ("driven by
        how much a loss stings, rather than by anything that changed about the
        investment itself"). If causal magnitude alone chose the top driver,
        a loss-aversion story could open with recent market movement and
        contradict itself one sentence later.
        """
        exp = explainer.explain(make_bias_result(bias), make_sim_result(),
                                make_user_input(), "en")
        assert expected in exp["facts"]["top_driver"]
        assert expected in exp["narrative"]["why_we_say_this"]

    def test_missing_emergency_fund_is_flagged(self, explainer):
        exp = explainer.explain(make_bias_result(), make_sim_result(),
                                make_user_input(emergency=0), "en")
        assert "emergency savings" in exp["narrative"]["what_to_do_now"]


# ══════════════════════════════════════════════════════════════════════════
# SECTION 5 — Determinism and the LLM numeric guard
# ══════════════════════════════════════════════════════════════════════════

class TestDeterminismAndGuard:

    def test_template_path_is_deterministic(self, explainer):
        args = (make_bias_result(), make_sim_result(), make_user_input(), "en")
        assert explainer.explain(*args)["narrative"] == explainer.explain(*args)["narrative"]

    def test_llm_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("EXPLAINER_LLM", raising=False)
        assert llm_polish.is_enabled() is False

    def test_llm_needs_both_flag_and_key(self, monkeypatch):
        monkeypatch.setenv("EXPLAINER_LLM", "on")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        assert llm_polish.is_enabled() is False, "flag alone must not enable the LLM"

    def test_polish_returns_input_when_disabled(self, monkeypatch):
        monkeypatch.delenv("EXPLAINER_LLM", raising=False)
        llm_polish.clear_cache()
        text = "You are down 15% and would have ₹5.8 lakh."
        assert llm_polish.polish(text) == text

    def test_guard_accepts_pure_rewording(self):
        original = "You are down 15%. In 20 years you would have about ₹5.8 lakh."
        reworded = "You're down 15%, and in 20 years you'd have roughly ₹5.8 lakh."
        assert llm_polish.guard_ok(original, reworded) is True

    def test_guard_rejects_invented_number(self):
        original = "In 20 years you would have about ₹5.8 lakh."
        invented = "In 20 years you would have about ₹9.9 lakh."
        assert llm_polish.guard_ok(original, invented) is False

    def test_guard_rejects_altered_percentage(self):
        assert llm_polish.guard_ok("You are down 15%.", "You are down 45%.") is False

    def test_guard_rejects_truncation_and_padding(self):
        original = "You are down 15%. " * 10
        assert llm_polish.guard_ok(original, "You are down 15%.") is False
        assert llm_polish.guard_ok(original, original * 3) is False

    def test_guard_rejects_empty(self):
        assert llm_polish.guard_ok("anything", "") is False

    # ── polish_sections: one request for a whole explanation ─────────────
    #
    # Gemini's free tier allows 5 requests a minute and 20 a day, so an
    # explanation must cost one request, not one per section. These tests use
    # a stub provider so the parsing logic is covered without spending quota.

    @pytest.fixture
    def stub_llm(self, monkeypatch):
        """Enable the LLM layer with a scripted provider."""
        monkeypatch.setenv("EXPLAINER_LLM", "on")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("EXPLAINER_LLM_PROVIDER", "stub")
        llm_polish.clear_cache()

        calls = []

        def install(reply_fn):
            def caller(prompt, timeout):
                calls.append(prompt)
                return reply_fn(prompt)
            monkeypatch.setitem(llm_polish._PROVIDERS, "stub", caller)
            return calls

        return install

    @staticmethod
    def _sections():
        return {
            "headline"   : "You are down 15% and thinking of selling.",
            "money_story": ("You have ₹75,000 invested.\n\n"
                            "| Year | Hold | Sell |\n|---|---|---|\n| 1 | ₹80,000 | ₹70,000 |\n\n"
                            "That gap grows over time."),
            "what_to_do" : "Our suggestion: stay invested.",
        }

    def test_whole_explanation_costs_one_request(self, stub_llm):
        calls = stub_llm(lambda prompt: prompt.split("TEXT:\n", 1)[1])
        llm_polish.polish_sections(self._sections(), "en")
        assert len(calls) == 1, f"expected 1 request for the explanation, made {len(calls)}"

    def test_sections_come_back_mapped_to_the_right_keys(self, stub_llm):
        def reply(prompt):
            body = prompt.split("TEXT:\n", 1)[1]
            return body.replace("You are down", "You're down")
        stub_llm(reply)

        out = llm_polish.polish_sections(self._sections(), "en")
        assert set(out) == set(self._sections())
        assert out["headline"].startswith("You're down 15%")
        assert out["what_to_do"] == "Our suggestion: stay invested."

    def test_table_is_never_sent_to_the_model(self, stub_llm):
        calls = stub_llm(lambda prompt: prompt.split("TEXT:\n", 1)[1])
        out = llm_polish.polish_sections(self._sections(), "en")

        assert "₹80,000" not in calls[0], "table rows were sent to the model"
        assert "[[TABLE_0]]" in calls[0], "table should be replaced by a placeholder"
        # ...and it comes back intact in the output
        assert "| 1 | ₹80,000 | ₹70,000 |" in out["money_story"]
        assert "[[TABLE_0]]" not in out["money_story"]

    def test_dropped_section_marker_falls_back_entirely(self, stub_llm):
        """If we can't map text to sections safely, we must not guess."""
        stub_llm(lambda prompt: "Some completely restructured reply with no markers.")
        original = self._sections()
        assert llm_polish.polish_sections(original, "en") == original

    def test_a_bad_section_falls_back_alone(self, stub_llm):
        """One invented number must not discard the other sections."""
        def reply(prompt):
            body = prompt.split("TEXT:\n", 1)[1]
            return body.replace("down 15%", "down 45%")     # only the headline is wrong
        stub_llm(reply)

        original = self._sections()
        out = llm_polish.polish_sections(original, "en")
        assert out["headline"] == original["headline"], "bad section must fall back"
        assert out["what_to_do"] == original["what_to_do"]

    def test_mangled_table_placeholder_is_rejected(self, stub_llm):
        stub_llm(lambda prompt: prompt.split("TEXT:\n", 1)[1].replace("[[TABLE_0]]", "a table"))
        original = self._sections()
        assert llm_polish.polish_sections(original, "en") == original

    def test_polish_sections_is_a_no_op_when_disabled(self, monkeypatch):
        monkeypatch.delenv("EXPLAINER_LLM", raising=False)
        llm_polish.clear_cache()
        original = self._sections()
        assert llm_polish.polish_sections(original, "en") == original

    def test_explainer_reports_when_it_polished(self, stub_llm):
        stub_llm(lambda prompt: prompt.split("TEXT:\n", 1)[1].replace("Your", "Your own"))
        exp = DecisionExplainer(use_llm=True).explain(
            make_bias_result(), make_sim_result(), make_user_input(), "en")
        assert exp["polished"] is True
        assert find_jargon(" ".join(exp["narrative"].values())) == []

    # ── The guarantee: a failing key never reaches the user ──────────────
    #
    # Whatever goes wrong with the LLM, the reader gets the template text and
    # a complete explanation. Never an error, never a blank section, never an
    # unbounded wait.

    @pytest.mark.parametrize("failure,exc", [
        ("rejected key",      PermissionError("401 API_KEY_INVALID")),
        ("quota exhausted",   RuntimeError("429 RESOURCE_EXHAUSTED")),
        ("endpoint timeout",  TimeoutError("504 DEADLINE_EXCEEDED")),
        ("network down",      ConnectionError("getaddrinfo failed")),
        ("garbage response",  ValueError("unparseable")),
    ])
    def test_every_provider_failure_falls_back_to_templates(self, stub_llm, failure, exc):
        def raiser(prompt):
            raise exc
        stub_llm(raiser)

        original = self._sections()
        out = llm_polish.polish_sections(original, "en")
        assert out == original, f"{failure} did not fall back cleanly"

    @pytest.mark.parametrize("reply", ["", "   ", "\n\n"])
    def test_empty_reply_falls_back(self, stub_llm, reply):
        stub_llm(lambda prompt: reply)
        original = self._sections()
        assert llm_polish.polish_sections(original, "en") == original

    def test_explanation_is_complete_even_when_the_key_fails(self, stub_llm):
        """The user still gets all six sections, in full, with no error."""
        stub_llm(lambda prompt: (_ for _ in ()).throw(RuntimeError("429 RESOURCE_EXHAUSTED")))

        exp = DecisionExplainer(use_llm=True).explain(
            make_bias_result(), make_sim_result(), make_user_input(), "en")

        assert [s["key"] for s in exp["sections"]] == T.SECTIONS
        for section in exp["sections"]:
            assert section["text"].strip()
        assert exp["polished"] is False
        assert find_jargon(" ".join(exp["narrative"].values())) == []

    def test_a_hung_provider_does_not_hang_the_page(self, stub_llm, monkeypatch):
        """
        The SDK retries internally, so its own timeout is not a ceiling. A
        stalled endpoint must not leave someone staring at a spinner.
        """
        import time
        monkeypatch.setenv("EXPLAINER_LLM_TIMEOUT", "1")
        monkeypatch.setattr(llm_polish, "_DEADLINE_GRACE", 1)

        def hang(prompt):
            time.sleep(30)                          # never returns in time
            return prompt

        stub_llm(hang)
        original = self._sections()

        started = time.time()
        out = llm_polish.polish_sections(original, "en")
        elapsed = time.time() - started

        assert out == original
        assert elapsed < 10, f"waited {elapsed:.1f}s for a hung provider"

    def test_repeated_failures_stop_calling_the_provider(self, stub_llm):
        """
        An exhausted daily quota is the state of the world for hours, not a
        blip. Paying several seconds per explanation to be told 'no' again is
        waste the reader pays for.
        """
        calls = stub_llm(lambda prompt: (_ for _ in ()).throw(RuntimeError("429")))

        # Different users, so the cache never masks the repeated calls.
        for i in range(5):
            sections = {k: f"{v} (user {i})" for k, v in self._sections().items()}
            assert llm_polish.polish_sections(sections, "en") == sections

        assert len(calls) <= llm_polish._FAILURE_THRESHOLD, \
            f"kept calling a failing provider {len(calls)} times"
        assert llm_polish.circuit_status()["paused"] is True

    def test_a_failure_is_not_cached(self, stub_llm):
        """
        Quota resets and networks come back. Caching a failure would mean
        never polishing that passage again for the life of the process.
        """
        state = {"fail": True}

        def flaky(prompt):
            if state["fail"]:
                raise RuntimeError("429")
            return prompt.split("TEXT:\n", 1)[1].replace("You are down", "You're down")

        stub_llm(flaky)
        original = self._sections()

        assert llm_polish.polish_sections(original, "en") == original   # fails
        state["fail"] = False
        llm_polish._record_success()                                     # quota resets

        out = llm_polish.polish_sections(original, "en")
        assert out["headline"].startswith("You're down"), \
            "the earlier failure was cached and blocked a later success"

    def test_a_working_provider_keeps_the_circuit_closed(self, stub_llm):
        stub_llm(lambda prompt: prompt.split("TEXT:\n", 1)[1])
        original = self._sections()
        for _ in range(3):
            llm_polish.polish_sections(original, "en")
        assert llm_polish.circuit_status()["paused"] is False

    def test_a_guard_rejection_is_not_a_provider_failure(self, stub_llm):
        """Bad wording says nothing about whether the connection works."""
        stub_llm(lambda prompt: prompt.split("TEXT:\n", 1)[1].replace("15%", "45%"))
        original = self._sections()
        for _ in range(4):
            llm_polish.polish_sections(original, "en")
        assert llm_polish.circuit_status()["paused"] is False, \
            "a rejected rewrite must not trip the breaker"

    def test_unreadable_config_does_not_break_the_explainer(self, monkeypatch):
        """A broken .env must cost the wording, not the explanation."""
        monkeypatch.setattr(llm_polish, "is_enabled",
                            lambda: (_ for _ in ()).throw(OSError("cannot read .env")))
        exp = DecisionExplainer(use_llm=None).explain(
            make_bias_result(), make_sim_result(), make_user_input(), "en")
        assert len(exp["sections"]) == len(T.SECTIONS)
        assert exp["polished"] is False

    def test_broken_provider_falls_back_silently(self, monkeypatch):
        """A dead API key must never stop a user from reading their explanation."""
        monkeypatch.setenv("EXPLAINER_LLM", "on")
        monkeypatch.setenv("EXPLAINER_LLM_PROVIDER", "does_not_exist")
        monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
        llm_polish.clear_cache()
        text = "You are down 15%."
        assert llm_polish.polish(text) == text


# ══════════════════════════════════════════════════════════════════════════
# SECTION 6 — The bias-only variant (pages with no simulation behind them)
# ══════════════════════════════════════════════════════════════════════════

class TestBiasOnly:

    @pytest.mark.parametrize("lang", LANGS)
    def test_only_simulation_free_sections(self, lang):
        exp = explain_bias_only(make_bias_result(), make_user_input(), lang, use_llm=False)
        assert [s["key"] for s in exp["sections"]] == list(BIAS_ONLY_SECTIONS)
        assert exp["partial"] is True

    def test_makes_no_recommendation_without_a_simulation(self):
        """Recommending HOLD or SELL with no simulation would be unearned advice."""
        exp = explain_bias_only(make_bias_result(), make_user_input(), "en", use_llm=False)
        assert exp["recommendation"] == ""

    def test_still_free_of_jargon(self):
        exp = explain_bias_only(make_bias_result("disposition"), make_user_input(gl=0.2),
                                "en", use_llm=False)
        assert find_jargon(" ".join(exp["narrative"].values())) == []


# ══════════════════════════════════════════════════════════════════════════
# SECTION 7 — Downloadable reports
# ══════════════════════════════════════════════════════════════════════════

class TestReports:

    @pytest.fixture
    def explanation(self):
        return generate_complete_explanation(make_bias_result(), make_sim_result(),
                                             make_user_input(), "en", use_llm=False)

    def test_markdown_has_every_section(self, explanation):
        md = report_mod.to_markdown(explanation)
        for section in explanation["sections"]:
            assert section["title"] in md
            assert section["text"].split("\n")[0][:40] in md

    def test_html_is_self_contained(self, explanation):
        html_doc = report_mod.to_html(explanation)
        assert html_doc.startswith("<!doctype html>")
        assert "<style>" in html_doc
        # A strict offline promise: no external asset may be referenced.
        assert "http://" not in html_doc and "https://" not in html_doc

    def test_html_escapes_and_renders_bold(self, explanation):
        html_doc = report_mod.to_html(explanation)
        assert "<strong>" in html_doc
        assert "**" not in html_doc, "Markdown bold markers leaked into HTML"

    def test_html_renders_the_money_story_as_a_list(self, explanation):
        assert "<ul>" in report_mod.to_html(explanation)

    def test_html_renders_the_year_table_as_a_real_table(self, explanation):
        html_doc = report_mod.to_html(explanation)
        assert "<table>" in html_doc and "<th>" in html_doc
        assert "|---|" not in html_doc, "raw Markdown table leaked into HTML"
        assert "table-wrap" in html_doc, "wide table must scroll on small screens"

    def test_pdf_renders_the_year_table_as_a_real_table(self, explanation):
        pytest.importorskip("reportlab")
        pypdf = pytest.importorskip("pypdf")
        import io as _io
        pdf = pypdf.PdfReader(_io.BytesIO(report_mod.to_pdf(explanation)))
        text = " ".join(page.extract_text() for page in pdf.pages)
        assert "|---|" not in text, "raw Markdown table leaked into the PDF"
        assert "If you stay invested" in text

    def test_pdf_renders_for_english(self, explanation):
        pytest.importorskip("reportlab")
        pdf = report_mod.to_pdf(explanation)
        assert pdf.startswith(b"%PDF"), "not a PDF"
        assert len(pdf) > 2_000

    def test_hindi_pdf_is_refused_not_mangled(self):
        """
        ReportLab cannot shape Devanagari. Refusing is correct; emitting
        wrongly ordered matras would be worse than no PDF at all.
        """
        hindi = generate_complete_explanation(make_bias_result(), make_sim_result(),
                                              make_user_input(), "hi", use_llm=False)
        assert "pdf" not in report_mod.available_formats("hi")
        with pytest.raises(ValueError):
            report_mod.to_pdf(hindi)

    def test_hindi_html_keeps_devanagari(self):
        hindi = generate_complete_explanation(make_bias_result(), make_sim_result(),
                                              make_user_input(), "hi", use_llm=False)
        html_doc = report_mod.to_html(hindi)
        assert 'lang="hi"' in html_doc
        assert len(re.findall(r"[ऀ-ॿ]", html_doc)) > 200

    def test_filenames_are_descriptive(self, explanation):
        name = report_mod.filename_for(explanation, "html")
        assert name.endswith(".html") and "loss_aversion" in name

    def test_render_markdown_shared_helper(self, explanation):
        assert render_markdown(explanation).startswith("# ")


# ══════════════════════════════════════════════════════════════════════════
# SECTION 8 — Template bank integrity
# ══════════════════════════════════════════════════════════════════════════

class TestTemplateBank:

    def test_both_languages_cover_the_same_biases(self):
        assert set(T.TEMPLATES["en"]) == set(T.TEMPLATES["hi"])

    def test_both_languages_cover_the_same_sections(self):
        for bias in T.TEMPLATES["en"]:
            assert set(T.TEMPLATES["en"][bias]) == set(T.TEMPLATES["hi"][bias]), bias
        assert set(T.SHARED["en"]) == set(T.SHARED["hi"])
        assert set(T.FRAGMENTS["en"]) == set(T.FRAGMENTS["hi"])

    def test_every_section_has_a_template_somewhere(self):
        for lang in LANGS:
            for section in T.SECTIONS:
                for bias in T.TEMPLATES[lang]:
                    assert (section in T.TEMPLATES[lang][bias]
                            or section in T.SHARED[lang]), f"{lang}/{bias}/{section}"

    def test_section_titles_exist_in_both_languages(self):
        for lang in LANGS:
            assert set(T.SECTION_TITLES[lang]) == set(T.SECTIONS)

    def test_driver_and_bias_maps_are_parallel(self):
        assert set(T.DRIVER_PLAIN["en"]) == set(T.DRIVER_PLAIN["hi"])
        assert set(T.BIAS_PLAIN["en"]) == set(T.BIAS_PLAIN["hi"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
