"""Pydantic schemas for the Budgets resource."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BudgetCreateRequest(BaseModel):
    """Schema for creating a category budget."""

    category_id: int = Field(..., description="Budgeted category ID")
    limit_amount: Decimal = Field(..., gt=0, decimal_places=2)
    period: Literal["WEEKLY", "MONTHLY"] = "MONTHLY"


class BudgetUpdateRequest(BaseModel):
    """Schema for updating budget limit."""

    limit_amount: Decimal | None = Field(None, gt=0, decimal_places=2)
    period: Literal["WEEKLY", "MONTHLY"] | None = None


class BudgetResponse(BaseModel):
    """Response schema for budget data."""

    id: int
    user_id: int
    category_id: int
    limit_amount: Decimal
    period: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
