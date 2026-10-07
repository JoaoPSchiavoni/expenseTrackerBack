from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.entities import RecurrenceFrequency, TransactionType


class RecurringTransactionCreateRequest(BaseModel):
    wallet_id: int = Field(..., gt=0)
    category_id: int | None = Field(None, gt=0)
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    transaction_type: TransactionType
    description: str | None = Field(None, max_length=255)
    frequency: RecurrenceFrequency
    interval_count: int = Field(1, ge=1, le=365)
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "RecurringTransactionCreateRequest":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class RecurringTransactionUpdateRequest(BaseModel):
    wallet_id: int | None = Field(None, gt=0)
    category_id: int | None = Field(None, gt=0)
    amount: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=2)
    transaction_type: TransactionType | None = None
    description: str | None = Field(None, max_length=255)
    frequency: RecurrenceFrequency | None = None
    interval_count: int | None = Field(None, ge=1, le=365)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


class RecurringTransactionResponse(BaseModel):
    id: int
    user_id: int
    wallet_id: int
    category_id: int | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    frequency: RecurrenceFrequency
    interval_count: int
    start_date: date
    next_run_date: date
    end_date: date | None
    is_active: bool
    last_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecurringProcessResponse(BaseModel):
    generated: int
    transaction_ids: list[int]
    processed_through: date
