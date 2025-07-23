"""
反垃圾訊息面板按鈕組件
- 定義各種功能按鈕
- 處理用戶交互
- 提供統一的按鈕樣式
"""

import discord
from discord import ui
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main.main import AntiSpam

class StatsButton(ui.Button):
    """統計資料按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="統計資料",
            emoji="📊",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """統計按鈕回調"""
        # 這裡需要從 view 中取得 cog 和 guild
        view = self.view
        if hasattr(view, 'show_stats'):
            await view.show_stats(interaction)
        else:
            await interaction.response.send_message("❌ 無法載入統計資料。", ephemeral=True)

class TestButton(ui.Button):
    """測試功能按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="功能測試",
            emoji="🧪",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """測試按鈕回調"""
        embed = discord.Embed(
            title="🧪 功能測試",
            description="測試功能正在開發中，敬請期待！",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class HelpButton(ui.Button):
    """幫助按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="幫助",
            emoji="❓",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """幫助按鈕回調"""
        view = self.view
        if hasattr(view, 'show_help'):
            await view.show_help(interaction)
        else:
            await interaction.response.send_message("❌ 無法載入幫助資訊。", ephemeral=True)

class ResetButton(ui.Button):
    """重置設定按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="重置設定",
            emoji="🔄",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """重置按鈕回調"""
        view = self.view
        if hasattr(view, 'reset_settings'):
            await view.reset_settings(interaction)
        else:
            await interaction.response.send_message("❌ 無法執行重置操作。", ephemeral=True)

class CloseButton(ui.Button):
    """關閉面板按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="關閉",
            emoji="❌",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """關閉按鈕回調"""
        embed = discord.Embed(
            title="👋 面板已關閉",
            description="感謝使用反垃圾訊息保護系統！",
            color=discord.Color.green()
        )
        
        # 禁用所有組件
        view = self.view
        if view:
            for item in view.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=view)

class CategorySelectButton(ui.Button):
    """分類選擇按鈕"""
    
    def __init__(self, category_id: str, category_name: str, emoji: str, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=category_name,
            emoji=emoji,
            custom_id=f"category_{category_id}",
            row=row
        )
        self.category_id = category_id
    
    async def callback(self, interaction: discord.Interaction):
        """分類選擇回調"""
        view = self.view
        if hasattr(view, 'current_category'):
            view.current_category = self.category_id
            if hasattr(view, 'build_embed'):
                embed = await view.build_embed()
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message("❌ 無法載入分類設定。", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 無法切換分類。", ephemeral=True)

class SensitivityButton(ui.Button):
    """靈敏度設定按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="靈敏度設定",
            emoji="⚙️",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """靈敏度設定回調"""
        view = self.view
        if hasattr(view, 'show_sensitivity_settings'):
            await view.show_sensitivity_settings(interaction)
        else:
            # 創建靈敏度設定視圖
            sensitivity_view = SensitivitySelectView(view.cog, view.user_id, view.guild)
            embed = await sensitivity_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=sensitivity_view)


class SensitivitySelectView(ui.View):
    """靈敏度選擇視圖"""
    
    def __init__(self, cog: "AntiSpam", user_id: int, guild: discord.Guild):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.guild = guild
        
        # 添加靈敏度選擇按鈕
        self.add_item(SensitivityLevelButton("low", "低", "🟢", row=0))
        self.add_item(SensitivityLevelButton("medium", "中", "🟡", row=0))
        self.add_item(SensitivityLevelButton("high", "高", "🔴", row=0))
        
        # 添加返回按鈕
        self.add_item(BackButton(row=1))
    
    async def build_embed(self) -> discord.Embed:
        """構建靈敏度設定嵌入"""
        # 獲取當前靈敏度
        current_sensitivity = await self.cog.get_cfg(self.guild.id, "sensitivity", "medium")
        
        embed = discord.Embed(
            title="⚙️ 靈敏度設定",
            description="選擇反垃圾訊息檢測的靈敏度等級",
            color=discord.Color.blue()
        )
        
        # 靈敏度說明
        sensitivity_info = {
            "low": "🟢 **低靈敏度**\n較寬鬆的檢測，適合活躍社群",
            "medium": "🟡 **中靈敏度**\n平衡的檢測，適合一般社群",
            "high": "🔴 **高靈敏度**\n嚴格的檢測，適合需要嚴格管理的社群"
        }
        
        for level, info in sensitivity_info.items():
            is_current = level == current_sensitivity
            status = " ✅ **目前設定**" if is_current else ""
            embed.add_field(
                name=f"{info.split('**')[1]}{status}",
                value=info.split('\n')[1],
                inline=False
            )
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """權限檢查"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有命令發起者可以操作", ephemeral=True)
            return False
        return True


class SensitivityLevelButton(ui.Button):
    """靈敏度等級按鈕"""
    
    def __init__(self, level: str, label: str, emoji: str, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=f"{label}靈敏度",
            emoji=emoji,
            custom_id=f"sensitivity_{level}",
            row=row
        )
        self.level = level
    
    async def callback(self, interaction: discord.Interaction):
        """靈敏度選擇回調"""
        view = self.view
        
        try:
            # 更新靈敏度設定
            await view.cog.set_cfg(view.guild.id, "sensitivity", self.level)
            
            # 根據靈敏度調整其他相關設定
            sensitivity_configs = {
                "low": {
                    "frequency_limit": "10",
                    "frequency_window": "60",
                    "repeat_threshold": "0.8",
                    "sticker_limit": "5"
                },
                "medium": {
                    "frequency_limit": "7",
                    "frequency_window": "45",
                    "repeat_threshold": "0.6",
                    "sticker_limit": "3"
                },
                "high": {
                    "frequency_limit": "5",
                    "frequency_window": "30",
                    "repeat_threshold": "0.4",
                    "sticker_limit": "2"
                }
            }
            
            # 批量更新設定
            config = sensitivity_configs[self.level]
            for key, value in config.items():
                await view.cog.set_cfg(view.guild.id, key, value)
            
            # 更新嵌入
            embed = await view.build_embed()
            embed.insert_field_at(
                0,
                name="✅ 設定已更新",
                value=f"靈敏度已設定為 **{self.label}靈敏度**",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 設定更新失敗：{str(e)}", ephemeral=True)


class BackButton(ui.Button):
    """返回按鈕"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="返回",
            emoji="↩️",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """返回主面板"""
        view = self.view
        from ..main_view import AntiSpamMainView
        
        main_view = AntiSpamMainView(view.cog, view.user_id, view.guild)
        embed = await main_view.build_main_embed()
        await interaction.response.edit_message(embed=embed, view=main_view) 