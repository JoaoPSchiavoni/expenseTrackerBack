from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.entities import TransactionSource, TransactionType


@dataclass(frozen=True)
class DashboardCashFlowRecord:
    occurred_at: datetime
    transaction_type: TransactionType
    base_amount: Decimal


@dataclass(frozen=True)
class DashboardRecentTransaction:
    id: int
    wallet_id: int
    wallet_name: str
    category_id: int | None
    category_name: str | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    occurred_at: datetime
    currency: str
    base_amount: Decimal
    source: TransactionSource


class DashboardRepositoryInterface(ABC):
    @abstractmethod
    def transaction_count(self, user_id: int, start: datetime, end: datetime) -> int: ...

    @abstractmethod
    def cash_flow_records(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[DashboardCashFlowRecord]: ...

    @abstractmethod
    def recent_transactions(self, user_id: int, limit: int) -> list[DashboardRecentTransaction]: ...

    @abstractmethod
    def goal_counts(self, user_id: int) -> tuple[int, int]: ...
