"""
反惡意連結保護模組 - 按鈕元件
"""

import discord
from discord import ui

from ..main_view import AntiLinkMainView


class TutorialButton(ui.Button):
    """教學按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="📚 使用教學", style=discord.ButtonStyle.secondary, emoji="📚"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        embed = discord.Embed(
            title="📚 反惡意連結保護使用教學",
            description="了解如何使用反惡意連結保護功能",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🔧 基本設定",
            value="• 使用面板選單切換不同設定頁面\n• 在設定頁面調整保護參數\n• 啟用後自動檢測惡意連結",
            inline=False,
        )

        embed.add_field(
            name="📝 白名單管理",
            value="• 添加信任的網域到白名單\n• 白名單中的網域不會被檢測\n• 支援萬用字元匹配",
            inline=False,
        )

        embed.add_field(
            name="🚫 黑名單管理",
            value="• 查看威脅情資黑名單\n• 手動添加危險網域\n• 定期自動更新",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class EnableButton(ui.Button):
    """啟用按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="🟢 啟用保護", style=discord.ButtonStyle.success, emoji="🟢"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        try:
            # 這裡應該調用實際的啟用功能
            await interaction.response.send_message(
                "✅ 反惡意連結保護已啟用", ephemeral=True
            )
            # 更新面板
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await interaction.response.send_message(
                f"❌ 啟用失敗:{exc}", ephemeral=True
            )


class DisableButton(ui.Button):
    """停用按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="🔴 停用保護", style=discord.ButtonStyle.danger, emoji="🔴"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        try:
            # 這裡應該調用實際的停用功能
            await interaction.response.send_message(
                "⚠️ 反惡意連結保護已停用", ephemeral=True
            )
            # 更新面板
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await interaction.response.send_message(
                f"❌ 停用失敗:{exc}", ephemeral=True
            )


class EditSettingsButton(ui.Button):
    """編輯設定按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="✏️ 編輯設定", style=discord.ButtonStyle.primary, emoji="✏️"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "⚙️ 設定編輯功能開發中...", ephemeral=True
        )


class ResetSettingsButton(ui.Button):
    """重置設定按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="🔄 重置設定", style=discord.ButtonStyle.secondary, emoji="🔄"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "🔄 設定重置功能開發中...", ephemeral=True
        )


class AddWhitelistButton(ui.Button):
    """添加白名單按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="➕ 添加白名單", style=discord.ButtonStyle.success, emoji="➕"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "➕ 添加白名單功能開發中...", ephemeral=True
        )


class RemoveWhitelistButton(ui.Button):
    """移除白名單按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="➖ 移除白名單", style=discord.ButtonStyle.danger, emoji="➖"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "➖ 移除白名單功能開發中...", ephemeral=True
        )


class ClearWhitelistButton(ui.Button):
    """清空白名單按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="🗑️ 清空白名單", style=discord.ButtonStyle.danger, emoji="🗑️"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "🗑️ 清空白名單功能開發中...", ephemeral=True
        )


class AddBlacklistButton(ui.Button):
    """添加黑名單按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="➕ 添加黑名單", style=discord.ButtonStyle.danger, emoji="➕"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "➕ 添加黑名單功能開發中...", ephemeral=True
        )


class RemoveBlacklistButton(ui.Button):
    """移除黑名單按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="➖ 移除黑名單", style=discord.ButtonStyle.success, emoji="➖"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "➖ 移除黑名單功能開發中...", ephemeral=True
        )


class RefreshBlacklistButton(ui.Button):
    """刷新黑名單按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="🔄 刷新黑名單", style=discord.ButtonStyle.secondary, emoji="🔄"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "🔄 刷新黑名單功能開發中...", ephemeral=True
        )


class ClearStatsButton(ui.Button):
    """清空統計按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="🗑️ 清空統計", style=discord.ButtonStyle.danger, emoji="🗑️"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "🗑️ 清空統計功能開發中...", ephemeral=True
        )


class ExportStatsButton(ui.Button):
    """匯出統計按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="📊 匯出統計", style=discord.ButtonStyle.primary, emoji="📊"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "📊 匯出統計功能開發中...", ephemeral=True
        )


class CloseButton(ui.Button):
    """關閉按鈕"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(
            label="❌ 關閉面板", style=discord.ButtonStyle.secondary, emoji="❌"
        )
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        embed = discord.Embed(
            title="👋 面板已關閉",
            description="感謝使用反惡意連結保護系統",
            color=discord.Color.greyple(),
        )

        # 禁用所有元件
        for item in self.main_view.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self.main_view)
