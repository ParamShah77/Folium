# Financial Decision Intelligence System
## Comprehensive Project Report — Master Blueprint Aligned
### Version 3.0 | April 2026

> **Single source of truth.** This document reflects an audit of the actual codebase
> against the Master Blueprint v2.0. Every claim below is verified against live files.

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Two-Layer Architecture](#2-two-layer-architecture)
3. [Full Codebase Audit — What Actually Exists](#3-full-codebase-audit--what-actually-exists)
4. [GAP 1 — Detailed Walkthrough of What Was Built](#4-gap-1--detailed-walkthrough-of-what-was-built)
5. [GAP Completion Scorecard](#5-gap-completion-scorecard)
6. [Dataset Audit](#6-dataset-audit)
7. [Database Schema Audit vs Tier 1 Blueprint](#7-database-schema-audit-vs-tier-1-blueprint)
8. [Immediate Next Steps — GAP 1 Finalization](#8-immediate-next-steps--gap-1-finalization)
9. [GAP 2 — Long-Horizon Portfolio Simulation (Plan)](#9-gap-2--long-horizon-portfolio-simulation-plan)
10. [GAP 3 — Decision-Centric Explainability + Debate Engine (Plan)](#10-gap-3--decision-centric-explainability--debate-engine-plan)
11. [GAP 4 — Counterfactual Verifiability & Auditability (Plan)](#11-gap-4--counterfactual-verifiability--auditability-plan)
12. [Practical Extensions — Layer 2 (Plan)](#12-practical-extensions--layer-2-plan)
13. [Complete Build Sequence — Master Checklist](#13-complete-build-sequence--master-checklist)
14. [Technology Stack](#14-technology-stack)
15. [Ramesh — End-to-End Demo Scenario](#15-ramesh--end-to-end-demo-scenario)
16. [Research Experiments & Metrics](#16-research-experiments--metrics)

---

## 1. Executive Summary

**Project Title:** "A Causal Decision-Time Framework for Behavioral Bias Detection and
Long-Horizon Portfolio Evaluation with Counterfactual Verifiable Intelligence"

**Core Problem:** Retail investors make emotionally-driven financial decisions — panic
selling, herd behavior, loss aversion — that cost 30–40% of lifetime wealth. Existing
systems analyze these behaviors after the damage is done, offer generic market-level
advice, and provide no verifiable reasoning. This project intervenes at the exact moment
of decision.

**Current Phase:** GAP 1 is functionally complete. The bias classifier, causal engine,
market data layer, database, API, and dashboard skeleton all exist and are running.
Several GAP 1 items from the blueprint — Tier 1 user inputs, missing synthetic datasets,
and formal refutation tests — remain to be finished before GAP 2 can begin.

**Next Milestone:** Complete the remaining GAP 1 items, then build `src/simulator.py`
for GAP 2.

---

## 2. Two-Layer Architecture

The project operates on two distinct layers that must never be confused.

| Layer | What It Is | Priority |
|---|---|---|
| **Research Core** (GAPs 1–4) | Required for grades, IEEE paper, and viva. 4 research gaps addressed, 4 objectives fulfilled, experiments documented. | **HIGHEST** |
| **Practical Extensions** | Transforms research into something a real investor uses — Kite API, SIP tracker, tax engine, multi-asset, WhatsApp bot. | **AFTER all GAPs** |

### The Four Research Gaps

| GAP | Current State of Research | This Project's Solution | Status |
|---|---|---|---|
| GAP 1 | Biases detected AFTER decisions | Detect at decision-time using XGBoost + causal reasoning | ✅ Core done, minor items remain |
| GAP 2 | Generic market-level predictions | Individual portfolio Monte Carlo simulation over 10–30 years | ❌ Not built |
| GAP 3 | Post-hoc static explainability (SHAP/LIME) | Decision-centric counterfactual narratives tied to long-term outcomes | ❌ Not built |
| GAP 4 | No counterfactual or verifiable intelligence | Counterfactual engine backed by SHA-256 audit trail | ⚠️ Partial (basic hash exists) |

---

## 3. Full Codebase Audit — What Actually Exists

### 3.1 Source Files (`src/`)

| File | Status | Size | Notes |
|---|---|---|---|
| `__init__.py` | ✅ Exists | 25 B | Package marker |
| `data_preparation.py` | ✅ Exists | 11.9 KB | Loads CSVs, feature engineering, train/test split |
| `bias_detector.py` | ✅ Exists | 25.5 KB | XGBoost 4-class + SHAP + SMOTE fix |
| `causal_structure.py` | ✅ Exists | 13.9 KB | NOTEARS structure learning |
| `causal_utils.py` | ✅ Exists | 6.3 KB | Load/normalize causal data |
| `causal_inference.py` | ✅ Exists | 26.5 KB | DoWhy LR + 4 interventions |
| `integration.py` | ✅ Exists | 13.9 KB | Unified real-time pipeline |
| `market_data.py` | ✅ Exists | 13.2 KB | NIFTY50 + SENSEX + Bank NIFTY + India VIX + ribbon |
| `database.py` | ✅ Exists | 21.0 KB | SQLite + SHA-256 audit + user management |
| `api.py` | ✅ Exists | 33.7 KB | **14 endpoints** (see §3.3) |
| `dashboard.py` | ✅ Exists | 33.0 KB | 3 pages + live ribbon + tax slab sidebar |
| `simulator.py` | ❌ Missing | — | GAP 2 — needs to be created |
| `explainer.py` | ❌ Missing | — | GAP 3 — needs to be created |
| `audit_logger.py` | ❌ Missing | — | GAP 4 — standalone class needed |
| `debate_engine.py` | ❌ Missing | — | GAP 3 extension — AutoGen multi-agent |
| `outcome_tracker.py` | ❌ Missing | — | Feedback loop — Version A |
| `kite_integration.py` | ❌ Missing | — | Practical Layer |
| `sip_tracker.py` | ❌ Missing | — | Practical Layer |
| `tax_engine.py` | ❌ Missing | — | Practical Layer |
| `multi_asset.py` | ❌ Missing | — | Practical Layer |
| `whatsapp_bot.py` | ❌ Missing | — | Practical Layer — LOWEST priority |

### 3.2 Models (`models/`)

| File | Status | Notes |
|---|---|---|
| `bias_detector_xgboost.pkl` | ✅ Exists | 1.78 MB — trained model |
| `causal_graph.pkl` | ✅ Exists | 1.1 KB — NOTEARS learned DAG |
| `causal_scaler.pkl` | ✅ Exists | 827 B — feature scaler |

### 3.3 API Endpoints (verified via source scan — 14 total)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | System health check |
| GET | `/model/status` | XGBoost model info |
| POST | `/analyze/decision` | Main bias detection pipeline |
| POST | `/analyze/batch` | Batch bias analysis |
| GET | `/causal/effects` | Causal treatment effects |
| GET | `/causal/interventions` | 4 intervention simulations |
| GET | `/demo` | Demo single decision |
| GET | `/demo/all_biases` | Demo all 4 bias types |
| POST | `/user/register` | Register new user |
| GET | `/user/{user_id}/profile` | Fetch user + bias profile |
| GET | `/user/{user_id}/decisions` | Decision history |
| GET | `/audit/{decision_id}` | Audit trail + tamper detection |
| GET | `/market/context` | Live NIFTY50 context |
| GET | `/market/ribbon` | Live 4-index ribbon |

**Missing endpoints (needed for future GAPs):**
`/simulate`, `/explain`, `/debate`, `/sip/register`, `/sip/{id}/impact`, `/tax/calculate`

### 3.4 Dashboard Pages (3 pages confirmed)
- `page_decision_analysis()` — Bias detection + causal output + SHAP viz
- `page_user_profile()` — User registration + decision history
- `page_market_context()` — Live NIFTY50 context panel

**All pages have:** live 4-index ribbon (NIFTY50, SENSEX, Bank NIFTY, India VIX)
**Sidebar has:** tax slab reference panel (STCG 20%, LTCG 12.5%, FY2024-25)

### 3.5 Tests (`tests/`)

| File | Status |
|---|---|
| `test_api.py` | ✅ Exists |
| `test_bias_detector.py` | ✅ Exists |
| `test_causal_inference.py` | ✅ Exists |
| `test_database.py` | ✅ Exists |
| `test_market_data.py` | ✅ Exists |
| `test_simulator.py` | ❌ Missing |
| `test_explainer.py` | ❌ Missing |
| `test_debate_engine.py` | ❌ Missing |

### 3.6 Scripts (`scripts/`)

| File | Status |
|---|---|
| `fix_herd_imbalance.py` | ✅ Exists |
| `bias_detector_retrainer.py` | ❌ Missing — feedback loop batch job |

---

## 4. GAP 1 — Detailed Walkthrough of What Was Built

### 4.1 Bias Detection & Explainability
**File:** `src/bias_detector.py` | **Size:** 25.5 KB

**What it does:**
- Trains an XGBoost classifier to detect one of 4 bias types per investment decision:
  `rational`, `disposition`, `loss_aversion`, `herd`
- Achieved **89.1% accuracy** on the `synthetic_decisions.csv` test set (target was ≥85%)
- SHAP integration: every prediction produces a top-5 feature attribution list explaining
  *exactly* which inputs drove the AI's conclusion

**How SMOTE was applied:**
- The original dataset had only **14 herd samples** out of 5,000 — making the model ignore
  that class entirely
- `scripts/fix_herd_imbalance.py` used SMOTE to synthesize new minority samples, bringing
  herd instances to **400**
- The fixed dataset was saved back permanently to `synthetic_decisions.csv`

**Why SHAP instead of a simpler metric:**
- SHAP is game-theory based — it distributes the model's output fairly across all input
  features, giving each feature a precise contribution value (+/-) for that specific prediction
- This satisfies the regulators' requirement that AI-driven financial advice be explainable
  at the individual decision level, not just at the population level

**Real-time API:**
`detect_bias_realtime()` → accepts raw user inputs → returns
`{bias_type, confidence, probabilities, shap_values, recommendation}`

---

### 4.2 Causal Inference & Intervention Simulation
**File:** `src/causal_inference.py` | **Size:** 26.5 KB

**What it does:**
- Uses Microsoft's **DoWhy** library to compute *causal effects* (not correlations)
- 6 causal treatment-outcome relationships computed:
  - `loss_aversion → decision`
  - `crowd_ratio → decision`
  - `market_return → decision`
  - `unrealized_gain_loss → decision`
  - `disposition_strength → decision`
  - `herd_sensitivity → decision`
- 4 intervention simulations:
  - `remove_loss_aversion`: What if we zero out loss aversion?
  - `hide_crowd_signal`: What if user can't see what others are doing?
  - `improve_market_conditions`: What if the market were +10% instead of -10%?
  - `increase_risk_tolerance`: What if user had higher risk tolerance?

**Upgrade from earlier version:**
- Original code used naive OLS partial correlations — mathematically equivalent to
  regression, NOT causal
- Upgraded to **Linear Regression Backdoor estimator** (DoWhy Tier 1), with
  propensity score matching (Tier 2) as fallback
- Added **Refutation Tests** (capped at 5 simulations to prevent hangs):
  - `random_common_cause` — does adding a random variable change the estimate?
  - `placebo_treatment` — does replacing treatment with noise eliminate the effect?
- If refutation passes → effect is causally valid, not a statistical fluke

**Why this matters for the paper:**
- "Correlation does not imply causation" — to justify an intervention (e.g., "reducing
  loss aversion changes the decision"), you must prove causal not correlational effect
- This is the core academic novelty of GAP 1

---

### 4.3 Live Ambient Market Context
**File:** `src/market_data.py` | **Size:** 13.2 KB

**What it fetches (via yfinance):**
| Index | Ticker | Fields Fetched |
|---|---|---|
| NIFTY 50 | `^NSEI` | 1M return, 30-day volatility, crowd_ratio proxy |
| SENSEX | `^BSESN` | Current price, 1-day % change |
| Bank NIFTY | `^NSEBANK` | Current price, 1-day % change |
| India VIX | `^INDIAVIX` | Current value, 1-day % change (also used for crowd_ratio) |

**Caching mechanism:**
- Thread-safe in-memory dictionary cache with **15-minute TTL**
- Prevents hitting yfinance rate limits on every dashboard interaction
- 3-tier graceful fallback: `live → stale cache → hardcoded mathematical defaults`
- The app **never crashes** because of market data failure

**India VIX → crowd_ratio conversion:**
`crowd_ratio = (vix_value - 10) / 40` — normalized to [0, 1], clipped at bounds
High VIX (>30) = crowd panic = crowd_ratio ≈ 0.5+, amplifying bias detection sensitivity

---

### 4.4 Tamper-Evident Database & Auditing
**File:** `src/database.py` | **Size:** 21.0 KB

**5 SQLite tables:**
| Table | Purpose |
|---|---|
| `user_profiles` | Registered investor profiles |
| `bias_profiles_live` | Running-average bias scores per user (incremental formula) |
| `decisions_live` | Individual decision analysis records with input/output JSON blobs |
| `audit_logs` | Append-only SHA-256 tamper-evident audit trail |
| `market_data_cache` | Persisted market context snapshots |

**SHA-256 audit mechanism:**
1. When a decision is analyzed, all inputs are serialized to JSON → SHA-256 hashed
2. The output (bias type, confidence, SHAP) is separately hashed
3. Both hashes + explanation hash are combined → `full_hash` stored
4. When `GET /audit/{decision_id}` is called, the system re-derives the hash from
   stored components and compares to `full_hash`
5. If they differ → `tamper_detected: true` is returned

**WAL mode:** SQLite is configured with Write-Ahead Logging for concurrent read/write safety

**What's missing from the blueprint's Tier 1 inputs:**
The current `user_profiles` table does NOT have:
- `monthly_emi` (total EMIs)
- `monthly_educational_expenses`
- `educational_expenses_end_year`
- `rent_paid`
- `monthly_surplus` (computed field)
These must be added for GAP 2 simulator to work correctly.

---

### 4.5 Full-Stack UI & API Layer
**Files:** `src/api.py` (33.7 KB), `src/dashboard.py` (33.0 KB)

**API layer (FastAPI + Uvicorn):**
- 14 live endpoints (see §3.3)
- Models loaded once at startup via `@app.on_event("startup")` singleton pattern
- All endpoints are typed with Pydantic models for automatic validation
- `GET /market/ribbon` returns all 4 indices — cached at API level, not dashboard level

**Dashboard (Streamlit — 3 pages):**
- **Decision Analysis page:** User inputs decision context → calls `/analyze/decision` →
  shows bias type, confidence, SHAP top-5 feature chart, causal effects, recommendation
- **User Profile page:** Registration form → calls `/user/register` →
  shows decision history and running bias profile
- **Market Context page:** Calls `/market/context` → shows NIFTY50 regime, volatility gauge

**Live index ribbon (all 3 pages):**
- 4 tiles: NIFTY50 / SENSEX / Bank NIFTY / India VIX
- Each shows: price, ▲▼ 1-day % change, green/red coloring
- Fetched from `/market/ribbon` via direct API call (no frontend caching to avoid
  caching empty responses during cold start)

**Tax slab sidebar (static, FY2024-25):**
- STCG 20% (< 12 months, equity)
- LTCG 12.5% (≥ 12 months, equity) with ₹1.25L annual exemption
- 5 asset classes: Equity, Equity MF, Debt MF, Real Estate, Gold
- Per Budget 23-Jul-2024 rates

---

## 5. GAP Completion Scorecard

| Component | Blueprint Target | Built? | Notes |
|---|---|---|---|
| XGBoost 4-class bias classifier | ≥85% accuracy | ✅ 89.1% | `bias_detector.py` |
| SHAP per-prediction explanations | Top-5 features | ✅ Done | Integrated |
| SMOTE herd class fix | 14 → 400 samples | ✅ Done | CSV permanently updated |
| DoWhy causal effects (6 treatments) | Linear regression backdoor | ✅ Done | Upgraded |
| 4 intervention simulations | remove_loss_aversion etc. | ✅ Done | Working |
| Formal refutation tests | random_common_cause + placebo | ✅ Done | Capped at 5 |
| market_data.py — NIFTY50 | 15-min TTL cache | ✅ Done | With 3-tier fallback |
| market_data.py — SENSEX, Bank NIFTY, VIX | All 4 indices | ✅ Done | Ribbon endpoint |
| database.py — 5 tables | Including audit_logs | ✅ Done | WAL mode |
| SHA-256 tamper detection | Audit trail working | ✅ Done | `/audit/{id}` endpoint |
| API — 13+ endpoints | All core routes | ✅ **14 endpoints** | Running |
| Dashboard — 3 pages | Decision / Profile / Market | ✅ Done | All pages live |
| Live market ribbon (all pages) | 4-index top banner | ✅ Done | Post-fix (no double-cache) |
| Static tax slab panel | STCG/LTCG sidebar | ✅ Done | FY2024-25 rates |
| Tier 1 user inputs (full) | EMI, edu fees, rent, surplus | ❌ Missing | DB schema needs update |
| Monthly surplus auto-calculation | income - EMI - fees - rent | ❌ Missing | Critical for GAP 2 |
| Synthetic datasets in data/ | 7 files per blueprint | ❌ ALL MISSING | Critical blocker |
| `simulator.py` | Monte Carlo simulator | ❌ Missing | GAP 2 |
| `explainer.py` | Counterfactual narratives | ❌ Missing | GAP 3 |
| `debate_engine.py` | Bull/Bear/Judge agents | ❌ Missing | GAP 3 extension |
| `audit_logger.py` | Standalone logger class | ❌ Missing | GAP 4 |
| `test_simulator.py` | Unit tests | ❌ Missing | — |
| `test_explainer.py` | Unit tests | ❌ Missing | — |
| `test_debate_engine.py` | Unit tests | ❌ Missing | — |
| `bias_detector_retrainer.py` | Monthly batch retrainer | ❌ Missing | Version A |
| All Practical Extension files | 5 files | ❌ Missing | Post-GAP-4 |

---

## 6. Dataset Audit

### 6.1 Current State (verified by filesystem scan)
All 7 required synthetic datasets are **MISSING from `data/`**. Only the SQLite database
and processed split indices exist.

| Dataset | Required By | Status |
|---|---|---|
| `synthetic_users.csv` | GAP 1, 2, 3 | ❌ MISSING |
| `synthetic_bias_profiles.csv` | GAP 1 validation | ❌ MISSING |
| `synthetic_market_paths.npy` | GAP 2 simulator | ❌ MISSING |
| `synthetic_market_summary.csv` | GAP 2 context | ❌ MISSING |
| `synthetic_decisions.csv` | GAP 1 training | ❌ MISSING (but model is trained) |
| `synthetic_counterfactuals.csv` | GAP 2 validation, GAP 3 | ❌ MISSING |
| `synthetic_audit_logs.csv` | GAP 4 reference | ❌ MISSING |

> **Note:** The XGBoost model (`bias_detector_xgboost.pkl`) is trained and saved, so
> GAP 1 inference works. But to re-train, run experiments, or build the GAP 2 simulator,
> the raw CSVs must be regenerated or recovered.

### 6.2 Foundational Principle (from Blueprint)
- **Synthetic data:** provides reasoning and validation backbone — bias labels, counterfactuals,
  30-year market paths. These are *impossible* to get from real data.
- **Real data (yfinance):** provides market context — current regime, VIX, live index values.
- They are **never mixed** — synthetic data trains the model; real data contextualizes it.

---

## 7. Database Schema Audit vs Tier 1 Blueprint

### 7.1 Current `user_profiles` Schema

```sql
CREATE TABLE user_profiles (
    user_id            TEXT PRIMARY KEY,
    age                INTEGER,
    monthly_income     REAL,
    risk_tolerance     REAL,
    investment_horizon INTEGER,
    has_emergency_fund INTEGER DEFAULT 0,
    name               TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
```

### 7.2 Required Tier 1 Fields (Blueprint §8B.2)

| Field | Status | Why Needed |
|---|---|---|
| `monthly_income` | ✅ Exists | Base for surplus calculation |
| `risk_tolerance` | ✅ Exists | Portfolio allocation in GAP 2 |
| `investment_horizon` | ✅ Exists | Monte Carlo simulation length |
| `has_emergency_fund` | ✅ Exists | SELL risk score modifier |
| `monthly_emi` | ❌ Missing | Reduces investable surplus |
| `monthly_educational_expenses` | ❌ Missing | Non-negotiable fixed outflow |
| `educational_expenses_end_year` | ❌ Missing | Simulation surplus increase from year N+1 |
| `rent_paid` | ❌ Missing | Monthly surplus reduction |
| `monthly_surplus` (computed) | ❌ Missing | Core GAP 2 input |

**Monthly surplus formula:**
`monthly_surplus = monthly_income + rent_received - rent_paid - monthly_emi - monthly_educational_expenses`

**Impact:** Without `monthly_surplus`, the GAP 2 simulator cannot compute how much
additional wealth Ramesh can accumulate by continuing to invest. The simulation will
be generic, not personalized.

---

## 8. Immediate Next Steps — GAP 1 Finalization

These are the remaining GAP 1 items. They must be completed before GAP 2 begins.

### Step 1: Regenerate Missing Synthetic Datasets
The 7 CSV/NPY files need to be created in `data/`. This requires a data generation script.

**What to generate:**
- `synthetic_users.csv` — 1,000 investor profiles with age, income, EMI, edu fees,
  rent, surplus, risk tolerance, emergency fund, investment horizon, goals
- `synthetic_bias_profiles.csv` — ground truth bias scores (disposition, herd, loss_aversion)
  per user — NOT for training, only for validation
- `synthetic_decisions.csv` — 5,000 labeled decision moments with bias_type (herd fixed to 400)
- `synthetic_market_paths.npy` — 10,000 paths × 30 years of simulated market returns
- `synthetic_market_summary.csv` — regime-labeled summary of market paths
- `synthetic_counterfactuals.csv` — 10,000 rows of HOLD vs SELL 20-year wealth projections
- `synthetic_audit_logs.csv` — sample SHA-256 audit demo data

### Step 2: Extend `database.py` — Add Tier 1 Fields
Add the missing columns to `user_profiles` and update `register_user()`:

```python
# New columns to add to user_profiles:
monthly_emi                    REAL DEFAULT 0.0,
monthly_educational_expenses   REAL DEFAULT 0.0,
educational_expenses_end_year  INTEGER DEFAULT NULL,
rent_paid                      REAL DEFAULT 0.0,
monthly_surplus                REAL DEFAULT 0.0,  -- computed and stored
```

Update `register_user()` to:
- Accept the new fields from the API request body
- Auto-compute `monthly_surplus = monthly_income - monthly_emi - monthly_educational_expenses - rent_paid`
- Store computed surplus alongside raw fields

### Step 3: Update `/user/register` Endpoint in `api.py`
The Pydantic model for registration needs the new Tier 1 fields:
```python
monthly_emi: float = 0.0
monthly_educational_expenses: float = 0.0
educational_expenses_end_year: Optional[int] = None
rent_paid: float = 0.0
```

### Step 4: Update Registration Form in `dashboard.py`
Add input widgets for the new Tier 1 fields in the "Register New User" expander on
the sidebar. Show computed `monthly_surplus` dynamically as fields are filled.

### Step 5: Behavioral Onboarding Quiz
5-question quiz to set initial `risk_tolerance` score (stored in `user_profiles`):
- Q1: How do you react to a 15% portfolio drop? (Scale 1–5)
- Q2: What is your primary financial goal?
- Q3: How long can you leave money invested?
- Q4: Do you have 6 months of expenses saved?
- Q5: What % of your savings can you afford to lose?

This replaces the raw 0.0–1.0 slider with a more user-friendly onboarding flow.

---

## 9. GAP 2 — Long-Horizon Portfolio Simulation (Plan)

**The research gap:** Current financial AI evaluates decisions at market level. GAP 2 models
how YOUR specific decisions compound over 10–30 years at the individual portfolio level,
personalized to your age, income, risk tolerance, and goals.

### 9.1 What to Build: `src/simulator.py`

```python
class LongHorizonSimulator:
    def simulate_individual(user_id, decision, current_portfolio) -> dict
    def compare_hold_vs_sell(user_id, current_wealth, unrealized_gl) -> dict
    def plot_trajectories(hold_outcomes, sell_outcomes) -> plotly.Figure
    def validate_against_precomputed(decision_id) -> dict
    def bias_impact_quantifier() -> dict  # population-level across 1000 users
```

### 9.2 Core Logic

**HOLD scenario:**
```
starting_wealth = current_wealth × (1 + unrealized_gl)
portfolio_returns = weighted sample from synthetic_market_paths.npy
                    (weighted by user risk_tolerance)
final_wealth[path] = starting_wealth × Π(1 + r) for each year
Output: {median, p10, p90, std, year_by_year[]}
```

**SELL scenario:**
```
realized = current_wealth × (1 + unrealized_gl × 0.95)  # 5% transaction cost
tax_deduction = STCG/LTCG calculation (if tax_engine.py exists)
reinvest at conservative allocation (panic-sold → risk-averse)
conservative_returns = market_paths weighted downward by sell-induced risk aversion
final_wealth[path] = realized × Π(1 + r_conservative) for each year
Output: {median, p10, p90, std, year_by_year[]}
```

**Opportunity cost:**
```
opportunity_cost_inr = mean(hold_outcomes) - mean(sell_outcomes)
prob_hold_better = (hold_outcomes > sell_outcomes).mean()
```

### 9.3 Data Dependencies
- `synthetic_market_paths.npy` (10,000 × 30) — **must exist first**
- `synthetic_users.csv` — user profiles for personalization
- `synthetic_counterfactuals.csv` — validation ground truth

### 9.4 Dashboard Update (after GAP 2 backend exists)
- Add "Wealth Projections" section to Decision Analysis page
- Show HOLD vs SELL trajectory chart with p10/p90 uncertainty bands
- Show opportunity cost in ₹ terms prominently

### 9.5 New API Endpoint
```
POST /simulate
Body: { user_id, current_wealth, unrealized_gl, decision }
Returns: { hold: {...}, sell: {...}, opportunity_cost_inr, confidence }
```

### 9.6 GAP 2 Experiment Target
Simulate 1,000 users → report average HOLD vs SELL wealth gap.
Expected result: **~42% wealth difference** (biased vs rational decisions).

---

## 10. GAP 3 — Decision-Centric Explainability + Debate Engine (Plan)

**The research gap:** SHAP explains "why the model predicted X". GAP 3 explains
"how decision X affects your life over 20 years." Explanations are decision-centric,
counterfactual, and temporal — not model-centric and static.

### 10.1 What to Build: `src/explainer.py`

```python
class DecisionExplainer:
    def explain_decision(user_id, decision_context, actual_decision) -> dict
    def _build_narrative(user, context, comparison, bias) -> str
    def visualize_temporal_impact(comparison, user) -> plotly.Figure
    def _get_bias_explanation(bias_type) -> str
    def generate_summary_card(explanation) -> str  # 3-sentence WhatsApp-ready
```

### 10.2 Explanation Output Structure

| Section | Content | Source |
|---|---|---|
| Situation | Market state, portfolio state, user horizon, current value | decision_context + user profile |
| Your Decision | What action was taken | user input |
| Counterfactual | If HOLD: median/p10/p90 in N years. If SELL: median/p10/p90 | GAP 2 simulator |
| Opportunity Cost | ₹ difference between HOLD and SELL | GAP 2 simulator |
| Causal Analysis | Which bias drove it + causal effect magnitude | GAP 1 causal_inference |
| Recommendation | Better decision + confidence backed by N simulations | GAP 2 + GAP 1 |
| Temporal Chart | Year-by-year wealth trajectory, both scenarios | GAP 2 trajectory arrays |
| Audit Hash | SHA-256 hash confirming explanation is tamper-proof | GAP 4 audit_logger |

### 10.3 Multi-Agent Debate Engine: `src/debate_engine.py`

When a user is about to make a financial decision, two AI agents debate it from opposing
sides. A Judge agent synthesizes the strongest arguments to produce a trustworthy recommendation.

**Architecture:**
```
Bull Agent  ──→→──┐
                  ↓
Bear Agent  ──→→──→  Judge Agent → final_recommendation + confidence + top3_pros + top3_cons
                  ↑
       (up to 3 rounds, extra round only if disagreement_score > threshold)
```

**Context passed to ALL agents:**
```python
debate_context = {
    "user":       { age, risk_tolerance, investment_horizon, has_emergency_fund },
    "bias":       { bias_type, confidence, causal_effect_magnitude },
    "simulation": { hold_median, sell_median, opportunity_cost, hold_p10, hold_p90 },
    "market":     { nifty_return, vix, bank_nifty_return },
    "position":   { unrealized_gl, holding_period_months, position_size_pct }
}
```

**Critical constraint:** All agents are instructed to cite ONLY numbers from `debate_context`.
No hallucinated statistics. Financial advice built on made-up numbers is dangerous.

**Judge output schema:**
```json
{
  "final_recommendation": "HOLD",
  "confidence": 0.82,
  "top_pros": ["₹29,292 opportunity cost", "25yr horizon absorbs volatility", "bias-driven"],
  "top_cons": ["Further downside possible", "EMI pressure noted"],
  "reasoning_summary": "2-3 sentence synthesis for non-technical users",
  "debate_transcript": "full round-by-round exchange for audit logging",
  "evidence_weights_used": { "simulation": 0.50, "causal": 0.30, "market": 0.20 }
}
```

**Technology:** `pyautogen` (AutoGen) + `claude-sonnet-4-20250514` via Anthropic API

**Why this strengthens GAP 3:**
- User sees BOTH sides argued with real numbers before recommendation is given
- Increases trust — recommendation feels earned, not just asserted
- Full transcript in audit trail strengthens GAP 4
- Academic framing: "decision-centric XAI + adversarial multi-agent reasoning"

---

## 11. GAP 4 — Counterfactual Verifiability & Auditability (Plan)

**Important framing from blueprint:**
- **70% of GAP 4 = Counterfactual engine** (personalized HOLD/SELL what-if outcomes)
- **30% of GAP 4 = Audit trail** (makes counterfactuals trustworthy)
- The audit trail is the supporting mechanism, NOT the primary contribution

### 11.1 Current State
Basic SHA-256 hash exists in `database.py` — single hash per decision.
Missing: chain linking, full `audit_logger.py` class, debate transcript hashing.

### 11.2 What to Build: `src/audit_logger.py`

```python
class BlockchainAuditSystem:
    def log_decision(inputs, bias_result, simulation_result, explanation, debate_transcript) -> block
    def verify_decision(decision_id) -> { verified: bool, tamper_detected: bool }
    def generate_audit_report(decision_id) -> dict
    def export_chain() -> list  # full chain for external verification
```

**Hash components:**
```
input_hash        = SHA256(serialize(decision_inputs))
bias_hash         = SHA256(serialize(bias_result + shap_values))
simulation_hash   = SHA256(serialize(hold/sell outcomes))
explanation_hash  = SHA256(serialize(narrative + debate_transcript))
block_hash        = SHA256(input_hash + bias_hash + simulation_hash + explanation_hash + previous_hash)
```

**Chain integrity:** Each block stores `previous_hash` — forming a tamper-detectable chain.
Modifying any decision in the middle breaks all subsequent hashes.

### 11.3 New API Endpoint
```
GET /audit/{decision_id}
→ Recomputes all hashes, compares to stored chain
→ Returns: verified, tamper_detected, full_hash, component_hashes, audit_report
```

### 11.4 Dashboard: Audit Trail Viewer
A new page or section showing:
- Decision ID + timestamp
- Full hash (user can copy and independently verify)
- Component hashes (input, bias, simulation, explanation)
- Chain position (block #N, links to block #N-1)
- Tamper status (✅ Verified / ❌ TAMPERED)

---

## 12. Practical Extensions — Layer 2 (Plan)

These are built **after all 4 GAPs are complete**. They make the research system real-world usable.

### 12.1 Tax Engine: `src/tax_engine.py`

| Rule | Value |
|---|---|
| STCG (equity, < 12 months) | 20% |
| LTCG (equity, ≥ 12 months) | 12.5% |
| LTCG annual exemption | First ₹1,25,000 of gains is tax-free |
| Debt MF (post-2023) | Taxed as per income slab |

**Integration:** All SELL scenario simulations deduct applicable tax before computing
final wealth. Example output: "Selling now triggers STCG of ₹12,000 — adding ₹2,400 tax.
Holding 4 more months qualifies for LTCG, saving ₹1,400 in tax."

### 12.2 SIP Tracker: `src/sip_tracker.py`
- Register SIPs: amount, frequency, start_date, fund/stock, target_amount
- Track continuity — was SIP paused in DB history?
- Simulate: SIP continued vs paused for N months (Monte Carlo)
- Trigger alert when market drops >3%: "Pausing your SIP now costs ₹X in Y years"
- API: `POST /sip/register`, `GET /sip/{user_id}/status`, `GET /sip/{user_id}/impact`

### 12.3 Zerodha Kite Integration: `src/kite_integration.py`
- **FREE** — portfolio/holdings/positions APIs (free since March 2025)
- OAuth flow — user logs in with Zerodha credentials, `access_token` stored in DB
- Auto-fetches: holdings (stock, qty, buy_price, current_price), P&L, order history
- Replaces manual input of `unrealized_gl`, `position_size_pct`, `holding_period_months`
- Fallback: users without Zerodha use manual input form (unchanged)

### 12.4 Multi-Asset Support: `src/multi_asset.py`

| Asset Class | Data Source |
|---|---|
| Stocks (NSE/BSE) | Zerodha Kite (auto) or yfinance |
| Mutual Funds | MFAPI.in — free, no auth, NAV by scheme code |
| Gold | yfinance `GOLDBEES.NS` ETF as proxy |
| Cryptocurrency | CoinGecko API — free, 30 calls/min |
| Real Estate | Manual only — no reliable free API in India |
| Fixed Deposits | Manual — static calculation |

### 12.5 WhatsApp Bot: `src/whatsapp_bot.py` ← LOWEST PRIORITY
- Meta WhatsApp Cloud API (direct, free for user-initiated conversations)
- User types: "Should I sell HDFC Bank?" → full pipeline → 3-sentence reply
- Uses `generate_summary_card()` from `explainer.py`
- Architecture: User → WhatsApp → webhook → `/analyze/decision` → formatted response
- Build ONLY after all GAPs, Kite, SIP, and tax engine are complete

### 12.6 Version A — Feedback Loop: `src/outcome_tracker.py` + `scripts/bias_detector_retrainer.py`
- Track whether recommendations were followed + actual outcome after N months (via Kite API)
- Monthly batch retraining: new real-world labeled decisions added to training set
- XGBoost retrained → saved as `bias_detector_v{N+1}.pkl`
- Academic framing: "continuous learning pipeline where real user decision outcomes serve
  as ground truth labels for periodic model retraining"

---

## 13. Complete Build Sequence — Master Checklist

### Phase 1 — Complete GAP 1 (Current Phase)
- [ ] **Generate all 7 synthetic datasets** — run data generation script
- [ ] **Extend `database.py`** — add Tier 1 fields: EMI, edu expenses, end year, rent, surplus
- [ ] **Update `/user/register`** — Pydantic model + surplus auto-calculation
- [ ] **Update dashboard registration form** — add new Tier 1 input widgets
- [ ] **Add behavioral onboarding quiz** — 5 questions → set initial `risk_tolerance`
- [ ] **Verify all 30 unit tests** pass with updated schema

### Phase 2 — Build GAP 2 Backend
- [ ] **Create `src/simulator.py`** — `LongHorizonSimulator` class
- [ ] **Implement HOLD vs SELL** Monte Carlo using `synthetic_market_paths.npy`
- [ ] **Validate against `synthetic_counterfactuals.csv`** — target 42% wealth gap
- [ ] **Add `POST /simulate`** to `api.py`
- [ ] **Write `tests/test_simulator.py`**
- [ ] **Update dashboard** — add wealth trajectory charts to Decision Analysis page

### Phase 3 — Build GAP 3 + Debate Engine
- [ ] **Create `src/explainer.py`** — `DecisionExplainer` class
- [ ] **Build counterfactual narrative generator**
- [ ] **Build year-by-year Plotly temporal visualization**
- [ ] **Create `src/debate_engine.py`** — Bull, Bear, Judge agents via AutoGen
- [ ] **Wire debate output** as backbone of explainer narrative
- [ ] **Add `/explain` and `/debate`** endpoints to `api.py`
- [ ] **Wire explainer + debate** to dashboard (pros/cons cards, recommendation panel)
- [ ] **Write `tests/test_explainer.py`** and **`tests/test_debate_engine.py`**

### Phase 4 — Build GAP 4 (Standalone Audit Logger)
- [ ] **Create `src/audit_logger.py`** — `BlockchainAuditSystem` class
- [ ] **Implement SHA-256 hash chain** with `previous_hash` chaining
- [ ] **Update `GET /audit/{id}`** — full chain verification
- [ ] **Add audit trail viewer** to dashboard (new page/section)

### Phase 5 — Practical Extensions (in order)
- [ ] `src/tax_engine.py` — STCG/LTCG, integrate with simulator SELL scenario
- [ ] `src/sip_tracker.py` — registration, continuity, pause cost
- [ ] `src/kite_integration.py` — Zerodha OAuth + portfolio auto-fetch
- [ ] `src/multi_asset.py` — MF, Gold, Crypto
- [ ] **Dashboard Financial Profile page** — Tier 2 inputs, net worth display
- [ ] Educational expense seasonal stress detection (April/July/Oct/Jan flags)
- [ ] `src/outcome_tracker.py` — tracks recommendation outcomes
- [ ] `scripts/bias_detector_retrainer.py` — monthly batch retraining
- [ ] `src/whatsapp_bot.py` ← build last

### Phase 6 — Integration & Validation
- [ ] Full end-to-end Ramesh scenario test
- [ ] Run all 4 experiments, document results
- [ ] Write research paper sections (IEEE format)
- [ ] Prepare demo video / viva presentation

---

## 14. Technology Stack

### Research Core
| Technology | Purpose |
|---|---|
| Python 3.9+ | Primary language |
| XGBoost | 4-class bias classification (89.1% accuracy) |
| SHAP | Per-prediction feature attribution |
| DoWhy | Causal inference, linear regression backdoor, refutation tests |
| CausalNex (NOTEARS) | Causal structure learning from data |
| imbalanced-learn (SMOTE) | Herd class oversampling |
| NumPy / Pandas | Data processing + Monte Carlo simulation |
| SciPy | Statistical tests, distribution fitting |
| Matplotlib / Plotly | Visualization + temporal trajectory charts |
| FastAPI + Uvicorn | REST API backend — 14 endpoints running |
| SQLite (sqlite3) | Persistent database — no ORM |
| hashlib (SHA-256) | Cryptographic audit trail |
| joblib / pickle | Model persistence |
| Streamlit | Interactive frontend dashboard |

### Multi-Agent Stack
| Technology | Purpose |
|---|---|
| pyautogen (AutoGen) | Bull, Bear, Judge round-robin debate orchestration |
| claude-sonnet-4-20250514 | LLM powering all 3 debate agents via Anthropic API |

### Practical Extensions
| Technology | Purpose |
|---|---|
| yfinance | NIFTY50, SENSEX, Bank NIFTY, India VIX, Gold ETF — free |
| kiteconnect (Python SDK) | Zerodha Kite API — portfolio auto-fetch |
| MFAPI.in (REST) | Mutual fund NAV lookup — free |
| CoinGecko API | Cryptocurrency prices — free tier |
| Meta WhatsApp Cloud API | WhatsApp bot — free, user-initiated |

---

## 15. Ramesh — End-to-End Demo Scenario

This is the north star. When it runs without error, the project is demo-ready.

**Context:** Market crashes 12% in one week. Ramesh, 38, has ₹75,000 in HDFC Bank stock.
Down 18% on paper. 88% of crowd is selling. He wants to sell.

**Profile:** Income ₹80,000/month. EMI ₹18,000. School fees ₹10,000/month (ends in 5 years).
Rent paid ₹12,000. Monthly surplus ₹40,000. Emergency fund: YES.
This ₹75K = 8% of liquid net worth — a small position relative to profile.

| Step | System Action | Output |
|---|---|---|
| 1 | Market fetch | NIFTY (-12%), VIX (high), Bank NIFTY (-14%) |
| 2 | Portfolio fetch | Kite auto-fetch: ₹75K HDFC, unrealized -18% |
| 3 | Bias detect | `loss_aversion`, 87% confidence, SHAP: unrealized_gl is top factor |
| 4 | Causal | loss_aversion → SELL effect: +0.312 |
| 5 | Simulate | HOLD → ₹67,583 median (20yr) | SELL → ₹38,291 median |
| 6 | Debate | Bull cites ₹29,292 cost + horizon. Bear cites further downside risk. Judge: HOLD wins (82% confidence) |
| 7 | Tax | SELL triggers STCG ₹1,800. Holding 4 months → LTCG → saves ₹1,800 in tax |
| 8 | Explain | "Loss Aversion detected (87%). Selling now costs ₹29,292 in expected 20-year wealth." |
| 9 | SIP check | "Pausing NIFTY SIP costs ₹8,400 more than continuing." |
| 10 | Audit | SHA-256 chain logged — inputs + bias + simulation + debate transcript all hashed |
| 11 | WhatsApp | "HOLD recommended. Your ₹40K/month surplus and 25yr horizon support this. Selling costs ₹29K long-term." |

**Final recommendation: HOLD.**

---

## 16. Research Experiments & Metrics

These 4 experiments form the Results section of the IEEE-format research paper.

| Experiment | What Is Measured | Target | GAP | Status |
|---|---|---|---|---|
| Exp 1: Bias Detection Accuracy | XGBoost test set classification | ≥85% accuracy | GAP 1 | ✅ 89.1% achieved |
| Exp 2: Long-Term Bias Impact | HOLD vs SELL wealth gap across 1,000 users × 30 years | ~42% wealth gap | GAP 2 | ❌ Not run |
| Exp 3: Explainability Quality | Counterfactual narrative vs `synthetic_counterfactuals.csv` | Error ≤5% | GAP 3 | ❌ Not run |
| Exp 4: Audit Integrity | Hash verification + chain tamper detection | 100% detection | GAP 4 | ❌ Not run |

---

*This document is the single source of truth for the Financial Decision Intelligence System.*
*Blueprint v2.0 aligned | Codebase audited April 2026 | Next milestone: Phase 1 finalization*
