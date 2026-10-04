"""Persistence contract for staged statement imports."""

from abc import ABC, abstractmethod

from app.domain.imports import ImportBatch, ImportItem


class ImportRepositoryInterface(ABC):
    @abstractmethod
    def create_batch(self, batch: ImportBatch) -> ImportBatch:
        pass

    @abstractmethod
    def add_items(self, items: list[ImportItem]) -> list[ImportItem]:
        pass

    @abstractmethod
    def get_batch_for_user(self, batch_id: int, user_id: int) -> ImportBatch | None:
        pass

    @abstractmethod
    def list_batches(self, user_id: int, limit: int, offset: int) -> list[ImportBatch]:
        pass

    @abstractmethod
    def list_items(self, batch_id: int) -> list[ImportItem]:
        pass

    @abstractmethod
    def update_batch(self, batch: ImportBatch) -> ImportBatch:
        pass

    @abstractmethod
    def update_items(self, items: list[ImportItem]) -> list[ImportItem]:
        pass

    @abstractmethod
    def delete_batch(self, batch_id: int) -> None:
        pass
