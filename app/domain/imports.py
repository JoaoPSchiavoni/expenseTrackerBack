"""Pure domain objects for statement import workflows."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from app.domain.entities import TransactionType


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ImportFileType(str, Enum):
    CSV = "CSV"
    OFX = "OFX"


class ImportStatus(str, Enum):
    PREVIEW = "PREVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImportItemStatus(str, Enum):
    READY = "READY"
    DUPLICATE = "DUPLICATE"
    INVALID = "INVALID"
    IMPORTED = "IMPORTED"
    IGNORED = "IGNORED"


@dataclass
class ImportBatch:
    user_id: int
    wallet_id: int
    filename: str
    file_type: ImportFileType
    file_hash: str
    status: ImportStatus = ImportStatus.PREVIEW
    mapping: dict[str, str] | None = None
    total_rows: int = 0
    valid_rows: int = 0
    duplicate_rows: int = 0
    invalid_rows: int = 0
    imported_rows: int = 0
    error_message: str | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=_utc_now)
    confirmed_at: datetime | None = None


@dataclass
class ImportItem:
    batch_id: int
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
    id: int | None = None
