"""RS256 JWT signing / verification and refresh-token hashing.

Tokens (§1A):
    access  — 15 min, httpOnly cookie
    refresh — 7 days, httpOnly cookie
Both carry: sub (user_id), role, jti, iat, exp, plus a ``type`` claim
("access" | "refresh") so a refresh token can't be replayed as an access token.

Signed with the RS256 private key; verified with the public key. Rotating the
private key auto-invalidates every outstanding token.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import jwt  # PyJWT

from ..config import get_settings

_ALGORITHM = "RS256"


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    access_jti: str
    refresh_jti: str
    access_expires_at: datetime
    refresh_expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_jti() -> str:
    return uuid.uuid4().hex


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_private_key, algorithm=_ALGORITHM)


def create_access_token(user_id: str, role: str) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at) for a 15-minute access token."""
    settings = get_settings()
    now = _now()
    exp = now + _timedelta(settings.ACCESS_TOKEN_TTL_SECONDS)
    jti = _new_jti()
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return _encode(payload), jti, exp


def create_refresh_token(user_id: str, role: str, remember: bool = True) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at) for a 7-day refresh token.

    ``rm`` records the "keep me signed in" choice so that /refresh, which
    rotates the token, can re-issue cookies with the same lifetime.
    """
    settings = get_settings()
    now = _now()
    exp = now + _timedelta(settings.REFRESH_TOKEN_TTL_SECONDS)
    jti = _new_jti()
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "type": "refresh",
        "rm": bool(remember),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return _encode(payload), jti, exp


def create_token_pair(user_id: str, role: str, remember: bool = True) -> TokenPair:
    access, access_jti, access_exp = create_access_token(user_id, role)
    refresh, refresh_jti, refresh_exp = create_refresh_token(user_id, role, remember)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        access_jti=access_jti,
        refresh_jti=refresh_jti,
        access_expires_at=access_exp,
        refresh_expires_at=refresh_exp,
    )


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or wrong-type."""


def decode_token(token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Verify signature + expiry and return the payload.

    Raises ``TokenError`` on any failure. If ``expected_type`` is given, the
    token's ``type`` claim must match.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError("Unexpected token type")
    return payload


def seconds_until_expiry(payload: dict[str, Any]) -> int:
    """Remaining lifetime of a token in seconds (>= 0), for blacklist TTLs."""
    exp = int(payload.get("exp", 0))
    remaining = exp - int(_now().timestamp())
    return max(0, remaining)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex of a raw refresh token — stored in refresh_tokens.token_hash."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """32-byte hex CSRF token (§1H)."""
    return secrets.token_hex(32)


def generate_url_token(nbytes: int = 32) -> str:
    """Random hex token for email-verify / password-reset Redis keys.

    ``nbytes=32`` -> 64 hex chars, matching §1B's "64-char" verification token.
    """
    return secrets.token_hex(nbytes)


# -- local import kept at bottom to avoid a heavy import at module top --------- #
from datetime import timedelta as _timedelta  # noqa: E402
