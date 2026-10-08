"""/v1 API router (§3B).

Milestones 1+2 wired auth, users (profile), and admin (MFA reset only,
Amendment 5); Milestone 3 adds decisions (§3F: async submit + SSE stream). The
simulate / audit / market / portfolio / sip routers (§3A) arrive with Phases 5
and 6 and are left as commented seams so the include order is obvious.
"""
from __future__ import annotations

from fastapi import APIRouter

from ...auth.routes import router as auth_router
from .admin import router as admin_router
from .decisions import router as decisions_router
from .market import router as market_router
from .meta import dev_mailbox_enabled, dev_router, meta_router
from .portfolio import router as portfolio_router
from .users import router as users_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
v1_router.include_router(users_router, prefix="/users", tags=["Users"])
v1_router.include_router(decisions_router, prefix="/decisions", tags=["Decisions"])
v1_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
v1_router.include_router(market_router, prefix="/market", tags=["Market"])
v1_router.include_router(meta_router, prefix="/meta", tags=["Meta"])
v1_router.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])

# Development-only outbox: not even a route unless email is in dev fallback.
if dev_mailbox_enabled():
    v1_router.include_router(dev_router, prefix="/dev", tags=["Development"])

# TODO: wire the remaining routers as they are built:
# v1_router.include_router(simulate_router,  prefix="/simulate",  tags=["Simulation"])
# v1_router.include_router(audit_router,     prefix="/audit",     tags=["Audit"])
# v1_router.include_router(sip_router,       prefix="/sip",       tags=["SIP"])

__all__ = ["v1_router"]
