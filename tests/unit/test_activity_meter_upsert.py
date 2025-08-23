"""
Activity Meter UPSERT 邏輯測試
T3 - 併發與資料庫鎖定穩定性實施

測試併發安全的 ActivityMeter 服務與 UPSERT 操作
"""

import os
import tempfile
import unittest
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.activity.concurrent_activity_meter import (
    ConcurrentActivityMeterService,
    integrate_with_existing_service,
    test_upsert_performance
)


class TestConcurrentActivityMeterService(unittest.TestCase):
    """測試併發安全的 ActivityMeter 服務"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_activity.db')
        self.service = ConcurrentActivityMeterService(self.db_path)
    
    def tearDown(self):
        """測試後清理"""
        try:
            self.service.close()
        except:
            pass
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_service_initialization(self):
        """測試服務初始化"""
        self.assertEqual(self.service.db_path, self.db_path)
        self.assertIsNotNone(self.service.factory)
        
        # 檢查資料表是否正確創建
        conn = self.service.factory.get_connection()
        result = conn.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_meter'"
        )
        self.assertIsNotNone(result)
    
    def test_table_structure(self):
        """測試資料表結構"""
        conn = self.service.factory.get_connection()
        
        # 檢查表結構
        table_info = conn.fetchall("PRAGMA table_info(activity_meter)")
        columns = {col[1]: col[2] for col in table_info}  # name: type
        
        self.assertIn('guild_id', columns)
        self.assertIn('user_id', columns)
        self.assertIn('score', columns)
        self.assertIn('last_msg', columns)
        
        # 檢查主鍵約束
        pk_columns = [col[1] for col in table_info if col[5] > 0]
        self.assertIn('guild_id', pk_columns)
        self.assertIn('user_id', pk_columns)
    
    def test_upsert_insert_new_record(self):
        """測試 UPSERT 插入新記錄"""
        result = self.service.upsert_activity_score(
            guild_id=123,
            user_id=456,
            score_delta=10.5,
            last_msg_time=1000
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['score'], 10.5)
        self.assertEqual(result['last_msg'], 1000)
        
        # 驗證資料確實插入
        record = self.service.get_activity_score(123, 456)
        self.assertIsNotNone(record)
        self.assertEqual(record['score'], 10.5)
    
    def test_upsert_update_existing_record(self):
        """測試 UPSERT 更新現有記錄"""
        # 先插入一筆記錄
        self.service.upsert_activity_score(123, 456, 10.0, 1000)
        
        # 更新同一筆記錄
        result = self.service.upsert_activity_score(123, 456, 5.0, 2000)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['score'], 15.0)  # 10.0 + 5.0
        self.assertEqual(result['last_msg'], 2000)
        
        # 驗證更新正確
        record = self.service.get_activity_score(123, 456)
        self.assertEqual(record['score'], 15.0)
        self.assertEqual(record['last_msg'], 2000)
    
    def test_upsert_max_score_limit(self):
        """測試最大分數限制"""
        # 插入接近最大值的分數
        result = self.service.upsert_activity_score(123, 456, 95.0, 1000, max_score=100.0)
        self.assertEqual(result['score'], 95.0)
        
        # 嘗試超過最大值
        result = self.service.upsert_activity_score(123, 456, 10.0, 2000, max_score=100.0)
        self.assertEqual(result['score'], 100.0)  # 應該被限制在最大值
    
    def test_get_activity_score_nonexistent(self):
        """測試獲取不存在的記錄"""
        result = self.service.get_activity_score(999, 999)
        self.assertIsNone(result)
    
    def test_batch_upsert_activities(self):
        """測試批次 UPSERT 操作"""
        activities = [
            (123, 456, 10.0, 1000),
            (123, 457, 15.0, 1100),
            (124, 456, 20.0, 1200),
            (123, 456, 5.0, 1300),  # 更新第一筆記錄
        ]
        
        result = self.service.batch_upsert_activities(activities)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['processed'], 4)
        self.assertEqual(result['errors'], 0)
        
        # 驗證批次操作結果
        record1 = self.service.get_activity_score(123, 456)
        self.assertEqual(record1['score'], 15.0)  # 10.0 + 5.0
        
        record2 = self.service.get_activity_score(123, 457)
        self.assertEqual(record2['score'], 15.0)
        
        record3 = self.service.get_activity_score(124, 456)
        self.assertEqual(record3['score'], 20.0)
    
    def test_get_top_users_by_score(self):
        """測試活躍度排行榜"""
        # 插入測試資料
        activities = [
            (123, 1, 100.0, 1000),
            (123, 2, 80.0, 1100),
            (123, 3, 90.0, 1200),
            (123, 4, 70.0, 1300),
            (123, 5, 95.0, 1400),
        ]
        
        self.service.batch_upsert_activities(activities)
        
        # 獲取前3名
        top_users = self.service.get_top_users_by_score(123, limit=3)
        
        self.assertEqual(len(top_users), 3)
        self.assertEqual(top_users[0]['user_id'], 1)  # 100.0 分
        self.assertEqual(top_users[1]['user_id'], 5)  # 95.0 分
        self.assertEqual(top_users[2]['user_id'], 3)  # 90.0 分
    
    def test_statistics(self):
        """測試統計資訊"""
        # 插入一些測試資料
        self.service.upsert_activity_score(123, 456, 10.0, 1000)
        self.service.upsert_activity_score(124, 457, 15.0, 1100)
        
        stats = self.service.get_statistics()
        
        self.assertEqual(stats['total_activity_records'], 2)
        self.assertIn('connection_stats', stats)
        self.assertEqual(stats['database_path'], self.db_path)


class TestConcurrentOperations(unittest.TestCase):
    """測試併發操作"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_concurrent.db')
        self.service = ConcurrentActivityMeterService(self.db_path)
    
    def tearDown(self):
        """測試後清理"""
        try:
            self.service.close()
        except:
            pass
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_upserts_same_user(self):
        """測試同一用戶的併發 UPSERT 操作"""
        guild_id = 123
        user_id = 456
        num_threads = 5
        operations_per_thread = 20
        
        def perform_upserts(thread_id):
            results = []
            for i in range(operations_per_thread):
                try:
                    result = self.service.upsert_activity_score(
                        guild_id, user_id, 1.0, int(time.time() * 1000) + i
                    )
                    results.append(result['success'])
                except Exception as e:
                    results.append(False)
                    print(f"Thread {thread_id} operation {i} failed: {e}")
            return results
        
        # 執行併發操作
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(perform_upserts, i) 
                for i in range(num_threads)
            ]
            
            all_results = []
            for future in as_completed(futures):
                all_results.extend(future.result())
        
        # 檢查成功率
        success_count = sum(all_results)
        total_operations = num_threads * operations_per_thread
        success_rate = success_count / total_operations
        
        self.assertGreater(success_rate, 0.8)  # 至少 80% 成功率
        
        # 檢查最終分數
        final_record = self.service.get_activity_score(guild_id, user_id)
        self.assertIsNotNone(final_record)
        self.assertGreater(final_record['score'], 0)
        
        print(f"併發 UPSERT 測試 - 成功率: {success_rate:.2%}, 最終分數: {final_record['score']}")
    
    def test_concurrent_upserts_different_users(self):
        """測試不同用戶的併發 UPSERT 操作"""
        guild_id = 123
        num_threads = 10
        operations_per_thread = 10
        
        def perform_upserts_different_users(thread_id):
            success_count = 0
            for i in range(operations_per_thread):
                user_id = thread_id * 1000 + i  # 確保不同的 user_id
                try:
                    result = self.service.upsert_activity_score(
                        guild_id, user_id, 5.0, int(time.time())
                    )
                    if result['success']:
                        success_count += 1
                except Exception as e:
                    print(f"Thread {thread_id} user {user_id} failed: {e}")
            
            return success_count
        
        # 執行併發操作
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(perform_upserts_different_users, i) 
                for i in range(num_threads)
            ]
            
            total_success = sum(future.result() for future in as_completed(futures))
        
        total_expected = num_threads * operations_per_thread
        success_rate = total_success / total_expected
        
        self.assertGreater(success_rate, 0.9)  # 不同用戶操作成功率應該更高
        
        # 檢查總記錄數
        stats = self.service.get_statistics()
        self.assertGreater(stats['total_activity_records'], 0)
        
        print(f"不同用戶併發測試 - 成功率: {success_rate:.2%}, 總記錄: {stats['total_activity_records']}")
    
    def test_concurrent_read_write_operations(self):
        """測試併發讀寫操作"""
        guild_id = 123
        
        # 先插入一些基礎資料
        for user_id in range(1, 21):
            self.service.upsert_activity_score(guild_id, user_id, 10.0, 1000)
        
        def writer_task(thread_id):
            success_count = 0
            for i in range(50):
                user_id = (thread_id * 10 + i) % 20 + 1  # 循環使用 user_id 1-20
                try:
                    result = self.service.upsert_activity_score(
                        guild_id, user_id, 1.0, int(time.time())
                    )
                    if result['success']:
                        success_count += 1
                    time.sleep(0.001)  # 短暫暫停
                except Exception as e:
                    print(f"Writer {thread_id} failed: {e}")
            return success_count
        
        def reader_task(thread_id):
            read_count = 0
            for i in range(100):
                user_id = i % 20 + 1  # 循環讀取 user_id 1-20
                try:
                    result = self.service.get_activity_score(guild_id, user_id)
                    if result is not None:
                        read_count += 1
                    time.sleep(0.0005)  # 短暫暫停
                except Exception as e:
                    print(f"Reader {thread_id} failed: {e}")
            return read_count
        
        # 併發讀寫測試
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 3個寫入者，3個讀取者
            write_futures = [executor.submit(writer_task, i) for i in range(3)]
            read_futures = [executor.submit(reader_task, i) for i in range(3)]
            
            write_results = [f.result() for f in as_completed(write_futures)]
            read_results = [f.result() for f in as_completed(read_futures)]
        
        total_writes = sum(write_results)
        total_reads = sum(read_results)
        
        self.assertGreater(total_writes, 0)
        self.assertGreater(total_reads, 0)
        
        print(f"併發讀寫測試 - 寫入成功: {total_writes}, 讀取成功: {total_reads}")


class TestMigrationAndCompatibility(unittest.TestCase):
    """測試資料遷移和相容性"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_migration.db')
    
    def tearDown(self):
        """測試後清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_migration_from_old_structure(self):
        """測試從舊表結構遷移"""
        # 創建舊版表結構
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE activity_meter (
                guild_id INTEGER,
                user_id INTEGER,
                score REAL DEFAULT 0,
                last_msg INTEGER DEFAULT 0
            )
        """)
        
        # 插入一些重複資料（模擬舊版可能的情況）
        test_data = [
            (123, 456, 10.0, 1000),
            (123, 456, 15.0, 1500),  # 重複的 guild_id, user_id
            (123, 457, 20.0, 2000),
            (124, 456, 25.0, 2500),
        ]
        
        conn.executemany(
            "INSERT INTO activity_meter (guild_id, user_id, score, last_msg) VALUES (?, ?, ?, ?)",
            test_data
        )
        conn.commit()
        conn.close()
        
        # 初始化服務，應該觸發遷移
        service = ConcurrentActivityMeterService(self.db_path)
        
        try:
            # 檢查遷移後的表結構
            conn = service.factory.get_connection()
            table_info = conn.fetchall("PRAGMA table_info(activity_meter)")
            
            # 檢查主鍵約束
            pk_columns = [col[1] for col in table_info if col[5] > 0]
            self.assertIn('guild_id', pk_columns)
            self.assertIn('user_id', pk_columns)
            
            # 檢查資料去重結果
            records = conn.fetchall("SELECT guild_id, user_id, score, last_msg FROM activity_meter ORDER BY guild_id, user_id")
            
            # 應該只剩3筆記錄（重複的被去重了）
            self.assertEqual(len(records), 3)
            
            # 檢查去重邏輯是否正確（保留最大值）
            user_456_guild_123 = next(r for r in records if r[0] == 123 and r[1] == 456)
            self.assertEqual(user_456_guild_123[2], 15.0)  # 分數應該是較大的
            self.assertEqual(user_456_guild_123[3], 1500)  # 時間應該是較大的
            
        finally:
            service.close()
    
    def test_integration_helper(self):
        """測試整合輔助函數"""
        service = integrate_with_existing_service(self.db_path)
        
        self.assertIsInstance(service, ConcurrentActivityMeterService)
        self.assertEqual(service.db_path, self.db_path)
        
        # 測試基本功能
        result = service.upsert_activity_score(123, 456, 10.0, 1000)
        self.assertTrue(result['success'])
        
        service.close()


class TestPerformanceBenchmark(unittest.TestCase):
    """性能基準測試"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_performance.db')
    
    def tearDown(self):
        """測試後清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_upsert_performance(self):
        """測試 UPSERT 性能"""
        num_operations = 1000
        
        result = test_upsert_performance(self.db_path, num_operations)
        
        self.assertEqual(result['total_operations'], num_operations)
        self.assertGreater(result['success_rate'], 0.8)  # 至少 80% 成功率
        self.assertGreater(result['operations_per_second'], 100)  # 至少 100 ops/sec
        
        print(f"性能測試結果: {result}")


if __name__ == '__main__':
    # 設定測試日誌級別
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # 執行測試
    unittest.main(verbosity=2)