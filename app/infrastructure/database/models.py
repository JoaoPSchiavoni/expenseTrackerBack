"""Typed SQLAlchemy models for the PostgreSQL relational schema."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.connection import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_currency: Mapped[str] = mapped_column(
        String(3), default="BRL", server_default=text("'BRL'")
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="America/Sao_Paulo", server_default=text("'America/Sao_Paulo'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now()
    )

    wallets: Mapped[list["WalletModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    categories: Mapped[list["CategoryModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["BudgetModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    import_batches: Mapped[list["ImportBatchModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WalletModel(Base):
    __tablename__ = "wallets"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_wallets_balance_nonnegative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )
    currency: Mapped[str] = mapped_column(String(3), default="BRL", server_default=text("'BRL'"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now()
    )

    user: Mapped[UserModel] = relationship(back_populates="wallets")
    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
    import_batches: Mapped[list["ImportBatchModel"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )


class CategoryModel(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[UserModel] = relationship(back_populates="categories")
    transactions: Mapped[list["TransactionModel"]] = relationship(back_populates="category")
    budgets: Mapped[list["BudgetModel"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "transaction_type IN ('INCOME', 'EXPENSE')",
            name="ck_transactions_type_valid",
        ),
        CheckConstraint(
            "source IN ('MANUAL', 'CSV', 'OFX')",
            name="ck_transactions_source_valid",
        ),
        CheckConstraint("exchange_rate > 0", name="ck_transactions_exchange_rate_positive"),
        CheckConstraint("base_amount > 0", name="ck_transactions_base_amount_positive"),
        UniqueConstraint(
            "wallet_id",
            "source",
            "external_id",
            name="uq_transactions_import_identity",
        ),
        Index("ix_transactions_wallet_occurred_at", "wallet_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    transaction_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now(), index=True
    )
    currency: Mapped[str] = mapped_column(String(3))
    base_currency: Mapped[str] = mapped_column(String(3))
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    rate_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(
        String(20), default="MANUAL", server_default=text("'MANUAL'")
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now(), index=True
    )

    wallet: Mapped[WalletModel] = relationship(back_populates="transactions")
    category: Mapped[CategoryModel | None] = relationship(back_populates="transactions")
    import_batch: Mapped["ImportBatchModel | None"] = relationship(back_populates="transactions")


class ImportBatchModel(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("file_type IN ('CSV', 'OFX')", name="ck_import_batches_file_type_valid"),
        CheckConstraint(
            "status IN ('PREVIEW', 'COMPLETED', 'FAILED')",
            name="ck_import_batches_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    mapping: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    total_rows: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    valid_rows: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    duplicate_rows: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    invalid_rows: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    imported_rows: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserModel] = relationship(back_populates="import_batches")
    wallet: Mapped[WalletModel] = relationship(back_populates="import_batches")
    items: Mapped[list["ImportItemModel"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[TransactionModel]] = relationship(back_populates="import_batch")


class ImportItemModel(Base):
    __tablename__ = "import_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('READY', 'DUPLICATE', 'INVALID', 'IMPORTED', 'IGNORED')",
            name="ck_import_items_status_valid",
        ),
        UniqueConstraint("batch_id", "row_number", name="uq_import_items_batch_row"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    batch: Mapped[ImportBatchModel] = relationship(back_populates="items")


class ExchangeRateModel(Base):
    """Cached daily exchange rate returned by the configured external provider."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        UniqueConstraint(
            "base_currency",
            "quote_currency",
            "requested_date",
            "provider",
            name="uq_exchange_rates_lookup",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), index=True)
    quote_currency: Mapped[str] = mapped_column(String(3), index=True)
    requested_date: Mapped[date] = mapped_column(Date, index=True)
    effective_date: Mapped[date] = mapped_column(Date)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10))
    provider: Mapped[str] = mapped_column(String(50))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now()
    )


class BudgetModel(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("limit_amount > 0", name="ck_budgets_limit_positive"),
        CheckConstraint("period IN ('WEEKLY', 'MONTHLY')", name="ck_budgets_period_valid"),
        UniqueConstraint("user_id", "category_id", "period", name="uq_budgets_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    period: Mapped[str] = mapped_column(
        String(20), default="MONTHLY", server_default=text("'MONTHLY'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, server_default=func.now()
    )

    user: Mapped[UserModel] = relationship(back_populates="budgets")
    category: Mapped[CategoryModel] = relationship(back_populates="budgets")
