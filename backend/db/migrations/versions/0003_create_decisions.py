"""0003 create decisions

The full ``decisions`` table (§2C) with the §2D indexes. Populated by the
analysis pipeline in Milestone 3; created now so RLS (0007) can attach to it.

Revision ID: 0003_create_decisions
Revises: 0002_create_auth_tables
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_create_decisions"
down_revision: Union[str, None] = "0002_create_auth_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE decisions (
            decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

            -- Pipeline status
            status              TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','processing','complete','failed')),
            pipeline_step       TEXT,
            error_message       TEXT,

            -- Decision input
            symbol              TEXT NOT NULL,
            exchange            TEXT DEFAULT 'NSE'
                                CHECK (exchange IN ('NSE', 'BSE')),
            holding_quantity    INTEGER NOT NULL CHECK (holding_quantity > 0),
            avg_buy_price       NUMERIC(12,2) NOT NULL CHECK (avg_buy_price > 0),
            current_price       NUMERIC(12,2) NOT NULL CHECK (current_price > 0),
            unrealized_pnl_pct  NUMERIC(7,4) NOT NULL,
            decision_intent     TEXT NOT NULL
                                CHECK (decision_intent IN ('sell','hold','buy_more')),
            user_reasoning      TEXT,

            -- Market context
            nifty_1d_change     NUMERIC(6,4),
            nifty_52w_return    NUMERIC(6,4),
            vix_value           NUMERIC(6,3),
            market_trend        TEXT CHECK (market_trend IN ('bull','bear','sideways')),
            sector              TEXT,

            -- ML outputs
            bias_detected       TEXT CHECK (bias_detected IN
                                ('loss_aversion','herd_behavior','disposition_effect','rational')),
            bias_confidence     NUMERIC(5,4) CHECK (bias_confidence BETWEEN 0.0 AND 1.0),
            recommendation      TEXT CHECK (recommendation IN ('HOLD','SELL','BUY_MORE')),
            causal_effect       NUMERIC(7,4),
            opportunity_cost_inr NUMERIC(15,2),

            -- Simulation summary
            hold_median_20y     NUMERIC(15,2),
            hold_p10_20y        NUMERIC(15,2),
            hold_p90_20y        NUMERIC(15,2),
            sell_median_20y     NUMERIC(15,2),
            sell_p10_20y        NUMERIC(15,2),
            sell_p90_20y        NUMERIC(15,2),

            -- JSONB outputs
            explainer_output    JSONB,
            debate_transcript   JSONB,
            simulation_curves   JSONB,

            -- Tax context
            holding_period_days INTEGER,
            tax_category        TEXT CHECK (tax_category IN ('STCG','LTCG')),

            -- Outcome tracking
            outcome_tracked     BOOLEAN DEFAULT FALSE,
            actual_outcome_pct  NUMERIC(7,4),
            recommendation_followed BOOLEAN,

            -- Timestamps
            submitted_at        TIMESTAMPTZ DEFAULT NOW(),
            completed_at        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute("CREATE INDEX idx_decisions_user_id ON decisions(user_id);")
    op.execute(
        "CREATE INDEX idx_decisions_status ON decisions(status) WHERE status != 'complete';"
    )
    op.execute("CREATE INDEX idx_decisions_created_at ON decisions(created_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS decisions CASCADE;")
