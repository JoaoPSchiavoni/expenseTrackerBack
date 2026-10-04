"""
SQLAlchemy Implementation of Wallet Repository.

Why: Maps WalletModel records to pure Wallet domain entities
and manages transactional balance updates to prevent race conditions.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.entities import Wallet
from app.domain.exceptions import WalletNotFoundError
from app.infrastructure.database.models import TransactionModel, WalletModel
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface


class SqlWalletRepository(WalletRepositoryInterface):
    """Wallet persistence adapter using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Injects active database session."""
        self.session = session

    def _to_entity(self, model: WalletModel) -> Wallet:
        """Maps WalletModel to the pure domain entity Wallet."""
        return Wallet(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            balance=model.balance,
            currency=model.currency,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def get_by_id(self, wallet_id: int, *, for_update: bool = False) -> Wallet | None:
        """Retrieves wallet by its ID."""
        query = self.session.query(WalletModel).filter(WalletModel.id == wallet_id)
        if for_update:
            query = query.with_for_update()
        model = query.first()
        return self._to_entity(model) if model else None

    def list_by_user(self, user_id: int) -> list[Wallet]:
        """Lists all wallets belonging to a user."""
        models = (
            self.session.query(WalletModel)
            .filter(WalletModel.user_id == user_id, WalletModel.is_active.is_(True))
            .all()
        )
        return [self._to_entity(m) for m in models]

    def create(self, wallet: Wallet) -> Wallet:
        """Inserts and persists a new wallet."""
        model = WalletModel(
            user_id=wallet.user_id,
            name=wallet.name,
            balance=wallet.balance,
            currency=wallet.currency,
            is_active=wallet.is_active,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def update_balance(self, wallet_id: int, new_balance: Decimal) -> Wallet:
        """Atomically updates wallet balance.

        Why: Updates balance within the current transaction,
        guaranteeing the latest balance is durably recorded.
        """
        model = self.session.query(WalletModel).filter(WalletModel.id == wallet_id).first()
        if not model:
            raise WalletNotFoundError(wallet_id)

        model.balance = new_balance
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def update(self, wallet: Wallet) -> Wallet:
        model = self.session.get(WalletModel, wallet.id)
        if model is None:
            raise WalletNotFoundError(wallet.id or 0)
        model.name = wallet.name
        model.currency = wallet.currency
        model.is_active = wallet.is_active
        model.balance = wallet.balance
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def has_transactions(self, wallet_id: int) -> bool:
        return (
            self.session.query(TransactionModel.id)
            .filter(TransactionModel.wallet_id == wallet_id)
            .first()
            is not None
        )
