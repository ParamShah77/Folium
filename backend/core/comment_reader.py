"""Phase B3 — understanding "Why? In your own words".

Before B3 nothing read the investor's comment. Now it is read twice over:

* **Phrase rules, always, offline.** English, Hinglish and a little Hindi.
  Nothing leaves the server.
* **Gemini, only with the investor's consent** (``users.ai_consent``) and a
  configured key. Its answer is accepted only if every quote it returns appears
  word for word in the comment; otherwise it is discarded and the rules stand.

What it finds is used in two different ways (the agreed design, option B):

* **Facts can shift the pattern reading.** A stated need for the money
  ("fees are due in March", "lost my job") becomes the bias model's
  ``cash_need_stated`` input (src/bias_model_v4.py), so a forced sale can read
  as rational. The quoted phrase is shown as the reason.
* **Feelings are shown, never used.** Fear, following the crowd, waiting to get
  back to even, locking in a gain, fear of missing out: quoted back in "In your
  own words", with whether they agree with the reading. They never change the
  reading or the recommendation, and nothing here touches the Hold/Sell verdict.

Output, stored on the decision as ``comment_facts``::

    {"source": "rules" | "rules+gemini", "cash_need": bool, "cash_need_quote": str | None,
     "facts": [{"kind", "quote"}], "cues": [{"kind", "suggests", "quote"}]}
"""
from __future__ import annotations

import json
import re
from typing import Any

#: Facts — statements about the investor's situation.
_FACT_RULES: dict[str, tuple[str, ...]] = {
    "cash_need": (
        r"\bneed (the |some |that |this )?(money|cash|funds?)\b",
        r"\b(school|college|tuition|education|exam) fees?\b",
        r"\bfees? (is |are )?(due|coming up)\b",
        r"\b(pay|paying) (my |the |off )?(emi|loan|rent)\b",
        r"\bemis? (is |are )?(due|pending|bouncing)\b",
        r"\b(medical|hospital|surgery|treatment|operation)\b",
        r"\b(lost my job|job loss|laid off|layoffs?|unemployed|no salary)\b",
        r"\b(wedding|marriage|shaadi)\b",
        r"\bdown ?payment\b",
        r"\b(paisa|paise|paison) (chahiye|ki zarurat|ki zaroorat|chahiye the)\b",
        r"\bfees? (bharni|bharna|deni)\b",
        r"पैसे चाहिए|पैसों की ज़रूरत|पैसों की जरूरत|फ़ीस|फीस|इलाज|अस्पताल|नौकरी चली गई",
    ),
    "rebalance": (
        r"\brebalanc\w*",
        r"\btoo much (money )?in (one|this|a single) (stock|share|company|fund)\b",
        r"\bdiversif\w*",
    ),
    "goal_near": (
        r"\b(next|this) (year|month)\b[^.!?]*\b(buy|house|home|flat|car|retire)\w*",
        r"\bretir(e|ing|ement) (soon|next year|this year)\b",
    ),
}

#: Feelings — shown, never used. Each suggests the pattern it resembles.
_CUE_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "fear": ("loss_aversion", (
        r"\b(scared|afraid|frightened|panic\w*|nervous|worried|anxious)\b",
        r"\bcan'?t (watch|bear|take|stand|handle)\b",
        r"\bkeeps? (falling|dropping|going down|crashing)\b",
        r"\bbefore it (gets worse|falls more|drops more)\b",
        r"\b(dar lag|ghabra\w*|tension ho)",
        r"डर|घबरा",
    )),
    "crowd": ("herd_behavior", (
        r"\b(everyone|everybody)\b",
        r"\ball (my )?(friends|colleagues|relatives)\b",
        r"\b(colleagues|friends|relatives|people at work) (are|is) (all )?(selling|buying|getting out|putting)",
        r"\b(whatsapp|telegram) group\b",
        r"\b(fr(ie|e)nds?|colleagues?|relatives?|cousins?|uncle|neighbou?rs?|someone|people)\b[^.!?]*\b(suggest|told|tell|say|said|recommend|advis|tip)\w*",
        r"\b(suggested|told|recommended|advised) (to me )?by (my )?(fr(ie|e)nds?|colleagues?|relatives?)\b",
        r"\btips?\b[^.!?]*\b(from|on|in)\b",
        r"\b(sab log|sab bech|sabhi log|sab khareed)\w*",
        r"सब लोग|सभी लोग",
    )),
    "get_even": ("disposition_effect", (
        r"\bbreak ?even\b",
        r"\bget (back )?to (what|the price) i (paid|bought)\b",
        r"\b(wait|hold) (till|until) it (recovers|comes back|goes back up)\b",
        r"\bwapas (aane|aa jaye)\b",
    )),
    "lock_gains": ("disposition_effect", (
        r"\bbook\w* (my )?profits?\b",
        r"\block in (the |my )?(gains?|profits?)\b",
        r"\bwhile (it'?s|it is) (still )?up\b",
        r"\bcan'?t keep going( up)?\b",
        r"\bmunafa\w*",
    )),
    "fomo": ("herd_behavior", (
        r"\b(missing out|fomo)\b",
        r"\b(to the moon|rocket\w*|multibagger)\b",
        r"\beveryone is making money\b",
    )),
}

FACT_KINDS = tuple(_FACT_RULES)
CUE_KINDS = tuple(_CUE_RULES)
CUE_SUGGESTS = {k: v[0] for k, v in _CUE_RULES.items()}

_SENTENCE = re.compile(r"[^.!?\n।]+[.!?।]?")


def _sentence_around(text: str, start: int, end: int, limit: int = 140) -> str:
    """The sentence holding a match: a verbatim quote that reads on its own."""
    for m in _SENTENCE.finditer(text):
        if m.start() <= start and end <= m.end():
            quote = m.group(0).strip()
            return quote if len(quote) <= limit else text[start:end].strip()
    return text[start:end].strip()


def read_with_rules(comment: str | None) -> dict[str, Any]:
    text = (comment or "").strip()
    facts: list[dict[str, str]] = []
    cues: list[dict[str, str]] = []
    if text:
        for kind, patterns in _FACT_RULES.items():
            for p in patterns:
                m = re.search(p, text, flags=re.IGNORECASE)
                if m:
                    facts.append({"kind": kind, "quote": _sentence_around(text, m.start(), m.end())})
                    break
        for kind, (suggests, patterns) in _CUE_RULES.items():
            for p in patterns:
                m = re.search(p, text, flags=re.IGNORECASE)
                if m:
                    cues.append({"kind": kind, "suggests": suggests,
                                 "quote": _sentence_around(text, m.start(), m.end())})
                    break
    need = next((f for f in facts if f["kind"] == "cash_need"), None)
    return {"source": "rules", "cash_need": need is not None,
            "cash_need_quote": need["quote"] if need else None, "facts": facts, "cues": cues}


# --------------------------------------------------------------------------- #
# Gemini (consent + key only)
# --------------------------------------------------------------------------- #

_PROMPT = """You read one short note an investor wrote about a decision. Return JSON only, no prose:
{{"facts": [{{"kind": "<one of {facts}>", "quote": "<exact words from the note>"}}],
  "cues": [{{"kind": "<one of {cues}>", "quote": "<exact words from the note>"}}]}}

Facts are statements about their situation: cash_need = they need the money (fees, EMIs, medical,
job loss, a planned expense); rebalance = too much in one holding; goal_near = a goal is close.
Cues are feelings: fear (of losses), crowd (following others), get_even (waiting to get back what
they paid), lock_gains (taking profit before it disappears), fomo (fear of missing a rally).
Every quote must be copied exactly from the note. Include only what the note clearly says.
The note may be in English, Hindi or Hinglish.

Note: {comment}"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def validate_ai_reading(comment: str, reply: str | None) -> dict[str, list[dict[str, str]]] | None:
    """Accept the model's answer only if every item is well-formed and quoted verbatim."""
    if not reply:
        return None
    try:
        data = json.loads(reply)
    except ValueError:
        m = re.search(r"\{.*\}", reply, flags=re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    source = _norm(comment)
    out: dict[str, list[dict[str, str]]] = {"facts": [], "cues": []}
    for group, allowed in (("facts", FACT_KINDS), ("cues", CUE_KINDS)):
        items = data.get(group) or []
        if not isinstance(items, list):
            return None
        for item in items:
            if not isinstance(item, dict):
                return None
            kind, quote = item.get("kind"), item.get("quote")
            if kind not in allowed or not isinstance(quote, str) or not quote.strip():
                return None
            if _norm(quote) not in source:          # an invented or paraphrased quote voids the answer
                return None
            entry = {"kind": kind, "quote": quote.strip()}
            if group == "cues":
                entry["suggests"] = CUE_SUGGESTS[kind]
            out[group].append(entry)
    return out


def read_comment(comment: str | None, use_ai: bool = False) -> dict[str, Any]:
    """Rules always; Gemini added on top when allowed and its answer checks out."""
    result = read_with_rules(comment)
    if not use_ai or not (comment or "").strip():
        return result
    from .ml_bridge import ensure_src_importable

    ensure_src_importable()
    try:
        from src import llm_polish
    except ImportError:
        return result
    ai = validate_ai_reading(comment, llm_polish.complete(
        _PROMPT.format(comment=comment.strip(), facts=", ".join(FACT_KINDS), cues=", ".join(CUE_KINDS)), timeout=20))
    if ai is None:
        result["ai"] = "rejected_or_unavailable"
        return result
    seen = {(x["kind"], _norm(x["quote"])) for x in result["facts"] + result["cues"]}
    have = {x["kind"] for x in result["facts"]} | {x["kind"] for x in result["cues"]}
    for group in ("facts", "cues"):
        for item in ai[group]:
            if (item["kind"], _norm(item["quote"])) not in seen and item["kind"] not in have:
                result[group].append(item)
    need = next((f for f in result["facts"] if f["kind"] == "cash_need"), None)
    result.update({"source": "rules+gemini", "cash_need": need is not None,
                   "cash_need_quote": need["quote"] if need else None})
    return result


# --------------------------------------------------------------------------- #
# Agreement with the reading
# --------------------------------------------------------------------------- #

_PATTERN_WORDS = {"loss_aversion": "loss aversion", "herd_behavior": "following the crowd",
                  "disposition_effect": "the disposition effect", "rational": "a clear-headed decision"}
_CUE_WORDS = {"fear": "fear of losses", "crowd": "following others", "get_even": "waiting to get back what you paid",
              "lock_gains": "taking profit before it disappears", "fomo": "fear of missing out"}


def compare_with_reading(facts: dict[str, Any] | None, bias: str | None) -> dict[str, Any] | None:
    """How the investor's own words line up with the pattern the numbers read."""
    if not facts or not (facts.get("facts") or facts.get("cues")):
        return None
    cues = facts.get("cues") or []
    suggested = {c["suggests"] for c in cues}
    if facts.get("cash_need") and bias == "rational":
        agreement, note = "agrees", "You said you need the money, and the reading treats the sale as driven by that need."
    elif bias and bias != "rational" and bias in suggested:
        others = sorted(_PATTERN_WORDS[s] for s in suggested if s != bias)
        agreement = "agrees"
        note = f"Your words point to {_PATTERN_WORDS[bias]} too" + (f", and also to {' and '.join(others)}." if others else ".")
    elif bias == "rational" and suggested:
        agreement = "differs"
        note = (f"Your words suggest {', '.join(sorted(_PATTERN_WORDS[s] for s in suggested))}, "
                "while the numbers read a clear-headed decision. Worth a second look at why you're deciding.")
    elif bias and bias != "rational" and suggested and bias not in suggested:
        agreement = "differs"
        note = (f"Your words suggest {', '.join(sorted(_PATTERN_WORDS[s] for s in suggested))}, "
                f"while the numbers read {_PATTERN_WORDS[bias]}. Both can be true at once.")
    else:
        agreement, note = "none", None
    return {
        "agreement": agreement, "note": note,
        "cues": [{**c, "label": _CUE_WORDS.get(c["kind"], c["kind"])} for c in cues],
        "facts": facts.get("facts") or [],
        "cash_need": bool(facts.get("cash_need")),
        "cash_need_quote": facts.get("cash_need_quote"),
        "source": facts.get("source"),
    }
