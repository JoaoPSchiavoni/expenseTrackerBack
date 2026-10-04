from abc import ABC, abstractmethod

from app.domain.entities import Budget


class BudgetRepositoryInterface(ABC):
    @abstractmethod
    def create(self, budget: Budget) -> Budget: ...

    @abstractmethod
    def get_by_id_for_user(self, budget_id: int, user_id: int) -> Budget | None: ...

    @abstractmethod
    def get_by_scope(self, user_id: int, category_id: int, period: str) -> Budget | None: ...

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[Budget]: ...

    @abstractmethod
    def list_by_category(self, user_id: int, category_id: int) -> list[Budget]: ...

    @abstractmethod
    def update(self, budget: Budget) -> Budget: ...

    @abstractmethod
    def delete(self, budget_id: int) -> None: ...
