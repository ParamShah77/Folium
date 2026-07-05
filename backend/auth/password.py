"""Password hashing (bcrypt cost 12) and strength checking (zxcvbn >= 3).

The WEAK_PASSWORD path raises ``WeakPasswordError`` carrying the score and
zxcvbn suggestions so the route can return the §3D error shape:
    { "error": "WEAK_PASSWORD", "message": ..., "detail": { score, suggestions } }
"""
from __future__ import annotations

from typing import List

import bcrypt
from zxcvbn import zxcvbn

_BCRYPT_ROUNDS = 12
_MIN_ZXCVBN_SCORE = 3


class WeakPasswordError(Exception):
    """Raised when a password scores below the zxcvbn threshold."""

    def __init__(self, score: int, suggestions: List[str]) -> None:
        self.score = score
        # zxcvbn sometimes returns no suggestions for a merely-short password;
        # give the user something actionable.
        self.suggestions = suggestions or [
            "Use a longer passphrase of several unrelated words.",
            "Add numbers or symbols and avoid common patterns.",
        ]
        super().__init__("Password is too weak.")


def _bcrypt_safe(password: str) -> bytes:
    """bcrypt only uses the first 72 bytes; truncate defensively to avoid the
    ValueError that bcrypt>=4 raises on longer inputs."""
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    """Return a bcrypt hash (cost 12) as a UTF-8 string."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(_bcrypt_safe(password), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time bcrypt verify. Returns False on any malformed hash."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_bcrypt_safe(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def assert_password_strength(password: str, user_inputs: List[str] | None = None) -> None:
    """Raise ``WeakPasswordError`` if zxcvbn score < 3 (§1B).

    ``user_inputs`` (email, name) are passed to zxcvbn so passwords derived from
    them score lower.
    """
    result = zxcvbn(password, user_inputs=user_inputs or [])
    score = int(result.get("score", 0))
    if score < _MIN_ZXCVBN_SCORE:
        feedback = result.get("feedback", {}) or {}
        suggestions = list(feedback.get("suggestions", []) or [])
        warning = feedback.get("warning")
        if warning:
            suggestions = [warning, *suggestions]
        raise WeakPasswordError(score=score, suggestions=suggestions)
