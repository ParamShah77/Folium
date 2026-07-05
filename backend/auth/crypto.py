"""Symmetric encryption helpers (Fernet) for secrets at rest.

Amendment 7: ``FERNET_KEY`` is a urlsafe-base64 key from
``cryptography.fernet.Fernet.generate_key()`` (NOT hex). Used to encrypt TOTP
secrets and future Kite tokens.

Milestone 1 does not encrypt anything yet (MFA is Milestone 2), but these
helpers are the single seam that M2 will call, so they live here and are
exercised by config loading.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().FERNET_KEY
    if not key:
        raise RuntimeError(
            "FERNET_KEY is not set. Run scripts/generate_dev_keys.py for local dev."
        )
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret (e.g. a TOTP secret) -> urlsafe token string."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Reverse of :func:`encrypt_secret`."""
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
