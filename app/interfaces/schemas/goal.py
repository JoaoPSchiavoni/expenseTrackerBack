"""Pydantic contracts for financial goals and contribution history."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.entities import GoalStatus


class GoalCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    target_amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    target_date: date | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Goal name cannot be blank")
        return normalized


class GoalUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    target_amount: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=2)
    target_date: date | None = None
    status: Literal[GoalStatus.ACTIVE, GoalStatus.CANCELLED] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Goal name cannot be blank")
        return normalized


class GoalContributionCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    note: str | None = Field(None, max_length=255)
    contributed_at: datetime | None = None


class GoalContributionResponse(BaseModel):
    id: int
    goal_id: int
    amount: Decimal
    note: str | None
    contributed_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoalResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None
    target_amount: Decimal
    current_amount: Decimal
    remaining_amount: Decimal
    progress_percentage: Decimal
    currency: str
    target_date: date | None
    status: GoalStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GoalContributionResult(BaseModel):
    goal: GoalResponse
    contribution: GoalContributionResponse
