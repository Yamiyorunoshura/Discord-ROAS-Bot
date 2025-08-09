"""主成就面板視圖模組.

此模組實作主成就面板的 Discord UI 組件,提供:
- 分類樹狀結構顯示
- 成就列表瀏覽
- 分類展開收合互動
- 即時進度顯示
- 效能優化快取
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

if TYPE_CHECKING:
    from ...database.models import Achievement, AchievementCategory
    from ...services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

# 常數定義
MAX_LOAD_TIME_MS = 250  # 最大載入時間(毫秒)
MAX_DROPDOWN_OPTIONS = 25  # Discord 下拉選單最大選項數
MAX_INTERACTION_TIME_MS = 400  # 最大互動回應時間(毫秒)


class MainAchievementPanelView(ui.View):
    """主成就面板視圖.

    提供完整的成就系統界面,支援:
    - 無限層級分類樹顯示
    - 分類展開收合互動
    - 成就瀏覽和進度追蹤
    - 快取優化和效能監控
    """

    def __init__(
        self,
        achievement_service: AchievementService,
        user_id: int,
        guild_id: int,
        interaction: discord.Interaction,
    ):
        """初始化主成就面板.

        Args:
            achievement_service: 成就服務實例
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            interaction: Discord 互動物件
        """
        super().__init__(timeout=300)  # 5 分鐘超時

        self.achievement_service = achievement_service
        self.user_id = user_id
        self.guild_id = guild_id
        self.interaction = interaction

        # 面板狀態
        self._current_category_id: int | None = None
        self._expanded_categories: set[int] = set()
        self._category_tree: list[dict[str, Any]] = []
        self._achievements_cache: dict[str, Any] = {}

        # 效能監控
        self._load_start_time: float = 0
        self._interaction_times: list[float] = []

        # 初始化 UI 組件
        self._setup_ui_components()

    def _setup_ui_components(self) -> None:
        """設置 UI 組件."""
        # 分類選擇下拉選單
        self.category_select = ui.Select(
            custom_id="achievement_category_select",
            placeholder="選擇成就分類...",
            min_values=0,
            max_values=1,
        )
        self.category_select.callback = self.on_category_select
        self.add_item(self.category_select)

        # 導航按鈕
        self.prev_button = ui.Button(
            label="◀️ 上一頁",
            style=discord.ButtonStyle.secondary,
            custom_id="achievement_prev_page",
            disabled=True,
        )
        self.prev_button.callback = self.on_previous_page
        self.add_item(self.prev_button)

        self.next_button = ui.Button(
            label="下一頁 ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="achievement_next_page",
            disabled=True,
        )
        self.next_button.callback = self.on_next_page
        self.add_item(self.next_button)

        # 操作按鈕
        self.refresh_button = ui.Button(
            label="🔄 重新整理",
            style=discord.ButtonStyle.primary,
            custom_id="achievement_refresh",
        )
        self.refresh_button.callback = self.on_refresh
        self.add_item(self.refresh_button)

        self.close_button = ui.Button(
            label="❌ 關閉",
            style=discord.ButtonStyle.danger,
            custom_id="achievement_close",
        )
        self.close_button.callback = self.on_close
        self.add_item(self.close_button)

    async def load_initial_data(self) -> None:
        """載入初始資料.

        效能要求:≤ 250ms
        """
        self._load_start_time = time.time()

        try:
            # 並行載入分類樹和初始成就資料
            tasks = [
                self._load_category_tree(),
                self._load_initial_achievements(),
            ]

            await asyncio.gather(*tasks)

            # 更新 UI 組件
            await self._update_category_select()

            # 效能監控
            load_time = (time.time() - self._load_start_time) * 1000
            if load_time > MAX_LOAD_TIME_MS:
                logger.warning(
                    f"主面板載入時間超過要求:{load_time:.1f}ms > 250ms",
                    extra={
                        "user_id": self.user_id,
                        "guild_id": self.guild_id,
                        "load_time_ms": load_time,
                    },
                )
            else:
                logger.debug(
                    f"主面板載入完成:{load_time:.1f}ms",
                    extra={"load_time_ms": load_time},
                )

        except Exception as e:
            logger.error(
                "載入初始資料失敗",
                extra={
                    "user_id": self.user_id,
                    "guild_id": self.guild_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def _load_category_tree(self) -> None:
        """載入分類樹結構."""
        try:
            self._category_tree = await self.achievement_service.get_category_tree()
            logger.debug(
                "分類樹載入完成", extra={"tree_size": len(self._category_tree)}
            )
        except Exception as e:
            logger.error(f"載入分類樹失敗: {e}")
            self._category_tree = []

    async def _load_initial_achievements(self) -> None:
        """載入初始成就資料."""
        try:
            achievements = await self.achievement_service.list_achievements(
                active_only=True
            )
            self._achievements_cache["all"] = achievements

            # 載入用戶統計
            user_stats = await self.achievement_service.get_user_achievement_stats(
                self.user_id
            )
            self._achievements_cache["user_stats"] = user_stats

            logger.debug(
                "初始成就資料載入完成",
                extra={
                    "total_achievements": len(achievements),
                    "user_achievements": user_stats.get("total_achievements", 0),
                },
            )
        except Exception as e:
            logger.error(f"載入初始成就資料失敗: {e}")
            self._achievements_cache = {}

    async def _update_category_select(self) -> None:
        """更新分類選擇下拉選單."""
        try:
            options = [
                discord.SelectOption(
                    label="📊 全部成就",
                    value="all",
                    description="顯示所有可用成就",
                    ,
                )
            ]

            # 遞歸添加分類選項
            def add_category_options(
                tree_nodes: list[dict[str, Any]], level: int = 0
            ) -> None:
                for node in tree_nodes:
                    category: AchievementCategory = node["category"]

                    # 限制下拉選單選項數量(Discord 限制 25 個)
                    if len(options) >= MAX_DROPDOWN_OPTIONS:
                        break

                    # 建立縮排顯示
                    indent = "　" * level  # 全形空格縮排
                    display_name = (
                        f"{indent}{category.icon_emoji or '📁'} {category.name}"
                    )

                    # 添加成就數量
                    achievement_count = node.get("achievement_count", 0)
                    description = (
                        f"{category.description[:50]}... ({achievement_count} 個成就)"
                    )

                    options.append(
                        discord.SelectOption(
                            label=display_name[:100],  # Discord 限制
                            value=str(category.id),
                            description=description[:100],  # Discord 限制
                        )
                    )

                    # 如果分類已展開,添加子分類
                    if category.id in self._expanded_categories and node.get(
                        "children"
                    ):
                        add_category_options(node["children"], level + 1)

            add_category_options(self._category_tree)

            # 更新選單選項
            self.category_select.options = options

            logger.debug(f"分類選單更新完成,共 {len(options)} 個選項")

        except Exception as e:
            logger.error(f"更新分類選單失敗: {e}")

    async def create_embed(self) -> discord.Embed:
        """建立主面板 Embed.

        Returns:
            主面板顯示的 Embed
        """
        try:
            # 基礎 Embed
            embed = StandardEmbedBuilder.create_info_embed(
                "🏆 成就系統", "瀏覽和追蹤您的成就進度"
            )

            # 添加用戶資訊
            try:
                user = self.interaction.user
                embed.set_author(
                    name=f"{user.display_name} 的成就", icon_url=user.display_avatar.url
                )
            except Exception:
                embed.set_author(name="成就面板")

            # 添加統計資訊
            user_stats = self._achievements_cache.get("user_stats", {})
            total_achievements = len(self._achievements_cache.get("all", []))
            user_achievements = user_stats.get("total_achievements", 0)
            user_points = user_stats.get("total_points", 0)

            completion_rate = (
                (user_achievements / total_achievements * 100)
                if total_achievements > 0
                else 0
            )

            embed.add_field(
                name="📊 成就統計",
                value=f"**已獲得**: {user_achievements}/{total_achievements}\n"
                f"**完成率**: {completion_rate:.1f}%\n"
                f"**總點數**: {user_points:,}",
                inline=True,
            )

            # 添加分類資訊
            if self._current_category_id:
                category = await self.achievement_service.get_category_by_id(
                    self._current_category_id
                )
                if category:
                    embed.add_field(
                        name="📁 當前分類",
                        value=f"{category.icon_emoji} {category.name}\n{category.description}",
                        inline=True,
                    )
            else:
                embed.add_field(
                    name="📁 瀏覽模式",
                    value="📊 顯示所有成就\n選擇分類進行篩選",
                    inline=True,
                )

            recent_achievements = await self._get_recent_user_achievements(limit=3)
            if recent_achievements:
                recent_text = "\n".join([
                    f"🏅 {ach.name}" for _, ach in recent_achievements
                ])
                embed.add_field(name="🏆 最近獲得", value=recent_text, inline=False)

            # 添加操作指南
            embed.add_field(
                name="操作指南",
                value="• 使用下拉選單選擇分類\n"
                "• 點擊 🔄 重新整理資料\n"
                "• 使用 ◀️ ▶️ 翻頁瀏覽",
                inline=False,
            )

            # 設置 footer
            embed.set_footer(
                text=f"成就面板 | 載入時間: {(time.time() - self._load_start_time) * 1000:.0f}ms"
            )

            return embed

        except Exception as e:
            logger.error(f"建立主面板 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入成就面板,請稍後再試"
            )

    async def _get_recent_user_achievements(
        self, limit: int = 3
    ) -> list[tuple[Any, Achievement]]:
        """取得用戶最近獲得的成就.

        Args:
            limit: 最大返回數量

        Returns:
            最近成就列表
        """
        try:
            return await self.achievement_service.get_user_achievements(
                user_id=self.user_id, limit=limit
            )
        except Exception as e:
            logger.error(f"取得最近成就失敗: {e}")
            return []

    # =============================================================================
    # 互動事件處理
    # =============================================================================

    async def on_category_select(self, interaction: discord.Interaction) -> None:
        """處理分類選擇事件.

        效能要求:≤ 400ms
        """
        start_time = time.time()

        try:
            await interaction.response.defer()

            selected_value = (
                self.category_select.values[0] if self.category_select.values else "all"
            )

            if selected_value == "all":
                self._current_category_id = None
            else:
                self._current_category_id = int(selected_value)

            # 重新載入當前分類的成就
            await self._load_category_achievements(self._current_category_id)

            # 更新顯示
            embed = await self.create_embed()
            await interaction.followup.edit_message(
                interaction.message.id, embed=embed, view=self
            )

            # 效能監控
            interaction_time = (time.time() - start_time) * 1000
            self._interaction_times.append(interaction_time)

            if interaction_time > MAX_INTERACTION_TIME_MS:
                logger.warning(
                    f"分類選擇響應時間超過要求:{interaction_time:.1f}ms > 400ms",
                    extra={
                        "user_id": self.user_id,
                        "category_id": self._current_category_id,
                        "interaction_time_ms": interaction_time,
                    },
                )

            logger.debug(
                f"分類選擇完成:{interaction_time:.1f}ms",
                extra={
                    "category_id": self._current_category_id,
                    "interaction_time_ms": interaction_time,
                },
            )

        except Exception as e:
            logger.error(
                "處理分類選擇失敗",
                extra={
                    "user_id": self.user_id,
                    "selected_value": selected_value
                    if "selected_value" in locals()
                    else "unknown",
                    "error": str(e),
                },
                exc_info=True,
            )
            await interaction.followup.send(
                "❌ 處理分類選擇時發生錯誤,請稍後再試", ephemeral=True
            )

    async def _load_category_achievements(self, category_id: int | None) -> None:
        """載入指定分類的成就.

        Args:
            category_id: 分類 ID,None 表示所有成就
        """
        try:
            cache_key = f"category_{category_id}" if category_id else "all"

            if cache_key not in self._achievements_cache:
                achievements = await self.achievement_service.list_achievements(
                    category_id=category_id, active_only=True
                )
                self._achievements_cache[cache_key] = achievements

            logger.debug(
                "分類成就載入完成",
                extra={
                    "category_id": category_id,
                    "achievement_count": len(self._achievements_cache[cache_key]),
                },
            )

        except Exception as e:
            logger.error(f"載入分類成就失敗: {e}")
            self._achievements_cache[cache_key] = []

    async def on_previous_page(self, interaction: discord.Interaction) -> None:
        """處理上一頁事件."""
        await interaction.response.send_message("⚠️ 分頁功能開發中", ephemeral=True)

    async def on_next_page(self, interaction: discord.Interaction) -> None:
        """處理下一頁事件."""
        await interaction.response.send_message("⚠️ 分頁功能開發中", ephemeral=True)

    async def on_refresh(self, interaction: discord.Interaction) -> None:
        """處理重新整理事件."""
        try:
            await interaction.response.defer()

            # 清除快取
            self._achievements_cache.clear()

            # 重新載入資料
            await self.load_initial_data()

            # 更新顯示
            embed = await self.create_embed()
            await interaction.followup.edit_message(
                interaction.message.id, embed=embed, view=self
            )

            logger.info("成就面板重新整理完成", extra={"user_id": self.user_id})

        except Exception as e:
            logger.error(f"重新整理失敗: {e}")
            await interaction.followup.send(
                "❌ 重新整理時發生錯誤,請稍後再試", ephemeral=True
            )

    async def on_close(self, interaction: discord.Interaction) -> None:
        """處理關閉事件."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "面板已關閉", "✅ 成就面板已關閉,感謝使用!"
            )

            # 停用所有組件
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

            # 記錄使用統計
            avg_interaction_time = (
                sum(self._interaction_times) / len(self._interaction_times)
                if self._interaction_times
                else 0
            )

            logger.info(
                "成就面板已關閉",
                extra={
                    "user_id": self.user_id,
                    "session_duration": time.time() - self._load_start_time,
                    "interactions_count": len(self._interaction_times),
                    "avg_interaction_time_ms": avg_interaction_time,
                },
            )

        except Exception as e:
            logger.error(f"關閉面板失敗: {e}")

    async def on_timeout(self) -> None:
        """處理超時事件."""
        try:
            # 停用所有組件
            for item in self.children:
                item.disabled = True

            embed = StandardEmbedBuilder.create_warning_embed(
                "面板已過期", "⏰ 成就面板已過期,請重新開啟"
            )

            if self.interaction and hasattr(self.interaction, "edit_original_response"):
                await self.interaction.edit_original_response(embed=embed, view=self)

            logger.debug("成就面板已超時", extra={"user_id": self.user_id})

        except Exception as e:
            logger.error(f"處理超時失敗: {e}")

    # =============================================================================
    # 公共介面
    # =============================================================================

    async def get_performance_stats(self) -> dict[str, Any]:
        """取得效能統計資料.

        Returns:
            效能統計字典
        """
        avg_interaction_time = (
            sum(self._interaction_times) / len(self._interaction_times)
            if self._interaction_times
            else 0
        )

        return {
            "load_time_ms": (time.time() - self._load_start_time) * 1000
            if self._load_start_time
            else 0,
            "interactions_count": len(self._interaction_times),
            "avg_interaction_time_ms": avg_interaction_time,
            "cache_size": len(self._achievements_cache),
            "expanded_categories": len(self._expanded_categories),
        }


# 輔助函數
async def create_main_achievement_panel(
    achievement_service: AchievementService,
    interaction: discord.Interaction,
) -> tuple[discord.Embed, MainAchievementPanelView]:
    """建立主成就面板.

    Args:
        achievement_service: 成就服務實例
        interaction: Discord 互動物件

    Returns:
        (Embed, View) 元組
    """
    try:
        # 建立主面板視圖
        view = MainAchievementPanelView(
            achievement_service=achievement_service,
            user_id=interaction.user.id,
            guild_id=interaction.guild_id,
            interaction=interaction,
        )

        # 載入初始資料
        await view.load_initial_data()

        # 建立 Embed
        embed = await view.create_embed()

        return embed, view

    except Exception as e:
        logger.error(f"建立主成就面板失敗: {e}")

        # 返回錯誤 Embed
        error_embed = StandardEmbedBuilder.create_error_embed(
            "載入失敗", "❌ 無法載入成就面板,請稍後再試"
        )

        return error_embed, None


__all__ = [
    "MainAchievementPanelView",
    "create_main_achievement_panel",
]
