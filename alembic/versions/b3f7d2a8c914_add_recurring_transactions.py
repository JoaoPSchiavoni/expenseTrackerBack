"""add recurring transactions

Revision ID: b3f7d2a8c914
Revises: d8e4f1a9c302
Create Date: 2026-10-07 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3f7d2a8c914"
down_revision: str | Sequence[str] | None = "d8e4f1a9c302"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store recurring rules and allow generated transactions to identify their source."""
    op.drop_constraint("ck_transactions_source_valid", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_source_valid",
        "transactions",
        "source IN ('MANUAL', 'CSV', 'OFX', 'RECURRING')",
    )
    op.create_table(
        "recurring_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("interval_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_recurring_transactions_amount_positive"),
        sa.CheckConstraint(
            "transaction_type IN ('INCOME', 'EXPENSE')",
            name="ck_recurring_transactions_type_valid",
        ),
        sa.CheckConstraint(
            "frequency IN ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY')",
            name="ck_recurring_transactions_frequency_valid",
        ),
        sa.CheckConstraint(
            "interval_count > 0", name="ck_recurring_transactions_interval_positive"
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_recurring_transactions_date_range",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurring_transactions_user_id", "recurring_transactions", ["user_id"]
    )
    op.create_index(
        "ix_recurring_transactions_wallet_id", "recurring_transactions", ["wallet_id"]
    )
    op.create_index(
        "ix_recurring_transactions_category_id", "recurring_transactions", ["category_id"]
    )
    op.create_index(
        "ix_recurring_transactions_next_run_date",
        "recurring_transactions",
        ["next_run_date"],
    )
    op.create_index(
        "ix_recurring_transactions_due",
        "recurring_transactions",
        ["user_id", "is_active", "next_run_date"],
    )


def downgrade() -> None:
    """Remove recurring rules and their generated transactions."""
    op.execute("DELETE FROM transactions WHERE source = 'RECURRING'")
    op.drop_index("ix_recurring_transactions_due", table_name="recurring_transactions")
    op.drop_index(
        "ix_recurring_transactions_next_run_date", table_name="recurring_transactions"
    )
    op.drop_index("ix_recurring_transactions_category_id", table_name="recurring_transactions")
    op.drop_index("ix_recurring_transactions_wallet_id", table_name="recurring_transactions")
    op.drop_index("ix_recurring_transactions_user_id", table_name="recurring_transactions")
    op.drop_table("recurring_transactions")
    op.drop_constraint("ck_transactions_source_valid", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_source_valid",
        "transactions",
        "source IN ('MANUAL', 'CSV', 'OFX')",
    )
