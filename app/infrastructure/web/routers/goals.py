"""Financial goal and contribution endpoints."""

from fastapi import APIRouter, Depends, Query, status

from app.domain.entities import GoalStatus, User, require_id
from app.infrastructure.web.dependencies import get_current_user, get_manage_goals_use_case
from app.interfaces.schemas.goal import (
    GoalContributionCreateRequest,
    GoalContributionResponse,
    GoalContributionResult,
    GoalCreateRequest,
    GoalResponse,
    GoalUpdateRequest,
)
from app.use_cases.goals import ManageGoalsUseCase

router = APIRouter(prefix="/goals", tags=["Financial Goals"])


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreateRequest,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> GoalResponse:
    goal = use_case.create(
        user_id=require_id(current_user.id),
        name=payload.name,
        description=payload.description,
        target_amount=payload.target_amount,
        currency=current_user.base_currency,
        target_date=payload.target_date,
    )
    return GoalResponse.model_validate(goal)


@router.get("/", response_model=list[GoalResponse])
def list_goals(
    goal_status: GoalStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> list[GoalResponse]:
    return [
        GoalResponse.model_validate(goal)
        for goal in use_case.list_goals(require_id(current_user.id), goal_status, limit, offset)
    ]


@router.get("/{id}", response_model=GoalResponse)
def get_goal(
    id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> GoalResponse:
    return GoalResponse.model_validate(use_case.get(id, require_id(current_user.id)))


@router.put("/{id}", response_model=GoalResponse)
def update_goal(
    id: int,
    payload: GoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> GoalResponse:
    goal = use_case.update(
        goal_id=id,
        user_id=require_id(current_user.id),
        name=payload.name,
        description=payload.description,
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        status=payload.status,
        name_was_set="name" in payload.model_fields_set,
        description_was_set="description" in payload.model_fields_set,
        target_date_was_set="target_date" in payload.model_fields_set,
    )
    return GoalResponse.model_validate(goal)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> None:
    use_case.delete(id, require_id(current_user.id))


@router.post(
    "/{id}/contributions",
    response_model=GoalContributionResult,
    status_code=status.HTTP_201_CREATED,
)
def add_contribution(
    id: int,
    payload: GoalContributionCreateRequest,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> GoalContributionResult:
    goal, contribution = use_case.contribute(
        goal_id=id,
        user_id=require_id(current_user.id),
        amount=payload.amount,
        note=payload.note,
        contributed_at=payload.contributed_at,
        timezone_name=current_user.timezone,
    )
    return GoalContributionResult(
        goal=GoalResponse.model_validate(goal),
        contribution=GoalContributionResponse.model_validate(contribution),
    )


@router.get("/{id}/contributions", response_model=list[GoalContributionResponse])
def list_contributions(
    id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> list[GoalContributionResponse]:
    return [
        GoalContributionResponse.model_validate(item)
        for item in use_case.list_contributions(id, require_id(current_user.id))
    ]


@router.delete("/{id}/contributions/{contribution_id}", response_model=GoalResponse)
def delete_contribution(
    id: int,
    contribution_id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageGoalsUseCase = Depends(get_manage_goals_use_case),
) -> GoalResponse:
    goal = use_case.delete_contribution(id, contribution_id, require_id(current_user.id))
    return GoalResponse.model_validate(goal)
