from sqlalchemy.orm import Session

from app.domain.entities import Budget
from app.infrastructure.database.models import BudgetModel
from app.use_cases.interfaces.budget_repository import BudgetRepositoryInterface


class SqlBudgetRepository(BudgetRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _to_entity(model: BudgetModel) -> Budget:
        return Budget(
            id=model.id,
            user_id=model.user_id,
            category_id=model.category_id,
            limit_amount=model.limit_amount,
            period=model.period,
            created_at=model.created_at,
        )

    def create(self, budget: Budget) -> Budget:
        model = BudgetModel(
            user_id=budget.user_id,
            category_id=budget.category_id,
            limit_amount=budget.limit_amount,
            period=budget.period,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def get_by_id_for_user(self, budget_id: int, user_id: int) -> Budget | None:
        model = (
            self.session.query(BudgetModel)
            .filter(BudgetModel.id == budget_id, BudgetModel.user_id == user_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def get_by_scope(self, user_id: int, category_id: int, period: str) -> Budget | None:
        model = (
            self.session.query(BudgetModel)
            .filter(
                BudgetModel.user_id == user_id,
                BudgetModel.category_id == category_id,
                BudgetModel.period == period,
            )
            .first()
        )
        return self._to_entity(model) if model else None

    def list_by_user(self, user_id: int) -> list[Budget]:
        models = (
            self.session.query(BudgetModel)
            .filter(BudgetModel.user_id == user_id)
            .order_by(BudgetModel.created_at.desc())
            .all()
        )
        return [self._to_entity(model) for model in models]

    def update(self, budget: Budget) -> Budget:
        model = self.session.get(BudgetModel, budget.id)
        if model is None:
            raise ValueError("Budget not found")
        model.limit_amount = budget.limit_amount
        model.period = budget.period
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def delete(self, budget_id: int) -> None:
        model = self.session.get(BudgetModel, budget_id)
        if model is None:
            raise ValueError("Budget not found")
        self.session.delete(model)
        self.session.flush()
