# Appendix A: Installation and Execution Guide

The steps below follow `SETUP.md` and `DEMO.md` in the repository. They assume a Windows laptop with native PostgreSQL and Memurai, as used in development; on Linux or macOS, Redis replaces Memurai and paths use forward slashes.

**A.1 Prerequisites.** Python 3.13, Node.js with npm, PostgreSQL 18, Memurai (or Redis), Git.

**A.2 Clone and create the environment.**

```text
git clone https://github.com/ParamShah77/Folium.git
cd Folium
python -m venv venv313
venv313\Scripts\activate
pip install -r backend/requirements.txt -r backend/requirements-ml.txt
python scripts/verify_ml_env.py
npm --prefix frontend install
```

**A.3 Configure.** Copy `.env.example` to `.env`. Generate development keys with `python scripts/generate_dev_keys.py` and paste the JWT key pair and Fernet key into `.env`. Set `DATABASE_URL` to the `app_user` role and `ALEMBIC_DATABASE_URL` to the owner role. Never commit `.env`.

**A.4 Create the database schema.**

```text
python scripts/with_env.py -m alembic -c backend/db/migrations/alembic.ini upgrade head
```

**A.5 Run.**

```text
python scripts/with_env.py -m uvicorn backend.main:app --port 8000 --reload
npm --prefix frontend run dev
```

Open `http://localhost:3000`. Without an e-mail service, verification and reset e-mails appear in the development inbox at `/dev/mailbox`.

**A.6 Demo data.** `python scripts/with_env.py scripts/seed_demo.py` creates demo accounts with portfolios and completed analyses (`--refresh` re-runs them after models change).

# Appendix B: API Reference

All routes are under `/v1` and use cookie authentication unless noted. Mutating requests (other than pre-session authentication) require the `X-CSRF-Token` header. Errors share one shape: `{"error": "MACHINE_CODE", "message": "…", "request_id": "…"}`.

| Area | Method and path | Purpose |
|---|---|---|
| Auth | `POST /auth/register` | Create account (3/hour) |
| | `GET /auth/verify-email` | Verify e-mail from link |
| | `POST /auth/login`, `POST /auth/login/mfa` | Log in (`remember_me`); second step |
| | `POST /auth/refresh`, `POST /auth/logout` | Rotate or end session |
| | `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/change-password` | Password management |
| | `GET /auth/me` | Current user |
| | `POST /auth/cancel-deletion` | Keep an account during its grace period |
| | `GET /auth/google/login`, `GET /auth/google/callback` | Google sign-in (callback incomplete in web app) |
| Two-step | `POST /auth/mfa/setup`, `/mfa/verify-setup`, `/mfa/disable`, `/mfa-recovery-request` | TOTP management and recovery |
| Profile and data | `GET`/`PUT /users/me/profile` | Profile |
| | `PUT /users/me/profile/sensitive` | Sensitive fields with re-verification |
| | `PUT /users/me/ai-consent` | Optional AI help consent |
| | `GET /users/me/export` | Download all data as JSON |
| | `POST /users/me/delete` | Schedule deletion (password and TOTP) |
| Portfolio | `GET /portfolio` | Holdings, assets and derived figures |
| | `POST /portfolio/holdings`, `PUT`/`DELETE /portfolio/holdings/{id}` | Manage holdings |
| | `PUT /portfolio/assets` | Gold, deposits, savings, property, loans, rent, SIP |
| | `GET /portfolio/mf-search`, `GET /portfolio/quote` | Fund search; live quote |
| Decisions | `POST /decisions/analyze` | Start an analysis (returns 202; 10/minute) |
| | `GET /decisions/my`, `GET /decisions/stats` | History and summary |
| | `GET /decisions/{id}/result` | Full result |
| | `GET /decisions/{id}/stream` | Live progress (server-sent events) |
| | `GET /decisions/{id}/verify` | Verify the audit record |
| | `GET /decisions/{id}/report?format=html\|pdf&lang=en\|hi` | Download report |
| Market | `GET /market/ribbon`, `GET /market/context` | Market summary and context |
| Meta | `GET /meta/config` (public), `GET /dev/mailbox` (development only) | Configuration; dev inbox |
| Admin | `GET /admin/users/{id}/mfa-status`, `POST /admin/users/{id}/reset-mfa` | Two-step administration |
| Health | `GET /health` | Liveness |

Table: Table B.1: API endpoints (`backend/api/v1/`, `backend/auth/routes.py`)

# Appendix C: Dataset and Database Schema

| Column group | Columns in `data/v4/decisions_v4.csv` |
|---|---|
| Identity and day | `case_id`, `date`, `regime` |
| Market | `nifty_1m_return`, `nifty_3m_return`, `nifty_volatility_30d`, `vix`, `drawdown_52w`, `crowd_ratio` |
| Position | `holding_period_months`, `unrealized_gl`, `action` |
| Household | `age`, `monthly_income`, `years_investing`, `risk_tolerance`, `investment_horizon`, `rent_paid`, `monthly_emi`, `education_monthly`, education end year, `has_emergency_fund`, `monthly_outflow` |
| Portfolio | `liquid_assets`, `position_share`, `equity_share`, `gold_share`, `real_estate_value`, `home_loan_outstanding`, `other_loans_outstanding`, `rent_received` and component values |
| Observable need | `cash_need_stated` |
| Hidden truth (never a feature) | `latent_loss_aversion`, `latent_herd`, `latent_disposition`, `latent_cash_shock`, `latent_shock_kind`, `latent_shock_u`, `latent_stated_u`, `latent_needs_cash` |
| Label | `motive`, `motive_share`, `bias_type` |

Table: Table C.1: Columns of dataset v4.1 (grouped)

| Table | Key columns | RLS |
|---|---|---|
| `users` | `user_id` PK, `email` unique, `password_hash`, `mfa_enabled`, `mfa_secret_enc`, profile fields, `ai_consent`, `purge_after`, `anonymised_at` | No (read by auth path) |
| `refresh_tokens` | `token_id` PK, `user_id` FK, `token_hash`, `jti`, `expires_at`, `revoked` | No |
| `mfa_backup_codes` / `mfa_recovery_requests` | `user_id` FK, `code_hash`, `used` / `email`, `status`, `resolved_by` | No |
| `profile_change_log` | `user_id` FK, `field_changed`, `old_value_hash`, `verified_via` | Yes |
| `financial_profiles` | `user_id` PK/FK, gold, deposits, savings, property, loans, rent, `monthly_sip` | Yes |
| `portfolios` | `holding_id` PK, `user_id` FK, `symbol`, `exchange`, `quantity`, `avg_buy_price`, `asset_type` | Yes |
| `decisions` | `decision_id` PK, `user_id` FK, inputs, market snapshot, `portfolio_context`, `comment_facts`, model outputs, `status`, `pipeline_step` | Yes |
| `audit_logs` | `log_id` PK, `user_id`, `decision_id`, `payload_hash`, `previous_hash`, `chain_hash`, `payload` | Yes; append-only rules |

Table: Table C.2: Database tables (migrations 0001–0012)

# Appendix D: Reproducibility and Test Commands

| Purpose | Command | Output |
|---|---|---|
| Check ML environment | `python scripts/verify_ml_env.py` | Version and artefact report |
| Rebuild dataset | `python -m src.dataset_v4` | `data/v4/decisions_v4.csv` |
| Train and evaluate bias model | `python scripts/train_bias_v4.py` | `models/bias_detector_v4.*`, `results/reports/bias_v4_evaluation.json` |
| Evaluate simulator | `python scripts/evaluate_simulator_v2.py` | `results/reports/simulator_v2_evaluation.json` |
| Run causal study | `python -m src.causal_v4` | `results/causal_v4.json` |
| Evaluate explanations | `python scripts/evaluate_explanations.py` | `results/reports/explanation_quality.json` |
| Regenerate report figures | `python blackbook/make_figures.py` | `blackbook/figures/*.png` |
| Model and engine tests | `python -m pytest tests` | 334 tests (5 skipped without AI key) |
| Back-end unit tests | `python -m pytest backend/tests/unit` | 162 tests |
| Full back-end tests | `python scripts/with_env.py -m pytest backend/tests` | 255 tests; needs PostgreSQL and Redis (~15 min) |
| Front-end tests and build | `npm --prefix frontend test`, `npm --prefix frontend run build` | 17 tests; production bundle |

Table: Table D.1: Commands to reproduce results and run tests

# Appendix E: Configuration Reference

| Variable | Purpose |
|---|---|
| `ENV` | `development` (dev mailbox, non-secure cookies) or production |
| `DATABASE_URL` | Application connection as `app_user` (never a superuser) |
| `ALEMBIC_DATABASE_URL`, `APP_DB_PASSWORD` | Owner connection for migrations; `app_user` password |
| `REDIS_URL` | Redis / Memurai |
| `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `FERNET_KEY` | Generated by `scripts/generate_dev_keys.py` |
| `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS` | E-mail links and CORS |
| `RESEND_API_KEY`, `EMAIL_FROM`, `ADMIN_EMAIL` | E-mail (empty in development → dev mailbox) |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` | Google sign-in (empty hides the button) |
| `BIAS_MODEL_VERSION` (`v4`), `SIMULATOR_VERSION` (`v2`) | Roll back to `v3` / `v1` |
| `MARKET_DATA_ENABLED`, `MARKET_DATA_TIMEOUT_SECONDS`, `SIMULATION_PATHS` | Market capture and simulation size |
| `EXPLAINER_LLM`, `GEMINI_API_KEY`, `AI_HELP` | Optional AI wording and comment reading (off by default) |
| `ACCOUNT_PURGE_INTERVAL_SECONDS` | Anonymisation interval (default 6 hours; 0 disables) |
| `PIPELINE_STUB_STEPS`, `SSE_*`, `RATE_LIMIT_ENABLED`, `SENTRY_DSN` | Operations |

Table: Table E.1: Environment variables (`.env.example`; values are secrets and are not reproduced here)

# Appendix F: User Manual

1. **Create an account.** On the landing page choose "Create your free account", enter your name, e-mail and a strong password, and open the verification link.
2. **Complete your profile.** Enter age, monthly income after tax, EMIs, rent, education fees and the year they end, whether you have an emergency fund, your horizon, and answer the five-question risk quiz.
3. **Secure your account (recommended).** In Settings → Security, turn on two-step verification, scan the QR code with an authenticator app and store the eight backup codes safely.
4. **Add your portfolio.** On the Portfolio page add shares (symbol, exchange, quantity, average price) and mutual funds (search by name), then gold, deposits, savings, property, loans, rent received and monthly SIP. Net worth, liquid assets and surplus are computed for you.
5. **Ask about a decision.** Choose "New analysis", pick a holding and what you are thinking of doing (sell, hold or buy more), optionally enter how many months you have held it and, in "Why? In your own words", your reason—for example, "I need money for college fees in March".
6. **Watch the analysis.** Five steps appear as they complete. You can leave and come back; the progress is kept.
7. **Read the result.** Start with the recommendation and its reasons, then the two futures, the pattern found and its confidence, and the explanation (switch to हिंदी if you prefer). "How this was worked out" lists every assumption and any value that was filled in for you.
8. **Keep or check the record.** Download the report (HTML or PDF) and use "Verify this record" at any time to confirm the analysis has not been changed.
9. **Your data.** Settings → Your data lets you download everything held about you, switch optional AI help on or off, or delete your account (you can change your mind for 30 days).

# Appendix G: Screenshots and Evidence to Be Supplied

The following evidence is not in the repository and must be captured by the team before submission.

| # | Evidence | How to capture | Replaces |
|---|---|---|---|
| 1 | Result page (top: recommendation, futures chart, pattern) | Seed demo data (Appendix A.6), log in as a demo user, open a completed analysis at `/app/decisions/<id>`, browser window ~1366 px wide, full-page screenshot | Figure 9.7 |
| 2 | Live progress | Start a new analysis and capture while steps 2–3 are running | Figure 9.8 |
| 3 | Hindi explanation | On a result page switch to हिंदी, capture the explanation section | Figure 9.9 |
| 4 | Portfolio page | `/app/portfolio` for a demo user with shares, a fund and gold | Figure 9.10 |
| 5 | Verify this record | Click "Verify this record" and capture the verified message with "How this was worked out" expanded | Figure 9.11 |
| 6 | Test run logs | Run the commands in Table D.1 and save terminal output (pytest summary lines) | Section 10.2 status |
| 7 | System test observations | Complete the "Observed" column of Table 10.4 | Table 10.4 |
| 8 | Institutional details | Roll/UID numbers, names of HOD and Principal, submission month and year | Front matter |

Table: Table G.1: Evidence required from the team

To insert a screenshot in the Word document, right-click the placeholder image, choose *Change Picture*, and select the new file; the caption and numbering remain unchanged.

# Appendix H: Glossary

| Term | Meaning in this report |
|---|---|
| Calibration | Agreement between a model's stated confidence and how often it is right |
| Common random numbers | Using the same random scenarios for two alternatives so that their difference is not polluted by noise |
| Disposition effect | Tendency to sell winners too early and hold losers too long |
| Do-operator | Notation for setting a variable by intervention rather than observing it |
| Genesis hash | The fixed starting value of an investor's audit chain |
| Guard | Step that removes classes the label definitions rule out |
| Herd behaviour | Following what others are doing, especially selling into fear or buying into a rally |
| Isotonic regression | Fitting a non-decreasing function; used here to map raw confidence to calibrated confidence |
| Loss aversion | Feeling losses more strongly than equal gains; here panic-selling or refusing to sell a deep loser |
| Negative control | A variable known to have no effect, used to check that a method does not find spurious effects |
| Paired difference | HOLD minus SELL wealth on the same simulated path |
| Row-level security | Database policies that restrict which rows a session may see or change |
| SHAP value | A feature's additive contribution to a model's output for one prediction |
| Toss-up band | $0.40 < p < 0.60$, where the simulation does not clearly favour either choice |

Table: Table H.1: Glossary

# Appendix I: Repository Reference

The source code, data, models, evaluation scripts and this report's figure script are in the Git repository `https://github.com/ParamShah77/Folium`. The repository's `FOLIUM_MASTER.md` is the single current technical reference; `data/v4/DATASET_CARD.md`, `results/reports/BIAS_MODEL_V4.md`, `results/reports/SIMULATOR_V2.md` and `results/reports/CAUSAL_V4.md` contain the full model reports from which Chapters 8 and 9 are drawn. The companion research paper by the same authors, "Folium: Behavioral Decision Intelligence Through Calibrated Bias Detection, Causal Analysis, and Paired Long-Horizon Portfolio Simulation", reports the same development-stage results.
