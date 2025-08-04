"""成就事件持久化測試模組.

測試成就事件資料存取層的完整功能:
- 事件資料庫操作
- 批次處理功能
- 查詢和統計功能
- 資料清理和歸檔
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cogs.achievement.database.models import AchievementEventData
from src.cogs.achievement.database.repository import AchievementEventRepository


class TestAchievementEventRepository:
    """成就事件資料存取庫測試類別."""

    @pytest.fixture
    def mock_pool(self):
        """模擬資料庫連線池."""
        return AsyncMock()

    @pytest.fixture
    def repository(self, mock_pool):
        """建立事件資料存取庫實例."""
        # 使用 patch 跳過 logger 初始化以避免 MagicMock 比較問題
        with patch("src.core.database.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            return AchievementEventRepository(mock_pool)

    @pytest.fixture
    def sample_event_data(self):
        """建立範例事件資料."""
        return AchievementEventData(
            user_id=12345,
            guild_id=67890,
            event_type="achievement.message_sent",
            event_data={"content_length": 50, "is_bot": False},
            timestamp=datetime.now(),
            channel_id=11111,
            processed=False,
            correlation_id="test-correlation-123",
        )

    # =============================================================================
    # 基本 CRUD 操作測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_single_event(self, repository, sample_event_data):
        """測試建立單個事件."""
        # 模擬資料庫執行結果
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        repository.execute_query = AsyncMock(return_value=mock_result)

        # 測試建立事件
        created_event = await repository.create_event(sample_event_data)

        assert created_event.id == 123
        assert created_event.user_id == sample_event_data.user_id
        assert created_event.guild_id == sample_event_data.guild_id

        # 驗證 SQL 調用
        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        assert "INSERT INTO achievement_events" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_events_batch(self, repository):
        """測試批次建立事件."""
        # 建立測試事件批次
        events = []
        for i in range(5):
            event = AchievementEventData(
                user_id=12345 + i,
                guild_id=67890,
                event_type="achievement.message_sent",
                event_data={"content_length": 50 + i, "is_bot": False},
                timestamp=datetime.now(),
            )
            events.append(event)

        repository.execute_batch = AsyncMock()

        # 測試批次建立
        created_events = await repository.create_events_batch(events)

        assert len(created_events) == 5
        repository.execute_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_by_id(self, repository):
        """測試根據 ID 取得事件."""
        # 模擬資料庫查詢結果
        mock_row = {
            "id": 123,
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": '{"content_length": 50, "is_bot": false}',
            "timestamp": datetime.now(),
            "channel_id": 11111,
            "processed": False,
            "correlation_id": "test-123",
        }

        repository.execute_query = AsyncMock(return_value=mock_row)

        # 測試取得事件
        event = await repository.get_event_by_id(123)

        assert event is not None
        repository.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_by_id_not_found(self, repository):
        """測試取得不存在的事件."""
        repository.execute_query = AsyncMock(return_value=None)

        event = await repository.get_event_by_id(999)

        assert event is None

    # =============================================================================
    # 查詢功能測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_get_events_by_user(self, repository):
        """測試取得用戶事件."""
        # 模擬查詢結果
        mock_rows = [
            {
                "id": 1,
                "user_id": 12345,
                "guild_id": 67890,
                "event_type": "achievement.message_sent",
                "event_data": '{"content_length": 50}',
                "timestamp": datetime.now(),
                "channel_id": None,
                "processed": False,
                "correlation_id": None,
            },
            {
                "id": 2,
                "user_id": 12345,
                "guild_id": 67890,
                "event_type": "achievement.reaction_added",
                "event_data": '{"emoji": "👍"}',
                "timestamp": datetime.now(),
                "channel_id": None,
                "processed": False,
                "correlation_id": None,
            },
        ]

        repository.execute_query = AsyncMock(return_value=mock_rows)

        # 測試取得用戶事件
        await repository.get_events_by_user(12345, limit=10)

        repository.execute_query.assert_called_once()
        # 驗證查詢參數
        call_args = repository.execute_query.call_args
        assert "user_id" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_events_by_user_with_filters(self, repository):
        """測試使用過濾器取得用戶事件."""
        repository.execute_query = AsyncMock(return_value=[])

        start_time = datetime.now() - timedelta(days=1)
        end_time = datetime.now()
        event_types = ["achievement.message_sent", "achievement.reaction_added"]

        # 測試帶過濾器的查詢
        await repository.get_events_by_user(
            user_id=12345,
            event_types=event_types,
            start_time=start_time,
            end_time=end_time,
            limit=50,
            offset=10,
        )

        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        sql = call_args[0][0]

        # 驗證 SQL 包含過濾條件
        assert "user_id" in sql
        assert "event_type" in sql
        assert "timestamp" in sql
        assert "LIMIT" in sql

    @pytest.mark.asyncio
    async def test_get_events_by_guild(self, repository):
        """測試取得伺服器事件."""
        repository.execute_query = AsyncMock(return_value=[])

        # 測試取得伺服器事件
        await repository.get_events_by_guild(67890, limit=20)

        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        assert "guild_id" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_unprocessed_events(self, repository):
        """測試取得未處理事件."""
        repository.execute_query = AsyncMock(return_value=[])

        # 測試取得未處理事件
        await repository.get_unprocessed_events(limit=100)

        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        sql = call_args[0][0]

        assert "processed" in sql
        assert "ORDER BY timestamp ASC" in sql

    @pytest.mark.asyncio
    async def test_mark_events_processed(self, repository):
        """測試標記事件為已處理."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        repository.execute_query = AsyncMock(return_value=mock_result)

        # 測試標記事件處理
        event_ids = [1, 2, 3]
        updated_count = await repository.mark_events_processed(event_ids)

        assert updated_count == 3
        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        assert "UPDATE" in call_args[0][0]
        assert "processed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_mark_events_processed_empty_list(self, repository):
        """測試標記空列表事件."""
        updated_count = await repository.mark_events_processed([])

        assert updated_count == 0
        # 不應該調用資料庫
        assert (
            not hasattr(repository, "execute_query")
            or not repository.execute_query.called
        )

    # =============================================================================
    # 統計功能測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_get_event_stats_basic(self, repository):
        """測試基本事件統計."""
        # 模擬基本統計查詢結果
        mock_stats_row = {
            "total_events": 100,
            "processed_events": 80,
            "unprocessed_events": 20,
            "unique_users": 25,
            "earliest_event": datetime.now() - timedelta(days=30),
            "latest_event": datetime.now(),
        }

        # 模擬事件類型統計查詢結果
        mock_type_rows = [
            {"event_type": "achievement.message_sent", "count": 60},
            {"event_type": "achievement.reaction_added", "count": 30},
            {"event_type": "achievement.voice_joined", "count": 10},
        ]

        repository.execute_query = AsyncMock(
            side_effect=[mock_stats_row, mock_type_rows]
        )

        # 測試取得統計
        stats = await repository.get_event_stats()

        assert stats["total_events"] == 100
        assert stats["processed_events"] == 80
        assert stats["unprocessed_events"] == 20
        assert len(stats["event_types"]) == 3
        assert stats["event_types"]["achievement.message_sent"] == 60

    @pytest.mark.asyncio
    async def test_get_event_stats_with_filters(self, repository):
        """測試帶過濾器的事件統計."""
        repository.execute_query = AsyncMock(side_effect=[{}, []])

        # 測試帶過濾器的統計
        await repository.get_event_stats(
            guild_id=67890,
            user_id=12345,
            start_time=datetime.now() - timedelta(days=7),
            end_time=datetime.now(),
        )

        # 驗證兩次查詢調用
        assert repository.execute_query.call_count == 2

    @pytest.mark.asyncio
    async def test_get_event_stats_error_handling(self, repository):
        """測試統計查詢錯誤處理."""
        repository.execute_query = AsyncMock(side_effect=Exception("Database error"))

        # 測試錯誤處理
        stats = await repository.get_event_stats()

        assert stats == {}  # 應該返回空字典

    # =============================================================================
    # 資料清理和歸檔測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_cleanup_old_events(self, repository):
        """測試清理舊事件."""
        # 模擬計數查詢
        mock_count_result = {"COUNT(*)": 1000}

        # 模擬刪除結果
        mock_delete_results = [
            MagicMock(rowcount=500),
            MagicMock(rowcount=500),
            MagicMock(rowcount=0),  # 最後一次沒有更多資料
        ]

        repository.execute_query = AsyncMock(
            side_effect=[mock_count_result, *mock_delete_results]
        )

        # 測試清理
        deleted_count = await repository.cleanup_old_events(
            older_than_days=30, batch_size=500, keep_processed=True
        )

        assert deleted_count == 1000
        # 應該調用 1 次計數 + 2 次刪除
        assert repository.execute_query.call_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_old_events_no_data(self, repository):
        """測試清理無舊資料情況."""
        mock_count_result = {"COUNT(*)": 0}
        repository.execute_query = AsyncMock(return_value=mock_count_result)

        # 測試清理
        deleted_count = await repository.cleanup_old_events()

        assert deleted_count == 0
        # 只應該調用一次計數查詢
        repository.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_old_events(self, repository):
        """測試歸檔舊事件."""
        mock_result = MagicMock()
        mock_result.rowcount = 500
        repository.execute_query = AsyncMock(return_value=mock_result)

        # 測試歸檔
        archived_count = await repository.archive_old_events(
            older_than_days=90, archive_table="test_archive"
        )

        assert archived_count == 500
        # 應該調用多次:建立歸檔表 + 插入 + 刪除
        assert repository.execute_query.call_count >= 2

    @pytest.mark.asyncio
    async def test_ensure_archive_table_exists(self, repository):
        """測試確保歸檔表存在."""
        repository.execute_query = AsyncMock()

        # 測試私有方法
        await repository._ensure_archive_table_exists("test_archive")

        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        assert "CREATE TABLE IF NOT EXISTS test_archive" in call_args[0][0]

    # =============================================================================
    # 資料模型轉換測試
    # =============================================================================

    def test_row_to_event_model(self, repository):
        """測試資料庫行轉換為事件模型."""
        mock_row = {
            "id": 123,
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": '{"content_length": 50, "is_bot": false}',
            "timestamp": datetime.now(),
            "channel_id": 11111,
            "processed": True,
            "correlation_id": "test-123",
        }

        # 模擬 _row_to_dict 方法
        repository._row_to_dict = MagicMock(return_value=mock_row)

        # 測試轉換
        event = repository._row_to_event_model(mock_row)

        assert isinstance(event, AchievementEventData)
        assert event.id == 123
        assert event.user_id == 12345
        assert event.guild_id == 67890
        assert event.event_type == "achievement.message_sent"
        assert event.event_data["content_length"] == 50
        assert event.processed is True

    def test_row_to_event_model_with_string_timestamp(self, repository):
        """測試字串時間戳轉換."""
        mock_row = {
            "id": 123,
            "user_id": 12345,
            "guild_id": 67890,
            "event_type": "achievement.message_sent",
            "event_data": "{}",
            "timestamp": "2024-01-01T12:00:00",  # 字串格式
            "channel_id": None,
            "processed": False,
            "correlation_id": None,
        }

        repository._row_to_dict = MagicMock(return_value=mock_row)

        # 測試轉換
        event = repository._row_to_event_model(mock_row)

        assert isinstance(event.timestamp, datetime)

    # =============================================================================
    # 錯誤處理測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_event_database_error(self, repository, sample_event_data):
        """測試建立事件資料庫錯誤處理."""
        repository.execute_query = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        # 測試錯誤處理
        with pytest.raises(Exception, match="Database connection failed"):
            await repository.create_event(sample_event_data)

    @pytest.mark.asyncio
    async def test_create_events_batch_error(self, repository):
        """測試批次建立事件錯誤處理."""
        events = [
            AchievementEventData(
                user_id=12345,
                guild_id=67890,
                event_type="achievement.message_sent",
                event_data={"is_bot": False},
                timestamp=datetime.now(),
            )
        ]

        repository.execute_batch = AsyncMock(
            side_effect=Exception("Batch insert failed")
        )

        # 測試錯誤處理
        with pytest.raises(Exception, match="Batch insert failed"):
            await repository.create_events_batch(events)

    @pytest.mark.asyncio
    async def test_get_event_by_id_error(self, repository):
        """測試取得事件錯誤處理."""
        repository.execute_query = AsyncMock(side_effect=Exception("Query failed"))

        # 測試錯誤處理
        event = await repository.get_event_by_id(123)

        assert event is None  # 錯誤時應該返回 None

    @pytest.mark.asyncio
    async def test_cleanup_old_events_error(self, repository):
        """測試清理事件錯誤處理."""
        repository.execute_query = AsyncMock(side_effect=Exception("Cleanup failed"))

        # 測試錯誤處理
        deleted_count = await repository.cleanup_old_events()

        assert deleted_count == 0  # 錯誤時應該返回 0

    # =============================================================================
    # 邊界情況測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_events_batch_empty_list(self, repository):
        """測試建立空事件列表."""
        result = await repository.create_events_batch([])

        assert result == []
        # 不應該調用資料庫
        assert (
            not hasattr(repository, "execute_batch")
            or not repository.execute_batch.called
        )

    @pytest.mark.asyncio
    async def test_get_events_with_zero_limit(self, repository):
        """測試限制為 0 的查詢."""
        repository.execute_query = AsyncMock(return_value=[])

        await repository.get_events_by_user(12345, limit=0)

        repository.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_events_with_large_offset(self, repository):
        """測試大偏移量查詢."""
        repository.execute_query = AsyncMock(return_value=[])

        await repository.get_events_by_user(12345, offset=1000000)

        repository.execute_query.assert_called_once()
        call_args = repository.execute_query.call_args
        assert "OFFSET 1000000" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cleanup_with_zero_batch_size(self, repository):
        """測試批次大小為 0 的清理."""
        # 應該使用預設批次大小
        mock_count_result = {"COUNT(*)": 100}
        mock_delete_result = MagicMock(rowcount=100)

        repository.execute_query = AsyncMock(
            side_effect=[mock_count_result, mock_delete_result]
        )

        await repository.cleanup_old_events(batch_size=0)

        # 應該仍然能正常工作
        assert repository.execute_query.call_count >= 1
