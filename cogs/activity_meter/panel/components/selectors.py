"""
活躍度系統選擇器元件
- 提供面板所需的各種選擇器
"""

import discord
from typing import Optional, Any, List

class PageSelector(discord.ui.Select):
    """頁面選擇器"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="設定頁面",
                description="查看和修改活躍度系統設定",
                emoji="⚙️",
                value="settings"
            ),
            discord.SelectOption(
                label="預覽排行榜",
                description="預覽自動播報的排行榜效果",
                emoji="👁️",
                value="preview"
            ),
            discord.SelectOption(
                label="統計資訊",
                description="查看活躍度系統的統計資訊",
                emoji="📊",
                value="stats"
            )
        ]
        
        super().__init__(
            placeholder="選擇頁面",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        """選擇器回調"""
        # 檢查權限
        if interaction.user.id != getattr(self.view, "author_id", 0):
            await interaction.response.send_message("❌ 只有原作者可以操作此面板", ephemeral=True)
            return
        
        # 切換頁面
        selected_value = self.values[0]
        await self.view.change_page(interaction, selected_value) 