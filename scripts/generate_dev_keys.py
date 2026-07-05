"""Generate local-dev key material and write it into the repo-root ``.env``.

Produces:
  * ``JWT_PRIVATE_KEY`` / ``JWT_PUBLIC_KEY`` — an RS256 (2048-bit RSA) key pair,
    stored ``\\n``-escaped so the PEM survives a single .env line.
  * ``FERNET_KEY`` — a urlsafe-base64 Fernet key (Amendment 7: NOT hex), used to
    encrypt TOTP secrets and future Kite tokens.

Behaviour:
  * If ``.env`` does not exist, it is seeded from ``.env.example``.
  * Existing non-key settings are preserved; only the three key vars are
    (re)written unless already present. Pass ``--force`` to overwrite existing
    key values (this rotates keys and invalidates all current tokens).

Never commit ``.env`` — it is gitignored.

Usage:
    python scripts/generate_dev_keys.py            # fill missing keys only
    python scripts/generate_dev_keys.py --force    # rotate/overwrite keys
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

KEY_VARS = ("JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY", "FERNET_KEY")


def _generate_rsa_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    # Escape newlines so the whole PEM fits on one .env line.
    return private_pem.replace("\n", "\\n"), public_pem.replace("\n", "\\n")


def _read_env_lines() -> list[str]:
    if ENV_PATH.exists():
        return ENV_PATH.read_text(encoding="utf-8").splitlines()
    if ENV_EXAMPLE_PATH.exists():
        print(f"[generate_dev_keys] .env not found — seeding from {ENV_EXAMPLE_PATH.name}")
        return ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
    print("[generate_dev_keys] Neither .env nor .env.example found — creating minimal .env")
    return ["ENV=development"]


def _existing_value(lines: list[str], var: str) -> str | None:
    prefix = f"{var}="
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _set_var(lines: list[str], var: str, value: str) -> list[str]:
    prefix = f"{var}="
    new_line = f"{var}={value}"
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = new_line
            return lines
    lines.append(new_line)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dev JWT + Fernet keys into .env")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing key values (rotates keys, invalidates tokens).",
    )
    args = parser.parse_args()

    lines = _read_env_lines()

    have_all = all(_existing_value(lines, v) for v in KEY_VARS)
    if have_all and not args.force:
        print(
            "[generate_dev_keys] All key vars already present in .env. "
            "Use --force to rotate them."
        )
        return 0

    private_pem, public_pem = _generate_rsa_pair()
    fernet_key = Fernet.generate_key().decode("utf-8")

    generated = {
        "JWT_PRIVATE_KEY": private_pem,
        "JWT_PUBLIC_KEY": public_pem,
        "FERNET_KEY": fernet_key,
    }

    for var, value in generated.items():
        current = _existing_value(lines, var)
        if current and not args.force:
            print(f"[generate_dev_keys] keeping existing {var}")
            continue
        lines = _set_var(lines, var, value)
        print(f"[generate_dev_keys] wrote {var}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[generate_dev_keys] .env updated at {ENV_PATH}")
    print("[generate_dev_keys] Reminder: .env is gitignored — never commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
