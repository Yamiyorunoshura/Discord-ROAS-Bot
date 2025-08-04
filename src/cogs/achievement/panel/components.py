"""成就系統 UI 組件模組.

提供成就系統面板使用的可重用 UI 組件:
- 頁面選擇器
- 導航按鈕
- 篩選組件
- 狀態指示器
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from .achievement_panel import AchievementPanel

logger = logging.getLogger(__name__)

class PageSelector(discord.ui.Select):
    """頁面選擇器組件.

    提供成就系統主面板的頁面導航功能.
    """

    def __init__(self, panel: AchievementPanel):
        """初始化頁面選擇器.

        Args:
            panel: 所屬的成就面板實例
        """
        self.panel = panel

        options = [
            discord.SelectOption(
                label="我的成就",
                description="查看您已獲得的成就和進度",
                emoji="🏅",
                value="personal",
            ),
            discord.SelectOption(
                label="成就瀏覽",
                description="瀏覽所有可用的成就",
                emoji="📚",
                value="browse",
            ),
            discord.SelectOption(
                label="排行榜",
                description="查看成就排行榜",
                emoji="🏆",
                value="leaderboard",
            ),
        ]

        super().__init__(
            placeholder="選擇要查看的頁面...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """選擇器回調處理."""
        try:
            selected_page = self.values[0]
            await self.panel.change_page(interaction, selected_page)
        except Exception as e:
            logger.error(f"[頁面選擇器]頁面切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class NavigationButton(discord.ui.Button):
    """導航按鈕組件.

    提供頁面間的導航功能.
    """

    def __init__(
        self,
        panel: AchievementPanel,
        *,
        label: str,
        emoji: str | None = None,
        target_page: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ):
        """初始化導航按鈕.

        Args:
            panel: 所屬的成就面板實例
            label: 按鈕標籤
            emoji: 按鈕表情符號
            target_page: 目標頁面
            style: 按鈕樣式
        """
        self.panel = panel
        self.target_page = target_page

        super().__init__(label=label, emoji=emoji, style=style)

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            await self.panel.change_page(interaction, self.target_page)
        except Exception as e:
            logger.error(f"[導航按鈕]頁面切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class RefreshButton(discord.ui.Button):
    """重新整理按鈕組件."""

    def __init__(self, panel: AchievementPanel):
        """初始化重新整理按鈕.

        Args:
            panel: 所屬的成就面板實例
        """
        self.panel = panel

        super().__init__(
            label="重新整理", emoji="🔄", style=discord.ButtonStyle.secondary
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            await self.panel.refresh_callback(interaction)
        except Exception as e:
            logger.error(f"[重新整理按鈕]重新整理失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class CloseButton(discord.ui.Button):
    """關閉按鈕組件."""

    def __init__(self, panel: AchievementPanel):
        """初始化關閉按鈕.

        Args:
            panel: 所屬的成就面板實例
        """
        self.panel = panel

        super().__init__(label="關閉", emoji="❌", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            await self.panel.close_callback(interaction)
        except Exception as e:
            logger.error(f"[關閉按鈕]關閉失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class BrowserCategorySelector(discord.ui.Select):
    """成就瀏覽頁面分類選擇器組件.

    專為成就瀏覽頁面設計的分類篩選功能.
    """

    def __init__(self, panel: AchievementPanel, categories: list[dict[str, Any]]):
        """初始化瀏覽分類選擇器.

        Args:
            panel: 所屬的成就面板實例
            categories: 可用的成就分類列表
        """
        self.panel = panel

        options = [
            discord.SelectOption(
                label="全部分類",
                description="顯示所有類型的成就",
                emoji="📋",
                value="all",
            )
        ]

        # 添加分類選項,包含成就數量資訊
        for category in categories[:24]:  # Discord 限制最多25個選項
            options.append(
                discord.SelectOption(
                    label=category["name"],
                    description=f"共 {category['count']} 個成就",
                    emoji=category.get("icon_emoji", "📁"),
                    value=str(category["id"]),
                )
            )

        super().__init__(
            placeholder="選擇成就分類...", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """選擇器回調處理."""
        try:
            selected_category = self.values[0]

            # 獲取瀏覽視圖並設置分類篩選
            browser_view = self.panel.view_manager.get_view("browse")
            category_id = None if selected_category == "all" else int(selected_category)
            browser_view.set_category_filter(category_id)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[瀏覽分類選擇器]分類切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class BrowserPaginationButton(discord.ui.Button):
    """成就瀏覽頁面分頁按鈕組件.

    專為成就瀏覽頁面設計的分頁導航功能.
    """

    def __init__(
        self,
        panel: AchievementPanel,
        *,
        direction: str,
        label: str,
        emoji: str | None = None,
        disabled: bool = False,
    ):
        """初始化瀏覽分頁按鈕.

        Args:
            panel: 所屬的成就面板實例
            direction: 導航方向 ("prev", "next", "first", "last")
            label: 按鈕標籤
            emoji: 按鈕表情符號
            disabled: 是否禁用
        """
        self.panel = panel
        self.direction = direction

        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            # 獲取瀏覽視圖
            browser_view = self.panel.view_manager.get_view("browse")

            # 根據方向調整頁面
            if self.direction == "prev":
                if browser_view.has_previous_page():
                    browser_view.set_page(browser_view.get_current_page() - 1)
            elif self.direction == "next":
                if browser_view.has_next_page():
                    browser_view.set_page(browser_view.get_current_page() + 1)
            elif self.direction == "first":
                browser_view.set_page(0)
            elif self.direction == "last":
                browser_view.set_page(browser_view.get_total_pages() - 1)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[瀏覽分頁按鈕]分頁導航失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class AchievementBrowserDetailButton(discord.ui.Button):
    """成就詳情按鈕組件.

    點擊後顯示成就的詳細資訊.
    """

    def __init__(self, panel: AchievementPanel, achievement_data: dict[str, Any]):
        """初始化成就詳情按鈕.

        Args:
            panel: 所屬的成就面板實例
            achievement_data: 成就資料
        """
        self.panel = panel
        self.achievement_data = achievement_data

        super().__init__(
            label=f"{achievement_data['name'][:20]}...",
            emoji="i",
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            # 創建成就詳情模態框
            modal = ComponentFactory.create_achievement_detail_modal(
                self.achievement_data
            )
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"[成就詳情按鈕]顯示詳情失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class AchievementProgressIndicatorView:
    """成就進度指示器視圖組件.

    提供成就進度的視覺化顯示.
    """

    @staticmethod
    def create_progress_embed_field(
        achievement: dict[str, Any], progress: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """創建進度顯示欄位.

        Args:
            achievement: 成就資料
            progress: 進度資料

        Returns:
            dict: 包含欄位名稱和值的字典
        """
        if not progress:
            return {
                "name": f"🎯 {achievement['name']}",
                "value": f"_{achievement['description']}_\n💰 獎勵: {achievement['points']} 點",
            }

        # 計算進度百分比
        current = progress.get("current", 0)
        target = progress.get("target", 100)
        percentage = min((current / target) * 100, 100) if target > 0 else 0

        # 創建進度條
        progress_bar = AchievementProgressIndicatorView._create_visual_progress_bar(
            current, target
        )

        return {
            "name": f"⏳ {achievement['name']} ({percentage:.0f}%)",
            "value": f"_{achievement['description']}_\n"
            f"{progress_bar} {current:,}/{target:,}\n"
            f"💰 獎勵: {achievement['points']} 點",
        }

    @staticmethod
    def _create_visual_progress_bar(current: int, target: int, length: int = 15) -> str:
        """創建視覺化進度條.

        Args:
            current: 當前進度
            target: 目標值
            length: 進度條長度

        Returns:
            str: 進度條字串
        """
        if target <= 0:
            return "▓" * length

        progress_ratio = min(current / target, 1.0)
        filled_length = int(length * progress_ratio)

        # 使用不同的字符來表示進度
        filled = "█" * filled_length
        empty = "░" * (length - filled_length)

        return f"[{filled}{empty}]"

class AchievementCategorySelector(discord.ui.Select):
    """成就分類選擇器組件.

    用於成就瀏覽頁面的分類篩選.
    """

    def __init__(self, panel: AchievementPanel, categories: list[dict[str, Any]]):
        """初始化分類選擇器.

        Args:
            panel: 所屬的成就面板實例
            categories: 可用的成就分類列表
        """
        self.panel = panel

        options = [
            discord.SelectOption(
                label="全部", description="顯示所有成就", emoji="📋", value="all"
            )
        ]

        # 添加分類選項
        for category in categories[:24]:  # Discord 限制最多25個選項
            options.append(
                discord.SelectOption(
                    label=category["name"],
                    description=f"{category['count']} 個成就",
                    emoji="📁",
                    value=str(category["id"]),
                )
            )

        super().__init__(
            placeholder="選擇成就分類...", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """選擇器回調處理."""
        try:
            selected_category = self.values[0]

            # 更新面板的分類篩選狀態
            self.panel.set_page_data("browse", {"selected_category": selected_category})

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[分類選擇器]分類切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class AchievementStatusButton(discord.ui.Button):
    """成就狀態篩選按鈕組件.

    用於篩選已獲得或未獲得的成就.
    """

    def __init__(
        self,
        panel: AchievementPanel,
        *,
        status: str,
        label: str,
        emoji: str | None = None,
    ):
        """初始化狀態篩選按鈕.

        Args:
            panel: 所屬的成就面板實例
            status: 篩選狀態 ("all", "earned", "not_earned")
            label: 按鈕標籤
            emoji: 按鈕表情符號
        """
        self.panel = panel
        self.status = status

        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            # 更新面板的狀態篩選
            current_data = self.panel.get_page_data("personal") or {}
            current_data["status_filter"] = self.status
            self.panel.set_page_data("personal", current_data)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[狀態篩選按鈕]狀態切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class PaginationButton(discord.ui.Button):
    """分頁導航按鈕組件.

    用於個人成就頁面的分頁導航.
    """

    def __init__(
        self,
        panel: AchievementPanel,
        *,
        direction: str,
        label: str,
        emoji: str | None = None,
        disabled: bool = False,
    ):
        """初始化分頁按鈕.

        Args:
            panel: 所屬的成就面板實例
            direction: 導航方向 ("prev", "next", "first", "last")
            label: 按鈕標籤
            emoji: 按鈕表情符號
            disabled: 是否禁用
        """
        self.panel = panel
        self.direction = direction

        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            # 獲取當前個人視圖
            personal_view = self.panel.view_manager.get_view("personal")

            # 根據方向調整頁面
            if self.direction == "prev":
                if personal_view.has_previous_page():
                    personal_view.set_page(personal_view.get_current_page() - 1)
            elif self.direction == "next":
                if personal_view.has_next_page():
                    personal_view.set_page(personal_view.get_current_page() + 1)
            elif self.direction == "first":
                personal_view.set_page(0)
            elif self.direction == "last":
                personal_view.set_page(personal_view.get_total_pages() - 1)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[分頁按鈕]分頁導航失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class PersonalCategorySelector(discord.ui.Select):
    """個人成就分類選擇器組件.

    用於個人成就頁面的分類篩選.
    """

    def __init__(self, panel: AchievementPanel, categories: list[dict[str, Any]]):
        """初始化個人成就分類選擇器.

        Args:
            panel: 所屬的成就面板實例
            categories: 可用的成就分類列表
        """
        self.panel = panel

        options = [
            discord.SelectOption(
                label="全部分類",
                description="顯示所有已獲得的成就",
                emoji="📋",
                value="all",
            )
        ]

        for category in categories[:24]:  # Discord 限制最多25個選項
            if category.get("user_achievements_count", 0) > 0:
                options.append(
                    discord.SelectOption(
                        label=category["name"],
                        description=f"已獲得 {category['user_achievements_count']} 個成就",
                        emoji="📁",
                        value=str(category["id"]),
                    )
                )

        super().__init__(
            placeholder="選擇成就分類進行篩選...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """選擇器回調處理."""
        try:
            selected_category = self.values[0]

            # 獲取個人視圖並設置分類篩選
            personal_view = self.panel.view_manager.get_view("personal")
            category_id = None if selected_category == "all" else int(selected_category)
            personal_view.set_category_filter(category_id)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[個人分類選擇器]分類切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class AchievementDetailModal(discord.ui.Modal):
    """成就詳情模態框組件.

    顯示成就的詳細資訊.
    """

    def __init__(self, achievement_data: dict[str, Any]):
        """初始化成就詳情模態框.

        Args:
            achievement_data: 成就資料
        """
        super().__init__(title=f"成就詳情: {achievement_data['name']}")

        self.achievement_data = achievement_data

        self.add_item(
            discord.ui.TextInput(
                label="成就名稱",
                default=achievement_data["name"],
                style=discord.TextStyle.short,
                required=False,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="成就描述",
                default=achievement_data["description"],
                style=discord.TextStyle.paragraph,
                required=False,
            )
        )

        if "points" in achievement_data:
            self.add_item(
                discord.ui.TextInput(
                    label="獲得點數",
                    default=str(achievement_data["points"]),
                    style=discord.TextStyle.short,
                    required=False,
                )
            )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """模態框提交處理(關閉)."""
        await interaction.response.defer()

class AchievementProgressIndicator:
    """成就進度指示器組件.

    提供成就進度的視覺化顯示方法.
    """

    @staticmethod
    def create_progress_embed(
        achievement: dict[str, Any], current: int, target: int
    ) -> discord.Embed:
        """創建進度顯示 Embed.

        Args:
            achievement: 成就資料
            current: 當前進度
            target: 目標值

        Returns:
            discord.Embed: 進度顯示 Embed
        """
        progress_percentage = min((current / target) * 100, 100) if target > 0 else 0

        embed = discord.Embed(
            title=f"🏆 {achievement['name']}",
            description=achievement.get("description", "無描述"),
            color=discord.Color.blue(),
        )

        # 添加進度條
        progress_bar = AchievementProgressIndicator._create_progress_bar(
            current, target
        )
        embed.add_field(
            name="📊 進度",
            value=f"{progress_bar}\n{current:,} / {target:,} ({progress_percentage:.1f}%)",
            inline=False,
        )

        # 添加分類和點數資訊
        if "category" in achievement:
            embed.add_field(name="📁 分類", value=achievement["category"], inline=True)

        if "points" in achievement:
            embed.add_field(
                name="💰 點數", value=f"{achievement['points']} 點", inline=True
            )

        return embed

    @staticmethod
    def _create_progress_bar(current: int, target: int, length: int = 20) -> str:
        """創建進度條字串.

        Args:
            current: 當前進度
            target: 目標值
            length: 進度條長度

        Returns:
            str: 進度條字串
        """
        if target <= 0:
            return "▓" * length

        progress_ratio = min(current / target, 1.0)
        filled_length = int(length * progress_ratio)

        filled = "▓" * filled_length
        empty = "░" * (length - filled_length)

        return f"{filled}{empty}"

class ComponentFactory:
    """UI 組件工廠類.

    提供統一的組件創建介面.
    """

    @staticmethod
    def create_page_selector(panel: AchievementPanel) -> PageSelector:
        """創建頁面選擇器.

        Args:
            panel: 成就面板實例

        Returns:
            PageSelector: 頁面選擇器組件
        """
        return PageSelector(panel)

    @staticmethod
    def create_navigation_button(
        panel: AchievementPanel, label: str, target_page: str, emoji: str | None = None
    ) -> NavigationButton:
        """創建導航按鈕.

        Args:
            panel: 成就面板實例
            label: 按鈕標籤
            target_page: 目標頁面
            emoji: 按鈕表情符號

        Returns:
            NavigationButton: 導航按鈕組件
        """
        return NavigationButton(
            panel, label=label, emoji=emoji, target_page=target_page
        )

    @staticmethod
    def create_refresh_button(panel: AchievementPanel) -> RefreshButton:
        """創建重新整理按鈕.

        Args:
            panel: 成就面板實例

        Returns:
            RefreshButton: 重新整理按鈕組件
        """
        return RefreshButton(panel)

    @staticmethod
    def create_close_button(panel: AchievementPanel) -> CloseButton:
        """創建關閉按鈕.

        Args:
            panel: 成就面板實例

        Returns:
            CloseButton: 關閉按鈕組件
        """
        return CloseButton(panel)

    @staticmethod
    def create_browser_category_selector(
        panel: AchievementPanel, categories: list[dict[str, Any]]
    ) -> BrowserCategorySelector:
        """創建瀏覽頁面分類選擇器.

        Args:
            panel: 成就面板實例
            categories: 可用分類列表

        Returns:
            BrowserCategorySelector: 瀏覽分類選擇器組件
        """
        return BrowserCategorySelector(panel, categories)

    @staticmethod
    def create_browser_pagination_buttons(
        panel: AchievementPanel, has_prev: bool = True, has_next: bool = True
    ) -> list[BrowserPaginationButton]:
        """創建瀏覽頁面分頁導航按鈕組.

        Args:
            panel: 成就面板實例
            has_prev: 是否有上一頁
            has_next: 是否有下一頁

        Returns:
            list[BrowserPaginationButton]: 分頁按鈕列表
        """
        return [
            BrowserPaginationButton(
                panel, direction="first", label="首頁", emoji="⏮️", disabled=not has_prev
            ),
            BrowserPaginationButton(
                panel,
                direction="prev",
                label="上一頁",
                emoji="◀️",
                disabled=not has_prev,
            ),
            BrowserPaginationButton(
                panel,
                direction="next",
                label="下一頁",
                emoji="▶️",
                disabled=not has_next,
            ),
            BrowserPaginationButton(
                panel, direction="last", label="末頁", emoji="⏭️", disabled=not has_next
            ),
        ]

    @staticmethod
    def create_achievement_detail_button(
        panel: AchievementPanel, achievement_data: dict[str, Any]
    ) -> AchievementBrowserDetailButton:
        """創建成就詳情按鈕.

        Args:
            panel: 成就面板實例
            achievement_data: 成就資料

        Returns:
            AchievementBrowserDetailButton: 成就詳情按鈕組件
        """
        return AchievementBrowserDetailButton(panel, achievement_data)

    @staticmethod
    def create_category_selector(
        panel: AchievementPanel, categories: list[dict[str, Any]]
    ) -> AchievementCategorySelector:
        """創建分類選擇器.

        Args:
            panel: 成就面板實例
            categories: 可用分類列表

        Returns:
            AchievementCategorySelector: 分類選擇器組件
        """
        return AchievementCategorySelector(panel, categories)

    @staticmethod
    def create_status_buttons(panel: AchievementPanel) -> list[AchievementStatusButton]:
        """創建狀態篩選按鈕組.

        Args:
            panel: 成就面板實例

        Returns:
            list[AchievementStatusButton]: 狀態篩選按鈕列表
        """
        return [
            AchievementStatusButton(panel, status="all", label="全部", emoji="📋"),
            AchievementStatusButton(panel, status="earned", label="已獲得", emoji="✅"),
            AchievementStatusButton(
                panel, status="not_earned", label="未獲得", emoji="⭕"
            ),
        ]

    @staticmethod
    def create_pagination_buttons(
        panel: AchievementPanel, has_prev: bool = True, has_next: bool = True
    ) -> list[PaginationButton]:
        """創建分頁導航按鈕組.

        Args:
            panel: 成就面板實例
            has_prev: 是否有上一頁
            has_next: 是否有下一頁

        Returns:
            list[PaginationButton]: 分頁按鈕列表
        """
        return [
            PaginationButton(
                panel, direction="first", label="首頁", emoji="⏮️", disabled=not has_prev
            ),
            PaginationButton(
                panel,
                direction="prev",
                label="上一頁",
                emoji="◀️",
                disabled=not has_prev,
            ),
            PaginationButton(
                panel,
                direction="next",
                label="下一頁",
                emoji="▶️",
                disabled=not has_next,
            ),
            PaginationButton(
                panel, direction="last", label="末頁", emoji="⏭️", disabled=not has_next
            ),
        ]

    @staticmethod
    def create_personal_category_selector(
        panel: AchievementPanel, categories: list[dict[str, Any]]
    ) -> PersonalCategorySelector:
        """創建個人成就分類選擇器.

        Args:
            panel: 成就面板實例
            categories: 可用分類列表

        Returns:
            PersonalCategorySelector: 個人分類選擇器組件
        """
        return PersonalCategorySelector(panel, categories)

    @staticmethod
    def create_achievement_detail_modal(
        achievement_data: dict[str, Any],
    ) -> AchievementDetailModal:
        """創建成就詳情模態框.

        Args:
            achievement_data: 成就資料

        Returns:
            AchievementDetailModal: 成就詳情模態框組件
        """
        return AchievementDetailModal(achievement_data)

    @staticmethod
    def create_leaderboard_type_selector(
        panel: AchievementPanel, categories: list[dict[str, Any]] | None = None
    ) -> LeaderboardTypeSelector:
        """創建排行榜類型選擇器.

        Args:
            panel: 成就面板實例
            categories: 可用分類列表

        Returns:
            LeaderboardTypeSelector: 排行榜類型選擇器組件
        """
        return LeaderboardTypeSelector(panel, categories)

    @staticmethod
    def create_leaderboard_pagination_buttons(
        panel: AchievementPanel, has_prev: bool = True, has_next: bool = True
    ) -> list[LeaderboardPaginationButton]:
        """創建排行榜分頁導航按鈕組.

        Args:
            panel: 成就面板實例
            has_prev: 是否有上一頁
            has_next: 是否有下一頁

        Returns:
            list[LeaderboardPaginationButton]: 分頁按鈕列表
        """
        return [
            LeaderboardPaginationButton(
                panel, direction="first", label="首頁", emoji="⏮️", disabled=not has_prev
            ),
            LeaderboardPaginationButton(
                panel,
                direction="prev",
                label="上一頁",
                emoji="◀️",
                disabled=not has_prev,
            ),
            LeaderboardPaginationButton(
                panel,
                direction="next",
                label="下一頁",
                emoji="▶️",
                disabled=not has_next,
            ),
            LeaderboardPaginationButton(
                panel, direction="last", label="末頁", emoji="⏭️", disabled=not has_next
            ),
        ]

class LeaderboardTypeSelector(discord.ui.Select):
    """排行榜類型選擇器組件.

    用於排行榜頁面的類型切換.
    """

    def __init__(
        self, panel: AchievementPanel, categories: list[dict[str, Any]] | None = None
    ):
        """初始化排行榜類型選擇器.

        Args:
            panel: 所屬的成就面板實例
            categories: 可用的成就分類列表(可選)
        """
        self.panel = panel
        self.categories = categories or []

        options = [
            discord.SelectOption(
                label="成就總數排行榜",
                description="按獲得成就總數排序",
                emoji="🏅",
                value="count",
            ),
            discord.SelectOption(
                label="成就點數排行榜",
                description="按獲得成就點數排序",
                emoji="💎",
                value="points",
            ),
        ]

        for category in self.categories[:3]:
            options.append(
                discord.SelectOption(
                    label=f"{category['name']} 排行榜",
                    description=f"按 {category['name']} 分類成就數排序",
                    emoji="📁",
                    value=f"category_{category['id']}",
                )
            )

        super().__init__(
            placeholder="選擇排行榜類型...", options=options, min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """選擇器回調處理."""
        try:
            selected_type = self.values[0]

            # 獲取排行榜視圖並設置類型
            leaderboard_view = self.panel.view_manager.get_view("leaderboard")

            if selected_type.startswith("category_"):
                category_id = int(selected_type.split("_")[1])
                leaderboard_view.set_leaderboard_type("category", category_id)
            else:
                leaderboard_view.set_leaderboard_type(selected_type)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[排行榜類型選擇器]類型切換失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class LeaderboardPaginationButton(discord.ui.Button):
    """排行榜分頁按鈕組件.

    專為排行榜頁面設計的分頁導航功能.
    """

    def __init__(
        self,
        panel: AchievementPanel,
        *,
        direction: str,
        label: str,
        emoji: str | None = None,
        disabled: bool = False,
    ):
        """初始化排行榜分頁按鈕.

        Args:
            panel: 所屬的成就面板實例
            direction: 導航方向 ("prev", "next", "first", "last")
            label: 按鈕標籤
            emoji: 按鈕表情符號
            disabled: 是否禁用
        """
        self.panel = panel
        self.direction = direction

        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """按鈕回調處理."""
        try:
            # 獲取排行榜視圖
            leaderboard_view = self.panel.view_manager.get_view("leaderboard")

            # 根據方向調整頁面
            if self.direction == "prev":
                if leaderboard_view.has_previous_page():
                    leaderboard_view.set_page(leaderboard_view.get_current_page() - 1)
            elif self.direction == "next":
                if leaderboard_view.has_next_page():
                    leaderboard_view.set_page(leaderboard_view.get_current_page() + 1)
            elif self.direction == "first":
                leaderboard_view.set_page(0)
            elif self.direction == "last":
                leaderboard_view.set_page(leaderboard_view.get_total_pages() - 1)

            # 重新載入頁面
            await self.panel.refresh_callback(interaction)

        except Exception as e:
            logger.error(f"[排行榜分頁按鈕]分頁導航失敗: {e}")
            await self.panel.on_error(interaction, e, self)

class ComponentManager:
    """組件管理器.

    負責管理面板中的 UI 組件狀態和生命週期.
    """

    def __init__(self, panel: AchievementPanel):
        """初始化組件管理器.

        Args:
            panel: 成就面板實例
        """
        self.panel = panel
        self._components: dict[str, discord.ui.Item] = {}

    def register_component(self, name: str, component: discord.ui.Item) -> None:
        """註冊組件.

        Args:
            name: 組件名稱
            component: 組件實例
        """
        self._components[name] = component

    def get_component(self, name: str) -> discord.ui.Item | None:
        """獲取組件.

        Args:
            name: 組件名稱

        Returns:
            discord.ui.Item | None: 組件實例或 None
        """
        return self._components.get(name)

    def update_component_state(self, name: str, **kwargs: Any) -> None:
        """更新組件狀態.

        Args:
            name: 組件名稱
            **kwargs: 狀態更新參數
        """
        component = self._components.get(name)
        if component:
            for key, value in kwargs.items():
                if hasattr(component, key):
                    setattr(component, key, value)

    def clear_components(self) -> None:
        """清除所有組件."""
        self._components.clear()
