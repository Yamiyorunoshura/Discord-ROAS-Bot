"""ProgressTracker 單元測試.

此模組測試進度追蹤器的核心功能,包含:
- 進度更新邏輯測試
- 進度計算測試
- 批量操作測試
- 驗證邏輯測試

遵循 AAA 模式(Arrange, Act, Assert)和測試最佳實踐.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
)
from src.cogs.achievement.services.progress_tracker import ProgressTracker
from tests.unit.achievement.services.conftest import (
    create_test_achievement,
    create_test_category,
    pytest_mark_unit,
)


@pytest_mark_unit
class TestProgressTracker:
    """ProgressTracker 單元測試類別."""

    # ==========================================================================
    # 初始化和配置測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_tracker_initialization(self, mock_repository):
        """測試進度追蹤器初始化."""
        # Arrange & Act
        tracker = ProgressTracker(mock_repository)

        # Assert
        assert tracker._repository == mock_repository

    @pytest.mark.asyncio
    async def test_tracker_context_manager(self, mock_repository):
        """測試進度追蹤器上下文管理器."""
        # Arrange
        tracker = ProgressTracker(mock_repository)

        # Act & Assert
        async with tracker as ctx_tracker:
            assert ctx_tracker is tracker

    # ==========================================================================
    # 進度更新核心邏輯測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_update_user_progress_increment(self, progress_tracker, repository):
        """測試增量式進度更新."""
        # Arrange
        category = await create_test_category(repository, "progress_cat")
        achievement = await create_test_achievement(
            repository, category.id, "progress_ach", AchievementType.COUNTER
        )
        user_id = 123456789

        # Act - 第一次更新
        progress1 = await progress_tracker.update_user_progress(
            user_id=user_id, achievement_id=achievement.id, increment_value=10.0
        )

        # Act - 第二次更新(累加)
        progress2 = await progress_tracker.update_user_progress(
            user_id=user_id, achievement_id=achievement.id, increment_value=15.0
        )

        # Assert
        assert progress1.current_value == 10.0
        assert progress2.current_value == 25.0
        assert progress2.target_value == 100.0  # 預設目標值

    @pytest.mark.asyncio
    async def test_update_user_progress_force_value(self, progress_tracker, repository):
        """測試強制設定進度值."""
        # Arrange
        category = await create_test_category(repository, "force_cat")
        achievement = await create_test_achievement(
            repository, category.id, "force_ach"
        )
        user_id = 123456789

        # 先設定一些進度
        await progress_tracker.update_user_progress(
            user_id=user_id, achievement_id=achievement.id, increment_value=50.0
        )

        # Act - 強制設定進度值
        progress = await progress_tracker.update_user_progress(
            user_id=user_id, achievement_id=achievement.id, force_value=80.0
        )

        # Assert
        assert progress.current_value == 80.0

    @pytest.mark.asyncio
    async def test_update_progress_with_data(self, progress_tracker, repository):
        """測試帶進度資料的更新."""
        # Arrange
        category = await create_test_category(repository, "data_cat")
        achievement = await create_test_achievement(
            repository, category.id, "data_ach", AchievementType.COUNTER
        )
        user_id = 123456789

        progress_data = {
            "session_data": {"duration": 300, "score": 85},
            "custom_field": "test_value",
        }

        # Act
        progress = await progress_tracker.update_user_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            increment_value=1.0,
            progress_data=progress_data,
        )

        # Assert
        assert progress.current_value == 1.0
        assert "session_data" in progress.progress_data
        assert "custom_field" in progress.progress_data
        assert "last_update_timestamp" in progress.progress_data

    @pytest.mark.asyncio
    async def test_update_progress_nonexistent_achievement(self, progress_tracker):
        """測試更新不存在成就的進度時失敗."""
        # Arrange
        user_id = 123456789
        nonexistent_achievement_id = 999

        # Act & Assert
        with pytest.raises(ValueError, match="成就 999 不存在"):
            await progress_tracker.update_user_progress(
                user_id=user_id,
                achievement_id=nonexistent_achievement_id,
                increment_value=1.0,
            )

    @pytest.mark.asyncio
    async def test_update_progress_inactive_achievement(
        self, progress_tracker, repository
    ):
        """測試更新未啟用成就的進度時失敗."""
        # Arrange
        category = await create_test_category(repository, "inactive_cat")
        achievement = await create_test_achievement(
            repository, category.id, "inactive_ach"
        )

        # 停用成就
        await repository.update_achievement(achievement.id, {"is_active": False})

        user_id = 123456789

        # Act & Assert
        with pytest.raises(ValueError, match=f"成就 {achievement.id} 未啟用"):
            await progress_tracker.update_user_progress(
                user_id=user_id, achievement_id=achievement.id, increment_value=1.0
            )

    @pytest.mark.asyncio
    async def test_update_progress_negative_value_clamped(
        self, progress_tracker, repository
    ):
        """測試負數進度值被限制為 0."""
        # Arrange
        category = await create_test_category(repository, "negative_cat")
        achievement = await create_test_achievement(
            repository, category.id, "negative_ach"
        )
        user_id = 123456789

        # Act - 嘗試設定負數進度值
        progress = await progress_tracker.update_user_progress(
            user_id=user_id, achievement_id=achievement.id, force_value=-10.0
        )

        # Assert
        assert progress.current_value == 0.0  # 應該被限制為 0

    # ==========================================================================
    # 進度資料合併邏輯測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_merge_progress_data_time_based(self, progress_tracker, repository):
        """測試時間型成就的進度資料合併."""
        # Arrange
        category = await create_test_category(repository, "time_cat")
        achievement = await create_test_achievement(
            repository, category.id, "time_ach", AchievementType.TIME_BASED
        )
        user_id = 123456789

        # 第一次更新
        await progress_tracker.update_user_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            increment_value=1.0,
            progress_data={"activity": "login"},
        )

        # Act - 第二次更新(應該合併進度資料)
        with patch(
            "src.cogs.achievement.services.progress_tracker.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.date.return_value.isoformat.return_value = (
                "2024-01-01"
            )
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-01-01T10:00:00"
            )

            progress = await progress_tracker.update_user_progress(
                user_id=user_id,
                achievement_id=achievement.id,
                increment_value=1.0,
                progress_data={"activity": "interaction"},
            )

        # Assert
        assert "streak_dates" in progress.progress_data
        assert "activity" in progress.progress_data
        assert progress.progress_data["activity"] == "interaction"

    @pytest.mark.asyncio
    async def test_merge_progress_data_counter(self, progress_tracker, repository):
        """測試計數型成就的進度資料合併."""
        # Arrange
        category = await create_test_category(repository, "counter_cat")
        achievement = await create_test_achievement(
            repository, category.id, "counter_ach", AchievementType.COUNTER
        )
        user_id = 123456789

        # Act - 多次更新計數型成就
        with patch(
            "src.cogs.achievement.services.progress_tracker.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.date.return_value.isoformat.return_value = (
                "2024-01-01"
            )
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-01-01T10:00:00"
            )

            progress = await progress_tracker.update_user_progress(
                user_id=user_id, achievement_id=achievement.id, increment_value=1.0
            )

        # Assert
        assert "daily_counts" in progress.progress_data
        assert progress.progress_data["daily_counts"]["2024-01-01"] == 1

    # ==========================================================================
    # 批量進度更新測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_batch_update_progress_success(self, progress_tracker, repository):
        """測試批量進度更新成功."""
        # Arrange
        category = await create_test_category(repository, "batch_cat")
        achievement1 = await create_test_achievement(repository, category.id, "batch1")
        achievement2 = await create_test_achievement(repository, category.id, "batch2")

        user_id = 123456789

        progress_updates = [
            (user_id, achievement1.id, 10.0, {"type": "batch1"}),
            (user_id, achievement2.id, 20.0, {"type": "batch2"}),
        ]

        # Act
        results = await progress_tracker.batch_update_progress(progress_updates)

        # Assert
        assert len(results) == 2
        assert results[0].current_value == 10.0
        assert results[1].current_value == 20.0

    @pytest.mark.asyncio
    async def test_batch_update_progress_partial_failure(
        self, progress_tracker, repository
    ):
        """測試批量進度更新部分失敗."""
        # Arrange
        category = await create_test_category(repository, "partial_batch_cat")
        achievement = await create_test_achievement(
            repository, category.id, "partial_batch"
        )

        user_id = 123456789

        progress_updates = [
            (user_id, achievement.id, 10.0, {}),  # 成功
            (user_id, 999, 20.0, {}),  # 失敗 - 成就不存在
            (user_id, achievement.id, 30.0, {}),  # 成功
        ]

        # Act
        results = await progress_tracker.batch_update_progress(progress_updates)

        # Assert - 應該有 2 個成功的結果
        assert len(results) == 2
        assert results[0].current_value == 10.0
        assert results[1].current_value == 40.0  # 10 + 30

    # ==========================================================================
    # 進度計算測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_calculate_counter_progress(self, progress_tracker, repository):
        """測試計數型成就進度計算."""
        # Arrange
        category = await create_test_category(repository, "calc_counter_cat")
        achievement = Achievement(
            name="計數測試",
            description="計數型成就測試",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100, "counter_field": "messages"},
            points=100,
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789
        current_metrics = {"messages": 75, "reactions": 20}

        # Act
        progress_value = await progress_tracker.calculate_achievement_progress(
            user_id=user_id, achievement=achievement, current_metrics=current_metrics
        )

        # Assert
        assert progress_value == 75.0

    @pytest.mark.asyncio
    async def test_calculate_milestone_progress(self, progress_tracker, repository):
        """測試里程碑型成就進度計算."""
        # Arrange
        category = await create_test_category(repository, "calc_milestone_cat")
        achievement = Achievement(
            name="里程碑測試",
            description="里程碑型成就測試",
            category_id=category.id,
            type=AchievementType.MILESTONE,
            criteria={"target_value": 50, "milestone_type": "level"},
            points=200,
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789
        current_metrics = {"level": 25, "exp": 5000}

        # Act
        progress_value = await progress_tracker.calculate_achievement_progress(
            user_id=user_id, achievement=achievement, current_metrics=current_metrics
        )

        # Assert
        assert progress_value == 25.0

    @pytest.mark.asyncio
    async def test_calculate_time_based_progress(self, progress_tracker, repository):
        """測試時間型成就進度計算."""
        # Arrange
        category = await create_test_category(repository, "calc_time_cat")
        achievement = Achievement(
            name="時間測試",
            description="時間型成就測試",
            category_id=category.id,
            type=AchievementType.TIME_BASED,
            criteria={"target_value": 7, "time_unit": "days"},
            points=300,
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 先建立一些進度資料
        today = datetime.now().date()
        streak_dates = [
            (today - timedelta(days=2)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
            today.isoformat(),
        ]

        await repository.update_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_value=3.0,
            progress_data={"streak_dates": streak_dates},
        )

        # Act
        progress_value = await progress_tracker.calculate_achievement_progress(
            user_id=user_id, achievement=achievement, current_metrics={}
        )

        # Assert
        assert progress_value == 3.0  # 3 天連續

    @pytest.mark.asyncio
    async def test_calculate_conditional_progress(self, progress_tracker, repository):
        """測試條件型成就進度計算."""
        # Arrange
        category = await create_test_category(repository, "calc_conditional_cat")
        achievement = Achievement(
            name="條件測試",
            description="條件型成就測試",
            category_id=category.id,
            type=AchievementType.CONDITIONAL,
            criteria={
                "target_value": 2,
                "conditions": [
                    {"type": "metric_threshold", "metric": "level", "threshold": 10},
                    {"type": "metric_threshold", "metric": "messages", "threshold": 50},
                ],
            },
            points=400,
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789
        current_metrics = {"level": 15, "messages": 60, "reactions": 5}

        # Act
        progress_value = await progress_tracker.calculate_achievement_progress(
            user_id=user_id, achievement=achievement, current_metrics=current_metrics
        )

        # Assert
        assert progress_value == 2.0  # 滿足 2 個條件

    # ==========================================================================
    # 進度驗證測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_validate_progress_update_success(self, progress_tracker, repository):
        """測試進度更新驗證成功."""
        # Arrange
        category = await create_test_category(repository, "validate_cat")
        achievement = await create_test_achievement(
            repository, category.id, "validate_ach"
        )
        user_id = 123456789

        # Act
        is_valid, error_message = await progress_tracker.validate_progress_update(
            user_id=user_id, achievement_id=achievement.id, new_value=50.0
        )

        # Assert
        assert is_valid is True
        assert error_message is None

    @pytest.mark.asyncio
    async def test_validate_progress_update_nonexistent_achievement(
        self, progress_tracker
    ):
        """測試驗證不存在成就的進度更新."""
        # Arrange
        user_id = 123456789
        nonexistent_achievement_id = 999

        # Act
        is_valid, error_message = await progress_tracker.validate_progress_update(
            user_id=user_id, achievement_id=nonexistent_achievement_id, new_value=50.0
        )

        # Assert
        assert is_valid is False
        assert "成就 999 不存在" in error_message

    @pytest.mark.asyncio
    async def test_validate_progress_update_negative_value(
        self, progress_tracker, repository
    ):
        """測試驗證負數進度值."""
        # Arrange
        category = await create_test_category(repository, "negative_validate_cat")
        achievement = await create_test_achievement(
            repository, category.id, "negative_validate"
        )
        user_id = 123456789

        # Act
        is_valid, error_message = await progress_tracker.validate_progress_update(
            user_id=user_id, achievement_id=achievement.id, new_value=-10.0
        )

        # Assert
        assert is_valid is False
        assert "進度值不能為負數" in error_message

    # ==========================================================================
    # 進度查詢和分析測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_user_progress_summary(self, progress_tracker, repository):
        """測試取得用戶進度摘要."""
        # Arrange
        category = await create_test_category(repository, "summary_cat")
        achievement1 = await create_test_achievement(
            repository, category.id, "summary1"
        )
        achievement2 = await create_test_achievement(
            repository, category.id, "summary2"
        )

        user_id = 123456789

        # 建立一些進度
        await progress_tracker.update_user_progress(
            user_id, achievement1.id, force_value=100.0
        )  # 完成
        await progress_tracker.update_user_progress(
            user_id, achievement2.id, force_value=50.0
        )  # 進行中

        # Act
        summary = await progress_tracker.get_user_progress_summary(user_id)

        # Assert
        assert summary["total_progresses"] == 2
        assert summary["completed_count"] == 1
        assert summary["in_progress_count"] == 1
        assert summary["average_progress"] > 0
        assert summary["closest_to_completion"]["achievement_id"] == achievement2.id

    @pytest.mark.asyncio
    async def test_consecutive_days_calculation(self, progress_tracker):
        """測試連續天數計算邏輯."""
        # Arrange
        today = datetime.now().date()

        # 連續 3 天的日期
        consecutive_dates = [
            (today - timedelta(days=2)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
            today.isoformat(),
        ]

        # 非連續日期
        non_consecutive_dates = [
            (today - timedelta(days=3)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
            today.isoformat(),
        ]

        # Act
        consecutive_count = progress_tracker._calculate_consecutive_days(
            consecutive_dates
        )
        non_consecutive_count = progress_tracker._calculate_consecutive_days(
            non_consecutive_dates
        )

        # Assert
        assert consecutive_count == 3
        assert non_consecutive_count == 2  # 只有最近 2 天是連續的
