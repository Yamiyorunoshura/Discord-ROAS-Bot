"""成就瀏覽組件單元測試.

此模組測試成就瀏覽相關的 UI 組件：
- BrowserCategorySelector
- BrowserPaginationButton
- AchievementBrowserDetailButton
- AchievementProgressIndicatorView
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cogs.achievement.panel.components import (
    AchievementBrowserDetailButton,
    AchievementProgressIndicatorView,
    BrowserCategorySelector,
    BrowserPaginationButton,
    ComponentFactory,
)


class TestBrowserCategorySelector:
    """BrowserCategorySelector 測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬面板."""
        panel = MagicMock()
        panel.view_manager = MagicMock()
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    @pytest.fixture
    def mock_categories(self) -> list[dict[str, Any]]:
        """創建模擬分類資料."""
        return [
            {"id": 1, "name": "活動成就", "count": 15, "icon_emoji": "🎯"},
            {"id": 2, "name": "社交成就", "count": 12, "icon_emoji": "👥"},
            {"id": 3, "name": "時間成就", "count": 8, "icon_emoji": "⏰"},
        ]

    def test_init(self, mock_panel: MagicMock, mock_categories: list[dict[str, Any]]):
        """測試初始化."""
        selector = BrowserCategorySelector(mock_panel, mock_categories)

        assert selector.panel == mock_panel
        assert len(selector.options) == 4  # 3 個分類 + 1 個 "全部分類"

        # 驗證選項內容
        all_option = selector.options[0]
        assert all_option.label == "全部分類"
        assert all_option.value == "all"
        assert all_option.emoji.name == "📋"

        first_category = selector.options[1]
        assert first_category.label == "活動成就"
        assert first_category.value == "1"
        assert first_category.description == "共 15 個成就"

    @pytest.mark.asyncio
    async def test_callback_select_all(self, mock_panel: MagicMock, mock_categories: list[dict[str, Any]]):
        """測試選擇全部分類."""
        selector = BrowserCategorySelector(mock_panel, mock_categories)
        selector.values = ["all"]

        mock_browser_view = MagicMock()
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await selector.callback(mock_interaction)

        # 驗證調用
        mock_panel.view_manager.get_view.assert_called_with("browse")
        mock_browser_view.set_category_filter.assert_called_with(None)
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_select_category(self, mock_panel: MagicMock, mock_categories: list[dict[str, Any]]):
        """測試選擇特定分類."""
        selector = BrowserCategorySelector(mock_panel, mock_categories)
        selector.values = ["2"]  # 選擇社交成就

        mock_browser_view = MagicMock()
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await selector.callback(mock_interaction)

        # 驗證調用
        mock_browser_view.set_category_filter.assert_called_with(2)
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, mock_panel: MagicMock, mock_categories: list[dict[str, Any]]):
        """測試回調錯誤處理."""
        selector = BrowserCategorySelector(mock_panel, mock_categories)
        selector.values = ["1"]

        # 模擬錯誤
        mock_panel.view_manager.get_view.side_effect = Exception("測試錯誤")

        mock_interaction = AsyncMock()

        # 執行回調
        await selector.callback(mock_interaction)

        # 驗證錯誤處理
        mock_panel.on_error.assert_called_once()


class TestBrowserPaginationButton:
    """BrowserPaginationButton 測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬面板."""
        panel = MagicMock()
        panel.view_manager = MagicMock()
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    def test_init(self, mock_panel: MagicMock):
        """測試初始化."""
        button = BrowserPaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️",
            disabled=False
        )

        assert button.panel == mock_panel
        assert button.direction == "next"
        assert button.label == "下一頁"
        assert button.emoji.name == "▶️"
        assert button.disabled is False

    @pytest.mark.asyncio
    async def test_callback_next_page(self, mock_panel: MagicMock):
        """測試下一頁按鈕."""
        button = BrowserPaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️"
        )

        mock_browser_view = MagicMock()
        mock_browser_view.has_next_page.return_value = True
        mock_browser_view.get_current_page.return_value = 1
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_browser_view.set_page.assert_called_with(2)
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_prev_page(self, mock_panel: MagicMock):
        """測試上一頁按鈕."""
        button = BrowserPaginationButton(
            mock_panel,
            direction="prev",
            label="上一頁",
            emoji="◀️"
        )

        mock_browser_view = MagicMock()
        mock_browser_view.has_previous_page.return_value = True
        mock_browser_view.get_current_page.return_value = 2
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_browser_view.set_page.assert_called_with(1)
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_first_page(self, mock_panel: MagicMock):
        """測試首頁按鈕."""
        button = BrowserPaginationButton(
            mock_panel,
            direction="first",
            label="首頁",
            emoji="⏮️"
        )

        mock_browser_view = MagicMock()
        mock_browser_view.get_total_pages.return_value = 5
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_browser_view.set_page.assert_called_with(0)
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_last_page(self, mock_panel: MagicMock):
        """測試末頁按鈕."""
        button = BrowserPaginationButton(
            mock_panel,
            direction="last",
            label="末頁",
            emoji="⏭️"
        )

        mock_browser_view = MagicMock()
        mock_browser_view.get_total_pages.return_value = 5
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_browser_view.set_page.assert_called_with(4)  # 最後一頁是 index 4
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_callback_no_next_page(self, mock_panel: MagicMock):
        """測試沒有下一頁時的行為."""
        button = BrowserPaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️"
        )

        mock_browser_view = MagicMock()
        mock_browser_view.has_next_page.return_value = False
        mock_panel.view_manager.get_view.return_value = mock_browser_view

        mock_interaction = AsyncMock()

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證不會調用 set_page
        mock_browser_view.set_page.assert_not_called()
        mock_panel.refresh_callback.assert_called_with(mock_interaction)


class TestAchievementBrowserDetailButton:
    """AchievementBrowserDetailButton 測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬面板."""
        panel = MagicMock()
        panel.on_error = AsyncMock()
        return panel

    @pytest.fixture
    def mock_achievement_data(self) -> dict[str, Any]:
        """創建模擬成就資料."""
        return {
            "id": 1,
            "name": "測試成就名稱很長可能會被截斷",
            "description": "這是一個測試成就的描述",
            "points": 100,
            "criteria": {"target_value": 50},
            "role_reward": None,
            "is_hidden": False
        }

    def test_init(self, mock_panel: MagicMock, mock_achievement_data: dict[str, Any]):
        """測試初始化."""
        button = AchievementBrowserDetailButton(mock_panel, mock_achievement_data)

        assert button.panel == mock_panel
        assert button.achievement_data == mock_achievement_data
        assert button.label == "測試成就名稱很長可能會被截斷"[:20] + "..."  # 標籤會被截斷
        assert button.emoji.name == "ℹ️"

    @pytest.mark.asyncio
    async def test_callback_success(self, mock_panel: MagicMock, mock_achievement_data: dict[str, Any]):
        """測試成功顯示詳情."""
        button = AchievementBrowserDetailButton(mock_panel, mock_achievement_data)

        mock_interaction = AsyncMock()
        mock_modal = MagicMock()

        with patch('src.cogs.achievement.panel.components.ComponentFactory.create_achievement_detail_modal') as mock_create_modal:
            mock_create_modal.return_value = mock_modal

            # 執行回調
            await button.callback(mock_interaction)

            # 驗證調用
            mock_create_modal.assert_called_with(mock_achievement_data)
            mock_interaction.response.send_modal.assert_called_with(mock_modal)

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, mock_panel: MagicMock, mock_achievement_data: dict[str, Any]):
        """測試錯誤處理."""
        button = AchievementBrowserDetailButton(mock_panel, mock_achievement_data)

        mock_interaction = AsyncMock()
        mock_interaction.response.send_modal.side_effect = Exception("測試錯誤")

        with patch('src.cogs.achievement.panel.components.ComponentFactory.create_achievement_detail_modal'):
            # 執行回調
            await button.callback(mock_interaction)

            # 驗證錯誤處理
            mock_panel.on_error.assert_called_once()


class TestAchievementProgressIndicatorView:
    """AchievementProgressIndicatorView 測試類別."""

    @pytest.fixture
    def mock_achievement(self) -> dict[str, Any]:
        """模擬成就資料."""
        return {
            "id": 1,
            "name": "測試成就",
            "description": "這是一個測試成就的描述",
            "points": 100,
            "criteria": {"count": 50},
            "role_reward": None,
            "is_hidden": False
        }

    def test_create_progress_embed_field_no_progress(self, mock_achievement: dict[str, Any]):
        """測試無進度的欄位創建."""
        field = AchievementProgressIndicatorView.create_progress_embed_field(
            mock_achievement, None
        )

        assert field["name"] == "🎯 測試成就"
        assert "這是一個測試成就" in field["value"]
        assert "50 點" in field["value"]

    def test_create_progress_embed_field_with_progress(self, mock_achievement: dict[str, Any]):
        """測試有進度的欄位創建."""
        progress = {
            "current": 30,
            "target": 100,
            "percentage": 30
        }

        field = AchievementProgressIndicatorView.create_progress_embed_field(
            mock_achievement, progress
        )

        assert "⏳ 測試成就 (30%)" in field["name"]
        assert "30/100" in field["value"]
        assert "█" in field["value"]  # 進度條應該包含填充字符
        assert "░" in field["value"]  # 進度條應該包含空白字符

    def test_create_visual_progress_bar(self):
        """測試視覺化進度條創建."""
        # 測試 50% 進度
        bar = AchievementProgressIndicatorView._create_visual_progress_bar(50, 100, 10)
        assert len(bar) == 12  # [進度條] 格式，所以是 10 + 2
        assert "█" in bar
        assert "░" in bar

        # 測試 100% 進度
        bar = AchievementProgressIndicatorView._create_visual_progress_bar(100, 100, 10)
        assert bar.count("█") == 10  # 應該全部填滿
        assert "░" not in bar

        # 測試 0% 進度
        bar = AchievementProgressIndicatorView._create_visual_progress_bar(0, 100, 10)
        assert "█" not in bar
        assert bar.count("░") == 10

        # 測試目標為 0 的情況
        bar = AchievementProgressIndicatorView._create_visual_progress_bar(50, 0, 10)
        assert bar.count("▓") == 10


class TestComponentFactory:
    """ComponentFactory 測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """創建模擬面板."""
        return MagicMock()

    def test_create_browser_category_selector(self, mock_panel: MagicMock):
        """測試創建瀏覽分類選擇器."""
        categories = [{"id": 1, "name": "測試分類", "count": 5}]

        selector = ComponentFactory.create_browser_category_selector(mock_panel, categories)

        assert isinstance(selector, BrowserCategorySelector)
        assert selector.panel == mock_panel

    def test_create_browser_pagination_buttons(self, mock_panel: MagicMock):
        """測試創建瀏覽分頁按鈕組."""
        buttons = ComponentFactory.create_browser_pagination_buttons(
            mock_panel, has_prev=True, has_next=False
        )

        assert len(buttons) == 4  # 首頁、上一頁、下一頁、末頁
        assert all(isinstance(btn, BrowserPaginationButton) for btn in buttons)

        # 檢查禁用狀態
        next_button = next(btn for btn in buttons if btn.direction == "next")
        prev_button = next(btn for btn in buttons if btn.direction == "prev")

        assert next_button.disabled is True
        assert prev_button.disabled is False

    def test_create_achievement_detail_button(self, mock_panel: MagicMock):
        """測試創建成就詳情按鈕."""
        achievement_data = {"name": "測試成就", "description": "描述"}

        button = ComponentFactory.create_achievement_detail_button(mock_panel, achievement_data)

        assert isinstance(button, AchievementBrowserDetailButton)
        assert button.panel == mock_panel
        assert button.achievement_data == achievement_data


class TestComponentsIntegration:
    """組件整合測試."""

    @pytest.mark.asyncio
    async def test_category_and_pagination_interaction(self):
        """測試分類選擇和分頁的互動."""
        # 這裡可以測試分類選擇後分頁的重置行為
        pass

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """測試錯誤傳播機制."""
        # 測試組件錯誤如何正確傳播到面板
        pass
