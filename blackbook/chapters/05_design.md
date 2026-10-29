# Chapter 5: System Architecture and Design

All diagrams in this chapter are generated diagrams drawn from the structure of the code (`blackbook/make_figures.py`); none is a screenshot. Equivalent Mermaid definitions are supplied separately in `blackbook/diagram_sources/`.

## 5.1 High-Level Architecture

![Figure 5.1: Three-tier architecture of Folium (generated diagram)](figures/fig5_1_architecture.png){width=100%}

Figure 5.1 shows the three tiers. The **presentation tier** is a React single-page application [51]. During development the Vite server proxies every `/v1/*` request to the API, so the browser sees one origin; this keeps the httpOnly session cookies and the CSRF double-submit check simple.

The **application tier** is a FastAPI [50] service (`backend/main.py`). Its routers live in `backend/api/v1/`, its cross-cutting concerns in `backend/middleware/`, its authentication primitives in `backend/auth/` and its domain services in `backend/services/`. The analysis itself runs as a background task orchestrated by `backend/core/pipeline.py`.

The **analytics tier** is the research code in `src/`. A deliberate design decision is that the back end never re-implements the models: `backend/core/ml_bridge.py` is the only place where `backend/` reaches into `src/`. It adds the repository root to the import path, imports the heavy ML libraries lazily (about 2 seconds and 400 MB), runs blocking work in a thread so the event loop is not stalled, and maps vocabulary between the two worlds (for example `disposition` ↔ `disposition_effect`). The rationale, recorded in the master reference, is that the research modules produced the reported numbers, and re-implementing them would risk silently changing those numbers.

The **data tier** consists of PostgreSQL, which stores users, portfolios, decisions and the audit chain under row-level security, and a Redis-compatible store, which holds the token blacklist, rate-limit counters and the event backlog for live progress. External services are called only for prices and market data, and—optionally—for e-mail and Gemini.

## 5.2 Component Architecture of the Analysis Pipeline

![Figure 5.2: Components involved in one analysis (generated diagram)](figures/fig5_2_components.png){width=100%}

Figure 5.2 zooms into the pipeline. `decisions.py` handles `POST /v1/decisions/analyze`, schedules `run_analysis_pipeline` as a FastAPI `BackgroundTask` and returns immediately. The orchestrator calls five step functions in a fixed order defined in `events.STEP_ORDER`: bias detection, simulation, explanation, debate (recommendation) and audit. Each step is registered through `steps.register_step`; the step registry also holds placeholder implementations (`stub_steps.py`) so that the orchestration could be built and tested before the models existed. The first four steps call into `src/` through the bridge. The audit step writes to the `audit_logs` table directly.

A step returns a `StepResult` holding the columns to update and the fields to attach to its progress event; it does not write status or publish events itself. The orchestrator owns those responsibilities and refuses any step that tries to write the columns it reserves (`status`, `pipeline_step`, `error_message`, and so on). This separation is visible in Listing 6.11.

## 5.3 Data-Flow Diagrams

![Figure 5.3: Context-level (level-0) data-flow diagram (generated diagram)](figures/fig5_3_dfd0.png){width=92%}

At the context level (Figure 5.3) the system exchanges data with three external entities. The investor supplies their profile, holdings, the intended action and an optional comment, and receives a verdict, projections, an explanation and a verifiable record. Market data providers supply prices, NIFTY and VIX. The Gemini API is an optional entity: it receives a comment and analysis numbers only for investors who have consented and only when the server enables it, and its output is accepted only after checks.

![Figure 5.4: Level-1 data-flow diagram of the analysis process (generated diagram)](figures/fig5_4_dfd1.png){width=95%}

Figure 5.4 decomposes the analysis into six processes. Process 1.0 corresponds to the `analyze` endpoint (context capture); processes 2.0–6.0 correspond to the five pipeline steps. Every process writes its outputs into the `decisions` store (D2) and the next process reads the refreshed row, which is why the orchestrator reloads the decision before each step. The simulation reads the investor's profile and financial profile (D1) for income, SIP and the destination of sale proceeds; the final process appends an entry to the audit store (D3).

## 5.4 Use-Case Diagram

![Figure 5.5: Use-case diagram (generated diagram)](figures/fig5_5_usecase.png){width=92%}

Figure 5.5 shows the two human actors and one external system actor. The investor's use cases correspond to the routes listed in Appendix B; registration and login are available both by e-mail and through Google. The administrator's implemented use case is resetting a user's two-step verification (`backend/api/v1/admin.py`); the wider administrator console is the next planned milestone (Section 12.5). The market data service participates in portfolio management (live prices) and in analysis requests (market context and stock risk).

## 5.5 Activity Diagram

![Figure 5.6: Activity diagram of a decision analysis (generated diagram)](figures/fig5_6_activity.png){width=78%}

Figure 5.6 traces one analysis from the investor's input to completion. The synchronous part (the first three activities) ends with an HTTP 202 response so that the browser is never kept waiting for the models. The five shaded activities run in the background. If any step raises an exception, control leaves the main flow: the decision is marked `failed`, the error is stored, a `failed` event is published so that connected browsers stop waiting, and the error is reported to Sentry if configured. Wording problems never fail an analysis, because the explanation step falls back to template text.

## 5.6 Sequence Diagram

![Figure 5.7: Sequence diagram of an analysis with live progress (generated diagram)](figures/fig5_7_sequence.png){width=100%}

Figure 5.7 shows the message order. A subtle detail is the *backlog replay*. If the browser opened the stream only by subscribing to Redis pub/sub, any event published before the subscription (for example a fast first step) would be lost, and a reload during an analysis would show an empty history. `backend/core/events.py` therefore appends every event to a Redis list with a time-to-live as well as publishing it. The stream endpoint first replays the list and then follows live messages, de-duplicating by a per-decision sequence number. If the stream cannot be opened at all, the result page falls back to polling.

## 5.7 Entity–Relationship Design

![Figure 5.8: Entity–relationship diagram of the main tables (generated from Alembic migrations 0001–0012)](figures/fig5_8_er.png){width=100%}

Figure 5.8 shows the principal entities. `users` is the root: it holds the account, the Tier-1 financial profile, the deletion schedule (`purge_after`, `anonymised_at`) and the AI consent flag. `financial_profiles` has a one-to-one relationship with `users` and stores gold, deposits, savings, property, loans, rent received and monthly SIP. `portfolios` holds shares and mutual funds. Each analysis is a row of `decisions`, which stores both the inputs (including JSONB snapshots of the portfolio and the comment reading) and every model output. `audit_logs` holds the hash-chained entries; its foreign keys use `ON DELETE SET NULL` so that the chain survives anonymisation. Authentication support tables (`refresh_tokens`, `mfa_backup_codes`, `mfa_recovery_requests`) and `profile_change_log` complete the schema. Tables `bias_profiles`, `market_cache`, `sip_registrations` and `kite_tokens` exist from earlier plans but are reserved and not used by the current product.

Row-level security is enabled and forced on `decisions`, `audit_logs`, `portfolios`, `sip_registrations` and `profile_change_log` (migration 0007), with `financial_profiles` added later. Each policy compares the row's `user_id` with a per-transaction setting, as explained in Section 6.10.

## 5.8 Deployment Diagram

![Figure 5.9: Deployment diagram of the development and demonstration set-up (generated diagram)](figures/fig5_9_deployment.png){width=95%}

Figure 5.9 shows the configuration actually used: all processes on one Windows laptop with native PostgreSQL 18 and Memurai. PostgreSQL has two roles: `finai`, the owner used for migrations, and `app_user`, a non-superuser used by the application so that RLS policies bind. Model artefacts and result files are read from disk. A container set-up exists in the repository but has not been used, and no production deployment with HTTPS exists yet.

## 5.9 User-Interface Design

The front end (`frontend/src/pages`) has public pages (landing, privacy, authentication, and `/auth/google`, where Google sign-in returns) and application pages under `/app`. A first Google sign-in lands on `/app/welcome`, which collects the Tier-1 profile; until it is filled, every other signed-in page except Settings redirects there. The remaining application pages are an overview dashboard, the portfolio, a new-analysis form with a live market card, the result page, history and settings. The result page is the centre of the design. In order, it shows the live five-step progress (with plain titles such as "Reading your decision" and "Projecting the future"), the recommendation with its reasons, the position against the whole portfolio, a chart of both futures, the pattern found with probability bars, the six-part explanation with an English/हिंदी switch, report downloads, "What weighed most", cause and effect, both sides in numbers, "In your own words", "Verify this record" and "How this was worked out". Product rules applied throughout are: no model names or accuracy figures, confidence as High/Medium/Low, and a light or dark theme with serif headings.

Screenshots of these pages are not included in the repository, and we have not reproduced them for this report. Appendix G lists the screenshots to capture and how to capture them; placeholders are reserved in Chapter 9.
