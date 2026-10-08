"""0011 account deletion with a grace period (Phase B2)

``users.deleted_at`` already marks an account as scheduled for deletion (login
answers ACCOUNT_DELETED). This adds:

* ``purge_after``   — when the grace period ends and the account is wiped;
* ``anonymised_at`` — when it was wiped.

Wiping anonymises rather than deletes: ``audit_logs`` is append-only
(migration 0004), so the decisions it references can't be removed, and the
user row must stay as the anchor of the chain's genesis (user id + created
time). Everything that identifies the person or describes their finances is
erased instead (``backend/services/account_deletion.py``).

Revision ID: 0011_account_deletion
Revises: 0010_monthly_sip
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011_account_deletion"
down_revision: Union[str, None] = "0010_monthly_sip"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN purge_after   TIMESTAMPTZ,
            ADD COLUMN anonymised_at TIMESTAMPTZ;
        """
    )
    op.execute("CREATE INDEX idx_users_purge_after ON users(purge_after) WHERE anonymised_at IS NULL;")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_purge_after;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS anonymised_at, DROP COLUMN IF EXISTS purge_after;")
