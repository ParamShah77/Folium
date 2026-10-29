# Chapter 3: Requirements Analysis and Feasibility Study

The requirements below were reconstructed from the implemented code, the API routes, the database migrations and the project's master reference document (`FOLIUM_MASTER.md`). Each requirement is marked with its status as found in the repository: **Built** (implemented and covered by tests), **Partial** (implemented in part) or **Pending** (designed but not implemented).

## 3.1 Functional Requirements

### 3.1.1 Accounts and security

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Register with e-mail and password; verify the e-mail address before first login | Built |
| FR-2 | Log in with an optional "Keep me signed in"; refresh sessions silently; log out | Built |
| FR-3 | Reset a forgotten password by e-mailed link | Built |
| FR-4 | Enable two-step verification with an authenticator app (TOTP), with 8 single-use backup codes | Built |
| FR-5 | Request two-step recovery; an administrator who proves their own TOTP may reset it | Built (endpoint only, no admin UI) |
| FR-6 | Sign in with Google end to end: return to the app, two-step verification, "keep me signed in", keep an account in its grace period | Built (Google replaced by a stand-in in automated tests; the local callback address is registered with Google) |
| FR-6a | After a first Google sign-in, collect the Tier-1 profile before any other page; let a Google-only account set a password | Built (`/app/welcome`, "Set a password" in Settings) |
| FR-7 | Re-verify (password, and TOTP if enabled) before changing sensitive profile fields; log every change | Built |

Table: Table 3.1: Functional requirements — accounts and security

### 3.1.2 Profile and portfolio

| ID | Requirement | Status |
|---|---|---|
| FR-8 | Record age, after-tax income, EMIs, rent, education fees (and end year), emergency fund, risk tolerance (five-question quiz) and horizon | Built |
| FR-9 | Add, edit and remove shares (NSE/BSE, live prices) and mutual funds (searched and priced via MFAPI.in) | Built |
| FR-10 | Record gold (grams), fixed deposits, savings, property, loans, rent received and monthly SIP | Built |
| FR-11 | Compute net worth, liquid assets, monthly surplus and allocation; fall back to average cost when a price is unavailable | Built |

Table: Table 3.2: Functional requirements — profile and portfolio

### 3.1.3 Analysis

| ID | Requirement | Status |
|---|---|---|
| FR-12 | Submit an analysis for one holding with an action (sell / hold / buy more), optional months held and a free-text reason | Built |
| FR-13 | Capture and store the market context (NIFTY 1-month return, 30-day volatility, India VIX), the portfolio snapshot and the stock's beta and own volatility at submission | Built |
| FR-14 | Run the five-step pipeline in the background and stream live progress; replay progress after a page reload | Built |
| FR-15 | Read the comment for stated cash needs (English, Hinglish, Hindi) and for feelings; quote them back verbatim | Built |
| FR-16 | Classify the behavioural pattern with calibrated High / Medium / Low confidence and show what weighed most | Built |
| FR-17 | Project HOLD and SELL over the investor's horizon, after tax, with median, bad-case and good-case values by year | Built |
| FR-18 | Show cause-and-effect factors and the single most helpful habit | Built |
| FR-19 | Produce a six-part explanation in English and Hindi; download HTML (both languages) and PDF (English) reports | Built |
| FR-20 | Issue a HOLD / SELL / BUY MORE verdict with reasons and the numbers used; show "both sides" | Built |
| FR-21 | Record the analysis in a tamper-evident chain and let the investor verify it | Built |
| FR-22 | List past analyses with filtering by pattern and search by holding | Built |

Table: Table 3.3: Functional requirements — analysis

### 3.1.4 Data rights and administration

| ID | Requirement | Status |
|---|---|---|
| FR-23 | Download all personal data as JSON | Built |
| FR-24 | Delete the account with a 30-day grace period, after which personal data is anonymised | Built |
| FR-25 | Opt in or out of optional AI help (Gemini) for comment reading and wording | Built (live API not exercised) |
| FR-26 | Administrative console with usage statistics, user management and an MFA-recovery queue | Planned for the next release (milestone C2); the aggregate statistics view and audited MFA-reset endpoints are in place |

Table: Table 3.4: Functional requirements — data rights and administration

## 3.2 Non-Functional Requirements

| ID | Category | Requirement and how it is met |
|---|---|---|
| NFR-1 | Correctness | Numbers shown must come from computation. Templates are authoritative; AI wording is rejected if it adds a number. |
| NFR-2 | Transparency | Missing inputs are filled with disclosed defaults listed under "How this was worked out". |
| NFR-3 | Security | bcrypt (cost 12), RS256 JWT (15-minute access, 7-day refresh with rotation), CSRF double-submit, TOTP, Fernet-encrypted MFA secrets, security headers. |
| NFR-4 | Privacy and isolation | PostgreSQL row-level security on all user-owned tables; the app connects as a non-superuser role. |
| NFR-5 | Integrity | Append-only audit table (UPDATE and DELETE rules do nothing) with per-investor hash chain. |
| NFR-6 | Availability under failure | A price or market-data outage never breaks a page; defaults are used and disclosed; explanation failures fall back to templates. |
| NFR-7 | Performance | One simulation of 1,000 paths × 30 years takes about 0.1 s (measured 103.4 ms in the evaluation file); analysis runs in the background so the request returns immediately (HTTP 202). |
| NFR-8 | Abuse resistance | Rate limits: login 5/minute, registration 3/hour, password reset 3/hour, analysis 10/minute. |
| NFR-9 | Usability | Plain titles, no model names or accuracy figures in the UI, confidence in words, light and dark themes, responsive layout. |
| NFR-10 | Localisation | Every explanation template exists in English and Hindi with identical structure, enforced by tests. |
| NFR-11 | Reproducibility | Market and portfolio snapshots stored with each decision; fixed random seeds for dataset, training and simulation. |
| NFR-12 | Maintainability | Single bridge between product and research code; versioned models with rollback switches (`BIAS_MODEL_VERSION`, `SIMULATOR_VERSION`). |

Table: Table 3.5: Non-functional requirements

## 3.3 Hardware Requirements

The project was developed and demonstrated on a Windows laptop running every service natively (`SETUP.md`). The figures below are the minimum we consider practical for the development set-up; they are based on the documented memory use of the ML libraries (~400 MB on import) and the size of the ML dependency set (~900 MB), not on a formal benchmark.

| Component | Development / demo | Notes |
|---|---|---|
| Processor | 4-core x86-64 | Model training (`scripts/train_bias_v4.py`) took 81.4 s on the development machine |
| Memory | 8 GB RAM (16 GB recommended) | PostgreSQL, Redis/Memurai, Uvicorn, Vite and the ML stack run together |
| Storage | ~3 GB free | Python environment, Node modules, dataset and models |
| Network | Internet access | Live prices (Yahoo Finance, MFAPI.in); optional e-mail and Gemini |

Table: Table 3.6: Hardware requirements

## 3.4 Software Requirements

| Layer | Software (versions as pinned in the repository) |
|---|---|
| Language runtimes | Python 3.13; Node.js with npm |
| Back end | FastAPI 0.115, Pydantic 2.10, asyncpg, Alembic, structlog, slowapi, Uvicorn |
| Authentication | PyJWT (RS256), bcrypt, zxcvbn, pyotp, Authlib, cryptography (Fernet) |
| Data stores | PostgreSQL 18; Redis-compatible store (Memurai on Windows) |
| Machine learning | numpy 2.4.2, pandas 3.0.1, scipy 1.17.1, scikit-learn 1.8.0, xgboost 3.2.0, shap 0.51.0, dowhy 0.14, networkx 3.6.1, pgmpy 1.0.0, yfinance 0.2.66 |
| Explanations and reports | jinja2 3.1.6, textstat 0.7.13, reportlab 5.0.1; optional google-genai |
| Front end | React 19, Vite 8, TypeScript, Tailwind 4, Radix-based components, TanStack Query 5, React Hook Form with Zod, Recharts 3, Vitest |
| Tooling | Git, pytest, Jupyter (research notebooks) |

Table: Table 3.7: Software requirements

**Why Python 3.13 is mandatory.** The comments in `backend/requirements-ml.txt` record that `dowhy 0.14` restricts scipy to ≤ 1.15.3 on Python versions below 3.13. On 3.11 or 3.12, pip would therefore downgrade scipy away from the 1.17.1 under which the model artefacts were built. Pinning Python 3.13 avoids this silent change.

## 3.5 Development Environment

Development used a Python virtual environment with the pinned ML stack, a helper (`scripts/with_env.py`) that loads `.env` into any command, Alembic migrations run as the owner role `finai`, the API served by Uvicorn on port 8000, and the Vite development server on port 3000 proxying `/v1/*` to the API so that cookies and CSRF operate on a single origin. A `Dockerfile.backend` and `docker-compose.yml` exist for later deployment but were not used locally.

## 3.6 Feasibility Study

### 3.6.1 Technical feasibility

Every component relies on mature open-source libraries. XGBoost, scikit-learn and SHAP are standard for tabular modelling; DoWhy provides causal identification and refutation; FastAPI and asyncpg support asynchronous I/O for long-running analyses; PostgreSQL provides row-level security natively. The heaviest computation—training the classifier and running the causal study—happens offline (81.4 s and 54.2 s respectively, per the evaluation files). At request time, one prediction and one 1,000-path simulation are fast enough to run inside a background task. The approach is therefore technically feasible on commodity hardware.

### 3.6.2 Operational feasibility

The user supplies information they already know (income, loans, holdings) once, and each analysis then needs only a holding, an action and an optional sentence. Gaps are filled with disclosed defaults instead of blocking the user. Explanations avoid jargon and are available in Hindi. A non-technical investor can therefore operate the system without training.

### 3.6.3 Economic feasibility

All software used is free and open source. Market data comes from free sources (Yahoo Finance via yfinance and MFAPI.in). The optional services—transactional e-mail and Gemini—have free tiers and are disabled by default. The development cost was therefore limited to the team's time and existing hardware. Hosting costs for a deployment have not been estimated because the system has not been deployed (Section 12.5).

### 3.6.4 Legal and ethical feasibility

The application handles personal financial data, so it implements data minimisation (no crypto, credit-card or insurance data collected), consent for any third-party AI processing, a privacy page that describes only what is true today, export and deletion of personal data, and a clear statement that the output is not investment advice. Formal regulatory review was outside the project's scope.

## 3.7 Use Cases and User Roles

| Role | Description | Main use cases |
|---|---|---|
| Visitor | Not signed in | View landing and privacy pages; register; log in; reset password |
| Investor (`role = user`) | Verified account holder | Maintain profile and portfolio; request and read analyses; download reports; verify records; export data; delete account; manage two-step and AI consent |
| Administrator (`role = admin`) | Operator with own TOTP | Inspect a user's two-step status; reset two-step after a recovery request |

Table: Table 3.8: User roles

The principal use case, "Request decision analysis", proceeds as follows. *Pre-condition:* the investor is signed in and has at least one holding. *Main flow:* (1) the investor opens "New analysis", picks a holding and an action, and optionally enters months held and a reason; (2) the system validates the input, captures the market and portfolio snapshots, creates the decision and returns its identifier; (3) the browser opens the live progress stream; (4) the five steps run and publish progress; (5) the result page shows the verdict, projections, explanation and verification. *Alternative flows:* market data unavailable → a calm median market is assumed and disclosed; a step fails → the decision is marked failed and the page says so. *Post-condition:* the decision row is complete and an audit entry exists.

## 3.8 Assumptions and Constraints

**Confirmed constraints (from the code).** One position per analysis; horizons capped at 30 years with a default of 20 when none is given; tax rules fixed to FY 2025-26 (new regime); mutual funds treated as equity funds; gold valued at the international price before Indian duty and GST; nominal (not inflation-adjusted) rupees; Hindi PDF reports refused because ReportLab cannot shape Devanagari (HTML offered instead).

**Income is collected after tax.** The profile asks for monthly take-home pay because that is the figure people know. Where the simulator needs income before tax (for the slab rate on interest), it inverts the income-tax formula (Section 7.8).

**Assumptions made by the models (stated in the app).** Long-run growth rates of 11% for shares, 9% for gold, 6.75% for FDs and 3% for savings; sale charges of 0.15%; a habit modelled as halving the tendency it acts on; the ₹1.25 lakh long-term gains exemption available for the sale.

**Assumptions made for this report.** Hardware figures in Table 3.6 are practical estimates. Institutional details marked in square brackets (roll numbers, names of the Head of Department and Principal, submission date) must be supplied by the team.
