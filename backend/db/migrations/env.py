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

# Resolve the sync (psycopg2) URL. An explicit ALEMBIC_DATABASE_URL wins so the
# test harness / CI can point migrations at a scratch database.
_settings = get_settings()
_url = os.getenv("ALEMBIC_DATABASE_URL")
if _url:
    if _url.startswith("postgresql://"):
        _url = "postgresql+psycopg2://" + _url[len("postgresql://") :]
    elif _url.startswith("postgres://"):
        _url = "postgresql+psycopg2://" + _url[len("postgres://") :]
else:
    _url = _settings.sync_database_url()

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
