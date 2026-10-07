from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.entities import BudgetAlert, BudgetAlertType
from app.infrastructure.database.models import (
    BudgetAlertModel,
    TransactionModel,
    WalletModel,
)
from app.use_cases.interfaces.budget_alert_repository import BudgetAlertRepositoryInterface


class SqlBudgetAlertRepository(BudgetAlertRepositoryInterface):
    """Persistence and aggregate queries used by the budget alert engine."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _to_entity(model: BudgetAlertModel) -> BudgetAlert:
        return BudgetAlert(
            id=model.id,
            user_id=model.user_id,
            budget_id=model.budget_id,
            category_id=model.category_id,
            alert_type=BudgetAlertType(model.alert_type),
            period_start=model.period_start,
            period_end=model.period_end,
            limit_amount=model.limit_amount,
            spent_amount=model.spent_amount,
            usage_percentage=model.usage_percentage,
            currency=model.currency,
            read_at=model.read_at,
            resolved_at=model.resolved_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def expense_total(
        self,
        user_id: int,
        category_id: int | None,
        start: datetime,
        end: datetime,
    ) -> Decimal:
        query = (
            self.session.query(func.coalesce(func.sum(TransactionModel.base_amount), 0))
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(
                WalletModel.user_id == user_id,
                TransactionModel.transaction_type == "EXPENSE",
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
        )
        if category_id is not None:
            query = query.filter(TransactionModel.category_id == category_id)
        value = query.scalar()
        return Decimal(value or 0)

    def upsert(self, alert: BudgetAlert) -> BudgetAlert:
        model = (
            self.session.query(BudgetAlertModel)
            .filter(
                BudgetAlertModel.budget_id == alert.budget_id,
                BudgetAlertModel.period_start == alert.period_start,
                BudgetAlertModel.alert_type == alert.alert_type.value,
            )
            .with_for_update()
            .first()
        )
        now = datetime.now(UTC)
        if model is None:
            model = BudgetAlertModel(
                user_id=alert.user_id,
                budget_id=alert.budget_id,
                category_id=alert.category_id,
                alert_type=alert.alert_type.value,
                period_start=alert.period_start,
                period_end=alert.period_end,
                limit_amount=alert.limit_amount,
                spent_amount=alert.spent_amount,
                usage_percentage=alert.usage_percentage,
                currency=alert.currency,
            )
            self.session.add(model)
        else:
            if model.resolved_at is not None:
                model.read_at = None
            model.period_end = alert.period_end
            model.limit_amount = alert.limit_amount
            model.spent_amount = alert.spent_amount
            model.usage_percentage = alert.usage_percentage
            model.currency = alert.currency
            model.resolved_at = None
            model.updated_at = now
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def resolve_missing_levels(
        self, budget_id: int, period_start: date, active_types: set[str]
    ) -> None:
        query = self.session.query(BudgetAlertModel).filter(
            BudgetAlertModel.budget_id == budget_id,
            BudgetAlertModel.period_start == period_start,
            BudgetAlertModel.resolved_at.is_(None),
        )
        if active_types:
            query = query.filter(BudgetAlertModel.alert_type.notin_(active_types))
        now = datetime.now(UTC)
        for model in query.all():
            model.resolved_at = now
            model.updated_at = now
        self.session.flush()

    def resolve_all_for_budget(self, budget_id: int) -> None:
        now = datetime.now(UTC)
        models = (
            self.session.query(BudgetAlertModel)
            .filter(
                BudgetAlertModel.budget_id == budget_id,
                BudgetAlertModel.resolved_at.is_(None),
            )
            .all()
        )
        for model in models:
            model.resolved_at = now
            model.updated_at = now
        self.session.flush()

    def list_by_user(
        self,
        user_id: int,
        *,
        unread_only: bool,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> list[BudgetAlert]:
        query = self.session.query(BudgetAlertModel).filter(BudgetAlertModel.user_id == user_id)
        if unread_only:
            query = query.filter(BudgetAlertModel.read_at.is_(None))
        if active_only:
            query = query.filter(BudgetAlertModel.resolved_at.is_(None))
        models = (
            query.order_by(BudgetAlertModel.created_at.desc(), BudgetAlertModel.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_entity(model) for model in models]

    def get_by_id_for_user(self, alert_id: int, user_id: int) -> BudgetAlert | None:
        model = (
            self.session.query(BudgetAlertModel)
            .filter(BudgetAlertModel.id == alert_id, BudgetAlertModel.user_id == user_id)
            .first()
        )
        return self._to_entity(model) if model else None

    def mark_read(self, alert_id: int) -> BudgetAlert:
        model = self.session.get(BudgetAlertModel, alert_id)
        if model is None:
            raise ValueError("Budget alert not found")
        if model.read_at is None:
            model.read_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def mark_all_read(self, user_id: int) -> int:
        models = (
            self.session.query(BudgetAlertModel)
            .filter(
                BudgetAlertModel.user_id == user_id,
                BudgetAlertModel.read_at.is_(None),
                BudgetAlertModel.resolved_at.is_(None),
            )
            .all()
        )
        now = datetime.now(UTC)
        for model in models:
            model.read_at = now
        self.session.flush()
        return len(models)

    def unread_count(self, user_id: int) -> int:
        return (
            self.session.query(func.count(BudgetAlertModel.id))
            .filter(
                BudgetAlertModel.user_id == user_id,
                BudgetAlertModel.read_at.is_(None),
                BudgetAlertModel.resolved_at.is_(None),
            )
            .scalar()
            or 0
        )
