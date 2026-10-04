"""Pydantic schemas for System Reports."""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.interfaces.schemas.common import CurrencyCode


class MonthlyReportResponse(BaseModel):
    """Schema for monthly summary of income, expenses, and net savings."""

    month: str = Field(..., description="Reference month (e.g., 2026-09)")
    currency: CurrencyCode
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal


class CategorySummaryItem(BaseModel):
    """Summary item for accumulated expenses per category."""

    category_id: int | None = None
    category_name: str
    total_spent: Decimal


class CategorySummaryResponse(BaseModel):
    """Schema for expenses breakdown grouped by category."""

    period: str = Field(..., description="Analyzed period")
    currency: CurrencyCode
    items: list[CategorySummaryItem]
