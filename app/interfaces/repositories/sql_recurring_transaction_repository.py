from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.domain.entities import (
    RecurrenceFrequency,
    RecurringTransaction,
    TransactionType,
)
from app.infrastructure.database.models import RecurringTransactionModel
from app.use_cases.interfaces.recurring_transaction_repository import (
    RecurringTransactionRepositoryInterface,
)


class SqlRecurringTransactionRepository(RecurringTransactionRepositoryInterface):
    """SQLAlchemy adapter for recurring transaction schedules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _to_entity(model: RecurringTransactionModel) -> RecurringTransaction:
        return RecurringTransaction(
            id=model.id,
            user_id=model.user_id,
            wallet_id=model.wallet_id,
            category_id=model.category_id,
            amount=model.amount,
            transaction_type=TransactionType(model.transaction_type),
            description=model.description,
            frequency=RecurrenceFrequency(model.frequency),
            interval_count=model.interval_count,
            start_date=model.start_date,
            next_run_date=model.next_run_date,
            end_date=model.end_date,
            is_active=model.is_active,
            last_generated_at=model.last_generated_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(self, recurring: RecurringTransaction) -> RecurringTransaction:
        model = RecurringTransactionModel(
            user_id=recurring.user_id,
            wallet_id=recurring.wallet_id,
            category_id=recurring.category_id,
            amount=recurring.amount,
            transaction_type=recurring.transaction_type.value,
            description=recurring.description,
            frequency=recurring.frequency.value,
            interval_count=recurring.interval_count,
            start_date=recurring.start_date,
            next_run_date=recurring.next_run_date,
            end_date=recurring.end_date,
            is_active=recurring.is_active,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def get_by_id_for_user(
        self, recurring_id: int, user_id: int, *, for_update: bool = False
    ) -> RecurringTransaction | None:
        query = self.session.query(RecurringTransactionModel).filter(
            RecurringTransactionModel.id == recurring_id,
            RecurringTransactionModel.user_id == user_id,
        )
        if for_update:
            query = query.with_for_update()
        model = query.first()
        return self._to_entity(model) if model else None

    def list_by_user(self, user_id: int) -> list[RecurringTransaction]:
        models = (
            self.session.query(RecurringTransactionModel)
            .filter(RecurringTransactionModel.user_id == user_id)
            .order_by(
                RecurringTransactionModel.is_active.desc(),
                RecurringTransactionModel.next_run_date.asc(),
                RecurringTransactionModel.id.asc(),
            )
            .all()
        )
        return [self._to_entity(model) for model in models]

    def list_due(self, user_id: int, through_date: date) -> list[RecurringTransaction]:
        models = (
            self.session.query(RecurringTransactionModel)
            .filter(
                RecurringTransactionModel.user_id == user_id,
                RecurringTransactionModel.is_active.is_(True),
                RecurringTransactionModel.next_run_date <= through_date,
            )
            .order_by(RecurringTransactionModel.next_run_date.asc())
            .with_for_update()
            .all()
        )
        return [self._to_entity(model) for model in models]

    def update(self, recurring: RecurringTransaction) -> RecurringTransaction:
        model = self.session.get(RecurringTransactionModel, recurring.id)
        if model is None:
            raise ValueError("Recurring transaction not found")
        model.wallet_id = recurring.wallet_id
        model.category_id = recurring.category_id
        model.amount = recurring.amount
        model.transaction_type = recurring.transaction_type.value
        model.description = recurring.description
        model.frequency = recurring.frequency.value
        model.interval_count = recurring.interval_count
        model.start_date = recurring.start_date
        model.next_run_date = recurring.next_run_date
        model.end_date = recurring.end_date
        model.is_active = recurring.is_active
        model.last_generated_at = recurring.last_generated_at
        model.updated_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def delete(self, recurring_id: int) -> None:
        model = self.session.get(RecurringTransactionModel, recurring_id)
        if model is None:
            raise ValueError("Recurring transaction not found")
        self.session.delete(model)
        self.session.flush()
