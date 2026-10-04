"""
FastAPI Dependency Injection Module.

Why: Configures FastAPI's native dependency injection container.
Aligned with the Dependency Inversion Principle (DIP) and Clean Architecture,
HTTP route handlers receive fully instantiated Use Cases with their dependencies resolved.
"""

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.entities import User
from app.infrastructure.database.connection import get_db_session
from app.infrastructure.exchange_rates import FrankfurterExchangeRateProvider
from app.infrastructure.imports import StatementParser
from app.infrastructure.security.jwt_handler import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.interfaces.repositories.sql_budget_repository import SqlBudgetRepository
from app.interfaces.repositories.sql_category_repository import SqlCategoryRepository
from app.interfaces.repositories.sql_exchange_rate_repository import SqlExchangeRateRepository
from app.interfaces.repositories.sql_goal_repository import SqlGoalRepository
from app.interfaces.repositories.sql_import_repository import SqlImportRepository
from app.interfaces.repositories.sql_report_repository import SqlReportRepository
from app.interfaces.repositories.sql_transaction_repository import SqlTransactionRepository
from app.interfaces.repositories.sql_user_repository import SqlUserRepository
from app.interfaces.repositories.sql_wallet_repository import SqlWalletRepository
from app.use_cases.auth.login import AuthenticateUserUseCase
from app.use_cases.auth.register import RegisterUserUseCase
from app.use_cases.exchange_rates import ExchangeRateService
from app.use_cases.goals import ManageGoalsUseCase
from app.use_cases.imports import ImportStatementsUseCase
from app.use_cases.interfaces.budget_repository import BudgetRepositoryInterface
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.user_repository import UserRepositoryInterface
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface
from app.use_cases.transactions.create_transaction import CreateTransactionUseCase
from app.use_cases.transactions.manage_transaction import ManageTransactionUseCase

# Why: Sets up Bearer Token security scheme for parsing Authorization headers
security_scheme = HTTPBearer(auto_error=True)


# --- 1. Database Session ---
def get_db() -> Generator[Session, None, None]:
    """Provides a database session for the current request."""
    yield from get_db_session()


# --- 2. Repositories ---
def get_user_repository(session: Session = Depends(get_db)) -> UserRepositoryInterface:
    """Provides the concrete user repository implementation."""
    return SqlUserRepository(session)


def get_wallet_repository(session: Session = Depends(get_db)) -> WalletRepositoryInterface:
    """Provides the concrete wallet repository implementation."""
    return SqlWalletRepository(session)


def get_transaction_repository(
    session: Session = Depends(get_db),
) -> TransactionRepositoryInterface:
    """Provides the concrete transaction repository implementation."""
    return SqlTransactionRepository(session)


def get_category_repository(session: Session = Depends(get_db)) -> CategoryRepositoryInterface:
    return SqlCategoryRepository(session)


def get_budget_repository(session: Session = Depends(get_db)) -> BudgetRepositoryInterface:
    return SqlBudgetRepository(session)


def get_report_repository(session: Session = Depends(get_db)) -> SqlReportRepository:
    return SqlReportRepository(session)


def get_exchange_rate_service(session: Session = Depends(get_db)) -> ExchangeRateService:
    """Build the exchange-rate service with persistent daily caching."""
    return ExchangeRateService(
        repository=SqlExchangeRateRepository(session),
        provider=FrankfurterExchangeRateProvider(
            settings.EXCHANGE_RATE_API_URL,
            settings.EXCHANGE_RATE_TIMEOUT_SECONDS,
        ),
    )


def get_import_repository(session: Session = Depends(get_db)) -> SqlImportRepository:
    return SqlImportRepository(session)


def get_goal_repository(session: Session = Depends(get_db)) -> SqlGoalRepository:
    return SqlGoalRepository(session)


# --- 3. Use Cases (Interactors) ---
def get_register_user_use_case(
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> RegisterUserUseCase:
    """Builds and injects the user registration use case."""
    return RegisterUserUseCase(
        user_repository=user_repo,
        hash_password_fn=hash_password,
    )


def get_authenticate_user_use_case(
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> AuthenticateUserUseCase:
    """Builds and injects the user authentication use case."""
    return AuthenticateUserUseCase(
        user_repository=user_repo,
        verify_password_fn=verify_password,
        create_token_fn=create_access_token,
    )


def get_create_transaction_use_case(
    tx_repo: TransactionRepositoryInterface = Depends(get_transaction_repository),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
    exchange_rate_service: ExchangeRateService = Depends(get_exchange_rate_service),
) -> CreateTransactionUseCase:
    """Builds and injects the create transaction use case."""
    return CreateTransactionUseCase(
        transaction_repository=tx_repo,
        wallet_repository=wallet_repo,
        exchange_rate_service=exchange_rate_service,
    )


def get_manage_transaction_use_case(
    tx_repo: TransactionRepositoryInterface = Depends(get_transaction_repository),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
    exchange_rate_service: ExchangeRateService = Depends(get_exchange_rate_service),
) -> ManageTransactionUseCase:
    return ManageTransactionUseCase(tx_repo, wallet_repo, exchange_rate_service)


def get_import_statements_use_case(
    import_repo: SqlImportRepository = Depends(get_import_repository),
    tx_repo: TransactionRepositoryInterface = Depends(get_transaction_repository),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
    create_transaction: CreateTransactionUseCase = Depends(get_create_transaction_use_case),
) -> ImportStatementsUseCase:
    return ImportStatementsUseCase(
        import_repository=import_repo,
        transaction_repository=tx_repo,
        wallet_repository=wallet_repo,
        category_repository=category_repo,
        create_transaction=create_transaction,
        parser=StatementParser(),
        max_file_size_bytes=settings.IMPORT_MAX_FILE_SIZE_BYTES,
        max_rows=settings.IMPORT_MAX_ROWS,
    )


def get_manage_goals_use_case(
    repository: SqlGoalRepository = Depends(get_goal_repository),
) -> ManageGoalsUseCase:
    return ManageGoalsUseCase(repository)


# --- 4. Current Authenticated User ---
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> User:
    """Extracts and verifies the authenticated user from the JWT Bearer token.

    Why: Centralizes credential verification and guarantees protected routes
    have immediate access to a valid and active User entity.

    Args:
        credentials: Authorization header credential pair.
        user_repo: Repository to fetch User entity.

    Returns:
        Authenticated User domain entity.

    Raises:
        HTTPException: 401 Unauthorized if the token is invalid, expired, or user not found.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token subject",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = user_repo.get_by_id(user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
