"""AchievementAwarder 測試.

此模組測試自動成就頒發系統的功能,包含:
- 單一和批量成就頒發測試
- 原子性和一致性測試
- 錯誤處理和重試測試
- 通知系統整合測試

測試遵循 AAA 模式和現代測試最佳實踐.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
    UserAchievement,
)
from src.cogs.achievement.services.achievement_awarder import (
    AchievementAwarder,
    AwardRequest,
    AwardStatus,
)
from src.cogs.achievement.services.event_processor import TriggerResult


@pytest.mark.unit
class TestAchievementAwarder:
    """AchievementAwarder 測試類別."""

    # ==========================================================================
    # 初始化和配置測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_awarder_initialization(self):
        """測試成就頒發器初始化."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # Act
        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=True,
            max_concurrent_awards=20,
        ) as awarder:
            # Assert
            assert awarder._repository == mock_repository
            assert awarder._progress_tracker == mock_progress_tracker
            assert awarder._notification_enabled is True
            assert awarder._max_concurrent_awards == 20

    # ==========================================================================
    # 單一成就頒發測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_award_single_achievement_success(self):
        """測試單一成就頒發成功案例."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 模擬成就存在且啟用
        test_achievement = Achievement(
            id=1,
            name="Test Achievement",
            type=AchievementType.COUNTER,
            is_active=True,
            points=100,
            role_reward=None,
            is_hidden=False,
        )
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        # 模擬頒發成功
        user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )
        mock_repository.award_achievement.return_value = user_achievement

        # 模擬事務
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=False,  # 禁用通知簡化測試
        ) as awarder:
            # Act
            result = await awarder.award_achievement(
                user_id=123,
                achievement_id=1,
                trigger_reason="達到計數目標",
                trigger_context={"message_count": 10},
            )

        # Assert
        assert result.status == AwardStatus.SUCCESS
        assert result.user_achievement == user_achievement
        assert result.error_message is None
        mock_repository.award_achievement.assert_called_once()

    @pytest.mark.asyncio
    async def test_award_achievement_already_earned(self):
        """測試頒發已獲得的成就."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        test_achievement = Achievement(
            id=1,
            name="Test Achievement",
            type=AchievementType.COUNTER,
            is_active=True,
            role_reward=None,
            is_hidden=False,
        )
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = True  # 已獲得

        async with AchievementAwarder(
            repository=mock_repository, progress_tracker=mock_progress_tracker
        ) as awarder:
            # Act
            result = await awarder.award_achievement(
                user_id=123, achievement_id=1, trigger_reason="測試觸發"
            )

        # Assert
        assert result.status == AwardStatus.DUPLICATE
        assert "用戶已獲得此成就" in result.error_message
        mock_repository.award_achievement.assert_not_called()

    @pytest.mark.asyncio
    async def test_award_inactive_achievement(self):
        """測試頒發未啟用的成就."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        inactive_achievement = Achievement(
            id=1,
            name="Inactive Achievement",
            type=AchievementType.COUNTER,
            is_active=False,  # 未啟用
            role_reward=None,
            is_hidden=False,
        )
        mock_repository.get_achievement_by_id.return_value = inactive_achievement

        async with AchievementAwarder(
            repository=mock_repository, progress_tracker=mock_progress_tracker
        ) as awarder:
            # Act
            result = await awarder.award_achievement(
                user_id=123, achievement_id=1, trigger_reason="測試觸發"
            )

        # Assert
        assert result.status == AwardStatus.INVALID
        assert "成就未啟用" in result.error_message

    @pytest.mark.asyncio
    async def test_award_nonexistent_achievement(self):
        """測試頒發不存在的成就."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        mock_repository.get_achievement_by_id.return_value = None  # 成就不存在

        async with AchievementAwarder(
            repository=mock_repository, progress_tracker=mock_progress_tracker
        ) as awarder:
            # Act
            result = await awarder.award_achievement(
                user_id=123, achievement_id=999, trigger_reason="測試觸發"
            )

        # Assert
        assert result.status == AwardStatus.INVALID
        assert "成就不存在" in result.error_message

    # ==========================================================================
    # 批量成就頒發測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_award_multiple_achievements_success(self):
        """測試批量成就頒發成功案例."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 創建多個頒發請求
        requests = [
            AwardRequest(
                user_id=123,
                achievement_id=1,
                trigger_reason="觸發原因1",
                processing_priority=1,
            ),
            AwardRequest(
                user_id=123,
                achievement_id=2,
                trigger_reason="觸發原因2",
                processing_priority=2,
            ),
            AwardRequest(
                user_id=456,
                achievement_id=1,
                trigger_reason="觸發原因3",
                processing_priority=0,
            ),
        ]

        # 模擬成就存在
        test_achievement = Achievement(
            id=1,
            name="Test Achievement",
            type=AchievementType.COUNTER,
            is_active=True,
            role_reward=None,
            is_hidden=False,
        )
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        # 模擬頒發成功
        user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )
        mock_repository.award_achievement.return_value = user_achievement

        # 模擬事務
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=False,
        ) as awarder:
            # Act
            results = await awarder.award_multiple_achievements(requests)

        # Assert
        assert len(results) == 3
        # 檢查優先級排序(高優先級先處理)
        assert (
            results[0].request.processing_priority
            >= results[1].request.processing_priority
        )
        assert all(result.status == AwardStatus.SUCCESS for result in results)

    @pytest.mark.asyncio
    async def test_award_multiple_achievements_with_errors(self):
        """測試批量頒發中的錯誤處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        requests = [
            AwardRequest(user_id=123, achievement_id=1, trigger_reason="正常頒發"),
            AwardRequest(
                user_id=123,
                achievement_id=999,  # 不存在的成就
                trigger_reason="錯誤頒發",
            ),
        ]

        # 模擬第一個成就存在,第二個不存在
        def mock_get_achievement(achievement_id):
            if achievement_id == 1:
                return Achievement(
                    id=1, is_active=True, role_reward=None, is_hidden=False
                )
            return None

        mock_repository.get_achievement_by_id.side_effect = mock_get_achievement
        mock_repository.has_user_achievement.return_value = False

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=False,
        ) as awarder:
            # Act
            results = await awarder.award_multiple_achievements(requests)

        # Assert
        assert len(results) == 2
        assert results[0].status == AwardStatus.SUCCESS
        assert results[1].status == AwardStatus.INVALID

    # ==========================================================================
    # 觸發結果處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_process_trigger_results(self):
        """測試處理觸發結果並頒發成就."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        trigger_results = [
            TriggerResult(
                user_id=123,
                achievement_id=1,
                triggered=True,
                reason="達到目標",
                processing_time=25.0,
            ),
            TriggerResult(
                user_id=123,
                achievement_id=2,
                triggered=False,  # 未觸發
                reason="未達到目標",
            ),
            TriggerResult(
                user_id=456,
                achievement_id=1,
                triggered=True,
                reason="達到目標",
                error="處理錯誤",  # 有錯誤
            ),
        ]

        async with AchievementAwarder(
            repository=mock_repository, progress_tracker=mock_progress_tracker
        ) as awarder:
            with patch.object(awarder, "award_multiple_achievements") as mock_award:
                mock_award.return_value = []

                # Act
                await awarder.process_trigger_results(trigger_results)

        # Assert
        # 只有第一個結果應該被處理(觸發且無錯誤)
        mock_award.assert_called_once()
        award_requests = mock_award.call_args[0][0]
        assert len(award_requests) == 1
        assert award_requests[0].user_id == 123
        assert award_requests[0].achievement_id == 1

    # ==========================================================================
    # 事務和一致性測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_award_transaction_rollback_on_error(self):
        """測試頒發過程中事務回滾."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        test_achievement = Achievement(id=1, name="Test Achievement", is_active=True)
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        # 模擬事務和頒發過程中的錯誤
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx
        mock_repository.award_achievement.side_effect = Exception("頒發失敗")

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=False,
        ) as awarder:
            # Act
            result = await awarder.award_achievement(
                user_id=123, achievement_id=1, trigger_reason="測試觸發"
            )

        # Assert
        assert result.status == AwardStatus.FAILED
        assert "頒發失敗" in result.error_message
        mock_tx.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_award_same_achievement(self):
        """測試併發頒發相同成就的處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        test_achievement = Achievement(id=1, name="Test Achievement", is_active=True)
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )
        mock_repository.award_achievement.return_value = user_achievement

        # 模擬事務
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=False,
        ) as awarder:
            # Act - 同時發起兩個相同的頒發請求
            tasks = [
                awarder.award_achievement(123, 1, "觸發1"),
                awarder.award_achievement(123, 1, "觸發2"),
            ]
            results = await asyncio.gather(*tasks)

        # Assert
        # 其中一個應該成功,另一個應該被標記為重複
        success_count = sum(1 for r in results if r.status == AwardStatus.SUCCESS)
        duplicate_count = sum(1 for r in results if r.status == AwardStatus.DUPLICATE)

        assert success_count == 1
        assert duplicate_count == 1

    # ==========================================================================
    # 通知系統測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_achievement_notification_sent(self):
        """測試成就通知發送."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        test_achievement = Achievement(
            id=1,
            name="Test Achievement",
            description="測試成就",
            is_active=True,
            points=100,
            rarity="common",
        )
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )
        mock_repository.award_achievement.return_value = user_achievement

        # 模擬事務
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx

        # 創建通知處理器
        notification_handler = AsyncMock()

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=True,
        ) as awarder:
            awarder.add_notification_handler(notification_handler)

            # Act
            result = await awarder.award_achievement(
                user_id=123,
                achievement_id=1,
                trigger_reason="測試觸發",
                source_event="message_sent",
            )

        # Assert
        assert result.status == AwardStatus.SUCCESS
        assert result.notification_sent is True
        notification_handler.assert_called_once()

        # 檢查通知資料
        call_args = notification_handler.call_args[0][0]
        assert call_args["user_id"] == 123
        assert call_args["achievement"]["name"] == "Test Achievement"
        assert call_args["source_event"] == "message_sent"

    @pytest.mark.asyncio
    async def test_notification_handler_error_handling(self):
        """測試通知處理器錯誤處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        test_achievement = Achievement(id=1, name="Test", is_active=True)
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )
        mock_repository.award_achievement.return_value = user_achievement

        # 模擬事務
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx

        # 創建會拋出異常的通知處理器
        error_handler = AsyncMock(side_effect=Exception("通知失敗"))

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            notification_enabled=True,
        ) as awarder:
            awarder.add_notification_handler(error_handler)

            # Act
            result = await awarder.award_achievement(
                user_id=123, achievement_id=1, trigger_reason="測試觸發"
            )

        # Assert
        # 頒發應該成功,即使通知失敗
        assert result.status == AwardStatus.SUCCESS
        assert result.notification_sent is False  # 通知失敗

    # ==========================================================================
    # 統計和監控測試
    # ==========================================================================

    def test_award_stats_tracking(self):
        """測試頒發統計追蹤."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        awarder = AchievementAwarder(
            repository=mock_repository, progress_tracker=mock_progress_tracker
        )

        # Act
        awarder._update_award_stats(AwardStatus.SUCCESS, 100.0)
        awarder._update_award_stats(AwardStatus.FAILED, 200.0)
        awarder._update_award_stats(AwardStatus.DUPLICATE, 50.0)

        # Assert
        stats = awarder.get_award_stats()
        assert stats["total_awards"] == 3
        assert stats["successful_awards"] == 1
        assert stats["failed_awards"] == 1
        assert stats["duplicate_awards"] == 1
        assert stats["average_processing_time"] == 116.67  # (100+200+50)/3

    def test_notification_handler_management(self):
        """測試通知處理器管理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        awarder = AchievementAwarder(
            repository=mock_repository, progress_tracker=mock_progress_tracker
        )

        handler1 = AsyncMock()
        handler2 = AsyncMock()

        # Act
        awarder.add_notification_handler(handler1)
        awarder.add_notification_handler(handler2)
        awarder.add_notification_handler(handler1)  # 重複添加

        stats_before_remove = awarder.get_award_stats()

        awarder.remove_notification_handler(handler1)

        stats_after_remove = awarder.get_award_stats()

        # Assert
        assert stats_before_remove["notification_handlers"] == 2  # 不重複
        assert stats_after_remove["notification_handlers"] == 1

    # ==========================================================================
    # 超時和資源管理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_award_timeout_handling(self):
        """測試頒發超時處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_progress_tracker = AsyncMock()

        test_achievement = Achievement(id=1, is_active=True)
        mock_repository.get_achievement_by_id.return_value = test_achievement
        mock_repository.has_user_achievement.return_value = False

        # 模擬慢速頒發操作
        async def slow_award(*args, **kwargs):
            await asyncio.sleep(2)  # 比超時時間長
            return UserAchievement(
                id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
            )

        mock_repository.award_achievement.side_effect = slow_award

        # 模擬事務
        mock_tx = AsyncMock()
        mock_repository.transaction.return_value.__aenter__.return_value = mock_tx

        async with AchievementAwarder(
            repository=mock_repository,
            progress_tracker=mock_progress_tracker,
            award_timeout=1.0,  # 1秒超時
        ) as awarder:
            # Act
            result = await awarder.award_achievement(
                user_id=123, achievement_id=1, trigger_reason="測試觸發"
            )

        # Assert
        assert result.status == AwardStatus.FAILED
        assert "頒發超時" in result.error_message


# ==========================================================================
# 測試輔助函數和 Fixtures
# ==========================================================================


@pytest.fixture
def sample_award_request():
    """創建範例頒發請求."""
    return AwardRequest(
        user_id=123,
        achievement_id=1,
        trigger_reason="測試觸發",
        trigger_context={"message_count": 10},
        source_event="message_sent",
    )


@pytest.fixture
def sample_achievement():
    """創建範例成就."""
    return Achievement(
        id=1,
        name="Test Achievement",
        description="測試成就描述",
        type=AchievementType.COUNTER,
        criteria={"target_value": 10, "counter_field": "message_count"},
        is_active=True,
        points=100,
        rarity="common",
    )


@pytest.fixture
def sample_user_achievement():
    """創建範例用戶成就."""
    return UserAchievement(
        id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
    )


def create_award_request(
    user_id: int,
    achievement_id: int,
    trigger_reason: str = "測試觸發",
    priority: int = 0,
) -> AwardRequest:
    """創建頒發請求物件."""
    return AwardRequest(
        user_id=user_id,
        achievement_id=achievement_id,
        trigger_reason=trigger_reason,
        processing_priority=priority,
    )
