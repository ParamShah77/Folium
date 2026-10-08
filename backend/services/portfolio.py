"""Portfolio valuation — net worth, monthly surplus, and a decision's context.

Formulas follow FOLIUM_MASTER.md §4, with one correction:

    liquid       = stocks + mutual funds + gold + fixed deposits + savings
    net_worth    = liquid + real_estate - home_loan - other_loans
    surplus      = income + rent_received - rent_paid - EMIs - education

§10 writes ``net_worth = liquid + (real_estate - home_loan)`` and lists other
loans under liabilities without subtracting them. Net worth subtracts every
loan, so other loans are deducted here.

Mutual funds are counted as equity when working out the equity share. Most
retail fund holdings are equity-oriented, and the app does not yet ask for each
fund's category. That approximation is disclosed wherever the share is shown.

All reads run inside the caller's RLS transaction: ``portfolios`` and
``financial_profiles`` are both per-user isolated (migrations 0007, 0009).
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Optional

from .prices import gold_price_per_gram, mf_nav, stock_quote

_TIER1_SQL = """
    SELECT monthly_income, monthly_emi, rent_paid, education_monthly,
           education_end_year, monthly_expense, has_emergency_fund
    FROM users WHERE user_id = $1
"""
_ASSETS_SQL = "SELECT * FROM financial_profiles WHERE user_id = $1"
_HOLDINGS_SQL = """
    SELECT holding_id, asset_type, symbol, exchange, name, scheme_code,
           quantity, avg_buy_price, buy_date, created_at
    FROM portfolios WHERE user_id = $1 ORDER BY asset_type, symbol
"""

ASSET_FIELDS = (
    "gold_grams", "gold_buy_price_per_gram", "real_estate_value",
    "home_loan_outstanding", "other_loans_outstanding", "rent_received",
    "fixed_deposits", "savings_balance", "monthly_sip",
)


def _f(v: Any) -> float:
    return float(v) if v is not None else 0.0


def _opt(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def committed_outflow(row: Any) -> Optional[float]:
    """EMIs + rent paid + education — §10's fixed monthly outflow.

    Falls back to the legacy ``monthly_expense`` for accounts created before
    the tiered fields existed.
    """
    parts = [row["monthly_emi"], row["rent_paid"], row["education_monthly"]]
    if all(p is None for p in parts):
        return _opt(row["monthly_expense"])
    return sum(_f(p) for p in parts)


async def _price_holding(h: dict[str, Any]) -> dict[str, Any]:
    if h["asset_type"] == "mf" and h.get("scheme_code"):
        q = await mf_nav(h["scheme_code"])
    else:
        q = await stock_quote(h["symbol"], h.get("exchange") or "NSE")
    qty, avg = _f(h["quantity"]), _f(h["avg_buy_price"])
    price = q["price"] if q else None
    value = qty * (price if price is not None else avg)
    invested = qty * avg
    return {
        "holding_id": str(h["holding_id"]),
        "asset_type": h["asset_type"],
        "symbol": h["symbol"],
        "exchange": h.get("exchange") or "NSE",
        "name": h.get("name") or h["symbol"],
        "scheme_code": h.get("scheme_code"),
        "quantity": qty,
        "avg_buy_price": avg,
        "buy_date": h["buy_date"].isoformat() if h.get("buy_date") else None,
        "current_price": price,
        "price_source": "live" if q else "unavailable",
        "price_as_of": q.get("as_of") if q else None,
        "day_change_pct": q.get("change_pct") if q else None,
        "invested": round(invested, 2),
        "value": round(value, 2),
        "pnl": round(value - invested, 2) if price is not None else None,
        "pnl_pct": round(price / avg - 1, 4) if price is not None and avg else None,
    }


async def load_portfolio(conn, user_id: str) -> dict[str, Any]:
    """Holdings priced live, other assets, and the derived summary."""
    tier1 = await conn.fetchrow(_TIER1_SQL, user_id)
    assets_row = await conn.fetchrow(_ASSETS_SQL, user_id)
    holdings_rows = [dict(r) for r in await conn.fetch(_HOLDINGS_SQL, user_id)]

    priced, gold = await asyncio.gather(
        asyncio.gather(*(_price_holding(h) for h in holdings_rows)),
        gold_price_per_gram(),
    )
    priced = list(priced)
    assets = {k: _opt(assets_row[k]) if assets_row else None for k in ASSET_FIELDS}

    stocks = sum(h["value"] for h in priced if h["asset_type"] == "equity")
    funds = sum(h["value"] for h in priced if h["asset_type"] == "mf")
    grams = _f(assets["gold_grams"])
    gold_price = gold["price"] if gold else _f(assets["gold_buy_price_per_gram"])
    gold_value = grams * gold_price
    fds, savings = _f(assets["fixed_deposits"]), _f(assets["savings_balance"])
    liquid = stocks + funds + gold_value + fds + savings
    real_estate = _f(assets["real_estate_value"])
    home_loan, other_loans = _f(assets["home_loan_outstanding"]), _f(assets["other_loans_outstanding"])
    net_worth = liquid + real_estate - home_loan - other_loans

    income = _opt(tier1["monthly_income"]) if tier1 else None
    outflow = committed_outflow(tier1) if tier1 else None
    rent_received = _f(assets["rent_received"])
    surplus = (income + rent_received - outflow) if income is not None and outflow is not None else None

    def share(x: float) -> float:
        return round(x / liquid, 4) if liquid > 0 else 0.0

    summary = {
        "liquid": round(liquid, 2),
        "net_worth": round(net_worth, 2),
        "invested_in_holdings": round(sum(h["invested"] for h in priced), 2),
        "holdings_value": round(stocks + funds, 2),
        "allocation": {
            "stocks": {"value": round(stocks, 2), "share": share(stocks)},
            "mutual_funds": {"value": round(funds, 2), "share": share(funds)},
            "gold": {"value": round(gold_value, 2), "share": share(gold_value)},
            "fixed_deposits": {"value": round(fds, 2), "share": share(fds)},
            "savings": {"value": round(savings, 2), "share": share(savings)},
        },
        "equity_share": share(stocks + funds),
        "real_estate": round(real_estate, 2),
        "liabilities": round(home_loan + other_loans, 2),
        "monthly_income": income,
        "rent_received": rent_received,
        "committed_outflow": outflow,
        "monthly_surplus": round(surplus, 2) if surplus is not None else None,
        "monthly_sip": _opt(assets["monthly_sip"]),
        "education_monthly": _opt(tier1["education_monthly"]) if tier1 else None,
        "education_end_year": tier1["education_end_year"] if tier1 else None,
        "gold": {
            "grams": grams,
            "price_per_gram": round(gold_price, 2) if gold_price else None,
            "price_source": "live" if gold else ("buy_price" if grams else "none"),
            "basis": gold["basis"] if gold else None,
        },
    }
    return {"holdings": priced, "assets": assets, "summary": summary}


def decision_context(portfolio: dict[str, Any], holding: dict[str, Any]) -> dict[str, Any]:
    """The portfolio snapshot stored with a decision (``portfolio_context``)."""
    s = portfolio["summary"]
    liquid = s["liquid"]
    value = holding["value"]
    return {
        "holding_id": holding["holding_id"],
        "asset_type": holding["asset_type"],
        "name": holding.get("name") or holding.get("symbol"),
        "position_value": value,
        "position_share": round(value / liquid, 4) if liquid > 0 else None,
        "liquid": liquid,
        "net_worth": s["net_worth"],
        "equity_share": s["equity_share"],
        # Bias model v4 inputs (asset mix, property and loans).
        "gold_share": s["allocation"]["gold"]["share"],
        "real_estate": s["real_estate"],
        "liabilities": s["liabilities"],
        # Simulation v2 inputs: where a sale's money would go, and what keeps
        # being added each month.
        "allocation": {k: v["value"] for k, v in s["allocation"].items()},
        "monthly_sip": s["monthly_sip"],
        "education_monthly": s["education_monthly"],
        "education_end_year": s["education_end_year"],
        "monthly_income": s["monthly_income"],
        "rent_received": s["rent_received"],
        "committed_outflow": s["committed_outflow"],
        "monthly_surplus": s["monthly_surplus"],
        "holdings_count": len(portfolio["holdings"]),
    }


def to_decimal(v: Optional[float], places: str = "0.01") -> Optional[Decimal]:
    return None if v is None else Decimal(str(v)).quantize(Decimal(places))
