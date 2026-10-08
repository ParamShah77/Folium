"""Download my data, and delete my account (Phase B2).

**Export** (:func:`export_user_data`) gathers everything Folium holds about an
investor into one JSON document: the account and profile, the financial
profile, holdings, every analysis, and their secure record with its
verification. Secrets are left out: the password hash, the two-step secret and
backup codes, session tokens.

**Deletion** happens in two stages:

1. :func:`schedule_deletion` — the investor asks; they're signed out
   everywhere and the account is locked. For ``GRACE_DAYS`` days, logging in
   offers to keep the account (:func:`cancel_deletion`).
2. :func:`purge_due_accounts` — after the grace period the account is
   anonymised. Deleting outright isn't possible: the audit chain is
   append-only and references the analyses, and the user row anchors the
   chain's genesis. So everything that identifies the person or describes
   their money is erased, and what remains is unlinkable:

   * erased: name, email, phone, photo, sign-in links, password, two-step
     secret, age, income, payments, risk answers, goal, the deletion reason;
     the financial profile, holdings, SIPs, broker tokens, sessions, backup
     codes and profile-change history; each analysis's comment, portfolio
     snapshot, explanation, projection and recommendation reasons;
   * kept, unlinked: the user id and creation time (the chain's anchor), the
     audit entries (fingerprints and a summary: stock, action, pattern,
     verdict), and each analysis's stock, action, prices and pattern.

The purge runs every few hours in the API process (``backend/main.py``) and
can be run by hand: ``scripts/purge_deleted_accounts.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from ..api.serialization import jsonable_row
from ..core import audit
from ..db import Database

logger = structlog.get_logger(__name__)

GRACE_DAYS = 30

#: Never exported: credentials and secrets.
_SECRET_USER_FIELDS = frozenset({"password_hash", "mfa_secret_enc", "oauth_id"})

#: Cleared on the users row when an account is anonymised.
_USER_PERSONAL_FIELDS = (
    "password_hash", "oauth_provider", "oauth_id", "mfa_secret_enc", "profile_picture", "phone",
    "age", "monthly_income", "monthly_expense", "risk_tolerance", "investment_horizon",
    "has_emergency_fund", "financial_strategy", "goal", "monthly_emi", "rent_paid",
    "education_monthly", "education_end_year", "last_login_at", "deletion_reason",
)

#: Cleared on each analysis (columns that hold personal text or finances).
_DECISION_PERSONAL_FIELDS = (
    "user_reasoning", "portfolio_context", "explainer_output", "simulation_curves",
    "debate_transcript", "holding_id", "opportunity_cost_inr",
    "hold_median_20y", "hold_p10_20y", "hold_p90_20y",
    "sell_median_20y", "sell_p10_20y", "sell_p90_20y",
)

#: Tables whose rows for the user are removed outright.
_DELETE_TABLES = ("financial_profiles", "portfolios", "sip_registrations", "kite_tokens",
                  "refresh_tokens", "mfa_backup_codes", "profile_change_log", "bias_profiles")


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #

async def export_user_data(db: Database, user_id: str) -> dict[str, Any]:
    user = await db.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    async with db.rls_transaction(user_id) as conn:
        profile = await conn.fetchrow("SELECT * FROM financial_profiles WHERE user_id = $1", user_id)
        holdings = await conn.fetch("SELECT * FROM portfolios WHERE user_id = $1 ORDER BY created_at", user_id)
        decisions = await conn.fetch("SELECT * FROM decisions WHERE user_id = $1 ORDER BY submitted_at", user_id)
        entries, genesis = await audit.load_chain(conn, user_id)
    chain = audit.verify_chain(entries, genesis)
    account = {k: v for k, v in jsonable_row(user).items() if k not in _SECRET_USER_FIELDS}
    by_order = {log_id: i for i, log_id in enumerate(chain["order"])}
    entries.sort(key=lambda e: by_order.get(str(e["log_id"]), len(by_order)))
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "about": (
            "Everything Folium holds about you: your account and profile, your financial profile and "
            "holdings, every analysis, and their secure record. Passwords, two-step secrets and "
            "session tokens are never included. Amounts are in Indian rupees."
        ),
        "account": account,
        "financial_profile": jsonable_row(profile) if profile else None,
        "holdings": [jsonable_row(h) for h in holdings],
        "analyses": [jsonable_row(d) for d in decisions],
        "secure_record": {
            "genesis": genesis,
            "how_to_check": ("Each entry's chain_hash is sha256(previous_hash + payload_hash), and "
                             "payload_hash is sha256 of the payload as compact JSON with sorted keys. The "
                             "first entry links to sha256('GENESIS:{user_id}:{created_at}'), or to 64 zeros "
                             "for records made in the earlier format."),
            "verification": {k: chain[k] for k in ("valid", "entries", "linked", "anchor", "problems")},
            "entries": [jsonable_row(e) for e in entries],
        },
    }


# --------------------------------------------------------------------------- #
# Deletion
# --------------------------------------------------------------------------- #

async def schedule_deletion(db: Database, user_id: str, reason: str | None = None,
                            now: datetime | None = None) -> datetime:
    """Lock the account and schedule the wipe; returns when it will happen."""
    now = now or datetime.now(timezone.utc)
    purge_after = now + timedelta(days=GRACE_DAYS)
    await db.execute(
        """UPDATE users SET deleted_at = $2, purge_after = $3, deletion_reason = $4, updated_at = NOW()
           WHERE user_id = $1 AND anonymised_at IS NULL""",
        user_id, now, purge_after, (reason or "").strip()[:500] or None,
    )
    await db.execute("DELETE FROM refresh_tokens WHERE user_id = $1", user_id)   # signed out everywhere
    logger.info("account_deletion_scheduled", user_id=str(user_id), purge_after=purge_after.isoformat())
    return purge_after


async def cancel_deletion(db: Database, user_id: str) -> bool:
    """Keep the account, if the grace period hasn't ended."""
    result = await db.execute(
        """UPDATE users SET deleted_at = NULL, purge_after = NULL, deletion_reason = NULL, updated_at = NOW()
           WHERE user_id = $1 AND deleted_at IS NOT NULL AND anonymised_at IS NULL AND purge_after > NOW()""",
        user_id,
    )
    kept = result.endswith("1")
    if kept:
        logger.info("account_deletion_cancelled", user_id=str(user_id))
    return kept


async def anonymise_account(db: Database, user_id: str) -> None:
    """Erase everything personal about one account (see the module docstring)."""
    async with db.rls_transaction(user_id) as conn:
        for table in _DELETE_TABLES:
            await conn.execute(f"DELETE FROM {table} WHERE user_id = $1", user_id)
        await conn.execute(
            f"UPDATE decisions SET {', '.join(f'{c} = NULL' for c in _DECISION_PERSONAL_FIELDS)} WHERE user_id = $1",
            user_id,
        )
        await conn.execute(
            "UPDATE mfa_recovery_requests SET email = 'deleted@deleted.invalid', message = NULL WHERE user_id = $1",
            user_id,
        )
        await conn.execute(
            f"""UPDATE users SET {', '.join(f'{c} = NULL' for c in _USER_PERSONAL_FIELDS)},
                    email = 'deleted-' || user_id::text || '@deleted.invalid',
                    name = 'Deleted user', mfa_enabled = FALSE, is_active = FALSE,
                    email_verified = FALSE, anonymised_at = NOW(), updated_at = NOW()
                WHERE user_id = $1""",
            user_id,
        )
    logger.info("account_anonymised", user_id=str(user_id))


async def purge_due_accounts(db: Database, now: datetime | None = None) -> int:
    """Anonymise every account whose grace period has ended. Returns how many."""
    now = now or datetime.now(timezone.utc)
    rows = await db.fetch(
        "SELECT user_id FROM users WHERE purge_after IS NOT NULL AND purge_after <= $1 AND anonymised_at IS NULL",
        now,
    )
    for r in rows:
        await anonymise_account(db, str(r["user_id"]))
    return len(rows)
