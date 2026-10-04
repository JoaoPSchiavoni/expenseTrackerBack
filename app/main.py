"""
FastAPI Main Application Entrypoint (Expense Tracker).

Why: Initializes the web application, registers domain exception handlers,
configures CORS middleware, and includes routers mapping all 53 endpoints
from the technical specification.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.domain.exceptions import (
    BudgetAlertNotFoundError,
    ContributionNotFoundError,
    GoalNotFoundError,
    InsufficientFundsError,
    InvalidCredentialsError,
    InvalidGoalStateError,
    UnauthorizedWalletAccessError,
    UserAlreadyExistsError,
    WalletNotFoundError,
)
from app.infrastructure.exchange_rates.frankfurter import (
    ExchangeRateProviderError,
    UnsupportedCurrencyError,
)
from app.infrastructure.web.routers import (
    auth_router,
    budget_alerts_router,
    budgets_router,
    categories_router,
    currencies_router,
    goals_router,
    health_router,
    imports_router,
    reports_router,
    transactions_router,
    users_router,
    wallets_router,
)

# Low-cardinality logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("expense_tracker")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle; schema changes are managed exclusively by Alembic."""
    logger.info("Application started in %s mode.", settings.ENVIRONMENT)
    yield
    logger.info("Application shutdown completed.")


# FastAPI application instance
app = FastAPI(
    title=settings.APP_NAME,
    description="Expense Tracker API built with FastAPI, SQLAlchemy, and Clean Architecture.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global Domain Exception Handlers ---
# Why: Translates decoupled domain business exceptions into semantic HTTP status codes
@app.exception_handler(InsufficientFundsError)
async def insufficient_funds_handler(request: Request, exc: InsufficientFundsError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "INSUFFICIENT_FUNDS", "detail": exc.message},
    )


@app.exception_handler(WalletNotFoundError)
async def wallet_not_found_handler(request: Request, exc: WalletNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "WALLET_NOT_FOUND", "detail": exc.message},
    )


@app.exception_handler(UnauthorizedWalletAccessError)
async def unauthorized_wallet_handler(
    request: Request, exc: UnauthorizedWalletAccessError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error": "FORBIDDEN_WALLET_ACCESS", "detail": exc.message},
    )


@app.exception_handler(UserAlreadyExistsError)
async def user_exists_handler(request: Request, exc: UserAlreadyExistsError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "USER_ALREADY_EXISTS", "detail": exc.message},
    )


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(
    request: Request, exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": "INVALID_CREDENTIALS", "detail": exc.message},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(GoalNotFoundError)
async def goal_not_found_handler(request: Request, exc: GoalNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "GOAL_NOT_FOUND", "detail": exc.message},
    )


@app.exception_handler(BudgetAlertNotFoundError)
async def budget_alert_not_found_handler(
    request: Request, exc: BudgetAlertNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "BUDGET_ALERT_NOT_FOUND", "detail": exc.message},
    )


@app.exception_handler(ContributionNotFoundError)
async def contribution_not_found_handler(
    request: Request, exc: ContributionNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "CONTRIBUTION_NOT_FOUND", "detail": exc.message},
    )


@app.exception_handler(InvalidGoalStateError)
async def invalid_goal_state_handler(
    request: Request, exc: InvalidGoalStateError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "INVALID_GOAL_STATE", "detail": exc.message},
    )


@app.exception_handler(ExchangeRateProviderError)
async def exchange_rate_provider_handler(
    request: Request, exc: ExchangeRateProviderError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"error": "EXCHANGE_RATE_UNAVAILABLE", "detail": str(exc)},
    )


@app.exception_handler(UnsupportedCurrencyError)
async def unsupported_currency_handler(
    request: Request, exc: UnsupportedCurrencyError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "UNSUPPORTED_CURRENCY", "detail": str(exc)},
    )


# --- Router Registration ---
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(wallets_router, prefix=settings.API_V1_PREFIX)
app.include_router(categories_router, prefix=settings.API_V1_PREFIX)
app.include_router(currencies_router, prefix=settings.API_V1_PREFIX)
app.include_router(imports_router, prefix=settings.API_V1_PREFIX)
app.include_router(goals_router, prefix=settings.API_V1_PREFIX)
app.include_router(budget_alerts_router, prefix=settings.API_V1_PREFIX)
app.include_router(transactions_router, prefix=settings.API_V1_PREFIX)
app.include_router(budgets_router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router, prefix=settings.API_V1_PREFIX)
app.include_router(health_router)
