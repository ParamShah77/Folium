# Autonomous Financial Decision Intelligence System
## Production Scale-Up — Full Implementation Plan (v2)

---

## 1. Project Overview

### What Are We Building?

A full-stack, AI-powered web application that helps **retail Indian investors** make **rational, evidence-based financial decisions** instead of emotional ones.

**The core problem:** Most retail investors lose money not because markets are unpredictable, but because they make *predictably irrational* decisions — panicking and selling during a drawdown (loss aversion), following the crowd into overvalued assets (herd behavior), or holding losers while selling winners (disposition effect). This system detects those biases in real-time, explains them causally, quantifies their 20-year financial cost, and gives a clear evidence-backed recommendation.

> **Explicit scope boundary:** This system does NOT predict stock prices. It does NOT replace a financial advisor. It does NOT tell you what to buy. It tells you — *when you are about to make a decision* — whether that decision is driven by rational analysis or by cognitive bias, and what the 20-year cost of acting on that bias would be.

### Target Users

1. **Retail Indian investors** — actively invest in stocks, MFs, SIPs; emotionally reactive to market volatility; lack a structured decision framework.
2. **Working professionals with savings** — salaried individuals who invest a portion of income and want calmer, structured guidance before major moves.

### Dual Context

| Context | Description |
|---|---|
| **Academic** | Major project / final-year submission organized around 4 research GAPs |
| **Product** | Real application to be deployed and iterated post-submission |

### Core Features

| # | Feature | Technology |
|---|---|---|
| 1 | Behavioral Bias Detection | XGBoost v3 — 85.81% Macro F1, 52 features |
| 2 | Causal Inference Engine | DoWhy — causal, not just correlational |
| 3 | 20-Year Monte Carlo Simulation | 10,000 paths, P10/P50/P90 bands |
| 4 | Multi-Agent AI Debate | AutoGen + Claude Sonnet (Bull/Bear/Judge) |
| 5 | Tamper-Evident Audit Trail | SHA-256 hash chain, append-only PostgreSQL |
| 6 | Live Portfolio Tracker | Kite API + manual entry, STCG/LTCG badges |
| 7 | SIP Pause Detector | Monte Carlo on pause cost, NIFTY-drop alerts |

### Research GAPs Status

| GAP | Question | Status |
|---|---|---|
| GAP 1 | Can ML detect behavioral biases? | ✅ Complete |
| GAP 2 | What is the 20-year cost of biased decisions? | ✅ Complete |
| GAP 3 | Can AI produce causal, readable explanations? | 🔲 Building |
| GAP 4 | Can audit trails be cryptographically tamper-evident? | 🔲 Building |

### What Distinguishes This From Trading Apps

| Typical Trading App | This System |
|---|---|
| Price charts → triggers emotion | Bias analysis → reduces emotion |
| Encourages frequent trading | Encourages fewer, calmer decisions |
| Red/green tickers → panic | Calm structured output → rationality |
| No explanation for suggestions | Causal reasoning + AI debate transcript |
| No audit trail | Cryptographic hash chain, verifiable |
| No behavioral tracking | Bias history over time — track improvement |

### Current State (Prototype → Production)

**Exists today:**
- FastAPI backend (13+ endpoints, functional)
- Streamlit dashboard (4-page, demo-ready)
- SQLite database (single-file, not scalable)
- XGBoost bias detector v3 (synthetic data trained)
- Partial GAP 2 simulator

**This plan:** Blueprint to migrate to React + Tailwind, PostgreSQL, proper multi-tenant auth, and cloud deployment.

---

## 2. Confirmed Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deployment | Render → AWS (later) | Docker-first; env var swap only |
| Auth | JWT RS256 + TOTP MFA + Google OAuth | No third-party auth lock-in |
| Database | PostgreSQL (Neon) + PgBouncer | ACID, RLS, concurrent writes |
| Redis | **Upstash Redis** (not Render Redis) | Persists on restart — security critical |
| API versioning | `/v1/` prefix on all routes | Prevents breaking changes mid-demo |
| UI framework | React 18 + Vite 5 + Tailwind CSS v3 | Full control, fast builds |
| Async jobs | FastAPI BackgroundTasks + SSE for short; Celery + Redis for debate engine | Debate takes 15–30s |
| Route pattern | `/v1/decisions/my` (no user_id in path) | Smaller attack surface |

---

## 3. System Architecture

```
[React SPA — Vite + Tailwind]
        │  HTTPS only (HSTS enforced)
        │  httpOnly JWT cookies
        │  X-CSRF-Token header on mutations
        ▼
[Nginx — Render]
   ├── /v1/*  → FastAPI backend (port 8000)
   └── /      → React SPA (port 3000)
        │
        ▼
[FastAPI Backend]
   ├── Auth layer       (JWT RS256 + TOTP + Google OAuth)
   ├── API layer        (versioned /v1/* routes)
   ├── Core ML          (XGBoost, DoWhy, Simulator, Debate)
   ├── Services         (market, tax, SIP, Kite, email)
   ├── Job Queue        (Celery workers for debate engine)
   └── Middleware       (CSRF, rate limit, security headers)
        │
   ┌────┼────────────┐
   ▼    ▼            ▼
[PostgreSQL  [Upstash  [Celery
 Neon]        Redis]    Workers]
```

---

## 4. PHASE 1 — Authentication System

### 4.1 Token Architecture

**Algorithm:** RS256 (asymmetric — only server can sign, public key verifiable)

| Token | Expiry | Storage | Purpose |
|---|---|---|---|
| Access token | 15 minutes | httpOnly cookie | API auth |
| Refresh token | 7 days | httpOnly cookie | Access renewal |
| CSRF token | Matches access token | Readable cookie (not httpOnly) | CSRF protection |
| MFA temp token | 5 minutes | Upstash Redis key | MFA step bridge |

**Token blacklist:** On logout, the refresh token's `jti` is written to Upstash Redis with TTL = remaining token lifetime. Every refresh attempt checks this list first.

### 4.2 CSRF Protection — Full Implementation

> [!IMPORTANT]
> CSRF is listed in the security summary but must be explicitly implemented in both backend middleware and frontend Axios interceptors.

**Backend (`middleware/csrf.py`):**
```python
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or cookie_token != header_token:
            raise HTTPException(status_code=403, detail="CSRF validation failed")
    return await call_next(request)
```

**Frontend (`lib/api.ts` — Axios interceptor):**
```typescript
api.interceptors.request.use((config) => {
  if (["post","put","patch","delete"].includes(config.method!)) {
    const csrf = document.cookie
      .split(";").find(c => c.trim().startsWith("csrf_token="))
      ?.split("=")[1]
    if (csrf) config.headers["X-CSRF-Token"] = csrf
  }
  return config
})
```

On login, backend sets:
- `access_token` — httpOnly, Secure, SameSite=Strict
- `refresh_token` — httpOnly, Secure, SameSite=Strict
- `csrf_token` — NOT httpOnly (readable by JS), Secure, SameSite=Strict

### 4.3 Registration Flow

```
POST /v1/auth/register
  Body: { email, password, name, age, ... }
  1. zxcvbn score check — reject if < 3
  2. bcrypt hash (cost 12)
  3. Generate 6-digit OTP → store in Upstash Redis (TTL 24h, key = email)
  4. Send verification email via Resend API
  5. Create user: is_active=false, email_verified=false
  6. Return: { message: "Check your email" }

GET /v1/auth/verify-email?token=<otp>&email=<email>
  1. Verify OTP from Upstash Redis
  2. Set email_verified=true, is_active=true
  3. Delete OTP key from Redis
  4. Redirect to /login
```

### 4.4 Login Flow

```
POST /v1/auth/login
  Body: { email, password }
  1. Look up user, verify bcrypt
  2. Check is_active, email_verified
  3a. If mfa_enabled=true:
      → Store temp_token in Upstash (TTL 5 min, value = user_id)
      → Return: { mfa_required: true, temp_token }
  3b. If mfa_enabled=false:
      → Set 3 cookies (access, refresh, csrf)
      → Return: { user: { id, name, role } }

POST /v1/auth/login/mfa
  Body: { temp_token, totp_code }
  1. Look up user_id from Upstash by temp_token
  2. Decrypt mfa_secret_enc, validate TOTP via pyotp
  3. Delete temp_token from Redis
  4. Set 3 cookies, return user object
```

### 4.5 Google OAuth — Edge Cases Fully Specified

```
GET /v1/auth/google/login     → Redirect to Google consent
GET /v1/auth/google/callback
  1. Exchange code → fetch { email, name, picture, sub } from Google
  2. Case A: New user (email not in DB)
     → Auto-register: oauth_provider='google', oauth_id=sub
     → Set is_active=true, email_verified=true (Google verified it)
     → Set cookies, return user
  3. Case B: Existing user, same email, also has password_hash
     → Log them in (Google login is valid)
     → DECISION: Google OAuth bypasses TOTP always.
        Rationale: Google's own auth is equivalent security.
        If user wants MFA enforcement even for Google, they must
        remove Google OAuth from the account.
  4. Case C: User registered via Google, now wants to add password
     → POST /v1/auth/add-password — requires Google session + new password
     → Sets password_hash, does NOT change oauth_provider
     → User can now login via either method
  5. Edge case: email collision with different Google account
     → Reject: "An account with this email already exists"
```

> [!IMPORTANT]
> **Rule:** Google OAuth always bypasses TOTP. This is a conscious decision, not an oversight. Document this explicitly in the settings page UI: "Accounts with Google login connected skip TOTP verification. Remove Google login to require TOTP on every login."

### 4.6 MFA — Full Flow Including Recovery

```
Setup:
  POST /v1/auth/mfa/setup
    → Generate TOTP secret via pyotp.random_base32()
    → Store encrypted in Upstash temporarily (TTL 10 min)
    → Return: { qr_code_url, secret }

  POST /v1/auth/mfa/verify-setup
    Body: { totp_code }
    → Validate code against Upstash secret
    → AES-256 encrypt secret, save to users.mfa_secret_enc
    → Generate 8 backup codes (cryptographically random, bcrypt-hashed in DB)
    → Set mfa_enabled=true
    → Return: { backup_codes: [...] }  ← shown ONCE

Recovery (user lost phone AND backup codes):
  POST /v1/auth/mfa/admin-reset   [Admin only]
    Body: { user_id }
    → Sets mfa_enabled=false, clears mfa_secret_enc, clears backup codes
    → Sends email to user: "Your MFA has been reset by an admin.
       You must set it up again on next login."
    → Logs change in profile_change_log
  
  Note: User cannot self-recover without a backup code.
  Admin reset is the only path for total lockout.
```

### 4.7 All Auth Endpoints

```
POST /v1/auth/register
POST /v1/auth/verify-email
POST /v1/auth/login
POST /v1/auth/login/mfa
POST /v1/auth/logout
POST /v1/auth/refresh
GET  /v1/auth/google/login
GET  /v1/auth/google/callback
POST /v1/auth/add-password          (Google user adds password)
POST /v1/auth/mfa/setup
POST /v1/auth/mfa/verify-setup
POST /v1/auth/mfa/disable           (password + TOTP)
POST /v1/auth/mfa/admin-reset       (admin only)
POST /v1/auth/forgot-password
POST /v1/auth/reset-password
POST /v1/auth/change-password
GET  /v1/auth/me
```

---

## 5. PHASE 2 — Database: PostgreSQL + PgBouncer

### 5.1 Why Upstash Instead of Render Redis

> [!CAUTION]
> Render's free Redis **wipes all data on restart**. The token blacklist lives in Redis. A wiped blacklist means logged-out tokens become valid again — a direct security vulnerability. Use Upstash Redis instead: free tier, persists data, HTTP REST fallback.

```python
# config.py
REDIS_URL: str  # points to Upstash Redis URL, not Render Redis
```

No other code changes. Just update the environment variable.

### 5.2 asyncpg + PgBouncer — Critical Fix

> [!CAUTION]
> PgBouncer in transaction mode does NOT support prepared statements. `asyncpg` uses them by default. This causes `"prepared statement already exists"` errors at runtime.

**Fix — `db/pool.py`:**
```python
engine = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    statement_cache_size=0,   # ← REQUIRED for PgBouncer transaction mode
    min_size=5,
    max_size=20,
)
```

This must be in the pool setup. Do not forget it.

### 5.3 PostgreSQL Schema

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- USERS
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT UNIQUE NOT NULL,
    email_verified      BOOLEAN DEFAULT FALSE,
    password_hash       TEXT,
    oauth_provider      TEXT,
    oauth_id            TEXT,
    name                TEXT NOT NULL,
    role                TEXT DEFAULT 'user' CHECK (role IN ('user','admin')),
    is_active           BOOLEAN DEFAULT FALSE,
    mfa_enabled         BOOLEAN DEFAULT FALSE,
    mfa_secret_enc      TEXT,
    profile_picture     TEXT,
    age                 INTEGER,
    monthly_income      NUMERIC(12,2),
    monthly_expense     NUMERIC(12,2),
    risk_tolerance      NUMERIC(4,3),
    investment_horizon  INTEGER,
    has_emergency_fund  BOOLEAN DEFAULT FALSE,
    financial_strategy  TEXT,
    goal                TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ DEFAULT NULL,
    deletion_reason     TEXT
);

-- MFA BACKUP CODES
CREATE TABLE mfa_backup_codes (
    code_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- DECISIONS
CREATE TABLE decisions (
    decision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol          TEXT,
    bias_detected   TEXT NOT NULL,
    confidence      NUMERIC(5,4),
    recommendation  TEXT,
    risk_score      NUMERIC(5,4),
    wealth_hold_p50 NUMERIC(14,2),
    wealth_sell_p50 NUMERIC(14,2),
    opportunity_cost NUMERIC(14,2),
    raw_input       JSONB NOT NULL,
    -- raw_output stores debate transcript reference, not full text
    -- full transcript stored in object storage (Cloudflare R2)
    debate_url      TEXT,           -- R2 URL for full transcript JSON
    debate_summary  JSONB,          -- Bull/Bear/Judge 2-line summaries only
    job_id          TEXT,           -- Celery job ID for async debate
    job_status      TEXT DEFAULT 'pending' CHECK (job_status IN ('pending','processing','complete','failed')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Row-Level Security
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY decisions_isolation ON decisions
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- AUDIT LOGS (append-only, immutable)
CREATE TABLE audit_logs (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID NOT NULL REFERENCES decisions(decision_id),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    block_index     BIGINT NOT NULL,
    input_hash      TEXT NOT NULL,
    output_hash     TEXT NOT NULL,
    previous_hash   TEXT NOT NULL,  -- SHA256("GENESIS") for first entry per user
    full_hash       TEXT NOT NULL,  -- SHA256(input_hash + output_hash + previous_hash)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
-- Hard block: no delete, no update on audit logs
CREATE RULE no_delete_audit AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE no_update_audit AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;

-- PORTFOLIOS
CREATE TABLE portfolios (
    holding_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol      TEXT NOT NULL,
    exchange    TEXT DEFAULT 'NSE',
    quantity    NUMERIC(12,4),
    buy_price   NUMERIC(12,2),
    buy_date    DATE,
    asset_type  TEXT DEFAULT 'stock',
    kite_linked BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
CREATE POLICY portfolio_isolation ON portfolios
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- BIAS PROFILES (running average per user)
CREATE TABLE bias_profiles (
    user_id               UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    disposition_score     NUMERIC(6,5) DEFAULT 0,
    herd_score            NUMERIC(6,5) DEFAULT 0,
    loss_aversion_score   NUMERIC(6,5) DEFAULT 0,
    rational_score        NUMERIC(6,5) DEFAULT 0,
    total_decisions       INTEGER DEFAULT 0,
    last_updated          TIMESTAMPTZ DEFAULT NOW()
);

-- PROFILE CHANGE LOG
CREATE TABLE profile_change_log (
    change_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    field_changed   TEXT NOT NULL,
    old_value_hash  TEXT,
    changed_at      TIMESTAMPTZ DEFAULT NOW(),
    verified_via    TEXT NOT NULL
);

-- REFRESH TOKENS
CREATE TABLE refresh_tokens (
    token_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- MARKET CACHE (shared, no isolation)
CREATE TABLE market_cache (
    cache_key   TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- SIPS
CREATE TABLE sips (
    sip_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    monthly_amount  NUMERIC(12,2),
    start_date      DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    last_credited   DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ADMIN AGGREGATE VIEW (no user_id, no raw data)
CREATE VIEW admin_stats_view AS
SELECT
    DATE(created_at)    AS date,
    COUNT(*)            AS total_decisions,
    COUNT(DISTINCT user_id) AS active_users,
    bias_detected,
    AVG(confidence)     AS avg_confidence,
    AVG(opportunity_cost) AS avg_opportunity_cost
FROM decisions
WHERE deleted_at IS NULL
GROUP BY DATE(created_at), bias_detected;
-- Note: user_id column does NOT appear in this view

-- PERFORMANCE INDEXES
CREATE INDEX idx_decisions_user_id   ON decisions(user_id);
CREATE INDEX idx_decisions_created   ON decisions(created_at DESC);
CREATE INDEX idx_audit_decision_id   ON audit_logs(decision_id);
CREATE INDEX idx_portfolios_user_id  ON portfolios(user_id);
CREATE INDEX idx_refresh_token_hash  ON refresh_tokens(token_hash);
CREATE INDEX idx_users_email         ON users(email);
```

### 5.4 Audit Chain Genesis Block

> [!IMPORTANT]
> The first audit log entry for each user has no prior entry to hash. Use a defined genesis value:

```python
GENESIS_HASH = hashlib.sha256(f"GENESIS:{user_id}".encode()).hexdigest()
# First entry: previous_hash = GENESIS_HASH
# All subsequent: previous_hash = prior entry's full_hash
```

This makes the chain user-specific and tamper-provable from the very first entry.

### 5.5 JSONB / Object Storage Strategy

> [!WARNING]
> Full debate transcripts are 5–10 KB each. At 1,000 decisions = 5–10 MB in `raw_output`. Neon free tier is 0.5 GB — won't run out immediately but will at scale.

**Strategy:**
- Store `debate_summary` (Bull/Bear/Judge 2-line summaries) as JSONB in PostgreSQL — small, queryable
- Store full transcript JSON in **Cloudflare R2** (free tier: 10 GB/month) — reference URL in `decisions.debate_url`
- `AuditVerifier` hashes the content fetched from R2, not from DB

---

## 6. PHASE 3 — Backend Restructure

### 6.1 Directory Layout

```
backend/
├── main.py                     # FastAPI app factory
├── config.py                   # Pydantic Settings (all env vars)
├── auth/
│   ├── jwt_handler.py          # RS256 sign/verify
│   ├── mfa_handler.py          # pyotp TOTP + backup codes
│   ├── oauth_handler.py        # authlib Google
│   ├── password.py             # bcrypt + zxcvbn
│   ├── csrf.py                 # CSRF middleware
│   ├── dependencies.py         # get_current_user, require_owner, require_admin
│   └── routes.py
├── api/
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py            # /v1/users/me/*
│   │   ├── decisions.py        # /v1/decisions/my
│   │   ├── simulate.py
│   │   ├── audit.py
│   │   ├── market.py
│   │   ├── portfolio.py
│   │   ├── sip.py
│   │   └── admin.py
├── core/
│   ├── bias_detector.py
│   ├── causal_inference.py
│   ├── simulator.py
│   ├── explainer.py
│   ├── debate_engine.py        # Celery task, not sync endpoint
│   └── audit_logger.py
├── jobs/
│   ├── celery_app.py           # Celery config (Upstash Redis broker)
│   └── debate_task.py          # @celery_app.task for debate
├── db/
│   ├── pool.py                 # asyncpg pool (statement_cache_size=0)
│   ├── schema.sql
│   └── migrations/             # Alembic versions
├── models/
│   ├── user.py
│   ├── decision.py
│   ├── simulation.py
│   └── audit.py
├── services/
│   ├── market_data.py          # NSE + yfinance fallback
│   ├── email_service.py        # Resend API
│   ├── tax_engine.py
│   ├── sip_tracker.py
│   ├── kite_integration.py
│   ├── r2_storage.py           # Cloudflare R2 for debate transcripts
│   └── outcome_tracker.py
├── middleware/
│   ├── rate_limiter.py         # slowapi + Upstash Redis
│   ├── security_headers.py
│   ├── cors.py
│   └── error_handlers.py       # Global exception handlers
└── tests/
    ├── test_auth.py
    ├── test_bias_detector.py
    ├── test_simulator.py
    ├── test_audit_chain.py
    └── test_api_isolation.py
```

### 6.2 API Versioning

All routes prefixed with `/v1/`. FastAPI router setup:

```python
# main.py
from api.v1 import auth, users, decisions, simulate, audit, market, portfolio, admin

app.include_router(auth.router,      prefix="/v1/auth",      tags=["auth"])
app.include_router(users.router,     prefix="/v1/users",     tags=["users"])
app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])
app.include_router(simulate.router,  prefix="/v1/simulate",  tags=["simulate"])
app.include_router(audit.router,     prefix="/v1/audit",     tags=["audit"])
app.include_router(market.router,    prefix="/v1/market",    tags=["market"])
app.include_router(portfolio.router, prefix="/v1/portfolio", tags=["portfolio"])
app.include_router(admin.router,     prefix="/v1/admin",     tags=["admin"])
```

Future: `/v2/` runs alongside `/v1/` without breaking existing frontend.

### 6.3 Route Pattern — No User ID in Path

> [!IMPORTANT]
> Do NOT use `/v1/user/{user_id}/decisions`. Use `/v1/decisions/my` instead. The `user_id` is read from the JWT, not from the URL. This eliminates the attack vector of spoofing another user's ID in the path parameter entirely.

```python
# decisions.py
@router.get("/my")
async def get_my_decisions(
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    # user_id comes from JWT, never from request
    return await db.fetch_decisions(current_user.user_id, limit, offset)
```

### 6.4 Global Error Handling

```python
# error_handlers.py

class APIError(BaseModel):
    error: str        # machine-readable code, e.g. "CLAUDE_UNAVAILABLE"
    message: str      # human-readable, safe to display
    detail: str | None = None

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=APIError(
            error=f"HTTP_{exc.status_code}",
            message=exc.detail
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception("Unhandled exception", exc_info=exc)  # Sentry captures this
    return JSONResponse(
        status_code=500,
        content=APIError(
            error="INTERNAL_ERROR",
            message="Something went wrong. Our team has been notified."
        ).dict()
    )
```

**Per-service fallbacks:**

| Service | Failure Behavior |
|---|---|
| Claude API (debate engine) | Job marked `failed`, frontend shows "Debate unavailable — try again later" |
| Kite API | Fall back to manual holdings entry, show "Kite connection lost" banner |
| Market data (NSE) | Serve stale cache (< 5 min old), log fetch failure to Sentry |
| yfinance | See note below — replace for production |

### 6.5 Market Data — Replacing yfinance

> [!WARNING]
> `yfinance` scrapes Yahoo Finance and breaks without warning on structure changes. Do NOT use it as the sole production data source.

**Priority order:**
1. **NSE India API** (`nsepython` library) — official, for Indian equities (NIFTY, SENSEX, VIX, individual stocks)
2. **MFAPI.in** — for mutual fund NAVs (free, stable)
3. **CoinGecko API** — for crypto prices (free tier, 30 req/min)
4. **yfinance** — ONLY as a fallback for gold (GOLDBEES) if nsepython fails

All fetches are wrapped in try/except and cached in `market_cache` table. Cache TTL = 5 minutes. If fetch fails, serve stale cache and log to Sentry.

### 6.6 Rate Limits

```
POST /v1/auth/login          5 req/min  per IP
POST /v1/auth/register       3 req/hour per IP
POST /v1/decisions/analyze   10 req/min per user
POST /v1/simulate            5 req/min  per user
GET  /v1/market/*            30 req/min per user
POST /v1/auth/forgot-password 3 req/hour per IP
```

---

## 7. PHASE 4 — Debate Engine: Async Job Queue

> [!IMPORTANT]
> This is the most critical architectural decision in the entire plan. The Bull→Bear→Judge debate involves ≥3 sequential Claude Sonnet API calls. Realistic latency: **15–30 seconds**. A synchronous FastAPI endpoint will either time out or leave the user stuck on a loading screen with no feedback.

### 7.1 Architecture

```
[Frontend] → POST /v1/decisions/analyze
                    │
                    ▼
            [FastAPI — sync]
            1. Run bias detector (fast, <100ms)
            2. Run causal inference (fast, <500ms)
            3. Run Monte Carlo (fast, <2s)
            4. Save decision record (job_status='pending')
            5. Submit Celery task → returns job_id
            6. Return HTTP 202 Accepted:
               { decision_id, job_id, bias, confidence, simulation_results }
                    │
                    ▼ (async, in background)
            [Celery Worker]
            1. Run Bull agent (Claude) → ~5s
            2. Run Bear agent (Claude) → ~5s
            3. Run Judge agent (Claude) → ~5s
            4. Upload full transcript to Cloudflare R2
            5. Save summary to decisions.debate_summary
            6. Update decisions.job_status = 'complete'
                    │
                    ▼
[Frontend — SSE listener]
  Subscribes to GET /v1/decisions/{decision_id}/stream
  Receives server-sent events:
    → { event: "bias_ready", data: {...} }        (immediate)
    → { event: "simulation_ready", data: {...} }  (immediate)
    → { event: "debate_complete", data: {...} }   (15-30s later)
    → { event: "done" }
```

### 7.2 Celery Configuration

```python
# jobs/celery_app.py
from celery import Celery

celery_app = Celery(
    "finai",
    broker=settings.REDIS_URL,        # Upstash Redis
    backend=settings.REDIS_URL,       # Store results in Redis
    include=["jobs.debate_task"],
)
celery_app.conf.task_soft_time_limit = 90   # seconds
celery_app.conf.task_time_limit = 120
celery_app.conf.task_acks_late = True       # only ack after completion
```

```python
# jobs/debate_task.py
@celery_app.task(bind=True, max_retries=2)
def run_debate(self, decision_id: str, decision_data: dict):
    try:
        # Run debate engine
        result = debate_engine.run(decision_data)
        # Upload to R2
        url = r2_storage.upload(f"debates/{decision_id}.json", result.full_transcript)
        # Update DB
        db.update_decision(decision_id, debate_url=url,
                           debate_summary=result.summary, job_status="complete")
    except Exception as exc:
        db.update_decision(decision_id, job_status="failed")
        raise self.retry(exc=exc, countdown=10)
```

### 7.3 Frontend SSE Listener

```typescript
// hooks/useDecisionStream.ts
const useDecisionStream = (decisionId: string) => {
  useEffect(() => {
    const es = new EventSource(`/v1/decisions/${decisionId}/stream`)
    es.addEventListener("bias_ready", (e) => setBias(JSON.parse(e.data)))
    es.addEventListener("simulation_ready", (e) => setSimulation(JSON.parse(e.data)))
    es.addEventListener("debate_complete", (e) => setDebate(JSON.parse(e.data)))
    es.addEventListener("done", () => es.close())
    return () => es.close()
  }, [decisionId])
}
```

### 7.4 Claude API Cost Management

At scale: 3 agents × ~1,000 tokens each = ~3,000 tokens per analysis.

**Optimizations:**
1. **Cache debate results** for identical inputs (Redis TTL 1 hour, key = SHA256 of input features)
2. **Judge runs only when Bull and Bear disagree** beyond a 30% confidence gap — saves 1 call in ~40% of cases
3. **Track usage** in a `claude_usage_log` table (tokens, cost estimate, decision_id)
4. **Monthly budget alert** via Anthropic dashboard webhook — email alert at 80% budget

---

## 8. PHASE 5 — ML Core Components

### 8.1 Bias Detector (Existing — GAP 1 ✅)

- XGBoost v3, 85.81% Macro F1, 52 features
- Input: financial decision features (unrealized G/L, holding period, position size, market context, etc.)
- Output: `{ bias: "loss_aversion"|"herd"|"disposition"|"rational", confidence: 0.87 }`
- No changes needed — wrap in a FastAPI-callable class

### 8.2 Causal Inference (Existing — GAP 2 ✅)

> [!NOTE]
> **Academic acknowledgement required (GAP 3 write-up):** DoWhy computes causal effects based on an assumed causal graph (DAG). The validity of these estimates depends on whether the synthetic training data faithfully represents real-world confounders. The assumed DAG must be explicitly stated in the paper: `Bias → Decision Intent → Outcome`. Reviewers will ask about unobserved confounders (e.g., financial literacy, risk capacity). Acknowledge this as a limitation.

### 8.3 Simulator (Existing — GAP 2 ✅)

- Monte Carlo, 10,000 paths
- Output: `{ hold: {p10, p50, p90}, sell: {p10, p50, p90}, opportunity_cost }`

### 8.4 Explainer — GAP 3 (Build)

```python
class DecisionExplainer:
    def explain(self, bias, confidence, simulation, causal_effect) -> dict:
        return {
            "situation": f"Market down X%, your {symbol} is down Y%",
            "bias_plain": "Loss aversion — you feel this loss 2.3x more than an equivalent gain",
            "causal_effect": 0.312,   # DoWhy estimate
            "recommendation": "HOLD",
            "cost_plain": f"Selling now costs ₹{opportunity_cost:,} over 20 years",
            "confidence_plain": f"87% confidence in this bias classification"
        }
```

### 8.5 Debate Engine — GAP 3 Extension (Build)

Three AutoGen agents with Claude Sonnet:

```python
BullAgent:  "Argue why HOLDING is rational given the evidence. Use the causal analysis."
BearAgent:  "Argue why SELLING may be justified. Present the strongest countercase."
JudgeAgent: "Review both arguments. Give a final verdict with clear reasoning."
```

Output schema (stored as summary in DB, full in R2):
```json
{
  "bull": { "argument": "...", "key_points": ["...", "..."] },
  "bear": { "argument": "...", "key_points": ["...", "..."] },
  "judge": { "verdict": "HOLD", "reasoning": "...", "confidence": 0.82 }
}
```

### 8.6 Audit Logger — GAP 4 (Build)

```python
class AuditLogger:
    GENESIS_PREFIX = "GENESIS"

    def log(self, decision_id, user_id, input_data, output_data):
        input_hash = sha256(json.dumps(input_data, sort_keys=True))
        output_hash = sha256(json.dumps(output_data, sort_keys=True))

        last = db.get_last_audit(user_id)
        previous_hash = last.full_hash if last else sha256(f"{self.GENESIS_PREFIX}:{user_id}")

        full_hash = sha256(input_hash + output_hash + previous_hash)

        db.insert_audit_log(
            decision_id=decision_id,
            user_id=user_id,
            block_index=(last.block_index + 1) if last else 0,
            input_hash=input_hash,
            output_hash=output_hash,
            previous_hash=previous_hash,
            full_hash=full_hash,
        )
```

---

## 9. PHASE 6 — React + Tailwind Frontend

### 9.1 Tech Stack

```
React 18 + Vite 5
Tailwind CSS v3
shadcn/ui (Radix UI — accessible component primitives)
Lucide React (icons)
Zustand (theme, auth state)
TanStack Query v5 (data fetching, caching, SSE integration)
React Router v6
React Hook Form + Zod (form validation)
Recharts (wealth trajectory, bias history charts)
Framer Motion (page transitions, card entrance animations)
Axios (HTTP — with CSRF interceptor)
Sentry React SDK (error boundary + automatic error reporting)
```

### 9.2 Design System — FINALIZED

**Name:** Decision Intelligence
**Stitch Project:** `14062838239756964673`

#### Dark Mode Tokens (Default)

```css
'bg-base':        '#08080F'   /* page background */
'bg-surface':     '#13131A'   /* card background */
'bg-container':   '#1F1F27'   /* nested panels */
'bg-elevated':    '#2A2931'   /* modals, popovers */
'border-subtle':  '#464554'
'border-focus':   '#6366F1'
'text-primary':   '#E4E1EC'
'text-secondary': '#C7C4D7'
'text-muted':     '#908FA0'
'indigo':         '#6366F1'   /* primary CTA, active nav ONLY */
'emerald':        '#10B981'   /* HOLD, rational, positive */
'rose':           '#F43F5E'   /* bias alerts, SELL line */
'amber':          '#F59E0B'   /* herd behavior, warnings */
```

#### Light Mode Tokens

```css
'bg-base':        '#F8F8FC'
'bg-surface':     '#FFFFFF'
'bg-container':   '#F3F3F8'
'border-subtle':  '#E5E7EB'
'text-primary':   '#111827'
'text-secondary': '#374151'
'text-muted':     '#6B7280'
/* accent colors same as dark mode */
```

#### Typography

```
Inter 700/600     → headings, labels
Inter 400/500     → body text
JetBrains Mono    → ALL financial numbers, hashes, tickers
```

#### Shapes

```
Card radius:   16px (rounded-2xl)
Button radius:  8px (rounded-lg)
Badge radius: 9999px (rounded-full)
Card padding:  24px
Grid gutter:   24px
```

#### Anti-Patterns

- ❌ Red/green price tickers
- ❌ Candlestick charts
- ❌ Dense tables > 6 columns
- ❌ Neon glows
- ❌ Heavy glassmorphism blur

### 9.3 FOUC Fix — Theme on First Load

> [!IMPORTANT]
> Zustand initializes AFTER React mounts. If theme preference is read by Zustand, there is a 1-frame flash of the wrong theme (FOUC). Fix with an inline script in `index.html` that runs BEFORE React:

```html
<!-- index.html — before <script type="module"> -->
<script>
  (function() {
    const t = localStorage.getItem('theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    document.documentElement.classList.add(t)
  })()
</script>
```

This guarantees the correct class is on `<html>` before the first paint. Zustand then reads and syncs from `localStorage` on mount.

### 9.4 Light/Dark Toggle

```typescript
// store/themeStore.ts
const useThemeStore = create<ThemeStore>((set) => ({
  theme: (localStorage.getItem('theme') as Theme) || 'dark',
  toggle: () => set((s) => {
    const next = s.theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.remove('dark', 'light')
    document.documentElement.classList.add(next)
    localStorage.setItem('theme', next)
    return { theme: next }
  }),
}))
```

### 9.5 Mobile Responsiveness

The bento grid uses a 12-column layout on desktop. Responsive collapse:

```
≥ 1280px (xl):  2-column bento, sidebar visible
≥ 768px  (md):  1-column bento, sidebar collapses to icon strip
< 768px  (sm):  1-column stacked cards, sidebar becomes bottom nav
```

```tsx
// Dashboard bento grid
<div className="grid grid-cols-1 md:grid-cols-1 xl:grid-cols-12 gap-6">
  <div className="xl:col-span-8"> {/* Portfolio Snapshot */} </div>
  <div className="xl:col-span-4"> {/* Bias Alert */} </div>
  <div className="xl:col-span-8"> {/* Last Decision */} </div>
  <div className="xl:col-span-4"> {/* Market Pulse */} </div>
</div>
```

Mobile sidebar → bottom nav with 5 icons: Dashboard, Analyze, Portfolio, History, Settings.

### 9.6 Route Map (Full)

```
/ (public)                  Landing page
/login                      Login + MFA step
/register                   Registration
/verify-email               Email verification
/forgot-password            Password reset request
/reset-password             Password reset form
/auth/google/callback       OAuth redirect handler

/dashboard                  Home — bento summary
/dashboard/decision         Analysis wizard + results
/dashboard/simulation       HOLD vs SELL chart (standalone)
/dashboard/portfolio        Holdings + live P&L
/dashboard/history          Past decisions + bias trend
/dashboard/audit            Audit log + hash verifier
/dashboard/profile          Profile viewer + edit
/dashboard/settings         MFA, password, theme, notifications, delete account

/admin                      Admin home — aggregate stats
/admin/users                User list + management
/admin/system               System health, model metrics
```

### 9.7 Error Handling — Frontend

```tsx
// ErrorBoundary wraps entire app
// Sentry.ErrorBoundary fallback component shows:
// "Something went wrong. Our engineers have been notified."
// + "Go back to Dashboard" button

// Per-request error display (React Query):
// On API error, TanStack Query's error object contains:
// { error: "CLAUDE_UNAVAILABLE", message: "Debate unavailable" }
// → Toast notification using shadcn/ui Toaster
```

### 9.8 Finalized Dashboard Card Layout

```
┌──────────────────────────────┬──────────────────┐
│ PORTFOLIO SNAPSHOT            │ ACTIVE BIAS ALERT │
│ ₹12,47,832 (JetBrains Mono)  │ Loss Aversion     │
│ ▁▂▃▅▄▆▇ (indigo sparkline)   │ Confidence: 87%   │
│ HOLD RECOMMENDED ● (badge)   │ rose progress bar │
│ Risk: 3.4  Diversification:82%│                   │
├──────────────────────────────┼──────────────────┤
│ LAST DECISION                 │ MARKET PULSE      │
│ HDFC Bank · Oct 24 · 09:45AM │ NIFTY 50 22,147 ▲ │
│ 140 shares @ ₹1,642.40       │ SENSEX   73,018 ▲ │
│ [View Analysis →] (indigo)   │ India VIX  14.82 ▼ │
│                               │ Updated 2 min ago │
└──────────────────────────────┴──────────────────┘
```

---

## 10. PHASE 7 — Landing Page

> [!IMPORTANT]
> The landing page is the first thing any user, professor, investor, or recruiter sees. Its spec is mandatory, not optional.

### Sections (in order)

**Hero:**
- Headline: "Stop investing on emotion. Start investing on evidence."
- Sub: "AI that detects your behavioral bias, quantifies its 20-year cost, and tells you what to do — with full causal reasoning."
- CTA: "Analyze a Decision Free →" (indigo, prominent)
- Secondary: "See how it works ↓" (ghost button)

**Social Proof Bar (below hero):**
- "85.81% bias detection accuracy · 4 bias types · 10,000 Monte Carlo paths · Cryptographic audit trail"
- These are real, defensible research numbers

**3 Core Value Props:**
1. "Know your bias" — bias detection card with animated confidence ring
2. "See the cost" — mini wealth trajectory chart (Hold vs Sell)
3. "Trust the proof" — hash chain visualization

**How It Works (3 steps):**
1. Enter your position (stock, gain/loss, intent)
2. AI analyzes your bias and simulates 20 years of outcomes
3. Get a clear recommendation with full causal explanation

**Demo CTA:**
- "Try it now — no sign-up required for one analysis"
- Or: "Watch a 90-second demo" → embed Loom video

**Footer:** GitHub link (if open-source), research paper link (when published), contact.

---

## 11. PHASE 8 — Practical Extensions

| Module | Priority | Key Implementation Detail |
|---|---|---|
| `tax_engine.py` | High | STCG 15% / LTCG 10%, holding period check, applied to SELL simulation |
| `sip_tracker.py` | High | Pause detection, Monte Carlo on pause cost, NIFTY-drop trigger |
| `kite_integration.py` | Medium | See Kite note below |
| `multi_asset.py` | Medium | MF via MFAPI.in, Gold via nsepython, Crypto via CoinGecko |
| `outcome_tracker.py` | Medium | Track if recommendation followed, fetch actual outcome 30/90 days later |
| `retrain_monthly.py` | Medium | Batch job: new real decisions + synthetic, retrain if F1 improves |
| `data_export.py` | Required | GDPR: `GET /v1/users/me/export` → full JSON, all user data |
| `whatsapp_bot.py` | Low | Meta Cloud API webhook, 3-line decision summary |

### Kite Daily Token Re-Auth

> [!WARNING]
> Zerodha Kite access tokens expire at **6 AM IST daily** — on a fixed clock, not a TTL. Storing the token in the DB is insufficient.

**Implementation:**
- Store the Kite `request_token` (long-lived) in `users.kite_refresh_token` (encrypted)
- On every portfolio fetch: check if `kite_token_expiry < NOW()` → auto-regenerate access token using `kite_connect` with stored refresh token
- If refresh fails (user revoked): show "Reconnect Kite" banner, set `kite_linked=false` on all holdings
- Daily cron job at 6:15 AM IST refreshes all active Kite sessions proactively

---

## 12. PHASE 9 — Infrastructure & Deployment

### 12.1 Render Configuration

```yaml
# render.yaml
services:
  - type: web
    name: finai-backend
    runtime: python
    buildCommand: pip install -r requirements.txt && alembic upgrade head
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
    envVars:
      - key: DATABASE_URL
        fromDatabase: { name: finai-postgres, property: connectionString }
      - key: REDIS_URL
        value: <Upstash Redis URL>       # NOT Render Redis
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: SECRET_KEY
        sync: false

  - type: worker
    name: finai-celery
    runtime: python
    startCommand: celery -A jobs.celery_app worker --loglevel=info --concurrency=2

  - type: web
    name: finai-frontend
    runtime: static
    buildCommand: cd frontend && npm ci && npm run build
    staticPublishPath: frontend/dist

databases:
  - name: finai-postgres
    plan: free
    databaseName: finai
```

### 12.2 AWS Migration Path

```
Render (now)            →    AWS (later)
────────────────────         ───────────────────────
Neon PostgreSQL         →    RDS PostgreSQL Multi-AZ
Upstash Redis           →    ElastiCache Redis (or keep Upstash)
Render Web Service      →    ECS Fargate (Docker containers)
Render Static Site      →    S3 + CloudFront CDN
Render Celery Worker    →    ECS Fargate (separate task definition)
Cloudflare R2           →    S3 (same SDK, different endpoint)
────────────────────         ───────────────────────
Only environment variables change. Zero code changes.
```

### 12.3 Docker

```dockerfile
# Dockerfile.backend
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Dockerfile.celery (same image, different CMD)
CMD ["celery", "-A", "jobs.celery_app", "worker", "--loglevel=info"]

# Dockerfile.frontend
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json .
RUN npm ci
COPY frontend/ .
RUN npm run build
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

---

## 13. PHASE 10 — Observability & Monitoring

> [!NOTE]
> For a system making ML inferences and external AI API calls, knowing *when* things fail and *why* is essential. This is not optional.

### Sentry (Error Tracking — Free Tier)

```python
# main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.2,     # 20% of requests traced
    environment=settings.ENVIRONMENT,
)
```

```typescript
// frontend/src/main.tsx
import * as Sentry from "@sentry/react"
Sentry.init({ dsn: import.meta.env.VITE_SENTRY_DSN, environment: "production" })
```

Every unhandled exception on both backend and frontend is automatically captured, with full stack trace and request context.

### structlog (Structured JSON Logs)

```python
# All service logs structured as JSON (Render surfaces these)
logger.info("debate_complete",
    decision_id=decision_id,
    tokens_used=tokens,
    duration_ms=duration,
    job_status="complete"
)
logger.error("market_fetch_failed",
    source="nsepython",
    symbol="NIFTY50",
    error=str(exc)
)
```

### What to Monitor

| Signal | Tool | Alert Threshold |
|---|---|---|
| Unhandled exceptions | Sentry | Any new error type |
| Celery job failure rate | Sentry + custom metric | > 5% failure rate |
| Claude API latency | structlog | > 45 seconds |
| Market data fetch failures | Sentry | > 3 consecutive failures |
| Neon DB connection errors | Sentry | Any |
| Token blacklist write failures | Sentry | Any (security critical) |

---

## 14. Test Strategy

### Unit Tests

```
tests/test_bias_detector.py
  - Test each bias class is correctly classified on known inputs
  - Test confidence scores are in [0,1]
  - Test feature vector shape matches expected 52 features

tests/test_simulator.py
  - Test output shape (p10/p50/p90 for both scenarios)
  - Test HOLD p50 > SELL p50 for loss-aversion inputs (known property)
  - Test reproducibility with fixed random seed

tests/test_audit_chain.py    ← correctness guarantee
  - Test genesis block has correct GENESIS:{user_id} hash
  - Test chain: entry N's previous_hash == entry N-1's full_hash
  - Test that modifying any entry breaks all subsequent hashes
  - Test append-only: delete and update SQL blocked
```

### Integration Tests

```
tests/test_auth.py
  - register → verify email → login → MFA setup → MFA login → refresh → logout
  - Google OAuth flow (mock Google response)
  - Token blacklist: verify token invalid after logout
  - Rate limit: 6th login attempt in 1 min → 429

tests/test_api_isolation.py    ← critical security tests
  - User A token → GET /v1/decisions/my → returns ONLY User A's decisions
  - User A token → attempt GET /v1/users/{user_b_id}/... → 403
  - Admin token → GET /v1/admin/stats → aggregate only, no user_id in response
  - Admin token → GET /v1/decisions/my → returns ONLY admin's own (empty usually)
```

### CI/CD Quality Gates

```yaml
# .github/workflows/main.yml
test-backend:
  - pytest backend/tests/ --cov=backend --cov-fail-under=70
  - Must pass: test_audit_chain.py (correctness guarantee)
  - Must pass: test_api_isolation.py (security guarantee)

test-frontend:
  - npm run test
  - npm run build  (catches type errors + build failures)

deploy:
  needs: [test-backend, test-frontend]
  - only: push to main
  - trigger Render deploy webhook
```

---

## 15. Security Summary

| Threat | Mitigation | Layer |
|---|---|---|
| User A reads User B's data | `get_current_user()` returns only own data, PostgreSQL RLS backup | App + DB |
| Admin reads raw user data | Admin queries `admin_stats_view` — no user_id column | DB query design |
| XSS token theft | httpOnly cookies — JS cannot read | Browser |
| CSRF | X-CSRF-Token double-submit, validated in middleware | App |
| Brute force login | 5 req/min per IP, Upstash Redis counter | Middleware |
| MFA bypass | Google OAuth explicitly documented as TOTP bypass | Design decision |
| Password breach | bcrypt cost=12, zxcvbn score ≥ 3 enforced | App |
| JWT forgery | RS256 asymmetric, private key never exposed | App |
| Token replay after logout | jti written to Upstash Redis blacklist | App + Redis |
| Redis wipe = blacklist lost | **Upstash Redis** (persists on restart, not Render Redis) | Infra |
| Audit tampering | PostgreSQL RULE blocks DELETE/UPDATE + SHA-256 hash chain | DB + App |
| GDPR | Soft delete → 30-day grace → hard delete + data export | App |
| SQL injection | asyncpg parameterized queries everywhere | App |
| OAuth account hijack | Email uniqueness constraint, Google email binding | App + DB |
| HTTPS downgrade | HSTS header, Render enforces HTTPS | Infra |
| PgBouncer prepared stmt | `statement_cache_size=0` in asyncpg pool | App |
| Kite token expiry | Daily proactive refresh at 6:15 AM IST | Services |

---

## 16. Role Permissions Reference

### Guest (Unauthenticated)

| Action | Allowed |
|---|---|
| View landing page | ✅ |
| Register / login / forgot password | ✅ |
| View market data (`/v1/market/context`) | ✅ |
| Any dashboard or API endpoint | ❌ 401 |

### User (role = `user`)

**Account:**

| Action | Verification Needed |
|---|---|
| View/edit name, goal, strategy | None |
| Change email | Password + OTP to old email |
| Change password | Current password + TOTP |
| Change monthly income/expenses | Current password |
| Enable/disable MFA | Password + current TOTP |
| Export own data (GDPR) | None |
| Delete account | Password + TOTP + type "DELETE" |
| View another user's profile | ❌ 403 |

**Decisions & Analysis:**

| Action | Allowed |
|---|---|
| Submit analysis (bias + simulation + debate) | ✅ Own user_id only |
| View own past decisions | ✅ |
| View own bias history | ✅ |
| View own audit trail + verify hash | ✅ |
| View another user's any data | ❌ 403 |
| Modify audit entries | ❌ DB-level blocked |

**Portfolio:**

| Action | Allowed |
|---|---|
| Add/edit/delete own holdings | ✅ |
| View own live P&L | ✅ |
| Connect Zerodha Kite | ✅ (with password re-verification) |
| View another user's portfolio | ❌ 403 |

**Sensitive Edit Window:** After re-verification, user has a 5-minute window to edit sensitive fields without re-verifying each one.

### Admin (role = `admin`)

**Can:**
- View user list (name, email, join date, is_active, decision count — NO financial data)
- Activate / deactivate user accounts
- Reset a user's password (triggers reset email to user)
- Force-reset MFA (triggers email notification to user)
- Hard-delete user after 30-day soft delete grace period
- View aggregate stats via `admin_stats_view`
- View system health metrics (API latency, error rates, model F1)
- Trigger manual model retraining

**Cannot (enforced at query level, not just application logic):**
- See any user's `raw_input`, `raw_output`, `debate_url`
- See any user's portfolio holdings
- See any user's decision history
- See user's income, expenses, financial profile
- See plaintext passwords (bcrypt only, never exposed)
- Modify or delete audit logs (DB RULE)
- Access any `/v1/decisions/my` or portfolio endpoint (returns admin's own empty data only)

---

## 17. Timeline (Realistic — 22 Weeks)

Given concurrent commitments (Barclays internship), this is the realistic schedule:

| Weeks | Phase | Deliverable |
|---|---|---|
| 1–3 | Phase 1 | Auth backend: register, verify, login, MFA, Google OAuth, CSRF |
| 3–5 | Phase 2 | PostgreSQL schema, Alembic migrations, asyncpg pool with PgBouncer fix |
| 5–7 | Phase 3 | Backend restructure: all `/v1/` routes, error handlers, rate limiting, Sentry |
| 7–9 | Phase 6 | React: auth pages, routing, Axios interceptors, theme toggle, FOUC fix |
| 9–11 | Phase 6 | React: dashboard layout, bento grid, market pulse, decision wizard |
| 11–12 | Phase 5 | GAP 3: Explainer + Debate Engine (Celery + SSE integration) |
| 12–13 | Phase 5 | GAP 4: Audit Logger (hash chain, genesis block, frontend verifier) |
| 13–14 | Phase 8 | Tax engine + SIP tracker |
| 14–15 | Phase 6 | React: portfolio page, simulation page, history + bias chart |
| 15–16 | Phase 6 | React: profile management, settings, account deletion flow |
| 16–17 | Phase 7 | Landing page (hero, value props, demo CTA) |
| 17–18 | Phase 9 | Docker setup, Render deployment, CI/CD, Sentry live |
| 18–19 | Phase 8 | Kite integration (with daily re-auth), mobile responsiveness QA |
| 19–20 | Phase 10 | Observability: structured logs, alert thresholds, Claude cost monitoring |
| 20–21 | Hardening | Security audit, test coverage to 70%+, load test |
| 21–22 | Launch | Admin panel, multi-asset support, submission-ready demo |

**Load-bearing structure (Phases 1–6):** Must ship before anything else. Academic submission viable after Week 17.
**Nice-to-have (Phase 8+):** Kite, WhatsApp, outcome tracker — can be cut without affecting submission.
