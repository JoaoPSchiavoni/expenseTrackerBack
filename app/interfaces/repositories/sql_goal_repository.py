from sqlalchemy.orm import Session

from app.domain.entities import FinancialGoal, GoalContribution, GoalStatus
from app.infrastructure.database.models import FinancialGoalModel, GoalContributionModel
from app.use_cases.interfaces.goal_repository import GoalRepositoryInterface


class SqlGoalRepository(GoalRepositoryInterface):
    """SQLAlchemy adapter for goals and their contribution history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _goal_to_entity(model: FinancialGoalModel) -> FinancialGoal:
        return FinancialGoal(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            description=model.description,
            target_amount=model.target_amount,
            current_amount=model.current_amount,
            currency=model.currency,
            target_date=model.target_date,
            status=GoalStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )

    @staticmethod
    def _contribution_to_entity(model: GoalContributionModel) -> GoalContribution:
        return GoalContribution(
            id=model.id,
            goal_id=model.goal_id,
            amount=model.amount,
            note=model.note,
            contributed_at=model.contributed_at,
            created_at=model.created_at,
        )

    def create(self, goal: FinancialGoal) -> FinancialGoal:
        model = FinancialGoalModel(
            user_id=goal.user_id,
            name=goal.name,
            description=goal.description,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            currency=goal.currency,
            target_date=goal.target_date,
            status=goal.status.value,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._goal_to_entity(model)

    def get_by_id_for_user(
        self, goal_id: int, user_id: int, *, for_update: bool = False
    ) -> FinancialGoal | None:
        query = self.session.query(FinancialGoalModel).filter(
            FinancialGoalModel.id == goal_id,
            FinancialGoalModel.user_id == user_id,
        )
        if for_update:
            query = query.with_for_update()
        model = query.first()
        return self._goal_to_entity(model) if model else None

    def list_by_user(
        self,
        user_id: int,
        status: GoalStatus | None,
        limit: int,
        offset: int,
    ) -> list[FinancialGoal]:
        query = self.session.query(FinancialGoalModel).filter(
            FinancialGoalModel.user_id == user_id
        )
        if status is not None:
            query = query.filter(FinancialGoalModel.status == status.value)
        models = (
            query.order_by(FinancialGoalModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._goal_to_entity(model) for model in models]

    def update(self, goal: FinancialGoal) -> FinancialGoal:
        model = self.session.get(FinancialGoalModel, goal.id)
        if model is None:
            raise ValueError("Financial goal not found")
        model.name = goal.name
        model.description = goal.description
        model.target_amount = goal.target_amount
        model.current_amount = goal.current_amount
        model.target_date = goal.target_date
        model.status = goal.status.value
        model.completed_at = goal.completed_at
        self.session.flush()
        self.session.refresh(model)
        return self._goal_to_entity(model)

    def delete(self, goal_id: int) -> None:
        model = self.session.get(FinancialGoalModel, goal_id)
        if model is None:
            raise ValueError("Financial goal not found")
        self.session.delete(model)
        self.session.flush()

    def create_contribution(self, contribution: GoalContribution) -> GoalContribution:
        model = GoalContributionModel(
            goal_id=contribution.goal_id,
            amount=contribution.amount,
            note=contribution.note,
            contributed_at=contribution.contributed_at,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._contribution_to_entity(model)

    def get_contribution_for_goal(
        self, contribution_id: int, goal_id: int
    ) -> GoalContribution | None:
        model = (
            self.session.query(GoalContributionModel)
            .filter(
                GoalContributionModel.id == contribution_id,
                GoalContributionModel.goal_id == goal_id,
            )
            .first()
        )
        return self._contribution_to_entity(model) if model else None

    def list_contributions(self, goal_id: int) -> list[GoalContribution]:
        models = (
            self.session.query(GoalContributionModel)
            .filter(GoalContributionModel.goal_id == goal_id)
            .order_by(
                GoalContributionModel.contributed_at.desc(),
                GoalContributionModel.id.desc(),
            )
            .all()
        )
        return [self._contribution_to_entity(model) for model in models]

    def delete_contribution(self, contribution_id: int) -> None:
        model = self.session.get(GoalContributionModel, contribution_id)
        if model is None:
            raise ValueError("Goal contribution not found")
        self.session.delete(model)
        self.session.flush()
