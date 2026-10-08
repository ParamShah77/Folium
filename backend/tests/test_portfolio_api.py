"""Portfolio-aware Folium: holdings, other assets, valuation, portfolio-linked
analyses, Tier 1 registration, "keep me signed in", and report downloads.

Live prices are disabled in the suite (conftest), so holdings are valued at
their average cost and gold at its buy price — which makes the arithmetic
below exact.
"""
from __future__ import annotations

import pytest

from .helpers import STRONG_PASSWORD, csrf_header, login_user, register_and_verify, verify_user_via_redis

pytestmark = pytest.mark.asyncio


async def _authed(client, redis_conn, email: str) -> None:
    await register_and_verify(client, redis_conn, email)
    resp = await login_user(client, email)
    assert resp.status_code == 200, resp.text


async def _add(client, **body):
    return await client.post("/v1/portfolio/holdings", json=body, headers=csrf_header(client))


STOCK = {"asset_type": "equity", "symbol": "HDFCBANK", "quantity": 100, "avg_buy_price": 1500}
FUND = {"asset_type": "mf", "scheme_code": "122639", "name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        "quantity": 250.5, "avg_buy_price": 80}


# --------------------------------------------------------------------------- #
# Holdings CRUD + isolation
# --------------------------------------------------------------------------- #
async def test_add_list_edit_delete_holdings(client, redis_conn):
    await _authed(client, redis_conn, "pf-crud@example.com")
    stock = await _add(client, **STOCK)
    assert stock.status_code == 201, stock.text
    fund = await _add(client, **FUND)
    assert fund.status_code == 201, fund.text

    pf = (await client.get("/v1/portfolio")).json()
    kinds = sorted(h["asset_type"] for h in pf["holdings"])
    assert kinds == ["equity", "mf"]
    mf = next(h for h in pf["holdings"] if h["asset_type"] == "mf")
    assert mf["quantity"] == pytest.approx(250.5)   # fractional units survive
    assert mf["price_source"] == "unavailable"       # prices are off in tests

    hid = stock.json()["holding_id"]
    edit = await client.put(f"/v1/portfolio/holdings/{hid}", json={**STOCK, "quantity": 120},
                            headers=csrf_header(client))
    assert edit.status_code == 200
    gone = await client.delete(f"/v1/portfolio/holdings/{hid}", headers=csrf_header(client))
    assert gone.status_code == 200
    assert len((await client.get("/v1/portfolio")).json()["holdings"]) == 1


async def test_duplicate_holding_is_409(client, redis_conn):
    await _authed(client, redis_conn, "pf-dup@example.com")
    assert (await _add(client, **STOCK)).status_code == 201
    dup = await _add(client, **STOCK)
    assert dup.status_code == 409
    assert dup.json()["error"] == "HOLDING_EXISTS"


async def test_holding_validation(client, redis_conn):
    await _authed(client, redis_conn, "pf-valid@example.com")
    assert (await _add(client, asset_type="equity", quantity=1, avg_buy_price=10)).status_code == 422
    assert (await _add(client, **{**STOCK, "quantity": 1.5})).status_code == 422   # whole shares
    assert (await _add(client, asset_type="mf", quantity=1, avg_buy_price=10, name="X")).status_code == 422


async def test_holdings_are_private_to_their_owner(client, redis_conn):
    await _authed(client, redis_conn, "pf-owner@example.com")
    hid = (await _add(client, **STOCK)).json()["holding_id"]
    await client.post("/v1/auth/logout", headers=csrf_header(client))

    await _authed(client, redis_conn, "pf-intruder@example.com")
    assert (await client.get("/v1/portfolio")).json()["holdings"] == []
    edit = await client.put(f"/v1/portfolio/holdings/{hid}", json=STOCK, headers=csrf_header(client))
    assert edit.status_code == 404                     # invisible, not forbidden
    gone = await client.delete(f"/v1/portfolio/holdings/{hid}", headers=csrf_header(client))
    assert gone.status_code == 404


# --------------------------------------------------------------------------- #
# Net worth + surplus (FOLIUM_MASTER.md §4)
# --------------------------------------------------------------------------- #
async def test_summary_follows_the_net_worth_and_surplus_formulas(client, redis_conn):
    await register_and_verify_with_profile(client, redis_conn, "pf-sum@example.com")
    await _add(client, **STOCK)                    # 100 x 1500 = 1,50,000
    await _add(client, **FUND)                     # 250.5 x 80 = 20,040
    assets = {
        "gold_grams": 10, "gold_buy_price_per_gram": 6000,   # 60,000 (buy price: no live gold)
        "fixed_deposits": 100000, "savings_balance": 50000,
        "real_estate_value": 5000000, "home_loan_outstanding": 2000000,
        "other_loans_outstanding": 300000, "rent_received": 15000,
    }
    assert (await client.put("/v1/portfolio/assets", json=assets, headers=csrf_header(client))).status_code == 200

    s = (await client.get("/v1/portfolio")).json()["summary"]
    liquid = 150000 + 20040 + 60000 + 100000 + 50000
    assert s["liquid"] == pytest.approx(liquid)
    assert s["net_worth"] == pytest.approx(liquid + 5000000 - 2000000 - 300000)
    assert s["equity_share"] == pytest.approx(round((150000 + 20040) / liquid, 4))
    # surplus = income + rent received - (EMIs + rent paid + education)
    assert s["committed_outflow"] == pytest.approx(20000 + 15000 + 5000)
    assert s["monthly_surplus"] == pytest.approx(120000 + 15000 - 40000)


async def register_and_verify_with_profile(client, redis_conn, email):
    body = {
        "email": email, "password": STRONG_PASSWORD, "name": "Planner",
        "age": 38, "monthly_income": 120000, "risk_tolerance": 0.5, "investment_horizon": 15,
        "has_emergency_fund": True, "financial_strategy": "moderate", "goal": "Wealth growth",
        "monthly_emi": 20000, "rent_paid": 15000, "education_monthly": 5000, "education_end_year": 2031,
    }
    resp = await client.post("/v1/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    assert (await verify_user_via_redis(client, redis_conn, email)).status_code == 200
    assert (await login_user(client, email)).status_code == 200


async def test_registration_derives_monthly_expense_from_tier1(client, redis_conn):
    await register_and_verify_with_profile(client, redis_conn, "tier1@example.com")
    p = (await client.get("/v1/users/me/profile")).json()["profile"]
    assert p["monthly_emi"] == 20000 and p["rent_paid"] == 15000 and p["education_monthly"] == 5000
    assert p["education_end_year"] == 2031
    assert p["monthly_expense"] == 40000


# --------------------------------------------------------------------------- #
# Portfolio-linked analysis
# --------------------------------------------------------------------------- #
async def test_analysis_of_a_holding_uses_the_portfolio(client, redis_conn, db_conn):
    await register_and_verify_with_profile(client, redis_conn, "pf-analyse@example.com")
    hid = (await _add(client, **STOCK)).json()["holding_id"]
    await _add(client, **FUND)
    await client.put("/v1/portfolio/assets", json={"fixed_deposits": 29960}, headers=csrf_header(client))

    resp = await client.post(
        "/v1/decisions/analyze",
        json={
            "holding_id": hid, "symbol": "IGNORED", "holding_quantity": 1, "avg_buy_price": 1,
            "current_price": 1200, "unrealized_pnl_pct": 0, "decision_intent": "sell",
        },
        headers=csrf_header(client),
    )
    assert resp.status_code == 202, resp.text
    decision_id = resp.json()["decision_id"]
    d = (await client.get(f"/v1/decisions/{decision_id}/result")).json()["decision"]

    # Position comes from the portfolio, priced at the confirmed 1,200.
    assert d["symbol"] == "HDFCBANK" and d["holding_quantity"] == 100
    assert d["unrealized_pnl_pct"] == pytest.approx(-0.2)
    ctx = d["portfolio_context"]
    assert ctx["position_value"] == pytest.approx(120000)
    assert ctx["liquid"] == pytest.approx(150000 + 20040 + 29960)
    # The bias model saw the real position size and asset mix, not standard values.
    bias = d["explainer_output"]["bias"]
    inputs = bias["model_inputs"]
    assert inputs["position_share"] == pytest.approx(ctx["position_share"], abs=1e-6)
    assert inputs["gold_share"] == pytest.approx(ctx["gold_share"], abs=1e-6)
    assert inputs["action"] == "sell"
    assert "position_share" not in bias["fixed_inputs"]
    assert d["simulation_curves"]["allocation_basis"] == "portfolio"
    # The projection runs to this investor's own 15-year horizon.
    assert d["simulation_curves"]["horizon_years"] == 15
    assert d["simulation_curves"]["horizon_source"] == "profile"
    assert d["simulation_curves"]["years"][-1] == 15


async def test_analysis_of_someone_elses_holding_is_404(client, redis_conn):
    await _authed(client, redis_conn, "pf-a@example.com")
    hid = (await _add(client, **STOCK)).json()["holding_id"]
    await client.post("/v1/auth/logout", headers=csrf_header(client))
    await _authed(client, redis_conn, "pf-b@example.com")
    resp = await client.post(
        "/v1/decisions/analyze",
        json={"holding_id": hid, "symbol": "X", "holding_quantity": 1, "avg_buy_price": 1,
              "current_price": 1, "unrealized_pnl_pct": 0, "decision_intent": "sell"},
        headers=csrf_header(client),
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
async def test_report_downloads(client, redis_conn):
    await _authed(client, redis_conn, "report@example.com")
    resp = await client.post(
        "/v1/decisions/analyze",
        json={"symbol": "INFY", "holding_quantity": 10, "avg_buy_price": 1500, "current_price": 1400,
              "unrealized_pnl_pct": -0.0667, "decision_intent": "sell"},
        headers=csrf_header(client),
    )
    did = resp.json()["decision_id"]

    html_en = await client.get(f"/v1/decisions/{did}/report", params={"format": "html", "lang": "en"})
    assert html_en.status_code == 200
    assert "attachment" in html_en.headers["content-disposition"]
    assert "<html" in html_en.text
    assert html_en.headers["content-type"].startswith("text/html")

    html_hi = await client.get(f"/v1/decisions/{did}/report", params={"format": "html", "lang": "hi"})
    assert html_hi.status_code == 200 and 'lang="hi"' in html_hi.text

    pdf = await client.get(f"/v1/decisions/{did}/report", params={"format": "pdf", "lang": "en"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    hi_pdf = await client.get(f"/v1/decisions/{did}/report", params={"format": "pdf", "lang": "hi"})
    assert hi_pdf.status_code == 400 and hi_pdf.json()["error"] == "PDF_ENGLISH_ONLY"


# --------------------------------------------------------------------------- #
# Keep me signed in
# --------------------------------------------------------------------------- #
def _auth_cookie_headers(resp) -> list[str]:
    return [h for h in resp.headers.get_list("set-cookie")
            if h.split("=", 1)[0] in ("access_token", "refresh_token", "csrf_token")]


async def test_unticked_keep_signed_in_sets_session_cookies(client, redis_conn):
    await register_and_verify(client, redis_conn, "session-only@example.com")
    resp = await client.post("/v1/auth/login", json={
        "email": "session-only@example.com", "password": STRONG_PASSWORD, "remember_me": False,
    })
    assert resp.status_code == 200
    cookies = _auth_cookie_headers(resp)
    assert len(cookies) == 3
    assert all("max-age" not in c.lower() and "expires" not in c.lower() for c in cookies)

    # Refreshing keeps the session-only choice.
    refreshed = await client.post("/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert all("max-age" not in c.lower() for c in _auth_cookie_headers(refreshed))


async def test_ticked_keep_signed_in_sets_persistent_cookies(client, redis_conn):
    await register_and_verify(client, redis_conn, "remembered@example.com")
    resp = await client.post("/v1/auth/login", json={
        "email": "remembered@example.com", "password": STRONG_PASSWORD, "remember_me": True,
    })
    assert all("max-age" in c.lower() for c in _auth_cookie_headers(resp))
