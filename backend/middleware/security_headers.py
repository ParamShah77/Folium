"""Security-header middleware (Amendment 11).

The backend sets HSTS / nosniff / X-Frame-Options / Referrer-Policy /
Permissions-Policy. It intentionally does NOT set Content-Security-Policy: per
Amendment 11 the authoritative SPA CSP is delivered by the static host at deploy
time (render.yaml headers), so §3G's FastAPI CSP block is superseded.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # NOTE (Amendment 11): no Content-Security-Policy here — set by static host.
        return response
