"""成就瀏覽視圖單元測試.

此模組測試 BrowserView 的核心功能:
- 資料載入和快取
- 分頁邏輯
- 分類篩選
- Embed 建立
- 錯誤處理
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cogs.achievement.panel.views import BrowserView
from src.cogs.achievement.services.achievement_service import AchievementService


class TestBrowserView:
    """BrowserView 測試類別."""

    @pytest.fixture
    def mock_achievement_service(self) -> AsyncMock:
        """創建模擬成就服務."""
        service = AsyncMock(spec=AchievementService)
        return service

    @pytest.fixture
    def browser_view(self, mock_achievement_service: AsyncMock) -> BrowserView:
        """創建 BrowserView 測試實例."""
        return BrowserView(
            achievement_service=mock_achievement_service, guild_id=12345, user_id=67890
        )

    @pytest.fixture
    def mock_achievements(self) -> list[Any]:
        """創建模擬成就資料."""
        achievements = []
        for i in range(25):  # 建立 25 個成就用於測試分頁
            achievement = MagicMock()
            achievement.id = i + 1
            achievement.name = f"成就 {i + 1}"
            achievement.description = f"這是第 {i + 1} 個成就的描述"
            achievement.category_id = (i % 4) + 1  # 分為 4 個分類
            achievement.points = (i + 1) * 10
            achievement.criteria = {"count": i + 1}
            achievement.badge_url = f"https://example.com/badge{i + 1}.png"
            achievements.append(achievement)
        return achievements

    @pytest.fixture
    def mock_user_achievements(self) -> list[tuple[Any, Any]]:
        """創建模擬用戶成就資料."""
        user_achievements = []
        for i in range(5):  # 假設用戶已獲得前 5 個成就
            user_achievement = MagicMock()
            user_achievement.user_id = 67890
            user_achievement.achievement_id = i + 1

            achievement = MagicMock()
            achievement.id = i + 1
            achievement.name = f"成就 {i + 1}"

            user_achievements.append((user_achievement, achievement))
        return user_achievements

    @pytest.mark.asyncio
    async def test_init(self, browser_view: BrowserView):
        """測試 BrowserView 初始化."""
        assert browser_view.guild_id == 12345
        assert browser_view.user_id == 67890
        assert browser_view._current_page == 0
        assert browser_view._page_size == 8
        assert browser_view._selected_category is None
        assert browser_view._total_pages == 0
        assert browser_view._total_achievements == 0

    @pytest.mark.asyncio
    async def test_load_data_success(
        self,
        browser_view: BrowserView,
        mock_achievements: list[Any],
        mock_user_achievements: list[tuple[Any, Any]],
    ):
        """測試成功載入資料."""
        # 設置模擬返回值
        browser_view.achievement_service.list_achievements.return_value = (
            mock_achievements
        )
        browser_view.achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )
        browser_view.achievement_service.get_category_by_id.return_value = None

        # 執行載入
        result = await browser_view.load_data(page=0, category_id=None)

        # 驗證結果
        assert "achievements" in result
        assert "current_page" in result
        assert "total_pages" in result
        assert "category_name" in result
        assert "stats" in result

        assert result["current_page"] == 0
        assert result["category_name"] == "全部分類"
        assert len(result["achievements"]) == 8  # 每頁 8 個成就

        # 驗證統計資訊
        stats = result["stats"]
        assert stats["total_achievements"] == 25
        assert "user_earned" in stats
        assert "completion_rate" in stats

    @pytest.mark.asyncio
    async def test_load_data_with_category_filter(
        self,
        browser_view: BrowserView,
        mock_achievements: list[Any],
        mock_user_achievements: list[tuple[Any, Any]],
    ):
        """測試帶分類篩選的資料載入."""
        # 篩選分類 1 的成就(每 4 個成就一個分類,所以約 6-7 個)
        category_achievements = [
            ach for ach in mock_achievements if ach.category_id == 1
        ]

        browser_view.achievement_service.list_achievements.return_value = (
            category_achievements
        )
        browser_view.achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )

        # 創建模擬分類
        mock_category = MagicMock()
        mock_category.name = "測試分類"
        browser_view.achievement_service.get_category_by_id.return_value = mock_category

        # 執行載入
        result = await browser_view.load_data(page=0, category_id=1)

        # 驗證結果
        assert result["category_name"] == "測試分類"
        assert result["category_id"] == 1
        browser_view.achievement_service.list_achievements.assert_called()

    @pytest.mark.asyncio
    async def test_pagination_logic(
        self,
        browser_view: BrowserView,
        mock_achievements: list[Any],
        mock_user_achievements: list[tuple[Any, Any]],
    ):
        """測試分頁邏輯."""
        browser_view.achievement_service.list_achievements.return_value = (
            mock_achievements
        )
        browser_view.achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )
        browser_view.achievement_service.get_category_by_id.return_value = None

        # 載入第一頁
        result = await browser_view.load_data(page=0)
        assert result["current_page"] == 0
        assert result["total_pages"] == 4  # 25 個成就,每頁 8 個 = 4 頁
        assert len(result["achievements"]) == 8

        # 載入第二頁
        result = await browser_view.load_data(page=1)
        assert result["current_page"] == 1
        assert len(result["achievements"]) == 8

        # 載入最後一頁
        result = await browser_view.load_data(page=3)
        assert result["current_page"] == 3
        assert len(result["achievements"]) == 1  # 最後一頁只有 1 個成就

    def test_set_page(self, browser_view: BrowserView):
        """測試頁面設置."""
        browser_view._total_pages = 5

        # 正常設置
        browser_view.set_page(2)
        assert browser_view.get_current_page() == 2

        # 邊界測試
        browser_view.set_page(-1)
        assert browser_view.get_current_page() == 0

        browser_view.set_page(10)
        assert browser_view.get_current_page() == 4  # 最大頁面是 4

    def test_set_category_filter(self, browser_view: BrowserView):
        """測試分類篩選設置."""
        browser_view._current_page = 3

        # 設置分類篩選
        browser_view.set_category_filter(2)
        assert browser_view.get_selected_category() == 2
        assert browser_view.get_current_page() == 0  # 應該重置到第一頁

        # 清除分類篩選
        browser_view.set_category_filter(None)
        assert browser_view.get_selected_category() is None

    def test_pagination_methods(self, browser_view: BrowserView):
        """測試分頁相關方法."""
        browser_view._current_page = 2
        browser_view._total_pages = 5

        assert browser_view.has_previous_page() is True
        assert browser_view.has_next_page() is True

        # 測試邊界
        browser_view._current_page = 0
        assert browser_view.has_previous_page() is False
        assert browser_view.has_next_page() is True

        browser_view._current_page = 4
        assert browser_view.has_previous_page() is True
        assert browser_view.has_next_page() is False

    def test_format_criteria(self, browser_view: BrowserView):
        """測試成就條件格式化."""
        # 測試不同類型的條件
        assert browser_view._format_criteria({}) == "無特殊條件"
        assert browser_view._format_criteria({"count": 10}) == "完成 10 次"
        assert browser_view._format_criteria({"duration": 7}) == "持續 7 天"
        assert browser_view._format_criteria({"target_value": 100}) == "達到 100"
        assert browser_view._format_criteria({"other": "value"}) == "達成特定條件"

    @pytest.mark.asyncio
    async def test_get_achievement_progress(self, browser_view: BrowserView):
        """測試成就進度獲取."""
        # 由於目前是模擬實作,測試返回值的結構
        with patch("random.choice", return_value=True):
            with patch("random.randint", side_effect=[50, 80]):
                progress = await browser_view._get_achievement_progress(1)

                assert progress is not None
                assert "current" in progress
                assert "target" in progress
                assert "percentage" in progress
                assert progress["current"] == 50
                assert progress["target"] == 100

    @pytest.mark.asyncio
    async def test_build_embed_success(
        self,
        browser_view: BrowserView,
        mock_achievements: list[Any],
        mock_user_achievements: list[tuple[Any, Any]],
    ):
        """測試成功建立 Embed."""
        # 設置模擬資料
        browser_view.achievement_service.list_achievements.return_value = (
            mock_achievements[:8]
        )
        browser_view.achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )
        browser_view.achievement_service.get_category_by_id.return_value = None

        # 建立 Embed
        embed = await browser_view.build_embed(page=0, category_id=None)

        # 驗證 Embed
        assert "成就瀏覽" in embed.title
        assert embed.description == "瀏覽所有可用的成就,了解獲得條件和獎勵"
        assert len(embed.fields) >= 3  # 至少有統計、分類、頁面欄位

    @pytest.mark.asyncio
    async def test_build_embed_error_handling(self, browser_view: BrowserView):
        """測試 Embed 建立錯誤處理."""
        # 模擬服務錯誤
        browser_view.achievement_service.list_achievements.side_effect = Exception(
            "服務錯誤"
        )

        # 建立 Embed
        embed = await browser_view.build_embed()

        # 驗證錯誤 Embed
        assert "載入失敗" in embed.title
        assert "無法載入成就瀏覽資料,請稍後再試" in embed.description

    @pytest.mark.asyncio
    async def test_load_data_error_handling(self, browser_view: BrowserView):
        """測試資料載入錯誤處理."""
        # 模擬服務錯誤
        browser_view.achievement_service.list_achievements.side_effect = Exception(
            "資料庫錯誤"
        )

        # 嘗試載入資料
        with pytest.raises(Exception):
            await browser_view.load_data()

    @pytest.mark.asyncio
    async def test_cache_behavior(
        self,
        browser_view: BrowserView,
        mock_achievements: list[Any],
        mock_user_achievements: list[tuple[Any, Any]],
    ):
        """測試快取行為."""
        browser_view.achievement_service.list_achievements.return_value = (
            mock_achievements
        )
        browser_view.achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )
        browser_view.achievement_service.get_category_by_id.return_value = None

        # 第一次載入
        result1 = await browser_view.get_cached_data(page=0)

        # 第二次載入(應該使用快取)
        result2 = await browser_view.get_cached_data(page=0)

        # 驗證只調用了一次服務
        assert browser_view.achievement_service.list_achievements.call_count == 1
        assert result1 == result2

        # 清除快取後重新載入
        browser_view.clear_cache()
        await browser_view.get_cached_data(page=0)

        # 驗證重新調用了服務
        assert browser_view.achievement_service.list_achievements.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_achievements_handling(self, browser_view: BrowserView):
        """測試空成就列表處理."""
        browser_view.achievement_service.list_achievements.return_value = []
        browser_view.achievement_service.get_user_achievements.return_value = []
        browser_view.achievement_service.get_category_by_id.return_value = None

        # 載入空資料
        result = await browser_view.load_data()

        # 驗證結果
        assert result["achievements"] == []
        assert result["total_pages"] == 1  # 至少有一頁
        assert result["stats"]["total_achievements"] == 0
        assert result["stats"]["user_earned"] == 0
        assert result["stats"]["completion_rate"] == 0

        # 建立 Embed
        embed = await browser_view.build_embed()

        # 驗證包含 "此分類暫無成就" 的欄位
        field_values = [field.value for field in embed.fields]
        assert any("此分類暫無成就" in value for value in field_values)


class TestBrowserViewIntegration:
    """BrowserView 整合測試."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """測試完整的工作流程."""
        # 這裡可以添加更複雜的整合測試
        # 模擬完整的用戶互動流程
        pass

    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self):
        """測試大量資料的效能."""
        # 可以測試處理大量成就資料時的效能
        pass
