"""User domain model — a light view over the ``users`` row.

Built from an asyncpg ``Record`` via :meth:`User.from_record`. Only the fields
the auth layer needs are typed explicitly; the rest travel in ``raw`` for
callers that need them without a second query.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional
from uuid import UUID

#: Tier 1 fields the sign-up form requires (FOLIUM_MASTER.md §4).
#: ``has_emergency_fund`` is absent because the column defaults to FALSE.
TIER1_REQUIRED = ("age", "monthly_income", "risk_tolerance", "investment_horizon")


@dataclass
class User:
    user_id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    email_verified: bool
    mfa_enabled: bool
    deleted_at: Optional[datetime] = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "User":
        return cls(
            user_id=record["user_id"],
            email=record["email"],
            name=record["name"],
            role=record["role"],
            is_active=record["is_active"],
            email_verified=record["email_verified"],
            mfa_enabled=record["mfa_enabled"],
            deleted_at=record.get("deleted_at"),
            raw=dict(record),
        )

    @property
    def id(self) -> UUID:  # convenience alias
        return self.user_id

    def public_dict(self) -> dict[str, Any]:
        """The shape returned to clients as ``user`` on login/me (§1C)."""
        return {
            "id": str(self.user_id),
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "mfa_enabled": self.mfa_enabled,
            "has_password": bool(self.raw.get("password_hash")),
            "needs_profile": any(self.raw.get(f) is None for f in TIER1_REQUIRED),
        }
