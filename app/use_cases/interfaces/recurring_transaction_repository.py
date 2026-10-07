from abc import ABC, abstractmethod
from datetime import date

from app.domain.entities import RecurringTransaction


class RecurringTransactionRepositoryInterface(ABC):
    """Persistence contract for recurring financial rules."""

    @abstractmethod
    def create(self, recurring: RecurringTransaction) -> RecurringTransaction: ...

    @abstractmethod
    def get_by_id_for_user(
        self, recurring_id: int, user_id: int, *, for_update: bool = False
    ) -> RecurringTransaction | None: ...

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[RecurringTransaction]: ...

    @abstractmethod
    def list_due(self, user_id: int, through_date: date) -> list[RecurringTransaction]: ...

    @abstractmethod
    def update(self, recurring: RecurringTransaction) -> RecurringTransaction: ...

    @abstractmethod
    def delete(self, recurring_id: int) -> None: ...
