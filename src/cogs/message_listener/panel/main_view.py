"""
訊息監聽系統面板視圖模組
- 提供設定面板
- 提供搜尋結果分頁視圖
- 智能批量調整界面
- 渲染設定功能
"""

from typing import Any

import discord
from discord.ui import View

from ..config.config import is_allowed
from .components.buttons import (
    AdjustBatchSize,
    AdjustBatchTime,
    CloseButton,
    ColorThemeButton,
    FontSettingsButton,
    HelpButton,
    LogChannelSelect,
    MonitoredChannelsSelect,
    PageButton,
    RenderPreviewButton,
    RenderQualityButton,
    # 新增的按鈕組件
    SmartBatchConfigButton,
    ToggleDeletes,
    ToggleEdits,
)
from .embeds import settings_embed


class EnhancedSettingsView(View):
    """
    增強版訊息監聽系統設定面板視圖

    功能:
    - 設定日誌頻道
    - 設定監聽頻道
    - 設定批次處理參數
    - 開關編輯/刪除記錄
    - 智能批量調整
    - 渲染品質設定
    - 字體和顏色主題
    """

    def __init__(self, cog):
        """
        初始化增強版設定面板視圖

        Args:
            cog: MessageListenerCog 實例
        """
        super().__init__(timeout=600)  # 10分鐘超時
        self.cog = cog
        self.message = None
        self.current_page = "main"  # main, smart_batch, render_settings

        # 設置初始組件
        self._setup_main_components()

    def _setup_main_components(self):
        """設置主要組件"""
        self.clear_items()

        # 第一行:智能功能
        self.add_item(SmartBatchConfigButton(self.cog))
        self.add_item(RenderQualityButton(self.cog))
        self.add_item(FontSettingsButton(self.cog))

        # 第二行:視覺設定
        self.add_item(ColorThemeButton(self.cog))
        self.add_item(RenderPreviewButton(self.cog))
        self.add_item(HelpButton())

        # 第三行:傳統設定
        self.add_item(LogChannelSelect(self.cog))
        self.add_item(MonitoredChannelsSelect(self.cog))

        # 第四行:批次設定
        self.add_item(AdjustBatchSize(self.cog))
        self.add_item(AdjustBatchTime(self.cog))

        # 第五行:開關和控制
        self.add_item(ToggleEdits(self.cog))
        self.add_item(ToggleDeletes(self.cog))
        self.add_item(CloseButton())

    async def on_timeout(self):
        """視圖超時處理"""
        try:
            # 禁用所有按鈕
            for item in self.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

            # 更新訊息
            if self.message:
                timeout_embed = discord.Embed(
                    title="⏰ 面板已超時",
                    description="面板已自動關閉,請重新開啟設定面板.",
                    color=discord.Color.orange(),
                )
                await self.message.edit(embed=timeout_embed, view=self)
        except Exception:
            pass

    async def refresh(self, interaction: discord.Interaction | None = None):
        """
        重新整理視圖

        Args:
            interaction: Discord 互動
        """
        try:
            # 更新嵌入訊息
            embed = await self._build_current_embed()

            # 更新訊息
            if interaction:
                await interaction.response.edit_message(embed=embed, view=self)
            elif self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            # 錯誤處理
            error_embed = discord.Embed(
                title="❌ 刷新失敗",
                description=f"無法刷新面板:{e!s}",
                color=discord.Color.red(),
            )

            if interaction:
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )

    async def _build_current_embed(self) -> discord.Embed:
        """構建當前頁面的嵌入"""
        if self.current_page == "main":
            return await self._build_main_embed()
        elif self.current_page == "smart_batch":
            return await self._build_smart_batch_embed()
        elif self.current_page == "render_settings":
            return await self._build_render_settings_embed()
        else:
            return await settings_embed(self.cog)

    async def _build_main_embed(self) -> discord.Embed:
        """構建主要設定嵌入"""
        embed = discord.Embed(
            title="📋 訊息監聽系統 - 增強版設定面板",
            description="全新的智能化訊息監聽系統,提供更強大的功能和更好的用戶體驗",
            color=discord.Color.blue(),
        )

        # 系統狀態
        try:
            processor = getattr(self.cog, "processor", None)
            if processor:
                stats = processor.get_batch_stats()
                embed.add_field(
                    name="🧠 智能批量狀態",
                    value=(
                        f"當前批量:{stats['current_batch_size']}\n"
                        f"待處理:{stats['pending_messages']}\n"
                        f"性能記錄:{stats['performance_records']}"
                    ),
                    inline=True,
                )
        except Exception:
            embed.add_field(
                name="🧠 智能批量狀態", value="系統初始化中...", inline=True
            )

        # 渲染設定狀態
        try:
            config = getattr(self.cog, "config", {})
            embed.add_field(
                name="🎨 渲染設定",
                value=(
                    f"品質:{config.get('image_quality', 'high')}\n"
                    f"格式:{config.get('image_format', 'PNG')}\n"
                    f"主題:{config.get('color_theme', 'Discord 預設')}"
                ),
                inline=True,
            )
        except Exception:
            embed.add_field(name="🎨 渲染設定", value="使用預設設定", inline=True)

        # 功能說明
        embed.add_field(
            name="✨ 新功能特色",
            value=(
                "🧠 **智能批量處理** - 自動調整批量大小\n"
                "🎨 **渲染品質設定** - 自訂圖片品質\n"
                "🔤 **字體設定** - 個性化字體選擇\n"
                "🌈 **顏色主題** - 多種視覺主題\n"
                "👁️ **渲染預覽** - 即時預覽效果"
            ),
            inline=False,
        )

        embed.set_footer(text="點擊上方按鈕來配置各項功能")
        return embed

    async def _build_smart_batch_embed(self) -> discord.Embed:
        """構建智能批量設定嵌入"""
        embed = discord.Embed(
            title="🧠 智能批量處理系統",
            description="基於機器學習的動態批量調整系統",
            color=discord.Color.green(),
        )

        try:
            processor = getattr(self.cog, "processor", None)
            if processor and hasattr(processor, "batch_processor"):
                bp = processor.batch_processor

                # 當前狀態
                embed.add_field(
                    name="📊 當前狀態",
                    value=(
                        f"批量大小:{bp.current_batch_size}\n"
                        f"最小批量:{bp.min_batch_size}\n"
                        f"最大批量:{bp.max_batch_size}\n"
                        f"性能記錄:{len(bp.performance_history)}"
                    ),
                    inline=True,
                )

                # 學習統計
                if bp.performance_history:
                    recent_perf = list(bp.performance_history)[-5:]
                    avg_time = sum(p["processing_time"] for p in recent_perf) / len(
                        recent_perf
                    )
                    avg_success = sum(p["success_rate"] for p in recent_perf) / len(
                        recent_perf
                    )

                    embed.add_field(
                        name="📈 性能統計",
                        value=(
                            f"平均處理時間:{avg_time:.2f}秒\n"
                            f"平均成功率:{avg_success:.1%}\n"
                            f"追蹤頻道:{len(bp.channel_activity)}\n"
                            f"學習樣本:{len(bp.performance_history)}"
                        ),
                        inline=True,
                    )

                # 智能特性
                embed.add_field(
                    name="🤖 智能特性",
                    value=(
                        "✅ 內容長度分析\n"
                        "✅ 附件數量檢測\n"
                        "✅ 頻道活躍度評估\n"
                        "✅ 歷史性能學習\n"
                        "✅ 自動參數調整"
                    ),
                    inline=False,
                )

        except Exception as e:
            embed.add_field(
                name="❌ 錯誤", value=f"無法載入智能批量系統:{e!s}", inline=False
            )

        return embed

    async def _build_render_settings_embed(self) -> discord.Embed:
        """構建渲染設定嵌入"""
        embed = discord.Embed(
            title="🎨 渲染設定系統",
            description="個性化您的訊息渲染體驗",
            color=discord.Color.purple(),
        )

        try:
            config = getattr(self.cog, "config", {})

            # 圖片設定
            embed.add_field(
                name="🖼️ 圖片設定",
                value=(
                    f"品質:{config.get('image_quality', 'high')}\n"
                    f"格式:{config.get('image_format', 'PNG')}\n"
                    f"寬度:{config.get('image_width', 1000)}px"
                ),
                inline=True,
            )

            # 字體設定
            embed.add_field(
                name="🔤 字體設定",
                value=(
                    f"字體:{config.get('font_family', 'Noto Sans CJK')}\n"
                    f"大小:{config.get('font_size', 14)}px\n"
                    f"行高:{config.get('line_height', 1.4)}"
                ),
                inline=True,
            )

            # 顏色主題
            theme_config = config.get("theme_config", {})
            embed.add_field(
                name="🌈 顏色主題",
                value=(
                    f"主題:{theme_config.get('name', 'Discord 預設')}\n"
                    f"背景:{theme_config.get('background', '#36393f')}\n"
                    f"文字:{theme_config.get('text_color', '#dcddde')}\n"
                    f"強調:{theme_config.get('accent', '#7289da')}"
                ),
                inline=True,
            )

        except Exception as e:
            embed.add_field(
                name="❌ 錯誤", value=f"無法載入渲染設定:{e!s}", inline=False
            )

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        檢查互動權限

        Args:
            interaction: Discord 互動

        Returns:
            bool: 是否允許互動
        """
        if not is_allowed(interaction, "訊息日誌設定"):
            await interaction.response.send_message(
                "❌ 您沒有權限使用此功能.需要「管理伺服器」權限.", ephemeral=True
            )
            return False
        return True


# 保持原有的 SettingsView 以向後兼容
class SettingsView(EnhancedSettingsView):
    """
    訊息監聽系統設定面板視圖 (向後兼容)
    """

    pass


class SearchPaginationView(View):
    """
    訊息搜尋結果分頁視圖

    功能:
    - 分頁顯示搜尋結果
    - 提供上一頁/下一頁按鈕
    """

    def __init__(self, cog, results: list[dict[str, Any]], owner_id: int):
        """
        初始化搜尋分頁視圖

        Args:
            cog: MessageListenerCog 實例
            results: 搜尋結果列表
            owner_id: 擁有者 ID
        """
        super().__init__(timeout=300)  # 5分鐘超時
        self.cog = cog
        self.results = results
        self.owner_id = owner_id
        self.page = 0
        self.per_page = 5
        self.total_pages = max(1, (len(results) + self.per_page - 1) // self.per_page)

        # 添加分頁按鈕
        self._update_buttons()

    def build_page_embed(self) -> discord.Embed:
        """
        構建當前頁面的嵌入訊息

        Returns:
            discord.Embed: 嵌入訊息
        """
        start = self.page * self.per_page
        end = min(start + self.per_page, len(self.results))
        current_results = self.results[start:end]

        embed = discord.Embed(
            title=f"📝 訊息搜尋結果 ({len(self.results)} 條)",
            description=f"第 {self.page + 1}/{self.total_pages} 頁",
            color=discord.Color.blue(),
        )

        if not current_results:
            embed.add_field(
                name="無結果", value="沒有找到符合條件的訊息.", inline=False
            )
            return embed

        for i, msg in enumerate(current_results, start=1):
            # 獲取用戶和頻道
            user = self.cog.bot.get_user(msg.get("author_id"))
            channel = self.cog.bot.get_channel(msg.get("channel_id"))

            # 格式化訊息內容
            content = msg.get("content", "")
            if len(content) > 100:
                content = content[:97] + "..."

            # 添加欄位
            field_name = f"{i}. "
            if user:
                field_name += f"{user.display_name}"
            else:
                field_name += f"用戶 {msg.get('author_id')}"

            if channel:
                field_name += f" 在 #{channel.name}"
            else:
                field_name += f" 在頻道 {msg.get('channel_id')}"

            field_name += f" ({msg.get('formatted_time')})"

            # 如果已刪除,添加標記
            if msg.get("deleted"):
                field_name += " [已刪除]"

            embed.add_field(name=field_name, value=content or "[無內容]", inline=False)

        embed.set_footer(text="使用下方按鈕瀏覽更多結果")
        return embed

    async def update(self, interaction: discord.Interaction):
        """
        更新視圖

        Args:
            interaction: Discord 互動
        """
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.build_page_embed(), view=self
        )

    def _update_buttons(self):
        """更新分頁按鈕狀態"""
        # 清除現有按鈕
        self.clear_items()

        # 添加分頁按鈕
        self.add_item(PageButton(self, -1, "⬅️ 上一頁", disabled=(self.page <= 0)))
        self.add_item(
            PageButton(
                self, 1, "下一頁 ➡️", disabled=(self.page >= self.total_pages - 1)
            )
        )

        # 添加關閉按鈕
        self.add_item(CloseButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        檢查互動權限

        Args:
            interaction: Discord 互動

        Returns:
            bool: 是否允許互動
        """
        # 只允許原始用戶互動
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ 只有原始搜尋者可以使用這些按鈕.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """視圖超時處理"""
        # 禁用所有按鈕
        for item in self.children:
            item.disabled = True

        # 嘗試更新訊息
        try:
            message = self.message
            if message:
                await message.edit(view=self)
        except Exception:
            pass
