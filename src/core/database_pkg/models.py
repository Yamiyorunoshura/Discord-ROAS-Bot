"""Database models for Discord ROAS Bot v2.0.

此模組定義了專案中的所有 SQLAlchemy ORM 模型, 提供:
- PostgreSQL 資料庫連接
- UUID 主鍵支援
- Discord Snowflake ID 類型
- JSONB 欄位支援
- 時間戳追蹤
- 完整的型別提示

主要模型:
- CurrencyBalance: 成員餘額與交易記錄
- Department: 政府部門資料及角色關聯
- GuildConfig: 伺服器配置設定
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BIGINT,
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    from datetime import datetime


class Base(DeclarativeBase):
    """Base class for all database models."""

    @declared_attr  # type: ignore[arg-type]
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower()

    # 通用欄位
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GuildConfig(Base):
    """伺服器配置模型.

    儲存每個 Discord 伺服器的配置設定.

    Attributes:
        guild_id: Discord 伺服器 Snowflake ID
        settings: JSONB 配置設定
        is_active: 伺服器是否啟用
    """

    guild_id: Mapped[int] = mapped_column(BIGINT, unique=True, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default={})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 關聯
    currency_balances: Mapped[list[CurrencyBalance]] = relationship(
        "CurrencyBalance", back_populates="guild", cascade="all, delete-orphan"
    )
    departments: Mapped[list[Department]] = relationship(
        "Department", back_populates="guild", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_guild_config_guild_id", "guild_id"),
        Index("idx_guild_config_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<GuildConfig(guild_id={self.guild_id}, active={self.is_active})>"


class CurrencyBalance(Base):
    """貨幣餘額模型.

    記錄成員的餘額與交易快照.

    Attributes:
        guild_id: Discord 伺服器 Snowflake ID
        user_id: Discord 成員 Snowflake ID
        balance: 目前餘額
        last_transaction_at: 最後交易時間
        transaction_count: 交易次數
        metadata: 額外的 JSONB 資料
    """

    guild_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("guild_config.guild_id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    balance: Mapped[int] = mapped_column(BIGINT, default=0)
    last_transaction_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default={})

    # 關聯
    guild: Mapped[GuildConfig] = relationship(
        "GuildConfig", back_populates="currency_balances"
    )

    # 索引
    __table_args__ = (
        Index("idx_currency_balance_guild_user", "guild_id", "user_id", unique=True),
        Index("idx_currency_balance_balance", "balance"),
        Index("idx_currency_balance_last_transaction", "last_transaction_at"),
    )

    def __repr__(self) -> str:
        return f"<CurrencyBalance(guild_id={self.guild_id}, user_id={self.user_id}, balance={self.balance})>"


class Department(Base):
    """政府部門模型.

    政府部門資料及角色關聯, 支援階層結構與 Discord 角色同步.

    Attributes:
        guild_id: Discord 伺服器 Snowflake ID
        name: 部門名稱
        description: 部門描述
        parent_id: 上級部門 ID (自引用, 支援階層結構)
        role_id: 對應的 Discord 角色 ID
        permissions: JSONB 權限設定
        extra_data: JSONB 其他中繼資料
        display_order: 顯示順序
        is_active: 部門是否啟用
    """

    guild_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("guild_config.guild_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("department.id"), nullable=True
    )
    role_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    permissions: Mapped[dict[str, Any]] = mapped_column(JSONB, default={})
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default={})
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 關聯
    guild: Mapped[GuildConfig] = relationship(
        "GuildConfig", back_populates="departments"
    )
    accounts: Mapped[list[DepartmentAccount]] = relationship(
        "DepartmentAccount", back_populates="department", cascade="all, delete-orphan"
    )

    parent: Mapped[Department | None] = relationship(
        "Department", remote_side="id", back_populates="children"
    )
    children: Mapped[list[Department]] = relationship(
        "Department", back_populates="parent", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_department_guild_name", "guild_id", "name", unique=True),
        Index("idx_department_guild_role", "guild_id", "role_id"),
        Index("idx_department_parent", "parent_id"),
        Index("idx_department_active", "is_active"),
        Index("idx_department_order", "display_order"),
    )

    def __repr__(self) -> str:
        return f"<Department(guild_id={self.guild_id}, name='{self.name}', role_id={self.role_id}, active={self.is_active})>"


class DepartmentAccount(Base):
    """部門帳戶模型.

    關聯部門與用戶的帳戶資料.

    Attributes:
        department_id: 部門 ID 參考
        user_id: Discord 成員 Snowflake ID
        role_name: 角色名稱
        permissions: JSONB 權限資料
        appointed_at: 任命時間
        is_active: 帳戶是否啟用
    """

    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("department.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    permissions: Mapped[dict[str, Any]] = mapped_column(JSONB, default={})
    appointed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 關聯
    department: Mapped[Department] = relationship(
        "Department", back_populates="accounts"
    )

    # 索引
    __table_args__ = (
        Index(
            "idx_department_account_dept_user", "department_id", "user_id", unique=True
        ),
        Index("idx_department_account_user", "user_id"),
        Index("idx_department_account_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<DepartmentAccount(dept_id={self.department_id}, user_id={self.user_id}, role='{self.role_name}')>"


# 為了向前相容, 從現有的成就系統模型導入
class AchievementCategory(Base):
    """成就分類模型."""

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    icon_emoji: Mapped[str | None] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 關聯
    achievements: Mapped[list[Achievement]] = relationship(
        "Achievement", back_populates="category", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_achievement_category_name", "name"),
        Index("idx_achievement_category_order", "display_order"),
    )

    def __repr__(self) -> str:
        return f"<AchievementCategory(name='{self.name}', active={self.is_active})>"


class Achievement(Base):
    """成就定義模型."""

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("achievement_category.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    badge_url: Mapped[str | None] = mapped_column(String(500))
    role_reward: Mapped[str | None] = mapped_column(String(100))
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 關聯
    category: Mapped[AchievementCategory] = relationship(
        "AchievementCategory", back_populates="achievements"
    )
    user_achievements: Mapped[list[UserAchievement]] = relationship(
        "UserAchievement", back_populates="achievement", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_achievement_category", "category_id"),
        Index("idx_achievement_type", "type"),
        Index("idx_achievement_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Achievement(name='{self.name}', type='{self.type}', active={self.is_active})>"


class UserAchievement(Base):
    """用戶成就獲得記錄模型."""

    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("achievement.id"), nullable=False
    )
    earned_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False)

    # 關聯
    achievement: Mapped[Achievement] = relationship(
        "Achievement", back_populates="user_achievements"
    )

    __table_args__ = (
        Index(
            "idx_user_achievement_user_achievement",
            "user_id",
            "achievement_id",
            unique=True,
        ),
        Index("idx_user_achievement_user", "user_id"),
        Index("idx_user_achievement_earned", "earned_at"),
    )

    def __repr__(self) -> str:
        return f"<UserAchievement(user_id={self.user_id}, achievement_id={self.achievement_id}, earned_at={self.earned_at})>"


__all__ = [
    "Achievement",
    "AchievementCategory",
    "Base",
    "CurrencyBalance",
    "Department",
    "DepartmentAccount",
    "GuildConfig",
    "UserAchievement",
]
