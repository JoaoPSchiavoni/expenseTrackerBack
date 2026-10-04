from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.infrastructure.database.models import CategoryModel, TransactionModel, WalletModel


class SqlReportRepository:
    """Read-optimized financial queries scoped to one user."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def monthly_totals(
        self, user_id: int, start: datetime, end: datetime
    ) -> tuple[Decimal, Decimal]:
        income, expense = (
            self.session.query(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                TransactionModel.transaction_type == "INCOME",
                                TransactionModel.base_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                TransactionModel.transaction_type == "EXPENSE",
                                TransactionModel.base_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(
                WalletModel.user_id == user_id,
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
            .one()
        )
        return Decimal(income), Decimal(expense)

    def category_expenses(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[tuple[int | None, str, Decimal]]:
        rows = (
            self.session.query(
                TransactionModel.category_id,
                func.coalesce(CategoryModel.name, "Uncategorized"),
                func.sum(TransactionModel.base_amount),
            )
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .outerjoin(CategoryModel, TransactionModel.category_id == CategoryModel.id)
            .filter(
                WalletModel.user_id == user_id,
                TransactionModel.transaction_type == "EXPENSE",
                TransactionModel.occurred_at >= start,
                TransactionModel.occurred_at < end,
            )
            .group_by(TransactionModel.category_id, CategoryModel.name)
            .order_by(func.sum(TransactionModel.base_amount).desc())
            .all()
        )
        return [(category_id, name, Decimal(total)) for category_id, name, total in rows]
