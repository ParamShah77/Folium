"""Application configuration.

Pydantic-settings model that reads the repo-root ``.env`` (per the Environment
Variables Reference table in implementation_plan_Final.md, as amended by
Amendment 7). Also wires up structlog JSON logging (§3E).

Key material (JWT_PRIVATE_KEY / JWT_PUBLIC_KEY / FERNET_KEY) is produced for
local dev by ``scripts/generate_dev_keys.py`` and never committed.
"""
from __future__ import annotations

import base64
import json
import logging
import sys
from functools import lru_cache
from typing import List

import structlog
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is two levels up from this file (backend/config.py -> repo root).
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


def _normalize_pem(raw: str) -> str:
    """Accept a PEM as raw text, ``\\n``-escaped text, or base64-encoded blob.

    Amendment/reference table allows all three forms for the JWT key vars so the
    same value works in a shell env var, a .env file, and a secrets manager.
    """
    if not raw:
        return raw
    value = raw.strip()
    if "BEGIN" in value and "KEY" in value:
        # Already PEM-ish; just un-escape literal \n sequences.
        return value.replace("\\n", "\n")
    # Otherwise assume base64-encoded PEM.
    try:
        decoded = base64.b64decode(value).decode("utf-8")
        if "BEGIN" in decoded:
            return decoded
    except Exception:  # noqa: BLE001 - fall through to returning raw
        pass
    return value.replace("\\n", "\n")


class Settings(BaseSettings):
    """Typed application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---
    ENV: str = "development"

    # --- Datastores ---
    # The running app connects as the NON-superuser role `app_user` THROUGH
    # PgBouncer (6432) so Row-Level Security is actually enforced — a superuser
    # would silently bypass every §2E policy. Migrations connect as `finai`
    # DIRECT to Postgres (see sync_database_url + env.py).
    DATABASE_URL: str = "postgresql://app_user:app_user@localhost:6432/finai"
    # Password for the app_user login role; consumed by migration 0007 (via the
    # APP_DB_PASSWORD env var) and must match the credentials in DATABASE_URL.
    APP_DB_PASSWORD: str = "app_user"
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT (RS256) ---
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""
    ACCESS_TOKEN_TTL_SECONDS: int = 15 * 60          # 15 minutes (§1A)
    REFRESH_TOKEN_TTL_SECONDS: int = 7 * 24 * 60 * 60  # 7 days (§1A)

    # --- Symmetric encryption for TOTP secrets / future Kite tokens ---
    FERNET_KEY: str = ""

    # --- Anthropic (Milestone 3 debate engine) ---
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-5"
    CLAUDE_MONTHLY_BUDGET_USD: float = 50.00

    # --- Ops / email ---
    ADMIN_EMAIL: str = "admin@example.com"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "FinAI <onboarding@resend.dev>"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Google OAuth (Milestone 2) ---
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""

    # --- Sentry (empty = disabled) ---
    SENTRY_DSN: str = ""

    # --- Zerodha Kite (deferred, Amendment 1) ---
    ZERODHA_KITE_API_KEY: str = ""
    ZERODHA_KITE_API_SECRET: str = ""

    # --- CORS ---
    CORS_ALLOWED_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Local tuning knobs ---
    RATE_LIMIT_ENABLED: bool = True
    # In-process TTL cache in front of the Redis blacklist (Amendment 10).
    # 0 in dev (local Redis has no quota); ~60 in production (Upstash quota).
    BLACKLIST_CACHE_TTL_SECONDS: int = 0

    # ------------------------------------------------------------------ #
    # Validators / derived helpers
    # ------------------------------------------------------------------ #
    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> object:
        """Allow the JSON-array string form from the .env file."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["http://localhost:3000"]
            if v.startswith("["):
                return json.loads(v)
            # comma-separated fallback
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"

    @property
    def cookie_secure(self) -> bool:
        """Secure cookie flag: off in dev (http://localhost), on otherwise (§1C)."""
        return not self.is_development

    @property
    def jwt_private_key(self) -> str:
        return _normalize_pem(self.JWT_PRIVATE_KEY)

    @property
    def jwt_public_key(self) -> str:
        return _normalize_pem(self.JWT_PUBLIC_KEY)

    def sync_database_url(self) -> str:
        """psycopg2 (sync) URL for Alembic — forces the psycopg2 driver.

        Alembic runs against Postgres *directly* (not through PgBouncer) using a
        sync driver; see backend/db/migrations/env.py for the rationale.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql+"):
            # normalise any async driver prefix to psycopg2
            url = "postgresql://" + url.split("://", 1)[1]
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor for settings."""
    return Settings()


def configure_logging(env: str) -> None:
    """Configure structlog to emit JSON logs (§3E).

    In development we still emit JSON (matches production) but at DEBUG level.
    """
    level = logging.DEBUG if env == "development" else logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Convenient module-level singleton for imports that don't want the DI form.
settings = get_settings()
