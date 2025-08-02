"""成就系統面板組件測試.

測試成就面板的 UI 組件功能：
- 頁面選擇器組件
- 導航按鈕組件
- 分類選擇器組件
- 組件工廠和管理器
"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.cogs.achievement.panel.components import (
    AchievementCategorySelector,
    AchievementStatusButton,
    CloseButton,
    ComponentFactory,
    ComponentManager,
    NavigationButton,
    PageSelector,
    RefreshButton,
)


class TestPageSelector:
    """頁面選擇器組件測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        panel = MagicMock()
        panel.change_page = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    def test_page_selector_initialization(self, mock_panel):
        """測試頁面選擇器初始化."""
        selector = PageSelector(mock_panel)

        assert selector.panel is mock_panel
        assert selector.placeholder == "選擇要查看的頁面..."
        assert len(selector.options) == 3

        # 檢查選項內容
        option_values = [opt.value for opt in selector.options]
        assert "personal" in option_values
        assert "browse" in option_values
        assert "leaderboard" in option_values

    @pytest.mark.asyncio
    async def test_page_selector_callback_success(self, mock_panel):
        """測試頁面選擇器回調成功。"""
        selector = PageSelector(mock_panel)
        selector.values = ["personal"]

        mock_interaction = MagicMock()

        await selector.callback(mock_interaction)

        mock_panel.change_page.assert_called_once_with(mock_interaction, "personal")

    @pytest.mark.asyncio
    async def test_page_selector_callback_error(self, mock_panel):
        """測試頁面選擇器回調錯誤處理。"""
        selector = PageSelector(mock_panel)
        selector.values = ["personal"]

        mock_interaction = MagicMock()
        mock_panel.change_page.side_effect = Exception("Page change failed")

        await selector.callback(mock_interaction)

        mock_panel.on_error.assert_called_once()


class TestNavigationButton:
    """導航按鈕組件測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        panel = MagicMock()
        panel.change_page = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    def test_navigation_button_initialization(self, mock_panel):
        """測試導航按鈕初始化."""
        button = NavigationButton(
            mock_panel,
            label="返回主頁",
            emoji="🏠",
            target_page="main",
            style=discord.ButtonStyle.primary
        )

        assert button.panel is mock_panel
        assert button.target_page == "main"
        assert button.label == "返回主頁"
        assert button.emoji == "🏠"
        assert button.style == discord.ButtonStyle.primary

    @pytest.mark.asyncio
    async def test_navigation_button_callback_success(self, mock_panel):
        """測試導航按鈕回調成功。"""
        button = NavigationButton(
            mock_panel,
            label="測試",
            target_page="test"
        )

        mock_interaction = MagicMock()

        await button.callback(mock_interaction)

        mock_panel.change_page.assert_called_once_with(mock_interaction, "test")

    @pytest.mark.asyncio
    async def test_navigation_button_callback_error(self, mock_panel):
        """測試導航按鈕回調錯誤處理。"""
        button = NavigationButton(
            mock_panel,
            label="測試",
            target_page="test"
        )

        mock_interaction = MagicMock()
        mock_panel.change_page.side_effect = Exception("Navigation failed")

        await button.callback(mock_interaction)

        mock_panel.on_error.assert_called_once()


class TestRefreshButton:
    """重新整理按鈕組件測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        panel = MagicMock()
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    def test_refresh_button_initialization(self, mock_panel):
        """測試重新整理按鈕初始化."""
        button = RefreshButton(mock_panel)

        assert button.panel is mock_panel
        assert button.label == "重新整理"
        assert button.emoji == "🔄"
        assert button.style == discord.ButtonStyle.secondary

    @pytest.mark.asyncio
    async def test_refresh_button_callback_success(self, mock_panel):
        """測試重新整理按鈕回調成功。"""
        button = RefreshButton(mock_panel)
        mock_interaction = MagicMock()

        await button.callback(mock_interaction)

        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_refresh_button_callback_error(self, mock_panel):
        """測試重新整理按鈕回調錯誤處理。"""
        button = RefreshButton(mock_panel)
        mock_interaction = MagicMock()
        mock_panel.refresh_callback.side_effect = Exception("Refresh failed")

        await button.callback(mock_interaction)

        mock_panel.on_error.assert_called_once()


class TestCloseButton:
    """關閉按鈕組件測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        panel = MagicMock()
        panel.close_callback = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    def test_close_button_initialization(self, mock_panel):
        """測試關閉按鈕初始化."""
        button = CloseButton(mock_panel)

        assert button.panel is mock_panel
        assert button.label == "關閉"
        assert button.emoji == "❌"
        assert button.style == discord.ButtonStyle.danger

    @pytest.mark.asyncio
    async def test_close_button_callback_success(self, mock_panel):
        """測試關閉按鈕回調成功。"""
        button = CloseButton(mock_panel)
        mock_interaction = MagicMock()

        await button.callback(mock_interaction)

        mock_panel.close_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_close_button_callback_error(self, mock_panel):
        """測試關閉按鈕回調錯誤處理。"""
        button = CloseButton(mock_panel)
        mock_interaction = MagicMock()
        mock_panel.close_callback.side_effect = Exception("Close failed")

        await button.callback(mock_interaction)

        mock_panel.on_error.assert_called_once()


class TestAchievementCategorySelector:
    """成就分類選擇器組件測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        panel = MagicMock()
        panel.set_page_data = MagicMock()
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    @pytest.fixture
    def sample_categories(self):
        """樣本分類資料."""
        return [
            {"id": 1, "name": "活動成就", "count": 8},
            {"id": 2, "name": "社交成就", "count": 6},
            {"id": 3, "name": "時間成就", "count": 4}
        ]

    def test_category_selector_initialization(self, mock_panel, sample_categories):
        """測試分類選擇器初始化."""
        selector = AchievementCategorySelector(mock_panel, sample_categories)

        assert selector.panel is mock_panel
        assert selector.placeholder == "選擇成就分類..."
        assert len(selector.options) == 4  # 3個分類 + 1個"全部"選項

        # 檢查第一個選項是"全部"
        assert selector.options[0].value == "all"
        assert selector.options[0].label == "全部"

    @pytest.mark.asyncio
    async def test_category_selector_callback_success(self, mock_panel, sample_categories):
        """測試分類選擇器回調成功。"""
        selector = AchievementCategorySelector(mock_panel, sample_categories)
        selector.values = ["1"]

        mock_interaction = MagicMock()

        await selector.callback(mock_interaction)

        mock_panel.set_page_data.assert_called_once_with("browse", {
            "selected_category": "1"
        })
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_category_selector_callback_error(self, mock_panel, sample_categories):
        """測試分類選擇器回調錯誤處理。"""
        selector = AchievementCategorySelector(mock_panel, sample_categories)
        selector.values = ["1"]

        mock_interaction = MagicMock()
        mock_panel.refresh_callback.side_effect = Exception("Refresh failed")

        await selector.callback(mock_interaction)

        mock_panel.on_error.assert_called_once()


class TestAchievementStatusButton:
    """成就狀態篩選按鈕測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        panel = MagicMock()
        panel.get_page_data = MagicMock(return_value={})
        panel.set_page_data = MagicMock()
        panel.refresh_callback = AsyncMock()
        panel.on_error = AsyncMock()
        return panel

    def test_status_button_initialization(self, mock_panel):
        """測試狀態篩選按鈕初始化."""
        button = AchievementStatusButton(
            mock_panel,
            status="earned",
            label="已獲得",
            emoji="✅"
        )

        assert button.panel is mock_panel
        assert button.status == "earned"
        assert button.label == "已獲得"
        assert button.emoji == "✅"
        assert button.style == discord.ButtonStyle.primary

    @pytest.mark.asyncio
    async def test_status_button_callback_success(self, mock_panel):
        """測試狀態篩選按鈕回調成功。"""
        button = AchievementStatusButton(
            mock_panel,
            status="earned",
            label="已獲得"
        )

        mock_interaction = MagicMock()

        await button.callback(mock_interaction)

        mock_panel.get_page_data.assert_called_once_with("personal")
        mock_panel.set_page_data.assert_called_once()
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_status_button_callback_error(self, mock_panel):
        """測試狀態篩選按鈕回調錯誤處理。"""
        button = AchievementStatusButton(
            mock_panel,
            status="earned",
            label="已獲得"
        )

        mock_interaction = MagicMock()
        mock_panel.refresh_callback.side_effect = Exception("Refresh failed")

        await button.callback(mock_interaction)

        mock_panel.on_error.assert_called_once()


class TestComponentFactory:
    """組件工廠測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        return MagicMock()

    def test_create_page_selector(self, mock_panel):
        """測試創建頁面選擇器。"""
        selector = ComponentFactory.create_page_selector(mock_panel)

        assert isinstance(selector, PageSelector)
        assert selector.panel is mock_panel

    def test_create_navigation_button(self, mock_panel):
        """測試創建導航按鈕。"""
        button = ComponentFactory.create_navigation_button(
            mock_panel,
            "測試按鈕",
            "test_page",
            "🧪"
        )

        assert isinstance(button, NavigationButton)
        assert button.panel is mock_panel
        assert button.label == "測試按鈕"
        assert button.target_page == "test_page"
        assert button.emoji == "🧪"

    def test_create_refresh_button(self, mock_panel):
        """測試創建重新整理按鈕。"""
        button = ComponentFactory.create_refresh_button(mock_panel)

        assert isinstance(button, RefreshButton)
        assert button.panel is mock_panel

    def test_create_close_button(self, mock_panel):
        """測試創建關閉按鈕。"""
        button = ComponentFactory.create_close_button(mock_panel)

        assert isinstance(button, CloseButton)
        assert button.panel is mock_panel

    def test_create_category_selector(self, mock_panel):
        """測試創建分類選擇器。"""
        categories = [{"id": 1, "name": "測試", "count": 5}]
        selector = ComponentFactory.create_category_selector(mock_panel, categories)

        assert isinstance(selector, AchievementCategorySelector)
        assert selector.panel is mock_panel

    def test_create_status_buttons(self, mock_panel):
        """測試創建狀態篩選按鈕組。"""
        buttons = ComponentFactory.create_status_buttons(mock_panel)

        assert len(buttons) == 3
        assert all(isinstance(btn, AchievementStatusButton) for btn in buttons)

        statuses = [btn.status for btn in buttons]
        assert "all" in statuses
        assert "earned" in statuses
        assert "not_earned" in statuses


class TestComponentManager:
    """組件管理器測試."""

    @pytest.fixture
    def mock_panel(self):
        """模擬成就面板."""
        return MagicMock()

    @pytest.fixture
    def component_manager(self, mock_panel):
        """組件管理器實例."""
        return ComponentManager(mock_panel)

    def test_component_manager_initialization(self, mock_panel):
        """測試組件管理器初始化。"""
        manager = ComponentManager(mock_panel)

        assert manager.panel is mock_panel
        assert len(manager._components) == 0

    def test_register_component(self, component_manager):
        """測試註冊組件。"""
        mock_component = MagicMock()

        component_manager.register_component("test_component", mock_component)

        assert "test_component" in component_manager._components
        assert component_manager._components["test_component"] is mock_component

    def test_get_component_exists(self, component_manager):
        """測試獲取存在的組件。"""
        mock_component = MagicMock()
        component_manager.register_component("test_component", mock_component)

        result = component_manager.get_component("test_component")

        assert result is mock_component

    def test_get_component_not_exists(self, component_manager):
        """測試獲取不存在的組件。"""
        result = component_manager.get_component("nonexistent")

        assert result is None

    def test_update_component_state(self, component_manager):
        """測試更新組件狀態。"""
        mock_component = MagicMock()
        mock_component.disabled = False
        mock_component.label = "原標籤"

        component_manager.register_component("test_component", mock_component)

        component_manager.update_component_state(
            "test_component",
            disabled=True,
            label="新標籤"
        )

        assert mock_component.disabled is True
        assert mock_component.label == "新標籤"

    def test_update_component_state_invalid_attribute(self, component_manager):
        """測試更新組件無效屬性。"""
        mock_component = MagicMock()
        del mock_component.nonexistent_attr  # 確保屬性不存在

        component_manager.register_component("test_component", mock_component)

        # 應該不會拋出異常
        component_manager.update_component_state(
            "test_component",
            nonexistent_attr="value"
        )

    def test_clear_components(self, component_manager):
        """測試清除所有組件。"""
        mock_component1 = MagicMock()
        mock_component2 = MagicMock()

        component_manager.register_component("component1", mock_component1)
        component_manager.register_component("component2", mock_component2)

        assert len(component_manager._components) == 2

        component_manager.clear_components()

        assert len(component_manager._components) == 0


class TestComponentIntegration:
    """組件整合測試."""

    @pytest.mark.asyncio
    async def test_complete_page_navigation_flow(self):
        """測試完整的頁面導航流程。"""
        mock_panel = MagicMock()
        mock_panel.change_page = AsyncMock()

        # 創建頁面選擇器
        selector = PageSelector(mock_panel)
        selector.values = ["personal"]

        mock_interaction = MagicMock()

        # 執行頁面切換
        await selector.callback(mock_interaction)

        # 驗證頁面切換被呼叫
        mock_panel.change_page.assert_called_once_with(mock_interaction, "personal")

    def test_component_factory_integration(self):
        """測試組件工廠整合。"""
        mock_panel = MagicMock()

        # 創建所有類型的組件
        page_selector = ComponentFactory.create_page_selector(mock_panel)
        nav_button = ComponentFactory.create_navigation_button(mock_panel, "測試", "test")
        refresh_button = ComponentFactory.create_refresh_button(mock_panel)
        close_button = ComponentFactory.create_close_button(mock_panel)
        status_buttons = ComponentFactory.create_status_buttons(mock_panel)

        # 驗證所有組件都正確創建
        assert isinstance(page_selector, PageSelector)
        assert isinstance(nav_button, NavigationButton)
        assert isinstance(refresh_button, RefreshButton)
        assert isinstance(close_button, CloseButton)
        assert len(status_buttons) == 3

        # 驗證所有組件都關聯到同一個面板
        components = [page_selector, nav_button, refresh_button, close_button, *status_buttons]
        for component in components:
            assert component.panel is mock_panel
