"""
Abstract Interface for Wallet Repository.

Why: Decouples wallet balance retrieval and updating logic from the storage engine,
enabling easy unit testing through mocks or in-memory repository implementations.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain.entities import Wallet


class WalletRepositoryInterface(ABC):
    """Contract for wallet persistence and balance manipulation."""

    @abstractmethod
    def get_by_id(self, wallet_id: int, *, for_update: bool = False) -> Wallet | None:
        """Retrieves a wallet by its ID.

        Args:
            wallet_id: Unique wallet identifier.

        Returns:
            Wallet entity or None if non-existent.
        """
        pass

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[Wallet]:
        """Lists all wallets owned by a specific user.

        Args:
            user_id: Owner user identifier.

        Returns:
            List of Wallet entities.
        """
        pass

    @abstractmethod
    def create(self, wallet: Wallet) -> Wallet:
        """Persists a new wallet.

        Args:
            wallet: Wallet entity to store.

        Returns:
            Persisted Wallet entity with generated ID.
        """
        pass

    @abstractmethod
    def update_balance(self, wallet_id: int, new_balance: Decimal) -> Wallet:
        """Atomically updates and persists the balance of a wallet.

        Why: Ensures consistency and immediate durability of balance mutations after a transaction.

        Args:
            wallet_id: Identifier of the wallet to update.
            new_balance: New calculated balance.

        Returns:
            Wallet entity reflecting the updated balance.
        """
        pass

    @abstractmethod
    def update(self, wallet: Wallet) -> Wallet:
        """Persist wallet metadata and active state."""
        pass

    @abstractmethod
    def has_transactions(self, wallet_id: int) -> bool:
        """Return whether changing immutable financial metadata would affect history."""
        pass
