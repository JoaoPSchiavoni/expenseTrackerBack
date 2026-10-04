from abc import ABC, abstractmethod

from app.domain.entities import FinancialGoal, GoalContribution, GoalStatus


class GoalRepositoryInterface(ABC):
    @abstractmethod
    def create(self, goal: FinancialGoal) -> FinancialGoal: ...

    @abstractmethod
    def get_by_id_for_user(
        self, goal_id: int, user_id: int, *, for_update: bool = False
    ) -> FinancialGoal | None: ...

    @abstractmethod
    def list_by_user(
        self,
        user_id: int,
        status: GoalStatus | None,
        limit: int,
        offset: int,
    ) -> list[FinancialGoal]: ...

    @abstractmethod
    def update(self, goal: FinancialGoal) -> FinancialGoal: ...

    @abstractmethod
    def delete(self, goal_id: int) -> None: ...

    @abstractmethod
    def create_contribution(self, contribution: GoalContribution) -> GoalContribution: ...

    @abstractmethod
    def get_contribution_for_goal(
        self, contribution_id: int, goal_id: int
    ) -> GoalContribution | None: ...

    @abstractmethod
    def list_contributions(self, goal_id: int) -> list[GoalContribution]: ...

    @abstractmethod
    def delete_contribution(self, contribution_id: int) -> None: ...
