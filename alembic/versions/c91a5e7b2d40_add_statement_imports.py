"""add statement imports

Revision ID: c91a5e7b2d40
Revises: 7b8f2d1c4a6e
Create Date: 2026-10-04 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c91a5e7b2d40"
down_revision: str | Sequence[str] | None = "7b8f2d1c4a6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persisted previews and connect confirmed transactions to their source batch."""
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=10), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=True),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("file_type IN ('CSV', 'OFX')", name="ck_import_batches_file_type_valid"),
        sa.CheckConstraint(
            "status IN ('PREVIEW', 'COMPLETED', 'FAILED')",
            name="ck_import_batches_status_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_file_hash", "import_batches", ["file_hash"])
    op.create_index("ix_import_batches_status", "import_batches", ["status"])
    op.create_index("ix_import_batches_user_id", "import_batches", ["user_id"])
    op.create_index("ix_import_batches_wallet_id", "import_batches", ["wallet_id"])

    op.add_column("transactions", sa.Column("import_batch_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_transactions_import_batch_id",
        "transactions",
        "import_batches",
        ["import_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_transactions_import_batch_id", "transactions", ["import_batch_id"])
    op.create_unique_constraint(
        "uq_transactions_import_identity",
        "transactions",
        ["wallet_id", "source", "external_id"],
    )

    op.create_table(
        "import_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("transaction_type", sa.String(length=20), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('READY', 'DUPLICATE', 'INVALID', 'IMPORTED', 'IGNORED')",
            name="ck_import_items_status_valid",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_import_items_batch_row"),
    )
    op.create_index("ix_import_items_batch_id", "import_items", ["batch_id"])
    op.create_index("ix_import_items_status", "import_items", ["status"])


def downgrade() -> None:
    """Remove statement import persistence."""
    op.drop_index("ix_import_items_status", table_name="import_items")
    op.drop_index("ix_import_items_batch_id", table_name="import_items")
    op.drop_table("import_items")
    op.drop_constraint("uq_transactions_import_identity", "transactions", type_="unique")
    op.drop_index("ix_transactions_import_batch_id", table_name="transactions")
    op.drop_constraint("fk_transactions_import_batch_id", "transactions", type_="foreignkey")
    op.drop_column("transactions", "import_batch_id")
    op.drop_index("ix_import_batches_wallet_id", table_name="import_batches")
    op.drop_index("ix_import_batches_user_id", table_name="import_batches")
    op.drop_index("ix_import_batches_status", table_name="import_batches")
    op.drop_index("ix_import_batches_file_hash", table_name="import_batches")
    op.drop_table("import_batches")
