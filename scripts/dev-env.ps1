# ---------------------------------------------------------------------------
# Local dev environment for the FinAI backend (Windows / PowerShell).
#
# DOT-SOURCE this at the start of a dev session so the variables land in your
# current shell (note the leading "dot space"):
#
#     . .\scripts\dev-env.ps1
#
# It sets $PY (the venv Python) plus the database URLs that Alembic and the test
# suite use to connect DIRECTLY to the Docker Postgres. On this machine that
# Postgres is published on host port 5433 (not the usual 5432) so it can coexist
# with a locally-installed PostgreSQL that already occupies 5432.
#
# TWO ROLES (this is a SECURITY requirement, not a convenience):
#   * finai    = POSTGRES_USER (superuser/owner). Used for admin work that must
#                BYPASS RLS: creating the test DB, running migrations, TRUNCATE,
#                and direct test assertions.
#   * app_user = a NON-superuser LOGIN role (created by migration 0007). The
#                APP POOL connects as app_user so Row-Level Security actually
#                binds — a superuser would silently bypass every policy.
#
# The running app connects through PgBouncer on 6432 (as app_user). Only host-
# side tools use these direct-to-Postgres URLs on 5433.
# ---------------------------------------------------------------------------

# Path to the backend virtualenv's Python. Call programs with:  & $PY -m ...
$PY = ".\backend\.venv\Scripts\python.exe"

# Alembic migrations -> finai DIRECT to Docker Postgres (host 5433 -> container 5432).
$env:ALEMBIC_DATABASE_URL    = "postgresql://finai:finai@localhost:5433/finai"

# Test suite (host-run pytest):
#   TEST_DATABASE_URL      finai  -> create/migrate/TRUNCATE + direct asserts
#   TEST_APP_DATABASE_URL  app_user -> the app pool, so RLS binds in tests
#   TEST_ADMIN_DATABASE_URL finai on the maintenance DB, used to CREATE the test DB
$env:TEST_DATABASE_URL       = "postgresql://finai:finai@localhost:5433/finai_test"
$env:TEST_APP_DATABASE_URL   = "postgresql://app_user:app_user@localhost:5433/finai_test"
$env:TEST_ADMIN_DATABASE_URL = "postgresql://finai:finai@localhost:5433/postgres"

# Password migration 0007 assigns to the app_user role (keep in sync with the
# app_user credentials above). Default is fine for local dev.
$env:APP_DB_PASSWORD         = "app_user"

Write-Host "Dev env loaded:" -ForegroundColor Green
Write-Host "  `$PY                   = $PY"
Write-Host "  ALEMBIC_DATABASE_URL  = $env:ALEMBIC_DATABASE_URL  (finai, direct)"
Write-Host "  TEST_DATABASE_URL     = $env:TEST_DATABASE_URL  (finai)"
Write-Host "  TEST_APP_DATABASE_URL = $env:TEST_APP_DATABASE_URL  (app_user -> RLS)"
Write-Host "Postgres (Docker) is on host port 5433; local Postgres keeps 5432."
