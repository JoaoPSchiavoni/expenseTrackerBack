from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.entities import (
    FinancialGoal,
    GoalContribution,
    GoalStatus,
    normalize_event_datetime,
    normalize_money,
    require_id,
)
from app.domain.exceptions import (
    ContributionNotFoundError,
    GoalNotFoundError,
    InvalidGoalStateError,
)
from app.use_cases.interfaces.goal_repository import GoalRepositoryInterface


class ManageGoalsUseCase:
    """Manage savings targets and atomically maintain contribution totals."""

    def __init__(self, repository: GoalRepositoryInterface) -> None:
        self.repository = repository

    def create(
        self,
        *,
        user_id: int,
        name: str,
        description: str | None,
        target_amount: Decimal,
        currency: str,
        target_date: date | None,
    ) -> FinancialGoal:
        return self.repository.create(
            FinancialGoal(
                user_id=user_id,
                name=name,
                description=description,
                target_amount=normalize_money(target_amount),
                currency=currency,
                target_date=target_date,
            )
        )

    def get(self, goal_id: int, user_id: int, *, for_update: bool = False) -> FinancialGoal:
        goal = self.repository.get_by_id_for_user(goal_id, user_id, for_update=for_update)
        if goal is None:
            raise GoalNotFoundError(goal_id)
        return goal

    def list_goals(
        self,
        user_id: int,
        status: GoalStatus | None,
        limit: int,
        offset: int,
    ) -> list[FinancialGoal]:
        return self.repository.list_by_user(user_id, status, limit, offset)

    def update(
        self,
        *,
        goal_id: int,
        user_id: int,
        name: str | None,
        description: str | None,
        target_amount: Decimal | None,
        target_date: date | None,
        status: GoalStatus | None,
        name_was_set: bool,
        description_was_set: bool,
        target_date_was_set: bool,
    ) -> FinancialGoal:
        goal = self.get(goal_id, user_id, for_update=True)
        if name_was_set and name is not None:
            goal.name = name
        if description_was_set:
            goal.description = description
        if target_date_was_set:
            goal.target_date = target_date
        if target_amount is not None:
            normalized_target = normalize_money(target_amount)
            if normalized_target < goal.current_amount:
                raise InvalidGoalStateError(
                    "Target amount cannot be lower than the current saved amount"
                )
            goal.target_amount = normalized_target
            if goal.status == GoalStatus.COMPLETED and goal.current_amount < normalized_target:
                goal.status = GoalStatus.ACTIVE
                goal.completed_at = None
            elif goal.current_amount == normalized_target and goal.status == GoalStatus.ACTIVE:
                goal.status = GoalStatus.COMPLETED
                goal.completed_at = datetime.now(UTC)
        if status == GoalStatus.CANCELLED:
            if goal.status == GoalStatus.COMPLETED:
                raise InvalidGoalStateError("A completed goal cannot be cancelled")
            goal.status = GoalStatus.CANCELLED
            goal.completed_at = None
        elif status == GoalStatus.ACTIVE:
            if goal.current_amount >= goal.target_amount:
                raise InvalidGoalStateError(
                    "A completed goal cannot be reopened without a new target"
                )
            goal.status = GoalStatus.ACTIVE
            goal.completed_at = None
        return self.repository.update(goal)

    def delete(self, goal_id: int, user_id: int) -> None:
        goal = self.get(goal_id, user_id)
        self.repository.delete(require_id(goal.id))

    def contribute(
        self,
        *,
        goal_id: int,
        user_id: int,
        amount: Decimal,
        note: str | None,
        contributed_at: datetime | None,
        timezone_name: str,
    ) -> tuple[FinancialGoal, GoalContribution]:
        goal = self.get(goal_id, user_id, for_update=True)
        if goal.status != GoalStatus.ACTIVE:
            raise InvalidGoalStateError("Contributions are only allowed for active goals")
        normalized_amount = normalize_money(amount)
        if normalized_amount > goal.remaining_amount:
            raise InvalidGoalStateError("Contribution exceeds the remaining goal amount")

        contribution = self.repository.create_contribution(
            GoalContribution(
                goal_id=require_id(goal.id),
                amount=normalized_amount,
                note=note,
                contributed_at=normalize_event_datetime(contributed_at, timezone_name),
            )
        )
        goal.current_amount = normalize_money(goal.current_amount + normalized_amount)
        if goal.current_amount == goal.target_amount:
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = datetime.now(UTC)
        return self.repository.update(goal), contribution

    def list_contributions(self, goal_id: int, user_id: int) -> list[GoalContribution]:
        goal = self.get(goal_id, user_id)
        return self.repository.list_contributions(require_id(goal.id))

    def delete_contribution(
        self, goal_id: int, contribution_id: int, user_id: int
    ) -> FinancialGoal:
        goal = self.get(goal_id, user_id, for_update=True)
        contribution = self.repository.get_contribution_for_goal(
            contribution_id, require_id(goal.id)
        )
        if contribution is None:
            raise ContributionNotFoundError(contribution_id)
        goal.current_amount = normalize_money(goal.current_amount - contribution.amount)
        if goal.status == GoalStatus.COMPLETED:
            goal.status = GoalStatus.ACTIVE
            goal.completed_at = None
        self.repository.delete_contribution(contribution_id)
        return self.repository.update(goal)
