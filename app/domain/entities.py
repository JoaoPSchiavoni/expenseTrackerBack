"""
Domain Entities for Expense Tracker.

Why: Domain entities form the core of Clean Architecture.
They are pure business objects (POPOs) with no dependencies on
SQLAlchemy, FastAPI, or external persistence frameworks.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from app.domain.exceptions import InsufficientFundsError


def _utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


MONEY_QUANTUM = Decimal("0.01")
RATE_QUANTUM = Decimal("0.0000000001")


def normalize_money(value: Decimal | int | float | str) -> Decimal:
    """Normalize monetary values to two decimal places without binary float arithmetic."""
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def normalize_rate(value: Decimal | int | float | str) -> Decimal:
    """Normalize exchange rates without losing the precision required for conversion."""
    return Decimal(str(value)).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def normalize_event_datetime(value: datetime | None, timezone_name: str) -> datetime:
    """Interpret naive client datetimes in the user's timezone and persist UTC."""
    event_time = value or _utc_now()
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=ZoneInfo(timezone_name))
    return event_time.astimezone(UTC)


def require_id(value: int | None) -> int:
    """Return a persisted entity ID and fail fast for transient entities."""
    if value is None:
        raise ValueError("Persisted entity is missing its identifier")
    return value


class TransactionType(str, Enum):
    """Possible types for a financial transaction."""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransactionSource(str, Enum):
    """Origin of a financial transaction."""

    MANUAL = "MANUAL"
    CSV = "CSV"
    OFX = "OFX"


@dataclass
class User:
    """Domain entity representing a user in the system."""

    email: str
    hashed_password: str
    id: int | None = None
    full_name: str | None = None
    base_currency: str = "BRL"
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Wallet:
    """Domain entity representing a financial wallet or bank account."""

    user_id: int
    name: str
    balance: Decimal = Decimal("0.00")
    currency: str = "BRL"
    is_active: bool = True
    id: int | None = None
    created_at: datetime = field(default_factory=_utc_now)

    def deposit(self, amount: Decimal) -> None:
        """Increases the available wallet balance.

        Why: Encapsulates increment rules within the entity to ensure
        non-positive amounts cannot be directly credited.

        Args:
            amount: Positive numeric amount to deposit.

        Raises:
            ValueError: If the amount is not strictly positive.
        """
        amount = normalize_money(amount)
        if amount <= 0:
            raise ValueError("Deposit amount must be greater than zero.")
        self.balance = normalize_money(self.balance + amount)

    def withdraw(self, amount: Decimal) -> None:
        """Deducts an amount from the available wallet balance.

        Why: Enforces the business invariant of sufficient funds before allowing
        a debit, preserving financial domain consistency.

        Args:
            amount: Positive numeric amount to withdraw.

        Raises:
            ValueError: If the amount is not strictly positive.
            InsufficientFundsError: If the current balance is lower than requested.
        """
        amount = normalize_money(amount)
        if amount <= 0:
            raise ValueError("Withdrawal amount must be greater than zero.")
        if self.balance < amount:
            raise InsufficientFundsError(
                wallet_id=self.id or 0, current_balance=self.balance, requested_amount=amount
            )
        self.balance = normalize_money(self.balance - amount)


@dataclass
class Category:
    """Domain entity that categorizes transactions."""

    user_id: int
    name: str
    description: str | None = None
    id: int | None = None


@dataclass
class Transaction:
    """Domain entity representing a financial movement (income or expense)."""

    wallet_id: int
    amount: Decimal
    transaction_type: TransactionType
    category_id: int | None = None
    description: str | None = None
    occurred_at: datetime = field(default_factory=_utc_now)
    currency: str = "BRL"
    base_currency: str = "BRL"
    exchange_rate: Decimal = Decimal("1.0000000000")
    base_amount: Decimal = Decimal("0.00")
    rate_date: date | None = None
    source: TransactionSource = TransactionSource.MANUAL
    external_id: str | None = None
    import_batch_id: int | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Budget:
    """Domain entity representing a category spending limit."""

    user_id: int
    category_id: int
    limit_amount: Decimal
    period: str = "MONTHLY"
    id: int | None = None
    created_at: datetime = field(default_factory=_utc_now)
