from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.entities import TransactionSource, TransactionType
from app.infrastructure.database.models import (
    CategoryModel,
    FinancialGoalModel,
    TransactionModel,
    WalletModel,
)
from app.use_cases.interfaces.dashboard_repository import (
    DashboardCashFlowRecord,
    DashboardRecentTransaction,
    DashboardRepositoryInterface,
)


class SqlDashboardRepository(DashboardRepositoryInterface):
    """Read-optimized projections for dashboard widgets."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def transaction_count(self, user_id: int, start: datetime, end: datetime) -> int:
        return (
            self.session.query(func.count(TransactionModel.id))
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(
                WalletModel.user_id == user_id,
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
            .scalar()
            or 0
        )

    def cash_flow_records(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[DashboardCashFlowRecord]:
        rows = (
            self.session.query(
                TransactionModel.occurred_at,
                TransactionModel.transaction_type,
                TransactionModel.base_amount,
            )
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(
                WalletModel.user_id == user_id,
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
            .all()
        )
        return [
            DashboardCashFlowRecord(
                occurred_at=occurred_at,
                transaction_type=TransactionType(transaction_type),
                base_amount=base_amount,
            )
            for occurred_at, transaction_type, base_amount in rows
        ]

    def recent_transactions(self, user_id: int, limit: int) -> list[DashboardRecentTransaction]:
        rows = (
            self.session.query(TransactionModel, WalletModel.name, CategoryModel.name)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .outerjoin(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .filter(WalletModel.user_id == user_id)
            .order_by(TransactionModel.occurred_at.desc(), TransactionModel.id.desc())
            .limit(limit)
            .all()
        )
        return [
            DashboardRecentTransaction(
                id=transaction.id,
                wallet_id=transaction.wallet_id,
                wallet_name=wallet_name,
                category_id=transaction.category_id,
                category_name=category_name,
                amount=transaction.amount,
                transaction_type=TransactionType(transaction.transaction_type),
                description=transaction.description,
                occurred_at=transaction.occurred_at,
                currency=transaction.currency,
                base_amount=transaction.base_amount,
                source=TransactionSource(transaction.source),
            )
            for transaction, wallet_name, category_name in rows
        ]

    def goal_counts(self, user_id: int) -> tuple[int, int]:
        rows = (
            self.session.query(FinancialGoalModel.status, func.count(FinancialGoalModel.id))
            .filter(FinancialGoalModel.user_id == user_id)
            .group_by(FinancialGoalModel.status)
            .all()
        )
        counts = {status: count for status, count in rows}
        return counts.get("ACTIVE", 0), counts.get("COMPLETED", 0)
