"""government_system_models

Revision ID: 20250803_001
Revises: 20250802_2100_v2_002_currency_indexes
Create Date: 2025-08-03 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250803_001"
down_revision = "20250802_2100_v2_002_currency_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升級: 添加政府系統模型的欄位"""

    # 為 department 表添加新欄位
    op.add_column(
        "department", sa.Column("parent_id", postgresql.UUID(), nullable=True)
    )
    op.add_column("department", sa.Column("role_id", sa.BIGINT(), nullable=True))
    op.add_column(
        "department",
        sa.Column(
            "permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "department",
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("department", sa.Column("display_order", sa.Integer(), nullable=True))

    # 添加外鍵約束
    op.create_foreign_key(
        "fk_department_parent_id", "department", "department", ["parent_id"], ["id"]
    )

    # 更新現有記錄的預設值
    op.execute("UPDATE department SET permissions = '{}' WHERE permissions IS NULL")
    op.execute("UPDATE department SET extra_data = '{}' WHERE extra_data IS NULL")
    op.execute("UPDATE department SET display_order = 0 WHERE display_order IS NULL")

    # 設置 NOT NULL 約束
    op.alter_column("department", "permissions", nullable=False)
    op.alter_column("department", "extra_data", nullable=False)
    op.alter_column("department", "display_order", nullable=False)

    # 添加新索引
    op.create_index("idx_department_guild_role", "department", ["guild_id", "role_id"])
    op.create_index("idx_department_parent", "department", ["parent_id"])
    op.create_index("idx_department_order", "department", ["display_order"])

    # 遷移舊 json_data 到新欄位結構
    op.execute("""
        UPDATE department
        SET permissions = COALESCE(json_data->'permissions', '{}'),
            extra_data = COALESCE(json_data->'metadata', '{}')
        WHERE json_data IS NOT NULL
    """)


def downgrade() -> None:
    """降級: 移除政府系統模型的欄位"""

    # 備份資料到 json_data
    op.execute("""
        UPDATE department
        SET json_data = json_build_object(
            'permissions', permissions,
            'metadata', extra_data
        )
    """)

    # 移除索引
    op.drop_index("idx_department_order", table_name="department")
    op.drop_index("idx_department_parent", table_name="department")
    op.drop_index("idx_department_guild_role", table_name="department")

    # 移除外鍵約束
    op.drop_constraint("fk_department_parent_id", "department", type_="foreignkey")

    # 移除欄位
    op.drop_column("department", "display_order")
    op.drop_column("department", "extra_data")
    op.drop_column("department", "permissions")
    op.drop_column("department", "role_id")
    op.drop_column("department", "parent_id")
