"""TOTP MFA + backup-code helpers (§1D/§1E).

TOTP: pyotp, 30-second period, ``valid_window=1`` everywhere (±30s clock drift).
The TOTP secret is stored Fernet-encrypted in ``users.mfa_secret_enc``
(Amendment 7 — FERNET_KEY) and only ever decrypted transiently for verification.

Backup codes: 8 codes of 8 uppercase hex chars (``secrets.token_hex(4).upper()``),
shown to the user ONCE as ``XXXX-XXXX``; only bcrypt hashes are stored in
``mfa_backup_codes``. Codes are single-use (``used`` flag).
"""
from __future__ import annotations

import secrets
from typing import Optional

import bcrypt
import pyotp

from ..db import Database
from .crypto import decrypt_secret, encrypt_secret

MFA_ISSUER = "FinAI Decision Intelligence"
BACKUP_CODE_COUNT = 8


# --------------------------------------------------------------------------- #
# TOTP
# --------------------------------------------------------------------------- #
def generate_totp_secret() -> str:
    """New random base32 TOTP secret (for the setup flow)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    """otpauth:// URI the frontend renders as a QR code (§1D)."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=MFA_ISSUER
    )


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code with ±30s tolerance (§1C/§1D)."""
    if not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


def encrypt_totp_secret(secret: str) -> str:
    """Fernet-encrypt for storage in users.mfa_secret_enc."""
    return encrypt_secret(secret)


def verify_user_totp(mfa_secret_enc: Optional[str], code: str) -> bool:
    """Decrypt a stored secret and verify ``code`` against it."""
    if not mfa_secret_enc:
        return False
    try:
        secret = decrypt_secret(mfa_secret_enc)
    except Exception:  # noqa: BLE001 - corrupt/foreign ciphertext -> not valid
        return False
    return verify_totp(secret, code)


# --------------------------------------------------------------------------- #
# Backup codes
# --------------------------------------------------------------------------- #
def _normalize_backup_code(code: str) -> str:
    """Uppercase and strip separators so 'ab12-cd34' == 'AB12CD34'."""
    return code.replace("-", "").replace(" ", "").strip().upper()


def format_backup_code(raw: str) -> str:
    """Display form shown once to the user: XXXX-XXXX."""
    return f"{raw[:4]}-{raw[4:]}"


def generate_backup_codes() -> tuple[list[str], list[str]]:
    """Return (display_codes, bcrypt_hashes) for 8 fresh single-use codes."""
    raw_codes = [secrets.token_hex(4).upper() for _ in range(BACKUP_CODE_COUNT)]
    hashes = [
        bcrypt.hashpw(c.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        for c in raw_codes
    ]
    return [format_backup_code(c) for c in raw_codes], hashes


async def store_backup_codes(db: Database, user_id: str, hashes: list[str]) -> None:
    """Replace any existing backup codes with a fresh set."""
    await db.execute("DELETE FROM mfa_backup_codes WHERE user_id = $1", user_id)
    for h in hashes:
        await db.execute(
            "INSERT INTO mfa_backup_codes (user_id, code_hash) VALUES ($1, $2)",
            user_id,
            h,
        )


async def try_consume_backup_code(db: Database, user_id: str, code: str) -> Optional[int]:
    """If ``code`` matches an UNUSED backup code, mark it used.

    Returns the number of REMAINING unused codes after consumption, or ``None``
    if no unused code matched.
    """
    normalized = _normalize_backup_code(code)
    if len(normalized) != 8:
        return None

    rows = await db.fetch(
        "SELECT code_id, code_hash FROM mfa_backup_codes "
        "WHERE user_id = $1 AND used = FALSE",
        user_id,
    )
    for row in rows:
        if bcrypt.checkpw(normalized.encode("utf-8"), row["code_hash"].encode("utf-8")):
            await db.execute(
                "UPDATE mfa_backup_codes SET used = TRUE, used_at = NOW() "
                "WHERE code_id = $1",
                row["code_id"],
            )
            remaining = await db.fetchval(
                "SELECT COUNT(*) FROM mfa_backup_codes "
                "WHERE user_id = $1 AND used = FALSE",
                user_id,
            )
            return int(remaining)
    return None


async def wipe_mfa(db: Database, user_id: str) -> None:
    """Disable MFA entirely: clear secret + flag, delete all backup codes."""
    await db.execute(
        "UPDATE users SET mfa_enabled = FALSE, mfa_secret_enc = NULL, "
        "updated_at = NOW() WHERE user_id = $1",
        user_id,
    )
    await db.execute("DELETE FROM mfa_backup_codes WHERE user_id = $1", user_id)
