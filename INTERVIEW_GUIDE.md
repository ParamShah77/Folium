# Folium: interview guide

How to explain this project out loud: what it is, what was built, how, and why every major choice was made. Everything here is taken from the repository (`FOLIUM_MASTER.md`, the three model reports, the git history). Numbers are the ones in those documents, so they are safe to quote.

Read it in this order: **§1 pitches** (memorise), **§2 story** (the timeline), **§3 to §9** (the how and why of each part), **§10 honest weaknesses** (rehearse these, they are what a good interviewer goes for), **§11 questions and answers**, **§12 number cheat sheet**.

---

## 1. The pitches

### 20 seconds

"Folium is a web app for Indian retail investors. You tell it about one holding and what you're thinking of doing: sell, hold or buy more. It looks at that decision against your whole financial picture, names the behavioural bias that may be behind it, projects both choices over your own horizon in rupees after tax, explains it in English or Hindi, and gives an evidence-based recommendation. Every analysis is sealed into a tamper-evident record."

### 2 minutes

"Most investing tools look at a stock. I wanted one that looks at the *person* deciding about the stock. Panic-selling in a crash, holding a loser to get back to even, buying a rally because everyone is: these are documented behavioural patterns and they cost real money. But the same sale can be perfectly sensible if you need the cash for college fees. So the hard part is telling the two apart, using the investor's income, loans, emergency fund, portfolio and horizon, plus what the market was doing.

It started as a research project with four ideas: detect the bias in real time, simulate long-horizon outcomes for an individual portfolio, explain decisions in plain language, and make the advice verifiable. I then turned it into a full product: a FastAPI backend with real authentication, PostgreSQL with row-level security, a React frontend, and a five-step analysis pipeline that streams live progress.

Under the hood there are four engines: an XGBoost bias model trained on 20,000 decisions built on real NIFTY and VIX history, a Monte Carlo simulator built from real NIFTY and gold history with Indian tax rules, a causal-inference module that measures what actually pushes a decision, and an explanation engine that writes in English and Hindi from templates so it can never invent a number. The recommendation itself comes from written rules, not from an AI. Optional Gemini help exists, but it is fenced in so it cannot change a number or the verdict."

### The one-line "why is it different"

"It judges the decision against the whole portfolio and the person's situation, it tells you honestly how sure it is, and it can prove afterwards that the advice wasn't altered."

---

## 2. The story: what we did, in order

The commit history shows five stages.

| When | Stage | What happened |
|---|---|---|
| Jan to Feb 2026 | **Research plan** | Initial plan: a "Financial Decision Intelligence System" with causal reasoning and blockchain-style auditability. Then four written research **gaps**, each its own document (12 Feb): Gap 1 causal decision-time reasoning (catch a bias as it happens), Gap 2 individual portfolio long-horizon evaluation, Gap 3 decision-centric explainability, Gap 4 counterfactual-verifiable auditability. Synthetic datasets built (income, edge cases such as deficit households, emergency funds). |
| Feb to May 2026 | **Research code** | Gap 1 bias detector (models v1 to v3, XGBoost), Gap 2 long-horizon portfolio simulator (v1), a financial-intelligence database, notebooks. A Streamlit and SQLite prototype was the "product". |
| Jul 2026 | **Production backend (milestones M0 to M2)** | Replaced the prototype with a real backend: auth core, `/v1` API, Alembic migrations, PostgreSQL with row-level security (and a fix when RLS turned out to be silently bypassed because the app connected as a superuser), TOTP two-step verification, Google OAuth, profile endpoints. |
| Sep 2026 | **Gap 3 explainability engine** | The English and Hindi explanation engine with HTML and PDF reports. |
| 6 to 9 Oct 2026 | **Folium web app and the new-ML phase** | The React app, the ML bridge, then Phase A (new models), Phase B (trust and data rights), Phase C1 (Google sign-in). Pushed to `github.com/ParamShah77/Folium` on 8 Oct. |

### The Phase plan from October (know this, it shows planning)

- **Web app first.** Get something real and demoable end to end (auth, portfolio, pipeline, UI), using the existing research models through a bridge.
- **Phase A: new ML.** A1 dataset v4 and 4.1, A2 bias model v4, A3 simulation v2, A4 causal re-run. Each step ended with a check-in on results before moving on.
- **Phase B: trust.** B1 audit chain with "Verify this record", B2 data export and account deletion with a 30-day grace period, B3 comment reading and "both sides" with optional Gemini.
- **Phase C: finish.** C1 Google sign-in end to end (done), C2 admin panel, C3 CI, C4 deployment with HTTPS (these three are pending).
- Also done: an audit of the ML and the formulas (found and fixed a wrong tax-slab calculation, a "% confidence" leak into plain-language text, and a duplicated dictionary that made a sentence read "Your choice to holding on").

**Why the order (web app first, models second)?** To have a working, demonstrable product early and a stable interface for the models to plug into. The bridge meant I could swap v3 for v4 later by changing one environment variable, with the old version kept for rollback.

---

## 3. Architecture and why

```
Browser (React SPA)  →  /v1/*  →  FastAPI backend  →  PostgreSQL 18 (row-level security)
                                       │              Redis (blacklist, rate limits, live events)
                                       └─ background pipeline → ml_bridge → src/ (models, simulator, causal, explainer)
```

| Choice | Why |
|---|---|
| **The ML bridge** (`backend/core/ml_bridge.py`) | The research modules produced the reported numbers. Re-implementing them in the backend risks silently changing them. The bridge is the only place `backend/` touches `src/`; it imports lazily (the ML libraries take about 2 s and 400 MB to load), runs blocking work in a thread, and fails loudly if the libraries are missing rather than falling back to made-up numbers. |
| **FastAPI + async + background pipeline** | The analysis takes seconds. `POST /decisions/analyze` returns `202` immediately; the browser follows progress. |
| **Server-sent events, not WebSockets** | Progress is one-directional (server to browser), SSE is simpler, works over plain HTTP and reconnects by itself. Events go through Redis, and the server replays the backlog first, so reloading mid-analysis still shows the full history. If the stream can't open, the page polls. |
| **PostgreSQL with row-level security** | Data isolation enforced by the database, not just by application code. A bug in a query cannot leak another user's row. |
| **Redis** | Token blacklist (logout), rate-limit counters, the SSE event bus. |
| **Python 3.13 everywhere** | `dowhy 0.14` caps scipy at 1.15.3 on older Pythons, which would change the scipy version the model artefacts were built with. |
| **Native Postgres and Redis (Memurai), no Docker locally** | Simpler on a Windows laptop; Dockerfile and compose file exist for later deployment. |
| **Market and portfolio snapshot stored on the decision** | A re-run reproduces the original analysis, which the audit chain depends on. No live fetch at inference time. |
| **React 19, Vite, TypeScript, Tailwind 4, shadcn-style Radix components, TanStack Query, React Hook Form + Zod, Recharts** | Standard modern stack: typed forms with schema validation, server-state caching, accessible primitives. |

**Frontend design:** soft palette (teal, blush, cream, orange used sparingly), serif headings. HOLD is teal and SELL is taupe, deliberately not green and red, so the colours don't pressure. Light and dark themes, responsive to phones. Product rules set early: no model names or accuracy figures in the UI, confidence shown as High / Medium / Low, plain titles on live steps.

---

## 4. The analysis pipeline: the heart of the app

User picks a holding and an action (sell / hold / buy more), optionally months held and a free-text reason.

1. **Submission** captures: market context (NIFTY 1-month return, 30-day volatility, India VIX), a portfolio snapshot, and the stock's measured beta and own volatility. All are stored on the decision.
2. **Five steps**, each publishing running/done events:

| Step | What | Why this order |
|---|---|---|
| 1. Reading your decision | Read the comment, then run the bias model | The comment can state a cash need, which is an *input* to the bias model, so it must be read first |
| 2. Projecting the future | Simulation v2, hold vs sell | Needs the investor's horizon and portfolio |
| 3. Explaining | Causal v4 + explanation engine (English and Hindi) | Uses the bias reading and the simulation numbers |
| 4. Forming a recommendation | Evidence rules, then "both sides" | The verdict reads only numbers; the two cases are written *after* it |
| 5. Saving a secure record | Append to the audit chain | Must hash the finished analysis |

**Design rules inside it:** step functions return results; the orchestrator owns status, events and persistence and refuses steps that try to write its columns. Each step reads the decision row afresh. A failure marks the decision `failed`. A per-investor advisory lock keeps the audit chain linear if two analyses finish together.

**Missing data is disclosed, never hidden:** gaps are filled with the model's training medians and listed under "How this was worked out" on the result page. If live market data is down, a calm market is assumed and the page says so. If a stock has too little history, the median NIFTY 50 stock (beta 1.0, own swings 21%) is used and disclosed.

---

## 5. The models: what, how, why

### 5.1 Training data (dataset v4.1)

- 20,000 synthetic investor decisions on **real** NIFTY 50 and India VIX, 2008 to 2026 (4,255 usable trading days).
- Each case: a real trading day, a household (income, EMIs, rent, fees, emergency fund, risk, horizon), a portfolio, an action, a gain or loss derived from the real NIFTY move × the stock's beta + stock-specific noise, and a **label**.

**Why synthetic?** There is no public dataset of Indian retail investors' decisions labelled with the psychological motive behind them. Nobody can observe *why* someone sold. So the labels follow behavioural-finance definitions. I'm upfront about this (see §10).

**How the labels are made: motives, not rules.** Each investor has hidden tendencies (loss aversion, herd sensitivity, disposition), partly explained by observable traits. The *situation* decides which bias motives could apply, those compete with a rational motive, the winner sets the action and **is the label**. So the same sale can be rational or biased and the model must infer which.

| Pattern | Applies when |
|---|---|
| Loss aversion, panic | At a loss, NIFTY down 2%+ in the month, high fear (VIX ≥ 20 or correction/crash) → sell |
| Loss aversion, refusal | Position down 25%+ → hold |
| Disposition, sell winner | Up 8%+ in normal or rising market → sell |
| Disposition, hold loser | Down 5 to 25% in normal or rising market → hold |
| Herd, sell into fear | VIX ≥ 22 or NIFTY down 5%+ → sell |
| Herd, buy into rally | NIFTY up 4%+ → buy more |
| Rational | The investor's own situation explains it (rebalancing, goal near, **needs cash**, buy value, cut a loss) |

**Version 4.1** added stretched households (8.2% of borrowers with EMIs above 60% of income, following RBI's stress threshold), 44% without an emergency fund, and cash shocks, so a *forced sale* can be read as rational. Labels: rational 55.7%, herd 19.6%, disposition 14.7%, loss aversion 10.0%. Hidden tendencies are stored as `latent_*` columns and never given to the model.

### 5.2 Bias model v4.1 (XGBoost)

- **22 inputs:** the action, gain/loss, holding period, market state (NIFTY return, VIX, volatility), which patterns the definitions allow here, age, horizon, risk tolerance, surplus ratio, emergency fund, position/equity/gold shares, property, debt ratio, and `cash_need_stated`.
- **402 trees, depth 5**, tree count from 5-fold cross-validation with early stopping.
- **Guard:** any pattern the definitions rule out is set to zero.
- **Confidence:** the chosen pattern's probability through a centred isotonic calibration curve fitted on out-of-fold predictions and weighted to real market frequencies. Shown as High ≥ 0.85, Medium ≥ 0.65, Low below. Never as a raw percentage.
- **Explanations:** exact TreeSHAP for the chosen pattern, grouped into 18 plain drivers. They sum to the model score within 1e-5.
- Stored as native XGBoost JSON, not a pickle (safer to load, no arbitrary code execution).
- **Years of investing deliberately not an input**: the app doesn't collect it and adding it gained 0.5 points.

**Results (real-frequency test set):** accuracy **87.9%**, macro-F1 0.840, calibration error 0.014, 21 of 21 sense checks. Versus v3: 53.4%, 0.309, 0.254, 5 of 13 scenarios. v3 never depended on the action; v4's answer depends on the action in 84% of cases.

**Why those evaluation choices matter (be able to explain):**
- *Re-weighting to real frequency.* Crashes are over-sampled in the data (24.5% of cases vs 6.6% of real days), so raw accuracy would mislead. Quote the re-weighted number.
- *Calibration matters more than accuracy here.* High confidence is right 98.7% of the time (68% of analyses), Medium 74%, Low 62%. "Low" usually means two patterns are close to a coin toss, and the UI shows which two.
- *Temporal validation.* A model trained only on 2008 to 2019 scored 86.5% on 2020 to 2026, a period it had never seen.

### 5.3 Simulation v2

Compares **holding vs selling** over the investor's own horizon (1 to 30 years; 20 only if none given, and the page says so), on the **same simulated markets** for both choices so the comparison measures the decision, not luck.

- **Futures:** each simulated month is a real month of NIFTY (+1.25% dividend yield) and gold-in-rupees, drawn in **12-month blocks** with wrap-around ("circular block bootstrap"). Blocks preserve crashes with their recoveries and the real share/gold correlation.
- **Growth reset:** replaying history exactly would assume gold keeps compounding at ~14.8%. So the swings are kept but typical growth is set to stated long-run rates: shares 11%, gold 9%, FD 6.75%, savings 3%.
- **The holding:** a stock moves with the market by its own **beta** plus company-specific volatility, both measured from 10 years of monthly prices at submission. Typical growth = FD rate + beta × (share growth − FD rate), the CAPM-style standard. A mutual fund tracks the market within 3%.
- **Selling:** 0.15% charges + real tax; proceeds go into the investor's own FD / savings / gold in their *current split* (so the alternative is realistic, not "cash").
- **Tax (FY 2025-26, new regime):** equity short-term 20%; long-term 12.5% above ₹1.25 lakh; gold 12.5% after 24 months; FD/savings interest at the investor's slab; 4% cess. The app asks for take-home pay, so I invert the tax function (`gross_from_take_home`, including Section 87A marginal relief) to find gross income and the right slab.
- **Output:** median, bad-case (10th percentile) and good-case (90th) wealth per year, the share of futures where holding wins, and the typical paired gap.

**Realism check against the real index (rolling 12 months):** bad year −6.9% simulated vs −7.5% real; typical +11.6% vs +11.3%; good year +34.7% vs +33.3%. The old v1 paths had bad years twice as bad as reality (−15.8%).

**What changed from v1 and why:** v1 was always 20 years, pre-tax, used synthetic paths wilder than the real index, and gave a stock and a fund the same answer. v2 fixed each of those.

### 5.4 Cause and effect v4

**The problem it solves:** "SHAP says VIX mattered" is correlation inside a model. I wanted to say what *actually pushes* a decision, and which habit helps.

**How:** because the dataset is generated by written rules, I replicated the generator exactly (matching all 20,000 stored decisions to 4 decimals). That lets me change any input and recompute the **true** causal effect. The estimates the *app* uses come from the data alone, like a real study: **DoWhy backdoor adjustment** (with placebo, random-common-cause and subset refutation tests) and **g-computation** with gradient boosting. Then I compared them against the known truth.

- Average error 0.5 points over 45 effects; right direction 97%; 12 of 13 refutation tests pass.
- **Gold share is a negative control** (no causal path by construction); both methods correctly estimate about zero.
- Key effects: a cash shock raises the chance of selling by ~32 points; an emergency fund lowers it ~7.5; 10 more VIX points raise it ~6.4.
- **Habits** are modelled as halving the tendency they act on (an assumption, stated). The app offers the *single* best habit, never a bundle, because habits can offset each other.

**Why it's a strong point:** most causal work can't be validated because the truth is unknown. Here it can, by construction. The caveat (be ready for it): this validates the *method*, not the real world.

### 5.5 Recommendation (evidence rules, deliberately not ML or LLM)

`p` = share of simulated futures where holding beat selling.

| Intent | Rule |
|---|---|
| Sell | p ≥ 0.60 → HOLD; p ≤ 0.40 → SELL; in between: HOLD if the sale looks biased, else SELL |
| Hold | p ≤ 0.40 → SELL, otherwise HOLD |
| Buy more | herd or a bias with confidence ≥ 0.60 → HOLD; else BUY MORE if p ≥ 0.50, else HOLD |

**Why rules?** Money advice must be inspectable. Every verdict stores its reasons and the exact numbers used, so a person can check it by hand. A language model should never decide about money. (`debate_transcript.engine = "evidence_rules_v1"`.)

### 5.6 Explanation engine (English and Hindi)

- Six sections: In short; What's going on right now; Your two possible futures; The story of your money; Why we're telling you this; What to do now.
- **Templates are authoritative.** Every sentence is a hand-written Jinja2 template filled from one `facts` dict with `StrictUndefined`, so a missing fact fails a test instead of printing a blank. A template cannot invent a rupee figure. 34 templates each in English and Hindi, structurally identical (enforced by tests), so Hindi works fully offline.
- **No jargon:** a translation layer maps internal terms ("p10", "opportunity cost") to plain phrases; a 30-term blocklist is tested. Money is formatted the Indian way (₹1.2 lakh, ₹1,32,451).
- **The typical outcome is narrated, not the average**, because wealth is right-skewed and the mean would contradict the year-by-year table.
- **Optional AI rewording** (Gemini Flash-Lite, off by default): "may reword, may not introduce, remove or alter a number." Every number must already appear in the original, placeholders intact, length within 0.6× to 1.8×, or the reply is discarded and the template is used. Two failures in a row pause the layer for 5 minutes.
- **Reports:** HTML in both languages, PDF in English only. ReportLab can't shape Devanagari, so a Hindi PDF is refused and the HTML (which prints to correct PDF from a browser) is offered. "Broken typography is worse than an honest alternative."
- **Measured:** completeness, actionability, personalisation 100%; 0 jargon leaks; English Flesch 78.3; Hindi 12.2 words per sentence.

### 5.7 Audit chain ("Verify this record")

Every completed analysis appends one entry to that investor's own hash chain in `audit_logs`:

```
inputs_hash   = sha256(canonical(holding, prices, action, reason, market, portfolio, comment reading))
analysis_hash = sha256(canonical(pattern + confidence, projection, explanation, recommendation))
chain_hash    = sha256(previous_hash + payload_hash)
genesis       = sha256("GENESIS:{user_id}:{created_at}")
```

- **Verify answers two questions:** is the chain intact (walk the links from genesis; catches an altered, removed, forged or forked entry), and does the analysis on screen still match its record (recompute both fingerprints, name what changed).
- `audit_logs` is append-only via `DO INSTEAD NOTHING` rules for UPDATE and DELETE.
- Each entry stores the list of columns it covers, so the set can grow without older entries failing.

**Honest framing:** this is tamper-*evident*, not tamper-*proof*. A database owner could rewrite the whole chain. It makes silent edits detectable; it isn't a distributed blockchain, and I chose not to build one because a per-user hash chain gives the useful property (detect changes) without consensus infrastructure the product doesn't need. That is a deliberate scope decision from the original "blockchain-style" research idea.

### 5.8 Comment reading and "both sides"

- **Reading "Why? In your own words":** phrase rules (English, Hinglish, Hindi) run always and offline. They find *facts* (need for money: fees, EMI, medical, wedding, "paise chahiye"; a too-big holding; a close goal) and *feelings* (fear of loss, following others, waiting to break even, locking in a gain, FOMO), each with the sentence quoted word for word.
- **Facts can change the reading; feelings never do.** A stated cash need sets the model's `cash_need_stated` input so a forced sale can read as rational. Feelings are only quoted back, with a note on whether they agree with the reading. *Why:* a cash need is a real constraint the model should know; text moving the analysis on feelings would be easy to game and hard to defend.
- **Gemini, only with the investor's consent and a server flag.** Its answer is accepted only if every item has an allowed kind and a quote that appears word for word in the comment; otherwise discarded.
- **Both sides in numbers:** the case for each choice is built from the analysis's own numbers. It never feeds the verdict.

---

## 6. Backend, auth and security: what and why

| Area | What I did | Why |
|---|---|---|
| Passwords | bcrypt cost 12; zxcvbn score ≥ 3 | Slow hash resists brute force; strength meter beats arbitrary composition rules |
| Sessions | RS256 JWT: access 15 min, refresh 7 days with rotation; httpOnly cookies, SameSite=Lax, Secure outside dev; dual-jti blacklist in Redis | Short-lived access limits damage; httpOnly keeps tokens away from JavaScript; blacklist makes logout real |
| "Keep me signed in" | Off = session cookies | Shared computers |
| CSRF | Double-submit cookie: `csrf_token` must equal the `X-CSRF-Token` header on every mutating request | Cookies are sent automatically, so mutating requests need proof of origin |
| Two-step verification | TOTP (secret encrypted with Fernet), 8 bcrypt-hashed backup codes, recovery requests resolved by an admin who must prove their own TOTP | Lost-phone path that doesn't become a bypass |
| Google sign-in | OpenID Connect via Authlib; single-use `state` in Redis (10 min) carrying "remember me" and the return page; only Google-**verified** emails; result returned in the URL **fragment** | State prevents login CSRF; verified-email rule stops someone linking an unverified address to another person's account; a fragment never reaches a server, so single-use tokens stay out of logs and Referer headers |
| Re-verification | Changing email, income, EMIs etc. needs password (+ TOTP); email change also needs a code to the old address; every change logged with the old value hashed | Account-takeover damage limits, and an audit trail |
| Row-level security | App connects as non-superuser `app_user`; every query runs in a transaction that sets `app.current_user_id`; `FORCE ROW LEVEL SECURITY` | **A superuser silently bypasses RLS**: I found that in July, and the fix was to connect as `app_user` |
| Rate limiting, headers, CORS | slowapi on Redis; security headers; CORS restricted | Abuse and browser hardening |
| Error shape | `{error, message, request_id}` everywhere | Debuggable, consistent client handling |

**Foreign ids return 404, not 403** because RLS makes the other user's row invisible, which also avoids confirming that the id exists.

### Data rights

- **Download my data:** full JSON export (without password hash, MFA secret or tokens).
- **Delete my account:** needs password (+ TOTP), signs out everywhere, 30-day grace period during which login offers "Keep my account". After that the account is **anonymised**, not deleted: personal fields, profile, holdings, sessions, and each analysis's comment, snapshot, explanation and projections are erased.
- **Why anonymise instead of delete?** `audit_logs` is append-only and the user row anchors the chain's genesis. The entries stay, unlinked to any person. This is a conscious trade-off between erasure rights and tamper-evidence, and I can explain it.

### Privacy

- Only a ticker or fund code goes out for prices. Gemini receives a comment and the analysis numbers (never name or email) only if the investor opts in *and* the server enables it. The in-app Privacy page states only what's true today.

---

## 7. The database

Tables: `users`, `refresh_tokens`, `mfa_backup_codes`, `mfa_recovery_requests`, `profile_change_log`, `decisions`, `audit_logs`, `portfolios`, `financial_profiles` (plus reserved ones). RLS on every user-owned table. Migrations with Alembic, 0001 to 0012, run under an owner role while the app uses the least-privileged `app_user`. The migrations map to the history of the build: 0003 decisions, 0004 audit, 0007 RLS + `app_user`, 0008 market features, 0009 Tier 1 outflows and financial profile, 0010 SIP, 0011 deletion schedule, 0012 comment facts and AI consent.

---

## 8. Inputs and the portfolio

**Tier 1, required at sign-up:** age, take-home income, EMIs / rent / education fees (and the year they end), emergency fund, a five-question risk quiz (each answer 0 to 3, `risk = total / 15`), horizon, style, goal.
**Tier 2, optional:** shares (live NSE/BSE via Yahoo Finance), mutual funds (searched and priced via MFAPI.in), gold (grams × `GC=F × INR=X / 31.1034768`), FDs, savings, property, loans, rent received, monthly SIP.

```
monthly surplus = income + rent received − (EMIs + rent paid + education fees)
liquid assets   = stocks + funds + gold + FDs + savings
net worth       = liquid + property − home loan − other loans
```

Decisions worth knowing: a price outage never breaks a page (average cost + "price unavailable"); prices cached 15 minutes; gold uses the international price and says so; crypto is excluded; sensitive fields can be filled once freely but changed only with re-verification.

---

## 9. Engineering practice

- **Tests:** 267 backend (149 run without a database), 343 root tests for models/data/explainer/simulator/causal (5 skipped without an AI key), 25 frontend. Template-structure tests, jargon blocklist tests, tamper tests for the audit chain, and sense-check scenarios for the models.
- **Rollback switches:** `BIAS_MODEL_VERSION=v3`, `SIMULATOR_VERSION=v1`. Old models and datasets are kept next to the new ones.
- **Reproducibility:** fixed seeds, scripts to regenerate every model and report, `verify_ml_env.py` checks pinned library versions, `seed_demo.py --refresh` regenerates demo analyses.
- **Documentation discipline:** `FOLIUM_MASTER.md` is the single source of truth; model reports record both wins and weaknesses.
- **Process:** check-ins with results after each ML step; the agreed definitions were discussed before building (e.g. what makes a pattern possible in a calm market).
- **A formula audit near the end** caught real bugs (tax slab used take-home as gross; duplicated dictionary garbling a sentence; "% confidence" leaking into text). This is a good story: I looked for errors rather than assuming correctness.

---

## 10. Honest weaknesses (rehearse these)

1. **Synthetic investors, real markets.** Labels follow behavioural-finance definitions, not observed Indian investors. 87.9% means "recovers the agreed definitions from the data", not "is right about real people's psychology".
2. **The circularity question.** The labels come from rules, so a model can score well by learning the rules. I measured this directly: a rules-only baseline reaches **85.2%**, the model **87.9%**, and a model that can also see the hidden tendencies **90.0%**. So the model's real value is *calibrated confidence* and judgement on ambiguous cases (78.3% on the 56% of cases that need judgement), not raw accuracy.
3. **Loss aversion vs herd in a fearful sell-off is close to a coin toss.** That's why it shows Low confidence with both probabilities.
4. **Calm markets can only read disposition effect, deep-loser loss aversion, or rational.** By the definitions, not a bug.
5. **Growth rates are assumptions** (11 / 9 / 6.75%). Results are most sensitive to the share growth rate and the stock's own volatility; both are stated on the result page and in the sensitivity table.
6. **Nominal rupees**, inflation not removed. Mutual funds treated as equity (a debt fund would look too risky). Tax assumes the ₹1.25 lakh exemption is available and doesn't set off losses. Gold excludes import duty and GST.
7. **One position per decision.** No "rebalance the whole portfolio" analysis.
8. **Unstated cash needs are missed:** forced sales read as rational 91% when the need is stated, 39% when it isn't. Comment rules are phrase lists and miss paraphrase.
9. **AI help has not been run live** (no Gemini key on the machine); its acceptance rules are tested with a stand-in. Don't claim it works live.
10. **Not yet done:** admin panel (C2), CI (C3), deployment with HTTPS (C4). Google sign-in works only at the registered address. Locally there is no HTTPS or real email service (dev mailbox).
11. **Tamper-evident, not tamper-proof** (see §5.7).
12. **Not investment advice.** Information and education only.
13. **Working-tree state:** the Google sign-in work, Welcome page and updated docs are uncommitted at the time of writing. Commit before you present.

---

## 11. Likely questions, with answers

**Q: In one sentence, what problem does it solve?**
Retail investors make costly emotional decisions, and generic tools can't tell a panic sale from a sensible one; Folium judges the decision against the person's whole situation.

**Q: Why synthetic data? Isn't that a weakness?**
Yes, and I say so. Motive labels don't exist in any real dataset because nobody can observe why someone sold. I used real markets (NIFTY, VIX 2008 to 2026) and behavioural-finance definitions to generate labelled decisions, designed so the same action can be rational or biased. I then measured honestly how much the model adds over the rules: 85.2% rules, 87.9% model, 90.0% ceiling. Real user feedback would let the weights be learned later.

**Q: If you wrote the rules that make the labels, isn't 87.9% meaningless?**
It's not "accuracy on the real world". It shows the model recovers the definitions including from noisy hidden tendencies, handles ambiguous cases (78.3% on those), and, importantly, is *calibrated*: High confidence is right 98.7% of the time. The value is knowing when it doesn't know.

**Q: Why XGBoost?**
Tabular data of mixed features, 20,000 rows: gradient-boosted trees are the strongest practical choice, handle interactions without scaling, and have exact TreeSHAP explanations. A neural network would add opacity without benefit at this size.

**Q: How do you explain a prediction?**
Exact TreeSHAP for the chosen pattern, grouped into 18 plain drivers that sum to the model score within 1e-5. The result page shows which factors pointed toward the pattern and which pointed away.

**Q: What is calibration and why did you do it?**
Whether stated confidence matches observed accuracy. Raw tree probabilities aren't calibrated. I used isotonic regression fitted on out-of-fold predictions, weighted to real market frequencies since crashes were over-sampled. Calibration error went from 0.254 (v3) to 0.014.

**Q: What does the simulator do differently from a basic Monte Carlo?**
It resamples real 12-month blocks of NIFTY and gold history (keeps crashes and correlation), resets the long-run growth to stated rates, uses the stock's own beta and idiosyncratic volatility, applies Indian tax, compares hold and sell on the *same* paths, and reports the after-tax in-hand value. I validated its single-year distribution against the real index.

**Q: Why block bootstrap instead of a normal distribution?**
Returns are fat-tailed and autocorrelated; crashes cluster with recoveries. Drawing independent normal returns understates that. Block resampling preserves it.

**Q: Why reset the growth rate?**
Replaying 2007 to 2026 exactly would bake in gold's unusual ~14.8% run. I keep the real swings but set the typical growth to long-run assumptions, and state them. The sensitivity analysis shows how much the answer moves.

**Q: How do you handle tax?**
FY 2025-26 new-regime rules for equity short and long term, gold, and interest at the slab rate. Because the app asks for take-home, I invert the tax function to get gross income (including 87A marginal relief) so the slab is right.

**Q: What does the causal module add over SHAP?**
SHAP explains the model; the causal module estimates the effect of changing a factor in the world. It uses DoWhy adjustment and g-computation, and I validated against the known true effects from the generator (0.5-point average error), with gold share as a negative control.

**Q: Why not use an LLM for the recommendation or explanations?**
A language model can hallucinate a rupee figure or change advice. The verdict comes from inspectable rules; the text from templates; Gemini is optional, consent-gated, can only reword, and its output is rejected if any number changes or any quote isn't verbatim.

**Q: How does the live progress work?**
The analyze call returns 202; a background task runs five steps and publishes events to Redis; the browser subscribes over SSE. The server replays the backlog first so a reload doesn't lose history; the client polls if the stream fails.

**Q: What stops one user seeing another's data?**
PostgreSQL row-level security. The app uses a non-superuser role and sets the current user id per transaction. I discovered that a superuser bypasses RLS silently during testing and fixed it.

**Q: How is auth secured?**
bcrypt, RS256 JWTs in httpOnly cookies with rotation and a Redis blacklist, double-submit CSRF, TOTP with encrypted secrets and backup codes, rate limiting, re-verification for sensitive changes.

**Q: How does the audit chain work, and can it be forged?**
Each entry hashes the inputs and analysis and links to the previous entry's hash. Edits, deletions or forks break the chain and verification names what changed. It's tamper-evident, not tamper-proof; someone with full database control could rewrite the whole chain, which is why I describe it that way.

**Q: How do you reconcile "right to delete" with an append-only log?**
Anonymise: erase everything personal and keep only the unlinked hash entries and the user id that anchors the chain.

**Q: What would you do with more time?**
Learn the motive weights from real user feedback; outcome tracking; admin panel, CI and deployment with HTTPS; broker integration; wider comment rules from real comments; inflation-adjusted outputs; whole-portfolio rebalancing analysis; proper debt/hybrid fund handling.

**Q: What was the hardest problem?**
Defining labels honestly: making the same action rational or biased depending on context, and making the model's confidence mean something. Second: validating causal estimates, solved by replicating the generator.

**Q: What bug are you proudest of finding?**
The row-level-security bypass (superuser), and in the final audit the tax slab using take-home as gross income.

**Q: How did you test it?**
Unit and integration tests at three layers, tamper tests for the chain, template-structure and jargon tests for the explainer, sense-check scenarios and out-of-time validation for the model, a realism check for the simulator, and refutation tests for the causal module.

**Q: Why is HOLD teal and SELL taupe?**
Green and red imply good and bad. The goal is to inform, not to pressure.

**Q: Is it investment advice?**
No. It is for information and education, and says so.

**Q: Did you use AI tools to build this?** *(answer truthfully)*
Be ready to say how you used them and, more importantly, to explain every design decision and trade-off in your own words. This guide is built for exactly that; the interviewer will probe understanding, not tools.

---

## 12. Number cheat sheet

| Fact | Value |
|---|---|
| Training cases | 20,000 (real NIFTY/VIX, 10 Jun 2008 to 5 Oct 2026; 4,255 trading days used) |
| Labels | rational 55.7%, herd 19.6%, disposition 14.7%, loss aversion 10.0% |
| Bias model | XGBoost, 22 features, 402 trees, depth 5 |
| Accuracy / macro-F1 / ECE | 87.9% / 0.840 / 0.014 (v3: 53.4% / 0.309 / 0.254) |
| Rules-only baseline / hidden-trait ceiling | 85.2% / 90.0% |
| Judgement-needed subset | 78.3% (56% of cases) |
| Out-of-time check | trained 2008 to 2019, 86.5% on 2020 to 2026 |
| Confidence | High ≥ 0.85 (right 98.7%, 68% of analyses); Medium ≥ 0.65 (74%); Low (62%) |
| Sense checks | 21 / 21 |
| Forced sale read as rational | 72% (91% when stated, 39% when not) |
| Simulator growth | shares 11%, gold 9%, FD 6.75%, savings 3%; dividends 1.25%; charges 0.15% |
| Simulator realism | bad year −6.9% vs real −7.5%; typical +11.6% vs +11.3%; good +34.7% vs +33.3% |
| Tax | equity ST 20%, LT 12.5% above ₹1.25 L, gold 12.5% after 24 months, cess 4% |
| Causal | 0.5-pt mean error, 45 effects, right direction 97%, 12 of 13 refutations |
| Causal effects | cash shock +32 pts, emergency fund −7.5, +10 VIX +6.4 |
| Explanations | 34 templates per language, 6 sections, Flesch 78.3, 0 jargon leaks |
| Recommendation thresholds | p ≥ 0.60 hold, p ≤ 0.40 sell |
| Auth | access 15 min, refresh 7 days, bcrypt cost 12, 8 backup codes |
| Account deletion grace | 30 days |
| Tests | 267 backend, 343 root, 25 frontend |
| Migrations | 0001 to 0012 |
| Repo | github.com/ParamShah77/Folium, branch master |

---

## 13. A 5-minute demo script

1. Landing page: what it is, the four patterns, the security section.
2. Log in as Ananya (`ananya.iyer@example.com`, see `DEMO.md`): dashboard, then Portfolio (net worth, surplus, live prices).
3. New analysis: HDFCBANK, **Sell**, with a reason. Watch the five live steps.
4. Result: recommendation and reasons; both futures chart after tax; the pattern and its High/Medium/Low confidence; switch the explanation to Hindi; "What weighed most"; "In your own words"; **Verify this record**.
5. Settings: two-step verification, Download my data, delete with 30-day grace.
6. Log in as Rohan: none of Ananya's data is visible (row-level security).

If asked "why didn't it say sell?": explain that the verdict is based on the share of futures where holding wins (thresholds 0.40 and 0.60), and the pattern is a tendency, not an accusation.
