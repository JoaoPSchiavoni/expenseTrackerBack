"""Pydantic schemas for the Categories resource."""

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreateRequest(BaseModel):
    """Schema for category creation."""

    name: str = Field(..., min_length=1, max_length=50, description="Category name")
    description: str | None = Field(None, max_length=200, description="Optional description")


class CategoryUpdateRequest(BaseModel):
    """Schema for category update."""

    name: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)


class CategoryResponse(BaseModel):
    """Response schema for category data."""

    id: int
    user_id: int
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)
