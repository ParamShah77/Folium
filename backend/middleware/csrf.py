"""CSRF validation middleware — double-submit cookie pattern (§1H).

Rules:
  * Skip GET / HEAD / OPTIONS (safe methods).
  * Skip the pre-session auth endpoints that run BEFORE a CSRF cookie exists:
    register, login, verify-email, forgot-password, reset-password, refresh.
    (These are protected by rate limiting + their own token/credential checks.)
  * For every other mutating request: the ``csrf_token`` cookie and the
    ``X-CSRF-Token`` header must both be present and equal, else 403.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths exempt from CSRF because no session/CSRF cookie exists yet (§1H).
# Matched as suffixes so the /v1 prefix and any mount point are tolerated.
_EXEMPT_SUFFIXES = (
    "/auth/register",
    "/auth/login",
    "/auth/login/mfa",  # TODO(M2): MFA second step — still pre-session
    "/auth/verify-email",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/refresh",
)


def _is_exempt(path: str) -> bool:
    return any(path.endswith(suffix) for suffix in _EXEMPT_SUFFIXES)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS or _is_exempt(request.url.path):
            return await call_next(request)

        cookie = request.cookies.get(CSRF_COOKIE_NAME)
        header = request.headers.get(CSRF_HEADER_NAME)

        if not cookie or not header or cookie != header:
            request_id = getattr(request.state, "request_id", "unknown")
            return JSONResponse(
                status_code=403,
                content={
                    "error": "CSRF_FAILED",
                    "message": "CSRF validation failed",
                    "request_id": request_id,
                },
            )
        return await call_next(request)
