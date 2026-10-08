"""Public app configuration + the development mailbox.

``GET /v1/meta/config`` tells the web app which sign-in options exist, so it
never shows a "Continue with Google" button that would only return 503.

``GET /v1/dev/mailbox`` is mounted only in development with no Resend key
(see ``services/dev_mailbox.py``); it is not a route at all in production.

NOTE: no ``from __future__ import annotations`` in route modules (see
auth/routes.py for the slowapi/PEP 563 body-inference reason).
"""
from fastapi import APIRouter

from ...config import get_settings
from ...services import dev_mailbox

meta_router = APIRouter()
dev_router = APIRouter()


def ai_help_available() -> bool:
    """Gemini help can be offered: switched on for this server, with a key (B3)."""
    from ...core.ai_help import available

    return available()


def dev_mailbox_enabled() -> bool:
    settings = get_settings()
    return settings.is_development and not settings.RESEND_API_KEY


@meta_router.get("/config")
async def app_config():
    settings = get_settings()
    return {
        "google_oauth": bool(
            settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
        ),
        "dev_mailbox": dev_mailbox_enabled(),
        "ai_help": ai_help_available(),
        "environment": settings.ENV,
    }


@dev_router.get("/mailbox")
async def mailbox():
    """Most recent dev-fallback emails, newest first."""
    return {"messages": dev_mailbox.messages()}
