"""通知偏好管理面板視圖.

此模組提供用戶通知偏好的管理介面，包括：
- 通知偏好設定面板
- 私訊通知開關
- 伺服器公告開關
- 通知類型篩選
- 管理員的全域通知設定
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from ..database.models import NotificationPreference

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)


class NotificationPreferencesView(discord.ui.View):
    """通知偏好設定面板視圖."""

    def __init__(
        self,
        user_id: int,
        guild_id: int,
        repository: AchievementRepository,
        current_preferences: NotificationPreference | None = None
    ):
        """初始化通知偏好面板.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            repository: 資料庫存取庫
            current_preferences: 當前通知偏好（如有）
        """
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.repository = repository
        self.preferences = current_preferences or NotificationPreference(
            user_id=user_id,
            guild_id=guild_id,
            dm_notifications=True,
            server_announcements=True,
            notification_types=[]
        )

        # 設定初始按鈕狀態
        self._update_button_states()

    def _update_button_states(self) -> None:
        """更新按鈕狀態以反映當前偏好."""
        # 更新私訊通知按鈕
        dm_button = self.get_item("dm_toggle")
        if dm_button:
            dm_button.style = discord.ButtonStyle.success if self.preferences.dm_notifications else discord.ButtonStyle.secondary
            dm_button.label = "私訊通知: 開啟" if self.preferences.dm_notifications else "私訊通知: 關閉"

        # 更新伺服器公告按鈕
        announcement_button = self.get_item("announcement_toggle")
        if announcement_button:
            announcement_button.style = discord.ButtonStyle.success if self.preferences.server_announcements else discord.ButtonStyle.secondary
            announcement_button.label = "伺服器公告: 開啟" if self.preferences.server_announcements else "伺服器公告: 關閉"

    @discord.ui.button(
        label="私訊通知: 開啟",
        style=discord.ButtonStyle.success,
        custom_id="dm_toggle",
        emoji="💬"
    )
    async def toggle_dm_notifications(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """切換私訊通知設定."""
        try:
            # 切換設定
            self.preferences.dm_notifications = not self.preferences.dm_notifications

            # 更新資料庫
            await self._save_preferences()

            # 更新按鈕狀態
            self._update_button_states()

            # 建立回應 embed
            embed = self._create_preferences_embed()

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"切換私訊通知失敗: {e}")
            await interaction.response.send_message(
                "❌ 設定更新失敗，請稍後再試。",
                ephemeral=True
            )

    @discord.ui.button(
        label="伺服器公告: 開啟",
        style=discord.ButtonStyle.success,
        custom_id="announcement_toggle",
        emoji="📢"
    )
    async def toggle_server_announcements(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """切換伺服器公告設定."""
        try:
            # 切換設定
            self.preferences.server_announcements = not self.preferences.server_announcements

            # 更新資料庫
            await self._save_preferences()

            # 更新按鈕狀態
            self._update_button_states()

            # 建立回應 embed
            embed = self._create_preferences_embed()

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"切換伺服器公告失敗: {e}")
            await interaction.response.send_message(
                "❌ 設定更新失敗，請稍後再試。",
                ephemeral=True
            )

    @discord.ui.button(
        label="通知類型篩選",
        style=discord.ButtonStyle.primary,
        custom_id="type_filter",
        emoji="🎯"
    )
    async def configure_notification_types(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """設定通知類型篩選."""
        try:
            # 建立通知類型選擇視圖
            type_view = NotificationTypeSelectView(
                self.user_id,
                self.guild_id,
                self.repository,
                self.preferences
            )

            embed = discord.Embed(
                title="🎯 通知類型篩選",
                description="選擇您想要接收通知的成就類型：",
                color=0x3498db
            )

            # 顯示當前設定
            if self.preferences.notification_types:
                type_names = {
                    'counter': '計數型成就',
                    'milestone': '里程碑成就',
                    'time_based': '時間型成就',
                    'conditional': '條件型成就',
                    'rare': '稀有成就',
                    'epic': '史詩成就',
                    'legendary': '傳奇成就',
                    'all': '所有成就'
                }
                current_types = [
                    type_names.get(t, t) for t in self.preferences.notification_types
                ]
                embed.add_field(
                    name="當前設定",
                    value="、".join(current_types) if current_types else "無特定篩選",
                    inline=False
                )
            else:
                embed.add_field(
                    name="當前設定",
                    value="無特定篩選（接收所有類型）",
                    inline=False
                )

            await interaction.response.send_message(
                embed=embed,
                view=type_view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"開啟通知類型設定失敗: {e}")
            await interaction.response.send_message(
                "❌ 無法開啟通知類型設定，請稍後再試。",
                ephemeral=True
            )

    @discord.ui.button(
        label="重置為預設",
        style=discord.ButtonStyle.danger,
        custom_id="reset_preferences",
        emoji="🔄"
    )
    async def reset_preferences(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """重置通知偏好為預設值."""
        try:
            # 重置為預設值
            self.preferences.dm_notifications = True
            self.preferences.server_announcements = True
            self.preferences.notification_types = []

            # 更新資料庫
            await self._save_preferences()

            # 更新按鈕狀態
            self._update_button_states()

            # 建立回應 embed
            embed = self._create_preferences_embed()
            embed.add_field(
                name="✅ 重置完成",
                value="通知偏好已重置為預設設定",
                inline=False
            )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"重置通知偏好失敗: {e}")
            await interaction.response.send_message(
                "❌ 重置失敗，請稍後再試。",
                ephemeral=True
            )

    async def _save_preferences(self) -> None:
        """儲存通知偏好到資料庫."""
        try:
            # 檢查是否已存在偏好設定
            existing = await self.repository.get_notification_preferences(
                self.user_id, self.guild_id
            )

            if existing:
                # 更新現有設定
                existing.dm_notifications = self.preferences.dm_notifications
                existing.server_announcements = self.preferences.server_announcements
                existing.notification_types = self.preferences.notification_types
                await self.repository.update_notification_preferences(existing)
            else:
                # 建立新設定
                await self.repository.create_notification_preferences(self.preferences)

        except Exception as e:
            logger.error(f"儲存通知偏好失敗: {e}")
            raise

    def _create_preferences_embed(self) -> discord.Embed:
        """建立通知偏好顯示 embed."""
        embed = discord.Embed(
            title="🔔 通知偏好設定",
            description="管理您的成就通知偏好",
            color=0x3498db
        )

        # 私訊通知狀態
        dm_status = "✅ 開啟" if self.preferences.dm_notifications else "❌ 關閉"
        embed.add_field(
            name="💬 私訊通知",
            value=dm_status,
            inline=True
        )

        # 伺服器公告狀態
        announcement_status = "✅ 開啟" if self.preferences.server_announcements else "❌ 關閉"
        embed.add_field(
            name="📢 伺服器公告",
            value=announcement_status,
            inline=True
        )

        # 通知類型篩選
        if self.preferences.notification_types:
            type_names = {
                'counter': '計數型',
                'milestone': '里程碑',
                'time_based': '時間型',
                'conditional': '條件型',
                'rare': '稀有',
                'epic': '史詩',
                'legendary': '傳奇',
                'all': '所有'
            }
            current_types = [
                type_names.get(t, t) for t in self.preferences.notification_types
            ]
            type_filter = "、".join(current_types)
        else:
            type_filter = "接收所有類型"

        embed.add_field(
            name="🎯 通知類型",
            value=type_filter,
            inline=False
        )

        embed.set_footer(text="點擊按鈕來調整您的通知偏好")

        return embed


class NotificationTypeSelectView(discord.ui.View):
    """通知類型選擇視圖."""

    def __init__(
        self,
        user_id: int,
        guild_id: int,
        repository: AchievementRepository,
        preferences: NotificationPreference
    ):
        """初始化通知類型選擇視圖.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            repository: 資料庫存取庫
            preferences: 通知偏好物件
        """
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.repository = repository
        self.preferences = preferences

        # 添加選擇選單
        self.add_item(NotificationTypeSelect(self.preferences))

    async def save_preferences(self) -> None:
        """儲存更新的偏好設定."""
        try:
            existing = await self.repository.get_notification_preferences(
                self.user_id, self.guild_id
            )

            if existing:
                existing.notification_types = self.preferences.notification_types
                await self.repository.update_notification_preferences(existing)
            else:
                await self.repository.create_notification_preferences(self.preferences)

        except Exception as e:
            logger.error(f"儲存通知類型偏好失敗: {e}")
            raise


class NotificationTypeSelect(discord.ui.Select):
    """通知類型選擇選單."""

    def __init__(self, preferences: NotificationPreference):
        """初始化選擇選單.

        Args:
            preferences: 通知偏好物件
        """
        self.preferences = preferences

        options = [
            discord.SelectOption(
                label="計數型成就",
                value="counter",
                description="基於計數的成就（如發送訊息數量）",
                emoji="🔢"
            ),
            discord.SelectOption(
                label="里程碑成就",
                value="milestone",
                description="達到特定里程碑的成就",
                emoji="🏆"
            ),
            discord.SelectOption(
                label="時間型成就",
                value="time_based",
                description="基於時間的成就（如連續登入）",
                emoji="⏰"
            ),
            discord.SelectOption(
                label="條件型成就",
                value="conditional",
                description="滿足特定條件的成就",
                emoji="✅"
            ),
            discord.SelectOption(
                label="稀有成就",
                value="rare",
                description="獲得難度較高的稀有成就",
                emoji="💎"
            ),
            discord.SelectOption(
                label="史詩成就",
                value="epic",
                description="非常難獲得的史詩級成就",
                emoji="⚡"
            ),
            discord.SelectOption(
                label="傳奇成就",
                value="legendary",
                description="極其罕見的傳奇級成就",
                emoji="👑"
            ),
            discord.SelectOption(
                label="所有成就",
                value="all",
                description="接收所有類型的成就通知",
                emoji="🌟"
            ),
        ]

        # 設定當前選中的選項
        for option in options:
            if option.value in preferences.notification_types:
                option.default = True

        super().__init__(
            placeholder="選擇您想要接收通知的成就類型...",
            min_values=0,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """處理選擇變更."""
        try:
            # 更新偏好設定
            self.preferences.notification_types = list(self.values)

            # 儲存到資料庫
            view = self.view
            if hasattr(view, 'save_preferences'):
                await view.save_preferences()

            # 建立回應 embed
            embed = discord.Embed(
                title="✅ 通知類型偏好已更新",
                color=0x00ff00
            )

            if self.values:
                type_names = {
                    'counter': '計數型成就',
                    'milestone': '里程碑成就',
                    'time_based': '時間型成就',
                    'conditional': '條件型成就',
                    'rare': '稀有成就',
                    'epic': '史詩成就',
                    'legendary': '傳奇成就',
                    'all': '所有成就'
                }
                selected_types = [type_names.get(t, t) for t in self.values]
                embed.add_field(
                    name="已選擇的通知類型",
                    value="、".join(selected_types),
                    inline=False
                )
            else:
                embed.add_field(
                    name="通知類型設定",
                    value="不接收任何類型的通知",
                    inline=False
                )

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"更新通知類型偏好失敗: {e}")
            await interaction.response.send_message(
                "❌ 設定更新失敗，請稍後再試。",
                ephemeral=True
            )


async def create_notification_preferences_panel(
    user_id: int,
    guild_id: int,
    repository: AchievementRepository
) -> tuple[discord.Embed, NotificationPreferencesView]:
    """建立通知偏好管理面板.

    Args:
        user_id: 用戶 ID
        guild_id: 伺服器 ID
        repository: 資料庫存取庫

    Returns:
        (embed, view) 元組
    """
    try:
        # 獲取當前偏好設定
        current_preferences = await repository.get_notification_preferences(user_id, guild_id)

        # 建立視圖
        view = NotificationPreferencesView(
            user_id,
            guild_id,
            repository,
            current_preferences
        )

        # 建立 embed
        embed = view._create_preferences_embed()

        return embed, view

    except Exception as e:
        logger.error(f"建立通知偏好面板失敗: {e}")

        # 建立錯誤 embed
        error_embed = discord.Embed(
            title="❌ 載入失敗",
            description="無法載入通知偏好設定，請稍後再試。",
            color=0xff0000
        )

        return error_embed, None


__all__ = [
    "NotificationPreferencesView",
    "NotificationTypeSelect",
    "NotificationTypeSelectView",
    "create_notification_preferences_panel",
]
