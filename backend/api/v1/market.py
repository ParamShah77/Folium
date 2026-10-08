"""Market context endpoints (M5 ``market_router``, built early for the web app).

Both require a session: the data is public, but the fetch is not free (it hits
Yahoo Finance) and there is no reason to let anonymous traffic drive it.

NOTE: no ``from __future__ import annotations`` in route modules (see
auth/routes.py for the slowapi/PEP 563 body-inference reason).
"""
from fastapi import APIRouter, Depends

from ...auth.dependencies import get_current_user
from ...models import User
from ...services.market_data import capture_market_context, get_ribbon

router = APIRouter()


@router.get("/ribbon")
async def market_ribbon(user: User = Depends(get_current_user)):
    """NIFTY 50, SENSEX, BANK NIFTY and India VIX — price and 1-day change."""
    return await get_ribbon()


@router.get("/context")
async def market_context(user: User = Depends(get_current_user)):
    """The exact market features a decision submitted now would be stored with."""
    return await capture_market_context()
