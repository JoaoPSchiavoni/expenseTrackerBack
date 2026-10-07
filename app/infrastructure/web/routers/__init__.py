"""Web routers package initialization."""

from app.infrastructure.web.routers.auth import router as auth_router
from app.infrastructure.web.routers.budget_alerts import router as budget_alerts_router
from app.infrastructure.web.routers.budgets import router as budgets_router
from app.infrastructure.web.routers.categories import router as categories_router
from app.infrastructure.web.routers.currencies import router as currencies_router
from app.infrastructure.web.routers.dashboard import router as dashboard_router
from app.infrastructure.web.routers.goals import router as goals_router
from app.infrastructure.web.routers.health import router as health_router
from app.infrastructure.web.routers.imports import router as imports_router
from app.infrastructure.web.routers.recurring_transactions import (
    router as recurring_transactions_router,
)
from app.infrastructure.web.routers.reports import router as reports_router
from app.infrastructure.web.routers.transactions import router as transactions_router
from app.infrastructure.web.routers.users import router as users_router
from app.infrastructure.web.routers.wallets import router as wallets_router

__all__ = [
    "auth_router",
    "budget_alerts_router",
    "users_router",
    "wallets_router",
    "categories_router",
    "currencies_router",
    "dashboard_router",
    "transactions_router",
    "budgets_router",
    "reports_router",
    "recurring_transactions_router",
    "health_router",
    "goals_router",
    "imports_router",
]
