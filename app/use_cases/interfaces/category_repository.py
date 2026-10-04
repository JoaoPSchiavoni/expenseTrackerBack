from abc import ABC, abstractmethod

from app.domain.entities import Category


class CategoryRepositoryInterface(ABC):
    @abstractmethod
    def create(self, category: Category) -> Category: ...

    @abstractmethod
    def get_by_id_for_user(self, category_id: int, user_id: int) -> Category | None: ...

    @abstractmethod
    def get_by_name_for_user(self, name: str, user_id: int) -> Category | None: ...

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[Category]: ...

    @abstractmethod
    def update(self, category: Category) -> Category: ...

    @abstractmethod
    def delete(self, category_id: int) -> None: ...
