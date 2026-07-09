"""Profile request/response schemas (§10 + §4I backend side).

Sensitive updates follow §4I / the Security Summary table:
    email change     -> password + OTP sent to the OLD email (one-time)
    income / expense / emergency fund -> password
    (+ TOTP additionally whenever the account has MFA enabled)
Non-sensitive (name, goal, financial_strategy) save without re-verification.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ProfileUpdateRequest(BaseModel):
    """Non-sensitive fields — §10 ProfileUpdateRequest."""

    name: str = Field(..., min_length=1)
    goal: Optional[str] = None
    financial_strategy: Optional[str] = Field(
        None, description="conservative | moderate | aggressive"
    )


class SensitiveProfileUpdateRequest(BaseModel):
    """§10 SensitiveProfileUpdateRequest (+ ``otp`` for the email-change step 2).

    ``password`` is always required. ``totp_code`` is required when the account
    has MFA enabled. Changing ``email`` is a two-step flow:
      1. request WITHOUT ``otp``  -> a 6-digit code is emailed to the OLD address
         (Redis ``otp:{user_id}``, TTL 300) and the response is
         ``{otp_required: true}`` — nothing is changed yet.
      2. request WITH ``otp``     -> code verified, email updated.
    """

    email: Optional[EmailStr] = None
    monthly_income: Optional[float] = Field(None, ge=0)
    monthly_expense: Optional[float] = Field(None, ge=0)
    has_emergency_fund: Optional[bool] = None
    password: str = Field(..., description="Verification password to confirm sensitive changes")
    totp_code: Optional[str] = Field(
        None, description="TOTP verification code if MFA is enabled"
    )
    otp: Optional[str] = Field(
        None, description="6-digit code emailed to the OLD address (email change step 2)"
    )
