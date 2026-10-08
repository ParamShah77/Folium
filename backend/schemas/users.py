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
    # Investor profile the models read. Not sensitive under the Security
    # Summary table, so they save without re-verification. Omitted = unchanged.
    age: Optional[int] = Field(None, ge=18, le=100)
    risk_tolerance: Optional[float] = Field(None, ge=0.0, le=1.0)
    investment_horizon: Optional[int] = Field(None, ge=1, le=60)
    # Sensitive fields may be *filled in* here only while still empty (e.g. a
    # Google sign-up that skipped the profile form). Changing an existing value
    # still goes through PUT /me/profile/sensitive with password re-verification.
    monthly_income: Optional[float] = Field(None, ge=0)
    monthly_expense: Optional[float] = Field(None, ge=0)
    has_emergency_fund: Optional[bool] = None
    # Tier 1 outflows (§10) follow the same first-fill rule as expenses.
    monthly_emi: Optional[float] = Field(None, ge=0)
    rent_paid: Optional[float] = Field(None, ge=0)
    education_monthly: Optional[float] = Field(None, ge=0)
    # When school/college fees end. Timing only, not an amount: not sensitive.
    education_end_year: Optional[int] = Field(None, ge=2000, le=2100)


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
    monthly_emi: Optional[float] = Field(None, ge=0)
    rent_paid: Optional[float] = Field(None, ge=0)
    education_monthly: Optional[float] = Field(None, ge=0)
    password: str = Field(..., description="Verification password to confirm sensitive changes")
    totp_code: Optional[str] = Field(
        None, description="TOTP verification code if MFA is enabled"
    )
    otp: Optional[str] = Field(
        None, description="6-digit code emailed to the OLD address (email change step 2)"
    )


class DeleteAccountRequest(BaseModel):
    """Phase B2. Deleting an account needs the password (and a TOTP code when
    two-step verification is on), like any other sensitive change (§4I)."""

    password: str
    totp_code: Optional[str] = Field(None, max_length=10)
    reason: Optional[str] = Field(None, max_length=500)


class AiConsentRequest(BaseModel):
    """Phase B3: Gemini help on or off for this investor."""

    enabled: bool
