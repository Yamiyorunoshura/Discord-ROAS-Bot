"""成就事件監聽器測試模組.

測試成就事件監聽器的完整功能：
- 事件監聽和過濾
- 事件資料處理
- 事件持久化
- 效能和負載測試
- 錯誤處理驗證
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from src.cogs.achievement.database.models import AchievementEventData
from src.cogs.achievement.database.repository import AchievementEventRepository
from src.cogs.achievement.main.event_processor import EventDataProcessor
from src.cogs.achievement.main.tracker import AchievementEventListener
from src.cogs.core.event_bus import Event, EventBus


class TestAchievementEventListener:
    """成就事件監聽器測試類別."""

    @pytest.fixture
    async def mock_bot(self):
        """模擬 Discord 機器人."""
        bot = MagicMock(spec=commands.Bot)
        return bot

    @pytest.fixture
    async def mock_achievement_service(self):
        """模擬成就服務."""
        service = AsyncMock()
        return service

    @pytest.fixture
    async def mock_database_pool(self):
        """模擬資料庫連線池."""
        return AsyncMock()

    @pytest.fixture
    async def mock_event_bus(self):
        """模擬 EventBus."""
        event_bus = AsyncMock(spec=EventBus)
        return event_bus

    @pytest.fixture
    async def event_listener(self, mock_bot, mock_achievement_service, mock_database_pool):
        """建立事件監聽器實例."""
        listener = AchievementEventListener(mock_bot)

        # 模擬初始化
        with patch('src.cogs.achievement.main.tracker.get_global_event_bus') as mock_get_bus, \
             patch('src.core.database.get_logger') as mock_get_logger:
            mock_event_bus = AsyncMock(spec=EventBus)
            mock_get_bus.return_value = mock_event_bus
            mock_get_logger.return_value = MagicMock()

            await listener.initialize(mock_achievement_service, mock_database_pool)

        return listener

    # =============================================================================
    # Task 5.1: 事件監聽器單元測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_listener_initialization(self, mock_bot, mock_achievement_service, mock_database_pool):
        """測試事件監聽器初始化."""
        listener = AchievementEventListener(mock_bot)

        with patch('src.cogs.achievement.main.tracker.get_global_event_bus') as mock_get_bus:
            mock_event_bus = AsyncMock(spec=EventBus)
            mock_get_bus.return_value = mock_event_bus

            await listener.initialize(mock_achievement_service, mock_database_pool)

            # 驗證初始化狀態
            assert listener.achievement_service == mock_achievement_service
            assert listener.event_repository is not None
            assert listener.event_processor is not None
            assert listener.event_bus is not None

            # 驗證 EventBus 訂閱
            mock_event_bus.subscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_discord_event_types(self, event_listener):
        """測試 Discord 事件類型常數."""
        event_types = event_listener.EVENT_TYPES

        # 驗證所有必要的事件類型都存在
        expected_types = [
            'MESSAGE_SENT', 'MESSAGE_EDITED', 'MESSAGE_DELETED',
            'REACTION_ADDED', 'REACTION_REMOVED',
            'VOICE_JOINED', 'VOICE_LEFT', 'VOICE_MOVED',
            'MEMBER_JOINED', 'MEMBER_LEFT', 'MEMBER_UPDATED',
            'COMMAND_USED', 'SLASH_COMMAND_USED'
        ]

        for event_type in expected_types:
            assert event_type in event_types
            assert event_types[event_type].startswith('achievement.')

    @pytest.mark.asyncio
    async def test_message_event_handling(self, event_listener):
        """測試訊息事件處理."""
        # 模擬 Discord 訊息
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author.bot = False
        mock_message.guild.id = 12345
        mock_message.author.id = 54321
        mock_message.channel.id = 67890
        mock_message.id = 98765
        mock_message.content = "Test message"
        mock_message.attachments = []
        mock_message.embeds = []
        mock_message.mentions = []

        # 模擬事件發布
        with patch.object(event_listener.event_bus, 'publish') as mock_publish:
            await event_listener.on_message(mock_message)

            # 驗證事件發布
            mock_publish.assert_called_once()
            published_event = mock_publish.call_args[0][0]

            assert published_event.event_type == 'achievement.message_sent'
            assert published_event.data['user_id'] == 54321
            assert published_event.data['guild_id'] == 12345

    @pytest.mark.asyncio
    async def test_voice_event_handling(self, event_listener):
        """測試語音事件處理."""
        # 模擬成員和語音狀態
        mock_member = MagicMock(spec=discord.Member)
        mock_member.bot = False
        mock_member.id = 12345
        mock_member.guild.id = 67890

        mock_before = MagicMock(spec=discord.VoiceState)
        mock_before.channel = None

        mock_after = MagicMock(spec=discord.VoiceState)
        mock_after.channel = MagicMock()
        mock_after.channel.id = 54321
        mock_after.channel.name = "General"

        # 模擬事件發布
        with patch.object(event_listener.event_bus, 'publish') as mock_publish:
            await event_listener.on_voice_state_update(mock_member, mock_before, mock_after)

            # 驗證事件發布
            mock_publish.assert_called_once()
            published_event = mock_publish.call_args[0][0]

            assert published_event.event_type == 'achievement.voice_joined'
            assert published_event.data['user_id'] == 12345

    @pytest.mark.asyncio
    async def test_bot_event_filtering(self, event_listener):
        """測試機器人事件過濾."""
        # 模擬機器人訊息
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author.bot = True
        mock_message.guild = MagicMock()

        # 模擬事件發布
        with patch.object(event_listener.event_bus, 'publish') as mock_publish:
            await event_listener.on_message(mock_message)

            # 驗證機器人事件不被發布
            mock_publish.assert_not_called()

    # =============================================================================
    # Task 5.2: 事件資料處理測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_event_data_processor_initialization(self):
        """測試事件資料處理器初始化."""
        processor = EventDataProcessor(
            batch_size=10,
            batch_timeout=1.0,
            max_memory_events=100
        )

        assert processor.batch_size == 10
        assert processor.batch_timeout == 1.0
        assert processor.max_memory_events == 100
        assert len(processor._filters) == 0
        assert len(processor._standardization_rules) > 0  # 預設規則

    @pytest.mark.asyncio
    async def test_event_data_standardization(self):
        """測試事件資料標準化."""
        processor = EventDataProcessor()

        # 測試訊息事件標準化
        event_data = {
            'user_id': 12345,
            'guild_id': 67890,
            'event_type': 'achievement.message_sent',
            'event_data': {
                'content_length': '50',  # 字串型別
                'has_attachments': 'true',  # 字串型別
                'mention_count': '3'  # 字串型別
            },
            'timestamp': time.time()
        }

        processed_event = await processor.process_event(event_data)

        assert processed_event is not None
        assert processed_event.event_data['content_length'] == 50  # 轉換為整數
        assert processed_event.event_data['mention_count'] == 3

    @pytest.mark.asyncio
    async def test_event_filtering(self):
        """測試事件過濾功能."""
        processor = EventDataProcessor()

        # 新增測試過濾器
        def test_filter(event):
            return event.user_id != 99999  # 過濾特定用戶

        processor.add_filter(test_filter, "test_filter")

        # 測試通過過濾器的事件
        event_data = {
            'user_id': 12345,
            'guild_id': 67890,
            'event_type': 'achievement.message_sent',
            'event_data': {'is_bot': False},
            'timestamp': time.time()
        }

        processed_event = await processor.process_event(event_data)
        assert processed_event is not None

        # 測試被過濾的事件
        event_data['user_id'] = 99999
        processed_event = await processor.process_event(event_data)
        assert processed_event is None

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """測試批次處理功能."""
        processor = EventDataProcessor(batch_size=3, batch_timeout=0.1)

        # 建立測試事件
        events = []
        for i in range(5):
            event_data = {
                'user_id': 12345 + i,
                'guild_id': 67890,
                'event_type': 'achievement.message_sent',
                'event_data': {'is_bot': False},
                'timestamp': time.time()
            }
            events.append(event_data)

        # 測試批次處理
        batch_results = []
        for event_data in events:
            batch = await processor.add_to_batch(event_data)
            if batch:
                batch_results.append(len(batch))

        # 應該有一個包含 3 個事件的批次
        assert len(batch_results) > 0
        assert max(batch_results) >= 3

    # =============================================================================
    # Task 5.3: 事件持久化測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_event_repository_creation(self):
        """測試事件儲存庫建立."""
        mock_pool = AsyncMock()
        repository = AchievementEventRepository(mock_pool)

        assert repository.table_name == "achievement_events"
        assert repository.pool == mock_pool

    @pytest.mark.asyncio
    async def test_single_event_persistence(self):
        """測試單個事件持久化."""
        mock_pool = AsyncMock()
        repository = AchievementEventRepository(mock_pool)

        # 模擬資料庫執行結果
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        repository.execute_query = AsyncMock(return_value=mock_result)

        # 建立測試事件
        event_data = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type='achievement.message_sent',
            event_data={'content_length': 50},
            timestamp=datetime.now()
        )

        # 測試建立事件
        created_event = await repository.create_event(event_data)

        assert created_event.id == 123
        assert created_event.user_id == 12345
        repository.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_event_persistence(self):
        """測試批次事件持久化."""
        mock_pool = AsyncMock()
        repository = AchievementEventRepository(mock_pool)
        repository.execute_batch = AsyncMock()

        # 建立測試事件批次
        events = []
        for i in range(5):
            event = AchievementEventData(
                user_id=12345 + i,
                guild_id=67890,
                event_type='achievement.message_sent',
                event_data={'content_length': 50 + i},
                timestamp=datetime.now()
            )
            events.append(event)

        # 測試批次建立
        created_events = await repository.create_events_batch(events)

        assert len(created_events) == 5
        repository.execute_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_querying(self):
        """測試事件查詢功能."""
        mock_pool = AsyncMock()
        repository = AchievementEventRepository(mock_pool)

        # 模擬查詢結果
        mock_rows = [
            {
                'id': 1,
                'user_id': 12345,
                'guild_id': 67890,
                'event_type': 'achievement.message_sent',
                'event_data': '{"content_length": 50}',
                'timestamp': datetime.now(),
                'channel_id': None,
                'processed': False,
                'correlation_id': None
            }
        ]
        repository.execute_query = AsyncMock(return_value=mock_rows)

        # 測試用戶事件查詢
        await repository.get_events_by_user(12345, limit=10)

        repository.execute_query.assert_called_once()
        # 由於模擬返回的是原始資料，實際實作中會轉換為 AchievementEventData

    # =============================================================================
    # Task 5.4: 效能測試和負載驗證
    # =============================================================================

    @pytest.mark.asyncio
    async def test_event_processing_performance(self):
        """測試事件處理效能."""
        processor = EventDataProcessor(batch_size=100)

        # 建立大量測試事件
        events = []
        for i in range(1000):
            event_data = {
                'user_id': 12345 + (i % 100),
                'guild_id': 67890,
                'event_type': 'achievement.message_sent',
                'event_data': {'is_bot': False, 'content_length': i},
                'timestamp': time.time()
            }
            events.append(event_data)

        # 測量處理時間
        start_time = time.time()

        processed_events = []
        for event_data in events:
            processed_event = await processor.process_event(event_data)
            if processed_event:
                processed_events.append(processed_event)

        processing_time = time.time() - start_time

        # 驗證效能要求
        assert processing_time < 10.0  # 1000 個事件應在 10 秒內完成
        assert len(processed_events) > 0

        # 驗證平均處理時間
        avg_time_per_event = processing_time / len(events)
        assert avg_time_per_event < 0.1  # 每個事件平均處理時間 < 100ms

    @pytest.mark.asyncio
    async def test_concurrent_event_handling(self, event_listener):
        """測試併發事件處理."""
        # 建立多個測試事件
        test_events = []
        for i in range(50):
            event = Event(
                event_type='achievement.message_sent',
                data={
                    'user_id': 12345 + i,
                    'guild_id': 67890,
                    'channel_id': 11111,
                    'is_bot': False
                },
                timestamp=time.time()
            )
            test_events.append(event)

        # 模擬批次持久化
        event_listener._persist_event_batch = AsyncMock()

        # 併發處理事件
        start_time = time.time()
        tasks = [event_listener._handle_achievement_event(event) for event in test_events]
        await asyncio.gather(*tasks, return_exceptions=True)
        processing_time = time.time() - start_time

        # 驗證併發處理效能
        assert processing_time < 5.0  # 50 個事件併發處理應在 5 秒內完成

        # 驗證統計資訊
        stats = event_listener.get_event_stats()
        assert stats['total_events'] >= 50

    @pytest.mark.asyncio
    async def test_memory_usage_control(self):
        """測試記憶體使用控制."""
        processor = EventDataProcessor(max_memory_events=10)

        # 添加超過限制的事件
        for i in range(20):
            event_data = {
                'user_id': 12345 + i,
                'guild_id': 67890,
                'event_type': 'achievement.message_sent',
                'event_data': {'is_bot': False},
                'timestamp': time.time()
            }
            await processor.add_to_batch(event_data)

        # 驗證記憶體限制
        stats = processor.get_processing_stats()
        assert stats['pending_events_count'] <= 10

    # =============================================================================
    # Task 5.5: 整合測試和錯誤處理驗證
    # =============================================================================

    @pytest.mark.asyncio
    async def test_end_to_end_integration(self, mock_bot, mock_achievement_service, mock_database_pool):
        """測試端到端整合."""
        # 建立完整的事件監聽器
        listener = AchievementEventListener(mock_bot)

        # 模擬初始化
        with patch('src.cogs.achievement.main.tracker.get_global_event_bus') as mock_get_bus:
            mock_event_bus = AsyncMock(spec=EventBus)
            mock_get_bus.return_value = mock_event_bus

            await listener.initialize(mock_achievement_service, mock_database_pool)

        # 模擬 Discord 訊息事件
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author.bot = False
        mock_message.guild.id = 12345
        mock_message.author.id = 54321
        mock_message.channel.id = 67890
        mock_message.id = 98765
        mock_message.content = "Test message"
        mock_message.attachments = []
        mock_message.embeds = []
        mock_message.mentions = []

        # 模擬事件處理
        await listener.on_message(mock_message)

        # 驗證事件發布
        listener.event_bus.publish.assert_called_once()

        # 驗證統計更新
        stats = listener.get_event_stats()
        assert 'total_events' in stats
        assert 'event_types' in stats

    @pytest.mark.asyncio
    async def test_error_handling_in_event_processing(self, event_listener):
        """測試事件處理中的錯誤處理."""
        # 模擬處理器故障
        event_listener.event_processor.add_to_batch = AsyncMock(side_effect=Exception("Test error"))

        # 建立測試事件
        test_event = Event(
            event_type='achievement.message_sent',
            data={
                'user_id': 12345,
                'guild_id': 67890,
                'is_bot': False
            },
            timestamp=time.time()
        )

        # 處理事件（不應該崩潰）
        await event_listener._handle_achievement_event(test_event)

        # 驗證錯誤統計
        stats = event_listener.get_event_stats()
        assert stats['failed_events'] > 0

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """測試資料庫錯誤處理."""
        mock_pool = AsyncMock()
        repository = AchievementEventRepository(mock_pool)

        # 模擬資料庫錯誤
        repository.execute_query = AsyncMock(side_effect=Exception("Database error"))

        # 測試事件建立錯誤處理
        event_data = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type='achievement.message_sent',
            event_data={'content_length': 50},
            timestamp=datetime.now()
        )

        # 應該拋出異常
        with pytest.raises(Exception, match="Database error"):
            await repository.create_event(event_data)

    @pytest.mark.asyncio
    async def test_cleanup_handling(self, event_listener):
        """測試清理處理."""
        # 模擬待處理事件
        mock_pending_events = [
            AchievementEventData(
                user_id=12345,
                guild_id=67890,
                event_type='achievement.message_sent',
                event_data={'content_length': 50},
                timestamp=datetime.now()
            )
        ]

        event_listener.event_processor.flush_pending_events = AsyncMock(return_value=mock_pending_events)
        event_listener._persist_event_batch = AsyncMock()

        # 執行清理
        await event_listener.cleanup()

        # 驗證清理邏輯
        event_listener.event_processor.flush_pending_events.assert_called_once()
        event_listener._persist_event_batch.assert_called_once_with(mock_pending_events)

    @pytest.mark.asyncio
    async def test_data_consistency_validation(self):
        """測試資料一致性驗證."""
        # 測試事件資料模型驗證

        # 有效資料
        valid_data = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type='achievement.message_sent',
            event_data={'content_length': 50, 'is_bot': False},
            timestamp=datetime.now()
        )

        assert valid_data.is_achievement_relevant()
        assert valid_data.user_id == 12345

        # 無效事件類型
        with pytest.raises(ValueError):
            AchievementEventData(
                user_id=12345,
                guild_id=67890,
                event_type='invalid.type',  # 不以 'achievement.' 開頭
                event_data={'is_bot': False},
                timestamp=datetime.now()
            )

        # 未來時間戳
        with pytest.raises(ValueError):
            AchievementEventData(
                user_id=12345,
                guild_id=67890,
                event_type='achievement.message_sent',
                event_data={'is_bot': False},
                timestamp=datetime.now() + timedelta(days=1)  # 未來時間
            )

    @pytest.mark.asyncio
    async def test_rate_limiting_filter(self):
        """測試頻率限制過濾器."""
        from src.cogs.achievement.main.event_processor import create_rate_limit_filter

        # 建立頻率限制過濾器
        rate_filter = create_rate_limit_filter(max_events_per_user=3, time_window_minutes=1)

        # 建立測試事件
        base_event = AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type='achievement.message_sent',
            event_data={'is_bot': False},
            timestamp=datetime.now()
        )

        # 測試頻率限制
        results = []
        for _i in range(5):
            result = rate_filter(base_event)
            results.append(result)

        # 前 3 個應該通過，後 2 個被限制
        assert sum(results) == 3
        assert results[:3] == [True, True, True]
        assert results[3:] == [False, False]

    def test_processing_statistics(self):
        """測試處理統計資訊."""
        processor = EventDataProcessor()

        # 初始統計
        stats = processor.get_processing_stats()
        assert stats['total_processed'] == 0
        assert stats['filtered_out'] == 0
        assert stats['success_rate'] == 1.0

        # 模擬處理一些事件後的統計
        processor._stats['total_processed'] = 100
        processor._stats['filtered_out'] = 10
        processor._stats['validation_errors'] = 5

        stats = processor.get_processing_stats()
        assert stats['total_processed'] == 100
        assert stats['success_rate'] == 0.85  # (100-10-5)/100
