"""
═══════════════════════════════════════════════════════════════════════════
 explanation_templates.py — GAP 3 template bank (English + Hindi)
═══════════════════════════════════════════════════════════════════════════

The plain-language vocabulary of the system.  Every sentence a user reads is
rendered from a template in this file, filled with real numbers produced by
Objective 1 (bias detection) and Objective 2 (long-horizon simulation).

Design rules — these are what make the output understandable:

  1. No jargon, ever.  "p10" becomes "if things go badly".  "opportunity
     cost" becomes "money you'd miss out on".  See JARGON_MAP below.
  2. No unexplained numbers.  Every figure is attached to a plain phrase
     that says what it means for the reader.
  3. Indian money formatting.  ₹1.2 lakh, not ₹1,20,000.
  4. English and Hindi are peers.  Both are hand-written and both work
     completely offline, with no LLM involved.
  5. Short sentences.  Target reading level ~8th grade (Flesch >= 60).

Templates are Jinja2 strings rendered against the `facts` dict built by
`explainer.build_facts()`.

Public API
----------
    TEMPLATES            — {lang: {bias_type: {section: template_str}}}
    SHARED               — {lang: {section: template_str}}
    SECTIONS             — canonical ordered list of the six sections
    SECTION_TITLES       — {lang: {section: heading}}
    JARGON_MAP           — internal term -> plain phrase (both languages)
    JARGON_BLOCKLIST     — terms that must never reach the user
    DRIVER_PLAIN         — causal driver name -> plain phrase
    format_inr()         — Indian money formatting (lakh / crore)
    format_pct()         — percentage with sensible precision
    confidence_word()    — 0.87 -> "fairly sure" / "काफ़ी हद तक"
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════
# SECTION DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

#: The six sections of every explanation, in reading order.
SECTIONS: list[str] = [
    "headline",          # 1. What you're about to do, and whether it's wise
    "whats_happening",   # 2. What's going on in your head, in human words
    "two_futures",       # 3. HOLD vs SELL in rupees
    "money_story",       # 4. Year-by-year story of your money
    "why_we_say_this",   # 5. What drove this conclusion
    "what_to_do_now",    # 6. One clear action + an honest caveat
]

SECTION_TITLES: dict[str, dict[str, str]] = {
    "en": {
        "headline"        : "In short",
        "whats_happening" : "What's going on right now",
        "two_futures"     : "Your two possible futures",
        "money_story"     : "The story of your money",
        "why_we_say_this" : "Why we're telling you this",
        "what_to_do_now"  : "What to do now",
    },
    "hi": {
        "headline"        : "संक्षेप में",
        "whats_happening" : "अभी क्या हो रहा है",
        "two_futures"     : "आपके दो संभावित भविष्य",
        "money_story"     : "आपके पैसे की कहानी",
        "why_we_say_this" : "हम यह क्यों कह रहे हैं",
        "what_to_do_now"  : "अब क्या करें",
    },
}

SUPPORTED_LANGS: tuple[str, ...] = ("en", "hi")

#: Column headings for the year-by-year table in section 4.
TABLE_HEADERS: dict[str, dict[str, str]] = {
    "en": {"year": "Year", "hold": "If you stay invested", "sell": "If you sell now",
           "gap": "Difference", "today": "Today"},
    "hi": {"year": "साल", "hold": "निवेश बनाए रखने पर", "sell": "अभी बेच देने पर",
           "gap": "अंतर", "today": "आज"},
}

LANG_NAMES: dict[str, str] = {"en": "English", "hi": "हिंदी"}


# ═══════════════════════════════════════════════════════════════════════════
# JARGON TRANSLATION LAYER
# ═══════════════════════════════════════════════════════════════════════════
#
# This is the heart of Objective 3.  The models speak in these terms; users
# do not.  Nothing on the left may ever appear in user-facing output.

JARGON_MAP: dict[str, dict[str, str]] = {
    "en": {
        "unrealized_gl"        : "how much your investment is up or down right now",
        "p10"                  : "if things go badly",
        "p90"                  : "if things go well",
        "p50"                  : "the middle, most likely case",
        "median"               : "the middle, most likely case",
        "opportunity_cost"     : "money you'd miss out on by selling",
        "prob_hold_better"     : "how often staying invested wins",
        "disposition effect"   : "selling winners too early and holding losers too long",
        "loss aversion"        : "losses hurting about twice as much as gains feel good",
        "herd behaviour"       : "following what everyone else is doing",
        "monte carlo"          : "thousands of simulated futures",
        "causal effect"        : "how much this one thing pushed your decision",
        "confidence"           : "how sure we are",
        "risk_score"           : "how risky this moment looks for you",
        "volatility"           : "how much prices are swinging",
        "investment_horizon"   : "how many years before you need this money",
        "crowd_ratio"          : "how many other investors are selling",
        "stock_allocation"     : "how much of your money sits in shares",
    },
    "hi": {
        "unrealized_gl"        : "आपका निवेश अभी कितना ऊपर या नीचे है",
        "p10"                  : "अगर हालात बुरे रहे",
        "p90"                  : "अगर हालात अच्छे रहे",
        "p50"                  : "बीच का, सबसे संभावित हाल",
        "median"               : "बीच का, सबसे संभावित हाल",
        "opportunity_cost"     : "बेचने पर जो पैसा आपके हाथ से निकल जाएगा",
        "prob_hold_better"     : "निवेश बनाए रखना कितनी बार बेहतर रहता है",
        "disposition effect"   : "फ़ायदे वाले निवेश जल्दी बेच देना और घाटे वाले पकड़े रहना",
        "loss aversion"        : "नुकसान का दर्द बराबर के फ़ायदे की ख़ुशी से लगभग दोगुना लगना",
        "herd behaviour"       : "जो सब कर रहे हैं वही करना",
        "monte carlo"          : "हज़ारों संभावित भविष्य",
        "causal effect"        : "इस एक बात ने आपके फ़ैसले को कितना धकेला",
        "confidence"           : "हमें कितना यक़ीन है",
        "risk_score"           : "यह पल आपके लिए कितना जोखिम भरा है",
        "volatility"           : "क़ीमतें कितना ऊपर-नीचे हो रही हैं",
        "investment_horizon"   : "इस पैसे की ज़रूरत पड़ने में कितने साल बाक़ी हैं",
        "crowd_ratio"          : "और कितने निवेशक बेच रहे हैं",
        "stock_allocation"     : "आपका कितना पैसा शेयरों में लगा है",
    },
}

#: Terms that must never appear in a rendered explanation.  Enforced by
#: tests/test_explainer.py and scripts/evaluate_explanations.py.
JARGON_BLOCKLIST: tuple[str, ...] = (
    "p10", "p25", "p50", "p75", "p90",
    "shap", "xgboost", "monte carlo", "percentile", "quantile",
    "causal effect", "unrealized_gl", "unrealised_gl", "crowd_ratio",
    "risk_score", "prob_hold_better", "opportunity_cost", "stock_allocation",
    "disposition_strength", "herd_sensitivity", "loss_aversion",
    "std", "stdev", "variance", "confidence interval", "n_simulations",
    "dowhy", "notears", "dag", "feature importance",
)

#: Causal driver variable names -> plain phrases.  Used by section 5.
DRIVER_PLAIN: dict[str, dict[str, str]] = {
    "en": {
        "loss_aversion"        : "how strongly losses affect you",
        "unrealized_gl"        : "how far your investment is down right now",
        "unrealized_gl_up"     : "how far your investment is up right now",
        "crowd_ratio"          : "how many other investors are selling",
        "herd_sensitivity"     : "how much other people's actions sway you",
        "disposition_strength" : "your habit of selling winners early and holding losers",
        "market_return"        : "how the market has moved recently",
        "market_volatility"    : "how sharply prices are swinging",
        "risk_tolerance"       : "how much risk you're comfortable with",
        "investment_horizon"   : "how many years you have before you need this money",
        "age"                  : "your age",
        "position_size_pct"    : "how big this investment is compared to everything you own",
        "holding_period_months": "how long you've held this investment",
        "has_emergency_fund"   : "whether you have emergency savings to fall back on",
    },
    "hi": {
        "loss_aversion"        : "नुकसान आप पर कितना असर करता है",
        "unrealized_gl"        : "आपका निवेश अभी कितना नीचे है",
        "unrealized_gl_up"     : "आपका निवेश अभी कितना ऊपर है",
        "crowd_ratio"          : "और कितने निवेशक बेच रहे हैं",
        "herd_sensitivity"     : "दूसरों के फ़ैसले आपको कितना प्रभावित करते हैं",
        "disposition_strength" : "फ़ायदे वाले निवेश जल्दी बेचने और घाटे वाले पकड़े रहने की आपकी आदत",
        "market_return"        : "बाज़ार हाल में कैसा चला है",
        "market_volatility"    : "क़ीमतें कितनी तेज़ी से ऊपर-नीचे हो रही हैं",
        "risk_tolerance"       : "आप कितना जोखिम सह सकते हैं",
        "investment_horizon"   : "इस पैसे की ज़रूरत पड़ने में कितने साल बाक़ी हैं",
        "age"                  : "आपकी उम्र",
        "position_size_pct"    : "आपकी कुल पूँजी के मुक़ाबले यह निवेश कितना बड़ा है",
        "holding_period_months": "आपने यह निवेश कितने समय से रखा है",
        "has_emergency_fund"   : "आपके पास आपातकालीन बचत है या नहीं",
    },
}

#: Bias type -> plain, non-clinical label.
BIAS_PLAIN: dict[str, dict[str, str]] = {
    "en": {
        "loss_aversion" : "fear of locking in a loss",
        "herd"          : "following the crowd",
        "disposition"   : "selling winners early, holding losers too long",
        "rational"      : "a clear-headed decision",
        "unknown"       : "an unclear pattern",
    },
    "hi": {
        "loss_aversion" : "नुकसान पक्का कर लेने का डर",
        "herd"          : "भीड़ के पीछे चलना",
        "disposition"   : "फ़ायदे वाले जल्दी बेचना, घाटे वाले पकड़े रहना",
        "rational"      : "एक समझदारी भरा फ़ैसला",
        "unknown"       : "एक अस्पष्ट पैटर्न",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# NUMBER FORMATTING — Indian conventions
# ═══════════════════════════════════════════════════════════════════════════

RUPEE  = "₹"

_LAKH  = 100_000
_CRORE = 10_000_000

_UNIT_WORDS = {
    "en": {"lakh": "lakh", "crore": "crore"},
    "hi": {"lakh": "लाख",  "crore": "करोड़"},
}


def _indian_group(n: float) -> str:
    """
    Group an integer with Indian digit separators: 1234567 -> '12,34,567'.
    """
    neg = n < 0
    s   = f"{abs(int(round(n))):d}"
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if neg else "") + s


def format_inr(value: float, lang: str = "en") -> str:
    """
    Format a rupee amount the way an Indian reader actually reads it.

        850        -> ₹850
        45600      -> ₹45,600
        120000     -> ₹1.2 lakh      / ₹1.2 लाख
        2450000    -> ₹24.5 lakh     / ₹24.5 लाख
        31200000   -> ₹3.1 crore     / ₹3.1 करोड़

    Large numbers are deliberately rounded — "₹1.2 crore" is understood
    instantly; "₹1,23,45,678" is not.
    """
    lang  = lang if lang in SUPPORTED_LANGS else "en"
    words = _UNIT_WORDS[lang]
    sign  = "-" if value < 0 else ""
    v     = abs(float(value))

    if v >= _CRORE:
        num = v / _CRORE
        txt = f"{num:.2f}".rstrip("0").rstrip(".") if num < 10 else f"{num:.1f}".rstrip("0").rstrip(".")
        return f"{sign}{RUPEE}{txt} {words['crore']}"

    if v >= _LAKH:
        num = v / _LAKH
        txt = f"{num:.1f}".rstrip("0").rstrip(".")
        return f"{sign}{RUPEE}{txt} {words['lakh']}"

    return f"{sign}{RUPEE}{_indian_group(v)}"


def format_inr_exact(value: float, lang: str = "en") -> str:
    """
    An exact rupee amount with Indian digit grouping: ₹1,32,451.

    Used in the year-by-year table, where `format_inr()`'s rounding would
    print two different years as the same "₹1.2 lakh" and destroy the very
    comparison the table exists to make. Prose keeps the rounded form, which
    reads better in a sentence.
    """
    sign = "-" if value < 0 else ""
    return f"{sign}{RUPEE}{_indian_group(abs(float(value)))}"


def format_pct(value: float, decimals: int = 0) -> str:
    """
    Format a fraction (0.153) or a percentage-like number as a clean percent
    string.  Always returns a magnitude — direction is expressed in words.
    """
    pct = abs(float(value)) * 100 if abs(float(value)) <= 1.5 else abs(float(value))
    if decimals == 0:
        return f"{pct:.0f}%"
    return f"{pct:.{decimals}f}%"


def confidence_word(confidence: float, lang: str = "en") -> str:
    """
    Turn a model confidence into an honest English/Hindi phrase.  We never
    say "certain" — the model is not, and pretending otherwise is a lie the
    user would pay for.
    """
    c = float(confidence)
    if lang == "hi":
        if c >= 0.85: return "काफ़ी हद तक यक़ीन है"
        if c >= 0.65: return "ठीक-ठाक यक़ीन है"
        if c >= 0.45: return "कुछ हद तक लगता है"
        return "पक्का नहीं कह सकते"
    if c >= 0.85: return "fairly sure"
    if c >= 0.65: return "reasonably sure"
    if c >= 0.45: return "somewhat sure"
    return "not at all sure"


# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATES — bias-specific sections (1, 2, 5)
# ═══════════════════════════════════════════════════════════════════════════
#
# Rendered with Jinja2 against the `facts` dict.  Keep sentences short.

TEMPLATES: dict[str, dict[str, dict[str, str]]] = {

    # ───────────────────────────────────────────────────────────────────
    # ENGLISH
    # ───────────────────────────────────────────────────────────────────
    "en": {

        "loss_aversion": {
            "headline": (
                "{% if resisted %}"
                "Your investment is down {{ gl_pct }}, and almost everything about this moment "
                "is pushing you to sell — but you've decided to stay put. That takes nerve, and "
                "the numbers say you've got it right."
                "{% else %}"
                "You're thinking about selling while your investment is down {{ gl_pct }}. "
                "Before you do, here's what that one decision is likely to cost you over the "
                "next {{ horizon_years }} years."
                "{% endif %}"
            ),
            "whats_happening": (
                "Your investment is down {{ gl_pct }} right now, and that genuinely hurts. "
                "Here's the thing though: research on thousands of investors shows a loss feels "
                "about twice as painful as the same-sized gain feels good. So the urge you're "
                "feeling is stronger than the actual damage warrants.\n\n"
                "That urge has a job — it wants you to stop the pain. But selling doesn't stop "
                "the loss. It makes it permanent. Right now the loss is only on paper, and paper "
                "losses have a habit of recovering when you give them time."
            ),
            "why_we_say_this": (
                "We looked at what actually drove this decision, and the biggest factor was "
                "{{ top_driver }}. {% if other_drivers %}{{ other_drivers_sentence }}{% endif %}\n\n"
                "That's the tell. A decision driven by how much a loss stings, rather than by "
                "anything that changed about the investment itself, is usually your emotions "
                "talking — not your judgement."
            ),
        },

        "herd": {
            "headline": (
                "{% if resisted %}"
                "Roughly {{ crowd_pct }} of investors are selling right now, and you've decided "
                "not to join them. Sitting still while everyone runs is genuinely hard — and it's "
                "the right call here."
                "{% else %}"
                "Roughly {{ crowd_pct }} of investors are selling right now, and you're about to "
                "do the same. Here's what following them is likely to cost you."
                "{% endif %}"
            ),
            "whats_happening": (
                "About {{ crowd_pct }} of investors are selling right now. When that many people "
                "move at once, staying put feels reckless — as if they must know something you "
                "don't.\n\n"
                "Usually they don't. Most of them are watching each other too, and fear spreads "
                "faster than facts. The uncomfortable truth about markets is that the moment when "
                "selling feels most obvious is often the worst moment to do it."
            ),
            "why_we_say_this": (
                "The strongest influence on this decision was {{ top_driver }}. "
                "{% if other_drivers %}{{ other_drivers_sentence }}{% endif %}\n\n"
                "Notice what isn't on that list: anything that actually changed about your "
                "investment or your own plan. The crowd's mood moved, and it pulled you with it."
            ),
        },

        "disposition": {
            "headline": (
                "{% if resisted %}"
                "You're up {{ gl_pct }} and choosing to let it run rather than cash out early. "
                "That's the harder choice, and the numbers back it."
                "{% elif gl_is_gain %}"
                "You're up {{ gl_pct }} and thinking about taking the money off the table. "
                "Locking in a win feels great — here's what it tends to cost."
                "{% else %}"
                "You're down {{ gl_pct }} and holding on. That's worth a closer look — here's "
                "what the numbers say about this position."
                "{% endif %}"
            ),
            "whats_happening": (
                "{% if gl_is_gain %}"
                "You're up {{ gl_pct }}, and there's a strong pull to bank it before it "
                "disappears. That pull is one of the most common patterns in investing: people "
                "sell their winners early and hold their losers far too long.\n\n"
                "It feels responsible — you're 'taking profit'. But a rising investment is "
                "usually rising for a reason, and cutting it short means you keep the small wins "
                "and carry all the losses. Over {{ horizon_years }} years that adds up."
                "{% else %}"
                "You're down {{ gl_pct }} and staying in. Sometimes that's exactly right. But the "
                "same pattern that makes people sell winners early also makes them cling to "
                "losers, hoping to get back to even.\n\n"
                "The question worth asking isn't 'will it come back?' — it's 'if I had this money "
                "in cash today, would I buy this again?' That question has no ego in it."
                "{% endif %}"
            ),
            "why_we_say_this": (
                "The main driver here was {{ top_driver }}. "
                "{% if other_drivers %}{{ other_drivers_sentence }}{% endif %}\n\n"
                "This pattern is easy to miss because each individual decision looks sensible. "
                "It only shows up when you look at many decisions together — which is exactly "
                "what we did."
            ),
        },

        "rational": {
            "headline": (
                "This looks like a clear-headed decision. We found no sign that fear, the crowd, "
                "or habit is steering you — so here's the straightforward money picture."
            ),
            "whats_happening": (
                "We checked this decision against the three patterns that most often cost "
                "investors money: panicking over losses, following the crowd, and cashing out "
                "winners too early. None of them stand out here.\n\n"
                "That doesn't automatically make it the best financial move — it just means the "
                "decision is yours, not your nerves'. So the only question left is what the "
                "numbers say."
            ),
            "why_we_say_this": (
                "The things shaping this decision were {{ top_driver }}"
                "{% if other_drivers %}, along with {{ other_drivers_plain }}{% endif %} — "
                "all ordinary parts of your situation rather than emotional pressure.\n\n"
                "So treat what follows as information, not a warning."
            ),
        },

        "unknown": {
            "headline": (
                "We couldn't confidently place this decision in a familiar pattern, so treat the "
                "numbers below as the main guide."
            ),
            "whats_happening": (
                "Your situation doesn't match the usual patterns cleanly enough for us to say "
                "anything confident about what's driving it. That happens, and it's better to "
                "say so than to guess.\n\n"
                "What we can still do reliably is show you where each choice is likely to leave "
                "you financially."
            ),
            "why_we_say_this": (
                "The factors we could measure were {{ top_driver }}"
                "{% if other_drivers %} and {{ other_drivers_plain }}{% endif %}, but none was "
                "strong enough to explain the decision on its own.\n\n"
                "When the pattern is unclear, the long-term numbers are the safer thing to lean on."
            ),
        },
    },

    # ───────────────────────────────────────────────────────────────────
    # HINDI
    # ───────────────────────────────────────────────────────────────────
    "hi": {

        "loss_aversion": {
            "headline": (
                "{% if resisted %}"
                "आपका निवेश {{ gl_pct }} नीचे है और इस समय सब कुछ आपको बेचने की ओर धकेल रहा है — "
                "फिर भी आपने रुके रहने का फ़ैसला किया। यह हिम्मत की बात है, और आँकड़े कहते हैं कि "
                "आपका फ़ैसला सही है।"
                "{% else %}"
                "आपका निवेश {{ gl_pct }} नीचे है और आप बेचने की सोच रहे हैं। बेचने से पहले देखिए कि "
                "अगले {{ horizon_years }} साल में इस एक फ़ैसले की कीमत क्या हो सकती है।"
                "{% endif %}"
            ),
            "whats_happening": (
                "अभी आपका निवेश {{ gl_pct }} नीचे है, और यह वाक़ई तकलीफ़ देता है। पर बात यह है कि "
                "हज़ारों निवेशकों पर हुए शोध बताते हैं — नुकसान का दर्द उतने ही बड़े फ़ायदे की ख़ुशी से "
                "लगभग दोगुना महसूस होता है। यानी जो बेचैनी आप महसूस कर रहे हैं, वह असली नुकसान से "
                "कहीं ज़्यादा बड़ी है।\n\n"
                "इस बेचैनी का एक ही मक़सद है — दर्द रोकना। लेकिन बेचने से नुकसान रुकता नहीं, वह पक्का "
                "हो जाता है। अभी यह नुकसान सिर्फ़ काग़ज़ पर है, और काग़ज़ का नुकसान समय मिलने पर अक्सर "
                "वापस भर जाता है।"
            ),
            "why_we_say_this": (
                "हमने देखा कि इस फ़ैसले के पीछे असल में क्या था, और सबसे बड़ी वजह थी {{ top_driver }}। "
                "{% if other_drivers %}{{ other_drivers_sentence }}{% endif %}\n\n"
                "यही पहचान है। जब फ़ैसला निवेश में हुए किसी असली बदलाव से नहीं, बल्कि नुकसान की चुभन से "
                "निकले, तो वह आमतौर पर आपकी भावनाएँ बोल रही होती हैं — आपकी समझ नहीं।"
            ),
        },

        "herd": {
            "headline": (
                "{% if resisted %}"
                "अभी लगभग {{ crowd_pct }} निवेशक बेच रहे हैं, और आपने उनके साथ न जाने का फ़ैसला किया। "
                "जब सब भाग रहे हों तब टिके रहना आसान नहीं होता — और यहाँ यही सही क़दम है।"
                "{% else %}"
                "अभी लगभग {{ crowd_pct }} निवेशक बेच रहे हैं, और आप भी वही करने जा रहे हैं। देखिए कि "
                "उनके पीछे चलने की कीमत क्या हो सकती है।"
                "{% endif %}"
            ),
            "whats_happening": (
                "इस समय लगभग {{ crowd_pct }} निवेशक बेच रहे हैं। जब इतने लोग एक साथ क़दम उठाते हैं, तो "
                "रुके रहना लापरवाही जैसा लगता है — मानो उन्हें कुछ ऐसा पता हो जो आपको नहीं।\n\n"
                "आमतौर पर ऐसा होता नहीं। उनमें से ज़्यादातर लोग भी एक-दूसरे को ही देख रहे होते हैं, और डर "
                "तथ्यों से तेज़ फैलता है। बाज़ार की असहज सच्चाई यह है कि जिस पल बेचना सबसे सही लगता है, "
                "अक्सर वही सबसे ग़लत पल होता है।"
            ),
            "why_we_say_this": (
                "इस फ़ैसले पर सबसे ज़्यादा असर डाला {{ top_driver }} ने। "
                "{% if other_drivers %}{{ other_drivers_sentence }}{% endif %}\n\n"
                "ध्यान दीजिए कि इस सूची में क्या नहीं है — आपके निवेश या आपकी अपनी योजना में हुआ कोई "
                "असली बदलाव। भीड़ का मिज़ाज बदला, और वह आपको भी अपने साथ खींच ले गया।"
            ),
        },

        "disposition": {
            "headline": (
                "{% if resisted %}"
                "आप {{ gl_pct }} ऊपर हैं और जल्दी मुनाफ़ा लेने के बजाय निवेश को चलने देना चुन रहे हैं। "
                "यह मुश्किल रास्ता है, और आँकड़े इसके साथ हैं।"
                "{% elif gl_is_gain %}"
                "आप {{ gl_pct }} ऊपर हैं और मुनाफ़ा निकाल लेने की सोच रहे हैं। जीत पक्की कर लेना अच्छा "
                "लगता है — देखिए इसकी कीमत आमतौर पर क्या होती है।"
                "{% else %}"
                "आप {{ gl_pct }} नीचे हैं और निवेश पकड़े हुए हैं। इसे थोड़ा ध्यान से देखना ज़रूरी है — "
                "आँकड़े इस बारे में क्या कहते हैं, यह रहा।"
                "{% endif %}"
            ),
            "whats_happening": (
                "{% if gl_is_gain %}"
                "आप {{ gl_pct }} ऊपर हैं, और मन कर रहा है कि मुनाफ़ा ग़ायब होने से पहले जेब में डाल लें। "
                "यह खिंचाव निवेश की सबसे आम आदतों में से एक है — लोग फ़ायदे वाले निवेश जल्दी बेच देते हैं "
                "और घाटे वाले बहुत लंबे समय तक पकड़े रहते हैं।\n\n"
                "यह समझदारी जैसा लगता है — आप 'मुनाफ़ा ले रहे हैं'। लेकिन बढ़ता हुआ निवेश आमतौर पर किसी "
                "वजह से बढ़ रहा होता है, और उसे बीच में काट देने का मतलब है कि छोटी-छोटी जीतें आपके पास "
                "रहें और पूरे नुकसान आप उठाते रहें। {{ horizon_years }} साल में यह फ़र्क़ बहुत बड़ा हो जाता है।"
                "{% else %}"
                "आप {{ gl_pct }} नीचे हैं और निवेश में बने हुए हैं। कई बार यही सही होता है। लेकिन जो आदत "
                "लोगों से फ़ायदे वाले निवेश जल्दी बिकवाती है, वही उन्हें घाटे वाले निवेश से चिपके रहने पर "
                "मजबूर करती है — इस उम्मीद में कि कम-से-कम बराबरी पर तो आ जाएँ।\n\n"
                "सही सवाल यह नहीं है कि 'क्या यह वापस ऊपर आएगा?' — सही सवाल है 'अगर आज यही पैसा मेरे पास "
                "नक़द होता, तो क्या मैं यह निवेश दोबारा ख़रीदता?' इस सवाल में अहंकार नहीं होता।"
                "{% endif %}"
            ),
            "why_we_say_this": (
                "यहाँ सबसे बड़ी वजह थी {{ top_driver }}। "
                "{% if other_drivers %}{{ other_drivers_sentence }}{% endif %}\n\n"
                "यह आदत आसानी से पकड़ में नहीं आती, क्योंकि अलग-अलग देखने पर हर फ़ैसला समझदारी भरा लगता है। "
                "यह तभी दिखती है जब कई फ़ैसलों को एक साथ देखा जाए — और हमने ठीक यही किया है।"
            ),
        },

        "rational": {
            "headline": (
                "यह एक समझदारी भरा फ़ैसला लगता है। हमें ऐसा कोई संकेत नहीं मिला कि डर, भीड़ या पुरानी आदत "
                "आपको चला रही हो — तो सीधे पैसे की तस्वीर देखते हैं।"
            ),
            "whats_happening": (
                "हमने आपके इस फ़ैसले को उन तीन आदतों के सामने रखकर देखा जो निवेशकों का सबसे ज़्यादा पैसा "
                "ले जाती हैं: नुकसान पर घबरा जाना, भीड़ के पीछे चलना, और फ़ायदे वाले निवेश जल्दी बेच देना। "
                "इनमें से कोई भी यहाँ साफ़ तौर पर नहीं दिखी।\n\n"
                "इसका मतलब यह नहीं कि यह अपने आप सबसे अच्छा वित्तीय क़दम है — इसका मतलब सिर्फ़ इतना है कि "
                "फ़ैसला आपका है, आपकी घबराहट का नहीं। अब बस यह देखना बाक़ी है कि आँकड़े क्या कहते हैं।"
            ),
            "why_we_say_this": (
                "इस फ़ैसले को आकार देने वाली बातें थीं {{ top_driver }}"
                "{% if other_drivers %}, और साथ में {{ other_drivers_plain }}{% endif %} — "
                "ये सब आपकी सामान्य परिस्थिति का हिस्सा हैं, कोई भावनात्मक दबाव नहीं।\n\n"
                "इसलिए आगे जो लिखा है उसे चेतावनी नहीं, जानकारी मानिए।"
            ),
        },

        "unknown": {
            "headline": (
                "हम इस फ़ैसले को किसी जानी-पहचानी आदत में यक़ीन के साथ नहीं रख पाए, इसलिए नीचे दिए आँकड़ों "
                "को ही मुख्य आधार मानिए।"
            ),
            "whats_happening": (
                "आपकी स्थिति सामान्य पैटर्न से इतनी साफ़ नहीं मिलती कि हम यक़ीन के साथ कह सकें कि इसके पीछे "
                "क्या है। ऐसा होता है, और अंदाज़ा लगाने से बेहतर है कि हम यह साफ़-साफ़ कह दें।\n\n"
                "जो हम फिर भी भरोसे के साथ कर सकते हैं, वह यह है कि हर विकल्प आपको आर्थिक रूप से कहाँ ले "
                "जाएगा, यह दिखा दें।"
            ),
            "why_we_say_this": (
                "जो बातें हम माप सके वे थीं {{ top_driver }}"
                "{% if other_drivers %} और {{ other_drivers_plain }}{% endif %}, लेकिन इनमें से कोई भी "
                "अकेले इस फ़ैसले को समझाने के लिए काफ़ी मज़बूत नहीं थी।\n\n"
                "जब पैटर्न साफ़ न हो, तो लंबी अवधि के आँकड़ों पर भरोसा करना ज़्यादा सुरक्षित होता है।"
            ),
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# SHARED TEMPLATES — sections 3, 4, 6 (driven by the simulation, not the bias)
# ═══════════════════════════════════════════════════════════════════════════

SHARED: dict[str, dict[str, str]] = {

    "en": {
        "two_futures": (
            "We ran your actual situation through {{ n_sim_plain }} different versions of the "
            "next {{ horizon_years }} years — good markets, bad markets, crashes and recoveries. "
            "Here's where each choice tends to leave you.\n\n"
            "**If you stay invested:** around {{ hold_mean }} by year {{ horizon_years }}. "
            "If things go badly, closer to {{ hold_bad }}. If things go well, about {{ hold_good }}.\n\n"
            "**If you sell now:** around {{ sell_mean }}. "
            "If things go badly, closer to {{ sell_bad }}. If things go well, about {{ sell_good }}.\n\n"
            "{% if better_is_hold %}"
            "Out of every 100 possible futures, staying invested comes out ahead in "
            "{{ prob_hold_better_100 }} of them. Selling now would leave you about {{ gap }} "
            "poorer on average — that's {{ gap_pct }} of what you have today."
            "{% else %}"
            "Out of every 100 possible futures, staying invested only comes out ahead in "
            "{{ prob_hold_better_100 }} of them. In your particular situation, selling is the "
            "stronger choice — by about {{ gap }} on average."
            "{% endif %}"
        ),

        "money_story": (
            "**Where your money stands today.** You have {{ invested_amount }} invested, and it is "
            "currently worth {{ position_today }}.\n\n"
            "{% if has_day_one_cost %}"
            "If you sell today you don't walk away with {{ position_today }}. After brokerage, taxes "
            "and the gap between the buying and selling price — roughly {{ sell_cost_pct }} in all — "
            "you'd be left with {{ sell_proceeds }} to put somewhere else. So selling costs you "
            "{{ day_one_cost }} straight away, before your money has had the chance to earn anything.\n\n"
            "{% endif %}"

            "**What each choice then does with it.**\n\n"
            "- **If you stay invested** — your {{ position_today }} stays in your current mix: "
            "{{ hold_stock_pct }} in shares and {{ hold_bond_pct }} in bonds. That split comes from "
            "your age, your {{ horizon_years }}-year timeline, and how much risk you're comfortable "
            "with. Shares jump around a lot, but over long stretches they are what actually grows "
            "your money.\n"
            "- **If you sell now** — your {{ sell_proceeds }} goes somewhere much safer: "
            "{{ sell_stock_pct }} in shares and {{ sell_bond_pct }} in bonds. It stops giving you "
            "sleepless nights, but bonds earn only about {{ bond_rate_pct }} a year, so your money "
            "grows far more slowly.\n\n"

            "That second point is the one almost everybody misses. Selling isn't just leaving this "
            "one investment. After a fright, people put the money somewhere safe and then leave it "
            "there — often for years. Over {{ horizon_years }} years, that caution usually costs "
            "more than the fall you were trying to escape.\n\n"

            "**Year by year.** Here is where your money is most likely to sit at the end of each "
            "year. The last column is how much more you'd have by staying invested.\n\n"
            "{{ year_table }}\n\n"
            "{% if dip_note %}{{ dip_note }}\n\n{% endif %}"

            "**How these numbers were worked out.** Each year, your money is multiplied by what your "
            "mix earned that year — partly how shares did, partly the interest from bonds. The next "
            "year then starts from that new total, so growth builds on earlier growth. That is also "
            "why the difference between the two columns doesn't grow by the same amount every year "
            "— it widens through good stretches and narrows through bad ones.\n\n"
            "Nobody knows which way markets will actually go, so we didn't guess. We ran your "
            "situation through {{ n_sim_plain }} different versions of the next {{ horizon_years }} "
            "years — booms, slumps and crashes included — and the table shows the middle one. Half "
            "of those futures turned out better than this, half turned out worse.\n\n"
            "{{ story_closing }}"
        ),

        "what_to_do_now": (
            "**{{ action_line }}**\n\n"
            "{{ horizon_line }}{% if emergency_line %} {{ emergency_line }}{% endif %}\n\n"
            "{{ confidence_line }}"
        ),
    },

    "hi": {
        "two_futures": (
            "हमने आपकी असली स्थिति को अगले {{ horizon_years }} साल के {{ n_sim_plain }} अलग-अलग रूपों से "
            "गुज़ारा — अच्छे बाज़ार, बुरे बाज़ार, गिरावटें और वापसियाँ। हर विकल्प आपको आमतौर पर कहाँ ले जाता "
            "है, यह रहा।\n\n"
            "**अगर आप निवेश बनाए रखते हैं:** {{ horizon_years }}वें साल तक लगभग {{ hold_mean }}। "
            "अगर हालात बुरे रहे तो क़रीब {{ hold_bad }}। अगर हालात अच्छे रहे तो लगभग {{ hold_good }}।\n\n"
            "**अगर आप अभी बेच देते हैं:** लगभग {{ sell_mean }}। "
            "अगर हालात बुरे रहे तो क़रीब {{ sell_bad }}। अगर हालात अच्छे रहे तो लगभग {{ sell_good }}।\n\n"
            "{% if better_is_hold %}"
            "हर 100 संभावित भविष्य में से {{ prob_hold_better_100 }} में निवेश बनाए रखना आगे रहता है। "
            "अभी बेचने पर औसतन लगभग {{ gap }} कम रह जाएगा — यानी आज आपके पास जो है उसका {{ gap_pct }}।"
            "{% else %}"
            "हर 100 संभावित भविष्य में से सिर्फ़ {{ prob_hold_better_100 }} में निवेश बनाए रखना आगे रहता है। "
            "आपकी ख़ास स्थिति में बेचना ज़्यादा मज़बूत विकल्प है — औसतन लगभग {{ gap }} का फ़ायदा।"
            "{% endif %}"
        ),

        "money_story": (
            "**आज आपका पैसा कहाँ खड़ा है।** आपने {{ invested_amount }} निवेश किए हैं, और उनकी मौजूदा "
            "क़ीमत {{ position_today }} है।\n\n"
            "{% if has_day_one_cost %}"
            "अगर आप आज बेचते हैं तो आपके हाथ में {{ position_today }} नहीं आएँगे। ब्रोकरेज, टैक्स और "
            "ख़रीद-बिक्री की क़ीमत के अंतर को मिलाकर लगभग {{ sell_cost_pct }} कट जाता है — यानी आपके पास "
            "कहीं और लगाने के लिए {{ sell_proceeds }} बचेंगे। इस तरह बेचने की क़ीमत आपको तुरंत "
            "{{ day_one_cost }} पड़ती है, इससे पहले कि आपके पैसे को कुछ कमाने का मौक़ा भी मिले।\n\n"
            "{% endif %}"

            "**इसके बाद हर विकल्प आपके पैसे के साथ क्या करता है।**\n\n"
            "- **अगर आप निवेश बनाए रखते हैं** — आपके {{ position_today }} आपके मौजूदा मिश्रण में ही रहते "
            "हैं: {{ hold_stock_pct }} शेयरों में और {{ hold_bond_pct }} बॉन्ड में। यह बँटवारा आपकी उम्र, "
            "आपके {{ horizon_years }} साल के समय और आपकी जोखिम सहने की क्षमता से तय होता है। शेयर बहुत "
            "ऊपर-नीचे होते हैं, लेकिन लंबे समय में असल बढ़त वही देते हैं।\n"
            "- **अगर आप अभी बेच देते हैं** — आपके {{ sell_proceeds }} कहीं ज़्यादा सुरक्षित जगह चले जाते "
            "हैं: {{ sell_stock_pct }} शेयरों में और {{ sell_bond_pct }} बॉन्ड में। रातों की नींद लौट आती "
            "है, पर बॉन्ड साल में सिर्फ़ लगभग {{ bond_rate_pct }} कमाते हैं, इसलिए पैसा बहुत धीरे बढ़ता "
            "है।\n\n"

            "दूसरी बात वही है जो लगभग सबसे छूट जाती है। बेचने का मतलब सिर्फ़ इस एक निवेश से निकलना नहीं "
            "होता। एक बार डर बैठ जाने के बाद लोग पैसा किसी सुरक्षित जगह रख देते हैं और फिर उसे वहीं छोड़ "
            "देते हैं — अक्सर सालों तक। {{ horizon_years }} साल में यह सावधानी आमतौर पर उस गिरावट से भी "
            "महँगी पड़ती है जिससे आप बचना चाहते थे।\n\n"

            "**साल दर साल।** नीचे देखिए कि हर साल के अंत में आपका पैसा सबसे संभावित रूप से कहाँ होगा। "
            "आख़िरी ख़ाना बताता है कि निवेश बनाए रखने पर आपके पास कितना ज़्यादा होता।\n\n"
            "{{ year_table }}\n\n"
            "{% if dip_note %}{{ dip_note }}\n\n{% endif %}"

            "**ये आँकड़े कैसे निकाले गए।** हर साल आपका पैसा उस साल की कमाई से गुणा होता है — कुछ हिस्सा "
            "शेयरों के प्रदर्शन से, कुछ बॉन्ड के ब्याज से। अगला साल उसी नए कुल से शुरू होता है, यानी बढ़त "
            "पर फिर बढ़त मिलती है। इसी वजह से दोनों ख़ानों का अंतर हर साल बराबर नहीं बढ़ता — अच्छे "
            "दौर में चौड़ा होता है और बुरे दौर में सिमट जाता है।\n\n"
            "बाज़ार किस ओर जाएगा यह कोई नहीं जानता, इसलिए हमने अंदाज़ा नहीं लगाया। हमने आपकी स्थिति को "
            "अगले {{ horizon_years }} साल के {{ n_sim_plain }} अलग-अलग रूपों से गुज़ारा — तेज़ी, मंदी और "
            "बड़ी गिरावटें भी शामिल — और तालिका बीच वाला रूप दिखाती है। उनमें से आधे भविष्य इससे बेहतर "
            "रहे और आधे इससे ख़राब।\n\n"
            "{{ story_closing }}"
        ),

        "what_to_do_now": (
            "**{{ action_line }}**\n\n"
            "{{ horizon_line }}{% if emergency_line %} {{ emergency_line }}{% endif %}\n\n"
            "{{ confidence_line }}"
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# SENTENCE FRAGMENTS — built in code, injected into the templates above
# ═══════════════════════════════════════════════════════════════════════════

FRAGMENTS: dict[str, dict[str, str]] = {

    "en": {
        # ── section 4 closings ──────────────────────────────────────────
        "story_closing_hold": (
            "Notice how small the difference looks early on, and how large it becomes later. "
            "That's compounding — and it's the entire reason a decision made in one afternoon "
            "matters {{ horizon_years }} years from now."
        ),
        "dip_note": (
            "You'll notice both columns fall between year {{ dip_year_prev }} and year "
            "{{ dip_year }}. That's a market crash in this particular future — the kind that "
            "happens every decade or so. Staying invested falls hardest, which is exactly the "
            "moment selling feels like the obvious thing to do. It is also the moment the "
            "recovery afterwards does the most work for you."
        ),
        "story_closing_hold_late_dip": (
            "The difference grows steadily for years, then narrows near the end when a crash pulls "
            "the invested column down. That is worth seeing plainly: staying invested does not win "
            "smoothly, and it does not win in every future. It still ends {{ gap }} ahead here, and "
            "it comes out ahead in {{ prob_hold_better_100 }} of every 100 futures we ran."
        ),
        "story_closing_sell": (
            "In your case the two paths stay close together, which is why selling isn't the "
            "costly mistake here that it usually is."
        ),

        # ── section 6 action lines ──────────────────────────────────────
        "action_hold": "Our suggestion: stay invested. Don't sell today.",
        "action_sell": "Our suggestion: selling is reasonable in your situation.",
        "action_hold_resisted": "Our suggestion: stick with your decision to stay invested. You're on the right track.",

        # ── section 6 horizon lines ─────────────────────────────────────
        "horizon_long": (
            "You have about {{ horizon_years }} years before you need this money. That's enough "
            "time to sit through several bad stretches and still come out ahead — markets have "
            "always recovered given that long."
        ),
        "horizon_short": (
            "You have about {{ horizon_years }} years before you need this money, which isn't "
            "long. With a shorter runway there's less time to recover from a bad patch, so "
            "protecting what you have matters more than chasing growth."
        ),

        # ── section 6 emergency-fund lines ──────────────────────────────
        "emergency_yes": (
            "You already have emergency savings set aside, so you're not being forced to sell "
            "to cover anything — this is a choice, not a necessity."
        ),
        "emergency_no": (
            "One thing worth fixing first: you don't have emergency savings set aside. Build "
            "that cushion, and you'll never have to sell investments at a bad moment just to "
            "cover a surprise bill."
        ),

        # ── section 6 honesty line ──────────────────────────────────────
        "confidence_line": (
            "How sure are we? We're {{ confidence_word }} about this read of your situation "
            "({{ confidence_pct }}). The rupee figures are estimates drawn from {{ n_sim_plain }} "
            "simulated futures — they show you what usually happens, not what will happen. "
            "Nobody can promise you the future, and you should be suspicious of anyone who does."
        ),

        # ── section 5 driver sentences ──────────────────────────────────
        "other_drivers_two": "After that came {{ d1 }}, then {{ d2 }}.",
        "other_drivers_one": "After that came {{ d1 }}.",

        # ── money_story gap phrases ─────────────────────────────────────
        "gap_ahead"  : "{{ amount }} ahead",
        "gap_behind" : "{{ amount }} behind",
    },

    "hi": {
        "story_closing_hold": (
            "ध्यान दीजिए कि शुरुआत में यह फ़र्क़ कितना छोटा दिखता है, और आगे चलकर कितना बड़ा हो जाता है। "
            "यही चक्रवृद्धि (compounding) है — और यही पूरी वजह है कि एक दोपहर में लिया गया फ़ैसला "
            "{{ horizon_years }} साल बाद इतना मायने रखता है।"
        ),
        "dip_note": (
            "ध्यान दीजिए कि साल {{ dip_year_prev }} और साल {{ dip_year }} के बीच दोनों ख़ाने नीचे "
            "गिरते हैं। इस ख़ास भविष्य में वहाँ बाज़ार में बड़ी गिरावट आती है — ऐसी गिरावट लगभग हर दशक "
            "में आती है। निवेश बनाए रखने वाला ख़ाना सबसे ज़्यादा गिरता है, और ठीक वही पल होता है जब "
            "बेचना सबसे सही लगता है। वही पल यह भी तय करता है कि उसके बाद की वापसी आपके लिए कितना "
            "काम करेगी।"
        ),
        "story_closing_hold_late_dip": (
            "यह अंतर सालों तक लगातार बढ़ता है, फिर आख़िर में एक गिरावट निवेश वाले ख़ाने को नीचे खींच "
            "देती है और अंतर सिमट जाता है। इसे साफ़-साफ़ देख लेना ज़रूरी है: निवेश बनाए रखना हर साल "
            "आराम से नहीं जीतता, और हर भविष्य में नहीं जीतता। फिर भी यहाँ यह {{ gap }} आगे रहता है, "
            "और हमने जो 100 भविष्य चलाए उनमें से {{ prob_hold_better_100 }} में यह आगे रहता है।"
        ),
        "story_closing_sell": (
            "आपके मामले में दोनों रास्ते आपस में क़रीब ही रहते हैं, इसीलिए यहाँ बेचना उतनी महँगी ग़लती "
            "नहीं है जितनी आमतौर पर होती है।"
        ),

        "action_hold": "हमारी सलाह: निवेश बनाए रखिए। आज बेचिए मत।",
        "action_sell": "हमारी सलाह: आपकी स्थिति में बेचना एक ठीक फ़ैसला है।",
        "action_hold_resisted": "हमारी सलाह: निवेश बनाए रखने का अपना फ़ैसला क़ायम रखिए। आप सही रास्ते पर हैं।",

        "horizon_long": (
            "इस पैसे की ज़रूरत पड़ने में आपके पास लगभग {{ horizon_years }} साल हैं। यह समय इतना है कि आप "
            "कई बुरे दौर झेलकर भी आगे निकल सकें — इतना वक़्त मिलने पर बाज़ार हमेशा वापस उठा है।"
        ),
        "horizon_short": (
            "इस पैसे की ज़रूरत पड़ने में आपके पास लगभग {{ horizon_years }} साल हैं, जो ज़्यादा नहीं है। "
            "कम समय में बुरे दौर से उबरने का मौक़ा कम मिलता है, इसलिए यहाँ बढ़त के पीछे भागने से ज़्यादा "
            "ज़रूरी है जो है उसे बचाकर रखना।"
        ),

        "emergency_yes": (
            "आपके पास आपातकालीन बचत पहले से मौजूद है, इसलिए किसी ख़र्च के लिए आपको बेचना नहीं पड़ रहा — "
            "यह आपकी पसंद है, मजबूरी नहीं।"
        ),
        "emergency_no": (
            "एक बात पहले सुधारने लायक़ है: आपके पास आपातकालीन बचत अलग से नहीं रखी है। वह गद्दी तैयार कर "
            "लीजिए, फिर किसी अचानक आए ख़र्च के लिए आपको ग़लत वक़्त पर निवेश बेचना नहीं पड़ेगा।"
        ),

        "confidence_line": (
            "हमें कितना यक़ीन है? आपकी स्थिति के इस आकलन पर हमें {{ confidence_word }} "
            "({{ confidence_pct }})। रुपयों के ये आँकड़े {{ n_sim_plain }} संभावित भविष्यों से निकाले गए "
            "अनुमान हैं — ये बताते हैं कि आमतौर पर क्या होता है, यह नहीं कि क्या होगा ही। भविष्य का वादा "
            "कोई नहीं कर सकता, और जो करे उस पर शक कीजिए।"
        ),

        "other_drivers_two": "इसके बाद आया {{ d1 }}, फिर {{ d2 }}।",
        "other_drivers_one": "इसके बाद आया {{ d1 }}।",

        "gap_ahead"  : "{{ amount }} आगे",
        "gap_behind" : "{{ amount }} पीछे",
    },
}


__all__ = [
    "SECTIONS", "SECTION_TITLES", "SUPPORTED_LANGS", "LANG_NAMES",
    "TEMPLATES", "SHARED", "FRAGMENTS", "TABLE_HEADERS",
    "JARGON_MAP", "JARGON_BLOCKLIST", "DRIVER_PLAIN", "BIAS_PLAIN",
    "format_inr", "format_inr_exact", "format_pct", "confidence_word",
]
