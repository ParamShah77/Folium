"""Shared profile_change_log writer.

profile_change_log is RLS-protected (§2E), so every insert goes through
``Database.rls_transaction`` (Amendment 9). Old values are stored as SHA-256
hashes — never plaintext (§2C: ``old_value_hash``).

For admin actions the GUC is set to the TARGET user's id (the row belongs to the
target; ``changed_by`` records the admin).
"""
from __future__ import annotations

import hashlib
from typing import Optional

from ..db import Database


def hash_old_value(value: object) -> Optional[str]:
    """SHA-256 hex of the old value's string form (None stays None)."""
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


async def log_profile_change(
    db: Database,
    user_id: str,
    field: str,
    verified_via: str,
    old_value: object = None,
    changed_by: Optional[str] = None,
) -> None:
    async with db.rls_transaction(user_id) as conn:
        await conn.execute(
            """
            INSERT INTO profile_change_log
                (user_id, field_changed, old_value_hash, verified_via, changed_by)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            field,
            hash_old_value(old_value),
            verified_via,
            changed_by,
        )
