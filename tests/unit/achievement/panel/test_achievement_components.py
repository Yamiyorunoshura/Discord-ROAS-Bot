"""成就系統組件測試模組.

測試分頁按鈕、分類選擇器等 UI 組件的功能。
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.cogs.achievement.panel.components import (
    AchievementProgressIndicator,
    ComponentFactory,
    PaginationButton,
    PersonalCategorySelector,
)


class TestPaginationButton:
    """分頁按鈕測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """模擬面板."""
        panel = MagicMock()
        panel.view_manager.get_view.return_value = MagicMock()
        return panel

    @pytest.fixture
    def mock_interaction(self) -> AsyncMock:
        """模擬 Discord 互動."""
        interaction = AsyncMock(spec=discord.Interaction)
        return interaction

    def test_pagination_button_init(self, mock_panel: MagicMock) -> None:
        """測試分頁按鈕初始化."""
        button = PaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️",
            disabled=False
        )

        assert button.panel == mock_panel
        assert button.direction == "next"
        assert button.label == "下一頁"
        assert button.emoji == "▶️"
        assert not button.disabled

    def test_pagination_button_disabled(self, mock_panel: MagicMock) -> None:
        """測試禁用狀態的分頁按鈕."""
        button = PaginationButton(
            mock_panel,
            direction="prev",
            label="上一頁",
            emoji="◀️",
            disabled=True
        )

        assert button.disabled

    @pytest.mark.asyncio
    async def test_pagination_button_callback_next(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock
    ) -> None:
        """測試下一頁按鈕回調."""
        # 設置模擬視圖
        mock_personal_view = MagicMock()
        mock_personal_view.has_next_page.return_value = True
        mock_personal_view.get_current_page.return_value = 0
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        button = PaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️"
        )

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_personal_view.set_page.assert_called_once_with(1)
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_pagination_button_callback_prev(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock
    ) -> None:
        """測試上一頁按鈕回調."""
        # 設置模擬視圖
        mock_personal_view = MagicMock()
        mock_personal_view.has_previous_page.return_value = True
        mock_personal_view.get_current_page.return_value = 2
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        button = PaginationButton(
            mock_panel,
            direction="prev",
            label="上一頁",
            emoji="◀️"
        )

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_personal_view.set_page.assert_called_once_with(1)
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_pagination_button_callback_first(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock
    ) -> None:
        """測試首頁按鈕回調."""
        mock_personal_view = MagicMock()
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        button = PaginationButton(
            mock_panel,
            direction="first",
            label="首頁",
            emoji="⏮️"
        )

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_personal_view.set_page.assert_called_once_with(0)
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_pagination_button_callback_last(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock
    ) -> None:
        """測試末頁按鈕回調."""
        mock_personal_view = MagicMock()
        mock_personal_view.get_total_pages.return_value = 5
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        button = PaginationButton(
            mock_panel,
            direction="last",
            label="末頁",
            emoji="⏭️"
        )

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證調用
        mock_personal_view.set_page.assert_called_once_with(4)
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_pagination_button_callback_no_movement(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock
    ) -> None:
        """測試無法移動時的按鈕回調."""
        # 設置模擬視圖（無下一頁）
        mock_personal_view = MagicMock()
        mock_personal_view.has_next_page.return_value = False
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        button = PaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️"
        )

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證沒有調用 set_page
        mock_personal_view.set_page.assert_not_called()
        # 但仍然應該刷新
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_pagination_button_callback_error(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock
    ) -> None:
        """測試分頁按鈕錯誤處理."""
        # 設置拋出錯誤的模擬
        mock_panel.view_manager.get_view.side_effect = Exception("View error")

        button = PaginationButton(
            mock_panel,
            direction="next",
            label="下一頁",
            emoji="▶️"
        )

        # 執行回調
        await button.callback(mock_interaction)

        # 驗證錯誤處理
        mock_panel.on_error.assert_called_once()


class TestPersonalCategorySelector:
    """個人分類選擇器測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """模擬面板."""
        panel = MagicMock()
        panel.view_manager.get_view.return_value = MagicMock()
        return panel

    @pytest.fixture
    def mock_interaction(self) -> AsyncMock:
        """模擬 Discord 互動."""
        interaction = AsyncMock(spec=discord.Interaction)
        return interaction

    @pytest.fixture
    def sample_categories(self) -> list[dict[str, Any]]:
        """範例分類資料."""
        return [
            {"id": 1, "name": "活動成就", "user_achievements_count": 5},
            {"id": 2, "name": "社交成就", "user_achievements_count": 3},
            {"id": 3, "name": "時間成就", "user_achievements_count": 0}  # 無成就的分類
        ]

    def test_category_selector_init(
        self,
        mock_panel: MagicMock,
        sample_categories: list[dict[str, Any]]
    ) -> None:
        """測試分類選擇器初始化."""
        selector = PersonalCategorySelector(mock_panel, sample_categories)

        assert selector.panel == mock_panel

        # 驗證選項（應該包含"全部"選項和有成就的分類）
        expected_options = 3  # 全部 + 活動成就 + 社交成就（時間成就被排除因為無成就）
        assert len(selector.options) == expected_options

        # 驗證"全部"選項
        all_option = selector.options[0]
        assert all_option.label == "全部分類"
        assert all_option.value == "all"

        # 驗證分類選項
        activity_option = next(opt for opt in selector.options if opt.value == "1")
        assert activity_option.label == "活動成就"
        assert "已獲得 5 個成就" in activity_option.description

    def test_category_selector_filters_empty_categories(
        self,
        mock_panel: MagicMock,
        sample_categories: list[dict[str, Any]]
    ) -> None:
        """測試分類選擇器過濾空分類."""
        selector = PersonalCategorySelector(mock_panel, sample_categories)

        # 驗證時間成就（無成就）被過濾掉
        category_values = [opt.value for opt in selector.options]
        assert "3" not in category_values  # 時間成就的 ID

    @pytest.mark.asyncio
    async def test_category_selector_callback_all(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock,
        sample_categories: list[dict[str, Any]]
    ) -> None:
        """測試選擇全部分類的回調."""
        mock_personal_view = MagicMock()
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        selector = PersonalCategorySelector(mock_panel, sample_categories)
        selector.values = ["all"]

        # 執行回調
        await selector.callback(mock_interaction)

        # 驗證調用
        mock_personal_view.set_category_filter.assert_called_once_with(None)
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_category_selector_callback_specific_category(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock,
        sample_categories: list[dict[str, Any]]
    ) -> None:
        """測試選擇特定分類的回調."""
        mock_personal_view = MagicMock()
        mock_panel.view_manager.get_view.return_value = mock_personal_view

        selector = PersonalCategorySelector(mock_panel, sample_categories)
        selector.values = ["1"]  # 活動成就

        # 執行回調
        await selector.callback(mock_interaction)

        # 驗證調用
        mock_personal_view.set_category_filter.assert_called_once_with(1)
        mock_panel.refresh_callback.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_category_selector_callback_error(
        self,
        mock_panel: MagicMock,
        mock_interaction: AsyncMock,
        sample_categories: list[dict[str, Any]]
    ) -> None:
        """測試分類選擇器錯誤處理."""
        # 設置拋出錯誤的模擬
        mock_panel.view_manager.get_view.side_effect = Exception("View error")

        selector = PersonalCategorySelector(mock_panel, sample_categories)
        selector.values = ["1"]

        # 執行回調
        await selector.callback(mock_interaction)

        # 驗證錯誤處理
        mock_panel.on_error.assert_called_once()


class TestAchievementProgressIndicator:
    """成就進度指示器測試類別."""

    def test_create_progress_embed(self) -> None:
        """測試創建進度 Embed."""
        achievement_data = {
            "name": "社交達人",
            "description": "與50個不同用戶互動",
            "category": "社交",
            "points": 100
        }

        embed = AchievementProgressIndicator.create_progress_embed(
            achievement_data, 30, 50
        )

        # 驗證 Embed 結構
        assert embed.title == "🏆 社交達人"
        assert embed.description == "與50個不同用戶互動"
        assert embed.color == discord.Color.blue()

        # 驗證欄位
        progress_field = next(field for field in embed.fields if field.name == "📊 進度")
        assert "30 / 50" in progress_field.value
        assert "60.0%" in progress_field.value

        category_field = next(field for field in embed.fields if field.name == "📁 分類")
        assert category_field.value == "社交"

        points_field = next(field for field in embed.fields if field.name == "💰 點數")
        assert "100 點" in points_field.value

    def test_create_progress_bar(self) -> None:
        """測試創建進度條."""
        # 測試半進度
        progress_bar = AchievementProgressIndicator._create_progress_bar(50, 100, 20)
        assert len(progress_bar) == 20
        assert progress_bar.count("▓") == 10
        assert progress_bar.count("░") == 10

        # 測試完成進度
        progress_bar = AchievementProgressIndicator._create_progress_bar(100, 100, 10)
        assert progress_bar.count("▓") == 10
        assert progress_bar.count("░") == 0

        # 測試零進度
        progress_bar = AchievementProgressIndicator._create_progress_bar(0, 100, 10)
        assert progress_bar.count("▓") == 0
        assert progress_bar.count("░") == 10

        # 測試異常情況
        progress_bar = AchievementProgressIndicator._create_progress_bar(50, 0, 10)
        assert progress_bar.count("▓") == 10  # 目標為0時應該顯示滿格


class TestComponentFactory:
    """組件工廠測試類別."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """模擬面板."""
        return MagicMock()

    def test_create_pagination_buttons(self, mock_panel: MagicMock) -> None:
        """測試創建分頁按鈕組."""
        buttons = ComponentFactory.create_pagination_buttons(
            mock_panel, has_prev=True, has_next=True
        )

        assert len(buttons) == 4  # 首頁、上一頁、下一頁、末頁

        # 驗證按鈕類型和狀態
        first_button = buttons[0]
        assert isinstance(first_button, PaginationButton)
        assert first_button.direction == "first"
        assert not first_button.disabled

        last_button = buttons[3]
        assert isinstance(last_button, PaginationButton)
        assert last_button.direction == "last"
        assert not last_button.disabled

    def test_create_pagination_buttons_disabled(self, mock_panel: MagicMock) -> None:
        """測試創建禁用的分頁按鈕組."""
        buttons = ComponentFactory.create_pagination_buttons(
            mock_panel, has_prev=False, has_next=False
        )

        # 驗證所有按鈕都被禁用
        for button in buttons:
            assert button.disabled

    def test_create_personal_category_selector(self, mock_panel: MagicMock) -> None:
        """測試創建個人分類選擇器."""
        categories = [
            {"id": 1, "name": "測試分類", "user_achievements_count": 5}
        ]

        selector = ComponentFactory.create_personal_category_selector(
            mock_panel, categories
        )

        assert isinstance(selector, PersonalCategorySelector)
        assert selector.panel == mock_panel


class TestComponentIntegration:
    """組件整合測試."""

    @pytest.fixture
    def mock_panel(self) -> MagicMock:
        """完整的模擬面板."""
        panel = MagicMock()

        # 模擬個人視圖
        mock_personal_view = MagicMock()
        mock_personal_view.has_next_page.return_value = True
        mock_personal_view.has_previous_page.return_value = True
        mock_personal_view.get_current_page.return_value = 1
        mock_personal_view.get_total_pages.return_value = 5

        panel.view_manager.get_view.return_value = mock_personal_view

        return panel

    @pytest.mark.asyncio
    async def test_pagination_workflow(self, mock_panel: MagicMock) -> None:
        """測試完整的分頁工作流程."""
        mock_interaction = AsyncMock(spec=discord.Interaction)

        # 創建分頁按鈕
        buttons = ComponentFactory.create_pagination_buttons(
            mock_panel, has_prev=True, has_next=True
        )

        # 測試下一頁
        next_button = next(btn for btn in buttons if btn.direction == "next")
        await next_button.callback(mock_interaction)

        # 驗證個人視圖被更新
        personal_view = mock_panel.view_manager.get_view.return_value
        personal_view.set_page.assert_called_with(2)  # 當前頁面 + 1

        # 驗證面板被刷新
        mock_panel.refresh_callback.assert_called_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_category_selection_workflow(self, mock_panel: MagicMock) -> None:
        """測試完整的分類選擇工作流程."""
        mock_interaction = AsyncMock(spec=discord.Interaction)

        categories = [
            {"id": 1, "name": "活動成就", "user_achievements_count": 5}
        ]

        # 創建分類選擇器
        selector = ComponentFactory.create_personal_category_selector(
            mock_panel, categories
        )

        # 模擬選擇分類
        selector.values = ["1"]
        await selector.callback(mock_interaction)

        # 驗證個人視圖被更新
        personal_view = mock_panel.view_manager.get_view.return_value
        personal_view.set_category_filter.assert_called_with(1)

        # 驗證面板被刷新
        mock_panel.refresh_callback.assert_called_with(mock_interaction)


@pytest.mark.asyncio
async def test_component_error_resilience() -> None:
    """測試組件錯誤恢復能力."""
    # 創建會拋出錯誤的模擬面板
    failing_panel = MagicMock()
    failing_panel.view_manager.get_view.side_effect = Exception("Service error")

    mock_interaction = AsyncMock(spec=discord.Interaction)

    # 測試分頁按鈕錯誤處理
    button = PaginationButton(
        failing_panel,
        direction="next",
        label="下一頁",
        emoji="▶️"
    )

    await button.callback(mock_interaction)
    failing_panel.on_error.assert_called_once()

    # 測試分類選擇器錯誤處理
    categories = [{"id": 1, "name": "測試", "user_achievements_count": 1}]
    selector = PersonalCategorySelector(failing_panel, categories)
    selector.values = ["1"]

    await selector.callback(mock_interaction)
    assert failing_panel.on_error.call_count == 2  # 被調用兩次


@pytest.mark.performance
def test_component_creation_performance() -> None:
    """測試組件創建效能."""
    import time

    mock_panel = MagicMock()

    # 測試大量分頁按鈕創建
    start_time = time.time()
    for _ in range(1000):
        ComponentFactory.create_pagination_buttons(mock_panel, True, True)
    creation_time = time.time() - start_time

    # 驗證效能（應該在合理時間內完成）
    assert creation_time < 1.0  # 1000個按鈕組應該在1秒內創建完成

    # 測試大量分類選擇器創建
    large_categories = [
        {"id": i, "name": f"分類 {i}", "user_achievements_count": 1}
        for i in range(100)
    ]

    start_time = time.time()
    for _ in range(100):
        ComponentFactory.create_personal_category_selector(mock_panel, large_categories)
    creation_time = time.time() - start_time

    assert creation_time < 1.0  # 應該在合理時間內完成
