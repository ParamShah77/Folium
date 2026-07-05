"""0004 create audit_logs

Tamper-evident audit chain (§2C): SHA-256 payload_hash / previous_hash /
chain_hash columns, plus RULEs that make UPDATE and DELETE no-ops so entries are
append-only. The genesis-hash design (audit_logger.compute_genesis_hash) is
implemented in Milestone 3; the table shape it writes to is created here.

Revision ID: 0004_create_audit_logs
Revises: 0003_create_decisions
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_create_audit_logs"
down_revision: Union[str, None] = "0003_create_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_logs (
            log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            decision_id     UUID REFERENCES decisions(decision_id) ON DELETE SET NULL,
            user_id         UUID REFERENCES users(user_id) ON DELETE SET NULL,

            event_type      TEXT NOT NULL,
            payload_hash    TEXT NOT NULL,
            previous_hash   TEXT NOT NULL,
            chain_hash      TEXT NOT NULL,

            payload         JSONB NOT NULL,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute("CREATE INDEX idx_audit_user_id ON audit_logs(user_id);")
    op.execute("CREATE INDEX idx_audit_decision_id ON audit_logs(decision_id);")

    # Append-only: block UPDATE and DELETE entirely.
    op.execute("CREATE RULE audit_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;")
    op.execute("CREATE RULE audit_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;")


def downgrade() -> None:
    # RULEs must be dropped before the table can be removed cleanly.
    op.execute("DROP RULE IF EXISTS audit_no_update ON audit_logs;")
    op.execute("DROP RULE IF EXISTS audit_no_delete ON audit_logs;")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
