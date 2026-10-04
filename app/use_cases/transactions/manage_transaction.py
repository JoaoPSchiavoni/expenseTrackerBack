from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.entities import (
    Transaction,
    TransactionType,
    Wallet,
    normalize_event_datetime,
    normalize_money,
    require_id,
)
from app.domain.exceptions import WalletNotFoundError
from app.use_cases.exchange_rates import ExchangeRateService
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface


class ManageTransactionUseCase:
    """Update and delete ledger entries while keeping wallet balances consistent."""

    def __init__(
        self,
        transaction_repository: TransactionRepositoryInterface,
        wallet_repository: WalletRepositoryInterface,
        exchange_rate_service: ExchangeRateService,
    ) -> None:
        self.transaction_repository = transaction_repository
        self.wallet_repository = wallet_repository
        self.exchange_rate_service = exchange_rate_service

    def _load(self, transaction_id: int, user_id: int) -> tuple[Transaction, Wallet]:
        transaction = self.transaction_repository.get_by_id_for_user(transaction_id, user_id)
        if transaction is None:
            raise ValueError("Transaction not found")
        wallet = self.wallet_repository.get_by_id(transaction.wallet_id, for_update=True)
        if wallet is None or not wallet.is_active:
            raise WalletNotFoundError(transaction.wallet_id)
        return transaction, wallet

    @staticmethod
    def _reverse(wallet: Wallet, transaction: Transaction) -> None:
        if transaction.transaction_type == TransactionType.INCOME:
            wallet.withdraw(transaction.amount)
        else:
            wallet.deposit(transaction.amount)

    @staticmethod
    def _apply(wallet: Wallet, transaction_type: TransactionType, amount: Decimal) -> None:
        if transaction_type == TransactionType.INCOME:
            wallet.deposit(amount)
        else:
            wallet.withdraw(amount)

    def update(
        self,
        *,
        transaction_id: int,
        user_id: int,
        amount: Decimal | None,
        transaction_type: TransactionType | None,
        category_id: int | None,
        description: str | None,
        occurred_at: datetime | None,
        category_was_set: bool,
        description_was_set: bool,
        occurred_at_was_set: bool,
        timezone_name: str,
    ) -> tuple[Transaction, Wallet]:
        transaction, wallet = self._load(transaction_id, user_id)
        new_amount = amount if amount is not None else transaction.amount
        new_type = transaction_type or transaction.transaction_type

        self._reverse(wallet, transaction)
        self._apply(wallet, new_type, new_amount)

        transaction.amount = new_amount
        transaction.transaction_type = new_type
        if category_was_set:
            transaction.category_id = category_id
        if description_was_set:
            transaction.description = description
        if occurred_at_was_set:
            transaction.occurred_at = normalize_event_datetime(occurred_at, timezone_name)

        requested_rate_date = transaction.occurred_at.astimezone(ZoneInfo(timezone_name)).date()
        if occurred_at_was_set:
            quote = self.exchange_rate_service.quote(
                amount=new_amount,
                base_currency=transaction.currency,
                quote_currency=transaction.base_currency,
                on_date=requested_rate_date,
            )
            transaction.exchange_rate = quote.rate
            transaction.rate_date = quote.effective_date
            transaction.base_amount = quote.converted_amount
        else:
            transaction.base_amount = normalize_money(new_amount * transaction.exchange_rate)

        saved = self.transaction_repository.update(transaction)
        updated_wallet = self.wallet_repository.update_balance(
            require_id(wallet.id), wallet.balance
        )
        return saved, updated_wallet

    def delete(self, *, transaction_id: int, user_id: int) -> Wallet:
        transaction, wallet = self._load(transaction_id, user_id)
        self._reverse(wallet, transaction)
        self.transaction_repository.delete(require_id(transaction.id))
        return self.wallet_repository.update_balance(require_id(wallet.id), wallet.balance)
