"""Phase B3: reading the comment, and the case for each side — no datastore, no network."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.core import comment_reader as R
from backend.core import debate as DB


# ── Reading the comment (offline rules) ──────────────────────────────────

@pytest.mark.parametrize("comment, quote_part", [
    ("I need the money for my daughter's college fees in March.", "college fees"),
    ("Lost my job last month, need cash to pay the EMI.", "Lost my job"),
    ("Hospital bills came up suddenly", "Hospital bills"),
    ("Beti ki shaadi hai, paise chahiye", "paise chahiye"),
    ("मुझे फीस के लिए पैसे चाहिए", "पैसे चाहिए"),
])
def test_a_stated_cash_need_is_found_and_quoted(comment, quote_part):
    r = R.read_with_rules(comment)
    assert r["cash_need"] is True
    assert quote_part.lower() in r["cash_need_quote"].lower()
    assert r["cash_need_quote"] in comment                      # verbatim


@pytest.mark.parametrize("comment, kind, suggests", [
    ("It keeps falling and my colleagues are all selling bank stocks.", "crowd", "herd_behavior"),
    ("It keeps falling and my colleagues are all selling bank stocks.", "fear", "loss_aversion"),
    ("Booking profits while it's up, it can't keep going.", "lock_gains", "disposition_effect"),
    ("I'll wait until it recovers to what I paid.", "get_even", "disposition_effect"),
    ("Everyone at work is putting more into flexi-cap funds right now.", "crowd", "herd_behavior"),
    ("Don't want to miss out on this rocket", "fomo", "herd_behavior"),
    ("I think it will give good returns and also my frends are suggesting", "crowd", "herd_behavior"),
    ("Friends told me", "crowd", "herd_behavior"),
    ("It was recommended by my colleagues", "crowd", "herd_behavior"),
])
def test_feelings_are_found_with_the_pattern_they_resemble(comment, kind, suggests):
    cues = {c["kind"]: c for c in R.read_with_rules(comment)["cues"]}
    assert kind in cues and cues[kind]["suggests"] == suggests
    assert cues[kind]["quote"] in comment


def test_feelings_alone_are_not_a_cash_need():
    r = R.read_with_rules("I'm scared, everyone is selling")
    assert r["cash_need"] is False and r["cash_need_quote"] is None


def test_an_empty_comment_reads_as_nothing():
    assert R.read_with_rules("") == {"source": "rules", "cash_need": False, "cash_need_quote": None, "facts": [], "cues": []}


# ── Gemini's answer must quote the comment exactly ───────────────────────

COMMENT = "My sister's wedding is in December and I need the money. Everyone says the market will crash."


def test_a_verbatim_ai_reading_is_accepted():
    reply = json.dumps({"facts": [{"kind": "cash_need", "quote": "I need the money"}],
                        "cues": [{"kind": "crowd", "quote": "Everyone says the market will crash"}]})
    out = R.validate_ai_reading(COMMENT, reply)
    assert out["facts"][0]["kind"] == "cash_need" and out["cues"][0]["suggests"] == "herd_behavior"


@pytest.mark.parametrize("reply", [
    json.dumps({"facts": [{"kind": "cash_need", "quote": "needs funds for a wedding"}], "cues": []}),  # paraphrase
    json.dumps({"facts": [{"kind": "inheritance", "quote": "I need the money"}], "cues": []}),        # unknown kind
    "not json at all",
    json.dumps(["a", "list"]),
])
def test_a_paraphrased_or_malformed_ai_reading_is_thrown_away(reply):
    assert R.validate_ai_reading(COMMENT, reply) is None


def test_without_consent_the_ai_is_never_asked(monkeypatch):
    called = []
    import src.llm_polish as LP
    monkeypatch.setattr(LP, "complete", lambda *a, **k: called.append(1) or None)
    R.read_comment(COMMENT, use_ai=False)
    assert called == []


def test_with_consent_a_good_ai_reading_adds_to_the_rules(monkeypatch):
    import src.llm_polish as LP
    reply = json.dumps({"facts": [], "cues": [{"kind": "fear", "quote": "the market will crash"}]})
    monkeypatch.setattr(LP, "complete", lambda *a, **k: reply)
    r = R.read_comment(COMMENT, use_ai=True)
    assert r["source"] == "rules+gemini"
    assert {c["kind"] for c in r["cues"]} >= {"crowd", "fear"}
    assert r["cash_need"] is True                             # the rules found it; the AI didn't need to


def test_with_consent_a_bad_ai_reading_leaves_the_rules_alone(monkeypatch):
    import src.llm_polish as LP
    monkeypatch.setattr(LP, "complete", lambda *a, **k: json.dumps({"facts": [{"kind": "cash_need", "quote": "made up"}]}))
    r = R.read_comment(COMMENT, use_ai=True)
    assert r["source"] == "rules" and r["ai"] == "rejected_or_unavailable"


# ── Agreement with the reading ───────────────────────────────────────────

def test_a_stated_need_agrees_with_a_rational_reading():
    out = R.compare_with_reading(R.read_with_rules("I need the money for fees"), "rational")
    assert out["agreement"] == "agrees" and out["cash_need"]


def test_crowd_words_against_a_rational_reading_are_flagged():
    out = R.compare_with_reading(R.read_with_rules("everyone is selling"), "rational")
    assert out["agreement"] == "differs" and "following the crowd" in out["note"]


def test_matching_words_agree():
    out = R.compare_with_reading(R.read_with_rules("everyone is selling"), "herd_behavior")
    assert out["agreement"] == "agrees"


def test_agreement_also_names_the_other_patterns_the_words_suggest():
    out = R.compare_with_reading(R.read_with_rules("It keeps falling and my colleagues are all selling"), "loss_aversion")
    assert out["agreement"] == "agrees" and "following the crowd" in out["note"]


# ── The case for each side ───────────────────────────────────────────────

def decision(**kw):
    d = {
        "decision_intent": "sell", "bias_detected": "loss_aversion", "opportunity_cost_inr": Decimal("229306.19"),
        "hold_p10_20y": Decimal("163000"), "sell_p10_20y": Decimal("216000"),
        "simulation_curves": {"prob_hold_better": 0.634, "horizon_years": 22,
                              "sale": {"tax": 0.0, "tax_kind": "long_term"},
                              "holding_risk": {"asset_type": "equity", "specific_vol": 0.142}},
        "portfolio_context": {"position_share": 0.063},
        "comment_facts": None,
    }
    d.update(kw)
    return d


def test_both_cases_are_built_from_the_numbers():
    stay, leave = DB.build_cases(decision())
    assert stay["title"] == "The case for holding" and leave["title"] == "The case for selling"
    assert any("63% of 22-year futures" in p for p in stay["points"])
    assert any("loss aversion" in p for p in stay["points"])
    assert any("37% of 22-year futures" in p for p in leave["points"])
    assert any("14% a year of their own" in p for p in leave["points"])


def test_a_stated_need_argues_for_selling():
    facts = {"cash_need": True, "cash_need_quote": "I need the money for fees"}
    _, leave = DB.build_cases(decision(comment_facts=facts))
    assert any("I need the money for fees" in p for p in leave["points"])


def test_buying_more_is_argued_as_adding_or_holding_off():
    stay, leave = DB.build_cases(decision(decision_intent="buy_more", bias_detected="herd_behavior"))
    assert (stay["title"], leave["title"]) == ("The case for adding", "The case for holding off")
    assert any("Staying invested came out ahead" in p for p in stay["points"])
    assert any("Exiting came out ahead" in p for p in leave["points"])


def test_ai_wording_is_kept_only_without_new_numbers(monkeypatch):
    import src.llm_polish as LP
    cases = DB.build_cases(decision())
    good = " ".join(cases[0]["points"]).replace("Holding came out", "Staying put came out")
    bad = "Selling wins in 90% of futures and saves ₹5 L."
    monkeypatch.setattr(LP, "complete", lambda *a, **k: json.dumps({"stay": good, "leave": bad}))
    out = DB.debate(decision(), use_ai=True)
    stay, leave = out["cases"]
    assert out["llm_debate"] is True
    assert stay["worded_by"] == "gemini" and stay["text"] == good
    assert leave["worded_by"] == "numbers" and "90%" not in leave["text"]


def test_without_ai_the_number_built_text_is_used():
    out = DB.debate(decision(), use_ai=False)
    assert out["llm_debate"] is False
    assert all(c["worded_by"] == "numbers" and c["text"] for c in out["cases"])
