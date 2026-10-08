"""Portfolio request bodies (``/v1/portfolio``).

Holdings are stocks (``equity``) or mutual funds (``mf``) — the positions a
decision can be about. Everything else in §10 Tier 2 (gold, property, loans,
rent received, FDs, savings) is a single figure per user, so it lives in
``AssetsUpdate`` rather than as holdings. Crypto is deliberately not collected.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

_SYMBOL = re.compile(r"^[A-Z0-9&.\-]{1,32}$")


class HoldingInput(BaseModel):
    asset_type: Literal["equity", "mf"]
    # equity
    symbol: Optional[str] = Field(None, max_length=32)
    exchange: Literal["NSE", "BSE"] = "NSE"
    # mutual fund (MFAPI.in scheme)
    scheme_code: Optional[str] = Field(None, max_length=16)
    name: Optional[str] = Field(None, max_length=200)
    # both
    quantity: float = Field(..., gt=0, le=1e9, description="shares, or fund units")
    avg_buy_price: float = Field(..., gt=0, le=1e8, description="per share / per unit (NAV)")
    buy_date: Optional[date] = None

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().upper()
        if not _SYMBOL.match(v):
            raise ValueError("symbol must be an NSE/BSE ticker such as RELIANCE")
        return v

    @model_validator(mode="after")
    def _complete(self) -> "HoldingInput":
        if self.asset_type == "equity" and not self.symbol:
            raise ValueError("a stock needs its symbol")
        if self.asset_type == "mf":
            if not (self.scheme_code and self.scheme_code.strip().isdigit()):
                raise ValueError("a mutual fund needs its scheme code")
            if not self.name:
                raise ValueError("a mutual fund needs its name")
        if self.asset_type == "equity" and self.quantity != int(self.quantity):
            raise ValueError("shares must be a whole number")
        return self


class AssetsUpdate(BaseModel):
    """Tier 2 figures. Omitted or null = not held / not applicable."""

    gold_grams: Optional[float] = Field(None, ge=0, le=1e6)
    gold_buy_price_per_gram: Optional[float] = Field(None, ge=0, le=1e6)
    real_estate_value: Optional[float] = Field(None, ge=0, le=1e11)
    home_loan_outstanding: Optional[float] = Field(None, ge=0, le=1e11)
    other_loans_outstanding: Optional[float] = Field(None, ge=0, le=1e11)
    rent_received: Optional[float] = Field(None, ge=0, le=1e9)
    fixed_deposits: Optional[float] = Field(None, ge=0, le=1e11)
    savings_balance: Optional[float] = Field(None, ge=0, le=1e11)
    monthly_sip: Optional[float] = Field(None, ge=0, le=1e9, description="monthly investing (SIP), all schemes")
