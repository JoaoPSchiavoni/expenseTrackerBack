"""Statement import API contracts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.entities import TransactionType
from app.domain.imports import ImportFileType, ImportItemStatus, ImportStatus


class ImportBatchResponse(BaseModel):
    id: int
    wallet_id: int
    filename: str
    file_type: ImportFileType
    status: ImportStatus
    total_rows: int
    valid_rows: int
    duplicate_rows: int
    invalid_rows: int
    imported_rows: int
    error_message: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ImportItemResponse(BaseModel):
    id: int
    row_number: int
    status: ImportItemStatus
    occurred_at: datetime | None = None
    amount: Decimal | None = None
    transaction_type: TransactionType | None = None
    description: str | None = None
    external_id: str | None = None
    category_id: int | None = None
    transaction_id: int | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ImportPreviewResponse(BaseModel):
    batch: ImportBatchResponse
    items: list[ImportItemResponse]


class ImportRowConfirmation(BaseModel):
    row_number: int = Field(..., gt=0)
    include: bool = True
    category_id: int | None = Field(None, gt=0)


class ImportConfirmRequest(BaseModel):
    default_category_id: int | None = Field(None, gt=0)
    rows: list[ImportRowConfirmation] = Field(default_factory=list)

    @model_validator(mode="after")
    def row_numbers_must_be_unique(self) -> "ImportConfirmRequest":
        row_numbers = [row.row_number for row in self.rows]
        if len(row_numbers) != len(set(row_numbers)):
            raise ValueError("Each row_number can only appear once")
        return self
