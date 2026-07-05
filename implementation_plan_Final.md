# Autonomous Financial Decision Intelligence System
## Production Implementation Plan — v2.0
### Fully Restructured & Specified

> Changes from v1.0 are marked `[NEW]` or `[REVISED]` throughout.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Phase 1 — Auth System](#phase-1--auth-system)
4. [Phase 2 — Database](#phase-2--database)
5. [Phase 3 — Backend Restructure](#phase-3--backend-restructure)
6. [Phase 4 — React Frontend](#phase-4--react-frontend)
7. [Phase 5 — ML Components](#phase-5--ml-components)
8. [Phase 6 — Practical Extensions](#phase-6--practical-extensions)
9. [Phase 7 — Infrastructure & Deployment](#phase-7--infrastructure--deployment)
10. [Phase 8 — Admin Dashboard](#phase-8--admin-dashboard)
11. [Security Summary](#security-summary)
12. [Test Strategy](#test-strategy)
13. [Build Sequence](#build-sequence)
14. [Role Reference](#role-reference)

---

## 1. Project Overview

### Mission

An **Autonomous Financial Decision Intelligence System** — a full-stack, AI-powered web application that helps retail Indian investors make rational, evidence-based financial decisions instead of emotional ones.

The core mission is **debiasing the investment decision process.** Retail investors lose money not because markets are unpredictable, but because they make predictably irrational decisions — panicking during a drawdown (loss aversion), following the crowd into overvalued assets (herd behavior), or holding losers and selling winners too early (disposition effect). This system detects those biases in real-time, explains them causally, quantifies the 20-year financial cost of acting on them, and gives a clear, evidence-backed recommendation.

> **What this system is NOT:**
> It does not predict stock prices. It does not replace a financial advisor. It does not tell you what to buy. It tells you — when you are *about to make a decision* — whether that decision is being driven by rational analysis or cognitive bias, and what the 20-year financial cost of that bias is.

---

### Target Users

**Retail Indian investors** — people who actively invest in stocks, mutual funds, or SIPs and make buy/sell decisions. They may be emotionally reactive to market volatility and lack a structured decision framework.

**Working professionals with savings** — salaried individuals who invest a portion of their income and want structured guidance before major moves (e.g., "should I sell my HDFC Bank shares that are down 18%?").

---

### Core Features

| # | Feature | Technology | Status |
|---|---|---|---|
| 1 | Behavioral Bias Detection | XGBoost v3 — 85.81% Macro F1 | ✅ Done |
| 2 | Causal Inference Engine | DoWhy — establishes causal relationship between bias and decision outcome | 🔲 Building |
| 3 | 20-Year Monte Carlo Simulation | 10,000 paths — HOLD vs SELL trajectories with P10/P50/P90 bands | ✅ Done |
| 4 | Multi-Agent AI Debate | AutoGen + Claude Sonnet — Bull / Bear / Judge, streamed via SSE | 🔲 Building |
| 5 | Tamper-Evident Audit Trail | SHA-256 hash chaining — every decision cryptographically chained | 🔲 Building |
| 6 | Live Portfolio Tracker | Real-time P&L via Zerodha Kite API or manual entry, STCG/LTCG badges | 🔲 Building |
| 7 | SIP Pause Detector | Detects SIP pauses during dips, quantifies opportunity cost | 🔲 Building |

---

### Research Pillars

| GAP | Research Question | Status |
|---|---|---|
| GAP 1 | Can ML detect behavioral biases from financial decision features? | ✅ Complete — XGBoost v3, 85.81% F1 |
| GAP 2 | What is the long-horizon cost of biased decisions? | ✅ Complete — Monte Carlo simulator |
| GAP 3 | Can AI provide causal, human-readable explanations for its recommendations? | 🔲 Building — Explainer + Debate Engine |
| GAP 4 | Can the audit trail be made cryptographically tamper-evident? | 🔲 Building — SHA-256 hash chain |

---

### What Makes This Different

| Typical Trading App | This System |
|---|---|
| Shows price charts and order books | Shows your cognitive bias and its 20-year ₹ cost |
| Encourages more trading (revenue model) | Encourages less, calmer, rational trading |
| Red/green flashing numbers → triggers panic | Calm, structured analysis → reduces panic |
| No explanation for suggestions | Full causal reasoning + AI debate transcript |
| No audit trail | Cryptographic audit log — every decision hashed and verifiable |
| No behavioral awareness | Bias history tracked over time |

---

### Migration Context

The system exists as a working prototype:
- FastAPI backend (13+ endpoints)
- Streamlit dashboard (4-page)
- SQLite database (not scalable)
- XGBoost bias detector v3 (trained on synthetic data)
- Partial GAP 2 simulator

This plan takes it to production: React + Tailwind frontend, PostgreSQL, proper multi-tenant auth, cloud deployment on Render with an AWS migration path.

---

### Confirmed Decisions

| Question | Decision |
|---|---|
| Deployment | Render (now) → AWS (later) — Docker-first for portability |
| Auth | JWT RS256 + MFA (TOTP) + OAuth (Google) |
| Database | PostgreSQL (Neon) + PgBouncer connection pooler |
| Cache / Sessions | Upstash Redis (replaces Render Redis — more reliable) `[REVISED]` |
| UI scope | Full-featured product, premium bento-grid minimalism |
| Profile changes | Re-verification required for sensitive fields |
| Account deletion | GDPR-compliant soft delete + hard delete after 30 days |
| API versioning | All routes prefixed `/v1/` `[NEW]` |
| Async decisions | SSE streaming + FastAPI BackgroundTasks (no Celery) `[NEW]` |
| Observability | Sentry (errors) + structlog (logs) `[NEW]` |

---

## 2. Architecture Overview

```
[React Frontend — Vite + Tailwind]
        │  HTTPS only (HSTS enforced)
        ▼
[Nginx — Render]
   ├── /api/v1/*  → FastAPI backend (port 8000)
   └── /          → React SPA (port 3000)
        │
        ▼
[FastAPI Backend]
   ├── Auth layer       (JWT RS256 + TOTP + Google OAuth + CSRF)
   ├── ML core          (XGBoost, DoWhy, Simulator, Debate Engine)
   ├── Services         (market, tax, SIP, Kite)
   ├── Background tasks (SSE-streamed AI pipeline)
   └── Observability    (Sentry + structlog)
        │
   ┌────┴────────────────┐
   ▼                     ▼
[Neon PostgreSQL      [Upstash Redis]
 + PgBouncer]         (token blacklist, rate limit,
                       OTP cache, SSE pub/sub)
```

### Key Architectural Decisions `[NEW]`

**1. No Celery — FastAPI BackgroundTasks + SSE**
The AI pipeline (bias → simulator → explainer → debate) is long-running (15–30s). Rather than adding Celery (which requires a worker process and is heavy on Render free tier), we use:
- `BackgroundTasks` to run the pipeline after returning a `decision_id` immediately
- **Server-Sent Events (SSE)** on `GET /v1/decisions/{id}/stream` so the frontend receives real-time progress
- The pipeline publishes step completions to an **Upstash Redis pub/sub channel** keyed by `decision_id`
- SSE endpoint subscribes and forwards events to the browser

This gives real-time UX with zero additional infrastructure.

**2. `/v1/` prefix on all API routes**
Allows breaking changes without breaking existing integrations. Frontend uses an Axios base URL of `/api/v1`.

**3. Ownership enforced by JWT, not path params**
Instead of `GET /v1/users/{user_id}/decisions` (path-param that could be spoofed), all user-owned endpoints use the JWT subject directly: `GET /v1/decisions/my`. The `user_id` never appears in the URL.

**4. asyncpg `statement_cache_size=0` `[NEW]`**
PgBouncer in transaction-pooling mode does not support prepared statements. asyncpg uses them by default. All connection pool setup must explicitly disable them.

---

### Environment Variables Reference [NEW]

Create a `.env` file in the root directory for local development.

| Variable | Description | Allowed Values / Format | Default |
|---|---|---|---|
| `ENV` | Application environment | `development`, `staging`, `production` | `development` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:port/db?sslmode=require` | (Required) |
| `REDIS_URL` | Upstash Redis connection string | `redis://default:token@host:port` or `rediss://` | (Required) |
| `JWT_PRIVATE_KEY` | RS256 asymmetric private key (PEM content) | Hex/base64 encoded or raw PEM string | (Required) |
| `JWT_PUBLIC_KEY` | RS256 asymmetric public key (PEM content) | Hex/base64 encoded or raw PEM string | (Required) |
| `AES_KEY` | 32-byte key for encrypting TOTP secrets and Kite tokens | 64-character hex string | (Required) |
| `CLAUDE_API_KEY` | Anthropic Claude API Key | `sk-ant-api03-...` | (Required) |
| `CLAUDE_MONTHLY_BUDGET_USD` | Safety budget ceiling for Claude API | Numeric, e.g. `50.00` | `50.00` |
| `ADMIN_EMAIL` | Target email for budget and system warnings | Email address | (Required) |
| `SMTP_HOST` | Host for outgoing notification emails | hostname | `smtp.gmail.com` |
| `SMTP_PORT` | Port for outgoing emails | `587` or `465` | `587` |
| `SMTP_USERNAME` | Email user for authentication | email / username | (Required) |
| `SMTP_PASSWORD` | App-specific password for SMTP | App password | (Required) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google Client ID for OAuth flow | `...apps.googleusercontent.com` | (Required) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google Client Secret | OAuth Secret | (Required) |
| `SENTRY_DSN` | Backend and Frontend Sentry tracking DSN | Sentry project DSN URL | (Optional) |
| `ZERODHA_KITE_API_KEY` | Zerodha Kite developer API key | Developer key | (Required for Kite) |
| `ZERODHA_KITE_API_SECRET` | Zerodha Kite developer API secret | Developer secret | (Required for Kite) |
| `META_WA_PHONE_NUMBER_ID` | Meta WhatsApp Bot phone number ID | Numeric ID | (Required for WA) |
| `META_WA_ACCESS_TOKEN` | Meta WhatsApp Bot access token | Permanent System User Token | (Required for WA) |
| `CORS_ALLOWED_ORIGINS` | CORS allowed origins for FastAPI backend | JSON array, e.g., `["http://localhost:3000"]` | `["http://localhost:3000"]` |

---

## Phase 1 — Auth System

### 1A. Core JWT Setup

**Algorithm:** RS256 — asymmetric. Private key signs tokens (server only). Public key verifies (can be distributed). If private key is ever rotated, old tokens auto-invalidate.

**Tokens:**

| Token | Expiry | Storage | Purpose |
|---|---|---|---|
| Access token | 15 minutes | httpOnly cookie | API authentication |
| Refresh token | 7 days | httpOnly cookie | Obtain new access token |
| CSRF token | Matches session | Non-httpOnly cookie | CSRF protection `[NEW]` |
| Email verify token | 24 hours | Upstash Redis | Email verification |
| Password reset token | 15 minutes | Upstash Redis | Password reset |
| Temp MFA token | 5 minutes | Upstash Redis | Between login and TOTP step |

**Key generation (run once, store as env vars):**
```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
# Store PEM content in JWT_PRIVATE_KEY and JWT_PUBLIC_KEY env vars
```

**JWT payload structure:**
```json
{
  "sub": "uuid-of-user",
  "role": "user",
  "jti": "unique-token-id",
  "iat": 1700000000,
  "exp": 1700000900
}
```

**Files:**
```
backend/auth/
├── jwt_handler.py      # sign/verify RS256, token creation, blacklist check
├── mfa_handler.py      # TOTP (pyotp) + backup code generation/verification
├── oauth_handler.py    # Google OAuth2 flow (authlib)
├── password.py         # bcrypt cost=12, zxcvbn strength check (reject score < 3)
├── csrf.py             # CSRF token generation + middleware validation [NEW]
├── dependencies.py     # get_current_user, require_mfa_verified, require_admin
└── routes.py           # all /v1/auth/* endpoints
```

---

### 1B. Registration Flow

```
POST /v1/auth/register
Body: {
  email: string,
  password: string,
  name: string,
  age: integer (optional),
  monthly_income: float (optional),
  monthly_expense: float (optional),
  risk_tolerance: float (optional, 0.0–1.0),
  investment_horizon: integer (years, optional),
  has_emergency_fund: boolean (optional),
  financial_strategy: string (optional),
  goal: string (optional)
}

Steps:
  1. Validate email format (pydantic EmailStr)
  2. Check email not already registered (return 409 if duplicate)
  3. zxcvbn password strength check — reject if score < 3
     Return: { error: "WEAK_PASSWORD", suggestions: ["..."] } if rejected
  4. bcrypt hash password (cost=12)
  5. Create user row: is_active=false, email_verified=false
  6. Generate 64-char random email verification token
  7. Store in Redis: key="email_verify:{token}" value=user_id, TTL=86400 (24h)
  8. Send verification email via Resend API
     Subject: "Verify your ScaleAI account"
     Body: link = https://app.com/auth/verify-email?token={token}
  9. Return 201: { message: "Check your email to verify your account." }

GET /v1/auth/verify-email?token={token}
Steps:
  1. Look up Redis key "email_verify:{token}"
     → 400 "Invalid or expired token" if not found
  2. Fetch user by user_id from Redis value
  3. Set email_verified=true, is_active=true, updated_at=NOW()
  4. Delete Redis key (one-time use)
  5. Redirect to /login?verified=true
     (frontend shows "Email verified! Please log in." toast)

Edge cases:
  - User registers, never verifies, re-registers with same email:
    → If user is not active and email_verified=false, allow re-registration
    → Delete old unverified record, create fresh one
  - User clicks verify link twice:
    → Redis key is already deleted → return 400 "Token already used"
```

---

### 1C. Login Flow

```
POST /v1/auth/login
Body: { email: string, password: string }

Steps:
  1. Look up user by email
     → 401 "Invalid credentials" if not found (do NOT reveal "email not found")
  2. bcrypt verify password
     → 401 "Invalid credentials" if mismatch
  3. Check is_active=true, email_verified=true
     → 403 "Please verify your email before logging in." if not active
  4. If user is soft-deleted (deleted_at IS NOT NULL):
     → 403 "This account has been scheduled for deletion."
       Include: { recovery_link: "/auth/cancel-deletion" }
  5. Update last_login_at = NOW()

  IF mfa_enabled = false:
    → Generate access_token + refresh_token + csrf_token
    → Store refresh token hash in refresh_tokens table
    → Set cookies: access_token (httpOnly), refresh_token (httpOnly), csrf_token (NOT httpOnly)
    → Return 200: { user: { id, name, role, mfa_enabled: false } }

  IF mfa_enabled = true:
    → Generate temp_token (32-char random hex)
    → Store in Redis: key="mfa_temp:{temp_token}" value=user_id, TTL=300 (5 minutes)
    → Return 200: { mfa_required: true, temp_token: "..." }
    → Frontend redirects to /login/mfa page

POST /v1/auth/login/mfa
Body: { temp_token: string, totp_code: string }

Steps:
  1. Look up Redis key "mfa_temp:{temp_token}"
     → 401 "Session expired. Please log in again." if not found
  2. Fetch user by user_id from Redis value
  3. Decrypt mfa_secret_enc from DB (AES-256)
  4. Validate TOTP code via pyotp.TOTP(secret).verify(totp_code, valid_window=1)
     valid_window=1 allows ±30 seconds for clock drift
     → 401 "Invalid code. Please try again." if invalid
  5. Also accept backup codes:
     → Hash the submitted code, compare against stored hashed backup codes
     → If match: mark that backup code as used (one-time)
     → Warn: "You used a backup code. 7 backup codes remaining."
  6. Delete Redis temp_token key
  7. Generate access_token + refresh_token + csrf_token
  8. Set cookies, return user object (same as non-MFA login)

POST /v1/auth/refresh
(No body — reads httpOnly refresh_token cookie)

Steps:
  1. Read refresh_token from cookie
     → 401 if cookie missing
  2. Verify RS256 signature, check expiry
     → 401 if invalid/expired
  3. Extract jti, check Redis blacklist "blacklist:{jti}"
     → 401 "Token revoked" if blacklisted
  4. Look up refresh_tokens table: find row by token_hash, verify user_id matches
     → 401 if not found (tampered token)
  5. Rotate: invalidate old refresh token (add jti to Redis blacklist, TTL=7 days)
  6. Generate new access_token + refresh_token
  7. Update refresh_tokens table with new hash
  8. Set new cookies
  9. Return 200: { refreshed: true }

POST /v1/auth/logout
(No body — reads cookies)

Steps:
  1. Read refresh_token from cookie
  2. If valid: add jti to Redis blacklist
  3. Delete row from refresh_tokens table
  4. Clear all auth cookies (set Max-Age=0)
  5. Return 200: { message: "Logged out." }
```

---

### 1D. MFA Setup Flow

```
POST /v1/auth/mfa/setup
(Requires authenticated user — not yet MFA-enabled)

Steps:
  1. Verify user is authenticated (valid access token)
  2. Check mfa_enabled=false — reject if already enabled
  3. Generate TOTP secret: pyotp.random_base32()
  4. Store in Redis (NOT DB yet): key="mfa_setup:{user_id}" value=secret, TTL=600 (10 min)
  5. Build QR code URL:
     pyotp.totp.TOTP(secret).provisioning_uri(
       name=user.email,
       issuer_name="FinAI Decision Intelligence"
     )
  6. Return: { secret: "...", qr_code_url: "otpauth://..." }
     → Frontend renders QR with `qrcode.react` library
     → Also shows secret as text for manual entry

POST /v1/auth/mfa/verify-setup
Body: { totp_code: string }
(Requires authenticated user)

Steps:
  1. Get secret from Redis "mfa_setup:{user_id}"
     → 400 "Setup session expired. Start again." if not found
  2. Validate code: pyotp.TOTP(secret).verify(totp_code, valid_window=1)
     → 400 "Invalid code" if fails
  3. AES-256 encrypt secret using AES_KEY env var:
     from cryptography.fernet import Fernet
     encrypted = Fernet(AES_KEY).encrypt(secret.encode())
  4. Save encrypted secret to users.mfa_secret_enc
  5. Generate 8 backup codes:
     codes = [secrets.token_hex(4).upper() for _ in range(8)]
     hashed = [bcrypt.hash(c) for c in codes]
     Store hashes in mfa_backup_codes table (separate table, user_id FK)
  6. Set users.mfa_enabled = true
  7. Delete Redis setup key
  8. Return 200: { backup_codes: ["XXXX-XXXX", ...] }
     ← Frontend MUST show this ONCE with "Save these codes" warning
        and a confirmation checkbox before dismissing

POST /v1/auth/mfa/disable
Body: { password: string, totp_code: string }
(Requires authenticated user)

Steps:
  1. Verify password via bcrypt
  2. Verify TOTP code (same as login flow)
  3. Set mfa_enabled=false, mfa_secret_enc=NULL
  4. Delete all rows from mfa_backup_codes for this user_id
  5. Log in profile_change_log: field_changed='mfa_status', verified_via='password+totp'
  6. Invalidate all existing refresh tokens (security: force re-login everywhere)
  7. Return 200: { message: "MFA disabled." }
```

---

### 1E. MFA Account Recovery `[NEW]`

This covers the case where a user loses both their authenticator app and all backup codes.

```
User-facing flow:
  1. User goes to /login, enters credentials
  2. MFA step appears
  3. User clicks "Lost access to authenticator?"
  4. Shown: list of remaining backup codes (count only, not values)
  5. If has backup codes: redirect to backup code entry page
  6. If no backup codes: shown: "Contact support to reset your MFA."
     Link to /auth/mfa-recovery-request

POST /v1/auth/mfa-recovery-request
Body: { email: string, message: string }

Steps:
  1. Rate limit: 1 request per email per 24 hours (Redis key)
  2. Create mfa_recovery_requests table row (status='pending')
  3. Send notification email to admin (configurable ADMIN_EMAIL env var)
     Subject: "MFA Recovery Request — {email}"
     Body: user's email, request time, their message
  4. Return 200: { message: "Request submitted. We'll contact you within 24 hours." }

Admin panel — MFA Reset:
  GET  /v1/admin/users/{user_id}/mfa-status
  POST /v1/admin/users/{user_id}/reset-mfa
  Body: { admin_totp_code: string }  ← admin must verify their own TOTP

Steps (admin reset):
  1. require_admin dependency
  2. Verify admin's own TOTP code
  3. Set target user's mfa_enabled=false, mfa_secret_enc=NULL
  4. Delete all mfa_backup_codes for target user
  5. Log in profile_change_log: verified_via='admin_action', changed_by=admin_user_id
  6. Send email to user:
     Subject: "Your MFA has been reset"
     Body: "Your MFA was reset by an administrator at {time}.
            Log in with your password and set up a new authenticator."
  7. Invalidate all refresh tokens for target user
  8. Update mfa_recovery_requests row: status='resolved'
  9. Return 200

mfa_backup_codes table:
CREATE TABLE mfa_backup_codes (
    code_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,
    used        BOOLEAN DEFAULT FALSE,
    used_at     TIMESTAMPTZ
);
```

---

### 1F. Google OAuth Flow `[REVISED]`

Includes edge cases for account linking and MFA interaction.

```
GET /v1/auth/google/login
  → Redirect to Google consent screen (authlib)
    Scopes: openid, email, profile

GET /v1/auth/google/callback?code=xxx&state=yyy
  Steps:
    1. Exchange code for Google tokens via authlib
    2. Fetch profile: { email, name, picture, sub (Google user ID) }

    CASE A — New user (email not in DB):
      3a. Auto-register:
          INSERT users (email, name, profile_picture, oauth_provider='google',
                        oauth_id=sub, email_verified=true, is_active=true)
          Note: password_hash = NULL (OAuth user — no local password)
      4a. Proceed to login (set cookies, return user)

    CASE B — Existing email/password user, first Google login:
      3b. Match found by email
      4b. Check if oauth_id is NULL (not yet linked)
      5b. Set oauth_id = sub, oauth_provider = 'google'
          (Link Google to existing account silently — same email = same person)
      6b. If mfa_enabled=true on the account:
          → Google login DOES require TOTP (MFA was explicitly set by user)
          → Follow same temp_token MFA flow
          (Google handles Google-account security, but MFA here protects
           THIS app's data, regardless of login method)
      7b. Proceed to login

    CASE C — Returning OAuth user (email + oauth_id both match):
      3c. Standard login, same MFA logic as Case B

    CASE D — Google email matches a soft-deleted account:
      3d. Return 403 with recovery info (same as password login Case 4)

OAuth ↔ MFA interaction (resolved) `[NEW]`:
  - MFA enabled on account = TOTP required regardless of login method
  - This is intentional: Google secures Google, TOTP secures THIS app
  - OAuth users CAN set up TOTP via Settings → Security
  - OAuth users CANNOT set a local password (would need separate "add password" flow — out of scope v1)

"Add password" flow (out of scope v1 — documented for v2):
  OAuth users who want a local password: POST /v1/auth/add-password
  Requires: authenticated session + Google re-auth confirmation
  Sets password_hash, keeps oauth_provider (dual auth)
```

---

### 1G. Password Reset

```
POST /v1/auth/forgot-password
Body: { email: string }

Steps:
  1. Rate limit: 3 req/hour per IP (Redis)
  2. Look up user — if not found: return 200 anyway
     (security: do not reveal whether email is registered)
  3. If found and active:
     a. Generate reset token (32-char hex)
     b. Store in Redis: key="pw_reset:{token}" value=user_id, TTL=900 (15 min)
     c. Send email via Resend:
        Subject: "Reset your password"
        Body: link = https://app.com/reset-password?token={token}
        Include: "This link expires in 15 minutes."
  4. Return 200: { message: "If that email is registered, you'll receive a reset link." }

POST /v1/auth/reset-password
Body: { token: string, new_password: string }

Steps:
  1. Look up Redis key "pw_reset:{token}"
     → 400 "Invalid or expired reset link." if not found
  2. zxcvbn check on new_password (same strength requirement)
  3. Fetch user, update password_hash = bcrypt(new_password, cost=12)
  4. Delete Redis token key (one-time use)
  5. Invalidate ALL refresh tokens for this user:
     DELETE FROM refresh_tokens WHERE user_id = user_id
     (Security: someone reset the password = they should re-authenticate everywhere)
  6. Log in profile_change_log: field_changed='password', verified_via='email_token'
  7. Return 200: { message: "Password updated. Please log in." }

POST /v1/auth/change-password
Body: { current_password: string, new_password: string }
(Requires authenticated user)

Steps:
  1. Verify current_password via bcrypt
  2. If mfa_enabled=true: require TOTP code in body
     Body: { current_password, new_password, totp_code }
  3. zxcvbn check on new_password
  4. Update password_hash
  5. Rotate all refresh tokens (same as reset flow)
  6. Log in profile_change_log
  7. Return 200
```

---

### 1H. CSRF Protection `[NEW]`

All mutating requests (POST, PUT, PATCH, DELETE) require CSRF validation.

**How it works — Double-Submit Cookie Pattern:**

```
On successful login:
  1. Backend generates csrf_token = secrets.token_hex(32)
  2. Store in Redis: key="csrf:{user_id}" value=csrf_token, TTL=7 days
  3. Set cookie: csrf_token=<value>
     HttpOnly: FALSE  ← must be JS-readable
     Secure: true
     SameSite: Lax
     Path: /

On every mutating request:
  Frontend reads document.cookie['csrf_token']
  Sets header: X-CSRF-Token: <value>

Backend middleware (middleware/csrf.py):
  1. Skip GET, HEAD, OPTIONS requests
  2. Read csrf_token cookie from request
  3. Read X-CSRF-Token header from request
  4. If either missing: 403 "CSRF validation failed"
  5. If cookie != header: 403 "CSRF validation failed"
  6. Proceed

Axios interceptor (frontend/src/lib/axios.ts):
  import Cookies from 'js-cookie'

  axiosInstance.interceptors.request.use((config) => {
    const methods = ['post', 'put', 'patch', 'delete']
    if (methods.includes(config.method || '')) {
      const csrf = Cookies.get('csrf_token')
      if (csrf) config.headers['X-CSRF-Token'] = csrf
    }
    return config
  })

On logout: delete csrf_token cookie + Redis key
On token refresh: issue new csrf_token
```

---

### 1I. All Auth Endpoints

```
POST   /v1/auth/register
GET    /v1/auth/verify-email?token=xxx
POST   /v1/auth/login
POST   /v1/auth/login/mfa
POST   /v1/auth/logout
POST   /v1/auth/refresh
GET    /v1/auth/google/login
GET    /v1/auth/google/callback
POST   /v1/auth/mfa/setup
POST   /v1/auth/mfa/verify-setup
POST   /v1/auth/mfa/disable
POST   /v1/auth/forgot-password
POST   /v1/auth/reset-password
POST   /v1/auth/change-password
GET    /v1/auth/me
POST   /v1/auth/mfa-recovery-request   [NEW]
```

---

## Phase 2 — Database

### 2A. PostgreSQL via Neon + PgBouncer

**Neon PostgreSQL** (free tier):
- 0.5 GB storage (monitor usage — `raw_output` JSONB can grow)
- Serverless autoscaling
- Zero-config branching: `main` (prod), `dev` (dev), `staging` branches
- Same `DATABASE_URL` format — swap in RDS later with zero code changes

> [!WARNING]
> **JSONB storage at scale:** Full debate transcripts stored as JSONB in the `decisions` table are 5–10 KB each. At 1,000 decisions = 5–10 MB. At 50,000 decisions = 250–500 MB — approaching the 0.5 GB free tier limit. **v1 mitigation:** store transcripts directly in JSONB (simpler). **v2 migration path:** move full transcripts to Cloudflare R2 (free: 10 GB/month), store only a summary JSONB + R2 URL in the DB. Monitor `pg_total_relation_size('decisions')` monthly.

**PgBouncer (transaction-mode pooling):**
```
FastAPI (N workers) → PgBouncer (pool=20) → Neon PostgreSQL (max_conn=25)
```

**CRITICAL — asyncpg prepared statement fix `[NEW]`:**
```python
# db/pool.py
import asyncpg

async def create_db_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=dsn,
        statement_cache_size=0,    # ← REQUIRED for PgBouncer transaction mode
        min_size=2,
        max_size=10,
        command_timeout=30.0
    )
```
Without `statement_cache_size=0`, asyncpg sends named prepared statements that PgBouncer cannot route correctly, causing `prepared statement "..." already exists` errors under load.

---

### 2B. Upstash Redis `[NEW]`

Replace Render Redis with **Upstash Redis** (free tier):
- Persistent (survives restarts — critical for token blacklisting)
- 10,000 commands/day free
- REST API available as fallback
- Same `redis://` URL format — just update `REDIS_URL` env var

**Redis key schema:**
```
email_verify:{token}         → user_id            TTL: 86400 (24h)
pw_reset:{token}             → user_id            TTL: 900 (15 min)
mfa_temp:{token}             → user_id            TTL: 300 (5 min)
mfa_setup:{user_id}          → totp_secret        TTL: 600 (10 min)
blacklist:{jti}              → "1"                TTL: token_remaining_life
csrf:{user_id}               → csrf_token         TTL: 604800 (7 days)
otp:{user_id}                → 6-digit OTP        TTL: 300 (email change)
rate:{endpoint}:{ip}         → request_count      TTL: per-window
sse:{decision_id}            → pub/sub channel    TTL: 3600 (1h)
mfa_recovery:{email}         → "1"                TTL: 86400 (cooldown)
```

---

### 2C. Full Database Schema

**users:**
```sql
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT UNIQUE NOT NULL,
    email_verified      BOOLEAN DEFAULT FALSE,
    password_hash       TEXT,                       -- NULL for OAuth-only users
    oauth_provider      TEXT,                       -- 'google' | NULL
    oauth_id            TEXT,                       -- Google sub claim
    name                TEXT NOT NULL,
    role                TEXT DEFAULT 'user'
                        CHECK (role IN ('user', 'admin')),
    is_active           BOOLEAN DEFAULT FALSE,
    mfa_enabled         BOOLEAN DEFAULT FALSE,
    mfa_secret_enc      TEXT,                       -- AES-256 encrypted TOTP secret
    profile_picture     TEXT,                       -- URL (Google or uploaded)
    phone               TEXT UNIQUE,                        -- for WhatsApp bot integration [NEW]
    -- Financial profile
    age                 INTEGER CHECK (age >= 18 AND age <= 100),
    monthly_income      NUMERIC(12,2) CHECK (monthly_income >= 0),
    monthly_expense     NUMERIC(12,2) CHECK (monthly_expense >= 0),
    risk_tolerance      NUMERIC(4,3)
                        CHECK (risk_tolerance >= 0.0 AND risk_tolerance <= 1.0),
    investment_horizon  INTEGER CHECK (investment_horizon >= 1),
    has_emergency_fund  BOOLEAN DEFAULT FALSE,
    financial_strategy  TEXT CHECK (financial_strategy IN
                        ('conservative','moderate','aggressive', NULL)),
    goal                TEXT,                       -- Display only, not ML feature
    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ DEFAULT NULL,
    deletion_reason     TEXT
);
```

**refresh_tokens:**
```sql
CREATE TABLE refresh_tokens (
    token_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash      TEXT UNIQUE NOT NULL,           -- SHA-256 of the raw token
    jti             TEXT UNIQUE NOT NULL,           -- JWT ID (matches JWT payload)
    issued_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked         BOOLEAN DEFAULT FALSE,
    user_agent      TEXT,                           -- for "active sessions" display
    ip_address      TEXT
);
```

**mfa_backup_codes:**
```sql
CREATE TABLE mfa_backup_codes (
    code_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,                      -- bcrypt hash of 8-char code
    used        BOOLEAN DEFAULT FALSE,
    used_at     TIMESTAMPTZ
);
```

**mfa_recovery_requests:** `[NEW]`
```sql
CREATE TABLE mfa_recovery_requests (
    request_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    email           TEXT NOT NULL,
    message         TEXT,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending', 'resolved', 'rejected')),
    resolved_by     UUID REFERENCES users(user_id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);
```

**profile_change_log:**
```sql
CREATE TABLE profile_change_log (
    change_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    field_changed   TEXT NOT NULL,
    old_value_hash  TEXT,                           -- hashed, not plaintext
    changed_at      TIMESTAMPTZ DEFAULT NOW(),
    verified_via    TEXT NOT NULL,                  -- 'password' | 'totp' | 'email_code' | 'admin_action'
    changed_by      UUID REFERENCES users(user_id) -- admin user_id if admin action
);
```

**decisions:**
```sql
CREATE TABLE decisions (
    decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Pipeline status [NEW]
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','processing','complete','failed')),
    pipeline_step       TEXT,                       -- 'bias_detection'|'simulation'|'explanation'|'debate'|'audit'
    error_message       TEXT,

    -- Decision input
    symbol              TEXT NOT NULL,              -- 'HDFCBANK', 'RELIANCE', etc.
    exchange            TEXT DEFAULT 'NSE'
                        CHECK (exchange IN ('NSE', 'BSE')),
    holding_quantity    INTEGER NOT NULL CHECK (holding_quantity > 0),
    avg_buy_price       NUMERIC(12,2) NOT NULL CHECK (avg_buy_price > 0),
    current_price       NUMERIC(12,2) NOT NULL CHECK (current_price > 0),
    unrealized_pnl_pct  NUMERIC(7,4) NOT NULL,      -- e.g. -0.1832 = -18.32%
    decision_intent     TEXT NOT NULL
                        CHECK (decision_intent IN ('sell','hold','buy_more')),
    user_reasoning      TEXT,                       -- optional free text

    -- Market context (auto-populated at submission time)
    nifty_1d_change     NUMERIC(6,4),               -- e.g. -0.012 = -1.2%
    nifty_52w_return    NUMERIC(6,4),
    vix_value           NUMERIC(6,3),
    market_trend        TEXT CHECK (market_trend IN ('bull','bear','sideways', NULL)),
    sector              TEXT,                       -- auto-mapped from symbol

    -- ML Outputs
    bias_detected       TEXT CHECK (bias_detected IN
                        ('loss_aversion','herd_behavior','disposition_effect','rational', NULL)),
    bias_confidence     NUMERIC(5,4) CHECK (bias_confidence BETWEEN 0.0 AND 1.0),
    recommendation      TEXT CHECK (recommendation IN ('HOLD','SELL','BUY_MORE', NULL)),
    causal_effect       NUMERIC(7,4),               -- DoWhy ATE estimate
    opportunity_cost_inr NUMERIC(15,2),             -- median 20y difference

    -- Simulation summary (percentile curves stored separately in JSONB)
    hold_median_20y     NUMERIC(15,2),
    hold_p10_20y        NUMERIC(15,2),
    hold_p90_20y        NUMERIC(15,2),
    sell_median_20y     NUMERIC(15,2),
    sell_p10_20y        NUMERIC(15,2),
    sell_p90_20y        NUMERIC(15,2),

    -- Full JSON outputs (JSONB)
    explainer_output    JSONB,                      -- structured reasoning
    debate_transcript   JSONB,                      -- Bull/Bear/Judge full transcript
    simulation_curves   JSONB,                      -- P10/P50/P90 at each year (120 numbers)
    -- NOTE: Do NOT store raw 10,000 simulation paths here — compute on demand or discard

    -- Tax context
    holding_period_days INTEGER,
    tax_category        TEXT CHECK (tax_category IN ('STCG','LTCG', NULL)),

    -- Outcome tracking (populated later by outcome_tracker.py)
    outcome_tracked     BOOLEAN DEFAULT FALSE,
    actual_outcome_pct  NUMERIC(7,4),               -- actual return after N months
    recommendation_followed BOOLEAN,

    -- Timestamps
    submitted_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

**audit_logs:**
```sql
CREATE TABLE audit_logs (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID REFERENCES decisions(decision_id) ON DELETE SET NULL,
    user_id         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    -- user_id SET NULL on delete: preserve chain integrity, just de-identify

    event_type      TEXT NOT NULL,                  -- 'decision_created' | 'decision_completed' | 'bias_detected' | etc.
    payload_hash    TEXT NOT NULL,                  -- SHA-256 of the event payload
    previous_hash   TEXT NOT NULL,                  -- hash of previous log entry for this user
    chain_hash      TEXT NOT NULL,                  -- SHA-256(payload_hash + previous_hash)
    -- chain_hash is what the frontend AuditVerifier re-computes to verify

    payload         JSONB NOT NULL,                 -- the event data (not sensitive — bias type, recommendation, etc.)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Tamper protection: block all UPDATE and DELETE
CREATE RULE audit_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
```

**Hash chain genesis block `[NEW]`:**
```python
# audit_logger.py
def compute_genesis_hash(user_id: str, created_at: datetime) -> str:
    """
    The first audit entry for a user hashes against this genesis value.
    Ties the chain to the user's identity and account creation time.
    Verifiable independently by anyone who knows user_id + created_at.
    """
    genesis_input = f"GENESIS:{user_id}:{created_at.isoformat()}"
    return hashlib.sha256(genesis_input.encode()).hexdigest()
```

**portfolios:**
```sql
CREATE TABLE portfolios (
    holding_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    exchange        TEXT DEFAULT 'NSE',
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    avg_buy_price   NUMERIC(12,2) NOT NULL,
    buy_date        DATE,                           -- for STCG/LTCG calculation
    asset_type      TEXT DEFAULT 'equity'
                    CHECK (asset_type IN ('equity','mf','gold','crypto')),
    kite_synced     BOOLEAN DEFAULT FALSE,          -- true if fetched from Kite
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**sip_registrations:**
```sql
CREATE TABLE sip_registrations (
    sip_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    fund_name       TEXT NOT NULL,
    isin            TEXT,
    monthly_amount  NUMERIC(10,2) NOT NULL,
    deduction_date  INTEGER CHECK (deduction_date BETWEEN 1 AND 28),
    is_active       BOOLEAN DEFAULT TRUE,
    paused_at       TIMESTAMPTZ,
    pause_reason    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**kite_tokens:** `[NEW]`
```sql
CREATE TABLE kite_tokens (
    user_id             UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    access_token        TEXT,                       -- encrypted with Fernet
    access_token_date   DATE,                       -- date token was issued (IST)
    request_token       TEXT,                       -- encrypted, used for re-auth
    connected_at        TIMESTAMPTZ DEFAULT NOW(),
    last_synced_at      TIMESTAMPTZ
);
```

**bias_profiles:** `[NEW]`
```sql
CREATE TABLE bias_profiles (
    user_id             UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    disposition_score   NUMERIC(4,3) DEFAULT 0.0 CHECK (disposition_score BETWEEN 0.0 AND 1.0),
    herd_score          NUMERIC(4,3) DEFAULT 0.0 CHECK (herd_score BETWEEN 0.0 AND 1.0),
    loss_aversion_score NUMERIC(4,3) DEFAULT 0.0 CHECK (loss_aversion_score BETWEEN 0.0 AND 1.0),
    rational_score      NUMERIC(4,3) DEFAULT 0.0 CHECK (rational_score BETWEEN 0.0 AND 1.0),
    total_decisions     INTEGER DEFAULT 0 CHECK (total_decisions >= 0),
    last_updated        TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

**market_cache:** `[NEW]`
```sql
CREATE TABLE market_cache (
    cache_key           TEXT PRIMARY KEY,           -- e.g., 'NSE_INDEX_SNAPSHOT'
    market_return       NUMERIC(7,4),               -- return metric
    market_volatility   NUMERIC(6,3),               -- VIX or custom volatility metric
    crowd_ratio         NUMERIC(5,4),               -- crowd behavior metric
    fetched_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 2D. Performance Indexes

```sql
-- Core lookups
CREATE INDEX idx_decisions_user_id ON decisions(user_id);
CREATE INDEX idx_decisions_status ON decisions(status) WHERE status != 'complete';
CREATE INDEX idx_decisions_created_at ON decisions(created_at DESC);
CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_decision_id ON audit_logs(decision_id);
CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_sip_user_id ON sip_registrations(user_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted ON users(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_bias_profiles_user_id ON bias_profiles(user_id);
CREATE INDEX idx_market_cache_key ON market_cache(cache_key);
```

---

### 2E. Row-Level Security (RLS)

RLS enforces data isolation at the database level — independently of application code.

```sql
-- Enable RLS on all user-owned tables
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE sip_registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_change_log ENABLE ROW LEVEL SECURITY;

-- Application role (used by FastAPI)
CREATE ROLE app_user;

-- RLS policies: user can only touch their own rows
CREATE POLICY decisions_isolation ON decisions
    FOR ALL TO app_user
    USING (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY audit_isolation ON audit_logs
    FOR ALL TO app_user
    USING (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY portfolios_isolation ON portfolios
    FOR ALL TO app_user
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- Set the context at start of each request
-- In FastAPI: await conn.execute("SET app.current_user_id = $1", str(user.user_id))
```

---

### 2F. Admin Aggregate VIEW

Admins query this view only — no access to raw tables.

```sql
CREATE VIEW admin_stats_view AS
SELECT
    DATE_TRUNC('day', d.created_at)     AS day,
    COUNT(d.decision_id)                AS total_decisions,
    COUNT(CASE WHEN d.status='complete' THEN 1 END) AS completed,
    COUNT(CASE WHEN d.status='failed' THEN 1 END)   AS failed,
    COUNT(CASE WHEN d.bias_detected='loss_aversion' THEN 1 END)     AS loss_aversion_count,
    COUNT(CASE WHEN d.bias_detected='herd_behavior' THEN 1 END)     AS herd_behavior_count,
    COUNT(CASE WHEN d.bias_detected='disposition_effect' THEN 1 END) AS disposition_effect_count,
    COUNT(CASE WHEN d.bias_detected='rational' THEN 1 END)          AS rational_count,
    AVG(d.bias_confidence)              AS avg_confidence,
    COUNT(DISTINCT d.user_id)           AS active_users
    -- NOTE: No user_id, no personal data, no financial figures
FROM decisions d
WHERE d.created_at > NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', d.created_at)
ORDER BY day DESC;
```

---

### 2G. Alembic Migration Setup

```
backend/db/
├── pool.py              # asyncpg pool factory (statement_cache_size=0)
├── schema.sql           # reference schema (not used by Alembic — for documentation)
└── migrations/
    ├── env.py           # Alembic env config — points to DATABASE_URL
    ├── alembic.ini
    └── versions/
        ├── 0001_create_users.py
        ├── 0002_create_auth_tables.py
        ├── 0003_create_decisions.py
        ├── 0004_create_audit_logs.py
        ├── 0005_create_portfolios.py
        ├── 0006_create_sip_kite.py
        └── 0007_create_rls_policies.py

# Run on deploy:
alembic upgrade head
```

---

## Phase 3 — Backend Restructure

### 3A. Project Layout

```
backend/
├── main.py                         # FastAPI app factory, middleware registration, lifespan
├── config.py                       # Pydantic Settings — reads .env
├── auth/
│   ├── jwt_handler.py
│   ├── mfa_handler.py
│   ├── oauth_handler.py
│   ├── password.py
│   ├── csrf.py                     # [NEW] double-submit CSRF middleware
│   ├── dependencies.py             # get_current_user, require_admin
│   └── routes.py
├── api/
│   ├── v1/
│   │   ├── __init__.py             # APIRouter prefix="/v1"
│   │   ├── users.py                # /v1/users/me, /v1/users/me/export
│   │   ├── decisions.py            # /v1/decisions/* (uses current user from JWT)
│   │   ├── simulate.py             # /v1/simulate/*
│   │   ├── audit.py                # /v1/audit/*
│   │   ├── market.py               # /v1/market/* (public)
│   │   ├── portfolio.py            # /v1/portfolio/*
│   │   ├── sip.py                  # /v1/sip/*
│   │   └── admin.py                # /v1/admin/* (aggregate only)
│   └── stream.py                   # [NEW] SSE streaming endpoint
├── core/
│   ├── bias_detector.py            # XGBoost inference
│   ├── causal_inference.py         # DoWhy causal effect
│   ├── simulator.py                # Monte Carlo engine
│   ├── explainer.py                # Structured reasoning JSON builder
│   ├── debate_engine.py            # AutoGen + Claude Sonnet
│   ├── audit_logger.py             # SHA-256 hash chain
│   └── pipeline.py                 # [NEW] orchestrates full analysis pipeline
├── db/
│   ├── pool.py
│   ├── schema.sql
│   └── migrations/
├── models/
│   ├── user.py
│   ├── decision.py
│   ├── simulation.py
│   └── audit.py
├── services/
│   ├── market_data.py
│   ├── email_service.py
│   ├── tax_engine.py
│   ├── sip_tracker.py
│   ├── kite_integration.py
│   └── outcome_tracker.py
└── middleware/
    ├── rate_limiter.py             # slowapi + Redis
    ├── csrf.py                     # [NEW] CSRF validation
    ├── security_headers.py         # [NEW] CSP + HSTS + X-Frame-Options
    ├── cors.py
    └── request_logger.py           # [NEW] structlog per-request logging
```

---

### 3B. API Versioning `[NEW]`

All routes are under `/v1/`. The frontend Axios instance targets `/api/v1`.

```python
# backend/api/v1/__init__.py
from fastapi import APIRouter
from .users import router as users_router
from .decisions import router as decisions_router
# ... etc

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(users_router,     prefix="/users",     tags=["Users"])
v1_router.include_router(decisions_router, prefix="/decisions", tags=["Decisions"])
v1_router.include_router(simulate_router,  prefix="/simulate",  tags=["Simulation"])
v1_router.include_router(audit_router,     prefix="/audit",     tags=["Audit"])
v1_router.include_router(market_router,    prefix="/market",    tags=["Market"])
v1_router.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
v1_router.include_router(admin_router,     prefix="/admin",     tags=["Admin"])

# backend/main.py
app.include_router(v1_router)
# OpenAPI docs at /api/v1/docs (only enabled in non-production)
```

---

### 3C. Ownership Pattern `[REVISED]`

Use JWT subject directly — no user_id in URL path.

```python
# dependencies.py
from fastapi import Depends, HTTPException
from .jwt_handler import verify_token

async def get_current_user(request: Request, db=Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = verify_token(token)              # raises on invalid/expired
    # Check Redis blacklist
    if await redis.exists(f"blacklist:{payload['jti']}"):
        raise HTTPException(401, "Token revoked")
    user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", payload["sub"])
    if not user or not user["is_active"]:
        raise HTTPException(401, "Account not active")
    if user["deleted_at"] is not None:
        raise HTTPException(403, "Account is scheduled for deletion")
    # Set RLS context
    await db.execute("SET LOCAL app.current_user_id = $1", str(user["user_id"]))
    return User(**user)

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user

# USAGE — clean ownership, no path param:
@router.get("/decisions/my")
async def get_my_decisions(user: User = Depends(get_current_user), db=Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM decisions WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50",
        user.user_id
    )
    return rows
# RLS also enforces this independently at DB level — double protection
```

---

### 3D. Error Handling Strategy `[NEW]`

**Unified error response shape:**
```json
{
  "error": "WEAK_PASSWORD",
  "message": "Password is too weak. Try adding numbers or symbols.",
  "detail": { "score": 2, "suggestions": ["Add a digit", "Add a symbol"] },
  "request_id": "abc123"
}
```

**Global exception handlers:**
```python
# main.py
from fastapi import Request
from fastapi.responses import JSONResponse
import sentry_sdk

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR",
            "message": str(exc.detail),
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    sentry_sdk.capture_exception(exc)
    logger.error("Unhandled exception", exc_info=exc, request_id=request.state.request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Our team has been notified.",
            "request_id": request.state.request_id
        }
    )
```

**External service failure handling:**
```python
# Pattern for all external calls (Kite, Claude API, market data, yfinance)

class ServiceUnavailableError(Exception):
    def __init__(self, service: str, detail: str = ""):
        self.service = service
        self.detail = detail

# market_data.py
async def get_current_price(symbol: str) -> float:
    try:
        return await _fetch_from_nsepy(symbol)
    except Exception as e:
        logger.warning("NSEPy failed, trying fallback", symbol=symbol, error=str(e))
        try:
            return await _fetch_from_yfinance(symbol)
        except Exception as e2:
            logger.error("All market data sources failed", symbol=symbol)
            raise ServiceUnavailableError("market_data", f"Cannot fetch price for {symbol}")

# In the API layer, catch and return appropriate 503
@app.exception_handler(ServiceUnavailableError)
async def service_unavailable_handler(request, exc):
    return JSONResponse(503, {
        "error": "SERVICE_UNAVAILABLE",
        "message": f"{exc.service} is currently unavailable. Please try again.",
        "service": exc.service
    })
```

---

### 3E. Observability `[NEW]`

**Sentry (error tracking):**
```python
# main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,        # set in .env, empty string = disabled (dev)
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,         # 10% of requests for performance tracing
    environment=settings.ENV,       # "production" | "staging" | "development"
    send_default_pii=False          # never send PII to Sentry
)
```

**Sentry Frontend (React SDK Setup):**
```typescript
// main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import App from "./App";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration(),
    ],
    tracesSampleRate: 0.1,         // Capture 10% of transactions
    replaysSessionSampleRate: 0.1, // Sample 10% of regular sessions
    replaysOnErrorSampleRate: 1.0, // Always sample when errors occur
    environment: import.meta.env.VITE_ENV || "development",
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

**structlog (structured JSON logging):**
```python
# config.py (logging setup)
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory()
)

# Usage in any module:
logger = structlog.get_logger(__name__)
logger.info("decision_submitted", decision_id=str(d_id), user_id=str(user_id), symbol=symbol)
logger.error("bias_detection_failed", decision_id=str(d_id), error=str(e))
```

**Per-request logging middleware:**
```python
# middleware/request_logger.py
import uuid, time, structlog

logger = structlog.get_logger()

@app.middleware("http")
async def request_logger_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
        request_id=request_id
    )
    response.headers["X-Request-ID"] = request_id
    return response
```

---

### 3F. Background Job Queue — SSE Streaming `[NEW]`

The full AI analysis pipeline is too slow for a synchronous HTTP response. This is the solution.

**Flow:**
```
1. POST /v1/decisions/submit
   → Validate input
   → Insert decisions row (status='pending')
   → Add BackgroundTask: run_analysis_pipeline(decision_id, user_id)
   → Return 202: { decision_id: "uuid", status: "pending" }

2. Frontend receives decision_id
   → Opens SSE connection: GET /v1/decisions/{id}/stream
   → Displays progress UI (animated steps)

3. BackgroundTask runs the pipeline:
   a. Update status='processing', pipeline_step='bias_detection'
   b. Publish to Redis: PUBLISH sse:{decision_id} '{"step":"bias_detection","status":"running"}'
   c. Run bias_detector → update decisions row
   d. Publish: '{"step":"bias_detection","status":"done","bias":"loss_aversion","confidence":0.87}'
   e. Run simulator → update decisions row
   f. Publish: '{"step":"simulation","status":"done"}'
   g. Run causal_inference → update explainer_output
   h. Publish: '{"step":"explanation","status":"done"}'
   i. Run debate_engine (slowest step — ~10-20s) → update debate_transcript
   j. Publish: '{"step":"debate","status":"done"}'
   k. Run audit_logger → update audit_logs table
   l. Publish: '{"step":"audit","status":"done"}'
   m. Update status='complete', completed_at=NOW()
   n. Publish: '{"step":"complete","decision_id":"uuid"}'

4. SSE endpoint subscribes to Redis channel and forwards events
5. Frontend receives events, animates step-by-step progress
6. On "complete": React Query refetches GET /v1/decisions/{id}/result
```

**SSE endpoint:**
```python
# api/stream.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio, json

router = APIRouter()

@router.get("/decisions/{decision_id}/stream")
async def stream_decision(
    decision_id: str,
    user: User = Depends(get_current_user)
):
    # Verify this decision belongs to this user
    row = await db.fetchrow(
        "SELECT user_id, status FROM decisions WHERE decision_id=$1", decision_id
    )
    if not row or str(row["user_id"]) != str(user.user_id):
        raise HTTPException(404, "Decision not found")

    # If already complete, return final state immediately
    if row["status"] == "complete":
        async def immediate():
            yield f"data: {json.dumps({'step':'complete','decision_id':decision_id})}\n\n"
        return StreamingResponse(immediate(), media_type="text/event-stream")

    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"sse:{decision_id}")
        try:
            timeout = 120  # 2 minutes max
            start = asyncio.get_event_loop().time()
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                    data = json.loads(message["data"])
                    if data.get("step") == "complete":
                        break
                if asyncio.get_event_loop().time() - start > timeout:
                    yield f"data: {json.dumps({'step':'timeout'})}\n\n"
                    break
        finally:
            await pubsub.unsubscribe(f"sse:{decision_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Pipeline orchestrator:**
```python
# core/pipeline.py
import asyncio, json
import structlog

logger = structlog.get_logger()

async def run_analysis_pipeline(decision_id: str, user_id: str):
    """
    Runs as a FastAPI BackgroundTask.
    Publishes SSE events to Redis at each step.
    """
    try:
        await _update_status(decision_id, "processing", "bias_detection")
        await _publish(decision_id, {"step": "bias_detection", "status": "running"})

        # Step 1: Bias Detection
        decision = await db.fetchrow("SELECT * FROM decisions WHERE decision_id=$1", decision_id)
        features = build_features(decision)
        bias, confidence = bias_detector.predict(features)
        await db.execute(
            "UPDATE decisions SET bias_detected=$1, bias_confidence=$2, pipeline_step=$3 WHERE decision_id=$4",
            bias, confidence, "simulation", decision_id
        )
        await _publish(decision_id, {"step": "bias_detection", "status": "done",
                                     "bias": bias, "confidence": confidence})

        # Step 2: Monte Carlo Simulation
        simulation = run_simulation(decision, user_profile=await get_user_profile(user_id))
        await db.execute(
            "UPDATE decisions SET hold_median_20y=$1, ... , simulation_curves=$2, pipeline_step=$3 WHERE decision_id=$4",
            simulation.hold_median, json.dumps(simulation.curves), "explanation", decision_id
        )
        await _publish(decision_id, {"step": "simulation", "status": "done"})

        # Step 3: Causal Inference + Explainer
        causal_effect = await run_causal_inference(features, bias)
        explanation = build_explanation(decision, bias, confidence, simulation, causal_effect)
        await db.execute(
            "UPDATE decisions SET causal_effect=$1, opportunity_cost_inr=$2, explainer_output=$3, pipeline_step=$4 WHERE decision_id=$5",
            causal_effect, simulation.opportunity_cost, json.dumps(explanation), "debate", decision_id
        )
        await _publish(decision_id, {"step": "explanation", "status": "done"})

        # Step 4: AI Debate (slowest)
        debate = await run_debate_engine(decision, bias, explanation)
        recommendation = debate["verdict"]
        await db.execute(
            "UPDATE decisions SET debate_transcript=$1, recommendation=$2, pipeline_step=$3 WHERE decision_id=$4",
            json.dumps(debate), recommendation, "audit", decision_id
        )
        await _publish(decision_id, {"step": "debate", "status": "done"})

        # Step 5: Audit Log
        await audit_logger.log_decision_complete(decision_id, user_id, bias, recommendation)
        await _update_status(decision_id, "complete", None)
        await db.execute("UPDATE decisions SET completed_at=NOW() WHERE decision_id=$1", decision_id)
        await _publish(decision_id, {"step": "complete", "decision_id": decision_id})

        logger.info("pipeline_complete", decision_id=decision_id, bias=bias, recommendation=recommendation)

    except Exception as e:
        logger.error("pipeline_failed", decision_id=decision_id, error=str(e))
        await db.execute(
            "UPDATE decisions SET status='failed', error_message=$1 WHERE decision_id=$2",
            str(e), decision_id
        )
        await _publish(decision_id, {"step": "failed", "error": str(e)})
        sentry_sdk.capture_exception(e)
```

---

### 3G. Security Headers + CSP `[NEW]`

```python
# middleware/security_headers.py
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://lh3.googleusercontent.com; "
        "connect-src 'self' https://api.anthropic.com; "
        "frame-ancestors 'none';"
    )
    return response
```

---

### 3H. Rate Limits

```
/v1/auth/login             5 req/min per IP         (brute force)
/v1/auth/register          3 req/hour per IP        (spam prevention)
/v1/auth/forgot-password   3 req/hour per IP        (enumeration prevention)
/v1/decisions/submit       10 req/min per user      (AI call cost)
/v1/simulate               5 req/min per user       (compute cost)
/v1/market/context         60 req/min per user      (cached anyway)
/v1/admin/*                20 req/min per admin     (admin ops)
```

---

## Phase 4 — React Frontend

### 4A. Tech Stack

```
React 18 + Vite 5
Tailwind CSS v3
shadcn/ui (Radix UI primitives — accessible, unstyled base)
Lucide React (icons)
Zustand (auth state, theme, market ribbon)
TanStack Query v5 (API caching, background refresh, optimistic updates)
React Router v6 (nested routes, protected routes, lazy loading)
React Hook Form + Zod (form validation)
Recharts (wealth trajectory, bias history charts)
Framer Motion (page transitions, card animations)
Axios (HTTP client with interceptors)
js-cookie (CSRF cookie reading)
qrcode.react (MFA QR code rendering)
react-hot-toast (toasts)
EventSource (native browser SSE for pipeline streaming)
```

---

### 4B. Design System — Finalized (Decision Intelligence)

> This design system is finalized. Do not deviate from these tokens.

**Philosophy:** "Premium Bento-Grid Minimalism." Calm, authoritative, data-forward. Not a trading app. No flashing red/green prices. No candlestick charts.

**Color Tokens — Dark Mode (default):**
```css
colors: {
  'bg-base':        '#08080F',   /* page bg — deepest layer */
  'bg-surface':     '#13131A',   /* cards */
  'bg-container':   '#1F1F27',   /* card hover, nested panels */
  'bg-elevated':    '#2A2931',   /* modals, popovers */

  'border-subtle':  '#464554',
  'border-focus':   '#6366F1',

  'text-primary':   '#E4E1EC',
  'text-secondary': '#C7C4D7',
  'text-muted':     '#908FA0',

  'indigo':         '#6366F1',   /* primary CTA, active nav, focus rings */
  'indigo-dim':     '#C0C1FF',   /* indigo text on dark bg */

  /* Semantic — data only, not UI chrome */
  'emerald':        '#10B981',   /* HOLD, rational, positive */
  'rose':           '#F43F5E',   /* bias alerts, SELL scenario */
  'amber':          '#F59E0B',   /* herd behavior, pause warnings */
}
```

**Color Tokens — Light Mode:**
```css
/* Applied when .light class on <html> */
colors: {
  'bg-base':        '#F8F8FC',
  'bg-surface':     '#FFFFFF',
  'bg-container':   '#F3F3F8',
  'border-subtle':  '#E5E7EB',
  'text-primary':   '#111827',
  'text-secondary': '#374151',
  'text-muted':     '#6B7280',
  /* indigo, emerald, rose, amber — same as dark */
}
```

**Typography:**
```
Inter 700, 48px, -0.02em    → display-lg (hero numbers, ₹ values)
Inter 600, 24px, -0.01em    → headline-md (card titles)
Inter 400, 16px, normal     → body-base
Inter 700, 11px, +0.1em UPPER → label-caps (card labels)
JetBrains Mono 500, 20px    → data-lg (financial values, percentages)
JetBrains Mono 400, 12px    → data-sm (tickers, hash strings)
```

**Shape & Spacing:**
```
card radius:    16px (rounded-2xl)
button radius:  8px  (rounded-lg)
badge radius:   9999px (rounded-full)
card padding:   24px
grid gutter:    24px
page margin:    32px (desktop) / 16px (mobile)
```

**Anti-patterns (NEVER implement):**
- ❌ Red/green price tickers anywhere
- ❌ Candlestick charts
- ❌ Dense tables with more than 6 columns
- ❌ Neon glows or heavy glassmorphism (opacity < 50%)
- ❌ Sidebar too narrow to read labels
- ❌ More than 2 font weights on one card

---

### 4C. FOUC Fix (Theme Flash Prevention) `[NEW]`

Zustand reads `localStorage` after React hydrates — causing a flash of the wrong theme on initial load.

```html
<!-- index.html — BEFORE the React bundle loads -->
<head>
  ...
  <script>
    // Runs synchronously before React mounts — no FOUC
    ;(function() {
      var theme = localStorage.getItem('finai_theme') || 'dark'
      document.documentElement.classList.add(theme)
    })()
  </script>
</head>
```

```ts
// store/theme.ts — Zustand store
const useThemeStore = create<ThemeStore>((set) => ({
  theme: (localStorage.getItem('finai_theme') || 'dark') as 'dark' | 'light',
  toggle: () => set((s) => {
    const next = s.theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.remove('dark', 'light')
    document.documentElement.classList.add(next)
    localStorage.setItem('finai_theme', next)
    return { theme: next }
  }),
}))
```

Add to `index.css`: `html { transition: background-color 200ms, color 200ms; }`

---

### 4D. Axios Setup + CSRF Interceptor `[NEW]`

```ts
// lib/axios.ts
import axios from 'axios'
import Cookies from 'js-cookie'

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,   // send httpOnly cookies
  timeout: 30000,
})

// CSRF: attach token on every mutating request
api.interceptors.request.use((config) => {
  const mutating = ['post', 'put', 'patch', 'delete']
  if (mutating.includes(config.method || '')) {
    const csrf = Cookies.get('csrf_token')
    if (csrf) config.headers['X-CSRF-Token'] = csrf
  }
  return config
})

// Token refresh: on 401, attempt refresh then retry
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        await api.post('/auth/refresh')
        return api(original)
      } catch {
        // Refresh failed — redirect to login
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
```

---

### 4E. Landing Page Spec `[NEW]`

The landing page is public (`/`) and the first thing users see. It must convey the product value, establish research credibility, and funnel users to register.

**Sections:**

**1. Hero (full viewport height)**
```
Background: bg-base with subtle radial gradient in indigo (very dim)
Content: centered, max-w-3xl

Headline (display-lg, text-primary):
  "Stop Trading on Emotion."
  "Start Deciding with Evidence."

Subheadline (body-base, text-secondary):
  "AI-powered behavioral bias detection, causal analysis, and 20-year
   Monte Carlo simulation — built for Indian retail investors."

CTA buttons (row):
  Primary: "Get Early Access →" (indigo bg, /register)
  Secondary: "See How It Works" (outline, scrolls to #how-it-works)

Trust signal (label-caps, text-muted, centered below buttons):
  XGBoost ML  ·  85.81% Macro F1  ·  10,000 Monte Carlo Paths  ·  SHA-256 Audit Trail
```

**2. Problem Statement**
```
Section title: "Why Most Investors Lose Money"
Three cards (bento-grid, 3-col):
  🧠 Loss Aversion    — "You feel selling losses twice as strongly as gains. So you panic-sell."
  🐑 Herd Behavior    — "You follow the crowd. The crowd is always late."
  📈 Disposition Effect — "You sell winners early and hold losers too long."
Each card: icon, title, 2-line description. Rose accent on the icon.
```

**3. How It Works (id="how-it-works")**
```
Three-step horizontal flow with arrows between:
  Step 1: "Enter Your Decision"
    "Tell us what you're about to do — sell, hold, or buy more."
    Icon: clipboard

  Step 2: "We Detect the Bias"
    "Our XGBoost model identifies which cognitive bias is driving your decision."
    Icon: brain / scan

  Step 3: "Get Evidence-Backed Guidance"
    "See the 20-year ₹ cost of your bias, an AI debate, and a clear recommendation."
    Icon: check/shield
```

**4. Feature Showcase**
```
Alternating left/right layout (3 features):

Feature A — Bias Detection (mockup: bias card)
  "Know If You're Trading Fear or Data"
  "Our machine learning model was trained to detect four behavioral biases:
   Loss Aversion, Herd Behavior, Disposition Effect, and Rational.
   85.81% Macro F1 on held-out test data."

Feature B — 20-Year Monte Carlo (mockup: simulation chart)
  "See the Real ₹ Cost of Each Mistake"
  "10,000 simulated wealth paths show you the median, best, and worst-case
   outcome of holding vs. selling over 20 years. The gap is usually larger
   than you expect."

Feature C — AI Debate (mockup: debate transcript panel)
  "Bull, Bear, and Judge Reason Through Your Decision"
  "Three AI agents debate every decision. The Bull argues for holding.
   The Bear argues for selling. The Judge delivers the verdict.
   Full transcript saved and cryptographically hashed."
```

**5. Research Credibility**
```
Title: "Built on Peer-Reviewed Behavioral Finance Research"
Four GAP badges:
  ✅ GAP 1: Bias Detection ML (XGBoost, 85.81% F1)
  ✅ GAP 2: Long-Horizon Cost Quantification (Monte Carlo)
  🔲 GAP 3: Causal AI Explanation (DoWhy + AutoGen)
  🔲 GAP 4: Tamper-Evident Audit Trail (SHA-256 chain)
"Academic project + real product. Both held to the same standard."
```

**6. CTA Footer Banner**
```
"Ready to make your first rational decision?"
CTA: "Create Free Account →" (/register)
```

**7. Footer**
```
Logo | Privacy Policy | About | GitHub (if public) | Contact
```

---

### 4F. Dashboard Layout — Home Screen

The finalized bento grid (carried over from v1, no changes):

```
┌─────────────────────────────────┬──────────────────────┐
│  PORTFOLIO SNAPSHOT              │  ACTIVE BIAS ALERT   │
│  ₹12,47,832 (data-lg, mono)      │  Loss Aversion       │
│  ▁▂▃▅▄▆▇ (indigo sparkline)      │  87% confidence      │
│  HOLD RECOMMENDED ● badge        │  bar (rose)          │
│  Risk: 3.4  Horizon: 82%         │                      │
├─────────────────────────────────┼──────────────────────┤
│  LAST DECISION                   │  MARKET PULSE        │
│  HDFC Bank · 140 shares          │  NIFTY 50            │
│  ₹1,642 avg · -18.2% unrealized  │  22,147.90 ▲0.43%    │
│  [View Analysis →] (indigo link) │  SENSEX              │
│                                  │  73,018.25 ▲0.38%    │
│                                  │  India VIX           │
│                                  │  14.82 ▼ -2.1%       │
│                                  │  Updated 2 min ago   │
└─────────────────────────────────┴──────────────────────┘
```

**Notes:**
- Portfolio Snapshot: ~65% width (most important card)
- Market Pulse: uses text-muted for VIX — lower VIX = calmer market, NOT a bad signal
- NIFTY/SENSEX changes use emerald (positive) / rose (negative) text only — no backgrounds
- "Decisions This Month" removed — not actionable

---

### 4G. Mobile Responsiveness Strategy `[NEW]`

The bento grid must degrade gracefully on mobile (< 640px).

```tsx
// All bento grids use responsive grid:
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-6">

// Dashboard home cards:
<Card className="sm:col-span-1 lg:col-span-7">  {/* Portfolio Snapshot */}
<Card className="sm:col-span-1 lg:col-span-5">  {/* Bias Alert */}
<Card className="sm:col-span-1 lg:col-span-7">  {/* Last Decision */}
<Card className="sm:col-span-1 lg:col-span-5">  {/* Market Pulse */}
```

**Mobile-specific rules:**
- Navbar: desktop = full links. Mobile = hamburger menu → slide-in drawer.
- Market ribbon: desktop = scrolling 8-ticker ribbon. Mobile = static 3-ticker display (NIFTY, SENSEX, VIX only).
- Charts: full-width on mobile, `height={200}` instead of `height={300}`.
- Decision form wizard: step indicators stack vertically below 480px.
- Audit hash display: truncated with copy button on mobile (full hash on desktop).
- Tables (portfolio, history): horizontal scroll on mobile (`overflow-x-auto`).
- Page margin: `px-4 sm:px-6 lg:px-8`.

---

### 4H. Page Map

```
/                           Landing page (public)
/login                      Email/password login + MFA step
/login/mfa                  TOTP input step
/register                   Registration form (multi-step)
/forgot-password            Password reset request
/reset-password?token=xxx   New password form
/auth/google/callback       OAuth redirect handler
/auth/verify-email?token=xx Email verification

/dashboard                  Home — bento grid summary
/dashboard/decision         Decision wizard + SSE results panel
/dashboard/decision/:id     View specific past decision result
/dashboard/simulation       HOLD vs SELL chart + settings
/dashboard/portfolio        Holdings table + live P&L
/dashboard/history          Past decisions + bias trend chart
/dashboard/audit            Audit log viewer + hash verifier
/dashboard/profile          Profile viewer + edit flows
/dashboard/settings         MFA setup, password, notifications, account deletion

/admin                      Admin home — aggregate stats
/admin/users                User list (activate/deactivate/search/MFA reset)
/admin/mfa-recovery         Pending MFA recovery requests
```

---

### 4I. Profile Management — Re-verification Flow

```
Sensitive fields (require verification modal):
  Email           → Current password + OTP to old email
  Password        → Current password + TOTP (if MFA on)
  Monthly income  → Current password
  Emergency fund  → Current password
  MFA disable     → Current password + current TOTP
  Account delete  → Current password + TOTP + type "DELETE"
  Kite connect    → Current password

Non-sensitive fields (no modal — save immediately):
  Name, goal, financial_strategy, profile_picture, notifications, theme

Verification modal UX:
  1. User clicks "Edit" on sensitive field
  2. Modal appears with lock icon: "For your security, verify your identity"
  3. Password field (always) + TOTP field (if mfa_enabled=true)
  4. On success: field becomes editable
  5. Sensitive edit window: 5 minutes (stored as timestamp in React state)
     User doesn't re-verify every field within this window
  6. Window expiry: field goes back to locked state
  7. On save: toast "Changes saved" + logged in profile_change_log
```

---

### 4J. Account Deletion Flow

```
1. Settings → "Delete Account" → warning screen (red border card)
   "This action is permanent. All your data will be deleted in 30 days."
   List of what will be deleted: profile, decisions, portfolio, SIPs, audit logs
   "Changed your mind? You can cancel within 30 days by logging back in."

2. User types "DELETE" in confirmation input (exact match)

3. Re-verification modal: password + TOTP

4. POST /v1/users/me/delete → backend:
   a. Set deleted_at = NOW(), deletion_reason = "user_request"
   b. Anonymize email: email = "deleted_{uuid}@deleted.finai"
   c. Clear: password_hash, mfa_secret_enc, oauth_id, profile_picture
   d. Send confirmation email to ORIGINAL email (before anonymizing)
      "Your account is scheduled for deletion on {date}."
   e. Clear all auth cookies
   f. Return 200

5. Frontend redirects to / with query param: ?account_deleted=1
   Landing page shows: "Account deletion scheduled. We're sorry to see you go."

6. 30-day grace: user logs in → modal:
   "Your account is scheduled for deletion on {date}."
   "Cancel deletion?" → POST /v1/users/me/cancel-deletion

7. Hard delete cron (nightly):
   SELECT * FROM users WHERE deleted_at < NOW() - INTERVAL '30 days'
   For each: delete all rows in all tables, then delete user row
   Audit logs: user_id SET NULL (FK already defined that way)
   Log to admin: "Hard deleted N accounts"
```

---

### 4K. Protected Routes

```tsx
// components/ProtectedRoute.tsx
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'

interface ProtectedRouteProps {
  children: React.ReactNode
  requireRole?: 'user' | 'admin'
}

export function ProtectedRoute({ children, requireRole = 'user' }: ProtectedRouteProps) {
  const { user, isLoading } = useAuthStore()
  const location = useLocation()

  if (isLoading) return <FullScreenSpinner />

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requireRole === 'admin' && user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

// App.tsx routes
<Route path="/dashboard/*" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
  <Route index element={<DashboardHome />} />
  <Route path="decision" element={<DecisionPage />} />
  <Route path="decision/:id" element={<DecisionResultPage />} />
  <Route path="simulation" element={<SimulationPage />} />
  <Route path="portfolio" element={<PortfolioPage />} />
  <Route path="history" element={<HistoryPage />} />
  <Route path="audit" element={<AuditPage />} />
  <Route path="profile" element={<ProfilePage />} />
  <Route path="settings" element={<SettingsPage />} />
</Route>
<Route path="/admin/*" element={<ProtectedRoute requireRole="admin"><AdminLayout /></ProtectedRoute>}>
  <Route index element={<AdminHome />} />
  <Route path="users" element={<AdminUsers />} />
  <Route path="mfa-recovery" element={<AdminMfaRecovery />} />
</Route>
```

---

### 4L. Key UI Components

**Navbar:**
Dark, sticky top. Left: Logo (wordmark). Center: live market ribbon (NIFTY / SENSEX / VIX, scrolling on desktop). Right: theme toggle + user avatar dropdown (profile, settings, logout).

**Decision Wizard (3 steps):**
Step 1 — Market Context: auto-filled (NIFTY 1D change, VIX). User can adjust if needed.
Step 2 — Your Position: symbol (autocomplete NSE symbols), quantity, avg buy price (auto-computes current price + P&L%), decision intent (sell / hold / buy more), optional reasoning text.
Step 3 — Review & Submit: summary card, disclaimer, "Analyze Decision →" button.

**SSE Progress Panel (shown after submit):**
```
Analyzing your decision...
  ✅ Bias Detection      (0.8s)
  ✅ Monte Carlo Simulation  (2.1s)
  ✅ Causal Explanation  (3.4s)
  🔄 AI Debate           (running...)  ← animated pulse
  ⬜ Audit Logging
```

**Results Panel (shown on pipeline complete):**
- Bias alert card: color-coded header (rose = loss aversion, amber = herd, purple = disposition, emerald = rational). Large bias name + confidence ring.
- Opportunity cost: large display-lg typography, "₹29,292 over 20 years"
- Dual wealth chart: HOLD (emerald) vs SELL (rose) lines with P10/P50/P90 bands. X-axis: years 0–20. Y-axis: ₹ wealth.
- Recommendation badge: HOLD or SELL — large, color-coded, centered.
- Debate panel: collapsible. Bull / Bear / Judge cards, each with their argument text.
- Audit section at bottom: decision hash + "Verify" button.

**AuditVerifier Component:**
```tsx
// Recomputes the SHA-256 chain hash client-side
// User can independently verify their decision was not tampered with
function AuditVerifier({ logEntry }) {
  const recomputed = sha256(logEntry.payload_hash + logEntry.previous_hash)
  const isValid = recomputed === logEntry.chain_hash
  return (
    <div className="flex items-center gap-2">
      {isValid
        ? <Badge variant="emerald">✓ Hash verified</Badge>
        : <Badge variant="rose">⚠ Chain broken</Badge>}
      <code className="data-sm text-muted truncate">{logEntry.chain_hash}</code>
    </div>
  )
}
```

---

## Phase 5 — ML Components

### 5A. GAP 1 — Bias Detector (`core/bias_detector.py`)

**Model:** XGBoost classifier v3, 4-class (loss_aversion, herd_behavior, disposition_effect, rational)
**Performance:** 85.81% Macro F1 on held-out test set
**Training data:** Synthetic dataset (acknowledged limitation in academic write-up)

**Input features (must match training schema exactly):**
```python
FEATURES = [
    "unrealized_pnl_pct",       # float: negative = unrealized loss
    "holding_period_days",      # int
    "nifty_1d_change",          # float
    "nifty_52w_return",         # float
    "vix_value",                # float
    "market_trend_encoded",     # 0=bear, 1=sideways, 2=bull
    "decision_intent_encoded",  # 0=sell, 1=hold, 2=buy_more
    "risk_tolerance",           # float 0.0–1.0 (from user profile)
    "investment_horizon",       # int (years)
    "has_emergency_fund",       # bool → int
    "monthly_income_log",       # log(monthly_income + 1)
    "sector_encoded",           # label-encoded sector
]
```

**Inference:**
```python
class BiasDetector:
    def __init__(self, model_path: str = "models/xgboost_v3.pkl"):
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)
        self.label_encoder = LabelEncoder()
        self.label_encoder.classes_ = np.array(
            ["disposition_effect", "herd_behavior", "loss_aversion", "rational"]
        )

    def predict(self, features: dict) -> tuple[str, float]:
        X = self._build_feature_vector(features)
        proba = self.model.predict_proba([X])[0]
        class_idx = np.argmax(proba)
        return self.label_encoder.classes_[class_idx], float(proba[class_idx])

    def _build_feature_vector(self, f: dict) -> list:
        return [
            f["unrealized_pnl_pct"],
            f["holding_period_days"],
            f["nifty_1d_change"],
            f["nifty_52w_return"],
            f["vix_value"],
            {"bear":0, "sideways":1, "bull":2}.get(f["market_trend"], 1),
            {"sell":0, "hold":1, "buy_more":2}[f["decision_intent"]],
            f.get("risk_tolerance", 0.5),
            f.get("investment_horizon", 10),
            int(f.get("has_emergency_fund", False)),
            math.log(f.get("monthly_income", 50000) + 1),
            SECTOR_ENCODING.get(f.get("sector", "unknown"), 0),
        ]
```

---

### 5B. GAP 2 — Monte Carlo Simulator (`core/simulator.py`)

Runs 10,000 simulated wealth paths for HOLD and SELL scenarios over 20 years.

**Parameters:**
```python
NIFTY_ANNUAL_MEAN_RETURN = 0.122   # 12.2% CAGR (historical Nifty 50)
NIFTY_ANNUAL_VOLATILITY  = 0.185   # 18.5% annualized std dev
RISK_FREE_RATE           = 0.065   # 6.5% (approximate 10Y G-Sec)
SEQUENTIAL_SELL_PENALTY  = 0.025   # 2.5% slippage + transaction costs
BEHAVIORAL_PENALTY       = 0.015   # 1.5% drag from emotional re-allocation

N_PATHS   = 10_000
N_YEARS   = 20
```

**Simulation logic:**
```python
def run_simulation(decision: dict, user_profile: dict) -> SimulationResult:
    initial_value = decision["holding_quantity"] * decision["current_price"]

    # HOLD scenario: equity remains invested
    hold_paths = simulate_paths(
        initial_value=initial_value,
        mu=NIFTY_ANNUAL_MEAN_RETURN,
        sigma=NIFTY_ANNUAL_VOLATILITY,
        years=N_YEARS, n_paths=N_PATHS
    )

    # SELL scenario: proceeds re-allocated conservatively (behavioral re-allocation)
    # Apply: tax hit (STCG/LTCG), slippage, then suboptimal reinvestment
    sell_proceeds = compute_post_tax_proceeds(decision)
    sell_paths = simulate_paths(
        initial_value=sell_proceeds,
        mu=NIFTY_ANNUAL_MEAN_RETURN - BEHAVIORAL_PENALTY,
        sigma=NIFTY_ANNUAL_VOLATILITY * 0.8,   # conservative re-allocation
        years=N_YEARS, n_paths=N_PATHS
    )

    # Compute percentile curves (stored in DB — 120 numbers total)
    hold_curves = compute_percentile_curves(hold_paths)  # {p10, p50, p90} × 20 years
    sell_curves = compute_percentile_curves(sell_paths)

    opportunity_cost = hold_curves["p50"][-1] - sell_curves["p50"][-1]

    return SimulationResult(
        hold_curves=hold_curves,
        sell_curves=sell_curves,
        hold_median_20y=hold_curves["p50"][-1],
        hold_p10_20y=hold_curves["p10"][-1],
        hold_p90_20y=hold_curves["p90"][-1],
        sell_median_20y=sell_curves["p50"][-1],
        sell_p10_20y=sell_curves["p10"][-1],
        sell_p90_20y=sell_curves["p90"][-1],
        opportunity_cost=opportunity_cost,
    )

def simulate_paths(initial_value, mu, sigma, years, n_paths) -> np.ndarray:
    # GBM: dS = S * (mu * dt + sigma * sqrt(dt) * Z)
    dt = 1.0  # annual steps
    Z = np.random.standard_normal((n_paths, years))
    returns = np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z)
    paths = initial_value * np.cumprod(returns, axis=1)
    return paths  # shape: (n_paths, years)

def compute_percentile_curves(paths: np.ndarray) -> dict:
    return {
        "p10": np.percentile(paths, 10, axis=0).tolist(),
        "p50": np.percentile(paths, 50, axis=0).tolist(),
        "p90": np.percentile(paths, 90, axis=0).tolist(),
    }
```

---

### 5C. GAP 3 — Causal Inference + Explainer

**DoWhy causal inference (`core/causal_inference.py`):**
```python
import dowhy

async def run_causal_inference(features: dict, bias: str) -> float:
    """
    Estimates Average Treatment Effect (ATE):
    "If bias_detected changes from 0 to 1, what is the causal effect on
     the probability of a suboptimal outcome (selling during a drawdown)?"

    Causal graph assumption (must be stated explicitly in academic write-up):
      market_conditions → bias_level → decision_intent → outcome
      user_risk_profile → bias_level

    LIMITATION (must acknowledge): The causal graph is assumed, not discovered.
    The synthetic training data may not fully capture real-world confounders.
    """
    data = build_causal_dataset(features)  # loads background distribution
    model = dowhy.CausalModel(
        data=data,
        treatment="bias_level",    # 0 = no bias, 1 = biased
        outcome="suboptimal_sell", # 1 = selling during drawdown
        graph=CAUSAL_GRAPH_DOT     # pre-specified DAG in DOT format
    )
    identified = model.identify_effect()
    estimate = model.estimate_effect(
        identified,
        method_name="backdoor.linear_regression"
    )
    return float(estimate.value)
```

**Explainer output structure (`core/explainer.py`):**
```python
def build_explanation(decision, bias, confidence, simulation, causal_effect) -> dict:
    return {
        "situation": f"Market {format_change(decision['nifty_1d_change'])}, you hold {decision['symbol']}, {format_pnl(decision['unrealized_pnl_pct'])} unrealized",
        "bias_detected": bias,
        "bias_confidence": confidence,
        "bias_explanation": BIAS_EXPLANATIONS[bias],   # human-readable definition
        "counterfactual": {
            "hold": {
                "median_20y": simulation.hold_median_20y,
                "p10": simulation.hold_p10_20y,
                "p90": simulation.hold_p90_20y,
            },
            "sell": {
                "median_20y": simulation.sell_median_20y,
                "p10": simulation.sell_p10_20y,
                "p90": simulation.sell_p90_20y,
            }
        },
        "opportunity_cost_inr": simulation.opportunity_cost,
        "recommendation": "HOLD" if simulation.hold_median_20y > simulation.sell_median_20y else "SELL",
        "reasoning": generate_reasoning_text(bias, simulation, causal_effect),
        "causal_effect": causal_effect,
        "causal_interpretation": f"Being biased causally increases the probability of a suboptimal decision by {abs(causal_effect):.1%}",
        "simulation_curves": simulation.hold_curves | {"sell": simulation.sell_curves}
    }

BIAS_EXPLANATIONS = {
    "loss_aversion": "You feel the pain of losses approximately 2× more intensely than equivalent gains. This causes you to sell falling assets too early to 'stop the pain', even when holding is the rational choice.",
    "herd_behavior": "You're reacting to what the crowd is doing rather than your own analysis. Markets often move irrationally in the short term; crowd-following consistently destroys returns.",
    "disposition_effect": "You're inclined to sell your winners and hold your losers. This is the opposite of what momentum evidence suggests. You want to 'lock in' gains, but those gains often continue growing.",
    "rational": "Your decision appears to be driven by evidence and your risk profile, not cognitive bias. Proceed with your analysis."
}
```

---

### 5D. GAP 3 Extension — Debate Engine (`core/debate_engine.py`)

AutoGen multi-agent framework with Claude Sonnet. Bull / Bear / Judge pattern.

```python
import autogen
from anthropic import Anthropic

CLAUDE_CONFIG = {
    "model": "claude-sonnet-4-20250514",
    "api_key": settings.ANTHROPIC_API_KEY,
    "temperature": 0.7,
    "max_tokens": 600,   # per agent response — keeps debate concise
}

async def run_debate_engine(decision: dict, bias: str, explanation: dict) -> dict:
    """
    Returns a structured debate transcript with Bull, Bear, and Judge responses.
    Total cost: ~3 × 600 tokens out + ~500 tokens in = ~2,300 tokens per decision.
    Budget: ~$0.01 per decision at Sonnet pricing.
    """
    context = build_debate_context(decision, bias, explanation)

    bull_arg   = await call_claude(BULL_SYSTEM_PROMPT, context)
    bear_arg   = await call_claude(BEAR_SYSTEM_PROMPT, context)
    judge_input = context + f"\n\nBull says: {bull_arg}\n\nBear says: {bear_arg}"
    verdict    = await call_claude(JUDGE_SYSTEM_PROMPT, judge_input)

    return {
        "bull":   { "agent": "Bull",  "stance": "HOLD",  "argument": bull_arg  },
        "bear":   { "agent": "Bear",  "stance": "SELL",  "argument": bear_arg  },
        "judge":  { "agent": "Judge", "verdict": extract_verdict(verdict), "reasoning": verdict },
        "final_recommendation": extract_verdict(verdict),
        "generated_at": datetime.utcnow().isoformat()
    }

BULL_SYSTEM_PROMPT = """You are the Bull agent in a financial debate. Your role is to 
make the strongest possible case for HOLDING the position described. You argue for the 
long-term thesis, mean reversion, and the behavioral finance evidence against panic-selling.
Respond in 3–4 concise sentences. End with "BULL VERDICT: HOLD." """

BEAR_SYSTEM_PROMPT = """You are the Bear agent in a financial debate. Your role is to 
make the strongest possible case for SELLING the position described. You argue for capital 
preservation, opportunity cost of locked-up capital, and downside risk.
Respond in 3–4 concise sentences. End with "BEAR VERDICT: SELL." """

JUDGE_SYSTEM_PROMPT = """You are the Judge in a financial debate. You have heard arguments 
from both Bull and Bear. Your role is to weigh the evidence objectively and deliver a final 
verdict. Consider: the bias detected, the 20-year cost quantification, and the causal analysis.
Be decisive. End with exactly one of: "FINAL VERDICT: HOLD" or "FINAL VERDICT: SELL." """

# Cost management: cache debate results for highly similar inputs [NEW]
# Cache key: hash of (symbol, unrealized_pnl_pct_bucket, bias, market_trend)
# Redis TTL: 1 hour — debates are opinion-based, stale cache is acceptable short-term
DEBATE_CACHE_TTL = 3600

# Optimization: Judge-only-on-disagreement [NEW]
# If Bull and Bear both lean the same direction (confidence gap < 30%),
# skip the Judge call entirely — saves ~1 Claude API call in ~40% of cases.
# Implementation: after Bull + Bear responses, parse their stances.
# If both say HOLD or both say SELL → auto-verdict without Judge.
# If they disagree → run Judge as normal.
JUDGE_DISAGREEMENT_THRESHOLD = 0.30

# Monthly Claude API budget alert [NEW]
# Track per-decision token usage in a claude_usage_log Redis key:
#   INCRBY claude_usage:{YYYY-MM} <tokens_used>
# Set a monthly budget ceiling (e.g., $50) in env var CLAUDE_MONTHLY_BUDGET_USD.
# After each debate, check if projected monthly spend > 80% of budget.
# If exceeded: send email alert to ADMIN_EMAIL via Resend.
# At 100%: disable debate engine, return explainer-only results.
CLAUDE_MONTHLY_BUDGET_USD = float(os.getenv("CLAUDE_MONTHLY_BUDGET_USD", "50"))

async def call_claude(system: str, user: str) -> str:
    # Check cache first
    cache_key = f"debate_cache:{hash_inputs(system, user)}"
    cached = await redis.get(cache_key)
    if cached:
        return cached.decode()

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_CONFIG["model"],
        max_tokens=CLAUDE_CONFIG["max_tokens"],
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    result = response.content[0].text
    await redis.setex(cache_key, DEBATE_CACHE_TTL, result)
    return result
```

---

### 5E. GAP 4 — Audit Logger (`core/audit_logger.py`)

SHA-256 hash chain. Every decision event is chained to the previous one, making retroactive tampering detectable.

```python
import hashlib, json
from datetime import datetime

class AuditLogger:

    def compute_genesis_hash(self, user_id: str, created_at: datetime) -> str:
        """
        Anchor for the first entry in a user's audit chain.
        Anyone can re-verify: SHA256("GENESIS:{user_id}:{created_at.isoformat()}")
        """
        genesis_input = f"GENESIS:{user_id}:{created_at.isoformat()}"
        return hashlib.sha256(genesis_input.encode()).hexdigest()

    async def get_previous_hash(self, user_id: str, db) -> str:
        """Fetch the chain_hash of the most recent audit entry for this user."""
        row = await db.fetchrow(
            "SELECT chain_hash FROM audit_logs WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1",
            user_id
        )
        if row:
            return row["chain_hash"]
        # No prior entries — use genesis hash
        user = await db.fetchrow("SELECT user_id, created_at FROM users WHERE user_id=$1", user_id)
        return self.compute_genesis_hash(str(user["user_id"]), user["created_at"])

    async def log_event(self, user_id: str, decision_id: str,
                        event_type: str, payload: dict, db) -> str:
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        previous_hash = await self.get_previous_hash(user_id, db)
        chain_hash = hashlib.sha256(
            (payload_hash + previous_hash).encode()
        ).hexdigest()

        await db.execute(
            """INSERT INTO audit_logs
               (decision_id, user_id, event_type, payload_hash, previous_hash, chain_hash, payload)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            decision_id, user_id, event_type,
            payload_hash, previous_hash, chain_hash,
            json.dumps(payload)
        )
        return chain_hash

    async def verify_chain(self, user_id: str, db) -> dict:
        """
        Verify the full audit chain for a user.
        Returns: { valid: bool, broken_at: log_id | None, total_entries: int }
        """
        entries = await db.fetch(
            "SELECT * FROM audit_logs WHERE user_id=$1 ORDER BY created_at ASC",
            user_id
        )
        if not entries:
            return {"valid": True, "broken_at": None, "total_entries": 0}

        user = await db.fetchrow("SELECT user_id, created_at FROM users WHERE user_id=$1", user_id)
        expected_prev = self.compute_genesis_hash(str(user["user_id"]), user["created_at"])

        for entry in entries:
            if entry["previous_hash"] != expected_prev:
                return {"valid": False, "broken_at": str(entry["log_id"]), "total_entries": len(entries)}
            recomputed = hashlib.sha256(
                (entry["payload_hash"] + entry["previous_hash"]).encode()
            ).hexdigest()
            if recomputed != entry["chain_hash"]:
                return {"valid": False, "broken_at": str(entry["log_id"]), "total_entries": len(entries)}
            expected_prev = entry["chain_hash"]

        return {"valid": True, "broken_at": None, "total_entries": len(entries)}
```

---

## Phase 6 — Practical Extensions

### 6A. Tax Engine (`services/tax_engine.py`)

```python
STCG_RATE = 0.15   # 15% Short Term Capital Gains (< 1 year)
LTCG_RATE = 0.10   # 10% Long Term Capital Gains (≥ 1 year), above ₹1L exemption
LTCG_EXEMPTION = 100_000  # ₹1,00,000 LTCG exempt per financial year

def compute_tax_impact(holding: dict) -> dict:
    """
    holding: { quantity, avg_buy_price, current_price, buy_date }
    Returns tax category, tax amount, and post-tax proceeds.
    """
    holding_days = (date.today() - holding["buy_date"]).days
    gross_pnl = (holding["current_price"] - holding["avg_buy_price"]) * holding["quantity"]
    gross_proceeds = holding["current_price"] * holding["quantity"]

    if gross_pnl <= 0:
        # Loss — no tax. Can be used for tax-loss harvesting.
        return {
            "tax_category": "STCG" if holding_days < 365 else "LTCG",
            "tax_amount": 0.0,
            "post_tax_proceeds": gross_proceeds,
            "is_loss": True,
            "loss_amount": abs(gross_pnl)
        }

    if holding_days < 365:
        tax_amount = gross_pnl * STCG_RATE
        return {
            "tax_category": "STCG",
            "tax_amount": tax_amount,
            "post_tax_proceeds": gross_proceeds - tax_amount,
            "holding_days": holding_days
        }
    else:
        taxable_ltcg = max(0, gross_pnl - LTCG_EXEMPTION)
        tax_amount = taxable_ltcg * LTCG_RATE
        return {
            "tax_category": "LTCG",
            "tax_amount": tax_amount,
            "post_tax_proceeds": gross_proceeds - tax_amount,
            "holding_days": holding_days,
            "ltcg_exempt_used": min(gross_pnl, LTCG_EXEMPTION)
        }
```

**Portfolio Page badges:** Each holding shows `STCG` (amber) or `LTCG` (emerald) badge based on holding days. Hovering shows "X days to LTCG status" if currently STCG.

---

### 6B. SIP Tracker (`services/sip_tracker.py`)

```python
SIP_PAUSE_OPPORTUNITY_RETURN = 0.122   # expected return for the months missed

def detect_sip_pause_intent(user_id: str) -> list[PauseAlert]:
    """
    Runs daily. Detects if any active SIP is due in the next 3 days
    AND current market is down > 2% from 30-day average (a common panic-pause scenario).
    """
    alerts = []
    sips = get_active_sips(user_id)
    for sip in sips:
        if days_until_deduction(sip) <= 3:
            if nifty_below_30d_avg_by(0.02):  # market down > 2%
                cost = compute_pause_cost(sip.monthly_amount, months=1)
                alerts.append(PauseAlert(
                    sip_id=sip.sip_id,
                    fund_name=sip.fund_name,
                    message=f"Your SIP of ₹{sip.monthly_amount:,.0f} in {sip.fund_name} is due in {days_until_deduction(sip)} days. Markets are down — pausing now would cost ~₹{cost:,.0f} over 20 years.",
                    opportunity_cost=cost,
                    recommended_action="Continue SIP"
                ))
    return alerts

def compute_pause_cost(monthly_amount: float, months: int = 1) -> float:
    """
    Opportunity cost of missing N months of SIP during a dip.
    Conservative: assume missed months reinvested at market average later.
    """
    future_value = monthly_amount * ((1 + NIFTY_MONTHLY_RETURN) ** (20 * 12) - 1) / NIFTY_MONTHLY_RETURN
    return future_value * months

# API endpoint
GET /v1/sip/alerts       → list of PauseAlert for current user
GET /v1/sip/             → list user's SIP registrations
POST /v1/sip/            → register new SIP
PUT /v1/sip/{id}         → update SIP (amount, date)
DELETE /v1/sip/{id}      → remove SIP
POST /v1/sip/{id}/pause  → manually pause SIP (logs event)
```

---

### 6C. Kite Integration (`services/kite_integration.py`) `[REVISED]`

Includes daily token expiry handling — Zerodha access tokens expire at 6 AM IST every day regardless of when they were issued.

```python
from kiteconnect import KiteConnect
from cryptography.fernet import Fernet
import pytz

IST = pytz.timezone("Asia/Kolkata")
KITE_TOKEN_EXPIRY_HOUR_IST = 6   # 6 AM IST daily

def is_kite_token_valid(issued_date: date) -> bool:
    """
    Token is valid only if it was issued TODAY after 6 AM IST.
    (Kite tokens expire at 6 AM IST every day — not on a TTL)
    """
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()
    cutoff = now_ist.replace(hour=KITE_TOKEN_EXPIRY_HOUR_IST, minute=0, second=0, microsecond=0)

    # If current time is before 6 AM, yesterday's tokens are still valid
    if now_ist < cutoff:
        valid_from_date = (now_ist - timedelta(days=1)).date()
    else:
        valid_from_date = today_ist

    return issued_date >= valid_from_date

async def get_kite_client(user_id: str, db) -> KiteConnect:
    token_row = await db.fetchrow(
        "SELECT access_token, access_token_date FROM kite_tokens WHERE user_id=$1", user_id
    )
    if not token_row or not is_kite_token_valid(token_row["access_token_date"]):
        raise KiteTokenExpiredError(
            "Kite session expired. Please reconnect your Zerodha account.",
            action="reconnect"
        )
    decrypted_token = Fernet(settings.FERNET_KEY).decrypt(token_row["access_token"]).decode()
    kite = KiteConnect(api_key=settings.KITE_API_KEY)
    kite.set_access_token(decrypted_token)
    return kite

# API endpoints
GET  /v1/portfolio/kite/connect    → redirect to Kite login (OAuth)
GET  /v1/portfolio/kite/callback   → exchange request_token for access_token, store encrypted
POST /v1/portfolio/kite/disconnect → delete kite_tokens row
GET  /v1/portfolio/kite/status     → returns { connected: bool, token_valid: bool, last_synced: datetime }
POST /v1/portfolio/kite/sync       → pull holdings + positions, update portfolios table

# Portfolio page "reconnect" banner logic:
# If GET /v1/portfolio/kite/status returns token_valid=false:
#   Show amber banner: "Kite session expired. Reconnect to sync live prices."
#   "Reconnect" button → GET /v1/portfolio/kite/connect

# Rate limits (Kite API limits):
# Max 3 connections per second
# Max 200 requests per minute
# All Kite calls go through a rate-limited wrapper
```

---

### 6D. Multi-Asset Support (`services/market_data.py`) `[REVISED]`

yfinance is unreliable as a primary source. Multi-layer fallback implemented.

```python
# Market data with fallback chain
async def get_price(symbol: str, exchange: str = "NSE") -> PriceData:
    """
    Fallback order:
    1. NSE official API (nsepy or mstock API)
    2. yfinance (Yahoo Finance scraping — unreliable, treat as fallback only)
    3. Cached value from Redis (up to 30 min stale — better than failure)
    4. Raise ServiceUnavailableError
    """
    cache_key = f"price:{exchange}:{symbol}"

    try:
        data = await _fetch_nsepy(symbol, exchange)
        await redis.setex(cache_key, 300, json.dumps(data))  # cache 5 min
        return data
    except Exception as e:
        logger.warning("NSEPy failed", symbol=symbol, error=str(e))

    try:
        yf_symbol = f"{symbol}.NS" if exchange == "NSE" else f"{symbol}.BO"
        data = await _fetch_yfinance(yf_symbol)
        await redis.setex(cache_key, 300, json.dumps(data))
        return data
    except Exception as e:
        logger.warning("yfinance failed", symbol=symbol, error=str(e))

    # Try stale cache (up to 30 min)
    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        data["stale"] = True
        data["stale_note"] = "Live price unavailable. Showing last known price."
        return data

    raise ServiceUnavailableError("market_data", f"Cannot fetch price for {symbol}")

# Asset type routing
ASSET_SOURCES = {
    "equity": get_nse_price,                    # NSEPy → yfinance
    "mf":     get_mfapi_nav,                    # MFAPI.in (free, reliable)
    "gold":   get_goldbees_price,               # Sovereign Gold ETF (NSE)
    "crypto": get_coingecko_price,              # CoinGecko free API
}
```

---

### 6E. Outcome Tracker (`services/outcome_tracker.py`)

Tracks whether the AI recommendation was followed and what the actual outcome was.

```python
# Runs as a scheduled check (monthly, triggered by admin or cron)
async def check_outcomes(db):
    """
    Find decisions that:
    1. Were made 3 months ago (enough time for outcome to materialize)
    2. Have outcome_tracked = false
    3. User has Kite connected
    """
    decisions = await db.fetch(
        """SELECT d.*, k.access_token
           FROM decisions d
           JOIN kite_tokens k ON d.user_id = k.user_id
           WHERE d.completed_at < NOW() - INTERVAL '90 days'
           AND d.outcome_tracked = false
           AND d.status = 'complete'
           LIMIT 100"""
    )
    for decision in decisions:
        try:
            current_price = await get_price(decision["symbol"])
            actual_return = (current_price - decision["current_price"]) / decision["current_price"]
            recommendation_followed = assess_if_followed(decision)  # check portfolio/kite
            await db.execute(
                """UPDATE decisions
                   SET outcome_tracked=true, actual_outcome_pct=$1, recommendation_followed=$2
                   WHERE decision_id=$3""",
                actual_return, recommendation_followed, decision["decision_id"]
            )
        except Exception as e:
            logger.warning("Outcome tracking failed", decision_id=str(decision["decision_id"]))
```

---

### 6F. ML Retrainer (`services/retrain_monthly.py`)

```python
async def retrain_if_improved():
    """
    Monthly job. Combines real outcome data (labeled) with synthetic data,
    retrains XGBoost. Deploys only if new F1 > current F1.

    Cold-start note: Until enough real labeled outcomes exist (N > 500),
    synthetic data will dominate. The model will still improve as real data accumulates.
    """
    real_data = await fetch_labeled_outcomes(min_samples=100)   # skip if too few
    synthetic_data = load_synthetic_dataset()

    if len(real_data) < 100:
        logger.info("Skipping retrain — insufficient real data", count=len(real_data))
        return

    combined = pd.concat([synthetic_data, real_data])
    new_model = train_xgboost(combined)
    new_f1 = evaluate_f1(new_model, test_set)
    current_f1 = get_current_model_f1()

    if new_f1 > current_f1:
        save_model(new_model, f"models/xgboost_v{next_version}.pkl")
        update_active_model_pointer(new_version)
        logger.info("Model updated", old_f1=current_f1, new_f1=new_f1, version=next_version)
        notify_admin(f"Model updated: {current_f1:.4f} → {new_f1:.4f}")
    else:
        logger.info("Retrain complete — no improvement", current_f1=current_f1, new_f1=new_f1)
```

---

### 6G. WhatsApp Bot (`services/whatsapp_bot.py`)

Priority: Low. Requires Meta Business API approval (2–4 week process — initiate early).

```python
# Webhook: POST /v1/webhooks/whatsapp
# User sends: "Should I sell HDFC Bank? Down 18%."
# Bot responds with a 3-line summary card.

async def handle_whatsapp_message(message: str, phone: str):
    user = await get_user_by_phone(phone)
    if not user:
        return "Reply with your registered email to link your account."

    # Parse intent from message (simple regex or LLM)
    decision_intent = parse_decision_from_text(message)
    if not decision_intent:
        return "I can help you with HOLD/SELL decisions. Try: 'Should I sell HDFC Bank? Down 15%.'"

    # Run bias detection only (fast, no full pipeline)
    bias, confidence = bias_detector.predict(decision_intent.features)

    return (
        f"*Bias Detected:* {bias.replace('_', ' ').title()} ({confidence:.0%} confidence)\n"
        f"*Recommendation:* {'HOLD — don\'t let {bias} drive you.' if bias != 'rational' else 'Looks rational. Proceed carefully.'}\n"
        f"*Full Analysis:* app.finai.in/dashboard/decision"
    )
```

---

### 6H. Data Export — GDPR (`services/data_export.py`)

```python
# GET /v1/users/me/export
async def export_user_data(user_id: str, db) -> dict:
    user = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
    decisions = await db.fetch("SELECT * FROM decisions WHERE user_id=$1", user_id)
    portfolio = await db.fetch("SELECT * FROM portfolios WHERE user_id=$1", user_id)
    sips = await db.fetch("SELECT * FROM sip_registrations WHERE user_id=$1", user_id)
    audit_logs = await db.fetch("SELECT * FROM audit_logs WHERE user_id=$1", user_id)
    change_log = await db.fetch("SELECT * FROM profile_change_log WHERE user_id=$1", user_id)

    return {
        "export_generated_at": datetime.utcnow().isoformat(),
        "user": sanitize(user),     # remove password_hash, mfa_secret_enc
        "decisions": [dict(d) for d in decisions],
        "portfolio": [dict(p) for p in portfolio],
        "sip_registrations": [dict(s) for s in sips],
        "audit_logs": [dict(a) for a in audit_logs],
        "profile_change_log": [dict(c) for c in change_log],
    }

# Returns as JSON response with:
# Content-Disposition: attachment; filename="finai_data_export_{date}.json"
```

---

## Phase 7 — Infrastructure & Deployment

### 7A. Docker Setup

**docker-compose.yml (local dev):**
```yaml
version: '3.9'
services:
  backend:
    build: { context: ., dockerfile: Dockerfile.backend }
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgres://finai:finai@postgres:5432/finai
      REDIS_URL: redis://redis:6379
      ENV: development
      SENTRY_DSN: ""   # empty = disabled in dev
    volumes: ["./backend:/app/backend"]
    depends_on: [postgres, redis]
    command: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

  frontend:
    build: { context: ./frontend, dockerfile: Dockerfile.frontend.dev }
    ports: ["3000:3000"]
    volumes: ["./frontend/src:/app/src"]
    environment:
      VITE_API_BASE: http://localhost:8000/api/v1

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: finai
      POSTGRES_USER: finai
      POSTGRES_PASSWORD: finai
    ports: ["5432:5432"]
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  pgbouncer:
    image: pgbouncer/pgbouncer:latest
    environment:
      DATABASES_HOST: postgres
      DATABASES_PORT: 5432
      DATABASES_DBNAME: finai
      PGBOUNCER_POOL_MODE: transaction
      PGBOUNCER_MAX_CLIENT_CONN: 100
      PGBOUNCER_DEFAULT_POOL_SIZE: 20
    ports: ["6432:5432"]
    depends_on: [postgres]

volumes:
  postgres_data:
```

**Dockerfile.backend:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY models/ models/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Dockerfile.frontend (production build):**
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
```

---

### 7B. Render Setup

```yaml
# render.yaml
services:
  - type: web
    name: finai-backend
    runtime: docker
    dockerfilePath: ./Dockerfile.backend
    buildCommand: ""
    startCommand: ""
    envVars:
      - key: DATABASE_URL
        fromDatabase: { name: finai-postgres, property: connectionString }
      - key: REDIS_URL
        value: "rediss://your-upstash-redis-url"     # Upstash Redis, NOT Render Redis
      - key: ENV
        value: production
      - key: JWT_PRIVATE_KEY
        sync: false    # manually set sensitive values
      - key: JWT_PUBLIC_KEY
        sync: false
      - key: AES_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: RESEND_API_KEY
        sync: false
      - key: SENTRY_DSN
        sync: false
      - key: KITE_API_KEY
        sync: false
      - key: KITE_API_SECRET
        sync: false

  - type: web
    name: finai-frontend
    runtime: static
    buildCommand: cd frontend && npm ci && npm run build
    staticPublishPath: frontend/dist
    headers:
      - path: /*
        name: X-Frame-Options
        value: DENY
    routes:
      - type: rewrite
        source: /*
        destination: /index.html   # SPA routing

databases:
  - name: finai-postgres
    plan: free
    databaseName: finai
    user: finai
```

---

### 7C. AWS Migration Path

Zero code changes required — only environment variable swaps.

```
Render (now)               AWS (later)
─────────────────────      ──────────────────────────
Neon PostgreSQL        →   RDS PostgreSQL (Multi-AZ)
Upstash Redis          →   ElastiCache Redis (cluster)
Render Web Service     →   ECS Fargate (Docker container)
Render Static Site     →   S3 + CloudFront (CDN, edge cache)
─────────────────────      ──────────────────────────
Change only: DATABASE_URL, REDIS_URL, and CDN_URL in .env
All application code stays identical (Docker portability)
```

---

### 7D. CI/CD (GitHub Actions)

```yaml
# .github/workflows/main.yml
name: CI/CD Pipeline
on:
  push:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: finai_test
          POSTGRES_USER: finai
          POSTGRES_PASSWORD: finai
        ports: ["5432:5432"]
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: alembic upgrade head
        env: { DATABASE_URL: postgres://finai:finai@localhost:5432/finai_test }
      - run: pytest backend/tests/ --cov=backend --cov-report=xml
        env:
          DATABASE_URL: postgres://finai:finai@localhost:5432/finai_test
          REDIS_URL: redis://localhost:6379
          JWT_PRIVATE_KEY: ${{ secrets.JWT_PRIVATE_KEY }}
          JWT_PUBLIC_KEY: ${{ secrets.JWT_PUBLIC_KEY }}
      - name: Fail if coverage < 70%
        run: python -c "import xml.etree.ElementTree as ET; tree=ET.parse('coverage.xml'); coverage=float(tree.getroot().get('line-rate'))*100; exit(0 if coverage>=70 else 1)"

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run test -- --coverage
      - run: cd frontend && npm run build   # catch build errors

  deploy:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy backend to Render
        run: curl -X POST ${{ secrets.RENDER_BACKEND_DEPLOY_HOOK }}
      - name: Deploy frontend to Render
        run: curl -X POST ${{ secrets.RENDER_FRONTEND_DEPLOY_HOOK }}
```

---

## Phase 8 — Admin Dashboard

### Overview

The admin dashboard is a separate React layout. Admins have **zero access** to individual user data — only aggregate statistics from `admin_stats_view`.

### 8A. Admin Home (`/admin`)

**Aggregate stats cards (4-card bento):**
- Total users: count, active today, new this week
- Decisions today: total, completed, failed
- Bias distribution (last 7 days): donut chart — % Loss Aversion / Herd / Disposition / Rational
- Model performance: current XGBoost version, F1 score, last retrained date

### 8B. Admin User Management (`/admin/users`)

```
Table columns: Name | Email | Joined | Last Active | Status | Decisions | Actions
Actions: Activate | Deactivate | Reset Password | Reset MFA | Hard Delete (only after 30d soft-delete)

Search: by name, email, join date range
Filter: is_active, mfa_enabled, has_kite

NO columns for: income, portfolio value, decision history, bias profile
```

**Endpoints:**
```
GET  /v1/admin/users                        → paginated list (no financial data)
GET  /v1/admin/users/{id}                   → user metadata only
POST /v1/admin/users/{id}/activate
POST /v1/admin/users/{id}/deactivate
POST /v1/admin/users/{id}/reset-password    → triggers email to user
POST /v1/admin/users/{id}/reset-mfa         → requires admin TOTP
DELETE /v1/admin/users/{id}                 → hard delete (only if deleted_at < 30 days ago)
GET  /v1/admin/stats                        → aggregate stats from admin_stats_view
GET  /v1/admin/system/health                → API latency, error rates, uptime
POST /v1/admin/ml/retrain                   → trigger batch retrain job
GET  /v1/admin/ml/metrics                   → model performance history
GET  /v1/admin/mfa-recovery                 → pending MFA recovery requests
POST /v1/admin/mfa-recovery/{id}/resolve    → mark resolved (after MFA reset)
```

### 8C. System Health (`/admin` → health card)

```python
# GET /v1/admin/system/health
{
    "api_status": "healthy",
    "database": { "connected": true, "pool_size": 10, "idle": 8 },
    "redis": { "connected": true, "memory_mb": 2.1 },
    "ml_model": { "loaded": true, "version": "v3", "f1": 0.8581 },
    "anthropic_api": { "reachable": true, "last_checked": "2025-01-15T10:00:00Z" },
    "kite_api": { "reachable": true },
    "uptime_seconds": 86400,
    "error_rate_1h": 0.002   # errors / total requests
}
```

---

## Security Summary

| Threat | Mitigation |
|---|---|
| User A reads User B's data | JWT ownership (no user_id in URL) + PostgreSQL RLS at DB level |
| Admin reads user raw data | Admin queries aggregate VIEWs only — no user_id column in view |
| XSS token theft | httpOnly cookies — JS cannot read access/refresh tokens |
| CSRF | Double-submit cookie (X-CSRF-Token header on all mutations) `[NEW]` |
| Brute force login | 5 req/min per IP via slowapi + Redis |
| Account takeover | MFA (TOTP) required for all sensitive field changes |
| Password breach | bcrypt cost=12, zxcvbn strength enforcement (reject score < 3) |
| JWT forgery | RS256 asymmetric — private key never leaves server |
| Token replay after logout | Redis blacklist on refresh token jti (Upstash — persistent) `[REVISED]` |
| Audit tampering | PostgreSQL RULE blocks DELETE/UPDATE + SHA-256 hash chain |
| GDPR violation | Soft delete + 30-day hard delete + data export endpoint |
| SQL injection | Parameterized queries via asyncpg everywhere |
| PgBouncer prepared stmt bug | statement_cache_size=0 on all asyncpg pools `[NEW]` |
| Sensitive field changes | Re-verification (password + TOTP) required |
| OAuth account hijack | Email binding — Google email must match existing account exactly |
| Google OAuth bypassing MFA | MFA required on account regardless of login method `[REVISED]` |
| Man-in-middle | HTTPS enforced via HSTS header |
| Clickjacking | X-Frame-Options: DENY + CSP frame-ancestors 'none' `[NEW]` |
| Content injection | Content-Security-Policy header on all responses `[NEW]` |
| Lost MFA device | Backup codes (8) + admin-reset path with TOTP verification `[NEW]` |
| Theme FOUC | Inline script in index.html before React mounts `[NEW]` |
| Redis unavailability | Upstash Redis (persistent) — token blacklist survives restarts `[NEW]` |
| External API failure | Multi-layer fallback chain + stale cache fallback + ServiceUnavailableError |
| SSE timeout | 2-minute max stream window, graceful timeout message to frontend `[NEW]` |

---

## Test Strategy `[NEW]`

### Backend Tests (`pytest` + `httpx`)

**Structure:**
```
backend/tests/
├── conftest.py              # shared fixtures: test db, test redis, auth tokens
├── unit/
│   ├── test_bias_detector.py
│   ├── test_simulator.py
│   ├── test_audit_logger.py    # hash chain integrity
│   ├── test_tax_engine.py
│   └── test_password.py        # zxcvbn, bcrypt
├── integration/
│   ├── test_auth_flow.py       # register → verify → login → MFA → refresh → logout
│   ├── test_decision_flow.py   # submit → stream → complete
│   ├── test_portfolio.py
│   └── test_admin.py           # verify admin cannot access user data
└── api/
    ├── test_auth_endpoints.py
    ├── test_decision_endpoints.py
    ├── test_ownership.py       # User A cannot access User B's data
    └── test_rate_limits.py
```

**Key test cases:**

```python
# test_audit_logger.py
def test_hash_chain_integrity():
    logger = AuditLogger()
    user_id = "test-user-id"
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    genesis = logger.compute_genesis_hash(user_id, created_at)

    # Simulate 3 chained entries
    entries = []
    prev_hash = genesis
    for i in range(3):
        payload_hash = sha256(f"payload_{i}".encode()).hexdigest()
        chain_hash = sha256((payload_hash + prev_hash).encode()).hexdigest()
        entries.append({"payload_hash": payload_hash, "previous_hash": prev_hash, "chain_hash": chain_hash})
        prev_hash = chain_hash

    # Tamper with entry 1 — should break chain at entry 2
    entries[1]["payload_hash"] = "tampered"
    result = verify_chain_entries(entries, genesis)
    assert result["valid"] == False
    assert result["broken_at_index"] == 2

# test_ownership.py
async def test_user_a_cannot_read_user_b_decisions(client, user_a_token, user_b_decision_id):
    response = await client.get(
        f"/v1/decisions/{user_b_decision_id}/result",
        cookies={"access_token": user_a_token}
    )
    assert response.status_code == 404   # not 403 — don't reveal existence

# test_auth_flow.py
async def test_full_mfa_flow(client):
    # Register
    r = await client.post("/v1/auth/register", json={...})
    assert r.status_code == 201

    # Verify email (simulate Redis token)
    token = get_email_token_from_redis(test_redis)
    r = await client.get(f"/v1/auth/verify-email?token={token}")
    assert r.status_code == 302

    # Login (no MFA yet)
    r = await client.post("/v1/auth/login", json={"email": "...", "password": "..."})
    assert r.status_code == 200
    assert "access_token" in r.cookies

    # Setup MFA
    r = await client.post("/v1/auth/mfa/setup", cookies=r.cookies)
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = await client.post("/v1/auth/mfa/verify-setup", json={"totp_code": code})
    assert r.status_code == 200
    assert len(r.json()["backup_codes"]) == 8

    # Logout and re-login with MFA
    await client.post("/v1/auth/logout")
    r = await client.post("/v1/auth/login", json={"email": "...", "password": "..."})
    assert r.json()["mfa_required"] == True
    temp_token = r.json()["temp_token"]
    code = pyotp.TOTP(secret).now()
    r = await client.post("/v1/auth/login/mfa", json={"temp_token": temp_token, "totp_code": code})
    assert r.status_code == 200
```

**Coverage target:** 70% overall, 90% on auth and audit modules.

### Frontend Tests (`Vitest` + `React Testing Library`)

**Structure:**
```
frontend/src/__tests__/
├── components/
│   ├── ProtectedRoute.test.tsx
│   ├── AuditVerifier.test.tsx
│   └── BiasAlertCard.test.tsx
├── pages/
│   ├── LoginPage.test.tsx
│   └── DecisionPage.test.tsx
└── lib/
    ├── axios.test.ts    # CSRF interceptor
    └── theme.test.ts    # FOUC prevention
```

**E2E Tests (Playwright):**
```
e2e/
├── auth.spec.ts         # register → verify → login → logout
├── decision.spec.ts     # submit decision → SSE stream → view result
└── mfa.spec.ts          # setup MFA → disable MFA
```

**Coverage target:** 60% component/page coverage. All critical user flows covered by E2E.

---

## Build Sequence

Realistic timeline accounting for the Barclays internship running concurrently.

```
Weeks 1–2:   Phase 1A–1H — Auth system
             Register, verify, login, MFA, Google OAuth, password reset, CSRF
             All auth endpoints tested + passing

Weeks 3–4:   Phase 2 — Database
             Full schema, Alembic migrations, RLS policies, admin view
             Local Docker setup working with Neon + Upstash

Weeks 5–6:   Phase 3 — Backend restructure
             Modular project layout, API versioning, ownership pattern
             Error handling, Sentry, structlog, security headers
             Rate limiting, all middleware

Weeks 7–8:   Phase 4A–4E — React setup + Landing page
             Vite + Tailwind + shadcn/ui scaffold
             Design tokens implemented, FOUC fix, Axios + CSRF setup
             Landing page fully built and deployed

Weeks 9–10:  Phase 4F–4L — Dashboard shell + Profile + Settings
             Dashboard bento grid, protected routes, mobile layout
             Profile management, re-verification modals, account deletion

Weeks 11–12: Phase 5A–5C — Bias Detector + Simulator + Explainer
             Migrate XGBoost inference to new backend structure
             Monte Carlo simulator integrated
             Explainer JSON builder + Decision page UI

Weeks 13–14: Phase 5D–5E + Phase 3F — Debate Engine + SSE + Audit Logger
             SSE streaming infrastructure (pipeline.py, stream.py)
             AutoGen + Claude debate engine
             SHA-256 audit hash chain + AuditVerifier component

Weeks 15–16: Phase 6A–6B — Tax Engine + SIP Tracker
             Tax computation + portfolio badges
             SIP registration + pause detection alerts

Weeks 17–18: Phase 8 + CI/CD — Admin Dashboard + GitHub Actions
             Aggregate stats, user management, MFA recovery management
             Full CI/CD pipeline, 70% coverage gate, Render deploy

Weeks 19–20: Phase 6C–6D — Kite Integration + Multi-Asset
             Zerodha Kite OAuth, daily re-auth mechanism, portfolio sync
             MF/Gold/Crypto price feeds with fallback chains

Weeks 21–22: Phase 6E–6F + Polish — Outcome Tracker + ML Retrainer
             Outcome tracking logic
             Monthly retrain pipeline
             Final QA pass, performance audit, academic write-up integration
             Full demo walkthrough, seed data for defense demo

Week 23+:    Phase 6G — WhatsApp Bot (stretch goal)
             Initiate Meta Business API approval process in Week 10 (6-week lead time)
```

---

## Role Reference

### Guest (Not Logged In)

| Action | Allowed |
|---|---|
| View landing page | ✅ |
| Register | ✅ |
| Login | ✅ |
| Request password reset | ✅ |
| View public market data (`/v1/market/context`) | ✅ |
| Access any dashboard page | ❌ Redirect to /login |
| Access any API endpoint (except auth + market) | ❌ 401 |

---

### User (Logged In, role = `user`)

**Account & Profile:**

| Action | Allowed | Notes |
|---|---|---|
| View own profile | ✅ | |
| Edit non-sensitive fields (name, goal, strategy) | ✅ | No verification |
| Edit sensitive fields (email, income, emergency fund) | ✅ | Re-verification required |
| Change password | ✅ | Current password + TOTP (if MFA on) |
| Enable / disable MFA | ✅ | Disable requires password + TOTP |
| Connect Google OAuth | ✅ | Same-email binding |
| Upload profile picture | ✅ | |
| Export own data (GDPR) | ✅ | `GET /v1/users/me/export` |
| Delete own account | ✅ | Password + TOTP + type "DELETE" + 30-day grace |
| View another user's profile | ❌ 404 |
| Modify another user's data | ❌ 404 |

**Financial Decisions:**

| Action | Allowed | Notes |
|---|---|---|
| Submit decision for AI analysis | ✅ | Async — returns decision_id immediately |
| Stream pipeline progress (SSE) | ✅ | `GET /v1/decisions/{id}/stream` |
| View own completed decisions | ✅ | |
| View own bias history | ✅ | |
| Run HOLD vs SELL simulation | ✅ | Rate limited: 5/min |
| View AI debate transcript | ✅ | Own decisions only |
| View opportunity cost report | ✅ | Own decisions only |
| View another user's decisions | ❌ 404 |

**Portfolio:**

| Action | Allowed | Notes |
|---|---|---|
| Add/edit/delete own holdings | ✅ | |
| View own live P&L | ✅ | Auto-refresh every 5 min via React Query |
| Connect Zerodha Kite | ✅ | OAuth — requires daily reconnect at 6 AM IST |
| View another user's portfolio | ❌ 404 |

**Audit Trail:**

| Action | Allowed | Notes |
|---|---|---|
| View own audit log | ✅ | |
| Verify own hash chain | ✅ | AuditVerifier component (client-side SHA-256) |
| View another user's audit log | ❌ 404 |
| Modify or delete any audit entry | ❌ PostgreSQL RULE blocks at DB level |

---

### Admin (role = `admin`)

> ZERO access to individual user financial data. All admin queries hit aggregate VIEWs.

**User Management:**

| Action | Allowed | Notes |
|---|---|---|
| View user list | ✅ | Metadata only: name, email, joined, is_active, decision count |
| Activate / deactivate user | ✅ | |
| Reset user password | ✅ | Sends email to user |
| Reset user MFA | ✅ | Requires admin's own TOTP + sends notification to user |
| Hard delete user | ✅ | Only after 30-day soft-delete grace period |
| Manage MFA recovery requests | ✅ | |
| View user raw_input / financial data | ❌ Query-level blocked |
| View user portfolio holdings | ❌ Query-level blocked |
| View user decision history | ❌ Query-level blocked |
| Access user's TOTP secret | ❌ AES-256 encrypted, never exposed |

**System & Analytics:**

| Action | Allowed | Notes |
|---|---|---|
| View aggregate bias distribution | ✅ | Via admin_stats_view — no user_id column |
| View total decisions per day | ✅ | Aggregate only |
| View system health metrics | ✅ | |
| Trigger ML model retraining | ✅ | |
| View model performance history | ✅ | |
| Modify or delete audit logs | ❌ PostgreSQL RULE blocks at DB level |
| Access any user-owned endpoint | ❌ JWT ownership prevents this |

---

### Sensitive Actions — Re-verification Required

| Action | Verification Required | Window |
|---|---|---|
| Change email | Password + OTP to old email | One-time |
| Change password | Current password + TOTP (if MFA) | One-time |
| Edit monthly income | Current password | 5-minute window |
| Edit emergency fund status | Current password | 5-minute window |
| Disable MFA | Current password + current TOTP | One-time |
| Delete account | Password + TOTP + type "DELETE" | One-time + 30s cooldown |
| Connect/disconnect Kite | Current password | One-time |

The "5-minute sensitive edit window" is tracked in React state — user does not re-verify every field within a 5-minute session after one successful verification.

---

### Data Isolation Summary

```
User A  → reads/writes ONLY WHERE user_id = their own UUID
           (enforced at API layer by JWT + at DB layer by PostgreSQL RLS)

Admin   → reads ONLY from admin_stats_view
           (no user_id column exists in the view)

Guest   → reads ONLY /v1/market/context and /v1/auth/* endpoints

Even if the application code has a bug, PostgreSQL RLS
independently blocks cross-user access at the database level.
```

---

## 9. Consolidated API Reference [NEW]

| Method | Endpoint | Auth Required | Rate Limit | Description |
|---|---|---|---|---|
| **Health & Status** | | | | |
| `GET` | `/health` | No | - | Liveness and health check |
| `GET` | `/model/status` | No | - | Inspect loaded XGBoost models and causal weights |
| `GET` | `/v1/admin/system/health` | Yes (Admin) | - | Admin system diagnostic data |
| **Authentication** | | | | |
| `POST` | `/v1/auth/register` | No | 3 req/hour per IP | Register user + onboard profile (returns OTP & onboarding questions) |
| `GET` | `/v1/auth/verify-email` | No | - | Verify user registration OTP |
| `POST` | `/v1/auth/login` | No | 5 req/min per IP | Perform password login (triggers MFA redirection if enabled) |
| `POST` | `/v1/auth/login/mfa` | No | 5 req/min per IP | MFA login with temp token + TOTP code |
| `POST` | `/v1/auth/logout` | Yes (User/Admin) | - | Revoke sessions, blacklist refresh token, clear cookies |
| `POST` | `/v1/auth/refresh` | Yes (User/Admin) | - | Refresh access token |
| `GET` | `/v1/auth/google/login` | No | - | Initiates Google OAuth flow |
| `GET` | `/v1/auth/google/callback` | No | - | Receives Google OAuth authorization callback |
| `POST` | `/v1/auth/add-password` | Yes (User) | - | OAuth-only user sets password |
| `POST` | `/v1/auth/mfa/setup` | Yes (User) | - | Initiates MFA TOTP setup (returns QR code & secret) |
| `POST` | `/v1/auth/mfa/verify-setup` | Yes (User) | - | Verifies TOTP code + enables MFA + returns backup codes |
| `POST` | `/v1/auth/mfa/disable` | Yes (User) | - | Disables MFA (requires password + TOTP) |
| `POST` | `/v1/auth/mfa/admin-reset` | Yes (Admin) | - | Admin resets a user's MFA settings |
| `POST` | `/v1/auth/forgot-password` | No | 3 req/hour per IP | Request password reset email |
| `POST` | `/v1/auth/reset-password` | No | - | Reset password using email token |
| `POST` | `/v1/auth/change-password` | Yes (User) | - | Authenticated password change (requires old password + TOTP) |
| `GET` | `/v1/auth/me` | Yes (User/Admin) | - | Fetch current session info |
| `POST` | `/v1/auth/mfa-recovery-request`| No | - | Request MFA recovery (manual admin review) |
| **Users Profile** | | | | |
| `GET` | `/v1/users/me/profile` | Yes (User) | - | Get profile and live bias scores |
| `PUT` | `/v1/users/me/profile` | Yes (User) | - | Update non-sensitive profile (name, goal, strategy) |
| `PUT` | `/v1/users/me/profile/sensitive` | Yes (User) | - | Update sensitive fields (requires re-verification) |
| `GET` | `/v1/users/me/export` | Yes (User) | - | GDPR compliance: export user data |
| `POST` | `/v1/users/me/delete` | Yes (User) | - | Soft delete user account (30-day grace period) |
| `POST` | `/v1/users/me/cancel-deletion` | Yes (User) | - | Cancel scheduled account deletion |
| **Financial Decisions** | | | | |
| `POST` | `/v1/decisions/analyze` | Yes (User) | 10 req/min | Submit decision for async AI pipeline analysis (returns `decision_id` & `job_id`) |
| `POST` | `/v1/decisions/batch` | Yes (User) | - | Analyze a batch of historical decisions |
| `GET` | `/v1/decisions/my` | Yes (User) | - | Get paginated decision history |
| `GET` | `/v1/decisions/{id}/result` | Yes (User) | - | Get completed decision details (SHAP, simulator stats, opportunity cost) |
| `GET` | `/v1/decisions/{id}/stream` | Yes (User) | - | SSE connection to stream pipeline progress |
| **Simulations** | | | | |
| `POST` | `/v1/simulate` | Yes (User) | 5 req/min | Compare HOLD vs SELL 20-year Monte Carlo trajectories |
| `POST` | `/v1/simulate/individual` | Yes (User) | 5 req/min | Run single-path simulation |
| `GET` | `/v1/simulate/validate/{id}` | Yes (User) | - | Validate simulation vs synthetic counterfactuals |
| `GET` | `/v1/simulate/bias_impact` | Yes (User) | - | Retrieve cohort bias impact statistics |
| **Audit Trails** | | | | |
| `GET` | `/v1/audit/{decision_id}` | Yes (User) | - | Fetch decision audit logs + client-side hash verification |
| **Market Data** | | | | |
| `GET` | `/v1/market/context` | No | 30 req/min | Fetch current NIFTY indices, India VIX, volatility & fear proxy |
| `GET` | `/v1/market/ribbon` | No | 30 req/min | Fetch top-bar index values & 1d changes |
| **Portfolio & SIPs** | | | | |
| `GET` | `/v1/portfolio` | Yes (User) | - | Get current portfolio holdings |
| `POST` | `/v1/portfolio` | Yes (User) | - | Add manual holding |
| `PUT` | `/v1/portfolio/{id}` | Yes (User) | - | Edit holding quantity/avg price |
| `DELETE`| `/v1/portfolio/{id}` | Yes (User) | - | Remove holding |
| `GET` | `/v1/sip` | Yes (User) | - | Get registered SIPs |
| `POST` | `/v1/sip` | Yes (User) | - | Add SIP registration |
| `PUT` | `/v1/sip/{id}` | Yes (User) | - | Toggle SIP status (active/paused) |
| `DELETE`| `/v1/sip/{id}` | Yes (User) | - | Remove SIP registration |
| **Zerodha Kite Integration** | | | | |
| `GET` | `/v1/kite/connect` | Yes (User) | - | Initiates Zerodha OAuth |
| `GET` | `/v1/kite/callback` | Yes (User) | - | Completes Kite OAuth & exchanges request token |
| `POST` | `/v1/kite/sync` | Yes (User) | - | Triggers daily sync of Zerodha portfolio holdings |
| **Admin Panel** | | | | |
| `GET` | `/v1/admin/users` | Yes (Admin) | - | Get paginated list of users metadata |
| `GET` | `/v1/admin/users/{id}` | Yes (Admin) | - | Get user metadata |
| `POST` | `/v1/admin/users/{id}/activate` | Yes (Admin) | - | Activate user |
| `POST` | `/v1/admin/users/{id}/deactivate` | Yes (Admin) | - | Deactivate user |
| `POST` | `/v1/admin/users/{id}/reset-password` | Yes (Admin) | - | Sends user a password reset mail |
| `POST` | `/v1/admin/users/{id}/reset-mfa` | Yes (Admin) | - | Reset user MFA (requires admin's own TOTP verification) |
| `DELETE`| `/v1/admin/users/{id}` | Yes (Admin) | - | Hard delete user after 30-day soft-delete grace period |
| `GET` | `/v1/admin/stats` | Yes (Admin) | - | Fetch global stats from `admin_stats_view` (aggregated) |
| `POST` | `/v1/admin/ml/retrain` | Yes (Admin) | - | Trigger offline model retraining |
| `GET` | `/v1/admin/ml/metrics` | Yes (Admin) | - | Retrieve model accuracy/F1 performance history |
| `GET` | `/v1/admin/mfa-recovery` | Yes (Admin) | - | View pending manual MFA recovery tickets |
| `POST` | `/v1/admin/mfa-recovery/{id}/resolve` | Yes (Admin) | - | Approve and resolve recovery request |

---

## 10. Consolidated Pydantic Schemas [NEW]

```python
# pydantic_schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime

# --- AUTH SCHEMAS ---

class UserRegistrationInput(BaseModel):
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="Strong user password")
    name: str = Field(..., description="Full name")
    age: int = Field(..., ge=18, le=100)
    monthly_income: float = Field(..., ge=0)
    monthly_expense: float = Field(..., ge=0)
    risk_tolerance: float = Field(..., ge=0.0, le=1.0)
    investment_horizon: int = Field(..., ge=1)
    has_emergency_fund: bool = Field(False)
    financial_strategy: str = Field("moderate")
    goal: Optional[str] = None
    phone: Optional[str] = Field(None, description="Optional phone number for WhatsApp alerts")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MfaLoginRequest(BaseModel):
    temp_token: str
    totp_code: str

class MfaVerifySetupRequest(BaseModel):
    totp_code: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class MfaRecoveryRequestInput(BaseModel):
    email: EmailStr
    message: str

# --- PROFILE SCHEMAS ---

class ProfileUpdateRequest(BaseModel):
    name: str
    goal: Optional[str] = None
    financial_strategy: Optional[str] = None

class SensitiveProfileUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    monthly_income: Optional[float] = None
    monthly_expense: Optional[float] = None
    has_emergency_fund: Optional[bool] = None
    password: str = Field(..., description="Verification password to confirm sensitive changes")
    totp_code: Optional[str] = Field(None, description="TOTP verification code if MFA is enabled")

# --- DECISION SCHEMAS ---

class DecisionInput(BaseModel):
    symbol: str = Field(..., description="Stock or Asset symbol (e.g. RELIANCE)")
    exchange: str = Field("NSE", description="NSE or BSE")
    holding_quantity: int = Field(..., gt=0)
    avg_buy_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    unrealized_pnl_pct: float = Field(..., description="e.g. -0.1832 = -18.32%")
    decision_intent: str = Field(..., description="sell | hold | buy_more")
    user_reasoning: Optional[str] = None
    holding_period_days: Optional[int] = None

class BatchInput(BaseModel):
    decisions: List[DecisionInput]

# --- SIMULATION SCHEMAS ---

class SimulateInput(BaseModel):
    user_id: str
    current_wealth: float = Field(..., gt=0)
    unrealized_gl: float = Field(..., ge=-1.0)
    n_simulations: int = Field(1000, ge=100, le=5000)

class SimulateIndividualInput(BaseModel):
    user_id: str
    decision: str = Field(..., description="hold | sell")
    current_portfolio: float = Field(..., gt=0)
    unrealized_gl: float = Field(...)
    n_simulations: int = Field(500, ge=100, le=5000)

# --- PORTFOLIO & SIP SCHEMAS ---

class PortfolioHoldingInput(BaseModel):
    symbol: str
    exchange: str = "NSE"
    quantity: float = Field(..., gt=0)
    buy_price: float = Field(..., gt=0)
    buy_date: Optional[date] = None
    asset_type: str = "equity"

class SipInput(BaseModel):
    symbol: str
    monthly_amount: float = Field(..., gt=0)
    deduction_date: int = Field(..., ge=1, le=28)
    is_active: bool = True
```
