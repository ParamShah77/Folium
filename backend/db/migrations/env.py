"""Alembic migration environment.

WHY SYNC / DIRECT POSTGRES (not asyncpg through PgBouncer):
  Migrations are DDL run once at deploy. Alembic's tooling is synchronous, and
  DDL must NOT go through PgBouncer's transaction pooler (session-level
  statements like CREATE ROLE / ALTER ... ENABLE RLS and multi-statement
  transactions behave incorrectly under transaction pooling). So env.py uses a
  plain psycopg2 connection straight to Postgres. Point DATABASE_URL at
  Postgres directly (host port 5432) when running Alembic — see .env.example
  and SETUP.md. The app runtime still uses asyncpg through PgBouncer (§2A).

These migrations are hand-written (no autogenerate / SQLAlchemy models) so the
exact §2C DDL — CHECK constraints, RULEs, RLS policies, the admin view — is
reproduced verbatim.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the repo root importable so ``backend.config`` resolves.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.config import get_settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve the sync (psycopg2) URL.
#
# Migrations MUST connect as the owner/superuser `finai` DIRECT to Postgres
# (not through PgBouncer, not as app_user): they CREATE ROLE, ENABLE RLS, etc.
# The app's DATABASE_URL now points at app_user-through-PgBouncer, so we do NOT
# fall back to it — that would run DDL through the transaction pooler as a role
# without the required privileges. Instead we REQUIRE ALEMBIC_DATABASE_URL to be
# set explicitly (scripts/dev-env.ps1 / SETUP.md do this), and only fall back to
# Settings.sync_database_url() when it is clearly a `finai` direct URL.
_settings = get_settings()
_raw = os.getenv("ALEMBIC_DATABASE_URL")
if not _raw:
    _candidate = _settings.sync_database_url()
    if "app_user" in _candidate or ":6432/" in _candidate:
        raise RuntimeError(
            "ALEMBIC_DATABASE_URL is not set and DATABASE_URL points at "
            "app_user/PgBouncer. Migrations must run as `finai` DIRECT to "
            "Postgres. Set ALEMBIC_DATABASE_URL, e.g.\n"
            "  postgresql://finai:finai@localhost:5433/finai\n"
            "(scripts/dev-env.ps1 sets this for you)."
        )
    _raw = _candidate

_url = _raw
if _url.startswith("postgresql://"):
    _url = "postgresql+psycopg2://" + _url[len("postgresql://") :]
elif _url.startswith("postgres://"):
    _url = "postgresql+psycopg2://" + _url[len("postgres://") :]

config.set_main_option("sqlalchemy.url", _url)

target_metadata = None  # hand-written migrations; no autogenerate


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
