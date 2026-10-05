"""Domain package initialization."""

from app.domain.entities import Budget, Category, Transaction, TransactionType, User, Wallet
from app.domain.exceptions import (
    DomainError,
    InvalidCredentialsError,
    UnauthorizedWalletAccessError,
    UserAlreadyExistsError,
    WalletNotFoundError,
)

__all__ = [
    "User",
    "Wallet",
    "Category",
    "Transaction",
    "Budget",
    "TransactionType",
    "DomainError",
    "WalletNotFoundError",
    "UnauthorizedWalletAccessError",
    "UserAlreadyExistsError",
    "InvalidCredentialsError",
]
