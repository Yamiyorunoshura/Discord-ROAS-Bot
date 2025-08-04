"""
模態框組件模組
- 提供各種模態框組件
"""

import discord
from discord.ui import Modal, TextInput

from ..embeds.settings_embed import settings_embed


class BatchSizeModal(Modal):
    """批次大小設定模態框"""

    def __init__(self, cog, current_size: str = "10"):
        super().__init__(title="設定批次大小")
        self.cog = cog

        # 添加文字輸入框
        self.batch_size = TextInput(
            label="批次大小(訊息數量)",
            placeholder="輸入 1-50 之間的數字",
            default=current_size,
            min_length=1,
            max_length=2,
            required=True,
            custom_id="batch_size_input",
        )
        self.add_item(self.batch_size)

    async def on_submit(self, interaction: discord.Interaction):
        """提交回調"""
        try:
            # 獲取輸入值
            size_str = self.batch_size.value

            # 驗證輸入
            try:
                size = int(size_str)
                MIN_BATCH_SIZE = 1
                MAX_BATCH_SIZE = 50
                if size < MIN_BATCH_SIZE or size > MAX_BATCH_SIZE:
                    raise ValueError(f"批次大小必須在 {MIN_BATCH_SIZE}-{MAX_BATCH_SIZE} 之間")
            except ValueError as exc:
                await interaction.response.send_message(
                    f"❌ 無效的批次大小: {exc}", ephemeral=True
                )
                return

            # 更新設定
            await self.cog.set_setting("batch_size", str(size))

            # 回應並發送確認訊息
            await interaction.response.defer()
            await interaction.followup.send(
                f"✅ 批次大小已設定為 {size} 條訊息", ephemeral=True
            )

            # 嘗試重新載入設定面板
            try:
                # 獲取原始訊息
                original_message = await interaction.original_response()

                # 重新載入設定
                await self.cog.refresh_settings()

                # 創建新的嵌入訊息

                embed = await settings_embed(self.cog)

                # 更新訊息
                await original_message.edit(embed=embed)
            except Exception:
                pass
        except Exception as exc:
            await interaction.response.send_message(
                f"❌ 設定批次大小失敗: {exc}", ephemeral=True
            )

class BatchTimeModal(Modal):
    """批次時間設定模態框"""

    def __init__(self, cog, current_time: str = "600"):
        super().__init__(title="設定批次時間")
        self.cog = cog

        # 轉換為分鐘
        try:
            minutes = int(int(current_time) / 60)
        except Exception:
            minutes = 10

        # 添加文字輸入框
        self.batch_time = TextInput(
            label="批次時間(分鐘)",
            placeholder="輸入 1-60 之間的數字",
            default=str(minutes),
            min_length=1,
            max_length=2,
            required=True,
            custom_id="batch_time_input",
        )
        self.add_item(self.batch_time)

    async def on_submit(self, interaction: discord.Interaction):
        """提交回調"""
        try:
            # 獲取輸入值
            time_str = self.batch_time.value

            # 驗證輸入
            try:
                minutes = int(time_str)
                MIN_BATCH_TIME = 1
                MAX_BATCH_TIME = 60
                if minutes < MIN_BATCH_TIME or minutes > MAX_BATCH_TIME:
                    raise ValueError(f"批次時間必須在 {MIN_BATCH_TIME}-{MAX_BATCH_TIME} 分鐘之間")

                # 轉換為秒
                seconds = minutes * 60
            except ValueError as exc:
                await interaction.response.send_message(
                    f"❌ 無效的批次時間: {exc}", ephemeral=True
                )
                return

            # 更新設定
            await self.cog.set_setting("batch_time", str(seconds))

            # 直接回應,不嘗試更新視圖
            await interaction.response.defer()

            # 發送確認訊息
            await interaction.followup.send(
                f"✅ 批次時間已設定為 {minutes} 分鐘", ephemeral=True
            )

            # 嘗試重新載入設定面板
            try:
                # 獲取原始訊息
                original_message = await interaction.original_response()

                # 重新載入設定
                await self.cog.refresh_settings()

                # 創建新的嵌入訊息

                embed = await settings_embed(self.cog)

                # 更新訊息
                await original_message.edit(embed=embed)
            except Exception:
                pass
        except Exception as exc:
            await interaction.response.send_message(
                f"❌ 設定批次時間失敗: {exc}", ephemeral=True
            )
