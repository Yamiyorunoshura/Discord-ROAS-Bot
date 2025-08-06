"""
活躍度系統對話框元件
- 提供面板所需的各種對話框
- 實現時間設定Modal功能
"""

import json
import re
from typing import Any

import discord

from ...constants import MAX_HOUR, MAX_MINUTE
from ...database.database import ActivityDatabase


class SetChannelModal(discord.ui.Modal, title="設定排行榜頻道"):
    """設定排行榜頻道對話框"""

    channel_id = discord.ui.TextInput(
        label="頻道 ID",
        placeholder="請輸入頻道 ID",
        required=True,
        min_length=1,
        max_length=20,
    )

    def __init__(self, view: Any):
        super().__init__()
        self.view = view
        self.db = ActivityDatabase()

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        try:
            # 獲取頻道 ID
            channel_id = int(self.channel_id.value.strip())

            # 檢查頻道是否存在
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "無法獲取伺服器資訊", ephemeral=True
                )
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "找不到指定的頻道", ephemeral=True
                )
                return

            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "指定的頻道不是文字頻道", ephemeral=True
                )
                return

            # 更新設定
            await self.db.set_report_channel(guild.id, channel_id)

            # 回應
            await interaction.response.send_message(
                f"已設定排行榜頻道為 {channel.mention}", ephemeral=True
            )

            # 重新整理面板
            if self.view and hasattr(self.view, "refresh"):
                await self.view.refresh(interaction)

        except ValueError:
            await interaction.response.send_message(
                "請輸入有效的頻道 ID", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"設定失敗:{e}", ephemeral=True)


class AnnouncementTimeModal(discord.ui.Modal, title="設定公告時間"):
    """公告時間設定對話框"""

    time_input = discord.ui.TextInput(
        label="公告時間",
        placeholder="格式: HH:MM (24小時制)",
        required=True,
        min_length=5,
        max_length=5,
        default="09:00",
    )

    description_input = discord.ui.TextInput(
        label="描述(可選)",
        placeholder="時間設定的描述",
        required=False,
        max_length=100,
    )

    def __init__(self, view: Any):
        super().__init__()
        self.view = view
        self.db = ActivityDatabase()

    def validate_time_format(self, time_str: str) -> bool:
        """
        驗證時間格式

        Args:
            time_str: 時間字符串

        Returns:
            bool: 格式是否正確
        """
        # 檢查格式
        pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
        if not re.match(pattern, time_str):
            return False

        # 解析時間
        try:
            hour, minute = map(int, time_str.split(":"))
            return 0 <= hour <= MAX_HOUR and 0 <= minute <= MAX_MINUTE
        except (ValueError, AttributeError):
            return False

    async def update_time_config(self, guild_id: int, time_str: str):
        """
        更新時間配置

        Args:
            guild_id: 伺服器ID
            time_str: 時間字符串
        """
        # 更新數據庫
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE activity_meter_config
                SET announcement_time = $1, last_modified = NOW()
                WHERE guild_id = $2
            """,
                time_str,
                guild_id,
            )

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        try:
            # 驗證時間格式
            time_str = self.time_input.value.strip()
            if not self.validate_time_format(time_str):
                raise ValueError("時間格式錯誤")

            # 更新數據庫
            await self.update_time_config(interaction.guild.id, time_str)

            # 提供成功反饋
            await interaction.response.send_message(
                f"公告時間已設定為 {time_str}", ephemeral=True
            )

        except ValueError as e:
            await interaction.response.send_message(
                f"{e!s},請使用 HH:MM 格式", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"設定失敗:{e!s}", ephemeral=True
            )


class CustomOptionsModal(discord.ui.Modal, title="自訂進度條選項"):
    """自訂進度條選項對話框"""

    show_percentage = discord.ui.TextInput(
        label="顯示百分比 (true/false)",
        placeholder="true 或 false",
        required=True,
        min_length=4,
        max_length=5,
        default="true",
    )

    show_level_badge = discord.ui.TextInput(
        label="顯示等級徽章 (true/false)",
        placeholder="true 或 false",
        required=True,
        min_length=4,
        max_length=5,
        default="true",
    )

    animation_style = discord.ui.TextInput(
        label="動畫樣式",
        placeholder="pulse, slide, sparkle, wave, glow",
        required=False,
        max_length=20,
        default="pulse",
    )

    custom_text = discord.ui.TextInput(
        label="自訂文字格式 (可選)",
        placeholder="{name} ‧ {level} ‧ {score:.1f}/100",
        required=False,
        max_length=100,
        style=discord.TextStyle.paragraph,
    )

    progress_style = discord.ui.TextInput(
        label="進度樣式",
        placeholder="gradient, solid, striped",
        required=False,
        max_length=20,
        default="gradient",
    )

    def __init__(self, view: Any, current_options: dict | None = None):
        super().__init__()
        self.view = view
        self.db = ActivityDatabase()

        # 如果有現有選項, 設置為默認值
        if current_options:
            self.show_percentage.default = str(
                current_options.get("show_percentage", True)
            ).lower()
            self.show_level_badge.default = str(
                current_options.get("show_level_badge", True)
            ).lower()
            self.animation_style.default = current_options.get(
                "animation_style", "pulse"
            )
            self.custom_text.default = current_options.get("custom_text", "")
            self.progress_style.default = current_options.get(
                "progress_style", "gradient"
            )

    def validate_boolean(self, value: str) -> bool:
        """驗證布林值"""
        return value.lower() in ["true", "false", "1", "0", "yes", "no"]

    def parse_boolean(self, value: str) -> bool:
        """解析布林值"""
        return value.lower() in ["true", "1", "yes"]

    def validate_animation_style(self, style: str) -> bool:
        """驗證動畫樣式"""
        valid_styles = ["pulse", "slide", "sparkle", "wave", "glow"]
        return style.lower() in valid_styles

    def validate_progress_style(self, style: str) -> bool:
        """驗證進度樣式"""
        valid_styles = ["gradient", "solid", "striped"]
        return style.lower() in valid_styles

    async def save_custom_options(self, guild_id: int, options: dict):
        """保存自訂選項到數據庫"""
        try:
            # 這裡應該有一個專門的表來儲存自訂選項
            # 暫時使用配置表的擴展字段

            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO activity_meter_config (guild_id, custom_options, last_modified)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (guild_id)
                    DO UPDATE SET custom_options = $2, last_modified = NOW()
                    """,
                    guild_id,
                    json.dumps(options),
                )
        except Exception as e:
            raise Exception(f"保存自訂選項失敗: {e}") from e

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        try:
            # 驗證輸入值
            show_percentage_value = self.show_percentage.value.strip()
            show_level_badge_value = self.show_level_badge.value.strip()
            animation_style_value = self.animation_style.value.strip().lower()
            custom_text_value = self.custom_text.value.strip()
            progress_style_value = self.progress_style.value.strip().lower()

            # 驗證布林值
            if not self.validate_boolean(show_percentage_value):
                await interaction.response.send_message(
                    "顯示百分比必須是 true 或 false", ephemeral=True
                )
                return

            if not self.validate_boolean(show_level_badge_value):
                await interaction.response.send_message(
                    "顯示等級徽章必須是 true 或 false", ephemeral=True
                )
                return

            # 驗證動畫樣式
            if animation_style_value and not self.validate_animation_style(
                animation_style_value
            ):
                await interaction.response.send_message(
                    "無效的動畫樣式, 請選擇: pulse, slide, sparkle, wave, glow",
                    ephemeral=True,
                )
                return

            # 驗證進度樣式
            if progress_style_value and not self.validate_progress_style(
                progress_style_value
            ):
                await interaction.response.send_message(
                    "無效的進度樣式, 請選擇: gradient, solid, striped",
                    ephemeral=True,
                )
                return

            # 構建選項字典
            options = {
                "show_percentage": self.parse_boolean(show_percentage_value),
                "show_level_badge": self.parse_boolean(show_level_badge_value),
                "show_animation": True,  # 預設啟用動畫
                "animation_style": animation_style_value or "pulse",
                "custom_text": custom_text_value if custom_text_value else None,
                "progress_style": progress_style_value or "gradient",
                "bar_thickness": "normal",
                "corner_style": "rounded",
            }

            # 保存到數據庫
            await self.save_custom_options(interaction.guild.id, options)

            # 更新渲染器的自訂選項
            if hasattr(self.view, "renderer_options"):
                self.view.renderer_options = options

            # 成功回應
            embed = discord.Embed(
                title="自訂選項已保存",
                description="您的進度條自訂選項已成功保存!",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="設定摘要",
                value=f"• 顯示百分比: {'是' if options['show_percentage'] else '否'}\n"
                f"• 顯示等級徽章: {'是' if options['show_level_badge'] else '否'}\n"
                f"• 動畫樣式: {options['animation_style']}\n"
                f"• 進度樣式: {options['progress_style']}\n"
                f"• 自訂文字: {options['custom_text'] if options['custom_text'] else '無'}",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"保存自訂選項失敗: {e}", ephemeral=True
            )
