"""0001 create users

Creates the pgcrypto extension (for gen_random_uuid) and the ``users`` table
verbatim from §2C, its indexes from §2D, and an ``updated_at`` auto-touch
trigger function reused by later tables.

Revision ID: 0001_create_users
Revises:
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_create_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # gen_random_uuid() lives in pgcrypto on PostgreSQL 13/14/15.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Shared trigger to keep updated_at current on UPDATE.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TABLE users (
            user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email               TEXT UNIQUE NOT NULL,
            email_verified      BOOLEAN DEFAULT FALSE,
            password_hash       TEXT,
            oauth_provider      TEXT,
            oauth_id            TEXT,
            name                TEXT NOT NULL,
            role                TEXT DEFAULT 'user'
                                CHECK (role IN ('user', 'admin')),
            is_active           BOOLEAN DEFAULT FALSE,
            mfa_enabled         BOOLEAN DEFAULT FALSE,
            mfa_secret_enc      TEXT,
            profile_picture     TEXT,
            phone               TEXT UNIQUE,
            -- Financial profile (all optional — Amendment 3)
            age                 INTEGER CHECK (age >= 18 AND age <= 100),
            monthly_income      NUMERIC(12,2) CHECK (monthly_income >= 0),
            monthly_expense     NUMERIC(12,2) CHECK (monthly_expense >= 0),
            risk_tolerance      NUMERIC(4,3)
                                CHECK (risk_tolerance >= 0.0 AND risk_tolerance <= 1.0),
            investment_horizon  INTEGER CHECK (investment_horizon >= 1),
            has_emergency_fund  BOOLEAN DEFAULT FALSE,
            financial_strategy  TEXT CHECK (financial_strategy IN
                                ('conservative','moderate','aggressive')),
            goal                TEXT,
            -- Metadata
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW(),
            last_login_at       TIMESTAMPTZ,
            deleted_at          TIMESTAMPTZ DEFAULT NULL,
            deletion_reason     TEXT
        );
        """
    )

    op.execute("CREATE INDEX idx_users_email ON users(email);")
    op.execute(
        "CREATE INDEX idx_users_deleted ON users(deleted_at) WHERE deleted_at IS NOT NULL;"
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    # pgcrypto extension intentionally left in place (other DBs may share it).
