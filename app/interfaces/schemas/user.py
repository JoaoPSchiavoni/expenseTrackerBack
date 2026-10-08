"""Pydantic schemas for the Users resource."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.interfaces.schemas.common import CurrencyCode


class UserResponse(BaseModel):
    """Schema exposing safe user data (without password)."""

    id: int
    email: str
    full_name: str | None = None
    base_currency: CurrencyCode
    timezone: str
    is_active: bool
    is_demo: bool
    onboarding_completed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    """Schema for updating user profile."""

    full_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    """Schema for password change request."""

    current_password: str = Field(..., min_length=8, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)


class UserPreferencesUpdateRequest(BaseModel):
    """Locale-sensitive financial preferences for reporting and transaction dates."""

    base_currency: CurrencyCode | None = None
    timezone: str | None = Field(None, min_length=1, max_length=64)
    onboarding_completed: bool | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_exist(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value
