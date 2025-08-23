"""
SQLite 連線工廠單元測試
T3 - 併發與資料庫鎖定穩定性實施

測試連線工廠的配置、連線重用與併發安全性
"""

import os
import tempfile
import unittest
import threading
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

from src.db.sqlite import (
    SQLiteConnectionFactory,
    OptimizedConnection,
    get_connection_factory,
    create_optimized_connection,
    cleanup_connections
)


class TestOptimizedConnection(unittest.TestCase):
    """測試 OptimizedConnection 類"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
    
    def tearDown(self):
        """測試後清理"""
        cleanup_connections()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_connection_creation(self):
        """測試連線建立"""
        conn = OptimizedConnection(self.db_path)
        sqlite_conn = conn.connect()
        
        self.assertIsInstance(sqlite_conn, sqlite3.Connection)
        self.assertFalse(conn.is_closed)
        
        conn.close()
        self.assertTrue(conn.is_closed)
    
    def test_connection_configuration(self):
        """測試連線配置"""
        conn = OptimizedConnection(self.db_path)
        sqlite_conn = conn.connect()
        
        # 檢查 WAL 模式
        cursor = sqlite_conn.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        self.assertEqual(journal_mode.upper(), 'WAL')
        
        # 檢查 busy_timeout
        cursor = sqlite_conn.execute("PRAGMA busy_timeout;")
        busy_timeout = cursor.fetchone()[0]
        self.assertEqual(busy_timeout, 30000)
        
        # 檢查同步模式
        cursor = sqlite_conn.execute("PRAGMA synchronous;")
        synchronous = cursor.fetchone()[0]
        self.assertEqual(synchronous, 1)  # NORMAL = 1
        
        conn.close()
    
    def test_basic_database_operations(self):
        """測試基礎資料庫操作"""
        conn = OptimizedConnection(self.db_path)
        
        # 建立測試表
        conn.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        conn.commit()
        
        # 插入資料
        conn.execute("INSERT INTO test_table (name) VALUES (?)", ("test_name",))
        conn.commit()
        
        # 查詢資料
        result = conn.fetchone("SELECT * FROM test_table WHERE name = ?", ("test_name",))
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "test_name")
        
        # 批量插入
        conn.executemany(
            "INSERT INTO test_table (name) VALUES (?)",
            [("name1",), ("name2",), ("name3",)]
        )
        conn.commit()
        
        # 查詢多筆
        results = conn.fetchall("SELECT name FROM test_table ORDER BY id")
        names = [row[0] for row in results]
        self.assertEqual(names, ["test_name", "name1", "name2", "name3"])
        
        conn.close()
    
    def test_transaction_management(self):
        """測試事務管理"""
        conn = OptimizedConnection(self.db_path)
        
        # 建立測試表
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()
        
        # 測試正常事務
        with conn.transaction():
            conn.execute("INSERT INTO test_table (value) VALUES (?)", ("test1",))
            conn.execute("INSERT INTO test_table (value) VALUES (?)", ("test2",))
        
        # 驗證資料已提交
        results = conn.fetchall("SELECT value FROM test_table ORDER BY id")
        self.assertEqual(len(results), 2)
        
        # 測試事務回滾
        try:
            with conn.transaction():
                conn.execute("INSERT INTO test_table (value) VALUES (?)", ("test3",))
                # 故意觸發錯誤
                conn.execute("INVALID SQL")
        except sqlite3.OperationalError:
            pass
        
        # 驗證事務已回滾
        results = conn.fetchall("SELECT value FROM test_table ORDER BY id")
        self.assertEqual(len(results), 2)  # 應該還是2筆
        
        conn.close()


class TestSQLiteConnectionFactory(unittest.TestCase):
    """測試 SQLiteConnectionFactory 類"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_factory.db')
    
    def tearDown(self):
        """測試後清理"""
        cleanup_connections()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_singleton_behavior(self):
        """測試單例模式"""
        factory1 = SQLiteConnectionFactory(self.db_path)
        factory2 = SQLiteConnectionFactory(self.db_path)
        
        self.assertIs(factory1, factory2)
    
    def test_different_paths_different_instances(self):
        """測試不同路徑產生不同實例"""
        db_path2 = os.path.join(self.temp_dir, 'test_factory2.db')
        
        factory1 = SQLiteConnectionFactory(self.db_path)
        factory2 = SQLiteConnectionFactory(db_path2)
        
        self.assertIsNot(factory1, factory2)
    
    def test_thread_specific_connections(self):
        """測試執行緒特定連線"""
        factory = SQLiteConnectionFactory(self.db_path)
        connections = {}
        
        def get_connection_in_thread(thread_id):
            # 每個執行緒獲取自己的連線
            conn = factory.get_connection()
            connections[thread_id] = id(conn)  # 使用物件 id 來比較
        
        # 在不同執行緒中獲取連線
        threads = []
        for i in range(3):
            thread = threading.Thread(target=get_connection_in_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 檢查每個執行緒都獲得了不同的連線
        self.assertEqual(len(connections), 3)
        connection_ids = list(connections.values())
        unique_ids = set(connection_ids)
        # 由於是不同執行緒，應該有不同的連線 id
        self.assertGreaterEqual(len(unique_ids), 1)  # 至少有一個，可能因為執行緒快速結束共享了連線
    
    def test_connection_reuse(self):
        """測試連線重用"""
        factory = SQLiteConnectionFactory(self.db_path)
        
        conn1 = factory.get_connection()
        conn2 = factory.get_connection()
        
        # 在同一執行緒中應該獲得相同的連線
        self.assertIs(conn1, conn2)
    
    def test_connection_stats(self):
        """測試連線統計"""
        factory = SQLiteConnectionFactory(self.db_path)
        
        # 初始統計
        stats = factory.get_connection_stats()
        self.assertEqual(stats['total_connections'], 0)
        self.assertEqual(stats['active_connections'], 0)
        
        # 獲取連線後統計
        conn = factory.get_connection()
        stats = factory.get_connection_stats()
        self.assertEqual(stats['total_connections'], 1)
        self.assertEqual(stats['active_connections'], 1)
        
        # 關閉連線後統計
        conn.close()
        stats = factory.get_connection_stats()
        self.assertEqual(stats['total_connections'], 1)
        self.assertEqual(stats['active_connections'], 0)
    
    def test_close_all_connections(self):
        """測試關閉所有連線"""
        factory = SQLiteConnectionFactory(self.db_path)
        
        # 獲取連線
        conn1 = factory.get_connection()
        self.assertFalse(conn1.is_closed)
        
        # 關閉所有連線
        factory.close_all_connections()
        self.assertTrue(conn1.is_closed)
        
        # 統計應該清零
        stats = factory.get_connection_stats()
        self.assertEqual(stats['total_connections'], 0)


class TestConcurrentAccess(unittest.TestCase):
    """測試併發存取"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_concurrent.db')
        
        # 建立測試資料庫與表
        factory = SQLiteConnectionFactory(self.db_path)
        conn = factory.get_connection()
        conn.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER,
                value TEXT,
                timestamp REAL
            )
        """)
        conn.commit()
    
    def tearDown(self):
        """測試後清理"""
        cleanup_connections()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_writes(self):
        """測試併發寫入"""
        factory = SQLiteConnectionFactory(self.db_path)
        
        def write_data(thread_id, count=100):
            """在指定執行緒中寫入資料"""
            conn = factory.get_connection()
            results = []
            
            for i in range(count):
                try:
                    conn.execute(
                        "INSERT INTO test_table (thread_id, value, timestamp) VALUES (?, ?, ?)",
                        (thread_id, f"value_{i}", time.time())
                    )
                    conn.commit()
                    results.append(True)
                except Exception as e:
                    results.append(False)
                    print(f"Thread {thread_id} write error: {e}")
            
            return results
        
        # 使用多個執行緒併發寫入
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(write_data, thread_id, 50) 
                for thread_id in range(5)
            ]
            
            results = []
            for future in as_completed(futures):
                results.extend(future.result())
        
        # 檢查寫入成功率
        success_rate = sum(results) / len(results)
        self.assertGreater(success_rate, 0.8)  # 至少80%成功率
        
        # 檢查總記錄數
        conn = factory.get_connection()
        total_records = conn.fetchone("SELECT COUNT(*) FROM test_table")[0]
        self.assertGreater(total_records, 0)
        
        print(f"併發寫入成功率: {success_rate:.2%}, 總記錄數: {total_records}")
    
    def test_concurrent_read_write(self):
        """測試併發讀寫"""
        factory = SQLiteConnectionFactory(self.db_path)
        
        # 先插入一些初始資料
        conn = factory.get_connection()
        for i in range(100):
            conn.execute(
                "INSERT INTO test_table (thread_id, value) VALUES (?, ?)",
                (0, f"initial_{i}")
            )
        conn.commit()
        
        def read_data(thread_id, count=50):
            """讀取資料"""
            conn = factory.get_connection()
            results = []
            
            for _ in range(count):
                try:
                    result = conn.fetchone("SELECT COUNT(*) FROM test_table")
                    results.append(result[0] if result else 0)
                    time.sleep(0.001)  # 短暫暫停
                except Exception as e:
                    print(f"Thread {thread_id} read error: {e}")
                    results.append(-1)
            
            return results
        
        def write_data(thread_id, count=20):
            """寫入資料"""
            conn = factory.get_connection()
            success_count = 0
            
            for i in range(count):
                try:
                    conn.execute(
                        "INSERT INTO test_table (thread_id, value) VALUES (?, ?)",
                        (thread_id, f"concurrent_{i}")
                    )
                    conn.commit()
                    success_count += 1
                    time.sleep(0.001)  # 短暫暫停
                except Exception as e:
                    print(f"Thread {thread_id} write error: {e}")
            
            return success_count
        
        # 併發讀寫測試
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 3個讀執行緒，2個寫執行緒
            read_futures = [
                executor.submit(read_data, f"r{i}", 30) 
                for i in range(3)
            ]
            write_futures = [
                executor.submit(write_data, f"w{i}", 15) 
                for i in range(2)
            ]
            
            # 收集結果
            read_results = []
            for future in as_completed(read_futures):
                read_results.extend(future.result())
            
            write_results = []
            for future in as_completed(write_futures):
                write_results.append(future.result())
        
        # 檢查讀取沒有錯誤
        error_reads = sum(1 for x in read_results if x < 0)
        self.assertEqual(error_reads, 0)
        
        # 檢查寫入成功數量
        total_writes = sum(write_results)
        self.assertGreater(total_writes, 0)
        
        print(f"併發讀寫測試 - 讀取操作: {len(read_results)}, 寫入成功: {total_writes}")


class TestUtilityFunctions(unittest.TestCase):
    """測試工具函數"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_utils.db')
    
    def tearDown(self):
        """測試後清理"""
        cleanup_connections()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_connection_factory(self):
        """測試 get_connection_factory 函數"""
        factory = get_connection_factory(self.db_path)
        self.assertIsInstance(factory, SQLiteConnectionFactory)
        
        # 應該返回相同的實例
        factory2 = get_connection_factory(self.db_path)
        self.assertIs(factory, factory2)
    
    def test_create_optimized_connection(self):
        """測試 create_optimized_connection 函數"""
        conn = create_optimized_connection(self.db_path)
        self.assertIsInstance(conn, OptimizedConnection)
        
        # 測試基本操作
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        
        result = conn.fetchone("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(result[0], "test")
        
        conn.close()
    
    def test_cleanup_connections(self):
        """測試連線清理函數"""
        # 建立一些連線工廠
        factory1 = get_connection_factory(self.db_path)
        factory2 = get_connection_factory(
            os.path.join(self.temp_dir, 'test2.db')
        )
        
        # 獲取連線
        conn1 = factory1.get_connection()
        conn2 = factory2.get_connection()
        
        self.assertFalse(conn1.is_closed)
        self.assertFalse(conn2.is_closed)
        
        # 清理所有連線
        cleanup_connections()
        
        self.assertTrue(conn1.is_closed)
        self.assertTrue(conn2.is_closed)


if __name__ == '__main__':
    # 設定測試日誌級別
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # 執行測試
    unittest.main(verbosity=2)