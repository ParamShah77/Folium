"""Anonymise accounts whose 30-day deletion grace period has ended (Phase B2).

The API does this every few hours on its own (ACCOUNT_PURGE_INTERVAL_SECONDS);
this runs it once, now.

    D:/FolioEnv/venv313/Scripts/python.exe scripts/with_env.py scripts/purge_deleted_accounts.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import get_settings  # noqa: E402
from backend.db import Database, create_db_pool  # noqa: E402
from backend.services.account_deletion import purge_due_accounts  # noqa: E402


async def main() -> int:
    pool = await create_db_pool(get_settings().DATABASE_URL)
    try:
        n = await purge_due_accounts(Database(pool))
        print(f"anonymised {n} account(s) whose grace period had ended")
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
