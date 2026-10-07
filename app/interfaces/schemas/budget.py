"""Pydantic schemas for the Budgets resource."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import BudgetAlertType, BudgetUsageStatus


class BudgetCreateRequest(BaseModel):
    """Schema for creating a global or category-specific budget."""

    category_id: int | None = Field(None, gt=0, description="Optional budgeted category ID")
    limit_amount: Decimal = Field(..., gt=0, decimal_places=2)
    period: Literal["WEEKLY", "MONTHLY"] = "MONTHLY"
    alert_threshold: int = Field(80, ge=1, le=99)
    alerts_enabled: bool = True


class BudgetUpdateRequest(BaseModel):
    """Schema for updating budget limit."""

    limit_amount: Decimal | None = Field(None, gt=0, decimal_places=2)
    period: Literal["WEEKLY", "MONTHLY"] | None = None
    alert_threshold: int | None = Field(None, ge=1, le=99)
    alerts_enabled: bool | None = None


class BudgetResponse(BaseModel):
    """Response schema for budget data."""

    id: int
    user_id: int
    category_id: int | None
    limit_amount: Decimal
    period: str
    alert_threshold: int
    alerts_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetUsageResponse(BaseModel):
    budget_id: int
    category_id: int | None
    period: str
    period_start: date
    period_end: date
    limit_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    usage_percentage: Decimal
    status: BudgetUsageStatus
    alert_threshold: int
    alerts_enabled: bool
    currency: str

    model_config = ConfigDict(from_attributes=True)


class BudgetAlertResponse(BaseModel):
    id: int
    user_id: int
    budget_id: int
    category_id: int | None
    alert_type: BudgetAlertType
    period_start: date
    period_end: date
    limit_amount: Decimal
    spent_amount: Decimal
    usage_percentage: Decimal
    currency: str
    read_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetAlertCountResponse(BaseModel):
    unread_count: int


class BudgetAlertsReadResponse(BaseModel):
    updated: int
