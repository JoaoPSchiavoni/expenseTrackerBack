"""add financial goals

Revision ID: e4f6a2c9d810
Revises: c91a5e7b2d40
Create Date: 2026-10-04 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4f6a2c9d810"
down_revision: str | Sequence[str] | None = "c91a5e7b2d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create goal aggregates and their auditable contribution history."""
    op.create_table(
        "financial_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("target_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("current_amount", sa.Numeric(precision=14, scale=2), server_default="0.00", nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("target_amount > 0", name="ck_financial_goals_target_positive"),
        sa.CheckConstraint("current_amount >= 0", name="ck_financial_goals_current_nonnegative"),
        sa.CheckConstraint("current_amount <= target_amount", name="ck_financial_goals_current_within_target"),
        sa.CheckConstraint("status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')", name="ck_financial_goals_status_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_goals_user_id", "financial_goals", ["user_id"])
    op.create_index("ix_financial_goals_target_date", "financial_goals", ["target_date"])
    op.create_index("ix_financial_goals_user_status", "financial_goals", ["user_id", "status"])

    op.create_table(
        "goal_contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("contributed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_goal_contributions_amount_positive"),
        sa.ForeignKeyConstraint(["goal_id"], ["financial_goals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_goal_contributions_goal_id", "goal_contributions", ["goal_id"])
    op.create_index("ix_goal_contributions_contributed_at", "goal_contributions", ["contributed_at"])
    op.create_index(
        "ix_goal_contributions_goal_contributed",
        "goal_contributions",
        ["goal_id", "contributed_at"],
    )


def downgrade() -> None:
    """Remove financial goals and contribution history."""
    op.drop_index("ix_goal_contributions_goal_contributed", table_name="goal_contributions")
    op.drop_index("ix_goal_contributions_contributed_at", table_name="goal_contributions")
    op.drop_index("ix_goal_contributions_goal_id", table_name="goal_contributions")
    op.drop_table("goal_contributions")
    op.drop_index("ix_financial_goals_user_status", table_name="financial_goals")
    op.drop_index("ix_financial_goals_target_date", table_name="financial_goals")
    op.drop_index("ix_financial_goals_user_id", table_name="financial_goals")
    op.drop_table("financial_goals")
