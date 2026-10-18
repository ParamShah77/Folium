# Folium

**Decide sell, hold or buy more, judged against your whole financial picture.**

Folium is a full-stack web app for Indian retail investors. You tell it about one holding and what you are thinking of doing with it. It reads the moment, names the behavioural pattern most likely behind the decision, projects both choices over your own horizon in rupees and after tax, explains what it found in plain English or Hindi, and gives a recommendation based on the evidence only. Every analysis is then sealed into a tamper-evident record you can verify later.

> Folium is for information and education. It is not investment advice.

---

## Table of contents

1. [About](#about)
2. [What it does](#what-it-does)
3. [Features](#features)
4. [How an analysis works](#how-an-analysis-works)
5. [The models](#the-models)
6. [Architecture](#architecture)
7. [Tech stack](#tech-stack)
8. [Project structure](#project-structure)
9. [Getting started](#getting-started)
10. [Configuration](#configuration)
11. [Demo accounts and walkthrough](#demo-accounts-and-walkthrough)
12. [Testing](#testing)
13. [API overview](#api-overview)
14. [Security and privacy](#security-and-privacy)
15. [Design decisions](#design-decisions)
16. [Known limitations](#known-limitations)
17. [Roadmap](#roadmap)
18. [Documentation](#documentation)
19. [Author](#author)

---

## About

Most investing tools look at a stock. Folium looks at the **person** deciding about the stock.

Selling a share in a panic, holding a loser to "get back to even", or buying into a rally because everyone else is: these are well-documented behavioural patterns, and they cost real money. At the same time, the same sale can be perfectly sensible if the investor needs the cash for fees or an EMI. Folium's job is to tell the difference, using the investor's own income, loans, emergency fund, portfolio and horizon, together with what the market was doing at the time.

The project began as a research effort on behavioural bias detection and grew into a complete product: authentication, a portfolio, a live analysis pipeline, explanations in two languages, reports, an audit trail and data-rights tooling.

### Principles

- **The pattern is a tendency to watch for, not an accusation.** The bias model reads the situation and the action; the recommendation weighs the evidence.
- **No hidden numbers.** Missing inputs are filled with disclosed defaults and listed on the result page under "How this was worked out".
- **Wording can never change a number.** Explanations are rendered from hand-written templates. Optional AI rewording is rejected if it alters a single figure.
- **AI never decides about money.** The recommendation comes from written evidence rules, not a language model.
- **Honest about uncertainty.** Confidence is shown as High, Medium or Low, calibrated against real market frequencies, never as a made-up percentage.

---

## What it does

For each decision, Folium:

1. **Reads the moment.** Names the pattern most likely behind it: loss aversion, herd behaviour, the disposition effect, or rational.
2. **Projects both choices.** Hold versus sell, across the investor's own horizon (1 to 30 years), in rupees, after tax and charges, on the same simulated markets for both.
3. **Explains it.** Six plain-language sections in English or Hindi, plus what pushes people toward that action and the one habit that would help most.
4. **Recommends.** SELL, HOLD or BUY MORE, with the reasons and the exact numbers used.
5. **Seals the analysis.** A hash-chained record per investor, with a "Verify this record" check.

---

## Features

### Accounts and security
- Email sign-up with verification, login, password reset, and an optional "Keep me signed in".
- Two-step verification (TOTP authenticator app, backup codes, and an admin-assisted recovery path).
- Google sign-in end to end, including two-step, grace-period handling and a profile step for new accounts.
- Re-verification (password, plus a code if two-step is on) before sensitive profile changes; every change is logged.

### Portfolio
- Shares (NSE/BSE, priced live), mutual funds (searched and priced live), gold (live), fixed deposits, savings, property, loans, rent received and monthly SIP.
- Net worth, liquid assets, monthly surplus and allocation computed for you.
- A price outage never breaks a page; unpriced holdings fall back to average cost and say so.

### Analysis
- Five-step pipeline with **live progress** over server-sent events; reloading mid-analysis replays the history.
- Bias model v4.1, simulation v2, cause-and-effect v4 and an explanation engine.
- **Comment reading:** the "Why? In your own words" text is read for stated needs ("college fees in March") and feelings, in English, Hinglish and Hindi, and quoted back word for word.
- **Both sides in numbers:** the case for each choice, built from the analysis's own figures. It never changes the verdict.

### Explanations and reports
- Six-part explanation in **English and हिंदी**, available offline.
- Downloadable report: HTML (both languages) and PDF (English).
- Optional AI rewording and AI comment reading, off by default and gated by a per-investor consent switch.

### Trust and data rights
- Tamper-evident audit chain with a one-click verification.
- "Download my data" (full JSON export).
- Account deletion with a 30-day grace period, after which personal data is erased and the audit anchor stays unlinked from any person.

### Interface
- Landing page, privacy policy, dashboard, portfolio, new analysis, live result page, history and settings.
- Light and dark themes, responsive down to phones.

---

## How an analysis works

1. The investor picks a **holding** and an **action** (sell, hold or buy more), optionally the months held and a free-text reason.
2. `POST /v1/decisions/analyze` captures the **market context** (NIFTY 1-month return, 30-day volatility, India VIX), the **portfolio snapshot**, and the stock's measured **beta** and own swings. These are stored on the decision so a re-run reproduces the original inputs. The call returns `202` with the decision id.
3. A background pipeline runs five steps, publishing progress events the browser follows live.

| Step | What it does |
|---|---|
| 1. Reading your decision | Reads the comment, then runs the bias model |
| 2. Projecting the future | Runs the simulation for hold versus sell |
| 3. Explaining | Cause-and-effect analysis and the explanation engine (English and Hindi) |
| 4. Forming a recommendation | Applies the evidence rules, then builds both sides |
| 5. Saving a secure record | Appends an entry to the investor's audit chain |

If a step fails, the decision is marked `failed` and the page says so. Wording problems never fail an analysis: the template text is used instead.

### Handled edge cases (selection)

| Situation | Behaviour |
|---|---|
| No live price | Valued at average cost, flagged "price unavailable" |
| Market data unavailable | A calm market is assumed and the page says so |
| Profile or portfolio gaps | Filled with training medians and listed under "How this was worked out" |
| No horizon given | 20 years, stated on the page; horizons are capped at 30 |
| Very large position or goal within 3 years | A sale can be read as rational |
| Account scheduled for deletion signs in | Told the date and offered "Keep my account" |
| Hindi PDF requested | Refused with an explanation; the HTML report is offered |

---

## The models

All model code lives in `src/` and is called by the backend through a single bridge, `backend/core/ml_bridge.py`, so the numbers reported in the evaluation are the numbers the product produces.

### Training data: dataset v4.1
20,000 synthetic investor decisions built on **real NIFTY 50 and India VIX history** (June 2008 to October 2026). Labels are driven by motives, not simple rules: hidden tendencies compete with a rational motive, and the winner sets both the action and the label. See `data/v4/DATASET_CARD.md`.

### Bias model v4.1
- XGBoost classifier on 22 features (the action, the market, and the investor's finances).
- Calibrated confidence (isotonic), reported as High / Medium / Low.
- Exact TreeSHAP explanations summed into 18 plain-language drivers.

| Metric (test set, real-market weighted) | v4.1 | v3 |
|---|---|---|
| Accuracy | 87.9% | 53.4% |
| Macro-F1 | 0.840 | 0.309 |
| Calibration error | 0.014 | 0.254 |

High-confidence readings are right about 98.7% of the time. Full evaluation: `results/reports/BIAS_MODEL_V4.md`.

### Simulation v2
Hold versus sell on the **same** simulated markets, built from 12-month blocks of real NIFTY and gold history with typical growth reset to stated long-run rates (shares 11%, gold 9%, FD 6.75%, savings 3%). The holding moves with the market by its own measured beta plus company-specific swings. Shown **after tax** (FY 2025-26, new regime) with median, bad-case and good-case wealth year by year. See `results/reports/SIMULATOR_V2.md`.

### Cause and effect v4
Estimates what pushes a decision and which single habit helps most, using DoWhy backdoor adjustment and g-computation, checked against the known truth of the data generator (about 0.5 points average error, right direction in 97% of effects). See `results/reports/CAUSAL_V4.md`.

### Recommendation
Evidence rules, not a language model. Using `p`, the share of simulated futures in which holding beat selling:

| Intent | Rule |
|---|---|
| Sell | `p ≥ 0.60` → HOLD; `p ≤ 0.40` → SELL; between: HOLD if the sale looks biased, otherwise SELL |
| Hold | `p ≤ 0.40` → SELL; otherwise HOLD |
| Buy more | Herd behaviour, or a bias with confidence ≥ 0.60 → HOLD; otherwise BUY MORE if `p ≥ 0.50` |

### Explanation engine
Hand-written Jinja2 templates, structurally identical in English and Hindi, with a jargon blocklist enforced by tests and Indian-style money formatting. Optional AI rewording is accepted only if every number is preserved and length stays within bounds.

---

## Architecture

```
Browser (React SPA, :3000)
   │  /v1/*   (Vite proxy in development: one origin, so cookies and CSRF stay simple)
   ▼
FastAPI backend (:8000)  ── auth, portfolio, decisions, market, reports
   │            │
   │            └── background pipeline: bias → simulation → explanation → recommendation → audit
   │                       │ calls the research code in place via backend/core/ml_bridge.py
   │                       ▼
   │                 src/  (bias_model_v4, simulator_v2, causal_v4, explainer, …)
   ▼
PostgreSQL 18 (:5432)                    Redis / Memurai (:6379)
per-user row-level security              token blacklist, rate limits, live event bus
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Pydantic 2, asyncpg, Alembic, structlog, slowapi |
| Auth | RS256 JWT (PyJWT), bcrypt, zxcvbn, pyotp (TOTP), Authlib (Google), Fernet encryption |
| Data | PostgreSQL 18 with row-level security, Redis-compatible store (Memurai on Windows) |
| ML | scikit-learn, XGBoost, SHAP, DoWhy, pandas, NumPy, SciPy, NetworkX, pgmpy |
| Reports | Jinja2, ReportLab, textstat |
| Market data | Yahoo Finance (yfinance), MFAPI.in |
| Frontend | React 19, Vite, TypeScript, Tailwind 4, Radix-based components, TanStack Query, React Hook Form + Zod, Recharts |

Exact ML versions are pinned in `backend/requirements-ml.txt` and checked by `scripts/verify_ml_env.py`.

---

## Project structure

```
Folio/
├── backend/            FastAPI product API
│   ├── api/v1/         Route handlers
│   ├── auth/           Login, tokens, MFA, Google sign-in
│   ├── core/           Pipeline, steps, ML bridge, audit chain, recommendation, comment reader
│   ├── services/       Portfolio, prices, market data, email, account deletion
│   ├── db/migrations/  Alembic migrations (0001 to 0012)
│   ├── middleware/     CSRF, security headers, rate limiting
│   ├── schemas/        Pydantic models
│   └── tests/          Backend tests (unit/ runs without a database)
├── frontend/           React single-page app
│   └── src/            pages, components, providers, lib, tests
├── src/                Models and engines (bias v4, simulator v2, causal v4, explainer)
├── models/             Trained model files
├── data/               Datasets (v4 decisions, real market history, simulation history)
├── results/            Evaluation outputs and reports/
├── scripts/            Setup, seeding, training and evaluation scripts
├── tests/              Tests for the models, data, explainer, simulator and causal code
├── notebooks/, archive/  Research notebooks and archived work
├── FOLIUM_MASTER.md    The complete reference
├── SETUP.md            First-time setup
├── DEMO.md             Running the demo
└── .env.example        Configuration template
```

---

## Getting started

These steps are for **Windows** with native services and no Docker. [SETUP.md](SETUP.md) has the full version with troubleshooting.

### Prerequisites

| | Version | Notes |
|---|---|---|
| Python | 3.13 | Not 3.11 or 3.12: the pinned scientific stack was built for 3.13 |
| Node.js | 22 or newer | For the frontend |
| PostgreSQL | 18 | Runs as a Windows service on 5432 |
| Memurai (Redis for Windows) | Developer edition | Runs as a service on 6379 |

### 1. Python environment

The ML libraries are large (about 2.5 GB), so put the environment on a drive with room.

```powershell
py -3.13 -m venv D:\FolioEnv\venv313
D:\FolioEnv\venv313\Scripts\python.exe -m pip install --upgrade pip
D:\FolioEnv\venv313\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-ml.txt
D:\FolioEnv\venv313\Scripts\python.exe scripts\verify_ml_env.py
```

If you use another location, replace `D:\FolioEnv\venv313` in the commands below.

### 2. Database

In `psql` as the `postgres` superuser:

```sql
CREATE ROLE finai LOGIN SUPERUSER PASSWORD 'choose-a-password';
CREATE DATABASE finai OWNER finai;
```

`finai` owns the schema and runs migrations. The app itself connects as a separate least-privilege role, `app_user`, created by migration 0007, so that row-level security is actually enforced (a superuser silently bypasses it).

### 3. Configuration

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\generate_dev_keys.py
```

This creates `.env` from `.env.example` and fills in the signing and encryption keys. Then set the database lines:

```
DATABASE_URL=postgresql://app_user:<APP_PASSWORD>@localhost:5432/finai
APP_DB_PASSWORD=<APP_PASSWORD>
ALEMBIC_DATABASE_URL=postgresql://finai:<FINAI_PASSWORD>@localhost:5432/finai
REDIS_URL=redis://localhost:6379/0
```

Use only letters and digits in passwords, or URL-encode them. `.env` is git-ignored. Every command that needs these values runs through `scripts\with_env.py`, which loads `.env` for that one command.

### 4. Create the tables

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m alembic -c backend\db\migrations\alembic.ini upgrade head
```

### 5. Install frontend packages

```powershell
npm --prefix frontend install
```

### 6. Seed demo data (optional)

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py scripts\seed_demo.py
```

### 7. Run

Backend, in one terminal:

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m uvicorn backend.main:app --port 8000 --reload
```

Frontend, in a second terminal:

```powershell
npm --prefix frontend run dev
```

Open **http://localhost:3000**.

With no email service configured in development, verification and reset emails appear in an in-app **development inbox** at `/dev/mailbox`.

---

## Configuration

All settings live in `.env` (template: `.env.example`).

| Variable | Purpose |
|---|---|
| `ENV` | `development` or production |
| `DATABASE_URL`, `ALEMBIC_DATABASE_URL`, `APP_DB_PASSWORD` | App connection (as `app_user`), owner connection for migrations, and the `app_user` password |
| `REDIS_URL` | Redis / Memurai |
| `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `FERNET_KEY` | Generated by `scripts/generate_dev_keys.py` |
| `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` | Used in email links and CORS |
| `RESEND_API_KEY`, `EMAIL_FROM`, `ADMIN_EMAIL` | Transactional email; empty in development means the dev mailbox |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` | Google sign-in; the button is hidden while these are empty |
| `BIAS_MODEL_VERSION`, `SIMULATOR_VERSION` | Switch to `v3` / `v1` to roll back |
| `MARKET_DATA_ENABLED`, `MARKET_DATA_TIMEOUT_SECONDS`, `SIMULATION_PATHS` | Market capture and simulation size |
| `EXPLAINER_LLM`, `AI_HELP` and the related API key | Optional AI rewording and comment reading; both off by default |
| `ACCOUNT_PURGE_INTERVAL_SECONDS` | How often finished grace periods are anonymised (default 6 hours) |

### Google sign-in (optional)
Create an OAuth client in Google Cloud Console and register the redirect URI `http://localhost:3000/v1/auth/google/callback`, then put the client id and secret in `.env`. SETUP.md walks through it.

---

## Demo accounts and walkthrough

`scripts/seed_demo.py` creates two demo investors with full portfolios and real analyses:

| Account | Profile |
|---|---|
| Ananya (34, salaried) | Five stocks, a mutual fund, gold, FDs, savings, a car loan, monthly SIP; 12 analyses |
| Rohan (52, near retirement) | Two stocks, gold, FDs, a flat with a home loan, rent received, education fees ending 2029; 2 analyses |

Credentials and a suggested six-minute walkthrough are in [DEMO.md](DEMO.md). Logging in as one shows none of the other's data, which demonstrates the per-user isolation in the database.

---

## Testing

```powershell
# Backend tests that need no database
D:\FolioEnv\venv313\Scripts\python.exe -m pytest backend\tests\unit

# Models, data, explainer, simulator and causal tests
D:\FolioEnv\venv313\Scripts\python.exe -m pytest tests

# Full backend suite (needs PostgreSQL and Redis; creates its own test database)
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m pytest backend\tests

# Frontend tests and production build
npm --prefix frontend test
npm --prefix frontend run build
```

Run the full backend suite one at a time: two runs share the same test database. Some tests that need an AI key are skipped without one.

---

## API overview

All routes are under `/v1` and cookie-authenticated unless noted. Mutating requests need the `X-CSRF-Token` header.

| Area | Examples |
|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/login/mfa`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `GET /auth/google/login` |
| Two-step | `POST /auth/mfa/setup`, `/auth/mfa/verify-setup`, `/auth/mfa/disable` |
| Profile and data | `GET`/`PUT /users/me/profile`, `GET /users/me/export`, `POST /users/me/delete` |
| Portfolio | `GET /portfolio`, `POST /portfolio/holdings`, `GET /portfolio/mf-search`, `GET /portfolio/quote` |
| Decisions | `POST /decisions/analyze`, `GET /decisions/{id}/result`, `/stream`, `/verify`, `/report` |
| Market | `GET /market/ribbon`, `GET /market/context` |
| Health | `GET /health` |

Errors share one shape: `{ "error": "MACHINE_CODE", "message": "…", "request_id": "…" }`. The full list is in FOLIUM_MASTER.md.

---

## Security and privacy

| Control | How |
|---|---|
| Passwords | bcrypt (cost 12), strength checked with zxcvbn |
| Sessions | RS256 JWT; 15-minute access token, 7-day rotating refresh token, httpOnly cookies, `SameSite=Lax`, `Secure` outside development; Redis blacklist on logout |
| CSRF | Double-submit cookie checked on every mutating request |
| Two-step verification | TOTP with an encrypted secret, hashed backup codes, admin-assisted recovery |
| Google sign-in | OpenID Connect with a single-use state; only Google-verified emails; the result returns in the URL fragment so tokens never reach a server log |
| Data isolation | PostgreSQL row-level security on every user-owned table; the app connects as a non-superuser |
| Audit | Append-only, hash-chained, verifiable per investor |
| Rate limiting | Redis-backed limits on auth and analysis endpoints |
| External calls | Only a ticker or fund code is sent for prices. Optional AI features send a comment and analysis numbers (never name or email), only for investors who opt in |
| Your data | Full JSON export; deletion with a 30-day grace period, then anonymisation |

Transport is plain HTTP locally; HTTPS applies once deployed.

---

## Design decisions

| Decision | Reason |
|---|---|
| The backend calls the research code in place | Re-implementing it risks silently changing the reported numbers |
| Market and portfolio captured at submission and stored | A re-run reproduces the original analysis, which the audit chain depends on |
| Templates are authoritative; AI is optional | A template cannot invent a rupee figure |
| The AI cannot change the recommendation | A chatbot should never decide about money |
| A stated fact in a comment can change the reading; a feeling never does | A cash need is a real constraint; feelings are quoted back without moving the analysis |
| Accounts are anonymised, not deleted | The audit log is append-only and anchors on the user row; everything personal is erased instead |
| Hindi PDF refused, HTML offered | Broken typography is worse than an honest alternative |
| One best habit offered, never a bundle | Habits can cancel each other out |

---

## Known limitations

- **Synthetic investors, real markets.** Labels follow behavioural-finance definitions, not observed Indian investors.
- **Typical growth is an assumption**, and results are sensitive to it; the assumptions are stated on every result page.
- **Rupees are nominal**; inflation is not taken out of either future.
- **Mutual funds are treated as equity funds**, so a debt or hybrid fund would be projected as riskier than it is.
- **Tax** is modelled for FY 2025-26 and assumes the long-term exemption is available; losses are not set off against other gains.
- **Gold** uses the international price, before Indian import duty and GST.
- **One position per decision.** The portfolio is context, not the subject.
- **Comment rules are phrase lists** and can miss paraphrase; feelings are shown but never change an analysis.
- **No HTTPS or email service locally**; both come with deployment.

See FOLIUM_MASTER.md section 15 for the complete list.

---

## Roadmap

**Built:** accounts and security, Google sign-in, portfolio, analysis pipeline, bias v4.1, simulation v2, cause-and-effect v4, explanations in two languages, reports, audit chain, data export and deletion, comment reading and both sides.

**Next:**
- Admin panel: usage statistics, user management, MFA recovery queue
- Continuous integration on GitHub
- Deployment with HTTPS

**Later:** widening the comment rules from real comments, learning the model's weights from real user feedback, broker integration, alerts, and outcome tracking.

---

## Documentation

| File | Contents |
|---|---|
| [FOLIUM_MASTER.md](FOLIUM_MASTER.md) | How everything works, every formula, and where the project stands |
| [SETUP.md](SETUP.md) | First-time setup on Windows |
| [DEMO.md](DEMO.md) | Starting the app, demo accounts, walkthrough |
| `data/v4/DATASET_CARD.md` | The training data in full |
| `results/reports/BIAS_MODEL_V4.md` | Bias model evaluation |
| `results/reports/SIMULATOR_V2.md` | Simulation evaluation and sensitivity |
| `results/reports/CAUSAL_V4.md` | Cause-and-effect results |

---

## Author

Built by [Param Shah](https://github.com/ParamShah77).

Repository: https://github.com/ParamShah77/Folium
