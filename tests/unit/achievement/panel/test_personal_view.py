"""個人成就視圖測試模組.

測試個人成就頁面的資料載入、顯示和分頁功能.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cogs.achievement.panel.views import PersonalView
from src.cogs.achievement.services.achievement_service import AchievementService


class TestPersonalView:
    """個人成就視圖測試類別."""

    @pytest.fixture
    def mock_achievement_service(self) -> AsyncMock:
        """模擬成就服務."""
        service = AsyncMock(spec=AchievementService)
        return service

    @pytest.fixture
    def personal_view(self, mock_achievement_service: AsyncMock) -> PersonalView:
        """創建個人視圖實例."""
        return PersonalView(
            achievement_service=mock_achievement_service, guild_id=12345, user_id=67890
        )

    @pytest.mark.asyncio
    async def test_init(self, personal_view: PersonalView) -> None:
        """測試初始化."""
        assert personal_view.guild_id == 12345
        assert personal_view.user_id == 67890
        assert personal_view._current_page == 0
        assert personal_view._page_size == 10
        assert personal_view._selected_category is None
        assert personal_view._total_pages == 0

    @pytest.mark.asyncio
    async def test_load_data_success(
        self, personal_view: PersonalView, mock_achievement_service: AsyncMock
    ) -> None:
        """測試成功載入資料."""
        # 準備模擬資料
        mock_stats = {
            "total_achievements": 5,
            "available_achievements": 20,
            "completion_rate": 25.0,
            "total_points": 150,
        }

        mock_user_achievements = [
            (
                MagicMock(earned_at=datetime(2024, 1, 1, 12, 0)),
                MagicMock(
                    name="初次嘗試",
                    description="發送第一條訊息",
                    points=10,
                    category_id=1,
                ),
            ),
            (
                MagicMock(earned_at=datetime(2024, 1, 2, 15, 30)),
                MagicMock(
                    name="活躍用戶",
                    description="連續7天發送訊息",
                    points=50,
                    category_id=1,
                ),
            ),
        ]

        # 設置模擬回傳值
        mock_achievement_service.get_user_achievement_stats.return_value = mock_stats
        mock_achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )
        mock_achievement_service.get_category_by_id.return_value = None

        # 執行測試
        data = await personal_view.load_data(page=0, category_id=None)

        # 驗證結果
        assert data["stats"]["earned"] == 5
        assert data["stats"]["total"] == 20
        assert data["stats"]["completion_rate"] == 25.0
        assert data["stats"]["total_points"] == 150

        assert len(data["earned_achievements"]) == 2
        assert data["earned_achievements"][0]["name"] == "初次嘗試"
        assert data["earned_achievements"][0]["points"] == 10
        assert data["earned_achievements"][1]["name"] == "活躍用戶"
        assert data["earned_achievements"][1]["points"] == 50

        assert data["current_page"] == 0
        assert data["category_name"] == "全部"

        # 驗證服務調用
        mock_achievement_service.get_user_achievement_stats.assert_called_once_with(
            67890
        )
        mock_achievement_service.get_user_achievements.assert_called_once_with(
            user_id=67890, category_id=None, limit=10
        )

    @pytest.mark.asyncio
    async def test_load_data_with_category(
        self, personal_view: PersonalView, mock_achievement_service: AsyncMock
    ) -> None:
        """測試載入特定分類資料."""
        # 準備模擬資料
        mock_stats = {"total_achievements": 3, "available_achievements": 10}
        mock_user_achievements = []
        mock_category = MagicMock(name="活動成就")

        # 設置模擬回傳值
        mock_achievement_service.get_user_achievement_stats.return_value = mock_stats
        mock_achievement_service.get_user_achievements.return_value = (
            mock_user_achievements
        )
        mock_achievement_service.get_category_by_id.return_value = mock_category

        # 執行測試
        data = await personal_view.load_data(page=0, category_id=1)

        # 驗證結果
        assert data["category_name"] == "活動成就"
        assert data["category_id"] == 1

        # 驗證服務調用
        mock_achievement_service.get_category_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_build_embed_success(
        self, personal_view: PersonalView, mock_achievement_service: AsyncMock
    ) -> None:
        """測試成功建立 Embed."""
        # 準備模擬資料
        personal_view._cache = {
            "stats": {
                "earned": 5,
                "total": 20,
                "completion_rate": 25.0,
                "total_points": 150,
            },
            "earned_achievements": [
                {
                    "name": "初次嘗試",
                    "description": "發送第一條訊息",
                    "points": 10,
                    "earned_at": "2024-01-01 12:00",
                }
            ],
            "in_progress": [{"name": "社交達人", "current": 15, "target": 50}],
            "current_page": 0,
            "total_pages": 1,
            "category_name": "全部",
        }
        personal_view._cache_valid = True

        # 執行測試
        embed = await personal_view.build_embed()

        # 驗證結果
        assert embed.title == "我的成就"
        assert embed.description == "查看您的成就進度和已獲得的成就"
        assert len(embed.fields) >= 3  # 統計、分類、頁面等欄位

        # 驗證統計資訊
        stats_field = next(
            field for field in embed.fields if field.name == "📊 成就統計"
        )
        assert "已獲得: 5" in stats_field.value
        assert "總數: 20" in stats_field.value
        assert "完成率: 25.0%" in stats_field.value
        assert "總點數: 150" in stats_field.value

    @pytest.mark.asyncio
    async def test_build_embed_error_handling(
        self, personal_view: PersonalView, mock_achievement_service: AsyncMock
    ) -> None:
        """測試 Embed 建立錯誤處理."""
        # 設置模擬錯誤
        mock_achievement_service.get_user_achievement_stats.side_effect = Exception(
            "Database error"
        )

        # 執行測試
        embed = await personal_view.build_embed()

        # 驗證錯誤處理
        assert "載入失敗" in embed.title
        assert "無法載入個人成就資料" in embed.description

    def test_create_progress_bar(self, personal_view: PersonalView) -> None:
        """測試進度條建立."""
        # 測試正常進度
        progress_bar = personal_view._create_progress_bar(30, 100)
        assert len(progress_bar) == 12  # [進度條]格式,包含括號
        assert "▓" in progress_bar
        assert "░" in progress_bar

        # 測試完成狀態
        progress_bar = personal_view._create_progress_bar(100, 100)
        assert progress_bar.count("▓") == 10

        # 測試空進度
        progress_bar = personal_view._create_progress_bar(0, 100)
        assert progress_bar.count("░") == 10

        # 測試異常情況
        progress_bar = personal_view._create_progress_bar(10, 0)
        assert progress_bar.count("▓") == 10

    def test_pagination_methods(self, personal_view: PersonalView) -> None:
        """測試分頁方法."""
        # 初始狀態
        assert personal_view.get_current_page() == 0
        assert personal_view.get_total_pages() == 0
        assert not personal_view.has_next_page()
        assert not personal_view.has_previous_page()

        # 設置總頁數
        personal_view._total_pages = 3

        # 測試頁面設置
        personal_view.set_page(1)
        assert personal_view.get_current_page() == 1
        assert personal_view.has_next_page()
        assert personal_view.has_previous_page()

        # 測試邊界情況
        personal_view.set_page(-1)
        assert personal_view.get_current_page() == 0

        personal_view.set_page(10)
        assert personal_view.get_current_page() == 2

    def test_category_filter_methods(self, personal_view: PersonalView) -> None:
        """測試分類篩選方法."""
        # 初始狀態
        assert personal_view.get_selected_category() is None

        # 設置分類篩選
        personal_view.set_category_filter(1)
        assert personal_view.get_selected_category() == 1
        assert personal_view.get_current_page() == 0  # 應該重置頁面

        # 清除分類篩選
        personal_view.set_category_filter(None)
        assert personal_view.get_selected_category() is None

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, personal_view: PersonalView) -> None:
        """測試快取無效化."""
        # 設置快取
        personal_view._cache = {"test": "data"}
        personal_view._cache_valid = True

        # 設置頁面(應該無效化快取)
        personal_view.set_page(1)
        assert not personal_view._cache_valid

        # 重新設置快取
        personal_view._cache_valid = True

        # 設置分類篩選(應該無效化快取)
        personal_view.set_category_filter(1)
        assert not personal_view._cache_valid

    @pytest.mark.asyncio
    async def test_get_user_progress_achievements(
        self, personal_view: PersonalView
    ) -> None:
        """測試獲取用戶進行中成就."""
        # 執行測試(使用模擬實作)
        progress_achievements = await personal_view._get_user_progress_achievements()

        # 驗證結果
        assert isinstance(progress_achievements, list)
        assert len(progress_achievements) >= 0

        # 如果有資料,驗證結構
        if progress_achievements:
            achievement = progress_achievements[0]
            assert "name" in achievement
            assert "current" in achievement
            assert "target" in achievement


class TestPersonalViewIntegration:
    """個人成就視圖整合測試."""

    @pytest.fixture
    def real_achievement_service(self) -> MagicMock:
        """真實的成就服務(模擬)."""
        service = MagicMock(spec=AchievementService)
        return service

    @pytest.mark.asyncio
    async def test_complete_workflow(self, real_achievement_service: MagicMock) -> None:
        """測試完整工作流程."""
        # 創建個人視圖
        personal_view = PersonalView(
            achievement_service=real_achievement_service, guild_id=12345, user_id=67890
        )

        # 設置模擬數據
        real_achievement_service.get_user_achievement_stats.return_value = {
            "total_achievements": 10,
            "available_achievements": 50,
            "completion_rate": 20.0,
            "total_points": 500,
        }

        real_achievement_service.get_user_achievements.return_value = []

        # 執行完整流程
        # 1. 載入資料
        data = await personal_view.load_data()
        assert data is not None

        # 2. 建立 Embed
        embed = await personal_view.build_embed()
        assert embed is not None

        # 3. 分頁操作
        personal_view.set_page(1)
        assert personal_view.get_current_page() == 1

        # 4. 分類篩選
        personal_view.set_category_filter(1)
        assert personal_view.get_selected_category() == 1


@pytest.mark.asyncio
async def test_error_resilience() -> None:
    """測試錯誤恢復能力."""
    # 創建會拋出錯誤的模擬服務
    failing_service = AsyncMock(spec=AchievementService)
    failing_service.get_user_achievement_stats.side_effect = Exception("Service error")

    personal_view = PersonalView(
        achievement_service=failing_service, guild_id=12345, user_id=67890
    )

    # 測試錯誤處理
    with pytest.raises(Exception):
        await personal_view.load_data()

    # 測試 Embed 建立的錯誤處理
    embed = await personal_view.build_embed()
    assert "載入失敗" in embed.title


@pytest.mark.performance
@pytest.mark.asyncio
async def test_performance_with_large_dataset() -> None:
    """測試大數據集的效能."""
    import time

    # 創建模擬大數據集
    mock_service = AsyncMock(spec=AchievementService)
    mock_service.get_user_achievement_stats.return_value = {
        "total_achievements": 1000,
        "available_achievements": 2000,
        "completion_rate": 50.0,
        "total_points": 50000,
    }

    # 創建大量成就資料
    large_achievements = []
    for i in range(100):
        large_achievements.append(
            (
                MagicMock(earned_at=datetime(2024, 1, 1)),
                MagicMock(
                    name=f"成就 {i}", description=f"描述 {i}", points=10, category_id=1
                ),
            )
        )

    mock_service.get_user_achievements.return_value = large_achievements

    personal_view = PersonalView(
        achievement_service=mock_service, guild_id=12345, user_id=67890
    )

    # 測試載入時間
    start_time = time.time()
    data = await personal_view.load_data()
    load_time = time.time() - start_time

    # 測試 Embed 建立時間
    start_time = time.time()
    await personal_view.build_embed()
    embed_time = time.time() - start_time

    # 驗證效能(應該在合理時間內完成)
    assert load_time < 1.0  # 載入應該在1秒內完成
    assert embed_time < 0.5  # Embed建立應該在0.5秒內完成
    assert len(data["earned_achievements"]) == 10  # 分頁限制生效
