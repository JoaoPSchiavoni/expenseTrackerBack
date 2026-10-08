"""HTTP schemas for the automation features."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import BillingAlertType, RuleMatchType, SubscriptionStatus
from app.interfaces.schemas.common import CurrencyCode


class CategorizationRuleCreateRequest(BaseModel):
    category_id: int
    name: str = Field(..., min_length=1, max_length=100)
    pattern: str = Field(..., min_length=1, max_length=255)
    match_type: RuleMatchType = RuleMatchType.CONTAINS
    priority: int = Field(100, ge=0, le=10_000)
    applies_to_imports: bool = True
    is_active: bool = True


class CategorizationRuleUpdateRequest(BaseModel):
    category_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    pattern: str | None = Field(None, min_length=1, max_length=255)
    match_type: RuleMatchType | None = None
    priority: int | None = Field(None, ge=0, le=10_000)
    applies_to_imports: bool | None = None
    is_active: bool | None = None


class CategorizationRuleResponse(BaseModel):
    id: int
    user_id: int
    category_id: int
    name: str
    pattern: str
    match_type: RuleMatchType
    priority: int
    applies_to_imports: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RuleTestRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)


class RuleTestResponse(BaseModel):
    category_id: int | None
    matched: bool


class DetectedSubscriptionResponse(BaseModel):
    id: int
    user_id: int
    wallet_id: int
    category_id: int | None
    merchant_name: str
    average_amount: Decimal
    currency: CurrencyCode
    frequency: str
    next_expected_date: date
    last_charge_date: date
    confidence: Decimal
    status: SubscriptionStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SubscriptionStatusRequest(BaseModel):
    status: SubscriptionStatus


class DetectionResponse(BaseModel):
    detected: int
    subscriptions: list[DetectedSubscriptionResponse]


class BillingAlertResponse(BaseModel):
    id: int
    user_id: int
    subscription_id: int
    alert_type: BillingAlertType
    expected_date: date
    expected_amount: Decimal
    currency: CurrencyCode
    read_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertSyncResponse(BaseModel):
    generated: int
    alerts: list[BillingAlertResponse]

