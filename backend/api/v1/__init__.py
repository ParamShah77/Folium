"""/v1 API router (§3B).

Milestone 1 wires the auth router only. The decisions / simulate / audit /
market / portfolio / sip / admin routers (§3A) arrive in later milestones and
are left as commented seams so the include order is obvious.
"""
from __future__ import annotations

from fastapi import APIRouter

from ...auth.routes import router as auth_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

# TODO(M3): wire the remaining routers as they are built:
# v1_router.include_router(users_router,     prefix="/users",     tags=["Users"])
# v1_router.include_router(decisions_router, prefix="/decisions", tags=["Decisions"])
# v1_router.include_router(simulate_router,  prefix="/simulate",  tags=["Simulation"])
# v1_router.include_router(audit_router,     prefix="/audit",     tags=["Audit"])
# v1_router.include_router(market_router,    prefix="/market",    tags=["Market"])
# v1_router.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
# v1_router.include_router(sip_router,       prefix="/sip",       tags=["SIP"])
# v1_router.include_router(admin_router,     prefix="/admin",     tags=["Admin"])

__all__ = ["v1_router"]
