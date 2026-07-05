"""0005 create portfolios (+ bias_profiles, market_cache)

portfolios (§2C) with the §2D index and an updated_at trigger. Also creates the
two small companion tables from §2C that don't warrant their own migration:
bias_profiles (per-user rolling bias scores) and market_cache (shared market
snapshot, not user-owned -> no RLS). Populated in Milestone 3.

Revision ID: 0005_create_portfolios
Revises: 0004_create_audit_logs
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_create_portfolios"
down_revision: Union[str, None] = "0004_create_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE portfolios (
            holding_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            symbol          TEXT NOT NULL,
            exchange        TEXT DEFAULT 'NSE',
            quantity        INTEGER NOT NULL CHECK (quantity > 0),
            avg_buy_price   NUMERIC(12,2) NOT NULL,
            buy_date        DATE,
            asset_type      TEXT DEFAULT 'equity'
                            CHECK (asset_type IN ('equity','mf','gold','crypto')),
            kite_synced     BOOLEAN DEFAULT FALSE,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);")
    op.execute(
        """
        CREATE TRIGGER trg_portfolios_updated_at
        BEFORE UPDATE ON portfolios
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    op.execute(
        """
        CREATE TABLE bias_profiles (
            user_id             UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            disposition_score   NUMERIC(4,3) DEFAULT 0.0 CHECK (disposition_score BETWEEN 0.0 AND 1.0),
            herd_score          NUMERIC(4,3) DEFAULT 0.0 CHECK (herd_score BETWEEN 0.0 AND 1.0),
            loss_aversion_score NUMERIC(4,3) DEFAULT 0.0 CHECK (loss_aversion_score BETWEEN 0.0 AND 1.0),
            rational_score      NUMERIC(4,3) DEFAULT 0.0 CHECK (rational_score BETWEEN 0.0 AND 1.0),
            total_decisions     INTEGER DEFAULT 0 CHECK (total_decisions >= 0),
            last_updated        TIMESTAMPTZ DEFAULT NOW(),
            created_at          TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_bias_profiles_user_id ON bias_profiles(user_id);")

    op.execute(
        """
        CREATE TABLE market_cache (
            cache_key           TEXT PRIMARY KEY,
            market_return       NUMERIC(7,4),
            market_volatility   NUMERIC(6,3),
            crowd_ratio         NUMERIC(5,4),
            fetched_at          TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_market_cache_key ON market_cache(cache_key);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market_cache CASCADE;")
    op.execute("DROP TABLE IF EXISTS bias_profiles CASCADE;")
    op.execute("DROP TABLE IF EXISTS portfolios CASCADE;")
