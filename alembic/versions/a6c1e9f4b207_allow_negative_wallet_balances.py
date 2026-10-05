"""allow negative wallet balances

Revision ID: a6c1e9f4b207
Revises: f2b7d9a4e631
Create Date: 2026-10-05 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a6c1e9f4b207"
down_revision: str | Sequence[str] | None = "f2b7d9a4e631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Let tracked bank, cash, overdraft, and credit accounts go below zero."""
    op.drop_constraint("ck_wallets_balance_nonnegative", "wallets", type_="check")


def downgrade() -> None:
    """Restore the original non-negative balance rule when data permits it."""
    op.create_check_constraint(
        "ck_wallets_balance_nonnegative",
        "wallets",
        "balance >= 0",
    )
