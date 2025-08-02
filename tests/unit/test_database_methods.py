"""
數據庫方法完善測試模塊
- 測試新增的數據庫查詢方法
- 驗證數據庫操作接口統一性
- 測試數據庫錯誤處理
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from cogs.activity_meter.database.database import ActivityDatabase, ActivityMeterError


class TestDatabaseMethods:
    """數據庫方法測試類"""

    @pytest_asyncio.fixture
    async def activity_db(self, activity_test_db):
        """建立測試用活躍度數據庫"""
        db = ActivityDatabase()
        # 使用mock pool模式
        mock_pool = MagicMock()

        @asynccontextmanager
        async def mock_get_connection_context(db_path):
            yield activity_test_db

        mock_pool.get_connection_context = mock_get_connection_context
        db._pool = mock_pool
        await db.init_db()
        return db

    @pytest.mark.asyncio
    async def test_get_announcement_time_existing(self, activity_db, activity_test_db):
        """測試獲取已存在的公告時間"""
        # 插入測試數據
        await activity_test_db.execute("""
            CREATE TABLE IF NOT EXISTS activity_meter_settings (
                guild_id INTEGER PRIMARY KEY,
                progress_style TEXT DEFAULT 'classic',
                announcement_channel INTEGER,
                announcement_time INTEGER DEFAULT 21
            )
        """)

        await activity_test_db.execute("""
            INSERT INTO activity_meter_settings (guild_id, announcement_time)
            VALUES (?, ?)
        """, (123, 14))  # 14:00

        await activity_test_db.commit()

        # 測試獲取公告時間
        result = await activity_db.get_announcement_time(123)
        assert result == "14:00", f"期望 14:00，實際 {result}"

    @pytest.mark.asyncio
    async def test_get_announcement_time_default(self, activity_db):
        """測試獲取預設公告時間"""
        # 測試不存在的guild_id
        result = await activity_db.get_announcement_time(999)
        assert result == "09:00", f"期望預設時間 09:00，實際 {result}"

    @pytest.mark.asyncio
    async def test_get_announcement_time_database_error(self, activity_db):
        """測試數據庫錯誤處理"""
        # 創建一個會拋出異常的數據庫連接
        mock_pool = MagicMock()

        @asynccontextmanager
        async def mock_get_connection_context_error(db_path):
            raise Exception("數據庫連接失敗")

        mock_pool.get_connection_context = mock_get_connection_context_error
        activity_db._pool = mock_pool

        # 應該拋出ActivityMeterError
        with pytest.raises(ActivityMeterError) as exc_info:
            await activity_db.get_announcement_time(123)

        assert "獲取公告時間失敗" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_announcement_time_valid(self, activity_db, activity_test_db):
        """測試更新有效的公告時間"""
        # 創建測試表
        await activity_test_db.execute("""
            CREATE TABLE IF NOT EXISTS activity_meter_settings (
                guild_id INTEGER PRIMARY KEY,
                progress_style TEXT DEFAULT 'classic',
                announcement_channel INTEGER,
                announcement_time INTEGER DEFAULT 21
            )
        """)
        await activity_test_db.commit()

        # 測試更新公告時間
        await activity_db.update_announcement_time(123, "15:30")

        # 驗證更新結果
        cursor = await activity_test_db.execute("""
            SELECT announcement_time FROM activity_meter_settings WHERE guild_id = ?
        """, (123,))
        result = await cursor.fetchone()

        assert result is not None, "應該有更新結果"
        assert result[0] == 15, f"期望小時為 15，實際 {result[0]}"

    @pytest.mark.asyncio
    async def test_update_announcement_time_invalid_format(self, activity_db):
        """測試更新無效格式的公告時間"""
        # 測試無效格式
        invalid_times = ["25:00", "12:60", "09:5", "abc", "12:30:45"]

        for time_str in invalid_times:
            with pytest.raises(ActivityMeterError) as exc_info:
                await activity_db.update_announcement_time(123, time_str)

            assert "更新公告時間失敗" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_time_format_valid(self, activity_db):
        """測試有效時間格式驗證"""
        valid_times = ["09:00", "12:30", "23:59", "00:00", "15:45"]

        for time_str in valid_times:
            result = activity_db._validate_time_format(time_str)
            assert result, f"時間格式 {time_str} 應該有效"

    @pytest.mark.asyncio
    async def test_validate_time_format_invalid(self, activity_db):
        """測試無效時間格式驗證"""
        invalid_times = [
            "25:00",  # 小時超出範圍
            "12:60",  # 分鐘超出範圍
            "09:5",   # 格式不正確
            "abc",    # 非數字
            "12:30:45",  # 包含秒
            "",       # 空字符串
        ]

        for time_str in invalid_times:
            result = activity_db._validate_time_format(time_str)
            assert not result, f"時間格式 {time_str} 應該無效"

    @pytest.mark.asyncio
    async def test_database_interface_unification(self, activity_db):
        """測試數據庫接口統一性"""
        # 檢查所有必要的數據庫方法都存在
        required_methods = [
            'get_announcement_time',
            'update_announcement_time',
            'get_user_activity',
            'update_user_activity',
            'set_report_channel',
            'get_report_channels',
            'load_settings',
            'save_all_settings'
        ]

        for method_name in required_methods:
            assert hasattr(activity_db, method_name), f"缺少方法: {method_name}"

    @pytest.mark.asyncio
    async def test_database_error_handling_consistency(self, activity_db):
        """測試數據庫錯誤處理一致性"""
        # 創建一個會拋出異常的數據庫連接
        mock_pool = MagicMock()

        @asynccontextmanager
        async def mock_get_connection_context_error(db_path):
            raise Exception("數據庫連接失敗")

        mock_pool.get_connection_context = mock_get_connection_context_error
        activity_db._pool = mock_pool

        # 測試各種方法的錯誤處理
        methods_to_test = [
            ('get_announcement_time', [123]),
            ('get_user_activity', [123, 456]),
            ('set_report_channel', [123, 789]),
        ]

        for method_name, args in methods_to_test:
            method = getattr(activity_db, method_name)

            with pytest.raises(ActivityMeterError) as exc_info:
                await method(*args)

            # 檢查錯誤訊息格式
            error_message = str(exc_info.value)
            assert "失敗" in error_message, f"錯誤訊息應該包含'失敗': {error_message}"
            assert exc_info.value.error_code.startswith("E"), f"錯誤代碼應該以'E'開頭: {exc_info.value.error_code}"

class TestDatabaseIntegration:
    """數據庫整合測試類"""

    @pytest_asyncio.fixture
    async def test_database(self, activity_test_db):
        """建立測試數據庫"""
        # 創建必要的表
        await activity_test_db.execute("""
            CREATE TABLE IF NOT EXISTS activity_meter_settings (
                guild_id INTEGER PRIMARY KEY,
                progress_style TEXT DEFAULT 'classic',
                announcement_channel INTEGER,
                announcement_time INTEGER DEFAULT 21
            )
        """)

        await activity_test_db.execute("""
            CREATE TABLE IF NOT EXISTS meter(
                guild_id INTEGER, user_id INTEGER,
                score REAL DEFAULT 0, last_msg INTEGER DEFAULT 0,
                PRIMARY KEY(guild_id, user_id)
            )
        """)

        await activity_test_db.commit()
        return activity_test_db

    @pytest.mark.asyncio
    async def test_database_operations_integration(self, test_database):
        """測試數據庫操作整合"""
        # 創建ActivityDatabase實例
        activity_db = ActivityDatabase()

        # 設置mock pool
        mock_pool = MagicMock()

        @asynccontextmanager
        async def mock_get_connection_context(db_path):
            yield test_database

        mock_pool.get_connection_context = mock_get_connection_context
        activity_db._pool = mock_pool

        # 測試完整的數據庫操作流程
        guild_id = 123
        user_id = 456

        # 1. 設置公告時間
        await activity_db.update_announcement_time(guild_id, "16:00")

        # 2. 獲取公告時間
        announcement_time = await activity_db.get_announcement_time(guild_id)
        assert announcement_time == "16:00"

        # 3. 更新用戶活動
        await activity_db.update_user_activity(guild_id, user_id, 75.5, 1234567890)

        # 4. 獲取用戶活動
        score, last_msg = await activity_db.get_user_activity(guild_id, user_id)
        assert score == 75.5
        assert last_msg == 1234567890

        # 5. 設置報告頻道
        await activity_db.set_report_channel(guild_id, 789)

        # 6. 獲取報告頻道
        channels = await activity_db.get_report_channels()
        assert (guild_id, 789) in channels

    @pytest.mark.asyncio
    async def test_database_transaction_consistency(self, test_database):
        """測試數據庫事務一致性"""
        # 創建ActivityDatabase實例
        activity_db = ActivityDatabase()

        # 設置mock pool
        mock_pool = MagicMock()

        @asynccontextmanager
        async def mock_get_connection_context(db_path):
            yield test_database

        mock_pool.get_connection_context = mock_get_connection_context
        activity_db._pool = mock_pool

        guild_id = 123

        # 測試事務一致性
        try:
            # 執行多個操作
            await activity_db.update_announcement_time(guild_id, "17:00")
            await activity_db.set_report_channel(guild_id, 888)

            # 驗證所有操作都成功
            announcement_time = await activity_db.get_announcement_time(guild_id)
            assert announcement_time == "17:00"

            channels = await activity_db.get_report_channels()
            assert (guild_id, 888) in channels

        except Exception as e:
            pytest.fail(f"數據庫事務應該成功，但失敗了: {e}")

# 測試工具函數
def test_database_method_completeness():
    """測試數據庫方法完整性"""
    db = ActivityDatabase()

    # 檢查所有必要的數據庫方法都存在
    required_methods = [
        'get_announcement_time',
        'update_announcement_time',
        '_validate_time_format',
        'get_user_activity',
        'update_user_activity',
        'set_report_channel',
        'get_report_channels'
    ]

    for method_name in required_methods:
        assert hasattr(db, method_name), f"缺少方法: {method_name}"

def test_database_error_handling_completeness():
    """測試數據庫錯誤處理完整性"""
    # 檢查錯誤類別
    # ActivityMeterError是自定義異常，檢查其基本功能
    assert issubclass(ActivityMeterError, Exception), "ActivityMeterError應該是Exception的子類"

    # 測試錯誤創建
    error = ActivityMeterError("E102", "測試錯誤")
    assert "E102" in str(error)
    assert "測試錯誤" in str(error)

    # 檢查錯誤訊息格式
    error_str = str(error)
    assert "E102" in error_str, "錯誤訊息應該包含錯誤代碼"
    assert "測試錯誤" in error_str, "錯誤訊息應該包含錯誤描述"
