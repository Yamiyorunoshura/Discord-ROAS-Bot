"""
反可執行檔案保護模組 - 按鈕元件
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from ..main_view import AntiExecutableMainView

# Modal imports (避免循環導入)
with contextlib.suppress(ImportError):
    from .modals import (
        AddBlacklistModal,
        AddFormatModal,
        AddWhitelistModal,
        RemoveBlacklistModal,
        RemoveFormatModal,
        RemoveWhitelistModal,
        SettingsModal,
    )


# 基礎按鈕類
class BaseButton(ui.Button):
    """基礎按鈕類"""

    def __init__(self, view: AntiExecutableMainView, **kwargs):
        super().__init__(**kwargs)
        self.main_view = view


# 主要面板按鈕
class EnableButton(BaseButton):
    """啟用模組按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="啟用保護", style=discord.ButtonStyle.green, emoji="🟢"
        )

    async def callback(self, interaction: discord.Interaction):
        """啟用模組"""
        try:
            await self.main_view.cog.enable_protection(self.main_view.guild_id)
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"啟用保護失敗:{exc}")


class DisableButton(BaseButton):
    """停用模組按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="停用保護", style=discord.ButtonStyle.red, emoji="🔴"
        )

    async def callback(self, interaction: discord.Interaction):
        """停用模組"""
        try:
            await self.main_view.cog.disable_protection(self.main_view.guild_id)
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"停用保護失敗:{exc}")


class SettingsButton(BaseButton):
    """設定按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="進階設定", style=discord.ButtonStyle.secondary, emoji="⚙️"
        )

    async def callback(self, interaction: discord.Interaction):
        """打開設定對話框"""
        modal = SettingsModal(self.main_view)
        await interaction.response.send_modal(modal)


class HelpButton(BaseButton):
    """說明按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="使用說明", style=discord.ButtonStyle.secondary, emoji="❓"
        )

    async def callback(self, interaction: discord.Interaction):
        """顯示使用說明"""
        embed = discord.Embed(
            title="🛡️ 反可執行檔案保護 - 使用說明",
            description="防止惡意可執行檔案傳播的保護系統",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🔧 功能說明",
            value="• 自動檢測並攔截可執行檔案\n• 支援多種檔案格式檢測\n• 白名單和黑名單管理\n• 詳細的攔截統計",
            inline=False,
        )

        embed.add_field(
            name="⚙️ 設定選項",
            value="• 刪除訊息:自動刪除違規訊息\n• 管理員通知:向管理員發送通知\n• 用戶警告:向用戶發送警告訊息",
            inline=False,
        )

        embed.add_field(
            name="📋 清單管理",
            value="• 白名單:允許的檔案格式或網域\n• 黑名單:直接攔截的項目\n• 格式管理:設定檢測的檔案格式",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# 白名單管理按鈕
class AddWhitelistButton(BaseButton):
    """新增白名單按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="新增項目", style=discord.ButtonStyle.green, emoji="+"
        )

    async def callback(self, interaction: discord.Interaction):
        """新增白名單項目"""
        modal = AddWhitelistModal(self.main_view)
        await interaction.response.send_modal(modal)


class RemoveWhitelistButton(BaseButton):
    """移除白名單按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="移除項目", style=discord.ButtonStyle.red, emoji="-"
        )

    async def callback(self, interaction: discord.Interaction):
        """移除白名單項目"""
        modal = RemoveWhitelistModal(self.main_view)
        await interaction.response.send_modal(modal)


class ClearWhitelistButton(BaseButton):
    """清空白名單按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="清空白名單", style=discord.ButtonStyle.red, emoji="🗑️"
        )

    async def callback(self, interaction: discord.Interaction):
        """清空白名單"""
        try:
            await self.main_view.cog.clear_whitelist(self.main_view.guild_id)
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"清空白名單失敗:{exc}")


# 黑名單管理按鈕
class AddBlacklistButton(BaseButton):
    """新增黑名單按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="新增項目", style=discord.ButtonStyle.green, emoji="+"
        )

    async def callback(self, interaction: discord.Interaction):
        """新增黑名單項目"""
        modal = AddBlacklistModal(self.main_view)
        await interaction.response.send_modal(modal)


class RemoveBlacklistButton(BaseButton):
    """移除黑名單按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="移除項目", style=discord.ButtonStyle.red, emoji="-"
        )

    async def callback(self, interaction: discord.Interaction):
        """移除黑名單項目"""
        modal = RemoveBlacklistModal(self.main_view)
        await interaction.response.send_modal(modal)


class RefreshBlacklistButton(BaseButton):
    """重新整理黑名單按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="重新整理", style=discord.ButtonStyle.secondary, emoji="🔄"
        )

    async def callback(self, interaction: discord.Interaction):
        """重新整理黑名單"""
        try:
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"重新整理失敗:{exc}")


# 格式管理按鈕
class AddFormatButton(BaseButton):
    """新增格式按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="新增格式", style=discord.ButtonStyle.green, emoji="+"
        )

    async def callback(self, interaction: discord.Interaction):
        """新增檔案格式"""
        modal = AddFormatModal(self.main_view)
        await interaction.response.send_modal(modal)


class RemoveFormatButton(BaseButton):
    """移除格式按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="移除格式", style=discord.ButtonStyle.red, emoji="-"
        )

    async def callback(self, interaction: discord.Interaction):
        """移除檔案格式"""
        modal = RemoveFormatModal(self.main_view)
        await interaction.response.send_modal(modal)


class ResetFormatsButton(BaseButton):
    """重置格式按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="重置格式", style=discord.ButtonStyle.secondary, emoji="🔄"
        )

    async def callback(self, interaction: discord.Interaction):
        """重置為預設格式"""
        try:
            await self.main_view.cog.reset_formats(self.main_view.guild_id)
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"重置格式失敗:{exc}")


# 統計面板按鈕
class ClearStatsButton(BaseButton):
    """清空統計按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="清空統計", style=discord.ButtonStyle.red, emoji="🗑️"
        )

    async def callback(self, interaction: discord.Interaction):
        """清空統計資料"""
        try:
            await self.main_view.cog.clear_stats(self.main_view.guild_id)
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"清空統計失敗:{exc}")


class ExportStatsButton(BaseButton):
    """匯出統計按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="匯出統計", style=discord.ButtonStyle.secondary, emoji="📊"
        )

    async def callback(self, interaction: discord.Interaction):
        """匯出統計資料"""
        try:
            await self.main_view.cog.export_stats(self.main_view.guild_id)
            # 這裡可以實現統計資料的匯出功能
            await interaction.response.send_message(
                "📊 統計資料匯出功能開發中...", ephemeral=True
            )
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"匯出統計失敗:{exc}")


class RefreshStatsButton(BaseButton):
    """重新整理統計按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="重新整理", style=discord.ButtonStyle.secondary, emoji="🔄"
        )

    async def callback(self, interaction: discord.Interaction):
        """重新整理統計資料"""
        try:
            await self.main_view.update_panel(interaction)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"重新整理失敗:{exc}")


# 分頁按鈕
class PrevPageButton(BaseButton):
    """上一頁按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="上一頁", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )

    async def callback(self, interaction: discord.Interaction):
        """上一頁"""
        await self.main_view.change_page(-1, interaction)


class NextPageButton(BaseButton):
    """下一頁按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="下一頁", style=discord.ButtonStyle.secondary, emoji="➡️"
        )

    async def callback(self, interaction: discord.Interaction):
        """下一頁"""
        await self.main_view.change_page(1, interaction)


# 通用按鈕
class CloseButton(BaseButton):
    """關閉按鈕"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(
            view=view, label="關閉面板", style=discord.ButtonStyle.secondary, emoji="✖️"
        )

    async def callback(self, interaction: discord.Interaction):
        """關閉面板"""
        try:
            embed = discord.Embed(
                title="✅ 面板已關閉",
                description="反可執行檔案保護面板已關閉",
                color=discord.Color.green(),
            )

            # 禁用所有元件
            for item in self.main_view.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self.main_view)
        except Exception as exc:
            await self.main_view._handle_error(interaction, f"關閉面板失敗:{exc}")
