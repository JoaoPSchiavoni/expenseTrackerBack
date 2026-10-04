"""Repository interfaces package for dependency inversion."""

from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.user_repository import UserRepositoryInterface
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface

__all__ = [
    "UserRepositoryInterface",
    "WalletRepositoryInterface",
    "TransactionRepositoryInterface",
]
