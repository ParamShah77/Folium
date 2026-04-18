# 🔬 Is GAP 1 Fully Complete? — Deep Analysis

---

## ✅ What GAP 1 Was Supposed to Deliver (Per Requirements)

From [GAP1_Causal_Decision_Time_Reasoning.md](file:///c:/Users/Lenovo/Desktop/Major%20Project/GAP1_Causal_Decision_Time_Reasoning.md) and [PROJECT_SPECIFICATION.md](file:///c:/Users/Lenovo/Desktop/Major%20Project/PROJECT_SPECIFICATION.md):

| Requirement | Description |
|-------------|-------------|
| **R1** | Real-time bias detection at decision moment (NOT hindsight) |
| **R2** | 4-class classifier: `disposition`, `loss_aversion`, `herd`, `rational` |
| **R3** | Confidence score per prediction |
| **R4** | Causal structure learning (NOTEARS) to find WHY biases occur |
| **R5** | Causal effect estimation (quantify how much each bias drives sell decisions) |
| **R6** | Intervention simulation ("what if we remove the bias?") |
| **R7** | Plain-English causal explanation chain |
| **R8** | Integration layer combining bias + causal into unified real-time API |
| **R9** | FastAPI REST endpoints for consumption by frontend/other systems |
| **R10** | Unit tests for bias detection and causal inference |

---

## 📊 Current Status — Requirement by Requirement

| Req | What's Built | Status | Notes |
|-----|-------------|--------|-------|
| R1 | [detect_bias_realtime()](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/bias_detector.py#236-405) in [bias_detector.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/bias_detector.py) | ✅ **Done** | 44-feature real-time vector, <100ms |
| R2 | XGBoost 4-class classifier | ✅ **Done** | **89% accuracy** (target was ≥85%) |
| R3 | `confidence` score in output dict | ✅ **Done** | Also returns all class probabilities |
| R4 | [causal_structure.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/causal_structure.py) — NOTEARS via CausalNex | ✅ **Done** | Saves [models/causal_graph.pkl](file:///c:/Users/Lenovo/Desktop/Major%20Project/models/causal_graph.pkl) |
| R5 | [causal_inference.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/causal_inference.py) — partial-corr OLS, 6 treatments | ✅ **Done** | Refutation tests also included |
| R6 | [simulate_intervention()](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/causal_inference.py#223-270) — 4 interventions | ✅ **Done** | `remove_loss_aversion`, `hide_crowd_signal`, etc. |
| R7 | [_build_explanation()](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/bias_detector.py#407-429), [_build_causal_chain()](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/integration.py#100-139) | ✅ **Done** | Human-readable text per bias type |
| R8 | [integration.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/integration.py) — [analyze_decision_realtime()](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/integration.py#144-235) | ✅ **Done** | Full pipeline, risk score, causal chain |
| R9 | [api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py) — 7 FastAPI endpoints | ✅ **Done** | `/analyze/decision`, `/demo/all_biases`, etc. |
| R10 | [tests/test_bias_detector.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/tests/test_bias_detector.py), [tests/test_causal_inference.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/tests/test_causal_inference.py) | ✅ **Done** | Unit tests present |

> **Overall GAP 1 Core Requirements: ✅ 10/10 Delivered**

---

## ⚠️ BUT — What Is MISSING or INCOMPLETE?

Despite the core requirements being met, there are **significant gaps** between what's built and what the full system requires according to [SYSTEM_ARCHITECTURE.md](file:///c:/Users/Lenovo/Desktop/Major%20Project/SYSTEM_ARCHITECTURE.md) and [PROJECT_SPECIFICATION.md](file:///c:/Users/Lenovo/Desktop/Major%20Project/PROJECT_SPECIFICATION.md).

### ❌ Missing 1: Real-Time Market Data Integration

**What's required (per SYSTEM_ARCHITECTURE.md §7):**
```
- NSE India API / Yahoo Finance (yfinance)
- Fetches: NIFTY50 recent return, current volatility (VIX or rolling std)
- Fetches: Crowd action ratio (put/call ratio, news sentiment via FinBERT)
- Market data cache (15-min TTL)
```

**What's built:**
- The API expects `market_return`, `crowd_ratio`, `market_volatility` as manual inputs
- **No actual market data fetching** — user must supply these manually
- No `yfinance` or NSE API calls anywhere in `src/`
- No crowd action ratio computation (no FinBERT sentiment)

**Impact:** High. Without this, the "real-time" claim is not real — someone must manually look up NIFTY data and type it in. The detection is NOT automated.

---

### ❌ Missing 2: Live Database (SQLite/PostgreSQL)

**What's required (per SYSTEM_ARCHITECTURE.md §4):**
```sql
Tables needed:
- user_profiles       (persistent user data, replaces synthetic_users)
- decisions_live      (stores every decision made by real users)
- audit_logs          (append-only, stores SHA-256 hashes)
- market_data_cache   (15-min TTL cache)
- bias_profiles_live  (updated after each decision via running average)
- portfolios          (user holdings — stock, quantity, buy price)
```

**What's built:**
- No database — all data lives in static CSV files
- No user registration or persistence
- No running bias profile update per user (bias is stateless per call)
- No actual audit log table — [synthetic_audit_logs.csv](file:///c:/Users/Lenovo/Desktop/Major%20Project/synthetic_audit_logs.csv) is a static demo file

**Impact:** Critical. Without a DB, the system cannot serve real users persistently.

---

### ❌ Missing 3: User Registration & Onboarding Flow

**What's required (per SYSTEM_ARCHITECTURE.md §2 & §5):**
```
- POST /user/register endpoint
- 5-question behavioral bias onboarding quiz 
- Initial bias profile stored with 'low' confidence
- Profile updates after every real decision (running average)
- Cold-start handling for new users
```

**What's built:**
- [api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py) has no `/user/register` endpoint
- No onboarding quiz
- No running bias profile evolution per user
- Every API call is stateless (no memory of past decisions)

**Impact:** High. The system cannot build personalized profiles over time.

---

### ❌ Missing 4: Portfolio Tracking

**What's required (per SYSTEM_ARCHITECTURE.md §8):**
```
- User enters: stock symbol, quantity, buy price, buy date
- System fetches live price from NSE
- Calculates: unrealized_gl_pct, holding_period_months, position_size_pct
- Dashboard shows portfolio with live P&L
```

**What's built:**
- Users manually input `unrealized_gl`, `position_size_pct`, `holding_period_months`
- No portfolio tracking — no ability to add/track actual stock holdings
- No live price fetching via NSE/Yahoo Finance

**Impact:** Medium for research, High for production. Without this, the system can't work without users doing their own math.

---

### ❌ Missing 5: Streamlit Frontend Dashboard

**What's required (per PROJECT_SPECIFICATION.md and SYSTEM_ARCHITECTURE.md §12):**
```
Frontend renders:
- Bias alert banner (red if biased, green if rational)
- Dual wealth trajectory charts with uncertainty bands  ← needs Gap 2 data
- Opportunity cost card
- Plain-English recommendation
- "How we decided this?" causal chain section
- Audit trail viewer (with hash verification)
```

**What's built:**
- FastAPI backend with Swagger UI at `/docs`
- **No Streamlit or React frontend**
- No charts or visualizations served to an actual user interface

**Impact:** High for demonstration/project presentation. The system has no face.

---

### ⚠️ Incomplete 6: Causal Inference Method is Simplified

**What was planned (per GAP1_Causal_Decision_Time_Reasoning.md):**
```python
# Propensity Score Matching via DoWhy
model = dowhy.CausalModel(data=df, treatment='loss_aversion', outcome='decision', graph=...)
effect = model.estimate_effect(method_name="backdoor.propensity_score_matching")
```

**What's actually implemented (in [causal_inference.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/causal_inference.py)):**
```python
# Partial Correlation (OLS Residualization)
effect_val = float(np.corrcoef(t_res, o_res)[0, 1])  # Line 101
method = "Partial correlation (OLS residualization)"
```

**Why this happened:** DoWhy's `propensity_score_matching` was replaced with partial correlation because the DoWhy API had convergence issues. This is documented inline in the code as a pragmatic fallback.

**Impact on research validity:** Moderate. Partial correlation is confounder-adjusted and produces causal-flavored estimates, but is technically a weaker claim than true do-calculus propensity matching. For the research paper, this needs to be addressed or properly justified. The refutation test included is also a simplified bootstrap shuffle, not DoWhy's formal refutation framework.

---

### ⚠️ Incomplete 7: `herd` Class Severely Underrepresented

**From [api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py) docs:**
> `herd` is a **rare class: only 14 training samples** in the herd class

**Issue:** In [synthetic_decisions.csv](file:///c:/Users/Lenovo/Desktop/Major%20Project/synthetic_decisions.csv), the herd bias label is generated only when `herd_sensitivity > 0.7 AND crowd_action_ratio > 0.7`. With `herd_sensitivity ~ Beta(2,4)` (mean=0.33) and uniform `crowd_ratio`, very few samples satisfy both conditions simultaneously.

**Impact:** Class imbalance — the XGBoost model may have poor recall for herd bias in edge cases. The dataset documentation ([DATASET_IMPROVEMENTS.md](file:///c:/Users/Lenovo/Desktop/Major%20Project/DATASET_IMPROVEMENTS.md)) acknowledges this but it may or may not have been fixed.

---

### ❌ Missing 8: SHAP Explainability Layer

**What's required (per PROJECT_SPECIFICATION.md and SYSTEM_ARCHITECTURE.md §10):**
```
"How we decided this?" section shows SHAP feature attribution (on-demand)
```

**What's built:**
- [bias_detector.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/bias_detector.py) generates `feature_importance.png` from XGBoost gain
- No SHAP values computed at inference time
- No per-prediction SHAP explanation returned by the API

**Impact:** Medium. SHAP was listed as the explainability layer in the spec but is missing from the real-time pipeline.

---

## ✅ Summary: GAP 1 Completeness Score

| Category | Score | Notes |
|----------|-------|-------|
| Core ML (Bias Detection) | ✅ 100% | XGBoost trained, saved, real-time ready |
| Core Causal Engine | ✅ 90% | NOTEARS + OLS (not full propensity matching) |
| Intervention Simulation | ✅ 100% | 4 interventions, quantified |
| API Endpoints | ✅ 95% | 7 endpoints, well-documented |
| Tests | ✅ 80% | 2 test files present |
| Real-Time Market Data | ❌ 0% | Not implemented |
| Database / Persistence | ❌ 0% | Not implemented |
| User Registration + Quiz | ❌ 0% | Not implemented |
| Portfolio Tracking | ❌ 0% | Not implemented |
| Frontend (Streamlit) | ❌ 0% | Not implemented |
| SHAP per-prediction | ❌ 0% | Not implemented |

**Research/Academic GAP 1: ~85% complete**  
**Production-Ready System GAP 1: ~35% complete**

---

## 🔗 How GAP 1 Connects to GAP 2 (and Beyond)

The entire system is one pipeline. GAP 1 feeds directly into GAP 2, GAP 3, and GAP 4. Here is the exact data handoff:

```
┌──────────────────────────────────────────────────────────────┐
│                      GAP 1 OUTPUT                            │
│                                                              │
│  {                                                           │
│    "bias_type": "loss_aversion",      ─────────────────────┐ │
│    "confidence": 0.87,                                     │ │
│    "risk_score": 0.45,                                     │ │
│    "causal_chain": [                                       │ │
│       "loss_aversion=3.2 → +0.312 causal effect"          │ │
│    ],                                                      │ │
│    "intervention": "Reframe losses (cognitive therapy)"  ──┤ │
│  }                                                         │ │
└────────────────────────────────────────────────────────────┼─┘
                                                            │
                  ┌─────────────────────────────────────────┼──┐
                  │              GAP 2 INPUT                │  │
                  │                                         ▼  │
                  │  The detected bias_type tells the        │  │
                  │  Long-Horizon Simulator WHICH scenario   │  │
                  │  to favor:                               │  │
                  │                                         │  │
                  │  • bias_detected=True → simulate both   │  │
                  │    HOLD and SELL and show the cost       │  │
                  │    of the biased choice                  │  │
                  │                                         │  │
                  │  • user profile (age, risk_tolerance,   │  │
                  │    investment_horizon) from the same     │  │
                  │    decision_context  → personalizes      │  │
                  │    asset allocation for simulation       │  │
                  │                                         │  │
                  │  • causal "rational action" output       │  │
                  │    from GAP 1 → used as the "corrected   │  │
                  │    decision" that GAP 2 simulates        │  │
                  └─────────────────────────────────────────┘
```

### The Full Connected Pipeline (9 Steps)

```
Step 1:  [INPUT] User submits decision + profile
Step 2:  [MARKET] Real-time NSE/Yahoo data fetched (crowd_ratio, market_return, volatility)
Step 3:  [CONTEXT] User profile + market data merged = Decision Context
                           │
                    ┌──── GAP 1 ────┐
Step 4:  [BIASES]   Bias Detector (XGBoost) → bias_type, confidence
Step 5:  [CAUSAL]   Causal Engine → which driver caused bias + intervention
                    └───────────────┘
                           │
                    ┌──── GAP 2 ────┐
Step 6:  [SIMULATE] Long-Horizon Simulator (Monte Carlo)
                    → wealth_if_HOLD (median/p10/p90)
                    → wealth_if_SELL (median/p10/p90)
                    → opportunity_cost
                    └───────────────┘
                           │
                    ┌──── GAP 3 ────┐
Step 7:  [EXPLAIN]  Explainability Engine
                    → Counterfactual narrative text
                    → SHAP attribution (why the model predicted this)
                    → Causal path trace (loss_aversion → sell → wealth loss)
                    └───────────────┘
                           │
                    ┌──── GAP 4 ────┐
Step 8:  [AUDIT]    Audit Logger
                    → SHA-256 hash of inputs + outputs + explanation
                    → Stored in append-only DB table
                    └───────────────┘
Step 9:  [OUTPUT]   JSON → Frontend renders bias alert + charts + recommendation
```

---

## 🔌 Exact Data Flow: GAP 1 → GAP 2

### What GAP 1 passes to GAP 2:

```python
gap1_output = {
    "bias_type": "loss_aversion",        # → GAP 2 uses this to label the "biased" scenario
    "confidence": 0.87,                  # → GAP 2 weights probability of bias being real
    "causal_effects": {
        "loss_aversion": {
            "causal_effect": +0.312      # → Used to compute "how much did bias inflate sell urge?"
        }
    },
    "intervention": "remove_loss_aversion"  # → GAP 2 simulates the "rational alternative"
}

# + decision_context (already in memory) which contains:
decision_context = {
    "age": 35,
    "risk_tolerance": 0.4,
    "investment_horizon": 25,            # → GAP 2: how many years to simulate
    "monthly_income": 60000,
    "has_emergency_fund": True,          # → GAP 2: affects if SELL is defensible
    "unrealized_gain_loss": -0.18,       # → GAP 2: starting position for both scenarios
    "market_return": -0.12,              # → GAP 2: current market context
}
```

### What GAP 2 uses from GAP 1:

| GAP 1 Output | How GAP 2 Uses It |
|---|---|
| `bias_type` | Labels one scenario as "biased choice", other as "rational choice" |
| `confidence` | Filters: only run full simulation if confidence > threshold (e.g., 60%) |
| [intervention](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py#264-274) (rational action) | The "rational" scenario that GAP 2 simulates (e.g., HOLD instead of SELL) |
| [causal_effect](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py#252-262) of bias | Used to quantify "bias-driven portion" of wealth loss in explanation |
| `unrealized_gl`, `age`, `horizon` | Personalize the Monte Carlo simulation parameters |

---

## 🔌 GAP 2 → GAP 3 → GAP 4 (Brief)

### GAP 2 → GAP 3 (Explainability)

GAP 2 produces the wealth numbers. GAP 3 wraps them in human language:

```python
gap2_output = {
    "wealth_if_hold": {"median": 67583, "p10": 31000, "p90": 140000},
    "wealth_if_sell": {"median": 38291, "p10": 19000, "p90": 75000},
    "opportunity_cost": 29292,
    "horizon_years": 20
}

# GAP 3 turns this into:
explanation = (
    "⚠️ Loss Aversion detected (87% confidence). "
    "If you HOLD: expected ₹67,583 in 20 years (range ₹31,000–₹1,40,000). "
    "If you SELL: expected ₹38,291 — 43% less. "
    "Your causal analysis shows 68% of your sell urge is bias-driven. "
    "RECOMMENDATION: HOLD. Your profile supports this (25-year horizon, stable income)."
)
```

### GAP 3 → GAP 4 (Audit)

GAP 4 receives the complete package (input + bias + simulation + explanation) and hashes everything:

```python
audit_entry = {
    "input_hash":       SHA256(market_return + unrealized_gl + crowd_ratio + user_id),
    "decision_hash":    SHA256(bias_type + confidence + recommendation),
    "explanation_hash": SHA256(explanation_text + wealth_hold + wealth_sell),
    "timestamp":        "2026-03-23T11:47:16+05:30",
    "bias_detected":    True
}
# Stored append-only in audit_logs DB table — can never be modified
```

---

## 🛠️ What Needs to Be Done to Complete GAP 1 (Priority Order)

### 🔴 High Priority (Needed for Demo/Presentation)

| Task | File to Create/Edit | Effort |
|------|---------------------|--------|
| **Build Streamlit frontend** | `src/dashboard.py` (new) | ~3-4 days |
| **Add `/user/register` endpoint + DB** | [src/api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py) + `src/database.py` (new) | ~2-3 days |
| **Add real market data fetcher** | `src/market_data.py` (new) using `yfinance` | ~1 day |
| **Fix herd class imbalance** | [synthetic_user.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/synthetic_user.py) + re-run generation | ~4-6 hours |

### 🟡 Medium Priority (Needed for Research Quality)

| Task | File | Effort |
|------|------|--------|
| **Add SHAP per-prediction to API** | [src/api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py), [src/bias_detector.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/bias_detector.py) | ~4-6 hours |
| **Upgrade causal estimation to propensity score matching** | [src/causal_inference.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/causal_inference.py) | ~1-2 days |
| **Add user bias profile evolution** | `src/database.py` (running average update) | ~1 day |
| **Expand unit tests** | [tests/test_bias_detector.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/tests/test_bias_detector.py) | ~4-6 hours |

### 🟢 Lower Priority (Production Completeness)

| Task | File | Effort |
|------|------|--------|
| Portfolio tracking endpoints | [src/api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py) + `src/portfolio.py` (new) | ~2 days |
| Onboarding behavioral quiz | [src/api.py](file:///c:/Users/Lenovo/Desktop/Major%20Project/src/api.py) + frontend | ~1-2 days |
| Rate-limited market data cache | `src/market_data.py` | ~4-6 hours |

---

## 📋 GAP 2 Specification (What Needs to Be Built Next)

### Gap 2 needs a `simulator.py` file in `src/` with:

```python
class LongHorizonSimulator:
    """
    Takes: user_id, initial_wealth, decision (HOLD or SELL), bias_context (from GAP 1)
    Returns: wealth distributions for both scenarios + opportunity cost
    
    Uses: synthetic_market_paths.npy (already exists ✅)
          synthetic_users.csv (already exists ✅)
          synthetic_counterfactuals.csv (for validation ✅)
    """
    
    def simulate_individual(user_id, initial_wealth, n_simulations=1000) → dict
    def compare_hold_vs_sell(user_id, current_wealth, unrealized_gl) → dict
    def plot_trajectories(hold_outcomes, sell_outcomes) → matplotlib figure
    def validate_against_precomputed(decision_id) → accuracy_metrics
```

### What GAP 2 already has that can be used:
- ✅ [synthetic_market_paths.npy](file:///c:/Users/Lenovo/Desktop/Major%20Project/synthetic_market_paths.npy) — 10,000 paths × 30 years (already at project root)
- ✅ [synthetic_users.csv](file:///c:/Users/Lenovo/Desktop/Major%20Project/synthetic_users.csv) — user profiles for personalization
- ✅ [synthetic_counterfactuals.csv](file:///c:/Users/Lenovo/Desktop/Major%20Project/synthetic_counterfactuals.csv) — pre-computed HOLD/SELL outcomes for validation
- ❌ `src/simulator.py` — **does NOT exist yet**, needs to be created

### Exact spec from [GAP2_Individual_Portfolio_Long_Horizon.md](file:///c:/Users/Lenovo/Desktop/Major%20Project/GAP2_Individual_Portfolio_Long_Horizon.md):

```python
# CORE LOGIC GAP 2 MUST IMPLEMENT:

# HOLD scenario:
starting_wealth = current_wealth * (1 + unrealized_gl)
final_hold = starting_wealth * product(1 + portfolio_returns for each year)

# SELL scenario (with costs):
realized_wealth = current_wealth * (1 + unrealized_gl * 0.95)  # 5% transaction cost
# Reinvest at lower stock allocation (panic-sold, moved to bonds)
final_sell = realized_wealth * product(1 + conservative_returns for each year)

# Opportunity cost:
opportunity_cost = mean(hold_outcomes) - mean(sell_outcomes)
prob_hold_better = (hold_outcomes > sell_outcomes).mean()
```

---

## 📊 Quick Reference: GAP Status

| GAP | What It Does | Code Status | Missing |
|-----|-------------|-------------|---------|
| **GAP 1** | Real-time bias detection + causal engine | ✅ Core done | DB, market feed, frontend, SHAP |
| **GAP 2** | 10–30 year Monte Carlo simulation | ❌ `simulator.py` missing | Entire simulator module |
| **GAP 3** | Counterfactual explanations | ❌ `explainer.py` missing | Entire explainer module |
| **GAP 4** | Verifiable audit trail | ⚠️ Hash logic exists in synthetic data | No real append-only DB table |

---

## 🚀 Recommended Next Steps (In Order)

```
1. ✅ Complete GAP 1 (Streamlit dashboard + market data feed + fix herd class)
         ↓ feeds into ↓
2. Build GAP 2 simulator.py (LongHorizonSimulator class)
         ↓ feeds into ↓
3. Build GAP 3 explainer.py (counterfactual narrative + SHAP attribution)
         ↓ feeds into ↓
4. Build GAP 4 audit DB (SQLite append-only audit_logs table + /audit endpoints)
         ↓
5. Wire everything together into full Streamlit dashboard
         ↓
6. Validate end-to-end with real test scenarios
```
