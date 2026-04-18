# 🧠 Major Project — Master Reference Document

**Title:** "A Causal Decision-Time Framework for Behavioral Bias Detection and Long-Horizon Portfolio Evaluation with Counterfactual Verifiable Intelligence"

> **This file is the single source of truth for the project.**
> Last updated: April 2026 — reflects v3 model (52 features, 7,439 rows) + full blueprint alignment.

---

## 1. CORE PROBLEM

Retail investors make emotionally-driven financial decisions — panic selling, herd behavior, loss aversion, disposition effect — that cost 30–40% of lifetime wealth. Existing systems analyze these behaviors **after** the damage is done, offer generic market-level advice, and provide no verifiable reasoning.

This project builds a system that **intervenes at the exact moment of decision.**

---

## 2. TWO-LAYER ARCHITECTURE

| Layer 1 — Research Core | Layer 2 — Practical Extensions |
|---|---|
| Required for grades, paper, and viva | Makes the system real-world usable |
| 4 Research GAPs addressed | Zerodha Kite API integration |
| All 4 objectives fulfilled | SIP tracking module |
| Experiments documented | Tax impact layer (STCG/LTCG) |
| IEEE-style paper ready | Multi-asset support |
| | WhatsApp bot interface |

---

## 3. FOUR RESEARCH GAPS

| GAP | Current State of Research | This Project's Solution | Status |
|---|---|---|---|
| **GAP 1** | Biases detected AFTER decisions | Detect biases AT decision-time using XGBoost + causal reasoning | ✅ COMPLETE |
| **GAP 2** | Generic market-level predictions only | Individual Monte Carlo simulations over 10–30 years personalized to user | 🔄 IN PROGRESS |
| **GAP 3** | Post-hoc, static explainability (SHAP/LIME) | Decision-centric counterfactual narratives + Bull/Bear/Judge debate engine | 🔲 PLANNED |
| **GAP 4** | No counterfactual or verifiable intelligence | Counterfactual engine (70%) + SHA-256 cryptographic audit trail (30%) | 🔲 PLANNED |

---

## 4. SYSTEM PIPELINE

```
INPUT → DETECT → REASON → SIMULATE → EXPLAIN → INTERVENE → AUDIT

INPUT:     User profile + portfolio state + market data + decision context
DETECT:    XGBoost v3 bias classifier → bias_type + confidence + SHAP explanation
REASON:    DoWhy causal engine → causal effects + intervention simulation
SIMULATE:  Monte Carlo long-horizon simulator → HOLD vs SELL wealth projections
EXPLAIN:   Bull/Bear/Judge debate → counterfactual narratives
INTERVENE: Cooling-off suggestions, rule-based bias mitigation actions
AUDIT:     SHA-256 hash chain → tamper-evident, append-only decision log
```

---

## 5. GAP 1 — BIAS DETECTION (COMPLETE)

### Model Performance — v3 (Current Production)

| Metric | Value | Target | Status |
|---|---|---|---|
| Test Macro F1 | **85.81%** | ≥ 85% | ✅ |
| CV Macro F1 (5-fold) | **86.38% ± 0.89%** | ≥ 82% | ✅ |
| CV-to-Test Gap | **0.57%** | < 5% | ✅ Excellent generalisation |
| Herd F1 | **97.39%** | ≥ 90% | ✅ |
| Loss Aversion F1 | **90.37%** | ≥ 80% | ✅ |
| Loss Aversion Recall | **85.0%** | ≥ 75% | ✅ |
| Herd borderline accuracy | **100%** | ≥ 90% | ✅ |
| Features | **52** (from 47 in v2) | ≥ 47 | ✅ |
| Training rows | 5,951 / 7,439 total | — | — |
| SMOTE | **Removed** — class weights only | — | — |

**Version history:** v1 (44 feat, 5,400 rows, SMOTE) → v2 (+diversity fix) → v3 (52 feat, 7,439 rows, NO SMOTE, Macro F1=85.81%)

**Model file:** `models/bias_detector_xgboost_v3.pkl`
**Report file:** `results/model_evaluation_report_v3.json`

### 4 Bias Classes

| Class | Label | Description | v3 F1 |
|---|---|---|---|
| `disposition` | 0 | Sell winners early, hold losers too long | 75.0% |
| `herd` | 1 | Follow the crowd blindly | **97.4%** |
| `loss_aversion` | 2 | Panic sell to stop emotional pain | **90.4%** |
| `rational` | 3 | No significant bias detected | 80.5% |

### GAP 1 Remaining Tasks
- Extend `market_data.py` — add SENSEX, Bank NIFTY, India VIX
- Add live market indices ribbon to dashboard (top banner all pages)
- Add static tax slab panel to dashboard sidebar (STCG 15%, LTCG 10%)
- Update `/user/register` — add Tier 1 inputs (educational expenses, rent, emergency fund)
- Add `monthly_surplus` auto-calculation to `database.py`
- Upgrade `causal_inference.py` to full DoWhy propensity score matching
- Add formal DoWhy refutation tests (random_common_cause, placebo_treatment)

---

## 6. GAP 2 — LONG-HORIZON PORTFOLIO SIMULATION (IN PROGRESS)

### What Needs to Be Built
**File:** `src/simulator.py` — `LongHorizonSimulator` class

```
Methods:
  simulate_individual(user_id, decision, current_portfolio) → wealth distribution dict
  compare_hold_vs_sell(user_id, current_wealth, unrealized_gl) → opportunity cost dict
  plot_trajectories(hold_outcomes, sell_outcomes) → plotly figure with uncertainty bands
  validate_against_precomputed(decision_id) → accuracy vs synthetic_counterfactuals.csv
  bias_impact_quantifier() → population-level wealth loss from biases across 1000 users
```

### Core Simulation Logic

| Scenario | Logic |
|---|---|
| **HOLD** | `starting_wealth = current_wealth × (1 + unrealized_gl)` → final = starting × ∏(1 + portfolio_returns) from `synthetic_market_paths.npy` weighted by risk_tolerance |
| **SELL** | `realized = current_wealth × (1 + unrealized_gl × 0.95)` — 5% transaction cost → reinvest at lower stock allocation (panic-sold → conservative) |
| **Opportunity cost** | `mean(hold_outcomes) − mean(sell_outcomes)` / `prob_hold_better = (hold > sell).mean()` |
| **Output** | median, p10, p90, std for both HOLD and SELL / year-by-year trajectory arrays / opportunity cost in absolute ₹ |

### Monte Carlo — Why 1,000 Paths
Running 1,000 random 30-year market paths gives **probability distributions**, not single numbers:
- Confidence bands (P10/P50/P90) — honest uncertainty
- Probability of underperforming rational benchmark
- Worst case / best case scenarios
- Statistically significant results (1,000 paths eliminates noise)

### Validation Target
Simulate 1,000 users, compare to `synthetic_counterfactuals.csv`.
Target: **~42% wealth gap** between biased and rational investors over 30 years.

### Data Already Available
- `synthetic_market_paths.npy` — 10,000 paths × 30 years ✅
- `synthetic_users.csv` — user profiles ✅
- `synthetic_counterfactuals.csv` — HOLD/SELL validation ✅
- `src/simulator.py` — ❌ needs to be built

---

## 7. GAP 3 — DECISION-CENTRIC EXPLAINABILITY + DEBATE ENGINE (PLANNED)

### The Gap
SHAP and LIME explain *"why the model predicted X"*. This system explains *"how decision X affects your life over 20 years."* Explanations are decision-centric, counterfactual, and temporal.

### What Needs to Be Built

**File:** `src/explainer.py` — `DecisionExplainer` class
```
Methods:
  explain_decision(user_id, decision_context, actual_decision) → full narrative + viz
  _build_narrative(user, context, comparison, bias) → structured text explanation
  visualize_temporal_impact(comparison, user) → year-by-year plotly chart
  _get_bias_explanation(bias_type) → human-readable cause explanation
  generate_summary_card(explanation) → short 3-sentence summary for WhatsApp/API
```

**Explanation Output Structure:**

| Section | Content | Source |
|---|---|---|
| Situation | Market state, portfolio state, user horizon | decision_context + user profile |
| Your Decision | What action was taken | user input |
| Counterfactual | HOLD: median/p10/p90 in N years \| SELL: median/p10/p90 | GAP 2 simulator |
| Opportunity Cost | ₹ difference between HOLD and SELL | GAP 2 simulator |
| Causal Analysis | Which bias drove decision + causal effect magnitude | GAP 1 causal_inference |
| Recommendation | Better decision + confidence % + N simulations backing | GAP 2 + GAP 1 |
| Temporal Chart | Year-by-year wealth trajectory for both scenarios | GAP 2 trajectory arrays |
| Audit Hash | SHA-256 hash confirming explanation is tamper-proof | GAP 4 audit_logger |

---

## 8. MULTI-AGENT DEBATE SYSTEM (GAP 3 EXTENSION)

When a user is about to make a financial decision, two AI agents debate it from opposing sides. A Judge synthesizes the strongest arguments. This makes explanations far more trustworthy than a single model output.

### Architecture

```
Bull Agent  ──┐
              ├──→  Round-Robin Debate  ──→  Judge Agent  ──→  Explainer Narrative
Bear Agent  ──┘

Round 1:  Each agent opens their case (simulation-grounded numbers)
Round 2:  Each agent responds to the other's strongest point
Round 3:  Only triggered if disagreement score > threshold (avoids verbosity)
Judge:    Receives full transcript → top 3 pros + top 3 cons
          Weights: simulation evidence 50% + causal 30% + market 20%
```

### Judge Output Schema (JSON)
```
final_recommendation:  HOLD or SELL
confidence:            float (0.0 – 1.0), weighted by evidence strength
top_pros:              list of 3 strongest HOLD arguments (simulation-grounded)
top_cons:              list of 3 strongest SELL arguments
reasoning_summary:     2–3 sentence synthesis for non-technical users
debate_transcript:     full round-by-round exchange for audit logging
evidence_weights_used: {simulation: 0.50, causal: 0.30, market: 0.20}
```

### Context Passed to All Agents
```
user:       age, risk_tolerance, investment_horizon, has_emergency_fund
bias:       bias_type, confidence, causal_effect_magnitude
simulation: hold_median, sell_median, opportunity_cost, hold_p10/p90, sell_p10/p90
market:     nifty_return, vix, bank_nifty_return
position:   unrealized_gl, holding_period_months, position_size_pct
```
> **CRITICAL:** All agents cite ONLY provided numbers. No hallucinated statistics.

### Tech Stack for Debate
| Technology | Purpose |
|---|---|
| `pyautogen` (AutoGen) | Multi-agent orchestration — round-robin conversation |
| `claude-sonnet-4-20250514` | LLM powering all 3 agents via Anthropic API |

### Files Required
- `src/debate_engine.py` — DebateEngine class (BullAgent, BearAgent, JudgeAgent)
- `tests/test_debate_engine.py` — unit tests

### Why This Strengthens the Research
- Current GAP 3: single model → one narrative (black box)
- With debate: user sees BOTH sides argued with real numbers before recommendation
- Full transcript in audit trail → AI reasoning is fully traceable (strengthens GAP 4)

---

## 9. GAP 4 — COUNTERFACTUAL VERIFIABILITY + AUDIT TRAIL (PLANNED)

### Primary vs Supporting Contribution
| Primary (70%) — Counterfactual Engine | Supporting (30%) — Audit Trail |
|---|---|
| Personalized HOLD vs SELL outcomes | SHA-256 hash chain on all decisions |
| What-if reasoning over 20–30 years | Makes counterfactuals trustworthy |
| Outcome distributions with uncertainty | Tamper detection + audit reports |
| **The novel technical contribution** | Supporting mechanism |

### What Needs to Be Built
**File:** `src/audit_logger.py` — `BlockchainAuditSystem` class

```
audit_logs table columns:
  log_id, decision_id, input_hash, output_hash, explanation_hash, full_hash, timestamp
  APPEND ONLY — no updates or deletes

Methods:
  log_decision()       — hash all components, chain to previous block
  verify_decision()    — recompute hashes, detect tampering
  generate_audit_report() — full decision trace with verified hashes
  export_chain()       — exportable audit trail

Hash components:
  input_hash + bias_hash + simulation_hash + explanation_hash + debate_transcript_hash
  → block_hash (each block stores previous_hash → tamper-detectable chain)

API endpoint: GET /audit/{decision_id} — recomputes, confirms, returns verified report
Dashboard: Audit trail viewer — shows hash, user can copy and verify independently
```

---

## 10. USER INPUT DESIGN — TIERED SYSTEM

### Tier 1 — Required at Onboarding (~2 minutes)

| Input Field | Why Required | How Used |
|---|---|---|
| Monthly income (post-tax) | Base for all cash flow calculations | surplus = income − EMIs − fees − rent |
| Total monthly EMIs | Non-negotiable outflow | Surplus calculation |
| Monthly educational expenses | School fees, tuition — fixed outflow | Surplus + seasonal stress detection |
| Educational expense time-bound? (Y/N + year) | Fees ending in N years increases future surplus | Simulator increases surplus from Year N+1 |
| Rent paid (if any) | Reduces monthly surplus | Surplus calculation |
| Has emergency fund? (Y/N) | Directly affects if SELL is defensible or reckless | SELL risk score modifier |
| Investment horizon (years) | Core parameter for simulation length | GAP 2 simulator |
| Risk tolerance (5-question quiz) | Determines asset allocation | GAP 2 portfolio allocation |

### Tier 2 — Optional (Financial Profile Page)

| Input Field | Why Valuable | How Used |
|---|---|---|
| Gold holdings (grams + purchase price) | Major asset for Indian families | Multi-asset portfolio simulation |
| Real estate value (manual estimate) | Largest asset for most Indians | Net worth calculation only |
| Outstanding home loan | Largest liability | Net worth + risk score modifier |
| Other loans (personal, car, education) | Total debt burden | Net worth calculation |
| Rent received (if any) | Positive cash flow | Monthly surplus calculation |
| Mutual fund holdings | Portfolio completeness | MFAPI.in NAV fetch |
| Crypto holdings | Volatile asset affecting risk profile | CoinGecko price fetch |
| Fixed deposits (total value) | Safe asset context | Net worth calculation |

### Tier 3 — NOT Collected
- Credit card balances (too volatile, changes daily)
- Insurance premium amounts (not decision-relevant)
- Grocery / utility expenses (too granular, users won't track accurately)
- Vehicle details (depreciating asset)
- Exact FD interest rates (total value is sufficient)

### Net Worth Calculation
```
liquid_net_worth   = stock_portfolio + mutual_funds + gold_value
                   + crypto_value + savings_balance + fixed_deposits

illiquid_net_worth = real_estate_value − outstanding_home_loan

total_liabilities  = home_loan + personal_loan + car_loan + education_loan

net_worth          = liquid_net_worth + illiquid_net_worth

monthly_surplus    = monthly_income + rent_received − rent_paid
                   − total_emi − monthly_educational_expenses

NOTE: educational_expenses_monthly = annual_fees / 12
      if time_bound: surplus increases from year (end_year + 1) in simulation
```

### Educational Expense — Special Handling
1. **Seasonal stress trigger:** Fee payments in April/July/October/January. System detects if decision is made within 30 days of fee payment month → flags as *cash flow stress amplifying bias.*
2. **Simulation impact:** If fees are time-bound, Monte Carlo shows increasing wealth from Year N+1 due to higher surplus.
3. **Intervention text example:** *"Your sell urge may be amplified by upcoming fee payment pressure (April quarter). Your ₹18,000 monthly surplus is sufficient to cover this without liquidating your investment. Selling now costs ₹29,292 in expected 20-year wealth."*

---

## 11. FEEDBACK-BASED MODEL IMPROVEMENT (VERSION A)

After each recommendation, the system tracks whether the user followed it and what the actual outcome was. Real behavior data is used to retrain the bias detector monthly.

### Why Version A (Not LLM Self-Critique)
| Version A — Real Feedback Loop ✅ | Version B — LLM Self-Critique ❌ |
|---|---|
| Model improves from real user behavior | LLM critiques its own output |
| Academically defensible and measurable | Wrong answer confidently refined = dangerous |
| Ground truth labels from actual outcomes | No ground truth — improvement unverifiable |
| XGBoost retrains on real decisions monthly | Hard to justify academically |

### Feedback Loop Flow
```
STEP 1: User follows or ignores recommendation (logged in decisions_live table)
STEP 2: After N months, fetch actual portfolio outcome from Kite API
STEP 3: Compare actual outcome to simulated HOLD/SELL projections
STEP 4: Label the decision: was the recommendation correct? (new ground truth)
STEP 5: bias_detector_retrainer.py runs monthly batch retraining
STEP 6: New samples added to training set with verified real-world labels
STEP 7: XGBoost retrained, saved as bias_detector_v{N+1}.pkl
STEP 8: Model version, accuracy logged in audit trail
STEP 9: Old model retained 6 months (rollback capability)
```

### Files Required
- `src/outcome_tracker.py` — tracks if recommendations were followed, fetches Kite outcomes
- `scripts/bias_detector_retrainer.py` — monthly batch job, retrains if accuracy improves

---

## 12. PRACTICAL EXTENSIONS (LAYER 2)

### Zerodha Kite API
- **Cost:** FREE — portfolio/holdings/positions APIs free since March 2025
- **What it replaces:** Manual input of unrealized_gl, position_size_pct, holding_period
- **What it fetches:** Holdings, positions, P&L, order history
- **File:** `src/kite_integration.py` (new)
- Users without Zerodha → manual input form (same as current)

### SIP Tracking Module (`src/sip_tracker.py`)
Most underserved problem: stopping SIPs during market crashes.
- SIP registration (amount, frequency, fund, target)
- Continuity tracking (was it paused?)
- **Pause cost simulation:** Monte Carlo — SIP continued vs paused N months
- **Alert trigger:** When market drops >3% → "Pausing your SIP costs ₹X in Y years"

### Tax Impact Layer (`src/tax_engine.py`)
| Rule | Rate |
|---|---|
| STCG (holding < 1 year, equity) | 15% |
| LTCG (holding ≥ 1 year, equity) | 10% on gains above ₹1 lakh |
| LTCG exemption | First ₹1,00,000 of long-term gains/year is tax-free |
| Post-2023 debt funds | Taxed as per income slab |

All SELL simulations add tax deduction.
Example: *"Selling now triggers STCG of ₹12,000 — ₹1,800 in tax. Holding 4 more months qualifies for LTCG and eliminates this cost entirely."*

### Multi-Asset Support (`src/multi_asset.py`)
| Asset | Data Source | Input Method |
|---|---|---|
| Stocks (NSE/BSE) | Kite API or yfinance | Auto or manual symbol |
| Mutual Funds | MFAPI.in (free, no auth) | Manual: scheme + units + purchase NAV |
| Gold | yfinance — GOLDBEES.NS ETF | Manual: grams + purchase price |
| Cryptocurrency | CoinGecko API (free, 30 calls/min) | Manual: coin + quantity |
| Real Estate | No reliable free API — excluded from auto | Manual: value + year |
| Fixed Deposits | Static calculation | Manual: principal + rate + tenure |

### WhatsApp Bot (`src/whatsapp_bot.py`)
- **Provider:** Meta WhatsApp Cloud API (NOT Twilio — direct is free)
- **Cost:** FREE for user-initiated conversations (1,000/month free tier)
- **Priority:** LOWEST — build after all 4 GAPs complete
- **Flow:** User → WhatsApp → webhook → FastAPI `/analyze/decision` → formatted reply
- Uses GAP 3 `generate_summary_card()` for 3-sentence WhatsApp-friendly output

### Proactive Panic Alert System
- **Trigger:** `market_data.py` detects intraday NIFTY drop >2%
- **Action:** Fetch all users with active holdings from DB
- **Message:** "Market is down 2.4% today. Based on your profile, you may feel like selling. Here is what that costs you long-term: [simulation]"

### Natural Language Query Interface
| User Query | System Response |
|---|---|
| "Should I sell my stocks now?" | Full bias detection + simulation + counterfactual |
| "Is stopping my SIP a good idea?" | SIP continuity analysis + pause cost |
| "What happens if I hold long term?" | Monte Carlo projection with uncertainty bands |
| "How much tax if I sell HDFC?" | STCG vs LTCG calculation based on holding period |

---

## 13. FOUR RESEARCH EXPERIMENTS

| Experiment | What Is Measured | Target Metric | GAP |
|---|---|---|---|
| **Exp 1: Bias Detection** | XGBoost on test set | > 85% Macro F1 (achieved: 85.81%) | GAP 1 |
| **Exp 2: Long-Term Bias Impact** | Wealth difference: biased vs rational over 30 years | ~42% wealth gap across 1,000 users | GAP 2 |
| **Exp 3: Explainability Quality** | Counterfactual correctness vs synthetic_counterfactuals.csv | Narrative matches simulation within 5% error | GAP 3 |
| **Exp 4: Audit Integrity** | Hash verification + chain tamper detection | 100% tamper detection, 100% reproducibility | GAP 4 |

---

## 14. COMPLETE FILE STRUCTURE

```
Major Project/
├── src/
│   ├── data_preparation.py        ✅ 52-feature pipeline, stratified split
│   ├── bias_detector.py           ✅ v3 XGBoost + detect_bias_realtime()
│   ├── causal_structure.py        ✅ NOTEARS causal DAG
│   ├── causal_utils.py            ✅ Causal data helpers
│   ├── causal_inference.py        ✅ Partial correlation + DoWhy
│   ├── integration.py             ✅ Unified real-time pipeline
│   ├── api.py                     ✅ FastAPI 13 endpoints
│   ├── dashboard.py               ✅ Streamlit 3-page app (extend incrementally)
│   ├── database.py                ✅ SQLite — users, decisions, audit logs
│   ├── market_data.py             ✅ NIFTY50 + VIX (extend to SENSEX, BankNifty)
│   ├── simulator.py               ❌ GAP 2 — LongHorizonSimulator class
│   ├── explainer.py               ❌ GAP 3 — DecisionExplainer class
│   ├── debate_engine.py           ❌ GAP 3 — BullAgent, BearAgent, JudgeAgent
│   ├── audit_logger.py            ❌ GAP 4 — BlockchainAuditSystem class
│   ├── kite_integration.py        ❌ Practical — Zerodha Kite OAuth + portfolio fetch
│   ├── sip_tracker.py             ❌ Practical — SIP registration + pause cost sim
│   ├── tax_engine.py              ❌ Practical — STCG/LTCG calculation
│   ├── multi_asset.py             ❌ Practical — MF/Gold/Crypto integration
│   ├── outcome_tracker.py         ❌ Feedback loop — track recommendation outcomes
│   └── whatsapp_bot.py            ❌ Practical (LAST) — Meta Cloud API webhook
│
├── scripts/
│   ├── train_bias_detector_v3.py  ✅ Definitive retraining script
│   ├── generate_expanded_dataset.py ✅ Generates 7,439-row dataset
│   ├── validate_herd_generalisation.py ✅ 60 borderline herd test suite
│   ├── verify_final.py            ✅ 35 acceptance criteria checker
│   └── bias_detector_retrainer.py ❌ Feedback loop — monthly batch retrain
│
├── notebooks/
│   ├── 07_final_evaluation.ipynb  ✅ PRIMARY — v1→v2→v3 full comparison
│   ├── 04_full_pipeline_demo.ipynb ✅ DEMO — all 4 bias types with stories
│   ├── 02_bias_detection.ipynb    ✅ v3 deep-dive + real-time inference
│   ├── 06_model_improvement.ipynb ✅ v1→v2 journey, methodology
│   ├── 03_causal_analysis.ipynb   ✅ Causal DAG + DoWhy analysis
│   └── 08_portfolio_simulation.ipynb ❌ GAP 2 — Monte Carlo analysis
│
├── models/
│   ├── bias_detector_xgboost_v3.pkl ✅ PRODUCTION (52 features)
│   ├── bias_detector_xgboost_v2.pkl ✅ Archive (NB07 3-way comparison)
│   ├── bias_detector_xgboost.pkl  ✅ Archive (NB07 3-way comparison)
│   ├── causal_graph.pkl           ✅ Learned causal DAG
│   └── causal_scaler.pkl          ✅ Causal feature scaler
│
├── tests/
│   ├── test_bias_detector.py      ✅ (needs update for 52-feature schema)
│   ├── test_causal_inference.py   ✅
│   ├── test_api.py                ✅
│   ├── test_database.py           ✅
│   ├── test_market_data.py        ✅
│   ├── test_simulator.py          ❌ needs to be written
│   ├── test_explainer.py          ❌ needs to be written
│   └── test_debate_engine.py      ❌ needs to be written
│
├── results/
│   ├── model_evaluation_report_v3.json ✅ Canonical v3 metrics
│   ├── herd_generalisation_test_v3.json ✅
│   ├── figures/ (v3 plots)        ✅
│   └── simulations/               ← Objective 2 outputs go here
│
├── data/
│   ├── processed/merged_features.csv ✅ 7,439 rows × 52 cols
│   └── financial_intelligence.db  ✅ SQLite DB
│
├── synthetic_decisions.csv        ✅ 7,439 rows — 4 bias classes
├── synthetic_users.csv            ✅ 3,057 user profiles
├── synthetic_bias_profiles.csv    ✅ Ground truth bias scores
├── synthetic_market_paths.npy     ✅ 10,000 × 30yr Monte Carlo paths
├── synthetic_market_summary.csv   ✅ Regime-labelled path statistics
├── synthetic_counterfactuals.csv  ✅ HOLD/SELL 20yr validation
├── synthetic_audit_logs.csv       ✅ SHA-256 demo audit trail
│
├── project_overview.md            ✅ THIS FILE — single source of truth
├── GAP2_Individual_Portfolio_Long_Horizon.md ✅ GAP 2 detailed spec
├── GAP3_Decision_Centric_Explainability.md   ✅ GAP 3 detailed spec
├── GAP4_Counterfactual_Verifiable_Auditable.md ✅ GAP 4 detailed spec
├── Master_Blueprint_v2.docx       ✅ Original blueprint document
├── MajorProjectPlan.md            ✅ High-level research roadmap
├── project_report_obj1_obj2.md    ✅ PPT content — Obj 1 + Obj 2
├── requirements.txt               ✅ All dependencies
│
└── archive/                       ← Completed one-off scripts + old notebooks
```

---

## 15. FULL BUILD SEQUENCE (36 Steps, 6 Phases)

### Phase 1 — Complete GAP 1 (Current)
1. Extend `market_data.py` — add SENSEX, Bank NIFTY, India VIX
2. Update `dashboard.py` — live market indices ribbon (top of all pages)
3. Add static tax slab panel to dashboard sidebar
4. Update `/user/register` — add Tier 1 inputs (educational expenses + time-bound flag, rent, emergency fund)
5. Add `monthly_surplus` auto-calculation to `database.py`
6. Upgrade `causal_inference.py` to full DoWhy propensity score matching
7. Add formal refutation tests (random_common_cause, placebo_treatment)

### Phase 2 — Build GAP 2 Backend
8. Create `src/simulator.py` — `LongHorizonSimulator` class
9. Implement HOLD vs SELL Monte Carlo using `synthetic_market_paths.npy`
10. Validate against `synthetic_counterfactuals.csv`
11. Add `/simulate` endpoint to `api.py`
12. Write `test_simulator.py`
13. Add wealth trajectory charts to dashboard (Page 4)

### Phase 3 — Build GAP 3 Backend + Debate Engine
14. Create `src/explainer.py` — `DecisionExplainer` class
15. Build counterfactual narrative generator
16. Build year-by-year temporal visualization (Plotly)
17. Create `src/debate_engine.py` — BullAgent, BearAgent, JudgeAgent using AutoGen
18. Wire debate output into explainer — Judge output becomes narrative backbone
19. Add `/explain` and `/debate` endpoints to `api.py`
20. Wire explainer + debate output to dashboard
21. Write `test_explainer.py` and `test_debate_engine.py`

### Phase 4 — Build GAP 4 Backend
22. Create `src/audit_logger.py` — `BlockchainAuditSystem` class
23. Implement SHA-256 hash chain with tamper detection
24. Add `GET /audit/{decision_id}` endpoint with hash verification
25. Add audit trail viewer to dashboard

### Phase 5 — Practical Extensions (in order)
26. `src/tax_engine.py` — STCG/LTCG, integrate with simulator SELL scenario
27. `src/sip_tracker.py` — SIP registration, continuity tracking, pause cost
28. `src/kite_integration.py` — Zerodha Kite OAuth, portfolio auto-fetch
29. `src/multi_asset.py` — MF (MFAPI.in), Gold (yfinance), Crypto (CoinGecko)
30. Dashboard Financial Profile page — Tier 2 inputs + net worth display
31. Net worth calculation integrated into simulator
32. Educational expense seasonal stress detection
33. `src/outcome_tracker.py` — track recommendation outcomes
34. `scripts/bias_detector_retrainer.py` — monthly batch retraining
35. `src/whatsapp_bot.py` — Meta Cloud API webhook

### Phase 6 — Integration and Validation
36. Full end-to-end Ramesh scenario test → research paper → viva demo

---

## 16. COMPLETE TECHNOLOGY STACK

### Research Core
| Technology | Purpose |
|---|---|
| Python 3.9+ | Primary language |
| XGBoost | Bias classification (4-class, v3 Macro F1=85.81%) |
| SHAP | Per-prediction feature attribution |
| DoWhy | Causal inference, propensity score matching, refutation tests |
| CausalNex (NOTEARS) | Causal structure learning |
| imbalanced-learn | SMOTE (removed from training, kept for reference) |
| NumPy / Pandas | Data processing, Monte Carlo simulation |
| SciPy | Statistical tests, distribution fitting |
| Matplotlib / Plotly | Visualization, temporal trajectory charts |
| FastAPI + Uvicorn | REST API backend (13+ endpoints) |
| SQLite | Persistent database — no ORM |
| hashlib (SHA-256) | Cryptographic audit trail |
| tqdm | Progress bars for Monte Carlo runs |
| joblib | Parallel simulation runs |
| Streamlit | 4-page interactive dashboard |
| scikit-learn | Cross-validation, metrics, preprocessing |

### Multi-Agent Debate Stack
| Technology | Purpose |
|---|---|
| `pyautogen` (AutoGen) | Multi-agent orchestration — Bull, Bear, Judge round-robin |
| `claude-sonnet-4-20250514` | LLM powering all 3 debate agents via Anthropic API |

### Practical Extensions Stack
| Technology | Purpose |
|---|---|
| yfinance | NIFTY50, SENSEX, Bank NIFTY, VIX, Gold ETF — free |
| kiteconnect (Python SDK) | Zerodha Kite — portfolio auto-fetch — free personal tier |
| MFAPI.in | Mutual fund NAV — free, no auth |
| CoinGecko API | Crypto prices — free (30 calls/min) |
| Meta WhatsApp Cloud API | WhatsApp bot — free for user-initiated (NOT Twilio) |
| requests | HTTP client for all external API calls |

---

## 17. COMPLETION CRITERIA

| Milestone | Completion Condition | Status |
|---|---|---|
| GAP 1 Core | Bias detected in real-time with causal explanation + SHAP | ✅ Done |
| GAP 1 Full | Market data live, DB persistent, 13 endpoints, dashboard functional | 🔄 In Progress |
| Tiered Input System | Tier 1 at onboarding + Tier 2 Financial Profile page | ❌ Not Built |
| GAP 2 | Monte Carlo simulator: HOLD vs SELL with uncertainty bands | ❌ Not Built |
| GAP 3 + Debate | Counterfactual narrative + Bull/Bear/Judge with pros/cons | ❌ Not Built |
| GAP 4 | SHA-256 audit trail with tamper detection and audit report | ⚠️ Partial |
| Tax Layer | STCG/LTCG applied to all SELL simulations | ❌ Not Built |
| SIP Tracker | SIP pause cost simulated and alerted | ❌ Not Built |
| Kite Integration | Portfolio auto-fetched from Zerodha account | ❌ Not Built |
| Feedback Loop (V.A) | Outcome tracker + monthly retrainer | ❌ Not Built |
| Multi-Asset | MF, Gold, Crypto feed portfolio simulation | ❌ Not Built |
| WhatsApp Bot | User query returns full analysis via WhatsApp | ❌ Not Built |
| End-to-End Demo | Ramesh scenario runs fully — decision to audit hash | ❌ Not Built |
| Research Paper | 4 experiments documented, results reported | ❌ Not Built |

---

## 18. THE RAMESH SCENARIO (North Star Demo)

When this runs end-to-end without error, the project is demo-ready.

```
CONTEXT:
  Market crashes 12% in one week. Ramesh, 38, has ₹75,000 in HDFC Bank stock.
  He is down 18% on paper. 88% of the crowd is selling. He wants to sell.

PROFILE:
  Income: ₹80,000/month | EMI: ₹18,000 | School fees: ₹10,000/month (ends in 5 years)
  Rent paid: ₹12,000 | Monthly surplus: ₹40,000 | Emergency fund: YES
  This ₹75K = 8% of liquid net worth — small position relative to profile

STEP 1 — MARKET FETCH:  NIFTY (-12%), VIX (high), Bank NIFTY (-14%) auto-fetched
STEP 2 — CONTEXT:       Kite portfolio auto-fetched — no manual input
STEP 3 — BIAS DETECT:   loss_aversion detected, 87% confidence, SHAP top: unrealized_gl
STEP 4 — CAUSAL:        loss_aversion → +0.312 causal effect on SELL decision
STEP 5 — SIMULATE:      HOLD → ₹67,583 median in 20 years | SELL → ₹38,291 median
STEP 6 — DEBATE:
  Bull argues: ₹67,583 expected, 25-year horizon, surplus covers fees
  Bear argues: 18% loss already, market may fall further
  Round 2: Bull cites simulation evidence. Bear cites emergency risk.
  Judge:  HOLD wins — simulation evidence (50% weight) strongly favors holding
  Pros: [₹29,292 opportunity cost, 25yr horizon absorbs volatility, bias-driven]
  Cons: [Further downside possible, cash flow pressure]
STEP 7 — TAX:          SELL triggers STCG ₹1,800. Holding 4 months = LTCG, saves tax.
STEP 8 — EXPLAIN:      "Loss Aversion detected (87%). Selling now costs ₹29,292."
STEP 9 — SIP CHECK:    "Pausing your SIP costs ₹8,400 more over your horizon."
STEP 10 — AUDIT:       Full SHA-256 hash chain logged including debate transcript.
STEP 11 — WHATSAPP:    Ramesh receives 3-line summary on WhatsApp. (future phase)

RECOMMENDATION:  HOLD. Your 25-year horizon and stable income support this.
```

---

## 19. CONSTRAINTS

- ❌ Do NOT add more core datasets — 7 synthetic datasets are final
- ❌ Do NOT mix synthetic and real data blindly — keep purposes separate
- ❌ Do NOT build full dashboard before GAP 2 and GAP 3 backends exist
- ❌ Do NOT jump to deep learning — XGBoost + causal inference is the right tool
- ❌ Do NOT overbuild the UI — research completeness first, polish second
- ❌ Do NOT try to predict markets — this is a decision intelligence system
- ❌ Do NOT include real estate in automated fetch — no reliable free API in India
- ❌ Do NOT use Twilio for WhatsApp — Meta Cloud API directly is free and simpler
- ❌ Do NOT build WhatsApp bot before all 4 GAPs are complete (lowest priority)
- ❌ Do NOT treat auditability as the primary GAP 4 contribution (counterfactuals are primary)
