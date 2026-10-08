"""Create isolated portfolio demo sessions with realistic financial data."""

import secrets
from calendar import monthrange
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    BudgetModel,
    CategorizationRuleModel,
    CategoryModel,
    FinancialGoalModel,
    RecurringTransactionModel,
    TransactionModel,
    UserModel,
    WalletModel,
)


def _shift_month(reference: date, months: int, day: int) -> date:
    month_index = reference.year * 12 + reference.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(day, monthrange(year, month)[1]))


class DemoService:
    def __init__(
        self,
        session: Session,
        hash_password_fn: Callable[[str], str],
        create_token_fn: Callable[[int, str], str],
    ) -> None:
        self.session = session
        self.hash_password_fn = hash_password_fn
        self.create_token_fn = create_token_fn

    def create_session(self) -> str:
        cutoff = datetime.now(UTC) - timedelta(days=2)
        stale_users = self.session.query(UserModel).filter(
            UserModel.is_demo.is_(True), UserModel.created_at < cutoff
        ).all()
        for stale_user in stale_users:
            self.session.delete(stale_user)
        self.session.flush()

        suffix = secrets.token_hex(6)
        email = f"demo-{suffix}@spendly.app"
        user = UserModel(
            email=email,
            hashed_password=self.hash_password_fn(secrets.token_urlsafe(24)),
            full_name="Visitante Demo",
            base_currency="BRL",
            timezone="America/Sao_Paulo",
            is_demo=True,
            onboarding_completed=True,
        )
        self.session.add(user)
        self.session.flush()

        category_names = [
            "Moradia",
            "Alimentação",
            "Transporte",
            "Lazer",
            "Saúde",
            "Assinaturas",
            "Educação",
        ]
        categories: dict[str, CategoryModel] = {}
        for name in category_names:
            model = CategoryModel(user_id=user.id, name=name)
            self.session.add(model)
            categories[name] = model
        self.session.flush()

        wallet = WalletModel(
            user_id=user.id,
            name="Conta principal",
            balance=Decimal("12840.20"),
            currency="BRL",
        )
        card = WalletModel(
            user_id=user.id,
            name="Cartão de crédito",
            balance=Decimal("-684.70"),
            currency="BRL",
        )
        self.session.add_all([wallet, card])
        self.session.flush()

        today = datetime.now(UTC).date()
        expense_templates = [
            ("Aluguel Residencial", "2600.00", "Moradia", 5),
            ("Supermercado Verde", "786.40", "Alimentação", 9),
            ("Mobilidade Urbana", "438.90", "Transporte", 12),
            ("Academia Movimento", "119.90", "Saúde", 15),
            ("Netflix", "55.90", "Assinaturas", 18),
            ("Spotify", "21.90", "Assinaturas", 19),
            ("Cinema e jantar", "248.00", "Lazer", 23),
            ("Cursos online", "189.00", "Educação", 25),
        ]
        for month_offset in range(-5, 1):
            salary_date = _shift_month(today, month_offset, 1)
            self.session.add(
                TransactionModel(
                    wallet_id=wallet.id,
                    amount=Decimal("8500.00"),
                    transaction_type="INCOME",
                    description="Salário Tech Company",
                    occurred_at=datetime.combine(salary_date, datetime.min.time(), tzinfo=UTC),
                    currency="BRL",
                    base_currency="BRL",
                    exchange_rate=Decimal("1"),
                    base_amount=Decimal("8500.00"),
                    rate_date=salary_date,
                    source="MANUAL",
                )
            )
            for index, (description, raw_amount, category_name, day) in enumerate(expense_templates):
                event_date = _shift_month(today, month_offset, day)
                variation = Decimal(str(((month_offset + index) % 3) * 3))
                amount = Decimal(raw_amount) + variation
                target_wallet = card if category_name in {"Lazer", "Assinaturas"} else wallet
                self.session.add(
                    TransactionModel(
                        wallet_id=target_wallet.id,
                        category_id=categories[category_name].id,
                        amount=amount,
                        transaction_type="EXPENSE",
                        description=description,
                        occurred_at=datetime.combine(event_date, datetime.min.time(), tzinfo=UTC),
                        currency="BRL",
                        base_currency="BRL",
                        exchange_rate=Decimal("1"),
                        base_amount=amount,
                        rate_date=event_date,
                        source="MANUAL",
                    )
                )

        self.session.add_all(
            [
                BudgetModel(
                    user_id=user.id,
                    limit_amount=Decimal("5200.00"),
                    period="MONTHLY",
                    alert_threshold=80,
                ),
                BudgetModel(
                    user_id=user.id,
                    category_id=categories["Alimentação"].id,
                    limit_amount=Decimal("1100.00"),
                    period="MONTHLY",
                    alert_threshold=75,
                ),
                FinancialGoalModel(
                    user_id=user.id,
                    name="Viagem para a Europa",
                    description="Meta para passagens, hospedagem e passeios",
                    target_amount=Decimal("18000.00"),
                    current_amount=Decimal("7800.00"),
                    currency="BRL",
                    target_date=today + timedelta(days=240),
                    status="ACTIVE",
                ),
                RecurringTransactionModel(
                    user_id=user.id,
                    wallet_id=wallet.id,
                    amount=Decimal("8500.00"),
                    transaction_type="INCOME",
                    description="Salário",
                    frequency="MONTHLY",
                    interval_count=1,
                    start_date=_shift_month(today, 1, 1),
                    next_run_date=_shift_month(today, 1, 1),
                    is_active=True,
                ),
                RecurringTransactionModel(
                    user_id=user.id,
                    wallet_id=wallet.id,
                    category_id=categories["Moradia"].id,
                    amount=Decimal("2600.00"),
                    transaction_type="EXPENSE",
                    description="Aluguel",
                    frequency="MONTHLY",
                    interval_count=1,
                    start_date=_shift_month(today, 1, 5),
                    next_run_date=_shift_month(today, 1, 5),
                    is_active=True,
                ),
                CategorizationRuleModel(
                    user_id=user.id,
                    category_id=categories["Assinaturas"].id,
                    name="Streaming",
                    pattern="Netflix|Spotify",
                    match_type="REGEX",
                    priority=10,
                    applies_to_imports=True,
                ),
                CategorizationRuleModel(
                    user_id=user.id,
                    category_id=categories["Alimentação"].id,
                    name="Supermercados",
                    pattern="supermercado",
                    match_type="CONTAINS",
                    priority=20,
                    applies_to_imports=True,
                ),
            ]
        )
        self.session.flush()
        return self.create_token_fn(user.id, email)
