"""
活躍度系統按鈕元件
- 提供面板所需的各種按鈕
"""

import discord
from typing import Optional, Any

class CloseButton(discord.ui.Button):
    """關閉面板按鈕"""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="關閉",
            emoji="❌",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕點擊回調"""
        # 檢查權限
        if interaction.user.id != getattr(self.view, "author_id", 0):
            await interaction.response.send_message("❌ 只有原作者可以關閉此面板", ephemeral=True)
            return
        
        # 刪除訊息
        if interaction.message:
            await interaction.message.delete()

class RefreshButton(discord.ui.Button):
    """重新整理面板按鈕"""
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="重新整理",
            emoji="🔄",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕點擊回調"""
        # 檢查權限
        if interaction.user.id != getattr(self.view, "author_id", 0):
            await interaction.response.send_message("❌ 只有原作者可以操作此面板", ephemeral=True)
            return
        
        # 重新整理面板
        try:
            await self.view.refresh(interaction)
        except AttributeError:
            await interaction.response.send_message("❌ 此面板不支援重新整理功能", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 重新整理時發生錯誤: {str(e)}", ephemeral=True)

class PreviewButton(discord.ui.Button):
    """預覽排行榜按鈕"""
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="預覽排行榜",
            emoji="👁️",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕點擊回調"""
        # 檢查權限
        if interaction.user.id != getattr(self.view, "author_id", 0):
            await interaction.response.send_message("❌ 只有原作者可以操作此面板", ephemeral=True)
            return
        
        # 切換到預覽頁面
        await self.view.change_page(interaction, "preview")

class SettingsButton(discord.ui.Button):
    """設定頁面按鈕"""
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="設定",
            emoji="⚙️",
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕點擊回調"""
        # 檢查權限
        if interaction.user.id != getattr(self.view, "author_id", 0):
            await interaction.response.send_message("❌ 只有原作者可以操作此面板", ephemeral=True)
            return
        
        # 切換到設定頁面
        await self.view.change_page(interaction, "settings")

class StatsButton(discord.ui.Button):
    """統計頁面按鈕"""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="統計",
            emoji="📊",
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕點擊回調"""
        # 檢查權限
        if interaction.user.id != getattr(self.view, "author_id", 0):
            await interaction.response.send_message("❌ 只有原作者可以操作此面板", ephemeral=True)
            return
        
        # 切換到統計頁面
        await self.view.change_page(interaction, "stats") 