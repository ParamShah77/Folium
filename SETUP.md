# FinAI Backend — Local Setup (Milestone 1)

This is a **step-by-step runbook** for bringing up the Milestone 1 backend on your
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
> - **The backend** is a FastAPI (Python) web server. In Milestone 1 it exposes the
>   authentication API (`/v1/auth/*`) and a `/health` check.

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

> Throughout this guide, `PY` means `backend\.venv\Scripts\python.exe`. You can set a
> shortcut for the session: `$PY = "backend\.venv\Scripts\python.exe"` and then call
> `& $PY ...`.

---

## Step 1 — Verify Docker Desktop is installed and running

```powershell
docker --version
docker compose version
```

**What/why:** confirms Docker (the container engine) and Docker Compose (the tool
that starts several containers together from `docker-compose.yml`) are available.
**Success:** you see two version lines, e.g. `Docker version 29.x` and
`Docker Compose version v2.x`. **If it fails:** install **Docker Desktop for
Windows**, launch it, and wait until the whale icon in the system tray says
"Docker Desktop is running." Docker commands fail with a pipe/connection error
when the Desktop app isn't running — start it first.

---

## Step 2 — Generate local dev keys and create your `.env`

The backend needs three secrets: an RSA key **pair** to sign/verify JWT login
tokens, and a **Fernet** key to encrypt sensitive data at rest. This script creates
them and writes them into a `.env` file (seeded from `.env.example`).

```powershell
backend\.venv\Scripts\python.exe scripts\generate_dev_keys.py
```

**What/why:** produces `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, and `FERNET_KEY` and
saves them to `.env`. `.env` is **gitignored** — it holds secrets and must never be
committed. **Success:** prints `wrote JWT_PRIVATE_KEY`, `wrote JWT_PUBLIC_KEY`,
`wrote FERNET_KEY`, then `.env updated`. A `.env` file now exists in the repo root.
**If it fails:** if it says keys already exist, that's fine — they're kept. To
rotate them, run with `--force` (this invalidates any existing logins).

> Open `.env` and skim it. For local dev the defaults are ready to go. Note:
> `RESEND_API_KEY` is intentionally blank — in development the app **prints**
> verification/reset emails to its log instead of sending them (Amendment 6), so you
> can test the flow with no email account.

---

## Step 3 — Start the infrastructure (PostgreSQL, Redis, PgBouncer)

```powershell
docker compose up -d postgres redis pgbouncer
```

**What/why:** `up` creates and starts the three containers; `-d` ("detached") runs
them in the background so your terminal is free. The first run **downloads** the
images (postgres, redis, pgbouncer) — this can take a minute or two. Later runs are
instant. **Success:** you see lines ending in `Started` / `Healthy` for the
containers.

Now check their status:

```powershell
docker compose ps
```

**What/why:** lists the running containers and their health. **Success:** you should
see `postgres` and `redis` with **STATUS** `Up ... (healthy)`, and `pgbouncer` as
`Up`. "healthy" means the container passed its built-in health check (for Postgres,
that the database is accepting connections). PgBouncer has no health check in this
setup, so plain `Up` is expected and correct.

**If it fails:**
- *"port is already allocated" / "bind: address already in use"* — something else on
  your machine is using port 5432 (Postgres), 6379 (Redis), or 6432 (PgBouncer).
  Stop that program, or change the host port on the left side of the `ports:` mapping
  in `docker-compose.yml` (e.g. `"5433:5432"`).
- *Cannot connect to the Docker daemon* — Docker Desktop isn't running (see Step 1).
- Containers restart-looping — view logs: `docker compose logs postgres`.

> **Ports recap:** on your machine, PostgreSQL is reachable at `localhost:5432`,
> PgBouncer at `localhost:6432`, Redis at `localhost:6379`. The app (in Docker) talks
> to Postgres *through* PgBouncer; migrations and tests talk to Postgres **directly**
> on 5432 (explained next).

---

## Step 4 — Create the test database and run the migrations

Migrations are versioned scripts that **build the database tables**. Running them is
how an empty PostgreSQL becomes the FinAI schema (users, refresh_tokens, decisions,
audit_logs with its tamper-proof rules, portfolios, RLS policies, and more).

> **Why "directly" on port 5432, not through PgBouncer (6432)?** PgBouncer pools
> connections in "transaction mode," which doesn't support the session-level SQL that
> creating roles and enabling row-level security need. So migrations use a direct
> Postgres connection. The running app still uses PgBouncer — that's fine because the
> app only runs normal queries.

**4a. Create the two databases.** The compose file already created the main `finai`
database. Create the `finai_test` database used by the test suite:

```powershell
docker compose exec postgres createdb -U finai finai_test
```

**What/why:** runs the `createdb` tool *inside* the postgres container as user
`finai`. **Success:** no output means success. **If it fails** with "already
exists," that's fine — it's already there.

**4b. Point Alembic at the database and upgrade to the latest version.** We set an
environment variable so Alembic connects directly to Postgres on 5432, then run the
upgrade.

Apply the schema to the **main** `finai` database:

```powershell
$env:ALEMBIC_DATABASE_URL = "postgresql://finai:finai@localhost:5432/finai"
backend\.venv\Scripts\python.exe -m alembic -c backend\db\migrations\alembic.ini upgrade head
```

**What/why:** `upgrade head` runs every migration `0001` → `0007` in order, creating
all tables, indexes, the append-only audit rules, the row-level-security policies,
and the admin stats view. **Success:** the output ends with lines like
`Running upgrade ... -> 0007_create_rls_policies`. Running it again is safe and just
prints nothing new (you're already at head). **If it fails:**
- *"could not connect" / "Connection refused"* — Postgres isn't up (redo Step 3) or
  you changed its host port (update the URL above to match).
- *"password authentication failed"* — the credentials in the URL must be
  `finai:finai` (the compose defaults).

> **What just happened, concretely:** you turned an empty database into ~13 tables
> with constraints. `alembic downgrade base` would reverse it all cleanly (drops
> everything). You normally never need that, but it's how migrations stay reversible.

*(The test suite in Step 5 will create/upgrade `finai_test` automatically, so you do
not have to run `upgrade head` against `finai_test` yourself. Applying it to `finai`
above is what lets you inspect real tables in Step 6.)*

---

## Step 5 — Run the backend test suite

The tests exercise the whole auth surface against the **real** local Postgres and
Redis: register → verify → login → refresh → logout, duplicate email, weak password,
login-before-verification, CSRF, password reset, rate limiting, row-level security,
and `/health`.

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -c backend\pytest.ini
```

**What/why:** runs pytest. The test setup automatically creates the `finai_test`
database (if missing), migrates it, and uses Redis database index **15** (kept
separate from the app's index 0) so tests never touch your real data. **Success:**
the final line looks like `===== NN passed in X.XXs =====` with no failures. **If it
fails:**
- *"connection refused" to Postgres/Redis* — infra isn't up (Step 3).
- *"database finai_test does not exist"* and it isn't auto-created — create it
  manually as in Step 4a.
- *A single rate-limit test flakes* — re-run; it depends on timing windows.

> The tests read the JWT/Fernet keys from your `.env`. If `.env` is missing they fall
> back to throwaway keys for the test process, so tests still run — but you should
> have done Step 2 anyway for the app itself.

---

## Step 6 — Look inside what you built

Now *see* the database and cache you created.

**6a. List the tables in PostgreSQL:**

```powershell
docker compose exec postgres psql -U finai -d finai -c "\dt"
```

**What/why:** opens `psql` (the Postgres command-line client) inside the container
and runs `\dt` ("describe tables"). **Success:** a table listing including `users`,
`refresh_tokens`, `decisions`, `audit_logs`, `portfolios`, `sip_registrations`,
`kite_tokens`, `bias_profiles`, `market_cache`, `mfa_backup_codes`,
`mfa_recovery_requests`, `profile_change_log`. (You'll only see rows if you ran the
app or tests against `finai`.)

Try a couple more, to build intuition:

```powershell
# See the columns of the users table:
docker compose exec postgres psql -U finai -d finai -c "\d users"
# Confirm the admin aggregate view exists:
docker compose exec postgres psql -U finai -d finai -c "\dv"
```

**6b. Confirm Redis is alive:**

```powershell
docker compose exec redis redis-cli ping
```

**What/why:** sends a `PING` to Redis. **Success:** it replies `PONG`. To peek at
live keys created by the app (e.g. after a registration), use:

```powershell
docker compose exec redis redis-cli KEYS "*"
```

You might see keys like `email_verify:<token>` (a pending verification),
`blacklist:<jti>` (a revoked token), or `csrf:<user_id>`. **If it fails:** Redis
isn't up — redo Step 3.

> **Run the API yourself (optional):** with infra up and `.env` in place, start the
> server and open the docs:
> ```powershell
> backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
> ```
> Then visit `http://localhost:8000/health` (should return `{"status":"ok",...}`) and
> the interactive API docs at `http://localhost:8000/api/v1/docs`.

---

## Step 7 — Shut everything down

When you're done for the day:

```powershell
docker compose down
```

**What/why:** stops and removes the containers but **keeps your data** (Postgres
stores it in a Docker "volume" that survives). Next time, `docker compose up -d
postgres redis pgbouncer` brings everything back with your data intact.

To wipe the data too (start completely fresh — you'll need to re-run migrations):

```powershell
docker compose down -v
```

**What/why:** the `-v` also deletes the named volumes, so the database is emptied.
Use this if you want a clean slate. **Difference in one line:** `down` = pause &
remove containers (data kept); `down -v` = the same **plus** delete the database
data.

---

## Quick reference (once you know the flow)

```powershell
# start infra
docker compose up -d postgres redis pgbouncer
docker compose ps

# migrate the main DB (one time, or after new migrations)
$env:ALEMBIC_DATABASE_URL = "postgresql://finai:finai@localhost:5432/finai"
backend\.venv\Scripts\python.exe -m alembic -c backend\db\migrations\alembic.ini upgrade head

# run tests
backend\.venv\Scripts\python.exe -m pytest backend\tests -c backend\pytest.ini

# inspect
docker compose exec postgres psql -U finai -d finai -c "\dt"
docker compose exec redis redis-cli ping

# stop (keep data) / stop and wipe data
docker compose down
docker compose down -v
```

---

## Milestone 2 will need from you

- **Google OAuth** credentials: a **Client ID** and **Client Secret** from the Google
  Cloud Console (for "Sign in with Google"). Put them in `.env` as
  `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`.
- **Resend API key** (optional): only if you want *real* emails in dev. Without it,
  emails are printed to the server log — which is enough to develop and test.
