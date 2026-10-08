"""Phase B3: when Gemini help may be used.

Three switches must all be on: the server (``AI_HELP``), a configured key
(``GEMINI_API_KEY``, read by src/llm_polish.py), and the investor's own consent
(``users.ai_consent``, off by default). Anything less and the offline paths run:
phrase rules for the comment, number-built text for the debate.
"""
from __future__ import annotations

from ..config import get_settings
from .ml_bridge import ensure_src_importable


def available() -> bool:
    if not get_settings().AI_HELP:
        return False
    ensure_src_importable()
    try:
        from src import llm_polish
    except ImportError:
        return False
    return llm_polish.key_configured()


def allowed_for(consent: bool | None) -> bool:
    return bool(consent) and available()
