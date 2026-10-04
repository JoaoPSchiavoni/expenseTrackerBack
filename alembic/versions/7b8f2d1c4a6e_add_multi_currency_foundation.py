"""add multi-currency accounting foundation

Revision ID: 7b8f2d1c4a6e
Revises: 0398c357fd34
Create Date: 2026-10-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b8f2d1c4a6e"
down_revision: str | Sequence[str] | None = "0398c357fd34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add user preferences, cached rates, and transaction conversion snapshots."""
    op.add_column(
        "users",
        sa.Column("base_currency", sa.String(length=3), server_default="BRL", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="America/Sao_Paulo",
            nullable=False,
        ),
    )
    op.alter_column(
        "wallets",
        "currency",
        existing_type=sa.String(length=10),
        type_=sa.String(length=3),
        existing_nullable=False,
    )

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("requested_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base_currency",
            "quote_currency",
            "requested_date",
            "provider",
            name="uq_exchange_rates_lookup",
        ),
    )
    op.create_index("ix_exchange_rates_base_currency", "exchange_rates", ["base_currency"])
    op.create_index("ix_exchange_rates_quote_currency", "exchange_rates", ["quote_currency"])
    op.create_index("ix_exchange_rates_requested_date", "exchange_rates", ["requested_date"])

    op.add_column("transactions", sa.Column("occurred_at", sa.DateTime(timezone=True)))
    op.add_column("transactions", sa.Column("currency", sa.String(length=3)))
    op.add_column("transactions", sa.Column("base_currency", sa.String(length=3)))
    op.add_column("transactions", sa.Column("exchange_rate", sa.Numeric(precision=20, scale=10)))
    op.add_column("transactions", sa.Column("base_amount", sa.Numeric(precision=14, scale=2)))
    op.add_column("transactions", sa.Column("rate_date", sa.Date()))
    op.add_column(
        "transactions",
        sa.Column("source", sa.String(length=20), server_default="MANUAL", nullable=False),
    )
    op.add_column("transactions", sa.Column("external_id", sa.String(length=255)))

    op.execute(
        """
        UPDATE transactions AS tx
        SET occurred_at = tx.created_at,
            currency = wallet.currency,
            base_currency = "user".base_currency,
            exchange_rate = 1.0000000000,
            base_amount = tx.amount,
            rate_date = CAST(tx.created_at AT TIME ZONE 'UTC' AS DATE)
        FROM wallets AS wallet
        JOIN users AS "user" ON "user".id = wallet.user_id
        WHERE tx.wallet_id = wallet.id
        """
    )
    for column_name in (
        "occurred_at",
        "currency",
        "base_currency",
        "exchange_rate",
        "base_amount",
        "rate_date",
    ):
        op.alter_column("transactions", column_name, nullable=False)

    op.create_check_constraint(
        "ck_transactions_exchange_rate_positive", "transactions", "exchange_rate > 0"
    )
    op.create_check_constraint(
        "ck_transactions_base_amount_positive", "transactions", "base_amount > 0"
    )
    op.create_check_constraint(
        "ck_transactions_source_valid",
        "transactions",
        "source IN ('MANUAL', 'CSV', 'OFX')",
    )
    op.drop_index("ix_transactions_wallet_created_at", table_name="transactions")
    op.create_index("ix_transactions_occurred_at", "transactions", ["occurred_at"])
    op.create_index("ix_transactions_external_id", "transactions", ["external_id"])
    op.create_index(
        "ix_transactions_wallet_occurred_at",
        "transactions",
        ["wallet_id", "occurred_at"],
    )


def downgrade() -> None:
    """Remove the multi-currency accounting foundation."""
    op.drop_index("ix_transactions_wallet_occurred_at", table_name="transactions")
    op.drop_index("ix_transactions_external_id", table_name="transactions")
    op.drop_index("ix_transactions_occurred_at", table_name="transactions")
    op.create_index(
        "ix_transactions_wallet_created_at",
        "transactions",
        ["wallet_id", "created_at"],
    )
    op.drop_constraint("ck_transactions_source_valid", "transactions", type_="check")
    op.drop_constraint("ck_transactions_base_amount_positive", "transactions", type_="check")
    op.drop_constraint("ck_transactions_exchange_rate_positive", "transactions", type_="check")
    for column_name in (
        "external_id",
        "source",
        "rate_date",
        "base_amount",
        "exchange_rate",
        "base_currency",
        "currency",
        "occurred_at",
    ):
        op.drop_column("transactions", column_name)

    op.drop_index("ix_exchange_rates_requested_date", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_quote_currency", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_base_currency", table_name="exchange_rates")
    op.drop_table("exchange_rates")
    op.alter_column(
        "wallets",
        "currency",
        existing_type=sa.String(length=3),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.drop_column("users", "timezone")
    op.drop_column("users", "base_currency")
