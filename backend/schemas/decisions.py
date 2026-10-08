"""Decision request/response schemas (§10 DecisionInput, §3F responses).

The validators mirror the CHECK constraints in migration 0003 so a bad value is
a 422 from the API rather than a 500 from Postgres.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

ALLOWED_EXCHANGES = ("NSE", "BSE")
ALLOWED_INTENTS = ("sell", "hold", "buy_more")
ALLOWED_MARKET_TRENDS = ("bull", "bear", "sideways")


class DecisionInput(BaseModel):
    """§10 DecisionInput — the body of ``POST /v1/decisions/analyze``."""

    symbol: str = Field(..., min_length=1, max_length=32, description="e.g. RELIANCE")
    exchange: str = Field("NSE", description="NSE or BSE")
    holding_quantity: float = Field(..., gt=0, description="shares, or mutual-fund units")
    # The portfolio holding this decision is about. When given, the server
    # takes symbol, units, average cost and live price from the portfolio and
    # stores the portfolio snapshot with the decision; the position fields in
    # the body are then only a fallback.
    holding_id: Optional[str] = Field(None, max_length=36)
    avg_buy_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    unrealized_pnl_pct: float = Field(
        ..., ge=-1, le=100, description="fraction, not percent: -0.1832 = -18.32%"
    )
    decision_intent: str = Field(..., description="sell | hold | buy_more")
    user_reasoning: Optional[str] = Field(None, max_length=2000)
    holding_period_days: Optional[int] = Field(None, ge=0)

    # Market context — supplied by the caller for now; Phase 6D's market_data
    # service will fill these server-side.
    market_trend: Optional[str] = Field(None, description="bull | bear | sideways")
    sector: Optional[str] = Field(None, max_length=64)

    @field_validator("symbol", "exchange", "sector")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v

    @field_validator("exchange")
    @classmethod
    def _check_exchange(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ALLOWED_EXCHANGES:
            raise ValueError(f"exchange must be one of {', '.join(ALLOWED_EXCHANGES)}")
        return upper

    @field_validator("decision_intent")
    @classmethod
    def _check_intent(cls, v: str) -> str:
        lower = v.strip().lower()
        if lower not in ALLOWED_INTENTS:
            raise ValueError(f"decision_intent must be one of {', '.join(ALLOWED_INTENTS)}")
        return lower

    @field_validator("market_trend")
    @classmethod
    def _check_trend(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        lower = v.strip().lower()
        if lower not in ALLOWED_MARKET_TRENDS:
            raise ValueError(
                f"market_trend must be one of {', '.join(ALLOWED_MARKET_TRENDS)}"
            )
        return lower


class DecisionSubmitResponse(BaseModel):
    """202 body from ``POST /v1/decisions/analyze`` (§3F step 1)."""

    decision_id: str
    status: str = "pending"
    stream_url: str
