"""add global budgets

Revision ID: d8e4f1a9c302
Revises: a6c1e9f4b207
Create Date: 2026-10-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e4f1a9c302"
down_revision: str | Sequence[str] | None = "a6c1e9f4b207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow budgets and their alerts to cover every expense without a category."""
    op.alter_column("budgets", "category_id", existing_type=sa.Integer(), nullable=True)
    op.create_index(
        "uq_budgets_global_period",
        "budgets",
        ["user_id", "period"],
        unique=True,
        postgresql_where=sa.text("category_id IS NULL"),
    )

    op.alter_column(
        "budget_alerts", "category_id", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    """Restore category-only budgets, removing global scopes first."""
    op.execute("DELETE FROM budgets WHERE category_id IS NULL")

    op.alter_column(
        "budget_alerts", "category_id", existing_type=sa.Integer(), nullable=False
    )

    op.drop_index("uq_budgets_global_period", table_name="budgets")
    op.alter_column("budgets", "category_id", existing_type=sa.Integer(), nullable=False)
