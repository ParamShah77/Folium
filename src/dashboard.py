"""
GAP 1 + GAP 2 + GAP 3 – Streamlit Dashboard
============================================
A multi-page financial decision intelligence dashboard that communicates
with the FastAPI backend (default: http://localhost:8000).

Pages
-----
  1. Decision Intelligence Hub — end-to-end: detect, simulate, and explain in
                                 plain language (English / Hindi), with a
                                 downloadable report
  2. Decision Analysis         — bias + SHAP + causal chain, with a plain-language
                                 summary on top
  3. User Profile              — bias score evolution, decision history table
  4. Market Context            — live NIFTY data, regime indicator
  5. Wealth Simulator          — GAP 2 HOLD vs SELL Monte Carlo

Environment variable
--------------------
  API_BASE_URL   — override backend URL (default: http://localhost:8000)

Run
---
  streamlit run src/dashboard.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import requests
import streamlit as st

# ── GAP 3 explainer ───────────────────────────────────────────────────────
# These modules only render text from dicts the API already returned — no
# model loading, no simulation — so importing them here costs nothing and
# saves a round trip.  If they are unavailable the dashboard degrades to the
# technical view instead of breaking.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
try:
    import explanation_report as _report
    import explanation_templates as _tpl
    from explainer import explain_bias_only, generate_complete_explanation
    _EXPLAINER_OK = True
except Exception as _exc:                              # noqa: BLE001
    _report = _tpl = None
    explain_bias_only = generate_complete_explanation = None
    _EXPLAINER_OK = False

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10   # seconds

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="FinDecision Intelligence",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL STYLES
# ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Root palette */
    :root {
        --primary:    #6C63FF;
        --success:    #00C9A7;
        --danger:     #FF6B6B;
        --warning:    #FFB347;
        --bg:         #0E1117;
        --card-bg:    #1E2130;
        --text:       #E0E0E0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background: var(--card-bg); }

    /* Cards */
    .card {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid var(--primary);
    }
    .card-danger  { border-left-color: var(--danger);  }
    .card-success { border-left-color: var(--success); }
    .card-warning { border-left-color: var(--warning); }

    /* Bias banner */
    .bias-banner {
        border-radius: 10px;
        padding: 1rem 1.5rem;
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .bias-biased   { background: rgba(255,107,107,0.2); border: 2px solid #FF6B6B; color: #FF6B6B; }
    .bias-rational { background: rgba(0,201,167,0.2);   border: 2px solid #00C9A7; color: #00C9A7; }

    /* Market banner */
    .market-banner {
        background: var(--card-bg);
        border-radius: 10px;
        padding: 0.8rem 1.2rem;
        display: flex;
        gap: 2rem;
        margin-bottom: 1.2rem;
        border: 1px solid rgba(108,99,255,0.3);
    }

    /* GAP 3 — plain-language narrative */
    .narrative-headline {
        font-size: 1.15rem;
        line-height: 1.65;
        padding: 1.1rem 1.3rem;
        border-radius: 10px;
        border-left: 6px solid #999;
        margin: 0.4rem 0 1.4rem 0;
        background: rgba(150,150,150,0.08);
    }
    .narr-warn { border-left-color: #d9534f; background: rgba(217,83,79,0.09); }
    .narr-ok   { border-left-color: #28a745; background: rgba(40,167,69,0.09); }
    .narr-caption {
        font-size: 0.78rem; color: #888; margin-top: -0.5rem; margin-bottom: 1rem;
    }
    /* Audit hash */
    .audit-hash {
        font-family: monospace;
        font-size: 0.8rem;
        background: rgba(108,99,255,0.1);
        border-radius: 6px;
        padding: 0.5rem 0.8rem;
        word-break: break-all;
    }

    /* ── Index ribbon ─────────────────────────── */
    .ribbon-wrap {
        display: flex;
        gap: 0.6rem;
        margin-bottom: 0.8rem;
        flex-wrap: wrap;
    }
    .ribbon-tile {
        background: var(--card-bg);
        border-radius: 10px;
        padding: 0.5rem 1rem;
        flex: 1 1 140px;
        border: 1px solid rgba(108,99,255,0.25);
        text-align: center;
    }
    .ribbon-tile .r-label  { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }
    .ribbon-tile .r-price  { font-size: 1.05rem; font-weight: 700; color: #E0E0E0; }
    .ribbon-tile .r-chg-up   { font-size: 0.8rem; color: #00C9A7; }
    .ribbon-tile .r-chg-down { font-size: 0.8rem; color: #FF6B6B; }
    .ribbon-tile .r-chg-neu  { font-size: 0.8rem; color: #888; }

    /* ── Tax slab sidebar ─────────────────────── */
    .tax-card {
        background: rgba(108,99,255,0.07);
        border: 1px solid rgba(108,99,255,0.25);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-top: 0.4rem;
    }
    .tax-row {
        display: flex;
        justify-content: space-between;
        padding: 0.18rem 0;
        font-size: 0.82rem;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .tax-row:last-child { border-bottom: none; }
    .tax-key   { color: #aaa; }
    .tax-val   { font-weight: 600; color: #E0E0E0; }
    .tax-badge {
        display: inline-block;
        background: rgba(0,201,167,0.15);
        color: #00C9A7;
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _api_get(path: str) -> dict | None:
    """GET request with graceful error handling."""
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to API at {API_BASE_URL}. Is the server running?")
        return None
    except requests.exceptions.Timeout:
        st.error("API request timed out. Please try again.")
        return None
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def _api_post(path: str, body: dict) -> dict | None:
    """POST request with graceful error handling."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}{path}", json=body, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to API at {API_BASE_URL}. Is the server running?")
        return None
    except requests.exceptions.Timeout:
        st.error("API request timed out. Please try again.")
        return None
    except requests.exceptions.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:
            pass
        st.error(f"API error {exc.response.status_code}: {detail or exc}")
        return None
    except Exception as exc:
        st.error(f"Error: {exc}")
        return None


def _market_regime(ret: float, vol: float) -> tuple[str, str]:
    """Return (label, color) for market regime."""
    if ret < -0.10 or vol > 0.03:
        return "CRASH / HIGH VOLATILITY", "#FF6B6B"
    elif ret < -0.03:
        return "🟠 BEAR MARKET", "#FFB347"
    elif ret < 0.03:
        return "🟡 NEUTRAL", "#FFD700"
    elif ret < 0.10:
        return "BULL MARKET", "#00C9A7"
    else:
        return "RALLY / EUPHORIA", "#6C63FF"


# ══════════════════════════════════════════════════════════════════════════
# INDICES RIBBON  (shown on every page)
# ══════════════════════════════════════════════════════════════════════════

_RIBBON_ORDER = [
    ("nifty50",   "NIFTY 50"),
    ("sensex",    "SENSEX"),
    ("banknifty", "BANK NIFTY"),
    ("india_vix", "India VIX"),
]

def _fetch_ribbon() -> dict:
    """Direct API call for ribbon — backed by a lightning-fast 15-min cache on the FastAPI backend."""
    try:
        resp = requests.get(f"{API_BASE_URL}/market/ribbon", timeout=8)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _render_indices_ribbon():
    """Render the 4-index top ribbon (NIFTY50 / SENSEX / Bank NIFTY / India VIX)."""
    ribbon = _fetch_ribbon()
    if not ribbon:
        return   # silent — no error banners in the ribbon

    tiles_html = ""
    for key, fallback_label in _RIBBON_ORDER:
        idx = ribbon.get(key, {})
        label     = idx.get("label", fallback_label)
        price     = idx.get("price")
        chg       = idx.get("change_pct")
        direction = idx.get("direction", "neutral")

        price_str = f"{price:,.2f}"if price is not None else "N/A"
        if chg is not None:
            sign  = "+"if chg >= 0 else ""
            chg_class = "r-chg-up"if direction == "up"else "r-chg-down"
            arrow = "▲"if direction == "up"else "▼"
            chg_str = f"<span class='{chg_class}'>{arrow} {sign}{chg:.2f}%</span>"
        else:
            chg_str = "<span class='r-chg-neu'>—</span>"

        tiles_html += (
            f"<div class='ribbon-tile'>"
            f"<div class='r-label'>{label}</div>"
            f"<div class='r-price'>{price_str}</div>"
            f"{chg_str}"
            f"</div>"
        )

    src   = ribbon.get("data_source", "")
    upd   = ribbon.get("last_updated", "")[:16]
    caption = f"<span style='font-size:0.7rem;color:#666;'>Source: {src} &nbsp;|&nbsp; {upd} UTC</span>"

    st.markdown(
        f"<div class='ribbon-wrap'>{tiles_html}</div>{caption}",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════

def _render_sidebar():
    st.sidebar.title("FinDecision AI")
    st.sidebar.markdown("---")
    page = st.sidebar.radio(
        "Navigate",
        [
            "Decision Intelligence Hub",
            "Decision Analysis",
            "User Profile",
            "Market Context",
            "Wealth Simulator",   # GAP 2
        ],
        key="page_selector",
    )

    # ── GAP 3: explanation language ──────────────────────────────────────
    if _EXPLAINER_OK:
        st.sidebar.markdown("---")
        names = _tpl.LANG_NAMES
        codes = list(_tpl.SUPPORTED_LANGS)
        current = st.session_state.get("explain_lang", "en")
        chosen = st.sidebar.radio(
            "Explanation language",
            codes,
            index=codes.index(current) if current in codes else 0,
            format_func=lambda c: names[c],
            horizontal=True,
            key="explain_lang_selector",
            help="Switches the plain-language explanation. Results are not recalculated.",
        )
        st.session_state["explain_lang"] = chosen

    st.sidebar.markdown("---")
    st.sidebar.subheader("User Session")

    # User ID input
    if "user_id"not in st.session_state:
        st.session_state.user_id = ""

    uid_input = st.sidebar.text_input(
        "Existing User ID", value=st.session_state.user_id,
        placeholder="Paste your user ID here", key="uid_input"
    )
    if uid_input:
        st.session_state.user_id = uid_input

    # Register new user expander
    with st.sidebar.expander("➕ Register New User"):
        with st.form("register_form"):
            name     = st.text_input("Full Name")
            age      = st.number_input("Age", 18, 100, 35)
            income   = st.number_input("Monthly Income (₹)", 10000, 5000000, 60000, step=5000)
            rt       = st.slider("Risk Tolerance", 0.0, 1.0, 0.5, 0.05)
            horizon  = st.number_input("Investment Horizon (years)", 1, 50, 10)
            emg_fund = st.selectbox("Emergency Fund?", ["Yes", "No"]) == "Yes"
            reg_btn  = st.form_submit_button("Register")

        if reg_btn and name:
            data = {
                "name": name, "age": int(age),
                "monthly_income": float(income),
                "risk_tolerance": float(rt),
                "investment_horizon": int(horizon),
                "has_emergency_fund": int(emg_fund),
            }
            result = _api_post("/user/register", data)
            if result:
                uid = result["user_id"]
                st.session_state.user_id = uid
                st.sidebar.success(f"Registered! User ID:\n`{uid}`")

    # ── Tax Slab Panel ────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    _render_tax_sidebar()

    st.sidebar.markdown("---")
    st.sidebar.caption(f"**API:** {API_BASE_URL}")
    return page


# ══════════════════════════════════════════════════════════════════════════
# TAX SLAB PANEL  (static, hardcoded per FY2024-25 Indian tax rules)
# ══════════════════════════════════════════════════════════════════════════

# FY 2024-25 (post-Budget 23-Jul-2024)
_TAX_DATA = {
    "Equity (Listed)": {
        "STCG": {"rate": "20%", "threshold": "< 12 months", "note": "Section 111A"},
        "LTCG": {"rate": "12.5%", "threshold": "≥ 12 months", "note": "Section 112A"},
        "exemption": "₹1.25 L / year tax-free on LTCG",
    },
    "Equity MF": {
        "STCG": {"rate": "20%", "threshold": "< 12 months", "note": "Same as equity"},
        "LTCG": {"rate": "12.5%", "threshold": "≥ 12 months", "note": "Section 112A"},
        "exemption": "₹1.25 L / year tax-free on LTCG",
    },
    "Debt MF / Bonds": {
        "STCG": {"rate": "Slab rate", "threshold": "< 24 months", "note": "Added to income"},
        "LTCG": {"rate": "12.5%", "threshold": "≥ 24 months", "note": "No indexation"},
        "exemption": "None",
    },
    "Real Estate": {
        "STCG": {"rate": "Slab rate", "threshold": "< 24 months", "note": "Added to income"},
        "LTCG": {"rate": "12.5%", "threshold": "≥ 24 months", "note": "No indexation (post Jul-24)"},
        "exemption": "Sec 54/54F rollover eligible",
    },
    "Gold / Commodities": {
        "STCG": {"rate": "Slab rate", "threshold": "< 36 months", "note": "Added to income"},
        "LTCG": {"rate": "12.5%", "threshold": "≥ 36 months", "note": "No indexation"},
        "exemption": "None",
    },
}

_SURCHARGE_NOTE = (
    "Surcharge: 10% if LTCG > ₹50L (equity). "
    "Health & Edu Cess: 4% on tax + surcharge."
)


def _render_tax_sidebar():
    """Render a static Indian capital-gains tax slab panel in the sidebar."""
    with st.sidebar.expander("📋 Indian Capital Gains Tax (FY25)", expanded=False):
        st.markdown(
            "<div style='font-size:0.72rem;color:#999;margin-bottom:6px;'>"
            "Post Budget 23-Jul-2024 &nbsp;·&nbsp; FY 2024-25"
            "</div>",
            unsafe_allow_html=True,
        )
        for asset, info in _TAX_DATA.items():
            st.markdown(
                f"<div style='font-size:0.78rem;font-weight:700;color:#6C63FF;"
                f"margin-top:8px;margin-bottom:2px;'>{asset}</div>",
                unsafe_allow_html=True,
            )
            rows_html = (
                f"<div class='tax-card'>"
                f"<div class='tax-row'>"
                f" <span class='tax-key'>STCG ({info['STCG']['threshold']})</span>"
                f" <span class='tax-val'>{info['STCG']['rate']}</span>"
                f"</div>"
                f"<div class='tax-row'>"
                f" <span class='tax-key'>LTCG ({info['LTCG']['threshold']})</span>"
                f" <span class='tax-val'>{info['LTCG']['rate']}</span>"
                f"</div>"
                f"<div class='tax-row'>"
                f" <span class='tax-key'>Exemption</span>"
                f" <span class='tax-badge'>{info['exemption']}</span>"
                f"</div>"
                f"</div>"
            )
            st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown(
            f"<div style='font-size:0.68rem;color:#666;margin-top:8px;line-height:1.4;'>"
            f"{_SURCHARGE_NOTE}</div>",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════
# PAGE 1 — DECISION ANALYSIS
# ══════════════════════════════════════════════════════════════════════════

def _render_market_banner():
    """Auto-fetch and display compact market context banner."""
    ctx = _api_get("/market/context")
    if ctx is None:
        st.warning("Market data unavailable — defaults will be used.")
        return

    ret  = ctx.get("market_return", 0)
    vol  = ctx.get("market_volatility", 0)
    crowd = ctx.get("crowd_ratio", 0.5)
    regime_label, regime_color = _market_regime(ret, vol)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NIFTY 1M Return",   f"{ret*100:.2f}%",  delta_color="normal")
    col2.metric("30-Day Volatility", f"{vol*100:.2f}%")
    col3.metric("Crowd Fear Ratio",  f"{crowd:.2f}")
    col4.markdown(
        f"<div style='padding:10px; background: rgba(108,99,255,0.1); "
        f"border-radius:8px; border:1px solid {regime_color}; "
        f"font-weight:700; color:{regime_color};'>{regime_label}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Data source: **{ctx.get('data_source', 'unknown')}** | "
        f"Updated: {ctx.get('last_updated', 'N/A')[:19]} UTC | "
        f"Market hours: {'Open'if ctx.get('market_hours') else '🔒 Closed'}"
    )


def _render_shap_chart(shap_data: list[dict]):
    """Render a horizontal Plotly bar chart for SHAP feature impacts."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("plotly not installed — `pip install plotly`")
        return

    if not shap_data or (len(shap_data) == 1 and "error"in shap_data[0]):
        st.info("SHAP explanations not available for this prediction.")
        return

    features = [d.get("feature", "?")[:30] for d in shap_data]
    impacts  = [d.get("shap_impact", 0) for d in shap_data]
    colors   = ["#FF6B6B"if v > 0 else "#00C9A7"for v in impacts]

    fig = go.Figure(go.Bar(
        x=impacts,
        y=features,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.4f}"for v in impacts],
        textposition="outside",
    ))
    fig.update_layout(
        title="SHAP Feature Contributions (Top 5)",
        xaxis_title="SHAP Impact on Bias Prediction",
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        height=300,
        margin=dict(l=200, r=40, t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# GAP 3 — PLAIN-LANGUAGE NARRATIVE
# ══════════════════════════════════════════════════════════════════════════

def _lang() -> str:
    """The explanation language currently selected in the sidebar."""
    return st.session_state.get("explain_lang", "en")


def _build_explanation(result1: dict, result2: dict, user_input: dict) -> dict | None:
    """
    Narrate results the API has already returned.

    Rendering happens locally and takes milliseconds, so switching language
    or downloading a report never re-runs the model or the simulation.
    """
    if not _EXPLAINER_OK:
        return None
    try:
        return generate_complete_explanation(result1, result2, user_input, _lang())
    except Exception as exc:                           # noqa: BLE001
        st.warning(f"Could not build the plain-language explanation: {exc}")
        return None


def _render_narrative(explanation: dict, sim_result: dict | None = None) -> None:
    """
    The story the user actually reads: one headline, then the sections in
    order, with the wealth chart sitting inside the story rather than after it.
    """
    sections = {s["key"]: s for s in explanation.get("sections", [])}
    calm     = (not explanation.get("is_biased")) or explanation.get("resisted")
    css      = "narr-ok" if calm else "narr-warn"

    if "headline" in sections:
        st.markdown(
            f"<div class='narrative-headline {css}'>{sections['headline']['text']}</div>",
            unsafe_allow_html=True,
        )

    for key in ("whats_happening", "two_futures", "money_story", "why_we_say_this"):
        section = sections.get(key)
        if not section:
            continue
        st.subheader(section["title"])
        st.markdown(section["text"])
        if key == "money_story" and sim_result:
            _render_trajectory_chart(sim_result)

    final = sections.get("what_to_do_now")
    if final:
        st.subheader(final["title"])
        st.info(final["text"])

    if explanation.get("polished"):
        st.caption("Wording refined by an AI writing assistant. Every figure comes "
                   "from the simulation and is checked before display.")


def _render_download_row(explanation: dict) -> None:
    """Offer the explanation as a keepable document."""
    if not _EXPLAINER_OK or _report is None:
        return

    lang    = explanation.get("lang", "en")
    formats = _report.available_formats(lang)
    st.markdown("---")
    st.markdown("**Take this with you**" if lang == "en" else "**इसे अपने साथ ले जाइए**")

    cols = st.columns(3)
    try:
        cols[0].download_button(
            "Report (HTML)" if lang == "en" else "रिपोर्ट (HTML)",
            _report.to_html(explanation).encode("utf-8"),
            file_name=_report.filename_for(explanation, "html"),
            mime="text/html", use_container_width=True,
        )
        cols[1].download_button(
            "Report (Markdown)" if lang == "en" else "रिपोर्ट (Markdown)",
            _report.to_markdown(explanation).encode("utf-8"),
            file_name=_report.filename_for(explanation, "md"),
            mime="text/markdown", use_container_width=True,
        )
        if "pdf" in formats:
            cols[2].download_button(
                "Report (PDF)",
                _report.to_pdf(explanation),
                file_name=_report.filename_for(explanation, "pdf"),
                mime="application/pdf", use_container_width=True,
            )
        else:
            # ReportLab cannot shape Devanagari, so a Hindi PDF would come out
            # wrong. The HTML report prints to a correct PDF from any browser.
            cols[2].caption("PDF के लिए: HTML रिपोर्ट खोलिए और ब्राउज़र से "
                            "Print → Save as PDF कीजिए।")
    except Exception as exc:                           # noqa: BLE001
        st.caption(f"Report download unavailable: {exc}")


def _render_technical_details(result1: dict, result2: dict | None = None) -> None:
    """
    Everything the models actually computed — SHAP, the causal chain, the raw
    distribution statistics. Kept one click away: available to anyone who
    wants it, out of the way of everyone who doesn't.
    """
    with st.expander("Technical details (model output, SHAP, causal chain)", expanded=False):
        bias_type  = result1.get("bias_type", "unknown")
        confidence = result1.get("confidence", 0) * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("Bias Type",  bias_type.replace("_", " ").title())
        c2.metric("Confidence", f"{confidence:.1f}%")
        c3.metric("Risk Score", f"{result1.get('risk_score', 0)*100:.1f}%")

        probs = result1.get("all_probabilities", {})
        if probs:
            st.caption("Class probabilities")
            st.dataframe(
                {"Bias": [k.replace("_", " ").title() for k in probs],
                 "Probability": [f"{v*100:.1f}%" for v in probs.values()]},
                use_container_width=True, hide_index=True,
            )

        shap_data = result1.get("shap_explanation", [])
        if shap_data:
            st.caption("SHAP feature contributions")
            _render_shap_chart(shap_data)

        causal_chain = result1.get("causal_chain", [])
        if causal_chain:
            st.caption("Causal chain (raw effect estimates)")
            for i, step in enumerate(causal_chain, 1):
                st.markdown(f"**Step {i}:** {step}")

        if result2:
            comp = result2.get("comparison", {})
            hold = result2.get("hold", {})
            sell = result2.get("sell", {})

            st.caption("Monte Carlo comparison")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("HOLD — mean", f"₹{hold.get('mean', 0):,.0f}")
            m2.metric("SELL — mean", f"₹{sell.get('mean', 0):,.0f}")
            m3.metric("Opportunity cost", f"₹{abs(comp.get('opportunity_cost_inr', 0)):,.0f}")
            m4.metric("P(HOLD better)", f"{comp.get('prob_hold_better', 0)*100:.1f}%")

            tab1, tab2 = st.tabs(["Final-wealth statistics", "Year-by-year table"])
            with tab1:
                import pandas as pd
                keys = ["mean", "median", "std", "p10", "p25", "p50", "p75", "p90"]
                st.dataframe(pd.DataFrame({
                    "Statistic" : [k.upper() for k in keys],
                    "HOLD (₹)"  : [f"₹{hold.get(k, 0):,.0f}" for k in keys],
                    "SELL (₹)"  : [f"₹{sell.get(k, 0):,.0f}" for k in keys],
                    "Difference": [f"₹{hold.get(k, 0) - sell.get(k, 0):+,.0f}" for k in keys],
                }), use_container_width=True, hide_index=True)

            with tab2:
                import pandas as pd
                horizon = result2.get("horizon_years", 20)
                years   = result2.get("years", list(range(1, horizon + 1)))
                h50     = result2.get("yearly_hold_p50", [])
                s50     = result2.get("yearly_sell_p50", [])
                h10     = result2.get("yearly_hold_p10", [])
                h90     = result2.get("yearly_hold_p90", [])
                if years and h50:
                    st.dataframe(pd.DataFrame({
                        "Year"            : years,
                        "HOLD Median (₹)" : [f"₹{v:,.0f}" for v in h50],
                        "HOLD P10 (₹)"    : [f"₹{v:,.0f}" for v in h10] if h10 else ["-"] * len(years),
                        "HOLD P90 (₹)"    : [f"₹{v:,.0f}" for v in h90] if h90 else ["-"] * len(years),
                        "SELL Median (₹)" : [f"₹{v:,.0f}" for v in s50] if s50 else ["-"] * len(years),
                    }), use_container_width=True, hide_index=True)
                else:
                    st.info("Trajectory data not available.")


def page_unified_pipeline():
    st.title("Decision Intelligence Hub")
    st.markdown("Analyse your investment decision and simulate its long-term financial impact in one click.")

    # ── Indices & Market Context ──────────────────────────────────────────
    _render_indices_ribbon()
    st.subheader("Live Market Context")
    _render_market_banner()
    
    st.divider()
    st.subheader("Step 1: Identify Investor")
    
    col_id, _ = st.columns([1, 2])
    with col_id:
        uid_input = st.text_input("Enter your User ID (e.g., 42):", value=st.session_state.get("user_id", ""), key="unified_uid_input")
        if st.button("Load Profile", type="primary", use_container_width=True):
            st.session_state["user_id"] = uid_input
            st.rerun()
            
    uid = st.session_state.get("user_id", "")
    profile = None
    if uid:
        profile_data = _api_get(f"/user/{uid}/profile")
        if profile_data:
            profile = profile_data.get("profile", {})
            st.success(f"Successfully loaded profile for {profile.get('name', 'User')}!")
            
    if not profile:
        st.info("Please enter a valid User ID (try 42) to continue with the end-to-end pipeline.")
        return
        
    st.divider()
    st.subheader("Step 2: Intelligent Intake")

    with st.form("unified_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Trade Parameters**")
            unrealized_gl = st.number_input("Unrealized Gain/Loss (%)", -100.0, 200.0, -5.0, 1.0) / 100.0
            holding_months = st.number_input("Holding Period (months)", 1, 360, 6)
            position_pct = st.number_input("Position Size (% of portfolio)", 0.1, 100.0, 10.0, 1.0) / 100.0
            decision_intent = st.selectbox("Decision Intent", ["Thinking of selling", "Planning to hold"])
            current_wealth = st.number_input(
                "Current Portfolio Value (₹)",
                min_value=1000.0, max_value=50000000.0,
                value=75000.0, step=5000.0
            )

        with col2:
            st.markdown("**Demographics & Profile**")
            st.info("Profile locked from session.")
            age = profile.get("age", 35)
            horizon = profile.get("investment_horizon", 10)
            risk_tolerance = profile.get("risk_tolerance", 0.5)
            monthly_income = profile.get("monthly_income", 60000)
            emg_fund_val = profile.get("has_emergency_fund", 1)
            emg_fund = emg_fund_val == 1
            
            # Render as disabled
            st.number_input("Your Age", value=age, disabled=True)
            st.number_input("Investment Horizon (years)", value=horizon, disabled=True)
            st.number_input("Risk Tolerance", value=float(risk_tolerance), disabled=True)
            st.number_input("Monthly Income (₹)", value=float(monthly_income), disabled=True)

        n_sims = st.select_slider("Monte Carlo Paths", options=[100, 500, 1000, 2000, 5000], value=1000)
        submitted = st.form_submit_button("Analyse & Simulate (End-to-End)", use_container_width=True)

    if submitted:
        payload1: dict[str, Any] = {
            "unrealized_gl": float(unrealized_gl),
            "holding_period_months": int(holding_months),
            "position_size_pct": float(position_pct),
            "age": int(age),
            "investment_horizon": int(horizon),
            "risk_tolerance": float(risk_tolerance),
            "has_emergency_fund": int(emg_fund),
            "monthly_income": float(monthly_income),
            "portfolio_value": float(current_wealth),
        }
        if uid: payload1["user_id"] = uid

        payload2 = {
            "current_wealth": float(current_wealth),
            "unrealized_gl": float(unrealized_gl),
            "n_simulations": int(n_sims),
        }
        if uid: 
            try:
                payload2["user_id"] = int(uid)
            except ValueError:
                pass  # Fallback gracefully if not castable

        # Execute Obj 1
        with st.spinner("Objective 1: Analysing with XGBoost & Causal Graph..."):
            result1 = _api_post("/analyze/decision", payload1)
        
        if result1 is None: return

        # Execute Obj 2
        with st.spinner(f"Objective 2: Running {n_sims} Monte Carlo paths for trajectory..."):
            result2 = _api_post("/simulate", payload2)
            
        if result2 is None: return

        st.session_state["hub_result"] = {
            "result1": result1,
            "result2": result2,
            "user_input": {
                "unrealized_gl"     : float(unrealized_gl),
                "crowd_ratio"       : (result1.get("market_auto_fetched", {}) or {}).get("crowd_ratio", 0.5),
                "has_emergency_fund": int(emg_fund),
                "decision_intent"   : decision_intent,
                "investment_horizon": int(horizon),
            },
        }

    # ── Results ──────────────────────────────────────────────────────────
    # Rendered from session state rather than straight after the API calls,
    # so switching language or downloading a report re-renders instantly
    # instead of re-running the model and the simulation.
    hub = st.session_state.get("hub_result")
    if not hub:
        return

    result1, result2 = hub["result1"], hub["result2"]

    st.success("Analysis complete")
    st.divider()

    explanation = _build_explanation(result1, result2, hub["user_input"])

    if explanation is None:
        # Explainer unavailable — fall back to the technical view rather than
        # showing the user nothing.
        st.warning("Plain-language explanation unavailable — showing model output.")
        _render_technical_details(result1, result2)
        return

    _render_narrative(explanation, result2)
    _render_download_row(explanation)

    st.divider()
    _render_technical_details(result1, result2)


def page_decision_analysis():
    st.title("Decision Analysis")
    st.markdown("Analyse your investment decision for hidden behavioural biases.")

    # ── Indices ribbon ───────────────────────────────────────────────────
    _render_indices_ribbon()

    # Market banner
    st.subheader("Live Market Context")
    _render_market_banner()

    st.divider()
    st.subheader("Decision Input")

    # FORM
    with st.form("decision_form"):
        col1, col2 = st.columns(2)
        with col1:
            unrealized_gl = st.number_input(
                "Unrealized Gain/Loss (%)", -100.0, 200.0, -5.0, 1.0,
                help="Negative = loss, Positive = gain"
            ) / 100.0
            holding_months = st.number_input("Holding Period (months)", 1, 360, 6)
            position_pct   = st.number_input(
                "Position Size (% of portfolio)", 0.1, 100.0, 10.0, 1.0
            ) / 100.0
            decision_intent = st.selectbox(
                "Decision Intent", ["Thinking of selling", "Planning to hold"]
            )
        with col2:
            age            = st.number_input("Your Age", 18, 80, 35)
            horizon        = st.number_input("Investment Horizon (years)", 1, 50, 10)
            risk_tolerance = st.slider("Risk Tolerance", 0.0, 1.0, 0.5, 0.05)
            emg_fund       = st.selectbox("Emergency Fund?", ["Yes", "No"]) == "Yes"
            monthly_income = st.number_input("Monthly Income (₹)", 10000, 5000000, 60000, step=5000)

        submitted = st.form_submit_button("Analyse Decision", use_container_width=True)

    if submitted:
        uid = st.session_state.get("user_id") or None
        payload: dict[str, Any] = {
            "unrealized_gl"       : float(unrealized_gl),
            "holding_period_months": int(holding_months),
            "position_size_pct"   : float(position_pct),
            "age"                 : int(age),
            "investment_horizon"  : int(horizon),
            "risk_tolerance"      : float(risk_tolerance),
            "has_emergency_fund"  : int(emg_fund),
            "monthly_income"      : float(monthly_income),
        }
        if uid:
            payload["user_id"] = uid

        with st.spinner("Analysing with XGBoost + SHAP + Causal Graph…"):
            result = _api_post("/analyze/decision", payload)

        if result is None:
            return

        # ── Bias Alert Banner ────────────────────────────────────────────
        bias_type  = result.get("bias_type", "unknown")
        confidence = result.get("confidence", 0) * 100
        is_biased  = result.get("is_biased", False)

        if is_biased:
            banner_class = "bias-biased"
            icon  = ""
            label = bias_type.replace("_", "").title()
            msg   = f"{icon} BIAS DETECTED: {label} ({confidence:.1f}% confidence)"
        else:
            banner_class = "bias-rational"
            icon  = ""
            msg   = f"{icon} RATIONAL DECISION ({confidence:.1f}% confidence)"

        st.markdown(
            f'<div class="bias-banner {banner_class}">{msg}</div>',
            unsafe_allow_html=True,
        )

        # ── GAP 3: plain-language summary ────────────────────────────────
        # This page has no simulation behind it, so only the sections that
        # describe the person and the bias are rendered — no money figures we
        # haven't actually computed.
        if _EXPLAINER_OK:
            try:
                plain = explain_bias_only(
                    result,
                    {
                        "unrealized_gl"     : float(unrealized_gl),
                        "crowd_ratio"       : (result.get("market_auto_fetched", {}) or {}).get("crowd_ratio", 0.5),
                        "has_emergency_fund": int(emg_fund),
                        "decision_intent"   : decision_intent,
                        "investment_horizon": int(horizon),
                    },
                    _lang(),
                )
                sections = {sec["key"]: sec for sec in plain["sections"]}
                calm = (not plain.get("is_biased")) or plain.get("resisted")
                st.markdown(
                    f"<div class='narrative-headline {'narr-ok' if calm else 'narr-warn'}'>"
                    f"{sections['headline']['text']}</div>",
                    unsafe_allow_html=True,
                )
                for key in ("whats_happening", "why_we_say_this"):
                    if key in sections:
                        st.subheader(sections[key]["title"])
                        st.markdown(sections[key]["text"])
                st.caption(
                    "For the full picture — what each choice is worth over your whole "
                    "horizon — run this decision through the Decision Intelligence Hub."
                    if _lang() == "en" else
                    "पूरी तस्वीर के लिए — हर विकल्प आपकी पूरी अवधि में कितना देता है — "
                    "यह फ़ैसला Decision Intelligence Hub से चलाइए।"
                )
                st.divider()
            except Exception as exc:                   # noqa: BLE001
                st.caption(f"Plain-language summary unavailable: {exc}")

        # ── Metrics row ──────────────────────────────────────────────────
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Bias Type",    bias_type.replace("_", "").title())
        mc2.metric("Confidence",   f"{confidence:.1f}%")
        mc3.metric("Risk Score",   f"{result.get('risk_score', 0)*100:.1f}%")

        st.divider()

        # ── SHAP Chart ───────────────────────────────────────────────────
        st.subheader("🔬 SHAP Feature Contributions")
        shap_data = result.get("shap_explanation", [])
        _render_shap_chart(shap_data)

        # ── Causal Chain ─────────────────────────────────────────────────
        causal_chain = result.get("causal_chain", [])
        if causal_chain:
            st.subheader("Causal Chain")
            with st.container():
                for i, step in enumerate(causal_chain, 1):
                    st.markdown(f"**Step {i}:** {step}")

        # ── Intervention Suggestion ──────────────────────────────────────
        intervention = result.get("intervention", "")
        if intervention:
            st.subheader("💡 Intervention Suggestion")
            st.info(intervention)

        # ── Explanation ──────────────────────────────────────────────────
        explanation = result.get("explanation", "")
        if explanation:
            st.subheader("📖 Explanation")
            st.markdown(explanation)

        # ── Audit Hash ───────────────────────────────────────────────────
        audit_hash  = result.get("audit_hash", "N/A")
        decision_id = result.get("decision_id", "N/A")
        st.subheader("🔒 Audit Trail")
        c1, c2 = st.columns([1, 3])
        c1.markdown("**Decision ID:**")
        c2.code(decision_id, language=None)
        c1.markdown("**Audit Hash:**")
        c2.markdown(f'<div class="audit-hash">{audit_hash}</div>', unsafe_allow_html=True)
        if decision_id != "N/A":
            st.caption(f"Verify at `GET /audit/{decision_id}`")


# ══════════════════════════════════════════════════════════════════════════
# PAGE 2 — USER PROFILE
# ══════════════════════════════════════════════════════════════════════════

def page_user_profile():
    st.title("User Profile")
    _render_indices_ribbon()

    uid = st.session_state.get("user_id", "")
    if not uid:
        st.warning("Please enter your User ID in the sidebar or register a new account.")
        return

    # Fetch profile
    profile_data = _api_get(f"/user/{uid}/profile")
    if profile_data is None:
        return

    profile      = profile_data.get("profile", {})
    bias_profile = profile_data.get("bias_profile", {})

    # Profile card
    st.subheader("Profile Details")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown(f"**Name:** {profile.get('name', 'N/A')}")
        st.markdown(f"**Age:** {profile.get('age', 'N/A')}")
        st.markdown(f"**Monthly Income:** ₹{profile.get('monthly_income', 0):,.0f}")
    with pc2:
        st.markdown(f"**Risk Tolerance:** {profile.get('risk_tolerance', 0):.2f}")
        st.markdown(f"**Investment Horizon:** {profile.get('investment_horizon', 0)} years")
        emg = "Yes"if profile.get("has_emergency_fund") else "No"
        st.markdown(f"**Emergency Fund:** {emg}")

    st.divider()

    # Bias profile evolution bar chart
    st.subheader("Bias Profile (Running Average)")
    if bias_profile:
        n    = int(bias_profile.get("total_decisions", 0))
        st.caption(f"Based on {n} decision(s)")
        scores = {
            "Disposition"   : float(bias_profile.get("disposition_score", 0)),
            "Herd"          : float(bias_profile.get("herd_score", 0)),
            "Loss Aversion" : float(bias_profile.get("loss_aversion_score", 0)),
            "Rational"      : float(bias_profile.get("rational_score", 0)),
        }
        try:
            import plotly.graph_objects as go
            colors = ["#6C63FF", "#FFB347", "#FF6B6B", "#00C9A7"]
            fig = go.Figure(go.Bar(
                x=list(scores.keys()),
                y=list(scores.values()),
                marker_color=colors,
                text=[f"{v:.2f}"for v in scores.values()],
                textposition="outside",
            ))
            fig.update_layout(
                title="Bias Score Distribution",
                yaxis_title="Average Score (0–1)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E0E0E0"),
                yaxis=dict(range=[0, 1.05]),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            for k, v in scores.items():
                st.metric(k, f"{v:.3f}")

    st.divider()

    # Decision history table
    st.subheader("📋 Decision History")
    decisions_data = _api_get(f"/user/{uid}/decisions")
    if decisions_data is None:
        return

    decisions = decisions_data.get("decisions", [])
    if decisions:
        import pandas as pd
        df = pd.DataFrame(decisions)
        # Select display columns
        display_cols = [c for c in ["timestamp", "bias_detected", "confidence", "risk_score", "recommendation", "decision_id"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No decisions recorded yet. Go to Decision Analysis to submit a decision.")


# ══════════════════════════════════════════════════════════════════════════
# PAGE 3 — MARKET CONTEXT
# ══════════════════════════════════════════════════════════════════════════

def page_market_context():
    st.title("Market Context")
    st.markdown("Live NIFTY50 data fetched from yfinance with 15-minute TTL cache.")
    _render_indices_ribbon()

    ctx = _api_get("/market/context")
    if ctx is None:
        return

    ret   = ctx.get("market_return", 0)
    vol   = ctx.get("market_volatility", 0)
    crowd = ctx.get("crowd_ratio", 0.5)
    source = ctx.get("data_source", "unknown")

    # Regime indicator
    regime_label, regime_color = _market_regime(ret, vol)
    st.markdown(
        f'<div style="text-align:center; font-size:2.2rem; font-weight:800; '
        f'padding:1.2rem; border-radius:12px; background: rgba(30,33,48,0.8); '
        f'border: 2px solid {regime_color}; color: {regime_color}; margin-bottom:1rem;">'
        f'{regime_label}</div>',
        unsafe_allow_html=True,
    )

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("NIFTY 1M Return",   f"{ret*100:.3f}%")
    m2.metric("30-Day Volatility", f"{vol*100:.3f}%")
    m3.metric("😱 Crowd Fear Ratio",  f"{crowd:.3f}",
              help="0 = calm, 1 = panic selling")
    m4.metric("Market Hours",
              "Open"if ctx.get("market_hours") else "Closed")

    st.divider()

    # Detail card
    st.subheader("Data Details")
    col1, col2 = st.columns(2)
    col1.markdown(f"**Data Source:** `{source}`")
    col1.markdown(f"**Last Updated:** {ctx.get('last_updated', 'N/A')[:19]} UTC")
    col2.markdown(f"**NSE Hours:** 09:15 – 15:30 IST")
    col2.markdown(f"**Cache TTL:** 15 minutes")

    st.info(
        "💡 **How crowd_ratio is computed:** India VIX is normalised to [0, 1] where "
        "VIX=10 → 0.20 and VIX=50 → 1.0. When VIX data is unavailable, a proxy based "
        "on 30-day daily return volatility is used."
    )

    # Regime guide
    st.subheader("📖 Market Regime Guide")
    guide = [
        ("CRASH / HIGH VOL", "Return < -10% or vol > 3%", "Extreme fear, high risk"),
        ("🟠 BEAR",             "Return -3% to -10%",         "Negative sentiment, caution"),
        ("🟡 NEUTRAL",          "Return -3% to +3%",          "Balanced market"),
        ("BULL",             "Return +3% to +10%",         "Positive momentum"),
        ("RALLY / EUPHORIA", "Return > +10%",              "Euphoric, watch for reversals"),
    ]
    import pandas as pd
    st.dataframe(
        pd.DataFrame(guide, columns=["Regime", "Condition", "Investor Implication"]),
        use_container_width=True, hide_index=True,
    )

    # Auto refresh
    if st.button("Refresh Market Data"):
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# PAGE 4 — WEALTH SIMULATOR (GAP 2)
# ══════════════════════════════════════════════════════════════════════════

def _render_trajectory_chart(result: dict):
    """
    Render HOLD vs SELL year-by-year trajectory chart using Plotly.
    Includes P10/P90 uncertainty bands, median lines, starting wealth baseline.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("plotly not installed — run: pip install plotly")
        return

    years         = result.get("years", [])
    hold_p50      = result.get("yearly_hold_p50", [])
    hold_p10      = result.get("yearly_hold_p10", [])
    hold_p90      = result.get("yearly_hold_p90", [])
    sell_p50      = result.get("yearly_sell_p50", [])
    sell_p10      = result.get("yearly_sell_p10", [])
    sell_p90      = result.get("yearly_sell_p90", [])
    current_wealth = result.get("inputs", {}).get("current_wealth", 100_000.0)

    if not years or not hold_p50:
        st.warning("Trajectory data not returned by the API.")
        return

    fig = go.Figure()

    # ── HOLD uncertainty band (P10–P90) ─────────────────────────────
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=hold_p90 + hold_p10[::-1],
        fill="toself",
        fillcolor="rgba(108,99,255,0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
        name="HOLD P10–P90",
    ))
    # ── SELL uncertainty band ───────────────────────────────────
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=sell_p90 + sell_p10[::-1],
        fill="toself",
        fillcolor="rgba(255,107,107,0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
        name="SELL P10–P90",
    ))
    # ── HOLD median trajectory ──────────────────────────────────
    fig.add_trace(go.Scatter(
        x=years, y=hold_p50,
        mode="lines",
        name="HOLD (median)",
        line=dict(color="#6C63FF", width=3),
        hovertemplate="Year %{x}<br>₹%{y:,.0f}<extra>HOLD median</extra>",
    ))
    # ── SELL median trajectory ──────────────────────────────────
    fig.add_trace(go.Scatter(
        x=years, y=sell_p50,
        mode="lines",
        name="SELL (median)",
        line=dict(color="#FF6B6B", width=3, dash="dash"),
        hovertemplate="Year %{x}<br>₹%{y:,.0f}<extra>SELL median</extra>",
    ))
    # ── Starting wealth baseline ───────────────────────────────
    fig.add_hline(
        y=current_wealth,
        line_dash="dot",
        line_color="#888",
        annotation_text=f"Starting ₹{current_wealth:,.0f}",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title=dict(
            text="HOLD vs SELL — Long-Horizon Wealth Projection",
            font=dict(size=17, color="#E0E0E0")
        ),
        xaxis=dict(
            title="Year",
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            color="#aaa", tickmode="linear", dtick=5,
        ),
        yaxis=dict(
            title="Portfolio Value (₹)",
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            color="#aaa", tickformat=",.0f",
        ),
        plot_bgcolor ="rgba(14,17,23,0)",
        paper_bgcolor="rgba(14,17,23,0)",
        font=dict(color="#E0E0E0", family="Inter, sans-serif"),
        legend=dict(
            bgcolor="rgba(30,33,48,0.85)",
            bordercolor="#444", borderwidth=1
        ),
        hovermode="x unified",
        height=450,
        margin=dict(l=60, r=30, t=60, b=50),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_distribution_chart(result: dict):
    """Render final wealth distribution histogram comparing HOLD vs SELL."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    hold = result.get("hold", {})
    sell = result.get("sell", {})

    # If raw outcomes not available (stripped by API), use summary stats to simulate
    hold_outcomes = hold.get("outcomes", [])
    sell_outcomes = sell.get("outcomes", [])

    if not hold_outcomes or not sell_outcomes:
        # Fallback: show box chart from summary stats
        fig = go.Figure()
        for label, data, color in [
            ("HOLD", hold, "#6C63FF"),
            ("SELL", sell, "#FF6B6B"),
        ]:
            fig.add_trace(go.Box(
                q1=[data.get("p25", 0)],
                median=[data.get("median", 0)],
                q3=[data.get("p75", 0)],
                lowerfence=[data.get("p10", 0)],
                upperfence=[data.get("p90", 0)],
                mean=[data.get("mean", 0)],
                name=label,
                marker_color=color,
                boxmean=True,
            ))
        fig.update_layout(
            title="Final Wealth Distribution (Summary Statistics)",
            yaxis_title="Final Wealth (₹)",
            yaxis=dict(tickformat=",.0f"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0"),
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    import numpy as np
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=hold_outcomes, name="HOLD",
        marker_color="rgba(108,99,255,0.75)",
        nbinsx=40, opacity=0.8,
    ))
    fig.add_trace(go.Histogram(
        x=sell_outcomes, name="SELL",
        marker_color="rgba(255,107,107,0.75)",
        nbinsx=40, opacity=0.8,
    ))
    fig.update_layout(
        barmode="overlay",
        title="Final Wealth Distribution Across 1 000 Scenarios",
        xaxis=dict(title="Final Wealth (₹)", tickformat=",.0f"),
        yaxis_title="Count",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        height=350,
        legend=dict(bgcolor="rgba(30,33,48,0.85)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def page_wealth_simulator():
    """GAP 2 — Personalised Long-Horizon Wealth Simulator."""
    st.title("Wealth Simulator")
    st.markdown(
        "**GAP 2**: Simulate your personal 10–30 year wealth trajectory under HOLD vs SELL — "
        "powered by Monte Carlo over 1 000 possible market futures."
    )
    _render_indices_ribbon()

    # ── INFO BANNER ────────────────────────────────────────────────────
    with st.expander("ℹ How the simulator works", expanded=False):
        st.markdown("""
        **Monte Carlo Simulation (1 000 paths, 10–30 years)**

        | Scenario | Logic |
        |--|--|
        | **HOLD** | Stay invested at current position. Compound returns over horizon using risk-adjusted portfolio (stocks + bonds). |
        | **SELL** | Realise P&L minus 5% transaction cost. Reinvest at 30% of original stock allocation (panic-selling → conservative reallocation). |

        **Output:** Year-by-year median trajectories + P10/P90 uncertainty bands for each scenario.
        The **Opportunity Cost** = expected HOLD wealth − expected SELL wealth.

        Data: `synthetic_market_paths.npy` (10 000 × 30yr annual return paths for Indian equity markets)
        """)

    st.divider()
    st.subheader("Simulation Parameters")

    # ── INPUT FORM ────────────────────────────────────────────────────
    with st.form("simulator_form"):
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.number_input(
                "User ID (from synthetic_users.csv)",
                min_value=0, max_value=99_999, value=42, step=1,
                help="User profile determines investment horizon, risk tolerance, age."
            )
            current_wealth = st.number_input(
                "Current Portfolio Value (₹)",
                min_value=1_000.0, max_value=50_000_000.0,
                value=75_000.0, step=5_000.0,
                format="%.0f"
            )
            unrealized_gl = st.number_input(
                "Unrealised Gain / Loss (%)",
                min_value=-70.0, max_value=200.0,
                value=-18.0, step=1.0,
                help="Negative = loss position. E.g. -18 means down 18%."
            ) / 100.0
        with col2:
            n_simulations = st.select_slider(
                "Monte Carlo Paths",
                options=[100, 200, 500, 1000, 2000, 5000],
                value=1000,
                help="More paths = more accurate but slower. 1 000 is recommended."
            )
            st.markdown("")
            st.markdown("")
            st.info(
                f"💡 **Ramesh Scenario**: User 42, ₹75 000, −18%, 1000 paths\n\n"
                "This mirrors the master blueprint demo from the project overview."
            )

        run_sim = st.form_submit_button(
            "Run Monte Carlo Simulation",
            use_container_width=True,
            type="primary"
        )

    # ── EXECUTE AND RENDER ─────────────────────────────────────────────
    if run_sim:
        with st.spinner(f"Running {n_simulations:,} Monte Carlo paths per scenario…"):
            payload = {
                "user_id"      : int(user_id),
                "current_wealth": float(current_wealth),
                "unrealized_gl": float(unrealized_gl),
                "n_simulations": int(n_simulations),
            }
            result = _api_post("/simulate", payload)

        if result is None:
            return

        # Store in session state so user can explore without re-running
        st.session_state["sim_result"] = result

    # Render from session state
    if "sim_result"not in st.session_state:
        st.info("↗ Fill in your parameters above and click Run to see your personalised wealth projection.")
        return

    result = st.session_state["sim_result"]
    hold   = result.get("hold", {})
    sell   = result.get("sell", {})
    comp   = result.get("comparison", {})
    user   = result.get("user_profile", {})
    inputs = result.get("inputs", {})
    horizon = result.get("horizon_years", 20)

    # ── USER PROFILE BANNER ────────────────────────────────────────────
    st.divider()
    st.subheader("Investor Profile Used")
    up1, up2, up3, up4 = st.columns(4)
    up1.metric("🏦 Age",              user.get("age", "N/A"))
    up2.metric("Investment Horizon", f"{user.get('investment_horizon', horizon)} yrs")
    up3.metric("⚖ Risk Tolerance",    f"{user.get('risk_tolerance', 0):.2f}")
    up4.metric("Goal",             user.get("goal", "N/A").replace("_", "").title())

    # ── KEY METRICS ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Simulation Results")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "HOLD — Expected",
        f"₹{hold.get('mean', 0):,.0f}",
        delta=f"P10: ₹{hold.get('p10', 0):,.0f} | P90: ₹{hold.get('p90', 0):,.0f}",
        delta_color="normal",
    )
    c2.metric(
        "SELL — Expected",
        f"₹{sell.get('mean', 0):,.0f}",
        delta=f"P10: ₹{sell.get('p10', 0):,.0f} | P90: ₹{sell.get('p90', 0):,.0f}",
        delta_color="normal",
    )
    opp_cost = comp.get("opportunity_cost_inr", 0)
    c3.metric(
        "Opportunity Cost of Selling",
        f"₹{abs(opp_cost):,.0f}",
        delta=f"{comp.get('opportunity_cost_pct', 0):.1f}% of portfolio",
        delta_color="inverse",  # red = bad (you lose money by selling)
    )
    prob = comp.get("prob_hold_better", 0)
    c4.metric(
        "P(HOLD wins)",
        f"{prob*100:.1f}%",
        delta="across 1k simulations",
        delta_color="off",
    )

    # ── RECOMMENDATION BANNER ─────────────────────────────────────────
    better = comp.get("better_decision", "HOLD")
    rec_text = comp.get("recommendation_text", "")
    if better == "HOLD":
        st.markdown(
            f'<div class="bias-banner bias-rational"> {rec_text}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="bias-banner bias-biased"> {rec_text}</div>',
            unsafe_allow_html=True,
        )

    # ── TRAJECTORY CHART ──────────────────────────────────────────────
    st.divider()
    st.subheader("Year-by-Year Wealth Trajectory")
    st.caption(
        "Shaded bands = P10–P90 range (most likely outcomes). "
        f"Solid lines = median. {n_simulations if 'n_simulations'not in result.get('inputs', {}) else result['inputs'].get('n_simulations', 1000):,} Monte Carlo paths per scenario."
    )
    _render_trajectory_chart(result)

    # ── DETAILED STATS TABLE ────────────────────────────────────────────
    st.divider()
    st.subheader("Detailed Statistics")
    tab1, tab2, tab3 = st.tabs(["HOLD vs SELL Summary", "Year-by-Year Table", "Validation"])

    with tab1:
        import pandas as pd
        stat_keys = ["mean", "median", "std", "p10", "p25", "p50", "p75", "p90"]
        hold_stats = {k: hold.get(k, 0) for k in stat_keys}
        sell_stats = {k: sell.get(k, 0) for k in stat_keys}
        stats_df = pd.DataFrame({
            "Statistic": [k.upper() for k in stat_keys],
            "HOLD (₹)": [f"₹{hold_stats[k]:,.0f}"for k in stat_keys],
            "SELL (₹)": [f"₹{sell_stats[k]:,.0f}"for k in stat_keys],
            "Difference": [f"₹{hold_stats[k] - sell_stats[k]:+,.0f}"for k in stat_keys],
        })
        st.dataframe(stats_df, use_container_width=True, hide_index=True)

    with tab2:
        years       = result.get("years", list(range(1, horizon + 1)))
        hold_p50    = result.get("yearly_hold_p50", [])
        sell_p50    = result.get("yearly_sell_p50", [])
        hold_p10    = result.get("yearly_hold_p10", [])
        hold_p90    = result.get("yearly_hold_p90", [])
        if years and hold_p50:
            import pandas as pd
            traj_data = {
                "Year"         : years,
                "HOLD Median (₹)": [f"₹{v:,.0f}"for v in hold_p50],
                "HOLD P10 (₹)" : [f"₹{v:,.0f}"for v in hold_p10] if hold_p10 else ["-"] * len(years),
                "HOLD P90 (₹)" : [f"₹{v:,.0f}"for v in hold_p90] if hold_p90 else ["-"] * len(years),
                "SELL Median (₹)": [f"₹{v:,.0f}"for v in sell_p50] if sell_p50 else ["-"] * len(years),
            }
            st.dataframe(pd.DataFrame(traj_data), use_container_width=True, hide_index=True)
        else:
            st.info("Trajectory data not available.")

    with tab3:
        st.markdown("**Validate against synthetic_counterfactuals.csv**")
        dec_id_val = st.number_input("Decision ID to validate", min_value=0, value=0, step=1)
        if st.button("Validate"):
            val = _api_get(f"/simulate/validate/{dec_id_val}")
            if val:
                if "error"in val:
                    st.error(val["error"])
                else:
                    v1, v2, v3 = st.columns(3)
                    v1.metric("HOLD Error",
                              f"{val['hold_error_pct']:.2f}%",
                              delta="PASS"if val["pass_hold"] else "FAIL",
                              delta_color="normal"if val["pass_hold"] else "inverse")
                    v2.metric("SELL Error",
                              f"{val['sell_error_pct']:.2f}%",
                              delta="PASS"if val["pass_sell"] else "FAIL",
                              delta_color="normal"if val["pass_sell"] else "inverse")
                    v3.metric("Overall",
                              "PASS"if val["pass_overall"] else "FAIL",
                              delta="< 20% error target",
                              delta_color="off")
                    with st.expander("Raw validation data"):
                        st.json(val)

    # ── POPULATION BIAS IMPACT ─────────────────────────────────────────
    st.divider()
    st.subheader("Population-Level Bias Cost (Research Experiment 2)")
    st.markdown(
        "**Experiment 2 target:** quantify the average wealth lost to behavioral biases "
        "across the population. Expected result: **~42% wealth gap** (biased vs rational investors)."
    )
    col_n, col_pf, _ = st.columns([1, 1, 2])
    n_users_pop = col_n.number_input("Sample users", min_value=10, max_value=500, value=50, step=10)
    pf_val      = col_pf.number_input("Portfolio size (₹)", min_value=10_000, value=75_000, step=5_000)

    if st.button("Run Population Analysis"):
        with st.spinner(f"Analysing {n_users_pop} users… (this may take ~30s)"):
            impact = _api_get(f"/simulate/bias_impact?n_users={n_users_pop}&assumed_portfolio={pf_val}")
        if impact:
            bi1, bi2, bi3 = st.columns(3)
            bi1.metric("Mean Bias Cost", f"₹{impact.get('mean_bias_cost_inr', 0):,.0f}")
            bi2.metric("Median Bias Cost", f"₹{impact.get('median_bias_cost_inr', 0):,.0f}")
            bi3.metric("Avg Wealth Loss %", f"{impact.get('mean_wealth_loss_pct', 0):.1f}%")
            st.success(impact.get("key_finding", ""))
            with st.expander("Full result"):
                st.json({k: v for k, v in impact.items() if k != "distribution"})


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    page = _render_sidebar()

    if page == "Decision Intelligence Hub":
        page_unified_pipeline()
    elif page == "Decision Analysis":
        page_decision_analysis()
    elif page == "User Profile":
        page_user_profile()
    elif page == "Market Context":
        page_market_context()
    elif page == "Wealth Simulator":
        page_wealth_simulator()


if __name__ == "__main__":
    main()
