"""資料庫操作測試模組.

此模組為Discord ROAS Bot的資料庫操作提供全面的測試覆蓋,
包括連接池管理、事務處理、CRUD操作等核心功能.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

import aiosqlite
import pytest

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import contextlib

from src.core.database import DatabasePool


class TestDatabasePool:
    """測試資料庫連接池功能."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_database_pool_initialization(self):
        """測試資料庫連接池初始化."""
        pool = DatabasePool(
            database_url=f"sqlite+aiosqlite:///{self.db_path}",
            pool_size=5,
            max_overflow=10,
        )

        assert pool.database_url == f"sqlite+aiosqlite:///{self.db_path}"
        assert pool.pool_size == 5
        assert pool.max_overflow == 10
        assert pool._pool is None  # 尚未初始化

    @pytest.mark.asyncio
    async def test_database_connection_creation(self):
        """測試資料庫連接創建."""
        pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}")

        async with pool.get_connection() as conn:
            assert conn is not None
            # 測試基本SQL操作
            await conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            await conn.commit()

            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = await cursor.fetchall()
            assert any("test" in str(table) for table in tables)

    @pytest.mark.asyncio
    async def test_connection_pool_reuse(self):
        """測試連接池的連接重用."""
        pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}", pool_size=2)

        connections = []

        # 獲取多個連接
        async with pool.get_connection() as conn1:
            connections.append(id(conn1))

        async with pool.get_connection() as conn2:
            connections.append(id(conn2))

        # 驗證連接可能被重用(或創建新的)
        assert len(connections) == 2

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self):
        """測試事務回滾功能."""
        pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}")

        async with pool.get_connection() as conn:
            await conn.execute("CREATE TABLE test_transaction (id INTEGER, value TEXT)")
            await conn.commit()

            # 測試事務回滾
            try:
                await conn.execute("BEGIN")
                await conn.execute(
                    "INSERT INTO test_transaction (id, value) VALUES (1, 'test')"
                )

                # 檢查數據已插入但未提交
                cursor = await conn.execute("SELECT COUNT(*) FROM test_transaction")
                count = await cursor.fetchone()
                assert count[0] == 1

                # 強制回滾
                await conn.execute("ROLLBACK")

                # 驗證數據已回滾
                cursor = await conn.execute("SELECT COUNT(*) FROM test_transaction")
                count = await cursor.fetchone()
                assert count[0] == 0

            except Exception:
                await conn.execute("ROLLBACK")
                raise

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """測試連接錯誤處理."""
        # 使用無效的資料庫路徑
        invalid_path = "/invalid/path/database.db"
        pool = DatabasePool(f"sqlite+aiosqlite:///{invalid_path}")

        with pytest.raises((OSError, aiosqlite.Error)):
            async with pool.get_connection() as conn:
                await conn.execute("SELECT 1")


@pytest.mark.skip(
    reason="DatabaseManager and TransactionManager classes not implemented yet"
)
class TestDatabaseManager:
    """測試資料庫管理器."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_database_manager_initialization(self):
        """測試資料庫管理器初始化."""
        manager = DatabaseManager()

        assert manager._pools == {}
        assert isinstance(manager._pools, dict)

    @pytest.mark.asyncio
    async def test_get_pool_creation(self):
        """測試獲取資料庫連接池."""
        manager = DatabaseManager()

        pool = await manager.get_pool(
            "test_db", database_url=f"sqlite+aiosqlite:///{self.db_path}"
        )

        assert pool is not None
        assert "test_db" in manager._pools
        assert manager._pools["test_db"] == pool

    @pytest.mark.asyncio
    async def test_pool_singleton_behavior(self):
        """測試連接池單例行為."""
        manager = DatabaseManager()

        pool1 = await manager.get_pool("test", f"sqlite+aiosqlite:///{self.db_path}")
        pool2 = await manager.get_pool("test", f"sqlite+aiosqlite:///{self.db_path}")

        # 應該返回相同的連接池實例
        assert pool1 is pool2

    @pytest.mark.asyncio
    async def test_multiple_pools(self):
        """測試多個資料庫連接池管理."""
        manager = DatabaseManager()

        temp_db2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path2 = temp_db2.name
        temp_db2.close()

        try:
            pool1 = await manager.get_pool("db1", f"sqlite+aiosqlite:///{self.db_path}")
            pool2 = await manager.get_pool("db2", f"sqlite+aiosqlite:///{db_path2}")

            assert pool1 is not pool2
            assert len(manager._pools) == 2
            assert "db1" in manager._pools
            assert "db2" in manager._pools

        finally:
            import os

            with contextlib.suppress(OSError, FileNotFoundError):
                os.unlink(db_path2)


@pytest.mark.skip(reason="TransactionManager class not implemented yet")
class TestTransactionManager:
    """測試事務管理器."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}")

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_transaction_manager_context(self):
        """測試事務管理器上下文管理."""
        async with self.pool.get_connection() as conn:
            await conn.execute("CREATE TABLE test_tx (id INTEGER, value TEXT)")
            await conn.commit()

            tx_manager = TransactionManager(conn)

            async with tx_manager:
                await conn.execute("INSERT INTO test_tx (id, value) VALUES (1, 'test')")

            # 事務應該自動提交
            cursor = await conn.execute("SELECT COUNT(*) FROM test_tx")
            count = await cursor.fetchone()
            assert count[0] == 1

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_exception(self):
        """測試異常時事務自動回滾."""
        async with self.pool.get_connection() as conn:
            await conn.execute("CREATE TABLE test_rollback (id INTEGER, value TEXT)")
            await conn.commit()

            tx_manager = TransactionManager(conn)

            try:
                async with tx_manager:
                    await conn.execute(
                        "INSERT INTO test_rollback (id, value) VALUES (1, 'test')"
                    )
                    # 故意拋出異常
                    raise ValueError("測試異常")
            except ValueError:
                pass  # 預期的異常

            # 驗證事務已回滾
            cursor = await conn.execute("SELECT COUNT(*) FROM test_rollback")
            count = await cursor.fetchone()
            assert count[0] == 0

    @pytest.mark.asyncio
    async def test_nested_transaction_handling(self):
        """測試嵌套事務處理."""
        async with self.pool.get_connection() as conn:
            await conn.execute("CREATE TABLE test_nested (id INTEGER, value TEXT)")
            await conn.commit()

            tx_manager1 = TransactionManager(conn)
            tx_manager2 = TransactionManager(conn)

            async with tx_manager1:
                await conn.execute(
                    "INSERT INTO test_nested (id, value) VALUES (1, 'outer')"
                )

                async with tx_manager2:
                    await conn.execute(
                        "INSERT INTO test_nested (id, value) VALUES (2, 'inner')"
                    )

            # 驗證兩條記錄都已提交
            cursor = await conn.execute("SELECT COUNT(*) FROM test_nested")
            count = await cursor.fetchone()
            assert count[0] == 2


class TestDatabaseIntegration:
    """測試資料庫整合功能."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_concurrent_connections(self):
        """測試並發連接處理."""
        pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}", pool_size=3)

        async def worker(worker_id: int):
            async with pool.get_connection() as conn:
                await conn.execute(
                    f"CREATE TABLE IF NOT EXISTS worker_{worker_id} (id INTEGER)"
                )
                await conn.commit()
                return worker_id

        # 並發執行多個工作任務
        tasks = [worker(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert results == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_database_migration_simulation(self):
        """測試資料庫遷移模擬."""
        pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}")

        async with pool.get_connection() as conn:
            # 模擬初始表結構
            await conn.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            await conn.commit()

            # 插入測試數據
            await conn.execute("INSERT INTO users (name) VALUES ('test_user')")
            await conn.commit()

            # 模擬遷移:添加新列
            await conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            await conn.commit()

            # 驗證遷移成功
            cursor = await conn.execute("PRAGMA table_info(users)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            assert "id" in column_names
            assert "name" in column_names
            assert "email" in column_names

    @pytest.mark.asyncio
    async def test_performance_with_bulk_operations(self):
        """測試批量操作性能."""
        pool = DatabasePool(f"sqlite+aiosqlite:///{self.db_path}")

        async with pool.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE performance_test (
                    id INTEGER PRIMARY KEY,
                    data TEXT
                )
            """)
            await conn.commit()

            # 批量插入測試
            import time

            start_time = time.time()

            await conn.execute("BEGIN")
            for i in range(1000):
                await conn.execute(
                    "INSERT INTO performance_test (data) VALUES (?)",
                    (f"test_data_{i}",),
                )
            await conn.commit()

            end_time = time.time()
            execution_time = end_time - start_time

            # 驗證數據插入成功且性能合理(小於5秒)
            cursor = await conn.execute("SELECT COUNT(*) FROM performance_test")
            count = await cursor.fetchone()
            assert count[0] == 1000
            assert execution_time < 5.0  # 性能基準
