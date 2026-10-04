"""
Abstract Interface for Transaction Repository.

Why: Enables CreateTransactionUseCase to store financial ledger movements
without coupling to relational databases (PostgreSQL) or ORMs (SQLAlchemy).
"""

from abc import ABC, abstractmethod

from app.domain.entities import Transaction, TransactionSource


class TransactionRepositoryInterface(ABC):
    """Abstract contract for transaction persistence operations."""

    @abstractmethod
    def create(self, transaction: Transaction) -> Transaction:
        """Persists a new financial transaction.

        Args:
            transaction: Transaction entity to record.

        Returns:
            Persisted Transaction entity with assigned ID and creation timestamp.
        """
        pass

    @abstractmethod
    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Retrieves a transaction by its unique ID.

        Args:
            transaction_id: Unique transaction identifier.

        Returns:
            Transaction entity or None if not found.
        """
        pass

    @abstractmethod
    def get_by_id_for_user(self, transaction_id: int, user_id: int) -> Transaction | None:
        """Retrieve a transaction only when it belongs to the user's wallet."""
        pass

    @abstractmethod
    def list_by_wallet(self, wallet_id: int, limit: int = 50, offset: int = 0) -> list[Transaction]:
        """Lists transactions associated with a wallet supporting pagination.

        Args:
            wallet_id: Target wallet identifier.
            limit: Maximum count of records to retrieve.
            offset: Starting pagination offset.

        Returns:
            List of Transaction entities.
        """
        pass

    @abstractmethod
    def update(self, transaction: Transaction) -> Transaction:
        """Persist changes to an existing transaction."""
        pass

    @abstractmethod
    def delete(self, transaction_id: int) -> None:
        """Delete a transaction from the ledger."""
        pass

    @abstractmethod
    def exists_for_user(self, user_id: int) -> bool:
        """Return whether a user already has at least one ledger entry."""
        pass

    @abstractmethod
    def existing_external_ids(
        self, wallet_id: int, source: TransactionSource, external_ids: set[str]
    ) -> set[str]:
        """Return import identities that already exist in a wallet ledger."""
        pass
