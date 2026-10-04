"""
SQLAlchemy Implementation of Transaction Repository.

Why: Encapsulates SQL operations against the transactions table,
converting between the pure Transaction domain entity and TransactionModel.
"""

from sqlalchemy.orm import Session

from app.domain.entities import Transaction, TransactionSource, TransactionType
from app.infrastructure.database.models import TransactionModel, WalletModel
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface


class SqlTransactionRepository(TransactionRepositoryInterface):
    """Transaction persistence adapter using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Injects active database session."""
        self.session = session

    def _to_entity(self, model: TransactionModel) -> Transaction:
        """Converts TransactionModel to pure Transaction entity."""
        return Transaction(
            id=model.id,
            wallet_id=model.wallet_id,
            category_id=model.category_id,
            amount=model.amount,
            transaction_type=TransactionType(model.transaction_type),
            description=model.description,
            occurred_at=model.occurred_at,
            currency=model.currency,
            base_currency=model.base_currency,
            exchange_rate=model.exchange_rate,
            base_amount=model.base_amount,
            rate_date=model.rate_date,
            source=TransactionSource(model.source),
            external_id=model.external_id,
            import_batch_id=model.import_batch_id,
            created_at=model.created_at,
        )

    def create(self, transaction: Transaction) -> Transaction:
        """Inserts and persists a new transaction."""
        model = TransactionModel(
            wallet_id=transaction.wallet_id,
            category_id=transaction.category_id,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type.value,
            description=transaction.description,
            occurred_at=transaction.occurred_at,
            currency=transaction.currency,
            base_currency=transaction.base_currency,
            exchange_rate=transaction.exchange_rate,
            base_amount=transaction.base_amount,
            rate_date=transaction.rate_date,
            source=transaction.source.value,
            external_id=transaction.external_id,
            import_batch_id=transaction.import_batch_id,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Retrieves transaction by primary key."""
        model = (
            self.session.query(TransactionModel)
            .filter(TransactionModel.id == transaction_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_by_id_for_user(self, transaction_id: int, user_id: int) -> Transaction | None:
        model = (
            self.session.query(TransactionModel)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(TransactionModel.id == transaction_id, WalletModel.user_id == user_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def list_by_wallet(self, wallet_id: int, limit: int = 50, offset: int = 0) -> list[Transaction]:
        """Retrieves transactions ordered by financial event date descending."""
        models = (
            self.session.query(TransactionModel)
            .filter(TransactionModel.wallet_id == wallet_id)
            .order_by(TransactionModel.occurred_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def update(self, transaction: Transaction) -> Transaction:
        model = self.session.get(TransactionModel, transaction.id)
        if model is None:
            raise ValueError("Transaction not found")
        if transaction.rate_date is None:
            raise ValueError("Transaction is missing its exchange-rate date")
        model.amount = transaction.amount
        model.transaction_type = transaction.transaction_type.value
        model.category_id = transaction.category_id
        model.description = transaction.description
        model.occurred_at = transaction.occurred_at
        model.exchange_rate = transaction.exchange_rate
        model.base_amount = transaction.base_amount
        model.rate_date = transaction.rate_date
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def delete(self, transaction_id: int) -> None:
        model = self.session.get(TransactionModel, transaction_id)
        if model is None:
            raise ValueError("Transaction not found")
        self.session.delete(model)
        self.session.flush()

    def exists_for_user(self, user_id: int) -> bool:
        return (
            self.session.query(TransactionModel.id)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(WalletModel.user_id == user_id)
            .first()
            is not None
        )

    def existing_external_ids(
        self, wallet_id: int, source: TransactionSource, external_ids: set[str]
    ) -> set[str]:
        if not external_ids:
            return set()
        rows = (
            self.session.query(TransactionModel.external_id)
            .filter(
                TransactionModel.wallet_id == wallet_id,
                TransactionModel.source == source.value,
                TransactionModel.external_id.in_(external_ids),
            )
            .all()
        )
        return {value for (value,) in rows if value is not None}
