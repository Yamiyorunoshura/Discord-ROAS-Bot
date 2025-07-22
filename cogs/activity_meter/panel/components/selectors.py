"""
活躍度系統選擇器元件
- 提供面板所需的各種選擇器
- 實現PRD v1.71的完整選擇器架構
"""

import discord
from typing import Optional, Any, List
from enum import Enum

# 進度條風格枚舉
class ProgressBarStyle(Enum):
    CLASSIC = "classic"
    MODERN = "modern" 
    NEON = "neon"
    MINIMAL = "minimal"
    GRADIENT = "gradient"

# 風格配置
STYLE_CONFIGS = {
    "classic": {
        "bg_color": (54, 57, 63, 255),
        "border_color": (114, 118, 125),
        "text_color": (255, 255, 255),
        "shadow": True,
        "glow": False
    },
    "modern": {
        "bg_color": (32, 34, 37, 255),
        "border_color": (79, 84, 92),
        "text_color": (220, 221, 222),
        "shadow": True,
        "glow": True
    },
    "neon": {
        "bg_color": (20, 20, 20, 255),
        "border_color": (0, 255, 255),
        "text_color": (255, 255, 255),
        "shadow": True,
        "glow": True,
        "glow_color": (0, 255, 255)
    },
    "minimal": {
        "bg_color": (255, 255, 255, 255),
        "border_color": (200, 200, 200),
        "text_color": (0, 0, 0),
        "shadow": False,
        "glow": False
    },
    "gradient": {
        "bg_color": (32, 34, 37, 255),
        "border_color": (79, 84, 92),
        "text_color": (255, 255, 255),
        "shadow": True,
        "glow": False,
        "gradient": True,
        "gradient_colors": [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    }
}

class PageSelector(discord.ui.Select):
    """頁面選擇下拉選單"""
    
    def __init__(self, view):
        options = [
            discord.SelectOption(label="設定", value="settings", emoji="⚙️", description="系統設定和配置"),
            discord.SelectOption(label="預覽", value="preview", emoji="👀", description="預覽目前進度條風格效果"),
            discord.SelectOption(label="統計", value="stats", emoji="📊", description="查看統計資訊")
        ]
        super().__init__(
            placeholder="選擇頁面",
            options=options,
            row=0
        )
        # 在 Discord.py 2.5.2 中，不能直接設置屬性
        # 使用 __dict__ 來設置 view 屬性
        self.__dict__['view'] = view
    
    async def callback(self, interaction: discord.Interaction):
        """頁面選擇回調"""
        try:
            # 檢查權限
            if not self.view.can_view_panel(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限查看此面板",
                    ephemeral=True
                )
                return
            
            selected_page = self.values[0]
            
            # 更新當前頁面
            self.view.current_page = selected_page
            
            # 動態更新面板組件
            self.view._update_page_components(selected_page)
            
            # 更新面板顯示
            await self.view.update_panel_display(interaction)
            
        except Exception as e:
            await self.view.handle_error(interaction, e)

class StyleSelector(discord.ui.Select):
    """進度條風格選擇器"""
    
    def __init__(self, view):
        options = [
            discord.SelectOption(label="經典", value="classic", emoji="📊"),
            discord.SelectOption(label="現代", value="modern", emoji="🎨"),
            discord.SelectOption(label="霓虹", value="neon", emoji="✨"),
            discord.SelectOption(label="極簡", value="minimal", emoji="⚪"),
            discord.SelectOption(label="漸層", value="gradient", emoji="🌈")
        ]
        super().__init__(
            placeholder="選擇進度條風格",
            options=options,
            row=1
        )
        # 在 Discord.py 2.5.2 中，不能直接設置屬性
        # 使用 __dict__ 來設置 view 屬性
        self.__dict__['view'] = view
    
    async def callback(self, interaction: discord.Interaction):
        """風格選擇回調"""
        try:
            # 檢查權限
            if not self.view.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            selected_style = self.values[0]
            await self.view.update_progress_style(interaction, selected_style)
            
        except Exception as e:
            await self.view.handle_error(interaction, e)

class ChannelSelector(discord.ui.Select):
    """公告頻道選擇器"""
    
    def __init__(self, view):
        # 動態獲取伺服器頻道
        guild = view.bot.get_guild(view.guild_id)
        channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]
        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id), emoji="📝")
            for ch in channels[:25]  # Discord限制最多25個選項
        ]
        super().__init__(
            placeholder="選擇公告頻道",
            options=options,
            row=1
        )
        # 在 Discord.py 2.5.2 中，不能直接設置屬性
        # 使用 __dict__ 來設置 view 屬性
        self.__dict__['view'] = view
    
    async def callback(self, interaction: discord.Interaction):
        """頻道選擇回調"""
        try:
            # 檢查權限
            if not self.view.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            selected_channel_id = int(self.values[0])
            await self.view.update_announcement_channel(interaction, selected_channel_id)
            
        except Exception as e:
            await self.view.handle_error(interaction, e)

class TimeSelector(discord.ui.Select):
    """公告時間選擇器"""
    
    def __init__(self, view):
        options = [
            discord.SelectOption(label=f"{hour:02d}:00", value=str(hour), emoji="⏰")
            for hour in range(24)
        ]
        super().__init__(
            placeholder="選擇公告時間",
            options=options,
            row=1
        )
        # 在 Discord.py 2.5.2 中，不能直接設置屬性
        # 使用 __dict__ 來設置 view 屬性
        self.__dict__['view'] = view
    
    async def callback(self, interaction: discord.Interaction):
        """時間選擇回調"""
        try:
            # 檢查權限
            if not self.view.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            selected_hour = int(self.values[0])
            await self.view.update_announcement_time(interaction, selected_hour)
            
        except Exception as e:
            await self.view.handle_error(interaction, e) 