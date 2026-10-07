"""Authenticated budget CRUD and live usage endpoints."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.entities import Budget, User, require_id
from app.infrastructure.web.dependencies import (
    get_budget_alert_service,
    get_budget_repository,
    get_category_repository,
    get_current_user,
)
from app.interfaces.schemas.budget import (
    BudgetCreateRequest,
    BudgetResponse,
    BudgetUpdateRequest,
    BudgetUsageResponse,
)
from app.use_cases.budget_alerts import BudgetAlertService
from app.use_cases.interfaces.budget_repository import BudgetRepositoryInterface
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface

router = APIRouter(prefix="/budgets", tags=["Budgets"])


def _reference_datetime(value: date | None, timezone_name: str) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return datetime.combine(value, time.min, tzinfo=ZoneInfo(timezone_name)).astimezone(UTC)


def _get_owned_budget(budget_id: int, user_id: int, repo: BudgetRepositoryInterface) -> Budget:
    budget = repo.get_by_id_for_user(budget_id, user_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.post("/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreateRequest,
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
    alert_service: BudgetAlertService = Depends(get_budget_alert_service),
) -> BudgetResponse:
    user_id = require_id(current_user.id)
    if (
        payload.category_id is not None
        and category_repo.get_by_id_for_user(payload.category_id, user_id) is None
    ):
        raise HTTPException(status_code=404, detail="Category not found")
    if repo.get_by_scope(user_id, payload.category_id, payload.period):
        raise HTTPException(status_code=409, detail="Budget already exists for this scope")
    budget = repo.create(
        Budget(
            user_id=user_id,
            category_id=payload.category_id,
            limit_amount=payload.limit_amount,
            period=payload.period,
            alert_threshold=payload.alert_threshold,
            alerts_enabled=payload.alerts_enabled,
        )
    )
    alert_service.evaluate_budget(
        budget, datetime.now(UTC), current_user.timezone, current_user.base_currency
    )
    return BudgetResponse.model_validate(budget)


@router.get("/", response_model=list[BudgetResponse])
def list_budgets(
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
) -> list[BudgetResponse]:
    return [
        BudgetResponse.model_validate(item)
        for item in repo.list_by_user(require_id(current_user.id))
    ]


@router.get("/status", response_model=list[BudgetUsageResponse])
def list_budget_statuses(
    on_date: date | None = None,
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
    alert_service: BudgetAlertService = Depends(get_budget_alert_service),
) -> list[BudgetUsageResponse]:
    reference = _reference_datetime(on_date, current_user.timezone)
    return [
        BudgetUsageResponse.model_validate(
            alert_service.get_usage(
                budget, reference, current_user.timezone, current_user.base_currency
            )
        )
        for budget in repo.list_by_user(require_id(current_user.id))
    ]


@router.get("/{id}", response_model=BudgetResponse)
def get_budget_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
) -> BudgetResponse:
    return BudgetResponse.model_validate(_get_owned_budget(id, require_id(current_user.id), repo))


@router.get("/{id}/status", response_model=BudgetUsageResponse)
def get_budget_status(
    id: int,
    on_date: date | None = None,
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
    alert_service: BudgetAlertService = Depends(get_budget_alert_service),
) -> BudgetUsageResponse:
    budget = _get_owned_budget(id, require_id(current_user.id), repo)
    return BudgetUsageResponse.model_validate(
        alert_service.get_usage(
            budget,
            _reference_datetime(on_date, current_user.timezone),
            current_user.timezone,
            current_user.base_currency,
        )
    )


@router.put("/{id}", response_model=BudgetResponse)
def update_budget(
    id: int,
    payload: BudgetUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
    alert_service: BudgetAlertService = Depends(get_budget_alert_service),
) -> BudgetResponse:
    user_id = require_id(current_user.id)
    budget = _get_owned_budget(id, user_id, repo)
    new_period = payload.period or budget.period
    duplicate = repo.get_by_scope(user_id, budget.category_id, new_period)
    if duplicate is not None and duplicate.id != budget.id:
        raise HTTPException(status_code=409, detail="Budget already exists for this scope")
    if payload.limit_amount is not None:
        budget.limit_amount = payload.limit_amount
    if payload.alert_threshold is not None:
        budget.alert_threshold = payload.alert_threshold
    if payload.alerts_enabled is not None:
        budget.alerts_enabled = payload.alerts_enabled
    if new_period != budget.period or payload.alerts_enabled is False:
        alert_service.resolve_all_for_budget(id)
    budget.period = new_period
    saved = repo.update(budget)
    alert_service.evaluate_budget(
        saved, datetime.now(UTC), current_user.timezone, current_user.base_currency
    )
    return BudgetResponse.model_validate(saved)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    id: int,
    current_user: User = Depends(get_current_user),
    repo: BudgetRepositoryInterface = Depends(get_budget_repository),
) -> None:
    _get_owned_budget(id, require_id(current_user.id), repo)
    repo.delete(id)
