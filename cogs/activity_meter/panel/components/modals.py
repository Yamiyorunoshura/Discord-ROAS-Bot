"""
活躍度系統對話框元件
- 提供面板所需的各種對話框
"""

import discord
from typing import Optional, Any, Dict

from ...database.database import ActivityDatabase

class SetChannelModal(discord.ui.Modal, title="設定排行榜頻道"):
    """設定排行榜頻道對話框"""
    
    channel_id = discord.ui.TextInput(
        label="頻道 ID",
        placeholder="請輸入頻道 ID",
        required=True,
        min_length=1,
        max_length=20
    )
    
    def __init__(self, view: Any):
        super().__init__()
        self.view = view
        self.db = ActivityDatabase()
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        try:
            # 獲取頻道 ID
            channel_id = int(self.channel_id.value.strip())
            
            # 檢查頻道是否存在
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ 無法獲取伺服器資訊", ephemeral=True)
                return
            
            channel = guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ 找不到指定的頻道", ephemeral=True)
                return
            
            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("❌ 指定的頻道不是文字頻道", ephemeral=True)
                return
            
            # 更新設定
            await self.db.set_report_channel(guild.id, channel_id)
            
            # 回應
            await interaction.response.send_message(f"✅ 已設定排行榜頻道為 {channel.mention}", ephemeral=True)
            
            # 重新整理面板
            if self.view and hasattr(self.view, "refresh"):
                await self.view.refresh(interaction)
        
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的頻道 ID", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 設定失敗：{e}", ephemeral=True) 