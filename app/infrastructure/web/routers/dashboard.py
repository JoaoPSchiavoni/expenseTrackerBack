"""Read-only aggregates designed for Flutter dashboard widgets."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.entities import User, require_id
from app.infrastructure.web.dependencies import get_current_user, get_dashboard_service
from app.interfaces.schemas.dashboard import (
    DashboardCashFlowItem,
    DashboardCashFlowResponse,
    DashboardCategoryItem,
    DashboardCategoryResponse,
    DashboardOverviewResponse,
    DashboardRecentTransactionResponse,
)
from app.use_cases.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _month_or_current(month: str | None, user: User, service: DashboardService) -> str:
    return month or service.current_month(user.timezone)


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardOverviewResponse:
    try:
        overview = service.overview(
            user_id=require_id(current_user.id),
            month=_month_or_current(month, current_user, service),
            timezone_name=current_user.timezone,
            currency=current_user.base_currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DashboardOverviewResponse.model_validate(overview)


@router.get("/cash-flow", response_model=DashboardCashFlowResponse)
def get_dashboard_cash_flow(
    months: int = Query(6, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardCashFlowResponse:
    items = service.cash_flow(
        user_id=require_id(current_user.id),
        months=months,
        timezone_name=current_user.timezone,
    )
    return DashboardCashFlowResponse(
        currency=current_user.base_currency,
        items=[DashboardCashFlowItem.model_validate(item) for item in items],
    )


@router.get("/spending-by-category", response_model=DashboardCategoryResponse)
def get_dashboard_spending_by_category(
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardCategoryResponse:
    selected_month = _month_or_current(month, current_user, service)
    try:
        items = service.spending_by_category(
            user_id=require_id(current_user.id),
            month=selected_month,
            timezone_name=current_user.timezone,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DashboardCategoryResponse(
        month=selected_month,
        currency=current_user.base_currency,
        items=[DashboardCategoryItem.model_validate(item) for item in items],
    )


@router.get(
    "/recent-transactions", response_model=list[DashboardRecentTransactionResponse]
)
def get_dashboard_recent_transactions(
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> list[DashboardRecentTransactionResponse]:
    return [
        DashboardRecentTransactionResponse.model_validate(item)
        for item in service.recent_transactions(require_id(current_user.id), limit)
    ]
