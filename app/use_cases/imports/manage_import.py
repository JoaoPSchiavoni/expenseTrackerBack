"""Upload, preview, confirm, and discard bank statement imports."""

import hashlib
from datetime import UTC, datetime

from app.domain.entities import TransactionSource, require_id
from app.domain.exceptions import (
    ImportNotFoundError,
    InvalidImportStateError,
    UnauthorizedWalletAccessError,
    WalletNotFoundError,
)
from app.domain.imports import (
    ImportBatch,
    ImportFileType,
    ImportItem,
    ImportItemStatus,
    ImportStatus,
)
from app.infrastructure.imports.parsers import ParsedRow, StatementParser
from app.use_cases.automation import AutomationService
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface
from app.use_cases.interfaces.import_repository import ImportRepositoryInterface
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface
from app.use_cases.transactions.create_transaction import CreateTransactionUseCase


class ImportStatementsUseCase:
    """Coordinate persisted previews and atomic ledger confirmation."""

    def __init__(
        self,
        import_repository: ImportRepositoryInterface,
        transaction_repository: TransactionRepositoryInterface,
        wallet_repository: WalletRepositoryInterface,
        category_repository: CategoryRepositoryInterface,
        create_transaction: CreateTransactionUseCase,
        automation_service: AutomationService,
        parser: StatementParser,
        max_file_size_bytes: int,
        max_rows: int,
    ) -> None:
        self.import_repository = import_repository
        self.transaction_repository = transaction_repository
        self.wallet_repository = wallet_repository
        self.category_repository = category_repository
        self.create_transaction = create_transaction
        self.automation_service = automation_service
        self.parser = parser
        self.max_file_size_bytes = max_file_size_bytes
        self.max_rows = max_rows

    @staticmethod
    def _file_type(filename: str) -> ImportFileType:
        extension = filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""
        if extension == "csv":
            return ImportFileType.CSV
        if extension in {"ofx", "qfx"}:
            return ImportFileType.OFX
        raise ValueError("Only .csv, .ofx, and .qfx files are supported")

    def create_preview(
        self,
        *,
        user_id: int,
        wallet_id: int,
        filename: str,
        content: bytes,
        timezone_name: str,
        options: dict[str, str] | None,
    ) -> tuple[ImportBatch, list[ImportItem]]:
        wallet = self.wallet_repository.get_by_id(wallet_id)
        if wallet is None or not wallet.is_active:
            raise WalletNotFoundError(wallet_id)
        if wallet.user_id != user_id:
            raise UnauthorizedWalletAccessError(wallet_id, user_id)
        if not content:
            raise ValueError("Import file is empty")
        if len(content) > self.max_file_size_bytes:
            raise ValueError(
                f"Import file exceeds the {self.max_file_size_bytes // (1024 * 1024)} MB limit"
            )
        safe_filename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1][:255]
        file_type = self._file_type(safe_filename)
        parsed = self.parser.parse(content, file_type, timezone_name, options)
        if len(parsed.rows) > self.max_rows:
            raise ValueError(f"Import contains more than {self.max_rows} rows")
        if parsed.currency and parsed.currency != wallet.currency:
            raise ValueError(
                f"Statement currency {parsed.currency} does not match wallet currency {wallet.currency}"
            )

        source = TransactionSource(file_type.value)
        candidate_ids = {row.external_id for row in parsed.rows if row.external_id}
        existing_ids = self.transaction_repository.existing_external_ids(
            wallet_id, source, candidate_ids
        )
        seen_ids: set[str] = set()
        staged_rows: list[tuple[ParsedRow, ImportItemStatus]] = []
        for row in parsed.rows:
            if row.error_message:
                status = ImportItemStatus.INVALID
            elif row.external_id in existing_ids or row.external_id in seen_ids:
                status = ImportItemStatus.DUPLICATE
            else:
                status = ImportItemStatus.READY
                if row.external_id:
                    seen_ids.add(row.external_id)
            staged_rows.append((row, status))

        ready_count = sum(status == ImportItemStatus.READY for _, status in staged_rows)
        duplicate_count = sum(status == ImportItemStatus.DUPLICATE for _, status in staged_rows)
        invalid_count = sum(status == ImportItemStatus.INVALID for _, status in staged_rows)
        batch = self.import_repository.create_batch(
            ImportBatch(
                user_id=user_id,
                wallet_id=wallet_id,
                filename=safe_filename,
                file_type=file_type,
                file_hash=hashlib.sha256(content).hexdigest(),
                mapping=options,
                total_rows=len(staged_rows),
                valid_rows=ready_count,
                duplicate_rows=duplicate_count,
                invalid_rows=invalid_count,
            )
        )
        batch_id = require_id(batch.id)
        items = self.import_repository.add_items(
            [
                ImportItem(
                    batch_id=batch_id,
                    row_number=row.row_number,
                    status=status,
                    occurred_at=row.occurred_at,
                    amount=row.amount,
                    transaction_type=row.transaction_type,
                    description=row.description,
                    external_id=row.external_id,
                    category_id=(
                        self.automation_service.match_category(
                            user_id, row.description, imports_only=True
                        )
                        if status == ImportItemStatus.READY
                        else None
                    ),
                    error_message=row.error_message,
                )
                for row, status in staged_rows
            ]
        )
        return batch, items

    def get_preview(self, *, batch_id: int, user_id: int) -> tuple[ImportBatch, list[ImportItem]]:
        batch = self.import_repository.get_batch_for_user(batch_id, user_id)
        if batch is None:
            raise ImportNotFoundError(batch_id)
        return batch, self.import_repository.list_items(batch_id)

    def list_batches(self, *, user_id: int, limit: int, offset: int) -> list[ImportBatch]:
        return self.import_repository.list_batches(user_id, limit, offset)

    def confirm(
        self,
        *,
        batch_id: int,
        user_id: int,
        base_currency: str,
        timezone_name: str,
        default_category_id: int | None,
        row_options: dict[int, tuple[bool, int | None]],
    ) -> tuple[ImportBatch, list[ImportItem]]:
        batch = self.import_repository.get_batch_for_user(batch_id, user_id)
        if batch is None:
            raise ImportNotFoundError(batch_id)
        if batch.status != ImportStatus.PREVIEW:
            raise InvalidImportStateError("Only imports in PREVIEW status can be confirmed")
        wallet = self.wallet_repository.get_by_id(batch.wallet_id)
        if wallet is None or not wallet.is_active or wallet.user_id != user_id:
            raise WalletNotFoundError(batch.wallet_id)

        category_ids = {default_category_id} if default_category_id else set()
        category_ids.update(
            category_id for _, category_id in row_options.values() if category_id is not None
        )
        for category_id in category_ids:
            if self.category_repository.get_by_id_for_user(category_id, user_id) is None:
                raise ValueError(f"Category {category_id} was not found")

        items = self.import_repository.list_items(batch_id)
        known_row_numbers = {item.row_number for item in items}
        unknown_rows = set(row_options) - known_row_numbers
        if unknown_rows:
            raise ValueError(
                f"Import rows do not exist: {', '.join(map(str, sorted(unknown_rows)))}"
            )
        source = TransactionSource(batch.file_type.value)
        ready_ids = {
            item.external_id
            for item in items
            if item.status == ImportItemStatus.READY and item.external_id
        }
        existing_ids = self.transaction_repository.existing_external_ids(
            batch.wallet_id, source, ready_ids
        )
        imported = 0
        for item in items:
            if item.status != ImportItemStatus.READY:
                continue
            include, category_override = row_options.get(item.row_number, (True, None))
            if not include:
                item.status = ImportItemStatus.IGNORED
                continue
            if item.external_id in existing_ids:
                item.status = ImportItemStatus.DUPLICATE
                continue
            if item.occurred_at is None or item.amount is None or item.transaction_type is None:
                raise InvalidImportStateError("A ready import row is missing required data")
            transaction, _ = self.create_transaction.execute(
                user_id=user_id,
                wallet_id=batch.wallet_id,
                amount=item.amount,
                transaction_type=item.transaction_type,
                category_id=category_override or item.category_id or default_category_id,
                description=item.description,
                occurred_at=item.occurred_at,
                base_currency=base_currency,
                timezone_name=timezone_name,
                source=source,
                external_id=item.external_id,
                import_batch_id=batch_id,
            )
            item.status = ImportItemStatus.IMPORTED
            item.category_id = category_override or item.category_id or default_category_id
            item.transaction_id = require_id(transaction.id)
            imported += 1

        updated_items = self.import_repository.update_items(items)
        batch.status = ImportStatus.COMPLETED
        batch.imported_rows = imported
        batch.duplicate_rows = sum(
            item.status == ImportItemStatus.DUPLICATE for item in updated_items
        )
        batch.valid_rows = sum(item.status == ImportItemStatus.IMPORTED for item in updated_items)
        batch.confirmed_at = datetime.now(UTC)
        return self.import_repository.update_batch(batch), updated_items

    def delete(self, *, batch_id: int, user_id: int) -> None:
        batch = self.import_repository.get_batch_for_user(batch_id, user_id)
        if batch is None:
            raise ImportNotFoundError(batch_id)
        if batch.status == ImportStatus.COMPLETED:
            raise InvalidImportStateError("Completed imports cannot be deleted")
        self.import_repository.delete_batch(batch_id)
