"""
T2 - 高併發連線競爭修復
ConnectionPoolManager 單元測試

驗證連線池管理器的核心功能和邊界條件
"""

import asyncio
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# 添加系統路徑支持
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(project_root)

from services.connection_pool.connection_pool_manager import ConnectionPoolManager, ConnectionWrapper
from services.connection_pool.models import PoolConfiguration, ConnectionStatus


class TestConnectionPoolManager(unittest.IsolatedAsyncioTestCase):
    """ConnectionPoolManager 單元測試類"""
    
    async def asyncSetUp(self):
        """設置測試環境"""
        # 使用臨時資料庫檔案
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # 基本配置
        self.config = PoolConfiguration(
            min_connections=2,
            max_connections=5,
            connection_timeout=10.0,
            acquire_timeout=2.0,
            enable_monitoring=True
        )
        
        self.pool_manager = ConnectionPoolManager(
            db_path=self.db_path,
            config=self.config
        )
    
"""
T2 - 高併發連線競爭修復
ConnectionPoolManager 單元測試

驗證連線池管理器的核心功能和邊界條件
"""

import asyncio
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# 添加系統路徑支持
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(project_root)

from services.connection_pool.connection_pool_manager import ConnectionPoolManager, ConnectionWrapper
from services.connection_pool.models import PoolConfiguration, ConnectionStatus


class TestConnectionPoolManager(unittest.IsolatedAsyncioTestCase):
    """ConnectionPoolManager 單元測試類"""
    
    async def asyncSetUp(self):
        """設置測試環境"""
        # 使用臨時資料庫檔案
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # 基本配置
        self.config = PoolConfiguration(
            min_connections=2,
            max_connections=5,
            connection_timeout=10.0,
            acquire_timeout=2.0,
            enable_monitoring=True
        )
        
        self.pool_manager = ConnectionPoolManager(
            db_path=self.db_path,
            config=self.config
        )
    
    async def asyncTearDown(self):
        """清理測試環境"""
        if hasattr(self, 'pool_manager'):
            await self.pool_manager.stop()
        
        # 清理臨時檔案
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
    
    async def test_pool_initialization(self):
        """測試連線池初始化"""
        # 測試初始化成功
        await self.pool_manager.start()
        self.assertTrue(self.pool_manager._is_running)
        
        # 驗證最小連線數
        stats = self.pool_manager.get_pool_stats()
        total_connections = stats['active_connections'] + stats['idle_connections']
        self.assertGreaterEqual(total_connections, self.config.min_connections)
        
        # 測試重複初始化不會造成問題
        await self.pool_manager.start()
        self.assertTrue(self.pool_manager._is_running)
    
    async def test_connection_acquisition_and_release(self):
        """測試連線獲取和釋放"""
        await self.pool_manager.start()
        
        # 測試獲取連線
        connection = await self.pool_manager.get_connection()
        self.assertIsNotNone(connection)
        
        # 驗證連線可用
        async with connection.execute("SELECT 1 as test") as cursor:
            result = await cursor.fetchone()
            self.assertEqual(result['test'], 1)
        
        # 測試歸還連線
        await self.pool_manager.release_connection(connection)
        
        # 驗證統計更新
        stats = self.pool_manager.get_pool_stats()
        self.assertGreaterEqual(stats['total_requests_served'], 1)
    
    async def test_connection_context_manager(self):
        """測試連線上下文管理器"""
        await self.pool_manager.start()
        
        async with self.pool_manager.connection() as conn:
            async with conn.execute("SELECT 'context_test' as msg") as cursor:
                result = await cursor.fetchone()
                self.assertEqual(result['msg'], 'context_test')
        
        # 連線應該自動歸還
        stats = self.pool_manager.get_pool_stats()
        self.assertGreaterEqual(stats['total_requests_served'], 1)
    
    async def test_concurrent_connections(self):
        """測試併發連線"""
        await self.pool_manager.start()
        
        async def worker_task(worker_id: int):
            async with self.pool_manager.connection() as conn:
                async with conn.execute("SELECT ? as worker_id", (worker_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result['worker_id']
        
        # 啟動多個併發工作者
        tasks = [worker_task(i) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        # 驗證所有工作者都完成
        self.assertEqual(sorted(results), [0, 1, 2])
        
        # 驗證統計
        stats = self.pool_manager.get_pool_stats()
        self.assertGreaterEqual(stats['total_requests_served'], 3)
    
    async def test_pool_limit_enforcement(self):
        """測試連線池限制強制執行"""
        await self.pool_manager.start()
        
        # 獲取所有可用連線
        connections = []
        for i in range(self.config.max_connections):
            conn = await self.pool_manager.get_connection()
            connections.append(conn)
        
        # 嘗試獲取超出限制的連線，應該超時
        start_time = time.time()
        
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(
                self.pool_manager.get_connection(), 
                timeout=0.5
            )
        
        # 確認等待時間符合預期
        elapsed = time.time() - start_time
        self.assertGreaterEqual(elapsed, 0.4)  # 允許一些誤差
        
        # 釋放一個連線後應該可以獲取
        await self.pool_manager.release_connection(connections[0])
        
        conn = await asyncio.wait_for(
            self.pool_manager.get_connection(), 
            timeout=1.0
        )
        self.assertIsNotNone(conn)
        
        # 清理
        for connection in connections[1:]:
            await self.pool_manager.release_connection(connection)
        await self.pool_manager.release_connection(conn)
    
    async def test_connection_validation(self):
        """測試連線驗證和健康檢查"""
        await self.pool_manager.start()
        
        # 獲取一個連線並驗證健康狀態
        connection = await self.pool_manager.get_connection()
        
        # 驗證連線可以正常執行查詢
        async with connection.execute("SELECT 1") as cursor:
            result = await cursor.fetchone()
            self.assertIsNotNone(result)
        
        # 歸還連線
        await self.pool_manager.release_connection(connection)
        
        # 連線應該正常歸還
        stats = self.pool_manager.get_pool_stats()
        self.assertGreaterEqual(stats['total_requests_served'], 1)
    
    async def test_pool_stats(self):
        """測試連線池統計功能"""
        await self.pool_manager.start()
        
        # 獲取初始統計
        stats = self.pool_manager.get_pool_stats()
        self.assertIsNotNone(stats['timestamp'])
        self.assertGreaterEqual(
            stats['active_connections'] + stats['idle_connections'], 
            self.config.min_connections
        )
        self.assertEqual(stats['max_connections'], self.config.max_connections)
        
        # 執行一些操作
        async with self.pool_manager.connection() as conn:
            await conn.execute("CREATE TABLE test_stats (id INTEGER PRIMARY KEY, value TEXT)")
            await conn.execute("INSERT INTO test_stats (value) VALUES (?)", ("test",))
            await conn.commit()
        
        # 獲取更新後的統計
        stats = self.pool_manager.get_pool_stats()
        self.assertGreaterEqual(stats['total_requests_served'], 1)
        self.assertGreaterEqual(stats['success_rate'], 99.0)  # 應該接近100%
    
    async def test_performance_metrics(self):
        """測試效能指標"""
        await self.pool_manager.start()
        
        # 執行一些操作產生指標
        async with self.pool_manager.connection() as conn:
            await conn.execute("SELECT 1")
        
        metrics = await self.pool_manager.get_performance_metrics()
        
        # 驗證效能指標結構
        self.assertGreaterEqual(metrics.total_requests, 0)
        self.assertGreaterEqual(metrics.successful_requests, 0)
        self.assertGreaterEqual(metrics.throughput_rps, 0)
        self.assertLessEqual(metrics.error_rate, 1.0)  # 錯誤率應該很低
    
    async def test_dynamic_optimization(self):
        """測試動態優化功能"""
        await self.pool_manager.start()
        
        # 記錄初始連線數
        initial_stats = self.pool_manager.get_pool_stats()
        initial_total = initial_stats['active_connections'] + initial_stats['idle_connections']
        
        # 手動觸發優化
        await self.pool_manager.optimize_pool()
        
        # 由於是輕負載，連線數應該保持穩定
        optimized_stats = self.pool_manager.get_pool_stats()
        optimized_total = optimized_stats['active_connections'] + optimized_stats['idle_connections']
        
        # 在輕負載情況下，連線數變化應該不大
        self.assertGreaterEqual(optimized_total, self.config.min_connections)
        self.assertLessEqual(optimized_total, self.config.max_connections)
    
    async def test_error_handling(self):
        """測試錯誤處理"""
        # 測試無效配置
        invalid_config = PoolConfiguration(
            min_connections=-1,  # 無效值
            max_connections=0
        )
        
        with self.assertRaises(ValueError):
            ConnectionPoolManager(
                db_path=self.db_path,
                config=invalid_config
            )
        
        # 測試正常的配置驗證
        valid_config = PoolConfiguration(
            min_connections=1,
            max_connections=10
        )
        
        errors = valid_config.validate()
        self.assertEqual(len(errors), 0)
    
    async def test_pool_stop(self):
        """測試連線池停止"""
        await self.pool_manager.start()
        
        # 獲取一些連線
        connections = []
        for i in range(2):
            conn = await self.pool_manager.get_connection()
            connections.append(conn)
        
        # 關閉連線池
        await self.pool_manager.stop()
        
        # 驗證狀態
        self.assertFalse(self.pool_manager._is_running)


class TestConnectionWrapper(unittest.IsolatedAsyncioTestCase):
    """ConnectionWrapper 單元測試類"""
    
    async def asyncSetUp(self):
        """設置測試環境"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # 創建測試連線
        import aiosqlite
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        
        self.wrapper = ConnectionWrapper(self.connection, "test_conn_1")
    
    async def asyncTearDown(self):
        """清理測試環境"""
        if hasattr(self, 'wrapper'):
            await self.wrapper.close()
        
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
    
    async def test_connection_wrapper_basic_operations(self):
        """測試連線包裝器基本操作"""
        # 測試執行查詢
        result = await self.wrapper.execute("SELECT 1 as test")
        self.assertIsNotNone(result)
        
        # 驗證統計更新
        self.assertEqual(self.wrapper.usage_count, 1)
        self.assertIsNotNone(self.wrapper.last_used_at)
        self.assertEqual(self.wrapper.status, ConnectionStatus.IDLE)
    
    async def test_connection_health_check(self):
        """測試連線健康檢查"""
        # 健康的連線應該返回True
        is_healthy = await self.wrapper.is_healthy()
        self.assertTrue(is_healthy)
        
        # 關閉連線後應該不健康
        await self.wrapper.close()
        is_healthy = await self.wrapper.is_healthy()
        self.assertFalse(is_healthy)
    
    async def test_error_handling(self):
        """測試錯誤處理"""
        # 執行無效SQL應該增加錯誤計數
        try:
            await self.wrapper.execute("INVALID SQL QUERY")
        except Exception:
            pass
        
        self.assertGreater(self.wrapper.error_count, 0)
        self.assertEqual(self.wrapper.status, ConnectionStatus.ERROR)


class TestPoolConfiguration(unittest.TestCase):
    """PoolConfiguration 單元測試類"""
    
    def test_valid_configuration(self):
        """測試有效配置"""
        config = PoolConfiguration(
            min_connections=1,
            max_connections=10,
            connection_timeout=30.0,
            acquire_timeout=5.0
        )
        
        errors = config.validate()
        self.assertEqual(len(errors), 0)
    
    def test_invalid_configurations(self):
        """測試無效配置"""
        # 負數最小連線
        config = PoolConfiguration(min_connections=-1, max_connections=10)
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("min_connections" in error for error in errors))
        
        # 最大連線為零
        config = PoolConfiguration(min_connections=1, max_connections=0)
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("max_connections" in error for error in errors))
        
        # 最小連線大於最大連線
        config = PoolConfiguration(min_connections=10, max_connections=5)
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("min_connections" in error and "max_connections" in error for error in errors))
        
        # 無效超時時間
        config = PoolConfiguration(
            min_connections=1,
            max_connections=10,
            connection_timeout=-1.0
        )
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("connection_timeout" in error for error in errors))
    
    def test_default_configuration(self):
        """測試預設配置"""
        config = PoolConfiguration()
        
        # 驗證預設值
        self.assertEqual(config.min_connections, 2)
        self.assertEqual(config.max_connections, 20)
        self.assertEqual(config.connection_timeout, 30.0)
        self.assertEqual(config.acquire_timeout, 10.0)
        self.assertTrue(config.enable_monitoring)
        
        # 預設配置應該是有效的
        errors = config.validate()
        self.assertEqual(len(errors), 0)


if __name__ == '__main__':
    unittest.main()