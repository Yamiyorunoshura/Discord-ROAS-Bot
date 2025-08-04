"""測試真實管理服務實現.

此模組測試 RealAdminService 的所有功能:
- 用戶成就管理
- 進度管理
- 數據重置
- 統計查詢
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.cogs.achievement.services.real_admin_service import RealAdminService
from src.cogs.achievement.database.models import (
    Achievement,
    AchievementProgress,
    UserAchievement,
    AchievementType,
)


@pytest.fixture
def mock_repository():
    """創建模擬的資料存取層."""
    repository = AsyncMock()
    return repository


@pytest.fixture
def admin_service(mock_repository):
    """創建管理服務實例."""
    return RealAdminService(mock_repository)


@pytest.fixture
def sample_achievement():
    """創建範例成就."""
    return Achievement(
        id=1,
        name="測試成就",
        description="這是一個測試成就",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={"target_value": 100, "counter_field": "message_count"},
        points=500,
        is_active=True,
    )


@pytest.fixture
def sample_user_achievement():
    """創建範例用戶成就."""
    return UserAchievement(
        user_id=123456789, achievement_id=1, earned_at=datetime.utcnow(), notified=False
    )


@pytest.fixture
def sample_progress():
    """創建範例進度記錄."""
    return AchievementProgress(
        user_id=123456789,
        achievement_id=1,
        current_value=75.0,
        target_value=100.0,
        last_updated=datetime.utcnow(),
    )


class TestRealAdminService:
    """測試真實管理服務."""

    @pytest.mark.asyncio
    async def test_get_user_achievements_success(
        self, admin_service, mock_repository, sample_user_achievement
    ):
        """測試成功獲取用戶成就."""
        # 設置模擬返回
        mock_repository.get_user_achievements.return_value = [sample_user_achievement]

        # 執行測試
        result = await admin_service.get_user_achievements(123456789)

        # 驗證結果
        assert len(result) == 1
        assert result[0] == sample_user_achievement
        mock_repository.get_user_achievements.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_get_user_achievements_error(self, admin_service, mock_repository):
        """測試獲取用戶成就時發生錯誤."""
        # 設置模擬拋出異常
        mock_repository.get_user_achievements.side_effect = Exception("Database error")

        # 執行測試
        result = await admin_service.get_user_achievements(123456789)

        # 驗證結果
        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_progress_success(
        self, admin_service, mock_repository, sample_progress
    ):
        """測試成功獲取用戶進度."""
        # 設置模擬返回
        mock_repository.get_user_progress.return_value = [sample_progress]

        # 執行測試
        result = await admin_service.get_user_progress(123456789)

        # 驗證結果
        assert len(result) == 1
        assert result[0] == sample_progress
        mock_repository.get_user_progress.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_get_user_stats_success(
        self, admin_service, mock_repository, sample_user_achievement, sample_progress
    ):
        """測試成功獲取用戶統計."""
        # 設置模擬返回 - 創建有 points 屬性的模擬對象
        mock_achievement = MagicMock()
        mock_achievement.points = 500
        mock_repository.get_user_achievements.return_value = [mock_achievement]
        mock_repository.get_user_progress.return_value = [sample_progress]

        # 執行測試
        result = await admin_service.get_user_stats(123456789)

        # 驗證結果
        assert result["total_achievements"] == 1
        assert result["total_progress"] == 1
        assert result["total_points"] == 500

    @pytest.mark.asyncio
    async def test_reset_user_achievements_success(
        self, admin_service, mock_repository
    ):
        """測試成功重置用戶成就."""
        # 設置模擬返回
        mock_repository.delete_user_achievements.return_value = None

        # 執行測試
        result = await admin_service.reset_user_achievements(123456789)

        # 驗證結果
        assert result is True
        mock_repository.delete_user_achievements.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_reset_user_achievements_error(self, admin_service, mock_repository):
        """測試重置用戶成就時發生錯誤."""
        # 設置模擬拋出異常
        mock_repository.delete_user_achievements.side_effect = Exception(
            "Database error"
        )

        # 執行測試
        result = await admin_service.reset_user_achievements(123456789)

        # 驗證結果
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_user_progress_success(self, admin_service, mock_repository):
        """測試成功重置用戶進度."""
        # 設置模擬返回
        mock_repository.delete_user_progress.return_value = None

        # 執行測試
        result = await admin_service.reset_user_progress(123456789)

        # 驗證結果
        assert result is True
        mock_repository.delete_user_progress.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_grant_achievement_success(self, admin_service, mock_repository):
        """測試成功授予成就."""
        # 設置模擬返回
        mock_repository.has_user_achievement.return_value = False
        mock_repository.create_user_achievement.return_value = None

        # 執行測試
        result = await admin_service.grant_achievement(123456789, 1, 987654321)

        # 驗證結果
        assert result is True
        mock_repository.has_user_achievement.assert_called_once_with(123456789, 1)
        mock_repository.create_user_achievement.assert_called_once()

    @pytest.mark.asyncio
    async def test_grant_achievement_already_has(self, admin_service, mock_repository):
        """測試授予已擁有的成就."""
        # 設置模擬返回
        mock_repository.has_user_achievement.return_value = True

        # 執行測試
        result = await admin_service.grant_achievement(123456789, 1, 987654321)

        # 驗證結果
        assert result is False
        mock_repository.has_user_achievement.assert_called_once_with(123456789, 1)
        mock_repository.create_user_achievement.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_achievement_success(self, admin_service, mock_repository):
        """測試成功撤銷成就."""
        # 設置模擬返回
        mock_repository.delete_user_achievement.return_value = None

        # 執行測試
        result = await admin_service.revoke_achievement(123456789, 1, 987654321)

        # 驗證結果
        assert result is True
        mock_repository.delete_user_achievement.assert_called_once_with(123456789, 1)

    @pytest.mark.asyncio
    async def test_update_user_progress_existing(
        self, admin_service, mock_repository, sample_progress
    ):
        """測試更新現有進度."""
        # 設置模擬返回
        mock_repository.get_user_progress_by_achievement.return_value = sample_progress
        mock_repository.update_user_progress.return_value = None

        # 執行測試
        result = await admin_service.update_user_progress(123456789, 1, 85.0, 987654321)

        # 驗證結果
        assert result is True
        assert sample_progress.current_value == 85.0
        mock_repository.update_user_progress.assert_called_once_with(sample_progress)

    @pytest.mark.asyncio
    async def test_update_user_progress_new(
        self, admin_service, mock_repository, sample_achievement
    ):
        """測試創建新進度記錄."""
        # 設置模擬返回
        mock_repository.get_user_progress_by_achievement.return_value = None
        mock_repository.get_achievement_by_id.return_value = sample_achievement
        mock_repository.create_user_progress.return_value = None

        # 執行測試
        result = await admin_service.update_user_progress(123456789, 1, 50.0, 987654321)

        # 驗證結果
        assert result is True
        mock_repository.create_user_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_stats_success(self, admin_service, mock_repository):
        """測試成功獲取系統統計."""
        # 設置模擬返回
        mock_repository.count_achievements.return_value = 10
        mock_repository.count_categories.return_value = 3
        mock_repository.count_users_with_achievements.return_value = 50
        mock_repository.count_active_achievements.return_value = 8
        mock_repository.count_total_awarded_achievements.return_value = 150

        # 執行測試
        result = await admin_service.get_system_stats()

        # 驗證結果
        assert result["total_achievements"] == 10
        assert result["total_categories"] == 3
        assert result["total_users"] == 50
        assert result["active_achievements"] == 8
        assert result["total_awarded"] == 150

    @pytest.mark.asyncio
    async def test_get_achievement_usage_stats_success(
        self, admin_service, mock_repository, sample_achievement
    ):
        """測試成功獲取成就使用統計."""
        # 設置模擬返回
        mock_repository.get_achievement_by_id.return_value = sample_achievement
        mock_repository.count_users_with_achievement.return_value = 20
        mock_repository.count_users_with_progress.return_value = 30

        # 執行測試
        result = await admin_service.get_achievement_usage_stats(1)

        # 驗證結果
        assert result["achievement"] == sample_achievement
        assert result["users_earned"] == 20
        assert result["users_in_progress"] == 30
        assert result["completion_rate"] == 40.0  # 20/(20+30)*100

    @pytest.mark.asyncio
    async def test_search_users_not_implemented(self, admin_service):
        """測試用戶搜尋功能(尚未實現)."""
        # 執行測試
        result = await admin_service.search_users("test")

        # 驗證結果
        assert result == []
