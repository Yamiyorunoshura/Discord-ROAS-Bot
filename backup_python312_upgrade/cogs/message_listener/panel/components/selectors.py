"""
選擇器組件模組
- 提供各種選擇器組件
"""

import discord
from discord.ui import ChannelSelect, Select
from typing import List, Optional

class LogChannelSelect(ChannelSelect):
    """日誌頻道選擇器"""
    
    def __init__(self, cog):
        super().__init__(
            placeholder="📺 選擇日誌頻道",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            custom_id="message_log_channel"
        )
        self.cog = cog
    
    async def callback(self, interaction: discord.Interaction):
        """選擇回調"""
        try:
            channel = self.values[0]
            # 設定日誌頻道
            await self.cog.set_setting("log_channel_id", str(channel.id))
            
            # 更新設定面板
            await self.view.refresh(interaction)
            
            # 發送確認訊息
            await interaction.followup.send(
                f"✅ 日誌頻道已設定為 {channel.mention}",
                ephemeral=True
            )
        except Exception as exc:
            await interaction.response.send_message(
                f"❌ 設定日誌頻道失敗: {exc}",
                ephemeral=True
            )


class MonitoredChannelsSelect(ChannelSelect):
    """監聽頻道選擇器"""
    
    def __init__(self, cog):
        super().__init__(
            placeholder="👁️ 管理監聽頻道",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=25,
            custom_id="monitored_channels"
        )
        self.cog = cog
    
    async def callback(self, interaction: discord.Interaction):
        """選擇回調"""
        try:
            # 獲取當前監聽頻道
            current_channels = await self.cog.db.get_monitored_channels()
            
            # 獲取選擇的頻道
            selected_channels = [channel.id for channel in self.values]
            
            # 計算添加和移除的頻道
            to_add = [ch_id for ch_id in selected_channels if ch_id not in current_channels]
            to_remove = [ch_id for ch_id in current_channels if ch_id not in selected_channels]
            
            # 更新監聽頻道
            for channel_id in to_add:
                await self.cog.db.add_monitored_channel(channel_id)
            
            for channel_id in to_remove:
                await self.cog.db.remove_monitored_channel(channel_id)
            
            # 更新快取
            await self.cog.refresh_monitored_channels()
            
            # 更新設定面板
            await self.view.refresh(interaction)
            
            # 發送確認訊息
            message = []
            if to_add:
                added_channels = [f"<#{ch_id}>" for ch_id in to_add]
                message.append(f"✅ 已添加 {len(to_add)} 個監聽頻道: {', '.join(added_channels)}")
            
            if to_remove:
                removed_channels = [f"<#{ch_id}>" for ch_id in to_remove]
                message.append(f"✅ 已移除 {len(to_remove)} 個監聽頻道: {', '.join(removed_channels)}")
            
            if not message:
                message = ["✅ 監聽頻道未變更"]
            
            await interaction.followup.send("\n".join(message), ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(
                f"❌ 更新監聽頻道失敗: {exc}",
                ephemeral=True
            ) 