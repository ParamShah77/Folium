"""Async Redis client wrapper + token-blacklist helpers.

Redis key schema (§2B):
    email_verify:{token}   -> user_id        TTL 86400 (24h)
    pw_reset:{token}       -> user_id        TTL 900 (15m)
    mfa_temp:{token}       -> user_id        TTL 300 (5m)   [Milestone 2]
    mfa_setup:{user_id}    -> totp_secret    TTL 600 (10m)  [Milestone 2]
    blacklist:{jti}        -> "1"            TTL token_remaining_life
    csrf:{user_id}         -> csrf_token     TTL 604800 (7d)
    rate:{endpoint}:{ip}   -> count          TTL per-window (handled by slowapi)
    mfa_recovery:{email}   -> "1"            TTL 86400        [Milestone 2]
    sse:{decision_id}      PUBLISH channel   (no TTL)         [Milestone 3, §3F]
    sse_log:{decision_id}  -> LIST of events TTL 3600         [Milestone 3, §3F]
    sse_seq:{decision_id}  -> counter        TTL 3600         [Milestone 3, §3F]

Blacklisting (Amendment 10): on logout and refresh rotation we blacklist BOTH
the refresh jti and the current access jti so the per-request check in
``get_current_user`` is meaningful. A small in-process TTL cache fronts the
Redis check to protect the Upstash quota in production (disabled in dev via
BLACKLIST_CACHE_TTL_SECONDS=0).
"""
from __future__ import annotations

import time
from typing import Optional

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger(__name__)


def create_redis_client(url: str) -> aioredis.Redis:
    """Create an async Redis client with string decoding on."""
    return aioredis.from_url(url, encoding="utf-8", decode_responses=True)


class _TTLCache:
    """Tiny in-process positive-result cache for blacklist hits/misses.

    Only used when BLACKLIST_CACHE_TTL_SECONDS > 0 (production/Upstash). Caches
    the boolean "is this jti blacklisted?" answer for a few seconds to avoid
    hammering Redis on every request.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, bool]] = {}

    def get(self, key: str) -> Optional[bool]:
        if self._ttl <= 0:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: bool) -> None:
        if self._ttl <= 0:
            return
        self._store[key] = (time.monotonic() + self._ttl, value)


class RedisService:
    """Blacklist + generic key helpers over an async Redis client."""

    def __init__(self, client: aioredis.Redis, blacklist_cache_ttl: int = 0) -> None:
        self._client = client
        self._cache = _TTLCache(blacklist_cache_ttl)

    @property
    def client(self) -> aioredis.Redis:
        return self._client

    # -- Blacklist (Amendment 10) ------------------------------------- #
    async def blacklist_jti(self, jti: str, ttl_seconds: int) -> None:
        """Add a token jti to the blacklist with a TTL (its remaining life)."""
        ttl = max(1, int(ttl_seconds))
        await self._client.set(f"blacklist:{jti}", "1", ex=ttl)
        self._cache.set(jti, True)

    async def is_blacklisted(self, jti: str) -> bool:
        cached = self._cache.get(jti)
        if cached is not None:
            return cached
        exists = bool(await self._client.exists(f"blacklist:{jti}"))
        self._cache.set(jti, exists)
        return exists

    # -- Generic helpers ---------------------------------------------- #
    async def set_with_ttl(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._client.set(key, value, ex=int(ttl_seconds))

    async def set_if_absent(self, key: str, value: str, ttl_seconds: int) -> bool:
        """SET NX with TTL. Returns True if the key was set (i.e. was absent).

        Used for single-use cooldowns like ``mfa_recovery:{email}`` (§1E: one
        request per email per 24 hours).
        """
        return bool(await self._client.set(key, value, ex=int(ttl_seconds), nx=True))

    async def get(self, key: str) -> Optional[str]:
        return await self._client.get(key)

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return await self._client.delete(*keys)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis_ping_failed", error=str(exc))
            return False

    async def close(self) -> None:
        await self._client.aclose()
