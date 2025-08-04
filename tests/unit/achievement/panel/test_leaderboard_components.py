"""測試排行榜組件模組.

測試排行榜相關的 UI 組件功能.
"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.cogs.achievement.panel.components import (
    ComponentFactory,
    LeaderboardPaginationButton,
    LeaderboardTypeSelector,
)


class TestLeaderboardTypeSelector:
    """LeaderboardTypeSelector 測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬的成就面板."""
        panel = MagicMock()
        view_manager = MagicMock()
        leaderboard_view = MagicMock()

        view_manager.get_view.return_value = leaderboard_view
        panel.view_manager = view_manager
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()

        return panel

    @pytest.fixture
    def mock_categories(self) -> list[dict]:
        """創建模擬的分類資料."""
        return [
            {"id": 1, "name": "活動成就", "count": 10},
            {"id": 2, "name": "社交成就", "count": 8},
            {"id": 3, "name": "時間成就", "count": 5},
        ]

    def test_initialization_basic(self, mock_panel):
        """測試基本初始化."""
        selector = LeaderboardTypeSelector(mock_panel)

        # 驗證基本選項
        assert len(selector.options) == 2  # 總數 + 點數
        assert selector.options[0].value == "count"
        assert selector.options[1].value == "points"
        assert selector.placeholder == "選擇排行榜類型..."

    def test_initialization_with_categories(self, mock_panel, mock_categories):
        """測試包含分類的初始化."""
        selector = LeaderboardTypeSelector(mock_panel, mock_categories)

        # 驗證選項數量(基本2個 + 分類3個)
        assert len(selector.options) == 5

        # 驗證分類選項
        category_options = selector.options[2:]
        assert category_options[0].value == "category_1"
        assert category_options[0].label == "活動成就 排行榜"
        assert category_options[1].value == "category_2"
        assert category_options[2].value == "category_3"

    def test_initialization_limits_categories(self, mock_panel):
        """測試分類數量限制(最多3個)."""
        # 創建大量分類
        many_categories = [
            {"id": i, "name": f"分類{i}", "count": 5} for i in range(1, 10)
        ]

        selector = LeaderboardTypeSelector(mock_panel, many_categories)

        # 驗證只添加了前3個分類
        assert len(selector.options) == 5  # 基本2個 + 分類3個
        assert selector.options[4].value == "category_3"

    @pytest.mark.asyncio
    async def test_callback_count_type(self, mock_panel):
        """測試選擇成就總數排行榜."""
        selector = LeaderboardTypeSelector(mock_panel)

        # 模擬互動
        mock_interaction = MagicMock(spec=discord.Interaction)

        # 直接設置內部屬性來模擬選擇
        selector._values = ["count"]

        await selector.callback(mock_interaction)

        # 驗證視圖設置
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_leaderboard_type.assert_called_once_with("count")

        # 驗證重新整理
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_points_type(self, mock_panel):
        """測試選擇成就點數排行榜."""
        selector = LeaderboardTypeSelector(mock_panel)

        mock_interaction = MagicMock(spec=discord.Interaction)

        # 直接設置內部屬性來模擬選擇
        selector._values = ["points"]

        await selector.callback(mock_interaction)

        # 驗證視圖設置
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_leaderboard_type.assert_called_once_with("points")

    @pytest.mark.asyncio
    async def test_callback_category_type(self, mock_panel):
        """測試選擇分類排行榜."""
        selector = LeaderboardTypeSelector(mock_panel)

        mock_interaction = MagicMock(spec=discord.Interaction)

        # 直接設置內部屬性來模擬選擇
        selector._values = ["category_42"]

        await selector.callback(mock_interaction)

        # 驗證視圖設置(分類類型需要傳遞分類ID)
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_leaderboard_type.assert_called_once_with("category", 42)

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, mock_panel):
        """測試回調錯誤處理."""
        selector = LeaderboardTypeSelector(mock_panel)

        # 模擬錯誤
        error = Exception("測試錯誤")
        mock_panel.refresh_callback.side_effect = error

        mock_interaction = MagicMock(spec=discord.Interaction)

        # 直接設置內部屬性來模擬選擇
        selector._values = ["count"]

        await selector.callback(mock_interaction)

        # 驗證錯誤處理
        mock_panel.on_error.assert_called_once_with(mock_interaction, error, selector)


class TestLeaderboardPaginationButton:
    """LeaderboardPaginationButton 測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬的成就面板."""
        panel = MagicMock()
        view_manager = MagicMock()
        leaderboard_view = MagicMock()

        # 設置分頁方法
        leaderboard_view.has_previous_page.return_value = True
        leaderboard_view.has_next_page.return_value = True
        leaderboard_view.get_current_page.return_value = 2
        leaderboard_view.get_total_pages.return_value = 5

        view_manager.get_view.return_value = leaderboard_view
        panel.view_manager = view_manager
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()

        return panel

    def test_initialization(self, mock_panel):
        """測試按鈕初始化."""
        button = LeaderboardPaginationButton(
            mock_panel, direction="next", label="下一頁", emoji="▶️", disabled=False
        )

        assert button.direction == "next"
        assert button.label == "下一頁"
        assert str(button.emoji) == "▶️"  # 比較字串表示
        assert not button.disabled
        assert button.style == discord.ButtonStyle.secondary

    @pytest.mark.asyncio
    async def test_callback_next_page(self, mock_panel):
        """測試下一頁按鈕."""
        button = LeaderboardPaginationButton(
            mock_panel, direction="next", label="下一頁", emoji="▶️"
        )

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證頁面設置
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_page.assert_called_once_with(3)  # 當前頁面2 + 1

        # 驗證重新整理
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_prev_page(self, mock_panel):
        """測試上一頁按鈕."""
        button = LeaderboardPaginationButton(
            mock_panel, direction="prev", label="上一頁", emoji="◀️"
        )

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證頁面設置
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_page.assert_called_once_with(1)  # 當前頁面2 - 1

    @pytest.mark.asyncio
    async def test_callback_first_page(self, mock_panel):
        """測試首頁按鈕."""
        button = LeaderboardPaginationButton(
            mock_panel, direction="first", label="首頁", emoji="⏮️"
        )

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證頁面設置
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_page.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_callback_last_page(self, mock_panel):
        """測試末頁按鈕."""
        button = LeaderboardPaginationButton(
            mock_panel, direction="last", label="末頁", emoji="⏭️"
        )

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證頁面設置
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.set_page.assert_called_once_with(4)  # 總頁數5 - 1

    @pytest.mark.asyncio
    async def test_callback_prev_boundary_check(self, mock_panel):
        """測試上一頁邊界檢查."""
        # 設置沒有上一頁
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.has_previous_page.return_value = False

        button = LeaderboardPaginationButton(
            mock_panel, direction="prev", label="上一頁", emoji="◀️"
        )

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證沒有設置頁面
        leaderboard_view.set_page.assert_not_called()

        # 但仍然重新整理
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_next_boundary_check(self, mock_panel):
        """測試下一頁邊界檢查."""
        # 設置沒有下一頁
        leaderboard_view = mock_panel.view_manager.get_view.return_value
        leaderboard_view.has_next_page.return_value = False

        button = LeaderboardPaginationButton(
            mock_panel, direction="next", label="下一頁", emoji="▶️"
        )

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證沒有設置頁面
        leaderboard_view.set_page.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, mock_panel):
        """測試回調錯誤處理."""
        button = LeaderboardPaginationButton(
            mock_panel, direction="next", label="下一頁", emoji="▶️"
        )

        # 模擬錯誤
        error = Exception("測試錯誤")
        mock_panel.refresh_callback.side_effect = error

        mock_interaction = MagicMock(spec=discord.Interaction)

        await button.callback(mock_interaction)

        # 驗證錯誤處理
        mock_panel.on_error.assert_called_once_with(mock_interaction, error, button)


class TestComponentFactory:
    """ComponentFactory 排行榜組件測試."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬的成就面板."""
        return MagicMock()

    def test_create_leaderboard_type_selector(self, mock_panel):
        """測試創建排行榜類型選擇器."""
        categories = [{"id": 1, "name": "測試分類", "count": 5}]

        selector = ComponentFactory.create_leaderboard_type_selector(
            mock_panel, categories
        )

        assert isinstance(selector, LeaderboardTypeSelector)
        assert selector.panel == mock_panel
        assert selector.categories == categories

    def test_create_leaderboard_type_selector_no_categories(self, mock_panel):
        """測試創建沒有分類的排行榜類型選擇器."""
        selector = ComponentFactory.create_leaderboard_type_selector(mock_panel)

        assert isinstance(selector, LeaderboardTypeSelector)
        assert selector.categories == []

    def test_create_leaderboard_pagination_buttons(self, mock_panel):
        """測試創建排行榜分頁按鈕組."""
        buttons = ComponentFactory.create_leaderboard_pagination_buttons(
            mock_panel, has_prev=True, has_next=True
        )

        assert len(buttons) == 4

        # 驗證按鈕順序和類型
        assert buttons[0].direction == "first"
        assert buttons[0].label == "首頁"
        assert not buttons[0].disabled

        assert buttons[1].direction == "prev"
        assert buttons[1].label == "上一頁"
        assert not buttons[1].disabled

        assert buttons[2].direction == "next"
        assert buttons[2].label == "下一頁"
        assert not buttons[2].disabled

        assert buttons[3].direction == "last"
        assert buttons[3].label == "末頁"
        assert not buttons[3].disabled

    def test_create_leaderboard_pagination_buttons_disabled(self, mock_panel):
        """測試創建禁用狀態的分頁按鈕組."""
        buttons = ComponentFactory.create_leaderboard_pagination_buttons(
            mock_panel, has_prev=False, has_next=False
        )

        # 驗證前兩個按鈕被禁用
        assert buttons[0].disabled  # first
        assert buttons[1].disabled  # prev

        # 驗證後兩個按鈕被禁用
        assert buttons[2].disabled  # next
        assert buttons[3].disabled  # last

    def test_create_leaderboard_pagination_buttons_partial_disabled(self, mock_panel):
        """測試創建部分禁用的分頁按鈕組."""
        buttons = ComponentFactory.create_leaderboard_pagination_buttons(
            mock_panel, has_prev=True, has_next=False
        )

        # 驗證只有 prev 相關按鈕啟用
        assert not buttons[0].disabled  # first - 啟用
        assert not buttons[1].disabled  # prev - 啟用
        assert buttons[2].disabled  # next - 禁用
        assert buttons[3].disabled  # last - 禁用
