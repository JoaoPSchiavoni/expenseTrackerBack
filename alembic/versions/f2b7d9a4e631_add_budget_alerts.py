"""add budget alerts

Revision ID: f2b7d9a4e631
Revises: e4f6a2c9d810
Create Date: 2026-10-04 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b7d9a4e631"
down_revision: str | Sequence[str] | None = "e4f6a2c9d810"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add alert preferences to budgets and persistent threshold notifications."""
    op.add_column(
        "budgets",
        sa.Column("alert_threshold", sa.Integer(), server_default="80", nullable=False),
    )
    op.add_column(
        "budgets",
        sa.Column("alerts_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_check_constraint(
        "ck_budgets_alert_threshold_valid",
        "budgets",
        "alert_threshold >= 1 AND alert_threshold <= 99",
    )

    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("spent_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("usage_percentage", sa.Numeric(precision=9, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "alert_type IN ('WARNING', 'EXCEEDED')", name="ck_budget_alerts_type_valid"
        ),
        sa.CheckConstraint("limit_amount > 0", name="ck_budget_alerts_limit_positive"),
        sa.CheckConstraint("spent_amount >= 0", name="ck_budget_alerts_spent_nonnegative"),
        sa.CheckConstraint("usage_percentage >= 0", name="ck_budget_alerts_usage_nonnegative"),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_id", "period_start", "alert_type", name="uq_budget_alerts_period_type"
        ),
    )
    op.create_index("ix_budget_alerts_user_id", "budget_alerts", ["user_id"])
    op.create_index("ix_budget_alerts_budget_id", "budget_alerts", ["budget_id"])
    op.create_index("ix_budget_alerts_category_id", "budget_alerts", ["category_id"])
    op.create_index("ix_budget_alerts_alert_type", "budget_alerts", ["alert_type"])
    op.create_index("ix_budget_alerts_period_start", "budget_alerts", ["period_start"])
    op.create_index(
        "ix_budget_alerts_user_active",
        "budget_alerts",
        ["user_id", "resolved_at", "read_at"],
    )


def downgrade() -> None:
    """Remove budget threshold notifications and preferences."""
    op.drop_index("ix_budget_alerts_user_active", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_period_start", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_alert_type", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_category_id", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_budget_id", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_user_id", table_name="budget_alerts")
    op.drop_table("budget_alerts")
    op.drop_constraint("ck_budgets_alert_threshold_valid", "budgets", type_="check")
    op.drop_column("budgets", "alerts_enabled")
    op.drop_column("budgets", "alert_threshold")
