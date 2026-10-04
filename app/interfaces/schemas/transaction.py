"""Pydantic schemas for the Transactions resource."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import TransactionSource, TransactionType
from app.interfaces.schemas.common import CurrencyCode


class TransactionCreateRequest(BaseModel):
    """Schema for recording a new income or expense."""

    wallet_id: int = Field(..., description="Target wallet ID")
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Positive monetary amount")
    transaction_type: TransactionType = Field(..., description="Type: INCOME or EXPENSE")
    category_id: int | None = Field(None, description="Optional category ID")
    description: str | None = Field(
        None, max_length=255, description="Transaction description note"
    )
    occurred_at: datetime | None = Field(None, description="Actual date of the financial event")


class TransactionUpdateRequest(BaseModel):
    """Schema for updating transaction metadata."""

    amount: Decimal | None = Field(None, gt=0, decimal_places=2)
    transaction_type: TransactionType | None = None
    category_id: int | None = None
    description: str | None = Field(None, max_length=255)
    occurred_at: datetime | None = None


class TransactionBulkCreateRequest(BaseModel):
    """Schema for bulk insertion of multiple transactions."""

    transactions: list[TransactionCreateRequest] = Field(
        ..., min_length=1, description="List of transactions"
    )


class TransactionResponse(BaseModel):
    """Response schema containing full transaction information."""

    id: int
    wallet_id: int
    amount: Decimal
    transaction_type: TransactionType
    category_id: int | None = None
    description: str | None = None
    occurred_at: datetime
    currency: CurrencyCode
    base_currency: CurrencyCode
    exchange_rate: Decimal
    base_amount: Decimal
    source: TransactionSource
    external_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionWithWalletResponse(BaseModel):
    """Enriched response schema including the transaction and updated wallet balance."""

    transaction: TransactionResponse
    updated_wallet_balance: Decimal


class TransactionBulkCreateResponse(BaseModel):
    """Result of an atomic bulk transaction operation."""

    transactions: list[TransactionResponse]
    processed: int
