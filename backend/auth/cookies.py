"""Auth cookie helpers — consistent flags across login/refresh/logout (§1C/§1H).

Cookies:
    access_token   httpOnly, Secure(dev off), SameSite=Lax, path=/
    refresh_token  httpOnly, Secure(dev off), SameSite=Lax, path=/
    csrf_token     NOT httpOnly (JS-readable), Secure(dev off), SameSite=Lax, path=/

Secure is off in development (http://localhost) and on otherwise
(``Settings.cookie_secure``).
"""
from __future__ import annotations

from fastapi import Response

from ..config import get_settings
from .csrf import CSRF_COOKIE_NAME
from .dependencies import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME

_SAMESITE = "lax"


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    access_ttl: int,
    refresh_ttl: int,
) -> None:
    secure = get_settings().cookie_secure

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=access_ttl,
        httponly=True,
        secure=secure,
        samesite=_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=refresh_ttl,
        httponly=True,
        secure=secure,
        samesite=_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=refresh_ttl,  # CSRF lifetime matches the session (§1H)
        httponly=False,  # must be JS-readable
        secure=secure,
        samesite=_SAMESITE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(key=name, path="/")
