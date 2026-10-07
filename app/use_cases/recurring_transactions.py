import calendar
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo

from app.domain.entities import (
    RecurrenceFrequency,
    RecurringTransaction,
    TransactionSource,
    TransactionType,
    require_id,
)
from app.domain.exceptions import UnauthorizedWalletAccessError, WalletNotFoundError
from app.use_cases.interfaces.recurring_transaction_repository import (
    RecurringTransactionRepositoryInterface,
)
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface
from app.use_cases.transactions.create_transaction import CreateTransactionUseCase


def next_occurrence(
    current: date,
    frequency: RecurrenceFrequency,
    interval_count: int,
    anchor_day: int,
) -> date:
    """Advance a schedule while preserving the preferred day where possible."""
    if frequency == RecurrenceFrequency.DAILY:
        return current + timedelta(days=interval_count)
    if frequency == RecurrenceFrequency.WEEKLY:
        return current + timedelta(weeks=interval_count)
    if frequency == RecurrenceFrequency.MONTHLY:
        absolute_month = current.year * 12 + current.month - 1 + interval_count
        year, zero_based_month = divmod(absolute_month, 12)
        month = zero_based_month + 1
        day = min(anchor_day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    year = current.year + interval_count
    month = current.month
    day = min(anchor_day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class ManageRecurringTransactionsUseCase:
    """Create schedules and materialize their due transactions idempotently."""

    def __init__(
        self,
        repository: RecurringTransactionRepositoryInterface,
        wallet_repository: WalletRepositoryInterface,
        create_transaction: CreateTransactionUseCase,
    ) -> None:
        self.repository = repository
        self.wallet_repository = wallet_repository
        self.create_transaction = create_transaction

    def _validate_wallet(self, wallet_id: int, user_id: int) -> None:
        wallet = self.wallet_repository.get_by_id(wallet_id)
        if wallet is None or not wallet.is_active:
            raise WalletNotFoundError(wallet_id)
        if wallet.user_id != user_id:
            raise UnauthorizedWalletAccessError(wallet_id, user_id)

    def create(
        self,
        *,
        user_id: int,
        wallet_id: int,
        category_id: int | None,
        amount: Decimal,
        transaction_type: TransactionType,
        description: str | None,
        frequency: RecurrenceFrequency,
        interval_count: int,
        start_date: date,
        end_date: date | None,
    ) -> RecurringTransaction:
        self._validate_wallet(wallet_id, user_id)
        if end_date is not None and end_date < start_date:
            raise ValueError("End date cannot be before start date")
        return self.repository.create(
            RecurringTransaction(
                user_id=user_id,
                wallet_id=wallet_id,
                category_id=category_id,
                amount=amount,
                transaction_type=transaction_type,
                description=description,
                frequency=frequency,
                interval_count=interval_count,
                start_date=start_date,
                next_run_date=start_date,
                end_date=end_date,
            )
        )

    def list_for_user(self, user_id: int) -> list[RecurringTransaction]:
        return self.repository.list_by_user(user_id)

    def get(self, recurring_id: int, user_id: int) -> RecurringTransaction:
        recurring = self.repository.get_by_id_for_user(recurring_id, user_id)
        if recurring is None:
            raise ValueError("Recurring transaction not found")
        return recurring

    def update(
        self,
        recurring_id: int,
        user_id: int,
        changes: dict[str, object],
    ) -> RecurringTransaction:
        recurring = self.repository.get_by_id_for_user(
            recurring_id, user_id, for_update=True
        )
        if recurring is None:
            raise ValueError("Recurring transaction not found")
        if "wallet_id" in changes:
            wallet_id = cast(int, changes["wallet_id"])
            self._validate_wallet(wallet_id, user_id)
            recurring.wallet_id = wallet_id
        for name in (
            "category_id",
            "amount",
            "transaction_type",
            "description",
            "frequency",
            "interval_count",
            "end_date",
            "is_active",
        ):
            if name in changes:
                setattr(recurring, name, changes[name])
        if "start_date" in changes:
            recurring.start_date = changes["start_date"]  # type: ignore[assignment]
            recurring.next_run_date = recurring.start_date
        if recurring.end_date is not None and recurring.end_date < recurring.start_date:
            raise ValueError("End date cannot be before start date")
        if recurring.end_date is not None and recurring.next_run_date > recurring.end_date:
            recurring.is_active = False
        return self.repository.update(recurring)

    def delete(self, recurring_id: int, user_id: int) -> None:
        recurring = self.repository.get_by_id_for_user(recurring_id, user_id)
        if recurring is None:
            raise ValueError("Recurring transaction not found")
        self.repository.delete(recurring_id)

    def process_due(
        self,
        *,
        user_id: int,
        through_date: date,
        base_currency: str,
        timezone_name: str,
        max_occurrences: int = 366,
    ) -> list[int]:
        """Generate every due occurrence in the same database transaction."""
        generated_ids: list[int] = []
        timezone = ZoneInfo(timezone_name)
        for recurring in self.repository.list_due(user_id, through_date):
            while recurring.is_active and recurring.next_run_date <= through_date:
                if len(generated_ids) >= max_occurrences:
                    return generated_ids
                occurrence = recurring.next_run_date
                if recurring.end_date is not None and occurrence > recurring.end_date:
                    recurring.is_active = False
                    break
                recurring_id = require_id(recurring.id)
                event_time = datetime.combine(occurrence, time(hour=12), tzinfo=timezone)
                transaction, _ = self.create_transaction.execute(
                    user_id=user_id,
                    wallet_id=recurring.wallet_id,
                    amount=recurring.amount,
                    transaction_type=recurring.transaction_type,
                    category_id=recurring.category_id,
                    description=recurring.description,
                    occurred_at=event_time,
                    base_currency=base_currency,
                    timezone_name=timezone_name,
                    source=TransactionSource.RECURRING,
                    external_id=f"recurring:{recurring_id}:{occurrence.isoformat()}",
                )
                generated_ids.append(require_id(transaction.id))
                recurring.last_generated_at = datetime.now(UTC)
                recurring.next_run_date = next_occurrence(
                    occurrence,
                    recurring.frequency,
                    recurring.interval_count,
                    recurring.start_date.day,
                )
                if (
                    recurring.end_date is not None
                    and recurring.next_run_date > recurring.end_date
                ):
                    recurring.is_active = False
            self.repository.update(recurring)
        return generated_ids
