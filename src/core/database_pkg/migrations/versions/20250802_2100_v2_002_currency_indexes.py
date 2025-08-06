"""currency_indexes

Revision ID: v2_002
Revises: v2_001
Create Date: 2025-08-02 21:00:00.000000

為 Currency 系統添加效能索引, 支援 Story 1.2 的排行榜查詢功能.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v2_002"
down_revision: str | None = "v2_001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply migration changes."""
    # Create currency leaderboard index for efficient ranking queries
    # This index supports ORDER BY balance DESC queries with guild_id filtering
    op.create_index(
        "currency_balance_guild_balance_idx",
        "currency_balance",
        ["guild_id", sa.text("balance DESC")],
        unique=False,
    )

    # Create index for transaction metadata queries
    # Supports queries filtering by transaction_count for analytics
    op.create_index(
        "idx_currency_balance_transaction_count",
        "currency_balance",
        ["transaction_count"],
        unique=False,
    )

    # Composite index for pagination and filtering in ranking queries
    # Supports LIMIT/OFFSET with guild filtering efficiently
    op.create_index(
        "idx_currency_balance_guild_updated",
        "currency_balance",
        ["guild_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Revert migration changes."""
    # Drop the indexes in reverse order
    op.drop_index("idx_currency_balance_guild_updated", "currency_balance")
    op.drop_index("idx_currency_balance_transaction_count", "currency_balance")
    op.drop_index("currency_balance_guild_balance_idx", "currency_balance")
