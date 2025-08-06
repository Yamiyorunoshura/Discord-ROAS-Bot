"""
按鈕組件模組
- 提供各種按鈕組件
"""

import discord
from discord.ui import Button, ChannelSelect, Modal, Select, TextInput


class SmartBatchConfigButton(Button):
    """智能批量配置按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.primary, label="智能批量設定", emoji="🧠", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """智能批量配置回調"""
        try:
            # 獲取批量統計
            processor = getattr(self.cog, "processor", None)
            if not processor:
                await interaction.response.send_message(
                    "❌ 處理器未初始化", ephemeral=True
                )
                return

            stats = processor.get_batch_stats()

            embed = discord.Embed(
                title="🧠 智能批量處理統計",
                description="當前批量處理系統的運行狀態",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="📊 當前狀態",
                value=(
                    f"批量大小:{stats['current_batch_size']}\n"
                    f"待處理訊息:{stats['pending_messages']}\n"
                    f"性能記錄:{stats['performance_records']}\n"
                    f"追蹤頻道:{stats['channel_activity_tracked']}"
                ),
                inline=True,
            )

            # 獲取頻道活躍度範例
            if hasattr(processor, "batch_processor"):
                bp = processor.batch_processor
                embed.add_field(
                    name="⚙️ 系統參數",
                    value=(
                        f"最小批量:{bp.min_batch_size}\n"
                        f"最大批量:{bp.max_batch_size}\n"
                        f"歷史記錄:{len(bp.performance_history)}\n"
                        f"活躍追蹤:{len(bp.channel_activity)}"
                    ),
                    inline=True,
                )

            embed.add_field(
                name="💡 智能特性",
                value=(
                    "✅ 內容長度動態調整\n"
                    "✅ 附件數量智能識別\n"
                    "✅ 頻道活躍度分析\n"
                    "✅ 歷史性能學習"
                ),
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 獲取統計失敗:{e!s}", ephemeral=True
            )


class RenderQualityButton(Button):
    """渲染品質設定按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="渲染品質", emoji="🎨", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """渲染品質設定回調"""
        modal = RenderQualityModal(self.cog)
        await interaction.response.send_modal(modal)


class FontSettingsButton(Button):
    """字體設定按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="字體設定", emoji="🔤", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """字體設定回調"""
        modal = FontSettingsModal(self.cog)
        await interaction.response.send_modal(modal)


class ColorThemeButton(Button):
    """顏色主題按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="顏色主題", emoji="🌈", row=1
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """顏色主題回調"""
        view = ColorThemeView(self.cog)
        embed = discord.Embed(
            title="🌈 顏色主題選擇",
            description="選擇您喜歡的訊息渲染主題",
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RenderPreviewButton(Button):
    """渲染預覽按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.success, label="渲染預覽", emoji="👁️", row=1
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """渲染預覽回調"""
        # 創建預覽選擇視圖
        view = PreviewSelectView(self.cog)

        embed = discord.Embed(
            title="🎨 渲染預覽選項",
            description="請選擇預覽類型",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🎨 完整預覽", value="生成完整的訊息渲染預覽圖片", inline=False
        )

        embed.add_field(
            name="⚡ 快速預覽", value="快速文字預覽,查看基本效果", inline=False
        )

        embed.add_field(name="⚙️ 預覽設定", value="配置預覽品質和選項", inline=False)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _get_render_config(self) -> dict[str, str]:
        """獲取渲染配置資訊"""
        try:
            # 從配置獲取渲染設定
            config = getattr(self.cog, "config", {})

            return {
                "image_settings": f"品質: {config.get('image_quality', 'high')}, 格式: {config.get('image_format', 'PNG')}",
                "font_settings": f"字體: {config.get('font_family', 'Noto Sans CJK')}, 大小: {config.get('font_size', 14)}px",
                "color_theme": config.get("color_theme", "Discord 預設"),
            }
        except Exception:
            return {
                "image_settings": "預設設定",
                "font_settings": "預設字體",
                "color_theme": "Discord 預設",
            }


# 模態框組件


class RenderQualityModal(Modal):
    """渲染品質設定模態框"""

    def __init__(self, cog):
        super().__init__(title="🎨 渲染品質設定")
        self.cog = cog

        # 圖片品質設定
        self.image_quality = TextInput(
            label="圖片品質 (low/medium/high)",
            placeholder="輸入: low, medium, 或 high",
            default="high",
            max_length=10,
        )
        self.add_item(self.image_quality)

        # 圖片格式設定
        self.image_format = TextInput(
            label="圖片格式 (PNG/JPEG)",
            placeholder="輸入: PNG 或 JPEG",
            default="PNG",
            max_length=10,
        )
        self.add_item(self.image_format)

        # 圖片尺寸設定
        self.image_size = TextInput(
            label="圖片寬度 (像素)",
            placeholder="輸入: 800-1200",
            default="1000",
            max_length=10,
        )
        self.add_item(self.image_size)

    async def on_submit(self, interaction: discord.Interaction):
        """提交設定"""
        try:
            # 驗證輸入
            quality = self.image_quality.value.lower()
            if quality not in ["low", "medium", "high"]:
                await interaction.response.send_message(
                    "❌ 品質設定無效,請輸入 low、medium 或 high", ephemeral=True
                )
                return

            format_type = self.image_format.value.upper()
            if format_type not in ["PNG", "JPEG"]:
                await interaction.response.send_message(
                    "❌ 格式設定無效,請輸入 PNG 或 JPEG", ephemeral=True
                )
                return

            try:
                size = int(self.image_size.value)
                MIN_IMAGE_SIZE = 800
                MAX_IMAGE_SIZE = 1200
                if size < MIN_IMAGE_SIZE or size > MAX_IMAGE_SIZE:
                    await interaction.response.send_message(
                        f"❌ 尺寸設定無效,請輸入 {MIN_IMAGE_SIZE}-{MAX_IMAGE_SIZE} 之間的數值",
                        ephemeral=True,
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ 尺寸必須是數字", ephemeral=True
                )
                return

            config = {
                "image_quality": quality,
                "image_format": format_type,
                "image_width": size,
            }

            # 更新配置
            if hasattr(self.cog, "config"):
                self.cog.config.update(config)

            embed = discord.Embed(
                title="✅ 渲染品質設定已更新",
                description="新的設定已套用",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="🎨 設定內容",
                value=(
                    f"圖片品質:{quality}\n圖片格式:{format_type}\n圖片寬度:{size}px"
                ),
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 設定失敗:{e!s}", ephemeral=True
            )


class FontSettingsModal(Modal):
    """字體設定模態框"""

    def __init__(self, cog):
        super().__init__(title="🔤 字體設定")
        self.cog = cog

        # 字體家族
        self.font_family = TextInput(
            label="字體家族",
            placeholder="例如: Noto Sans CJK, Arial, 微軟正黑體",
            default="Noto Sans CJK",
            max_length=50,
        )
        self.add_item(self.font_family)

        # 字體大小
        self.font_size = TextInput(
            label="字體大小 (像素)",
            placeholder="輸入: 12-24",
            default="14",
            max_length=5,
        )
        self.add_item(self.font_size)

        # 行高
        self.line_height = TextInput(
            label="行高倍數", placeholder="輸入: 1.2-2.0", default="1.4", max_length=5
        )
        self.add_item(self.line_height)

    async def on_submit(self, interaction: discord.Interaction):
        """提交字體設定"""
        try:
            # 驗證字體大小
            try:
                size = int(self.font_size.value)
                MIN_FONT_SIZE = 12
                MAX_FONT_SIZE = 24
                if size < MIN_FONT_SIZE or size > MAX_FONT_SIZE:
                    await interaction.response.send_message(
                        f"❌ 字體大小無效,請輸入 {MIN_FONT_SIZE}-{MAX_FONT_SIZE} 之間的數值",
                        ephemeral=True,
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ 字體大小必須是數字", ephemeral=True
                )
                return

            # 驗證行高
            try:
                line_height = float(self.line_height.value)
                MIN_LINE_HEIGHT = 1.2
                MAX_LINE_HEIGHT = 2.0
                if line_height < MIN_LINE_HEIGHT or line_height > MAX_LINE_HEIGHT:
                    await interaction.response.send_message(
                        f"❌ 行高無效,請輸入 {MIN_LINE_HEIGHT}-{MAX_LINE_HEIGHT} 之間的數值",
                        ephemeral=True,
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ 行高必須是數字", ephemeral=True
                )
                return

            # 儲存設定
            config = {
                "font_family": self.font_family.value,
                "font_size": size,
                "line_height": line_height,
            }

            # 更新配置
            if hasattr(self.cog, "config"):
                self.cog.config.update(config)

            embed = discord.Embed(
                title="✅ 字體設定已更新",
                description="新的字體設定已套用",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="🔤 設定內容",
                value=(
                    f"字體家族:{self.font_family.value}\n"
                    f"字體大小:{size}px\n"
                    f"行高倍數:{line_height}"
                ),
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 設定失敗:{e!s}", ephemeral=True
            )


class ColorThemeView(discord.ui.View):
    """顏色主題視圖"""

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
        self.add_item(ColorThemeSelect(cog))


class ColorThemeSelect(Select):
    """顏色主題選擇器"""

    def __init__(self, cog):
        self.cog = cog

        options = [
            discord.SelectOption(
                label="Discord 預設",
                description="使用 Discord 官方預設顏色",
                emoji="🎮",
                value="discord_default",
            ),
            discord.SelectOption(
                label="明亮主題",
                description="明亮清爽的顏色搭配",
                emoji="☀️",
                value="light_theme",
            ),
            discord.SelectOption(
                label="高對比主題",
                description="高對比度,適合視覺輔助",
                emoji="🔍",
                value="high_contrast",
            ),
            discord.SelectOption(
                label="護眼主題",
                description="柔和的護眼色調",
                emoji="👁️",
                value="eye_care",
            ),
            discord.SelectOption(
                label="彩虹主題",
                description="豐富多彩的顏色組合",
                emoji="🌈",
                value="rainbow",
            ),
        ]

        super().__init__(
            placeholder="選擇顏色主題...", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """主題選擇回調"""
        try:
            selected_theme = self.values[0]

            # 主題配置
            theme_configs = {
                "discord_default": {
                    "name": "Discord 預設",
                    "background": "#36393f",
                    "message_bg": "#40444b",
                    "text_color": "#dcddde",
                    "accent": "#7289da",
                },
                "light_theme": {
                    "name": "明亮主題",
                    "background": "#ffffff",
                    "message_bg": "#f6f6f6",
                    "text_color": "#2c2f33",
                    "accent": "#5865f2",
                },
                "high_contrast": {
                    "name": "高對比主題",
                    "background": "#000000",
                    "message_bg": "#1a1a1a",
                    "text_color": "#ffffff",
                    "accent": "#ffff00",
                },
                "eye_care": {
                    "name": "護眼主題",
                    "background": "#1e2124",
                    "message_bg": "#2f3136",
                    "text_color": "#b9bbbe",
                    "accent": "#99aab5",
                },
                "rainbow": {
                    "name": "彩虹主題",
                    "background": "#2c2f33",
                    "message_bg": "#23272a",
                    "text_color": "#ffffff",
                    "accent": "#ff6b6b",
                },
            }

            theme_config = theme_configs.get(
                selected_theme, theme_configs["discord_default"]
            )

            # 更新配置
            if hasattr(self.cog, "config"):
                self.cog.config.update({
                    "color_theme": selected_theme,
                    "theme_config": theme_config,
                })

            embed = discord.Embed(
                title="✅ 顏色主題已更新",
                description=f"已套用「{theme_config['name']}」主題",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="🎨 主題配置",
                value=(
                    f"背景色:{theme_config['background']}\n"
                    f"訊息背景:{theme_config['message_bg']}\n"
                    f"文字顏色:{theme_config['text_color']}\n"
                    f"強調色:{theme_config['accent']}"
                ),
                inline=False,
            )

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 主題設定失敗:{e!s}", ephemeral=True
            )


class HelpButton(Button):
    """幫助按鈕"""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="幫助", emoji="❓", row=2
        )

    async def callback(self, interaction: discord.Interaction):
        """幫助回調"""
        embed = discord.Embed(
            title="❓ 訊息監聽器幫助",
            description="以下是各項功能的說明",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🧠 智能批量設定",
            value="查看和配置智能批量處理系統的運行狀態",
            inline=False,
        )

        embed.add_field(
            name="🎨 渲染品質", value="設定圖片品質、格式和尺寸", inline=False
        )

        embed.add_field(
            name="🔤 字體設定", value="調整字體家族、大小和行高", inline=False
        )

        embed.add_field(
            name="🌈 顏色主題", value="選擇不同的顏色主題風格", inline=False
        )

        embed.add_field(name="👁️ 渲染預覽", value="預覽當前設定的渲染效果", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class AdjustBatchSize(Button):
    """調整批量大小按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="調整批量大小", emoji="📊", row=2
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """調整批量大小回調"""
        embed = discord.Embed(
            title="📊 批量大小調整",
            description="批量大小調整功能正在開發中",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AdjustBatchTime(Button):
    """調整批量時間按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="調整批量時間", emoji="⏰", row=2
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """調整批量時間回調"""
        embed = discord.Embed(
            title="⏰ 批量時間調整",
            description="批量時間調整功能正在開發中",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class LogChannelSelect(ChannelSelect):
    """日誌頻道選擇器"""

    def __init__(self, cog):
        super().__init__(
            placeholder="選擇日誌頻道...", channel_types=[discord.ChannelType.text]
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """日誌頻道選擇回調"""
        selected_channel = self.values[0]
        await interaction.response.send_message(
            f"已選擇日誌頻道:{selected_channel.mention}", ephemeral=True
        )


class MonitoredChannelsSelect(ChannelSelect):
    """監控頻道選擇器"""

    def __init__(self, cog):
        super().__init__(
            placeholder="選擇要監控的頻道...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=10,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """監控頻道選擇回調"""
        selected_channels = self.values
        channel_names = [channel.mention for channel in selected_channels]
        await interaction.response.send_message(
            f"已選擇監控頻道:{', '.join(channel_names)}", ephemeral=True
        )


class ToggleEdits(Button):
    """切換編輯監控按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="編輯監控", emoji="✏️", row=3
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """切換編輯監控回調"""
        # 這裡可以添加實際的切換邏輯
        current_state = getattr(self.cog, "monitor_edits", True)
        new_state = not current_state

        if hasattr(self.cog, "monitor_edits"):
            self.cog.monitor_edits = new_state

        embed = discord.Embed(
            title="✏️ 編輯監控設定",
            description=f"編輯監控已{'啟用' if new_state else '停用'}",
            color=discord.Color.green() if new_state else discord.Color.red(),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # 更新按鈕樣式
        self.style = (
            discord.ButtonStyle.success if new_state else discord.ButtonStyle.secondary
        )
        self.label = f"編輯監控 ({'開' if new_state else '關'})"

        # 刷新視圖
        if hasattr(self.view, "refresh"):
            await self.view.refresh(interaction)


class ToggleDeletes(Button):
    """切換刪除監控按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="刪除監控", emoji="🗑️", row=3
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """切換刪除監控回調"""
        # 這裡可以添加實際的切換邏輯
        current_state = getattr(self.cog, "monitor_deletes", True)
        new_state = not current_state

        if hasattr(self.cog, "monitor_deletes"):
            self.cog.monitor_deletes = new_state

        embed = discord.Embed(
            title="🗑️ 刪除監控設定",
            description=f"刪除監控已{'啟用' if new_state else '停用'}",
            color=discord.Color.green() if new_state else discord.Color.red(),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # 更新按鈕樣式
        self.style = (
            discord.ButtonStyle.success if new_state else discord.ButtonStyle.secondary
        )
        self.label = f"刪除監控 ({'開' if new_state else '關'})"

        # 刷新視圖
        if hasattr(self.view, "refresh"):
            await self.view.refresh(interaction)


class CloseButton(Button):
    """關閉按鈕"""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger, label="關閉", emoji="❌", row=4
        )

    async def callback(self, interaction: discord.Interaction):
        """關閉回調"""
        embed = discord.Embed(
            title="👋 面板已關閉",
            description="感謝使用訊息監聽器設定面板!",
            color=discord.Color.green(),
        )

        # 刪除視圖
        if hasattr(self.view, "delete"):
            await self.view.delete(interaction)
        else:
            await interaction.response.edit_message(embed=embed, view=None)


class PageButton(Button):
    """翻頁按鈕"""

    def __init__(self, view, direction: int, label: str, disabled: bool = False):
        super().__init__(
            style=discord.ButtonStyle.secondary, label=label, disabled=disabled, row=4
        )
        self.view_parent = view
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        """翻頁回調"""
        await self.view_parent.update(interaction)


# 預覽功能組件


class PreviewSelectView(discord.ui.View):
    """預覽選擇視圖"""

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog

        # 添加預覽按鈕
        self.add_item(FullPreviewButton(cog))
        self.add_item(QuickPreviewButton(cog))
        self.add_item(PreviewSettingsButton(cog))
        self.add_item(ClosePreviewButton())


class FullPreviewButton(Button):
    """完整預覽按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.primary, label="完整預覽", emoji="🎨", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """完整預覽回調"""
        # 創建簡化的預覽模態框
        modal = SimplePreviewModal(self.cog, "完整預覽")
        await interaction.response.send_modal(modal)


class QuickPreviewButton(Button):
    """快速預覽按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="快速預覽", emoji="⚡", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """快速預覽回調"""
        # 創建簡化的快速預覽
        embed = discord.Embed(
            title="⚡ 快速預覽",
            description="這是一個快速預覽示例",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📝 預覽內容",
            value="```\n這是一個測試訊息,用來展示渲染效果!\n```",
            inline=False,
        )

        embed.add_field(
            name="🎨 渲染效果描述",
            value=(
                "• 文字長度:25 字元\n"
                "• 預估寬度:200px\n"
                "• 預估高度:60px\n"
                "• 顏色主題:Discord 預設"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class PreviewSettingsButton(Button):
    """預覽設定按鈕"""

    def __init__(self, cog):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="預覽設定", emoji="⚙️", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """預覽設定回調"""
        # 創建簡化的設定模態框
        modal = SimplePreviewModal(self.cog, "預覽設定")
        await interaction.response.send_modal(modal)


class ClosePreviewButton(Button):
    """關閉預覽按鈕"""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="關閉", emoji="❌", row=1
        )

    async def callback(self, interaction: discord.Interaction):
        """關閉預覽回調"""
        embed = discord.Embed(
            title="👋 預覽面板已關閉",
            description="感謝使用預覽功能!",
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(embed=embed, view=None)


class SimplePreviewModal(Modal):
    """簡化的預覽模態框"""

    def __init__(self, cog, title: str):
        super().__init__(title=f"🎨 {title}")
        self.cog = cog

        # 預覽文字輸入
        self.preview_text = TextInput(
            label="預覽文字",
            placeholder="輸入要預覽的訊息內容...",
            default="這是一個預覽訊息!",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=500,
        )
        self.add_item(self.preview_text)

        # 用戶名稱輸入
        self.username = TextInput(
            label="用戶名稱",
            placeholder="輸入用戶名稱",
            default="測試用戶",
            min_length=1,
            max_length=32,
        )
        self.add_item(self.username)

    async def on_submit(self, interaction: discord.Interaction):
        """提交預覽請求"""
        try:
            embed = discord.Embed(
                title="✅ 預覽生成完成",
                description="以下是您的預覽效果",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="📝 預覽內容",
                value=f"```\n{self.preview_text.value}\n```",
                inline=False,
            )

            embed.add_field(
                name="👤 用戶資訊",
                value=f"用戶名稱:{self.username.value}",
                inline=False,
            )

            embed.add_field(
                name="🎨 渲染資訊",
                value=(
                    f"內容長度:{len(self.preview_text.value)} 字元\n"
                    f"預估寬度:{len(self.preview_text.value) * 8}px\n"
                    f"預估高度:60px"
                ),
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 預覽失敗:{e!s}", ephemeral=True
            )
