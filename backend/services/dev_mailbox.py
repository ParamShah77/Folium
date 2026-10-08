"""In-memory outbox for development — makes sign-up demoable without Resend.

With ``ENV=development`` and no ``RESEND_API_KEY``, ``EmailService`` logs mail
instead of sending it (Amendment 6). That keeps verification and reset links in
the server log, where a live demo of sign-up cannot reach them. This module
keeps the last few dev-fallback emails in process memory, and
``GET /v1/dev/mailbox`` shows them in the web app.

It is inert outside the dev fallback: nothing is ever recorded when real email
is configured, and the endpoint is only mounted in development. Process memory
(not Redis) is deliberate — the mailbox dies with the server and never reaches
a shared store.
"""
from __future__ import annotations

import re
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

_MAX_MESSAGES = 25
_LINK = re.compile(r"https?://\S+")

_messages: deque[dict[str, Any]] = deque(maxlen=_MAX_MESSAGES)
_lock = threading.Lock()


def record(to: str, subject: str, text: str) -> None:
    link = _LINK.search(text)
    with _lock:
        _messages.appendleft(
            {
                "to": to,
                "subject": subject,
                "body": text,
                "link": link.group(0) if link else None,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def messages() -> list[dict[str, Any]]:
    with _lock:
        return list(_messages)
