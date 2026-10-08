"""0012 reading the investor's comment, and consent for AI help (Phase B3)

* ``decisions.comment_facts`` — what "Why? In your own words" was found to say
  (backend/core/comment_reader.py): stated facts such as a need for the money,
  which can shift the pattern reading, and feelings, which are only shown.
  Stored so a re-run reads the same comment the same way.
* ``users.ai_consent`` — the investor allows Gemini to read their comment and
  word the case for holding and selling. Off by default; the offline phrase
  rules work without it.

Revision ID: 0012_comment_reading
Revises: 0011_account_deletion
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012_comment_reading"
down_revision: Union[str, None] = "0011_account_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE decisions ADD COLUMN comment_facts JSONB;")
    op.execute("ALTER TABLE users ADD COLUMN ai_consent BOOLEAN NOT NULL DEFAULT FALSE;")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS ai_consent;")
    op.execute("ALTER TABLE decisions DROP COLUMN IF EXISTS comment_facts;")
