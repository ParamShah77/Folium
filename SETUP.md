# FinAI Backend — Local Setup (Milestones 1+2)

This is a **step-by-step runbook** for bringing up the backend (Milestones 1+2) on your
own machine (Windows 11 + PowerShell). It assumes you have **never used Docker,
PostgreSQL, Redis, or Alembic before**, so each step explains *what* the command
does, *why*, what a *successful* result looks like, and *what to do if it fails*.

Run every command from the repository root:
`C:\Users\Lenovo\Desktop\MajorProject-ScaleLevel`

> **Mental model of the stack**
> - **Docker** runs three small "containers" (mini virtual machines): **PostgreSQL**
>   (the database that stores users, tokens, decisions), **Redis** (a fast
>   in-memory store for short-lived things like email-verification tokens and the
>   token blacklist), and **PgBouncer** (a connection pooler that sits in front of
>   PostgreSQL).
> - **Alembic** is a "migration" tool: it runs versioned SQL scripts that build the
>   database tables. You run it once to create the schema.
> - **The backend** is a FastAPI (Python) web server. It exposes the authentication
>   API (`/v1/auth/*` — email/password, TOTP MFA, Google OAuth), profile management
>   (`/v1/users/me/*`), the admin MFA reset (`/v1/admin/*`), and a `/health` check.

> **Two database roles — this is a SECURITY design, not a detail.**
> The database has two login roles and they are used on purpose:
> - **`finai`** is the PostgreSQL **superuser** (it owns everything). It is used for
>   *admin* work: creating databases, **running migrations**, and the test suite's
>   direct setup/cleanup. Superusers can do anything — including **bypassing**
>   Row-Level Security (RLS).
> - **`app_user`** is a **non-superuser** login role created by migration `0007`. The
>   **running app** connects as `app_user` (through PgBouncer). This is *required*:
>   RLS — the per-user data isolation that stops one user reading another's rows — is
>   **silently bypassed by superusers**. So the app must NOT connect as `finai`, or
>   the isolation guarantee would not actually hold. Its password is `app_user` for
>   local dev (set by `APP_DB_PASSWORD`).
>
> One-line takeaway: **migrations run as `finai`; the app runs as `app_user`.**

> **Ports on this machine.** The Docker Postgres is published on host port **5433**
> (not the usual 5432) so it can coexist with any locally-installed PostgreSQL that
> already uses 5432. PgBouncer is on **6432**, Redis on **6379**. Inside Docker the
> containers still talk to Postgres on 5432 — only *host-side* tools (Alembic run
> from your machine, pytest) use 5433.

Two Python interpreters are involved. That's normal:
- **Host Python 3.13** (on your machine) — used to generate keys and, if you like,
  to run migrations and tests directly. A dedicated virtualenv lives at
  `backend\.venv`.
- **Container Python 3.11** — used *inside* the Docker `backend` service. You don't
  interact with it directly.

---

## Step 0 — One-time: create the backend Python environment

You need a Python environment with the backend's libraries installed (for the
key-generator, migrations, and tests when run from the host).

```powershell
py -3.13 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

**What/why:** creates an isolated set of Python packages so the backend's
dependencies don't collide with the prototype's. **Success:** the last command ends
with `Successfully installed fastapi-... uvicorn-... asyncpg-...`. **If it fails:**
make sure Python 3.13 is installed (`py -3.13 --version`); if `py` is missing, use
`python -m venv backend\.venv` with a Python 3.11–3.13 on PATH.

---

## Step 1 — Load the dev environment variables (do this in every new shell)

The project ships a helper that sets `$PY` (the venv Python) and the database URLs
that Alembic and the tests use. **Dot-source** it (note the leading `. ` — a dot,
then a space) so the variables land in your *current* shell:

```powershell
. .\scripts\dev-env.ps1
```

**What/why:** exports `ALEMBIC_DATABASE_URL`, `TEST_DATABASE_URL`,
`TEST_APP_DATABASE_URL`, `TEST_ADMIN_DATABASE_URL`, and `APP_DB_PASSWORD` (all
pointing at the Docker Postgres on host port **5433**), and sets `$PY`. **Success:**
it prints "Dev env loaded:" and the URLs. **If it fails** with "running scripts is
disabled," allow local scripts for this session:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and re-run.

> Re-run this dot-source **every time you open a new PowerShell window** — env vars
> don't persist across shells. Everywhere below, `$PY` means the venv Python it set.

---

## Step 2 — Verify Docker Desktop is installed and running

```powershell
docker --version
docker compose version
```

**What/why:** confirms Docker (the container engine) and Docker Compose (the tool
that starts several containers together from `docker-compose.yml`) are available.
**Success:** two version lines, e.g. `Docker version 29.x` and
`Docker Compose version v2.x`. **If it fails:** install **Docker Desktop for
Windows**, launch it, and wait until the tray icon says "Docker Desktop is running."

---

## Step 3 — Generate local dev keys and create your `.env`

The backend needs three secrets: an RSA key **pair** to sign/verify JWT login
tokens, and a **Fernet** key to encrypt sensitive data at rest. This script creates
them and writes them into a `.env` file (seeded from `.env.example`).

```powershell
& $PY scripts\generate_dev_keys.py
```

**What/why:** produces `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, and `FERNET_KEY` and
saves them to `.env`. `.env` is **gitignored** — never commit it. **Success:** prints
`wrote JWT_PRIVATE_KEY` etc., then `.env updated`. **If it fails** saying keys already
exist, that's fine — they're kept (use `--force` to rotate, which logs everyone out).

> Open `.env` and skim it. The `DATABASE_URL` there points at **app_user** through
> PgBouncer (`postgresql://app_user:app_user@localhost:6432/finai`) — that's the app's
> connection and it's correct. `RESEND_API_KEY` is intentionally blank: in development
> the app **prints** verification/reset emails to its log instead of sending them
> (Amendment 6), so you can test the flow with no email account.

---

## Step 4 — Start the infrastructure (PostgreSQL, Redis, PgBouncer)

```powershell
docker compose up -d postgres redis pgbouncer
docker compose ps
```

**What/why:** `up -d` creates and starts the three containers in the background. The
first run **downloads** the images (a minute or two); later runs are instant.
**Success:** `docker compose ps` shows `postgres` and `redis` as `Up ... (healthy)`
and `pgbouncer` as `Up`. ("healthy" = it passed its built-in check; PgBouncer has no
check here, so plain `Up` is expected and correct.)

**If it fails:**
- *"port is already allocated"* — something else uses 5433 / 6379 / 6432. Stop it, or
  change the host port on the left of the `ports:` mapping in `docker-compose.yml`.
- *Cannot connect to the Docker daemon* — Docker Desktop isn't running (Step 2).
- Containers restart-looping — view logs: `docker compose logs postgres`.

> **Heads-up about PgBouncer:** it authenticates to Postgres as `app_user`, which
> **doesn't exist until you run migrations** (Step 5). PgBouncer connects *lazily*
> (only on the first query), so this is fine — just migrate before you hit the app.

---

## Step 5 — Create the databases and run the migrations (as `finai`)

Migrations **build the database tables** and create the `app_user` role. They run as
the superuser `finai`, connecting **directly** to Postgres on **5433** (not through
PgBouncer).

> **Why directly, as `finai`?** Migrations do superuser-only things — `CREATE ROLE`,
> enabling Row-Level Security, granting privileges. PgBouncer's transaction pooling
> can't run that kind of session-level SQL, and `app_user` lacks the privileges. So
> migrations always go straight to Postgres as `finai`. (`ALEMBIC_DATABASE_URL`,
> already set by Step 1, points there.)

**5a. Create the two databases** — the main `finai` was created by compose; add the
test database:

```powershell
docker compose exec postgres createdb -U finai finai_test
```

**What/why:** runs `createdb` inside the postgres container as `finai`. **Success:**
no output. **If it says "already exists,"** that's fine.

**5b. Apply the schema to the main `finai` database:**

```powershell
& $PY -m alembic -c backend\db\migrations\alembic.ini upgrade head
```

**What/why:** runs migrations `0001` → `0007` in order — all tables, indexes, the
append-only audit rules, the **`app_user` role**, the **RLS policies**, the grants
`app_user` needs, and the admin view. **Success:** output ends with
`Running upgrade ... -> 0007_create_rls_policies`. Re-running is safe (nothing to do
if already at head). **If it fails:**
- *"ALEMBIC_DATABASE_URL is not set..."* — you skipped Step 1; dot-source
  `dev-env.ps1` and retry.
- *"could not connect"* — Postgres isn't up (Step 4), or the host port isn't 5433.
- *"password authentication failed"* — the URL must use `finai:finai`.

*(You do **not** need to migrate `finai_test` yourself — the test suite in Step 6
creates and migrates it automatically. Migrating `finai` above is what lets you
inspect real tables in Step 7 and run the app.)*

---

## Step 6 — Run the backend test suite

The tests exercise the whole auth surface against the **real** local Postgres and
Redis: register → verify → login → refresh → logout, duplicate email, weak password,
login-before-verification, CSRF, password reset, rate limiting, **row-level
security**, `/health` — and the Milestone 2 features: the full **TOTP MFA**
lifecycle (setup → QR secret → backup codes → two-step login → disable), MFA
recovery + the admin reset, **Google OAuth** (all four §1F cases with a mocked
Google exchange — no test ever contacts Google, even with real credentials in
`.env`), and the **sensitive-profile** re-verification flows (password / TOTP /
email-change OTP). The RLS tests connect the app pool as `app_user`, so they
prove the isolation guarantee actually holds.

If you haven't since Milestone 2 landed, install the two new dependencies first
(`pyotp` for TOTP, `Authlib` for OAuth):

```powershell
& $PY -m pip install -r backend\requirements.txt
```

Then run the suite:

```powershell
& $PY -m pytest backend\tests -c backend\pytest.ini
```

**What/why:** the test setup creates `finai_test` (if missing), migrates it, and uses
Redis database index **15** (separate from the app's index 0). The app pool inside the
tests connects as `app_user` (`TEST_APP_DATABASE_URL`); the setup/cleanup uses `finai`
(`TEST_DATABASE_URL`). **Success:** the final line is `===== 43 passed in X.XXs =====`.
**If it fails:**
- *connection refused* — infra isn't up (Step 4) or Step 1 wasn't dot-sourced.
- *permission denied for table ...* — the `finai_test` DB was migrated with an OLD
  `0007`. Re-migrate on a fresh volume (see the box below).
- *the two RLS tests fail (user A sees another user's rows / unset GUC returns rows)*
  — same cause: the app pool is connecting as a superuser. Confirm
  `TEST_APP_DATABASE_URL` uses `app_user` (Step 1 sets it) and that `0007` ran.

> **⚠ Upgrading from an earlier build? Re-migrate on a FRESH volume.**
> Migration `0007` changed (it now makes `app_user` a real login role and grants it
> schema access). If you already had the old schema, wipe the database volume and
> rebuild so the new `0007` runs cleanly:
> ```powershell
> docker compose down -v
> docker compose up -d postgres redis pgbouncer
> . .\scripts\dev-env.ps1
> docker compose exec postgres createdb -U finai finai_test
> & $PY -m alembic -c backend\db\migrations\alembic.ini upgrade head
> & $PY -m pytest backend\tests -c backend\pytest.ini
> ```
> After this, **all 43 tests pass.** (Milestone 2 added no new migrations — the
> MFA/OAuth/profile tables were already in 0001–0007, so no re-migrate is needed
> when coming from a working Milestone 1 schema.)

---

## Step 7 — Look inside what you built

**7a. List the tables in PostgreSQL:**

```powershell
docker compose exec postgres psql -U finai -d finai -c "\dt"
```

**Success:** a listing including `users`, `refresh_tokens`, `decisions`,
`audit_logs`, `portfolios`, `sip_registrations`, `kite_tokens`, `bias_profiles`,
`market_cache`, `mfa_backup_codes`, `mfa_recovery_requests`, `profile_change_log`.

Confirm the `app_user` role and the admin view exist:

```powershell
docker compose exec postgres psql -U finai -d finai -c "\du app_user"
docker compose exec postgres psql -U finai -d finai -c "\dv"
```

**7b. Confirm Redis is alive:**

```powershell
docker compose exec redis redis-cli ping        # -> PONG
docker compose exec redis redis-cli KEYS "*"     # live keys after using the app
```

> **Run the API yourself (optional):** with infra up, migrations done, and `.env` in
> place, start the server and open the docs:
> ```powershell
> & $PY -m uvicorn backend.main:app --reload --port 8000
> ```
> Then visit `http://localhost:8000/health` (should return `{"status":"ok",...}`) and
> the interactive docs at `http://localhost:8000/api/v1/docs`. This app connects as
> `app_user` through PgBouncer — RLS is live.

---

## Step 8 — Shut everything down

```powershell
docker compose down        # stop & remove containers, KEEP data (volume survives)
docker compose down -v     # the same PLUS delete the database data (clean slate)
```

Use `down -v` whenever `0007` (or any migration) changes and you want to re-migrate
from scratch. After `down` (without `-v`), just `docker compose up -d ...` brings your
data back.

---

## Quick reference (once you know the flow)

```powershell
# every new shell
. .\scripts\dev-env.ps1

# start infra
docker compose up -d postgres redis pgbouncer
docker compose ps

# create test DB + migrate the main DB (as finai, direct 5433)
docker compose exec postgres createdb -U finai finai_test
& $PY -m alembic -c backend\db\migrations\alembic.ini upgrade head

# run tests (43 total; RLS tests use app_user, OAuth tests mock Google)
& $PY -m pytest backend\tests -c backend\pytest.ini

# inspect
docker compose exec postgres psql -U finai -d finai -c "\dt"
docker compose exec redis redis-cli ping

# stop (keep data) / wipe data (re-migrate needed after)
docker compose down
docker compose down -v
```

---

## Google OAuth — Cloud Console setup (for live "Sign in with Google")

The test suite never contacts Google (the exchange is mocked), but to try the
real flow in a browser you need an OAuth client:

1. Go to **console.cloud.google.com** → create (or pick) a project.
2. **APIs & Services → OAuth consent screen**: choose **External**, fill in the
   app name + your email, add yourself under **Test users** (while the app is in
   "Testing" mode only listed test users can log in). Scopes: the defaults —
   `openid`, `email`, `profile` — are all this app requests.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URI (must match EXACTLY):
     `http://localhost:8000/v1/auth/google/callback`
   (No "authorized JavaScript origins" needed for this server-side flow.)
4. Copy the **Client ID** and **Client Secret** into `.env` as
   `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`. Leave
   `GOOGLE_OAUTH_REDIRECT_URI` empty in local dev — the backend derives the
   `localhost:8000` callback automatically. (Set it explicitly at deploy time
   when the public URL differs.)
5. Try it: start the API (`& $PY -m uvicorn backend.main:app --reload --port 8000`),
   open `http://localhost:8000/v1/auth/google/login` in a browser, pick your
   Google account, and you should land back on the callback with a JSON body
   containing your new `user` (cookies are set — `GET /v1/auth/me` now works).
   While the credentials are empty, the endpoint returns
   503 "Google login not configured" by design.

## Still optional

- **Resend API key**: only if you want *real* emails in dev. Without it, emails
  (verification links, password resets, email-change OTPs, MFA notices) are
  printed to the server log — enough to develop and test.
