"""
Use Case: Create Transaction (Income/Expense).

Why: Coordinates the core domain business rule: every financial movement
must consistently and atomically update the corresponding wallet balance,
enforcing ownership and data-integrity constraints.
"""

import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.entities import (
    Transaction,
    TransactionSource,
    TransactionType,
    Wallet,
    normalize_event_datetime,
    require_id,
)
from app.domain.exceptions import (
    UnauthorizedWalletAccessError,
    WalletNotFoundError,
)
from app.use_cases.budget_alerts import BudgetAlertService
from app.use_cases.exchange_rates import ExchangeRateService
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface

logger = logging.getLogger(__name__)


class CreateTransactionUseCase:
    """Use case for recording transactions and synchronizing wallet balances.

    Why: Demonstrates Clean Architecture by orchestrating business rules
    without direct coupling to web controllers or raw SQL statements.
    """

    def __init__(
        self,
        transaction_repository: TransactionRepositoryInterface,
        wallet_repository: WalletRepositoryInterface,
        exchange_rate_service: ExchangeRateService,
        budget_alert_service: BudgetAlertService,
    ) -> None:
        """Injects repository dependencies required to complete the workflow.

        Args:
            transaction_repository: Repository to persist the transaction.
            wallet_repository: Repository to query and update the wallet balance.
        """
        self.transaction_repository = transaction_repository
        self.wallet_repository = wallet_repository
        self.exchange_rate_service = exchange_rate_service
        self.budget_alert_service = budget_alert_service

    def execute(
        self,
        user_id: int,
        wallet_id: int,
        amount: Decimal,
        transaction_type: TransactionType,
        category_id: int | None = None,
        description: str | None = None,
        occurred_at: datetime | None = None,
        base_currency: str = "BRL",
        timezone_name: str = "America/Sao_Paulo",
        source: TransactionSource = TransactionSource.MANUAL,
        external_id: str | None = None,
        import_batch_id: int | None = None,
    ) -> tuple[Transaction, Wallet]:
        """Executes transaction creation, updating the wallet balance accordingly.

        Why: Ensures referential and business integrity block-by-block:
        1. Validates wallet existence.
        2. Verifies ownership by the requesting user (resource security / IDOR defense).
        3. Applies the balance mutation on the pure domain entity.
        4. Persists the updated balance and new transaction record together.

        Args:
            user_id: Authenticated user ID performing the operation.
            wallet_id: Target wallet ID for the transaction.
            amount: Monetary value of the operation (must be strictly positive).
            transaction_type: Transaction type enum (INCOME or EXPENSE).
            category_id: Optional assigned category ID.
            description: Optional textual note describing the transaction.

        Returns:
            Tuple containing created Transaction and updated Wallet entities.

        Raises:
            ValueError: If amount is not strictly positive or transaction type is unknown.
            WalletNotFoundError: If target wallet does not exist.
            UnauthorizedWalletAccessError: If the wallet belongs to a different user.
        """
        if amount <= 0:
            raise ValueError("Transaction amount must be greater than zero.")

        # Why: Verifies wallet existence before running calculations
        wallet = self.wallet_repository.get_by_id(wallet_id)
        if wallet is None:
            logger.warning("Wallet not found with id %s for user %s", wallet_id, user_id)
            raise WalletNotFoundError(wallet_id)

        # Why: Validates that the wallet belongs to the authenticated user (prevents IDOR)
        if wallet.user_id != user_id:
            logger.warning("Unauthorized access to wallet %s by user %s", wallet_id, user_id)
            raise UnauthorizedWalletAccessError(wallet_id, user_id)

        if not wallet.is_active:
            raise WalletNotFoundError(wallet_id)

        event_time = normalize_event_datetime(occurred_at, timezone_name)
        requested_rate_date = event_time.astimezone(ZoneInfo(timezone_name)).date()
        quote = self.exchange_rate_service.quote(
            amount=amount,
            base_currency=wallet.currency,
            quote_currency=base_currency,
            on_date=requested_rate_date,
        )

        # Do not keep a row lock open while a missing external rate is fetched.
        locked_wallet = self.wallet_repository.get_by_id(wallet_id, for_update=True)
        if locked_wallet is None or not locked_wallet.is_active:
            raise WalletNotFoundError(wallet_id)
        if locked_wallet.user_id != user_id:
            raise UnauthorizedWalletAccessError(wallet_id, user_id)
        if locked_wallet.currency != wallet.currency:
            quote = self.exchange_rate_service.quote(
                amount=amount,
                base_currency=locked_wallet.currency,
                quote_currency=base_currency,
                on_date=requested_rate_date,
            )
        wallet = locked_wallet

        # Why: Delegates balance update to pure Wallet domain methods
        if transaction_type == TransactionType.INCOME:
            wallet.deposit(amount)
        elif transaction_type == TransactionType.EXPENSE:
            wallet.withdraw(amount)
        else:
            raise ValueError(f"Unknown transaction type: {transaction_type}")

        # Why: Updates persistent wallet balance
        wallet_id = require_id(wallet.id)
        updated_wallet = self.wallet_repository.update_balance(wallet_id, wallet.balance)

        # Why: Persists the transaction record
        new_transaction = Transaction(
            wallet_id=wallet_id,
            amount=amount,
            transaction_type=transaction_type,
            category_id=category_id,
            description=description,
            occurred_at=event_time,
            currency=wallet.currency,
            base_currency=base_currency,
            exchange_rate=quote.rate,
            base_amount=quote.converted_amount,
            rate_date=quote.effective_date,
            source=source,
            external_id=external_id,
            import_batch_id=import_batch_id,
        )
        saved_transaction = self.transaction_repository.create(new_transaction)
        self.budget_alert_service.evaluate_transaction(
            saved_transaction, user_id, timezone_name
        )

        logger.info(
            "Transaction %s created for wallet %s with new balance %s",
            saved_transaction.id,
            wallet.id,
            updated_wallet.balance,
        )

        return saved_transaction, updated_wallet
