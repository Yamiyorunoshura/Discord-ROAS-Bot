"""
反惡意連結保護模組 - 選擇器元件
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from ..main_view import AntiLinkMainView


class PanelSelector(ui.Select):
    """面板選擇器"""

    def __init__(self, view: AntiLinkMainView):
        # 定義選項
        options = [
            discord.SelectOption(
                label="預覽面板",
                description="查看模組狀態和基本資訊",
                value="preview",
            ),
            discord.SelectOption(
                label="設定面板",
                description="管理保護設定和參數",
                value="config",
            ),
            discord.SelectOption(
                label="白名單管理",
                description="管理信任的網域列表",
                value="whitelist",
            ),
            discord.SelectOption(
                label="黑名單管理",
                description="管理危險網域列表",
                value="blacklist",
            ),
            discord.SelectOption(
                label="統計資訊",
                description="查看攔截統計和分析",
                value="stats",
            ),
        ]

        super().__init__(
            placeholder="選擇要查看的面板...",
            min_values=1,
            max_values=1,
            options=options,
        )

        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """選擇器回調"""
        selected_panel = self.values[0]
        await self.main_view.switch_panel(selected_panel, interaction)
