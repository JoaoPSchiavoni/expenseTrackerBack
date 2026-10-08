"""add automation and demo fields

Revision ID: e7c9a1d4f205
Revises: b3f7d2a8c914
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7c9a1d4f205"
down_revision: str | None = "b3f7d2a8c914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "categorization_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("pattern", sa.String(255), nullable=False),
        sa.Column("match_type", sa.String(20), server_default="CONTAINS", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("applies_to_imports", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.CheckConstraint("match_type IN ('CONTAINS', 'EXACT', 'REGEX')"),
        sa.CheckConstraint("priority >= 0"),
        sa.UniqueConstraint("user_id", "name", name="uq_categorization_rules_user_name"),
    )
    op.create_index(
        "ix_categorization_rules_user_active",
        "categorization_rules",
        ["user_id", "is_active", "priority"],
    )
    op.create_index("ix_categorization_rules_user_id", "categorization_rules", ["user_id"])
    op.create_index(
        "ix_categorization_rules_category_id", "categorization_rules", ["category_id"]
    )
    op.create_table(
        "detected_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("merchant_name", sa.String(160), nullable=False),
        sa.Column("normalized_key", sa.String(160), nullable=False),
        sa.Column("average_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("next_expected_date", sa.Date(), nullable=False),
        sa.Column("last_charge_date", sa.Date(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.CheckConstraint("average_amount > 0"),
        sa.CheckConstraint("frequency IN ('WEEKLY', 'MONTHLY', 'YEARLY')"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISMISSED')"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 100"),
        sa.UniqueConstraint(
            "user_id", "wallet_id", "normalized_key", name="uq_subscriptions_identity"
        ),
    )
    op.create_index(
        "ix_subscriptions_user_status_due",
        "detected_subscriptions",
        ["user_id", "status", "next_expected_date"],
    )
    for column in ("user_id", "wallet_id", "category_id", "next_expected_date"):
        op.create_index(f"ix_detected_subscriptions_{column}", "detected_subscriptions", [column])
    op.create_table(
        "billing_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(20), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["detected_subscriptions.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("alert_type IN ('DUE_SOON', 'OVERDUE')"),
        sa.CheckConstraint("expected_amount > 0"),
        sa.UniqueConstraint(
            "subscription_id", "expected_date", "alert_type", name="uq_billing_alerts_occurrence"
        ),
    )
    op.create_index(
        "ix_billing_alerts_user_active",
        "billing_alerts",
        ["user_id", "resolved_at", "read_at"],
    )
    for column in ("user_id", "subscription_id", "alert_type", "expected_date"):
        op.create_index(f"ix_billing_alerts_{column}", "billing_alerts", [column])


def downgrade() -> None:
    op.drop_table("billing_alerts")
    op.drop_table("detected_subscriptions")
    op.drop_table("categorization_rules")
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "is_demo")
