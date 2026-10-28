"""Seed demo accounts with complete portfolios and real analyses.

Creates two verified accounts, each with:
  * a Tier 1 profile (income, EMIs, rent paid, education fees, risk, horizon),
  * a portfolio of shares and a mutual fund, plus gold, deposits, savings,
    property and loans (FOLIUM_MASTER.md §4),
  * several portfolio-linked decisions run through the *real* pipeline
    (pattern detection, 20-year simulation, explanation in English and Hindi,
    recommendation, audit record).

Average buy prices are set relative to the live price at seed time, so each
holding shows the gain or loss its scenario needs (e.g. HDFCBANK down 18%)
whatever the market has done since. Without network access, fixed fallback
prices are used.

Two accounts, deliberately: logging in as the second shows none of the first
one's data, which demonstrates the per-account isolation.

Idempotent: an account that already exists is left untouched. Accounts can't
be deleted and re-created, because ``audit_logs`` is append-only (migration
0004). ``--refresh`` re-runs the pipeline over existing demo decisions instead,
after reconciling each portfolio snapshot (see :func:`_reconcile`); every
re-run adds a new entry to the audit chain.

Credentials are documented in DEMO.md; they are demo values only.

Run (repo root, PostgreSQL + Memurai running):
    D:/FolioEnv/venv313/Scripts/python.exe scripts/with_env.py scripts/seed_demo.py [--refresh]
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.auth.password import hash_password  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.core import run_analysis_pipeline  # noqa: E402  (registers all steps)
from backend.db import Database, RedisService, create_db_pool, create_redis_client  # noqa: E402
from backend.services.market_data import capture_market_context  # noqa: E402
from backend.services.portfolio import ASSET_FIELDS, decision_context, load_portfolio  # noqa: E402
from backend.services.prices import mf_nav, stock_quote, stock_risk  # noqa: E402

# Demo-only credential, also recorded in DEMO.md.
DEMO_PASSWORD = "Folium-Demo-Walkthrough-2026"

# Fallback prices, used only if live prices can't be fetched while seeding.
FALLBACK_PRICE = {
    "HDFCBANK": 1650.0, "INFY": 1500.0, "RELIANCE": 1400.0, "ITC": 420.0,
    "ASIANPAINT": 2400.0, "SBIN": 800.0, "TCS": 3100.0, "MF122639": 80.0,
}

ACCOUNTS = [
    {
        "email": "ananya.iyer@example.com",
        "name": "Ananya Iyer",
        "profile": dict(age=34, monthly_income=160000, monthly_emi=22000, rent_paid=28000,
                        education_monthly=0, education_end_year=None, risk_tolerance=0.55,
                        investment_horizon=20, has_emergency_fund=True,
                        financial_strategy="moderate", goal="Wealth growth"),
        "assets": dict(gold_grams=40, gold_buy_price_per_gram=9200, fixed_deposits=300000,
                       savings_balance=150000, real_estate_value=None, home_loan_outstanding=None,
                       other_loans_outstanding=180000, rent_received=None, monthly_sip=25000),
        # (key, asset_type, quantity, gain/loss vs buy price, fund name)
        "holdings": [
            ("HDFCBANK", "equity", 120, -0.18, None),
            ("INFY", "equity", 80, 0.27, None),
            ("RELIANCE", "equity", 40, 0.23, None),
            ("ITC", "equity", 300, -0.05, None),
            ("ASIANPAINT", "equity", 25, -0.22, None),
            ("MF122639", "mf", 300.0, 0.25, "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"),
        ],
        "decisions": [
            # (holding key, intent, months held, days ago, reasoning)
            ("HDFCBANK", "sell", 14, 21, "Banking stocks keep falling and I want out before it gets worse."),
            ("INFY", "hold", 30, 17, None),
            ("MF122639", "buy_more", 26, 12, "Everyone at work is putting more into flexi-cap funds right now."),
            ("RELIANCE", "sell", 6, 8, "Booking profits while it's up, it can't keep going."),
            ("ITC", "hold", 26, 4, None),
            ("ASIANPAINT", "sell", 20, 1, "I can't watch it lose any more."),
        ],
    },
    {
        "email": "rohan.mehta@example.com",
        "name": "Rohan Mehta",
        "profile": dict(age=52, monthly_income=240000, monthly_emi=45000, rent_paid=0,
                        education_monthly=30000, education_end_year=2029, risk_tolerance=0.3,
                        investment_horizon=10, has_emergency_fund=True,
                        financial_strategy="conservative", goal="Retirement"),
        "assets": dict(gold_grams=120, gold_buy_price_per_gram=6100, fixed_deposits=1200000,
                       savings_balance=400000, real_estate_value=9500000, home_loan_outstanding=3200000,
                       other_loans_outstanding=None, rent_received=22000, monthly_sip=40000),
        "holdings": [
            ("SBIN", "equity", 150, -0.16, None),
            ("TCS", "equity", 30, 0.14, None),
        ],
        "decisions": [
            ("SBIN", "sell", 18, 6, "The market is falling, I should protect my retirement money."),
            ("TCS", "hold", 40, 2, None),
        ],
    },
]


async def _live_price(key: str, asset_type: str) -> float:
    quote = await (mf_nav(key[2:]) if asset_type == "mf" else stock_quote(key, "NSE"))
    return float(quote["price"]) if quote else FALLBACK_PRICE[key]


async def _create_account(db: Database, account: dict) -> str:
    p = account["profile"]
    outflow = p["monthly_emi"] + p["rent_paid"] + p["education_monthly"]
    user_id = str(await db.fetchval(
        """
        INSERT INTO users (email, password_hash, name, age, monthly_income, monthly_expense,
                           monthly_emi, rent_paid, education_monthly, education_end_year,
                           risk_tolerance, investment_horizon, has_emergency_fund,
                           financial_strategy, goal, is_active, email_verified)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15, TRUE, TRUE)
        RETURNING user_id
        """,
        account["email"], hash_password(DEMO_PASSWORD), account["name"], p["age"],
        p["monthly_income"], outflow, p["monthly_emi"], p["rent_paid"], p["education_monthly"],
        p["education_end_year"], p["risk_tolerance"], p["investment_horizon"],
        p["has_emergency_fund"], p["financial_strategy"], p["goal"],
    ))
    a = account["assets"]
    async with db.rls_transaction(user_id) as conn:
        await conn.execute(
            f"INSERT INTO financial_profiles (user_id, {', '.join(ASSET_FIELDS)}) "
            f"VALUES ($1, {', '.join(f'${i}' for i in range(2, len(ASSET_FIELDS) + 2))})",
            user_id, *[a[f] for f in ASSET_FIELDS],
        )
        for key, asset_type, qty, gain, name in account["holdings"]:
            live = await _live_price(key, asset_type)
            avg = round(live / (1 + gain), 2 if asset_type == "equity" else 4)
            await conn.execute(
                """
                INSERT INTO portfolios (user_id, asset_type, symbol, exchange, name, scheme_code,
                                        quantity, avg_buy_price)
                VALUES ($1,$2,$3,'NSE',$4,$5,$6,$7)
                """,
                user_id, asset_type, key, name or key,
                key[2:] if asset_type == "mf" else None, qty, avg,
            )
    return user_id


async def _seed_decision(db: Database, redis: RedisService, user_id: str, market: dict, spec: tuple) -> str:
    key, intent, months, days_ago, reasoning = spec
    async with db.rls_transaction(user_id) as conn:
        portfolio = await load_portfolio(conn, user_id)
    holding = next(h for h in portfolio["holdings"] if h["symbol"] == key)
    price = holding["current_price"] or FALLBACK_PRICE[key]
    context = decision_context(portfolio, {**holding, "value": holding["quantity"] * price})
    pnl = round(price / holding["avg_buy_price"] - 1, 4)
    held_days = round(months * 30.44)

    async with db.rls_transaction(user_id) as conn:
        decision_id = str(await conn.fetchval(
            """
            INSERT INTO decisions (user_id, status, symbol, exchange, holding_quantity, avg_buy_price,
                                   current_price, unrealized_pnl_pct, decision_intent, user_reasoning,
                                   holding_period_days, market_trend, tax_category,
                                   nifty_1m_return, nifty_volatility_30d, nifty_1d_change,
                                   vix_value, market_data_source, holding_id, portfolio_context)
            VALUES ($1,'pending',$2,'NSE',$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18::jsonb)
            RETURNING decision_id
            """,
            user_id, key, holding["quantity"], holding["avg_buy_price"], price, pnl, intent,
            reasoning, held_days, market["market_trend"], "LTCG" if held_days >= 365 else "STCG",
            market["nifty_1m_return"], market["nifty_volatility_30d"], market["nifty_1d_change"],
            market["vix_value"], market["market_data_source"], holding["holding_id"], json.dumps(context),
        ))

    await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)

    async with db.rls_transaction(user_id) as conn:
        await conn.execute(
            """
            UPDATE decisions
               SET submitted_at = NOW() - $2::interval,
                   completed_at = NOW() - $2::interval + INTERVAL '9 seconds'
             WHERE decision_id = $1
            """,
            decision_id, timedelta(days=days_ago, hours=3),
        )
    return decision_id


def _reconcile(context: dict, portfolio: dict) -> dict:
    """Make a snapshot's derived figures add up, all from one moment.

    Refreshes used to add only *missing* keys, so a snapshot could mix an old
    ``liquid`` with an allocation (and gold share) priced on a later day. The
    asset mix is rebuilt from today's portfolio with this holding at the
    analysis's own price; every share, liquid and net worth follow from it.
    """
    summary = portfolio["summary"]
    alloc = {k: v["value"] for k, v in summary["allocation"].items()}
    position_value = float(context["position_value"])
    holding = next(
        (h for h in portfolio["holdings"] if str(h["holding_id"]) == str(context.get("holding_id"))), None
    )
    if holding is not None:
        bucket = "mutual_funds" if context.get("asset_type") == "mf" else "stocks"
        alloc[bucket] = round(alloc[bucket] - holding["value"] + position_value, 2)
    liquid = round(sum(alloc.values()), 2)

    def share(x: float) -> float:
        return round(x / liquid, 4) if liquid > 0 else 0.0

    return {
        **context,
        "allocation": alloc,
        "liquid": liquid,
        "position_share": share(position_value),
        "equity_share": share(alloc["stocks"] + alloc["mutual_funds"]),
        "gold_share": share(alloc["gold"]),
        "real_estate": summary["real_estate"],
        "liabilities": summary["liabilities"],
        "net_worth": round(liquid + summary["real_estate"] - summary["liabilities"], 2),
    }


async def _refresh(db: Database, redis: RedisService) -> None:
    for account in ACCOUNTS:
        user_id = await db.fetchval("SELECT user_id FROM users WHERE email = $1", account["email"])
        if not user_id:
            print(f"- {account['email']} not seeded yet; run without --refresh first")
            continue
        user_id = str(user_id)
        async with db.rls_transaction(user_id) as conn:
            # Fields added after the account was seeded (e.g. monthly_sip, 0010).
            for field, value in account["assets"].items():
                if value is not None:
                    await conn.execute(
                        f"UPDATE financial_profiles SET {field} = $2 WHERE user_id = $1 AND {field} IS NULL",
                        user_id, value,
                    )
            rows = await conn.fetch("SELECT decision_id, symbol, exchange, portfolio_context FROM decisions ORDER BY submitted_at")
            # A refresh re-runs everything with today's models, comment reading included.
            await conn.execute("UPDATE decisions SET comment_facts = NULL")
            portfolio = await load_portfolio(conn, user_id)
        print(f"~ {account['email']}: re-running {len(rows)} analyses")
        # Snapshots taken before bias model v4 / simulation v2 lack their
        # inputs: missing keys come from today's portfolio, and the asset mix
        # is then reconciled so every figure in a snapshot is from one moment.
        summary = portfolio["summary"]
        backfill = {
            "gold_share": summary["allocation"]["gold"]["share"],
            "real_estate": summary["real_estate"],
            "liabilities": summary["liabilities"],
            "allocation": {k: v["value"] for k, v in summary["allocation"].items()},
            "monthly_sip": summary["monthly_sip"],
            "education_monthly": summary["education_monthly"],
            "education_end_year": summary["education_end_year"],
        }
        for row in rows:
            decision_id = str(row["decision_id"])
            context = row["portfolio_context"]
            if isinstance(context, str):
                context = json.loads(context)
            missing = {k: v for k, v in backfill.items() if context is not None and k not in context}
            if context is not None and context.get("asset_type") == "equity" and "stock_risk" not in context:
                risk = await stock_risk(row["symbol"], row["exchange"] or "NSE")
                if risk:
                    missing["stock_risk"] = risk
            if context is not None:
                context = _reconcile({**context, **missing}, portfolio)
                async with db.rls_transaction(user_id) as conn:
                    await conn.execute(
                        "UPDATE decisions SET portfolio_context = $2::jsonb WHERE decision_id = $1",
                        decision_id, json.dumps(context),
                    )
            await run_analysis_pipeline(decision_id, user_id, db=db, redis=redis)
            async with db.rls_transaction(user_id) as conn:
                await conn.execute(
                    "UPDATE decisions SET completed_at = submitted_at + INTERVAL '9 seconds' WHERE decision_id = $1",
                    decision_id,
                )


async def main() -> int:
    settings = get_settings()
    pool = await create_db_pool(settings.DATABASE_URL)
    redis_client = create_redis_client(settings.REDIS_URL)
    db, redis = Database(pool), RedisService(redis_client)
    try:
        if "--refresh" in sys.argv:
            await _refresh(db, redis)
            print("Done.")
            return 0
        print("Capturing market context…")
        market = await capture_market_context()
        print(f"  market data: {market['market_data_source']}")
        for account in ACCOUNTS:
            if await db.fetchval("SELECT 1 FROM users WHERE email = $1", account["email"]):
                print(f"- {account['email']} already exists; leaving it as is")
                continue
            user_id = await _create_account(db, account)
            print(f"+ {account['email']} created with {len(account['holdings'])} holdings")
            for spec in account["decisions"]:
                decision_id = await _seed_decision(db, redis, user_id, market, spec)
                async with db.rls_transaction(user_id) as conn:
                    row = await conn.fetchrow(
                        "SELECT status, bias_detected, recommendation, error_message, "
                        "portfolio_context->>'position_share' AS share FROM decisions WHERE decision_id = $1",
                        decision_id,
                    )
                if row["status"] != "complete":
                    print(f"    {spec[0]:<11} FAILED: {row['error_message']}")
                    continue
                print(f"    {spec[0]:<11} {spec[1]:<9} -> {row['bias_detected']:<19} "
                      f"recommend {row['recommendation']:<9} ({float(row['share']):.0%} of liquid)")
        print("\nDone. Demo credentials are in DEMO.md.")
        return 0
    finally:
        await db.close()
        await redis.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
