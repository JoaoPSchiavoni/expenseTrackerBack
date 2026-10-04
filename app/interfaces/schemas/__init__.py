"""Schemas package initialization."""

from app.interfaces.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.interfaces.schemas.budget import BudgetCreateRequest, BudgetResponse, BudgetUpdateRequest
from app.interfaces.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.interfaces.schemas.report import CategorySummaryResponse, MonthlyReportResponse
from app.interfaces.schemas.transaction import (
    TransactionBulkCreateRequest,
    TransactionBulkCreateResponse,
    TransactionCreateRequest,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionWithWalletResponse,
)
from app.interfaces.schemas.user import ChangePasswordRequest, UserResponse, UserUpdateRequest
from app.interfaces.schemas.wallet import WalletCreateRequest, WalletResponse, WalletUpdateRequest

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "UserUpdateRequest",
    "ChangePasswordRequest",
    "WalletCreateRequest",
    "WalletUpdateRequest",
    "WalletResponse",
    "CategoryCreateRequest",
    "CategoryUpdateRequest",
    "CategoryResponse",
    "TransactionCreateRequest",
    "TransactionUpdateRequest",
    "TransactionBulkCreateRequest",
    "TransactionBulkCreateResponse",
    "TransactionResponse",
    "TransactionWithWalletResponse",
    "BudgetCreateRequest",
    "BudgetUpdateRequest",
    "BudgetResponse",
    "MonthlyReportResponse",
    "CategorySummaryResponse",
]
