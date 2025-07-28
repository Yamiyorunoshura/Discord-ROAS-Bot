"""
資料庫連接池測試

測試專業級資料庫連接池系統的核心功能

作者: Discord ADR Bot Team
創建時間: 2025-01-24
"""

import os
import tempfile

import aiosqlite
import pytest
import pytest_asyncio

from src.core.database import (
    DatabaseConnectionPool,
    PoolConfiguration,
    PoolMetrics,
    close_global_pool,
    get_global_pool,
)


class TestPoolConfiguration:
    """測試連接池配置"""

    def test_default_configuration(self):
        """測試預設配置"""
        config = PoolConfiguration()
        assert config.max_connections == 20
        assert config.max_idle_time == 300
        assert config.enable_wal is True
        assert config.enable_metrics is True


class TestPoolMetrics:
    """測試連接池指標收集器"""

    @pytest.mark.asyncio
    async def test_connection_metrics(self):
        """測試連接指標記錄"""
        metrics = PoolMetrics()

        # 測試創建連接
        await metrics.record_connection_created()
        assert metrics.total_connections_created == 1
        assert metrics.active_connections == 1

        # 測試關閉連接
        await metrics.record_connection_closed()
        assert metrics.total_connections_closed == 1
        assert metrics.active_connections == 0


class TestDatabaseConnectionPool:
    """測試資料庫連接池"""

    @pytest_asyncio.fixture
    async def temp_db(self):
        """創建臨時資料庫"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # 創建資料庫表
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            await conn.commit()

        yield db_path

        # 清理
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest_asyncio.fixture
    async def pool(self):
        """創建連接池"""
        config = PoolConfiguration(max_connections=3)
        pool = DatabaseConnectionPool(config)
        await pool.initialize()
        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """測試連接池初始化"""
        pool = DatabaseConnectionPool()
        assert pool._initialized is False

        await pool.initialize()
        assert pool._initialized is True

        await pool.close()
        assert pool._initialized is False

    @pytest.mark.asyncio
    async def test_get_connection(self, pool, temp_db):
        """測試獲取連接"""
        # 獲取連接
        conn1 = await pool.get_connection(temp_db)
        assert conn1 is not None
        assert conn1.in_use is True

        # 歸還連接
        await pool.return_connection(conn1)
        assert conn1.in_use is False

    @pytest.mark.asyncio
    async def test_connection_context_manager(self, pool, temp_db):
        """測試連接上下文管理器"""
        async with pool.get_connection_context(temp_db) as conn:
            assert conn is not None
            assert conn.in_use is True

            # 執行查詢
            cursor = await conn.execute("SELECT 1")
            row = await cursor.fetchone()
            assert row is not None

        # 連接應該被自動歸還
        assert conn.in_use is False

    @pytest.mark.asyncio
    async def test_execute_convenience_method(self, pool, temp_db):
        """測試便利執行方法"""
        cursor = await pool.execute(temp_db, "SELECT 1")
        row = await cursor.fetchone()
        assert row is not None


class TestGlobalPool:
    """測試全局連接池"""

    @pytest.mark.asyncio
    async def test_global_pool_singleton(self):
        """測試全局連接池單例"""
        # 確保全局池已關閉
        await close_global_pool()

        # 獲取全局池
        pool1 = await get_global_pool()
        pool2 = await get_global_pool()

        # 應該是同一個實例
        assert pool1 is pool2
        assert pool1._initialized is True

        # 清理
        await close_global_pool()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
