from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.entities import BudgetUsageStatus, TransactionType, normalize_money
from app.interfaces.repositories.sql_report_repository import SqlReportRepository
from app.use_cases.budget_alerts import BudgetAlertService, BudgetUsage
from app.use_cases.exchange_rates import ExchangeRateService
from app.use_cases.interfaces.budget_repository import BudgetRepositoryInterface
from app.use_cases.interfaces.dashboard_repository import (
    DashboardRecentTransaction,
    DashboardRepositoryInterface,
)
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface


@dataclass(frozen=True)
class DashboardOverview:
    month: str
    currency: str
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    savings_rate: Decimal
    transaction_count: int
    net_worth: Decimal
    active_wallets: int
    active_goals: int
    completed_goals: int
    budgets_warning: int
    budgets_exceeded: int
    unread_alerts: int
    generated_at: datetime


@dataclass(frozen=True)
class CashFlowPoint:
    month: str
    income: Decimal
    expense: Decimal
    net: Decimal


@dataclass(frozen=True)
class CategorySpending:
    category_id: int | None
    category_name: str
    amount: Decimal
    percentage: Decimal


class DashboardService:
    """Compose chart-ready financial projections in the user's base currency."""

    def __init__(
        self,
        dashboard_repository: DashboardRepositoryInterface,
        report_repository: SqlReportRepository,
        wallet_repository: WalletRepositoryInterface,
        budget_repository: BudgetRepositoryInterface,
        budget_alert_service: BudgetAlertService,
        exchange_rate_service: ExchangeRateService,
    ) -> None:
        self.dashboard_repository = dashboard_repository
        self.report_repository = report_repository
        self.wallet_repository = wallet_repository
        self.budget_repository = budget_repository
        self.budget_alert_service = budget_alert_service
        self.exchange_rate_service = exchange_rate_service

    @staticmethod
    def _parse_month(value: str, timezone_name: str) -> tuple[datetime, datetime]:
        try:
            year_text, month_text = value.split("-", maxsplit=1)
            year, month = int(year_text), int(month_text)
            timezone = ZoneInfo(timezone_name)
            start = datetime(year, month, 1, tzinfo=timezone)
            if month == 12:
                end = datetime(year + 1, 1, 1, tzinfo=timezone)
            else:
                end = datetime(year, month + 1, 1, tzinfo=timezone)
            return start.astimezone(UTC), end.astimezone(UTC)
        except (TypeError, ValueError) as exc:
            raise ValueError("Month must use YYYY-MM format") from exc

    @staticmethod
    def current_month(timezone_name: str) -> str:
        return datetime.now(UTC).astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m")

    @staticmethod
    def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
        absolute = year * 12 + month - 1 + offset
        return absolute // 12, absolute % 12 + 1

    def _net_worth(
        self, user_id: int, base_currency: str, on_date: date
    ) -> tuple[Decimal, int]:
        wallets = self.wallet_repository.list_by_user(user_id)
        total = Decimal("0.00")
        for wallet in wallets:
            if wallet.balance == 0:
                continue
            quote = self.exchange_rate_service.quote(
                wallet.balance, wallet.currency, base_currency, on_date
            )
            total += quote.converted_amount
        return normalize_money(total), len(wallets)

    def _budget_usages(
        self,
        user_id: int,
        reference: datetime,
        timezone_name: str,
        currency: str,
    ) -> list[BudgetUsage]:
        return [
            self.budget_alert_service.get_usage(
                budget, reference, timezone_name, currency
            )
            for budget in self.budget_repository.list_by_user(user_id)
        ]

    def overview(
        self,
        *,
        user_id: int,
        month: str,
        timezone_name: str,
        currency: str,
    ) -> DashboardOverview:
        start, end = self._parse_month(month, timezone_name)
        income, expense = self.report_repository.monthly_totals(user_id, start, end)
        income = normalize_money(income)
        expense = normalize_money(expense)
        net = normalize_money(income - expense)
        savings_rate = (
            normalize_money(net * 100 / income) if income > 0 else Decimal("0.00")
        )
        now = datetime.now(UTC)
        if now < start:
            reference = start
        elif now >= end:
            reference = end - timedelta(microseconds=1)
        else:
            reference = now
        net_worth, wallet_count = self._net_worth(
            user_id,
            currency,
            datetime.now(UTC).astimezone(ZoneInfo(timezone_name)).date(),
        )
        budget_usages = self._budget_usages(
            user_id, reference, timezone_name, currency
        )
        active_goals, completed_goals = self.dashboard_repository.goal_counts(user_id)
        return DashboardOverview(
            month=month,
            currency=currency,
            total_income=income,
            total_expense=expense,
            net_savings=net,
            savings_rate=savings_rate,
            transaction_count=self.dashboard_repository.transaction_count(user_id, start, end),
            net_worth=net_worth,
            active_wallets=wallet_count,
            active_goals=active_goals,
            completed_goals=completed_goals,
            budgets_warning=sum(
                item.status == BudgetUsageStatus.WARNING for item in budget_usages
            ),
            budgets_exceeded=sum(
                item.status == BudgetUsageStatus.EXCEEDED for item in budget_usages
            ),
            unread_alerts=self.budget_alert_service.unread_count(user_id),
            generated_at=datetime.now(UTC),
        )

    def cash_flow(
        self,
        *,
        user_id: int,
        months: int,
        timezone_name: str,
    ) -> list[CashFlowPoint]:
        timezone = ZoneInfo(timezone_name)
        now = datetime.now(UTC).astimezone(timezone)
        first_year, first_month = self._shift_month(now.year, now.month, -(months - 1))
        first_label = f"{first_year:04d}-{first_month:02d}"
        _, range_end = self._parse_month(f"{now.year:04d}-{now.month:02d}", timezone_name)
        range_start, _ = self._parse_month(first_label, timezone_name)
        totals = {
            f"{self._shift_month(first_year, first_month, offset)[0]:04d}-"
            f"{self._shift_month(first_year, first_month, offset)[1]:02d}": [
                Decimal("0.00"),
                Decimal("0.00"),
            ]
            for offset in range(months)
        }
        for record in self.dashboard_repository.cash_flow_records(
            user_id, range_start, range_end
        ):
            occurred_at = record.occurred_at
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            label = occurred_at.astimezone(timezone).strftime("%Y-%m")
            index = 0 if record.transaction_type == TransactionType.INCOME else 1
            totals[label][index] += record.base_amount
        return [
            CashFlowPoint(
                month=label,
                income=normalize_money(values[0]),
                expense=normalize_money(values[1]),
                net=normalize_money(values[0] - values[1]),
            )
            for label, values in totals.items()
        ]

    def spending_by_category(
        self,
        *,
        user_id: int,
        month: str,
        timezone_name: str,
        limit: int,
    ) -> list[CategorySpending]:
        start, end = self._parse_month(month, timezone_name)
        all_rows = self.report_repository.category_expenses(user_id, start, end)
        rows = all_rows[:limit]
        total = sum((amount for _, _, amount in all_rows), Decimal("0.00"))
        return [
            CategorySpending(
                category_id=category_id,
                category_name=name,
                amount=normalize_money(amount),
                percentage=(
                    normalize_money(amount * 100 / total) if total > 0 else Decimal("0.00")
                ),
            )
            for category_id, name, amount in rows
        ]

    def recent_transactions(
        self, user_id: int, limit: int
    ) -> list[DashboardRecentTransaction]:
        return self.dashboard_repository.recent_transactions(user_id, limit)
