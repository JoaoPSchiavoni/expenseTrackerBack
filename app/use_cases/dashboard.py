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
from app.use_cases.interfaces.recurring_transaction_repository import (
    RecurringTransactionRepositoryInterface,
)
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface
from app.use_cases.recurring_transactions import next_occurrence


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


@dataclass(frozen=True)
class BalanceProjectionPoint:
    month: str
    projected_income: Decimal
    projected_expense: Decimal
    net_change: Decimal
    projected_balance: Decimal


@dataclass(frozen=True)
class PeriodComparison:
    current_period: str
    previous_period: str
    current_income: Decimal
    previous_income: Decimal
    income_change_percentage: Decimal | None
    current_expense: Decimal
    previous_expense: Decimal
    expense_change_percentage: Decimal | None
    current_net: Decimal
    previous_net: Decimal
    net_change: Decimal


@dataclass(frozen=True)
class FinancialHealth:
    score: int
    status: str
    summary: str
    savings_rate: Decimal
    reserve_months: Decimal
    budgets_on_track: int
    budgets_at_risk: int
    active_goals: int


@dataclass(frozen=True)
class FinancialRecommendation:
    priority: str
    category: str
    title: str
    message: str


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
        recurring_transaction_repository: RecurringTransactionRepositoryInterface,
    ) -> None:
        self.dashboard_repository = dashboard_repository
        self.report_repository = report_repository
        self.wallet_repository = wallet_repository
        self.budget_repository = budget_repository
        self.budget_alert_service = budget_alert_service
        self.exchange_rate_service = exchange_rate_service
        self.recurring_transaction_repository = recurring_transaction_repository

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

    def _net_worth(self, user_id: int, base_currency: str, on_date: date) -> tuple[Decimal, int]:
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
            self.budget_alert_service.get_usage(budget, reference, timezone_name, currency)
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
        savings_rate = normalize_money(net * 100 / income) if income > 0 else Decimal("0.00")
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
        budget_usages = self._budget_usages(user_id, reference, timezone_name, currency)
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
            budgets_warning=sum(item.status == BudgetUsageStatus.WARNING for item in budget_usages),
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
        for record in self.dashboard_repository.cash_flow_records(user_id, range_start, range_end):
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

    def recent_transactions(self, user_id: int, limit: int) -> list[DashboardRecentTransaction]:
        return self.dashboard_repository.recent_transactions(user_id, limit)

    @staticmethod
    def _percentage_change(current: Decimal, previous: Decimal) -> Decimal | None:
        if previous == 0:
            return None
        return normalize_money((current - previous) * 100 / previous)

    def period_comparison(
        self,
        *,
        user_id: int,
        month: str,
        timezone_name: str,
    ) -> PeriodComparison:
        current_start, current_end = self._parse_month(month, timezone_name)
        year, month_number = (int(part) for part in month.split("-"))
        previous_year, previous_month = self._shift_month(year, month_number, -1)
        previous_label = f"{previous_year:04d}-{previous_month:02d}"
        previous_start, previous_end = self._parse_month(previous_label, timezone_name)
        current_income, current_expense = self.report_repository.monthly_totals(
            user_id, current_start, current_end
        )
        previous_income, previous_expense = self.report_repository.monthly_totals(
            user_id, previous_start, previous_end
        )
        current_income = normalize_money(current_income)
        current_expense = normalize_money(current_expense)
        previous_income = normalize_money(previous_income)
        previous_expense = normalize_money(previous_expense)
        current_net = normalize_money(current_income - current_expense)
        previous_net = normalize_money(previous_income - previous_expense)
        return PeriodComparison(
            current_period=month,
            previous_period=previous_label,
            current_income=current_income,
            previous_income=previous_income,
            income_change_percentage=self._percentage_change(current_income, previous_income),
            current_expense=current_expense,
            previous_expense=previous_expense,
            expense_change_percentage=self._percentage_change(current_expense, previous_expense),
            current_net=current_net,
            previous_net=previous_net,
            net_change=normalize_money(current_net - previous_net),
        )

    def balance_projection(
        self,
        *,
        user_id: int,
        months: int,
        timezone_name: str,
        currency: str,
    ) -> tuple[Decimal, list[BalanceProjectionPoint]]:
        timezone = ZoneInfo(timezone_name)
        today = datetime.now(UTC).astimezone(timezone).date()
        wallets = self.wallet_repository.list_by_user(user_id)
        wallets_by_id = {wallet.id: wallet for wallet in wallets}
        current_balance, _ = self._net_worth(user_id, currency, today)
        totals: dict[str, list[Decimal]] = {}
        for offset in range(months):
            year, month_number = self._shift_month(today.year, today.month, offset)
            totals[f"{year:04d}-{month_number:02d}"] = [
                Decimal("0.00"),
                Decimal("0.00"),
            ]
        last_year, last_month = self._shift_month(today.year, today.month, months - 1)
        horizon = (
            date(last_year + 1, 1, 1) - timedelta(days=1)
            if last_month == 12
            else date(last_year, last_month + 1, 1) - timedelta(days=1)
        )
        for recurring in self.recurring_transaction_repository.list_by_user(user_id):
            wallet = wallets_by_id.get(recurring.wallet_id)
            if not recurring.is_active or wallet is None:
                continue
            occurrence = recurring.next_run_date
            occurrences = 0
            while occurrence <= horizon and occurrences < 1000:
                if occurrence >= today and (
                    recurring.end_date is None or occurrence <= recurring.end_date
                ):
                    quote = self.exchange_rate_service.quote(
                        recurring.amount, wallet.currency, currency, occurrence
                    )
                    index = 0 if recurring.transaction_type == TransactionType.INCOME else 1
                    totals[occurrence.strftime("%Y-%m")][index] += quote.converted_amount
                occurrence = next_occurrence(
                    occurrence,
                    recurring.frequency,
                    recurring.interval_count,
                    recurring.start_date.day,
                )
                occurrences += 1
        running_balance = current_balance
        points: list[BalanceProjectionPoint] = []
        for label, values in totals.items():
            income = normalize_money(values[0])
            expense = normalize_money(values[1])
            net = normalize_money(income - expense)
            running_balance = normalize_money(running_balance + net)
            points.append(
                BalanceProjectionPoint(
                    month=label,
                    projected_income=income,
                    projected_expense=expense,
                    net_change=net,
                    projected_balance=running_balance,
                )
            )
        return current_balance, points

    def financial_health(
        self,
        *,
        user_id: int,
        month: str,
        timezone_name: str,
        currency: str,
    ) -> FinancialHealth:
        overview = self.overview(
            user_id=user_id,
            month=month,
            timezone_name=timezone_name,
            currency=currency,
        )
        start, end = self._parse_month(month, timezone_name)
        reference = min(datetime.now(UTC), end - timedelta(microseconds=1))
        if reference < start:
            reference = start
        usages = self._budget_usages(user_id, reference, timezone_name, currency)
        on_track = sum(item.status == BudgetUsageStatus.SAFE for item in usages)
        at_risk = len(usages) - on_track
        reserve_months = (
            normalize_money(overview.net_worth / overview.total_expense)
            if overview.total_expense > 0 and overview.net_worth > 0
            else Decimal("0.00")
        )
        savings_score = max(0, min(40, int(overview.savings_rate * Decimal("1.6"))))
        budget_score = round(25 * on_track / len(usages)) if usages else 15
        reserve_score = max(0, min(25, round(float(reserve_months) / 6 * 25)))
        goals_score = 10 if overview.completed_goals else (7 if overview.active_goals else 5)
        score = max(0, min(100, savings_score + budget_score + reserve_score + goals_score))
        if score >= 80:
            status, summary = "HEALTHY", "Sua vida financeira está saudável e consistente."
        elif score >= 60:
            status, summary = "STABLE", "Você está no caminho certo, com alguns ajustes possíveis."
        elif score >= 40:
            status, summary = "ATTENTION", "Alguns indicadores financeiros precisam de atenção."
        else:
            status, summary = "CRITICAL", "Priorize o controle de gastos e a criação de reserva."
        return FinancialHealth(
            score=score,
            status=status,
            summary=summary,
            savings_rate=overview.savings_rate,
            reserve_months=reserve_months,
            budgets_on_track=on_track,
            budgets_at_risk=at_risk,
            active_goals=overview.active_goals,
        )

    def recommendations(
        self,
        *,
        user_id: int,
        month: str,
        timezone_name: str,
        currency: str,
    ) -> list[FinancialRecommendation]:
        health = self.financial_health(
            user_id=user_id,
            month=month,
            timezone_name=timezone_name,
            currency=currency,
        )
        comparison = self.period_comparison(
            user_id=user_id, month=month, timezone_name=timezone_name
        )
        items: list[FinancialRecommendation] = []
        if health.savings_rate < 10:
            items.append(
                FinancialRecommendation(
                    priority="HIGH",
                    category="SAVINGS",
                    title="Aumente sua margem mensal",
                    message="Busque reservar ao menos 10% da renda antes dos gastos variáveis.",
                )
            )
        if health.budgets_at_risk:
            items.append(
                FinancialRecommendation(
                    priority="HIGH",
                    category="BUDGET",
                    title="Revise os orçamentos em risco",
                    message=(
                        f"Você possui {health.budgets_at_risk} orçamento(s) em alerta ou excedido(s)."
                    ),
                )
            )
        if health.reserve_months < 3:
            items.append(
                FinancialRecommendation(
                    priority="MEDIUM",
                    category="RESERVE",
                    title="Construa uma reserva de emergência",
                    message="Uma reserva equivalente a 3–6 meses de despesas reduz imprevistos.",
                )
            )
        if (
            comparison.expense_change_percentage is not None
            and comparison.expense_change_percentage > 10
        ):
            items.append(
                FinancialRecommendation(
                    priority="MEDIUM",
                    category="SPENDING",
                    title="Despesas cresceram neste mês",
                    message=(
                        "Seus gastos subiram "
                        f"{comparison.expense_change_percentage}% em relação ao mês anterior."
                    ),
                )
            )
        if health.active_goals == 0:
            items.append(
                FinancialRecommendation(
                    priority="LOW",
                    category="GOALS",
                    title="Defina uma meta financeira",
                    message="Transforme seu próximo objetivo em uma meta acompanhável no app.",
                )
            )
        if not items:
            items.append(
                FinancialRecommendation(
                    priority="LOW",
                    category="MAINTENANCE",
                    title="Continue assim",
                    message="Seus principais indicadores estão equilibrados. Mantenha a rotina.",
                )
            )
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        return sorted(items, key=lambda item: priority_order[item.priority])[:4]
