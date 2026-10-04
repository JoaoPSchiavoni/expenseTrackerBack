"""Pydantic schemas for the Wallets resource."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.interfaces.schemas.common import CurrencyCode


class WalletCreateRequest(BaseModel):
    """Schema for creating a new wallet."""

    name: str = Field(..., min_length=1, max_length=60, description="Account or wallet name")
    currency: CurrencyCode = Field("BRL", description="ISO 4217 currency code")
    initial_balance: Decimal = Field(Decimal("0.00"), ge=0, decimal_places=2)


class WalletUpdateRequest(BaseModel):
    """Schema for updating wallet metadata."""

    name: str | None = Field(None, min_length=1, max_length=60)
    currency: CurrencyCode | None = None


class WalletResponse(BaseModel):
    """Response schema containing wallet data."""

    id: int
    user_id: int
    name: str
    balance: Decimal
    currency: CurrencyCode
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
