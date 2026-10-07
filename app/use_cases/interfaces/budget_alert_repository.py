from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal

from app.domain.entities import BudgetAlert


class BudgetAlertRepositoryInterface(ABC):
    @abstractmethod
    def expense_total(
        self,
        user_id: int,
        category_id: int | None,
        start: datetime,
        end: datetime,
    ) -> Decimal: ...

    @abstractmethod
    def upsert(self, alert: BudgetAlert) -> BudgetAlert: ...

    @abstractmethod
    def resolve_missing_levels(
        self, budget_id: int, period_start: date, active_types: set[str]
    ) -> None: ...

    @abstractmethod
    def resolve_all_for_budget(self, budget_id: int) -> None: ...

    @abstractmethod
    def list_by_user(
        self,
        user_id: int,
        *,
        unread_only: bool,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> list[BudgetAlert]: ...

    @abstractmethod
    def get_by_id_for_user(self, alert_id: int, user_id: int) -> BudgetAlert | None: ...

    @abstractmethod
    def mark_read(self, alert_id: int) -> BudgetAlert: ...

    @abstractmethod
    def mark_all_read(self, user_id: int) -> int: ...

    @abstractmethod
    def unread_count(self, user_id: int) -> int: ...
