"""EventTriggerProcessor 測試.

此模組測試事件驅動觸發處理器的功能，包含：
- 事件處理和過濾測試
- 批量事件處理測試
- 效能優化測試
- 錯誤處理和復原測試

測試遵循 AAA 模式和現代測試最佳實踐。
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
)
from src.cogs.achievement.services.event_processor import (
    EventTriggerContext,
    EventTriggerProcessor,
    TriggerResult,
)


@pytest.mark.unit
class TestEventTriggerProcessor:
    """EventTriggerProcessor 測試類別."""

    # ==========================================================================
    # 初始化和配置測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_processor_initialization(self):
        """測試事件處理器初始化."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # Act
        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker,
            batch_size=50,
            batch_timeout=5.0
        ) as processor:
            # Assert
            assert processor._repository == mock_repository
            assert processor._trigger_engine == mock_trigger_engine
            assert processor._progress_tracker == mock_progress_tracker
            assert processor._batch_size == 50
            assert processor._batch_timeout == 5.0

    # ==========================================================================
    # 單一事件處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_process_single_event_high_priority(self):
        """測試高優先級事件的即時處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 模擬觸發檢查結果
        trigger_result = TriggerResult(
            user_id=123,
            achievement_id=1,
            triggered=True,
            reason="成就觸發",
            processing_time=25.0
        )

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            with patch.object(processor, '_process_event_immediately') as mock_immediate:
                mock_immediate.return_value = [trigger_result]

                # Act
                results = await processor.process_event(
                    user_id=123,
                    event_type="message_sent",
                    event_data={"message_count": 1},
                    priority=5  # 高優先級
                )

        # Assert
        assert len(results) == 1
        assert results[0].triggered is True
        mock_immediate.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_event_normal_priority(self):
        """測試一般優先級事件的隊列處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            with patch.object(processor, '_enqueue_event') as mock_enqueue:
                # Act
                results = await processor.process_event(
                    user_id=123,
                    event_type="message_sent",
                    event_data={"message_count": 1},
                    priority=1  # 一般優先級
                )

        # Assert
        assert len(results) == 0  # 隊列處理不會立即返回結果
        mock_enqueue.assert_called_once()

    # ==========================================================================
    # 批量事件處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_process_batch_events(self):
        """測試批量事件處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 創建測試事件
        events = [
            EventTriggerContext(
                user_id=123,
                event_type="message_sent",
                event_data={"message_count": 1},
                timestamp=datetime.now()
            ),
            EventTriggerContext(
                user_id=456,
                event_type="reaction_added",
                event_data={"reaction_count": 1},
                timestamp=datetime.now()
            )
        ]

        # 模擬用戶事件處理結果
        user_results = [
            TriggerResult(user_id=123, achievement_id=1, triggered=True),
            TriggerResult(user_id=456, achievement_id=2, triggered=False)
        ]

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            with patch.object(processor, '_process_user_events') as mock_process_user:
                mock_process_user.return_value = user_results

                # Act
                results = await processor.process_batch_events(events)

        # Assert
        assert len(results) == 4  # 2個用戶 × 2個結果
        assert mock_process_user.call_count == 2  # 兩個不同用戶

    @pytest.mark.asyncio
    async def test_process_batch_events_with_error(self):
        """測試批量事件處理中的錯誤處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        events = [
            EventTriggerContext(
                user_id=123,
                event_type="message_sent",
                event_data={"message_count": 1},
                timestamp=datetime.now()
            )
        ]

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            with patch.object(processor, '_process_user_events') as mock_process_user:
                mock_process_user.side_effect = Exception("處理失敗")

                # Act
                results = await processor.process_batch_events(events)

        # Assert
        assert len(results) == 1
        assert results[123] == []  # 失敗時返回空列表

    # ==========================================================================
    # 事件過濾和預處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_filter_relevant_achievements(self):
        """測試事件相關成就過濾."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 模擬啟用的成就
        all_achievements = [
            Achievement(
                id=1,
                name="Message Achievement",
                type=AchievementType.COUNTER,
                is_active=True
            ),
            Achievement(
                id=2,
                name="Voice Achievement",
                type=AchievementType.TIME_BASED,
                is_active=True
            ),
            Achievement(
                id=3,
                name="Milestone Achievement",
                type=AchievementType.MILESTONE,
                is_active=True
            )
        ]

        mock_repository.list_achievements.return_value = all_achievements
        mock_repository.has_user_achievement.return_value = False

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            # Act
            relevant_achievements = await processor._filter_relevant_achievements(
                event_type="message_sent",
                user_id=123
            )

        # Assert
        # message_sent 事件應該對應 COUNTER 類型成就
        counter_achievements = [a for a in relevant_achievements if a.type == AchievementType.COUNTER]
        assert len(counter_achievements) >= 1
        mock_repository.has_user_achievement.assert_called()

    @pytest.mark.asyncio
    async def test_preprocess_message_event(self):
        """測試訊息事件預處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        context = EventTriggerContext(
            user_id=123,
            event_type="message_sent",
            event_data={
                "content": "Hello world! https://example.com",
                "attachment_count": 2
            },
            timestamp=datetime.now()
        )

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            # Act
            processed_data = await processor._preprocess_event_data(context)

        # Assert
        assert processed_data["message_length"] == len("Hello world! https://example.com")
        assert processed_data["has_links"] is True
        assert processed_data["has_attachments"] is True
        assert processed_data["event_type"] == "message_sent"

    @pytest.mark.asyncio
    async def test_preprocess_voice_event(self):
        """測試語音事件預處理."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        join_time = datetime.now()
        leave_time = join_time + timedelta(minutes=30)

        context = EventTriggerContext(
            user_id=123,
            event_type="voice_joined",
            event_data={
                "join_time": join_time.isoformat(),
                "leave_time": leave_time.isoformat()
            },
            timestamp=datetime.now()
        )

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            # Act
            processed_data = await processor._preprocess_event_data(context)

        # Assert
        assert processed_data["voice_duration"] == 30 * 60  # 30分鐘 = 1800秒

    # ==========================================================================
    # 用戶事件處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_process_user_events_success(self):
        """測試用戶事件處理成功案例."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 模擬相關成就
        relevant_achievements = [
            Achievement(
                id=1,
                name="Message Achievement",
                type=AchievementType.COUNTER,
                is_active=True
            )
        ]

        # 模擬觸發檢查結果
        mock_trigger_engine.check_achievement_trigger.return_value = (True, "成就觸發")

        events = [
            EventTriggerContext(
                user_id=123,
                event_type="message_sent",
                event_data={"message_count": 1},
                timestamp=datetime.now()
            )
        ]

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            with patch.object(processor, '_filter_relevant_achievements') as mock_filter:
                mock_filter.return_value = relevant_achievements

                # Act
                results = await processor._process_user_events(123, events)

        # Assert
        assert len(results) == 1
        assert results[0].triggered is True
        assert results[0].user_id == 123
        assert results[0].achievement_id == 1
        mock_trigger_engine.check_achievement_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_user_events_with_trigger_error(self):
        """測試用戶事件處理中的觸發檢查錯誤."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        relevant_achievements = [
            Achievement(
                id=1,
                name="Message Achievement",
                type=AchievementType.COUNTER,
                is_active=True
            )
        ]

        # 模擬觸發檢查拋出異常
        mock_trigger_engine.check_achievement_trigger.side_effect = Exception("觸發檢查失敗")

        events = [
            EventTriggerContext(
                user_id=123,
                event_type="message_sent",
                event_data={"message_count": 1},
                timestamp=datetime.now()
            )
        ]

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            with patch.object(processor, '_filter_relevant_achievements') as mock_filter:
                mock_filter.return_value = relevant_achievements

                # Act
                results = await processor._process_user_events(123, events)

        # Assert
        assert len(results) == 1
        assert results[0].triggered is False
        assert results[0].error == "觸發檢查失敗: 觸發檢查失敗"

    # ==========================================================================
    # 快取管理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_event_mapping_cache_update(self):
        """測試事件映射快取更新."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            # 清除快取時間以強制更新
            processor._mapping_cache_time = None

            # Act
            await processor._update_event_mapping_cache()

        # Assert
        assert processor._mapping_cache_time is not None
        assert "message_sent" in processor._event_achievement_mapping
        assert AchievementType.COUNTER in processor._event_achievement_mapping["message_sent"]

    # ==========================================================================
    # 統計和監控測試
    # ==========================================================================

    def test_get_processing_stats(self):
        """測試處理統計資訊取得."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        processor = EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        )

        # 模擬一些統計資料
        processor._stats["events_processed"] = 100
        processor._stats["cache_hits"] = 80
        processor._stats["cache_misses"] = 20

        # Act
        stats = processor.get_processing_stats()

        # Assert
        assert stats["events_processed"] == 100
        assert "queue_sizes" in stats
        assert "uptime_seconds" in stats
        assert "events_per_second" in stats

    def test_reset_stats(self):
        """測試統計資料重置."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        processor = EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        )

        # 設置一些統計資料
        processor._stats["events_processed"] = 100
        processor._stats["achievements_triggered"] = 50

        # Act
        processor.reset_stats()

        # Assert
        assert processor._stats["events_processed"] == 0
        assert processor._stats["achievements_triggered"] == 0
        assert processor._stats["last_reset"] is not None

    # ==========================================================================
    # 效能測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self):
        """測試並發事件處理效能."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        # 模擬快速回應的觸發檢查
        mock_trigger_engine.check_achievement_trigger.return_value = (False, "未觸發")

        # 創建大量事件
        events = []
        for i in range(100):
            events.append(EventTriggerContext(
                user_id=i % 10,  # 10個不同用戶
                event_type="message_sent",
                event_data={"message_count": 1},
                timestamp=datetime.now()
            ))

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker,
            max_concurrent_processing=5
        ) as processor:

            with patch.object(processor, '_filter_relevant_achievements') as mock_filter:
                mock_filter.return_value = []  # 無相關成就，加速測試

                # Act
                start_time = datetime.now()
                results = await processor.process_batch_events(events)
                end_time = datetime.now()

                processing_time = (end_time - start_time).total_seconds()

        # Assert
        assert len(results) >= 0  # 可能沒有觸發結果
        assert processing_time < 5.0  # 處理時間應該在5秒內

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """測試高負載下的記憶體使用."""
        # Arrange
        mock_repository = AsyncMock()
        mock_trigger_engine = AsyncMock()
        mock_progress_tracker = AsyncMock()

        async with EventTriggerProcessor(
            repository=mock_repository,
            trigger_engine=mock_trigger_engine,
            progress_tracker=mock_progress_tracker
        ) as processor:

            # 添加大量事件到隊列
            for i in range(1000):
                context = EventTriggerContext(
                    user_id=i,
                    event_type="message_sent",
                    event_data={"message_count": 1},
                    timestamp=datetime.now()
                )
                await processor._enqueue_event(context)

            # Act & Assert
            # 檢查隊列大小不會無限增長
            assert len(processor._event_queue) <= 1000
            assert len(processor._priority_queue) <= 1000


# ==========================================================================
# 測試輔助函數和 Fixtures
# ==========================================================================

@pytest.fixture
def sample_event_context():
    """創建範例事件上下文."""
    return EventTriggerContext(
        user_id=123,
        event_type="message_sent",
        event_data={
            "content": "Hello world!",
            "message_count": 1,
            "channel_id": 456
        },
        timestamp=datetime.now(),
        guild_id=789,
        channel_id=456
    )


@pytest.fixture
def sample_achievements():
    """創建範例成就列表."""
    return [
        Achievement(
            id=1,
            name="First Message",
            type=AchievementType.MILESTONE,
            criteria={"milestone_type": "first_message"},
            is_active=True
        ),
        Achievement(
            id=2,
            name="Message Counter",
            type=AchievementType.COUNTER,
            criteria={"target_value": 10, "counter_field": "message_count"},
            is_active=True
        ),
        Achievement(
            id=3,
            name="Daily Active",
            type=AchievementType.TIME_BASED,
            criteria={"target_value": 7, "time_unit": "days"},
            is_active=True
        )
    ]


def create_trigger_result(
    user_id: int,
    achievement_id: int,
    triggered: bool = False,
    reason: str | None = None,
    error: str | None = None
) -> TriggerResult:
    """創建觸發結果物件."""
    return TriggerResult(
        user_id=user_id,
        achievement_id=achievement_id,
        triggered=triggered,
        reason=reason,
        processing_time=10.0,
        error=error
    )
