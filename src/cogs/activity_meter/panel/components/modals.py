"""
活躍度系統對話框元件
- 提供面板所需的各種對話框
- 實現時間設定Modal功能
"""

import re
from typing import Any

import discord

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
                    "❌ 無法獲取伺服器資訊", ephemeral=True
                )
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "❌ 找不到指定的頻道", ephemeral=True
                )
                return

            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "❌ 指定的頻道不是文字頻道", ephemeral=True
                )
                return

            # 更新設定
            await self.db.set_report_channel(guild.id, channel_id)

            # 回應
            await interaction.response.send_message(
                f"✅ 已設定排行榜頻道為 {channel.mention}", ephemeral=True
            )

            # 重新整理面板
            if self.view and hasattr(self.view, "refresh"):
                await self.view.refresh(interaction)

        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的頻道 ID", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ 設定失敗:{e}", ephemeral=True)


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
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except:
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
                f"✅ 公告時間已設定為 {time_str}", ephemeral=True
            )

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ {e!s},請使用 HH:MM 格式", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 設定失敗:{e!s}", ephemeral=True
            )
