"""/v1/portfolio — holdings, other assets and liabilities, live valuation.

    GET    /v1/portfolio                     holdings (live-priced) + assets + summary
    POST   /v1/portfolio/holdings            add a stock or mutual fund
    PUT    /v1/portfolio/holdings/{id}       edit one
    DELETE /v1/portfolio/holdings/{id}       remove one
    PUT    /v1/portfolio/assets              gold, property, loans, rent, FDs, savings
    GET    /v1/portfolio/mf-search?q=        find a fund (MFAPI.in)
    GET    /v1/portfolio/quote?symbol=       check a ticker and get its price

Every query runs in ``rls_transaction``: ``portfolios`` and
``financial_profiles`` are per-user isolated, so another user's holding id is
simply not found (404), never forbidden.

NOTE: no ``from __future__ import annotations`` in route modules (see
auth/routes.py for the slowapi/PEP 563 body-inference reason).
"""
import uuid

from fastapi import APIRouter, Depends, Query

from ...auth.dependencies import get_current_user
from ...db import Database
from ...errors import AppError
from ...models import User
from ...schemas.portfolio import AssetsUpdate, HoldingInput
from ...services.portfolio import ASSET_FIELDS, load_portfolio
from ...services.prices import mf_search, stock_quote
from ...state import get_db

router = APIRouter()

_MAX_HOLDINGS = 200


def _holding_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise AppError(status_code=404, error="HOLDING_NOT_FOUND", message="Holding not found") from None


@router.get("")
async def get_portfolio(user: User = Depends(get_current_user), db: Database = Depends(get_db)):
    async with db.rls_transaction(str(user.user_id)) as conn:
        return await load_portfolio(conn, str(user.user_id))


@router.post("/holdings", status_code=201)
async def add_holding(
    payload: HoldingInput,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    symbol = payload.symbol if payload.asset_type == "equity" else f"MF{payload.scheme_code}"
    async with db.rls_transaction(str(user.user_id)) as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM portfolios")
        if count >= _MAX_HOLDINGS:
            raise AppError(status_code=409, error="TOO_MANY_HOLDINGS", message="Portfolio limit reached.")
        exists = await conn.fetchval(
            "SELECT holding_id FROM portfolios WHERE symbol = $1 AND exchange = $2",
            symbol, payload.exchange,
        )
        if exists:
            raise AppError(
                status_code=409, error="HOLDING_EXISTS",
                message="That's already in your portfolio. Edit it instead.",
                extra={"holding_id": str(exists)},
            )
        holding_id = await conn.fetchval(
            """
            INSERT INTO portfolios (user_id, asset_type, symbol, exchange, name, scheme_code,
                                    quantity, avg_buy_price, buy_date)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            RETURNING holding_id
            """,
            user.user_id, payload.asset_type, symbol, payload.exchange,
            payload.name if payload.asset_type == "mf" else payload.symbol,
            payload.scheme_code, payload.quantity, payload.avg_buy_price, payload.buy_date,
        )
    return {"holding_id": str(holding_id)}


@router.put("/holdings/{holding_id}")
async def update_holding(
    holding_id: str,
    payload: HoldingInput,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    hid = _holding_id(holding_id)
    async with db.rls_transaction(str(user.user_id)) as conn:
        updated = await conn.fetchval(
            """
            UPDATE portfolios SET quantity = $2, avg_buy_price = $3, buy_date = $4
            WHERE holding_id = $1 RETURNING holding_id
            """,
            hid, payload.quantity, payload.avg_buy_price, payload.buy_date,
        )
    if not updated:
        raise AppError(status_code=404, error="HOLDING_NOT_FOUND", message="Holding not found")
    return {"holding_id": str(updated)}


@router.delete("/holdings/{holding_id}")
async def delete_holding(
    holding_id: str,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    hid = _holding_id(holding_id)
    async with db.rls_transaction(str(user.user_id)) as conn:
        deleted = await conn.fetchval("DELETE FROM portfolios WHERE holding_id = $1 RETURNING holding_id", hid)
    if not deleted:
        raise AppError(status_code=404, error="HOLDING_NOT_FOUND", message="Holding not found")
    return {"deleted": True}


@router.put("/assets")
async def update_assets(
    payload: AssetsUpdate,
    user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    values = [getattr(payload, f) for f in ASSET_FIELDS]
    cols = ", ".join(ASSET_FIELDS)
    params = ", ".join(f"${i}" for i in range(2, len(ASSET_FIELDS) + 2))
    updates = ", ".join(f"{f} = EXCLUDED.{f}" for f in ASSET_FIELDS)
    async with db.rls_transaction(str(user.user_id)) as conn:
        await conn.execute(
            f"""
            INSERT INTO financial_profiles (user_id, {cols}) VALUES ($1, {params})
            ON CONFLICT (user_id) DO UPDATE SET {updates}, updated_at = NOW()
            """,
            user.user_id, *values,
        )
    return {"message": "Saved"}


@router.get("/mf-search")
async def search_funds(q: str = Query(..., min_length=3, max_length=80), user: User = Depends(get_current_user)):
    return {"results": await mf_search(q)}


@router.get("/quote")
async def quote(
    symbol: str = Query(..., min_length=1, max_length=32),
    exchange: str = Query("NSE", pattern="^(NSE|BSE)$"),
    user: User = Depends(get_current_user),
):
    q = await stock_quote(symbol, exchange)
    return {"symbol": symbol.strip().upper(), "exchange": exchange, "quote": q}
