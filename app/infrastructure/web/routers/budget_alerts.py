"""Authenticated budget notification inbox endpoints."""

from fastapi import APIRouter, Depends, Query

from app.domain.entities import User, require_id
from app.infrastructure.web.dependencies import get_budget_alert_service, get_current_user
from app.interfaces.schemas.budget import (
    BudgetAlertCountResponse,
    BudgetAlertResponse,
    BudgetAlertsReadResponse,
)
from app.use_cases.budget_alerts import BudgetAlertService

router = APIRouter(prefix="/budget-alerts", tags=["Budget Alerts"])


@router.get("/", response_model=list[BudgetAlertResponse])
def list_budget_alerts(
    unread_only: bool = Query(False),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: BudgetAlertService = Depends(get_budget_alert_service),
) -> list[BudgetAlertResponse]:
    return [
        BudgetAlertResponse.model_validate(alert)
        for alert in service.list_alerts(
            require_id(current_user.id),
            unread_only=unread_only,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
    ]


@router.get("/unread-count", response_model=BudgetAlertCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    service: BudgetAlertService = Depends(get_budget_alert_service),
) -> BudgetAlertCountResponse:
    return BudgetAlertCountResponse(unread_count=service.unread_count(require_id(current_user.id)))


@router.post("/read-all", response_model=BudgetAlertsReadResponse)
def mark_all_alerts_read(
    current_user: User = Depends(get_current_user),
    service: BudgetAlertService = Depends(get_budget_alert_service),
) -> BudgetAlertsReadResponse:
    return BudgetAlertsReadResponse(updated=service.mark_all_read(require_id(current_user.id)))


@router.patch("/{id}/read", response_model=BudgetAlertResponse)
def mark_alert_read(
    id: int,
    current_user: User = Depends(get_current_user),
    service: BudgetAlertService = Depends(get_budget_alert_service),
) -> BudgetAlertResponse:
    return BudgetAlertResponse.model_validate(service.mark_read(id, require_id(current_user.id)))
