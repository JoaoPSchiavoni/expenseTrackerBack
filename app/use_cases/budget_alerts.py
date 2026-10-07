from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.entities import (
    Budget,
    BudgetAlert,
    BudgetAlertType,
    BudgetUsageStatus,
    Transaction,
    TransactionType,
    normalize_money,
    require_id,
)
from app.domain.exceptions import BudgetAlertNotFoundError
from app.use_cases.interfaces.budget_alert_repository import BudgetAlertRepositoryInterface
from app.use_cases.interfaces.budget_repository import BudgetRepositoryInterface


@dataclass(frozen=True)
class BudgetUsage:
    budget_id: int
    category_id: int | None
    period: str
    period_start: date
    period_end: date
    limit_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    usage_percentage: Decimal
    status: BudgetUsageStatus
    alert_threshold: int
    alerts_enabled: bool
    currency: str


class BudgetAlertService:
    """Calculate recurring budget usage and maintain deduplicated notifications."""

    def __init__(
        self,
        budget_repository: BudgetRepositoryInterface,
        alert_repository: BudgetAlertRepositoryInterface,
    ) -> None:
        self.budget_repository = budget_repository
        self.alert_repository = alert_repository

    @staticmethod
    def _period_bounds(
        period: str, reference: datetime, timezone_name: str
    ) -> tuple[date, date, datetime, datetime]:
        timezone = ZoneInfo(timezone_name)
        local_date = reference.astimezone(timezone).date()
        if period == "WEEKLY":
            start_date = local_date - timedelta(days=local_date.weekday())
            end_date = start_date + timedelta(days=7)
        else:
            start_date = local_date.replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)
        start = datetime.combine(start_date, time.min, tzinfo=timezone).astimezone(UTC)
        end = datetime.combine(end_date, time.min, tzinfo=timezone).astimezone(UTC)
        return start_date, end_date, start, end

    def get_usage(
        self,
        budget: Budget,
        reference: datetime,
        timezone_name: str,
        currency: str,
    ) -> BudgetUsage:
        start_date, end_date, start, end = self._period_bounds(
            budget.period, reference, timezone_name
        )
        spent = normalize_money(
            self.alert_repository.expense_total(budget.user_id, budget.category_id, start, end)
        )
        percentage = normalize_money(spent * 100 / budget.limit_amount)
        if percentage >= 100:
            usage_status = BudgetUsageStatus.EXCEEDED
        elif percentage >= budget.alert_threshold:
            usage_status = BudgetUsageStatus.WARNING
        else:
            usage_status = BudgetUsageStatus.SAFE
        return BudgetUsage(
            budget_id=require_id(budget.id),
            category_id=budget.category_id,
            period=budget.period,
            period_start=start_date,
            period_end=end_date,
            limit_amount=normalize_money(budget.limit_amount),
            spent_amount=spent,
            remaining_amount=normalize_money(max(Decimal("0.00"), budget.limit_amount - spent)),
            usage_percentage=percentage,
            status=usage_status,
            alert_threshold=budget.alert_threshold,
            alerts_enabled=budget.alerts_enabled,
            currency=currency,
        )

    def evaluate_budget(
        self,
        budget: Budget,
        reference: datetime,
        timezone_name: str,
        currency: str,
    ) -> BudgetUsage:
        usage = self.get_usage(budget, reference, timezone_name, currency)
        budget_id = require_id(budget.id)
        if not budget.alerts_enabled:
            self.alert_repository.resolve_all_for_budget(budget_id)
            return usage

        active_types: set[BudgetAlertType] = set()
        if usage.usage_percentage >= budget.alert_threshold:
            active_types.add(BudgetAlertType.WARNING)
        if usage.usage_percentage >= 100:
            active_types.add(BudgetAlertType.EXCEEDED)
        for alert_type in active_types:
            self.alert_repository.upsert(
                BudgetAlert(
                    user_id=budget.user_id,
                    budget_id=budget_id,
                    category_id=budget.category_id,
                    alert_type=alert_type,
                    period_start=usage.period_start,
                    period_end=usage.period_end,
                    limit_amount=usage.limit_amount,
                    spent_amount=usage.spent_amount,
                    usage_percentage=usage.usage_percentage,
                    currency=currency,
                )
            )
        self.alert_repository.resolve_missing_levels(
            budget_id,
            usage.period_start,
            {alert_type.value for alert_type in active_types},
        )
        return usage

    def evaluate_scope(
        self,
        *,
        user_id: int,
        category_id: int | None,
        reference: datetime,
        timezone_name: str,
        currency: str,
    ) -> None:
        budgets = self.budget_repository.list_by_category(user_id, None)
        if category_id is not None:
            budgets += self.budget_repository.list_by_category(user_id, category_id)
        for budget in budgets:
            self.evaluate_budget(budget, reference, timezone_name, currency)

    def evaluate_transaction(
        self, transaction: Transaction, user_id: int, timezone_name: str
    ) -> None:
        if transaction.transaction_type != TransactionType.EXPENSE:
            return
        self.evaluate_scope(
            user_id=user_id,
            category_id=transaction.category_id,
            reference=transaction.occurred_at,
            timezone_name=timezone_name,
            currency=transaction.base_currency,
        )

    def resolve_all_for_budget(self, budget_id: int) -> None:
        self.alert_repository.resolve_all_for_budget(budget_id)

    def list_alerts(
        self,
        user_id: int,
        *,
        unread_only: bool,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> list[BudgetAlert]:
        return self.alert_repository.list_by_user(
            user_id,
            unread_only=unread_only,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    def mark_read(self, alert_id: int, user_id: int) -> BudgetAlert:
        alert = self.alert_repository.get_by_id_for_user(alert_id, user_id)
        if alert is None:
            raise BudgetAlertNotFoundError(alert_id)
        return self.alert_repository.mark_read(require_id(alert.id))

    def mark_all_read(self, user_id: int) -> int:
        return self.alert_repository.mark_all_read(user_id)

    def unread_count(self, user_id: int) -> int:
        return self.alert_repository.unread_count(user_id)
