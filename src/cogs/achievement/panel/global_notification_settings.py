"""全域通知設定管理面板視圖.

此模組提供管理員的全域通知設定管理介面,包括:
- 伺服器公告頻道設定
- 公告功能開關
- 通知頻率限制設定
- 重要成就篩選設定
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..database.models import GlobalNotificationSettings

# 常數定義
MIN_RATE_LIMIT_SECONDS = 10
MAX_RATE_LIMIT_SECONDS = 3600

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)


class GlobalNotificationSettingsView(discord.ui.View):
    """全域通知設定面板視圖."""

    def __init__(
        self,
        guild_id: int,
        repository: AchievementRepository,
        current_settings: GlobalNotificationSettings | None = None,
    ):
        """初始化全域通知設定面板.

        Args:
            guild_id: 伺服器 ID
            repository: 資料庫存取庫
            current_settings: 當前全域設定(如有)
        """
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.repository = repository
        self.settings = current_settings or GlobalNotificationSettings(
            guild_id=guild_id,
            announcement_enabled=False,
            rate_limit_seconds=60,
            important_achievements_only=False,
        )

        # 設定初始按鈕狀態
        self._update_button_states()

    def _update_button_states(self) -> None:
        """更新按鈕狀態以反映當前設定."""
        # 更新公告功能按鈕
        announcement_button = self.get_item("announcement_toggle")
        if announcement_button:
            announcement_button.style = (
                discord.ButtonStyle.success
                if self.settings.announcement_enabled
                else discord.ButtonStyle.secondary
            )
            announcement_button.label = (
                "伺服器公告: 開啟"
                if self.settings.announcement_enabled
                else "伺服器公告: 關閉"
            )

        # 更新篩選按鈕
        filter_button = self.get_item("filter_toggle")
        if filter_button:
            filter_button.style = (
                discord.ButtonStyle.success
                if self.settings.important_achievements_only
                else discord.ButtonStyle.secondary
            )
            filter_button.label = (
                "重要成就篩選: 開啟"
                if self.settings.important_achievements_only
                else "重要成就篩選: 關閉"
            )

    @discord.ui.button(
        label="設定公告頻道",
        style=discord.ButtonStyle.primary,
        custom_id="set_channel",
        ,
    )
    async def set_announcement_channel(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        """設定公告頻道."""
        try:
            # 建立頻道選擇選單
            channel_select = ChannelSelectView(
                self.guild_id, self.repository, self.settings
            )

            embed = discord.Embed(
                title="📢 設定公告頻道",
                description="選擇要用於發送成就公告的頻道:",
                color=0x3498DB,
            )

            # 顯示當前設定
            if self.settings.announcement_channel_id:
                channel = interaction.guild.get_channel(
                    self.settings.announcement_channel_id
                )
                if channel:
                    embed.add_field(
                        name="當前頻道", value=f"#{channel.name}", inline=False
                    )
                else:
                    embed.add_field(
                        name="當前頻道", value="頻道已被刪除,請重新設定", inline=False
                    )
            else:
                embed.add_field(name="當前頻道", value="未設定", inline=False)

            await interaction.response.send_message(
                embed=embed, view=channel_select, ephemeral=True
            )

        except Exception as e:
            logger.error(f"開啟頻道設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 無法開啟頻道設定,請稍後再試.", ephemeral=True
            )

    @discord.ui.button(
        label="伺服器公告: 關閉",
        style=discord.ButtonStyle.secondary,
        custom_id="announcement_toggle",
        ,
    )
    async def toggle_announcements(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        """切換伺服器公告功能."""
        try:
            # 切換設定
            self.settings.announcement_enabled = not self.settings.announcement_enabled

            # 更新資料庫
            await self._save_settings()

            # 更新按鈕狀態
            self._update_button_states()

            # 建立回應 embed
            embed = self._create_settings_embed(interaction.guild)

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"切換公告功能失敗: {e}")
            await interaction.response.send_message(
                "❌ 設定更新失敗,請稍後再試.", ephemeral=True
            )

    @discord.ui.button(
        label="頻率限制設定",
        style=discord.ButtonStyle.primary,
        custom_id="rate_limit",
        ,
    )
    async def configure_rate_limit(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        """設定通知頻率限制."""
        try:
            # 建立頻率限制設定模態框
            modal = RateLimitModal(self.settings, self.repository)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"開啟頻率限制設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 無法開啟頻率限制設定,請稍後再試.", ephemeral=True
            )

    @discord.ui.button(
        label="重要成就篩選: 關閉",
        style=discord.ButtonStyle.secondary,
        custom_id="filter_toggle",
    )
    async def toggle_important_filter(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        """切換重要成就篩選."""
        try:
            # 切換設定
            self.settings.important_achievements_only = (
                not self.settings.important_achievements_only
            )

            # 更新資料庫
            await self._save_settings()

            # 更新按鈕狀態
            self._update_button_states()

            # 建立回應 embed
            embed = self._create_settings_embed(interaction.guild)

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"切換篩選設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 設定更新失敗,請稍後再試.", ephemeral=True
            )

    @discord.ui.button(
        label="重置設定",
        style=discord.ButtonStyle.danger,
        custom_id="reset_settings",
        ,
    )
    async def reset_settings(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        """重置全域設定為預設值."""
        try:
            # 重置為預設值
            self.settings.announcement_channel_id = None
            self.settings.announcement_enabled = False
            self.settings.rate_limit_seconds = 60
            self.settings.important_achievements_only = False

            # 更新資料庫
            await self._save_settings()

            # 更新按鈕狀態
            self._update_button_states()

            # 建立回應 embed
            embed = self._create_settings_embed(interaction.guild)
            embed.add_field(
                name="✅ 重置完成", value="全域通知設定已重置為預設值", inline=False
            )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"重置全域設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 重置失敗,請稍後再試.", ephemeral=True
            )

    async def _save_settings(self) -> None:
        """儲存全域設定到資料庫."""
        try:
            # 檢查是否已存在設定
            existing = await self.repository.get_global_notification_settings(
                self.guild_id
            )

            if existing:
                # 更新現有設定
                existing.announcement_channel_id = self.settings.announcement_channel_id
                existing.announcement_enabled = self.settings.announcement_enabled
                existing.rate_limit_seconds = self.settings.rate_limit_seconds
                existing.important_achievements_only = (
                    self.settings.important_achievements_only
                )
                await self.repository.update_global_notification_settings(existing)
            else:
                # 建立新設定
                await self.repository.create_global_notification_settings(self.settings)

        except Exception as e:
            logger.error(f"儲存全域設定失敗: {e}")
            raise

    def _create_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """建立全域設定顯示 embed."""
        embed = discord.Embed(
            title="🔧 全域通知設定",
            description=f"管理 {guild.name} 的成就通知設定",
            color=0xE74C3C,
        )

        # 公告頻道
        if self.settings.announcement_channel_id:
            channel = guild.get_channel(self.settings.announcement_channel_id)
            channel_name = f"#{channel.name}" if channel else "頻道已刪除"
        else:
            channel_name = "未設定"

        embed.add_field(name="📢 公告頻道", value=channel_name, inline=True)

        # 公告功能狀態
        announcement_status = (
            "✅ 開啟" if self.settings.announcement_enabled else "❌ 關閉"
        )
        embed.add_field(name="🔔 伺服器公告", value=announcement_status, inline=True)

        # 頻率限制
        embed.add_field(
            name="⏱️ 頻率限制",
            value=f"{self.settings.rate_limit_seconds} 秒",
            inline=True,
        )

        # 重要成就篩選
        filter_status = (
            "✅ 開啟" if self.settings.important_achievements_only else "❌ 關閉"
        )
        embed.add_field(name="重要成就篩選", value=filter_status, inline=True)

        embed.set_footer(text="僅管理員可以修改這些設定")

        return embed


class ChannelSelectView(discord.ui.View):
    """頻道選擇視圖."""

    def __init__(
        self,
        guild_id: int,
        repository: AchievementRepository,
        settings: GlobalNotificationSettings,
    ):
        """初始化頻道選擇視圖."""
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.repository = repository
        self.settings = settings

        # 添加頻道選擇選單
        self.add_item(ChannelSelect(self.settings))

    async def save_settings(self) -> None:
        """儲存更新的設定."""
        try:
            existing = await self.repository.get_global_notification_settings(
                self.guild_id
            )

            if existing:
                existing.announcement_channel_id = self.settings.announcement_channel_id
                await self.repository.update_global_notification_settings(existing)
            else:
                await self.repository.create_global_notification_settings(self.settings)

        except Exception as e:
            logger.error(f"儲存頻道設定失敗: {e}")
            raise


class ChannelSelect(discord.ui.ChannelSelect):
    """頻道選擇選單."""

    def __init__(self, settings: GlobalNotificationSettings):
        """初始化頻道選擇選單."""
        self.settings = settings

        super().__init__(
            placeholder="選擇公告頻道...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """處理頻道選擇."""
        try:
            # 更新設定
            selected_channel = self.values[0]
            self.settings.announcement_channel_id = selected_channel.id

            # 儲存到資料庫
            view = self.view
            if hasattr(view, "save_settings"):
                await view.save_settings()

            # 建立回應 embed
            embed = discord.Embed(
                title="✅ 公告頻道已設定",
                description=f"已將 {selected_channel.mention} 設為成就公告頻道",
                color=0x00FF00,
            )

            embed.add_field(
                name="📝 注意事項",
                value="請確保機器人有在該頻道發送訊息的權限",
                inline=False,
            )

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"設定公告頻道失敗: {e}")
            await interaction.response.send_message(
                "❌ 頻道設定失敗,請稍後再試.", ephemeral=True
            )


class RateLimitModal(discord.ui.Modal):
    """頻率限制設定模態框."""

    def __init__(
        self, settings: GlobalNotificationSettings, repository: AchievementRepository
    ):
        """初始化頻率限制模態框."""
        super().__init__(title="設定通知頻率限制")
        self.settings = settings
        self.repository = repository

        # 添加輸入框
        self.rate_limit_input = discord.ui.TextInput(
            label="頻率限制(秒)",
            placeholder="輸入頻率限制時間(10-3600秒)",
            default=str(settings.rate_limit_seconds),
            min_length=2,
            max_length=4,
        )
        self.add_item(self.rate_limit_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理模態框提交."""
        try:
            # 驗證輸入值
            rate_limit = int(self.rate_limit_input.value)

            if (
                rate_limit < MIN_RATE_LIMIT_SECONDS
                or rate_limit > MAX_RATE_LIMIT_SECONDS
            ):
                await interaction.response.send_message(
                    "❌ 頻率限制必須在 {MIN_RATE_LIMIT_SECONDS}-{MAX_RATE_LIMIT_SECONDS} 秒之間",
                    ephemeral=True,
                )
                return

            # 更新設定
            self.settings.rate_limit_seconds = rate_limit

            # 儲存到資料庫
            existing = await self.repository.get_global_notification_settings(
                self.settings.guild_id
            )

            if existing:
                existing.rate_limit_seconds = rate_limit
                await self.repository.update_global_notification_settings(existing)
            else:
                await self.repository.create_global_notification_settings(self.settings)

            # 建立回應 embed
            embed = discord.Embed(
                title="✅ 頻率限制已更新",
                description=f"通知頻率限制已設定為 {rate_limit} 秒",
                color=0x00FF00,
            )

            embed.add_field(
                name="📝 說明",
                value="這個設定會限制成就公告的發送頻率,避免頻道被洗版",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的數字", ephemeral=True
            )
        except Exception as e:
            logger.error(f"更新頻率限制失敗: {e}")
            await interaction.response.send_message(
                "❌ 設定更新失敗,請稍後再試.", ephemeral=True
            )


async def create_global_notification_settings_panel(
    guild_id: int, repository: AchievementRepository
) -> tuple[discord.Embed, GlobalNotificationSettingsView]:
    """建立全域通知設定管理面板.

    Args:
        guild_id: 伺服器 ID
        repository: 資料庫存取庫

    Returns:
        (embed, view) 元組
    """
    try:
        # 獲取當前設定
        current_settings = await repository.get_global_notification_settings(guild_id)

        # 建立視圖
        view = GlobalNotificationSettingsView(guild_id, repository, current_settings)

        # 建立 embed(需要 guild 物件,這裡先建立基本版本)
        embed = discord.Embed(
            title="🔧 全域通知設定",
            description="管理伺服器的成就通知設定",
            color=0xE74C3C,
        )

        # 基本設定資訊
        if current_settings:
            embed.add_field(
                name="📢 公告頻道",
                value=f"<#{current_settings.announcement_channel_id}>"
                if current_settings.announcement_channel_id
                else "未設定",
                inline=True,
            )

            announcement_status = (
                "✅ 開啟" if current_settings.announcement_enabled else "❌ 關閉"
            )
            embed.add_field(
                name="🔔 伺服器公告", value=announcement_status, inline=True
            )

            embed.add_field(
                name="⏱️ 頻率限制",
                value=f"{current_settings.rate_limit_seconds} 秒",
                inline=True,
            )

            filter_status = (
                "✅ 開啟" if current_settings.important_achievements_only else "❌ 關閉"
            )
            embed.add_field(name="重要成就篩選", value=filter_status, inline=True)
        else:
            embed.add_field(name="📋 狀態", value="尚未設定,將使用預設值", inline=False)

        embed.set_footer(text="僅管理員可以修改這些設定")

        return embed, view

    except Exception as e:
        logger.error(f"建立全域設定面板失敗: {e}")

        # 建立錯誤 embed
        error_embed = discord.Embed(
            title="❌ 載入失敗",
            description="無法載入全域通知設定,請稍後再試.",
            color=0xFF0000,
        )

        return error_embed, None


__all__ = [
    "ChannelSelect",
    "ChannelSelectView",
    "GlobalNotificationSettingsView",
    "RateLimitModal",
    "create_global_notification_settings_panel",
]
