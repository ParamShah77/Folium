"""0009 portfolio-aware profile (FOLIUM_MASTER.md §4, tiered inputs)

Folium judges a decision against the investor's whole financial picture, not
one stock in isolation. This migration adds the inputs §10 specifies:

Tier 1 — required at sign-up, on ``users`` next to income:
    monthly_emi, rent_paid, education_monthly, education_end_year
  ``monthly_expense`` stays as the committed outflow the bias model reads; the
  API now derives it as EMIs + rent paid + education (§10's surplus formula).

Tier 2 — optional, in a NEW table ``financial_profiles`` (one row per user):
    gold_grams, gold_buy_price_per_gram, real_estate_value,
    home_loan_outstanding, other_loans_outstanding, rent_received,
    fixed_deposits, savings_balance
  It is a separate, RLS-protected table rather than more ``users`` columns
  because ``users`` is read by the auth path without the RLS GUC set; net-worth
  data belongs behind the same per-user isolation as decisions (§2E).

Holdings — the existing ``portfolios`` table:
  * ``quantity`` INTEGER -> NUMERIC(14,4): mutual-fund units are fractional.
  * ``name`` (fund name) and ``scheme_code`` (MFAPI.in id for live NAV).
  Crypto stays in the CHECK for schema compatibility but is not collected.

Decisions:
  * ``holding_quantity`` INTEGER -> NUMERIC(14,4), for fund units.
  * ``holding_id`` — the portfolio holding the decision is about.
  * ``portfolio_context`` JSONB — the portfolio snapshot at submission
    (position share, net worth, monthly surplus, equity share), stored like
    the market context so a re-run reproduces the original inputs.

Revision ID: 0009_portfolio_profile
Revises: 0008_decision_market_features
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009_portfolio_profile"
down_revision: Union[str, None] = "0008_decision_market_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN monthly_emi        NUMERIC(12,2) CHECK (monthly_emi >= 0),
            ADD COLUMN rent_paid          NUMERIC(12,2) CHECK (rent_paid >= 0),
            ADD COLUMN education_monthly  NUMERIC(12,2) CHECK (education_monthly >= 0),
            ADD COLUMN education_end_year INTEGER
                CHECK (education_end_year BETWEEN 2000 AND 2100);
        """
    )

    op.execute(
        """
        CREATE TABLE financial_profiles (
            user_id                 UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
            gold_grams              NUMERIC(10,3) CHECK (gold_grams >= 0),
            gold_buy_price_per_gram NUMERIC(10,2) CHECK (gold_buy_price_per_gram >= 0),
            real_estate_value       NUMERIC(15,2) CHECK (real_estate_value >= 0),
            home_loan_outstanding   NUMERIC(15,2) CHECK (home_loan_outstanding >= 0),
            other_loans_outstanding NUMERIC(15,2) CHECK (other_loans_outstanding >= 0),
            rent_received           NUMERIC(12,2) CHECK (rent_received >= 0),
            fixed_deposits          NUMERIC(15,2) CHECK (fixed_deposits >= 0),
            savings_balance         NUMERIC(15,2) CHECK (savings_balance >= 0),
            updated_at              TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute("ALTER TABLE financial_profiles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE financial_profiles FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY financial_profiles_isolation ON financial_profiles
            USING ({_POLICY_USING})
            WITH CHECK ({_POLICY_USING});
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON financial_profiles TO app_user;")

    op.execute(
        """
        ALTER TABLE portfolios
            ALTER COLUMN quantity TYPE NUMERIC(14,4),
            ADD COLUMN name        TEXT,
            ADD COLUMN scheme_code TEXT;
        """
    )

    op.execute(
        """
        ALTER TABLE decisions
            ALTER COLUMN holding_quantity TYPE NUMERIC(14,4),
            ADD COLUMN holding_id        UUID REFERENCES portfolios(holding_id) ON DELETE SET NULL,
            ADD COLUMN portfolio_context JSONB;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE decisions
            DROP COLUMN IF EXISTS portfolio_context,
            DROP COLUMN IF EXISTS holding_id,
            ALTER COLUMN holding_quantity TYPE INTEGER USING ceil(holding_quantity)::integer;
        """
    )
    op.execute(
        """
        ALTER TABLE portfolios
            DROP COLUMN IF EXISTS scheme_code,
            DROP COLUMN IF EXISTS name,
            ALTER COLUMN quantity TYPE INTEGER USING round(quantity)::integer;
        """
    )
    op.execute("DROP TABLE IF EXISTS financial_profiles CASCADE;")
    op.execute(
        """
        ALTER TABLE users
            DROP COLUMN IF EXISTS education_end_year,
            DROP COLUMN IF EXISTS education_monthly,
            DROP COLUMN IF EXISTS rent_paid,
            DROP COLUMN IF EXISTS monthly_emi;
        """
    )
