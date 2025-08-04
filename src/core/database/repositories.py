"""Repository implementations for Discord ROAS Bot v2.0.

此模組提供各種資料模型的 Repository 實作, 包含:
- GuildConfigRepository: 伺服器配置管理
- CurrencyBalanceRepository: 貨幣餘額管理
- DepartmentRepository: 部門管理
- AchievementRepository: 成就系統管理
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.core.database.models import (
    Achievement,
    AchievementCategory,
    CurrencyBalance,
    Department,
    DepartmentAccount,
    GuildConfig,
    UserAchievement,
)
from src.core.database.postgresql import BaseRepository


class GuildConfigRepository(BaseRepository):
    """伺服器配置 Repository."""

    async def get_by_guild_id(self, guild_id: int) -> GuildConfig | None:
        """根據 Guild ID 取得配置.

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            伺服器配置或 None
        """
        result = await self.session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self, guild_id: int, settings: dict[str, Any], is_active: bool = True
    ) -> GuildConfig:
        """建立或更新伺服器配置.

        Args:
            guild_id: Discord 伺服器 ID
            settings: 配置設定
            is_active: 是否啟用

        Returns:
            伺服器配置

        Raises:
            Exception: 當資料庫操作失敗時
        """
        try:
            # 檢查是否已存在
            existing = await self.get_by_guild_id(guild_id)

            if existing:
                # 更新現有配置
                existing.settings = settings
                existing.is_active = is_active
                await self.flush()
                await self.refresh(existing)
                return existing
            else:
                # 建立新配置
                config = GuildConfig(
                    guild_id=guild_id, settings=settings, is_active=is_active
                )
                self.session.add(config)
                await self.flush()
                await self.refresh(config)
                return config
        except Exception as e:
            await self.rollback()
            self.logger.error(f"建立或更新伺服器配置失敗 (guild_id={guild_id}): {e}")
            raise

    async def get_all_active(self) -> Sequence[GuildConfig]:
        """取得所有啟用的伺服器配置."""
        result = await self.session.execute(
            select(GuildConfig).where(GuildConfig.is_active)
        )
        return result.scalars().all()

    async def deactivate_guild(self, guild_id: int) -> bool:
        """停用伺服器.

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            是否成功停用
        """
        result = await self.session.execute(
            update(GuildConfig)
            .where(GuildConfig.guild_id == guild_id)
            .values(is_active=False)
        )
        return result.rowcount > 0

class CurrencyBalanceRepository(BaseRepository):
    """貨幣餘額 Repository."""

    async def get_balance(self, guild_id: int, user_id: int) -> CurrencyBalance | None:
        """取得用戶餘額.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID

        Returns:
            用戶餘額或 None
        """
        result = await self.session.execute(
            select(CurrencyBalance).where(
                CurrencyBalance.guild_id == guild_id, CurrencyBalance.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update_balance(
        self,
        guild_id: int,
        user_id: int,
        balance: int,
        extra_data: dict[str, Any] | None = None,
    ) -> CurrencyBalance:
        """建立或更新用戶餘額.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            balance: 餘額
            extra_data: 額外資料

        Returns:
            用戶餘額記錄
        """
        existing = await self.get_balance(guild_id, user_id)

        if existing:
            existing.balance = balance
            existing.transaction_count += 1
            if extra_data:
                existing.extra_data.update(extra_data)
            await self.flush()
            await self.refresh(existing)
            return existing
        else:
            balance_record = CurrencyBalance(
                guild_id=guild_id,
                user_id=user_id,
                balance=balance,
                transaction_count=1,
                extra_data=extra_data or {},
            )
            self.session.add(balance_record)
            await self.flush()
            await self.refresh(balance_record)
            return balance_record

    async def add_to_balance(
        self, guild_id: int, user_id: int, amount: int
    ) -> CurrencyBalance:
        """增加用戶餘額.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            amount: 增加金額

        Returns:
            更新後的餘額記錄
        """
        existing = await self.get_balance(guild_id, user_id)

        new_balance = existing.balance + amount if existing else amount

        return await self.create_or_update_balance(guild_id, user_id, new_balance)

    async def get_top_balances(
        self, guild_id: int, limit: int = 10
    ) -> Sequence[CurrencyBalance]:
        """取得伺服器餘額排行榜.

        Args:
            guild_id: Discord 伺服器 ID
            limit: 限制數量

        Returns:
            餘額排行榜
        """
        result = await self.session.execute(
            select(CurrencyBalance)
            .where(CurrencyBalance.guild_id == guild_id)
            .order_by(CurrencyBalance.balance.desc())
            .limit(limit)
        )
        return result.scalars().all()

class DepartmentRepository(BaseRepository):
    """部門 Repository."""

    async def get_by_guild_and_name(
        self, guild_id: int, name: str
    ) -> Department | None:
        """根據伺服器和名稱取得部門.

        Args:
            guild_id: Discord 伺服器 ID
            name: 部門名稱

        Returns:
            部門或 None
        """
        result = await self.session.execute(
            select(Department).where(
                Department.guild_id == guild_id, Department.name == name
            )
        )
        return result.scalar_one_or_none()

    async def create_department(
        self,
        guild_id: int,
        name: str,
        description: str | None = None,
        json_data: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> Department:
        """建立部門.

        Args:
            guild_id: Discord 伺服器 ID
            name: 部門名稱
            description: 部門描述
            json_data: JSON 資料
            is_active: 是否啟用

        Returns:
            新建立的部門
        """
        department = Department(
            guild_id=guild_id,
            name=name,
            description=description,
            json_data=json_data or {},
            is_active=is_active,
        )
        self.session.add(department)
        await self.flush()
        await self.refresh(department)
        return department

    async def get_guild_departments(
        self, guild_id: int, active_only: bool = True
    ) -> Sequence[Department]:
        """取得伺服器所有部門.

        Args:
            guild_id: Discord 伺服器 ID
            active_only: 是否只取得啟用的部門

        Returns:
            部門列表
        """
        query = select(Department).where(Department.guild_id == guild_id)

        if active_only:
            query = query.where(Department.is_active)

        result = await self.session.execute(
            query.options(selectinload(Department.accounts))
        )
        return result.scalars().all()

    async def add_department_account(
        self,
        department_id: uuid.UUID,
        user_id: int,
        role_name: str,
        permissions: dict[str, Any] | None = None,
    ) -> DepartmentAccount:
        """新增部門帳戶.

        Args:
            department_id: 部門 ID
            user_id: Discord 用戶 ID
            role_name: 角色名稱
            permissions: 權限設定

        Returns:
            新建立的部門帳戶
        """
        account = DepartmentAccount(
            department_id=department_id,
            user_id=user_id,
            role_name=role_name,
            permissions=permissions or {},
            is_active=True,
        )
        self.session.add(account)
        await self.flush()
        await self.refresh(account)
        return account

class AchievementRepository(BaseRepository):
    """成就 Repository."""

    async def get_by_id(self, achievement_id: uuid.UUID) -> Achievement | None:
        """根據 ID 取得成就.

        Args:
            achievement_id: 成就 ID

        Returns:
            成就或 None
        """
        result = await self.session.execute(
            select(Achievement)
            .where(Achievement.id == achievement_id)
            .options(selectinload(Achievement.category))
        )
        return result.scalar_one_or_none()

    async def get_active_achievements(self) -> Sequence[Achievement]:
        """取得所有啟用的成就."""
        result = await self.session.execute(
            select(Achievement)
            .where(Achievement.is_active)
            .options(selectinload(Achievement.category))
        )
        return result.scalars().all()

    async def create_category(
        self,
        name: str,
        description: str,
        display_order: int = 0,
        icon_emoji: str | None = None,
    ) -> AchievementCategory:
        """建立成就分類.

        Args:
            name: 分類名稱
            description: 分類描述
            display_order: 顯示順序
            icon_emoji: 圖示表情符號

        Returns:
            新建立的成就分類
        """
        category = AchievementCategory(
            name=name,
            description=description,
            display_order=display_order,
            icon_emoji=icon_emoji,
            is_active=True,
        )
        self.session.add(category)
        await self.flush()
        await self.refresh(category)
        return category

    async def award_achievement(
        self, user_id: int, achievement_id: uuid.UUID
    ) -> UserAchievement:
        """授予用戶成就.

        Args:
            user_id: Discord 用戶 ID
            achievement_id: 成就 ID

        Returns:
            用戶成就記錄
        """
        user_achievement = UserAchievement(
            user_id=user_id, achievement_id=achievement_id, notified=False
        )
        self.session.add(user_achievement)
        await self.flush()
        await self.refresh(user_achievement)
        return user_achievement

    async def get_user_achievements(self, user_id: int) -> Sequence[UserAchievement]:
        """取得用戶所有成就.

        Args:
            user_id: Discord 用戶 ID

        Returns:
            用戶成就列表
        """
        result = await self.session.execute(
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .options(selectinload(UserAchievement.achievement))
        )
        return result.scalars().all()

    async def check_user_has_achievement(
        self, user_id: int, achievement_id: uuid.UUID
    ) -> bool:
        """檢查用戶是否已獲得特定成就.

        Args:
            user_id: Discord 用戶 ID
            achievement_id: 成就 ID

        Returns:
            是否已獲得成就
        """
        result = await self.session.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement_id,
            )
        )
        return result.scalar_one_or_none() is not None

__all__ = [
    "AchievementRepository",
    "CurrencyBalanceRepository",
    "DepartmentRepository",
    "GuildConfigRepository",
]
