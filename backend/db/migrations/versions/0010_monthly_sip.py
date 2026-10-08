"""0010 monthly SIP on the financial profile (Phase A3)

Simulation v2 keeps adding money every month in both futures — the investor's
SIP, and education fees once they end — so the decision can be judged against
the whole portfolio it will sit in. The SIP amount is a Tier 2 figure, next to
FDs and savings, and optional: without it the projection assumes no monthly
investing and says so.

Revision ID: 0010_monthly_sip
Revises: 0009_portfolio_profile
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010_monthly_sip"
down_revision: Union[str, None] = "0009_portfolio_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE financial_profiles "
        "ADD COLUMN monthly_sip NUMERIC(12,2) CHECK (monthly_sip >= 0);"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE financial_profiles DROP COLUMN IF EXISTS monthly_sip;")
