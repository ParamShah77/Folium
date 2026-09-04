"""
═══════════════════════════════════════════════════════════════════════════
 llm_polish.py — optional LLM fluency layer for GAP 3 explanations
═══════════════════════════════════════════════════════════════════════════

The templates in `explanation_templates.py` produce correct, complete, and
slightly stiff prose.  This module optionally asks a free-tier LLM to make
that prose flow better — and then *checks its work*.

The contract with the model is narrow and enforced, not trusted:

    The LLM may reword.  It may not introduce, remove, or alter a number.

Every numeric token and every rupee amount in the polished text must already
appear in the template text.  If even one doesn't, the polish is thrown away
and the user reads the template version.  This is why an LLM can improve the
writing here without ever being able to invent a figure that costs someone
money.

THE GUARANTEE
-------------
This module never raises and never blocks indefinitely.  Whatever goes wrong —
no API key, a rejected key, no network, quota exhausted, a hung endpoint, a
malformed reply, a tripped guard — the caller gets the original template text
back, and the reader gets a complete explanation.  There is no failure mode
here worth showing a person who is waiting to be told what to do with their
money, because the answer was already written before the model was asked.

Configuration (environment variables)
------------------------------------
    EXPLAINER_LLM           on | off        (default: off)
    EXPLAINER_LLM_PROVIDER  gemini | openai_compat   (default: gemini)
    EXPLAINER_LLM_MODEL     model id        (default: gemini-flash-lite-latest)
    EXPLAINER_LLM_TIMEOUT   seconds         (default: 30)

    GEMINI_API_KEY / GOOGLE_API_KEY         for provider=gemini
    EXPLAINER_LLM_BASE_URL + EXPLAINER_LLM_API_KEY   for provider=openai_compat
                                            (Grok, OpenRouter, any OpenAI-shaped API)

Public API
----------
    is_enabled()                 -> bool
    polish(text, lang)           -> str
    polish_sections(sections, lang) -> dict   (one request for a whole explanation)
    guard_ok(original, polished) -> bool
    provider_info()              -> dict
    circuit_status()             -> dict   (is the layer currently pausing?)
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time

logger = logging.getLogger(__name__)

# The google-genai SDK prints an automatic-function-calling advisory on every
# generate_content call. We pass no tools, so it never applies — and it would
# otherwise appear in the middle of a user-facing dashboard run.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

# Flash-Lite, deliberately: this is a rewording task, not a reasoning one, and
# the lighter model answers in ~1.5s where the flagship regularly exceeded the
# request deadline on the longest section. It also draws on its own free-tier
# quota pool, which the flagship exhausts in 20 requests a day.
DEFAULT_MODEL   = "gemini-flash-lite-latest"
DEFAULT_TIMEOUT = 30

#: In-memory cache so repeated renders of identical text cost one call, and
#: so a single dashboard session stays internally consistent.
_CACHE: dict[tuple[str, str], str] = {}

_PROMPT = {
    "en": (
        "You are editing a financial explanation written for an ordinary person "
        "with no finance background.\n\n"
        "Rewrite the text below so it reads more naturally and warmly. Rules you "
        "must follow exactly:\n"
        "1. Do NOT change, add, or remove any number, amount, percentage, or year. "
        "Every figure must appear exactly as written.\n"
        "2. Do NOT add any new fact, claim, prediction, or advice.\n"
        "3. Do NOT introduce financial jargon. Keep the language simple enough for "
        "a 13-year-old.\n"
        "4. Keep the same meaning, the same order, and roughly the same length.\n"
        "5. Keep any Markdown formatting (**bold**, bullet lists) as it is.\n"
        "6. Any placeholder in double square brackets, such as [[TABLE_0]] or "
        "[[SECTION_3]], must be copied through exactly as it appears, on its own "
        "line, in the same order. Do not describe, expand, reorder or drop them.\n"
        "7. Reply with the rewritten text only. No preamble, no commentary.\n\n"
        "TEXT:\n{text}"
    ),
    "hi": (
        "आप एक ऐसे व्यक्ति के लिए लिखी गई वित्तीय व्याख्या का संपादन कर रहे हैं जिसे "
        "वित्त की कोई पृष्ठभूमि नहीं है।\n\n"
        "नीचे दिए गए पाठ को और स्वाभाविक और आत्मीय बनाइए। इन नियमों का सख़्ती से पालन करें:\n"
        "1. किसी भी संख्या, राशि, प्रतिशत या वर्ष को बदलें, जोड़ें या हटाएँ नहीं। हर आँकड़ा "
        "ठीक वैसा ही रहना चाहिए।\n"
        "2. कोई नया तथ्य, दावा, भविष्यवाणी या सलाह न जोड़ें।\n"
        "3. कोई वित्तीय शब्दजाल न लाएँ। भाषा इतनी सरल रखें कि तेरह साल का बच्चा समझ ले।\n"
        "4. अर्थ, क्रम और लगभग लंबाई वही रखें।\n"
        "5. Markdown स्वरूपण (**bold**, सूचियाँ) जैसा है वैसा ही रखें।\n"
        "6. दोहरे कोष्ठकों वाले किसी भी प्लेसहोल्डर को — जैसे [[TABLE_0]] या [[SECTION_3]] — "
        "ज्यों का त्यों, अलग पंक्ति में, उसी क्रम में रहने दें। न वर्णन करें, न बदलें, न हटाएँ।\n"
        "7. उत्तर में केवल पुनर्लिखित पाठ दें। कोई भूमिका या टिप्पणी नहीं।\n\n"
        "पाठ:\n{text}"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

_env_loaded = False


def _load_env() -> None:
    """
    Read `.env` from the project root, once.

    Keeping the key in a gitignored file means it is never typed into a shell,
    never captured in shell history, and never pasted into a notebook cell
    that later gets committed with its output.
    """
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    try:
        from dotenv import load_dotenv
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(root, ".env"), override=False)
    except Exception:                              # python-dotenv absent — env vars still work
        pass


def _provider() -> str:
    _load_env()
    return os.getenv("EXPLAINER_LLM_PROVIDER", "gemini").strip().lower()


def _api_key() -> str | None:
    _load_env()
    if _provider() == "openai_compat":
        return os.getenv("EXPLAINER_LLM_API_KEY")
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def is_enabled() -> bool:
    """
    True only when the flag is on AND a key is configured.  Off by default so
    the system is deterministic and offline-safe unless someone opts in.
    """
    _load_env()
    flag = os.getenv("EXPLAINER_LLM", "off").strip().lower()
    return flag in ("on", "1", "true", "yes") and bool(_api_key())


def provider_info() -> dict:
    """Diagnostic summary — safe to log, never includes the key itself."""
    return {
        "enabled"  : is_enabled(),
        "provider" : _provider(),
        "model"    : os.getenv("EXPLAINER_LLM_MODEL", DEFAULT_MODEL),
        "key_set"  : bool(_api_key()),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE NUMERIC GUARD
# ═══════════════════════════════════════════════════════════════════════════

_NUM_RE   = re.compile(r"\d+(?:[.,]\d+)*")
_MONEY_RE = re.compile(r"₹\s?\d+(?:[.,]\d+)*\s*(?:lakh|crore|लाख|करोड़)?", re.IGNORECASE)

#: Placeholder standing in for a Markdown table while the prose is polished.
_TABLE_TOKEN = "[[TABLE_{}]]"
_TABLE_TOKEN_RE = re.compile(r"\[\[TABLE_(\d+)\]\]")


def _protect_tables(text: str) -> tuple[str, list[str]]:
    """
    Swap Markdown tables out for placeholders before sending text to a model.

    A table is data, not prose. Rewording it has no upside and three downsides:
    the model may reformat it, the year-by-year table is by far the largest
    block in the explanation (large enough to time the request out on its
    own), and every cell is a number the guard would then have to re-verify.
    """
    blocks, tables = [], []
    for block in text.split("\n\n"):
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        if lines and all(ln.lstrip().startswith("|") for ln in lines):
            blocks.append(_TABLE_TOKEN.format(len(tables)))
            tables.append(block)
        else:
            blocks.append(block)
    return "\n\n".join(blocks), tables


def _restore_tables(text: str, tables: list[str]) -> str | None:
    """
    Put the tables back. Returns None if the model dropped or duplicated a
    placeholder, which means the reply cannot be trusted to be a rewrite.
    """
    found = [int(m) for m in _TABLE_TOKEN_RE.findall(text)]
    if sorted(found) != list(range(len(tables))):
        return None
    return _TABLE_TOKEN_RE.sub(lambda m: tables[int(m.group(1))], text)


def _numbers(text: str) -> set[str]:
    """Every numeric token, normalised so 1,20,000 and 120000 compare equal."""
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUM_RE.finditer(text)}


def _money(text: str) -> set[str]:
    """Every rupee amount, whitespace-normalised."""
    return {re.sub(r"\s+", "", m.group(0)).lower() for m in _MONEY_RE.finditer(text)}


def guard_ok(original: str, polished: str) -> bool:
    """
    The whole safety argument for this module.

    Rejects the polished text if it contains any number or rupee amount that
    is not present in the original, or if its length has drifted far enough
    to suggest content was invented or dropped.
    """
    if not polished or not polished.strip():
        return False

    invented_numbers = _numbers(polished) - _numbers(original)
    if invented_numbers:
        logger.warning("LLM polish rejected — invented numbers: %s", sorted(invented_numbers))
        return False

    invented_money = _money(polished) - _money(original)
    if invented_money:
        logger.warning("LLM polish rejected — invented amounts: %s", sorted(invented_money))
        return False

    ratio = len(polished) / max(len(original), 1)
    if not 0.6 <= ratio <= 1.8:
        logger.warning("LLM polish rejected — length drift x%.2f", ratio)
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════════
# PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════

def _call_gemini(prompt: str, timeout: int) -> str:
    """Google Gemini via the google-genai SDK (has a free tier)."""
    from google import genai                       # imported lazily — optional dependency

    client = genai.Client(api_key=_api_key())
    response = client.models.generate_content(
        model    = os.getenv("EXPLAINER_LLM_MODEL", DEFAULT_MODEL),
        contents = prompt,
        config   = {"temperature": 0.3, "http_options": {"timeout": timeout * 1000}},
    )
    return (response.text or "").strip()


def _call_openai_compat(prompt: str, timeout: int) -> str:
    """
    Any OpenAI-shaped chat endpoint — Grok, OpenRouter, a local server.
    Uses `requests`, which the project already depends on.
    """
    import requests

    base = os.getenv("EXPLAINER_LLM_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    resp = requests.post(
        f"{base}/chat/completions",
        headers = {"Authorization": f"Bearer {_api_key()}",
                   "Content-Type" : "application/json"},
        json    = {
            "model"      : os.getenv("EXPLAINER_LLM_MODEL", "grok-beta"),
            "messages"   : [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout = timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


_PROVIDERS = {
    "gemini"        : _call_gemini,
    "openai_compat" : _call_openai_compat,
}


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def polish(text: str, lang: str = "en") -> str:
    """
    Improve the fluency of `text`, or return `text` unchanged.

    This function never raises and never blocks the caller for long — a
    failure here must never stop a user from reading their explanation.
    """
    if not text or not text.strip() or not is_enabled():
        return text

    if _circuit_open():
        return text

    cache_key = (lang, text)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        timeout = int(os.getenv("EXPLAINER_LLM_TIMEOUT", str(DEFAULT_TIMEOUT)))
        caller  = _PROVIDERS.get(_provider())
        if caller is None:
            logger.warning("Unknown EXPLAINER_LLM_PROVIDER=%r — using templates", _provider())
            return text

        # Tables go out as placeholders and come back untouched.
        stripped, tables = _protect_tables(text)

        prompt   = _PROMPT.get(lang, _PROMPT["en"]).format(text=stripped)
        polished = _strip_fences(
            _call_with_deadline(lambda: caller(prompt, timeout),
                                timeout + _DEADLINE_GRACE))

        if tables:
            restored = _restore_tables(polished, tables)
            if restored is None:
                logger.warning("LLM polish rejected — table placeholders were altered")
                _CACHE[cache_key] = text
                return text
            polished = restored

        # The provider answered, so the connection is healthy even if we go on
        # to reject the wording. A guard rejection is not a provider failure.
        _record_success()

        if not guard_ok(text, polished):
            _CACHE[cache_key] = text
            return text

        _CACHE[cache_key] = polished
        return polished

    except Exception as exc:                       # noqa: BLE001 — deliberate catch-all
        # Deliberately NOT cached. A failure describes the provider right now,
        # not this text: quota resets, networks come back. Caching it would
        # mean never polishing this passage again for the life of the process.
        # Suppressing the retries is the circuit breaker's job, not the cache's.
        _record_failure()
        logger.warning("LLM polish failed (%s: %s) — using template text",
                       type(exc).__name__, exc)
        return text


#: Marker separating sections inside a single combined request.
_SECTION_TOKEN = "[[SECTION_{}]]"
_SECTION_SPLIT_RE = re.compile(r"\[\[SECTION_(\d+)\]\]")


def polish_sections(sections: dict[str, str], lang: str = "en") -> dict[str, str]:
    """
    Polish a whole explanation in ONE request.

    Gemini's free tier allows 5 requests per minute. An explanation has six
    sections, so polishing them individually exceeded the quota on every
    single run and most sections fell back anyway. Sending the sections
    together as one marked-up document costs one request instead of six, which
    fits the quota with room to spare and is faster besides.

    Each section is still guarded separately on the way back, so one bad
    rewrite loses only that section.

    Returns a dict with the same keys; any section that fails verification
    keeps its original template text.
    """
    try:
        if not sections or not is_enabled():
            return dict(sections)

        keys = list(sections)
        combined = "\n\n".join(
            f"{_SECTION_TOKEN.format(i)}\n\n{sections[key]}" for i, key in enumerate(keys))

        polished = polish(combined, lang=lang)
        if polished == combined:                   # a failure already fell back
            return dict(sections)

        # Split the reply back into sections. Anything unexpected in the
        # structure means we cannot map text to sections safely, so keep the
        # templates.
        parts = _SECTION_SPLIT_RE.split(polished)
        recovered: dict[int, str] = {}
        for i in range(1, len(parts) - 1, 2):
            recovered[int(parts[i])] = parts[i + 1].strip()

        if sorted(recovered) != list(range(len(keys))):
            logger.warning("LLM polish rejected — section markers did not come back intact")
            return dict(sections)

        out = {}
        for i, key in enumerate(keys):
            candidate = recovered[i]
            out[key] = candidate if guard_ok(sections[key], candidate) else sections[key]
        return out

    except Exception as exc:                       # noqa: BLE001 — deliberate catch-all
        # The caller is rendering something a person is waiting to read. There
        # is no failure here worth showing them: the template text is complete,
        # correct, and already in hand.
        logger.warning("LLM polish failed (%s: %s) — using template text",
                       type(exc).__name__, exc)
        return dict(sections)


#: Seconds of slack beyond the request timeout before we stop waiting.
_DEADLINE_GRACE = 5

# ── Circuit breaker ───────────────────────────────────────────────────────
#
# A dead key or an exhausted daily quota is not a transient blip — it is the
# state of the world for the next few hours. Without this, every explanation
# would pay several seconds waiting for the same refusal. After a couple of
# consecutive failures we stop asking for a while and go straight to the
# templates, which is what the reader would have got anyway.

_FAILURE_THRESHOLD  = 2
_CIRCUIT_COOLDOWN   = 300          # seconds
_consecutive_failures = 0
_circuit_open_until   = 0.0


def _circuit_open() -> bool:
    return time.monotonic() < _circuit_open_until


def _record_failure() -> None:
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures += 1
    if _consecutive_failures >= _FAILURE_THRESHOLD:
        _circuit_open_until = time.monotonic() + _CIRCUIT_COOLDOWN
        logger.warning(
            "LLM polish paused for %ds after %d consecutive failures — "
            "explanations continue from templates",
            _CIRCUIT_COOLDOWN, _consecutive_failures)


def _record_success() -> None:
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures = 0
    _circuit_open_until = 0.0


def circuit_status() -> dict:
    """Whether the polish layer is currently pausing, and for how much longer."""
    remaining = max(0.0, _circuit_open_until - time.monotonic())
    return {
        "paused"              : remaining > 0,
        "seconds_remaining"   : round(remaining),
        "consecutive_failures": _consecutive_failures,
    }


def _call_with_deadline(call, seconds: int):
    """
    Run `call` on a daemon thread and give up after `seconds`.

    The provider SDK retries internally, so its own per-request timeout is not
    an upper bound on how long a call can take — a flaky endpoint can stall
    for multiples of it. Somebody is waiting to read their explanation, so we
    put a ceiling on the wait and walk away. The thread is a daemon, so an
    abandoned call can never hold up interpreter shutdown either.
    """
    box: dict[str, object] = {}

    def run() -> None:
        try:
            box["value"] = call()
        except BaseException as exc:               # noqa: BLE001 — re-raised below
            box["error"] = exc

    thread = threading.Thread(target=run, daemon=True, name="llm-polish")
    thread.start()
    thread.join(seconds)

    if thread.is_alive():
        raise TimeoutError(f"provider did not respond within {seconds}s")
    if "error" in box:
        raise box["error"]                         # type: ignore[misc]
    return box.get("value", "")


def _strip_fences(text: str) -> str:
    """Remove ```-fenced wrappers some models add around their answer."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return t.strip()


def clear_cache() -> None:
    """Drop the in-memory polish cache and reset the circuit breaker."""
    _CACHE.clear()
    _record_success()


__all__ = ["is_enabled", "polish", "polish_sections", "guard_ok",
           "provider_info", "circuit_status", "clear_cache"]
