"""成就事件處理器測試模組.

測試事件資料處理系統的完整功能:
- 事件資料標準化
- 事件過濾邏輯
- 批次處理機制
- 效能和記憶體管理
"""

import time
from datetime import datetime, timedelta

import pytest

from src.cogs.achievement.database.models import AchievementEventData
from src.cogs.achievement.main.event_processor import (
    EventDataProcessor,
    create_event_type_filter,
    create_guild_whitelist_filter,
    create_rate_limit_filter,
    create_time_window_filter,
    create_user_whitelist_filter,
)


class TestEventDataProcessor:
    """事件資料處理器測試類別."""

    @pytest.fixture
    def processor(self):
        """建立事件處理器實例."""
        return EventDataProcessor(batch_size=5, batch_timeout=1.0, max_memory_events=50)

    # =============================================================================
    # 基本功能測試
    # =============================================================================

    def test_processor_initialization(self):
        """測試處理器初始化."""
        processor = EventDataProcessor(
            batch_size=10, batch_timeout=2.0, max_memory_events=100
        )

        assert processor.batch_size == 10
        assert processor.batch_timeout == 2.0
        assert processor.max_memory_events == 100
        assert len(processor._pending_events) == 0
        assert len(processor._standardization_rules) > 0

    @pytest.mark.asyncio
    async def test_event_structure_validation(self, processor):
        """測試事件結構驗證."""
        # 有效事件資料
        valid_event = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": {"is_bot": False},
            "timestamp": time.time(),
        }

        result = await processor.process_event(valid_event)
        assert result is not None
        assert isinstance(result, AchievementEventData)

        # 缺少必要欄位
        invalid_event = {
            "user_id": 12345,
            # 缺少 guild_id
            "event_type": "achievement.message_sent",
            "event_data": {"is_bot": False},
        }

        result = await processor.process_event(invalid_event)
        assert result is None

    # =============================================================================
    # 資料標準化測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_message_event_standardization(self, processor):
        """測試訊息事件標準化."""
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": {
                "content_length": "50",  # 字串格式
                "has_attachments": True,
                "mention_count": "3",  # 字串格式
                "is_bot": False,
            },
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)

        assert result is not None
        assert result.event_data["content_length"] == 50  # 轉換為整數
        assert result.event_data["mention_count"] == 3
        assert result.event_data["has_attachments"] is True

    @pytest.mark.asyncio
    async def test_reaction_event_standardization(self, processor):
        """測試反應事件標準化."""
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.reaction_added",
            "event_data": {"emoji": "👍", "is_custom_emoji": False, "is_bot": False},
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)

        assert result is not None
        assert result.event_data["emoji"] == "👍"
        assert result.event_data["is_custom_emoji"] is False
        assert "message_author_id" in result.event_data  # 應該被填入預設值

    @pytest.mark.asyncio
    async def test_voice_event_standardization(self, processor):
        """測試語音事件標準化."""
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.voice_joined",
            "event_data": {"joined_channel_id": 54321, "is_bot": False},
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)

        assert result is not None
        assert "joined_channel_name" in result.event_data  # 應該被填入預設值

    @pytest.mark.asyncio
    async def test_member_event_standardization(self, processor):
        """測試成員事件標準化."""
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.member_joined",
            "event_data": {
                "join_timestamp": time.time(),
                "roles_count": "-1",  # 無效值
                "is_bot": False,
            },
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)

        assert result is not None
        assert result.event_data["roles_count"] == 0  # 修正為非負數

    # =============================================================================
    # 事件過濾測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_custom_filter_addition(self, processor):
        """測試自訂過濾器新增."""

        # 新增過濾器
        def test_filter(event):
            return event.user_id != 99999

        processor.add_filter(test_filter, "test_filter")

        # 測試通過過濾器的事件
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": {"is_bot": False},
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)
        assert result is not None

        # 測試被過濾的事件
        event_data["user_id"] = 99999
        result = await processor.process_event(event_data)
        assert result is None

    @pytest.mark.asyncio
    async def test_bot_event_filtering(self, processor):
        """測試機器人事件過濾."""
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": {"is_bot": True},  # 機器人事件
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)
        assert result is None  # 應該被過濾

    @pytest.mark.asyncio
    async def test_invalid_event_type_filtering(self, processor):
        """測試無效事件類型過濾."""
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "invalid.event_type",  # 不以 achievement. 開頭
            "event_data": {"is_bot": False},
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)
        assert result is None  # 應該被過濾

    # =============================================================================
    # 批次處理測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_batch_size_trigger(self, processor):
        """測試批次大小觸發."""
        # 新增事件到批次
        batch_results = []
        for i in range(7):  # 超過批次大小 5
            event_data = {
                "user_id": 12345 + i,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            }

            batch = await processor.add_to_batch(event_data)
            if batch:
                batch_results.append(len(batch))

        # 應該有一個包含 5 個事件的批次
        assert len(batch_results) > 0
        assert max(batch_results) == 5

    @pytest.mark.asyncio
    async def test_batch_timeout_trigger(self, processor):
        """測試批次超時觸發."""
        # 新增少量事件
        for i in range(2):
            event_data = {
                "user_id": 12345 + i,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            }

            batch = await processor.add_to_batch(event_data)
            assert batch is None  # 還未達到批次大小

        # 模擬時間經過
        processor._last_batch_time = time.time() - 2.0  # 2 秒前

        # 再新增一個事件
        event_data = {
            "user_id": 12347,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": {"is_bot": False},
            "timestamp": time.time(),
        }

        batch = await processor.add_to_batch(event_data)
        assert batch is not None  # 應該因為超時而觸發批次
        assert len(batch) == 3  # 包含之前的 2 個 + 現在的 1 個

    @pytest.mark.asyncio
    async def test_batch_processing_with_invalid_events(self, processor):
        """測試包含無效事件的批次處理."""
        events = [
            {
                "user_id": 12345,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            },
            {
                # 缺少必要欄位
                "user_id": 12346,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            },
            {
                "user_id": 12347,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            },
        ]

        results = await processor.process_batch(events)

        # 應該只有 2 個有效事件被處理
        assert len(results) == 2
        assert all(isinstance(event, AchievementEventData) for event in results)

    # =============================================================================
    # 記憶體管理測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self):
        """測試記憶體限制執行."""
        processor = EventDataProcessor(max_memory_events=5)

        # 新增超過限制的事件
        for i in range(10):
            event_data = {
                "user_id": 12345 + i,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            }
            await processor.add_to_batch(event_data)

        # 檢查記憶體使用
        stats = processor.get_processing_stats()
        assert stats["pending_events_count"] <= 5

    @pytest.mark.asyncio
    async def test_flush_pending_events(self, processor):
        """測試強制清空待處理事件."""
        # 新增一些事件
        for i in range(3):
            event_data = {
                "user_id": 12345 + i,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            }
            await processor.add_to_batch(event_data)

        # 強制清空
        flushed_events = await processor.flush_pending_events()

        assert len(flushed_events) == 3
        assert processor.get_processing_stats()["pending_events_count"] == 0

    # =============================================================================
    # 統計資訊測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_processing_statistics(self, processor):
        """測試處理統計資訊."""
        # 初始統計
        stats = processor.get_processing_stats()
        assert stats["total_processed"] == 0
        assert stats["success_rate"] == 1.0

        # 處理一些事件
        valid_events = 5
        invalid_events = 3

        for i in range(valid_events):
            event_data = {
                "user_id": 12345 + i,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            }
            await processor.process_event(event_data)

        for i in range(invalid_events):
            event_data = {
                "user_id": 12345 + i,
                # 缺少 guild_id
                "event_type": "achievement.message_sent",
                "event_data": {"is_bot": False},
                "timestamp": time.time(),
            }
            await processor.process_event(event_data)

        # 檢查統計
        stats = processor.get_processing_stats()
        assert stats["total_processed"] == valid_events + invalid_events
        assert stats["validation_errors"] == invalid_events

    def test_clear_statistics(self, processor):
        """測試統計資訊清除."""
        # 設置一些統計資料
        processor._stats["total_processed"] = 100
        processor._stats["filtered_out"] = 10
        processor._filter_stats["test_filter"] = 5

        # 清除統計
        processor.clear_stats()

        # 驗證清除結果
        stats = processor.get_processing_stats()
        assert stats["total_processed"] == 0
        assert stats["filtered_out"] == 0
        assert len(stats["filter_stats"]) == 0

    # =============================================================================
    # 預設過濾器測試
    # =============================================================================

    def test_user_whitelist_filter(self):
        """測試用戶白名單過濾器."""
        whitelist = {12345, 54321}
        filter_func = create_user_whitelist_filter(whitelist)

        # 建立測試事件
        allowed_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        blocked_event = AchievementEventData(
            user_id=99999,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        assert filter_func(allowed_event) is True
        assert filter_func(blocked_event) is False

    def test_guild_whitelist_filter(self):
        """測試伺服器白名單過濾器."""
        whitelist = {67890, 11111}
        filter_func = create_guild_whitelist_filter(whitelist)

        allowed_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        blocked_event = AchievementEventData(
            user_id=12345,
            guild_id=99999,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        assert filter_func(allowed_event) is True
        assert filter_func(blocked_event) is False

    def test_event_type_filter(self):
        """測試事件類型過濾器."""
        allowed_types = {"achievement.message_sent", "achievement.reaction_added"}
        filter_func = create_event_type_filter(allowed_types)

        allowed_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        blocked_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.voice_joined",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        assert filter_func(allowed_event) is True
        assert filter_func(blocked_event) is False

    def test_time_window_filter(self):
        """測試時間窗口過濾器."""
        now = datetime.now()
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        filter_func = create_time_window_filter(start_time, end_time)

        allowed_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=now,
        )

        blocked_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=now - timedelta(hours=2),  # 超出時間窗口
        )

        assert filter_func(allowed_event) is True
        assert filter_func(blocked_event) is False

    def test_rate_limit_filter(self):
        """測試頻率限制過濾器."""
        filter_func = create_rate_limit_filter(
            max_events_per_user=2, time_window_minutes=60
        )

        event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"is_bot": False},
            timestamp=datetime.now(),
        )

        # 前兩個事件應該通過
        assert filter_func(event) is True
        assert filter_func(event) is True

        # 第三個事件應該被限制
        assert filter_func(event) is False

    # =============================================================================
    # 自訂標準化規則測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_custom_standardization_rule(self, processor):
        """測試自訂標準化規則."""

        # 新增自訂標準化規則
        def custom_rule(data):
            data["custom_field"] = "processed"
            return data

        processor.add_standardization_rule("achievement.custom_event", custom_rule)

        # 測試自訂事件
        event_data = {
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.custom_event",
            "event_data": {"is_bot": False},
            "timestamp": time.time(),
        }

        result = await processor.process_event(event_data)

        assert result is not None
        assert result.event_data["custom_field"] == "processed"
