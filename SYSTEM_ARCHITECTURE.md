# SYSTEM ARCHITECTURE & COMPLETE REFERENCE
## Autonomous Financial Decision Intelligence System
### Causal Reasoning · Behavioral Bias Detection · Long-Horizon Simulation · Verifiable Audit Trail

---

# PART 1 — CORE SYSTEM ARCHITECTURE (Technical View)

---

## 1. SYSTEM OVERVIEW — THE BIG PICTURE

```
USER (Browser/App)
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Streamlit / React Dashboard)                            │
│  • User profile form  • Decision input form  • Portfolio viewer     │
│  • Real-time output panel                    • Audit log viewer     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │  HTTP / REST (JSON)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BACKEND API  (FastAPI + Uvicorn)                                   │
│  • /decision  • /portfolio  • /simulation  • /audit  • /user        │
└──────────┬──────────┬──────────┬─────────────────────────────────┬──┘
           │          │          │                                 │
           ▼          ▼          ▼                                 ▼
     [User DB]  [Decision    [Market       [Audit
     (SQLite/   Engine]      Data Layer]   Logger]
     PostgreSQL)                           (Audit DB)
```

---

## 2. USER INPUT — TWO TYPES OF USERS

### Type A — NEW User (First-Time)

```
User opens app
     │
     ▼
Fills onboarding form:
  ├── Name / User ID (generated or given)
  ├── Age
  ├── Monthly Income (INR)
  ├── Monthly Expenses
  ├── Investment Horizon (years)
  ├── Risk tolerance quiz (5-question assessment)
  └── Investment Goal (retirement / wealth growth)
     │
     ▼
Backend /user/register endpoint
     │
     ├── Validates all fields (range checks, type checks)
     ├── Calculates derived fields:
     │     ├── expense_ratio = expenses / income
     │     ├── monthly_surplus = income − expenses
     │     ├── financial_strategy (saving/balanced/credit/family_support)
     │     ├── has_emergency_fund (based on surplus trend)
     │     ├── investment_experience (novice / intermediate / expert)
     │     └── age_horizon_mismatch flag
     │
     ▼
SAVED TO: user_profiles table (persistent DB)
     │
     ▼
A NEW ROW is added — Synthetic data is NOT modified — DB is the live store
```

### Type B — RETURNING User (Makes a Decision)

```
User is logged in, views portfolio, enters a decision moment:
  ├── "Should I sell or hold my current position?"
  ├── Inputs current unrealized gain/loss %
  ├── Sees crowd action ratio (fetched real-time)
  └── Sees recent market return (fetched from market API)
     │
     ▼
Decision is sent via /decision endpoint
```

---

## 3. HOW INPUT IS HANDLED — STEP BY STEP

```
DECISION INPUT (user_id, unrealized_gl %, current action intent)
     │
     ▼
STEP 1: Input Validation Layer (FastAPI Pydantic models)
  ├── Type checks (float, int, string)
  ├── Range checks (unrealized_gl must be in [-1, +5])
  └── User existence verification (lookup user_profiles DB)

     │
     ▼
STEP 2: Market State Fetcher (Real-Time)
  ├── Calls Yahoo Finance API / NSE API / Alpha Vantage
  ├── Fetches: NIFTY50 recent return (1-day, 1-week)
  ├── Fetches: Current volatility (VIX or rolling std)
  ├── Fetches: Crowd action ratio (put/call ratio, news sentiment)
  └── Returns: market_context object
  → STORED IMMEDIATELY in: market_data_cache table (with timestamp)

     │
     ▼
STEP 3: Decision Context Builder
  ├── Loads user profile from user_profiles DB
  ├── Loads user's bias profile from bias_profiles DB
  ├── Merges: {user profile} + {market context} + {decision input}
  └── Creates unified decision_context object

     │
     ▼
STEP 4: Bias Detection Module (ML Model)
  INPUT: market_return_recent, unrealized_gl, crowd_action_ratio,
         market_regime, position_size_pct, user financial features
  MODEL: Gradient Boosting Classifier (pre-trained on synthetic_decisions.csv)
  OUTPUT: bias_type (none / disposition / loss_aversion / herd)
          confidence score (0.0 → 1.0)
          secondary_biases (overconfidence co-occurring)

     │
     ▼
STEP 5: Causal Reasoning Engine (DoWhy / CausalNex)
  INPUT: decision_context + bias_type
  ├── Loads pre-built Causal DAG (from training on synthetic data)
  ├── Estimates causal effect of bias on decision
  ├── Performs intervention: do(remove_bias) → what would rational decision be?
  └── OUTPUT: causal_effect_size, recommended_action

     │
     ▼
STEP 6: Long-Horizon Simulator (Monte Carlo)
  INPUT: user profile (age, horizon, risk) + decision (hold vs sell)
  ├── Loads 10,000 paths from synthetic_market_paths.npy
  ├── Runs 1,000 sampled paths for HOLD scenario
  ├── Runs 1,000 sampled paths for SELL scenario
  └── OUTPUT:
       ├── wealth_if_hold (median, 10th, 90th percentile)
       ├── wealth_if_sell (median, 10th, 90th percentile)
       └── opportunity_cost = wealth_hold − wealth_sell

     │
     ▼
STEP 7: Explainability Engine
  INPUT: all above outputs
  Generates human-readable explanation:
  ├── "You appear to be showing LOSS AVERSION bias (confidence: 82%)"
  ├── "If you HOLD → expected ₹67,583 in 20 years (median)"
  ├── "If you SELL → expected ₹38,291 in 20 years"
  ├── "Opportunity cost of selling: ₹29,292 (43% less wealth)"
  └── "RECOMMENDATION: Hold. Your financial profile supports this."

     │
     ▼
STEP 8: Audit Logger
  ├── SHA-256 hash of input data
  ├── SHA-256 hash of decision + bias type
  ├── SHA-256 hash of explanation + counterfactuals
  ├── Timestamp (ISO 8601)
  └── STORED IN: audit_logs table (append-only, immutable)
```

---

## 4. DATABASE ARCHITECTURE — WHERE EVERYTHING IS STORED

```
┌───────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                         │
│               (SQLite for dev, PostgreSQL for prod)       │
├──────────────────┬─────────────────────┬──────────────────┤
│  user_profiles   │  decisions_live      │  audit_logs      │
│  ─────────────   │  ──────────────────  │  ──────────────  │
│  user_id (PK)    │  decision_id (PK)    │  decision_id     │
│  age             │  user_id (FK)        │  user_id         │
│  monthly_income  │  timestamp           │  input_hash      │
│  monthly_expense │  market_return       │  decision_hash   │
│  risk_tolerance  │  unrealized_gl       │  explanation_hash│
│  investment_hori-│  crowd_ratio         │  timestamp       │
│   zon            │  bias_type           │  bias_detected   │
│  goal            │  confidence          │                  │
│  financial_strat │  decision (hold/sell)│                  │
│  has_emerg_fund  │  recommendation      │                  │
│  years_investing │  wealth_hold_20y     │                  │
│  ...             │  wealth_sell_20y     │                  │
├──────────────────┴─────────────────────┴──────────────────┤
│  market_data_cache         │  bias_profiles_live           │
│  ─────────────────         │  ────────────────────         │
│  cache_id (PK)             │  user_id (FK)                 │
│  timestamp                 │  disposition_strength         │
│  market_return_1d          │  loss_aversion                │
│  market_return_1w          │  herd_sensitivity             │
│  volatility                │  confidence (low/medium/high) │
│  vix_value                 │  n_decisions                  │
│  crowd_action_ratio        │  (updated as user makes       │
│  source (NSE/Yahoo)        │   more decisions over time)   │
└────────────────────────────┴───────────────────────────────┘
```

---

## 5. BIAS PROFILE — WHEN AND HOW IT IS BUILT

### The Core Insight

The ML bias detection model does NOT need the user's personal bias profile to detect bias. It infers bias purely from observable decision-time signals (market return, unrealized loss, crowd ratio, user financial profile). The bias profile is built separately, in parallel, and used for personalization and longitudinal tracking only.

### Step A — Bias Onboarding Quiz at Registration

Right after the financial profile is saved, the user completes a 5-question behavioral assessment:

```
Q1: "When your investment drops 10%, your first instinct is to:"
    a) Sell and protect what remains       → high loss_aversion signal
    b) Hold and wait for recovery          → low loss_aversion signal
    c) Buy more at the lower price         → contrarian signal

Q2: "When you see a stock up 8%, you usually:"
    a) Sell and take the profit            → high disposition signal
    b) Hold and wait for more upside       → low disposition signal
    c) Depends on target price             → rational signal

Q3: "How much do other investors' actions influence your decisions?"
    a) A lot — if everyone is selling, I get worried  → high herd signal
    b) Somewhat — I consider but verify myself        → medium herd signal
    c) Not at all — I stick to my own analysis        → low herd signal

Q4: "In the 2020 COVID crash (−38%), what would you have done?"
    a) Sold everything immediately          → high loss_aversion
    b) Sold some, held most                → moderate
    c) Held everything / Bought more       → low loss_aversion

Q5: "How often do you check portfolio during downturns?"
    a) Multiple times a day                → high anxiety / loss_aversion
    b) Once a day                          → moderate
    c) Weekly or less                      → low
```

Output stored in bias_profiles_live with confidence = 'low'.

### Step B — Profile Evolution Over Decisions

```
After each decision, detected bias_type updates the running estimate:
  new_estimate = (old_estimate × (n − 1) + new_observation) / n

Confidence upgrades:
  After quiz only:     'low'
  After 1 decision:    'medium-low'
  After 5 decisions:   'medium-high'
  After 20+ decisions: 'high'
```

### Bias Profile Status Table

| Stage | Bias Profile Status | Source | Confidence |
|---|---|---|---|
| Before registration | None | — | — |
| After financial form only | None | — | — |
| After onboarding quiz | Initial estimate | 5 questions | Low |
| After 1st real decision | Updated estimate | Quiz + 1 decision | Medium-Low |
| After 5+ decisions | Solid estimate | Quiz + decision history | High |
| After 20+ decisions | Accurate profile | Full behavioral history | Very High |

---

## 6. SYNTHETIC DATASETS — EXACT ROLES

```
SYNTHETIC DATA — Pre-generated, static, research-purpose
Never modified by live user input. Never written to at runtime.

synthetic_users.csv
├── PURPOSE:  Baseline for training personalization logic
├── USED IN:  Training bias detector · Calibrating simulator defaults
└── LIVE EQUIVALENT: user_profiles table in DB

synthetic_bias_profiles.csv
├── PURPOSE:  Ground truth for generating decision labels (training only)
├── USED IN:  Generating synthetic_decisions.csv labels ONLY
└── LIVE EQUIVALENT: bias_profiles_live table in DB

synthetic_decisions.csv
├── PURPOSE:  Labeled training data for bias detection ML model
├── USED IN:  Training GB classifier (one-time offline)
└── LIVE EQUIVALENT: decisions_live table in DB

synthetic_market_paths.npy
├── PURPOSE:  30-year Monte Carlo simulation backbone
├── USED IN:  Long-Horizon Simulator at EVERY inference call
└── LIVE COMPLEMENT: Real NIFTY data used for current context only

synthetic_counterfactuals.csv
├── PURPOSE:  Pre-computed what-if reference (validation + demos)
├── USED IN:  Validating simulator output format
└── LIVE EQUIVALENT: wealth_hold / wealth_sell in decisions_live

synthetic_audit_logs.csv
├── PURPOSE:  Demonstrating and validating audit trail structure
├── USED IN:  Development + testing of audit_logger module
└── LIVE EQUIVALENT: audit_logs table in DB (append-only)
```

Key Rule: Synthetic datasets are the school where the system learned. The live database is where the system does its actual daily job. They only combine during periodic model retraining (admin operation).

---

## 7. REAL-TIME MARKET DATA PIPELINE

```
SOURCES:
  ├── NSE India API (NIFTY50, sector indices)  — Primary
  ├── Yahoo Finance API (yfinance library)     — Fallback
  ├── Alpha Vantage API (intraday backup)      — Backup
  └── NewsAPI / FinBERT (sentiment → crowd proxy)

COMPUTATION:
  return_1d          = (close_today − close_yesterday) / close_yesterday
  return_1w          = (close_today − close_5d_ago) / close_5d_ago
  rolling_volatility = std(daily_returns[-20:]) × √252
  crowd_action_ratio = put/call ratio OR FinBERT sentiment score
  market_regime:
    r < −0.30         → 'extreme_crash'
    −0.30 ≤ r < −0.15 → 'severe_crash'
    −0.15 ≤ r < −0.05 → 'correction'
    −0.05 ≤ r ≤ 0.05  → 'normal'
    r > 0.05          → 'bull'
    r > 0.15          → 'euphoria'

CACHE: market_data_cache table (TTL = 15 minutes)
```

---

## 8. USER PORTFOLIO TRACKING

```
MANUAL INPUT:
  User enters: Stock symbol, Quantity, Buy price, Buy date

ON EVERY DASHBOARD LOAD:
  current_price         ← live from NSE API
  unrealized_gl_pct     = (current_price − buy_price) / buy_price × 100
  unrealized_gl_abs     = (current_price − buy_price) × quantity
  holding_period_months = months_between(buy_date, today)
  position_size_pct     = holding_value / total_portfolio_value × 100

ALTERNATIVE: User uploads CSV → system parses, validates, enriches with
             live prices, stores in portfolios table
```

---

## 9. USER DATA UPDATE FLOWS

```
UPDATE PROFILE:        PUT /user/{id}
  └── Updates user_profiles table, recalculates derived fields

ADD HOLDING:           POST /portfolio/add
  └── Inserts row in portfolios table, fetches live price immediately

NEW DECISION:          POST /decision
  └── Full 9-step pipeline → result in decisions_live
  └── bias_profiles_live updated (running average)
  └── Audit entry written (append-only)

VIEW HISTORY:          GET /decisions/{user_id}
  └── All past decisions, bias trend chart over time

VERIFY AUDIT:          GET /audit/{decision_id}
  └── Raw data + hashes → user can recompute SHA-256 to verify

MODEL RETRAIN (admin):
  When decisions_live accumulates 500+ real decisions
  └── Combined: synthetic_decisions.csv + decisions_live
  └── If accuracy improves → new model deployed (old version retained)
```

---

## 10. OUTPUT GENERATION & STORAGE

```
GENERATED PER DECISION:
  ├── bias_alert         "Loss Aversion Detected — 82% confidence"
  ├── recommendation     "HOLD"
  ├── wealth_hold        {median, p10, p90, trajectory array}
  ├── wealth_sell        {median, p10, p90, trajectory array}
  ├── opportunity_cost   ₹29,292
  ├── causal_explanation "Because VIX is high AND unrealized loss > 10%..."
  └── audit_entry        {input_hash, decision_hash, explanation_hash}

STORED IN:
  ├── decisions_live  (full record)
  └── audit_logs      (hashes only, tamper-proof, append-only)

RETURNED TO FRONTEND:
  JSON → Streamlit/React renders:
  ├── Bias alert banner (red if biased, green if rational)
  ├── Dual wealth trajectory charts with uncertainty bands
  ├── Opportunity cost card
  ├── Plain-English recommendation
  └── "How we decided this" section (SHAP + causal path)
```

---

## 11. COMPLETE END-TO-END FLOW SUMMARY

```
USER TYPES INPUT
     │
     ▼
INPUT VALIDATION (FastAPI Pydantic)
     ├──→ [NEW USER]     → Create profile + bias onboarding quiz → DB
     └──→ [RETURNING]    → Load profile from DB
     │
     ▼
FETCH REAL-TIME MARKET DATA (NSE API / yfinance)
Cached in market_data_cache (15-min TTL)
     │
     ▼
MERGE: User Profile + Market State + Decision Input = Decision Context
     │
     ▼
BIAS DETECTION MODULE
Model trained on synthetic_decisions.csv
Output: bias_type + confidence
     │
     ▼
BIAS PROFILE UPDATE (running average in bias_profiles_live)
     │
     ▼
CAUSAL ENGINE
Pre-built DAG from synthetic data
do-calculus: what if bias removed?
Output: causal effect + rational recommendation
     │
     ▼
LONG-HORIZON SIMULATOR
10,000 synthetic paths (synthetic_market_paths.npy)
Monte Carlo for HOLD vs SELL
Output: wealth distributions + opportunity cost
     │
     ▼
EXPLAINABILITY ENGINE
Human-readable explanation + counterfactual narratives
SHAP feature attribution (on-demand)
     │
     ▼
AUDIT LOGGER
SHA-256 hashes → audit_logs table (append-only)
     │
     ▼
JSON RESPONSE → Frontend renders output
     │
     ▼
ALL RESULTS STORED in decisions_live DB table
```

---

## 12. KEY ARCHITECTURAL PRINCIPLES

| Principle | Implementation |
|---|---|
| Synthetic data = training only | Never written to by user input; stays static |
| Live data = DB tables | All user interactions stored in SQL |
| Market data = cached API calls | 15-min TTL prevents rate-limiting |
| Audit logs = append-only | No UPDATE/DELETE on audit_logs table |
| Models = pre-trained + versioned | Loaded at startup, retrained periodically |
| Bias profiles evolve per user | Updated after every decision via running avg |
| Cold-start handled at registration | Onboarding quiz provides initial bias estimate |
| Bias detection needs no profile | ML model uses only observable signals |
| Separation of concerns | Each module is independent and separately testable |
| Recommendation is advisory | System distinguishes distress from bias; never overrides user |

---
---

# PART 2 — END-TO-END FLOW IN SIMPLE LANGUAGE

---

## What Is This System?

Imagine you are an individual investor in India. You have some money invested in stocks. One day the market drops sharply and you feel the urge to sell everything. This system acts like a smart financial advisor sitting right next to you. Before you press that sell button, it analyzes your decision, tells you whether you are making it out of fear or logic, shows you what will happen to your money 20 years from now if you sell versus if you hold, and explains exactly why it thinks so. All of this happens in seconds, and every recommendation the system makes is recorded in a tamper-proof log so it can never be disputed later.

---

## Step 1 — You Open the App for the First Time

You open the web application on your browser. You are asked to create a profile. You fill in basic details: your age, your monthly income, your monthly expenses, how many years you plan to stay invested, and what your goal is — retirement or growing your wealth.

The system takes this information and immediately calculates things you may not have thought about. It figures out how much money you are actually saving each month (your surplus). It checks whether your expenses are greater than your income (a real scenario for many people). It assigns you a financial health label — whether you are a healthy saver, living paycheck to paycheck, or managing a deficit through credit cards or family support. It also estimates your investment experience level based on your age.

All of this gets saved into the live database. Your profile now exists in the system permanently.

---

## Step 2 — The Bias Onboarding Quiz

Immediately after your financial profile is saved, you are shown 5 short behavioral questions framed as "Help us understand your investment style." Questions like "When your investment drops 10%, what is your first instinct?" and "How often do you check your portfolio during a downturn?"

Your answers give the system an initial estimate of your three behavioral tendencies: how strongly you show the disposition effect, how loss-averse you are, and how likely you are to follow the crowd. This initial estimate is stored with low confidence — the system knows it is just a rough picture based on 5 questions. Over time, as you make real decisions, this picture gets updated and becomes more accurate.

This step is mandatory because without it, the system has no starting bias profile when you make your first decision.

---

## Step 3 — You Come Back Later and Want to Make a Decision

A few weeks later, the market has fallen 8% in one day. You log back in. The app shows your portfolio — your current holdings, how much you are up or down, and what the market is doing right now.

You think: "Should I sell my position and cut my losses, or should I hold and wait it out?"

You enter this as a decision request: "I am considering selling. My current position is down 12%. What should I do?"

---

## Step 4 — The System Fetches Live Market Data

The moment you submit that decision, the system goes out to the internet and fetches real-time data from NSE or Yahoo Finance. It grabs today's NIFTY50 return, the overall market volatility level, and an estimate of what the majority of investors are doing right now — are most people selling or holding?

This data is stored temporarily in a cache for 15 minutes so that if 100 other users are also making decisions at the same time, the system does not flood the market data provider with thousands of requests.

---

## Step 5 — The System Builds Your Complete Picture

Now the system has everything it needs. It combines three things into one unified picture:

- Your profile — age, income, risk tolerance, investment horizon, financial health
- The market right now — today's return, volatility, crowd behavior
- Your decision input — how much you are down, what you are thinking of doing

This combined picture is called the Decision Context. Every analysis that follows is based on this.

---

## Step 6 — Bias Detection

This is the first and most important intelligence layer. The system runs a machine learning model that was trained on 5,000 synthetic decision records. This model has learned to recognize patterns that indicate behavioral biases purely from observable signals — it does not need your personal bias profile to work.

It looks at your decision context and asks: Is this person selling because it is rationally the right move, or because they are emotionally reacting?

The three biases it checks for:

- Disposition Effect — Are you selling because you are sitting on a gain and want to lock it in too early? Or holding a losing position too long because you cannot mentally accept the loss?
- Loss Aversion — Is the pain of your current loss causing you to panic and sell when a rational investor would hold?
- Herd Behavior — Are you selling simply because everyone else is selling, not because your own financial situation demands it?

The model outputs: "Loss Aversion detected — 82% confidence."

---

## Step 7 — Bias Profile Gets Updated

Once the bias type is detected, the system updates your personal bias profile in the database using a running average. If this is your first decision, your low-confidence quiz estimate gets its first real data point. After 5 decisions, your profile has meaningful confidence. After 20 decisions, it is highly accurate. This profile is then used in future decisions to make the causal analysis and explanations more personalized.

---

## Step 8 — Causal Reasoning

Finding a bias is not enough. The system needs to understand WHY that bias is affecting your decision and what would happen if the bias were removed.

The Causal Engine uses do-calculus from causal inference theory. Instead of just saying "you tend to sell when markets drop," it says "if we could remove your loss aversion, your decision would change from SELL to HOLD — and here is how much that change is worth." It also tells you what percentage of your urge to sell is driven by the bias versus genuine rational market response. For example: "68% of your sell urge is bias-driven. Only 32% is a rational response to current market conditions."

---

## Step 9 — Long-Horizon Simulation

Now the system answers the most important question: "What does this decision actually cost you over 20 years?"

It loads the synthetic_market_paths.npy file which contains 10,000 possible versions of the next 30 years of market returns, generated mathematically with realistic crash events built in. It picks 1,000 of those paths and runs two simulations:

If you HOLD: Most likely outcome: ₹67,583 in 20 years. Worst case: ₹31,000. Best case: ₹1,40,000.

If you SELL: You miss the recovery, pay transaction costs, and reinvest at lower rates. Most likely outcome: ₹38,291.

The opportunity cost of selling is ₹29,292 — 43% less wealth in 20 years.

This simulation uses synthetic market paths precisely because real future returns do not exist. The 30-year synthetic paths give statistically valid probability distributions of possible outcomes.

---

## Step 10 — Explanation Generation

All the numbers and analysis get translated into plain language:

"You are showing signs of Loss Aversion. The pain of your current 12% loss is making this feel more urgent than it actually is. Investors who sell during corrections like this one end up with 43% less wealth over 20 years. Your investment horizon is 18 years and your financial profile is stable — there is no immediate need to liquidate. Our recommendation is to HOLD."

It also generates a chart showing two wealth trajectories with shaded bands showing the range of possible outcomes.

---

## Step 11 — Audit Logging

Every decision the system makes is recorded before the result is shown to you. The system takes a cryptographic fingerprint (SHA-256 hash) of three things: the input data, the decision output, and the explanation. These hashes are stored in an append-only audit table. No one can modify or delete them. Six months from now, if you want to verify exactly what data the system used and what it told you, you can recompute the hash and confirm nothing was altered.

---

## Step 12 — The Result Comes Back to You

The frontend shows you:
- A bias alert at the top (red if biased, green if rational)
- Your two wealth trajectories on a chart
- The opportunity cost in rupees
- A plain-English recommendation with a confidence level
- A collapsible "How did we decide this?" section showing the causal chain

---

## What Happens to Your Data Over Time?

Every decision you make gets stored in the live decisions database. After several decisions, the system builds a personal bias profile for you from your actual observed behavior. If you consistently show loss aversion in down markets, your live bias profile gets updated to reflect that, making future detections even more accurate for you personally.

If you update your income, change your goal, or add new stocks to your portfolio, you do it through the Edit Profile or Add Holdings screens. Those changes update the database immediately and all future analyses automatically use the new values.

---

## Where Does Synthetic Data End and Live Data Begin?

| Synthetic Data | Live Data |
|---|---|
| Used to train the ML bias detection model | Real users stored in SQL database |
| Used to build the causal graph | Real decisions stored in decisions table |
| Provides 10,000 market paths for simulation | Real market prices fetched from NSE/Yahoo API |
| Provides ground truth for validation | Real audit logs in append-only audit table |
| Never modified by any user action | Only place that changes as users interact |

The synthetic datasets are like the school where the system learned. The live database is where the system now does its actual job.

---
---

# PART 3 — EVERY FORMULA IN THE SYSTEM (Why, When, Where, How)

---

## CATEGORY 1 — USER PROFILE GENERATION FORMULAS

---

### Formula 1 — Age-Based Income Generation

**What it is:**
```
If age < 35:  income ~ Uniform(30,000, 80,000)
If age 35–50: income ~ Uniform(60,000, 150,000)
If age > 50:  income ~ Uniform(100,000, 250,000)

Then: income = round(income / 1000) × 1000
```

**Why:** Real Indian salary data follows a career-stage progression. The rounding to nearest ₹1,000 mimics how people actually state their salaries — nobody says "my salary is ₹67,342", they say "₹67,000".

**When:** During synthetic data generation (once). For live users, replaced by their actual self-reported income.

**Where used:** Output monthly_income feeds into expense_ratio, monthly_surplus, financial_strategy, and the long-horizon wealth simulator.

---

### Formula 2 — Expense Ratio Distribution

**What it is:**
```
80% of users:  expense_ratio ~ Uniform(0.50, 0.85)   → healthy finances
15% of users:  expense_ratio ~ Uniform(0.90, 1.05)   → paycheck to paycheck
5% of users:   expense_ratio ~ Uniform(1.10, 1.30)   → spending more than earning
```

**Why:** A single flat distribution would never produce users who overspend, but roughly 15–20% of real households carry monthly deficits. If the bias detector never sees a user with a negative surplus, it cannot learn to distinguish genuine financial distress (which demands selling) from irrational panic selling (which is a bias).

**When:** At profile generation, once per user.

**Where used:** monthly_expense = monthly_income × expense_ratio, then feeds into monthly_surplus, financial_strategy, and bias detection features.

---

### Formula 3 — Monthly Surplus and Financial Strategy

**What it is:**
```
monthly_surplus = monthly_income − monthly_expense

If surplus > 5,000:          strategy = 'saving'
If 0 ≤ surplus ≤ 5,000:      strategy = 'balanced'
If −5,000 ≤ surplus < 0:     strategy = 'credit_card'
If surplus < −5,000:         strategy = 'family_support'
```

**Why:** One of the four research gaps is distinguishing genuine financial need to sell from behavioral bias-driven selling. A user with monthly_surplus = −₹8,000 who sells during a crash may be doing the right thing — they need liquidity. A user with surplus = ₹40,000 who sells the same day is almost certainly acting out of fear. Without this formula, the bias detector would flag both as biased, which is wrong.

**When:** At profile creation. For live users, updated whenever they edit income or expenses.

**Where used:** Directly as a feature in the bias detection model. In the explainability engine to contextualize recommendations.

---

### Formula 4 — Emergency Fund Probability

**What it is:**
```
If financial_strategy in ['saving', 'balanced']:
    P(has_emergency_fund = True) = 0.70

If financial_strategy in ['credit_card', 'family_support']:
    P(has_emergency_fund = True) = 0.20
```

**Why:** Emergency fund status is a critical contextual variable. Someone without a 3–6 month expense reserve has a legitimate reason to sell in a crisis — it is not irrational. Someone with a full emergency fund who still sells during a market drop is exhibiting loss aversion. Real RBI survey data supports these probability values.

**When:** At profile creation, sampled from a Bernoulli distribution.

**Where used:** As an input feature to bias detection. As a confounder variable in the causal reasoning engine.

---

### Formula 5 — Investment Experience

**What it is:**
```
years_investing = clip((age − 25) × Uniform(0.3, 0.8), 0, 30)

experience_level:
  years_investing ∈ [0, 2]   → 'novice'
  years_investing ∈ (2, 10]  → 'intermediate'
  years_investing > 10        → 'expert'
```

**Why:** A 45-year-old who started investing at 23 (22 years experience) responds to crashes very differently from a 45-year-old who started at 44 (1 year experience). The Uniform(0.3, 0.8) multiplier captures that not everyone starts investing as soon as they start working.

**When:** At profile generation.

**Where used:** As a feature in bias detection (novice investors show higher herd sensitivity). In the explainability engine to adjust language (simpler for novices, more technical for experts).

---

### Formula 6 — Age-Horizon Mismatch Detection

**What it is:**
```
If age < 35 AND investment_horizon < 10:  → 'young_short'
If age > 55 AND investment_horizon > 20:  → 'old_long'
Else:                                     → 'normal'
```

**Why:** A 28-year-old with a 5-year horizon is probably saving for a house down payment — their risk profile is completely different from a 28-year-old with a 25-year horizon. The system needs to handle these edge cases differently rather than treating everyone as a default wealth-growth investor.

**When:** At profile creation, re-evaluated if investment horizon is updated.

**Where used:** As a validation flag. In portfolio simulation for adjusted risk-based asset allocation. In bias detection — 'young_short' users selling during drops may be rationally reducing risk for a near-term goal.

---

## CATEGORY 2 — BEHAVIORAL BIAS PARAMETER FORMULAS

---

### Formula 7 — Disposition Strength (Beta Distribution)

**What it is:**

$$\text{disposition\_strength} \sim \text{Beta}(\alpha=3, \beta=2)$$

Mean = 3/(3+2) = **0.60**

**Why Beta(3,2):** The Beta distribution stays between 0 and 1, perfect for proportional tendencies. Beta(3,2) with mean 0.60 is slightly right-skewed, meaning most people have a moderate-to-high disposition effect. This matches Odean (1998) behavioral economics research — the disposition effect is widespread, not rare. Beta(2,5) would give mean 0.29, contradicting the literature.

**What it represents:** 0.0 = never sells winners early. 1.0 = always sells at first sign of profit regardless of fundamentals.

**When:** Once at synthetic profile generation. For live users, estimated from actual decision patterns over time.

**Where used:**
```
Decision rule: If disposition_strength > 0.6 AND unrealized_gain > 5%  → SELL (bias)
               If disposition_strength > 0.6 AND unrealized_loss > 5%  → HOLD (bias)
```
Also as a feature in the ML classifier training.

---

### Formula 8 — Loss Aversion Coefficient (Kahneman-Tversky Prospect Theory)

**What it is:**

$$\lambda \sim \text{Uniform}(1.0, 3.0)$$

The Prospect Theory value function:

$$v(x) = \begin{cases} x^{0.88} & \text{if } x \geq 0 \text{ (gain)} \\ -\lambda \cdot (-x)^{0.88} & \text{if } x < 0 \text{ (loss)} \end{cases}$$

**Why this range:** This λ (lambda) comes directly from Kahneman and Tversky's Prospect Theory (1979). Their research found the average λ ≈ 2.25 — meaning a ₹10,000 loss feels as painful as a ₹22,500 gain feels good. The range 1.0–3.0 covers the full population spectrum. The 0.88 exponent captures diminishing sensitivity — each extra ₹1,000 of gain feels less good than the previous.

**When:** At synthetic profile generation. For live users, estimated from historical sell decisions during drawdown periods.

**Where used:**
- Bias detection rule: If λ > 2.5 AND unrealized_loss < −10% → SELL (loss aversion bias)
- As a numerical feature in the ML classifier
- As the key exposure variable in the loss-aversion causal pathway

---

### Formula 9 — Herd Sensitivity (Beta Distribution)

**What it is:**

$$\text{herd\_sensitivity} \sim \text{Beta}(\alpha=2, \beta=4)$$

Mean = 2/6 = **0.33**

**Why Beta(2,4):** Left-skewed distribution meaning most people are NOT heavy herd followers — only the right tail (above 0.7) is strongly susceptible. This matches empirical findings: herd behavior is more common in retail investors during extreme events, but is not the default mode for most people.

**When:** At profile generation.

**Where used:**
- Decision rule: If herd_sensitivity > 0.7 AND crowd_action_ratio > 0.7 → SELL (herd bias)
- As a feature in ML classifier
- In the causal graph — herd sensitivity moderates the effect of crowd_action_ratio on the decision

---

## CATEGORY 3 — MARKET SIMULATION FORMULAS

---

### Formula 10 — Geometric Brownian Motion (GBM)

**What it is:**

$$r_t \sim \mathcal{N}(\mu, \sigma^2)$$

$$S_T = S_0 \times \prod_{t=1}^{T}(1 + r_t)$$

Where μ = 0.10 (10% expected annual return), σ = 0.20 (20% annual volatility).

**Why GBM:** GBM is the foundational model for stock price evolution, used in the Black-Scholes options pricing model. It models: returns in year 10 are independent of year 9 (no memory), percentage returns are normally distributed, and wealth can never go negative. Parameters μ=10%, σ=20% are calibrated to long-run Nifty50 historical performance.

**When:** Once at data generation time to create synthetic_market_paths.npy. At inference time, 1,000 paths are sampled from this pre-generated array.

**Where used:** Generating the 10,000 × 30 array. Feeding into Hold and Sell wealth projection formulas. Regime classification.

**How to read it:** Each row = one 30-year future. Path[0] might be [0.12, 0.08, −0.35, 0.18, 0.22, ...] meaning year 1: +12%, year 2: +8%, year 3: −35% (crash), year 4: +18% recovery, etc.

---

### Formula 11 — Market Crash Injection

**What it is:**
```
At year 10 and year 20 of each path:
crash_magnitude ~ Uniform(0.30, 0.50)
r[path, crash_year] = r[path, crash_year] − crash_magnitude
```

**Why:** Pure GBM almost never produces a −30% to −50% single-year crash because the probability from Normal(0.10, 0.20) is less than 0.01%. But major crashes happen roughly every 10 years (2008: −52%, 2020: −38%, 2000: −49%). Without injection, the 30-year simulation shows impossibly smooth wealth accumulation. The recovery after the injected crash is what makes HOLD far more valuable than SELL.

**When:** At data generation time, applied to all 10,000 paths.

**Where used:** Creates realistic crash regime scenarios. Forces simulator to include crash-and-recovery sequences. Makes the counterfactual analysis capture the most critical scenario.

---

### Formula 12 — Market Regime Classification

**What it is:**
```
r_t < −0.30             → 'extreme_crash'
−0.30 ≤ r_t < −0.15     → 'severe_crash'
−0.15 ≤ r_t < −0.05     → 'correction'
−0.05 ≤ r_t ≤ 0.05      → 'normal'
r_t > 0.05              → 'bull'
r_t > 0.15              → 'euphoria'
```

**Why these thresholds:** Standard classification boundaries from financial analysis. A >5% single-day drop is a correction trigger. A >15% drop from peak is technically a bear market. A >30% drop is a crash (matches 2008, 2020). A >15% single-period gain is euphoric.

**When:** During market_summary.csv generation AND on every live market state fetch from NSE API.

**Where used:** As a feature in bias detection. In explanations to contextualize the current market. As a confounder in the causal model.

---

### Formula 13 — Rolling Volatility

**What it is:**

$$\sigma_{rolling} = \text{std}(r_{t-19}, r_{t-18}, ..., r_t) \times \sqrt{252}$$

20-day window, annualized by √252 (252 trading days per year).

**Why √252:** Industry standard — volatility is always expressed on an annual basis for comparability. During a crash this spikes from ~15% to ~60–80%, signaling a stressed market state.

**When:** Every time real-time market data is fetched from NSE/Yahoo Finance.

**Where used:** As a feature in real-time bias detection. To set the width of uncertainty bands on the wealth chart (higher volatility = wider bands). Displayed as the "current market stress indicator."

---

## CATEGORY 4 — COUNTERFACTUAL WEALTH PROJECTION FORMULAS

---

### Formula 14 — Hold Scenario Wealth Projection

**What it is:**

$$W_{\text{hold}} = W_0 \times (1 + g) \times \prod_{t=1}^{H}(1 + r_t)$$

Where W₀ = ₹10,000 (standardized), g = unrealized_gain_loss (%), r_t = annual return from synthetic paths, H = min(20, investment_horizon).

**Why:** The (1+g) factor captures current unrealized P&L — if down 12%, they start with 88% of their investment still working. The multiplication per year (not addition) is critical — a 50% loss followed by a 50% gain does NOT get you back to zero; you end at 75% of where you started. This is the mathematics of compounding that most retail investors do not intuitively grasp.

**When:** For every decision, 1,000 sampled paths run through this formula, producing a distribution summarized as median, p10, p90.

**Where used:** Core output of the Simulator. Displayed as "If you HOLD: ₹X in 20 years." Used to compute opportunity cost.

---

### Formula 15 — Sell Scenario Wealth Projection

**What it is:**

$$W_{\text{sell}} = W_0 \times (1 + 0.9g) \times \prod_{t=1}^{H}(1 + 0.7r_t)$$

**Why the two coefficients:**
- 0.9g → 10% friction cost = ~1% brokerage + ~15.6% short-term capital gains tax + ~1% STT. Conservative but defensible.
- 0.7r_t → Reinvestment at 70% of market return because panic-sellers typically move to fixed deposits or bonds. Indian debt funds have historically returned ~7–8% vs NIFTY ~11–12%, ratio ≈ 0.65–0.72, rounded to 0.70.

**When:** Simultaneously with Hold formula, on the same 1,000 sampled paths.

**Where used:** Displayed as "If you SELL: ₹Y in 20 years." Mathematical proof behind the recommendation. Source of the "43% less wealth" figure.

---

### Formula 16 — Opportunity Cost

**What it is:**

$$\text{Opportunity Cost} = W_{\text{hold,median}} - W_{\text{sell,median}}$$

$$\text{Opportunity Cost \%} = \frac{W_{\text{hold}} - W_{\text{sell}}}{W_{\text{sell}}} \times 100$$

**Why:** The absolute rupee figure (e.g., ₹29,292) is far more emotionally impactful than saying "you should hold." It converts an abstract recommendation into a concrete financial consequence. Behavioral economists call this loss framing — by showing what the user gives up, the system uses the same loss aversion psychology it just detected, now to motivate better behavior.

**When:** Computed after both Hold and Sell simulations complete.

**Where used:** Displayed prominently as "Selling now will cost you ₹29,292 over 20 years." Stored in decisions_live. Used in the audit log explanation hash.

---

## CATEGORY 5 — BIAS DETECTION MODEL FORMULAS

---

### Formula 17 — Gradient Boosting Decision Rule

**What it is:**

$$\hat{y} = F(x) = \sum_{m=1}^{M} \gamma_m h_m(x)$$

Where h_m(x) = decision tree m (weak learner), γ_m = learning rate × leaf value, M = 100–500 boosting rounds, ŷ = predicted class (none / disposition / loss_aversion / herd).

**Input features (x):** market_return_recent, unrealized_gain_loss, crowd_action_ratio, market_regime (one-hot), position_size_pct, holding_period_months, crash_speed, risk_tolerance, investment_horizon, expense_ratio, financial_strategy.

**Why Gradient Boosting:** Neural network needs more than 5,000 training rows. Logistic Regression cannot capture non-linear interactions (loss aversion only triggers when BOTH loss is high AND λ is high). GB gives feature importance scores used later in SHAP explanations.

**When:** Trained once offline on synthetic_decisions.csv. Saved as .pkl, loaded at API startup. Retraining when enough real decisions accumulate.

**Where used:** Step 4 of decision pipeline — every user decision, runs in milliseconds.

---

### Formula 18 — SHAP Values for Explanation

**What it is:**

$$\phi_i = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F|-|S|-1)!}{|F|!} [f(S \cup \{i\}) - f(S)]$$

Where ϕᵢ = contribution of feature i to this specific prediction.

**In plain language:** Regular feature importance tells you what matters on average. SHAP tells you the contribution for THIS specific prediction — "for THIS user, with THIS market condition, the unrealized loss of −12% contributed +0.38 toward the loss_aversion prediction."

**When:** Computed on-demand when user clicks "Why did you decide this?" Too expensive to run automatically for every decision.

**Where used:** Powers the "How we decided this" section. Shown as a horizontal bar chart. Used to generate causal explanation text.

---

## CATEGORY 6 — CAUSAL INFERENCE FORMULAS

---

### Formula 19 — Backdoor Adjustment

**What it is:**

$$P(Y = y \mid do(X = x)) = \sum_z P(Y = y \mid X = x, Z = z) \times P(Z = z)$$

Where Y = decision outcome (hold/sell), X = bias indicator (present/absent), Z = confounders: {market_regime, has_emergency_fund, financial_strategy}.

**Why:** Without this, you only measure correlation. The backdoor adjustment controls for all observable confounders, isolating the pure causal effect of the bias itself.

**When:** Causal DAG and backdoor sets are pre-computed from synthetic data. At inference time, only the adjustment sum is computed.

**Where used:** Produces the "if we remove the bias, what would you decide?" counterfactual. Quantifies "Loss aversion is responsible for 68% of the sell decision."

---

### Formula 20 — Average Treatment Effect (ATE)

**What it is:**

$$\text{ATE} = E[Y \mid do(X=1)] - E[Y \mid do(X=0)]$$

Expected change in decision outcome when bias is set to present vs absent, after backdoor adjustment.

**Why ATE:** Gives a single number representing causal impact. ATE = 0.45 means: having the loss aversion bias present causes a 45 percentage point increase in the probability of selling compared to the same scenario without the bias.

**When:** Computed during causal model training on the full synthetic dataset. Pre-computed ATE retrieved and scaled by confidence at inference time.

**Where used:** In the research paper as the primary causal finding. In the explanation: "Under neutral conditions, a −12% loss causes 20% probability of selling. With loss aversion this rises to 65% — a 45-point increase caused by the bias alone."

---

## CATEGORY 7 — AUDIT AND CRYPTOGRAPHY FORMULAS

---

### Formula 21 — SHA-256 Cryptographic Hash

**What it is:**

$$h = \text{SHA256}(\text{string representation of data})$$

Example:
```
input_hash = SHA256(str({"user_id": 42, "market_return": -0.08, "unrealized_gl": -0.12}))
           → "a3f8c2d9e1b7..."  (64 hex characters, always)
```

**Why SHA-256:** Produces a 256-bit fingerprint. Change even one character in the input and the entire hash changes completely. SHA-256 specifically because MD5 and SHA-1 have known cryptographic collisions. SHA-256 has no known collisions and is the industry standard used in Bitcoin and all major blockchain systems.

**When:** Immediately after every decision is processed. Three separate hashes generated in sequence.

**Where used:**
- input_hash → proves what data the system received
- decision_hash → proves what the system decided and why
- explanation_hash → proves what explanation was given
- All stored in audit_logs with timestamp — any auditor can recompute and verify

---

## CATEGORY 8 — PORTFOLIO AND ASSET ALLOCATION FORMULAS

---

### Formula 22 — Asset Allocation

**What it is:**

$$\text{equity\_allocation} = 0.40 + (\text{risk\_tolerance} \times 0.50)$$

$$\text{debt\_allocation} = 1 - \text{equity\_allocation}$$

**Why:** At risk_tolerance = 0: 40% equity, 60% debt. At risk_tolerance = 1: 90% equity, 10% debt. The 40% floor ensures even the most conservative investor has meaningful equity exposure. The 90% ceiling ensures a minimal debt buffer. Matches standard Indian mutual fund recommendations.

**When:** During long-horizon simulation, once per decision evaluation.

**Where used:**
```
effective_return = equity_allocation × market_return + debt_allocation × 0.07
```
(7% = typical Indian debt fund return). Personalizes the simulation so two users facing the same market with different risk tolerances see different projected wealth figures.

---

### Formula 23 — Unrealized Gain/Loss Calculation

**What it is:**

$$\text{unrealized\_gl\%} = \frac{\text{current\_price} - \text{buy\_price}}{\text{buy\_price}} \times 100$$

$$\text{unrealized\_gl\_abs} = (\text{current\_price} - \text{buy\_price}) \times \text{quantity}$$

**Why both:** The bias detection model uses the percentage (biases are triggered by relative loss, not absolute). The explainability engine shows the absolute rupee amount (₹50,000 loss on a small portfolio is very different from the same loss on a large one).

**When:** Every time the user loads their portfolio dashboard. Current price fetched live from NSE API.

**Where used:** Primary input to bias detection. Input to Hold/Sell wealth projection. Displayed on portfolio dashboard with live refresh.

---

## FORMULA SUMMARY TABLE

| Formula | Expression | Used In |
|---|---|---|
| Monthly surplus | income − expense | Profile creation |
| Expense ratio | expense / income | Bias detection feature |
| Asset allocation | equity = 0.40 + (risk_tol × 0.50) | Simulator |
| GBM annual return | r_t ~ N(μ=0.10, σ=0.20) | Market path generation |
| Crash injection | r[crash_year] -= Uniform(0.30, 0.50) | Market path generation |
| Rolling volatility | std(returns[-20:]) × √252 | Live market fetch |
| Hold wealth | W₀ × (1+g) × ∏(1+r_t) | Simulator |
| Sell wealth | W₀ × (1+0.9g) × ∏(1+0.7r_t) | Simulator |
| Opportunity cost | W_hold_median − W_sell_median | Explainability |
| Unrealized GL% | (current − buy) / buy × 100 | Portfolio tracker |
| Bias profile update | (old × (n−1) + new_obs) / n | Post-decision update |
| Backdoor adjustment | Σ_z P(Y\|X,Z) × P(Z) | Causal engine |
| ATE | E[Y\|do(X=1)] − E[Y\|do(X=0)] | Causal engine |
| SHAP value | Σ_S [f(S∪{i}) − f(S)] × weight | Explainability |
| SHA-256 hash | SHA256(str(data_dict)) | Audit logger |
| Prospect Theory v(x) | x^0.88 (gain) / −λ(−x)^0.88 (loss) | Bias thresholds |

---
---

# PART 4 — COMPLETE TECHNICAL REFERENCE

---

## DECISION PIPELINE — FULL DETAIL

### Step 1 — Input Validation
```
RECEIVED: { user_id, unrealized_gl%, intended_action, timestamp }
  ├── user_id exists in user_profiles table?
  ├── unrealized_gl is float in range [−1.0, +5.0]?
  ├── intended_action is one of ['sell', 'hold', 'undecided']?
  └── timestamp is recent (not stale request)?
If any check fails → 400 Bad Request returned immediately
```

### Step 2 — Real-Time Market Data Fetch
```
SOURCES:
  Primary:  NSE India API
  Fallback: yfinance.download('NIFTY50', period='5d')
  Sentiment: NewsAPI + FinBERT

COMPUTED:
  market_return_1d    = (close_today − close_yesterday) / close_yesterday
  market_return_1w    = (close_today − close_5d_ago) / close_5d_ago
  rolling_volatility  = std(daily_returns[-20:]) × √252
  crowd_action_ratio  = put_call_ratio OR news_sentiment_sell_score
  market_regime       → 6 buckets as defined in Part 1

CACHING: market_data_cache table, TTL = 15 minutes
```

### Step 3 — Decision Context Assembly
```
User Profile (from user_profiles DB)
  + Market State (from market_data_cache)
  + Decision Input (unrealized_gl, position_size, holding_period)
  = Decision Context Object
```

### Step 4 — Bias Detection
```
MODEL:     Gradient Boosting Classifier
TRAINED:   synthetic_decisions.csv (5,000 labeled records)
FILE:      bias_detector_v1.pkl (loaded at API startup)
OUTPUT:    bias_type, confidence, secondary_biases
NOTE:      Does NOT require user's personal bias profile
```

### Step 5 — Bias Profile Update
```
Detected bias_type → updates bias_profiles_live:
  new_estimate = (old_estimate × (n − 1) + new_observation) / n

Confidence:  1 decision → medium-low | 5 → medium-high | 20+ → high
```

### Step 6 — Causal Reasoning Engine
```
METHOD:     Backdoor Adjustment (Pearl's do-calculus)
CONFOUNDERS (Z): market_regime, has_emergency_fund, financial_strategy
OUTPUT:     causal_effect_size (ATE), rational_decision, bias_contribution_pct
```

### Step 7 — Long-Horizon Monte Carlo Simulator
```
DATA:   synthetic_market_paths.npy [10,000 × 30]
SAMPLE: 1,000 paths per simulation run

HOLD:   W₀ × (1+g) × ∏(1 + equity_alloc × r_t + debt_alloc × 0.07)
SELL:   W₀ × (1+0.9g) × ∏(1 + 0.7 × (equity_alloc × r_t + debt_alloc × 0.07))

OUTPUT per scenario: median, p10, p90, full trajectory array
OPPORTUNITY COST: W_hold_median − W_sell_median
```

### Step 8 — Explainability Engine
```
Generates:
  1. Bias alert string + confidence
  2. Wealth comparison (₹ figures, 20-year)
  3. Contextual statement (uses surplus, emergency fund)
  4. Causal chain (bias → decision → outcome)
  5. SHAP bar chart (on-demand)
  6. Recommendation + confidence
  7. Chart data (dual trajectory arrays for frontend)
```

### Step 9 — Audit Logger
```
THREE HASHES:
  input_hash       = SHA256(str({user_id, market_return, unrealized_gl, crowd_ratio}))
  decision_hash    = SHA256(str({decision_id, bias_type, confidence, rational_decision}))
  explanation_hash = SHA256(str({recommendation, wealth_hold, wealth_sell, opp_cost}))

STORED: audit_logs table — APPEND-ONLY, no UPDATE or DELETE permitted
```

---

## FULL DATABASE SCHEMA

```
user_profiles:
  user_id (PK), age, monthly_income, monthly_expense, monthly_surplus,
  expense_ratio, risk_tolerance, investment_horizon, goal,
  financial_strategy, has_emergency_fund, age_horizon_mismatch,
  years_investing, investment_experience, created_at, updated_at

bias_profiles_live:
  user_id (FK), disposition_strength, loss_aversion, herd_sensitivity,
  confidence, n_decisions, quiz_source, last_updated

decisions_live:
  decision_id (PK), user_id (FK), timestamp, market_return_recent,
  rolling_volatility, unrealized_gain_loss, crowd_action_ratio,
  market_regime, position_size_pct, holding_period_months,
  bias_type, confidence, secondary_biases, causal_effect_size,
  bias_contribution_pct, rational_decision, recommendation,
  wealth_hold_median, wealth_sell_median, wealth_hold_p10,
  wealth_hold_p90, wealth_sell_p10, wealth_sell_p90, opportunity_cost

audit_logs: [APPEND-ONLY — NO UPDATE OR DELETE]
  log_id (PK), decision_id (FK), user_id (FK),
  input_hash (CHAR 64), decision_hash (CHAR 64),
  explanation_hash (CHAR 64), timestamp, bias_detected

market_data_cache:
  cache_id (PK), fetched_at, expires_at (TTL 15 min),
  market_return_1d, market_return_1w, rolling_volatility,
  crowd_action_ratio, market_regime, source

portfolios:
  portfolio_id (PK), user_id (FK), symbol, quantity,
  buy_price, buy_date, current_price, unrealized_gl_pct,
  unrealized_gl_abs, holding_period_months, position_size_pct,
  last_price_update
```

---

## TECH STACK

```
FRONTEND       Streamlit (research demo) / React (production)
BACKEND API    FastAPI + Uvicorn (Python)
DATABASE       SQLite (development) / PostgreSQL (production)
BIAS DETECTOR  scikit-learn / XGBoost (Gradient Boosting Classifier)
CAUSAL ENGINE  DoWhy + CausalNex + NetworkX
SIMULATOR      NumPy (vectorized Monte Carlo)
EXPLAINABILITY SHAP + Plotly + Matplotlib
PERSISTENCE    joblib (.pkl model files, versioned)
MARKET DATA    NSE India API / yfinance / Alpha Vantage
SENTIMENT      NewsAPI + FinBERT (HuggingFace)
CRYPTOGRAPHY   hashlib (Python built-in SHA-256)
DEV TOOLS      Jupyter · pytest · black · flake8
```

---

## FORMULA USAGE MAP

| Formula | Training | Inference | Explanation | Audit |
|---|---|---|---|---|
| GBM market paths | ✅ Generate data | ✅ Simulate futures | — | — |
| Crash injection | ✅ Generate data | ✅ Realistic scenarios | — | — |
| Beta distributions | ✅ Bias profiles | — | — | — |
| Prospect Theory λ | ✅ Decision labels | ✅ Bias detection | ✅ Explain why | — |
| Backdoor adjustment | ✅ Causal DAG | ✅ Remove bias effect | ✅ Causal chain | — |
| ATE | ✅ Effect size | ✅ Quantify bias | ✅ "68% of urge" | — |
| Hold/Sell formulas | ✅ Counterfactuals | ✅ User's projection | ✅ Display wealth | ✅ Hash |
| Opportunity cost | ✅ Baseline | ✅ Per decision | ✅ "₹29,292 cost" | ✅ Hash |
| SHAP values | ✅ Model training | On-demand | ✅ Bar chart | — |
| SHA-256 | — | ✅ After every decision | — | ✅ All entries |
| Rolling volatility | — | ✅ Live market fetch | ✅ Stress indicator | — |
| Asset allocation | — | ✅ Personalized sim | ✅ Portfolio context | — |
