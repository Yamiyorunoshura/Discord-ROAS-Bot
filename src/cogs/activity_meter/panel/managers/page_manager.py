"""
活躍度面板頁面管理器
- 管理頁面狀態和切換邏輯
- 提供統一的頁面載入機制
- 支援頁面歷史記錄
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import discord

from ...config import config
from ...database.database import ActivityDatabase
from .permission_manager import PermissionManager

logger = logging.getLogger("activity_meter")


class ActivityMeterError(Exception):
    """活躍度系統錯誤基類"""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")


class PageManager:
    """
    頁面管理器

    功能:
    - 管理頁面狀態和切換邏輯
    - 提供統一的頁面載入機制
    - 支援頁面歷史記錄
    """

    def __init__(self):
        """初始化頁面管理器"""
        self.current_page = "settings"
        self.page_history = []
        self.page_data = {}
        self.pages = {}

    async def switch_page(
        self, page_name: str, interaction: discord.Interaction
    ) -> bool:
        """
        切換到指定頁面 - 修復版本

        Args:
            page_name: 頁面名稱
            interaction: Discord 互動

        Returns:
            bool: 切換是否成功
        """
        try:
            # 驗證頁面存在性
            available_pages = ["settings", "preview", "stats", "history"]
            if page_name not in available_pages:
                raise ActivityMeterError("E202", f"頁面不存在: {page_name}")

            # 檢查用戶權限

            permission_manager = PermissionManager()
            if not permission_manager.can_access_page(interaction.user, page_name):
                raise ActivityMeterError("E001", f"權限不足,無法訪問 {page_name} 頁面")

            # 更新頁面歷史
            if self.current_page != page_name:
                self.page_history.append(self.current_page)

            # 更新當前頁面
            self.current_page = page_name

            # 載入頁面數據
            await self.load_page_data(page_name, interaction)

            logger.info(f"頁面已成功切換到: {page_name}")
            return True

        except Exception as e:
            logger.error(f"頁面切換失敗: {e}")
            raise ActivityMeterError("E202", f"頁面切換失敗: {e!s}") from e

    async def load_page(self, page_name: str, interaction: discord.Interaction):
        """
        載入指定頁面 - 向後兼容方法

        Args:
            page_name: 頁面名稱
            interaction: Discord 互動
        """
        await self.switch_page(page_name, interaction)

    async def load_page_data(self, page_name: str, interaction: discord.Interaction):
        """
        載入頁面所需數據

        Args:
            page_name: 頁面名稱
            interaction: Discord 互動
        """
        try:
            if page_name == "settings":
                await self._load_settings_data(interaction)
            elif page_name == "preview":
                await self._load_preview_data(interaction)
            elif page_name == "stats":
                await self._load_stats_data(interaction)
            elif page_name == "history":
                await self._load_history_data(interaction)
        except Exception as e:
            logger.error(f"載入頁面數據失敗: {e}")
            raise

    async def _load_settings_data(self, interaction: discord.Interaction):
        """載入設定頁面數據"""
        # 獲取當前設定

        db = ActivityDatabase()

        report_channels = await db.get_report_channels()
        channel_id = next(
            (ch_id for g_id, ch_id in report_channels if g_id == interaction.guild.id),
            None,
        )

        self.page_data["settings"] = {
            "channel_id": channel_id,
            "guild": interaction.guild,
        }

    async def _load_preview_data(self, interaction: discord.Interaction):
        """載入預覽頁面數據"""

        db = ActivityDatabase()

        # 獲取今日日期
        now = datetime.now(config.TW_TZ)
        ymd = now.strftime(config.DAY_FMT)

        # 獲取排行榜資料
        rankings = await db.get_daily_rankings(ymd, interaction.guild.id, limit=5)

        self.page_data["preview"] = {
            "rankings": rankings,
            "guild": interaction.guild,
            "date": ymd,
        }

    async def _load_stats_data(self, interaction: discord.Interaction):
        """載入統計頁面數據"""

        db = ActivityDatabase()

        # 獲取日期
        now = datetime.now(config.TW_TZ)
        today_ymd = now.strftime(config.DAY_FMT)
        yesterday_ymd = (now - timedelta(days=1)).strftime(config.DAY_FMT)
        current_month = now.strftime(config.MONTH_FMT)

        # 獲取統計數據
        today_rankings = await db.get_daily_rankings(
            today_ymd, interaction.guild.id, limit=3
        )
        yesterday_rankings = await db.get_daily_rankings(
            yesterday_ymd, interaction.guild.id, limit=3
        )
        monthly_stats = await db.get_monthly_stats(current_month, interaction.guild.id)

        self.page_data["stats"] = {
            "today_rankings": today_rankings,
            "yesterday_rankings": yesterday_rankings,
            "monthly_stats": monthly_stats,
            "guild": interaction.guild,
        }

    async def _load_history_data(self, interaction: discord.Interaction):
        """載入歷史頁面數據"""
        # 暫時返回佔位符數據
        self.page_data["history"] = {
            "guild": interaction.guild,
            "message": "歷史記錄功能將在後續版本中實現",
        }

    def get_current_page(self) -> str:
        """獲取當前頁面"""
        return self.current_page

    def get_page_data(self, page_name: str | None = None) -> dict[str, Any]:
        """獲取頁面數據"""
        page = page_name or self.current_page
        return self.page_data.get(page, {})

    def get_page_history(self) -> list[str]:
        """獲取頁面歷史"""
        return self.page_history.copy()

    def can_go_back(self) -> bool:
        """檢查是否可以返回上一頁"""
        return len(self.page_history) > 0

    def go_back(self) -> str | None:
        """返回上一頁"""
        if self.can_go_back():
            previous_page = self.page_history.pop()
            self.current_page = previous_page
            return previous_page
        return None
