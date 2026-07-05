"""0002 create auth tables

refresh_tokens, mfa_backup_codes, mfa_recovery_requests, profile_change_log
(§2C) with the §2D indexes. MFA tables are created now (schema completeness) but
only populated starting Milestone 2.

Revision ID: 0002_create_auth_tables
Revises: 0001_create_users
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_create_auth_tables"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            token_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            token_hash      TEXT UNIQUE NOT NULL,
            jti             TEXT UNIQUE NOT NULL,
            issued_at       TIMESTAMPTZ DEFAULT NOW(),
            expires_at      TIMESTAMPTZ NOT NULL,
            revoked         BOOLEAN DEFAULT FALSE,
            user_agent      TEXT,
            ip_address      TEXT
        );
        """
    )
    op.execute("CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);")
    op.execute("CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);")

    op.execute(
        """
        CREATE TABLE mfa_backup_codes (
            code_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            code_hash   TEXT NOT NULL,
            used        BOOLEAN DEFAULT FALSE,
            used_at     TIMESTAMPTZ
        );
        """
    )
    op.execute("CREATE INDEX idx_mfa_backup_codes_user ON mfa_backup_codes(user_id);")

    op.execute(
        """
        CREATE TABLE mfa_recovery_requests (
            request_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID REFERENCES users(user_id) ON DELETE SET NULL,
            email           TEXT NOT NULL,
            message         TEXT,
            status          TEXT DEFAULT 'pending'
                            CHECK (status IN ('pending', 'resolved', 'rejected')),
            resolved_by     UUID REFERENCES users(user_id),
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            resolved_at     TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        CREATE TABLE profile_change_log (
            change_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            field_changed   TEXT NOT NULL,
            old_value_hash  TEXT,
            changed_at      TIMESTAMPTZ DEFAULT NOW(),
            verified_via    TEXT NOT NULL,
            changed_by      UUID REFERENCES users(user_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_profile_change_log_user ON profile_change_log(user_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile_change_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS mfa_recovery_requests CASCADE;")
    op.execute("DROP TABLE IF EXISTS mfa_backup_codes CASCADE;")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE;")
