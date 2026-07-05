"""Row-Level Security tests (§2E, Amendment 9).

These exercise the DB layer directly (not via HTTP) to prove that:
  * the ``rls_transaction`` helper sets ``app.current_user_id`` so a user sees
    only their own rows, and
  * an UNSET GUC denies rather than errors (NULLIF(..., '') design).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _make_user(conn, email: str) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO users (email, name, is_active, email_verified) "
            "VALUES ($1, $2, TRUE, TRUE) RETURNING user_id",
            email,
            "RLS User",
        )
    )


async def test_rls_isolates_rows_between_users(app, db_conn):
    """Two users insert portfolios; each sees only their own under RLS."""
    from backend.state import get_database

    db = get_database()

    # Seed two users (users table is not RLS-protected).
    uid_a = await _make_user(db_conn, "rls-a@example.com")
    uid_b = await _make_user(db_conn, "rls-b@example.com")

    # Insert a portfolio row for each, each inside its own RLS transaction.
    async with db.rls_transaction(uid_a) as conn:
        await conn.execute(
            "INSERT INTO portfolios (user_id, symbol, quantity, avg_buy_price) "
            "VALUES ($1, 'AAA', 10, 100.0)",
            uid_a,
        )
    async with db.rls_transaction(uid_b) as conn:
        await conn.execute(
            "INSERT INTO portfolios (user_id, symbol, quantity, avg_buy_price) "
            "VALUES ($1, 'BBB', 20, 200.0)",
            uid_b,
        )

    # User A sees only AAA.
    async with db.rls_transaction(uid_a) as conn:
        rows = await conn.fetch("SELECT symbol FROM portfolios")
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"AAA"}

    # User B sees only BBB.
    async with db.rls_transaction(uid_b) as conn:
        rows = await conn.fetch("SELECT symbol FROM portfolios")
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"BBB"}


async def test_rls_unset_guc_denies_all(app, db_conn):
    """With the GUC unset (user_id=None), the policy denies all rows (no error)."""
    from backend.state import get_database

    db = get_database()
    uid = await _make_user(db_conn, "rls-c@example.com")
    async with db.rls_transaction(uid) as conn:
        await conn.execute(
            "INSERT INTO portfolios (user_id, symbol, quantity, avg_buy_price) "
            "VALUES ($1, 'CCC', 5, 50.0)",
            uid,
        )

    # None -> GUC set to '' -> NULLIF('','') = NULL -> predicate NULL -> deny.
    async with db.rls_transaction(None) as conn:
        rows = await conn.fetch("SELECT symbol FROM portfolios")
    assert rows == []
