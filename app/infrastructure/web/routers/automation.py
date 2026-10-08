"""Endpoints for automatic categorization and recurring-charge intelligence."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.domain.entities import CategorizationRule, User, require_id
from app.infrastructure.web.dependencies import (
    get_automation_repository,
    get_automation_service,
    get_category_repository,
    get_current_user,
)
from app.interfaces.repositories.sql_automation_repository import SqlAutomationRepository
from app.interfaces.schemas.automation import (
    AlertSyncResponse,
    BillingAlertResponse,
    CategorizationRuleCreateRequest,
    CategorizationRuleResponse,
    CategorizationRuleUpdateRequest,
    DetectedSubscriptionResponse,
    DetectionResponse,
    RuleTestRequest,
    RuleTestResponse,
    SubscriptionStatusRequest,
)
from app.use_cases.automation import AutomationService
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface

router = APIRouter(prefix="/automation", tags=["Automation"])


def _check_category(category_id: int, user_id: int, repo: CategoryRepositoryInterface) -> None:
    if repo.get_by_id_for_user(category_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")


@router.post("/rules", response_model=CategorizationRuleResponse, status_code=201)
def create_rule(
    payload: CategorizationRuleCreateRequest,
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
    service: AutomationService = Depends(get_automation_service),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> CategorizationRuleResponse:
    user_id = require_id(current_user.id)
    _check_category(payload.category_id, user_id, category_repo)
    try:
        service.validate_pattern(payload.match_type, payload.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        rule = repository.create_rule(
            CategorizationRule(user_id=user_id, **payload.model_dump())
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A rule with this name already exists") from exc
    return CategorizationRuleResponse.model_validate(rule)


@router.get("/rules", response_model=list[CategorizationRuleResponse])
def list_rules(
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
) -> list[CategorizationRuleResponse]:
    return [
        CategorizationRuleResponse.model_validate(item)
        for item in repository.list_rules(require_id(current_user.id))
    ]


@router.post("/rules/test-match", response_model=RuleTestResponse)
def test_rules(
    payload: RuleTestRequest,
    current_user: User = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> RuleTestResponse:
    category_id = service.match_category(require_id(current_user.id), payload.description)
    return RuleTestResponse(category_id=category_id, matched=category_id is not None)


@router.put("/rules/{rule_id}", response_model=CategorizationRuleResponse)
def update_rule(
    rule_id: int,
    payload: CategorizationRuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
    service: AutomationService = Depends(get_automation_service),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> CategorizationRuleResponse:
    user_id = require_id(current_user.id)
    rule = repository.get_rule(rule_id, user_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Categorization rule not found")
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _check_category(changes["category_id"], user_id, category_repo)
    for field, value in changes.items():
        setattr(rule, field, value)
    try:
        service.validate_pattern(rule.match_type, rule.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return CategorizationRuleResponse.model_validate(repository.update_rule(rule))
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A rule with this name already exists") from exc


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
) -> None:
    try:
        repository.delete_rule(rule_id, require_id(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/subscriptions/detect", response_model=DetectionResponse)
def detect_subscriptions(
    current_user: User = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> DetectionResponse:
    items = service.detect_subscriptions(require_id(current_user.id))
    return DetectionResponse(
        detected=len(items),
        subscriptions=[DetectedSubscriptionResponse.model_validate(item) for item in items],
    )


@router.get("/subscriptions", response_model=list[DetectedSubscriptionResponse])
def list_subscriptions(
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
) -> list[DetectedSubscriptionResponse]:
    return [
        DetectedSubscriptionResponse.model_validate(item)
        for item in repository.list_subscriptions(require_id(current_user.id))
    ]


@router.patch("/subscriptions/{subscription_id}", response_model=DetectedSubscriptionResponse)
def update_subscription_status(
    subscription_id: int,
    payload: SubscriptionStatusRequest,
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
) -> DetectedSubscriptionResponse:
    try:
        item = repository.set_subscription_status(
            subscription_id, require_id(current_user.id), payload.status
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DetectedSubscriptionResponse.model_validate(item)


@router.post("/billing-alerts/sync", response_model=AlertSyncResponse)
def sync_billing_alerts(
    days_ahead: int = Query(7, ge=0, le=30),
    current_user: User = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> AlertSyncResponse:
    today = datetime.now(UTC).astimezone(ZoneInfo(current_user.timezone)).date()
    items = service.sync_alerts(
        require_id(current_user.id), today=today, days_ahead=days_ahead
    )
    return AlertSyncResponse(
        generated=len(items),
        alerts=[BillingAlertResponse.model_validate(item) for item in items],
    )


@router.get("/billing-alerts", response_model=list[BillingAlertResponse])
def list_billing_alerts(
    include_resolved: bool = False,
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
) -> list[BillingAlertResponse]:
    return [
        BillingAlertResponse.model_validate(item)
        for item in repository.list_alerts(
            require_id(current_user.id), include_resolved=include_resolved
        )
    ]


@router.patch("/billing-alerts/{alert_id}/read", response_model=BillingAlertResponse)
def mark_billing_alert_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    repository: SqlAutomationRepository = Depends(get_automation_repository),
) -> BillingAlertResponse:
    try:
        item = repository.mark_alert_read(alert_id, require_id(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BillingAlertResponse.model_validate(item)
