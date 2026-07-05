"""asyncpg connection pool + per-request RLS transaction helper.

CRITICAL (§2A): ``statement_cache_size=0`` is REQUIRED because the app connects
through PgBouncer in transaction-pooling mode, which cannot route asyncpg's
named prepared statements (``prepared statement "..." already exists`` under load).

RLS mechanics (Amendment 9): user-owned queries run inside an explicit
transaction that first calls
    SELECT set_config('app.current_user_id', $1::text, true)
so the ``USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)``
policies resolve. ``set_config(..., is_local => true)`` is transaction-scoped and,
unlike ``SET LOCAL x = $1``, accepts a bind parameter.
"""
from __future__ import annotations

import contextlib
from typing import AsyncIterator, Optional

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


def _normalize_asyncpg_dsn(dsn: str) -> str:
    """asyncpg wants a bare ``postgresql://`` DSN (no SQLAlchemy driver suffix)."""
    if dsn.startswith("postgresql+"):
        dsn = "postgresql://" + dsn.split("://", 1)[1]
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return dsn


async def create_db_pool(dsn: str) -> asyncpg.Pool:
    """Create the asyncpg pool with PgBouncer-safe settings (§2A)."""
    pool = await asyncpg.create_pool(
        dsn=_normalize_asyncpg_dsn(dsn),
        statement_cache_size=0,  # REQUIRED for PgBouncer transaction mode
        min_size=2,
        max_size=10,
        command_timeout=30.0,
    )
    logger.info("db_pool_created", min_size=2, max_size=10)
    return pool


class Database:
    """Thin wrapper around an asyncpg pool with convenience query methods.

    Two access patterns:
      * ``fetch`` / ``fetchrow`` / ``fetchval`` / ``execute`` — for NON user-owned
        queries (auth lookups by email, token tables, etc.). These acquire a
        connection from the pool directly.
      * ``rls_transaction(user_id)`` — an async context manager that opens an
        explicit transaction, sets ``app.current_user_id`` for the duration, and
        yields the connection. ALL access to RLS-protected tables (decisions,
        audit_logs, portfolios, sip_registrations, profile_change_log) must go
        through this so the policies resolve (Amendment 9).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @property
    def pool(self) -> asyncpg.Pool:
        return self._pool

    # -- Direct (non-RLS) helpers ------------------------------------- #
    async def fetch(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args) -> str:
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    # -- RLS-scoped transaction (Amendment 9) ------------------------- #
    @contextlib.asynccontextmanager
    async def rls_transaction(
        self, user_id: Optional[str]
    ) -> AsyncIterator[asyncpg.Connection]:
        """Yield a connection inside a transaction with the RLS GUC set.

        ``user_id`` may be ``None`` (e.g. admin-context reads that legitimately
        need an unset GUC) — the policies then deny all user-owned rows because
        ``NULLIF('', '')`` is NULL.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.current_user_id', $1::text, true)",
                    str(user_id) if user_id is not None else "",
                )
                yield conn

    async def close(self) -> None:
        await self._pool.close()
        logger.info("db_pool_closed")
