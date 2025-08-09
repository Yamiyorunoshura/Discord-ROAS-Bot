"""
Sync Data 面板頁面選擇下拉選單組件
提供四個頁面的快速導航功能
"""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ..main_view import SyncDataMainView


class PageSelectDropdown(discord.ui.Select):
    """頁面選擇下拉選單"""

    def __init__(self, view: "SyncDataMainView", current_page: str = "status"):
        """
        初始化頁面選擇下拉選單

        Args:
            view: 主面板視圖實例
            current_page: 當前頁面名稱
        """
        self.main_view = view

        options = [
            discord.SelectOption(
                label="同步狀態",
                description="查看當前同步狀態和基本資訊",
                ,
                value="status",
                default=(current_page == "status"),
            ),
            discord.SelectOption(
                label="同步歷史",
                description="查看歷史同步記錄",
                ,
                value="history",
                default=(current_page == "history"),
            ),
            discord.SelectOption(
                label="同步設定",
                description="管理自動同步和範圍設定",
                ,
                value="settings",
                default=(current_page == "settings"),
            ),
            discord.SelectOption(
                label="診斷工具",
                description="系統診斷和故障排除",
                ,
                value="diagnostics",
                default=(current_page == "diagnostics"),
            ),
        ]

        super().__init__(
            placeholder="選擇頁面...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,  # 放在第一行
        )

    async def callback(self, interaction: discord.Interaction):
        """
        下拉選單選擇回調

        Args:
            interaction: Discord 互動物件
        """
        # 權限檢查由基類 StandardPanelView 處理
        selected_page = self.values[0]
        await self.main_view.change_page(interaction, selected_page)
