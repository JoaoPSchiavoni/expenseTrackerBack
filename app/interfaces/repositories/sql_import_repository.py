"""SQLAlchemy adapter for import batches and preview rows."""

from sqlalchemy.orm import Session

from app.domain.entities import TransactionType
from app.domain.imports import (
    ImportBatch,
    ImportFileType,
    ImportItem,
    ImportItemStatus,
    ImportStatus,
)
from app.infrastructure.database.models import ImportBatchModel, ImportItemModel
from app.use_cases.interfaces.import_repository import ImportRepositoryInterface


class SqlImportRepository(ImportRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _batch_entity(model: ImportBatchModel) -> ImportBatch:
        return ImportBatch(
            id=model.id,
            user_id=model.user_id,
            wallet_id=model.wallet_id,
            filename=model.filename,
            file_type=ImportFileType(model.file_type),
            file_hash=model.file_hash,
            status=ImportStatus(model.status),
            mapping=model.mapping,
            total_rows=model.total_rows,
            valid_rows=model.valid_rows,
            duplicate_rows=model.duplicate_rows,
            invalid_rows=model.invalid_rows,
            imported_rows=model.imported_rows,
            error_message=model.error_message,
            created_at=model.created_at,
            confirmed_at=model.confirmed_at,
        )

    @staticmethod
    def _item_entity(model: ImportItemModel) -> ImportItem:
        return ImportItem(
            id=model.id,
            batch_id=model.batch_id,
            row_number=model.row_number,
            status=ImportItemStatus(model.status),
            occurred_at=model.occurred_at,
            amount=model.amount,
            transaction_type=(
                TransactionType(model.transaction_type) if model.transaction_type else None
            ),
            description=model.description,
            external_id=model.external_id,
            category_id=model.category_id,
            transaction_id=model.transaction_id,
            error_message=model.error_message,
        )

    def create_batch(self, batch: ImportBatch) -> ImportBatch:
        model = ImportBatchModel(
            user_id=batch.user_id,
            wallet_id=batch.wallet_id,
            filename=batch.filename,
            file_type=batch.file_type.value,
            file_hash=batch.file_hash,
            status=batch.status.value,
            mapping=batch.mapping,
            total_rows=batch.total_rows,
            valid_rows=batch.valid_rows,
            duplicate_rows=batch.duplicate_rows,
            invalid_rows=batch.invalid_rows,
            imported_rows=batch.imported_rows,
            error_message=batch.error_message,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._batch_entity(model)

    def add_items(self, items: list[ImportItem]) -> list[ImportItem]:
        models = [
            ImportItemModel(
                batch_id=item.batch_id,
                row_number=item.row_number,
                status=item.status.value,
                occurred_at=item.occurred_at,
                amount=item.amount,
                transaction_type=(item.transaction_type.value if item.transaction_type else None),
                description=item.description,
                external_id=item.external_id,
                category_id=item.category_id,
                transaction_id=item.transaction_id,
                error_message=item.error_message,
            )
            for item in items
        ]
        self.session.add_all(models)
        self.session.flush()
        for model in models:
            self.session.refresh(model)
        return [self._item_entity(model) for model in models]

    def get_batch_for_user(self, batch_id: int, user_id: int) -> ImportBatch | None:
        model = (
            self.session.query(ImportBatchModel)
            .filter(ImportBatchModel.id == batch_id, ImportBatchModel.user_id == user_id)
            .first()
        )
        return self._batch_entity(model) if model else None

    def list_batches(self, user_id: int, limit: int, offset: int) -> list[ImportBatch]:
        models = (
            self.session.query(ImportBatchModel)
            .filter(ImportBatchModel.user_id == user_id)
            .order_by(ImportBatchModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._batch_entity(model) for model in models]

    def list_items(self, batch_id: int) -> list[ImportItem]:
        models = (
            self.session.query(ImportItemModel)
            .filter(ImportItemModel.batch_id == batch_id)
            .order_by(ImportItemModel.row_number)
            .all()
        )
        return [self._item_entity(model) for model in models]

    def update_batch(self, batch: ImportBatch) -> ImportBatch:
        model = self.session.get(ImportBatchModel, batch.id)
        if model is None:
            raise ValueError("Import batch not found")
        model.status = batch.status.value
        model.total_rows = batch.total_rows
        model.valid_rows = batch.valid_rows
        model.duplicate_rows = batch.duplicate_rows
        model.invalid_rows = batch.invalid_rows
        model.imported_rows = batch.imported_rows
        model.error_message = batch.error_message
        model.confirmed_at = batch.confirmed_at
        self.session.flush()
        self.session.refresh(model)
        return self._batch_entity(model)

    def update_items(self, items: list[ImportItem]) -> list[ImportItem]:
        updated: list[ImportItem] = []
        for item in items:
            model = self.session.get(ImportItemModel, item.id)
            if model is None:
                raise ValueError("Import item not found")
            model.status = item.status.value
            model.category_id = item.category_id
            model.transaction_id = item.transaction_id
            model.error_message = item.error_message
            self.session.flush()
            self.session.refresh(model)
            updated.append(self._item_entity(model))
        return updated

    def delete_batch(self, batch_id: int) -> None:
        model = self.session.get(ImportBatchModel, batch_id)
        if model is None:
            raise ValueError("Import batch not found")
        self.session.delete(model)
        self.session.flush()
