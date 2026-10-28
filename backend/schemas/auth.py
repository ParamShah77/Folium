"""Auth request/response schemas (§10, corrected by Amendment 3).

Amendment 3: on registration the financial-profile fields (age, income,
expense, risk_tolerance, horizon, emergency fund, strategy, goal, phone) are
OPTIONAL. The §10 ``UserRegistrationInput`` (which marked them required) is
corrected here.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="Strong user password")
    name: str = Field(..., min_length=1, description="Full name")

    # --- Optional financial profile (Amendment 3) ---
    age: Optional[int] = Field(None, ge=18, le=100)
    monthly_income: Optional[float] = Field(None, ge=0)
    monthly_expense: Optional[float] = Field(None, ge=0)
    risk_tolerance: Optional[float] = Field(None, ge=0.0, le=1.0)
    investment_horizon: Optional[int] = Field(None, ge=1)
    has_emergency_fund: Optional[bool] = None
    financial_strategy: Optional[str] = Field(
        None, description="conservative | moderate | aggressive"
    )
    goal: Optional[str] = None
    phone: Optional[str] = Field(None, description="Optional phone number for future alerts")

    # --- Tier 1 outflows (FOLIUM_MASTER.md §4) ---
    # When any is given, the stored monthly_expense is derived as their sum.
    monthly_emi: Optional[float] = Field(None, ge=0)
    rent_paid: Optional[float] = Field(None, ge=0)
    education_monthly: Optional[float] = Field(None, ge=0)
    education_end_year: Optional[int] = Field(None, ge=2000, le=2100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Unticked in the web app = session cookies that end with the browser.
    # Defaults to True so existing API clients keep their 7-day sessions.
    remember_me: bool = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    # Required (and verified) when the user has mfa_enabled=true (§1G).
    totp_code: Optional[str] = None


# --- MFA (§1C/§1D/§1E) ---

class MfaLoginRequest(BaseModel):
    temp_token: str
    # A 6-digit TOTP code OR an 8-char backup code (XXXX-XXXX accepted).
    totp_code: str
    remember_me: bool = True


class MfaVerifySetupRequest(BaseModel):
    totp_code: str


class MfaDisableRequest(BaseModel):
    password: str
    totp_code: str


class MfaRecoveryRequestInput(BaseModel):
    email: EmailStr
    message: str = Field(..., min_length=1, max_length=2000)


class AdminMfaResetRequest(BaseModel):
    admin_totp_code: str


class MeResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    mfa_enabled: bool
    # A Google-only account has no password until the investor sets one.
    has_password: bool = True
    # Tier 1 (age, income, risk, horizon) is still missing: a Google sign-up
    # skips the sign-up form, so the app asks for it before anything else.
    needs_profile: bool = False


class GoogleKeepAccountRequest(BaseModel):
    """Phase C1: keep an account in its grace period after a Google sign-in."""

    token: str = Field(..., min_length=16, max_length=128)
    remember_me: bool = False


class CancelDeletionRequest(BaseModel):
    """Phase B2: keep an account during its grace period."""

    email: EmailStr
    password: str
