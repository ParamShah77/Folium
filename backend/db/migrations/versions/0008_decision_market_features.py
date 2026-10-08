"""0008 decisions: market features the bias model was actually trained on

Migration 0003 gave ``decisions`` a market context of ``nifty_1d_change``,
``nifty_52w_return`` and ``vix_value``. None of those is what the XGBoost v3
classifier consumes:

  * ``market_return_recent`` in training is the **1-month** NIFTY50 return
    (5th–95th pct: -0.113 … +0.085). A 52-week return sits far outside that
    range, and a 1-day change is far too small to carry the same signal.
  * ``market_volatility`` in training is the **30-day std of daily returns**
    (median 0.028).

Both are captured at submission time and stored on the row, not re-fetched at
inference, so re-running a decision reproduces its original prediction — the
property Objective 4's audit trail depends on. ``market_data_source`` records
whether the values were live, served from the 15-minute cache, or unavailable.

Column-level grants are not needed: migration 0007 granted app_user privileges
on whole tables, which covers columns added later.

Revision ID: 0008_decision_market_features
Revises: 0007_create_rls_policies
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008_decision_market_features"
down_revision: Union[str, None] = "0007_create_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE decisions
            ADD COLUMN nifty_1m_return      NUMERIC(7,4),
            ADD COLUMN nifty_volatility_30d NUMERIC(7,5),
            ADD COLUMN market_data_source   TEXT
                CHECK (market_data_source IN ('live', 'cache', 'unavailable'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE decisions
            DROP COLUMN IF EXISTS market_data_source,
            DROP COLUMN IF EXISTS nifty_volatility_30d,
            DROP COLUMN IF EXISTS nifty_1m_return;
        """
    )
