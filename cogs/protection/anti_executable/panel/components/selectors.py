"""
反可執行檔案保護模組 - 選擇器元件
"""

from __future__ import annotations
import discord
from discord import ui
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main_view import AntiExecutableMainView

class PanelSelector(ui.Select):
    """面板選擇器"""
    
    def __init__(self, view: AntiExecutableMainView):
        """
        初始化面板選擇器
        
        Args:
            view: 主要視圖實例
        """
        self.main_view = view
        
        # 定義選項
        options = [
            discord.SelectOption(
                label="主要面板",
                description="檢視模組狀態和基本設定",
                emoji="🏠",
                value="main"
            ),
            discord.SelectOption(
                label="白名單管理",
                description="管理允許的檔案格式和網域",
                emoji="📋",
                value="whitelist"
            ),
            discord.SelectOption(
                label="黑名單管理",
                description="管理被禁止的項目",
                emoji="🚫",
                value="blacklist"
            ),
            discord.SelectOption(
                label="格式管理",
                description="管理檢測的檔案格式",
                emoji="📁",
                value="formats"
            ),
            discord.SelectOption(
                label="攔截統計",
                description="檢視詳細的攔截統計資料",
                emoji="📊",
                value="stats"
            )
        ]
        
        super().__init__(
            placeholder="選擇要檢視的面板...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """處理選擇器回調"""
        try:
            selected_panel = self.values[0]
            await self.main_view.switch_panel(selected_panel, interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"切換面板失敗：{exc}") 