"""Run a command with the project's ``.env`` loaded into the environment.

Alembic's ``env.py`` and migration 0007 read ``ALEMBIC_DATABASE_URL`` and
``APP_DB_PASSWORD`` with ``os.getenv`` and never load ``.env`` themselves, and
the test suite's ``conftest.py`` reads its ``TEST_*`` URLs the same way. This
wrapper exports ``.env`` first, so secrets stay in that file and never have to
be typed into a shell, where they would end up in history.

It also derives the test-suite URLs from the native (Docker-free) setup when
they aren't set explicitly:

    TEST_ADMIN_DATABASE_URL  <- ALEMBIC_DATABASE_URL, database 'postgres'
    TEST_DATABASE_URL        <- ALEMBIC_DATABASE_URL, database 'finai_test'
    TEST_APP_DATABASE_URL    <- DATABASE_URL,         database 'finai_test'
    TEST_REDIS_URL           <- REDIS_URL,            db index 15

Usage:
    python scripts/with_env.py -m alembic -c backend/db/migrations/alembic.ini upgrade head
    python scripts/with_env.py -m pytest backend/tests -q
    python scripts/with_env.py -m uvicorn backend.main:app --port 8000
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def _with_path(url: str, path: str) -> str:
    """Return ``url`` with its path (database name / redis db index) replaced."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def build_env() -> dict[str, str]:
    env = dict(os.environ)
    for key, value in dotenv_values(ROOT / ".env").items():
        if value is not None and key not in env:
            env[key] = value

    admin = env.get("ALEMBIC_DATABASE_URL")
    app = env.get("DATABASE_URL")
    redis = env.get("REDIS_URL")
    if admin:
        env.setdefault("TEST_ADMIN_DATABASE_URL", _with_path(admin, "/postgres"))
        env.setdefault("TEST_DATABASE_URL", _with_path(admin, "/finai_test"))
    if app:
        env.setdefault("TEST_APP_DATABASE_URL", _with_path(app, "/finai_test"))
    if redis:
        env.setdefault("TEST_REDIS_URL", _with_path(redis, "/15"))
    return env


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return subprocess.call([sys.executable, *sys.argv[1:]], cwd=ROOT, env=build_env())


if __name__ == "__main__":
    raise SystemExit(main())
