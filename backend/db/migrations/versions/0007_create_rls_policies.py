"""0007 create RLS policies + admin view

Enables Row-Level Security on the five user-owned tables (§2E) with policies
written per Amendment 9:

    USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)

The ``NULLIF(..., '')`` means an UNSET GUC yields NULL, so the predicate is NULL
(deny) rather than raising — a request that forgot to set the context sees zero
rows instead of a 500. The app sets the GUC with
``SELECT set_config('app.current_user_id', $1::text, true)`` inside the same
transaction (backend/db/pool.py: Database.rls_transaction).

FORCE ROW LEVEL SECURITY is applied so the policies bind even when the
connection role owns the table (local dev / tests connect as the DB owner).
Because of this, ALL access to these tables must go through an rls_transaction —
which the backend already does. The non-protected tables (users, refresh_tokens,
etc.) are untouched, so direct auth queries keep working.

Also creates the ``app_user`` role (§2E) for least-privilege production
deployments and the ``admin_stats_view`` aggregate (§2F, no PII).

Revision ID: 0007_create_rls_policies
Revises: 0006_create_sip_kite
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007_create_rls_policies"
down_revision: Union[str, None] = "0006_create_sip_kite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROTECTED_TABLES = (
    "decisions",
    "audit_logs",
    "portfolios",
    "sip_registrations",
    "profile_change_log",
)

_POLICY_USING = (
    "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"
)


def upgrade() -> None:
    # Least-privilege application role (used in production; NOLOGIN by default).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user;
            END IF;
        END
        $$;
        """
    )

    for table in _PROTECTED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # FORCE so the owner role is also subject to the policy (see docstring).
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
                FOR ALL
                USING ({_POLICY_USING})
                WITH CHECK ({_POLICY_USING});
            """
        )
        # Grant CRUD to app_user so the production role can operate under RLS.
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user;"
        )

    # Admin aggregate view — no user_id, no PII, no financial figures (§2F).
    op.execute(
        """
        CREATE VIEW admin_stats_view AS
        SELECT
            DATE_TRUNC('day', d.created_at)     AS day,
            COUNT(d.decision_id)                AS total_decisions,
            COUNT(CASE WHEN d.status='complete' THEN 1 END) AS completed,
            COUNT(CASE WHEN d.status='failed' THEN 1 END)   AS failed,
            COUNT(CASE WHEN d.bias_detected='loss_aversion' THEN 1 END)      AS loss_aversion_count,
            COUNT(CASE WHEN d.bias_detected='herd_behavior' THEN 1 END)      AS herd_behavior_count,
            COUNT(CASE WHEN d.bias_detected='disposition_effect' THEN 1 END) AS disposition_effect_count,
            COUNT(CASE WHEN d.bias_detected='rational' THEN 1 END)           AS rational_count,
            AVG(d.bias_confidence)              AS avg_confidence,
            COUNT(DISTINCT d.user_id)           AS active_users
        FROM decisions d
        WHERE d.created_at > NOW() - INTERVAL '90 days'
        GROUP BY DATE_TRUNC('day', d.created_at)
        ORDER BY day DESC;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS admin_stats_view;")
    for table in _PROTECTED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    # Revoke grants before dropping the role.
    for table in _PROTECTED_TABLES:
        op.execute(
            f"REVOKE ALL ON {table} FROM app_user;"
        )
    op.execute("DROP ROLE IF EXISTS app_user;")
