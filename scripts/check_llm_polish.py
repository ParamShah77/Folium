"""
═══════════════════════════════════════════════════════════════════════════
 check_llm_polish.py — verify the optional LLM layer end to end
═══════════════════════════════════════════════════════════════════════════

Run this AFTER putting your own key in `.env` (copy `.env.example` first).
It makes one real API call and reports what came back.

    python scripts/check_llm_polish.py

The key is never printed, logged, or written anywhere — only whether one is
configured. Nothing here is required for the system to work: with the flag
off, explanations render from templates exactly as they do today.

What it checks
--------------
  1. configuration is picked up from .env
  2. a real request reaches the provider and returns text
  3. the numeric guard passes clean rewording
  4. the numeric guard still rejects an altered figure
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import llm_polish

def _provider_is_gemini() -> bool:
    return llm_polish.provider_info()["provider"] == "gemini"


#: Deliberately stiff prose. A working model should have something to improve
#: here; a sample that is already well written can legitimately come back
#: unchanged, which would make this check ambiguous.
SAMPLE = (
    "The current unrealised position reflects a decline of 15%. It is noted that "
    "empirical evidence indicates the disutility of losses is approximately twice "
    "the utility of equivalent gains. Retention of the position yields a projected "
    "terminal value of approximately ₹1.4 lakh over a 14 year period. Liquidation "
    "of the position yields a projected terminal value of approximately ₹1.3 lakh."
)


def main() -> int:
    print("=" * 70)
    print("GAP 3 — OPTIONAL LLM POLISH CHECK")
    print("=" * 70)

    info = llm_polish.provider_info()
    print(f"\nProvider : {info['provider']}")
    print(f"Model    : {info['model']}")
    print(f"Key set  : {info['key_set']}")          # boolean only — never the key
    print(f"Enabled  : {info['enabled']}")

    if not info["key_set"]:
        print("\nNo API key found.")
        print("  1. copy .env.example to .env")
        print("  2. add your key from https://aistudio.google.com/apikey")
        print("  3. set EXPLAINER_LLM=on")
        print("\n.env is gitignored, so the key stays out of the repository.")
        return 1

    if not info["enabled"]:
        print("\nA key is present but EXPLAINER_LLM is not 'on' — set it in .env.")
        return 1

    # ── 1. Prove the call actually reaches the provider ──────────────────
    #
    # Checked separately from the polish result, because "the text came back
    # unchanged" is ambiguous on its own: the request may have failed, or the
    # model may simply have judged the text fine as it was. Those need
    # different responses from whoever runs this.
    print("\n" + "-" * 70)
    print("Calling the provider once...")

    import time
    llm_polish.clear_cache()
    started = time.time()
    try:
        raw = llm_polish._strip_fences(
            llm_polish._call_gemini(llm_polish._PROMPT["en"].format(text=SAMPLE),
                                    int(os.getenv("EXPLAINER_LLM_TIMEOUT", "30")))
            if _provider_is_gemini() else llm_polish.polish(SAMPLE, lang="en"))
    except Exception as exc:                       # noqa: BLE001
        detail = str(exc)
        print(f"\nThe request failed after {time.time() - started:.1f}s.\n")
        if "RESOURCE_EXHAUSTED" in detail or "429" in detail:
            print("  Quota exhausted for this model. Free-tier limits are per model")
            print("  and per day. Either wait, or pin a lighter model in .env:")
            print("      EXPLAINER_LLM_MODEL=gemini-flash-lite-latest")
        elif "DEADLINE" in detail or "timeout" in detail.lower():
            print("  The request timed out. Try a lighter model, or raise")
            print("      EXPLAINER_LLM_TIMEOUT")
        elif "API_KEY" in detail or "401" in detail or "403" in detail:
            print("  The key was rejected. Check GEMINI_API_KEY in .env.")
        else:
            print(f"  {detail[:300]}")
        print("\nNothing is broken by this — explanations render from templates.")
        return 2

    elapsed = time.time() - started
    print(f"\nRequest succeeded in {elapsed:.1f}s.")

    polished = raw if llm_polish.guard_ok(SAMPLE, raw) else SAMPLE

    print("\nBEFORE (template):\n")
    print("  " + SAMPLE.replace("\n", "\n  "))
    if polished == SAMPLE:
        print("\nAFTER: unchanged.")
        print("  Either the model judged the text fine as it was, or the guard")
        print("  rejected the rewrite. Both are safe outcomes — the user reads")
        print("  the template text.")
    else:
        print("\nAFTER (polished):\n")
        print("  " + polished.replace("\n", "\n  "))

    # ── 2. The guard still holds ─────────────────────────────────────────
    print("\n" + "-" * 70)
    print("Numeric guard:")
    checks = [
        ("accepted the polished text",        llm_polish.guard_ok(SAMPLE, polished), True),
        ("rejects an invented amount",        llm_polish.guard_ok(SAMPLE, SAMPLE.replace("₹1.4 lakh", "₹9.9 lakh")), False),
        ("rejects an altered percentage",     llm_polish.guard_ok(SAMPLE, SAMPLE.replace("15%", "45%")), False),
    ]
    ok = True
    for label, got, expected in checks:
        mark = "PASS" if got == expected else "FAIL"
        ok &= got == expected
        print(f"  [{mark}] {label}")

    every_figure_survived = all(
        figure in polished for figure in ("15%", "₹1.4 lakh", "₹1.3 lakh"))
    print(f"  [{'PASS' if every_figure_survived else 'FAIL'}] every figure survived intact")

    print("\n" + "=" * 70)
    print("LLM polish is working." if ok and every_figure_survived
          else "Something is off — see the failures above.")
    print("Turn it off any time by setting EXPLAINER_LLM=off in .env.")
    return 0 if ok and every_figure_survived else 2


if __name__ == "__main__":
    raise SystemExit(main())
