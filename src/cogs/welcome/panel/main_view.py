"""
歡迎系統面板視圖模組 - 重構版本

此模組包含歡迎系統的主要設定面板視圖,採用依賴注入架構
提供更好的可測試性和錯誤處理
"""

import builtins
import contextlib
from typing import TYPE_CHECKING, Protocol

import discord

from ...core.error_handler import ErrorCodes, create_error_handler
from ...core.logger import setup_module_logger

if TYPE_CHECKING:
    from ..main.main import WelcomeCog

# 匯入模態對話框組件
from .components.modals import (
    SetAvatarSizeModal,
    SetAvatarXModal,
    SetAvatarYModal,
    SetChannelModal,
    SetDescFontSizeModal,
    SetDescModal,
    SetDescYModal,
    SetMsgModal,
    SetTitleFontSizeModal,
    SetTitleModal,
    SetTitleYModal,
)
from .embeds.settings_embed import build_settings_embed

# 設置日誌
logger = setup_module_logger("welcome.panel")
error_handler = create_error_handler("welcome.panel", logger)


# 定義UI組件接口
class IUIComponentFactory(Protocol):
    """UI組件工廠接口"""

    def create_modal(
        self,
        modal_type: str,
        cog: "WelcomeCog",
        panel_msg: discord.Message | None = None,
    ) -> discord.ui.Modal: ...


class UIComponentFactory:
    """UI組件工廠實現"""

    def create_modal(
        self,
        modal_type: str,
        cog: "WelcomeCog",
        panel_msg: discord.Message | None = None,
    ) -> discord.ui.Modal:
        """
        創建UI模態對話框

        Args:
            modal_type: 對話框類型
            cog: WelcomeCog實例
            panel_msg: 面板訊息

        Returns:
            discord.ui.Modal: 對話框實例
        """

        modal_map = {
            "channel": SetChannelModal,
            "title": SetTitleModal,
            "description": SetDescModal,
            "message": SetMsgModal,
            "avatar_x": SetAvatarXModal,
            "avatar_y": SetAvatarYModal,
            "title_y": SetTitleYModal,
            "desc_y": SetDescYModal,
            "title_font_size": SetTitleFontSizeModal,
            "desc_font_size": SetDescFontSizeModal,
            "avatar_size": SetAvatarSizeModal,
        }

        if modal_type not in modal_map:
            raise ValueError(f"未知的對話框類型: {modal_type}")

        return modal_map[modal_type](cog, panel_msg)


class SettingsView(discord.ui.View):
    """歡迎系統設定面板視圖 - 重構版本"""

    def __init__(
        self, cog: "WelcomeCog", ui_factory: IUIComponentFactory | None = None
    ):
        """
        初始化設定面板視圖

        Args:
            cog: WelcomeCog 實例
            ui_factory: UI組件工廠(可選,用於測試)
        """
        super().__init__(timeout=300)  # 5分鐘超時
        self.cog = cog
        self.panel_msg: discord.Message | None = None
        self.ui_factory = ui_factory or UIComponentFactory()

        logger.debug("SettingsView 初始化完成")

    @discord.ui.select(
        placeholder="選擇要調整的設定項目",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="📺 設定歡迎頻道", description="設定歡迎訊息發送的頻道"
            ),
            discord.SelectOption(
                label="📝 設定圖片標題", description="設定歡迎圖片上的標題文字"
            ),
            discord.SelectOption(
                label="📄 設定圖片內容", description="設定歡迎圖片上的內容文字"
            ),
            discord.SelectOption(
                label="🎨 上傳背景圖片", description="上傳自訂背景圖片(PNG/JPG)"
            ),
            discord.SelectOption(
                label="💬 設定歡迎訊息", description="設定純文字歡迎訊息"
            ),
            discord.SelectOption(
                label="📍 調整頭像 X 位置", description="調整頭像在圖片上的 X 座標"
            ),
            discord.SelectOption(
                label="📍 調整頭像 Y 位置", description="調整頭像在圖片上的 Y 座標"
            ),
            discord.SelectOption(
                label="📍 調整標題 Y 位置", description="調整標題的 Y 座標"
            ),
            discord.SelectOption(
                label="📍 調整內容 Y 位置", description="調整內容的 Y 座標"
            ),
            discord.SelectOption(
                label="🔤 調整標題字體大小", description="調整標題字體大小(像素)"
            ),
            discord.SelectOption(
                label="🔤 調整內容字體大小", description="調整內容字體大小(像素)"
            ),
            discord.SelectOption(
                label="🖼️ 調整頭像大小", description="調整頭像顯示的像素大小"
            ),
        ],
    )
    async def select_callback(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """
        選擇器回調函數

        Args:
            interaction: Discord 互動物件
            select: 選擇器物件
        """
        try:
            if not interaction.guild_id:
                await interaction.response.send_message(
                    "❌ 此功能只能在伺服器中使用", ephemeral=True
                )
                return

            # 根據選擇的選項顯示不同的設定介面
            option = select.values[0]

            if "上傳背景圖片" in option:
                await interaction.response.send_message(
                    "請上傳一張背景圖片(PNG 或 JPG 格式,最大 5MB)", ephemeral=True
                )

                # 等待使用者上傳圖片
                def check(m):
                    return (
                        m.author.id == interaction.user.id
                        and m.channel.id == interaction.channel_id
                        and m.attachments
                    )

                try:
                    msg = await self.cog.bot.wait_for(
                        "message", check=check, timeout=60.0
                    )

                    if msg.attachments:
                        attachment = msg.attachments[0]
                        success = await self.cog.handle_background_upload(
                            interaction, attachment
                        )

                        if success:
                            # 刪除上傳的訊息
                            with contextlib.suppress(builtins.BaseException):
                                await msg.delete()

                            # 發送成功訊息
                            await interaction.followup.send(
                                "✅ 背景圖片已上傳並設定", ephemeral=True
                            )

                            # 更新面板
                            await self._refresh_panel()

                except TimeoutError:
                    await interaction.followup.send(
                        "❌ 上傳超時,請重新操作", ephemeral=True
                    )

            else:
                # 其他設定項目:使用工廠模式創建對應的 Modal
                modal_type_map = {
                    "設定歡迎頻道": "channel",
                    "設定圖片標題": "title",
                    "設定圖片內容": "description",
                    "設定歡迎訊息": "message",
                    "調整頭像 X 位置": "avatar_x",
                    "調整頭像 Y 位置": "avatar_y",
                    "調整標題 Y 位置": "title_y",
                    "調整內容 Y 位置": "desc_y",
                    "調整標題字體大小": "title_font_size",
                    "調整內容字體大小": "desc_font_size",
                    "調整頭像大小": "avatar_size",
                }

                modal_type = None
                for key, value in modal_type_map.items():
                    if key in option:
                        modal_type = value
                        break

                if modal_type:
                    try:
                        modal = self.ui_factory.create_modal(
                            modal_type, self.cog, self.panel_msg
                        )
                        await interaction.response.send_modal(modal)
                        logger.debug(f"已顯示 {modal_type} 對話框")
                    except Exception as e:
                        logger.error(f"創建對話框失敗 - 類型: {modal_type}, 錯誤: {e}")
                        await interaction.response.send_message(
                            "❌ 創建設定對話框失敗", ephemeral=True
                        )
                else:
                    await interaction.response.send_message(
                        "❌ 未知的設定項目", ephemeral=True
                    )

        except Exception as exc:
            await error_handler.handle_error(
                exc,
                ErrorCodes.UI_INTERACTION_FAILED,
                f"選擇器回調失敗 - 選項: {select.values[0] if select.values else 'unknown'}",
                interaction,
            )

    @discord.ui.button(label="預覽效果", style=discord.ButtonStyle.primary, emoji="👁️")
    async def preview_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        """
        預覽按鈕回調函數

        Args:
            interaction: Discord 互動物件
            button: 按鈕物件
        """
        try:
            if not interaction.guild_id or not interaction.guild:
                await interaction.response.send_message(
                    "❌ 此功能只能在伺服器中使用", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)

            # 確保使用者是成員物件
            if not isinstance(interaction.user, discord.Member):
                await interaction.followup.send("❌ 無法取得成員資訊", ephemeral=True)
                return

            # 生成預覽圖片
            member = interaction.user
            image = await self.cog._generate_welcome_image(
                interaction.guild_id, member, force_refresh=True
            )

            if image:
                # 取得設定
                settings = await self.cog.db.get_settings(interaction.guild_id)

                # 渲染訊息
                message = settings.get(
                    "message", "歡迎 {member.mention} 加入 {guild.name}!"
                )

                # 確保頻道是文字頻道
                channel = None
                if isinstance(interaction.channel, discord.TextChannel):
                    channel = interaction.channel

                rendered_message = self.cog.renderer.render_message(
                    member, interaction.guild, channel, message
                )

                await interaction.followup.send(
                    content=f"**預覽效果**\n{rendered_message}",
                    file=discord.File(fp=image, filename="welcome_preview.png"),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send("❌ 生成預覽圖片失敗", ephemeral=True)

        except Exception as exc:
            await error_handler.handle_error(
                exc, ErrorCodes.UI_INTERACTION_FAILED, "預覽按鈕操作失敗", interaction
            )

    @discord.ui.button(label="關閉", style=discord.ButtonStyle.secondary, emoji="❌")
    async def close_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        """
        關閉按鈕回調函數

        Args:
            interaction: Discord 互動物件
            button: 按鈕物件
        """
        try:
            await interaction.response.defer()

            if self.panel_msg:
                await self.panel_msg.delete()
                self.panel_msg = None
                self.stop()

        except Exception as exc:
            logger.error(f"關閉按鈕操作失敗: {exc}")

    async def _refresh_panel(self):
        """更新面板訊息"""
        if not self.panel_msg or not self.panel_msg.guild:
            return

        try:
            # 取得設定
            settings = await self.cog.db.get_settings(self.panel_msg.guild.id)

            # 建立新的 Embed
            embed = await build_settings_embed(self.cog, self.panel_msg.guild, settings)

            # 更新訊息
            await self.panel_msg.edit(embed=embed, view=self)

        except Exception as exc:
            logger.error(f"更新設定面板失敗: {exc}")

    async def on_timeout(self):
        """面板超時處理"""
        if self.panel_msg:
            with contextlib.suppress(builtins.BaseException):
                await self.panel_msg.edit(view=None)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        """處理視圖錯誤"""
        await error_handler.handle_error(
            error,
            ErrorCodes.UI_INTERACTION_FAILED,
            f"視圖組件錯誤 - 組件類型: {type(item).__name__}",
            interaction,
        )
