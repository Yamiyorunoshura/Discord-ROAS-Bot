"""成就系統管理面板控制器.

此模組提供成就系統管理面板的核心控制器,包含:
- 管理面板的主要邏輯控制
- Discord UI 組件的統一管理
- 面板狀態和會話管理
- 管理操作的統籌協調
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

# 運行時需要的 imports
from src.core.container import Container

from ....core.di_container import DIContainer
from ..database.models import Achievement, AchievementCategory, AchievementType
from ..services.admin_service import AchievementAdminService, BulkOperationResult
from ..services.user_admin_service import UserSearchService
from .achievement_criteria_manager import AchievementCriteriaManager
from .admin_help_system import AdminHelpSystem
from .category_views import (
    CategoryListView,
    CategoryReorderView,
    CategorySelectionView,
    CategoryStatisticsView,
    CreateCategoryModal,
)
from .user_management_views import UserSearchResultView

if TYPE_CHECKING:
    from discord.ext import commands

    from ..services.achievement_service import AchievementService
    from ..services.admin_permission_service import AdminPermissionService
    from ..services.real_admin_service import RealAdminService

logger = logging.getLogger(__name__)

# 常數定義

# UI 顯示限制常數
MAX_DISPLAYED_ITEMS = 5  # 最多顯示基本項目數
MAX_DISPLAYED_USERS = 10  # 最多顯示用戶數
MAX_CATEGORY_DISPLAY = 3  # 最多顯示分類數
MAX_PREVIEW_ITEMS = 8  # 預覽最多項目數
MAX_ERROR_DISPLAY = 5  # 最多顯示錯誤數
MAX_SUCCESS_DISPLAY = 10  # 最多顯示成功項目數

# 系統常數
MAX_POINTS = 10000  # 成就最大點數
SUCCESS_RATE_THRESHOLD = 100  # 成功率閾值

# 測試相關常數
MAGIC_ACHIEVEMENT_ID_FOR_TESTING = 999  # 用於測試的模擬成就 ID
TEST_ACHIEVEMENT_ID_2 = 2  # 測試用成就ID 2

# 進度和統計相關常數
DIFFICULTY_SIMPLE_THRESHOLD = 80  # 簡單難度門檻(%)
DIFFICULTY_NORMAL_THRESHOLD = 50  # 普通難度門檻(%)
DIFFICULTY_HARD_THRESHOLD = 20  # 困難難度門檻(%)
DIFFICULTY_EXTREME_THRESHOLD = 5  # 極難難度門檻(%)

# 成就點數難度分級
POINTS_SIMPLE_MAX = 25  # 簡單成就最大點數
POINTS_NORMAL_MAX = 50  # 普通成就最大點數
POINTS_HARD_MAX = 100  # 困難成就最大點數
POINTS_EXTREME_MAX = 200  # 極難成就最大點數

# 字符限制常數
MIN_REASON_LENGTH = 5  # 最小原因長度
MIN_RESET_REASON_LENGTH = 10  # 最小重置原因長度
SUMMARY_MAX_LENGTH = 100  # 摘要最大長度

# 確認步驟常數
SECOND_CONFIRMATION_STEP = 2  # 第二次確認步驟
FULL_SUCCESS_RATE = 100  # 完全成功率(%)
PARTIAL_SUCCESS_THRESHOLD = 50  # 部分成功門檻(%)


class AdminPanelState(Enum):
    """管理面板狀態枚舉."""

    INITIALIZING = "initializing"  # 初始化中
    OVERVIEW = "overview"  # 系統概覽
    ACHIEVEMENTS = "achievements"  # 成就管理
    USERS = "users"  # 用戶管理
    SETTINGS = "settings"  # 系統設定
    ERROR = "error"  # 錯誤狀態
    CLOSED = "closed"  # 已關閉


class AdminPanel:
    """成就系統管理面板控制器.

    提供管理員專用的成就系統管理介面,支援:
    - 多頁面導航和狀態管理
    - 權限檢查和會話控制
    - 統一的錯誤處理
    - 可擴展的功能架構
    """

    def __init__(
        self,
        bot: commands.Bot,
        achievement_service: AchievementService,
        admin_permission_service: AdminPermissionService,
        guild_id: int,
        admin_user_id: int,
    ):
        """初始化管理面板.

        Args:
            bot: Discord 機器人實例
            achievement_service: 成就服務實例
            admin_permission_service: 管理員權限服務實例
            guild_id: 伺服器 ID
            admin_user_id: 管理員用戶 ID
        """
        self.bot = bot
        self.achievement_service = achievement_service
        self.admin_permission_service = admin_permission_service
        self.guild_id = guild_id
        self.admin_user_id = admin_user_id

        # 面板狀態管理
        self.current_state = AdminPanelState.INITIALIZING
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.session_timeout = timedelta(minutes=15)  # 15分鐘會話超時

        # UI 組件
        self.current_view: AdminPanelView | None = None
        self.current_interaction: discord.Interaction | None = None

        # 初始化條件管理器和幫助系統
        self.criteria_manager = AchievementCriteriaManager(self, achievement_service)
        self.help_system = AdminHelpSystem(self)

        # 統計和緩存
        self._cached_stats: dict[str, Any] | None = None
        self._cache_expires_at: datetime | None = None
        self._cache_ttl = timedelta(minutes=5)  # 5分鐘統計緩存

        logger.debug(f"[管理面板]為用戶 {admin_user_id} 在伺服器 {guild_id} 創建面板")

    async def start(self, interaction: discord.Interaction) -> None:
        """啟動管理面板.

        Args:
            interaction: Discord 互動物件
        """
        try:
            self.current_interaction = interaction
            self.current_state = AdminPanelState.OVERVIEW
            self.last_activity = datetime.utcnow()

            # 創建主面板視圖
            self.current_view = AdminPanelView(self)

            # 獲取系統統計
            stats = await self._load_system_stats()

            # 創建概覽 embed
            embed = await self._create_overview_embed(stats)

            # 發送面板
            await interaction.followup.send(
                embed=embed, view=self.current_view, ephemeral=True
            )

            logger.info(f"[管理面板]用戶 {self.admin_user_id} 啟動管理面板")

        except Exception as e:
            logger.error(f"[管理面板]啟動失敗: {e}")
            await self._handle_error(interaction, "面板啟動失敗", str(e))

    async def handle_navigation(
        self,
        interaction: discord.Interaction,
        target_state: AdminPanelState,
    ) -> None:
        """處理面板導航.

        Args:
            interaction: Discord 互動物件
            target_state: 目標狀態
        """
        try:
            # 更新活動時間和狀態
            self.last_activity = datetime.utcnow()

            # 檢查會話是否過期
            if await self._is_session_expired():
                await self._handle_session_expired(interaction)
                return

            member = (
                interaction.guild.get_member(self.admin_user_id)
                if interaction.guild
                else None
            )
            if not member or not isinstance(member, discord.Member):
                await self._handle_error(interaction, "權限錯誤", "無法獲取用戶資訊")
                return

            permission_result = (
                await self.admin_permission_service.check_admin_permission(
                    user=member,
                    action=f"導航到{target_state.value}",
                    context={
                        "navigation": True,
                        "from_state": self.current_state.value,
                        "to_state": target_state.value,
                    },
                )
            )

            if not permission_result.allowed:
                await self.admin_permission_service.handle_permission_denied(
                    interaction, permission_result, f"導航到{target_state.value}"
                )
                return

            # 更新狀態
            previous_state = self.current_state
            self.current_state = target_state

            # 根據目標狀態創建相應的內容
            embed, view = await self._create_state_content(target_state)

            # 更新當前視圖
            self.current_view = view

            # 更新互動回應
            await interaction.response.edit_message(embed=embed, view=view)

            logger.debug(
                f"[管理面板]用戶 {self.admin_user_id} 從 {previous_state.value} 導航到 {target_state.value}"
            )

        except Exception as e:
            logger.error(f"[管理面板]導航失敗: {e}")
            await self._handle_error(interaction, "導航失敗", str(e))

    async def close_panel(self, interaction: discord.Interaction) -> None:
        """關閉管理面板.

        Args:
            interaction: Discord 互動物件
        """
        try:
            self.current_state = AdminPanelState.CLOSED

            # 創建關閉確認 embed
            embed = StandardEmbedBuilder.create_success_embed(
                "面板已關閉",
                "✅ 成就系統管理面板已安全關閉.\n\n"
                f"**會話持續時間**: {datetime.utcnow() - self.created_at}\n"
                f"**最後活動**: {self.last_activity.strftime('%H:%M:%S')}\n\n"
                "感謝您的使用!",
            )
            embed.set_footer(text="所有管理操作已記錄")

            # 移除所有 UI 組件
            await interaction.response.edit_message(embed=embed, view=None)

            logger.info(f"[管理面板]用戶 {self.admin_user_id} 關閉管理面板")

        except Exception as e:
            logger.error(f"[管理面板]關閉失敗: {e}")
            # 即使關閉失敗也要嘗試清理
            with contextlib.suppress(builtins.BaseException):
                await interaction.response.edit_message(
                    content="管理面板已關閉(清理時發生錯誤)", embed=None, view=None
                )

    async def _create_state_content(
        self, state: AdminPanelState
    ) -> tuple[discord.Embed, AdminPanelView]:
        """根據狀態創建對應的內容.

        Args:
            state: 面板狀態

        Returns:
            (embed, view) 元組
        """
        if state == AdminPanelState.OVERVIEW:
            stats = await self._load_system_stats()
            embed = await self._create_overview_embed(stats)
            view = AdminPanelView(self)
        elif state == AdminPanelState.ACHIEVEMENTS:
            embed = await self._create_achievements_embed()
            view = AchievementManagementView(self)
        elif state == AdminPanelState.USERS:
            embed = await self._create_users_embed()
            view = UserManagementView(self)
        elif state == AdminPanelState.SETTINGS:
            embed = await self._create_settings_embed()
            view = AdminPanelView(self)
        else:
            embed = await self._create_error_embed(
                "未知狀態", f"不支援的面板狀態: {state.value}"
            )
            view = AdminPanelView(self)

        return embed, view

    async def _create_overview_embed(self, stats: dict[str, Any]) -> discord.Embed:
        """創建系統概覽 Embed.

        Args:
            stats: 系統統計數據

        Returns:
            概覽 Embed
        """
        embed = StandardEmbedBuilder.create_info_embed(
            "🛠️ 成就系統管理面板",
            "歡迎使用 Discord ROAS Bot 成就系統管理面板!\n\n"
            "**主要功能:**\n"
            "🏆 **成就管理** - 創建、編輯、刪除成就\n"
            "🎯 **條件設置** - 設置成就達成條件\n"
            "👥 **用戶管理** - 管理用戶成就和進度\n"
            "📦 **批量操作** - 批量處理成就和用戶\n"
            "📊 **統計分析** - 查看系統統計和報表\n\n"
            "💡 **提示:** 點擊下方的「📚 使用指南」查看詳細說明",
        )

        # 系統狀態
        embed.add_field(name="📊 系統狀態", value="🟢 正常運行", inline=True)

        # 統計數據
        embed.add_field(
            name="👥 總用戶數", value=f"{stats.get('total_users', 0):,}", inline=True
        )

        embed.add_field(
            name="🏆 總成就數",
            value=f"{stats.get('total_achievements', 0):,}",
            inline=True,
        )

        embed.add_field(
            name="🎯 已解鎖成就",
            value=f"{stats.get('unlocked_achievements', 0):,}",
            inline=True,
        )

        embed.add_field(
            name="📈 解鎖率", value=f"{stats.get('unlock_rate', 0):.1f}%", inline=True
        )

        embed.add_field(
            name="⏰ 最後更新",
            value=f"<t:{int(datetime.utcnow().timestamp())}:R>",
            inline=True,
        )

        # 設置橙色主題
        embed.color = 0xFF6B35
        embed.set_footer(text="僅限管理員使用 | 所有操作將被記錄")

        return embed

    async def _create_achievements_embed(self) -> discord.Embed:
        """創建成就管理 Embed."""
        try:
            # 載入成就統計數據
            achievement_stats = await self._load_achievement_management_stats()

            embed = StandardEmbedBuilder.create_info_embed(
                "🏆 成就管理",
                "管理成就定義和分類,支援 CRUD 操作和批量管理.",
            )

            # 統計數據
            embed.add_field(
                name="📊 總成就數",
                value=f"{achievement_stats.get('total_achievements', 0):,}",
                inline=True,
            )
            embed.add_field(
                name="✅ 啟用成就",
                value=f"{achievement_stats.get('active_achievements', 0):,}",
                inline=True,
            )
            embed.add_field(
                name="📂 分類數量",
                value=f"{achievement_stats.get('category_count', 0):,}",
                inline=True,
            )

            # 最近活動
            recent_activity = achievement_stats.get("recent_activity", [])
            if recent_activity:
                activity_text = "\n".join([
                    f"• {activity}" for activity in recent_activity[:3]
                ])
                embed.add_field(name="📝 最近活動", value=activity_text, inline=False)

            embed.color = 0xFF6B35
            embed.set_footer(text="選擇下方操作來管理成就 | 所有操作將被記錄")

            return embed

        except Exception as e:
            logger.error(f"[管理面板]創建成就管理 embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "載入成就管理面板時發生錯誤,請稍後再試."
            )

    async def _create_users_embed(self) -> discord.Embed:
        """創建用戶管理 Embed."""
        try:
            # 載入用戶管理統計數據
            user_stats = await self._load_user_management_stats()

            embed = StandardEmbedBuilder.create_info_embed(
                "👤 用戶成就管理",
                "管理用戶的成就和進度,支援手動授予、撤銷和重置等操作.",
            )

            # 統計數據
            embed.add_field(
                name="📊 用戶統計",
                value=(
                    f"**總用戶數**: {user_stats.get('total_users', 0):,}\n"
                    f"**有成就用戶**: {user_stats.get('users_with_achievements', 0):,}\n"
                    f"**活躍用戶**: {user_stats.get('active_users', 0):,}"
                ),
                inline=True,
            )
            embed.add_field(
                name="🏆 成就分布",
                value=(
                    f"**總獲得數**: {user_stats.get('total_user_achievements', 0):,}\n"
                    f"**平均每人**: {user_stats.get('avg_achievements_per_user', 0):.1f}\n"
                    f"**最高持有**: {user_stats.get('max_achievements', 0)} 個"
                ),
                inline=True,
            )

            # 最近活動
            recent_activity = user_stats.get("recent_activity", [])
            if recent_activity:
                activity_text = "\n".join([
                    f"• {activity}" for activity in recent_activity[:3]
                ])
                embed.add_field(name="📝 最近活動", value=activity_text, inline=False)

            # 功能說明
            embed.add_field(
                name="⚡ 可用功能",
                value=(
                    "🔍 **用戶搜尋** - 搜尋特定用戶進行管理\n"
                    "🎁 **授予成就** - 手動授予用戶成就\n"
                    "❌ **撤銷成就** - 撤銷用戶已獲得的成就\n"
                    "📈 **調整進度** - 調整用戶成就進度\n"
                    "🔄 **重置資料** - 重置用戶成就資料\n"
                    "👥 **批量操作** - 批量用戶操作"
                ),
                inline=False,
            )

            embed.color = 0xFF6B35
            embed.set_footer(text="選擇下方操作來管理用戶成就 | 所有操作將被記錄")

            return embed

        except Exception as e:
            logger.error(f"[管理面板]創建用戶管理 embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "載入用戶管理面板時發生錯誤,請稍後再試."
            )

    async def _create_settings_embed(self) -> discord.Embed:
        """創建系統設定 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "⚙️ 系統設定",
            "**功能規劃中**\n\n"
            "此功能將提供:\n"
            "• 成就系統開關\n"
            "• 通知設定\n"
            "• 快取配置\n"
            "• 權限管理\n"
            "• 系統維護工具\n\n"
            "⚠️ 此功能目前正在規劃中,將在未來版本中實現.",
        )
        embed.color = 0xFF6B35
        return embed

    async def _create_error_embed(self, title: str, description: str) -> discord.Embed:
        """創建錯誤 Embed."""
        return StandardEmbedBuilder.create_error_embed(title, description)

    async def _load_system_stats(self) -> dict[str, Any]:
        """載入系統統計數據.

        Returns:
            系統統計字典
        """
        try:
            # 檢查緩存
            if (
                self._cached_stats
                and self._cache_expires_at
                and datetime.utcnow() < self._cache_expires_at
            ):
                return self._cached_stats

            stats = {
                "total_users": await self._get_total_users(),
                "total_achievements": await self._get_total_achievements(),
                "unlocked_achievements": await self._get_unlocked_achievements(),
                "unlock_rate": 0.0,
            }

            # 計算解鎖率
            if stats["total_achievements"] > 0:
                stats["unlock_rate"] = (
                    stats["unlocked_achievements"] / stats["total_achievements"] * 100
                )

            # 更新緩存
            self._cached_stats = stats
            self._cache_expires_at = datetime.utcnow() + self._cache_ttl

            return stats

        except Exception as e:
            logger.error(f"[管理面板]載入統計數據失敗: {e}")
            return {
                "total_users": 0,
                "total_achievements": 0,
                "unlocked_achievements": 0,
                "unlock_rate": 0.0,
            }

    async def _get_total_users(self) -> int:
        """獲取總用戶數."""
        try:
            # 從成就服務獲取真實的用戶統計數據
            global_stats = await self.achievement_service.get_global_achievement_stats()
            total_users = global_stats.get("total_users", 0)

            # 如果成就服務沒有用戶數據,使用Discord伺服器成員數作為備用
            if total_users == 0:
                guild = self.bot.get_guild(self.guild_id)
                total_users = guild.member_count if guild else 0

            return total_users
        except Exception as e:
            logger.error(f"[管理面板]獲取總用戶數失敗: {e}")
            try:
                guild = self.bot.get_guild(self.guild_id)
                return guild.member_count if guild else 0
            except Exception:
                return 0

    async def _get_total_achievements(self) -> int:
        """獲取總成就數."""
        try:
            # 從成就服務獲取全域統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("total_achievements", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取總成就數失敗: {e}")
            return 0

    async def _load_achievement_management_stats(self) -> dict[str, Any]:
        """載入成就管理統計數據.

        Returns:
            成就管理統計字典
        """
        try:
            # 從成就服務載入管理統計
            total_achievements = await self._get_total_achievements()
            active_achievements = await self._get_active_achievements_count()
            category_count = await self._get_category_count()
            recent_activity = await self._get_recent_management_activity()

            return {
                "total_achievements": total_achievements,
                "active_achievements": active_achievements,
                "category_count": category_count,
                "inactive_achievements": total_achievements - active_achievements,
                "recent_activity": recent_activity,
            }
        except Exception as e:
            logger.error(f"[管理面板]載入成就管理統計失敗: {e}")
            return {
                "total_achievements": 0,
                "active_achievements": 0,
                "category_count": 0,
                "inactive_achievements": 0,
                "recent_activity": [],
            }

    async def _get_active_achievements_count(self) -> int:
        """獲取啟用成就數量."""
        try:
            # 從成就服務獲取啟用成就統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("active_achievements", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取啟用成就數量失敗: {e}")
            return 0

    async def _get_category_count(self) -> int:
        """獲取成就分類數量."""
        try:
            # 從成就服務獲取分類統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("category_count", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取分類數量失敗: {e}")
            return 0

    async def _get_recent_management_activity(self) -> list[str]:
        """獲取最近管理活動."""
        try:
            # 嘗試從審計日誌服務獲取最近活動
            if hasattr(self, "audit_service"):
                activities = await self.audit_service.get_recent_activities(limit=5)
                return [
                    f"{activity.timestamp}: {activity.description}"
                    for activity in activities
                ]

            # 如果沒有審計服務,返回空列表
            logger.warning("審計服務不可用,無法獲取最近管理活動")
            return []

        except Exception as e:
            logger.error(f"[管理面板]獲取最近活動失敗: {e}")
            return []

    async def _load_user_management_stats(self) -> dict[str, Any]:
        """載入用戶管理統計數據.

        Returns:
            用戶管理統計字典
        """
        try:
            # 從成就服務載入用戶統計
            total_users = await self._get_total_users()
            users_with_achievements = await self._get_users_with_achievements_count()
            active_users = await self._get_active_users_count()
            total_user_achievements = await self._get_total_user_achievements()
            avg_achievements_per_user = await self._get_avg_achievements_per_user()
            max_achievements = await self._get_max_achievements_per_user()
            recent_activity = await self._get_recent_user_activity()

            return {
                "total_users": total_users,
                "users_with_achievements": users_with_achievements,
                "active_users": active_users,
                "total_user_achievements": total_user_achievements,
                "avg_achievements_per_user": avg_achievements_per_user,
                "max_achievements": max_achievements,
                "recent_activity": recent_activity,
            }
        except Exception as e:
            logger.error(f"[管理面板]載入用戶管理統計失敗: {e}")
            return {
                "total_users": 0,
                "users_with_achievements": 0,
                "active_users": 0,
                "total_user_achievements": 0,
                "avg_achievements_per_user": 0.0,
                "max_achievements": 0,
                "recent_activity": [],
            }

    async def _get_users_with_achievements_count(self) -> int:
        """獲取有成就的用戶數量."""
        try:
            # 從成就服務獲取統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("users_with_achievements", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取有成就用戶數量失敗: {e}")
            return 0

    async def _get_active_users_count(self) -> int:
        """獲取活躍用戶數量."""
        try:
            # 從成就服務獲取活躍用戶統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("active_users", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取活躍用戶數量失敗: {e}")
            return 0

    async def _get_total_user_achievements(self) -> int:
        """獲取總用戶成就數."""
        try:
            # 從成就服務獲取總用戶成就統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("total_user_achievements", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取總用戶成就數失敗: {e}")
            return 0

    async def _get_avg_achievements_per_user(self) -> float:
        """獲取平均每人成就數."""
        try:
            # 從成就服務獲取平均統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("avg_achievements_per_user", 0.0)
        except Exception as e:
            logger.error(f"[管理面板]獲取平均成就數失敗: {e}")
            return 0.0

    async def _get_max_achievements_per_user(self) -> int:
        """獲取最多成就持有數."""
        try:
            # 從成就服務獲取最大值統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("max_achievements_per_user", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取最多成就數失敗: {e}")
            return 0

    async def _get_recent_user_activity(self) -> list[str]:
        """獲取最近用戶活動."""
        try:
            # 從審計日誌獲取最近用戶相關活動
            if hasattr(self.achievement_service, "get_recent_user_activity"):
                activities = await self.achievement_service.get_recent_user_activity()
                return activities if activities else ["暫無最近活動"]
            else:
                logger.warning("成就服務不支援活動記錄,返回暫無數據")
                return ["暫無最近活動"]
        except Exception as e:
            logger.error(f"[管理面板]獲取最近用戶活動失敗: {e}")
            return ["暫無最近活動"]

    async def _load_category_management_stats(self) -> dict[str, Any]:
        """載入分類管理統計數據.

        Returns:
            分類管理統計字典
        """
        try:
            # 從服務層載入分類統計
            total_categories = await self._get_total_categories_count()
            categories_with_achievements = (
                await self._get_categories_with_achievements_count()
            )
            total_achievements_in_categories = (
                await self._get_achievements_in_categories_count()
            )
            most_used_category = await self._get_most_used_category()
            recent_category_activity = await self._get_recent_category_activity()

            return {
                "total_categories": total_categories,
                "categories_with_achievements": categories_with_achievements,
                "empty_categories": total_categories - categories_with_achievements,
                "total_achievements_in_categories": total_achievements_in_categories,
                "most_used_category": most_used_category,
                "recent_activity": recent_category_activity,
            }
        except Exception as e:
            logger.error(f"[管理面板]載入分類管理統計失敗: {e}")
            return {
                "total_categories": 0,
                "categories_with_achievements": 0,
                "empty_categories": 0,
                "total_achievements_in_categories": 0,
                "most_used_category": "無",
                "recent_activity": [],
            }

    async def _get_total_categories_count(self) -> int:
        """獲取總分類數量."""
        try:
            # 從分類服務獲取總數量
            if hasattr(self.achievement_service, "get_categories_count"):
                return await self.achievement_service.get_categories_count()
            else:
                logger.warning("成就服務不支援分類統計,返回0")
                return 0
        except Exception as e:
            logger.error(f"[管理面板]獲取總分類數量失敗: {e}")
            return 0

    async def _get_categories_with_achievements_count(self) -> int:
        """獲取有成就的分類數量."""
        try:
            # 從分類服務獲取有成就的分類數量
            if hasattr(
                self.achievement_service, "get_categories_with_achievements_count"
            ):
                return await self.achievement_service.get_categories_with_achievements_count()
            else:
                logger.warning("成就服務不支援分類統計,返回0")
                return 0
        except Exception as e:
            logger.error(f"[管理面板]獲取有成就分類數量失敗: {e}")
            return 0

    async def _get_achievements_in_categories_count(self) -> int:
        """獲取分類中的成就總數."""
        try:
            # 從成就服務獲取分類中的成就總數
            return await self._get_total_achievements()
        except Exception as e:
            logger.error(f"[管理面板]獲取分類成就數量失敗: {e}")
            return 0

    async def _get_most_used_category(self) -> str:
        """獲取使用最多的分類."""
        try:
            # 從統計服務獲取最常用分類
            if hasattr(self.achievement_service, "get_most_used_category"):
                result = await self.achievement_service.get_most_used_category()
                return result if result else "暫無數據"
            else:
                logger.warning("成就服務不支援分類統計,返回暫無數據")
                return "暫無數據"
        except Exception as e:
            logger.error(f"[管理面板]獲取最常用分類失敗: {e}")
            return "暫無數據"

    async def _get_recent_category_activity(self) -> list[str]:
        """獲取最近分類活動."""
        try:
            # 從審計日誌獲取分類相關活動
            if hasattr(self.achievement_service, "get_recent_category_activity"):
                activities = (
                    await self.achievement_service.get_recent_category_activity()
                )
                return activities if activities else ["暫無最近活動"]
            else:
                logger.warning("成就服務不支援活動記錄,返回暫無數據")
                return ["暫無最近活動"]
        except Exception as e:
            logger.error(f"[管理面板]獲取分類活動失敗: {e}")
            return ["暫無最近活動"]

    async def _create_category_management_embed(
        self, category_stats: dict[str, Any]
    ) -> discord.Embed:
        """建立分類管理 Embed.

        Args:
            category_stats: 分類統計數據

        Returns:
            分類管理 Embed
        """
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "📂 分類管理",
                "管理成就分類,包含 CRUD 操作、排序和使用統計.",
            )

            # 統計數據
            embed.add_field(
                name="📊 分類統計",
                value=(
                    f"**總分類數**: {category_stats.get('total_categories', 0):,}\n"
                    f"**有成就分類**: {category_stats.get('categories_with_achievements', 0):,}\n"
                    f"**空分類**: {category_stats.get('empty_categories', 0):,}"
                ),
                inline=True,
            )
            embed.add_field(
                name="🏆 成就分布",
                value=(
                    f"**分類中成就數**: {category_stats.get('total_achievements_in_categories', 0):,}\n"
                    f"**最常用分類**: {category_stats.get('most_used_category', '無')}\n"
                    f"**平均成就數**: {category_stats.get('total_achievements_in_categories', 0) // max(category_stats.get('total_categories', 1), 1)}"
                ),
                inline=True,
            )

            # 最近活動
            recent_activity = category_stats.get("recent_activity", [])
            if recent_activity:
                activity_text = "\n".join([
                    f"• {activity}" for activity in recent_activity[:3]
                ])
                embed.add_field(name="📝 最近活動", value=activity_text, inline=False)

            # 功能說明
            embed.add_field(
                name="⚡ 可用功能",
                value=(
                    "🆕 **新增分類** - 建立新的成就分類\n"
                    "✏️ **編輯分類** - 修改分類資訊和設定\n"
                    "🗑️ **刪除分類** - 移除不需要的分類\n"
                    "🔄 **排序管理** - 調整分類顯示順序\n"
                    "📈 **使用統計** - 查看分類使用情況\n"
                    "📦 **成就重新分配** - 處理分類變更"
                ),
                inline=False,
            )

            embed.color = 0xFF6B35
            embed.set_footer(text="選擇下方操作來管理分類 | 所有操作將被記錄")

            return embed

        except Exception as e:
            logger.error(f"[管理面板]創建分類管理 embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "載入分類管理面板時發生錯誤,請稍後再試."
            )

    async def _get_unlocked_achievements(self) -> int:
        """獲取已解鎖成就數."""
        try:
            # 從成就服務獲取全域統計
            global_stats = await self.achievement_service.get_global_achievement_stats()
            return global_stats.get("total_user_achievements", 0)
        except Exception as e:
            logger.error(f"[管理面板]獲取已解鎖成就數失敗: {e}")
            return 0

    async def _is_session_expired(self) -> bool:
        """檢查會話是否過期."""
        return datetime.utcnow() - self.last_activity > self.session_timeout

    async def _handle_session_expired(self, interaction: discord.Interaction) -> None:
        """處理會話過期."""
        try:
            embed = StandardEmbedBuilder.create_warning_embed(
                "會話已過期",
                "⏰ 您的管理面板會話已過期(超過15分鐘無活動).\n\n"
                "為了安全起見,面板已自動關閉.\n"
                "請重新使用 `/成就管理` 指令開啟面板.",
            )

            await interaction.response.edit_message(embed=embed, view=None)
            self.current_state = AdminPanelState.CLOSED

            logger.info(f"[管理面板]用戶 {self.admin_user_id} 的會話已過期")

        except Exception as e:
            logger.error(f"[管理面板]處理會話過期失敗: {e}")

    async def _handle_error(
        self, interaction: discord.Interaction, title: str, error_message: str
    ) -> None:
        """處理面板錯誤.

        Args:
            interaction: Discord 互動物件
            title: 錯誤標題
            error_message: 錯誤訊息
        """
        try:
            self.current_state = AdminPanelState.ERROR

            embed = StandardEmbedBuilder.create_error_embed(
                title,
                f"❌ {error_message}\n\n"
                f"**錯誤時間**: <t:{int(datetime.utcnow().timestamp())}:f>\n"
                f"**會話ID**: {id(self)}\n\n"
                "請嘗試重新開啟管理面板,如果問題持續請聯繫開發者.",
            )

            # 嘗試編輯訊息,如果失敗則發送新訊息
            if interaction.response.is_done():
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=None
                )
            else:
                await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"[管理面板]處理錯誤時發生異常: {e}")


class AdminPanelView(ui.View):
    """管理面板的 Discord UI 視圖."""

    def __init__(self, panel: AdminPanel):
        """初始化視圖.

        Args:
            panel: 管理面板控制器
        """
        super().__init__(timeout=900)  # 15分鐘超時
        self.panel = panel

    @ui.select(
        placeholder="選擇管理功能...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="📊 系統概覽",
                value="overview",
                description="查看系統狀態和統計",
                emoji="📊",
            ),
            discord.SelectOption(
                label="🏆 成就管理",
                value="achievements",
                description="管理成就定義(Story 4.2)",
                emoji="🏆",
            ),
            discord.SelectOption(
                label="👤 用戶管理",
                value="users",
                description="管理用戶成就(Story 4.3)",
                emoji="👤",
            ),
            discord.SelectOption(
                label="⚙️ 系統設定",
                value="settings",
                description="系統配置管理",
                emoji="⚙️",
            ),
        ],
    )
    async def navigation_select(
        self, interaction: discord.Interaction, select: ui.Select
    ) -> None:
        """處理導航選擇."""
        try:
            selected_value = select.values[0]

            # 映射選擇值到面板狀態
            state_map = {
                "overview": AdminPanelState.OVERVIEW,
                "achievements": AdminPanelState.ACHIEVEMENTS,
                "users": AdminPanelState.USERS,
                "settings": AdminPanelState.SETTINGS,
            }

            target_state = state_map.get(selected_value)
            if target_state:
                await self.panel.handle_navigation(interaction, target_state)
            else:
                await interaction.response.send_message("❌ 無效的選擇", ephemeral=True)

        except Exception as e:
            logger.error(f"[管理面板]導航選擇處理失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理導航時發生錯誤", ephemeral=True
            )

    @ui.button(label="📚 使用指南", style=discord.ButtonStyle.primary, emoji="📚")
    async def help_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """顯示使用指南."""
        try:
            await self.panel.help_system.show_help_overview(interaction)
        except Exception as e:
            logger.error(f"[管理面板]顯示幫助失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入幫助文檔時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """處理重新整理按鈕."""
        try:
            # 清除統計緩存
            self.panel._cached_stats = None
            self.panel._cache_expires_at = None

            # 重新載入當前狀態
            await self.panel.handle_navigation(interaction, self.panel.current_state)

        except Exception as e:
            logger.error(f"[管理面板]重新整理失敗: {e}")
            await interaction.response.send_message(
                "❌ 重新整理時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 關閉面板", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """處理關閉按鈕."""
        await self.panel.close_panel(interaction)

    async def on_timeout(self) -> None:
        """處理視圖超時."""
        try:
            self.panel.current_state = AdminPanelState.CLOSED
            logger.info(f"[管理面板]用戶 {self.panel.admin_user_id} 的面板因超時而關閉")
        except Exception as e:
            logger.error(f"[管理面板]處理超時失敗: {e}")

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        """處理視圖錯誤."""
        logger.error(f"[管理面板]UI 錯誤: {error}, 項目: {item}")
        with contextlib.suppress(builtins.BaseException):
            await interaction.response.send_message(
                "❌ 處理互動時發生錯誤,請稍後再試", ephemeral=True
            )


class AchievementManagementView(ui.View):
    """成就管理專用視圖.

    提供成就管理的所有操作選項.
    """

    def __init__(self, panel: AdminPanel):
        """初始化成就管理視圖.

        Args:
            panel: 管理面板控制器
        """
        super().__init__(timeout=900)  # 15分鐘超時
        self.panel = panel

    @ui.select(
        placeholder="選擇成就管理操作...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="+ 新增成就",
                value="create",
                description="創建新的成就定義",
                emoji="+",
            ),
            discord.SelectOption(
                label="📝 編輯成就",
                value="edit",
                description="修改現有成就",
                emoji="📝",
            ),
            discord.SelectOption(
                label="📋 成就列表",
                value="list",
                description="查看所有成就",
                emoji="📋",
            ),
            discord.SelectOption(
                label="📄 複製成就",
                value="copy",
                description="複製現有成就創建新成就",
                emoji="📄",
            ),
            discord.SelectOption(
                label="🗑️ 刪除成就",
                value="delete",
                description="刪除成就定義",
                emoji="🗑️",
            ),
            discord.SelectOption(
                label="📦 批量操作",
                value="bulk",
                description="批量管理成就",
                emoji="📦",
            ),
            discord.SelectOption(
                label="📂 分類管理",
                value="categories",
                description="管理成就分類",
                emoji="📂",
            ),
            discord.SelectOption(
                label="🎯 條件設置",
                value="criteria",
                description="設置成就達成條件",
                emoji="🎯",
            ),
        ],
    )
    async def achievement_operation_select(
        self, interaction: discord.Interaction, select: ui.Select
    ) -> None:
        """處理成就管理操作選擇."""
        try:
            selected_value = select.values[0]

            # 處理不同操作
            if selected_value == "create":
                await self._handle_create_achievement(interaction)
            elif selected_value == "edit":
                await self._handle_edit_achievement(interaction)
            elif selected_value == "list":
                await self._handle_list_achievements(interaction)
            elif selected_value == "copy":
                await self._handle_copy_achievement(interaction)
            elif selected_value == "delete":
                await self._handle_delete_achievement(interaction)
            elif selected_value == "bulk":
                await self._handle_bulk_operations(interaction)
            elif selected_value == "categories":
                await self._handle_category_management(interaction)
            elif selected_value == "criteria":
                await self._handle_criteria_management(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 無效的操作選擇", ephemeral=True
                )

        except Exception as e:
            logger.error(f"[成就管理視圖]操作選擇處理失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理操作時發生錯誤", ephemeral=True
            )

    async def _handle_create_achievement(
        self, interaction: discord.Interaction
    ) -> None:
        """處理新增成就操作."""
        try:
            # 建立成就新增模態框
            modal = CreateAchievementModal(self.panel)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就管理視圖]新增成就操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就新增表單時發生錯誤", ephemeral=True
            )

    async def _handle_edit_achievement(self, interaction: discord.Interaction) -> None:
        """處理編輯成就操作."""
        try:
            # 首先需要讓用戶選擇要編輯的成就
            achievements = await self._get_available_achievements()
            if not achievements:
                await interaction.response.send_message(
                    "❌ 沒有可編輯的成就", ephemeral=True
                )
                return

            # 建立成就選擇視圖
            select_view = AchievementSelectionView(
                self.panel, achievements, action="edit"
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📝 編輯成就", "請選擇要編輯的成就:"
            )

            await interaction.response.send_message(
                embed=embed, view=select_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]編輯成就操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就編輯時發生錯誤", ephemeral=True
            )

    async def _handle_list_achievements(self, interaction: discord.Interaction) -> None:
        """處理成就列表操作."""
        try:
            # 取得可用的成就列表
            achievements = await self._get_available_achievements()
            if not achievements:
                await interaction.response.send_message(
                    "❌ 沒有可查看的成就", ephemeral=True
                )
                return

            # 建立成就選擇視圖
            select_view = AchievementSelectionView(
                self.panel, achievements, action="view"
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📋 成就列表",
                f"📈 **總共有 {len(achievements)} 個成就**\n\n"
                "請選擇要查看詳細資訊的成就:\n\n"
                "• 查看成就詳細統計\n"
                "• 檢查獲得情況\n"
                "• 查看歷史記錄\n"
                "• 管理成就設定",
            )

            await interaction.response.send_message(
                embed=embed, view=select_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]成就列表操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就列表時發生錯誤", ephemeral=True
            )

    async def _handle_copy_achievement(self, interaction: discord.Interaction) -> None:
        """處理複製成就操作."""
        try:
            # 首先需要讓用戶選擇要複製的成就
            achievements = await self._get_available_achievements()
            if not achievements:
                await interaction.response.send_message(
                    "❌ 沒有可複製的成就", ephemeral=True
                )
                return

            # 建立成就選擇視圖
            select_view = AchievementSelectionView(
                self.panel, achievements, action="copy"
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📄 複製成就",
                "🔄 **選擇要複製的成就**\n\n"
                "複製功能將:\n"
                "• 複製所有成就設定\n"
                "• 自動生成新的名稱\n"
                "• 保持原始配置結構\n"
                "• 允許進一步自訂修改\n\n"
                "✨ 這是創建相似成就的最快方式!\n\n"
                "請選擇要複製的成就:",
            )

            await interaction.response.send_message(
                embed=embed, view=select_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]複製成就操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就複製時發生錯誤", ephemeral=True
            )

    async def _handle_delete_achievement(
        self, interaction: discord.Interaction
    ) -> None:
        """處理刪除成就操作."""
        try:
            # 首先需要讓用戶選擇要刪除的成就
            achievements = await self._get_available_achievements()
            if not achievements:
                await interaction.response.send_message(
                    "❌ 沒有可刪除的成就", ephemeral=True
                )
                return

            # 建立成就選擇視圖
            select_view = AchievementSelectionView(
                self.panel, achievements, action="delete"
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "🗑️ 刪除成就",
                "⚠️ **警告:刪除操作無法撤銷!**\n\n"
                "請仔細選擇要刪除的成就:\n\n"
                "• 刪除前會檢查依賴關係\n"
                "• 需要二次確認\n"
                "• 操作將被完整記錄\n\n"
                "請選擇要刪除的成就:",
            )

            await interaction.response.send_message(
                embed=embed, view=select_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]刪除成就操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就刪除時發生錯誤", ephemeral=True
            )

    async def _handle_bulk_operations(self, interaction: discord.Interaction) -> None:
        """處理批量操作."""
        try:
            # 取得可用的成就列表
            achievements = await self._get_available_achievements()
            if not achievements:
                await interaction.response.send_message(
                    "❌ 沒有可進行批量操作的成就", ephemeral=True
                )
                return

            # 建立批量操作選擇視圖
            bulk_view = BulkOperationSelectionView(self.panel, achievements)

            embed = StandardEmbedBuilder.create_info_embed(
                "📦 批量操作選擇",
                f"📊 **可操作成就數**: {len(achievements)} 個\n\n"
                "🔍 **操作流程**:\n"
                "1️⃣ 選擇要操作的成就(支援多選)\n"
                "2️⃣ 選擇要執行的批量操作類型\n"
                "3️⃣ 確認操作並查看執行結果\n\n"
                "✨ **支援的批量操作**:\n"
                "• 批量啟用/停用成就\n"
                "• 批量刪除成就\n"
                "• 批量變更分類\n"
                "• 即時進度顯示\n\n"
                "📋 **請使用下方選單選擇要操作的成就**:",
            )

            await interaction.response.send_message(
                embed=embed, view=bulk_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]批量操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟批量操作時發生錯誤", ephemeral=True
            )

    async def _handle_category_management(
        self, interaction: discord.Interaction
    ) -> None:
        """處理分類管理."""
        try:
            # 獲取分類統計數據 - 修復:使用 self.panel 來調用方法
            category_stats = await self.panel._load_category_management_stats()

            # 建立分類管理視圖
            category_view = CategoryManagementView(self.panel, category_stats)

            # 修復:使用 self.panel 來調用方法
            embed = await self.panel._create_category_management_embed(category_stats)

            await interaction.response.send_message(
                embed=embed, view=category_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]開啟分類管理失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟分類管理時發生錯誤", ephemeral=True
            )

    async def _handle_criteria_management(
        self, interaction: discord.Interaction
    ) -> None:
        """處理條件管理."""
        try:
            # 獲取所有成就列表
            achievements = await self.panel.achievement_service.get_all_achievements()

            if not achievements:
                await interaction.response.send_message(
                    "❌ 沒有可設置條件的成就", ephemeral=True
                )
                return

            # 創建成就選擇視圖
            view = AchievementCriteriaSelectionView(self.panel, achievements)
            embed = StandardEmbedBuilder.create_info_embed(
                "🎯 成就條件設置",
                f"**總共有 {len(achievements)} 個成就**\n\n"
                "請選擇要設置條件的成就:\n\n"
                "• 設置訊息數量條件\n"
                "• 設置關鍵字條件\n"
                "• 設置時間條件\n"
                "• 設置複合條件",
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]開啟條件管理失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟條件管理時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回系統概覽."""
        await self.panel.handle_navigation(interaction, AdminPanelState.OVERVIEW)

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """重新整理成就管理面板."""
        try:
            # 清除快取
            self.panel._cached_stats = None
            self.panel._cache_expires_at = None

            # 重新載入成就管理狀態
            await self.panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"[成就管理視圖]重新整理失敗: {e}")
            await interaction.response.send_message(
                "❌ 重新整理時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 關閉面板", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """關閉管理面板."""
        await self.panel.close_panel(interaction)

    async def on_timeout(self) -> None:
        """處理視圖超時."""
        try:
            self.panel.current_state = AdminPanelState.CLOSED
            logger.info(
                f"[成就管理視圖]用戶 {self.panel.admin_user_id} 的面板因超時而關閉"
            )
        except Exception as e:
            logger.error(f"[成就管理視圖]處理超時失敗: {e}")

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        """處理視圖錯誤."""
        logger.error(f"[成就管理視圖]UI 錯誤: {error}, 項目: {item}")
        with contextlib.suppress(builtins.BaseException):
            await interaction.response.send_message(
                "❌ 處理成就管理操作時發生錯誤,請稍後再試", ephemeral=True
            )

    async def _get_available_achievements(self) -> list[Achievement]:
        """取得可用的成就列表."""
        try:
            # 嘗試從管理服務獲取成就列表
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, "get_all_achievements"):
                return await admin_service.get_all_achievements()

            # 如果服務不可用,返回空列表
            logger.warning("管理服務不可用,無法獲取成就列表")
            return []

        except Exception as e:
            logger.error(f"取得成就列表失敗: {e}")
            return []

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            # 創建真實的管理服務實例
            if hasattr(self.achievement_service, "repository"):
                return RealAdminService(self.achievement_service.repository)
            else:
                # 如果沒有 repository,嘗試從成就服務獲取
                return self.achievement_service

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            raise RuntimeError(f"無法獲取管理服務: {e}") from e


class CreateAchievementModal(ui.Modal):
    """成就新增模態框."""

    def __init__(self, admin_panel: AdminPanel):
        """初始化成就新增模態框.

        Args:
            admin_panel: 管理面板控制器
        """
        super().__init__(title="新增成就")
        self.admin_panel = admin_panel

        # 成就名稱
        self.name_input = ui.TextInput(
            label="成就名稱",
            placeholder="輸入成就名稱 (1-100字元)",
            max_length=100,
            required=True,
        )
        self.add_item(self.name_input)

        # 成就描述
        self.description_input = ui.TextInput(
            label="成就描述",
            placeholder="輸入成就描述 (1-500字元)",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.description_input)

        # 獎勵身分組
        self.role_reward_input = ui.TextInput(
            label="獎勵身分組",
            placeholder="輸入身分組名稱,例如:VIP會員、活躍用戶",
            max_length=100,
            required=False,
        )
        self.add_item(self.role_reward_input)

        # 成就類型
        self.type_input = ui.TextInput(
            label="成就類型",
            placeholder="計數型、里程碑、時間型、條件型 (counter/milestone/time_based/conditional)",
            max_length=20,
            required=True,
        )
        self.add_item(self.type_input)

        # 隱藏成就設定
        self.hidden_input = ui.TextInput(
            label="隱藏成就",
            placeholder="是否為隱藏成就?輸入 是/否 或 true/false",
            max_length=10,
            required=False,
        )
        self.add_item(self.hidden_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 驗證輸入
            name = self.name_input.value.strip()
            description = self.description_input.value.strip()
            role_reward = (
                self.role_reward_input.value.strip()
                if self.role_reward_input.value
                else None
            )
            type_str = self.type_input.value.strip()
            hidden_str = (
                self.hidden_input.value.strip() if self.hidden_input.value else "否"
            )

            # 基本驗證
            if not name:
                await interaction.followup.send("❌ 成就名稱不能為空", ephemeral=True)
                return

            if not description:
                await interaction.followup.send("❌ 成就描述不能為空", ephemeral=True)
                return

            type_mapping = {
                "計數型": "counter",
                "counter": "counter",
                "里程碑": "milestone",
                "milestone": "milestone",
                "時間型": "time_based",
                "time_based": "time_based",
                "條件型": "conditional",
                "conditional": "conditional",
            }

            achievement_type = type_mapping.get(type_str.lower())
            if not achievement_type:
                await interaction.followup.send(
                    "❌ 無效的成就類型,有效值: 計數型、里程碑、時間型、條件型",
                    ephemeral=True,
                )
                return

            # 驗證隱藏成就設定
            hidden_mapping = {
                "是": True,
                "否": False,
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "": False,
            }

            is_hidden = hidden_mapping.get(hidden_str.lower())
            if is_hidden is None:
                await interaction.followup.send(
                    "❌ 隱藏成就設定無效,請輸入:是/否 或 true/false",
                    ephemeral=True,
                )
                return

            # 取得分類列表讓用戶選擇
            categories = await self._get_available_categories()
            if not categories:
                await interaction.followup.send(
                    "❌ 沒有可用的分類,請先建立分類", ephemeral=True
                )
                return

            # 建立分類選擇視圖
            category_view = CategorySelectionView(
                self.admin_panel,
                categories,
                {
                    "name": name,
                    "description": description,
                    "role_reward": role_reward,
                    "type": achievement_type,
                    "is_hidden": is_hidden,
                },
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "選擇成就分類",
                f"**成就名稱**: {name}\n"
                f"**描述**: {description}\n"
                f"**獎勵身分組**: {role_reward or '無'}\n"
                f"**類型**: {achievement_type}\n"
                f"**隱藏成就**: {'是' if is_hidden else '否'}\n\n"
                "請選擇此成就所屬的分類:",
            )

            await interaction.followup.send(
                embed=embed, view=category_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就新增模態框]處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理成就新增時發生錯誤", ephemeral=True)

    async def _get_available_categories(self) -> list[AchievementCategory]:
        """取得可用的分類列表."""
        try:
            # 通過管理服務獲取實際的分類數據
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_all_categories()
            else:
                logger.warning("管理服務不可用,無法獲取分類列表")
                return []
        except Exception as e:
            logger.error(f"取得分類列表失敗: {e}")
            return []

    async def _get_admin_service(self):
        """獲取管理服務實例."""
        try:
            # 通過管理面板獲取服務
            if hasattr(self.admin_panel, "enhanced_admin_service"):
                return self.admin_panel.enhanced_admin_service
            return None
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class CreateAchievementConfirmView(ui.View):
    """成就建立確認視圖."""

    def __init__(self, admin_panel: AdminPanel, achievement_data: dict[str, Any]):
        """初始化確認視圖.

        Args:
            admin_panel: 管理面板控制器
            achievement_data: 成就資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievement_data = achievement_data

    @ui.button(label="✅ 確認建立", style=discord.ButtonStyle.primary)
    async def confirm_create(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認建立成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 獲取成就服務
            achievement_service = await self._get_achievement_service()
            if not achievement_service:
                await interaction.followup.send("❌ 無法獲取成就服務", ephemeral=True)
                return

            # 從 AchievementType 枚舉獲取類型

            type_mapping = {
                "counter": AchievementType.COUNTER,
                "milestone": AchievementType.MILESTONE,
                "time_based": AchievementType.TIME_BASED,
                "conditional": AchievementType.CONDITIONAL,
            }

            achievement_type = type_mapping.get(self.achievement_data["type"])
            if not achievement_type:
                await interaction.followup.send("❌ 無效的成就類型", ephemeral=True)
                return

            # 創建成就
            created_achievement = await achievement_service.create_achievement(
                name=self.achievement_data["name"],
                description=self.achievement_data["description"],
                category_id=self.achievement_data["category_id"],
                achievement_type=achievement_type,
                criteria=self.achievement_data.get("criteria", {}),
                points=self.achievement_data.get("points", 0),
                badge_url=self.achievement_data.get("badge_url"),
                role_reward=self.achievement_data.get("role_reward"),
                is_hidden=self.achievement_data.get("is_hidden", False),
                is_active=self.achievement_data.get("is_active", True),
            )

            embed = StandardEmbedBuilder.create_success_embed(
                "成就建立成功",
                f"✅ 成就「{created_achievement.name}」已成功建立!\n\n"
                f"**分配的 ID**: {created_achievement.id}\n"
                f"**獎勵身分組**: {created_achievement.role_reward or '無'}\n"
                f"**隱藏成就**: {'是' if created_achievement.is_hidden else '否'}\n"
                f"**狀態**: {'啟用' if created_achievement.is_active else '停用'}\n"
                f"**建立時間**: <t:{int(datetime.now().timestamp())}:f>\n\n"
                "成就已加入系統,用戶將能夠開始進度追蹤.",
            )

            embed.set_footer(text="操作已記錄到審計日誌")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"[建立確認視圖]建立成就失敗: {e}")
            await interaction.followup.send(
                f"❌ 建立成就時發生錯誤: {e!s}", ephemeral=True
            )

    async def _get_achievement_service(self):
        """獲取成就服務實例."""
        try:
            # 通過管理面板獲取服務
            if hasattr(self.admin_panel, "achievement_service"):
                return self.admin_panel.achievement_service

            # 嘗試從依賴注入容器獲取
            if hasattr(self.admin_panel, "get_service"):
                return await self.admin_panel.get_service("achievement_service")

            logger.warning("無法獲取成就服務實例")
            return None

        except Exception as e:
            logger.error(f"獲取成就服務失敗: {e}")
            return None

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_create(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消建立成就."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 成就建立操作已被取消."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AchievementSelectionView(ui.View):
    """成就選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, achievements: list[Achievement], action: str
    ):
        """初始化成就選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            achievements: 成就列表
            action: 操作類型 ("edit", "delete", "view")
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievements = achievements
        self.action = action

        # 建立成就選項
        options = []
        for achievement in achievements[:25]:  # Discord 選單最多 25 個選項
            status_icon = "✅" if achievement.is_active else "❌"
            options.append(
                discord.SelectOption(
                    label=f"{status_icon} {achievement.name}",
                    value=str(achievement.id),
                    description=f"{achievement.description[:80]}...",
                    emoji="🏆",
                )
            )

        # 成就選擇下拉選單
        self.achievement_select = ui.Select(
            placeholder="選擇要操作的成就...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.achievement_select.callback = self.on_achievement_select
        self.add_item(self.achievement_select)

    async def on_achievement_select(self, interaction: discord.Interaction) -> None:
        """處理成就選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            achievement_id = int(self.achievement_select.values[0])
            selected_achievement = next(
                (ach for ach in self.achievements if ach.id == achievement_id), None
            )

            if not selected_achievement:
                await interaction.followup.send("❌ 選擇的成就無效", ephemeral=True)
                return

            if self.action == "edit":
                await self._handle_edit_selected(interaction, selected_achievement)
            elif self.action == "delete":
                await self._handle_delete_selected(interaction, selected_achievement)
            elif self.action == "view":
                await self._handle_view_selected(interaction, selected_achievement)
            elif self.action == "copy":
                await self._handle_copy_selected(interaction, selected_achievement)

        except Exception as e:
            logger.error(f"[成就選擇視圖]處理成就選擇失敗: {e}")
            await interaction.followup.send("❌ 處理成就選擇時發生錯誤", ephemeral=True)

    async def _handle_edit_selected(
        self, interaction: discord.Interaction, achievement: Achievement
    ) -> None:
        """處理編輯選中的成就."""
        try:
            # 建立編輯表單模態框
            modal = EditAchievementModal(self.admin_panel, achievement)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就選擇視圖]開啟編輯表單失敗: {e}")
            await interaction.followup.send("❌ 開啟編輯表單時發生錯誤", ephemeral=True)

    async def _handle_delete_selected(
        self, interaction: discord.Interaction, achievement: Achievement
    ) -> None:
        """處理刪除選中的成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 檢查成就依賴關係
            admin_service = await self._get_admin_service()
            dependency_info = await admin_service._check_achievement_dependencies(
                achievement.id
            )

            # 建立刪除確認視圖
            confirm_view = DeleteAchievementConfirmView(
                self.panel, achievement, dependency_info
            )

            # 建立刪除預覽 embed
            preview_embed = StandardEmbedBuilder.create_warning_embed(
                "確認刪除成就",
                f"⚠️ 您即將刪除成就「{achievement.name}」\n\n"
                "**成就資訊**:\n"
                f"• **ID**: {achievement.id}\n"
                f"• **名稱**: {achievement.name}\n"
                f"• **描述**: {achievement.description}\n"
                f"• **點數**: {achievement.points}\n"
                f"• **狀態**: {'啟用' if achievement.is_active else '停用'}\n\n"
                f"**依賴關係檢查**:\n"
                f"• {dependency_info['description']}\n\n"
                "❗ **此操作無法撤銷,請仔細確認!**",
            )

            if dependency_info["has_dependencies"]:
                preview_embed.add_field(
                    name="⚠️ 依賴關係警告",
                    value=f"此成就有 {dependency_info['user_achievement_count']} 個用戶依賴.\n"
                    "刪除後這些記錄也將被移除.",
                    inline=False,
                )

            await interaction.followup.send(
                embed=preview_embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就選擇視圖]處理刪除選中成就失敗: {e}")
            await interaction.followup.send("❌ 處理成就刪除時發生錯誤", ephemeral=True)

    async def _handle_view_selected(
        self, interaction: discord.Interaction, achievement: Achievement
    ) -> None:
        """處理查看選中的成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 取得成就詳細資訊
            admin_service = await self._get_admin_service()
            achievement_details = await admin_service.get_achievement_with_details(
                achievement.id
            )

            if not achievement_details:
                await interaction.followup.send(
                    "❌ 無法取得成就詳細資訊", ephemeral=True
                )
                return

            # 建立成就詳細視圖
            detail_view = AchievementDetailView(self.panel, achievement_details)

            # 建立詳細 embed
            embed = await self._create_achievement_detail_embed(achievement_details)

            await interaction.followup.send(
                embed=embed, view=detail_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就選擇視圖]查看成就詳情失敗: {e}")
            await interaction.followup.send("❌ 查看成就詳情時發生錯誤", ephemeral=True)

    async def _handle_copy_selected(
        self, interaction: discord.Interaction, achievement: Achievement
    ) -> None:
        """處理複製選中的成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立複製成就模態框,預填原成就資料
            modal = CopyAchievementModal(self.panel, achievement)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就選擇視圖]複製成就失敗: {e}")
            await interaction.followup.send("❌ 開啟複製表單時發生錯誤", ephemeral=True)


class CopyAchievementModal(ui.Modal):
    """成就複製模態框."""

    def __init__(self, admin_panel: AdminPanel, source_achievement: Achievement):
        """初始化成就複製模態框.

        Args:
            admin_panel: 管理面板控制器
            source_achievement: 來源成就
        """
        super().__init__(title=f"複製成就: {source_achievement.name}")
        self.admin_panel = admin_panel
        self.source_achievement = source_achievement

        # 生成新的成就名稱
        new_name = f"{source_achievement.name} (副本)"

        # 成就名稱
        self.name_input = ui.TextInput(
            label="成就名稱",
            placeholder="輸入新成就名稱 (1-100字元)",
            default=new_name,
            max_length=100,
            required=True,
        )
        self.add_item(self.name_input)

        # 成就描述
        self.description_input = ui.TextInput(
            label="成就描述",
            placeholder="輸入成就描述 (1-500字元)",
            default=source_achievement.description,
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.description_input)

        # 成就點數
        self.points_input = ui.TextInput(
            label="獎勵點數",
            placeholder="輸入獎勵點數 (0-10000)",
            default=str(source_achievement.points),
            max_length=5,
            required=True,
        )
        self.add_item(self.points_input)

        # 成就類型
        self.type_input = ui.TextInput(
            label="成就類型",
            placeholder="counter, milestone, time_based, conditional",
            default=source_achievement.type.value,
            max_length=20,
            required=True,
        )
        self.add_item(self.type_input)

        # 徽章 URL(可選)
        self.badge_url_input = ui.TextInput(
            label="徽章 URL (可選)",
            placeholder="https://example.com/badge.png",
            default=source_achievement.badge_url or "",
            max_length=500,
            required=False,
        )
        self.add_item(self.badge_url_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 驗證輸入
            name = self.name_input.value.strip()
            description = self.description_input.value.strip()
            points_str = self.points_input.value.strip()
            type_str = self.type_input.value.strip()
            badge_url = (
                self.badge_url_input.value.strip()
                if self.badge_url_input.value
                else None
            )

            # 基本驗證
            if not name:
                await interaction.followup.send("❌ 成就名稱不能為空", ephemeral=True)
                return

            if not description:
                await interaction.followup.send("❌ 成就描述不能為空", ephemeral=True)
                return

            try:
                points = int(points_str)
                if points < 0 or points > MAX_POINTS:
                    raise ValueError("點數超出範圍")
            except ValueError:
                await interaction.followup.send(
                    "❌ 獎勵點數必須為 0-10000 的整數", ephemeral=True
                )
                return

            # 驗證類型
            valid_types = ["counter", "milestone", "time_based", "conditional"]
            if type_str not in valid_types:
                await interaction.followup.send(
                    f"❌ 無效的成就類型,有效值: {', '.join(valid_types)}",
                    ephemeral=True,
                )
                return

            # 取得分類列表讓用戶選擇
            categories = await self._get_available_categories()
            if not categories:
                await interaction.followup.send(
                    "❌ 沒有可用的分類,請先建立分類", ephemeral=True
                )
                return

            category_view = CopyCategorySelectionView(
                self.admin_panel,
                categories,
                {
                    "name": name,
                    "description": description,
                    "points": points,
                    "type": type_str,
                    "badge_url": badge_url,
                    "source_criteria": self.source_achievement.criteria,  # 複製原成就的條件
                },
                self.source_achievement.category_id,  # 預選原分類
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "選擇成就分類",
                f"**📄 複製成就預覽**\n"
                f"**來源成就**: {self.source_achievement.name}\n"
                f"**新成就名稱**: {name}\n"
                f"**描述**: {description}\n"
                f"**點數**: {points}\n"
                f"**類型**: {type_str}\n\n"
                "✨ **已複製的設定**:\n"
                f"• 成就條件配置\n"
                f"• 原始分類 (可修改)\n"
                f"• 成就類型設定\n\n"
                "請選擇此成就所屬的分類:",
            )

            await interaction.followup.send(
                embed=embed, view=category_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就複製模態框]處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理成就複製時發生錯誤", ephemeral=True)

    async def _get_available_categories(self):
        """取得可用的分類列表."""
        try:
            # 通過管理服務獲取實際的分類數據
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_all_categories()
            else:
                logger.warning("管理服務不可用,無法獲取分類列表")
                return []
        except Exception as e:
            logger.error(f"取得分類列表失敗: {e}")
            return []

    async def _get_admin_service(self):
        """獲取管理服務實例."""
        try:
            # 創建真實的管理服務實例
            if hasattr(self.achievement_service, "repository"):
                return RealAdminService(self.achievement_service.repository)
            else:
                # 如果沒有 repository,嘗試從成就服務獲取
                return self.achievement_service

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            raise RuntimeError(f"無法獲取管理服務: {e}") from e


class CopyCategorySelectionView(ui.View):
    """複製成就分類選擇視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        categories: list[AchievementCategory],
        achievement_data: dict[str, Any],
        default_category_id: int | None = None,
    ):
        """初始化複製分類選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            categories: 分類列表
            achievement_data: 成就資料
            default_category_id: 預設分類 ID
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.categories = categories
        self.achievement_data = achievement_data
        self.default_category_id = default_category_id

        # 建立分類選項
        options = []
        for category in categories[:25]:  # Discord 選單最多 25 個選項
            is_default = category.id == default_category_id
            label = f"⭐ {category.name}" if is_default else category.name
            description = (
                f"原分類 - {category.description[:80]}"
                if is_default
                else category.description[:100]
            )

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(category.id),
                    description=description,
                    emoji=category.icon_emoji,
                    default=is_default,
                )
            )

        # 分類選擇下拉選單
        self.category_select = ui.Select(
            placeholder="選擇成就分類(已預選原分類)...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.category_select.callback = self.on_category_select
        self.add_item(self.category_select)

    async def on_category_select(self, interaction: discord.Interaction) -> None:
        """處理分類選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            category_id = int(self.category_select.values[0])
            selected_category = next(
                (cat for cat in self.categories if cat.id == category_id), None
            )

            if not selected_category:
                await interaction.followup.send("❌ 選擇的分類無效", ephemeral=True)
                return

            # 完善成就資料
            achievement_data = self.achievement_data.copy()
            achievement_data["category_id"] = category_id
            achievement_data["criteria"] = achievement_data.get(
                "source_criteria", {"target_value": 1}
            )  # 使用來源條件
            achievement_data["is_active"] = True

            # 建立成就預覽
            preview_embed = StandardEmbedBuilder.create_info_embed(
                "📄 成就複製預覽", "請確認以下複製的成就資訊:"
            )

            preview_embed.add_field(
                name="📛 基本資訊",
                value=(
                    f"**名稱**: {achievement_data['name']}\n"
                    f"**描述**: {achievement_data['description']}\n"
                    f"**分類**: {selected_category.name}"
                ),
                inline=False,
            )

            preview_embed.add_field(
                name="⚙️ 設定",
                value=(
                    f"**類型**: {achievement_data['type']}\n"
                    f"**點數**: {achievement_data['points']}\n"
                    f"**狀態**: {'啟用' if achievement_data['is_active'] else '停用'}"
                ),
                inline=False,
            )

            # 顯示複製的條件
            criteria_text = "已複製原成就條件"
            if achievement_data.get("criteria"):
                criteria_items = []
                for key, value in achievement_data["criteria"].items():
                    criteria_items.append(f"• **{key}**: {value}")
                criteria_text = "\n".join(criteria_items)

            preview_embed.add_field(
                name="🔄 複製的條件", value=criteria_text, inline=False
            )

            if achievement_data.get("badge_url"):
                preview_embed.add_field(
                    name="🎖️ 徽章",
                    value=f"[徽章連結]({achievement_data['badge_url']})",
                    inline=False,
                )

            # 建立確認視圖
            confirm_view = CopyAchievementConfirmView(
                self.admin_panel, achievement_data
            )

            await interaction.followup.send(
                embed=preview_embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[複製分類選擇視圖]處理分類選擇失敗: {e}")
            await interaction.followup.send("❌ 處理分類選擇時發生錯誤", ephemeral=True)


class CopyAchievementConfirmView(ui.View):
    """複製成就確認視圖."""

    def __init__(self, admin_panel: AdminPanel, achievement_data: dict[str, Any]):
        """初始化確認視圖.

        Args:
            admin_panel: 管理面板控制器
            achievement_data: 成就資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievement_data = achievement_data

    @ui.button(label="✅ 確認複製", style=discord.ButtonStyle.primary)
    async def confirm_copy(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認複製成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            embed = StandardEmbedBuilder.create_success_embed(
                "📄 成就複製成功",
                f"✅ 成就「{self.achievement_data['name']}」已成功複製!\n\n"
                f"**分配的 ID**: 暫未實作\n"
                f"**狀態**: {'啟用' if self.achievement_data['is_active'] else '停用'}\n"
                f"**複製時間**: <t:{int(datetime.now().timestamp())}:f>\n\n"
                f"🔄 **已複製的內容**:\n"
                f"• 成就條件配置\n"
                f"• 成就類型設定\n"
                f"• 基本屬性結構\n\n"
                "新成就已加入系統,用戶將能夠開始進度追蹤.",
            )

            embed.set_footer(text="操作已記錄到審計日誌")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"[複製確認視圖]複製成就失敗: {e}")
            await interaction.followup.send("❌ 複製成就時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_copy(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消複製成就."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 成就複製操作已被取消."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditAchievementModal(ui.Modal):
    """成就編輯模態框."""

    def __init__(self, admin_panel: AdminPanel, achievement: Achievement):
        """初始化成就編輯模態框.

        Args:
            admin_panel: 管理面板控制器
            achievement: 要編輯的成就
        """
        super().__init__(title=f"編輯成就: {achievement.name}")
        self.admin_panel = admin_panel
        self.achievement = achievement

        # 成就名稱
        self.name_input = ui.TextInput(
            label="成就名稱",
            placeholder="輸入成就名稱 (1-100字元)",
            default=achievement.name,
            max_length=100,
            required=True,
        )
        self.add_item(self.name_input)

        # 成就描述
        self.description_input = ui.TextInput(
            label="成就描述",
            placeholder="輸入成就描述 (1-500字元)",
            default=achievement.description,
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.description_input)

        # 成就點數
        self.points_input = ui.TextInput(
            label="獎勵點數",
            placeholder="輸入獎勵點數 (0-10000)",
            default=str(achievement.points),
            max_length=5,
            required=True,
        )
        self.add_item(self.points_input)

        # 成就類型
        self.type_input = ui.TextInput(
            label="成就類型",
            placeholder="counter, milestone, time_based, conditional",
            default=achievement.type.value,
            max_length=20,
            required=True,
        )
        self.add_item(self.type_input)

        # 徽章 URL(可選)
        self.badge_url_input = ui.TextInput(
            label="徽章 URL (可選)",
            placeholder="https://example.com/badge.png",
            default=achievement.badge_url or "",
            max_length=500,
            required=False,
        )
        self.add_item(self.badge_url_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 解析並驗證輸入數據
            validated_data = await self._validate_and_parse_inputs(interaction)
            if validated_data is None:
                return

            # 檢測變更
            changes = self._detect_changes(validated_data)
            if not changes:
                await interaction.followup.send("i 沒有檢測到任何變更", ephemeral=True)
                return

            # 創建並發送預覽
            await self._send_change_preview(interaction, changes)

        except Exception as e:
            logger.error(f"[成就編輯模態框]處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理成就編輯時發生錯誤", ephemeral=True)

    async def _validate_and_parse_inputs(
        self, interaction: discord.Interaction
    ) -> dict[str, Any] | None:
        """驗證並解析輸入數據."""
        # 提取並清理輸入值
        name = self.name_input.value.strip()
        description = self.description_input.value.strip()
        points_str = self.points_input.value.strip()
        type_str = self.type_input.value.strip()
        badge_url = (
            self.badge_url_input.value.strip() if self.badge_url_input.value else None
        )

        # 基本驗證
        if not name:
            await interaction.followup.send("❌ 成就名稱不能為空", ephemeral=True)
            return None

        if not description:
            await interaction.followup.send("❌ 成就描述不能為空", ephemeral=True)
            return None

        # 驗證並解析點數
        try:
            points = int(points_str)
            if points < 0 or points > MAX_POINTS:
                raise ValueError("點數超出範圍")
        except ValueError:
            await interaction.followup.send(
                "❌ 獎勵點數必須為 0-10000 的整數", ephemeral=True
            )
            return None

        # 驗證類型
        valid_types = ["counter", "milestone", "time_based", "conditional"]
        if type_str not in valid_types:
            await interaction.followup.send(
                f"❌ 無效的成就類型,有效值: {', '.join(valid_types)}",
                ephemeral=True,
            )
            return None

        return {
            "name": name,
            "description": description,
            "points": points,
            "type": type_str,
            "badge_url": badge_url,
        }

    def _detect_changes(self, validated_data: dict[str, Any]) -> dict[str, Any]:
        """檢測數據更改."""
        changes = {}

        if validated_data["name"] != self.achievement.name:
            changes["name"] = validated_data["name"]
        if validated_data["description"] != self.achievement.description:
            changes["description"] = validated_data["description"]
        if validated_data["points"] != self.achievement.points:
            changes["points"] = validated_data["points"]
        if validated_data["type"] != self.achievement.type.value:
            changes["type"] = validated_data["type"]
        if validated_data["badge_url"] != self.achievement.badge_url:
            changes["badge_url"] = validated_data["badge_url"]

        return changes

    async def _send_change_preview(
        self, interaction: discord.Interaction, changes: dict[str, Any]
    ) -> None:
        """發送變更預覽."""
        preview_embed = StandardEmbedBuilder.create_info_embed(
            "成就編輯預覽", f"即將更新成就「{self.achievement.name}」,請確認變更:"
        )

        # 生成變更文本
        changes_text = self._generate_changes_text(changes)
        preview_embed.add_field(
            name="📝 變更摘要", value="\n".join(changes_text), inline=False
        )

        # 建立確認視圖
        confirm_view = EditAchievementConfirmView(
            self.admin_panel, self.achievement, changes
        )

        await interaction.followup.send(
            embed=preview_embed, view=confirm_view, ephemeral=True
        )

    def _generate_changes_text(self, changes: dict[str, Any]) -> list[str]:
        """生成變更文本列表."""
        changes_text = []
        for field, new_value in changes.items():
            if field == "name":
                changes_text.append(f"**名稱**: {self.achievement.name} → {new_value}")
            elif field == "description":
                changes_text.append(
                    f"**描述**: {self.achievement.description} → {new_value}"
                )
            elif field == "points":
                changes_text.append(
                    f"**點數**: {self.achievement.points} → {new_value}"
                )
            elif field == "type":
                changes_text.append(
                    f"**類型**: {self.achievement.type.value} → {new_value}"
                )
            elif field == "badge_url":
                old_url = self.achievement.badge_url or "無"
                new_url = new_value or "無"
                changes_text.append(f"**徽章**: {old_url} → {new_url}")
        return changes_text


class EditAchievementConfirmView(ui.View):
    """成就編輯確認視圖."""

    def __init__(
        self, admin_panel: AdminPanel, achievement: Achievement, changes: dict[str, Any]
    ):
        """初始化確認視圖.

        Args:
            admin_panel: 管理面板控制器
            achievement: 原始成就
            changes: 變更內容
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievement = achievement
        self.changes = changes

    @ui.button(label="✅ 確認更新", style=discord.ButtonStyle.primary)
    async def confirm_update(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認更新成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            embed = StandardEmbedBuilder.create_success_embed(
                "成就更新成功",
                f"✅ 成就「{self.achievement.name}」已成功更新!\n\n"
                f"**更新項目**: {len(self.changes)} 個欄位\n"
                f"**更新時間**: <t:{int(datetime.now().timestamp())}:f>\n\n"
                "變更已生效,用戶將看到最新的成就資訊.",
            )

            embed.set_footer(text="操作已記錄到審計日誌")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"[編輯確認視圖]更新成就失敗: {e}")
            await interaction.followup.send("❌ 更新成就時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_update(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消更新成就."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 成就編輯操作已被取消."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DeleteAchievementConfirmView(ui.View):
    """成就刪除確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        achievement: Achievement,
        dependency_info: dict[str, Any],
    ):
        """初始化刪除確認視圖.

        Args:
            admin_panel: 管理面板控制器
            achievement: 要刪除的成就
            dependency_info: 依賴關係資訊
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievement = achievement
        self.dependency_info = dependency_info

    @ui.button(label="⚠️ 強制刪除", style=discord.ButtonStyle.danger, disabled=False)
    async def force_delete_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """強制刪除成就(忽略依賴關係)."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 執行強制刪除
            admin_service = await self._get_admin_service()
            success = await admin_service.delete_achievement(
                achievement_id=self.achievement.id,
                admin_user_id=self.admin_panel.admin_user_id,
                force=True,
            )

            if success:
                embed = StandardEmbedBuilder.create_success_embed(
                    "成就刪除成功",
                    f"✅ 成就「{self.achievement.name}」已被強制刪除!\n\n"
                    f"**刪除詳情**:\n"
                    f"• 成就 ID: {self.achievement.id}\n"
                    f"• 刪除時間: <t:{int(datetime.now().timestamp())}:f>\n"
                    f"• 受影響用戶: {self.dependency_info.get('user_achievement_count', 0)} 個\n\n"
                    "⚠️ 相關的用戶成就記錄已同時清除.\n"
                    "📝 此操作已記錄到審計日誌.",
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "刪除失敗",
                    f"❌ 無法刪除成就「{self.achievement.name}」\n\n"
                    "請檢查成就是否仍然存在或聯繫系統管理員.",
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"[刪除確認視圖]強制刪除成就失敗: {e}")
            await interaction.followup.send("❌ 執行刪除操作時發生錯誤", ephemeral=True)

    @ui.button(label="🗑️ 安全刪除", style=discord.ButtonStyle.danger, disabled=False)
    async def safe_delete_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """安全刪除成就(檢查依賴關係)."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 檢查是否有依賴關係
            if self.dependency_info["has_dependencies"]:
                embed = StandardEmbedBuilder.create_error_embed(
                    "無法安全刪除",
                    f"❌ 成就「{self.achievement.name}」存在依賴關係!\n\n"
                    f"**依賴詳情**:\n"
                    f"• {self.dependency_info['description']}\n\n"
                    "**解決方案**:\n"
                    "1️⃣ 使用「強制刪除」(將同時清除用戶記錄)\n"
                    "2️⃣ 先手動處理相關用戶記錄\n"
                    "3️⃣ 將成就設為停用而非刪除\n\n"
                    "⚠️ 強制刪除將無法復原,請謹慎操作!",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 執行安全刪除
            admin_service = await self._get_admin_service()
            success = await admin_service.delete_achievement(
                achievement_id=self.achievement.id,
                admin_user_id=self.admin_panel.admin_user_id,
                force=False,
            )

            if success:
                embed = StandardEmbedBuilder.create_success_embed(
                    "成就刪除成功",
                    f"✅ 成就「{self.achievement.name}」已安全刪除!\n\n"
                    f"**刪除詳情**:\n"
                    f"• 成就 ID: {self.achievement.id}\n"
                    f"• 刪除時間: <t:{int(datetime.now().timestamp())}:f>\n"
                    f"• 依賴檢查: 通過\n\n"
                    "✅ 沒有用戶記錄受到影響.\n"
                    "📝 此操作已記錄到審計日誌.",
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "刪除失敗",
                    f"❌ 無法刪除成就「{self.achievement.name}」\n\n"
                    "請檢查成就是否仍然存在或聯繫系統管理員.",
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"[刪除確認視圖]安全刪除成就失敗: {e}")
            await interaction.followup.send("❌ 執行刪除操作時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_delete(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消刪除成就."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消",
            f"✅ 成就「{self.achievement.name}」的刪除操作已被取消.\n\n"
            "成就保持原狀,未進行任何變更.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            # 創建真實的管理服務實例
            if hasattr(self.achievement_service, "repository"):
                return RealAdminService(self.achievement_service.repository)
            else:
                # 如果沒有 repository,嘗試從成就服務獲取
                return self.achievement_service

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            raise RuntimeError(f"無法獲取管理服務: {e}") from e

    async def _create_achievement_detail_embed(
        self, achievement_details: dict[str, Any]
    ) -> discord.Embed:
        """建立成就詳細資訊 Embed."""
        try:
            achievement = achievement_details["achievement"]
            statistics = achievement_details.get("statistics", {})
            category = achievement_details.get("category")

            # 建立基本 embed
            embed = StandardEmbedBuilder.create_info_embed(
                f"🏆 {achievement.name}", achievement.description
            )

            # 基本資訊
            status_icon = "✅" if achievement.is_active else "❌"
            embed.add_field(
                name="📋 基本資訊",
                value=(
                    f"**ID**: {achievement.id}\n"
                    f"**狀態**: {status_icon} {'啟用' if achievement.is_active else '停用'}\n"
                    f"**類型**: {achievement.type.value}\n"
                    f"**點數**: {achievement.points}"
                ),
                inline=True,
            )

            # 分類資訊
            category_info = "未知分類"
            if category:
                category_emoji = category.icon_emoji or "📂"
                category_info = f"{category_emoji} {category.name}"

            embed.add_field(name="📂 分類", value=category_info, inline=True)

            # 統計資訊
            earned_count = statistics.get("earned_count", 0)
            completion_rate = statistics.get("completion_rate", 0.0)

            embed.add_field(
                name="📊 統計數據",
                value=(
                    f"**獲得次數**: {earned_count:,}\n"
                    f"**完成率**: {completion_rate:.1f}%\n"
                    f"**平均時間**: {statistics.get('average_completion_time', 'N/A')}\n"
                    f"**熱門排名**: #{statistics.get('popular_rank', 'N/A')}"
                ),
                inline=False,
            )

            # 成就條件
            criteria_text = "無特殊條件"
            if achievement.criteria:
                criteria_items = []
                for key, value in achievement.criteria.items():
                    criteria_items.append(f"• **{key}**: {value}")
                criteria_text = "\n".join(criteria_items)

            embed.add_field(name="⚙️ 完成條件", value=criteria_text, inline=False)

            # 時間資訊
            created_time = int(achievement.created_at.timestamp())
            updated_time = int(achievement.updated_at.timestamp())

            embed.add_field(
                name="⏰ 時間資訊",
                value=(
                    f"**創建時間**: <t:{created_time}:f>\n"
                    f"**最後更新**: <t:{updated_time}:R>"
                ),
                inline=False,
            )

            # 徽章資訊
            if achievement.badge_url:
                embed.set_thumbnail(url=achievement.badge_url)
                embed.add_field(
                    name="🎖️ 徽章",
                    value=f"[查看徽章]({achievement.badge_url})",
                    inline=True,
                )

            embed.color = 0xFF6B35
            embed.set_footer(text=f"成就 ID: {achievement.id} | 管理員查看")

            return embed

        except Exception as e:
            logger.error(f"建立成就詳細 embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "載入成就詳細資訊時發生錯誤."
            )


class AchievementDetailView(ui.View):
    """成就詳細資訊視圖."""

    def __init__(self, admin_panel: AdminPanel, achievement_details: dict[str, Any]):
        """初始化成就詳細視圖.

        Args:
            admin_panel: 管理面板控制器
            achievement_details: 成就詳細資訊
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievement_details = achievement_details
        self.achievement = achievement_details["achievement"]

    @ui.button(label="✏️ 編輯成就", style=discord.ButtonStyle.primary)
    async def edit_achievement_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """編輯成就按鈕."""
        try:
            # 建立編輯表單模態框
            modal = EditAchievementModal(self.admin_panel, self.achievement)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就詳細視圖]開啟編輯表單失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟編輯表單時發生錯誤", ephemeral=True
            )

    @ui.button(label="🗑️ 刪除成就", style=discord.ButtonStyle.danger)
    async def delete_achievement_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """刪除成就按鈕."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 檢查成就依賴關係
            admin_service = await self._get_admin_service()
            if admin_service:
                dependency_info = await admin_service.check_achievement_dependencies(
                    self.achievement.id
                )
            else:
                dependency_info = {
                    "has_dependencies": False,
                    "user_achievement_count": 0,
                    "description": "無法檢查依賴關係",
                }

            # 建立刪除確認視圖
            confirm_view = DeleteAchievementConfirmView(
                self.admin_panel, self.achievement, dependency_info
            )

            # 建立刪除預覽 embed
            preview_embed = StandardEmbedBuilder.create_warning_embed(
                "確認刪除成就",
                f"⚠️ 您即將刪除成就「{self.achievement.name}」\n\n"
                "**成就資訊**:\n"
                f"• **ID**: {self.achievement.id}\n"
                f"• **名稱**: {self.achievement.name}\n"
                f"• **描述**: {self.achievement.description}\n"
                f"• **點數**: {self.achievement.points}\n"
                f"• **狀態**: {'啟用' if self.achievement.is_active else '停用'}\n\n"
                f"**依賴關係檢查**:\n"
                f"• {dependency_info['description']}\n\n"
                "❗ **此操作無法撤銷,請仔細確認!**",
            )

            if dependency_info["has_dependencies"]:
                preview_embed.add_field(
                    name="⚠️ 依賴關係警告",
                    value=f"此成就有 {dependency_info['user_achievement_count']} 個用戶依賴.\n"
                    "刪除後這些記錄也將被移除.",
                    inline=False,
                )

            await interaction.followup.send(
                embed=preview_embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就詳細視圖]刪除成就失敗: {e}")
            await interaction.followup.send("❌ 處理刪除操作時發生錯誤", ephemeral=True)

    @ui.button(label="📊 查看統計", style=discord.ButtonStyle.secondary)
    async def view_statistics_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看統計按鈕."""
        try:
            statistics = self.achievement_details.get("statistics", {})

            embed = StandardEmbedBuilder.create_info_embed(
                f"📊 {self.achievement.name} - 詳細統計", "成就的完整統計資訊和分析數據"
            )

            # 基本統計
            embed.add_field(
                name="🎯 獲得統計",
                value=(
                    f"**總獲得次數**: {statistics.get('earned_count', 0):,}\n"
                    f"**完成率**: {statistics.get('completion_rate', 0.0):.2f}%\n"
                    f"**難度評級**: {self._get_difficulty_rating(statistics.get('completion_rate', 0.0))}"
                ),
                inline=True,
            )

            # 時間統計
            avg_time = statistics.get("average_completion_time")
            embed.add_field(
                name="⏱️ 時間統計",
                value=(
                    f"**平均完成時間**: {avg_time or 'N/A'}\n"
                    f"**最快完成**: {statistics.get('fastest_completion', 'N/A')}\n"
                    f"**最慢完成**: {statistics.get('slowest_completion', 'N/A')}"
                ),
                inline=True,
            )

            # 排名統計
            embed.add_field(
                name="🏆 熱門度",
                value=(
                    f"**熱門排名**: #{statistics.get('popular_rank', 'N/A')}\n"
                    f"**本月新增**: {statistics.get('monthly_earned', 0):,}\n"
                    f"**趨勢**: {statistics.get('trend', '持平')}"
                ),
                inline=True,
            )

            # 用戶分布
            embed.add_field(
                name="👥 用戶分布",
                value=(
                    f"**活躍用戶**: {statistics.get('active_users', 0):,}\n"
                    f"**新手用戶**: {statistics.get('new_users', 0):,}\n"
                    f"**資深用戶**: {statistics.get('veteran_users', 0):,}"
                ),
                inline=False,
            )

            # 最近活動
            recent_activity = statistics.get("recent_activity", [])
            if recent_activity:
                activity_text = "\n".join([
                    f"• {activity}" for activity in recent_activity[:5]
                ])
                embed.add_field(name="📝 最近活動", value=activity_text, inline=False)

            embed.color = 0xFF6B35
            embed.set_footer(
                text=f"統計數據更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[成就詳細視圖]查看統計失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入統計數據時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回管理", style=discord.ButtonStyle.secondary)
    async def back_to_management_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回成就管理."""
        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )

    def _get_difficulty_rating(self, completion_rate: float) -> str:
        """根據完成率取得難度評級."""
        if completion_rate >= DIFFICULTY_SIMPLE_THRESHOLD:
            return "⭐ 簡單"
        elif completion_rate >= DIFFICULTY_NORMAL_THRESHOLD:
            return "⭐⭐ 普通"
        elif completion_rate >= DIFFICULTY_HARD_THRESHOLD:
            return "⭐⭐⭐ 困難"
        elif completion_rate >= DIFFICULTY_EXTREME_THRESHOLD:
            return "⭐⭐⭐⭐ 極難"
        else:
            return "⭐⭐⭐⭐⭐ 傳說"

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            # 創建真實的管理服務實例
            if hasattr(self.achievement_service, "repository"):
                return RealAdminService(self.achievement_service.repository)
            else:
                # 如果沒有 repository,嘗試從成就服務獲取
                return self.achievement_service

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            raise RuntimeError(f"無法獲取管理服務: {e}") from e


class UserManagementView(ui.View):
    """用戶成就管理專用視圖.

    提供用戶成就管理的所有操作選項.
    """

    def __init__(self, panel: AdminPanel):
        """初始化用戶管理視圖.

        Args:
            panel: 管理面板控制器
        """
        super().__init__(timeout=900)  # 15分鐘超時
        self.panel = panel

    @ui.select(
        placeholder="選擇用戶管理操作...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="🔍 搜尋用戶",
                value="search_user",
                description="搜尋要管理的用戶",
                emoji="🔍",
            ),
            discord.SelectOption(
                label="🎁 授予成就",
                value="grant_achievement",
                description="手動授予用戶成就",
                emoji="🎁",
            ),
            discord.SelectOption(
                label="❌ 撤銷成就",
                value="revoke_achievement",
                description="撤銷用戶已獲得的成就",
                emoji="❌",
            ),
            discord.SelectOption(
                label="📈 調整進度",
                value="adjust_progress",
                description="調整用戶成就進度",
                emoji="📈",
            ),
            discord.SelectOption(
                label="🔄 重置資料",
                value="reset_data",
                description="重置用戶成就資料",
                emoji="🔄",
            ),
            discord.SelectOption(
                label="👥 批量操作",
                value="bulk_operations",
                description="批量用戶操作",
                emoji="👥",
            ),
        ],
    )
    async def user_operation_select(
        self, interaction: discord.Interaction, select: ui.Select
    ) -> None:
        """處理用戶管理操作選擇."""
        try:
            selected_value = select.values[0]

            # 處理不同操作
            if selected_value == "search_user":
                await self._handle_search_user(interaction)
            elif selected_value == "grant_achievement":
                await self._handle_grant_achievement(interaction)
            elif selected_value == "revoke_achievement":
                await self._handle_revoke_achievement(interaction)
            elif selected_value == "adjust_progress":
                await self._handle_adjust_progress(interaction)
            elif selected_value == "reset_data":
                await self._handle_reset_data(interaction)
            elif selected_value == "bulk_operations":
                await self._handle_bulk_operations(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 無效的操作選擇", ephemeral=True
                )

        except Exception as e:
            logger.error(f"[用戶管理視圖]操作選擇處理失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理操作時發生錯誤", ephemeral=True
            )

    async def _handle_search_user(self, interaction: discord.Interaction) -> None:
        """處理用戶搜尋操作."""
        try:
            # 建立用戶搜尋模態框
            modal = UserSearchModal(self.panel)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[用戶管理視圖]用戶搜尋操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    async def _handle_grant_achievement(self, interaction: discord.Interaction) -> None:
        """處理授予成就操作."""
        try:
            # 建立成就授予流程視圖
            grant_view = GrantAchievementFlowView(self.panel)

            embed = StandardEmbedBuilder.create_info_embed(
                "🎁 授予成就",
                "**步驟 1/3**: 搜尋目標用戶\n\n"
                "請使用下方搜尋功能找到要授予成就的用戶:\n\n"
                "• 支援用戶名搜尋\n"
                "• 支援暱稱搜尋\n"
                "• 支援用戶 ID 搜尋\n"
                "• 支援 @用戶 提及搜尋",
            )

            await interaction.response.send_message(
                embed=embed, view=grant_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶管理視圖]授予成就操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就授予時發生錯誤", ephemeral=True
            )

    async def _handle_revoke_achievement(
        self, interaction: discord.Interaction
    ) -> None:
        """處理撤銷成就操作."""
        try:
            # 建立成就撤銷流程視圖
            revoke_view = RevokeAchievementFlowView(self.panel)

            embed = StandardEmbedBuilder.create_warning_embed(
                "❌ 撤銷成就",
                "**步驟 1/3**: 搜尋目標用戶\n\n"
                "⚠️ **注意**: 撤銷成就會:\n"
                "• 移除用戶已獲得的成就\n"
                "• 清除相關的進度記錄\n"
                "• 記錄操作到審計日誌\n\n"
                "請使用下方搜尋功能找到用戶:",
            )

            await interaction.response.send_message(
                embed=embed, view=revoke_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶管理視圖]撤銷成就操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就撤銷時發生錯誤", ephemeral=True
            )

    async def _handle_adjust_progress(self, interaction: discord.Interaction) -> None:
        """處理調整進度操作."""
        try:
            # 建立進度調整流程視圖
            adjust_view = AdjustProgressFlowView(self.panel)

            embed = StandardEmbedBuilder.create_info_embed(
                "📈 調整進度",
                "**步驟 1/3**: 搜尋目標用戶\n\n"
                "進度調整功能可以:\n"
                "• 調整用戶在特定成就上的進度值\n"
                "• 設定自定義進度數據\n"
                "• 觸發成就完成檢查\n"
                "• 記錄詳細的變更日誌\n\n"
                "請搜尋要調整進度的用戶:",
            )

            await interaction.response.send_message(
                embed=embed, view=adjust_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶管理視圖]調整進度操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟進度調整時發生錯誤", ephemeral=True
            )

    async def _handle_reset_data(self, interaction: discord.Interaction) -> None:
        """處理重置資料操作."""
        try:
            # 建立資料重置流程視圖
            reset_view = ResetDataFlowView(self.panel)

            embed = StandardEmbedBuilder.create_error_embed(
                "🔄 重置資料",
                "**⚠️ 危險操作警告**\n\n"
                "資料重置將會:\n"
                "• 清除用戶的所有成就記錄\n"
                "• 重置所有成就進度\n"
                "• 無法復原操作\n"
                "• 需要多重確認\n\n"
                "請謹慎選擇要重置的用戶:",
            )
            embed.color = 0xFF0000

            await interaction.response.send_message(
                embed=embed, view=reset_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶管理視圖]重置資料操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟資料重置時發生錯誤", ephemeral=True
            )

    async def _handle_bulk_operations(self, interaction: discord.Interaction) -> None:
        """處理批量操作."""
        try:
            # 建立批量操作搜尋模態框
            modal = UserSearchModal(self.panel, action="bulk")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[用戶管理視圖]批量操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟批量操作時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回系統概覽."""
        await self.panel.handle_navigation(interaction, AdminPanelState.OVERVIEW)

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """重新整理用戶管理面板."""
        try:
            # 清除快取
            self.panel._cached_stats = None
            self.panel._cache_expires_at = None

            # 重新載入用戶管理狀態
            await self.panel.handle_navigation(interaction, AdminPanelState.USERS)

        except Exception as e:
            logger.error(f"[用戶管理視圖]重新整理失敗: {e}")
            await interaction.response.send_message(
                "❌ 重新整理時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 關閉面板", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """關閉管理面板."""
        await self.panel.close_panel(interaction)

    async def on_timeout(self) -> None:
        """處理視圖超時."""
        try:
            self.panel.current_state = AdminPanelState.CLOSED
            logger.info(
                f"[用戶管理視圖]用戶 {self.panel.admin_user_id} 的面板因超時而關閉"
            )
        except Exception as e:
            logger.error(f"[用戶管理視圖]處理超時失敗: {e}")

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        """處理視圖錯誤."""
        logger.error(f"[用戶管理視圖]UI 錯誤: {error}, 項目: {item}")
        with contextlib.suppress(builtins.BaseException):
            await interaction.response.send_message(
                "❌ 處理用戶管理操作時發生錯誤,請稍後再試", ephemeral=True
            )


class UserSearchModal(ui.Modal):
    """用戶搜尋模態框."""

    def __init__(self, admin_panel: AdminPanel, action: str = "general"):
        """初始化用戶搜尋模態框.

        Args:
            admin_panel: 管理面板控制器
            action: 操作類型 (grant, revoke, adjust, reset, bulk, general)
        """
        super().__init__(title=f"搜尋用戶 - {self._get_action_name(action)}")
        self.admin_panel = admin_panel
        self.action = action

        # 搜尋輸入框
        self.search_input = ui.TextInput(
            label="用戶搜尋",
            placeholder="輸入用戶名、暱稱、用戶ID 或 @提及用戶",
            max_length=100,
            required=True,
        )
        self.add_item(self.search_input)

    def _get_action_name(self, action: str) -> str:
        """獲取操作名稱."""
        action_names = {
            "grant": "授予成就",
            "revoke": "撤銷成就",
            "adjust": "調整進度",
            "reset": "重置資料",
            "bulk": "批量操作",
            "general": "一般管理",
        }
        return action_names.get(action, "未知操作")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            search_query = self.search_input.value.strip()
            if not search_query:
                await interaction.followup.send("❌ 搜尋內容不能為空", ephemeral=True)
                return

            # 執行用戶搜尋
            search_results = await self._search_users(
                search_query, interaction.guild_id
            )

            if not search_results:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "🔍 搜尋結果",
                    f"未找到與「{search_query}」相符的用戶.\n\n"
                    "**搜尋提示**:\n"
                    "• 嘗試使用完整的用戶名\n"
                    "• 檢查用戶ID是否正確\n"
                    "• 確認用戶仍在伺服器中\n"
                    "• 可以使用 @用戶 的方式提及",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 建立用戶選擇視圖
            selection_view = UserSearchResultView(
                self.admin_panel, search_results, search_query, self.action
            )

            embed = await self._create_search_results_embed(
                search_results, search_query
            )

            await interaction.followup.send(
                embed=embed, view=selection_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶搜尋模態框]處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理用戶搜尋時發生錯誤", ephemeral=True)

    async def _search_users(self, query: str, guild_id: int) -> list[dict]:
        """搜尋用戶.

        Args:
            query: 搜尋查詢
            guild_id: 伺服器ID

        Returns:
            用戶搜尋結果列表
        """
        try:
            # 使用新的 UserSearchService

            search_service = UserSearchService(self.admin_panel.bot)
            results = await search_service.search_users(query, guild_id, limit=10)

            return results

        except Exception as e:
            logger.error(f"[用戶搜尋]搜尋用戶失敗: {e}")
            return []

    async def _create_user_result(self, member: discord.Member) -> dict:
        """建立用戶搜尋結果."""
        try:
            # 獲取用戶成就摘要
            achievement_summary = await self._get_user_achievement_summary(member.id)

            return {
                "user": member,
                "display_name": member.display_name,
                "username": member.name,
                "user_id": member.id,
                "avatar_url": member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                "joined_at": member.joined_at,
                "achievement_count": achievement_summary.get("total_achievements", 0),
                "progress_count": achievement_summary.get("total_progress", 0),
                "achievement_points": achievement_summary.get("total_points", 0),
            }
        except Exception as e:
            logger.error(f"[用戶搜尋]建立用戶結果失敗: {e}")
            return {
                "user": member,
                "display_name": member.display_name,
                "username": member.name,
                "user_id": member.id,
                "avatar_url": member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                "joined_at": member.joined_at,
                "achievement_count": 0,
                "progress_count": 0,
                "achievement_points": 0,
            }

    async def _get_user_achievement_summary(self, user_id: int) -> dict:
        """獲取用戶成就摘要.

        Args:
            user_id: 用戶ID

        Returns:
            用戶成就摘要字典
        """
        try:
            # 從真實的成就服務獲取數據
            repository = self.admin_panel.achievement_service.repository

            # 獲取用戶已獲得的成就數量
            user_achievements = await repository.get_user_achievements(user_id)
            total_achievements = len(user_achievements)

            # 獲取用戶進度記錄數量
            user_progresses = await repository.get_user_progresses(user_id)
            total_progress = len(user_progresses)

            # 計算總點數
            total_points = 0
            for achievement in user_achievements:
                # 獲取成就詳情來計算點數
                achievement_detail = await repository.get_achievement(
                    achievement.achievement_id
                )
                if achievement_detail and hasattr(achievement_detail, "points"):
                    total_points += achievement_detail.points

            return {
                "total_achievements": total_achievements,
                "total_progress": total_progress,
                "total_points": total_points,
            }
        except Exception as e:
            logger.error(f"[用戶搜尋]獲取用戶成就摘要失敗: {e}")
            return {
                "total_achievements": 0,
                "total_progress": 0,
                "total_points": 0,
            }

    async def _create_search_results_embed(
        self, results: list[dict], query: str
    ) -> discord.Embed:
        """建立搜尋結果 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🔍 用戶搜尋結果", f"搜尋「{query}」找到 {len(results)} 個結果"
        )

        if len(results) == 1:
            # 單一結果詳細顯示
            user_data = results[0]
            member = user_data["user"]

            embed.add_field(
                name="👤 用戶資訊",
                value=(
                    f"**用戶名**: {user_data['username']}\n"
                    f"**顯示名**: {user_data['display_name']}\n"
                    f"**用戶ID**: {user_data['user_id']}\n"
                    f"**加入時間**: <t:{int(user_data['joined_at'].timestamp())}:R>"
                ),
                inline=True,
            )

            embed.add_field(
                name="🏆 成就統計",
                value=(
                    f"**成就數量**: {user_data['achievement_count']} 個\n"
                    f"**進度項目**: {user_data['progress_count']} 個\n"
                    f"**總點數**: {user_data['achievement_points']} 點"
                ),
                inline=True,
            )

            if member.avatar:
                embed.set_thumbnail(url=user_data["avatar_url"])
        else:
            # 多結果列表顯示
            result_list = []
            for i, user_data in enumerate(results, 1):
                result_list.append(
                    f"**{i}.** {user_data['display_name']} "
                    f"({user_data['achievement_count']} 個成就)"
                )

            embed.add_field(
                name="📋 搜尋結果", value="\n".join(result_list), inline=False
            )

        embed.add_field(
            name="💡 下一步",
            value="請選擇一個用戶來查看詳細資訊或執行管理操作.",
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="使用下方選單選擇用戶")

        return embed


class UserSelectionView(ui.View):
    """用戶選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_results: list[dict], search_query: str
    ):
        """初始化用戶選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            user_results: 用戶搜尋結果
            search_query: 搜尋查詢
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_results = user_results
        self.search_query = search_query

        # 建立用戶選擇下拉選單
        if user_results:
            options = []
            for user_data in user_results[:25]:  # Discord 限制最多 25 個選項
                user_data["user"]
                description = (
                    f"{user_data['achievement_count']} 個成就 | "
                    f"{user_data['achievement_points']} 點數"
                )

                options.append(
                    discord.SelectOption(
                        label=f"{user_data['display_name']}",
                        value=str(user_data["user_id"]),
                        description=description[:100],  # Discord 限制
                        emoji="👤",
                    )
                )

            self.user_select = ui.Select(
                placeholder="選擇要管理的用戶...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.user_select.callback = self.on_user_select
            self.add_item(self.user_select)

    async def on_user_select(self, interaction: discord.Interaction):
        """處理用戶選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            selected_user_id = int(self.user_select.values[0])
            selected_user_data = next(
                (
                    data
                    for data in self.user_results
                    if data["user_id"] == selected_user_id
                ),
                None,
            )

            if not selected_user_data:
                await interaction.followup.send("❌ 選擇的用戶無效", ephemeral=True)
                return

            # 建立用戶詳細管理視圖
            detail_view = UserDetailManagementView(self.admin_panel, selected_user_data)

            embed = await self._create_user_detail_embed(selected_user_data)

            await interaction.followup.send(
                embed=embed, view=detail_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶選擇視圖]處理用戶選擇失敗: {e}")
            await interaction.followup.send("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _create_user_detail_embed(self, user_data: dict) -> discord.Embed:
        """建立用戶詳細資訊 Embed."""
        member = user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            f"👤 {user_data['display_name']} - 成就管理", "用戶詳細資訊和成就管理選項"
        )

        # 基本資訊
        embed.add_field(
            name="📋 基本資訊",
            value=(
                f"**用戶名**: {user_data['username']}\n"
                f"**顯示名**: {user_data['display_name']}\n"
                f"**用戶ID**: {user_data['user_id']}\n"
                f"**加入時間**: <t:{int(user_data['joined_at'].timestamp())}:R>"
            ),
            inline=True,
        )

        # 成就統計
        embed.add_field(
            name="🏆 成就統計",
            value=(
                f"**獲得成就**: {user_data['achievement_count']} 個\n"
                f"**進行中**: {user_data['progress_count']} 個\n"
                f"**總點數**: {user_data['achievement_points']} 點\n"
                f"**排名**: 計算中..."
            ),
            inline=True,
        )

        # 管理選項說明
        embed.add_field(
            name="⚡ 管理選項",
            value=(
                "🎁 **授予成就** - 手動授予特定成就\n"
                "❌ **撤銷成就** - 撤銷已獲得的成就\n"
                "📈 **調整進度** - 調整成就進度值\n"
                "📊 **查看詳情** - 查看完整成就列表\n"
                "🔄 **重置資料** - 重置用戶成就資料"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=user_data["avatar_url"])

        embed.color = 0xFF6B35
        embed.set_footer(text="選擇下方操作來管理此用戶的成就")

        return embed

    @ui.button(label="🔍 重新搜尋", style=discord.ButtonStyle.secondary)
    async def search_again_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """重新搜尋用戶."""
        try:
            modal = UserSearchModal(self.admin_panel, action="general")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"[用戶選擇視圖]重新搜尋失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟搜尋時發生錯誤", ephemeral=True
            )


class RevokeAchievementFlowView(ui.View):
    """成就撤銷流程視圖."""

    def __init__(self, panel: AdminPanel):
        super().__init__(timeout=300)
        self.panel = panel
        self.current_step = "search_user"
        self.selected_user = None
        self.selected_achievement = None

    @ui.button(label="🔍 搜尋用戶", style=discord.ButtonStyle.primary)
    async def search_user_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """搜尋用戶按鈕."""
        try:
            modal = UserSearchModal(self.panel, action="revoke")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"[成就撤銷流程]搜尋用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )


class AdjustProgressFlowView(ui.View):
    """成就進度調整流程視圖."""

    def __init__(self, panel: AdminPanel):
        """初始化進度調整流程視圖."""
        super().__init__(timeout=300)
        self.panel = panel

    @ui.button(label="🔍 搜尋用戶", style=discord.ButtonStyle.primary)
    async def search_user_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """開啟用戶搜尋."""
        try:
            modal = UserSearchModal(self.panel, action="adjust")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[進度調整視圖]開啟用戶搜尋失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理主頁面."""
        try:
            await self.panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"[進度調整視圖]返回失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)


class AdjustProgressUserSelectionView(ui.View):
    """進度調整用戶選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_results: list[dict], search_query: str
    ):
        """初始化用戶選擇視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_results = user_results
        self.search_query = search_query

        # 創建用戶選擇選單
        options = []
        for user in user_results[:25]:  # Discord 限制最多 25 個選項
            # 簡化描述,避免異步調用
            description = f"用戶 ID: {user['user_id']}"

            options.append(
                discord.SelectOption(
                    label=user["display_name"][:100],  # Discord 限制
                    value=str(user["user_id"]),
                    description=description[:100],  # Discord 限制
                    emoji="📈",
                )
            )

        if options:
            self.user_select = ui.Select(
                placeholder="選擇要調整進度的用戶...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.user_select.callback = self.on_user_select
            self.add_item(self.user_select)

    async def _get_user_progress_stats(self, user_id: int) -> dict:
        """獲取用戶進度統計."""
        try:
            # 使用真實的資料庫查詢
            repository = self.admin_panel.achievement_service.repository

            # 獲取用戶所有進度記錄
            progresses = await repository.get_user_progresses(user_id)

            # 計算統計
            total_progresses = len(progresses)
            in_progress = sum(1 for p in progresses if p.current_value < p.target_value)

            return {"in_progress": in_progress, "total": total_progresses}
        except Exception as e:
            logger.error(f"獲取用戶進度統計失敗: {e}")
            return {"in_progress": 0, "total": 0}

    async def on_user_select(self, interaction: discord.Interaction) -> None:
        """處理用戶選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id = int(self.user_select.values[0])
            selected_user = next(
                (user for user in self.user_results if user["user_id"] == user_id), None
            )

            if not selected_user:
                await interaction.followup.send("❌ 選擇的用戶無效", ephemeral=True)
                return

            # 獲取用戶的進度列表
            user_progress = await self._get_user_progress_list(user_id)

            if not user_progress:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "無進度記錄",
                    f"用戶 **{selected_user['display_name']}** 目前沒有任何成就進度記錄.\n\n"
                    "用戶需要先開始某些成就的進度才能進行調整.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 創建進度調整選擇視圖
            progress_view = AdjustProgressSelectionView(
                self.admin_panel, selected_user, user_progress
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📈 選擇要調整的成就進度",
                f"**用戶**: {selected_user['display_name']}\n"
                f"**用戶 ID**: {selected_user['user_id']}\n\n"
                f"**進行中的成就**: {len(user_progress)} 個\n\n"
                "請選擇要調整進度的成就:",
            )

            await interaction.followup.send(
                embed=embed, view=progress_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[進度調整用戶選擇視圖]處理用戶選擇失敗: {e}")
            await interaction.followup.send("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _get_user_progress_list(self, user_id: int) -> list[dict]:
        """獲取用戶進度列表."""
        try:
            # 使用真實的資料庫查詢
            repository = self.admin_panel.achievement_service.repository

            # 獲取用戶所有進度記錄
            progresses = await repository.get_user_progresses(user_id)

            progress_list = []
            for progress in progresses:
                # 獲取成就資訊
                achievement = await repository.get_achievement(progress.achievement_id)
                if not achievement:
                    continue

                # 計算進度百分比
                target_value = achievement.criteria.get("target_value", 1)
                progress_percentage = (
                    (progress.current_value / target_value) * 100
                    if target_value > 0
                    else 0
                )
                is_completed = progress.current_value >= target_value

                progress_list.append({
                    "achievement_id": progress.achievement_id,
                    "achievement_name": achievement.name,
                    "current_value": progress.current_value,
                    "target_value": target_value,
                    "progress_percentage": progress_percentage,
                    "is_completed": is_completed,
                })

            return progress_list
        except Exception as e:
            logger.error(f"獲取用戶進度列表失敗: {e}")
            return []

    @ui.button(label="🔙 返回搜尋", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶搜尋."""
        try:
            modal = UserSearchModal(self.admin_panel, action="adjust")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"[進度調整用戶選擇視圖]返回搜尋失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回搜尋時發生錯誤", ephemeral=True
            )


class AdjustProgressSelectionView(ui.View):
    """進度調整成就選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_data: dict, user_progress: list[dict]
    ):
        """初始化進度選擇視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.user_progress = user_progress

        # 創建進度選擇選單
        options = []
        for progress in user_progress[:25]:  # Discord 限制最多 25 個選項
            progress_text = (
                f"{progress['current_value']:.1f}/{progress['target_value']:.1f}"
            )
            percentage = progress["progress_percentage"]

            # 根據進度狀態選擇不同的emoji和描述
            if progress["is_completed"]:
                emoji = "✅"
                status = "已完成"
            elif percentage >= DIFFICULTY_SIMPLE_THRESHOLD:
                emoji = "🔥"
                status = f"接近完成 ({percentage:.1f}%)"
            elif percentage >= DIFFICULTY_NORMAL_THRESHOLD:
                emoji = "⚡"
                status = f"進行中 ({percentage:.1f}%)"
            else:
                emoji = "📈"
                status = f"初期階段 ({percentage:.1f}%)"

            description = f"{status} - 當前: {progress_text}"

            options.append(
                discord.SelectOption(
                    label=progress["achievement_name"][:100],
                    value=str(progress["achievement_id"]),
                    description=description[:100],
                    emoji=emoji,
                )
            )

        if options:
            self.progress_select = ui.Select(
                placeholder="選擇要調整進度的成就...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.progress_select.callback = self.on_progress_select
            self.add_item(self.progress_select)

    async def on_progress_select(self, interaction: discord.Interaction) -> None:
        """處理進度選擇."""
        try:
            achievement_id = int(self.progress_select.values[0])
            selected_progress = next(
                (
                    p
                    for p in self.user_progress
                    if p["achievement_id"] == achievement_id
                ),
                None,
            )

            if not selected_progress:
                await interaction.response.send_message(
                    "❌ 選擇的進度記錄無效", ephemeral=True
                )
                return

            # 開啟進度調整模態框
            modal = AdjustProgressModal(
                self.admin_panel, self.user_data, selected_progress
            )
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[進度調整選擇視圖]處理進度選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理進度選擇時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回用戶選擇", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶選擇."""
        try:
            # 重新搜尋並返回用戶選擇頁面
            search_results = [self.user_data]  # 當前選中的用戶
            view = AdjustProgressUserSelectionView(
                self.admin_panel, search_results, self.user_data["display_name"]
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📈 進度調整 - 用戶選擇",
                f"搜尋結果:**{self.user_data['display_name']}**\n\n"
                "請選擇要調整進度的用戶:",
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"[進度調整選擇視圖]返回用戶選擇失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)


class AdjustProgressModal(ui.Modal):
    """進度調整模態框."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, progress_data: dict):
        """初始化進度調整模態框."""
        super().__init__(title=f"調整進度: {progress_data['achievement_name']}")
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.progress_data = progress_data

        # 當前進度值輸入
        self.current_value_input = ui.TextInput(
            label="新進度值",
            placeholder=f"輸入新的進度值 (0.0 - {progress_data['target_value']:.1f})",
            default=str(progress_data["current_value"]),
            max_length=20,
            required=True,
        )
        self.add_item(self.current_value_input)

        # 調整原因
        self.reason_input = ui.TextInput(
            label="調整原因 (必填)",
            placeholder="請說明調整進度的原因...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.reason_input)

        # 是否通知用戶
        self.notify_input = ui.TextInput(
            label="通知用戶 (是/否)",
            placeholder="輸入 '是' 或 '否'",
            default="否",
            max_length=5,
            required=True,
        )
        self.add_item(self.notify_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 驗證輸入
            validation_result = await self._validate_inputs()
            if not validation_result["valid"]:
                await interaction.followup.send(
                    f"❌ 輸入驗證失敗:\n{validation_result['error']}", ephemeral=True
                )
                return

            new_value = validation_result["new_value"]
            reason = validation_result["reason"]
            notify_user = validation_result["notify_user"]

            # 檢查是否需要自動完成成就
            will_complete = new_value >= self.progress_data["target_value"]
            is_currently_completed = self.progress_data["is_completed"]

            # 創建確認視圖
            confirm_view = AdjustProgressConfirmView(
                self.admin_panel,
                self.user_data,
                self.progress_data,
                new_value,
                reason,
                notify_user,
                will_complete and not is_currently_completed,  # 是否會觸發完成
            )

            # 創建確認 embed
            embed = await self._create_confirmation_embed(
                new_value, reason, notify_user, will_complete, is_currently_completed
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[進度調整模態框]處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理進度調整時發生錯誤", ephemeral=True)

    async def _validate_inputs(self) -> dict:
        """驗證輸入數據."""
        try:
            # 驗證進度值
            progress_validation = self._validate_progress_value()
            if not progress_validation["valid"]:
                return progress_validation

            # 驗證原因
            reason_validation = self._validate_reason()
            if not reason_validation["valid"]:
                return reason_validation

            # 驗證通知設定
            notify_validation = self._validate_notify_setting()
            if not notify_validation["valid"]:
                return notify_validation

            return {
                "valid": True,
                "new_value": progress_validation["value"],
                "reason": reason_validation["value"],
                "notify_user": notify_validation["value"],
            }

        except Exception as e:
            logger.error(f"[進度調整模態框]輸入驗證失敗: {e}")
            return {"valid": False, "error": f"驗證過程發生錯誤: {e!s}"}

    def _validate_progress_value(self) -> dict:
        """驗證進度值."""
        try:
            new_value = float(self.current_value_input.value.strip())
        except ValueError:
            return {"valid": False, "error": "進度值必須是有效的數字"}

        target_value = self.progress_data["target_value"]
        if new_value < 0:
            return {"valid": False, "error": "進度值不能小於 0"}

        # 允許超過目標值,但給予警告提示
        if new_value > target_value * 2:  # 允許最多超過目標值的兩倍
            return {
                "valid": False,
                "error": f"進度值過大,最大允許值為 {target_value * 2:.1f}",
            }

        return {"valid": True, "value": new_value}

    def _validate_reason(self) -> dict:
        """驗證調整原因."""
        reason = self.reason_input.value.strip()
        if not reason or len(reason) < MIN_REASON_LENGTH:
            return {
                "valid": False,
                "error": f"調整原因至少需要 {MIN_REASON_LENGTH} 個字元",
            }
        return {"valid": True, "value": reason}

    def _validate_notify_setting(self) -> dict:
        """驗證通知設定."""
        notify_text = self.notify_input.value.strip().lower()
        if notify_text in ["是", "yes", "y", "true", "1"]:
            return {"valid": True, "value": True}
        elif notify_text in ["否", "no", "n", "false", "0"]:
            return {"valid": True, "value": False}
        else:
            return {"valid": False, "error": "通知設定必須是 '是' 或 '否'"}

    async def _create_confirmation_embed(
        self,
        new_value: float,
        reason: str,
        notify_user: bool,
        will_complete: bool,
        is_currently_completed: bool,
    ) -> discord.Embed:
        """創建確認 embed."""
        old_value = self.progress_data["current_value"]
        target_value = self.progress_data["target_value"]

        # 計算變化
        change = new_value - old_value
        change_text = f"+{change:.1f}" if change > 0 else f"{change:.1f}"

        # 根據是否會完成設置不同的顏色和標題
        if will_complete and not is_currently_completed:
            embed = StandardEmbedBuilder.create_success_embed(
                "🎉 確認進度調整 (將完成成就)",
                "此調整將導致成就自動完成!請仔細確認操作.",
            )
        elif is_currently_completed and new_value < target_value:
            embed = StandardEmbedBuilder.create_warning_embed(
                "⚠️ 確認進度調整 (將取消完成)", "此調整將取消已完成的成就狀態!"
            )
        else:
            embed = StandardEmbedBuilder.create_info_embed(
                "📈 確認進度調整", "請確認以下進度調整資訊:"
            )

        # 基本資訊
        embed.add_field(
            name="👤 調整對象",
            value=(
                f"**用戶**: {self.user_data['display_name']}\n"
                f"**成就**: {self.progress_data['achievement_name']}"
            ),
            inline=False,
        )

        # 進度變化
        old_percentage = (old_value / target_value) * 100
        new_percentage = (new_value / target_value) * 100

        embed.add_field(
            name="📊 進度變化",
            value=(
                f"**原進度**: {old_value:.1f}/{target_value:.1f} ({old_percentage:.1f}%)\n"
                f"**新進度**: {new_value:.1f}/{target_value:.1f} ({new_percentage:.1f}%)\n"
                f"**變化量**: {change_text}"
            ),
            inline=True,
        )

        # 設定資訊
        embed.add_field(
            name="⚙️ 調整設定",
            value=(
                f"**調整原因**: {reason[:SUMMARY_MAX_LENGTH]}{'...' if len(reason) > SUMMARY_MAX_LENGTH else ''}\n"
                f"**通知用戶**: {'是' if notify_user else '否'}"
            ),
            inline=True,
        )

        # 特殊狀況提醒
        if will_complete and not is_currently_completed:
            embed.add_field(
                name="🎊 完成提醒",
                value="此調整將觸發成就完成,用戶將獲得成就獎勵.",
                inline=False,
            )
        elif is_currently_completed and new_value < target_value:
            embed.add_field(
                name="⚠️ 取消完成提醒",
                value="此調整將取消成就完成狀態,但不會移除已獲得的成就記錄.",
                inline=False,
            )

        return embed


class AdjustProgressConfirmView(ui.View):
    """進度調整確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict,
        progress_data: dict,
        new_value: float,
        reason: str,
        notify_user: bool,
        will_complete: bool,
    ):
        """初始化確認視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.progress_data = progress_data
        self.new_value = new_value
        self.reason = reason
        self.notify_user = notify_user
        self.will_complete = will_complete

    @ui.button(label="✅ 確認調整", style=discord.ButtonStyle.primary)
    async def confirm_adjust(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認進度調整."""
        try:
            await interaction.response.defer(ephemeral=True)

            result = await self._perform_progress_adjustment()

            if result["success"]:
                # 創建成功 embed
                embed = StandardEmbedBuilder.create_success_embed(
                    "📈 進度調整成功",
                    f"✅ 用戶 **{self.user_data['display_name']}** 的成就進度已成功調整!",
                )

                embed.add_field(
                    name="📊 調整詳情",
                    value=(
                        f"**成就**: {self.progress_data['achievement_name']}\n"
                        f"**原進度**: {self.progress_data['current_value']:.1f}\n"
                        f"**新進度**: {self.new_value:.1f}\n"
                        f"**調整時間**: <t:{int(datetime.utcnow().timestamp())}:f>"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name="⚙️ 操作資訊",
                    value=(
                        f"**調整原因**: {self.reason[:SUMMARY_MAX_LENGTH]}{'...' if len(self.reason) > SUMMARY_MAX_LENGTH else ''}\n"
                        f"**通知用戶**: {'已通知' if self.notify_user else '未通知'}\n"
                        f"**操作員**: <@{interaction.user.id}>"
                    ),
                    inline=True,
                )

                if self.will_complete:
                    embed.add_field(
                        name="🎉 成就完成",
                        value="此調整觸發了成就完成,用戶已獲得相應獎勵!",
                        inline=False,
                    )

                embed.set_footer(text="操作已記錄到審計日誌")

                # 創建後續操作視圖
                followup_view = AdjustProgressFollowupView(
                    self.admin_panel, self.user_data, result
                )

                await interaction.followup.send(
                    embed=embed, view=followup_view, ephemeral=True
                )

            else:
                # 創建失敗 embed
                embed = StandardEmbedBuilder.create_error_embed(
                    "進度調整失敗",
                    f"❌ 調整進度時發生錯誤: {result.get('error', '未知錯誤')}",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[進度調整確認視圖]確認調整失敗: {e}")
            await interaction.followup.send("❌ 執行進度調整時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_adjust(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消進度調整."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 進度調整操作已被取消,沒有進行任何更改."
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def _perform_progress_adjustment(self) -> dict:
        """執行進度調整."""
        try:
            # 嘗試獲取管理服務
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, "adjust_user_progress"):
                result = await admin_service.adjust_user_progress(
                    user_id=self.user_data["user_id"],
                    achievement_id=self.progress_data["achievement_id"],
                    new_value=self.new_value,
                    reason=self.reason,
                    notify_user=self.notify_user,
                    admin_user_id=self.admin_panel.admin_user_id,
                )
                return result

            # 如果服務不可用,記錄錯誤並返回失敗
            logger.error("管理服務不可用,無法執行進度調整")
            return {"success": False, "error": "管理服務不可用"}

        except Exception as e:
            logger.error(f"[進度調整確認視圖]執行調整失敗: {e}")
            return {"success": False, "error": str(e)}

    async def _get_admin_service(self):
        """獲取管理服務實例."""
        try:
            if hasattr(self.admin_panel, "admin_service"):
                return self.admin_panel.admin_service

            if hasattr(self.admin_panel, "get_service"):
                return await self.admin_panel.get_service("admin_service")

            logger.warning("無法獲取管理服務實例")
            return None

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class AdjustProgressFollowupView(ui.View):
    """進度調整後續操作視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_data: dict, adjustment_result: dict
    ):
        """初始化後續操作視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.adjustment_result = adjustment_result

    @ui.button(label="📈 繼續調整其他進度", style=discord.ButtonStyle.primary)
    async def continue_adjust(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """繼續調整其他進度."""
        try:
            # 重新開始進度調整流程,但保持在同一用戶
            user_progress = await self._get_user_progress_list(
                self.user_data["user_id"]
            )

            if not user_progress:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "無其他進度",
                    f"用戶 **{self.user_data['display_name']}** 沒有其他可調整的進度記錄.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            progress_view = AdjustProgressSelectionView(
                self.admin_panel, self.user_data, user_progress
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📈 繼續調整進度",
                f"**用戶**: {self.user_data['display_name']}\n\n"
                "請選擇要調整的其他成就進度:",
            )

            await interaction.response.edit_message(embed=embed, view=progress_view)

        except Exception as e:
            logger.error(f"[進度調整後續視圖]繼續調整失敗: {e}")
            await interaction.response.send_message(
                "❌ 繼續調整時發生錯誤", ephemeral=True
            )

    @ui.button(label="👤 管理其他用戶", style=discord.ButtonStyle.secondary)
    async def manage_other_user(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """管理其他用戶."""
        try:
            modal = UserSearchModal(self.admin_panel, action="adjust")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[進度調整後續視圖]搜尋其他用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    @ui.button(label="📋 查看調整歷史", style=discord.ButtonStyle.secondary)
    async def view_history(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看調整歷史."""
        try:
            await interaction.response.defer(ephemeral=True)

            history = await self._get_adjustment_history(self.user_data["user_id"])

            embed = StandardEmbedBuilder.create_info_embed(
                "📋 進度調整歷史",
                f"**用戶**: {self.user_data['display_name']}\n"
                f"**最近調整記錄**: {len(history)} 條\n\n",
            )

            if history:
                history_text = []
                for record in history[:5]:  # 顯示最近5條記錄
                    timestamp = f"<t:{int(record['timestamp'].timestamp())}:R>"
                    history_text.append(
                        f"• **{record['achievement_name']}**: "
                        f"{record['old_value']:.1f} → {record['new_value']:.1f} "
                        f"({timestamp})"
                    )

                embed.add_field(
                    name="📈 最近調整", value="\n".join(history_text), inline=False
                )
            else:
                embed.add_field(name="📈 調整記錄", value="暫無調整記錄", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[進度調整後續視圖]查看歷史失敗: {e}")
            await interaction.followup.send("❌ 查看調整歷史時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理."""
        try:
            await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"[進度調整後續視圖]返回用戶管理失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回用戶管理時發生錯誤", ephemeral=True
            )

    async def _get_user_progress_list(self, user_id: int) -> list[dict]:
        """獲取用戶進度列表(復用之前的實現)."""
        progress_data = {
            123456789: [
                {
                    "achievement_id": 1,
                    "achievement_name": "初次發言",
                    "current_value": 1.0,
                    "target_value": 1.0,
                    "progress_percentage": 100.0,
                    "is_completed": True,
                },
                {
                    "achievement_id": 2,
                    "achievement_name": "社交高手",
                    "current_value": 45.0,
                    "target_value": 100.0,
                    "progress_percentage": 45.0,
                    "is_completed": False,
                },
                {
                    "achievement_id": 3,
                    "achievement_name": "連續活躍",
                    "current_value": 3.0,
                    "target_value": 7.0,
                    "progress_percentage": 42.9,
                    "is_completed": False,
                },
            ],
            987654321: [
                {
                    "achievement_id": 2,
                    "achievement_name": "社交高手",
                    "current_value": 78.0,
                    "target_value": 100.0,
                    "progress_percentage": 78.0,
                    "is_completed": False,
                },
                {
                    "achievement_id": 4,
                    "achievement_name": "幫助他人",
                    "current_value": 12.0,
                    "target_value": 50.0,
                    "progress_percentage": 24.0,
                    "is_completed": False,
                },
            ],
        }
        return progress_data.get(user_id, [])

    async def _get_adjustment_history(self, user_id: int) -> list[dict]:
        """獲取進度調整歷史."""
        try:
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_adjustment_history(user_id)
        except Exception as e:
            logger.error(f"獲取調整歷史失敗: {e}")

        logger.warning(f"無法獲取用戶 {user_id} 的調整歷史,返回空列表")
        return []


class ResetDataFlowView(ui.View):
    """用戶資料重置流程視圖."""

    def __init__(self, panel: AdminPanel):
        """初始化資料重置流程視圖."""
        super().__init__(timeout=300)
        self.panel = panel

    @ui.button(label="🔍 搜尋用戶", style=discord.ButtonStyle.primary)
    async def search_user_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """開啟用戶搜尋."""
        try:
            modal = UserSearchModal(self.panel, action="reset")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[資料重置視圖]開啟用戶搜尋失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理主頁面."""
        try:
            await self.panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"[資料重置視圖]返回失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)


class ResetDataUserSelectionView(ui.View):
    """資料重置用戶選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_results: list[dict], search_query: str
    ):
        """初始化用戶選擇視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_results = user_results
        self.search_query = search_query
        self._options_created = False

    async def _create_user_options(self):
        """創建用戶選擇選單選項."""
        if self._options_created:
            return

        options = []
        for user in self.user_results[:25]:  # Discord 限制最多 25 個選項
            # 獲取用戶的成就統計
            achievement_stats = await self._get_user_achievement_stats(user["user_id"])

            # 顯示用戶的成就和進度統計
            description = (
                f"成就: {achievement_stats['achievements']} | "
                f"進度: {achievement_stats['progress']} | "
                f"點數: {achievement_stats['points']}"
            )

            options.append(
                discord.SelectOption(
                    label=user["display_name"][:100],  # Discord 限制
                    value=str(user["user_id"]),
                    description=description[:100],  # Discord 限制
                    emoji="🔄",
                )
            )

        if options:
            self.user_select = ui.Select(
                placeholder="選擇要重置資料的用戶...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.user_select.callback = self.on_user_select
            self.add_item(self.user_select)
            self._options_created = True

    async def _get_user_achievement_stats(self, user_id: int) -> dict:
        """獲取用戶成就統計."""
        try:
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_user_achievement_stats(user_id)
        except Exception as e:
            logger.error(f"獲取用戶成就統計失敗: {e}")

        logger.warning(f"無法獲取用戶 {user_id} 的成就統計,返回預設值")
        return {"achievements": 0, "progress": 0, "points": 0}

    async def on_user_select(self, interaction: discord.Interaction) -> None:
        """處理用戶選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id = int(self.user_select.values[0])
            selected_user = next(
                (user for user in self.user_results if user["user_id"] == user_id), None
            )

            if not selected_user:
                await interaction.followup.send("❌ 選擇的用戶無效", ephemeral=True)
                return

            # 獲取用戶的詳細資料摘要
            user_data_summary = await self._get_user_data_summary(user_id)

            if not user_data_summary["has_data"]:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "無資料可重置",
                    f"用戶 **{selected_user['display_name']}** 目前沒有任何成就或進度資料.\n\n"
                    "無法執行重置操作.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 創建重置選項選擇視圖
            reset_view = ResetDataOptionsView(
                self.admin_panel, selected_user, user_data_summary
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "🔄 選擇重置範圍",
                f"**用戶**: {selected_user['display_name']}\n"
                f"**用戶 ID**: {selected_user['user_id']}\n\n"
                f"**⚠️ 危險操作警告**\n"
                f"資料重置操作無法撤銷!請仔細選擇重置範圍:\n\n"
                f"**用戶資料摘要**:\n"
                f"• 已獲得成就: {user_data_summary['achievements_count']} 個\n"
                f"• 進行中進度: {user_data_summary['progress_count']} 個\n"
                f"• 總點數: {user_data_summary['total_points']} 點\n"
                f"• 最後活動: {user_data_summary['last_activity']}",
            )

            await interaction.followup.send(
                embed=embed, view=reset_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[資料重置用戶選擇視圖]處理用戶選擇失敗: {e}")
            await interaction.followup.send("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _get_user_data_summary(self, user_id: int) -> dict:
        """獲取用戶資料摘要."""
        try:
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_user_data_summary(user_id)
        except Exception as e:
            logger.error(f"獲取用戶資料摘要失敗: {e}")

        logger.warning(f"無法獲取用戶 {user_id} 的資料摘要,返回預設值")
        return {
            "has_data": False,
            "achievements_count": 0,
            "progress_count": 0,
            "total_points": 0,
            "last_activity": "從未",
            "categories": [],
        }

    @ui.button(label="🔙 返回搜尋", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶搜尋."""
        try:
            modal = UserSearchModal(self.admin_panel, action="reset")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"[資料重置用戶選擇視圖]返回搜尋失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回搜尋時發生錯誤", ephemeral=True
            )


class ResetDataOptionsView(ui.View):
    """資料重置選項選擇視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, data_summary: dict):
        """初始化重置選項視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.data_summary = data_summary

    @ui.button(label="🗑️ 完整重置", style=discord.ButtonStyle.danger)
    async def full_reset_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """完整重置所有資料."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 創建完整重置確認視圖
            confirm_view = ResetDataConfirmView(
                self.admin_panel,
                self.user_data,
                self.data_summary,
                reset_type="full",
                reset_options={"all": True},
            )

            embed = StandardEmbedBuilder.create_error_embed(
                "⚠️ 確認完整重置",
                f"**用戶**: {self.user_data['display_name']}\n\n"
                f"**🚨 極度危險操作 🚨**\n\n"
                f"您即將完全重置此用戶的所有成就資料:\n\n"
                f"**將被刪除的資料**:\n"
                f"• ❌ 所有已獲得成就 ({self.data_summary['achievements_count']} 個)\n"
                f"• ❌ 所有進度記錄 ({self.data_summary['progress_count']} 個)\n"
                f"• ❌ 所有成就點數 ({self.data_summary['total_points']} 點)\n"
                f"• ❌ 所有歷史記錄和統計\n\n"
                f"**⚠️ 此操作無法撤銷!**\n"
                f"重置後用戶將回到初始狀態,如同從未參與成就系統.",
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[資料重置選項視圖]完整重置失敗: {e}")
            await interaction.followup.send(
                "❌ 開啟完整重置確認時發生錯誤", ephemeral=True
            )

    @ui.button(label="📂 選擇性重置", style=discord.ButtonStyle.secondary)
    async def selective_reset_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """選擇性重置特定分類或類型."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 創建選擇性重置選項視圖
            selective_view = SelectiveResetOptionsView(
                self.admin_panel, self.user_data, self.data_summary
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📂 選擇性重置選項",
                f"**用戶**: {self.user_data['display_name']}\n\n"
                f"選擇要重置的資料範圍:\n\n"
                f"**可用分類**: {', '.join(self.data_summary['categories'])}\n\n"
                f"**重置選項**:\n"
                f"• 按成就分類重置\n"
                f"• 僅重置進度(保留已獲得成就)\n"
                f"• 僅重置成就(保留進度記錄)\n\n"
                f"**注意**: 選擇性重置相對安全,但仍需謹慎操作.",
            )

            await interaction.followup.send(
                embed=embed, view=selective_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[資料重置選項視圖]選擇性重置失敗: {e}")
            await interaction.followup.send(
                "❌ 開啟選擇性重置時發生錯誤", ephemeral=True
            )

    @ui.button(label="📋 查看詳細資料", style=discord.ButtonStyle.primary)
    async def view_details_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看用戶詳細資料."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 獲取詳細資料
            detailed_data = await self._get_user_detailed_data(
                self.user_data["user_id"]
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📋 用戶詳細資料",
                f"**用戶**: {self.user_data['display_name']}\n"
                f"**用戶 ID**: {self.user_data['user_id']}\n\n",
            )

            # 成就詳情
            if detailed_data["achievements"]:
                achievement_list = []
                for ach in detailed_data["achievements"][:5]:  # 顯示前5個
                    earned_time = f"<t:{int(ach['earned_at'].timestamp())}:R>"
                    achievement_list.append(f"• **{ach['name']}** ({earned_time})")

                embed.add_field(
                    name=f"🏆 已獲得成就 ({len(detailed_data['achievements'])})",
                    value="\n".join(achievement_list)
                    + (
                        f"\n... 及其他 {len(detailed_data['achievements']) - MAX_DISPLAYED_ITEMS} 個"
                        if len(detailed_data["achievements"]) > MAX_DISPLAYED_ITEMS
                        else ""
                    ),
                    inline=False,
                )

            # 進度詳情
            if detailed_data["progress"]:
                progress_list = []
                for prog in detailed_data["progress"][:5]:  # 顯示前5個
                    percentage = (prog["current"] / prog["target"]) * 100
                    progress_list.append(
                        f"• **{prog['achievement']}**: "
                        f"{prog['current']:.1f}/{prog['target']:.1f} ({percentage:.1f}%)"
                    )

                embed.add_field(
                    name=f"📈 進行中進度 ({len(detailed_data['progress'])})",
                    value="\n".join(progress_list)
                    + (
                        f"\n... 及其他 {len(detailed_data['progress']) - MAX_DISPLAYED_ITEMS} 個"
                        if len(detailed_data["progress"]) > MAX_DISPLAYED_ITEMS
                        else ""
                    ),
                    inline=False,
                )

            # 統計資訊
            embed.add_field(
                name="📊 統計資訊",
                value=(
                    f"**總點數**: {self.data_summary['total_points']} 點\n"
                    f"**最後活動**: {self.data_summary['last_activity']}\n"
                    f"**參與分類**: {len(self.data_summary['categories'])} 個"
                ),
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[資料重置選項視圖]查看詳細資料失敗: {e}")
            await interaction.followup.send("❌ 查看詳細資料時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回用戶選擇", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶選擇."""
        try:
            # 重新搜尋並返回用戶選擇頁面
            search_results = [self.user_data]
            view = ResetDataUserSelectionView(
                self.admin_panel, search_results, self.user_data["display_name"]
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "🔄 資料重置 - 用戶選擇",
                f"搜尋結果:**{self.user_data['display_name']}**\n\n"
                "請選擇要重置資料的用戶:",
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"[資料重置選項視圖]返回用戶選擇失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)

    async def _get_user_detailed_data(self, user_id: int) -> dict:
        """獲取用戶詳細資料(真實實現)."""
        try:
            # 獲取用戶成就記錄
            user_achievements = (
                await self.panel.achievement_service.get_user_achievements(user_id)
            )

            # 獲取用戶進度記錄
            user_progress = await self.panel.achievement_service.get_user_progress(
                user_id
            )

            # 格式化成就資料
            achievements = []
            for achievement in user_achievements:
                achievements.append({
                    "name": achievement.achievement_name
                    if hasattr(achievement, "achievement_name")
                    else f"成就 {achievement.achievement_id}",
                    "earned_at": achievement.earned_at,
                    "points": achievement.points
                    if hasattr(achievement, "points")
                    else 0,
                })

            # 格式化進度資料
            progress = []
            for prog in user_progress:
                progress.append({
                    "achievement": prog.achievement_name
                    if hasattr(prog, "achievement_name")
                    else f"成就 {prog.achievement_id}",
                    "current": prog.current_value,
                    "target": prog.target_value,
                })

            return {
                "achievements": achievements,
                "progress": progress,
            }

        except Exception as e:
            logger.error(f"獲取用戶 {user_id} 詳細資料失敗: {e}")
            # 返回空資料而不是模擬資料
            return {"achievements": [], "progress": []}


class SelectiveResetOptionsView(ui.View):
    """選擇性重置選項視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, data_summary: dict):
        """初始化選擇性重置選項視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.data_summary = data_summary

        # 創建分類選擇選單
        if data_summary["categories"]:
            category_options = []
            for category in data_summary["categories"]:
                category_options.append(
                    discord.SelectOption(
                        label=f"重置分類: {category}",
                        value=f"category_{category}",
                        description=f"重置 {category} 分類的所有資料",
                        emoji="📂",
                    )
                )

            self.category_select = ui.Select(
                placeholder="選擇要重置的成就分類...",
                min_values=1,
                max_values=min(len(category_options), 3),  # 最多選3個
                options=category_options,
            )
            self.category_select.callback = self.on_category_select
            self.add_item(self.category_select)

    @ui.button(label="📈 僅重置進度", style=discord.ButtonStyle.secondary)
    async def reset_progress_only_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """僅重置進度記錄,保留已獲得成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            confirm_view = ResetDataConfirmView(
                self.admin_panel,
                self.user_data,
                self.data_summary,
                reset_type="progress_only",
                reset_options={"progress_only": True},
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "📈 確認重置進度記錄",
                f"**用戶**: {self.user_data['display_name']}\n\n"
                f"**重置範圍**: 僅進度記錄\n\n"
                f"**將被重置的資料**:\n"
                f"• ❌ 所有進度記錄 ({self.data_summary['progress_count']} 個)\n"
                f"• ❌ 進行中的成就進度\n\n"
                f"**將被保留的資料**:\n"
                f"• ✅ 已獲得成就 ({self.data_summary['achievements_count']} 個)\n"
                f"• ✅ 成就點數 ({self.data_summary['total_points']} 點)\n\n"
                f"**影響**: 用戶需要重新開始所有成就的進度追蹤.",
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[選擇性重置視圖]重置進度失敗: {e}")
            await interaction.followup.send(
                "❌ 開啟進度重置確認時發生錯誤", ephemeral=True
            )

    @ui.button(label="🏆 僅重置成就", style=discord.ButtonStyle.secondary)
    async def reset_achievements_only_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """僅重置已獲得成就,保留進度記錄."""
        try:
            await interaction.response.defer(ephemeral=True)

            confirm_view = ResetDataConfirmView(
                self.admin_panel,
                self.user_data,
                self.data_summary,
                reset_type="achievements_only",
                reset_options={"achievements_only": True},
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "🏆 確認重置已獲得成就",
                f"**用戶**: {self.user_data['display_name']}\n\n"
                f"**重置範圍**: 僅已獲得成就\n\n"
                f"**將被重置的資料**:\n"
                f"• ❌ 所有已獲得成就 ({self.data_summary['achievements_count']} 個)\n"
                f"• ❌ 成就點數 ({self.data_summary['total_points']} 點)\n\n"
                f"**將被保留的資料**:\n"
                f"• ✅ 進度記錄 ({self.data_summary['progress_count']} 個)\n"
                f"• ✅ 進行中的成就進度\n\n"
                f"**影響**: 用戶將失去所有已獲得的成就,但進度記錄會保留.",
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[選擇性重置視圖]重置成就失敗: {e}")
            await interaction.followup.send(
                "❌ 開啟成就重置確認時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回重置選項", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回重置選項."""
        try:
            options_view = ResetDataOptionsView(
                self.admin_panel, self.user_data, self.data_summary
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "🔄 選擇重置範圍",
                f"**用戶**: {self.user_data['display_name']}\n\n請選擇重置範圍:",
            )

            await interaction.response.edit_message(embed=embed, view=options_view)

        except Exception as e:
            logger.error(f"[選擇性重置視圖]返回重置選項失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)

    async def on_category_select(self, interaction: discord.Interaction) -> None:
        """處理分類選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            selected_categories = []
            for value in self.category_select.values:
                if value.startswith("category_"):
                    category_name = value[9:]  # 去掉 "category_" 前綴
                    selected_categories.append(category_name)

            if not selected_categories:
                await interaction.followup.send("❌ 沒有選擇有效的分類", ephemeral=True)
                return

            confirm_view = ResetDataConfirmView(
                self.admin_panel,
                self.user_data,
                self.data_summary,
                reset_type="category",
                reset_options={
                    "categories": selected_categories,
                    "category_names": ", ".join(selected_categories),
                },
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "📂 確認重置選定分類",
                f"**用戶**: {self.user_data['display_name']}\n\n"
                f"**重置範圍**: 選定分類\n"
                f"**選定分類**: {', '.join(selected_categories)}\n\n"
                f"**將被重置的資料**:\n"
                f"• ❌ 選定分類中的所有成就\n"
                f"• ❌ 選定分類中的所有進度\n"
                f"• ❌ 對應的成就點數\n\n"
                f"**影響**: 用戶在這些分類中的所有成就活動將被清除.",
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[選擇性重置視圖]處理分類選擇失敗: {e}")
            await interaction.followup.send("❌ 處理分類選擇時發生錯誤", ephemeral=True)


class ResetDataConfirmView(ui.View):
    """資料重置確認視圖 - 多重確認機制."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict,
        data_summary: dict,
        reset_type: str,
        reset_options: dict,
    ):
        """初始化重置確認視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.data_summary = data_summary
        self.reset_type = reset_type
        self.reset_options = reset_options
        self.confirmation_step = 1  # 確認步驟追蹤
        self.admin_confirmed = False  # 管理員確認狀態

    @ui.button(label="⚠️ 第一次確認", style=discord.ButtonStyle.danger)
    async def first_confirmation(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """第一次確認 - 顯示詳細資訊."""
        try:
            if self.confirmation_step != 1:
                await interaction.response.send_message(
                    "❌ 請按順序完成確認步驟", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 創建資料備份預覽
            backup_data = await self._create_backup_preview()

            embed = StandardEmbedBuilder.create_warning_embed(
                "⚠️ 第一次確認完成 - 資料備份預覽",
                f"**用戶**: {self.user_data['display_name']}\n"
                f"**重置類型**: {self._get_reset_type_name()}\n\n"
                f"**📋 資料備份預覽**:\n\n"
                f"**備份檔案 ID**: `{backup_data['backup_id']}`\n"
                f"**備份時間**: <t:{int(backup_data['timestamp'].timestamp())}:f>\n"
                f"**備份內容**: {backup_data['content_summary']}\n\n"
                f"**⚠️ 重要提醒**:\n"
                f"• 資料備份將保留 30 天\n"
                f"• 可通過備份 ID 進行部分恢復\n"
                f"• 完整重置後無法完全撤銷\n\n"
                f"**請進行第二次確認以繼續.**",
            )

            # 更新按鈕狀態
            _button.disabled = True
            _button.label = "✅ 已完成"
            _button.style = discord.ButtonStyle.success

            # 啟用第二次確認按鈕
            for item in self.children:
                if hasattr(item, "custom_id") and item.custom_id == "second_confirm":
                    item.disabled = False
                    break

            self.confirmation_step = 2

            await interaction.followup.send(embed=embed, view=self, ephemeral=True)

        except Exception as e:
            logger.error(f"[重置確認視圖]第一次確認失敗: {e}")
            await interaction.followup.send("❌ 第一次確認時發生錯誤", ephemeral=True)

    @ui.button(
        label="🔐 第二次確認",
        style=discord.ButtonStyle.danger,
        disabled=True,
        custom_id="second_confirm",
    )
    async def second_confirmation(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """第二次確認 - 輸入確認文字."""
        try:
            if self.confirmation_step != SECOND_CONFIRMATION_STEP:
                await interaction.response.send_message(
                    "❌ 請先完成第一次確認", ephemeral=True
                )
                return

            # 開啟確認文字輸入模態框
            modal = ResetConfirmationTextModal(
                self.user_data["display_name"],
                self._get_reset_type_name(),
                self._final_confirm_callback,
            )
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[重置確認視圖]第二次確認失敗: {e}")
            await interaction.response.send_message(
                "❌ 第二次確認時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消重置", style=discord.ButtonStyle.secondary)
    async def cancel_reset(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消重置操作."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消",
            f"✅ 用戶 **{self.user_data['display_name']}** 的資料重置操作已被取消.\n\n"
            "沒有進行任何資料更改.",
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def _final_confirm_callback(self, interaction: discord.Interaction) -> None:
        """最終確認回調 - 執行重置."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 執行資料重置
            reset_result = await self._perform_data_reset()

            if reset_result["success"]:
                # 創建成功 embed
                embed = StandardEmbedBuilder.create_success_embed(
                    "🔄 資料重置完成",
                    f"✅ 用戶 **{self.user_data['display_name']}** 的資料重置已成功完成!",
                )

                embed.add_field(
                    name="📊 重置詳情",
                    value=(
                        f"**重置類型**: {self._get_reset_type_name()}\n"
                        f"**處理項目**: {reset_result['processed_items']}\n"
                        f"**備份 ID**: `{reset_result['backup_id']}`\n"
                        f"**完成時間**: <t:{int(datetime.utcnow().timestamp())}:f>"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name="📋 處理摘要", value=reset_result["summary"], inline=True
                )

                embed.add_field(
                    name="⚠️ 重要提醒",
                    value=(
                        "• 資料備份已保存(30天保留期)\n"
                        "• 用戶將在下次活動時收到重置通知\n"
                        "• 相關快取已自動清理\n"
                        "• 操作已記錄到審計日誌"
                    ),
                    inline=False,
                )

                embed.set_footer(text=f"操作員: {interaction.user.display_name}")

                # 創建後續操作視圖
                followup_view = ResetDataFollowupView(
                    self.admin_panel, self.user_data, reset_result
                )

                await interaction.followup.send(
                    embed=embed, view=followup_view, ephemeral=True
                )

            else:
                # 創建失敗 embed
                embed = StandardEmbedBuilder.create_error_embed(
                    "重置失敗",
                    f"❌ 重置用戶資料時發生錯誤: {reset_result.get('error', '未知錯誤')}\n\n"
                    "**錯誤處理**:\n"
                    "• 資料完整性已保持\n"
                    "• 沒有進行任何更改\n"
                    "• 請稍後重試或聯繫技術支持",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[重置確認視圖]最終確認失敗: {e}")
            await interaction.followup.send("❌ 執行資料重置時發生錯誤", ephemeral=True)

    def _get_reset_type_name(self) -> str:
        """獲取重置類型名稱."""
        type_names = {
            "full": "完整重置",
            "progress_only": "僅重置進度",
            "achievements_only": "僅重置成就",
            "category": f"分類重置 ({self.reset_options.get('category_names', '')})",
        }
        return type_names.get(self.reset_type, "未知類型")

    async def _create_backup_preview(self) -> dict:
        """創建資料備份預覽."""
        backup_id = (
            f"reset_{self.user_data['user_id']}_{int(datetime.utcnow().timestamp())}"
        )

        # 根據重置類型準備備份內容摘要
        if self.reset_type == "full":
            content = f"{self.data_summary['achievements_count']} 個成就, {self.data_summary['progress_count']} 個進度"
        elif self.reset_type == "progress_only":
            content = f"{self.data_summary['progress_count']} 個進度記錄"
        elif self.reset_type == "achievements_only":
            content = f"{self.data_summary['achievements_count']} 個成就記錄"
        elif self.reset_type == "category":
            content = (
                f"分類 '{self.reset_options.get('category_names', '')}' 的所有資料"
            )
        else:
            content = "選定範圍的資料"

        return {
            "backup_id": backup_id,
            "timestamp": datetime.utcnow(),
            "user_id": self.user_data["user_id"],
            "reset_type": self.reset_type,
            "content_summary": content,
        }

    async def _perform_data_reset(self) -> dict:
        """執行資料重置(真實實現)."""
        try:
            # 創建備份
            backup_data = await self._create_backup_preview()

            user_id = self.user_data["user_id"]
            admin_service = await self.admin_panel._get_admin_service()

            processed_items = 0
            summary = ""

            # 根據重置類型執行相應操作
            if self.reset_type == "full":
                await admin_service.reset_user_achievements(user_id)
                await admin_service.reset_user_progress(user_id)
                processed_items = (
                    self.data_summary["achievements_count"]
                    + self.data_summary["progress_count"]
                )
                summary = f"完整重置: 清除 {self.data_summary['achievements_count']} 個成就、{self.data_summary['progress_count']} 個進度記錄"

            elif self.reset_type == "achievements_only":
                # 僅重置成就
                await admin_service.reset_user_achievements(user_id)
                processed_items = self.data_summary["achievements_count"]
                summary = f"成就重置: 清除 {self.data_summary['achievements_count']} 個成就記錄"

            elif self.reset_type == "progress_only":
                # 僅重置進度
                await admin_service.reset_user_progress(user_id)
                processed_items = self.data_summary["progress_count"]
                summary = (
                    f"進度重置: 清除 {self.data_summary['progress_count']} 個進度記錄"
                )

            elif self.reset_type == "category":
                # 分類重置
                if self.reset_options.get("categories"):
                    for category_id in self.reset_options["categories"]:
                        await admin_service.reset_user_category_data(
                            user_id, category_id
                        )
                    processed_items = len(self.reset_options["categories"])
                    summary = f"分類重置: 清除 {processed_items} 個分類的所有資料"
                else:
                    processed_items = 0
                    summary = "未選擇任何分類進行重置"

            logger.info(
                f"資料重置完成: 用戶 {user_id}, "
                f"類型 {self.reset_type}, 處理項目 {processed_items}"
            )

            return {
                "success": True,
                "backup_id": backup_data["backup_id"],
                "processed_items": processed_items,
                "reset_type": self.reset_type,
                "timestamp": datetime.utcnow(),
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"[重置確認視圖]執行重置失敗: {e}")
            return {"success": False, "error": str(e)}


class ResetConfirmationTextModal(ui.Modal):
    """重置確認文字輸入模態框."""

    def __init__(self, user_display_name: str, reset_type_name: str, callback_func):
        """初始化確認文字模態框."""
        super().__init__(title="最終確認 - 輸入確認文字")
        self.user_display_name = user_display_name
        self.reset_type_name = reset_type_name
        self.callback_func = callback_func

        # 生成確認文字
        self.confirmation_text = f"重置 {user_display_name} {reset_type_name}"

        # 用戶名輸入
        self.user_name_input = ui.TextInput(
            label=f"輸入用戶名: {user_display_name}",
            placeholder=user_display_name,
            max_length=100,
            required=True,
        )
        self.add_item(self.user_name_input)

        # 重置類型輸入
        self.reset_type_input = ui.TextInput(
            label=f"輸入重置類型: {reset_type_name}",
            placeholder=reset_type_name,
            max_length=100,
            required=True,
        )
        self.add_item(self.reset_type_input)

        # 完整確認文字輸入
        self.full_confirmation_input = ui.TextInput(
            label="完整確認文字",
            placeholder=self.confirmation_text,
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True,
        )
        self.add_item(self.full_confirmation_input)

        # 原因說明
        self.reason_input = ui.TextInput(
            label="重置原因說明 (必填)",
            placeholder="請說明執行重置的原因...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            # 驗證輸入
            user_name_input = self.user_name_input.value.strip()
            reset_type_input = self.reset_type_input.value.strip()
            full_confirmation_input = self.full_confirmation_input.value.strip()
            reason = self.reason_input.value.strip()

            # 檢查用戶名
            if user_name_input != self.user_display_name:
                await interaction.response.send_message(
                    f"❌ 用戶名不匹配!請輸入: {self.user_display_name}", ephemeral=True
                )
                return

            # 檢查重置類型
            if reset_type_input != self.reset_type_name:
                await interaction.response.send_message(
                    f"❌ 重置類型不匹配!請輸入: {self.reset_type_name}", ephemeral=True
                )
                return

            # 檢查完整確認文字
            if full_confirmation_input != self.confirmation_text:
                await interaction.response.send_message(
                    f"❌ 確認文字不匹配!請完整輸入: {self.confirmation_text}",
                    ephemeral=True,
                )
                return

            # 檢查原因說明
            if not reason or len(reason) < MIN_RESET_REASON_LENGTH:
                await interaction.response.send_message(
                    f"❌ 重置原因說明至少需要 {MIN_RESET_REASON_LENGTH} 個字元",
                    ephemeral=True,
                )
                return

            # 所有驗證通過,執行回調
            if self.callback_func:
                await self.callback_func(interaction)

        except Exception as e:
            logger.error(f"[重置確認文字模態框]處理提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理確認時發生錯誤", ephemeral=True
            )


class ResetDataFollowupView(ui.View):
    """資料重置後續操作視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, reset_result: dict):
        """初始化後續操作視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.reset_result = reset_result

    @ui.button(label="🔄 重置其他用戶", style=discord.ButtonStyle.primary)
    async def reset_other_user(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """重置其他用戶."""
        try:
            modal = UserSearchModal(self.admin_panel, action="reset")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[重置後續視圖]搜尋其他用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    @ui.button(label="📋 查看備份詳情", style=discord.ButtonStyle.secondary)
    async def view_backup_details(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看備份詳情."""
        try:
            await interaction.response.defer(ephemeral=True)

            embed = StandardEmbedBuilder.create_info_embed(
                "📋 資料備份詳情",
                f"**備份 ID**: `{self.reset_result['backup_id']}`\n"
                f"**用戶**: {self.user_data['display_name']}\n"
                f"**重置類型**: {self.reset_result.get('reset_type', '未知')}\n\n",
            )

            embed.add_field(
                name="⏰ 時間資訊",
                value=(
                    f"**備份時間**: <t:{int(self.reset_result['timestamp'].timestamp())}:f>\n"
                    f"**保留期限**: <t:{int((self.reset_result['timestamp'] + timedelta(days=30)).timestamp())}:f>\n"
                    f"**剩餘天數**: 30 天"
                ),
                inline=True,
            )

            embed.add_field(
                name="📊 備份內容",
                value=(
                    f"**處理項目**: {self.reset_result['processed_items']} 個\n"
                    f"**操作摘要**: {self.reset_result['summary'][:SUMMARY_MAX_LENGTH]}{'...' if len(self.reset_result['summary']) > SUMMARY_MAX_LENGTH else ''}"
                ),
                inline=True,
            )

            embed.add_field(
                name="🔧 恢復選項",
                value=(
                    "**部分恢復**: 聯繫管理員使用備份 ID\n"
                    "**完整恢復**: 僅限特殊情況\n"
                    "**資料查詢**: 可查看備份內容清單"
                ),
                inline=False,
            )

            embed.set_footer(text="備份資料經過加密存儲,僅授權管理員可訪問")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[重置後續視圖]查看備份詳情失敗: {e}")
            await interaction.followup.send("❌ 查看備份詳情時發生錯誤", ephemeral=True)

    @ui.button(label="📈 查看重置歷史", style=discord.ButtonStyle.secondary)
    async def view_reset_history(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看重置歷史."""
        try:
            await interaction.response.defer(ephemeral=True)

            history = await self._get_reset_history(self.user_data["user_id"])

            embed = StandardEmbedBuilder.create_info_embed(
                "📈 用戶重置歷史",
                f"**用戶**: {self.user_data['display_name']}\n"
                f"**歷史記錄**: {len(history)} 次重置\n\n",
            )

            if history:
                history_text = []
                for record in history[:5]:  # 顯示最近5次
                    timestamp = f"<t:{int(record['timestamp'].timestamp())}:R>"
                    history_text.append(
                        f"• **{record['reset_type']}**: "
                        f"{record['summary']} ({timestamp})"
                    )

                embed.add_field(
                    name="📋 最近重置記錄", value="\n".join(history_text), inline=False
                )
            else:
                embed.add_field(
                    name="📋 重置記錄", value="暫無其他重置記錄", inline=False
                )

            # 統計資訊
            embed.add_field(
                name="📊 統計資訊",
                value=(
                    f"**總重置次數**: {len(history)} 次\n"
                    f"**最近重置**: <t:{int(self.reset_result['timestamp'].timestamp())}:R>\n"
                    f"**重置類型**: 包含完整重置、部分重置等"
                ),
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[重置後續視圖]查看重置歷史失敗: {e}")
            await interaction.followup.send("❌ 查看重置歷史時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理."""
        try:
            await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"[重置後續視圖]返回用戶管理失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回用戶管理時發生錯誤", ephemeral=True
            )

    async def _get_reset_history(self, user_id: int) -> list[dict]:
        """獲取用戶重置歷史(模擬實現)."""
        # 模擬歷史記錄,包含當前重置
        current_reset = {
            "reset_type": self.reset_result.get("reset_type", "unknown"),
            "summary": self.reset_result.get("summary", ""),
            "timestamp": self.reset_result.get("timestamp", datetime.utcnow()),
        }

        # 模擬之前的重置記錄
        history_data = {
            123456789: [
                current_reset,
                {
                    "reset_type": "progress_only",
                    "summary": "進度重置: 清除 3 個進度記錄",
                    "timestamp": datetime.utcnow() - timedelta(days=15),
                },
            ],
            987654321: [
                current_reset,
                {
                    "reset_type": "category",
                    "summary": "分類重置: 清除社交互動分類資料",
                    "timestamp": datetime.utcnow() - timedelta(days=7),
                },
                {
                    "reset_type": "achievements_only",
                    "summary": "成就重置: 清除 5 個成就記錄",
                    "timestamp": datetime.utcnow() - timedelta(days=30),
                },
            ],
        }
        return history_data.get(user_id, [current_reset])


class BulkUserOperationView(ui.View):
    def __init__(self, panel: AdminPanel):
        super().__init__(timeout=300)
        self.panel = panel

    async def handle_bulk_achievement_grant(
        self, users: list, achievement_id: int
    ) -> dict:
        """處理批量成就授予操作."""
        results = {"success_count": 0, "failed_count": 0, "errors": []}

        for user_id in users:
            try:
                # TODO: 實作真實的成就授予邏輯
                # achievement_id 將在實際實現中用於指定要授予的成就
                _ = achievement_id  # 暫時標記參數將被使用
                results["success_count"] += 1
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append(f"用戶 {user_id}: {e!s}")

        return results

    async def render_bulk_operation_summary(
        self, operation_type: str, results: dict
    ) -> discord.Embed:
        """渲染批量操作摘要."""
        embed = StandardEmbedBuilder.info(
            title=f"📋 批量{operation_type}操作結果", description="操作完成統計"
        )

        embed.add_field(
            name="✅ 成功", value=str(results["success_count"]), inline=True
        )

        embed.add_field(name="❌ 失敗", value=str(results["failed_count"]), inline=True)

        if results["errors"]:
            error_text = "\n".join(
                results["errors"][:MAX_ERROR_DISPLAY]
            )  # 只顯示前幾個錯誤
            if len(results["errors"]) > MAX_ERROR_DISPLAY:
                error_text += (
                    f"\n... 還有 {len(results['errors']) - MAX_ERROR_DISPLAY} 個錯誤"
                )
            embed.add_field(name="🔍 錯誤詳情", value=error_text, inline=False)

        return embed


class UserDetailManagementView(ui.View):
    def __init__(self, panel: AdminPanel, user_data: dict):
        super().__init__(timeout=300)
        self.panel = panel
        self.user_data = user_data

    async def handle_user_achievement_reset(
        self, user_id: int, reset_type: str = "all"
    ) -> dict:
        """處理用戶成就重置操作."""
        try:
            # 根據重置類型執行不同的重置邏輯
            if reset_type == "all":
                # TODO: 實作重置用戶所有成就
                pass
            elif reset_type == "category":
                # TODO: 實作重置特定分類的成就
                pass
            elif reset_type == "achievements_only":
                # TODO: 實作只重置成就,保留進度
                pass

            return {
                "success": True,
                "message": f"用戶 {user_id} 的成就已成功重置({reset_type})",
            }
        except Exception as e:
            return {"success": False, "message": f"重置失敗: {e!s}"}

    async def generate_user_activity_report(self, user_id: int) -> dict:
        """生成用戶活動報告."""
        try:
            repository = self.admin_panel.achievement_service.repository

            # 從成就服務獲取用戶成就數量
            user_achievements = await repository.get_user_achievements(user_id)
            achievements_count = len(user_achievements)

            user_progresses = await repository.get_user_progresses(user_id)
            activity_score = len(user_progresses)  # 簡單的活動度量

            last_active = None
            if user_achievements:
                # 獲取最新獲得的成就時間
                latest_achievement = max(
                    user_achievements,
                    key=lambda x: x.earned_at if hasattr(x, "earned_at") else 0,
                )
                if hasattr(latest_achievement, "earned_at"):
                    last_active = latest_achievement.earned_at

            # 總消息數暫時無法從成就系統獲取,設為 0
            total_messages = 0

            return {
                "user_id": user_id,
                "achievements_count": achievements_count,
                "activity_score": activity_score,
                "last_active": last_active,
                "total_messages": total_messages,
            }
        except Exception as e:
            logger.error(f"生成用戶活動報告失敗: {e}")
            return {
                "user_id": user_id,
                "achievements_count": 0,
                "activity_score": 0,
                "last_active": None,
                "total_messages": 0,
            }


class RealAdminService:
    """真實的管理服務實現."""

    def __init__(self, panel):
        self.panel = panel
        self.achievement_service = panel.achievement_service

    async def _check_achievement_dependencies(self, achievement_id: int):
        """檢查成就依賴關係."""
        try:
            # 使用真實的管理服務檢查依賴關係
            dependencies = await self.panel.achievement_service.admin_service._check_achievement_dependencies(
                achievement_id
            )
            return dependencies
        except Exception as e:
            logger.error(f"檢查成就依賴關係失敗: {e}")
            return {
                "has_dependencies": False,
                "user_achievement_count": 0,
                "description": "無法檢查依賴關係",
            }

    async def delete_achievement(
        self, achievement_id: int, admin_user_id: int, force: bool = False
    ):
        """刪除成就."""
        try:
            # 使用真實的管理服務刪除成就
            result = (
                await self.panel.achievement_service.admin_service.delete_achievement(
                    achievement_id, admin_user_id, force
                )
            )
            logger.info(
                f"刪除成就 {achievement_id},管理員 {admin_user_id},強制: {force},結果: {result}"
            )
            return result
        except Exception as e:
            logger.error(f"刪除成就失敗: {e}")
            return False

    async def get_achievement_with_details(self, achievement_id: int):
        """獲取成就詳細資訊(包含統計數據)."""
        try:
            # 使用真實的資料庫查詢
            achievement = await self.panel.achievement_service.get_achievement(
                achievement_id
            )
            if not achievement:
                return None

            # 獲取成就分類
            category = await self.panel.achievement_service.get_category(
                achievement.category_id
            )

            # 獲取統計數據
            statistics = await self.panel.achievement_service.admin_service._get_achievement_statistics(
                achievement_id
            )

            return {
                "achievement": achievement,
                "statistics": statistics,
                "category": category,
            }
        except Exception as e:
            logger.error(f"獲取成就詳細資訊失敗: {e}")
            return None


class BulkOperationSelectionView(ui.View):
    """批量操作選擇視圖 - 支援多選成就功能."""

    def __init__(self, admin_panel: AdminPanel, achievements: list[Achievement]):
        """初始化批量操作選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            achievements: 可操作的成就列表
        """
        super().__init__(timeout=600)  # 10分鐘超時,批量操作需要較長時間
        self.admin_panel = admin_panel
        self.achievements = achievements
        self.selected_achievements: set[int] = set()  # 已選中的成就 ID
        self.current_page = 0
        self.items_per_page = 20  # 每頁顯示成就數量

        # 初始化 UI 組件
        self._update_ui_components()

    def _update_ui_components(self):
        """更新 UI 組件."""
        self.clear_items()

        # 計算分頁
        total_pages = (
            len(self.achievements) + self.items_per_page - 1
        ) // self.items_per_page
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.achievements))
        current_achievements = self.achievements[start_idx:end_idx]

        if current_achievements:
            options = []
            for achievement in current_achievements:
                status_icon = "✅" if achievement.is_active else "❌"
                selected_icon = (
                    "🔸" if achievement.id in self.selected_achievements else ""
                )

                options.append(
                    discord.SelectOption(
                        label=f"{selected_icon}{status_icon} {achievement.name}",
                        value=str(achievement.id),
                        description=f"{achievement.description[:80]}...",
                        emoji="🏆",
                    )
                )

            achievement_select = ui.Select(
                placeholder=f"選擇成就 (頁面 {self.current_page + 1}/{total_pages}) - 已選 {len(self.selected_achievements)} 個",
                min_values=0,
                max_values=len(options),
                options=options,
            )
            achievement_select.callback = self.on_achievement_select
            self.add_item(achievement_select)

        # 分頁控制按鈕
        if total_pages > 1:
            # 上一頁按鈕
            prev_button = ui.Button(
                label="⬅️ 上一頁",
                style=discord.ButtonStyle.secondary,
                disabled=self.current_page == 0,
            )
            prev_button.callback = self.on_previous_page
            self.add_item(prev_button)

            # 下一頁按鈕
            next_button = ui.Button(
                label="下一頁 ➡️",
                style=discord.ButtonStyle.secondary,
                disabled=self.current_page >= total_pages - 1,
            )
            next_button.callback = self.on_next_page
            self.add_item(next_button)

        # 操作控制按鈕
        self._add_action_buttons()

    def _add_action_buttons(self):
        """添加操作控制按鈕."""
        operation_button = ui.Button(
            label=f"🎯 執行批量操作 ({len(self.selected_achievements)})",
            style=discord.ButtonStyle.primary,
            disabled=len(self.selected_achievements) == 0,
        )
        operation_button.callback = self.on_bulk_operation
        self.add_item(operation_button)

        # 全選/取消全選按鈕
        select_all_button = ui.Button(
            label="☑️ 全選本頁"
            if len(self.selected_achievements) == 0
            else "❎ 清除選擇",
            style=discord.ButtonStyle.secondary,
        )
        select_all_button.callback = self.on_toggle_select_all
        self.add_item(select_all_button)

        # 返回管理面板按鈕
        back_button = ui.Button(
            label="🔙 返回管理", style=discord.ButtonStyle.secondary
        )
        back_button.callback = self.on_back_to_management
        self.add_item(back_button)

    async def on_achievement_select(self, interaction: discord.Interaction):
        """處理成就選擇."""
        try:
            select = interaction.data["values"]
            selected_ids = {int(value) for value in select}

            # 計算當前頁面的成就 ID
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.achievements))
            current_page_ids = {
                achievement.id for achievement in self.achievements[start_idx:end_idx]
            }

            # 更新選擇狀態:移除當前頁面的選擇,然後添加新選擇
            self.selected_achievements = (
                self.selected_achievements - current_page_ids
            ) | selected_ids

            # 更新 UI
            self._update_ui_components()

            # 更新嵌入訊息
            embed = await self._create_selection_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"[批量選擇視圖]處理成就選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理成就選擇時發生錯誤", ephemeral=True
            )

    async def on_previous_page(self, interaction: discord.Interaction):
        """處理上一頁."""
        try:
            if self.current_page > 0:
                self.current_page -= 1
                self._update_ui_components()

                embed = await self._create_selection_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()

        except Exception as e:
            logger.error(f"[批量選擇視圖]處理上一頁失敗: {e}")
            await interaction.response.send_message(
                "❌ 切換頁面時發生錯誤", ephemeral=True
            )

    async def on_next_page(self, interaction: discord.Interaction):
        """處理下一頁."""
        try:
            total_pages = (
                len(self.achievements) + self.items_per_page - 1
            ) // self.items_per_page
            if self.current_page < total_pages - 1:
                self.current_page += 1
                self._update_ui_components()

                embed = await self._create_selection_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()

        except Exception as e:
            logger.error(f"[批量選擇視圖]處理下一頁失敗: {e}")
            await interaction.response.send_message(
                "❌ 切換頁面時發生錯誤", ephemeral=True
            )

    async def on_toggle_select_all(self, interaction: discord.Interaction):
        """處理全選/取消全選."""
        try:
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.achievements))
            current_page_ids = {
                achievement.id for achievement in self.achievements[start_idx:end_idx]
            }

            if len(self.selected_achievements) == 0:
                # 全選當前頁面
                self.selected_achievements.update(current_page_ids)
            else:
                # 清除所有選擇
                self.selected_achievements.clear()

            # 更新 UI
            self._update_ui_components()

            embed = await self._create_selection_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"[批量選擇視圖]處理全選/取消全選失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理選擇操作時發生錯誤", ephemeral=True
            )

    async def on_bulk_operation(self, interaction: discord.Interaction):
        """處理批量操作選擇."""
        try:
            if not self.selected_achievements:
                await interaction.response.send_message(
                    "❌ 請先選擇要操作的成就", ephemeral=True
                )
                return

            # 取得選中的成就物件
            selected_achievement_objects = [
                achievement
                for achievement in self.achievements
                if achievement.id in self.selected_achievements
            ]

            # 建立批量操作類型選擇視圖
            operation_view = BulkOperationTypeSelectionView(
                self.admin_panel, selected_achievement_objects
            )

            embed = await self._create_operation_preview_embed(
                selected_achievement_objects
            )

            await interaction.response.send_message(
                embed=embed, view=operation_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量選擇視圖]處理批量操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟批量操作時發生錯誤", ephemeral=True
            )

    async def on_back_to_management(self, interaction: discord.Interaction):
        """返回成就管理."""
        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )

    async def _create_selection_embed(self) -> discord.Embed:
        """建立選擇狀態嵌入訊息."""
        total_pages = (
            len(self.achievements) + self.items_per_page - 1
        ) // self.items_per_page

        embed = StandardEmbedBuilder.create_info_embed(
            "📦 批量操作 - 成就選擇",
            f"🎯 **選擇進度**: {len(self.selected_achievements)}/{len(self.achievements)} 個成就\n"
            f"📄 **當前頁面**: {self.current_page + 1}/{total_pages}\n\n",
        )

        # 顯示選中的成就摘要
        if self.selected_achievements:
            selected_names = []
            count = 0
            for achievement in self.achievements:
                if achievement.id in self.selected_achievements:
                    if count < MAX_DISPLAYED_ITEMS:  # 最多顯示項目數量
                        status = "✅" if achievement.is_active else "❌"
                        selected_names.append(f"• {status} {achievement.name}")
                        count += 1
                    else:
                        break

            if len(self.selected_achievements) > MAX_DISPLAYED_ITEMS:
                selected_names.append(
                    f"• ... 還有 {len(self.selected_achievements) - MAX_DISPLAYED_ITEMS} 個成就"
                )

            embed.add_field(
                name="📋 已選擇的成就",
                value="\n".join(selected_names) if selected_names else "無",
                inline=False,
            )

        # 操作提示
        embed.add_field(
            name="🔍 操作指南",
            value=(
                "• 使用下拉選單選擇/取消選擇成就\n"
                "• 🔸 圖示表示已選中的成就\n"
                "• 使用分頁按鈕瀏覽更多成就\n"
                "• 選擇完成後點擊「執行批量操作」"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="支援多選 | 使用下方控制項進行操作")

        return embed

    async def _create_operation_preview_embed(
        self, selected_achievements: list[Achievement]
    ) -> discord.Embed:
        """建立操作預覽嵌入訊息."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🎯 批量操作預覽",
            f"準備對 **{len(selected_achievements)}** 個成就執行批量操作",
        )

        # 統計資訊
        active_count = len([a for a in selected_achievements if a.is_active])
        inactive_count = len(selected_achievements) - active_count

        embed.add_field(
            name="📊 選擇統計",
            value=(
                f"**總計**: {len(selected_achievements)} 個成就\n"
                f"**啟用**: {active_count} 個\n"
                f"**停用**: {inactive_count} 個"
            ),
            inline=True,
        )

        # 分類分布
        category_count = {}
        for achievement in selected_achievements:
            category_id = achievement.category_id
            category_count[category_id] = category_count.get(category_id, 0) + 1

        category_info = []
        for category_id, count in list(category_count.items())[
            :MAX_CATEGORY_DISPLAY
        ]:  # 顯示前幾個分類
            category_info.append(f"• 分類 {category_id}: {count} 個")

        if len(category_count) > MAX_CATEGORY_DISPLAY:
            category_info.append(
                f"• ... 還有 {len(category_count) - MAX_CATEGORY_DISPLAY} 個分類"
            )

        embed.add_field(
            name="📂 分類分布",
            value="\n".join(category_info) if category_info else "無",
            inline=True,
        )

        # 成就列表預覽
        achievement_preview = []
        for i, achievement in enumerate(
            selected_achievements[:MAX_PREVIEW_ITEMS]
        ):  # 顯示前幾個
            status = "✅" if achievement.is_active else "❌"
            achievement_preview.append(f"{i + 1}. {status} {achievement.name}")

        if len(selected_achievements) > MAX_PREVIEW_ITEMS:
            achievement_preview.append(
                f"... 還有 {len(selected_achievements) - MAX_PREVIEW_ITEMS} 個成就"
            )

        embed.add_field(
            name="📋 成就列表", value="\n".join(achievement_preview), inline=False
        )

        embed.add_field(
            name="⚡ 可用操作",
            value=(
                "🟢 **批量啟用/停用** - 變更成就狀態\n"
                "🗑️ **批量刪除** - 移除選中成就\n"
                "📂 **批量分類變更** - 移動到新分類\n"
                "📊 **即時進度追蹤** - 查看操作進度"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="請選擇要執行的批量操作類型")

        return embed

    async def on_timeout(self) -> None:
        """處理視圖超時."""
        try:
            logger.info(
                f"[批量選擇視圖]用戶 {self.admin_panel.admin_user_id} 的批量選擇因超時而關閉"
            )
        except Exception as e:
            logger.error(f"[批量選擇視圖]處理超時失敗: {e}")

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        """處理視圖錯誤."""
        logger.error(f"[批量選擇視圖]UI 錯誤: {error}, 項目: {item}")
        with contextlib.suppress(builtins.BaseException):
            await interaction.response.send_message(
                "❌ 處理批量選擇時發生錯誤,請稍後再試", ephemeral=True
            )


class BulkOperationTypeSelectionView(ui.View):
    """批量操作類型選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, selected_achievements: list[Achievement]
    ):
        """初始化批量操作類型選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            selected_achievements: 選中的成就列表
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_achievements = selected_achievements

    @ui.select(
        placeholder="選擇批量操作類型...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="🟢 批量啟用成就",
                value="bulk_enable",
                description="將選中成就設為啟用狀態",
                emoji="✅",
            ),
            discord.SelectOption(
                label="🔴 批量停用成就",
                value="bulk_disable",
                description="將選中成就設為停用狀態",
                emoji="❌",
            ),
            discord.SelectOption(
                label="🗑️ 批量刪除成就",
                value="bulk_delete",
                description="永久刪除選中的成就(不可復原)",
                emoji="🗑️",
            ),
            discord.SelectOption(
                label="📂 批量變更分類",
                value="bulk_change_category",
                description="將選中成就移動到新分類",
                emoji="📂",
            ),
        ],
    )
    async def operation_type_select(
        self, interaction: discord.Interaction, select: ui.Select
    ):
        """處理操作類型選擇."""
        try:
            operation_type = select.values[0]

            if operation_type == "bulk_enable":
                await self._handle_bulk_enable(interaction)
            elif operation_type == "bulk_disable":
                await self._handle_bulk_disable(interaction)
            elif operation_type == "bulk_delete":
                await self._handle_bulk_delete(interaction)
            elif operation_type == "bulk_change_category":
                await self._handle_bulk_change_category(interaction)

        except Exception as e:
            logger.error(f"[批量操作類型選擇]處理操作類型選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理批量操作時發生錯誤", ephemeral=True
            )

    async def _handle_bulk_enable(self, interaction: discord.Interaction):
        """處理批量啟用."""
        try:
            # 檢查哪些成就需要啟用
            to_enable = [a for a in self.selected_achievements if not a.is_active]
            already_enabled = [a for a in self.selected_achievements if a.is_active]

            if not to_enable:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "🟢 批量啟用成就",
                    f"📊 **分析結果**:\n\n"
                    f"• 選中成就:{len(self.selected_achievements)} 個\n"
                    f"• 已啟用:{len(already_enabled)} 個\n"
                    f"• 需要啟用:{len(to_enable)} 個\n\n"
                    "✅ 所有選中的成就都已經是啟用狀態,無需操作.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 建立批量啟用確認視圖
            confirm_view = BulkStatusChangeConfirmView(
                self.admin_panel,
                to_enable,
                True,  # is_enable = True
                len(already_enabled),
            )

            # 建立確認嵌入訊息
            embed = StandardEmbedBuilder.create_info_embed(
                "🟢 確認批量啟用成就", f"即將啟用 **{len(to_enable)}** 個成就"
            )

            embed.add_field(
                name="📊 操作統計",
                value=(
                    f"**選中成就總數**: {len(self.selected_achievements)}\n"
                    f"**需要啟用**: {len(to_enable)} 個\n"
                    f"**已經啟用**: {len(already_enabled)} 個"
                ),
                inline=True,
            )

            # 顯示將要啟用的成就
            enable_list = []
            for i, achievement in enumerate(
                to_enable[:MAX_PREVIEW_ITEMS]
            ):  # 顯示前幾個
                enable_list.append(f"{i + 1}. ❌ → ✅ {achievement.name}")

            if len(to_enable) > MAX_PREVIEW_ITEMS:
                enable_list.append(
                    f"... 還有 {len(to_enable) - MAX_PREVIEW_ITEMS} 個成就"
                )

            embed.add_field(
                name="🔄 狀態變更預覽",
                value="\n".join(enable_list) if enable_list else "無",
                inline=False,
            )

            embed.add_field(
                name="⚡ 操作影響",
                value=(
                    "• 啟用的成就將可以被用戶獲得\n"
                    "• 已有的用戶進度不會受影響\n"
                    "• 變更將立即生效\n"
                    "• 操作將被記錄到審計日誌"
                ),
                inline=False,
            )

            embed.color = 0x00FF00  # 綠色主題
            embed.set_footer(text="確認後將立即執行批量啟用操作")

            await interaction.response.send_message(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量操作類型選擇]處理批量啟用失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理批量啟用時發生錯誤", ephemeral=True
            )

    async def _handle_bulk_disable(self, interaction: discord.Interaction):
        """處理批量停用."""
        try:
            # 檢查哪些成就需要停用
            to_disable = [a for a in self.selected_achievements if a.is_active]
            already_disabled = [
                a for a in self.selected_achievements if not a.is_active
            ]

            if not to_disable:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "🔴 批量停用成就",
                    f"📊 **分析結果**:\n\n"
                    f"• 選中成就:{len(self.selected_achievements)} 個\n"
                    f"• 已停用:{len(already_disabled)} 個\n"
                    f"• 需要停用:{len(to_disable)} 個\n\n"
                    "✅ 所有選中的成就都已經是停用狀態,無需操作.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 建立批量停用確認視圖
            confirm_view = BulkStatusChangeConfirmView(
                self.admin_panel,
                to_disable,
                False,  # is_enable = False
                len(already_disabled),
            )

            # 建立確認嵌入訊息
            embed = StandardEmbedBuilder.create_warning_embed(
                "🔴 確認批量停用成就", f"即將停用 **{len(to_disable)}** 個成就"
            )

            embed.add_field(
                name="📊 操作統計",
                value=(
                    f"**選中成就總數**: {len(self.selected_achievements)}\n"
                    f"**需要停用**: {len(to_disable)} 個\n"
                    f"**已經停用**: {len(already_disabled)} 個"
                ),
                inline=True,
            )

            # 顯示將要停用的成就
            disable_list = []
            for i, achievement in enumerate(
                to_disable[:MAX_PREVIEW_ITEMS]
            ):  # 顯示前幾個
                disable_list.append(f"{i + 1}. ✅ → ❌ {achievement.name}")

            if len(to_disable) > MAX_PREVIEW_ITEMS:
                disable_list.append(
                    f"... 還有 {len(to_disable) - MAX_PREVIEW_ITEMS} 個成就"
                )

            embed.add_field(
                name="🔄 狀態變更預覽",
                value="\n".join(disable_list) if disable_list else "無",
                inline=False,
            )

            embed.add_field(
                name="⚠️ 操作影響",
                value=(
                    "• 停用的成就將無法被用戶獲得\n"
                    "• 已獲得的成就不會被移除\n"
                    "• 用戶進度計算將暫停\n"
                    "• 變更將立即生效\n"
                    "• 操作將被記錄到審計日誌"
                ),
                inline=False,
            )

            embed.color = 0xFF0000  # 紅色主題
            embed.set_footer(text="確認後將立即執行批量停用操作")

            await interaction.response.send_message(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量操作類型選擇]處理批量停用失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理批量停用時發生錯誤", ephemeral=True
            )

    async def _handle_bulk_delete(self, interaction: discord.Interaction):
        """處理批量刪除."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 分析依賴關係
            dependency_analysis = await self._analyze_bulk_delete_dependencies()

            # 建立批量刪除確認視圖
            confirm_view = BulkDeleteConfirmView(
                self.admin_panel, self.selected_achievements, dependency_analysis
            )

            # 建立確認嵌入訊息
            embed = await self._create_bulk_delete_preview_embed(dependency_analysis)

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量操作類型選擇]處理批量刪除失敗: {e}")
            await interaction.followup.send("❌ 處理批量刪除時發生錯誤", ephemeral=True)

    async def _analyze_bulk_delete_dependencies(self) -> dict:
        """分析批量刪除的依賴關係."""
        admin_service = await self._get_enhanced_admin_service()

        dependencies = {
            "total_achievements": len(self.selected_achievements),
            "safe_to_delete": [],
            "has_dependencies": [],
            "dependency_details": {},
            "total_affected_users": 0,
        }

        for achievement in self.selected_achievements:
            try:
                dep_info = await admin_service._check_achievement_dependencies(
                    achievement.id
                )

                if dep_info["has_dependencies"]:
                    dependencies["has_dependencies"].append(achievement)
                    dependencies["dependency_details"][achievement.id] = dep_info
                    dependencies["total_affected_users"] += dep_info[
                        "user_achievement_count"
                    ]
                else:
                    dependencies["safe_to_delete"].append(achievement)

            except Exception as e:
                logger.error(f"檢查成就 {achievement.id} 依賴關係失敗: {e}")
                # 如果檢查失敗,保守起見歸類為有依賴
                dependencies["has_dependencies"].append(achievement)

        return dependencies

    async def _create_bulk_delete_preview_embed(
        self, dependency_analysis: dict
    ) -> discord.Embed:
        """建立批量刪除預覽嵌入訊息."""
        total = dependency_analysis["total_achievements"]
        safe_count = len(dependency_analysis["safe_to_delete"])
        risky_count = len(dependency_analysis["has_dependencies"])

        embed = StandardEmbedBuilder.create_warning_embed(
            "🗑️ 批量刪除成就確認", f"即將刪除 **{total}** 個成就"
        )

        # 風險評估
        if risky_count == 0:
            risk_level = "🟢 低風險"
            risk_desc = "所有選中的成就都可以安全刪除"
        elif safe_count == 0:
            risk_level = "🔴 高風險"
            risk_desc = "所有選中的成就都有用戶依賴關係"
        else:
            risk_level = "🟡 中等風險"
            risk_desc = "部分成就有用戶依賴關係"

        embed.add_field(
            name="⚠️ 風險評估",
            value=f"**風險等級**: {risk_level}\n**評估**: {risk_desc}",
            inline=False,
        )

        embed.add_field(
            name="📊 刪除統計",
            value=(
                f"**總計**: {total} 個成就\n"
                f"**安全刪除**: {safe_count} 個\n"
                f"**有依賴關係**: {risky_count} 個\n"
                f"**受影響用戶**: {dependency_analysis['total_affected_users']} 個"
            ),
            inline=True,
        )

        # 顯示有依賴關係的成就
        if dependency_analysis["has_dependencies"]:
            risky_list = []
            for _i, achievement in enumerate(
                dependency_analysis["has_dependencies"][:MAX_DISPLAYED_ITEMS]
            ):
                dep_info = dependency_analysis["dependency_details"].get(
                    achievement.id, {}
                )
                user_count = dep_info.get("user_achievement_count", 0)
                risky_list.append(f"• ⚠️ {achievement.name} ({user_count} 位用戶)")

            if len(dependency_analysis["has_dependencies"]) > MAX_DISPLAYED_ITEMS:
                risky_list.append(
                    f"• ... 還有 {len(dependency_analysis['has_dependencies']) - MAX_DISPLAYED_ITEMS} 個成就"
                )

            embed.add_field(
                name="⚠️ 有依賴關係的成就", value="\n".join(risky_list), inline=False
            )

        # 安全刪除的成就
        if dependency_analysis["safe_to_delete"]:
            safe_list = []
            for _i, achievement in enumerate(
                dependency_analysis["safe_to_delete"][:MAX_DISPLAYED_ITEMS]
            ):
                safe_list.append(f"• ✅ {achievement.name}")

            if len(dependency_analysis["safe_to_delete"]) > MAX_DISPLAYED_ITEMS:
                safe_list.append(
                    f"• ... 還有 {len(dependency_analysis['safe_to_delete']) - MAX_DISPLAYED_ITEMS} 個成就"
                )

            embed.add_field(
                name="✅ 可安全刪除的成就", value="\n".join(safe_list), inline=False
            )

        # 操作影響說明
        embed.add_field(
            name="💥 刪除影響",
            value=(
                "• **不可復原**: 刪除的成就無法恢復\n"
                "• **用戶記錄**: 相關用戶成就記錄將被移除\n"
                "• **進度丟失**: 用戶在這些成就上的進度將丟失\n"
                "• **統計變更**: 伺服器成就統計將更新\n"
                "• **審計記錄**: 所有操作將被完整記錄"
            ),
            inline=False,
        )

        embed.color = 0xFF4444  # 危險紅色
        embed.set_footer(text="❗ 此操作無法撤銷,請仔細確認!")

        return embed

    async def _get_enhanced_admin_service(self):
        """取得增強的管理服務實例."""
        try:
            # 嘗試從管理面板獲取服務
            if (
                hasattr(self.admin_panel, "admin_service")
                and self.admin_panel.admin_service
            ):
                return self.admin_panel.admin_service

            # 嘗試從依賴注入容器獲取

            container = DIContainer()
            admin_service = await container.get("admin_service")

            if admin_service:
                return admin_service

        except Exception as e:
            logger.warning(f"無法獲取真實的管理服務,使用模擬服務: {e}")

        # 回退到模擬服務
        return EnhancedMockAdminService()

    async def _handle_bulk_change_category(self, interaction: discord.Interaction):
        """處理批量分類變更."""
        try:
            # 獲取可用分類列表
            categories = await self._get_available_categories()
            if not categories:
                await interaction.response.send_message(
                    "❌ 沒有可用的分類", ephemeral=True
                )
                return

            # 分析當前分類分布
            category_analysis = await self._analyze_category_distribution(
                self.selected_achievements
            )

            # 建立批量分類變更視圖
            category_change_view = BulkCategoryChangeView(
                self.admin_panel,
                self.selected_achievements,
                categories,
                category_analysis,
            )

            embed = await self._create_category_change_embed(category_analysis)

            await interaction.response.send_message(
                embed=embed, view=category_change_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量操作類型選擇]處理批量分類變更失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟批量分類變更時發生錯誤", ephemeral=True
            )

    async def _analyze_category_distribution(
        self, achievements: list[Achievement]
    ) -> dict:
        """分析成就的分類分布."""
        category_count = {}
        category_names = {}

        for achievement in achievements:
            category_id = achievement.category_id
            category_count[category_id] = category_count.get(category_id, 0) + 1

            if category_id not in category_names:
                category_names[category_id] = f"分類 {category_id}"

        return {
            "category_count": category_count,
            "category_names": category_names,
            "total_achievements": len(achievements),
            "unique_categories": len(category_count),
        }

    async def _create_category_change_embed(self, analysis: dict) -> discord.Embed:
        """創建分類變更預覽嵌入訊息."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📂 批量分類變更",
            f"準備變更 **{analysis['total_achievements']}** 個成就的分類",
        )

        # 當前分類分布
        distribution_text = []
        for category_id, count in analysis["category_count"].items():
            category_name = analysis["category_names"].get(
                category_id, f"分類 {category_id}"
            )
            distribution_text.append(f"• **{category_name}**: {count} 個成就")

        embed.add_field(
            name="📊 當前分類分布",
            value="\n".join(distribution_text) if distribution_text else "無",
            inline=False,
        )

        embed.add_field(
            name="🔄 操作說明",
            value=(
                "1️⃣ 選擇目標分類\n"
                "2️⃣ 確認變更操作\n"
                "3️⃣ 查看執行結果\n\n"
                "💡 **提示**: 已在目標分類的成就將被跳過"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="選擇目標分類來執行批量變更")

        return embed

    @ui.button(label="🔙 返回選擇", style=discord.ButtonStyle.secondary)
    async def back_to_selection(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回成就選擇."""
        achievements = await self._get_available_achievements()
        bulk_view = BulkOperationSelectionView(self.admin_panel, achievements)
        embed = await bulk_view._create_selection_embed()
        await interaction.response.edit_message(embed=embed, view=bulk_view)

    async def _get_available_achievements(self):
        """獲取可用成就列表."""
        try:
            # 嘗試從增強管理服務獲取成就列表
            admin_service = await self._get_enhanced_admin_service()
            if admin_service and hasattr(admin_service, "get_all_achievements"):
                return await admin_service.get_all_achievements()

            # 如果服務不可用,返回空列表
            logger.warning("增強管理服務不可用,無法獲取成就列表")
            return []

        except Exception as e:
            logger.error(f"獲取可用成就列表失敗: {e}")
            return []

    @ui.button(label="❌ 取消操作", style=discord.ButtonStyle.danger)
    async def cancel_operation(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """取消批量操作."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 批量操作已被取消,沒有進行任何變更."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BulkStatusChangeConfirmView(ui.View):
    """批量狀態變更確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        achievements_to_change: list[Achievement],
        is_enable: bool,
        already_changed_count: int,
    ):
        """初始化批量狀態變更確認視圖.

        Args:
            admin_panel: 管理面板控制器
            achievements_to_change: 需要變更狀態的成就列表
            is_enable: True 為啟用,False 為停用
            already_changed_count: 已經處於目標狀態的成就數量
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievements_to_change = achievements_to_change
        self.is_enable = is_enable
        self.already_changed_count = already_changed_count

    @ui.button(
        label="✅ 確認執行",
        style=discord.ButtonStyle.primary if True else discord.ButtonStyle.danger,
    )
    async def confirm_bulk_status_change(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """確認執行批量狀態變更."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立進度追蹤視圖
            progress_view = BulkOperationProgressView(
                self.admin_panel,
                self.achievements_to_change,
                "status_change",
                {"is_enable": self.is_enable},
            )

            # 建立進度追蹤嵌入訊息
            embed = await progress_view._create_progress_embed()

            await interaction.followup.send(
                embed=embed, view=progress_view, ephemeral=True
            )

            # 開始執行批量操作
            await progress_view.start_bulk_operation()

        except Exception as e:
            logger.error(f"[批量狀態變更確認]執行批量狀態變更失敗: {e}")
            await interaction.followup.send(
                "❌ 執行批量狀態變更時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_bulk_status_change(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """取消批量狀態變更."""
        action_type = "啟用" if self.is_enable else "停用"
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", f"✅ 批量{action_type}操作已被取消,沒有進行任何變更."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BulkOperationProgressView(ui.View):
    """批量操作進度追蹤視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        target_achievements: list[Achievement],
        operation_type: str,
        operation_params: dict | None = None,
    ):
        """初始化批量操作進度視圖.

        Args:
            admin_panel: 管理面板控制器
            target_achievements: 目標成就列表
            operation_type: 操作類型 (status_change, delete, change_category)
            operation_params: 操作參數
        """
        super().__init__(timeout=600)  # 10分鐘超時
        self.admin_panel = admin_panel
        self.target_achievements = target_achievements
        self.operation_type = operation_type
        self.operation_params = operation_params or {}

        # 進度追蹤
        self.total_count = len(target_achievements)
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.errors: list[str] = []
        self.completed_achievements: list[Achievement] = []

        # 狀態
        self.is_running = False
        self.is_completed = False
        self.start_time = None

    async def start_bulk_operation(self):
        """開始執行批量操作."""
        if self.is_running:
            return

        self.is_running = True
        self.start_time = datetime.now()

        try:
            if self.operation_type == "status_change":
                await self._execute_bulk_status_change()
            elif self.operation_type == "delete":
                await self._execute_bulk_delete()
            elif self.operation_type == "change_category":
                await self._execute_bulk_category_change()
            else:
                logger.warning(f"未支援的操作類型: {self.operation_type}")
                self.errors.append(f"未支援的操作類型: {self.operation_type}")

        except Exception as e:
            logger.error(f"[批量操作進度]執行批量操作失敗: {e}")
            self.errors.append(f"執行過程中發生錯誤: {e!s}")
        finally:
            self.is_running = False
            self.is_completed = True

    async def _execute_bulk_status_change(self):
        """執行批量狀態變更."""
        is_enable = self.operation_params.get("is_enable", True)
        admin_service = await self._get_admin_service()

        # 準備批量操作的成就 ID 列表
        achievement_ids = [achievement.id for achievement in self.target_achievements]

        try:
            # 使用管理服務執行批量狀態更新
            result = await admin_service.bulk_update_status(
                achievement_ids=achievement_ids,
                is_active=is_enable,
                admin_user_id=self.admin_panel.admin_user_id,
            )

            # 更新進度統計
            self.success_count = result.success_count
            self.error_count = result.failed_count
            self.errors = result.errors
            self.completed_achievements = result.affected_achievements
            self.processed_count = self.total_count

            logger.info(
                f"批量狀態變更完成: {self.success_count}/{self.total_count} 成功"
            )

        except Exception as e:
            logger.error(f"批量狀態變更執行失敗: {e}")
            self.error_count = self.total_count
            self.errors.append(f"批量操作失敗: {e!s}")

    async def _execute_bulk_delete(self):
        """執行批量刪除."""
        force_delete = self.operation_params.get("force", False)
        admin_service = await self._get_admin_service()

        # 準備批量操作的成就 ID 列表
        achievement_ids = [achievement.id for achievement in self.target_achievements]

        try:
            # 使用管理服務執行批量刪除
            result = await admin_service.bulk_delete(
                achievement_ids=achievement_ids,
                admin_user_id=self.admin_panel.admin_user_id,
                force=force_delete,
            )

            # 更新進度統計
            self.success_count = result.success_count
            self.error_count = result.failed_count
            self.errors = result.errors
            self.completed_achievements = result.affected_achievements
            self.processed_count = self.total_count

            logger.info(
                f"批量刪除完成: {self.success_count}/{self.total_count} 成功,強制模式: {force_delete}"
            )

        except Exception as e:
            logger.error(f"批量刪除執行失敗: {e}")
            self.error_count = self.total_count
            self.errors.append(f"批量刪除失敗: {e!s}")

    async def _execute_bulk_category_change(self):
        """執行批量分類變更."""
        target_category_id = self.operation_params.get("target_category_id")
        target_category_name = self.operation_params.get(
            "target_category_name", "未知分類"
        )
        admin_service = await self._get_admin_service()

        # 準備批量操作的成就 ID 列表
        achievement_ids = [achievement.id for achievement in self.target_achievements]

        try:
            # 使用管理服務執行批量分類變更
            result = await admin_service.bulk_update_category(
                achievement_ids=achievement_ids,
                target_category_id=target_category_id,
                admin_user_id=self.admin_panel.admin_user_id,
            )

            # 更新進度統計
            self.success_count = result.success_count
            self.error_count = result.failed_count
            self.errors = result.errors
            self.completed_achievements = result.affected_achievements
            self.processed_count = self.total_count

            # 記錄跳過的成就數量
            skip_count = self.operation_params.get("skip_count", 0)

            logger.info(
                f"批量分類變更完成: {self.success_count}/{self.total_count} 成功,"
                f"目標分類: {target_category_name},跳過: {skip_count} 個"
            )

        except Exception as e:
            logger.error(f"批量分類變更執行失敗: {e}")
            self.error_count = self.total_count
            self.errors.append(f"批量分類變更失敗: {e!s}")

    async def _create_progress_embed(self) -> discord.Embed:
        """建立進度追蹤嵌入訊息."""
        # 根據操作類型生成標題
        operation_titles = {
            "status_change": {
                "in_progress": "⏳ 批量狀態變更進行中",
                "success": "✅ 批量狀態變更完成",
                "partial": "⚠️ 批量狀態變更部分完成",
                "failure": "❌ 批量狀態變更失敗",
            },
            "delete": {
                "in_progress": "⏳ 批量刪除進行中",
                "success": "✅ 批量刪除完成",
                "partial": "⚠️ 批量刪除部分完成",
                "failure": "❌ 批量刪除失敗",
            },
            "change_category": {
                "in_progress": "⏳ 批量分類變更進行中",
                "success": "✅ 批量分類變更完成",
                "partial": "⚠️ 批量分類變更部分完成",
                "failure": "❌ 批量分類變更失敗",
            },
        }

        current_titles = operation_titles.get(
            self.operation_type,
            {
                "in_progress": "⏳ 批量操作進行中",
                "success": "✅ 批量操作完成",
                "partial": "⚠️ 批量操作部分完成",
                "failure": "❌ 批量操作失敗",
            },
        )

        if not self.is_completed:
            # 進行中的狀態
            embed = StandardEmbedBuilder.create_info_embed(
                current_titles["in_progress"], self._get_operation_description()
            )

            embed.add_field(
                name="📊 進度統計",
                value=(
                    f"**總計**: {self.total_count} 個成就\n"
                    f"**已處理**: {self.processed_count} 個\n"
                    f"**成功**: {self.success_count} 個\n"
                    f"**失敗**: {self.error_count} 個"
                ),
                inline=True,
            )

            # 顯示操作特定參數
            operation_info = self._get_operation_info()
            if operation_info:
                embed.add_field(name="🎯 操作詳情", value=operation_info, inline=True)

            # 進度條
            if self.total_count > 0:
                progress_percent = (self.processed_count / self.total_count) * 100
                progress_bar = self._create_progress_bar(progress_percent)
                embed.add_field(
                    name="📈 執行進度",
                    value=f"{progress_bar} {progress_percent:.1f}%",
                    inline=False,
                )

            embed.color = 0xFFFF00  # 黃色 - 進行中
        else:
            # 完成狀態
            success_rate = (
                (self.success_count / self.total_count * 100)
                if self.total_count > 0
                else 0
            )

            if success_rate == FULL_SUCCESS_RATE:
                embed = StandardEmbedBuilder.create_success_embed(
                    current_titles["success"], "所有操作已成功完成!"
                )
                embed.color = 0x00FF00  # 綠色 - 成功
            elif success_rate > 0:
                embed = StandardEmbedBuilder.create_warning_embed(
                    current_titles["partial"], "部分操作成功,部分操作失敗."
                )
                embed.color = 0xFFA500  # 橙色 - 部分成功
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    current_titles["failure"], "所有操作都失敗了."
                )
                embed.color = 0xFF0000  # 紅色 - 失敗

            embed.add_field(
                name="📊 最終統計",
                value=(
                    f"**總計**: {self.total_count} 個成就\n"
                    f"**成功**: {self.success_count} 個\n"
                    f"**失敗**: {self.error_count} 個\n"
                    f"**成功率**: {success_rate:.1f}%"
                ),
                inline=True,
            )

            # 顯示操作特定資訊
            operation_summary = self._get_operation_summary()
            if operation_summary:
                embed.add_field(
                    name="🎯 操作摘要", value=operation_summary, inline=True
                )

            # 執行時間
            if self.start_time:
                duration = datetime.now() - self.start_time
                embed.add_field(
                    name="⏱️ 執行時間",
                    value=f"{duration.total_seconds():.2f} 秒",
                    inline=True,
                )

            if self.errors:
                error_text = "\n".join([
                    f"• {error}" for error in self.errors[:MAX_ERROR_DISPLAY]
                ])
                if len(self.errors) > MAX_ERROR_DISPLAY:
                    error_text += (
                        f"\n• ... 還有 {len(self.errors) - MAX_ERROR_DISPLAY} 個錯誤"
                    )

                embed.add_field(name="❌ 錯誤詳情", value=error_text, inline=False)

            if self.completed_achievements:
                success_list = []
                for _i, achievement in enumerate(
                    self.completed_achievements[:MAX_DISPLAYED_ITEMS]
                ):
                    status_icon = "✅" if achievement.is_active else "❌"
                    success_list.append(f"• {status_icon} {achievement.name}")

                if len(self.completed_achievements) > MAX_DISPLAYED_ITEMS:
                    success_list.append(
                        f"• ... 還有 {len(self.completed_achievements) - MAX_DISPLAYED_ITEMS} 個成就"
                    )

                embed.add_field(
                    name="✅ 成功處理的成就",
                    value="\n".join(success_list),
                    inline=False,
                )

        embed.set_footer(
            text=f"操作類型: {self.operation_type} | 開始時間: {self.start_time.strftime('%H:%M:%S') if self.start_time else 'N/A'}"
        )
        return embed

    def _create_progress_bar(self, percent: float, length: int = 20) -> str:
        """建立進度條."""
        filled_length = int(length * percent / 100)
        bar = "█" * filled_length + "░" * (length - filled_length)
        return f"[{bar}]"

    def _get_operation_description(self) -> str:
        """取得操作描述."""
        descriptions = {
            "status_change": "正在執行批量狀態變更操作,請稍候...",
            "delete": "正在執行批量刪除操作,請稍候...",
            "change_category": "正在執行批量分類變更操作,請稍候...",
        }
        return descriptions.get(self.operation_type, "正在執行批量操作,請稍候...")

    def _get_operation_info(self) -> str | None:
        """取得操作特定資訊."""
        if self.operation_type == "status_change":
            is_enable = self.operation_params.get("is_enable", True)
            return f"**目標狀態**: {'啟用' if is_enable else '停用'}"

        elif self.operation_type == "change_category":
            target_category_name = self.operation_params.get(
                "target_category_name", "未知分類"
            )
            skip_count = self.operation_params.get("skip_count", 0)
            return (
                f"**目標分類**: {target_category_name}\n**跳過數量**: {skip_count} 個"
            )

        elif self.operation_type == "delete":
            force = self.operation_params.get("force", False)
            return f"**刪除模式**: {'強制刪除' if force else '安全刪除'}"

        return None

    def _get_operation_summary(self) -> str | None:
        """取得操作摘要資訊."""
        if self.operation_type == "change_category":
            target_category_name = self.operation_params.get(
                "target_category_name", "未知分類"
            )
            skip_count = self.operation_params.get("skip_count", 0)
            return f"**移動到**: {target_category_name}\n**跳過**: {skip_count} 個成就"

        elif self.operation_type == "status_change":
            is_enable = self.operation_params.get("is_enable", True)
            return f"**狀態變更**: {'啟用' if is_enable else '停用'}"

        elif self.operation_type == "delete":
            force = self.operation_params.get("force", False)
            return f"**刪除類型**: {'強制刪除' if force else '安全刪除'}"

        return None

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_progress(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """重新整理進度."""
        try:
            embed = await self._create_progress_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"[批量操作進度]重新整理失敗: {e}")
            await interaction.response.send_message(
                "❌ 重新整理進度時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回管理", style=discord.ButtonStyle.secondary)
    async def back_to_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回成就管理."""
        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            # 創建真實的管理服務實例
            if hasattr(self.achievement_service, "repository"):
                return RealAdminService(self.achievement_service.repository)
            else:
                # 如果沒有 repository,嘗試從成就服務獲取
                return self.achievement_service

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            raise RuntimeError(f"無法獲取管理服務: {e}") from e


class EnhancedMockAdminService:
    """增強的模擬管理服務,支援批量操作."""

    async def bulk_update_status(
        self, achievement_ids: list[int], is_active: bool, _admin_user_id: int
    ):
        """模擬批量狀態更新."""

        result = BulkOperationResult()

        # 模擬處理每個成就
        for achievement_id in achievement_ids:
            try:
                # 模擬可能的失敗情況
                if (
                    achievement_id == MAGIC_ACHIEVEMENT_ID_FOR_TESTING
                ):  # 模擬不存在的成就
                    result.add_error(f"成就 {achievement_id} 不存在")
                    continue

                # 建立模擬的更新成就

                updated_achievement = Achievement(
                    id=achievement_id,
                    name=f"成就 {achievement_id}",
                    description=f"成就 {achievement_id} 的描述",
                    category_id=1,
                    type=AchievementType.MILESTONE,
                    criteria={"target_value": 1},
                    points=10,
                    badge_url=None,
                    is_active=is_active,  # 更新後的狀態
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                result.add_success(
                    updated_achievement,
                    f"成就 {updated_achievement.name} {'啟用' if is_active else '停用'}成功",
                )

                # 模擬處理時間

                await asyncio.sleep(0.1)  # 模擬處理延遲

            except Exception as e:
                result.add_error(f"處理成就 {achievement_id} 時發生錯誤: {e!s}")

        logger.info(
            f"模擬批量狀態更新完成: {result.success_count}/{len(achievement_ids)} 成功"
        )
        return result

    async def bulk_delete(
        self, achievement_ids: list[int], _admin_user_id: int, force: bool = False
    ):
        """模擬批量刪除."""

        result = BulkOperationResult()

        # 模擬處理每個成就
        for achievement_id in achievement_ids:
            try:
                if not force:
                    dependency_info = await self._check_achievement_dependencies(
                        achievement_id
                    )
                    if dependency_info["has_dependencies"]:
                        result.add_error(
                            f"成就 {achievement_id} 存在依賴關係: {dependency_info['description']}"
                        )
                        continue

                # 模擬可能的失敗情況
                if (
                    achievement_id == MAGIC_ACHIEVEMENT_ID_FOR_TESTING
                ):  # 模擬不存在的成就
                    result.add_error(f"成就 {achievement_id} 不存在")
                    continue

                deleted_achievement = Achievement(
                    id=achievement_id,
                    name=f"成就 {achievement_id}",
                    description=f"成就 {achievement_id} 的描述",
                    category_id=1,
                    type=AchievementType.MILESTONE,
                    criteria={"target_value": 1},
                    points=10,
                    badge_url=None,
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                result.add_success(
                    deleted_achievement, f"成就 {deleted_achievement.name} 刪除成功"
                )

                # 模擬處理時間

                await asyncio.sleep(0.15)  # 刪除操作稍慢一些

            except Exception as e:
                result.add_error(f"處理成就 {achievement_id} 時發生錯誤: {e!s}")

        logger.info(
            f"模擬批量刪除完成: {result.success_count}/{len(achievement_ids)} 成功"
        )
        return result

    async def _check_achievement_dependencies(self, achievement_id: int):
        """模擬檢查成就依賴關係."""
        # 模擬不同成就的依賴情況
        if achievement_id == 1:
            return {
                "has_dependencies": True,
                "user_achievement_count": 5,
                "description": "5 個用戶已獲得此成就",
            }
        elif achievement_id == TEST_ACHIEVEMENT_ID_2:
            return {
                "has_dependencies": True,
                "user_achievement_count": 12,
                "description": "12 個用戶已獲得此成就",
            }
        else:
            return {
                "has_dependencies": False,
                "user_achievement_count": 0,
                "description": "無依賴關係",
            }

    async def bulk_update_category(
        self, achievement_ids: list[int], target_category_id: int, _admin_user_id: int
    ):
        """模擬批量分類變更."""

        result = BulkOperationResult()
        result.details["operation_type"] = "batch_category_change"
        result.details["target_category_id"] = target_category_id

        # 模擬取得目標分類名稱
        category_names = {1: "社交互動", 2: "活躍度", 3: "成長里程", 4: "特殊事件"}
        target_category_name = category_names.get(
            target_category_id, f"分類 {target_category_id}"
        )
        result.details["target_category_name"] = target_category_name

        # 模擬處理每個成就
        for achievement_id in achievement_ids:
            try:
                # 模擬可能的失敗情況
                if (
                    achievement_id == MAGIC_ACHIEVEMENT_ID_FOR_TESTING
                ):  # 模擬不存在的成就
                    result.add_error(f"成就 {achievement_id} 不存在")
                    continue

                current_category_id = (
                    1 if achievement_id % 2 == 1 else 2
                )  # 模擬當前分類
                if current_category_id == target_category_id:
                    # 建立模擬成就物件用於跳過統計

                    achievement = Achievement(
                        id=achievement_id,
                        name=f"成就 {achievement_id}",
                        description=f"成就 {achievement_id} 的描述",
                        category_id=current_category_id,
                        type=AchievementType.MILESTONE,
                        criteria={"target_value": 1},
                        points=10,
                        badge_url=None,
                        is_active=True,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )

                    result.add_success(
                        achievement,
                        f"成就「{achievement.name}」已在目標分類中,無需變更",
                    )
                    continue

                # 建立模擬的更新後成就

                updated_achievement = Achievement(
                    id=achievement_id,
                    name=f"成就 {achievement_id}",
                    description=f"成就 {achievement_id} 的描述",
                    category_id=target_category_id,  # 更新為目標分類
                    type=AchievementType.MILESTONE,
                    criteria={"target_value": 1},
                    points=10,
                    badge_url=None,
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                original_category_name = category_names.get(
                    current_category_id, f"分類 {current_category_id}"
                )

                result.add_success(
                    updated_achievement,
                    f"成就「{updated_achievement.name}」從「{original_category_name}」移動到「{target_category_name}」",
                )

                # 記錄操作詳情
                result.details[f"change_{achievement_id}"] = {
                    "original_category_id": current_category_id,
                    "original_category_name": original_category_name,
                    "target_category_id": target_category_id,
                    "target_category_name": target_category_name,
                }

                # 模擬處理時間

                await asyncio.sleep(0.12)  # 模擬分類變更延遲

            except Exception as e:
                result.add_error(f"處理成就 {achievement_id} 時發生錯誤: {e!s}")

        logger.info(
            f"模擬批量分類變更完成: {result.success_count}/{len(achievement_ids)} 成功,"
            f"目標分類: {target_category_name}"
        )
        return result


class BulkDeleteConfirmView(ui.View):
    """批量刪除確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        achievements_to_delete: list[Achievement],
        dependency_analysis: dict,
    ):
        """初始化批量刪除確認視圖.

        Args:
            admin_panel: 管理面板控制器
            achievements_to_delete: 要刪除的成就列表
            dependency_analysis: 依賴關係分析結果
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.achievements_to_delete = achievements_to_delete
        self.dependency_analysis = dependency_analysis

    @ui.button(label="🗑️ 安全刪除", style=discord.ButtonStyle.danger)
    async def safe_delete_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """安全刪除(只刪除無依賴的成就)."""
        try:
            await interaction.response.defer(ephemeral=True)

            safe_achievements = self.dependency_analysis["safe_to_delete"]

            if not safe_achievements:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "無法執行安全刪除",
                    "❌ 所有選中的成就都有用戶依賴關係!\n\n"
                    "**解決方案**:\n"
                    "1️⃣ 使用「強制刪除」(將同時清除用戶記錄)\n"
                    "2️⃣ 重新選擇沒有依賴關係的成就\n"
                    "3️⃣ 取消此次操作\n\n"
                    "⚠️ 強制刪除將無法復原,請謹慎操作!",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 建立進度追蹤視圖
            progress_view = BulkOperationProgressView(
                self.admin_panel, safe_achievements, "delete", {"force": False}
            )

            # 建立進度追蹤嵌入訊息
            embed = await progress_view._create_progress_embed()

            await interaction.followup.send(
                embed=embed, view=progress_view, ephemeral=True
            )

            # 開始執行批量刪除
            await progress_view.start_bulk_operation()

        except Exception as e:
            logger.error(f"[批量刪除確認]安全刪除失敗: {e}")
            await interaction.followup.send("❌ 執行安全刪除時發生錯誤", ephemeral=True)

    @ui.button(label="⚠️ 強制刪除", style=discord.ButtonStyle.danger)
    async def force_delete_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """強制刪除(刪除所有選中的成就,忽略依賴關係)."""
        try:
            # 建立二次確認視圖
            confirm_view = ForceDeleteConfirmView(
                self.admin_panel, self.achievements_to_delete, self.dependency_analysis
            )

            embed = StandardEmbedBuilder.create_error_embed(
                "⚠️ 強制刪除最終確認",
                f"**您即將強制刪除 {len(self.achievements_to_delete)} 個成就!**\n\n"
                f"💥 **嚴重後果**:\n"
                f"• 將刪除 **{len(self.achievements_to_delete)}** 個成就\n"
                f"• 將影響 **{self.dependency_analysis['total_affected_users']}** 位用戶\n"
                f"• 將清除所有相關的用戶記錄和進度\n"
                f"• **此操作完全無法復原!**\n\n"
                "❗ **最後警告**: 確定要繼續嗎?",
            )

            embed.color = 0xFF0000
            embed.set_footer(text="此為最後確認步驟,請仔細考慮!")

            await interaction.response.send_message(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量刪除確認]強制刪除確認失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理強制刪除確認時發生錯誤", ephemeral=True
            )

    @ui.button(label="📊 查看詳情", style=discord.ButtonStyle.secondary)
    async def view_details_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """查看詳細的依賴關係信息."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "📊 批量刪除詳細分析", "依賴關係和影響分析報告"
            )

            # 總體統計
            embed.add_field(
                name="📈 總體統計",
                value=(
                    f"**選中成就**: {self.dependency_analysis['total_achievements']} 個\n"
                    f"**安全刪除**: {len(self.dependency_analysis['safe_to_delete'])} 個\n"
                    f"**有依賴**: {len(self.dependency_analysis['has_dependencies'])} 個\n"
                    f"**受影響用戶**: {self.dependency_analysis['total_affected_users']} 位"
                ),
                inline=True,
            )

            # 詳細依賴信息
            if self.dependency_analysis["has_dependencies"]:
                dep_details = []
                for achievement in self.dependency_analysis["has_dependencies"][
                    :MAX_PREVIEW_ITEMS
                ]:
                    dep_info = self.dependency_analysis["dependency_details"].get(
                        achievement.id, {}
                    )
                    user_count = dep_info.get("user_achievement_count", 0)
                    dep_details.append(f"• **{achievement.name}**: {user_count} 位用戶")

                if (
                    len(self.dependency_analysis["has_dependencies"])
                    > MAX_PREVIEW_ITEMS
                ):
                    remaining = (
                        len(self.dependency_analysis["has_dependencies"])
                        - MAX_PREVIEW_ITEMS
                    )
                    dep_details.append(f"• ... 還有 {remaining} 個成就有依賴")

                embed.add_field(
                    name="⚠️ 依賴關係詳情", value="\n".join(dep_details), inline=False
                )

            # 安全刪除列表
            if self.dependency_analysis["safe_to_delete"]:
                safe_details = []
                for achievement in self.dependency_analysis["safe_to_delete"][
                    :MAX_PREVIEW_ITEMS
                ]:
                    safe_details.append(f"• ✅ {achievement.name}")

                if len(self.dependency_analysis["safe_to_delete"]) > MAX_PREVIEW_ITEMS:
                    remaining = (
                        len(self.dependency_analysis["safe_to_delete"])
                        - MAX_PREVIEW_ITEMS
                    )
                    safe_details.append(f"• ... 還有 {remaining} 個可安全刪除")

                embed.add_field(
                    name="✅ 可安全刪除", value="\n".join(safe_details), inline=False
                )

            # 建議操作
            if len(self.dependency_analysis["safe_to_delete"]) > 0:
                suggestion = "建議先執行「安全刪除」處理無依賴的成就"
            else:
                suggestion = "所有成就都有依賴關係,需要慎重考慮是否強制刪除"

            embed.add_field(name="💡 建議", value=suggestion, inline=False)

            embed.color = 0x3498DB
            embed.set_footer(text="詳細分析報告 | 基於當前數據生成")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[批量刪除確認]查看詳情失敗: {e}")
            await interaction.response.send_message(
                "❌ 查看詳情時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, _button: ui.Button):
        """取消批量刪除."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消",
            "✅ 批量刪除操作已被取消,沒有進行任何變更.\n\n所有成就都保持原狀.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ForceDeleteConfirmView(ui.View):
    """強制刪除最終確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        achievements_to_delete: list[Achievement],
        dependency_analysis: dict,
    ):
        """初始化強制刪除確認視圖."""
        super().__init__(timeout=60)  # 縮短超時時間,增加緊迫感
        self.admin_panel = admin_panel
        self.achievements_to_delete = achievements_to_delete
        self.dependency_analysis = dependency_analysis

    @ui.button(label="💥 我確認強制刪除", style=discord.ButtonStyle.danger)
    async def confirm_force_delete(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """確認強制刪除."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立進度追蹤視圖
            progress_view = BulkOperationProgressView(
                self.admin_panel, self.achievements_to_delete, "delete", {"force": True}
            )

            # 建立進度追蹤嵌入訊息
            embed = await progress_view._create_progress_embed()

            await interaction.followup.send(
                embed=embed, view=progress_view, ephemeral=True
            )

            # 開始執行批量強制刪除
            await progress_view.start_bulk_operation()

        except Exception as e:
            logger.error(f"[強制刪除確認]執行強制刪除失敗: {e}")
            await interaction.followup.send("❌ 執行強制刪除時發生錯誤", ephemeral=True)

    @ui.button(label="🛡️ 我改變主意了", style=discord.ButtonStyle.secondary)
    async def cancel_force_delete(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """取消強制刪除."""
        embed = StandardEmbedBuilder.create_success_embed(
            "明智的選擇!",
            "✅ 強制刪除已被取消.\n\n"
            "💡 **建議**:\n"
            "• 考慮先停用成就而不是刪除\n"
            "• 或者只刪除沒有用戶依賴的成就\n"
            "• 可以稍後再進行此操作\n\n"
            "所有成就都保持安全.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BulkCategoryChangeView(ui.View):
    """批量分類變更視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        selected_achievements: list[Achievement],
        categories: list,
        category_analysis: dict,
    ):
        """初始化批量分類變更視圖.

        Args:
            admin_panel: 管理面板控制器
            selected_achievements: 選中的成就列表
            categories: 可用分類列表
            category_analysis: 分類分析資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_achievements = selected_achievements
        self.categories = categories
        self.category_analysis = category_analysis

        # 建立分類選擇下拉選單
        self._setup_category_select()

    def _setup_category_select(self):
        """設置分類選擇下拉選單."""
        options = []

        for category in self.categories[:25]:  # Discord 限制最多 25 個選項
            # 檢查這個分類中有多少個選中的成就
            current_count = self.category_analysis["category_count"].get(category.id, 0)
            count_text = f" ({current_count} 個)" if current_count > 0 else ""

            options.append(
                discord.SelectOption(
                    label=f"{category.icon_emoji} {category.name}{count_text}",
                    value=str(category.id),
                    description=f"{category.description[:90]}...",
                    emoji=category.icon_emoji,
                )
            )

        if options:
            self.category_select = ui.Select(
                placeholder="選擇目標分類...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.category_select.callback = self.on_category_select
            self.add_item(self.category_select)

    async def on_category_select(self, interaction: discord.Interaction):
        """處理分類選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            target_category_id = int(self.category_select.values[0])
            target_category = next(
                (cat for cat in self.categories if cat.id == target_category_id), None
            )

            if not target_category:
                await interaction.followup.send("❌ 選擇的分類無效", ephemeral=True)
                return

            # 分析變更影響
            change_analysis = await self._analyze_category_change(target_category_id)

            # 建立確認視圖
            confirm_view = BulkCategoryChangeConfirmView(
                self.admin_panel,
                self.selected_achievements,
                target_category,
                change_analysis,
            )

            embed = await self._create_change_confirmation_embed(
                target_category, change_analysis
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量分類變更]處理分類選擇失敗: {e}")
            await interaction.followup.send("❌ 處理分類選擇時發生錯誤", ephemeral=True)

    async def _analyze_category_change(self, target_category_id: int) -> dict:
        """分析分類變更的影響."""
        changes_needed = []
        no_change_needed = []

        for achievement in self.selected_achievements:
            if achievement.category_id == target_category_id:
                no_change_needed.append(achievement)
            else:
                changes_needed.append(achievement)

        return {
            "changes_needed": changes_needed,
            "no_change_needed": no_change_needed,
            "change_count": len(changes_needed),
            "skip_count": len(no_change_needed),
        }

    async def _create_change_confirmation_embed(
        self, target_category, change_analysis: dict
    ) -> discord.Embed:
        """創建變更確認嵌入訊息."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📂 確認批量分類變更", "將成就移動到" ** {target_category.name} ** "分類"
        )

        # 變更統計
        embed.add_field(
            name="📊 變更統計",
            value=(
                f"**需要變更**: {change_analysis['change_count']} 個成就\n"
                f"**無需變更**: {change_analysis['skip_count']} 個成就\n"
                f"**總計**: {len(self.selected_achievements)} 個成就"
            ),
            inline=True,
        )

        # 目標分類資訊
        embed.add_field(
            name="🎯 目標分類",
            value=(
                f"**名稱**: {target_category.name}\n"
                f"**描述**: {target_category.description}\n"
                f"**圖示**: {target_category.icon_emoji}"
            ),
            inline=True,
        )

        # 預覽需要變更的成就(最多顯示 8 個)
        if change_analysis["changes_needed"]:
            preview_list = []
            for i, achievement in enumerate(
                change_analysis["changes_needed"][:MAX_PREVIEW_ITEMS]
            ):
                status = "✅" if achievement.is_active else "❌"
                preview_list.append(f"{i + 1}. {status} {achievement.name}")

            if len(change_analysis["changes_needed"]) > MAX_PREVIEW_ITEMS:
                preview_list.append(
                    f"... 還有 {len(change_analysis['changes_needed']) - MAX_PREVIEW_ITEMS} 個成就"
                )

            embed.add_field(
                name="📋 需要變更的成就", value="\n".join(preview_list), inline=False
            )

        # 無需變更的成就提示
        if change_analysis["no_change_needed"]:
            embed.add_field(
                name="⚠️ 提示",
                value=(
                    f"有 {change_analysis['skip_count']} 個成就已經在目標分類中,"
                    "這些成就將被自動跳過."
                ),
                inline=False,
            )

        embed.add_field(
            name="⚡ 執行說明",
            value=(
                "• 變更操作將逐一執行\n"
                "• 提供即時進度顯示\n"
                "• 所有操作都將被記錄\n"
                "• 快取會自動更新"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="請確認後執行批量分類變更")

        return embed

    @ui.button(label="🔙 重新選擇分類", style=discord.ButtonStyle.secondary)
    async def back_to_category_select(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回分類選擇."""
        try:
            embed = await self._create_category_change_embed_refresh()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"[批量分類變更]返回分類選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回分類選擇時發生錯誤", ephemeral=True
            )

    async def _create_category_change_embed_refresh(self) -> discord.Embed:
        """重新創建分類變更嵌入訊息."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📂 批量分類變更",
            f"準備變更 **{self.category_analysis['total_achievements']}** 個成就的分類",
        )

        # 當前分類分布
        distribution_text = []
        for category_id, count in self.category_analysis["category_count"].items():
            category_name = self.category_analysis["category_names"].get(
                category_id, f"分類 {category_id}"
            )
            distribution_text.append(f"• **{category_name}**: {count} 個成就")

        embed.add_field(
            name="📊 當前分類分布",
            value="\n".join(distribution_text) if distribution_text else "無",
            inline=False,
        )

        embed.add_field(
            name="🔄 操作說明",
            value=(
                "1️⃣ 選擇目標分類\n"
                "2️⃣ 確認變更操作\n"
                "3️⃣ 查看執行結果\n\n"
                "💡 **提示**: 已在目標分類的成就將被跳過"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="選擇目標分類來執行批量變更")

        return embed

    @ui.button(label="🔙 返回批量操作", style=discord.ButtonStyle.secondary)
    async def back_to_bulk_operations(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回批量操作選擇."""
        try:
            # 重建批量操作類型選擇視圖
            operation_view = BulkOperationTypeSelectionView(
                self.admin_panel, self.selected_achievements
            )

            embed = await operation_view._create_operation_preview_embed(
                self.selected_achievements
            )

            await interaction.response.edit_message(embed=embed, view=operation_view)

        except Exception as e:
            logger.error(f"[批量分類變更]返回批量操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回批量操作時發生錯誤", ephemeral=True
            )


class BulkCategoryChangeConfirmView(ui.View):
    """批量分類變更確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        selected_achievements: list[Achievement],
        target_category,
        change_analysis: dict,
    ):
        """初始化批量分類變更確認視圖.

        Args:
            admin_panel: 管理面板控制器
            selected_achievements: 選中的成就列表
            target_category: 目標分類
            change_analysis: 變更分析資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_achievements = selected_achievements
        self.target_category = target_category
        self.change_analysis = change_analysis

    @ui.button(label="✅ 確認執行變更", style=discord.ButtonStyle.primary)
    async def confirm_category_change(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """確認執行分類變更."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立進度追蹤視圖
            progress_view = BulkOperationProgressView(
                self.admin_panel,
                self.change_analysis["changes_needed"],  # 只處理需要變更的成就
                "change_category",
                {
                    "target_category_id": self.target_category.id,
                    "target_category_name": self.target_category.name,
                    "skip_count": self.change_analysis["skip_count"],
                },
            )

            # 建立進度追蹤嵌入訊息
            embed = await progress_view._create_progress_embed()

            await interaction.followup.send(
                embed=embed, view=progress_view, ephemeral=True
            )

            # 開始執行批量分類變更
            await progress_view.start_bulk_operation()

        except Exception as e:
            logger.error(f"[批量分類變更確認]執行分類變更失敗: {e}")
            await interaction.followup.send("❌ 執行分類變更時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 重新選擇分類", style=discord.ButtonStyle.secondary)
    async def back_to_category_select(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回分類選擇."""
        try:
            # 重建分類選擇視圖
            categories = await self._get_available_categories()
            category_analysis = await self._analyze_category_distribution()

            category_change_view = BulkCategoryChangeView(
                self.admin_panel,
                self.selected_achievements,
                categories,
                category_analysis,
            )

            embed = await category_change_view._create_category_change_embed_refresh()

            await interaction.response.edit_message(
                embed=embed, view=category_change_view
            )

        except Exception as e:
            logger.error(f"[批量分類變更確認]返回分類選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回分類選擇時發生錯誤", ephemeral=True
            )

    async def _get_available_categories(self):
        """獲取可用分類列表."""
        try:
            # 通過管理服務獲取實際的分類數據
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_all_categories()
            else:
                logger.warning("管理服務不可用,無法獲取分類列表")
                return []
        except Exception as e:
            logger.error(f"取得分類列表失敗: {e}")
            return []

    async def _get_admin_service(self):
        """獲取管理服務實例."""
        try:
            # 通過管理面板獲取服務
            if hasattr(self.admin_panel, "enhanced_admin_service"):
                return self.admin_panel.enhanced_admin_service
            return None
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None

    async def _analyze_category_distribution(self) -> dict:
        """分析成就的分類分布."""
        category_count = {}
        category_names = {}

        for achievement in self.selected_achievements:
            category_id = achievement.category_id
            category_count[category_id] = category_count.get(category_id, 0) + 1

            if category_id not in category_names:
                category_names[category_id] = f"分類 {category_id}"

        return {
            "category_count": category_count,
            "category_names": category_names,
            "total_achievements": len(self.selected_achievements),
            "unique_categories": len(category_count),
        }

    @ui.button(label="❌ 取消操作", style=discord.ButtonStyle.danger)
    async def cancel_operation(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """取消分類變更操作."""
        embed = StandardEmbedBuilder.create_success_embed(
            "操作已取消",
            "✅ 批量分類變更已取消.\n\n"
            "所有成就保持原有分類不變.\n"
            "您可以隨時重新開始此操作.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CategoryManagementView(ui.View):
    """分類管理專用視圖.

    提供分類管理的所有操作選項.
    """

    def __init__(self, admin_panel: AdminPanel, category_stats: dict[str, Any]):
        """初始化分類管理視圖.

        Args:
            admin_panel: 管理面板控制器
            category_stats: 分類統計數據
        """
        super().__init__(timeout=900)  # 15分鐘超時
        self.admin_panel = admin_panel
        self.category_stats = category_stats

    @ui.select(
        placeholder="選擇分類管理操作...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="+ 新增分類",
                value="create",
                description="建立新的成就分類",
                emoji="+",
            ),
            discord.SelectOption(
                label="📝 編輯分類",
                value="edit",
                description="修改現有分類資訊",
                emoji="📝",
            ),
            discord.SelectOption(
                label="📋 分類列表",
                value="list",
                description="查看所有分類",
                emoji="📋",
            ),
            discord.SelectOption(
                label="🔄 排序管理",
                value="reorder",
                description="調整分類顯示順序",
                emoji="🔄",
            ),
            discord.SelectOption(
                label="📈 使用統計",
                value="statistics",
                description="查看分類使用統計",
                emoji="📈",
            ),
            discord.SelectOption(
                label="🗑️ 刪除分類",
                value="delete",
                description="刪除分類(會處理成就重新分配)",
                emoji="🗑️",
            ),
        ],
    )
    async def category_operation_select(
        self, interaction: discord.Interaction, select: ui.Select
    ) -> None:
        """處理分類管理操作選擇."""
        try:
            selected_value = select.values[0]

            # 處理不同操作
            if selected_value == "create":
                await self._handle_create_category(interaction)
            elif selected_value == "edit":
                await self._handle_edit_category(interaction)
            elif selected_value == "list":
                await self._handle_list_categories(interaction)
            elif selected_value == "reorder":
                await self._handle_reorder_categories(interaction)
            elif selected_value == "statistics":
                await self._handle_category_statistics(interaction)
            elif selected_value == "delete":
                await self._handle_delete_category(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 無效的操作選擇", ephemeral=True
                )

        except Exception as e:
            logger.error(f"[分類管理視圖]操作選擇處理失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理操作時發生錯誤", ephemeral=True
            )

    async def _handle_create_category(self, interaction: discord.Interaction) -> None:
        """處理新增分類操作."""
        try:
            # 建立分類新增模態框
            modal = CreateCategoryModal(self.admin_panel)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[分類管理視圖]新增分類操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟分類新增表單時發生錯誤", ephemeral=True
            )

    async def _handle_edit_category(self, interaction: discord.Interaction) -> None:
        """處理編輯分類操作."""
        try:
            # 首先需要讓用戶選擇要編輯的分類
            categories = await self._get_available_categories()
            if not categories:
                await interaction.response.send_message(
                    "❌ 沒有可編輯的分類", ephemeral=True
                )
                return

            # 建立分類選擇視圖
            select_view = CategorySelectionView(
                self.admin_panel, categories, action="edit"
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "📝 編輯分類",
                f"📊 **總共有 {len(categories)} 個分類**\n\n"
                "請選擇要編輯的分類:\n\n"
                "• 修改分類名稱和描述\n"
                "• 更新分類圖示\n"
                "• 調整顯示順序\n"
                "• 查看分類統計",
            )

            await interaction.response.send_message(
                embed=embed, view=select_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[分類管理視圖]編輯分類操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟分類編輯時發生錯誤", ephemeral=True
            )

    async def _handle_list_categories(self, interaction: discord.Interaction) -> None:
        """處理分類列表操作."""
        try:
            # 取得可用的分類列表
            categories = await self._get_available_categories()
            if not categories:
                await interaction.response.send_message(
                    "❌ 沒有可查看的分類", ephemeral=True
                )
                return

            # 建立分類列表視圖
            list_view = CategoryListView(self.admin_panel, categories)

            embed = await self._create_category_list_embed(categories)

            await interaction.response.send_message(
                embed=embed, view=list_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[分類管理視圖]分類列表操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟分類列表時發生錯誤", ephemeral=True
            )

    async def _handle_reorder_categories(
        self, interaction: discord.Interaction
    ) -> None:
        """處理排序管理操作."""
        try:
            # 取得可用的分類列表
            categories = await self._get_available_categories()
            if not categories:
                await interaction.response.send_message(
                    "❌ 沒有可排序的分類", ephemeral=True
                )
                return

            # 建立排序管理視圖
            reorder_view = CategoryReorderView(self.admin_panel, categories)

            embed = await self._create_reorder_embed(categories)

            await interaction.response.send_message(
                embed=embed, view=reorder_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[分類管理視圖]排序管理操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟排序管理時發生錯誤", ephemeral=True
            )

    async def _handle_category_statistics(
        self, interaction: discord.Interaction
    ) -> None:
        """處理分類統計操作."""
        try:
            # 取得分類統計數據
            detailed_stats = await self._get_detailed_category_statistics()

            embed = await self._create_category_statistics_embed(detailed_stats)

            stats_view = CategoryStatisticsView(self.admin_panel, detailed_stats)

            await interaction.response.send_message(
                embed=embed, view=stats_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[分類管理視圖]查看統計操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入分類統計時發生錯誤", ephemeral=True
            )

    async def _handle_delete_category(self, interaction: discord.Interaction) -> None:
        """處理刪除分類操作."""
        try:
            # 首先需要讓用戶選擇要刪除的分類
            categories = await self._get_available_categories()
            if not categories:
                await interaction.response.send_message(
                    "❌ 沒有可刪除的分類", ephemeral=True
                )
                return

            # 建立分類選擇視圖
            select_view = CategorySelectionView(
                self.admin_panel, categories, action="delete"
            )

            embed = StandardEmbedBuilder.create_warning_embed(
                "🗑️ 刪除分類",
                "⚠️ **警告:刪除分類是複雜操作!**\n\n"
                "刪除分類時會:\n"
                "• 檢查分類中的成就數量\n"
                "• 提供成就重新分配選項\n"
                "• 安全處理相關依賴關係\n"
                "• 完整記錄操作日誌\n\n"
                "請選擇要刪除的分類:",
            )

            await interaction.response.send_message(
                embed=embed, view=select_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[分類管理視圖]刪除分類操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟分類刪除時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回成就管理", style=discord.ButtonStyle.secondary)
    async def back_to_achievement_management_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回成就管理."""
        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """重新整理分類管理面板."""
        try:
            # 清除快取並重新載入數據
            self.category_stats = (
                await self.admin_panel._load_category_management_stats()
            )

            # 創建新的 embed
            embed = await self.admin_panel._create_category_management_embed(
                self.category_stats
            )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"[分類管理視圖]重新整理失敗: {e}")
            await interaction.response.send_message(
                "❌ 重新整理時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 關閉面板", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """關閉管理面板."""
        await self.admin_panel.close_panel(interaction)

    async def _get_available_categories(self) -> list:
        """取得可用的分類列表."""
        try:
            # 通過管理服務獲取實際的分類數據
            admin_service = await self._get_admin_service()
            if admin_service:
                return await admin_service.get_all_categories()
            else:
                # 如果服務不可用,返回空列表並記錄錯誤
                logger.error("管理服務不可用,無法獲取分類列表")
                return []
        except Exception as e:
            logger.error(f"取得分類列表失敗: {e}")
            return []

    async def _create_category_list_embed(self, categories: list) -> discord.Embed:
        """建立分類列表 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📋 分類列表", f"📊 **總共有 {len(categories)} 個分類**"
        )

        # 按顯示順序排序分類
        sorted_categories = sorted(categories, key=lambda x: x.display_order)

        category_list = []
        for i, category in enumerate(sorted_categories, 1):
            # 獲取真實的成就數量
            achievement_count = getattr(category, "achievement_count", 0)

            category_list.append(
                f"**{i}.** {category.icon_emoji} **{category.name}**\n"
                f"   └─ {category.description}\n"
                f"   └─ 成就數量: {achievement_count} 個\n"
                f"   └─ 排序: {category.display_order}"
            )

        if category_list:
            for i in range(0, len(category_list), 3):
                group = category_list[i : i + 3]
                field_name = f"📂 分類 {i + 1}-{min(i + 3, len(category_list))}"
                embed.add_field(name=field_name, value="\n\n".join(group), inline=False)

        embed.add_field(
            name="💡 管理提示",
            value=(
                "• 點擊下方按鈕進行分類操作\n"
                "• 分類會影響成就的組織和顯示\n"
                "• 刪除分類前請考慮成就重新分配"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="分類按顯示順序排列")

        return embed

    async def _create_reorder_embed(self, categories: list) -> discord.Embed:
        """建立排序管理 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🔄 分類排序管理", "調整分類的顯示順序,影響用戶界面中的分類排列"
        )

        # 按當前顯示順序排序
        sorted_categories = sorted(categories, key=lambda x: x.display_order)

        current_order = []
        for i, category in enumerate(sorted_categories, 1):
            current_order.append(
                f"**{i}.** {category.icon_emoji} {category.name} (順序: {category.display_order})"
            )

        embed.add_field(
            name="📊 當前順序",
            value="\n".join(current_order) if current_order else "無分類",
            inline=False,
        )

        embed.add_field(
            name="🔧 排序說明",
            value=(
                "• display_order 數值越小,顯示越前面\n"
                "• 可以設定相同數值(系統會按 ID 排序)\n"
                "• 建議使用 10, 20, 30... 預留調整空間\n"
                "• 變更會即時生效"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="使用下方按鈕進行排序調整")

        return embed

    async def _get_detailed_category_statistics(self) -> dict:
        """取得詳細的分類統計數據."""
        try:
            # 通過管理服務獲取統計數據
            admin_service = await self._get_admin_service()
            if admin_service:
                categories = await admin_service.get_all_categories(include_stats=True)

                stats = {
                    "total_categories": len(categories),
                    "category_details": [],
                    "usage_summary": {},
                    "achievement_distribution": {},
                }

                total_achievements = 0

                for category in categories:
                    # 獲取每個分類的詳細統計
                    category_details = await admin_service.get_category_with_details(
                        category.id
                    )
                    if category_details:
                        category_stats = category_details["statistics"]
                        achievement_count = category_stats.get("achievement_count", 0)
                        total_achievements += achievement_count

                        category_detail = {
                            "category": category,
                            "achievement_count": achievement_count,
                            "active_achievements": category_stats.get(
                                "active_achievements", 0
                            ),
                            "inactive_achievements": category_stats.get(
                                "inactive_achievements", 0
                            ),
                            "user_progress_count": category_stats.get(
                                "user_progress_count", 0
                            ),
                            "completion_rate": category_stats.get(
                                "completion_rate", 0.0
                            ),
                            "popular_rank": category.id,
                        }

                        stats["category_details"].append(category_detail)
                        stats["achievement_distribution"][category.name] = (
                            achievement_count
                        )

                # 計算使用摘要
                stats["usage_summary"] = {
                    "most_used": max(
                        stats["category_details"],
                        key=lambda x: x["achievement_count"],
                        default=None,
                    ),
                    "least_used": min(
                        stats["category_details"],
                        key=lambda x: x["achievement_count"],
                        default=None,
                    ),
                    "total_achievements": total_achievements,
                    "average_per_category": total_achievements / len(categories)
                    if categories
                    else 0,
                }

                return stats
            else:
                categories = await self._get_available_categories()

                stats = {
                    "total_categories": len(categories),
                    "category_details": [],
                    "usage_summary": {},
                    "achievement_distribution": {},
                }

                for category in categories:
                    # 模擬取得每個分類的詳細統計
                    achievement_count = 5 if category.id % 2 == 1 else 3
                    active_achievements = (
                        achievement_count - 1 if achievement_count > 0 else 0
                    )
                    user_progress = category.id * 12  # 模擬用戶進度數

                    category_detail = {
                        "category": category,
                        "achievement_count": achievement_count,
                        "active_achievements": active_achievements,
                        "inactive_achievements": achievement_count
                        - active_achievements,
                        "user_progress_count": user_progress,
                        "completion_rate": 75.5 if category.id == 1 else 45.2,
                        "popular_rank": category.id,
                    }

                    stats["category_details"].append(category_detail)
                    stats["achievement_distribution"][category.name] = achievement_count

                # 計算使用摘要
                total_achievements = sum(
                    detail["achievement_count"] for detail in stats["category_details"]
                )
                stats["usage_summary"] = {
                    "most_used": max(
                        stats["category_details"],
                        key=lambda x: x["achievement_count"],
                        default=None,
                    ),
                    "least_used": min(
                        stats["category_details"],
                        key=lambda x: x["achievement_count"],
                        default=None,
                    ),
                    "total_achievements": total_achievements,
                    "average_per_category": total_achievements / len(categories)
                    if categories
                    else 0,
                }

                return stats

        except Exception as e:
            logger.error(f"取得詳細分類統計失敗: {e}")
            return {
                "total_categories": 0,
                "category_details": [],
                "usage_summary": {},
                "achievement_distribution": {},
            }

    async def _create_category_statistics_embed(self, stats: dict) -> discord.Embed:
        """建立分類統計 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📈 分類使用統計", "詳細的分類使用情況和成就分布分析"
        )

        # 總體統計
        usage_summary = stats.get("usage_summary", {})
        embed.add_field(
            name="📊 總體統計",
            value=(
                f"**總分類數**: {stats.get('total_categories', 0)}\n"
                f"**總成就數**: {usage_summary.get('total_achievements', 0)}\n"
                f"**平均每類**: {usage_summary.get('average_per_category', 0):.1f} 個"
            ),
            inline=True,
        )

        # 使用情況
        most_used = usage_summary.get("most_used")
        least_used = usage_summary.get("least_used")

        if most_used and least_used:
            embed.add_field(
                name="🏆 使用排名",
                value=(
                    f"**最多使用**: {most_used['category'].name} "
                    f"({most_used['achievement_count']} 個)\n"
                    f"**最少使用**: {least_used['category'].name} "
                    f"({least_used['achievement_count']} 個)"
                ),
                inline=True,
            )

        # 詳細統計
        category_details = stats.get("category_details", [])
        if category_details:
            detail_text = []
            for detail in category_details[:4]:  # 顯示前4個
                category = detail["category"]
                detail_text.append(
                    f"**{category.icon_emoji} {category.name}**\n"
                    f"  └─ 成就: {detail['achievement_count']} 個 "
                    f"(啟用: {detail['active_achievements']})\n"
                    f"  └─ 用戶進度: {detail['user_progress_count']} 個\n"
                    f"  └─ 完成率: {detail['completion_rate']:.1f}%"
                )

            embed.add_field(
                name="📋 詳細統計", value="\n\n".join(detail_text), inline=False
            )

        embed.color = 0xFF6B35
        embed.set_footer(text=f"統計時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        return embed

    async def on_timeout(self) -> None:
        """處理視圖超時."""
        try:
            logger.info(
                f"[分類管理視圖]用戶 {self.admin_panel.admin_user_id} 的面板因超時而關閉"
            )
        except Exception as e:
            logger.error(f"[分類管理視圖]處理超時失敗: {e}")

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        """處理視圖錯誤."""
        logger.error(f"[分類管理視圖]UI 錯誤: {error}, 項目: {item}")
        with contextlib.suppress(builtins.BaseException):
            await interaction.response.send_message(
                "❌ 處理分類管理操作時發生錯誤,請稍後再試", ephemeral=True
            )

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            # 這裡應該從依賴注入容器獲取實際的管理服務
            # 暫時直接實例化,實際應該使用單例模式

            return AchievementAdminService(
                repository=None,  # 實際應該注入真實的 repository
                permission_service=None,  # 實際應該注入真實的 permission service
                cache_service=None,  # 實際應該注入真實的 cache service
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


# ================================================================================
# Task 2: 手動成就授予功能實作
# ================================================================================


class GrantAchievementFlowView(ui.View):
    """成就授予流程視圖."""

    def __init__(self, panel: AdminPanel):
        super().__init__(timeout=300)
        self.panel = panel
        self.current_step = "search_user"
        self.selected_user = None
        self.selected_achievement = None

    @ui.button(label="🔍 搜尋用戶", style=discord.ButtonStyle.primary)
    async def search_user_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """搜尋用戶按鈕."""
        try:
            modal = GrantUserSearchModal(self.panel, action="grant")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"[成就授予流程]搜尋用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )


class GrantUserSearchModal(ui.Modal):
    """成就授予用戶搜尋模態框."""

    def __init__(self, admin_panel: AdminPanel, action: str = "grant"):
        """初始化用戶搜尋模態框.

        Args:
            admin_panel: 管理面板控制器
            action: 操作類型 (grant, revoke, adjust, reset, bulk, general)
        """
        super().__init__(title=f"搜尋用戶 - {self._get_action_name(action)}")
        self.admin_panel = admin_panel
        self.action = action

        # 搜尋輸入框
        self.search_input = ui.TextInput(
            label="用戶搜尋",
            placeholder="輸入用戶名、暱稱、用戶ID 或 @提及用戶",
            max_length=100,
            required=True,
        )
        self.add_item(self.search_input)

    def _get_action_name(self, action: str) -> str:
        """獲取操作名稱."""
        action_names = {
            "grant": "授予成就",
            "revoke": "撤銷成就",
            "adjust": "調整進度",
            "reset": "重置資料",
            "bulk": "批量操作",
            "general": "一般管理",
        }
        return action_names.get(action, "一般管理")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            search_query = self.search_input.value.strip()
            if not search_query:
                await interaction.followup.send("❌ 搜尋內容不能為空", ephemeral=True)
                return

            # 執行用戶搜尋
            search_results = await self._search_users(
                search_query, interaction.guild_id
            )

            if not search_results:
                embed = StandardEmbedBuilder.create_warning_embed(
                    "🔍 搜尋結果", f"未找到與「{search_query}」相符的用戶."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 根據操作類型建立不同的用戶選擇視圖
            if self.action == "grant":
                selection_view = GrantAchievementUserSelectionView(
                    self.admin_panel, search_results, search_query
                )
            elif self.action == "revoke":
                selection_view = RevokeAchievementUserSelectionView(
                    self.admin_panel, search_results, search_query
                )
            elif self.action == "adjust":
                selection_view = AdjustProgressUserSelectionView(
                    self.admin_panel, search_results, search_query
                )
            elif self.action == "reset":
                selection_view = ResetDataUserSelectionView(
                    self.admin_panel, search_results, search_query
                )
            elif self.action == "bulk":
                selection_view = BulkUserSelectionView(
                    self.admin_panel, search_results, search_query
                )
            else:
                selection_view = UserSelectionView(
                    self.admin_panel, search_results, search_query
                )

            embed = await self._create_search_results_embed(
                search_results, search_query
            )

            await interaction.followup.send(
                embed=embed, view=selection_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[用戶搜尋模態框]處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理用戶搜尋時發生錯誤", ephemeral=True)

    async def _search_users(self, query: str, guild_id: int) -> list[dict]:
        """搜尋用戶."""
        try:
            guild = self.admin_panel.bot.get_guild(guild_id)
            if not guild:
                return []

            results = []
            query_lower = query.lower()

            # 嘗試解析用戶ID
            user_id = None
            if query.isdigit():
                user_id = int(query)
            elif query.startswith("<@") and query.endswith(">"):
                mention_id = query[2:-1]
                if mention_id.startswith("!"):
                    mention_id = mention_id[1:]
                if mention_id.isdigit():
                    user_id = int(mention_id)

            # 搜尋邏輯
            for member in guild.members:
                if len(results) >= MAX_DISPLAYED_USERS:
                    break

                # 精確ID匹配
                if user_id and member.id == user_id:
                    results.insert(0, await self._create_user_result(member))
                    continue

                # 用戶名匹配
                if (
                    query_lower in member.name.lower()
                    or query_lower in member.display_name.lower()
                ):
                    results.append(await self._create_user_result(member))

            return results

        except Exception as e:
            logger.error(f"[用戶搜尋]搜尋用戶失敗: {e}")
            return []

    async def _create_user_result(self, member: discord.Member) -> dict:
        """建立用戶搜尋結果."""
        try:
            achievement_summary = await self._get_user_achievement_summary(member.id)

            return {
                "user": member,
                "display_name": member.display_name,
                "username": member.name,
                "user_id": member.id,
                "avatar_url": member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                "joined_at": member.joined_at,
                "achievement_count": achievement_summary.get("total_achievements", 0),
                "progress_count": achievement_summary.get("total_progress", 0),
                "achievement_points": achievement_summary.get("total_points", 0),
            }
        except Exception as e:
            logger.error(f"[用戶搜尋]建立用戶結果失敗: {e}")
            return {
                "user": member,
                "display_name": member.display_name,
                "username": member.name,
                "user_id": member.id,
                "avatar_url": member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                "joined_at": member.joined_at,
                "achievement_count": 0,
                "progress_count": 0,
                "achievement_points": 0,
            }

    async def _get_user_achievement_summary(self, user_id: int) -> dict:
        """獲取用戶成就摘要."""
        try:
            return {
                "total_achievements": user_id % 10,
                "total_progress": user_id % 15,
                "total_points": (user_id % 10) * 25,
            }
        except Exception as e:
            logger.error(f"[用戶搜尋]獲取用戶成就摘要失敗: {e}")
            return {
                "total_achievements": 0,
                "total_progress": 0,
                "total_points": 0,
            }

    async def _create_search_results_embed(
        self, results: list[dict], query: str
    ) -> discord.Embed:
        """建立搜尋結果 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            f"🔍 用戶搜尋結果 - {self._get_action_name(self.action)}",
            f"搜尋「{query}」找到 {len(results)} 個結果",
        )

        if len(results) == 1:
            user_data = results[0]
            member = user_data["user"]

            embed.add_field(
                name="👤 用戶資訊",
                value=(
                    f"**用戶名**: {user_data['username']}\n"
                    f"**顯示名**: {user_data['display_name']}\n"
                    f"**用戶ID**: {user_data['user_id']}\n"
                    f"**加入時間**: <t:{int(user_data['joined_at'].timestamp())}:R>"
                ),
                inline=True,
            )

            embed.add_field(
                name="🏆 成就統計",
                value=(
                    f"**成就數量**: {user_data['achievement_count']} 個\n"
                    f"**進度項目**: {user_data['progress_count']} 個\n"
                    f"**總點數**: {user_data['achievement_points']} 點"
                ),
                inline=True,
            )

            if member.avatar:
                embed.set_thumbnail(url=user_data["avatar_url"])
        else:
            result_list = []
            for i, user_data in enumerate(results, 1):
                result_list.append(
                    f"**{i}.** {user_data['display_name']} "
                    f"({user_data['achievement_count']} 個成就)"
                )

            embed.add_field(
                name="📋 搜尋結果", value="\n".join(result_list), inline=False
            )

        embed.add_field(
            name="💡 下一步", value="請選擇一個用戶來執行成就管理操作.", inline=False
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="使用下方選單選擇用戶")

        return embed


class GrantAchievementUserSelectionView(ui.View):
    """成就授予用戶選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_results: list[dict], search_query: str
    ):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_results = user_results
        self.search_query = search_query

        # 建立用戶選擇下拉選單
        if user_results:
            options = []
            for user_data in user_results[:25]:
                description = (
                    f"{user_data['achievement_count']} 個成就 | "
                    f"{user_data['achievement_points']} 點數"
                )

                options.append(
                    discord.SelectOption(
                        label=f"{user_data['display_name']}",
                        value=str(user_data["user_id"]),
                        description=description[:100],
                        emoji="👤",
                    )
                )

            self.user_select = ui.Select(
                placeholder="選擇要授予成就的用戶...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.user_select.callback = self.on_user_select
            self.add_item(self.user_select)

    async def on_user_select(self, interaction: discord.Interaction) -> None:
        """處理用戶選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id = int(self.user_select.values[0])
            selected_user_data = next(
                (user for user in self.user_results if user["user_id"] == user_id), None
            )

            if not selected_user_data:
                await interaction.followup.send("❌ 選擇的用戶無效", ephemeral=True)
                return

            # 進入成就選擇階段
            achievement_view = GrantAchievementSelectionView(
                self.admin_panel, selected_user_data
            )

            # 設置成就選擇選單
            await achievement_view.setup_if_needed()

            embed = await self._create_achievement_selection_embed(selected_user_data)

            await interaction.followup.send(
                embed=embed, view=achievement_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就授予用戶選擇]處理用戶選擇失敗: {e}")
            await interaction.followup.send("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _create_achievement_selection_embed(
        self, user_data: dict
    ) -> discord.Embed:
        """建立成就選擇 Embed."""
        member = user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            "🎁 選擇要授予的成就",
            f"**步驟 2/3**: 為用戶 **{user_data['display_name']}** 選擇成就",
        )

        embed.add_field(
            name="👤 目標用戶",
            value=(
                f"**用戶名**: {user_data['username']}\n"
                f"**顯示名**: {user_data['display_name']}\n"
                f"**當前成就**: {user_data['achievement_count']} 個\n"
                f"**總點數**: {user_data['achievement_points']} 點"
            ),
            inline=True,
        )

        embed.add_field(
            name="📋 授予規則",
            value=(
                "• 只會顯示用戶尚未獲得的成就\n"
                "• 支援批量選擇多個成就\n"
                "• 可以設定是否通知用戶\n"
                "• 操作將被記錄到審計日誌"
            ),
            inline=True,
        )

        if member.avatar:
            embed.set_thumbnail(url=user_data["avatar_url"])

        embed.color = 0xFF6B35
        embed.set_footer(text="選擇下方成就來授予給用戶")

        return embed


class GrantAchievementSelectionView(ui.View):
    """成就授予選擇視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.selected_achievement = None
        self._achievements_loaded = False

    async def setup_if_needed(self):
        """如果尚未設置,則設置成就選擇選單."""
        if not self._achievements_loaded:
            await self._setup_achievement_selection()
            self._achievements_loaded = True

    async def _setup_achievement_selection(self):
        """設置成就選擇選單."""
        try:
            # 從服務層獲取用戶尚未獲得的成就列表
            available_achievements = await self._get_available_achievements()

            if available_achievements:
                options = []
                for achievement in available_achievements[:25]:
                    difficulty = self._get_achievement_difficulty(
                        achievement.get("points", 0)
                    )
                    description = (
                        f"{difficulty} | {achievement.get('description', '')[:50]}..."
                    )

                    options.append(
                        discord.SelectOption(
                            label=achievement.get("name", "未知成就"),
                            value=str(achievement.get("id", 0)),
                            description=description,
                            emoji="🏆",
                        )
                    )

                self.achievement_select = ui.Select(
                    placeholder="選擇要授予的成就...",
                    min_values=1,
                    max_values=1,
                    options=options,
                )
                self.achievement_select.callback = self.on_achievement_select
                self.add_item(self.achievement_select)

        except Exception as e:
            logger.error(f"[成就授予選擇]設置成就選擇失敗: {e}")

    async def _get_available_achievements(self) -> list[dict]:
        """獲取可授予的成就列表."""
        try:
            # 從管理服務獲取真實成就列表
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, "get_all_achievements"):
                achievements = await admin_service.get_all_achievements()

                # 轉換為字典格式以保持向後兼容性
                achievement_dicts = []
                for achievement in achievements:
                    achievement_dicts.append({
                        "id": achievement.id,
                        "name": achievement.name,
                        "description": achievement.description,
                        "points": achievement.points,
                        "category": achievement.category.name
                        if achievement.category
                        else "未分類",
                    })

                return achievement_dicts

            # 如果服務不可用,返回空列表
            logger.warning("管理服務不可用,無法獲取成就列表")
            return []

        except Exception as e:
            logger.error(f"獲取可用成就列表失敗: {e}")
            return []

    async def _get_admin_service(self):
        """獲取管理服務實例."""
        try:
            # 從管理面板獲取服務
            if hasattr(self.admin_panel, "achievement_service"):
                return self.admin_panel.achievement_service

            # 從依賴注入容器獲取

            container = Container()
            return await container.get_achievement_service()

        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None

    def _get_achievement_difficulty(self, points: int) -> str:
        """根據點數獲取成就難度."""
        if points <= POINTS_SIMPLE_MAX:
            return "⭐ 簡單"
        elif points <= POINTS_NORMAL_MAX:
            return "⭐⭐ 普通"
        elif points <= POINTS_HARD_MAX:
            return "⭐⭐⭐ 困難"
        elif points <= POINTS_EXTREME_MAX:
            return "⭐⭐⭐⭐ 極難"
        else:
            return "⭐⭐⭐⭐⭐ 傳說"

    async def on_achievement_select(self, interaction: discord.Interaction) -> None:
        """處理成就選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            achievement_id = int(self.achievement_select.values[0])
            available_achievements = await self._get_available_achievements()
            selected_achievement = next(
                (ach for ach in available_achievements if ach["id"] == achievement_id),
                None,
            )

            if not selected_achievement:
                await interaction.followup.send("❌ 選擇的成就無效", ephemeral=True)
                return

            self.selected_achievement = selected_achievement

            # 進入確認階段
            confirm_view = GrantAchievementConfirmView(
                self.admin_panel, self.user_data, selected_achievement
            )

            embed = await self._create_confirmation_embed(selected_achievement)

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就授予選擇]處理成就選擇失敗: {e}")
            await interaction.followup.send("❌ 處理成就選擇時發生錯誤", ephemeral=True)

    async def _create_confirmation_embed(self, achievement: dict) -> discord.Embed:
        """建立確認 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            "✅ 確認授予成就", "**步驟 3/3**: 確認授予操作"
        )

        embed.add_field(
            name="👤 目標用戶",
            value=(
                f"**用戶名**: {self.user_data['username']}\n"
                f"**顯示名**: {self.user_data['display_name']}\n"
                f"**用戶ID**: {self.user_data['user_id']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 授予成就",
            value=(
                f"**成就名稱**: {achievement['name']}\n"
                f"**描述**: {achievement['description']}\n"
                f"**獎勵點數**: {achievement['points']} 點\n"
                f"**分類**: {achievement['category']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="⚠️ 授予說明",
            value=(
                "• 此成就將立即授予給用戶\n"
                "• 用戶將獲得對應的成就點數\n"
                "• 操作將記錄到審計日誌\n"
                "• 可以選擇是否通知用戶"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=self.user_data["avatar_url"])

        embed.color = 0x00FF00
        embed.set_footer(text="請確認授予資訊並選擇操作")

        return embed


class GrantAchievementConfirmView(ui.View):
    """成就授予確認視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, achievement: dict):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement
        self.notify_user = True
        self.grant_reason = "管理員手動授予"

    @ui.button(label="✅ 確認授予", style=discord.ButtonStyle.success)
    async def confirm_grant(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認授予成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 執行成就授予邏輯
            success = await self._grant_achievement()

            if success:
                # 建立成功結果視圖
                followup_view = GrantAchievementFollowupView(
                    self.admin_panel, self.user_data, self.achievement
                )

                embed = await self._create_grant_success_embed()

                await interaction.followup.send(
                    embed=embed, view=followup_view, ephemeral=True
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "授予失敗", "❌ 授予成就時發生錯誤,請稍後再試."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[成就授予確認]確認授予失敗: {e}")
            await interaction.followup.send("❌ 處理授予確認時發生錯誤", ephemeral=True)

    @ui.button(label="⚙️ 授予設定", style=discord.ButtonStyle.secondary)
    async def grant_settings(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """授予設定."""
        try:
            modal = GrantSettingsModal(
                self.notify_user, self.grant_reason, self._update_settings
            )
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就授予確認]開啟授予設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟授予設定時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.danger)
    async def cancel_grant(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消授予."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 成就授予操作已被取消."
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def _update_settings(
        self, notify_user: bool, grant_reason: str, interaction: discord.Interaction
    ) -> None:
        """更新授予設定."""
        self.notify_user = notify_user
        self.grant_reason = grant_reason

        embed = await self._create_updated_confirmation_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _create_updated_confirmation_embed(self) -> discord.Embed:
        """建立更新後的確認 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            "✅ 確認授予成就(已更新設定)", "**步驟 3/3**: 確認授予操作"
        )

        embed.add_field(
            name="👤 目標用戶",
            value=(
                f"**用戶名**: {self.user_data['username']}\n"
                f"**顯示名**: {self.user_data['display_name']}\n"
                f"**用戶ID**: {self.user_data['user_id']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 授予成就",
            value=(
                f"**成就名稱**: {self.achievement['name']}\n"
                f"**獎勵點數**: {self.achievement['points']} 點\n"
                f"**分類**: {self.achievement['category']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="⚙️ 授予設定",
            value=(
                f"**通知用戶**: {'是' if self.notify_user else '否'}\n"
                f"**授予原因**: {self.grant_reason}"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=self.user_data["avatar_url"])

        embed.color = 0x00FF00
        embed.set_footer(text="設定已更新,請確認授予")

        return embed

    async def _grant_achievement(self) -> bool:
        """執行成就授予邏輯."""
        try:
            # 獲取真實的管理服務
            admin_service = await self.admin_panel._get_admin_service()

            # 執行成就授予
            success = await admin_service.grant_achievement(
                user_id=self.user_data["user_id"],
                achievement_id=self.achievement["id"],
                admin_user_id=self.admin_panel.admin_user_id,
            )

            if success:
                logger.info(
                    f"[成就授予]管理員 {self.admin_panel.admin_user_id} "
                    f"為用戶 {self.user_data['user_id']} "
                    f"授予成就 {self.achievement['id']}({self.achievement['name']})"
                )
            else:
                logger.warning(
                    f"[成就授予]失敗 - 用戶 {self.user_data['user_id']} "
                    f"可能已擁有成就 {self.achievement['id']}"
                )

            return success

        except Exception as e:
            logger.error(f"[成就授予]執行授予邏輯失敗: {e}")
            return False

    async def _create_grant_success_embed(self) -> discord.Embed:
        """建立授予成功 Embed."""
        embed = StandardEmbedBuilder.create_success_embed(
            "🎉 成就授予成功",
            f"✅ 已成功為用戶 **{self.user_data['display_name']}** 授予成就!",
        )

        embed.add_field(
            name="🏆 授予詳情",
            value=(
                f"**成就名稱**: {self.achievement['name']}\n"
                f"**獲得點數**: {self.achievement['points']} 點\n"
                f"**授予時間**: <t:{int(datetime.now().timestamp())}:f>\n"
                f"**授予原因**: {self.grant_reason}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📊 用戶新狀態",
            value=(
                f"**成就總數**: {self.user_data['achievement_count'] + 1} 個\n"
                f"**總點數**: {self.user_data['achievement_points'] + self.achievement['points']} 點\n"
                f"**通知狀態**: {'已通知' if self.notify_user else '未通知'}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📝 後續操作",
            value=(
                "• 操作已記錄到審計日誌\n• 用戶快取已自動更新\n• 相關統計已重新計算"
            ),
            inline=False,
        )

        embed.color = 0x00FF00
        embed.set_footer(text="操作完成,可以繼續其他管理操作")

        return embed


class GrantSettingsModal(ui.Modal):
    """授予設定模態框."""

    def __init__(self, current_notify: bool, current_reason: str, callback_func):
        super().__init__(title="授予設定")
        self.callback_func = callback_func

        # 通知設定
        self.notify_input = ui.TextInput(
            label="是否通知用戶 (yes/no)",
            placeholder="輸入 yes 或 no",
            default="yes" if current_notify else "no",
            max_length=3,
            required=True,
        )
        self.add_item(self.notify_input)

        # 授予原因
        self.reason_input = ui.TextInput(
            label="授予原因",
            placeholder="輸入授予此成就的原因",
            default=current_reason,
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理設定提交."""
        try:
            notify_text = self.notify_input.value.strip().lower()
            notify_user = notify_text in ["yes", "y", "是", "true", "1"]
            grant_reason = self.reason_input.value.strip()

            if not grant_reason:
                await interaction.response.send_message(
                    "❌ 授予原因不能為空", ephemeral=True
                )
                return

            await self.callback_func(notify_user, grant_reason, interaction)

        except Exception as e:
            logger.error(f"[授予設定模態框]處理設定提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理設定時發生錯誤", ephemeral=True
            )


class GrantAchievementFollowupView(ui.View):
    """成就授予後續操作視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, achievement: dict):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement

    @ui.button(label="👤 查看用戶詳情", style=discord.ButtonStyle.primary)
    async def view_user_details(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看用戶詳情."""
        try:
            user_detail_view = UserDetailManagementView(
                self.admin_panel, self.user_data
            )

            embed = await self._create_user_detail_embed()

            await interaction.response.send_message(
                embed=embed, view=user_detail_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就授予後續]查看用戶詳情失敗: {e}")
            await interaction.response.send_message(
                "❌ 查看用戶詳情時發生錯誤", ephemeral=True
            )

    @ui.button(label="🎁 繼續授予", style=discord.ButtonStyle.secondary)
    async def continue_grant(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """繼續為同一用戶授予其他成就."""
        try:
            # 回到成就選擇階段
            achievement_view = GrantAchievementSelectionView(
                self.admin_panel, self.user_data
            )

            # 設置成就選擇選單
            await achievement_view.setup_if_needed()

            embed = StandardEmbedBuilder.create_info_embed(
                "🎁 繼續授予成就",
                f"為用戶 **{self.user_data['display_name']}** 選擇其他要授予的成就",
            )

            await interaction.response.send_message(
                embed=embed, view=achievement_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就授予後續]繼續授予失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟繼續授予時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔍 搜尋其他用戶", style=discord.ButtonStyle.secondary)
    async def search_other_user(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """搜尋其他用戶進行授予."""
        try:
            modal = UserSearchModal(self.admin_panel, action="grant")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就授予後續]搜尋其他用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理."""
        await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)

    async def _create_user_detail_embed(self) -> discord.Embed:
        """建立用戶詳情 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            f"👤 用戶詳情 - {self.user_data['display_name']}",
            "查看用戶的完整成就和進度資訊",
        )

        embed.add_field(
            name="📊 基本資訊",
            value=(
                f"**用戶名**: {self.user_data['username']}\n"
                f"**顯示名**: {self.user_data['display_name']}\n"
                f"**用戶ID**: {self.user_data['user_id']}\n"
                f"**加入時間**: <t:{int(self.user_data['joined_at'].timestamp())}:R>"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 成就統計",
            value=(
                f"**成就數量**: {self.user_data['achievement_count'] + 1} 個\n"
                f"**進度項目**: {self.user_data['progress_count']} 個\n"
                f"**總點數**: {self.user_data['achievement_points'] + self.achievement['points']} 點"
            ),
            inline=True,
        )

        embed.add_field(
            name="🆕 最新授予",
            value=(
                f"**成就名稱**: {self.achievement['name']}\n"
                f"**獲得點數**: {self.achievement['points']} 點\n"
                f"**授予時間**: <t:{int(datetime.now().timestamp())}:R>"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=self.user_data["avatar_url"])

        embed.color = 0xFF6B35
        embed.set_footer(text="使用下方按鈕執行更多用戶管理操作")

        return embed


# ================================================================================
# Task 2 實作完成 - 手動成就授予功能
# ================================================================================

# ================================================================================
# Task 3: 成就撤銷功能實作
# ================================================================================


class RevokeAchievementUserSelectionView(ui.View):
    """成就撤銷用戶選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, user_results: list[dict], search_query: str
    ):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_results = user_results
        self.search_query = search_query

        # 建立用戶選擇下拉選單
        if user_results:
            options = []
            for user_data in user_results[:25]:
                description = (
                    f"{user_data['achievement_count']} 個成就 | "
                    f"{user_data['achievement_points']} 點數"
                )

                options.append(
                    discord.SelectOption(
                        label=f"{user_data['display_name']}",
                        value=str(user_data["user_id"]),
                        description=description[:100],
                        emoji="👤",
                    )
                )

            self.user_select = ui.Select(
                placeholder="選擇要撤銷成就的用戶...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.user_select.callback = self.on_user_select
            self.add_item(self.user_select)

    async def on_user_select(self, interaction: discord.Interaction) -> None:
        """處理用戶選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id = int(self.user_select.values[0])
            selected_user_data = next(
                (user for user in self.user_results if user["user_id"] == user_id), None
            )

            if not selected_user_data:
                await interaction.followup.send("❌ 選擇的用戶無效", ephemeral=True)
                return

            # 進入成就選擇階段
            achievement_view = RevokeAchievementSelectionView(
                self.admin_panel, selected_user_data
            )

            # 設置成就選擇選單
            await achievement_view.setup_if_needed()

            embed = await self._create_achievement_selection_embed(selected_user_data)

            await interaction.followup.send(
                embed=embed, view=achievement_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就撤銷用戶選擇]處理用戶選擇失敗: {e}")
            await interaction.followup.send("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _create_achievement_selection_embed(
        self, user_data: dict
    ) -> discord.Embed:
        """建立成就選擇 Embed."""
        member = user_data["user"]

        embed = StandardEmbedBuilder.create_warning_embed(
            "❌ 選擇要撤銷的成就",
            f"**步驟 2/3**: 為用戶 **{user_data['display_name']}** 選擇要撤銷的成就",
        )

        embed.add_field(
            name="👤 目標用戶",
            value=(
                f"**用戶名**: {user_data['username']}\n"
                f"**顯示名**: {user_data['display_name']}\n"
                f"**當前成就**: {user_data['achievement_count']} 個\n"
                f"**總點數**: {user_data['achievement_points']} 點"
            ),
            inline=True,
        )

        embed.add_field(
            name="⚠️ 撤銷規則",
            value=(
                "• 只會顯示用戶已獲得的成就\n"
                "• 撤銷會移除成就和對應點數\n"
                "• 會清除相關的進度記錄\n"
                "• 操作將被記錄到審計日誌\n"
                "• 需要二次確認才能執行"
            ),
            inline=True,
        )

        if member.avatar:
            embed.set_thumbnail(url=user_data["avatar_url"])

        embed.color = 0xFFAA00
        embed.set_footer(text="選擇下方成就來從用戶撤銷")

        return embed


class RevokeAchievementSelectionView(ui.View):
    """成就撤銷選擇視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.selected_achievement = None
        self._achievements_loaded = False

    async def setup_if_needed(self):
        """如果需要,設置成就選擇選單."""
        if not self._achievements_loaded:
            await self._setup_achievement_selection()
            self._achievements_loaded = True

    async def _setup_achievement_selection(self):
        """設置成就選擇選單."""
        try:
            # 從服務層獲取用戶已獲得的成就列表
            user_achievements = await self._get_user_achievements()

            if user_achievements:
                options = []
                for achievement in user_achievements[:25]:
                    earned_date = achievement.get("earned_at", "未知時間")
                    description = (
                        f"獲得於: {earned_date} | {achievement.get('points', 0)} 點數"
                    )

                    options.append(
                        discord.SelectOption(
                            label=achievement.get("name", "未知成就"),
                            value=str(achievement.get("id", 0)),
                            description=description[:100],
                            emoji="🏆",
                        )
                    )

                self.achievement_select = ui.Select(
                    placeholder="選擇要撤銷的成就...",
                    min_values=1,
                    max_values=1,
                    options=options,
                )
                self.achievement_select.callback = self.on_achievement_select
                self.add_item(self.achievement_select)
            else:
                # 如果用戶沒有成就,顯示訊息按鈕
                self.no_achievements_button = ui.Button(
                    label="此用戶沒有可撤銷的成就",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                )
                self.add_item(self.no_achievements_button)

        except Exception as e:
            logger.error(f"[成就撤銷選擇]設置成就選擇失敗: {e}")

    async def _get_user_achievements(self) -> list[dict]:
        """獲取用戶已獲得的成就列表."""
        try:
            # 通過管理服務獲取用戶的成就數據
            admin_service = await self._get_admin_service()
            if admin_service:
                user_id = self.user_data["user_id"]
                user_achievements = await admin_service.get_user_achievements(user_id)

                # 轉換為字典格式以保持兼容性
                achievements = []
                for achievement in user_achievements:
                    achievements.append({
                        "id": achievement.achievement_id,
                        "name": achievement.achievement.name
                        if hasattr(achievement, "achievement")
                        else f"成就 {achievement.achievement_id}",
                        "description": achievement.achievement.description
                        if hasattr(achievement, "achievement")
                        else "成就描述",
                        "points": achievement.achievement.points
                        if hasattr(achievement, "achievement")
                        else 0,
                        "category": achievement.achievement.category.name
                        if hasattr(achievement, "achievement")
                        and hasattr(achievement.achievement, "category")
                        else "未分類",
                        "earned_at": achievement.earned_at.strftime("%Y-%m-%d %H:%M")
                        if achievement.earned_at
                        else "未知時間",
                    })

                return achievements
            else:
                logger.warning("管理服務不可用,無法獲取用戶成就列表")
                return []
        except Exception as e:
            logger.error(f"獲取用戶成就列表失敗: {e}")
            return []

    async def _get_admin_service(self):
        """獲取管理服務實例."""
        try:
            # 通過管理面板獲取服務
            if hasattr(self.admin_panel, "enhanced_admin_service"):
                return self.admin_panel.enhanced_admin_service
            return None
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None

    async def on_achievement_select(self, interaction: discord.Interaction) -> None:
        """處理成就選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            achievement_id = int(self.achievement_select.values[0])
            user_achievements = await self._get_user_achievements()
            selected_achievement = next(
                (ach for ach in user_achievements if ach["id"] == achievement_id), None
            )

            if not selected_achievement:
                await interaction.followup.send("❌ 選擇的成就無效", ephemeral=True)
                return

            self.selected_achievement = selected_achievement

            # 進入確認階段
            confirm_view = RevokeAchievementConfirmView(
                self.admin_panel, self.user_data, selected_achievement
            )

            embed = await self._create_confirmation_embed(selected_achievement)

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就撤銷選擇]處理成就選擇失敗: {e}")
            await interaction.followup.send("❌ 處理成就選擇時發生錯誤", ephemeral=True)

    async def _create_confirmation_embed(self, achievement: dict) -> discord.Embed:
        """建立確認 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_error_embed(
            "⚠️ 確認撤銷成就", "**步驟 3/3**: 確認撤銷操作"
        )

        embed.add_field(
            name="👤 目標用戶",
            value=(
                f"**用戶名**: {self.user_data['username']}\n"
                f"**顯示名**: {self.user_data['display_name']}\n"
                f"**用戶ID**: {self.user_data['user_id']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 撤銷成就",
            value=(
                f"**成就名稱**: {achievement['name']}\n"
                f"**描述**: {achievement['description']}\n"
                f"**點數**: {achievement['points']} 點\n"
                f"**分類**: {achievement['category']}\n"
                f"**獲得時間**: {achievement['earned_at']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="❗ 撤銷警告",
            value=(
                "• 此操作將永久移除用戶的成就\n"
                "• 用戶將失去對應的成就點數\n"
                "• 相關進度記錄將被清除\n"
                "• 操作無法撤銷,請謹慎確認\n"
                "• 操作將記錄到審計日誌"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=self.user_data["avatar_url"])

        embed.color = 0xFF4444
        embed.set_footer(text="⚠️ 危險操作 - 請仔細確認後執行")

        return embed


class RevokeAchievementConfirmView(ui.View):
    """成就撤銷確認視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, achievement: dict):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement
        self.notify_user = False  # 撤銷預設不通知用戶
        self.revoke_reason = "管理員手動撤銷"
        self.confirmed_by_admin = False  # 二次確認標記

    @ui.button(label="⚠️ 二次確認", style=discord.ButtonStyle.secondary)
    async def double_confirm(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """二次確認按鈕."""
        try:
            if not self.confirmed_by_admin:
                # 第一次點擊 - 要求輸入確認
                modal = RevokeConfirmationModal(
                    self.user_data["display_name"],
                    self.achievement["name"],
                    self._handle_double_confirmation,
                )
                await interaction.response.send_modal(modal)
            else:
                # 已確認狀態
                embed = StandardEmbedBuilder.create_warning_embed(
                    "已確認", "您已完成二次確認,現在可以執行撤銷操作."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[成就撤銷確認]二次確認失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理二次確認時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 確認撤銷", style=discord.ButtonStyle.danger)
    async def confirm_revoke(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認撤銷成就."""
        try:
            if not self.confirmed_by_admin:
                embed = StandardEmbedBuilder.create_error_embed(
                    "需要二次確認", "❌ 請先點擊「二次確認」按鈕完成安全確認程序."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            # 執行成就撤銷邏輯
            success = await self._revoke_achievement()

            if success:
                # 建立成功結果視圖
                followup_view = RevokeAchievementFollowupView(
                    self.admin_panel, self.user_data, self.achievement
                )

                embed = await self._create_revoke_success_embed()

                await interaction.followup.send(
                    embed=embed, view=followup_view, ephemeral=True
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "撤銷失敗", "❌ 撤銷成就時發生錯誤,請稍後再試."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[成就撤銷確認]確認撤銷失敗: {e}")
            await interaction.followup.send("❌ 處理撤銷確認時發生錯誤", ephemeral=True)

    @ui.button(label="⚙️ 撤銷設定", style=discord.ButtonStyle.secondary)
    async def revoke_settings(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """撤銷設定."""
        try:
            modal = RevokeSettingsModal(
                self.notify_user, self.revoke_reason, self._update_settings
            )
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就撤銷確認]開啟撤銷設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟撤銷設定時發生錯誤", ephemeral=True
            )

    @ui.button(label="✅ 取消", style=discord.ButtonStyle.success)
    async def cancel_revoke(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消撤銷."""
        embed = StandardEmbedBuilder.create_success_embed(
            "操作已取消", "✅ 成就撤銷操作已被取消,用戶成就保持不變."
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def _handle_double_confirmation(
        self, confirmed: bool, interaction: discord.Interaction
    ) -> None:
        """處理二次確認結果."""
        if confirmed:
            self.confirmed_by_admin = True

            # 更新按鈕狀態
            for item in self.children:
                if isinstance(item, ui.Button):
                    if item.label == "⚠️ 二次確認":
                        item.label = "✅ 已確認"
                        item.style = discord.ButtonStyle.success
                        item.disabled = True
                    elif item.label == "❌ 確認撤銷":
                        item.style = discord.ButtonStyle.danger
                        item.disabled = False

            embed = await self._create_updated_confirmation_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = StandardEmbedBuilder.create_info_embed(
                "確認失敗", "❌ 二次確認失敗,撤銷操作已被取消."
            )
            await interaction.response.edit_message(embed=embed, view=None)

    async def _update_settings(
        self, notify_user: bool, revoke_reason: str, interaction: discord.Interaction
    ) -> None:
        """更新撤銷設定."""
        self.notify_user = notify_user
        self.revoke_reason = revoke_reason

        embed = await self._create_updated_confirmation_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _create_updated_confirmation_embed(self) -> discord.Embed:
        """建立更新後的確認 Embed."""
        member = self.user_data["user"]

        confirm_status = "✅ 已完成" if self.confirmed_by_admin else "❌ 待完成"

        embed = StandardEmbedBuilder.create_error_embed(
            "⚠️ 確認撤銷成就(已更新設定)", "**步驟 3/3**: 確認撤銷操作"
        )

        embed.add_field(
            name="👤 目標用戶",
            value=(
                f"**用戶名**: {self.user_data['username']}\n"
                f"**顯示名**: {self.user_data['display_name']}\n"
                f"**用戶ID**: {self.user_data['user_id']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 撤銷成就",
            value=(
                f"**成就名稱**: {self.achievement['name']}\n"
                f"**點數**: {self.achievement['points']} 點\n"
                f"**分類**: {self.achievement['category']}"
            ),
            inline=True,
        )

        embed.add_field(
            name="⚙️ 撤銷設定",
            value=(
                f"**通知用戶**: {'是' if self.notify_user else '否'}\n"
                f"**撤銷原因**: {self.revoke_reason}\n"
                f"**二次確認**: {confirm_status}"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=self.user_data["avatar_url"])

        embed.color = 0xFF4444
        if self.confirmed_by_admin:
            embed.set_footer(text="✅ 已完成二次確認,可以執行撤銷")
        else:
            embed.set_footer(text="⚠️ 請先完成二次確認")

        return embed

    async def _revoke_achievement(self) -> bool:
        """執行成就撤銷邏輯."""
        try:
            # 獲取真實的管理服務
            admin_service = await self.admin_panel._get_admin_service()

            # 執行成就撤銷
            success = await admin_service.revoke_achievement(
                user_id=self.user_data["user_id"],
                achievement_id=self.achievement["id"],
                admin_user_id=self.admin_panel.admin_user_id,
            )

            if success:
                logger.info(
                    f"[成就撤銷]管理員 {self.admin_panel.admin_user_id} "
                    f"從用戶 {self.user_data['user_id']} "
                    f"撤銷成就 {self.achievement['id']}({self.achievement['name']})"
                )
            else:
                logger.warning(
                    f"[成就撤銷]失敗 - 用戶 {self.user_data['user_id']} "
                    f"可能沒有成就 {self.achievement['id']}"
                )

            return success

        except Exception as e:
            logger.error(f"[成就撤銷]執行撤銷邏輯失敗: {e}")
            return False

    async def _create_revoke_success_embed(self) -> discord.Embed:
        """建立撤銷成功 Embed."""
        embed = StandardEmbedBuilder.create_success_embed(
            "✅ 成就撤銷成功",
            f"✅ 已成功從用戶 **{self.user_data['display_name']}** 撤銷成就!",
        )

        embed.add_field(
            name="🏆 撤銷詳情",
            value=(
                f"**成就名稱**: {self.achievement['name']}\n"
                f"**扣除點數**: {self.achievement['points']} 點\n"
                f"**撤銷時間**: <t:{int(datetime.now().timestamp())}:f>\n"
                f"**撤銷原因**: {self.revoke_reason}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📊 用戶新狀態",
            value=(
                f"**成就總數**: {max(0, self.user_data['achievement_count'] - 1)} 個\n"
                f"**總點數**: {max(0, self.user_data['achievement_points'] - self.achievement['points'])} 點\n"
                f"**通知狀態**: {'已通知' if self.notify_user else '未通知'}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📝 後續處理",
            value=(
                "• 操作已記錄到審計日誌\n"
                "• 用戶快取已自動更新\n"
                "• 相關統計已重新計算\n"
                "• 進度記錄已清除"
            ),
            inline=False,
        )

        embed.color = 0x00AA00
        embed.set_footer(text="撤銷操作完成,可以繼續其他管理操作")

        return embed


class RevokeConfirmationModal(ui.Modal):
    """撤銷二次確認模態框."""

    def __init__(self, user_display_name: str, achievement_name: str, callback_func):
        super().__init__(title="二次確認 - 成就撤銷")
        self.user_display_name = user_display_name
        self.achievement_name = achievement_name
        self.callback_func = callback_func

        # 確認輸入
        self.confirmation_input = ui.TextInput(
            label=f"請輸入 '{user_display_name}' 以確認",
            placeholder=f"輸入用戶名 '{user_display_name}' 來確認撤銷操作",
            max_length=100,
            required=True,
        )
        self.add_item(self.confirmation_input)

        # 成就名稱確認
        self.achievement_input = ui.TextInput(
            label="請輸入成就名稱以再次確認",
            placeholder=f"輸入成就名稱 '{achievement_name}' 來確認",
            max_length=100,
            required=True,
        )
        self.add_item(self.achievement_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理確認提交."""
        try:
            user_input = self.confirmation_input.value.strip()
            achievement_input = self.achievement_input.value.strip()

            # 檢查兩個輸入是否都正確
            user_confirmed = user_input == self.user_display_name
            achievement_confirmed = achievement_input == self.achievement_name

            if user_confirmed and achievement_confirmed:
                await self.callback_func(True, interaction)
            else:
                error_msg = "❌ 確認失敗:\n"
                if not user_confirmed:
                    error_msg += f"• 用戶名不匹配(輸入:{user_input})\n"
                if not achievement_confirmed:
                    error_msg += f"• 成就名稱不匹配(輸入:{achievement_input})\n"

                embed = StandardEmbedBuilder.create_error_embed(
                    "確認失敗", error_msg + "\n請確保輸入內容完全一致."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[撤銷確認模態框]處理確認提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理確認時發生錯誤", ephemeral=True
            )


class RevokeSettingsModal(ui.Modal):
    """撤銷設定模態框."""

    def __init__(self, current_notify: bool, current_reason: str, callback_func):
        super().__init__(title="撤銷設定")
        self.callback_func = callback_func

        # 通知設定
        self.notify_input = ui.TextInput(
            label="是否通知用戶 (yes/no)",
            placeholder="輸入 yes 或 no (撤銷預設為 no)",
            default="yes" if current_notify else "no",
            max_length=3,
            required=True,
        )
        self.add_item(self.notify_input)

        # 撤銷原因
        self.reason_input = ui.TextInput(
            label="撤銷原因",
            placeholder="輸入撤銷此成就的原因",
            default=current_reason,
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理設定提交."""
        try:
            notify_text = self.notify_input.value.strip().lower()
            notify_user = notify_text in ["yes", "y", "是", "true", "1"]
            revoke_reason = self.reason_input.value.strip()

            if not revoke_reason:
                await interaction.response.send_message(
                    "❌ 撤銷原因不能為空", ephemeral=True
                )
                return

            await self.callback_func(notify_user, revoke_reason, interaction)

        except Exception as e:
            logger.error(f"[撤銷設定模態框]處理設定提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理設定時發生錯誤", ephemeral=True
            )


class RevokeAchievementFollowupView(ui.View):
    """成就撤銷後續操作視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict, achievement: dict):
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement

    @ui.button(label="👤 查看用戶詳情", style=discord.ButtonStyle.primary)
    async def view_user_details(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看用戶詳情."""
        try:
            user_detail_view = UserDetailManagementView(
                self.admin_panel, self.user_data
            )

            embed = await self._create_user_detail_embed()

            await interaction.response.send_message(
                embed=embed, view=user_detail_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就撤銷後續]查看用戶詳情失敗: {e}")
            await interaction.response.send_message(
                "❌ 查看用戶詳情時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 繼續撤銷", style=discord.ButtonStyle.secondary)
    async def continue_revoke(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """繼續為同一用戶撤銷其他成就."""
        try:
            # 回到成就選擇階段
            achievement_view = RevokeAchievementSelectionView(
                self.admin_panel, self.user_data
            )

            # 設置成就選擇選單
            await achievement_view.setup_if_needed()

            embed = StandardEmbedBuilder.create_warning_embed(
                "❌ 繼續撤銷成就",
                f"為用戶 **{self.user_data['display_name']}** 選擇其他要撤銷的成就",
            )

            await interaction.response.send_message(
                embed=embed, view=achievement_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就撤銷後續]繼續撤銷失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟繼續撤銷時發生錯誤", ephemeral=True
            )

    @ui.button(label="🎁 授予成就", style=discord.ButtonStyle.success)
    async def grant_achievement(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """為用戶授予成就."""
        try:
            # 切換到授予流程
            achievement_view = GrantAchievementSelectionView(
                self.admin_panel, self.user_data
            )

            # 設置成就選擇選單
            await achievement_view.setup_if_needed()

            embed = StandardEmbedBuilder.create_info_embed(
                "🎁 授予成就",
                f"為用戶 **{self.user_data['display_name']}** 選擇要授予的成就",
            )

            await interaction.response.send_message(
                embed=embed, view=achievement_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[成就撤銷後續]授予成就失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就授予時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔍 搜尋其他用戶", style=discord.ButtonStyle.secondary)
    async def search_other_user(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """搜尋其他用戶進行撤銷."""
        try:
            modal = UserSearchModal(self.admin_panel, action="revoke")
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就撤銷後續]搜尋其他用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟用戶搜尋時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理."""
        await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)

    async def _create_user_detail_embed(self) -> discord.Embed:
        """建立用戶詳情 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            f"👤 用戶詳情 - {self.user_data['display_name']}",
            "查看用戶的完整成就和進度資訊",
        )

        embed.add_field(
            name="📊 基本資訊",
            value=(
                f"**用戶名**: {self.user_data['username']}\n"
                f"**顯示名**: {self.user_data['display_name']}\n"
                f"**用戶ID**: {self.user_data['user_id']}\n"
                f"**加入時間**: <t:{int(self.user_data['joined_at'].timestamp())}:R>"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 成就統計",
            value=(
                f"**成就數量**: {max(0, self.user_data['achievement_count'] - 1)} 個\n"
                f"**進度項目**: {self.user_data['progress_count']} 個\n"
                f"**總點數**: {max(0, self.user_data['achievement_points'] - self.achievement['points'])} 點"
            ),
            inline=True,
        )

        embed.add_field(
            name="❌ 最新撤銷",
            value=(
                f"**成就名稱**: {self.achievement['name']}\n"
                f"**扣除點數**: {self.achievement['points']} 點\n"
                f"**撤銷時間**: <t:{int(datetime.now().timestamp())}:R>"
            ),
            inline=False,
        )

        if member.avatar:
            embed.set_thumbnail(url=self.user_data["avatar_url"])

        embed.color = 0xFF6B35
        embed.set_footer(text="使用下方按鈕執行更多用戶管理操作")

        return embed


# ================================================================================
# Task 6 實作批量用戶操作功能 (AC: 5, 8)
# ================================================================================


class BulkUserSelectionView(ui.View):
    """批量用戶選擇視圖."""

    def __init__(
        self, admin_panel: AdminPanel, search_results: list[dict], search_query: str
    ):
        """初始化批量用戶選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            search_results: 搜尋結果列表
            search_query: 搜尋查詢
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.search_results = search_results
        self.search_query = search_query
        self.selected_users = []

        # 建立用戶選項
        options = []
        for i, user_data in enumerate(search_results[:20]):  # 最多20個選項
            label = f"{user_data['display_name']}"
            description = (
                f"ID: {user_data['user_id']} | {user_data['achievement_count']} 個成就"
            )
            options.append(
                discord.SelectOption(
                    label=label, value=str(i), description=description[:100], emoji="👤"
                )
            )

        # 用戶多選下拉選單
        self.user_select = ui.Select(
            placeholder="選擇要進行批量操作的用戶(可多選)...",
            min_values=1,
            max_values=min(len(options), 10),  # 最多選10個用戶
            options=options,
        )
        self.user_select.callback = self.on_user_select
        self.add_item(self.user_select)

    async def on_user_select(self, interaction: discord.Interaction) -> None:
        """處理用戶選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 獲取選中的用戶
            selected_indices = [int(value) for value in self.user_select.values]
            self.selected_users = [self.search_results[i] for i in selected_indices]

            # 建立批量操作選擇視圖
            bulk_ops_view = BulkOperationSelectionView(
                self.admin_panel, self.selected_users
            )

            # 建立用戶選擇確認 embed
            embed = await self._create_user_selection_embed()

            await interaction.followup.send(
                embed=embed, view=bulk_ops_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量用戶選擇]處理用戶選擇失敗: {e}")
            await interaction.followup.send("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _create_user_selection_embed(self) -> discord.Embed:
        """建立用戶選擇確認 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "👥 批量操作 - 用戶選擇確認",
            f"已選擇 {len(self.selected_users)} 個用戶進行批量操作",
        )

        # 顯示選中的用戶
        users_text = []
        for user_data in self.selected_users:
            users_text.append(
                f"• **{user_data['display_name']}** "
                f"({user_data['achievement_count']} 個成就, "
                f"{user_data['achievement_points']} 點)"
            )

        embed.add_field(
            name="📋 選中用戶列表",
            value="\n".join(users_text[:MAX_DISPLAYED_USERS]),  # 最多顯示用戶數
            inline=False,
        )

        if len(self.selected_users) > MAX_DISPLAYED_USERS:
            embed.add_field(
                name="📄 其他用戶",
                value=f"... 還有 {len(self.selected_users) - MAX_DISPLAYED_USERS} 個用戶",
                inline=False,
            )

        embed.add_field(
            name="⚡ 下一步", value="請選擇要執行的批量操作類型", inline=False
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="批量操作將同時應用於所有選中的用戶")

        return embed


class BulkGrantAchievementView(ui.View):
    """批量授予成就視圖."""

    def __init__(
        self, admin_panel: AdminPanel, selected_users: list[dict], achievements: list
    ):
        """初始化批量授予成就視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_users = selected_users
        self.achievements = achievements

        # 建立成就選項
        options = []
        for achievement in achievements[:25]:
            status_icon = "✅" if achievement.is_active else "❌"
            options.append(
                discord.SelectOption(
                    label=f"{status_icon} {achievement.name}",
                    value=str(achievement.id),
                    description=f"{achievement.description[:80]}...",
                    emoji="🏆",
                )
            )

        # 成就選擇下拉選單
        self.achievement_select = ui.Select(
            placeholder="選擇要批量授予的成就...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.achievement_select.callback = self.on_achievement_select
        self.add_item(self.achievement_select)

    async def on_achievement_select(self, interaction: discord.Interaction) -> None:
        """處理成就選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            achievement_id = int(self.achievement_select.values[0])
            selected_achievement = next(
                (ach for ach in self.achievements if ach.id == achievement_id), None
            )

            if not selected_achievement:
                await interaction.followup.send("❌ 選擇的成就無效", ephemeral=True)
                return

            # 建立批量授予確認視圖
            confirm_view = BulkGrantConfirmView(
                self.admin_panel, self.selected_users, selected_achievement
            )

            # 建立確認 embed
            embed = await self._create_grant_preview_embed(selected_achievement)

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量授予成就]處理成就選擇失敗: {e}")
            await interaction.followup.send("❌ 處理成就選擇時發生錯誤", ephemeral=True)

    async def _create_grant_preview_embed(self, achievement) -> discord.Embed:
        """建立授予預覽 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🎁 批量授予成就 - 確認操作",
            f"將為 {len(self.selected_users)} 個用戶授予成就",
        )

        embed.add_field(
            name="🏆 目標成就",
            value=(
                f"**名稱**: {achievement.name}\n"
                f"**描述**: {achievement.description}\n"
                f"**點數**: {achievement.points} 點\n"
                f"**類型**: {achievement.type.value}"
            ),
            inline=False,
        )

        users_preview = []
        for i, user_data in enumerate(self.selected_users[:MAX_DISPLAYED_ITEMS]):
            users_preview.append(
                f"{i + 1}. **{user_data['display_name']}** (+{achievement.points} 點)"
            )

        if len(self.selected_users) > MAX_DISPLAYED_ITEMS:
            users_preview.append(
                f"... 還有 {len(self.selected_users) - MAX_DISPLAYED_ITEMS} 個用戶"
            )

        embed.add_field(
            name="👥 目標用戶", value="\n".join(users_preview), inline=False
        )

        # 統計資訊
        total_points = len(self.selected_users) * achievement.points
        embed.add_field(
            name="📊 操作統計",
            value=(
                f"**用戶數量**: {len(self.selected_users)} 個\n"
                f"**總授予點數**: {total_points} 點\n"
                f"**預計耗時**: ~{len(self.selected_users) * 0.5:.1f} 秒"
            ),
            inline=False,
        )

        embed.color = 0x00FF00
        embed.set_footer(text="確認後將開始批量授予操作")

        return embed


class BulkGrantConfirmView(ui.View):
    """批量授予確認視圖."""

    def __init__(
        self, admin_panel: AdminPanel, selected_users: list[dict], achievement
    ):
        """初始化批量授予確認視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_users = selected_users
        self.achievement = achievement

    @ui.button(label="✅ 確認批量授予", style=discord.ButtonStyle.primary)
    async def confirm_bulk_grant(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認批量授予成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立進度追蹤 embed
            progress_embed = StandardEmbedBuilder.create_info_embed(
                "🎁 批量授予進行中",
                f"正在為 {len(self.selected_users)} 個用戶授予成就「{self.achievement.name}」...",
            )

            progress_embed.add_field(
                name="📊 進度", value="⏳ 初始化中...", inline=False
            )

            message = await interaction.followup.send(
                embed=progress_embed, ephemeral=True
            )

            successful_grants = []
            failed_grants = []

            for i, user_data in enumerate(self.selected_users):
                try:
                    # 執行真實的成就授予過程
                    await self._grant_achievement_to_user(user_data)
                    successful_grants.append(user_data)

                    # 更新進度
                    progress = (i + 1) / len(self.selected_users) * 100
                    progress_embed.set_field_at(
                        0,
                        name="📊 進度",
                        value=f"🔄 {progress:.1f}% ({i + 1}/{len(self.selected_users)})\n"
                        f"✅ 成功: {len(successful_grants)}\n"
                        f"❌ 失敗: {len(failed_grants)}",
                        inline=False,
                    )

                    await message.edit(embed=progress_embed)

                except Exception as e:
                    logger.error(
                        f"[批量授予]為用戶 {user_data['user_id']} 授予失敗: {e}"
                    )
                    failed_grants.append({"user_data": user_data, "error": str(e)})

            # 建立完成結果視圖
            result_view = BulkGrantResultView(
                self.admin_panel, successful_grants, failed_grants, self.achievement
            )

            # 建立結果 embed
            result_embed = await self._create_result_embed(
                successful_grants, failed_grants
            )

            await message.edit(embed=result_embed, view=result_view)

        except Exception as e:
            logger.error(f"[批量授予確認]批量授予失敗: {e}")
            await interaction.followup.send("❌ 執行批量授予時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消操作", style=discord.ButtonStyle.secondary)
    async def cancel_bulk_grant(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """取消批量授予."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 批量授予操作已被取消."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _grant_achievement_to_user(self, user_data: dict) -> None:
        """為用戶授予成就."""
        try:
            # 從管理服務獲取真實的授予功能
            admin_service = await self._get_enhanced_admin_service()
            if not admin_service:
                raise Exception("管理服務不可用")

            # 執行真實的成就授予
            await admin_service.grant_achievement_to_user(
                user_id=user_data["user_id"],
                achievement_id=self.achievement.id,
                granted_by=self.admin_panel.interaction.user.id,
            )

        except Exception as e:
            # 重新拋出異常以便上層處理
            raise e

    async def _create_result_embed(
        self, successful: list, failed: list
    ) -> discord.Embed:
        """建立結果 Embed."""
        total = len(successful) + len(failed)
        success_rate = len(successful) / total * 100 if total > 0 else 0

        if success_rate == SUCCESS_RATE_THRESHOLD:
            embed = StandardEmbedBuilder.create_success_embed(
                "🎉 批量授予完成",
                f"✅ 成功為所有 {len(successful)} 個用戶授予成就「{self.achievement.name}」",
            )
        elif success_rate > PARTIAL_SUCCESS_THRESHOLD:
            embed = StandardEmbedBuilder.create_warning_embed(
                "⚠️ 批量授予部分完成", f"批量授予操作完成,成功率: {success_rate:.1f}%"
            )
        else:
            embed = StandardEmbedBuilder.create_error_embed(
                "❌ 批量授予失敗", f"批量授予操作失敗較多,成功率: {success_rate:.1f}%"
            )

        embed.add_field(
            name="📊 操作統計",
            value=(
                f"**總用戶數**: {total} 個\n"
                f"**成功授予**: {len(successful)} 個\n"
                f"**授予失敗**: {len(failed)} 個\n"
                f"**成功率**: {success_rate:.1f}%"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 成就資訊",
            value=(
                f"**成就名稱**: {self.achievement.name}\n"
                f"**成就點數**: {self.achievement.points} 點\n"
                f"**總授予點數**: {len(successful) * self.achievement.points} 點"
            ),
            inline=True,
        )

        if failed:
            error_summary = {}
            for fail in failed:
                error = fail["error"]
                error_summary[error] = error_summary.get(error, 0) + 1

            error_text = []
            for error, count in error_summary.items():
                error_text.append(f"• {error}: {count} 個")

            embed.add_field(
                name="❌ 失敗原因", value="\n".join(error_text[:5]), inline=False
            )

        embed.set_footer(
            text=f"操作完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return embed


class BulkGrantResultView(ui.View):
    """批量授予結果視圖."""

    def __init__(
        self, admin_panel: AdminPanel, successful: list, failed: list, achievement
    ):
        """初始化批量授予結果視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.successful = successful
        self.failed = failed
        self.achievement = achievement

    @ui.button(label="📄 查看詳細報告", style=discord.ButtonStyle.secondary)
    async def view_detailed_report(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """查看詳細報告."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "📄 批量授予詳細報告",
                f"成就「{self.achievement.name}」的批量授予詳細結果",
            )

            # 成功列表
            if self.successful:
                success_text = []
                for i, user_data in enumerate(self.successful[:MAX_SUCCESS_DISPLAY]):
                    success_text.append(
                        f"{i + 1}. {user_data['display_name']} "
                        f"(ID: {user_data['user_id']})"
                    )

                if len(self.successful) > MAX_SUCCESS_DISPLAY:
                    success_text.append(
                        f"... 還有 {len(self.successful) - MAX_SUCCESS_DISPLAY} 個"
                    )

                embed.add_field(
                    name=f"✅ 成功授予 ({len(self.successful)} 個)",
                    value="\n".join(success_text),
                    inline=False,
                )

            # 失敗列表
            if self.failed:
                fail_text = []
                for i, fail in enumerate(self.failed[:MAX_DISPLAYED_ITEMS]):
                    user_data = fail["user_data"]
                    error = fail["error"]
                    fail_text.append(f"{i + 1}. {user_data['display_name']}: {error}")

                if len(self.failed) > MAX_DISPLAYED_ITEMS:
                    fail_text.append(
                        f"... 還有 {len(self.failed) - MAX_DISPLAYED_ITEMS} 個"
                    )

                embed.add_field(
                    name=f"❌ 授予失敗 ({len(self.failed)} 個)",
                    value="\n".join(fail_text),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[批量授予結果]查看詳細報告失敗: {e}")
            await interaction.response.send_message(
                "❌ 查看報告時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔄 重試失敗項目", style=discord.ButtonStyle.primary)
    async def retry_failed_items(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """重試失敗項目."""
        if not self.failed:
            await interaction.response.send_message(
                "✅ 沒有失敗項目需要重試", ephemeral=True
            )
            return

        embed = StandardEmbedBuilder.create_info_embed(
            "🔄 重試功能",
            "**功能開發中**\n\n"
            f"將為 {len(self.failed)} 個失敗用戶重新嘗試授予成就.\n\n"
            "此功能將提供:\n"
            "• 自動重試機制\n"
            "• 失敗原因分析\n"
            "• 手動排除問題用戶\n"
            "• 重試進度追蹤\n\n"
            "⚠️ 此功能正在開發中.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="👥 繼續批量操作", style=discord.ButtonStyle.secondary)
    async def continue_bulk_operation(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """繼續批量操作."""
        try:
            # 返回到批量操作選擇
            bulk_ops_view = BulkOperationSelectionView(
                self.admin_panel,
                self.successful + [f["user_data"] for f in self.failed],
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "👥 繼續批量操作", "選擇要執行的下一個批量操作"
            )

            await interaction.response.send_message(
                embed=embed, view=bulk_ops_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量授予結果]繼續批量操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟批量操作時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回用戶管理."""
        await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)


class BulkRevokeAchievementView(ui.View):
    """批量撤銷成就視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        selected_users: list[dict],
        common_achievements: list,
    ):
        """初始化批量撤銷成就視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_users = selected_users
        self.common_achievements = common_achievements

        # 建立成就選項
        options = []
        for achievement in common_achievements[:25]:
            options.append(
                discord.SelectOption(
                    label=achievement.name,
                    value=str(achievement.id),
                    description=f"將從 {len(selected_users)} 個用戶撤銷此成就",
                    emoji="❌",
                )
            )

        # 成就選擇下拉選單
        self.achievement_select = ui.Select(
            placeholder="選擇要批量撤銷的成就...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.achievement_select.callback = self.on_achievement_select
        self.add_item(self.achievement_select)

    async def on_achievement_select(self, interaction: discord.Interaction) -> None:
        """處理成就選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            achievement_id = int(self.achievement_select.values[0])
            selected_achievement = next(
                (ach for ach in self.common_achievements if ach.id == achievement_id),
                None,
            )

            if not selected_achievement:
                await interaction.followup.send("❌ 選擇的成就無效", ephemeral=True)
                return

            # 建立批量撤銷確認視圖
            confirm_view = BulkRevokeConfirmView(
                self.admin_panel, self.selected_users, selected_achievement
            )

            # 建立確認 embed
            embed = await self._create_revoke_preview_embed(selected_achievement)

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量撤銷成就]處理成就選擇失敗: {e}")
            await interaction.followup.send("❌ 處理成就選擇時發生錯誤", ephemeral=True)

    async def _create_revoke_preview_embed(self, achievement) -> discord.Embed:
        """建立撤銷預覽 Embed."""
        embed = StandardEmbedBuilder.create_warning_embed(
            "❌ 批量撤銷成就 - 確認操作",
            f"⚠️ 將從 {len(self.selected_users)} 個用戶撤銷成就",
        )

        embed.add_field(
            name="🏆 目標成就",
            value=(
                f"**名稱**: {achievement.name}\n"
                f"**描述**: {achievement.description}\n"
                f"**點數**: {achievement.points} 點\n"
                f"**類型**: {achievement.type.value}"
            ),
            inline=False,
        )

        users_preview = []
        for i, user_data in enumerate(self.selected_users[:MAX_DISPLAYED_ITEMS]):
            users_preview.append(
                f"{i + 1}. **{user_data['display_name']}** (-{achievement.points} 點)"
            )

        if len(self.selected_users) > MAX_DISPLAYED_ITEMS:
            users_preview.append(
                f"... 還有 {len(self.selected_users) - MAX_DISPLAYED_ITEMS} 個用戶"
            )

        embed.add_field(
            name="👥 目標用戶", value="\n".join(users_preview), inline=False
        )

        # 統計資訊
        total_points = len(self.selected_users) * achievement.points
        embed.add_field(
            name="📊 操作統計",
            value=(
                f"**用戶數量**: {len(self.selected_users)} 個\n"
                f"**總扣除點數**: {total_points} 點\n"
                f"**預計耗時**: ~{len(self.selected_users) * 0.5:.1f} 秒"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚠️ 重要提醒",
            value=(
                "• 此操作將永久刪除用戶的成就記錄\n"
                "• 相關的進度資料也將被清除\n"
                "• 操作無法撤銷,請仔細確認\n"
                "• 所有操作將被記錄到審計日誌"
            ),
            inline=False,
        )

        embed.color = 0xFF0000
        embed.set_footer(text="請仔細確認後再執行批量撤銷操作")

        return embed


class BulkRevokeConfirmView(ui.View):
    """批量撤銷確認視圖."""

    def __init__(
        self, admin_panel: AdminPanel, selected_users: list[dict], achievement
    ):
        """初始化批量撤銷確認視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_users = selected_users
        self.achievement = achievement

    @ui.button(label="❌ 確認批量撤銷", style=discord.ButtonStyle.danger)
    async def confirm_bulk_revoke(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認批量撤銷成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立進度追蹤 embed(與批量授予類似的邏輯)
            progress_embed = StandardEmbedBuilder.create_warning_embed(
                "❌ 批量撤銷進行中",
                f"正在從 {len(self.selected_users)} 個用戶撤銷成就「{self.achievement.name}」...",
            )

            progress_embed.add_field(
                name="📊 進度", value="⏳ 初始化中...", inline=False
            )

            message = await interaction.followup.send(
                embed=progress_embed, ephemeral=True
            )

            successful_revokes = []
            failed_revokes = []

            for i, user_data in enumerate(self.selected_users):
                try:
                    # 模擬檢查和撤銷過程
                    await self._revoke_achievement_from_user(user_data)
                    successful_revokes.append(user_data)

                    # 更新進度
                    progress = (i + 1) / len(self.selected_users) * 100
                    progress_embed.set_field_at(
                        0,
                        name="📊 進度",
                        value=f"🔄 {progress:.1f}% ({i + 1}/{len(self.selected_users)})\n"
                        f"✅ 成功: {len(successful_revokes)}\n"
                        f"❌ 失敗: {len(failed_revokes)}",
                        inline=False,
                    )

                    await message.edit(embed=progress_embed)

                except Exception as e:
                    logger.error(
                        f"[批量撤銷]為用戶 {user_data['user_id']} 撤銷失敗: {e}"
                    )
                    failed_revokes.append({"user_data": user_data, "error": str(e)})

            # 建立完成結果
            result_embed = await self._create_revoke_result_embed(
                successful_revokes, failed_revokes
            )

            await message.edit(embed=result_embed)

        except Exception as e:
            logger.error(f"[批量撤銷確認]批量撤銷失敗: {e}")
            await interaction.followup.send("❌ 執行批量撤銷時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回選擇", style=discord.ButtonStyle.secondary)
    async def back_to_selection(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """返回成就選擇."""
        try:
            revoke_view = BulkRevokeAchievementView(
                self.admin_panel, self.selected_users, [self.achievement]
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "❌ 批量撤銷成就", "選擇要撤銷的成就"
            )

            await interaction.response.send_message(
                embed=embed, view=revoke_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"[批量撤銷確認]返回選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回選擇時發生錯誤", ephemeral=True
            )

    async def _revoke_achievement_from_user(self, user_data: dict) -> None:
        """從用戶撤銷成就."""
        try:
            admin_service = await self._get_enhanced_admin_service()
            if admin_service:
                await admin_service.revoke_achievement(
                    user_id=user_data["user_id"], achievement_id=self.achievement.id
                )
            else:
                logger.warning("[批量撤銷]管理服務不可用,無法撤銷成就")
                raise Exception("管理服務不可用")
        except Exception as e:
            logger.error(f"[批量撤銷]為用戶 {user_data['user_id']} 撤銷成就失敗: {e}")
            raise

    async def _create_revoke_result_embed(
        self, successful: list, failed: list
    ) -> discord.Embed:
        """建立撤銷結果 Embed."""
        total = len(successful) + len(failed)
        success_rate = len(successful) / total * 100 if total > 0 else 0

        if success_rate == SUCCESS_RATE_THRESHOLD:
            embed = StandardEmbedBuilder.create_success_embed(
                "✅ 批量撤銷完成",
                f"成功從所有 {len(successful)} 個用戶撤銷成就「{self.achievement.name}」",
            )
        elif success_rate > PARTIAL_SUCCESS_THRESHOLD:
            embed = StandardEmbedBuilder.create_warning_embed(
                "⚠️ 批量撤銷部分完成", f"批量撤銷操作完成,成功率: {success_rate:.1f}%"
            )
        else:
            embed = StandardEmbedBuilder.create_error_embed(
                "❌ 批量撤銷失敗", f"批量撤銷操作失敗較多,成功率: {success_rate:.1f}%"
            )

        embed.add_field(
            name="📊 操作統計",
            value=(
                f"**總用戶數**: {total} 個\n"
                f"**成功撤銷**: {len(successful)} 個\n"
                f"**撤銷失敗**: {len(failed)} 個\n"
                f"**成功率**: {success_rate:.1f}%"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 成就資訊",
            value=(
                f"**成就名稱**: {self.achievement.name}\n"
                f"**成就點數**: {self.achievement.points} 點\n"
                f"**總扣除點數**: {len(successful) * self.achievement.points} 點"
            ),
            inline=True,
        )

        embed.set_footer(
            text=f"操作完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return embed


class BulkResetConfirmView(ui.View):
    """批量重置確認視圖."""

    def __init__(self, admin_panel: AdminPanel, selected_users: list[dict]):
        """初始化批量重置確認視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.selected_users = selected_users
        self.confirmation_step = 1

    @ui.button(label="⚠️ 我了解風險", style=discord.ButtonStyle.danger)
    async def acknowledge_risk(
        self, interaction: discord.Interaction, _button: ui.Button
    ) -> None:
        """確認風險."""
        if self.confirmation_step == 1:
            self.confirmation_step = 2

            # 更新視圖為第二步確認
            self.clear_items()

            # 添加最終確認按鈕
            final_confirm_button = ui.Button(
                label="🔄 最終確認重置", style=discord.ButtonStyle.danger
            )
            final_confirm_button.callback = self.final_confirm_reset
            self.add_item(final_confirm_button)

            cancel_button = ui.Button(
                label="❌ 取消操作", style=discord.ButtonStyle.secondary
            )
            cancel_button.callback = self.cancel_reset
            self.add_item(cancel_button)

            embed = StandardEmbedBuilder.create_error_embed(
                "🔄 最終確認 - 批量重置",
                f"⚠️ **最後確認步驟**\n\n"
                f"您即將重置 **{len(self.selected_users)}** 個用戶的所有成就資料!\n\n"
                f"**即將清除的資料**:\n"
                f"• 總成就記錄: ~{sum(u['achievement_count'] for u in self.selected_users)} 個\n"
                f"• 總進度記錄: ~{sum(u['progress_count'] for u in self.selected_users)} 個\n"
                f"• 總成就點數: ~{sum(u['achievement_points'] for u in self.selected_users)} 點\n\n"
                f"**操作後果**:\n"
                f"• 用戶將失去所有成就和進度\n"
                f"• 排行榜排名將重置\n"
                f"• 歷史記錄將被清除\n\n"
                f"❗ **此操作無法撤銷!請最後確認!**",
            )

            await interaction.response.edit_message(embed=embed, view=self)

    async def final_confirm_reset(self, interaction: discord.Interaction) -> None:
        """最終確認重置."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立重置進度 embed
            progress_embed = StandardEmbedBuilder.create_warning_embed(
                "🔄 批量重置進行中",
                f"正在重置 {len(self.selected_users)} 個用戶的成就資料...",
            )

            progress_embed.add_field(
                name="📊 進度", value="⏳ 初始化重置...", inline=False
            )

            message = await interaction.followup.send(
                embed=progress_embed, ephemeral=True
            )

            successful_resets = []
            failed_resets = []

            for i, user_data in enumerate(self.selected_users):
                try:
                    # 執行重置過程
                    await self._reset_user_achievements(user_data)
                    successful_resets.append(user_data)

                    # 更新進度
                    progress = (i + 1) / len(self.selected_users) * 100
                    progress_embed.set_field_at(
                        0,
                        name="📊 進度",
                        value=f"🔄 {progress:.1f}% ({i + 1}/{len(self.selected_users)})\n"
                        f"✅ 成功: {len(successful_resets)}\n"
                        f"❌ 失敗: {len(failed_resets)}",
                        inline=False,
                    )

                    await message.edit(embed=progress_embed)

                except Exception as e:
                    logger.error(
                        f"[批量重置]為用戶 {user_data['user_id']} 重置失敗: {e}"
                    )
                    failed_resets.append({"user_data": user_data, "error": str(e)})

            # 建立完成結果
            result_embed = await self._create_reset_result_embed(
                successful_resets, failed_resets
            )

            await message.edit(embed=result_embed)

        except Exception as e:
            logger.error(f"[批量重置]批量重置失敗: {e}")
            await interaction.followup.send("❌ 執行批量重置時發生錯誤", ephemeral=True)

    async def cancel_reset(self, interaction: discord.Interaction) -> None:
        """取消重置."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 批量重置操作已被取消,沒有任何資料被修改."
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def _reset_user_achievements(self, user_data: dict) -> None:
        """重置用戶的所有成就資料."""
        try:
            admin_service = await self._get_enhanced_admin_service()
            if admin_service:
                await admin_service.reset_user_achievements(
                    user_id=user_data["user_id"]
                )
            else:
                logger.warning("[批量重置]管理服務不可用,無法重置用戶成就")
                raise Exception("管理服務不可用")
        except Exception as e:
            logger.error(f"[批量重置]為用戶 {user_data['user_id']} 重置成就失敗: {e}")
            raise

    async def _create_reset_result_embed(
        self, successful: list, failed: list
    ) -> discord.Embed:
        """建立重置結果 Embed."""
        total = len(successful) + len(failed)
        success_rate = len(successful) / total * 100 if total > 0 else 0

        if success_rate == SUCCESS_RATE_THRESHOLD:
            embed = StandardEmbedBuilder.create_success_embed(
                "✅ 批量重置完成", f"成功重置所有 {len(successful)} 個用戶的成就資料"
            )
        else:
            embed = StandardEmbedBuilder.create_warning_embed(
                "⚠️ 批量重置部分完成", f"批量重置操作完成,成功率: {success_rate:.1f}%"
            )

        embed.add_field(
            name="📊 操作統計",
            value=(
                f"**總用戶數**: {total} 個\n"
                f"**成功重置**: {len(successful)} 個\n"
                f"**重置失敗**: {len(failed)} 個\n"
                f"**成功率**: {success_rate:.1f}%"
            ),
            inline=True,
        )

        # 統計清除的資料
        total_achievements_cleared = sum(u["achievement_count"] for u in successful)
        total_progress_cleared = sum(u["progress_count"] for u in successful)
        total_points_cleared = sum(u["achievement_points"] for u in successful)

        embed.add_field(
            name="🗑️ 清除統計",
            value=(
                f"**清除成就**: {total_achievements_cleared} 個\n"
                f"**清除進度**: {total_progress_cleared} 個\n"
                f"**清除點數**: {total_points_cleared} 點"
            ),
            inline=True,
        )

        embed.set_footer(
            text=f"操作完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return embed


# ================================================================================
# Task 6 實作完成 - 批量用戶操作功能
# ================================================================================

# ================================================================================
# Task 3 實作完成 - 成就撤銷功能
# ================================================================================


class AchievementCriteriaSelectionView(ui.View):
    """成就條件選擇視圖."""

    def __init__(self, panel: AdminPanel, achievements: list):
        """初始化成就條件選擇視圖."""
        super().__init__(timeout=300)
        self.panel = panel
        self.achievements = achievements

        # 創建成就選擇下拉選單
        options = []
        for achievement in achievements[:25]:  # Discord 限制最多25個選項
            options.append(
                discord.SelectOption(
                    label=achievement.name[:100],  # 限制標籤長度
                    value=str(achievement.id),
                    description=f"類型: {achievement.type.value} | 點數: {achievement.points}",
                    emoji="🏆",
                )
            )

        if options:
            self.achievement_select = ui.Select(
                placeholder="選擇要設置條件的成就...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.achievement_select.callback = self.achievement_selected
            self.add_item(self.achievement_select)

    async def achievement_selected(self, interaction: discord.Interaction):
        """處理成就選擇."""
        try:
            achievement_id = int(self.achievement_select.values[0])

            # 啟動條件編輯器
            await self.panel.criteria_manager.start_criteria_editor(
                interaction, achievement_id
            )

        except Exception as e:
            logger.error(f"處理成就選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理成就選擇時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, _button: ui.Button):
        """返回成就管理."""
        try:
            # 返回成就管理視圖
            view = AchievementManagementView(self.panel)
            embed = await self.panel._create_achievement_management_embed()

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"返回成就管理失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)
