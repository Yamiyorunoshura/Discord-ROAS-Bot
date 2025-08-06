"""分類展開收合交互組件.

此模組實作成就分類的展開收合互動功能,提供:
- 分類樹狀結構顯示
- 分類展開/收合動畫效果
- 即時 UI 更新
- 效能優化
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

if TYPE_CHECKING:
    from ...database.models import AchievementCategory
    from ...services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

# 常數定義
MAX_RESPONSE_TIME_MS = 400  # 最大回應時間(毫秒)
MAX_ACHIEVEMENTS_DISPLAY = 10  # 最多顯示成就數量
MAX_BUTTON_COUNT = 20  # 最多按鈕數量(保留位置給操作按鈕)


class CategoryTreeButton(ui.Button):
    """分類樹展開/收合按鈕.

    用於控制分類的展開狀態,支援:
    - 單擊展開/收合
    - 動態圖示變更
    - 效能監控
    """

    def __init__(
        self,
        category: AchievementCategory,
        is_expanded: bool = False,
        has_children: bool = False,
        achievement_count: int = 0,
    ):
        """初始化分類按鈕.

        Args:
            category: 成就分類
            is_expanded: 是否已展開
            has_children: 是否有子分類
            achievement_count: 成就數量
        """
        self.category = category
        self.is_expanded = is_expanded
        self.has_children = has_children
        self.achievement_count = achievement_count

        # 確定按鈕樣式和標籤
        if has_children:
            emoji = "📂" if is_expanded else "📁"
            style = (
                discord.ButtonStyle.primary
                if is_expanded
                else discord.ButtonStyle.secondary
            )
        else:
            emoji = category.icon_emoji or "📄"
            style = discord.ButtonStyle.secondary

        # 建立顯示標籤
        indent = "　" * category.level  # 全形空格縮排
        label = f"{indent}{emoji} {category.name}"
        if achievement_count > 0:
            label += f" ({achievement_count})"

        super().__init__(
            label=label[:80],  # Discord 限制
            style=style,
            custom_id=f"category_tree_{category.id}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """處理按鈕點擊事件."""
        start_time = time.time()

        try:
            # 檢查是否有子分類
            if not self.has_children:
                # 沒有子分類,顯示該分類的成就
                await self._show_category_achievements(interaction)
                return

            # 有子分類,切換展開狀態
            await interaction.response.defer()

            # 從 view 中獲取服務
            view = self.view
            if not hasattr(view, "achievement_service"):
                await interaction.followup.send(
                    "❌ 服務不可用,請重新整理面板", ephemeral=True
                )
                return

            achievement_service: AchievementService = view.achievement_service

            # 切換展開狀態
            new_state = await achievement_service.toggle_category_expansion(
                self.category.id
            )
            self.is_expanded = new_state

            # 更新按鈕外觀
            self._update_button_appearance()

            # 重新建構整個視圖
            await view.rebuild_category_tree(interaction)

            # 效能監控
            interaction_time = (time.time() - start_time) * 1000
            if interaction_time > MAX_RESPONSE_TIME_MS:
                logger.warning(
                    f"分類展開/收合響應時間超過要求:{interaction_time:.1f}ms > 400ms",
                    extra={
                        "category_id": self.category.id,
                        "category_name": self.category.name,
                        "interaction_time_ms": interaction_time,
                    },
                )

            logger.debug(
                f"分類展開/收合完成:{interaction_time:.1f}ms",
                extra={
                    "category_id": self.category.id,
                    "new_state": new_state,
                    "interaction_time_ms": interaction_time,
                },
            )

        except Exception as e:
            logger.error(
                "處理分類展開/收合失敗",
                extra={
                    "category_id": self.category.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            await interaction.followup.send(
                "❌ 處理分類操作時發生錯誤,請稍後再試", ephemeral=True
            )

    def _update_button_appearance(self) -> None:
        """更新按鈕外觀."""
        if self.has_children:
            emoji = "📂" if self.is_expanded else "📁"
            self.style = (
                discord.ButtonStyle.primary
                if self.is_expanded
                else discord.ButtonStyle.secondary
            )
        else:
            emoji = self.category.icon_emoji or "📄"

        # 更新標籤
        indent = "　" * self.category.level
        label = f"{indent}{emoji} {self.category.name}"
        if self.achievement_count > 0:
            label += f" ({self.achievement_count})"

        self.label = label[:80]

    async def _show_category_achievements(
        self, interaction: discord.Interaction
    ) -> None:
        """顯示分類下的成就."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 從 view 中獲取服務
            view = self.view
            if not hasattr(view, "achievement_service"):
                await interaction.followup.send(
                    "❌ 服務不可用,請重新整理面板", ephemeral=True
                )
                return

            achievement_service: AchievementService = view.achievement_service

            # 獲取分類下的成就
            achievements = await achievement_service.get_achievements_by_category(
                guild_id=None,  # 目前未使用
                category=self.category.id,
            )

            if not achievements:
                await interaction.followup.send(
                    f"📂 分類「{self.category.name}」目前沒有成就", ephemeral=True
                )
                return

            # 建立成就列表 Embed
            embed = StandardEmbedBuilder.create_info_embed(
                f"{self.category.icon_emoji} {self.category.name}",
                self.category.description,
            )

            # 添加成就列表
            achievement_text = ""
            for i, achievement in enumerate(achievements[:10], 1):  # 最多顯示 10 個
                achievement_text += (
                    f"{i}. **{achievement.name}** ({achievement.points} 點)\n"
                )
                achievement_text += f"   _{achievement.description[:50]}..._\n\n"

            if achievement_text:
                embed.add_field(
                    name=f"📋 成就列表 ({len(achievements)} 個)",
                    value=achievement_text[:1024],  # Discord 限制
                    inline=False,
                )

            if len(achievements) > MAX_ACHIEVEMENTS_DISPLAY:
                embed.add_field(
                    name="📄 更多成就",
                    value=f"還有 {len(achievements) - MAX_ACHIEVEMENTS_DISPLAY} 個成就,請使用主面板查看",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"顯示分類成就失敗: {e}")
            await interaction.followup.send("❌ 載入分類成就時發生錯誤", ephemeral=True)


class CategoryTreeView(ui.View):
    """分類樹狀視圖.

    提供完整的分類樹狀結構顯示,支援:
    - 無限層級分類
    - 展開/收合互動
    - 動態重建
    - 效能優化
    """

    def __init__(
        self,
        achievement_service: AchievementService,
        user_id: int,
        guild_id: int,
    ):
        """初始化分類樹視圖.

        Args:
            achievement_service: 成就服務實例
            user_id: 用戶 ID
            guild_id: 伺服器 ID
        """
        super().__init__(timeout=300)

        self.achievement_service = achievement_service
        self.user_id = user_id
        self.guild_id = guild_id

        # 狀態追蹤
        self._category_tree: list[dict[str, Any]] = []
        self._expanded_categories: set[int] = set()

    async def load_category_tree(self) -> None:
        """載入分類樹結構."""
        try:
            self._category_tree = await self.achievement_service.get_category_tree()

            # 載入展開狀態
            for node in self._flatten_tree(self._category_tree):
                category: AchievementCategory = node["category"]
                if category.is_expanded:
                    self._expanded_categories.add(category.id)

            logger.debug(
                "分類樹載入完成",
                extra={
                    "tree_size": len(self._category_tree),
                    "expanded_count": len(self._expanded_categories),
                },
            )

        except Exception as e:
            logger.error(f"載入分類樹失敗: {e}")
            self._category_tree = []

    def _flatten_tree(self, tree_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """展平樹結構為列表.

        Args:
            tree_nodes: 樹節點列表

        Returns:
            展平後的節點列表
        """
        flattened = []
        for node in tree_nodes:
            flattened.append(node)
            if node.get("children"):
                flattened.extend(self._flatten_tree(node["children"]))
        return flattened

    async def build_tree_buttons(self) -> None:
        """建構分類樹按鈕."""
        try:
            # 清除現有按鈕
            self.clear_items()

            # 遞歸添加分類按鈕
            button_count = 0
            self._add_tree_buttons(self._category_tree, button_count)

            # 添加操作按鈕
            self._add_action_buttons()

        except Exception as e:
            logger.error(f"建構分類樹按鈕失敗: {e}")

    def _add_tree_buttons(
        self, tree_nodes: list[dict[str, Any]], button_count: int
    ) -> int:
        """遞歸添加分類樹按鈕.

        Args:
            tree_nodes: 樹節點列表
            button_count: 當前按鈕數量

        Returns:
            更新後的按鈕數量
        """
        for node in tree_nodes:
            # Discord View 最多 25 個組件
            if button_count >= MAX_BUTTON_COUNT:  # 保留位置給操作按鈕
                break

            category: AchievementCategory = node["category"]

            # 建立分類按鈕
            button = CategoryTreeButton(
                category=category,
                is_expanded=category.id in self._expanded_categories,
                has_children=node.get("has_children", False),
                achievement_count=node.get("achievement_count", 0),
            )

            self.add_item(button)
            button_count += 1

            # 如果分類已展開且有子分類,遞歸添加子按鈕
            if (
                category.id in self._expanded_categories
                and node.get("children")
                and button_count < MAX_BUTTON_COUNT
            ):
                button_count = self._add_tree_buttons(node["children"], button_count)

        return button_count

    def _add_action_buttons(self) -> None:
        """添加操作按鈕."""
        # 全部展開按鈕
        expand_all_button = ui.Button(
            label="📂 全部展開",
            style=discord.ButtonStyle.secondary,
            custom_id="expand_all_categories",
        )
        expand_all_button.callback = self.expand_all_categories
        self.add_item(expand_all_button)

        # 全部收合按鈕
        collapse_all_button = ui.Button(
            label="📁 全部收合",
            style=discord.ButtonStyle.secondary,
            custom_id="collapse_all_categories",
        )
        collapse_all_button.callback = self.collapse_all_categories
        self.add_item(collapse_all_button)

        # 重新整理按鈕
        refresh_button = ui.Button(
            label="🔄 重新整理",
            style=discord.ButtonStyle.primary,
            custom_id="refresh_category_tree",
        )
        refresh_button.callback = self.refresh_tree
        self.add_item(refresh_button)

    async def expand_all_categories(self, interaction: discord.Interaction) -> None:
        """展開所有分類."""
        try:
            await interaction.response.defer()

            # 展開所有有子分類的分類
            for node in self._flatten_tree(self._category_tree):
                if node.get("has_children", False):
                    category: AchievementCategory = node["category"]
                    self._expanded_categories.add(category.id)
                    await self.achievement_service.toggle_category_expansion(
                        category.id
                    )

            # 重建視圖
            await self.rebuild_category_tree(interaction)

            logger.info("所有分類已展開", extra={"user_id": self.user_id})

        except Exception as e:
            logger.error(f"展開所有分類失敗: {e}")
            await interaction.followup.send("❌ 展開分類時發生錯誤", ephemeral=True)

    async def collapse_all_categories(self, interaction: discord.Interaction) -> None:
        """收合所有分類."""
        try:
            await interaction.response.defer()

            # 收合所有分類
            for category_id in list(self._expanded_categories):
                await self.achievement_service.toggle_category_expansion(category_id)

            self._expanded_categories.clear()

            # 重建視圖
            await self.rebuild_category_tree(interaction)

            logger.info("所有分類已收合", extra={"user_id": self.user_id})

        except Exception as e:
            logger.error(f"收合所有分類失敗: {e}")
            await interaction.followup.send("❌ 收合分類時發生錯誤", ephemeral=True)

    async def refresh_tree(self, interaction: discord.Interaction) -> None:
        """重新整理分類樹."""
        try:
            await interaction.response.defer()

            # 重新載入分類樹
            await self.load_category_tree()

            # 重建視圖
            await self.rebuild_category_tree(interaction)

            logger.info("分類樹重新整理完成", extra={"user_id": self.user_id})

        except Exception as e:
            logger.error(f"重新整理分類樹失敗: {e}")
            await interaction.followup.send("❌ 重新整理時發生錯誤", ephemeral=True)

    async def rebuild_category_tree(self, interaction: discord.Interaction) -> None:
        """重建分類樹視圖."""
        try:
            # 重建按鈕
            await self.build_tree_buttons()

            # 建立新的 Embed
            embed = await self.create_tree_embed()

            # 更新訊息
            await interaction.followup.edit_message(
                interaction.message.id, embed=embed, view=self
            )

        except Exception as e:
            logger.error(f"重建分類樹視圖失敗: {e}")

    async def create_tree_embed(self) -> discord.Embed:
        """建立分類樹 Embed."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "🌳 成就分類樹", "點擊分類來展開/收合或查看成就"
            )

            # 統計資訊
            total_categories = len(self._flatten_tree(self._category_tree))
            expanded_count = len(self._expanded_categories)

            embed.add_field(
                name="📊 統計資訊",
                value=f"**總分類數**: {total_categories}\n"
                f"**已展開**: {expanded_count}\n"
                f"**樹層級**: {self._get_max_level()}",
                inline=True,
            )

            # 操作說明
            embed.add_field(
                name="💡 操作說明",
                value="• 點擊 📁 展開分類\n• 點擊 📂 收合分類\n• 點擊 📄 查看成就",
                inline=True,
            )

            return embed

        except Exception as e:
            logger.error(f"建立分類樹 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed("載入失敗", "無法載入分類樹")

    def _get_max_level(self) -> int:
        """取得樹的最大層級."""
        max_level = 0
        for node in self._flatten_tree(self._category_tree):
            category: AchievementCategory = node["category"]
            max_level = max(max_level, category.level)
        return max_level + 1  # 層級從 0 開始


# 輔助函數
async def create_category_tree_panel(
    achievement_service: AchievementService,
    interaction: discord.Interaction,
) -> tuple[discord.Embed, CategoryTreeView]:
    """建立分類樹面板.

    Args:
        achievement_service: 成就服務實例
        interaction: Discord 互動物件

    Returns:
        (Embed, View) 元組
    """
    try:
        # 建立分類樹視圖
        view = CategoryTreeView(
            achievement_service=achievement_service,
            user_id=interaction.user.id,
            guild_id=interaction.guild_id,
        )

        # 載入分類樹
        await view.load_category_tree()

        # 建構按鈕
        await view.build_tree_buttons()

        # 建立 Embed
        embed = await view.create_tree_embed()

        return embed, view

    except Exception as e:
        logger.error(f"建立分類樹面板失敗: {e}")

        # 返回錯誤 Embed
        error_embed = StandardEmbedBuilder.create_error_embed(
            "載入失敗", "❌ 無法載入分類樹面板,請稍後再試"
        )

        return error_embed, None


__all__ = [
    "CategoryTreeButton",
    "CategoryTreeView",
    "create_category_tree_panel",
]
