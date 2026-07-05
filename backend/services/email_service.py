"""Transactional email via Resend, with a dev-log fallback (Amendment 6).

When ``ENV=development`` and ``RESEND_API_KEY`` is empty, the full email —
including the verification / reset link — is printed to the server log instead
of being sent. This lets the whole auth flow be exercised locally with no
Resend account. The tests rely on the Redis token, not on parsing the log.
"""
from __future__ import annotations

import structlog

from ..config import Settings, get_settings

logger = structlog.get_logger(__name__)


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def _use_dev_fallback(self) -> bool:
        return self._settings.is_development and not self._settings.RESEND_API_KEY

    async def _send(self, to: str, subject: str, html: str, text: str) -> None:
        if self._use_dev_fallback:
            logger.info(
                "email_dev_fallback",
                to=to,
                subject=subject,
                body=text,
                note="RESEND_API_KEY empty in dev — email logged, not sent (Amendment 6)",
            )
            return

        if not self._settings.RESEND_API_KEY:
            # Not dev and no key: surface loudly rather than silently dropping mail.
            logger.error("email_not_configured", to=to, subject=subject)
            return

        # Import lazily so the dependency isn't needed when using the dev fallback.
        import resend

        resend.api_key = self._settings.RESEND_API_KEY
        try:
            resend.Emails.send(
                {
                    "from": self._settings.EMAIL_FROM,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                    "text": text,
                }
            )
            logger.info("email_sent", to=to, subject=subject)
        except Exception as exc:  # noqa: BLE001 - email must never crash the request
            logger.error("email_send_failed", to=to, subject=subject, error=str(exc))

    # -- Public templates --------------------------------------------- #
    async def send_verification_email(self, to: str, token: str) -> None:
        link = f"{self._settings.FRONTEND_URL}/auth/verify-email?token={token}"
        subject = "Verify your ScaleAI account"
        text = (
            f"Welcome to ScaleAI. Verify your account by opening this link:\n{link}\n\n"
            "This link expires in 24 hours."
        )
        html = (
            f"<p>Welcome to ScaleAI.</p>"
            f'<p><a href="{link}">Verify your account</a></p>'
            f"<p>This link expires in 24 hours.</p>"
        )
        await self._send(to, subject, html, text)

    async def send_password_reset_email(self, to: str, token: str) -> None:
        link = f"{self._settings.FRONTEND_URL}/reset-password?token={token}"
        subject = "Reset your password"
        text = (
            f"Reset your password by opening this link:\n{link}\n\n"
            "This link expires in 15 minutes. If you did not request this, ignore this email."
        )
        html = (
            f'<p><a href="{link}">Reset your password</a></p>'
            f"<p>This link expires in 15 minutes.</p>"
        )
        await self._send(to, subject, html, text)


# Module-level default instance (settings resolved lazily on first send).
email_service = EmailService()
