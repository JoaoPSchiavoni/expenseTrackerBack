"""Pydantic schemas for the Authentication module."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Schema for new user registration requests."""

    email: EmailStr = Field(..., description="Valid user email address")
    password: str = Field(..., min_length=8, max_length=72)
    full_name: str | None = Field(None, max_length=100, description="Optional user full name")


class LoginRequest(BaseModel):
    """Schema for user login requests."""

    email: EmailStr = Field(..., description="Registered user email address")
    password: str = Field(..., min_length=8, max_length=72)


class TokenResponse(BaseModel):
    """Response schema containing JWT access token."""

    access_token: str = Field(..., description="JWT Bearer token string")
    token_type: str = Field("bearer", description="Token scheme type")

    model_config = ConfigDict(from_attributes=True)
