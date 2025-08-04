"""
反可執行檔案保護模組 - 主要視圖類
負責管理面板狀態和UI元件的協調
"""

import logging

import discord
from discord import ui

from ..main.main import AntiExecutable
from .components.buttons import (
    AddBlacklistButton,
    AddFormatButton,
    AddWhitelistButton,
    ClearStatsButton,
    ClearWhitelistButton,
    CloseButton,
    DisableButton,
    EnableButton,
    ExportStatsButton,
    HelpButton,
    NextPageButton,
    PrevPageButton,
    RefreshBlacklistButton,
    RefreshStatsButton,
    RemoveBlacklistButton,
    RemoveFormatButton,
    RemoveWhitelistButton,
    ResetFormatsButton,
    SettingsButton,
)
from .components.selectors import PanelSelector
from .embeds.blacklist_embed import BlacklistEmbed
from .embeds.formats_embed import FormatsEmbed
from .embeds.main_embed import MainEmbed
from .embeds.stats_embed import StatsEmbed
from .embeds.whitelist_embed import WhitelistEmbed


class AntiExecutableMainView(ui.View):
    """
    反可執行檔案保護模組主要視圖類

    負責:
    - 管理面板狀態和分頁
    - 協調各種UI元件
    - 處理面板生命週期
    - 統一的錯誤處理
    """

    def __init__(self, cog: AntiExecutable, guild_id: int, user_id: int):
        """
        初始化主要視圖

        Args:
            cog: 反可執行檔案模組實例
            guild_id: 伺服器ID
            user_id: 用戶ID
        """
        super().__init__(timeout=300.0)  # 5分鐘超時

        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

        # 面板狀態
        self.current_panel = "main"  # 當前顯示的面板
        self.page_number = 0  # 當前頁碼(用於列表分頁)

        # Embed 生成器
        self.main_embed = MainEmbed(cog, guild_id)
        self.whitelist_embed = WhitelistEmbed(cog, guild_id)
        self.blacklist_embed = BlacklistEmbed(cog, guild_id)
        self.formats_embed = FormatsEmbed(cog, guild_id)
        self.stats_embed = StatsEmbed(cog, guild_id)

        # 初始化UI元件
        self._setup_components()

    def _setup_components(self):
        """設置UI元件"""
        # 面板選擇器
        self.add_item(PanelSelector(self))

        # 根據當前面板添加相應的按鈕
        self._update_buttons()

    def _update_buttons(self):
        """根據當前面板更新按鈕"""
        items_to_remove = [
            item for item in self.children if isinstance(item, ui.Button)
        ]
        for item in items_to_remove:
            self.remove_item(item)

        # 根據面板類型添加按鈕
        if self.current_panel == "main":
            self.add_item(EnableButton(self))
            self.add_item(DisableButton(self))
            self.add_item(SettingsButton(self))
            self.add_item(HelpButton(self))
        elif self.current_panel == "whitelist":
            self.add_item(AddWhitelistButton(self))
            self.add_item(RemoveWhitelistButton(self))
            self.add_item(ClearWhitelistButton(self))
            if self.page_number > 0:
                self.add_item(PrevPageButton(self))
            # 檢查是否有下一頁的邏輯可以在這裡添加
            self.add_item(NextPageButton(self))
        elif self.current_panel == "blacklist":
            self.add_item(AddBlacklistButton(self))
            self.add_item(RemoveBlacklistButton(self))
            self.add_item(RefreshBlacklistButton(self))
        elif self.current_panel == "formats":
            self.add_item(AddFormatButton(self))
            self.add_item(RemoveFormatButton(self))
            self.add_item(ResetFormatsButton(self))
        elif self.current_panel == "stats":
            self.add_item(ClearStatsButton(self))
            self.add_item(ExportStatsButton(self))
            self.add_item(RefreshStatsButton(self))

        # 通用按鈕
        self.add_item(CloseButton(self))

    async def get_current_embed(self) -> discord.Embed:
        """
        獲取當前面板的Embed

        Returns:
            當前面板的Embed
        """
        try:
            panel_handlers = {
                "main": lambda: self.main_embed.create_embed(),
                "whitelist": lambda: self.whitelist_embed.create_embed(self.page_number),
                "blacklist": lambda: self.blacklist_embed.create_embed(self.page_number),
                "formats": lambda: self.formats_embed.create_embed(),
                "stats": lambda: self.stats_embed.create_embed(),
            }

            handler = panel_handlers.get(self.current_panel, panel_handlers["main"])
            return await handler()

        except Exception as exc:
            return discord.Embed(
                title="❌ 面板載入錯誤",
                description=f"載入面板時發生錯誤:{exc}",
                color=discord.Color.red(),
            )

    async def switch_panel(self, panel_name: str, interaction: discord.Interaction):
        """
        切換面板

        Args:
            panel_name: 面板名稱
            interaction: Discord互動
        """
        try:
            self.current_panel = panel_name
            self.page_number = 0  # 重置頁碼
            self._update_buttons()

            embed = await self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as exc:
            await self._handle_error(interaction, f"切換面板失敗:{exc}")

    async def update_panel(self, interaction: discord.Interaction):
        """
        更新當前面板

        Args:
            interaction: Discord互動
        """
        try:
            embed = await self.get_current_embed()
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except Exception as exc:
            await self._handle_error(interaction, f"更新面板失敗:{exc}")

    async def change_page(self, direction: int, interaction: discord.Interaction):
        """
        翻頁

        Args:
            direction: 翻頁方向 (1=下一頁, -1=上一頁)
            interaction: Discord互動
        """
        try:
            self.page_number = max(0, self.page_number + direction)
            self._update_buttons()
            embed = await self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as exc:
            await self._handle_error(interaction, f"翻頁失敗:{exc}")

    async def _handle_error(self, interaction: discord.Interaction, error_msg: str):
        """
        統一錯誤處理

        Args:
            interaction: Discord互動
            error_msg: 錯誤訊息
        """
        try:
            embed = discord.Embed(
                title="❌ 操作失敗", description=error_msg, color=discord.Color.red()
            )

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            # 如果連錯誤處理都失敗,記錄到日誌
            logger = logging.getLogger("anti_executable")
            logger.error(f"面板錯誤處理失敗:{error_msg}")

    async def on_timeout(self):
        """處理超時"""
        try:
            # 禁用所有元件
            for item in self.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

            # 這裡可以添加超時後的處理邏輯
            # 例如編輯訊息顯示超時狀態
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        檢查互動權限

        Args:
            interaction: Discord互動

        Returns:
            是否有權限
        """
        # 檢查是否為原始用戶
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令執行者可以操作此面板", ephemeral=True
            )
            return False

        # 檢查管理員權限
        if interaction.guild is None:
            return False

        member = interaction.guild.get_member(interaction.user.id)
        if member is None or not member.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 需要「管理伺服器」權限才能使用此功能", ephemeral=True
            )
            return False

        return True
