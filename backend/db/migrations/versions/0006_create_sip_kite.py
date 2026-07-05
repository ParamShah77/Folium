"""0006 create sip_registrations + kite_tokens

sip_registrations (§2C) and kite_tokens (§2C). Kite is DEFERRED (Amendment 1)
but the table stays in the schema for future use. kite_tokens is keyed 1:1 on
user_id and its token columns are Fernet-encrypted at write time (Milestone 3+).

Revision ID: 0006_create_sip_kite
Revises: 0005_create_portfolios
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006_create_sip_kite"
down_revision: Union[str, None] = "0005_create_portfolios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sip_registrations (
            sip_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            fund_name       TEXT NOT NULL,
            isin            TEXT,
            monthly_amount  NUMERIC(10,2) NOT NULL,
            deduction_date  INTEGER CHECK (deduction_date BETWEEN 1 AND 28),
            is_active       BOOLEAN DEFAULT TRUE,
            paused_at       TIMESTAMPTZ,
            pause_reason    TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_sip_user_id ON sip_registrations(user_id);")

    op.execute(
        """
        CREATE TABLE kite_tokens (
            user_id             UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            access_token        TEXT,
            access_token_date   DATE,
            request_token       TEXT,
            connected_at        TIMESTAMPTZ DEFAULT NOW(),
            last_synced_at      TIMESTAMPTZ
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kite_tokens CASCADE;")
    op.execute("DROP TABLE IF EXISTS sip_registrations CASCADE;")
