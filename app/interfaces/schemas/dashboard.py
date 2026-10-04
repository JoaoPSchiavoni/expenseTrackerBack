"""Chart-ready response contracts for the Flutter dashboard."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.entities import TransactionSource, TransactionType
from app.interfaces.schemas.common import CurrencyCode


class DashboardOverviewResponse(BaseModel):
    month: str
    currency: CurrencyCode
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    savings_rate: Decimal
    transaction_count: int
    net_worth: Decimal
    active_wallets: int
    active_goals: int
    completed_goals: int
    budgets_warning: int
    budgets_exceeded: int
    unread_alerts: int
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardCashFlowItem(BaseModel):
    month: str
    income: Decimal
    expense: Decimal
    net: Decimal

    model_config = ConfigDict(from_attributes=True)


class DashboardCashFlowResponse(BaseModel):
    currency: CurrencyCode
    items: list[DashboardCashFlowItem]


class DashboardCategoryItem(BaseModel):
    category_id: int | None
    category_name: str
    amount: Decimal
    percentage: Decimal

    model_config = ConfigDict(from_attributes=True)


class DashboardCategoryResponse(BaseModel):
    month: str
    currency: CurrencyCode
    items: list[DashboardCategoryItem]


class DashboardRecentTransactionResponse(BaseModel):
    id: int
    wallet_id: int
    wallet_name: str
    category_id: int | None
    category_name: str | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    occurred_at: datetime
    currency: CurrencyCode
    base_amount: Decimal
    source: TransactionSource

    model_config = ConfigDict(from_attributes=True)
