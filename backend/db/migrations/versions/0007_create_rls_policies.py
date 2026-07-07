"""0007 create RLS policies + admin view + least-privilege app_user role

Enables Row-Level Security on the five user-owned tables (§2E) with policies
written per Amendment 9:

    USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)

The ``NULLIF(..., '')`` means an UNSET GUC yields NULL, so the predicate is NULL
(deny) rather than raising — a request that forgot to set the context sees zero
rows instead of a 500. The app sets the GUC with
``SELECT set_config('app.current_user_id', $1::text, true)`` inside the same
transaction (backend/db/pool.py: Database.rls_transaction).

WHO RLS ACTUALLY BINDS (the security-critical part):
  PostgreSQL RLS is UNCONDITIONALLY BYPASSED by superusers and by a table's
  OWNER (unless FORCE is set). In this stack the migration/owner role ``finai``
  is the ``POSTGRES_USER`` and is therefore a SUPERUSER — no amount of ENABLE /
  FORCE can make a superuser obey a policy. So the application (and the RLS test
  path) MUST connect as a dedicated NON-superuser role that is subject to the
  policies. That role is ``app_user``, created here as a LOGIN role with a
  password (APP_DB_PASSWORD, default 'app_user' for local dev). FORCE ROW LEVEL
  SECURITY is still applied — it is harmless for a non-owner and correctly
  protects the case where ``app_user`` ever owns a table — but it is NOT what
  makes the guarantee hold; connecting as a non-superuser is.

Migrations, admin operations, and the direct test fixtures keep using ``finai``
(they need owner/superuser privileges: CREATE ROLE, ENABLE RLS, TRUNCATE, etc.).

app_user is granted what the app needs across the WHOLE public schema (not just
the five protected tables) so the non-RLS auth queries (users, refresh_tokens,
…) also work through the app pool:
  * USAGE on schema public
  * SELECT/INSERT/UPDATE/DELETE on all tables (existing + future default privs)
  * SELECT on admin_stats_view (views are not covered by ON ALL TABLES)
  * USAGE/SELECT on all sequences (harmless if there are none)

Also creates the ``admin_stats_view`` aggregate (§2F, no PII).

Revision ID: 0007_create_rls_policies
Revises: 0006_create_sip_kite
Create Date: 2026-07-05
"""
import os
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

# Password for the least-privilege application login role. Sourced from the
# environment so production can inject a real secret; defaults to 'app_user' for
# local dev (matches docker-compose / .env.example / SETUP.md).
_APP_DB_PASSWORD = os.getenv("APP_DB_PASSWORD", "app_user")


def _sql_str_literal(value: str) -> str:
    """Return a safely single-quoted SQL string literal (doubles embedded quotes)."""
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    pw_literal = _sql_str_literal(_APP_DB_PASSWORD)

    # Least-privilege application LOGIN role (subject to RLS: NOT a superuser).
    # Create-or-update so the password is set even if the role already exists.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user LOGIN PASSWORD {pw_literal};
            ELSE
                ALTER ROLE app_user LOGIN PASSWORD {pw_literal};
            END IF;
        END
        $$;
        """
    )

    for table in _PROTECTED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # FORCE is harmless for a non-owner; kept for owner-safety (see docstring).
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
                FOR ALL
                USING ({_POLICY_USING})
                WITH CHECK ({_POLICY_USING});
            """
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

    # ------------------------------------------------------------------ #
    # Grant app_user everything the app pool needs across the whole schema.
    # Without these, the 18 auth tests that run through the app pool would
    # fail with permission-denied (app_user is not the owner).
    # ------------------------------------------------------------------ #
    op.execute("GRANT USAGE ON SCHEMA public TO app_user;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;"
    )
    op.execute("GRANT SELECT ON admin_stats_view TO app_user;")
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;"
    )
    # Default privileges so tables/sequences created by FUTURE migrations (run as
    # finai) are automatically usable by app_user without another grant pass.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO app_user;"
    )


def downgrade() -> None:
    # Undo default privileges first (must mirror the GRANTs above).
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_user;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM app_user;"
    )
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_user;")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_user;")

    op.execute("DROP VIEW IF EXISTS admin_stats_view;")

    for table in _PROTECTED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    op.execute("REVOKE USAGE ON SCHEMA public FROM app_user;")
    op.execute("DROP ROLE IF EXISTS app_user;")
