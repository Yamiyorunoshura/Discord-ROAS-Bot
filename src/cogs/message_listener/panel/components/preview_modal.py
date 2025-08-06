"""
訊息監聽渲染預覽對話框
- 預覽輸入功能
- 即時渲染預覽
- 設定測試
"""

import builtins
import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from ...main.main import MessageListenerCog

logger = logging.getLogger("message_listener")

# 常數定義
PREVIEW_TEXT_MAX_LENGTH = 100


class RenderPreviewModal(ui.Modal):
    """渲染預覽對話框"""

    def __init__(self, cog: "MessageListenerCog"):
        super().__init__(title="🎨 渲染預覽")
        self.cog = cog

        # 預覽文字輸入
        self.preview_text = ui.TextInput(
            label="預覽文字",
            placeholder="輸入要預覽的訊息內容...",
            default="這是一個預覽訊息,用來測試渲染效果!",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=2000,
        )
        self.add_item(self.preview_text)

        # 用戶名稱輸入
        self.username = ui.TextInput(
            label="用戶名稱",
            placeholder="輸入用戶名稱",
            default="測試用戶",
            min_length=1,
            max_length=32,
        )
        self.add_item(self.username)

        # 頭像 URL 輸入
        self.avatar_url = ui.TextInput(
            label="頭像 URL (可選)",
            placeholder="輸入頭像 URL,留空使用預設頭像",
            default="",
            required=False,
            min_length=0,
            max_length=500,
        )
        self.add_item(self.avatar_url)

        # 渲染選項
        self.render_options = ui.TextInput(
            label="渲染選項",
            placeholder="輸入: high (高品質), medium (中品質), low (低品質)",
            default="high",
            min_length=3,
            max_length=10,
        )
        self.add_item(self.render_options)

    async def on_submit(self, interaction: discord.Interaction):
        """提交預覽請求"""
        try:
            # 延遲回應以避免超時
            await interaction.response.defer(ephemeral=True)

            # 驗證渲染選項
            quality = self.render_options.value.lower()
            if quality not in ["high", "medium", "low"]:
                await interaction.followup.send(
                    "❌ 渲染選項無效,請輸入 high、medium 或 low", ephemeral=True
                )
                return

            # 處理頭像 URL
            avatar_url = self.avatar_url.value.strip()
            if not avatar_url:
                # 使用預設頭像
                avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

            # 建立預覽訊息物件
            preview_message = {
                "content": self.preview_text.value,
                "author": {
                    "name": self.username.value,
                    "avatar_url": avatar_url,
                    "display_name": self.username.value,
                },
                "timestamp": discord.utils.utcnow(),
                "channel_id": interaction.channel.id if interaction.channel else 0,
                "guild_id": interaction.guild.id if interaction.guild else 0,
            }

            # 發送處理中訊息
            processing_embed = discord.Embed(
                title="🎨 正在生成預覽...",
                description="請稍候,正在渲染您的訊息預覽",
                color=discord.Color.blue(),
            )
            processing_embed.add_field(
                name="📝 預覽內容",
                value=f"```\n{self.preview_text.value[:PREVIEW_TEXT_MAX_LENGTH]}{'...' if len(self.preview_text.value) > PREVIEW_TEXT_MAX_LENGTH else ''}\n```",
                inline=False,
            )
            processing_embed.add_field(
                name="⚙️ 渲染設定",
                value=f"品質:{quality.upper()}\n用戶:{self.username.value}",
                inline=False,
            )

            await interaction.followup.send(embed=processing_embed, ephemeral=True)

            # 執行渲染
            try:
                rendered_image = await self._render_preview(preview_message, quality)

                if rendered_image:
                    # 成功渲染
                    success_embed = discord.Embed(
                        title="✅ 渲染預覽完成",
                        description="以下是您的訊息渲染預覽",
                        color=discord.Color.green(),
                    )

                    success_embed.add_field(
                        name="📊 渲染資訊",
                        value=(
                            f"品質:{quality.upper()}\n"
                            f"用戶:{self.username.value}\n"
                            f"內容長度:{len(self.preview_text.value)} 字元"
                        ),
                        inline=False,
                    )

                    # 發送圖片
                    file = discord.File(rendered_image, filename="preview.png")
                    success_embed.set_image(url="attachment://preview.png")

                    await interaction.followup.send(
                        embed=success_embed, file=file, ephemeral=True
                    )

                else:
                    # 渲染失敗
                    await interaction.followup.send(
                        "❌ 渲染失敗,請檢查設定後重試", ephemeral=True
                    )

            except Exception as render_error:
                logger.error(f"渲染預覽失敗: {render_error}")
                await interaction.followup.send(
                    f"❌ 渲染過程中發生錯誤:{render_error!s}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"預覽模態框提交失敗: {e}")
            with contextlib.suppress(builtins.BaseException):
                await interaction.followup.send(f"❌ 預覽失敗:{e!s}", ephemeral=True)

    async def _render_preview(self, message_data: dict, quality: str) -> str | None:
        """執行實際的渲染預覽"""
        try:
            # 獲取渲染器
            if not hasattr(self.cog, "renderer"):
                logger.error("找不到渲染器")
                return None

            renderer = self.cog.renderer

            # 設定渲染品質
            quality_settings = {
                "high": {"width": 800, "height": 600, "dpi": 150},
                "medium": {"width": 600, "height": 450, "dpi": 100},
                "low": {"width": 400, "height": 300, "dpi": 75},
            }

            settings = quality_settings.get(quality, quality_settings["medium"])

            # 模擬訊息物件
            class MockMessage:
                def __init__(self, data):
                    self.content = data["content"]
                    self.author = MockUser(data["author"])
                    self.created_at = data["timestamp"]
                    self.channel = MockChannel(data["channel_id"])
                    self.guild = MockGuild(data["guild_id"])

            class MockUser:
                def __init__(self, data):
                    self.name = data["name"]
                    self.display_name = data["display_name"]
                    self.avatar = MockAsset(data["avatar_url"])
                    self.status = discord.Status.online

            class MockAsset:
                def __init__(self, url):
                    self.url = url

                async def read(self):
                    # 這裡應該實際下載頭像
                    return b""

            class MockChannel:
                def __init__(self, channel_id):
                    self.id = channel_id
                    self.name = "preview-channel"

            class MockGuild:
                def __init__(self, guild_id):
                    self.id = guild_id
                    self.name = "Preview Guild"

            # 建立模擬訊息
            mock_message = MockMessage(message_data)

            # 執行渲染
            rendered_path = await renderer.render_message(
                mock_message,
                width=settings["width"],
                height=settings["height"],
                dpi=settings["dpi"],
            )

            return rendered_path

        except Exception as e:
            logger.error(f"渲染預覽執行失敗: {e}")
            return None


class QuickPreviewModal(ui.Modal):
    """快速預覽對話框"""

    def __init__(self, cog: "MessageListenerCog"):
        super().__init__(title="⚡ 快速預覽")
        self.cog = cog

        # 快速預覽文字
        self.quick_text = ui.TextInput(
            label="快速預覽",
            placeholder="輸入簡短文字進行快速預覽...",
            default="Hello World! 🌍",
            min_length=1,
            max_length=100,
        )
        self.add_item(self.quick_text)

    async def on_submit(self, interaction: discord.Interaction):
        """提交快速預覽"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 建立快速預覽
            embed = discord.Embed(
                title="⚡ 快速預覽",
                description="以下是您的快速預覽效果",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="📝 預覽內容",
                value=f"```\n{self.quick_text.value}\n```",
                inline=False,
            )

            embed.add_field(
                name="💡 提示",
                value="這是簡化版預覽, 完整預覽請使用「渲染預覽」功能",
                inline=False,
            )

            # 模擬渲染效果的文字描述
            embed.add_field(
                name="🎨 渲染效果描述",
                value=(
                    f"• 文字長度:{len(self.quick_text.value)} 字元\n"
                    f"• 預估寬度:{len(self.quick_text.value) * 8}px\n"
                    f"• 預估高度:60px\n"
                    f"• 顏色主題:Discord 預設"
                ),
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"快速預覽失敗: {e}")
            await interaction.followup.send(f"❌ 快速預覽失敗:{e!s}", ephemeral=True)


class PreviewSettingsModal(ui.Modal):
    """預覽設定對話框"""

    def __init__(self, cog: "MessageListenerCog"):
        super().__init__(title="⚙️ 預覽設定")
        self.cog = cog

        # 預設品質設定
        self.default_quality = ui.TextInput(
            label="預設品質",
            placeholder="輸入: high, medium, low",
            default="high",
            min_length=3,
            max_length=10,
        )
        self.add_item(self.default_quality)

        # 預覽尺寸設定
        self.preview_size = ui.TextInput(
            label="預覽尺寸",
            placeholder="輸入: large (800x600), medium (600x450), small (400x300)",
            default="large",
            min_length=4,
            max_length=10,
        )
        self.add_item(self.preview_size)

        # 快取設定
        self.cache_enabled = ui.TextInput(
            label="啟用快取",
            placeholder="輸入: true (啟用), false (停用)",
            default="true",
            min_length=4,
            max_length=5,
        )
        self.add_item(self.cache_enabled)

    async def on_submit(self, interaction: discord.Interaction):
        """提交預覽設定"""
        try:
            # 驗證品質設定
            quality = self.default_quality.value.lower()
            if quality not in ["high", "medium", "low"]:
                await interaction.response.send_message(
                    "❌ 品質設定無效,請輸入 high、medium 或 low", ephemeral=True
                )
                return

            # 驗證尺寸設定
            size = self.preview_size.value.lower()
            if size not in ["large", "medium", "small"]:
                await interaction.response.send_message(
                    "❌ 尺寸設定無效,請輸入 large、medium 或 small", ephemeral=True
                )
                return

            # 驗證快取設定
            cache = self.cache_enabled.value.lower()
            if cache not in ["true", "false"]:
                await interaction.response.send_message(
                    "❌ 快取設定無效,請輸入 true 或 false", ephemeral=True
                )
                return

            # 儲存設定
            preview_settings = {
                "default_quality": quality,
                "preview_size": size,
                "cache_enabled": cache == "true",
                "updated_at": discord.utils.utcnow().isoformat(),
            }

            # 更新 cog 配置
            if hasattr(self.cog, "preview_config"):
                self.cog.preview_config.update(preview_settings)
            else:
                self.cog.preview_config = preview_settings

            # 建立確認嵌入
            embed = discord.Embed(
                title="✅ 預覽設定已更新",
                description="新的預覽設定已套用",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="⚙️ 設定內容",
                value=(
                    f"預設品質:{quality.upper()}\n"
                    f"預覽尺寸:{size.upper()}\n"
                    f"快取狀態:{'啟用' if cache == 'true' else '停用'}"
                ),
                inline=False,
            )

            embed.add_field(
                name="💡 提示", value="設定將在下次預覽時生效", inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"預覽設定失敗: {e}")
            await interaction.response.send_message(
                f"❌ 設定失敗:{e!s}", ephemeral=True
            )
