# Folium: master reference

The single source of truth for what Folium is, how it works, every formula it uses, and where the project stands. Last updated **2026-10-08**. Companion documents are listed in §17; everything else that used to describe the project has been retired (kept in the separate `Major Project` folder).

---

## 1. What Folium is

Folium is a web app that helps an Indian retail investor decide **sell, hold or buy more** on one holding, judged against their **whole financial picture**.

For each decision it:

1. reads the moment and names the behavioural pattern most likely behind it (loss aversion, herd behaviour, disposition effect, or rational);
2. projects both choices, hold and sell, across the investor's own horizon, in rupees and **after tax**;
3. explains what it found in plain English or Hindi, and what pushes people towards that action;
4. gives a recommendation, based on the evidence only;
5. seals the analysis into a tamper-evident record the investor can verify.

It is for information and education, not investment advice. The product rules: no model names or accuracy figures in the UI, confidence shown as High / Medium / Low, plain titles on the live-analysis steps, and an explicit security and data-privacy story.

### Status at a glance (2026-10-08)

| Area | State |
|---|---|
| Accounts: sign-up, email verification, login, "keep me signed in", password reset, two-step verification (TOTP + backup codes + recovery), profile with re-verification | Built, tested |
| Google sign-in | Backend built and tested with mocks; **not finished in the web app** (the callback returns JSON instead of returning the browser to the app) |
| Portfolio: shares, mutual funds (live prices), gold (live), FDs, savings, property, loans, rent, monthly SIP | Built, tested |
| Analysis pipeline with live progress (SSE) | Built, tested |
| Bias model **v4.1**, simulation **v2**, cause-and-effect **v4**, explanation engine (English + Hindi, HTML/PDF reports) | Built, tested |
| Tamper-evident audit chain with "verify my record" (**B1**) | Built, tested |
| Account deletion with a 30-day grace period, and data export (**B2**) | Built, tested |
| Comment reading and "both sides" (**B3**), with optional Gemini help | Built, tested (the Gemini path is tested with a stand-in; it runs live once `AI_HELP` and a key are set) |
| Admin panel | Pending (only the MFA-reset endpoint exists) |
| Deployment, repo move to `ParamShah77/Folium`, CI | Pending |

Tests: **255** backend (needs PostgreSQL + Redis; 162 of them run without a database under `backend/tests/unit`), **334** in the root `tests/` folder (models, data, explainer, simulator, causal; no database; 329 run, 5 need an AI key and are skipped without one), **17** frontend.

---

## 2. Architecture

```
Browser (React SPA, :3000)
   │  /v1/*  (Vite proxy in dev: one origin, so cookies + CSRF stay simple)
   ▼
FastAPI backend (:8000)  ── auth, portfolio, decisions, market, reports
   │            │
   │            └── background pipeline: bias → simulation → explanation → recommendation → audit
   │                       │ calls research code in place via backend/core/ml_bridge.py
   │                       ▼
   │                 src/  (bias_model_v4, simulator_v2, causal_v4, explainer, …)  +  models/, results/, data/
   ▼
PostgreSQL 18 (native service, :5432)   Redis / Memurai (:6379)
 per-user row-level security              token blacklist, rate limits, SSE event bus
```

**The bridge.** The backend never re-implements the ML. `backend/core/ml_bridge.py` is the only place `backend/` reaches into `src/`: it puts the repo root on `sys.path`, imports lazily (the ML libraries take ~2 s and ~400 MB to import), moves blocking work to a thread, and holds the vocabulary mapping (`disposition` ↔ `disposition_effect`, `herd` ↔ `herd_behavior`). The ML libraries are optional at import time; a missing install fails an analysis with a clear error, never silently falls back to placeholder numbers.

**Python 3.13 everywhere.** `dowhy 0.14` caps scipy at 1.15.3 below Python 3.13, which would change the scipy version the model artefacts were built under.

### Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115, Pydantic 2.10, asyncpg (PgBouncer-safe settings), Alembic, structlog, slowapi |
| Auth | PyJWT (RS256), bcrypt (cost 12), zxcvbn, pyotp, Authlib (Google), Fernet (cryptography) |
| Data | PostgreSQL 18, Redis-compatible store (Memurai on Windows) |
| ML | numpy 2.4.2, pandas 3.0.1, scipy 1.17.1, scikit-learn 1.8.0, xgboost 3.2.0, shap 0.51.0, dowhy 0.14, networkx 3.6.1, pgmpy 1.0.0, yfinance 0.2.66, jinja2 3.1.6, textstat 0.7.13, reportlab 5.0.1 (pinned in `backend/requirements-ml.txt`; `scripts/verify_ml_env.py` checks them) |
| Frontend | Vite 8, React 19, TypeScript, Tailwind 4, Radix-based components in the shadcn style, TanStack Query, React Hook Form + Zod, Recharts, sonner |
| Environment | Python venv at `D:\FolioEnv\venv313`; `scripts/with_env.py` loads `.env` into any command |

---

## 3. Repository map

| Path | Contents |
|---|---|
| `backend/` | The product API. `api/v1/` routes, `auth/`, `core/` (pipeline + steps), `services/` (portfolio, prices, market, email, account deletion), `db/migrations/` (Alembic, 0001–0012), `schemas/`, `middleware/`, `tests/` |
| `frontend/` | The React app (`src/pages`, `src/components`, `src/lib`, `src/providers`, `src/test`) |
| `src/` | The models and engines. **Current:** `dataset_v4.py`, `bias_model_v4.py`, `simulator_v2.py`, `causal_v4.py`, `explainer.py`, `explanation_templates.py`, `explanation_report.py`, `llm_polish.py`, `market_data.py`. **Earlier research versions, kept as rollback or reference:** `bias_detector.py` (v3), `simulator.py` (v1), `causal_inference.py`, `causal_structure.py`, `causal_utils.py`, `data_preparation.py`, `integration.py`, `database.py`, and `api.py` / `dashboard.py` (the old Streamlit prototype, not part of the product) |
| `models/` | `bias_detector_v4.json` + `.meta.json` (current), `bias_detector_v4.0.*` (previous), `bias_detector_xgboost_v3.pkl` and older (rollback) |
| `data/v4/` | `decisions_v4.csv` (20,000 cases), `market_history.csv` (real NIFTY/VIX), `DATASET_CARD.md`, `v4.0/` (previous dataset) |
| `data/sim_v2/` | `monthly_history.csv`: real NIFTY and gold-in-rupee history for the simulation |
| `results/` | `causal_v4.json`, evaluation JSONs, and `reports/` (the three model reports) |
| `scripts/` | `with_env.py`, `seed_demo.py`, `purge_deleted_accounts.py`, `train_bias_v4.py`, `evaluate_simulator_v2.py`, `evaluate_explanations.py`, `verify_ml_env.py`, `generate_dev_keys.py`, and earlier research scripts |
| `tests/` | Root tests for the models and engines |
| `notebooks/`, `archive/` | Research notebooks and archived scripts and results |
| `Dockerfile.backend`, `docker-compose.yml` | Container definitions for a later deployment (not used locally) |

---

## 4. The investor's inputs

Two tiers, from the original design.

### Tier 1: required at sign-up

| Input | Used for |
|---|---|
| Age | Model input |
| Monthly income, after tax | Surplus, model input |
| EMIs, rent paid, education fees (and the year the fees end) | Fixed monthly outflow |
| Emergency fund (yes/no) | Model input; shapes how a sale is read |
| Risk tolerance (five-question quiz, scored 0–1) | Model input |
| Horizon (years until the money is needed) | Simulation length, model input |
| Investing style and main goal | Profile |

Risk quiz: five questions, each answer scores 0–3; `risk_tolerance = total / 15`, rounded to 2 places.

### Tier 2: optional (Portfolio page)

| Input | Notes |
|---|---|
| Shares (symbol, exchange, quantity, average buy price) | Priced live, NSE `.NS` / BSE `.BO` via Yahoo Finance |
| Mutual funds (scheme code, units, average NAV) | Searched and priced via MFAPI.in |
| Gold (grams, buy price per gram) | Valued at the live international price |
| Fixed deposits, savings and cash | Typed in |
| Property value, home loan, other loans | Typed in |
| Rent received, monthly SIP | Typed in |

Not collected: crypto, credit-card balances, insurance premiums, groceries and utilities, vehicle details.

### Derived figures

```
committed outflow (monthly_expense) = EMIs + rent paid + education fees
monthly surplus  = income + rent received − committed outflow

liquid assets    = stocks + mutual funds + gold + fixed deposits + savings
net worth        = liquid + property − home loan − other loans

equity share     = (stocks + mutual funds) / liquid        (funds are counted as equity)
position share   = value of the holding / liquid
gold value       = grams × price per gram
price per gram   = GC=F (USD per troy ounce) × INR=X (₹ per USD) / 31.1034768
```

Gold uses the international price, before Indian import duty and GST, and the app says so. If live gold is unavailable, the buy price is used. A holding without a live price is valued at its average cost, and the page shows "price unavailable". All prices are cached for 15 minutes; a failed lookup never breaks a page.

Sensitive fields (income, EMIs, rent, education fees, emergency fund) can be **filled in once** from the profile form. Changing a value that exists requires the password (and an authenticator code if two-step is on), and every change is logged.

---

## 5. How an analysis runs

1. The investor picks a **holding**, their **action** (sell / hold / buy more), optionally the months held and a free-text reason.
2. `POST /v1/decisions/analyze` captures the **market context** (NIFTY 1-month return, 30-day volatility, India VIX; a user-stated trend wins over the derived one), the **portfolio snapshot** (`portfolio_context`), and the stock's measured **beta and own swings**. All three are stored on the decision, so a re-run reproduces the original inputs. It returns `202` with the decision id.
3. A background pipeline runs five steps, each publishing `running` / `done` events to Redis. The browser opens `GET /v1/decisions/{id}/stream` (server-sent events). The server replays the event backlog first, so a reload mid-analysis still shows the full history, and de-duplicates by sequence number.

| Step | What it does | Writes |
|---|---|---|
| 1 Reading your decision | Reads the comment (§7.8), then bias model v4.1 | `comment_facts`, `bias_detected`, `bias_confidence`, `explainer_output.bias` |
| 2 Projecting the future | Simulation v2 | `hold/sell_*`, `opportunity_cost_inr`, `simulation_curves` |
| 3 Explaining | Cause-and-effect v4 + explanation engine (EN + HI) + the comment against the reading | `causal_effect`, `explainer_output` |
| 4 Forming a recommendation | Evidence rules (§7.5), then both sides (§7.8) | `recommendation`, `debate_transcript` |
| 5 Saving a secure record | Audit chain (§7.7) | `audit_logs` row |

A failing step marks the decision `failed` and publishes a `failed` event. Step functions return a result; the orchestrator owns status, events and persistence, and refuses steps that try to write its columns. Each step reads the decision row afresh, so later steps see earlier steps' writes.

**Missing inputs are disclosed, never hidden.** Profile gaps are filled with the model's training medians and listed in `assumed_defaults`; portfolio gaps in `fixed_inputs`. The result page's "How this was worked out" shows both.

### Edge cases and how they are handled

| Situation | Behaviour |
|---|---|
| No live price for a holding | Valued at its average cost, shown as "price unavailable"; for a new analysis the investor enters today's price. A price outage never blocks a page |
| No live market data (Yahoo Finance down or slow) | A calm market is assumed (the median real trading day: NIFTY +1.0% in a month, VIX 16.9) and the page says so; market capture is bounded by a timeout |
| Profile or portfolio gaps | Filled with the model's training medians and listed under "How this was worked out" |
| A stock with too little price history | The median NIFTY 50 stock (beta 1.0, own swings 21%) is used and disclosed |
| No horizon given | 20 years, stated on the page; horizons are capped at 30 |
| Paying out more than is earned | `surplus_ratio` is clipped at −2; households like this exist in the training data (0.7%), and a stated cash need reads a sale as rational |
| Very large position (above ~35% of liquid assets) | A sale can be read as rational rebalancing rather than a bias |
| Goal very near (horizon of 3 years or less) with a gain | A sale can be read as rational |
| Education fees ending | Surplus rises from the end year in the simulation, in both futures |
| Page reloaded or opened late during an analysis | The event backlog is replayed, so the full progress history appears; if the live stream cannot open, the page polls |
| Two analyses finishing at once | A per-investor advisory lock keeps the audit chain linear |
| An unverified account registering again | The unverified record is replaced; a verified email returns "already registered" |
| Account scheduled for deletion signing in | Told the deletion date and offered "Keep my account" until the 30-day grace period ends; afterwards the account is gone |
| A comment the rules can't read, or AI help failing | The rules' reading is used (possibly empty); a Gemini reply is discarded unless every quote is word for word from the comment |
| Explanation or AI rewording fails | The template text is used; an analysis never fails because of its wording |
| Hindi PDF requested | Refused with an explanation; the HTML report is offered |

---

## 6. Data and database

### Tables

| Table | Purpose | Row-level security |
|---|---|---|
| `users` | Account and Tier 1 profile; deletion schedule (`purge_after`, `anonymised_at`); AI-help consent | no (read by the auth path) |
| `refresh_tokens`, `mfa_backup_codes`, `mfa_recovery_requests` | Sessions and two-step recovery | no |
| `profile_change_log` | Every profile change, with the old value hashed | **yes** |
| `decisions` | One row per analysis: inputs, market snapshot, portfolio snapshot, comment reading, every model output | **yes** |
| `audit_logs` | The per-investor hash chain; append-only | **yes** |
| `portfolios` | Shares and mutual funds | **yes** |
| `financial_profiles` | Gold, deposits, savings, property, loans, rent received, monthly SIP | **yes** |
| `bias_profiles`, `market_cache`, `sip_registrations`, `kite_tokens` | Reserved | partly |

Row-level security: the app connects as **`app_user`**, a non-superuser (a superuser silently bypasses RLS), and every user-owned query runs inside a transaction that sets `app.current_user_id`. Policies use `user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid`, with `FORCE ROW LEVEL SECURITY`. Another user's row is invisible, so a foreign id returns 404, not 403. `audit_logs` has `DO INSTEAD NOTHING` rules for UPDATE and DELETE.

### Migrations (Alembic, run as the owner role `finai` through `ALEMBIC_DATABASE_URL`)

| # | Adds |
|---|---|
| 0001–0002 | Users; refresh tokens, MFA backup codes, recovery requests, profile change log |
| 0003 | `decisions` |
| 0004 | `audit_logs` (append-only rules) |
| 0005–0006 | Portfolios, bias profiles, market cache; SIP and Kite tables |
| 0007 | RLS policies, `admin_stats_view`, least-privilege `app_user` |
| 0008 | Market features on decisions (`nifty_1m_return`, `nifty_volatility_30d`, `market_data_source`) |
| 0009 | Tier 1 outflows on users; `financial_profiles`; fractional quantities and fund fields on `portfolios`; `holding_id` and `portfolio_context` on decisions |
| 0010 | `financial_profiles.monthly_sip` |
| 0011 | `users.purge_after`, `users.anonymised_at` (account deletion) |
| 0012 | `decisions.comment_facts`, `users.ai_consent` (comment reading, AI-help consent) |

---

## 7. The models

### 7.1 Training data: dataset v4.1 (`src/dataset_v4.py`)

20,000 investor decisions built on **real NIFTY 50 and India VIX** for 10 Jun 2008 to 5 Oct 2026 (4,475 trading days, 4,255 used). Each case has a real trading day, a household (income, EMIs, rent, education fees, emergency fund, risk, horizon), a portfolio (shares, funds, gold, FDs, savings, property, loans, rent received), the investor's **action** (sell / hold / buy more), a gain or loss derived from the real NIFTY move over the holding period × the stock's beta plus stock-specific noise, and a label.

**Labels are motives, not rules.** Each investor has hidden tendencies (loss aversion, herd sensitivity, disposition), partly explained by what the app can see. The situation decides which bias motives can apply; they compete with a rational motive; the winner sets the action and **is the label**. So the same sale can be rational or biased, and the model must infer which. Hidden tendencies are stored as `latent_*` columns and are never model inputs.

| Pattern | Motive | Action | Applies when |
|---|---|---|---|
| Loss aversion | panic | sell | at a loss, NIFTY down 2%+ over the month, and fear high (VIX ≥ 20 or a correction/crash) |
| Loss aversion | refusal | hold | the position is down 25% or more |
| Disposition effect | sell winner | sell | up 8%+ in a normal or rising market |
| Disposition effect | hold loser | hold | down 5–25% in a normal or rising market |
| Herd behaviour | sell into fear | sell | VIX ≥ 22 or NIFTY down 5%+ over the month |
| Herd behaviour | buy into a rally | buy more | NIFTY up 4%+ over the month |
| Rational | stay the course, add regularly, buy value, average down, cut a loss, rebalance, goal near, **needs cash** | any | the investor's own situation explains the action |

Version 4.1 (2026-10-08) added stretched households (8.2% of borrowers with EMIs above 60% of income, 0.7% paying out more than they earn), 44% without an emergency fund, and cash shocks (6.8% of decisions), so a forced sale can be read as rational. Labels: rational 55.7%, herd 19.6%, disposition 14.7%, loss aversion 10.0%. Full detail: `data/v4/DATASET_CARD.md`.

Consequence of the definitions, which is correct and not a gap: in a calm market herd behaviour and panic-driven loss aversion cannot occur, so a calm-market analysis can only read disposition effect, loss-aversion "refusal" (a deep loser) or rational.

### 7.2 Bias model v4.1 (`src/bias_model_v4.py`)

**Inputs (22 features):** the action (3 flags); gain or loss; holding period; NIFTY 1-month return, VIX, 30-day volatility; three flags for which patterns the definitions permit here (`allows_*`); age, horizon, risk tolerance; surplus ratio; emergency fund; position share, equity share, gold share; owns property; debt ratio; and `cash_need_stated` (the investor said they need the money, read from their comment, §7.8).

```
surplus_ratio = clip( (income + rent received − committed outflow) / income , −2, 2 )
debt_ratio    = clip( loans / (liquid assets + property) , 0, 5 )
owns_property = 1 if property value > 0
```

**Model:** XGBoost, 402 trees, depth 5 (tree count from 5-fold cross-validation with early stopping). A **guard** sets to zero any pattern the definitions rule out. **Confidence** is the chosen pattern's probability through a centred isotonic curve fitted on out-of-fold predictions and weighted to real market frequencies, so it means what it says. Shown as **High ≥ 0.85, Medium ≥ 0.65, Low below**. **Explanations** are exact TreeSHAP values for the *chosen* pattern, summed into 18 plain drivers (they add up to the model score within 1e-5). Stored as native XGBoost JSON, not a pickle.

**Years of investing is deliberately not an input**: the app doesn't collect it, and adding it gained only 0.5 points.

**Results (test set, re-weighted to real market frequency):**

| | v4.1 | v3 (previous) |
|---|---|---|
| Accuracy | **87.9%** | 53.4% |
| Macro-F1 | **0.840** | 0.309 |
| Calibration error | 0.014 | 0.254 |
| Sense checks passed | **21 / 21** | 5 of 13 scenarios |
| Answer depends on the action | 84% of cases | never |
| Forced sales read as rational | 72% (91% when the need is stated) | — |

High confidence is right 98.7% of the time (68% of analyses), Medium 74%, Low 62%. A rules-only baseline reaches 85.2% and a model that also sees the hidden tendencies 90.0%, so v4's value is judgement and calibrated confidence rather than raw accuracy. On the 56% of cases that need judgement, accuracy is 78.3%; a model trained only on 2008–2019 scored 86.5% on 2020–2026, a period it had never seen. Full evaluation: `results/reports/BIAS_MODEL_V4.md`. Rollback: `BIAS_MODEL_VERSION=v3`.

### 7.3 Simulation v2 (`src/simulator_v2.py`)

Compares **holding** with **selling** across the investor's own horizon (1–30 years; 20 only when none is given, and the page says so), on the **same** simulated markets for both choices.

**Futures.** Each simulated month is a real month of NIFTY (plus a 1.25% dividend yield) and gold in rupees, drawn in **12-month blocks** that wrap around the 2007–2026 history ("circular" resampling), preserving the real link between shares and gold and keeping crashes with their recoveries. The swings are kept but **typical growth is reset** to stated long-run rates:

| Asset | Growth | Notes |
|---|---|---|
| Shares (NIFTY 50) | 11% | Median year, with dividends |
| Gold (rupees) | 9% | |
| Fixed deposit | 6.75% | Before tax |
| Savings account | 3% | Before tax |

**The holding.** A stock moves with the market by its own **beta** plus **company-specific swings**, both measured from its last 10 years of monthly prices when the analysis is submitted (default when unavailable: beta 1.0, own swings 21%, the median NIFTY 50 stock, and the page says so). Its typical growth: `FD rate + beta × (share growth − FD rate)`. A mutual fund tracks the market within 3% a year.

**Selling.** Charges of 0.15% plus tax, and the proceeds go into the investor's own FDs, savings and gold in their **current split**. The comparison is **in hand after tax**: each year shows what each path would yield if cashed in then.

**Tax (FY 2025-26, new regime):**

| Item | Rule |
|---|---|
| Equity, held under 12 months | 20% short-term |
| Equity, held 12 months or more | 12.5% on gains above ₹1,25,000 |
| Gold | 12.5% after 24 months |
| FD and savings interest | At the investor's slab rate every year |
| Cess | 4% on top |

Slab rate for extra interest income: taxable income = gross − ₹75,000 standard deduction; up to ₹12,00,000 taxable the Section 87A rebate leaves slab income untaxed; above that, slabs of 0–4 L 0%, 4–8 L 5%, 8–12 L 10%, 12–16 L 15%, 16–20 L 20%, 20–24 L 25%, above 24 L 30%, each ×1.04.

**Monthly investing.** The SIP and freed-up education fees go into the investor's current mix in **both** futures, so they set the size of the portfolio without changing the gap.

**Outputs:** median, bad-case (10th percentile) and good-case (90th) wealth for each path, year by year; the share of futures where holding wins; and the **typical gap**, the median paired difference, future by future.

**Realism check against the real index** (rolling 12 months): bad year (1 in 10) −6.9% simulated vs −7.5% real; typical +11.6% vs +11.3%; good year +34.7% vs +33.3%. The old v1 paths had bad years twice as bad as reality.

Results depend most on how fast shares are assumed to grow, and on how jumpy the particular stock is; the assumptions are stated on the result page. Full detail, sensitivity table and per-stock figures: `results/reports/SIMULATOR_V2.md`. Rollback: `SIMULATOR_VERSION=v1`.

### 7.4 Cause and effect v4 (`src/causal_v4.py`)

Quantifies what pushes a decision, and which habits help, by exploiting the fact that dataset v4 is generated by written rules: the exact generator is replicated (matching all 20,000 stored decisions to 4 decimals), so any input can be changed and the **true** effect recomputed. The estimates the app uses come from the data alone, as a real study would produce them: **DoWhy backdoor adjustment** (linear, with placebo, random-common-cause and subset refutations) and **g-computation** with a gradient-boosted model. **Gold share is a negative control** (no causal path by construction), and both methods estimate about zero for it.

Accuracy against the truth: 0.5 points average error across 45 effects, right direction in 97%; 12 of 13 refutation tests pass (the exception is the zero-effect negative control, which a check against chance can't confirm). Habits are modelled as **halving the tendency** they act on, which is an assumption and is stated. The app offers the single habit that helps most in the situation, never a bundle, because habits can offset each other. Key v4.1 effects: a cash shock raises the chance of selling by ~32 points; an emergency fund lowers it by ~7.5; 10 more VIX points raise it ~6.4. Full detail: `results/reports/CAUSAL_V4.md`. Results file: `results/causal_v4.json`; the backend caches it, so restart after regenerating.

### 7.5 Recommendation (`backend/core/recommendation.py`)

Evidence rules, not a language model. `p` = the share of simulated futures in which holding beat selling over the investor's horizon.

| Intent | Rule |
|---|---|
| Sell | `p ≥ 0.60` → HOLD; `p ≤ 0.40` → SELL; between: HOLD if the sale looks biased, else SELL |
| Hold | `p ≤ 0.40` → SELL; otherwise HOLD |
| Buy more | Herd behaviour, or a bias with confidence ≥ 0.60 → HOLD; otherwise BUY MORE if `p ≥ 0.50`, else HOLD |

Every verdict stores its reasons and the exact numbers used, so it can be checked by hand (`debate_transcript.engine = "evidence_rules_v1"`). The same transcript then carries the two cases of §7.8, which are written after the verdict and never read by it; `llm_debate` is true only when Gemini worded them.

### 7.6 Explanation engine (`src/explainer.py`, `explanation_templates.py`, `explanation_report.py`, `llm_polish.py`)

Turns the model outputs into one plain-language story, in **English and Hindi**, with a downloadable report. The backend renders both languages on every analysis and stores them.

**Six sections:** In short; What's going on right now; Your two possible futures; The story of your money (a year-by-year table plus how the figures arose); Why we're telling you this (the top causal drivers in plain words); What to do now (one clear action and an honest confidence caveat).

**Design.**
- **Templates are authoritative.** Every sentence is rendered from a hand-written Jinja2 template filled from one `facts` dict built by `build_facts()`, with `StrictUndefined`, so a missing fact fails a test instead of printing a blank. A template cannot invent a rupee figure. English and Hindi banks are hand-written and structurally identical (34 templates each, enforced by tests), so Hindi works fully offline.
- **No jargon.** A translation layer maps internal terms ("p10", "opportunity cost", causal variable names) to plain phrases, and a 30-term blocklist is enforced by tests. Money is formatted the Indian way (₹1.2 lakh in prose, ₹1,32,451 exact in tables).
- **The typical outcome is narrated, not the average**, because wealth is right-skewed and the mean would contradict the year-by-year table.
- **Optional AI rewording** (`EXPLAINER_LLM`, off by default; Google Gemini Flash-Lite via `google-genai`): one request for all six sections, tables never sent. *The model may reword; it may not introduce, remove or alter a number.* Every number and rupee amount in the reply must already appear in the original, placeholders must be intact, and length may drift only 0.6×–1.8×, or the reply is discarded. Any failure (no key, bad key, quota, timeout, network, malformed reply) returns the template text; two consecutive failures pause the layer for 5 minutes.
- **Reports:** HTML (both languages, self-contained and print-ready) and PDF (English only). ReportLab cannot shape Devanagari, so Hindi is served as HTML, which prints to a correct PDF from any browser.

**Measured quality** (`scripts/evaluate_explanations.py`, 64 explanations): completeness 100%, actionability 100%, personalisation 100%, jargon leaks 0, English Flesch 78.3 (target ≥ 60), Hindi 12.2 words per sentence (target ≤ 20). Flesch is not used for Hindi because its syllable model is undefined for Devanagari. Tests: `tests/test_explainer.py` (128).

### 7.7 Audit chain (`backend/core/audit.py`)

Every completed analysis appends one entry to the investor's own chain in `audit_logs`:

```
inputs_hash   = sha256( canonical( holding, prices, action, reason, market snapshot, portfolio snapshot, comment reading ) )
analysis_hash = sha256( canonical( pattern + confidence, projection, explanation, recommendation ) )
payload_hash  = sha256( canonical(payload) )
chain_hash    = sha256( previous_hash + payload_hash )
genesis       = sha256( "GENESIS:{user_id}:{created_at}" )          (chain_version 2)
```

**Verification** (`GET /v1/decisions/{id}/verify`, shown as "Verify this record") answers two questions: *is the chain intact?*, by walking links from the genesis (not by timestamp), which catches an altered entry, a removed one, a forged one and a fork; and *does the analysis on screen still match its record?*, by recomputing both fingerprints from the current row and naming the part that changed. Appends take a per-investor advisory lock so two analyses finishing together can't claim the same predecessor. Each entry stores the list of columns its fingerprints cover, so the set can grow without older entries failing verification. Entries from the earlier placeholder format (zero genesis) are accepted as the start of a chain and labelled as such.

### 7.8 Comment reading and both sides (`backend/core/comment_reader.py`, `debate.py`, `ai_help.py`)

**Reading "Why? In your own words".** Read once, in step 1, before the bias model runs, and stored as `decisions.comment_facts` so a re-run reads it the same way.

- **Phrase rules, always, offline.** English, Hinglish and Hindi patterns find *facts*: a need for the money (fees, EMIs, medical, job loss, a wedding, "paise chahiye"), a holding that's too big, a goal that's close. They also find *feelings*: fear of losses, following others ("everyone", "my colleagues", "friends told me"), waiting to get back to even, locking in a gain, fear of missing out. Each comes with the sentence it was found in, quoted word for word.
- **Gemini, only with consent.** When the investor has turned on AI help and the server has `AI_HELP=true` plus a key, Gemini reads the comment too. Its answer is accepted only if every item has an allowed kind and a quote that appears **word for word** in the comment; otherwise it is discarded and the rules stand.

**What it changes.** A stated need for the money sets the bias model's `cash_need_stated` input, so a forced sale can read as rational, and the quote is shown as the reason. **Feelings never change anything**: they are quoted back in "In your own words", with a note on whether they agree with the reading. For example: "Your words point to loss aversion too, and also to following the crowd", or, when the words suggest following the crowd but the numbers read a clear-headed decision, "Worth a second look at why you're deciding".

**Both sides.** After the verdict, two cases are built from the analysis's own numbers: for holding and for selling, or for adding and holding off.

- The points cover how often each side won and the typical gap, tax on selling today, the horizon, the pattern found, the bad-case outcomes, the stock's own swings, the size of the holding, and a stated need for the money.
- With consent and a key, Gemini may reword each case. A rewrite is kept only if it passes the explanation engine's number guard: it may add no number or rupee amount, and its length may drift only 0.6×–1.8×.
- The cases never feed the verdict.

**Consent.** `users.ai_consent`, off by default, set in Settings → Your data. The Privacy page states that, when it is on, the comment and the analysis numbers (not the name or email) are sent to Google.

---

## 8. API reference (`/v1`, cookie-authenticated unless noted)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `GET /auth/verify-email`, `POST /auth/login` (`remember_me`), `POST /auth/login/mfa`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/change-password`, `GET /auth/me`, `POST /auth/cancel-deletion` (keep an account during its grace period; pre-session), `GET /auth/google/login`, `GET /auth/google/callback` |
| Two-step | `POST /auth/mfa/setup`, `/mfa/verify-setup`, `/mfa/disable`, `/mfa-recovery-request` |
| Profile and your data | `GET`/`PUT /users/me/profile`, `PUT /users/me/profile/sensitive`, `PUT /users/me/ai-consent`, `GET /users/me/export` (JSON download), `POST /users/me/delete` (password, and TOTP when two-step is on) |
| Portfolio | `GET /portfolio`, `POST /portfolio/holdings`, `PUT`/`DELETE /portfolio/holdings/{id}`, `PUT /portfolio/assets`, `GET /portfolio/mf-search`, `GET /portfolio/quote` |
| Decisions | `POST /decisions/analyze` (202), `GET /decisions/my`, `GET /decisions/stats`, `GET /decisions/{id}/result`, `/stream` (SSE), `/verify`, `/report?format=html\|pdf&lang=en\|hi` |
| Market | `GET /market/ribbon`, `GET /market/context` |
| Meta | `GET /meta/config` (public), `GET /dev/mailbox` (development only, when no email service is configured) |
| Admin | `GET /admin/users/{id}/mfa-status`, `POST /admin/users/{id}/reset-mfa` |
| Health | `GET /health` |

Errors share one shape: `{ "error": "MACHINE_CODE", "message": "…", "request_id": "…" }`. Mutating requests (other than pre-session auth endpoints) need the `X-CSRF-Token` header.

---

## 9. Security and privacy

| Control | How |
|---|---|
| Passwords | bcrypt, cost 12; zxcvbn score ≥ 3 required; the server's message is shown |
| Sessions | RS256 JWT: access token 15 min, refresh token 7 days with rotation; both in httpOnly cookies, `SameSite=Lax`, `Secure` outside development; a dual-jti blacklist in Redis invalidates tokens on logout and refresh |
| "Keep me signed in" | Unticked (default) = session cookies that end when the browser closes; the choice survives token refresh |
| CSRF | Double-submit cookie: `csrf_token` must equal the `X-CSRF-Token` header on every mutating request |
| Two-step verification | TOTP (`valid_window=1`), secret encrypted with Fernet, 8 bcrypt-hashed backup codes, recovery requests (one per email per 24 h) resolved by an admin who must prove their own TOTP |
| Re-verification | Changing email, income, EMIs, rent, education fees or the emergency fund needs the password (and TOTP); an email change also needs a code sent to the old address. Every change is logged with the old value hashed |
| Data isolation | PostgreSQL row-level security on every user-owned table (§6) |
| Rate limiting | slowapi with a Redis store on auth and analysis endpoints |
| Headers | Security headers on every response; CORS restricted to the configured origin |
| Audit | Append-only, hash-chained, verifiable (§7.7) |
| External calls | Only the ticker or fund code is sent for prices (Yahoo Finance, MFAPI.in). An email service and Google sign-in are optional. Gemini receives a comment and the analysis numbers (never the name or email) only for investors who turn on AI help, and only when the server enables it |
| Your data | "Download my data" exports everything held about the investor as JSON (account, financial profile, holdings, analyses, and the secure record with the steps to check it), without the password hash, two-step secret or tokens |
| Deleting an account | Needs the password (and TOTP); signs the investor out everywhere at once. For 30 days, logging in offers "Keep my account". Then the account is **anonymised** (every few hours in the API process, or `scripts/purge_deleted_accounts.py`): name, email, phone, sign-in links, password, two-step secret, age, income and payments, risk answers, goal, the financial profile, holdings, SIPs, sessions, backup codes, profile history and bias profile are erased, and each analysis loses its comment, portfolio snapshot, explanation and projections. The user id and creation time (the audit chain's anchor) and the audit entries stay, unlinked to a person. Deleting outright is impossible because `audit_logs` is append-only |
| Transport | Everything is served over HTTP locally; HTTPS applies once deployed |

The in-app Privacy page (`/privacy`) says only what is true today.

---

## 10. Frontend

Single-page app, soft palette (teal, blush, cream; orange used sparingly; serif Fraunces headings, Inter body), light and dark themes, responsive down to phones.

| Route | Page |
|---|---|
| `/` | Landing: "Create your free account", how it works, the four patterns, Security and data privacy |
| `/privacy` | Privacy policy |
| `/login`, `/register`, `/forgot-password`, `/reset-password`, `/check-email`, `/auth/verify-email`, `/dev/mailbox` | Authentication, with a development inbox when no email service is configured |
| `/app` | Overview: bias pattern, wealth at stake, portfolio snapshot, recent decisions |
| `/app/portfolio` | Net worth, liquid assets, surplus, loans, allocation; add/edit/remove holdings; gold, deposits, property, loans, rent, SIP |
| `/app/new` | Pick a holding and an action; live market card |
| `/app/decisions/:id` | Live five-step progress, then the result: recommendation with reasons, position against the whole portfolio, both futures chart, pattern found, six-part explanation (EN/हिंदी), report downloads, what weighed most, cause and effect, both sides in numbers, "In your own words", "Verify this record", "How this was worked out" |
| `/app/history` | Filter by pattern, search by holding |
| `/app/settings` | Profile (with the secure-update dialog), security (two-step setup with QR and backup codes, change password), your data (download, delete with a 30-day grace period, AI help switch), appearance |

Logging in to an account scheduled for deletion shows the date and a "Keep my account" button. Route guards: signed-out visitors go to `/login` (remembering where they were going); a deliberate logout goes to the home page; a signed-in user never sees the sign-in pages.

---

## 11. Configuration (`.env`; template: `.env.example`)

| Variable | Purpose |
|---|---|
| `ENV` | `development` (dev mailbox, non-secure cookies) or production |
| `DATABASE_URL` | The app's connection, as **`app_user`** (never a superuser) |
| `ALEMBIC_DATABASE_URL`, `APP_DB_PASSWORD` | Owner connection for migrations; password for `app_user` |
| `REDIS_URL` | Redis / Memurai |
| `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `FERNET_KEY` | Generate with `scripts/generate_dev_keys.py` |
| `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` | Used in email links and CORS |
| `RESEND_API_KEY`, `EMAIL_FROM`, `ADMIN_EMAIL` | Email; empty in development means mail goes to the dev mailbox |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` | Google sign-in; empty hides the button |
| `BIAS_MODEL_VERSION` (`v4`), `SIMULATOR_VERSION` (`v2`) | Switch to `v3` / `v1` to roll back |
| `MARKET_DATA_ENABLED`, `MARKET_DATA_TIMEOUT_SECONDS`, `SIMULATION_PATHS` | Market capture and simulation size (tests turn market data off) |
| `EXPLAINER_LLM`, `GEMINI_API_KEY`, `EXPLAINER_LLM_*` | Optional wording polish; off by default |
| `AI_HELP` | Lets investors who opt in have Gemini read their comment and word both sides (needs `GEMINI_API_KEY`); off by default |
| `ACCOUNT_PURGE_INTERVAL_SECONDS` | How often the API anonymises accounts whose grace period has ended (default 6 hours; 0 turns it off) |
| `PIPELINE_STUB_STEPS`, `SSE_*`, `RATE_LIMIT_ENABLED`, `BLACKLIST_CACHE_TTL_SECONDS`, `SENTRY_DSN` | Operations |
| `ANTHROPIC_API_KEY`, `CLAUDE_*` | Present in the settings but unused: Gemini was chosen for the debate |

---

## 12. Running and testing

Setup and the daily commands are in `SETUP.md` and `DEMO.md`. In short:

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m alembic -c backend\db\migrations\alembic.ini upgrade head
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m uvicorn backend.main:app --port 8000 --reload
npm --prefix frontend run dev
```

| Check | Command | Needs |
|---|---|---|
| ML environment (versions, artefacts, specimens) | `python scripts\verify_ml_env.py` | the venv |
| Backend (255) | `python scripts\with_env.py -m pytest backend\tests` | PostgreSQL + Redis; ~15 min. Run one at a time: two runs share the test database and wipe each other's rows |
| Backend, no database | `python -m pytest backend\tests\unit` | the venv |
| Models and engines (334; 5 skipped without an AI key) | `python -m pytest tests` | the venv |
| Frontend (17) | `npm --prefix frontend test` | Node |
| Frontend build | `npm --prefix frontend run build` | Node |

Regenerate the models and reports: `python -m src.dataset_v4`, `python scripts\train_bias_v4.py`, `python scripts\evaluate_simulator_v2.py`, `python -m src.causal_v4`. After regenerating the demo's analyses: `python scripts\with_env.py scripts\seed_demo.py --refresh` (it also re-reads comments and fills newly added snapshot fields). Anonymise accounts whose grace period has ended now: `python scripts\with_env.py scripts\purge_deleted_accounts.py`.

---

## 13. Design decisions worth remembering

| Decision | Reason |
|---|---|
| The backend calls the research code in place (the bridge) | The research modules produced the reported numbers; re-implementing them risks silently changing them |
| Python 3.13 | `dowhy 0.14` otherwise forces an older scipy than the model artefacts were built with |
| Market and portfolio captured at submission and stored | A re-run reproduces the original analysis, which the audit chain depends on |
| `crowd_ratio = clamp((VIX − 10) / 40, 0.05, 1)` derived from the stored VIX | Deterministic; no live fetch at inference time |
| The bias model reads the situation and the action; the recommendation weighs the evidence | The pattern is a tendency to watch for, not an accusation |
| Templates authoritative, AI optional | A template cannot hallucinate a rupee figure |
| The AI cannot change the recommendation | A chatbot should never decide about money |
| Hindi PDF refused, HTML offered | Broken typography is worse than an honest alternative |
| Single best habit offered, never a bundle | Habits can cancel each other (shown in the causal results) |
| Accounts are anonymised, not deleted | `audit_logs` is append-only and the user row anchors the chain's genesis; everything personal is erased instead |
| A stated fact in a comment can change the reading; a feeling never does | A cash need is a constraint the model should know; quoting feelings back helps the investor without letting text move the analysis |
| Gemini quotes must be word for word | An AI can't put words in the investor's mouth or change a number |

---

## 14. Roadmap

**Built:** everything in §1's status table marked built.

**Next:** finish Google sign-in in the web app; admin panel (usage statistics, user management, MFA recovery queue); moving the repository to `github.com/ParamShah77/Folium`, CI, and deployment with HTTPS; turning on AI help with a Gemini key and checking it live.

**Later:** widening the comment rules from real comments; learning the model's weights from real user feedback; the original plan's deferred items (broker integration, WhatsApp alerts, outcome tracking and monthly retraining).

---

## 15. Known limitations

- **Synthetic investors, real markets.** Labels follow behavioural-finance definitions, not observed Indian investors. Real feedback would let the motive weights be learned.
- **Calm markets lean towards disposition effect or rational**, by the definitions (§7.1), and loss aversion versus herd behaviour in a fearful sell-off is close to a coin toss (shown as Low confidence with both probabilities).
- **Typical growth is an assumption** (shares 11%, gold 9%, FD 6.75%); the sensitivity analysis shows how much it matters.
- **Rupees are nominal**; inflation is not taken out of either future.
- **Mutual funds are treated as equity funds**, so a debt or hybrid fund would be projected as too risky; they are also counted as equity in the equity share.
- **Tax** is FY 2025-26 and assumes the ₹1.25 lakh long-term exemption is available; losses are not set off against other gains.
- **Gold** uses the international price, before Indian import duty and GST.
- **One position per decision.** The portfolio is the context, not the subject; a "rebalance the whole portfolio" analysis is not built.
- **Money left each month is a small lever in the causal data**: only 0.7% of synthetic households pay out more than they earn. Cash shocks matter far more.
- **An unstated cash need is often missed**: forced sales read as rational 91% of the time when the need is stated in the comment, 39% when it isn't.
- **Comment rules are phrase lists.** They catch common English, Hinglish and Hindi wording but miss paraphrase; Gemini (with consent) covers more. Feelings are shown only, so a missed or wrong cue never changes an analysis.
- **AI help has not been run live** (no key on this machine yet); its acceptance rules are tested with a stand-in.
- **Google sign-in is unfinished end to end.** The backend flow works (four account cases, tested with mocks), but after Google confirms the user the callback sets the session and returns a JSON page rather than redirecting back into the app, and it has not been tried live. It needs the callback registered in Google Cloud and a redirect to the frontend.
- **No HTTPS or email service locally**; both come with deployment.

---

## 16. Revision note

This file replaces the earlier specification, architecture, plan, blueprint and status documents, which described the Streamlit/SQLite prototype and the first models. They are kept in the separate `Major Project` folder for history. When something changes, update this file and the relevant report together.

---

## 17. Companion documents

| File | Contents |
|---|---|
| `SETUP.md` | First-time setup on a Windows laptop with native PostgreSQL and Memurai |
| `DEMO.md` | Starting the app, demo accounts, a walkthrough, what to say about known behaviour |
| `data/v4/DATASET_CARD.md` | The training data in full detail |
| `data/v4/v4.0/DATASET_CARD.md` | The previous dataset version (kept with its models for comparison) |
| `results/reports/BIAS_MODEL_V4.md` | Bias model evaluation, comparison with v3, sense checks |
| `results/reports/SIMULATOR_V2.md` | Simulation evaluation, realism check, sensitivity, per-stock figures |
| `results/reports/CAUSAL_V4.md` | Cause-and-effect results against the known truth |
