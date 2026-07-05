# Scale-Level Production Plan
## Autonomous Financial Decision Intelligence System
### Final Plan — Incorporating All User Decisions

---

## Project Overview

### What Are We Building?

An **Autonomous Financial Decision Intelligence System** — a full-stack, AI-powered web application that helps retail Indian investors make **rational, evidence-based financial decisions** instead of emotional ones.

The system's core mission is **debiasing the investment decision process.** Most retail investors lose money not because markets are unpredictable, but because they make predictably irrational decisions — panicking and selling during a drawdown (loss aversion), following the crowd into overvalued assets (herd behavior), or holding losers and selling winners too early (disposition effect). This system detects those biases in real-time, explains them, quantifies the long-term cost of acting on them, and gives the user a clear, evidence-backed recommendation.

> **What this system is NOT:**
> It does not predict stock prices. It does not replace a financial advisor. It does not tell you what to buy. It tells you — when you are *about to make a decision* — whether that decision is being driven by rational analysis or cognitive bias, and what the 20-year financial cost of that bias is.

---

### Target Users

1. **Retail Indian investors** — people who actively invest in stocks, mutual funds, or SIPs and make buy/sell decisions. They may be emotionally reactive to market volatility and lack a structured decision framework.

2. **Working professionals with savings** — salaried individuals who invest a portion of their income and want smarter, calmer guidance before making major moves (e.g., "should I sell my HDFC Bank shares that are down 18%?").

---

### Core Features

| # | Feature | Technology |
|---|---|---|
| 1 | **Behavioral Bias Detection** | XGBoost classifier (85.81% Macro F1) — detects Loss Aversion, Herd Behavior, Disposition Effect, Rational |
| 2 | **Causal Inference Engine** | DoWhy library — establishes causal (not just correlational) relationship between bias and decision outcome |
| 3 | **20-Year Monte Carlo Simulation** | 10,000 paths — compares HOLD vs SELL wealth trajectories with P10/P50/P90 confidence bands |
| 4 | **Multi-Agent AI Debate** | AutoGen + Claude Sonnet — Bull agent vs Bear agent vs Judge agent reason through the decision and produce a verdict |
| 5 | **Tamper-Evident Audit Trail** | SHA-256 hash chaining — every AI decision is logged with a cryptographic chain, proving no retroactive changes |
| 6 | **Live Portfolio Tracker** | Real-time P&L using Zerodha Kite API (or manual entry) with STCG/LTCG tax status badges |
| 7 | **SIP Pause Detector** | Detects if a user is pausing a SIP during a market dip (common behavioral mistake), quantifies the opportunity cost |

---

### Research Pillars (Academic Context)

This system is simultaneously a **major project / final year academic submission** and a **real product in development**. The academic research is organized around 4 research gaps (GAPs):

| GAP | Research Question | Status |
|---|---|---|
| GAP 1 | Can ML detect behavioral biases from financial decision features? | ✅ Complete — XGBoost v3, 85.81% F1 |
| GAP 2 | What is the long-horizon cost of biased decisions? | ✅ Complete — Monte Carlo simulator |
| GAP 3 | Can AI provide causal, human-readable explanations for its recommendations? | 🔲 Building — Explainer + Debate Engine |
| GAP 4 | Can the audit trail be made cryptographically tamper-evident? | 🔲 Building — SHA-256 hash chain |

---

### What Makes This Different From Other Finance Apps?

| Typical Trading App | This System |
|---|---|
| Shows you price charts and order books | Shows you your *cognitive bias* and its 20-year cost |
| Encourages more trading (revenue model) | Encourages less, calmer, rational trading |
| Red/green flashing numbers → triggers panic | Calm, structured analysis → reduces panic |
| No explanation for suggestions | Full causal reasoning + AI debate transcript |
| No audit trail | Cryptographic audit log — every decision is timestamped, hashed, and verifiable |
| No behavioral awareness | Bias history tracked over time — you can see if you're improving |

---

### Migration Context

The system currently exists as a **working prototype** with:
- FastAPI backend (13+ endpoints, functional)
- Streamlit dashboard (4-page, demonstration-ready)
- SQLite database (single-file, not scalable)
- XGBoost bias detector v3 (trained on synthetic data)
- Partial GAP 2 simulator

This plan is the **full blueprint to take it from prototype to production** — migrating to React + Tailwind frontend, PostgreSQL database, proper multi-tenant authentication, and cloud deployment on Render (with an AWS migration path).

---

## Confirmed Decisions

| Question | Decision |
|---|---|
| Deployment | Render (now) → AWS later — Docker-first for portability |
| Auth | JWT + MFA (TOTP authenticator app) + OAuth (Google) |
| Database | PostgreSQL + PgBouncer connection pooler |
| UI scope | Full-featured product, modern + elegant, not chaotic |
| Profile changes | Re-verification required for sensitive fields |
| Account deletion | Yes — GDPR-compliant soft delete + hard delete |

---


## Architecture Overview

```
[React Frontend — Vite + Tailwind]
        │  HTTPS only
        ▼
[Nginx — Render]
   ├── /api/*  → FastAPI backend (port 8000)
   └── /       → React SPA (port 3000)
        │
        ▼
[FastAPI Backend]
   ├── Auth layer (JWT RS256 + TOTP + Google OAuth)
   ├── ML core (XGBoost, DoWhy, Simulator)
   └── Services (market, tax, SIP, Kite)
        │
   ┌────┴────┐
   ▼         ▼
[PostgreSQL  [Redis]
 + PgBouncer] (token blacklist + rate limit + OTP cache)
```

---

## PHASE 1 — Auth System (MFA + OAuth)

### 1A. Core JWT Setup

**Algorithm:** RS256 (asymmetric — public key verifiable, private key on server only)

**Tokens:**
- Access token: 15-minute expiry, in httpOnly cookie
- Refresh token: 7-day expiry, in httpOnly cookie, rotated on every use
- Token blacklist: Redis SET keyed by `jti` (JWT ID)

**Files:**
```
backend/auth/
├── jwt_handler.py      # sign/verify RS256 tokens
├── mfa_handler.py      # TOTP (pyotp) + backup codes
├── oauth_handler.py    # Google OAuth2 flow (authlib)
├── password.py         # bcrypt cost=12, zxcvbn strength check
├── dependencies.py     # FastAPI deps: get_current_user, require_owner, require_admin
└── routes.py           # all /auth/* endpoints
```

### 1B. Registration Flow

```
POST /auth/register
  Body: { email, password, name, age, ... }
  Steps:
    1. zxcvbn password strength check (reject score < 3)
    2. bcrypt hash (cost 12)
    3. Generate email verification token (24h expiry, stored in Redis)
    4. Send verification email via Resend API (free tier)
    5. Create user record (is_active=false, email_verified=false)
    6. Return: { message: "Check your email" }

GET /auth/verify-email?token=xxx
  Steps:
    1. Verify token from Redis
    2. Set email_verified=true, is_active=true
    3. Redirect to /login
```

### 1C. Login Flow (with MFA)

```
POST /auth/login
  Body: { email, password }
  Steps:
    1. Lookup user, verify bcrypt hash
    2. Check is_active, email_verified
    3. If mfa_enabled=true:
         Return: { mfa_required: true, temp_token: "..." }
         (temp_token is a short-lived Redis key, 5 minutes)
    4. If mfa_enabled=false:
         Set httpOnly cookies: access_token, refresh_token
         Return: { user: { id, name, role }, mfa_enabled: false }

POST /auth/login/mfa
  Body: { temp_token, totp_code }
  Steps:
    1. Validate temp_token from Redis
    2. Validate TOTP code via pyotp
    3. Set httpOnly cookies: access_token, refresh_token
    4. Return: { user: { id, name, role } }
```

### 1D. MFA Setup Flow (after login)

```
POST /auth/mfa/setup
  (requires authenticated user)
  Steps:
    1. Generate TOTP secret (pyotp.random_base32())
    2. Store secret in Redis temporarily (not DB yet)
    3. Return: { secret, qr_code_url }
    → Frontend shows QR code for Google Authenticator / Authy

POST /auth/mfa/verify-setup
  Body: { totp_code }
  Steps:
    1. Verify the code against Redis-stored secret
    2. On success: save secret encrypted in users table
    3. Generate 8 backup codes (random, hashed in DB)
    4. Set mfa_enabled=true
    5. Return: { backup_codes: [...] }  ← shown ONCE, user must save them
```

### 1E. Google OAuth Flow

```
GET /auth/google/login
  → Redirect to Google consent screen

GET /auth/google/callback?code=xxx
  Steps:
    1. Exchange code for Google tokens via authlib
    2. Fetch user profile from Google (email, name, picture)
    3. If user exists (email match): log them in
    4. If new user: auto-register (no password, oauth_provider='google')
    5. MFA not required for OAuth users by default (Google handles their security)
    6. Set httpOnly cookies, return user object
```

### 1F. Password Reset (with identity re-verification)

```
POST /auth/forgot-password
  Body: { email }
  → Send reset link (6-digit code + link, 15-minute expiry in Redis)

POST /auth/reset-password
  Body: { token, new_password }
  → Verify token, validate strength, update hash, invalidate all refresh tokens
```

### 1G. All Auth Endpoints

```
POST /auth/register
POST /auth/login
POST /auth/login/mfa
POST /auth/logout               (revoke refresh token in Redis)
POST /auth/refresh              (rotate refresh token)
GET  /auth/google/login
GET  /auth/google/callback
POST /auth/mfa/setup
POST /auth/mfa/verify-setup
POST /auth/mfa/disable          (requires TOTP code + password)
POST /auth/forgot-password
POST /auth/reset-password
POST /auth/change-password      (requires current password)
GET  /auth/me                   (current user info)
```

---

## PHASE 2 — Database: PostgreSQL + PgBouncer

### Why PgBouncer?

FastAPI is async with many concurrent requests. PostgreSQL has a connection limit (~100 default). PgBouncer pools connections (transaction-mode) so 500 concurrent requests share ~20 real DB connections. This is the standard production pattern for Python + PostgreSQL.

```
FastAPI (N workers) → PgBouncer (pool=20) → PostgreSQL (max_conn=25)
```

### Database: Neon PostgreSQL (Render Compatible)

- **Neon** free tier: 0.5 GB storage, 1 compute unit, serverless autoscaling
- Zero config branching (dev/staging/prod environments)
- Direct PostgreSQL wire protocol — works with all drivers
- When moving to AWS: switch `DATABASE_URL` to RDS PostgreSQL — zero code changes

### Schema Design

**Performance indexes:**
```sql
CREATE INDEX idx_decisions_user_id ON decisions(user_id);
CREATE INDEX idx_decisions_created_at ON decisions(created_at DESC);
CREATE INDEX idx_audit_decision_id ON audit_logs(decision_id);
CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
```

**GDPR-ready soft delete:**
```sql
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE users ADD COLUMN deletion_reason TEXT;

-- Soft delete: set deleted_at, anonymize PII
-- Hard delete: separate admin-triggered job after 30-day grace period
```

**User table — expanded:**
```sql
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT UNIQUE NOT NULL,
    email_verified      BOOLEAN DEFAULT FALSE,
    password_hash       TEXT,                    -- NULL for OAuth users
    oauth_provider      TEXT,                    -- 'google' | NULL
    oauth_id            TEXT,                    -- Google sub claim
    name                TEXT NOT NULL,
    role                TEXT DEFAULT 'user' CHECK (role IN ('user','admin')),
    is_active           BOOLEAN DEFAULT FALSE,   -- activated after email verify
    mfa_enabled         BOOLEAN DEFAULT FALSE,
    mfa_secret_enc      TEXT,                    -- AES-256 encrypted TOTP secret
    profile_picture     TEXT,                    -- URL (from Google or uploaded)
    -- Financial profile
    age                 INTEGER,
    monthly_income      NUMERIC(12,2),
    monthly_expense     NUMERIC(12,2),
    risk_tolerance      NUMERIC(4,3),
    investment_horizon  INTEGER,
    has_emergency_fund  BOOLEAN DEFAULT FALSE,
    financial_strategy  TEXT,
    goal                TEXT,
    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ DEFAULT NULL,
    deletion_reason     TEXT
);
```

**Sensitive field change log:**
```sql
CREATE TABLE profile_change_log (
    change_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    field_changed   TEXT NOT NULL,      -- 'email', 'monthly_income', etc.
    old_value_hash  TEXT,               -- hashed, not stored plaintext
    changed_at      TIMESTAMPTZ DEFAULT NOW(),
    verified_via    TEXT NOT NULL       -- 'password' | 'totp' | 'email_code'
);
```

---

## PHASE 3 — Backend Restructure

### Project Layout

```
backend/
├── main.py                   # FastAPI app factory + middleware registration
├── config.py                 # Pydantic Settings from .env
├── auth/
│   ├── jwt_handler.py
│   ├── mfa_handler.py        # pyotp TOTP
│   ├── oauth_handler.py      # authlib Google
│   ├── password.py           # bcrypt + zxcvbn
│   ├── dependencies.py       # get_current_user, require_owner, require_admin
│   └── routes.py
├── api/
│   ├── users.py              # profile CRUD + deletion
│   ├── decisions.py          # /analyze/* (bound to token.sub)
│   ├── simulate.py           # /simulate/*
│   ├── audit.py              # /audit/*
│   ├── market.py             # /market/* (public)
│   ├── portfolio.py          # /portfolio/*
│   └── admin.py              # aggregate stats + user management ONLY
├── core/
│   ├── bias_detector.py
│   ├── causal_inference.py
│   ├── simulator.py
│   ├── explainer.py          # GAP 3
│   ├── debate_engine.py      # GAP 3 — AutoGen + Claude
│   └── audit_logger.py       # GAP 4 — hash chain
├── db/
│   ├── pool.py               # asyncpg connection pool
│   ├── schema.sql
│   └── migrations/           # Alembic
├── models/
│   ├── user.py               # Pydantic request/response schemas
│   ├── decision.py
│   ├── simulation.py
│   └── audit.py
├── services/
│   ├── market_data.py
│   ├── email_service.py      # Resend API
│   ├── tax_engine.py
│   ├── sip_tracker.py
│   ├── kite_integration.py
│   └── outcome_tracker.py
└── middleware/
    ├── rate_limiter.py        # slowapi + Redis
    ├── security_headers.py
    └── cors.py
```

### Key Security Rules (Code Level)

```python
# dependencies.py

async def require_owner(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    if str(current_user.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user

# EVERY decision endpoint uses this:
@router.get("/user/{user_id}/decisions")
async def get_decisions(
    user_id: str,
    user: User = Depends(require_owner)   # ← enforces ownership
):
    ...

# Admin routes use a VIEW, never raw tables:
@router.get("/admin/stats")
async def admin_stats(admin: User = Depends(require_admin)):
    return await db.fetch("SELECT * FROM admin_stats_view")
    # admin_stats_view has NO raw_input, raw_output, personal data
```

### Rate Limits

```
/auth/login          5 req/min per IP
/auth/register       3 req/hour per IP
/analyze/decision    10 req/min per user
/simulate            5 req/min per user
/market/context      30 req/min per user (shared cache anyway)
```

---

## PHASE 4 — React + Tailwind Frontend

### Tech Stack

```
React 18 + Vite 5
Tailwind CSS v3
shadcn/ui (Radix UI primitives — accessible, unstyled base)
Lucide React (icons)
Zustand (auth state, market ribbon)
TanStack Query v5 (API calls, caching, background refresh)
React Router v6 (nested routes, protected routes)
React Hook Form + Zod (forms with validation)
Recharts (wealth trajectory charts, bias history)
Framer Motion (page transitions, card animations)
Axios (HTTP client with interceptors)
```

### Design System — FINALIZED (Decision Intelligence)

> [!IMPORTANT]
> This design system is finalized and was built + approved in Stitch (project ID: `14062838239756964673`). All frontend implementation must follow these exact tokens. Do NOT deviate.

**Philosophy:** "Premium Bento-Grid Minimalism." Calm, authoritative, data-forward. NOT a trading app. No flashing red/green prices. No candlestick charts. Every element exists with purpose.

**Design name:** `Decision Intelligence`
**Stitch Project:** `14062838239756964673` (design system asset: `bbd5e5aaf279438ca731f69ce515d651`)

---

#### Color Tokens — Dark Mode (Default)

```css
/* tailwind.config.ts — extend colors */
colors: {
  /* Backgrounds — tonal layering, not flat black */
  'bg-base':        '#08080F',   /* deepest layer — page bg */
  'bg-surface':     '#13131A',   /* cards */
  'bg-container':   '#1F1F27',   /* card hover, nested panels */
  'bg-elevated':    '#2A2931',   /* modals, popovers */

  /* Borders */
  'border-subtle':  '#464554',   /* card borders (6% white opacity) */
  'border-focus':   '#6366F1',   /* indigo on focus */

  /* Text */
  'text-primary':   '#E4E1EC',   /* main body text */
  'text-secondary': '#C7C4D7',   /* labels, secondary */
  'text-muted':     '#908FA0',   /* timestamps, helper text */

  /* Accent — used SPARINGLY */
  'indigo':         '#6366F1',   /* primary CTA, active nav, focus rings */
  'indigo-dim':     '#C0C1FF',   /* indigo text on dark bg */

  /* Semantic — for data only, not UI chrome */
  'emerald':        '#10B981',   /* HOLD, positive, rational */
  'rose':           '#F43F5E',   /* bias alerts, SELL scenario line */
  'amber':          '#F59E0B',   /* herd behavior, pause warnings */
}
```

#### Color Tokens — Light Mode

```css
/* Applied when .light class is on <html> */
colors: {
  'bg-base':        '#F8F8FC',   /* cool off-white — NOT warm paper */
  'bg-surface':     '#FFFFFF',   /* cards — pure white with shadow */
  'bg-container':   '#F3F3F8',   /* nested panels */

  'border-subtle':  '#E5E7EB',
  'text-primary':   '#111827',
  'text-secondary': '#374151',
  'text-muted':     '#6B7280',
  /* indigo, emerald, rose, amber — same as dark mode */
}
```

#### Typography Tokens

```css
/* Google Fonts: Inter + JetBrains Mono */
font-family: {
  sans:  ['Inter', 'system-ui', 'sans-serif'],
  mono:  ['JetBrains Mono', 'Menlo', 'monospace'],
}

/* Scale */
display-lg:   Inter 700, 48px, -0.02em tracking  /* hero numbers */
headline-md:  Inter 600, 24px, -0.01em tracking  /* card titles */
body-base:    Inter 400, 16px, normal            /* paragraphs */
label-caps:   Inter 700, 11px, 0.1em tracking, UPPERCASE /* card labels */
data-lg:      JetBrains Mono 500, 20px           /* financial values */
data-sm:      JetBrains Mono 400, 12px, 0.05em  /* tickers, hashes */
```

#### Shape & Spacing

```css
border-radius: {
  card:    '16px',   /* rounded-2xl — all bento cards */
  button:  '8px',    /* rounded-lg — CTAs */
  badge:   '9999px', /* rounded-full — status pills */
}
spacing: {
  card-padding:  '24px',
  grid-gutter:   '24px',
  page-margin:   '32px',
}
```

#### Anti-Patterns (NEVER implement)

- ❌ Red/green price tickers anywhere
- ❌ Candlestick charts
- ❌ Dense data tables with more than 6 columns
- ❌ Neon glows or heavy glassmorphism blur
- ❌ Glassmorphism with opacity < 50%
- ❌ Sidebar too narrow to read labels

---

#### Light/Dark Toggle Implementation

```tsx
// theme.ts — Zustand store
const useThemeStore = create((set) => ({
  theme: localStorage.getItem('theme') || 'dark',
  toggle: () => set((s) => {
    const next = s.theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    document.documentElement.classList.toggle('light', next === 'light')
    localStorage.setItem('theme', next)
    return { theme: next }
  }),
}))

// Navbar toggle button
<button onClick={toggle}>
  {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
</button>
// Transition: transition-colors duration-200 on <html>
```

---

### Finalized Dashboard Layout — Home Screen

The bento grid layout was finalized and approved. The dashboard home has **4 bento cards** in a 12-column grid:

```
┌─────────────────────────────┬──────────────────┐
│   PORTFOLIO SNAPSHOT        │  ACTIVE BIAS      │
│   ₹12,47,832 (mono)         │  ALERT            │
│   ▁▂▃▅▄▆▇ (indigo sparkline)│  Loss Aversion    │
│   HOLD RECOMMENDED ● badge  │  87% confidence   │
│   Risk: 3.4  Div: 82%       │  bar (rose)       │
├─────────────────────────────┼──────────────────┤
│   LAST DECISION             │  MARKET PULSE     │
│   HDFC Bank                 │  NIFTY 50         │
│   140 shares @ ₹1,642       │  22,147.90 ▲0.43% │
│   [View Analysis →] (indigo)│  SENSEX           │
│                             │  73,018.25 ▲0.38% │
│                             │  India VIX        │
│                             │  14.82 ▼ -2.1%    │
│                             │  Updated 2min ago │
└─────────────────────────────┴──────────────────┘
```

**Key decisions:**
- "Decisions This Month" card was **removed** — not actionable
- Replaced with **Market Pulse** — NIFTY 50 / SENSEX / India VIX live data
- India VIX shown in muted color (not red) — lower VIX means calmer market, not bad
- Portfolio Snapshot is the widest card (takes ~65% width) — it's the most important

---

### Page Map

```
/                           Landing page (public)
/login                      Login + MFA step
/register                   Registration form
/forgot-password            Password reset
/auth/google/callback       OAuth redirect handler

/dashboard                  Home — summary cards
/dashboard/decision         Main analysis form + results
/dashboard/simulation       HOLD vs SELL chart + debate panel
/dashboard/portfolio        Holdings + live P&L
/dashboard/history          Past decisions + bias trend chart
/dashboard/audit            Audit log viewer + hash verifier
/dashboard/profile          Profile viewer + edit flows
/dashboard/settings         MFA setup, password change, notifications

/admin                      Admin home — aggregate stats
/admin/users                User list (activate/deactivate/search)
```

### Profile Management — Re-verification Flow

Sensitive fields requiring re-verification before saving:

| Field | Verification Required |
|---|---|
| Email change | Current password + OTP to OLD email |
| Password change | Current password + TOTP (if MFA on) |
| Monthly income | Current password |
| Emergency fund status | Current password |
| Account deletion | Password + TOTP (if MFA on) + 30s cooldown |
| MFA disable | Password + current TOTP code |

**UI pattern:**
```
1. User clicks "Edit" on a sensitive field
2. Modal appears: "For your security, verify your identity"
3. User enters password (+ TOTP if MFA enabled)
4. On success: field becomes editable for 5 minutes (session token)
5. User saves → confirmation toast
6. Change logged in profile_change_log table
```

### Account Deletion Flow

```
1. User goes to Settings → "Delete Account"
2. Warning screen: "This is permanent. Your data will be deleted."
3. User must type "DELETE" to confirm
4. Re-verification: password + TOTP
5. Backend: soft delete (deleted_at = NOW(), anonymize email)
6. Email confirmation sent: "Account deletion scheduled for 30 days"
7. 30-day grace period: user can cancel by logging back in
8. After 30 days: hard delete cron job removes all personal data
9. Audit logs: user_id set to anonymized placeholder (preserve integrity)
10. Return: 200 OK, clear all cookies
```

**GDPR compliance:**
- Right to erasure honored (30-day hard delete)
- Data portability: `GET /user/me/export` returns full JSON of all user data
- Audit logs preserved but de-identified (research integrity)

### Protected Route Setup

```tsx
// All dashboard routes require auth
<Route path="/dashboard/*" element={
  <ProtectedRoute>
    <DashboardLayout />
  </ProtectedRoute>
}>
  <Route index element={<DashboardHome />} />
  <Route path="decision" element={<DecisionPage />} />
  <Route path="simulation" element={<SimulationPage />} />
  <Route path="portfolio" element={<PortfolioPage />} />
  <Route path="history" element={<HistoryPage />} />
  <Route path="audit" element={<AuditPage />} />
  <Route path="profile" element={<ProfilePage />} />
  <Route path="settings" element={<SettingsPage />} />
</Route>

// Admin requires role check
<Route path="/admin/*" element={
  <ProtectedRoute requireRole="admin">
    <AdminLayout />
  </ProtectedRoute>
}>
```

### Key UI Components

**Navbar:** Dark, sticky. Left: logo. Center: live market ribbon (NIFTY/SENSEX/BankNifty/VIX in scrolling ticker). Right: user avatar + dropdown (profile, settings, logout).

**Decision Form:** Step-by-step wizard. Step 1: market context (auto-filled). Step 2: your position (symbol, unrealized G/L). Step 3: decision intent. Submit → loading skeleton → results panel slides in.

**Results Panel:**
- Bias alert card (color-coded: red/orange/purple/green)
- Confidence percentage with animated ring
- Two wealth trajectory charts (HOLD vs SELL with P10/P50/P90 bands)
- Opportunity cost in large typography
- Debate panel (Bull/Bear/Judge collapsible)
- Audit hash at bottom with "Verify" button

**Bias History:** Line chart over last N decisions. Stacked area chart showing bias composition over time.

**Portfolio Page:** Table with live prices (auto-refreshed every 5 min via React Query), unrealized P&L colored green/red, STCG/LTCG status badges.

---

## PHASE 5 — Remaining ML Components

### GAP 3: Explainer (`core/explainer.py`)

`DecisionExplainer` class generates structured JSON output for the frontend:

```json
{
  "situation": "Market down 12%, you hold HDFC Bank, down 18%",
  "bias_detected": "loss_aversion",
  "bias_confidence": 0.87,
  "counterfactual": {
    "hold": { "median_20y": 67583, "p10": 31000, "p90": 140000 },
    "sell": { "median_20y": 38291, "p10": 18000, "p90": 72000 }
  },
  "opportunity_cost_inr": 29292,
  "recommendation": "HOLD",
  "reasoning": "Your loss aversion is driving this urge. Selling now locks in a loss and costs ₹29,292 over 20 years.",
  "causal_effect": 0.312,
  "temporal_chart_data": [...],
  "audit_hash": "sha256..."
}
```

### GAP 3 Extension: Debate Engine (`core/debate_engine.py`)

AutoGen framework + Claude Sonnet. Bull/Bear/Judge pattern. Full transcript stored in `decisions.raw_output` JSONB. Frontend `DebatePanel` component renders it as an expandable timeline.

### GAP 4: Audit Logger (`core/audit_logger.py`)

Hash chain — each audit log entry includes `previous_hash` pointing to the prior entry. Tampering with any entry breaks the chain. Frontend `AuditVerifier` lets users recompute their own hash to verify independently.

---

## PHASE 6 — Practical Extensions

| Module | Priority | Key Detail |
|---|---|---|
| `tax_engine.py` | High | STCG 15% / LTCG 10% applied to all SELL simulations. Badge on portfolio showing tax status. |
| `sip_tracker.py` | High | SIP registration, pause detection, pause-cost Monte Carlo, alert on NIFTY > 2% drop |
| `kite_integration.py` | Medium | Zerodha Kite OAuth, auto-fetch holdings, positions, P&L. Fallback to manual entry. |
| `multi_asset.py` | Medium | MF via MFAPI.in, Gold via yfinance GOLDBEES, Crypto via CoinGecko |
| `outcome_tracker.py` | Medium | Track if recommendation followed, fetch actual outcome via Kite after N months |
| `retrain_monthly.py` | Medium | Batch job: combine live decisions + synthetic data, retrain if F1 improves |
| `whatsapp_bot.py` | Low | Meta Cloud API webhook, 3-line summary via `generate_summary_card()` |
| `data_export.py` | Required | `GET /user/me/export` — GDPR data portability, returns full user JSON |

---

## PHASE 7 — Infrastructure & Deployment

### Render Setup (Now)

```yaml
# render.yaml (Infrastructure as Code)
services:
  - type: web
    name: finai-backend
    runtime: python
    buildCommand: pip install -r requirements.txt && alembic upgrade head
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: finai-postgres
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: finai-redis
          type: redis

  - type: web
    name: finai-frontend
    runtime: static
    buildCommand: cd frontend && npm ci && npm run build
    staticPublishPath: frontend/dist

databases:
  - name: finai-postgres
    plan: free
    databaseName: finai

  - name: finai-redis
    plan: free
```

### AWS Migration Path (Later)

When moving from Render to AWS — zero code changes needed because of Docker:

```
Render (now)           →    AWS (later)
─────────────────────       ────────────────────────
Render PostgreSQL      →    RDS PostgreSQL (Multi-AZ)
Render Redis           →    ElastiCache Redis
Render Web Service     →    ECS Fargate (Docker)
Render Static Site     →    S3 + CloudFront (CDN)
─────────────────────       ────────────────────────
Just change env vars. All code stays identical.
```

### Docker Setup

```
docker-compose.yml (local dev):
  - backend (FastAPI)
  - frontend (Vite dev server)
  - postgres
  - redis
  - pgbouncer

Dockerfile.backend:
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY backend/ backend/
  CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

Dockerfile.frontend:
  FROM node:20-alpine as build
  WORKDIR /app
  COPY frontend/package*.json .
  RUN npm ci
  COPY frontend/ .
  RUN npm run build
  FROM nginx:alpine
  COPY --from=build /app/dist /usr/share/nginx/html
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/main.yml
on: [push to main]
jobs:
  test-backend:
    - pytest backend/tests/ --cov
    - fail if coverage < 70%
  test-frontend:
    - npm run test
    - npm run build (catch build errors)
  deploy:
    needs: [test-backend, test-frontend]
    - trigger Render deploy webhook
```

---

## Security Summary

| Threat | Mitigation |
|---|---|
| User A reads User B's data | `require_owner` dep + PostgreSQL RLS |
| Admin reads user raw data | Admin uses aggregate VIEW — no access to raw tables |
| XSS token theft | httpOnly cookies — JS cannot read tokens |
| CSRF | Double-submit cookie (X-CSRF-Token header) |
| Brute force login | 5 req/min per IP via slowapi + Redis |
| Account takeover | MFA (TOTP) required for sensitive changes |
| Password breach | bcrypt cost=12, zxcvbn strength enforcement |
| Weak passwords | zxcvbn library rejects score < 3 |
| JWT forgery | RS256 asymmetric — only server signs |
| Token replay after logout | Redis blacklist on refresh token jti |
| Audit tampering | PostgreSQL RULE blocks DELETE/UPDATE + hash chain |
| GDPR violation | Soft delete + 30-day hard delete + data export endpoint |
| SQL injection | Parameterized queries via asyncpg everywhere |
| Sensitive field changes | Re-verification (password + TOTP) required |
| OAuth account hijack | Email binding — Google email must match exactly |
| Man-in-middle | HTTPS enforced via HSTS header |

---

## Build Sequence (Sequential, Dependency-Ordered)

```
Week 1-2:   Auth system (Phase 1) — register, login, MFA, Google OAuth
Week 2-3:   PostgreSQL schema + Alembic migrations (Phase 2)
Week 3-4:   Backend restructure into modules (Phase 3)
Week 4-5:   React setup + auth pages (login, register, MFA, OAuth)
Week 5-6:   Dashboard layout + Decision page + Results UI
Week 6-7:   Profile management + settings + account deletion
Week 7-8:   GAP 3 explainer + debate engine
Week 8:     GAP 4 audit logger (hash chain)
Week 9:     Tax engine + SIP tracker
Week 9-10:  Simulation page + portfolio page + history page
Week 10:    Admin dashboard (aggregate stats + user management)
Week 11:    Docker setup + Render deployment + CI/CD
Week 12:    Kite integration + multi-asset
Week 13+:   WhatsApp bot + feedback loop retrainer
```

---

## Role Reference: What Each Role Can & Cannot Do

There are three roles in this system: **Guest (unauthenticated)**, **User (authenticated)**, and **Admin**.

---

### 🔓 Guest (Not Logged In)

| Action | Allowed |
|---|---|
| View landing page | ✅ |
| Register an account | ✅ |
| Login (email/password or Google) | ✅ |
| Request password reset | ✅ |
| View public market data (`/market/context`) | ✅ |
| Access any dashboard page | ❌ Redirect to /login |
| Access any API endpoint (except auth + market) | ❌ 401 Unauthorized |

---

### 👤 User (Logged In, role = `user`)

#### Account & Profile

| Action | Allowed | Notes |
|---|---|---|
| View their own profile | ✅ | |
| Edit non-sensitive profile fields (name, goal, strategy) | ✅ | No verification needed |
| Edit sensitive fields (email, income, emergency fund) | ✅ | Re-verification required (password + TOTP if enabled) |
| Change password | ✅ | Requires current password + TOTP |
| Enable / disable MFA | ✅ | Requires password + current TOTP to disable |
| Connect Google OAuth to existing account | ✅ | |
| Upload profile picture | ✅ | |
| Export their own data (GDPR) | ✅ | `GET /user/me/export` — full JSON |
| Delete their own account | ✅ | Password + TOTP + type "DELETE" + 30-day grace |
| View another user's profile | ❌ 403 Forbidden |
| Modify another user's data | ❌ 403 Forbidden |

#### Financial Decisions & Analysis

| Action | Allowed | Notes |
|---|---|---|
| Submit a decision for AI analysis | ✅ | Bound to their own `user_id` only |
| View their own past decisions | ✅ | |
| View another user's decisions | ❌ 403 Forbidden |
| View their own bias profile / history | ✅ | |
| Run a HOLD vs SELL simulation | ✅ | Rate limited: 5/min |
| View the AI debate transcript (Bull/Bear/Judge) | ✅ | For their own decisions only |
| View their own opportunity cost report | ✅ | |

#### Portfolio

| Action | Allowed | Notes |
|---|---|---|
| Add / edit / delete their own holdings | ✅ | |
| View their own live P&L | ✅ | |
| Connect Zerodha Kite (OAuth) | ✅ | Auto-imports their holdings |
| View another user's portfolio | ❌ 403 Forbidden |

#### Audit Trail

| Action | Allowed | Notes |
|---|---|---|
| View their own audit log | ✅ | |
| Verify hash integrity of their own decision | ✅ | Frontend `AuditVerifier` component |
| View another user's audit log | ❌ 403 Forbidden |
| Modify or delete any audit entry | ❌ Blocked at DB level (PostgreSQL RULE) |

#### Settings

| Action | Allowed | Notes |
|---|---|---|
| Toggle light/dark theme | ✅ | Stored in localStorage |
| Configure notification preferences | ✅ | |
| Manage SIP registrations | ✅ | |
| View tax impact (STCG/LTCG) on their decisions | ✅ | |
| Access admin panel | ❌ Redirect to /dashboard |

---

### 🛡️ Admin (Logged In, role = `admin`)

> [!CAUTION]
> Admin role has ZERO access to individual user's financial data, decisions, or personal portfolio. This is enforced at the query level — admin routes query aggregate VIEWs only, never the raw `decisions`, `portfolios`, or `audit_logs` tables directly.

#### User Management

| Action | Allowed | Notes |
|---|---|---|
| View list of all users | ✅ | Shows: name, email, joined date, is_active, decision count — NO financial data |
| Activate a user account | ✅ | |
| Deactivate a user account | ✅ | User is locked out immediately |
| Reset a user's password | ✅ | Triggers reset email to user |
| Permanently delete a user (hard delete) | ✅ | Only after 30-day soft delete grace period |
| View a user's raw_input / raw_output | ❌ Query-level blocked |
| View a user's portfolio holdings | ❌ Query-level blocked |
| View a user's decision history | ❌ Query-level blocked |
| View a user's income / expenses / financial profile | ❌ Query-level blocked |
| Access a user's TOTP secret | ❌ AES-256 encrypted, never exposed |

#### System & Analytics

| Action | Allowed | Notes |
|---|---|---|
| View aggregate bias distribution (e.g., 42% of users showed loss aversion today) | ✅ | Via `admin_stats_view` — no individual data |
| View total decisions per day / week | ✅ | Aggregate only |
| View system health (API latency, error rates, uptime) | ✅ | |
| Trigger manual ML model retraining | ✅ | Batch job via admin action |
| View model performance metrics (F1, accuracy) | ✅ | |
| Modify or delete audit logs | ❌ Blocked at DB level |
| Access any user-owned API endpoint | ❌ `require_owner` blocks admin tokens |

---

### 🔐 Data Isolation Summary

```
User A → can ONLY read/write rows WHERE user_id = their own UUID
Admin  → can ONLY read from admin_stats_view (no user_id column exists in the view)
Guest  → can ONLY read /market/context and /auth/* endpoints

PostgreSQL RLS enforces this at the database level independently of application code.
Even if there is a bug in the API, the DB will still block cross-user access.
```

---

### 📋 Sensitive Actions Requiring Re-Verification (Users)

These actions open a verification modal before proceeding:

| Action | Verification Method |
|---|---|
| Change email address | Password + OTP sent to old email |
| Change password | Current password + TOTP (if MFA enabled) |
| Edit monthly income / expenses | Current password |
| Edit emergency fund status | Current password |
| Disable MFA | Current password + current TOTP code |
| Delete account | Password + TOTP + type "DELETE" manually |
| Connect/disconnect Kite OAuth | Current password |

After successful verification, the session is granted a 5-minute "sensitive edit window" — the user does not need to re-verify for every single field change within that window.

