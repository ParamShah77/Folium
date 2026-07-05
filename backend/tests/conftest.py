"""Pytest fixtures for the auth suite.

Provisions an isolated test environment against the local compose stack:

  * A dedicated ``finai_test`` database on the compose Postgres. It is created
    (if missing) and migrated to head via Alembic once per session. Migrations
    run through psycopg2 DIRECTLY against Postgres (see env.py), so point
    ``TEST_DATABASE_URL`` at Postgres directly (default host port 5432).
  * A dedicated Redis DB index (default 15) that is flushed before each test so
    blacklist / token / csrf keys never leak between tests.
  * A per-test ``clean_db`` fixture that TRUNCATEs the mutable tables so each
    test starts from an empty schema without re-running migrations.
  * An ``httpx.AsyncClient`` bound to the ASGI app via lifespan, with the app's
    pool/redis pointed at the test datastores. Rate limiting is disabled by
    default (RATE_LIMIT_ENABLED=false) and re-enabled only by the rate-limit test.

Environment overrides (all optional; sensible localhost defaults):
    TEST_DATABASE_URL   postgresql://finai:finai@localhost:5432/finai_test
    TEST_REDIS_URL      redis://localhost:6379/15

Requires the compose stack up (postgres + redis) and dev keys present in .env
(scripts/generate_dev_keys.py). If keys are absent, a throwaway RSA + Fernet key
is generated for the test process so the suite can still run.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

_REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Environment setup — MUST run before backend.config is imported.
# --------------------------------------------------------------------------- #
_ADMIN_DEFAULT = "postgresql://finai:finai@localhost:5432/postgres"
_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql://finai:finai@localhost:5432/finai_test"
)
_TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")


def _ensure_keys() -> None:
    """Load keys from .env if present; otherwise mint throwaway ones."""
    # Let pydantic-settings read .env for real key material first.
    from dotenv import dotenv_values

    env_path = _REPO_ROOT / ".env"
    values = dotenv_values(env_path) if env_path.exists() else {}

    for key in ("JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY", "FERNET_KEY"):
        if not os.getenv(key) and values.get(key):
            os.environ[key] = values[key]

    if not (os.getenv("JWT_PRIVATE_KEY") and os.getenv("JWT_PUBLIC_KEY")):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        os.environ["JWT_PRIVATE_KEY"] = k.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        os.environ["JWT_PUBLIC_KEY"] = (
            k.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
    if not os.getenv("FERNET_KEY"):
        from cryptography.fernet import Fernet

        os.environ["FERNET_KEY"] = Fernet.generate_key().decode()


os.environ["ENV"] = "development"
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["REDIS_URL"] = _TEST_REDIS_URL
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("RESEND_API_KEY", "")  # force dev email fallback
_ensure_keys()


# --------------------------------------------------------------------------- #
# Session-scoped: create + migrate the test database.
# --------------------------------------------------------------------------- #
def _create_test_database() -> None:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    admin_url = os.getenv("TEST_ADMIN_DATABASE_URL", _ADMIN_DEFAULT)
    db_name = _TEST_DB_URL.rsplit("/", 1)[-1]

    conn = psycopg2.connect(admin_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
                )
    finally:
        conn.close()


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    ini_path = _REPO_ROOT / "backend" / "db" / "migrations" / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent))
    # env.py honours ALEMBIC_DATABASE_URL; point it at the test DB (direct).
    os.environ["ALEMBIC_DATABASE_URL"] = _TEST_DB_URL
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    _create_test_database()
    _run_migrations()
    yield


# --------------------------------------------------------------------------- #
# Per-test isolation: truncate tables + flush the test Redis index.
# --------------------------------------------------------------------------- #
_MUTABLE_TABLES = (
    "profile_change_log",
    "audit_logs",
    "sip_registrations",
    "portfolios",
    "kite_tokens",
    "bias_profiles",
    "mfa_recovery_requests",
    "mfa_backup_codes",
    "refresh_tokens",
    "decisions",
    "users",
)


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    """Wipe DB rows + the test Redis index before each test."""
    import asyncpg
    import redis.asyncio as aioredis

    conn = await asyncpg.connect(_TEST_DB_URL, statement_cache_size=0)
    try:
        # RLS is FORCEd on some tables; TRUNCATE is a table-level op unaffected
        # by row policies, so this clears them regardless of the GUC.
        await conn.execute(
            "TRUNCATE " + ", ".join(_MUTABLE_TABLES) + " RESTART IDENTITY CASCADE"
        )
    finally:
        await conn.close()

    r = aioredis.from_url(_TEST_REDIS_URL, decode_responses=True)
    try:
        await r.flushdb()
    finally:
        await r.aclose()
    yield


# --------------------------------------------------------------------------- #
# App + HTTP client.
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def app():
    """Fresh app instance with lifespan run (opens pool + redis)."""
    from backend.config import get_settings
    from backend.main import create_app

    get_settings.cache_clear()  # re-read env each session start
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app):
    """httpx AsyncClient bound to the ASGI app."""
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac


# --------------------------------------------------------------------------- #
# Helpers shared across tests.
# --------------------------------------------------------------------------- #
STRONG_PASSWORD = "Tr0ub4dour&3xplosion!parrot"


@pytest_asyncio.fixture
async def redis_conn():
    """Direct handle to the test Redis index (to pull verify/reset tokens)."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(_TEST_REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


@pytest_asyncio.fixture
async def db_conn():
    """Direct asyncpg handle to the test DB (assertions / seeding)."""
    import asyncpg

    conn = await asyncpg.connect(_TEST_DB_URL, statement_cache_size=0)
    try:
        yield conn
    finally:
        await conn.close()
