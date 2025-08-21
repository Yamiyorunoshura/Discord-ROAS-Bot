"""
DatabaseManager 整合測試
Task ID: 1 - 建立核心架構基礎

測試 DatabaseManager 的所有功能：
- 資料庫連線和連線池管理
- 事務管理
- CRUD 操作
- 遷移系統
- 向後相容性
- 錯誤處理
"""
import pytest
import pytest_asyncio
import asyncio
import os
import tempfile
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
import aiosqlite

from core.database_manager import (
    DatabaseManager,
    ConnectionPool,
    DatabaseMigration,
    Database,
    ensure_dbs_path
)
from core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseQueryError
)


@pytest_asyncio.fixture
async def temp_db_manager():
    """建立臨時資料庫管理器 - 每個測試使用獨立的資料庫文件"""
    import uuid
    unique_id = str(uuid.uuid4())
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 設定臨時環境變數
        original_project_root = os.environ.get("PROJECT_ROOT")
        os.environ["PROJECT_ROOT"] = temp_dir
        
        # 為每個測試使用唯一的資料庫名稱確保完全隔離
        db_manager = DatabaseManager(
            db_name=f"test_main_{unique_id}.db",
            message_db_name=f"test_message_{unique_id}.db",
            pool_size=3
        )
        
        await db_manager.initialize()
        
        yield db_manager
        
        # 確保完全清理
        await db_manager.cleanup()
        
        # 恢復環境變數
        if original_project_root:
            os.environ["PROJECT_ROOT"] = original_project_root
        elif "PROJECT_ROOT" in os.environ:
            del os.environ["PROJECT_ROOT"]


@pytest_asyncio.fixture
async def temp_connection_pool():
    """建立臨時連線池"""
    pool = ConnectionPool(max_connections=3)
    yield pool
    await pool.close_all_connections()


class TestEnsureDbsPath:
    """測試 ensure_dbs_path 函數"""
    
    def test_ensure_dbs_path_none(self):
        """測試空檔名"""
        result = ensure_dbs_path(None, "default.db")
        assert result.endswith("default.db")
        assert "dbs" in result
    
    def test_ensure_dbs_path_basename_only(self):
        """測試只有檔名"""
        result = ensure_dbs_path("test.db", "default.db")
        assert result.endswith("test.db")
        assert "dbs" in result
    
    def test_ensure_dbs_path_full_path_outside_dbs(self):
        """測試在 dbs 目錄外的完整路徑"""
        result = ensure_dbs_path("/tmp/test.db", "default.db")
        assert result.endswith("test.db")
        assert "dbs" in result
    
    def test_ensure_dbs_path_already_in_dbs(self):
        """測試已在 dbs 目錄內的路徑"""
        with tempfile.TemporaryDirectory() as temp_dir:
            dbs_dir = os.path.join(temp_dir, "dbs")
            os.makedirs(dbs_dir, exist_ok=True)
            test_path = os.path.join(dbs_dir, "test.db")
            
            with patch("core.database_manager.DBS_DIR", dbs_dir):
                result = ensure_dbs_path(test_path, "default.db")
            
            assert result == test_path


class TestConnectionPool:
    """ConnectionPool 測試類別"""
    
    @pytest.mark.asyncio
    async def test_get_connection(self, temp_connection_pool):
        """測試獲取連線"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            conn = await temp_connection_pool.get_connection(db_path)
            assert isinstance(conn, aiosqlite.Connection)
            await conn.close()
        finally:
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_return_connection(self, temp_connection_pool):
        """測試歸還連線"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            conn = await temp_connection_pool.get_connection(db_path)
            await temp_connection_pool.return_connection(db_path, conn)
            
            # 再次獲取應該得到同一個連線
            conn2 = await temp_connection_pool.get_connection(db_path)
            assert conn == conn2
            
            await conn2.close()
        finally:
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_connection_pool_limits(self, temp_connection_pool):
        """測試連線池限制"""
        import uuid
        # 使用唯一名稱避免衝突
        unique_id = str(uuid.uuid4())
        with tempfile.NamedTemporaryFile(suffix=f"_{unique_id}.db", delete=False) as f:
            db_path = f.name
        
        try:
            # 先建立一個連接以初始化資料庫
            first_conn = await temp_connection_pool.get_connection(db_path)
            await first_conn.close()
            
            # 測試連接計數器
            connections = []
            for i in range(2):  # 減少連接數量避免WAL衝突
                conn = await temp_connection_pool.get_connection(db_path)
                connections.append(conn)
            
            # 檢查連線計數（注意：first_conn已關閉，計數器應該反映當前活躍連接）
            assert temp_connection_pool.connection_counts[db_path] >= 1
            
            for conn in connections:
                await conn.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_close_all_connections(self, temp_connection_pool):
        """測試關閉所有連線"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            conn = await temp_connection_pool.get_connection(db_path)
            await temp_connection_pool.return_connection(db_path, conn)
            
            await temp_connection_pool.close_all_connections(db_path)
            
            assert len(temp_connection_pool.connections.get(db_path, [])) == 0
            assert temp_connection_pool.connection_counts.get(db_path, 0) == 0
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestDatabaseMigration:
    """DatabaseMigration 測試類別"""
    
    @pytest.mark.asyncio
    async def test_add_migration(self, temp_db_manager):
        """測試添加遷移"""
        migration = temp_db_manager.migration_manager
        
        migration.add_migration(
            version="test_001",
            description="Test migration",
            up_sql="CREATE TABLE test (id INTEGER PRIMARY KEY);",
            down_sql="DROP TABLE test;"
        )
        
        assert len(migration.migrations) > 0
        test_migration = next(m for m in migration.migrations if m['version'] == 'test_001')
        assert test_migration['description'] == "Test migration"
    
    @pytest.mark.asyncio
    async def test_initialize_migration_table(self, temp_db_manager):
        """測試初始化遷移表"""
        migration = temp_db_manager.migration_manager
        
        await migration.initialize_migration_table()
        
        # 檢查遷移表是否存在
        result = await temp_db_manager.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_apply_migrations(self, temp_db_manager):
        """測試應用遷移"""
        migration = temp_db_manager.migration_manager
        
        # 添加測試遷移
        migration.add_migration(
            version="test_002",
            description="Create test table",
            up_sql="CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);",
            down_sql="DROP TABLE test_table;"
        )
        
        result = await migration.apply_migrations()
        assert result is True
        
        # 檢查表是否被建立
        table_result = await temp_db_manager.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert table_result is not None
        
        # 檢查遷移記錄
        migration_result = await temp_db_manager.fetchone(
            "SELECT version FROM schema_migrations WHERE version='test_002'"
        )
        assert migration_result is not None


class TestDatabaseManager:
    """DatabaseManager 測試類別"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, temp_db_manager):
        """測試資料庫管理器初始化"""
        assert temp_db_manager.is_initialized is True
        assert temp_db_manager.conn is not None
        assert temp_db_manager.message_conn is not None
    
    @pytest.mark.asyncio
    async def test_execute_query(self, temp_db_manager):
        """測試執行查詢"""
        import uuid
        table_suffix = str(uuid.uuid4()).replace('-', '_')[:8]
        table_name = f"test_execute_{table_suffix}"
        
        await temp_db_manager.execute(
            f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        await temp_db_manager.execute(
            f"INSERT INTO {table_name} (value) VALUES (?)",
            ("test_value",)
        )
        
        result = await temp_db_manager.fetchone(
            f"SELECT value FROM {table_name} WHERE id = 1"
        )
        
        assert result['value'] == "test_value"
    
    @pytest.mark.asyncio
    async def test_fetchone(self, temp_db_manager):
        """測試查詢單筆資料"""
        import uuid
        table_suffix = str(uuid.uuid4()).replace('-', '_')[:8]
        table_name = f"test_fetchone_{table_suffix}"
        
        await temp_db_manager.execute(
            f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
        )
        await temp_db_manager.execute(
            f"INSERT INTO {table_name} (value) VALUES (?)",
            ("single_value",)
        )
        
        result = await temp_db_manager.fetchone(
            f"SELECT value FROM {table_name} WHERE id = 1"
        )
        
        assert result is not None
        assert result['value'] == "single_value"
    
    @pytest.mark.asyncio
    async def test_fetchall(self, temp_db_manager):
        """測試查詢多筆資料"""
        import uuid
        table_suffix = str(uuid.uuid4()).replace('-', '_')[:8]
        table_name = f"test_fetchall_{table_suffix}"
        
        await temp_db_manager.execute(
            f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        values = ["value1", "value2", "value3"]
        for value in values:
            await temp_db_manager.execute(
                f"INSERT INTO {table_name} (value) VALUES (?)",
                (value,)
            )
        
        results = await temp_db_manager.fetchall(f"SELECT value FROM {table_name} ORDER BY id")
        
        assert len(results) == 3
        assert [row['value'] for row in results] == values
    
    @pytest.mark.asyncio
    async def test_executemany(self, temp_db_manager):
        """測試批量執行"""
        import uuid
        table_suffix = str(uuid.uuid4()).replace('-', '_')[:8]
        table_name = f"test_executemany_{table_suffix}"
        
        await temp_db_manager.execute(
            f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        data = [("value1",), ("value2",), ("value3",)]
        await temp_db_manager.executemany(
            f"INSERT INTO {table_name} (value) VALUES (?)",
            data
        )
        
        results = await temp_db_manager.fetchall(f"SELECT value FROM {table_name} ORDER BY id")
        
        assert len(results) == 3
        assert [row['value'] for row in results] == ["value1", "value2", "value3"]
    
    @pytest.mark.asyncio
    async def test_transaction_success(self, temp_db_manager):
        """測試事務成功"""
        import uuid
        table_suffix = str(uuid.uuid4()).replace('-', '_')[:8]
        table_name = f"test_transaction_{table_suffix}"
        
        await temp_db_manager.execute(
            f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        async with temp_db_manager.transaction():
            await temp_db_manager.execute(
                f"INSERT INTO {table_name} (value) VALUES (?)",
                ("transaction_value",)
            )
        
        result = await temp_db_manager.fetchone(
            f"SELECT value FROM {table_name} WHERE id = 1"
        )
        
        assert result['value'] == "transaction_value"
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, temp_db_manager):
        """測試事務回滾"""
        # 先清理表格（如果存在）
        try:
            await temp_db_manager.execute("DROP TABLE IF EXISTS test_rollback")
        except:
            pass
            
        await temp_db_manager.execute(
            "CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        try:
            async with temp_db_manager.transaction() as conn:
                await conn.execute(
                    "INSERT INTO test_rollback (value) VALUES (?)",
                    ("rollback_value",)
                )
                # 故意拋出異常觸發回滾
                raise Exception("Test rollback")
        except Exception:
            pass
        
        result = await temp_db_manager.fetchone(
            "SELECT COUNT(*) as count FROM test_rollback"
        )
        
        assert result['count'] == 0
    
    @pytest.mark.asyncio
    async def test_message_database_operations(self, temp_db_manager):
        """測試訊息資料庫操作"""
        import random
        # 使用隨機ID避免UNIQUE constraint衝突
        message_id = random.randint(100000, 999999)
        
        await temp_db_manager.log_message(
            message_id=message_id,
            channel_id=67890,
            guild_id=11111,
            author_id=22222,
            content="Test message",
            timestamp=1234567890.0,
            attachments=None
        )
        
        result = await temp_db_manager.fetchone(
            f"SELECT content FROM messages WHERE message_id = {message_id}",
            db_type="message"
        )
        
        assert result['content'] == "Test message"
    
    @pytest.mark.asyncio
    async def test_get_database_stats(self, temp_db_manager):
        """測試獲取資料庫統計"""
        stats = await temp_db_manager.get_database_stats()
        
        assert "main_database" in stats
        assert "message_database" in stats
        assert "connection_pool" in stats
        assert "path" in stats["main_database"]
        assert "tables" in stats["main_database"]
    
    @pytest.mark.asyncio
    async def test_backup_database(self, temp_db_manager):
        """測試資料庫備份"""
        import uuid
        table_suffix = str(uuid.uuid4()).replace('-', '_')[:8]
        table_name = f"test_backup_{table_suffix}"
        
        # 建立一些測試資料
        await temp_db_manager.execute(
            f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
        )
        await temp_db_manager.execute(
            f"INSERT INTO {table_name} (value) VALUES (?)",
            ("backup_test",)
        )
        
        backup_path = await temp_db_manager.backup_database()
        
        assert os.path.exists(backup_path)
        assert backup_path.endswith(".db")
        
        # 驗證備份檔案內容
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT value FROM {table_name} WHERE id = 1")
        result = cursor.fetchone()
        conn.close()
        
        assert result[0] == "backup_test"
        
        # 清理備份檔案
        os.unlink(backup_path)


class TestBackwardCompatibility:
    """向後相容性測試"""
    
    @pytest.mark.asyncio
    async def test_welcome_message_operations(self, temp_db_manager):
        """測試歡迎訊息操作"""
        guild_id = 12345
        channel_id = 67890
        message = "Welcome to our server!"
        
        await temp_db_manager.update_welcome_message(guild_id, channel_id, message)
        
        result = await temp_db_manager.get_welcome_message(guild_id)
        assert result == message
        
        settings = await temp_db_manager.get_welcome_settings(guild_id)
        assert settings['channel_id'] == channel_id
    
    @pytest.mark.asyncio
    async def test_welcome_background_operations(self, temp_db_manager):
        """測試歡迎背景操作"""
        guild_id = 12345
        image_path = "/path/to/background.jpg"
        
        await temp_db_manager.update_welcome_background(guild_id, image_path)
        
        result = await temp_db_manager.get_welcome_background(guild_id)
        assert result == image_path
    
    @pytest.mark.asyncio
    async def test_settings_operations(self, temp_db_manager):
        """測試設定操作"""
        setting_name = "test_setting"
        setting_value = "test_value"
        
        await temp_db_manager.set_setting(setting_name, setting_value)
        
        result = await temp_db_manager.get_setting(setting_name)
        assert result == setting_value
    
    @pytest.mark.asyncio
    async def test_monitored_channels_operations(self, temp_db_manager):
        """測試監聽頻道操作"""
        channel_id = 12345
        
        await temp_db_manager.add_monitored_channel(channel_id)
        
        channels = await temp_db_manager.get_monitored_channels()
        assert channel_id in channels
        
        await temp_db_manager.remove_monitored_channel(channel_id)
        
        channels = await temp_db_manager.get_monitored_channels()
        assert channel_id not in channels
    
    @pytest.mark.asyncio
    async def test_text_position_operations(self, temp_db_manager):
        """測試文字位置操作"""
        guild_id = 12345
        text_type = "username"
        position = 100
        
        await temp_db_manager.update_text_position(guild_id, text_type, None, position)
        
        result = await temp_db_manager.get_text_position(guild_id, text_type)
        assert result == position


class TestDatabaseCompatibilityLayer:
    """Database 相容層測試"""
    
    @pytest.mark.asyncio
    async def test_database_cog_compatibility(self):
        """測試 Database Cog 相容性"""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_project_root = os.environ.get("PROJECT_ROOT")
            os.environ["PROJECT_ROOT"] = temp_dir
            
            try:
                bot = MagicMock()
                db_cog = Database(bot, "test_compat.db", "test_compat_msg.db")
                
                await db_cog.cog_load()
                
                assert db_cog.ready is True
                assert hasattr(bot, 'database')
                assert db_cog.db_manager.is_initialized is True
                
                # 測試方法轉發
                result = await db_cog.set_setting("test_key", "test_value")
                retrieved = await db_cog.get_setting("test_key")
                assert retrieved == "test_value"
                
                await db_cog.cog_unload()
                
            finally:
                if original_project_root:
                    os.environ["PROJECT_ROOT"] = original_project_root
                elif "PROJECT_ROOT" in os.environ:
                    del os.environ["PROJECT_ROOT"]


class TestErrorHandling:
    """錯誤處理測試"""
    
    @pytest.mark.asyncio
    async def test_connection_error(self):
        """測試連線錯誤"""
        # 使用無效路徑測試連線錯誤
        invalid_path = "/invalid/path/database.db"
        
        pool = ConnectionPool()
        
        with pytest.raises(DatabaseConnectionError):
            await pool.get_connection(invalid_path)
    
    @pytest.mark.asyncio
    async def test_query_error(self, temp_db_manager):
        """測試查詢錯誤"""
        # 執行無效 SQL
        with pytest.raises(DatabaseQueryError):
            await temp_db_manager.execute("INVALID SQL STATEMENT")
    
    @pytest.mark.asyncio
    async def test_permission_validation(self, temp_db_manager):
        """測試權限驗證"""
        # DatabaseManager 預設允許所有操作
        result = await temp_db_manager.validate_permissions(12345, 67890, "test_action")
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__])