"""
重試機制單元測試  
T3 - 併發與資料庫鎖定穩定性實施

測試指數退避重試裝飾器的邏輯與錯誤處理
"""

import time
import unittest
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from src.db.retry import (
    retry_on_database_locked,
    RetryStrategy,
    DatabaseRetryError,
    is_retryable_database_error,
    retry_database_operation,
    CommonRetryStrategies
)


class TestRetryStrategy(unittest.TestCase):
    """測試 RetryStrategy 類"""
    
    def test_default_strategy(self):
        """測試預設重試策略"""
        strategy = RetryStrategy()
        
        self.assertEqual(strategy.max_retries, 5)
        self.assertEqual(strategy.base_delay, 0.1)
        self.assertEqual(strategy.max_delay, 30.0)
        self.assertEqual(strategy.backoff_multiplier, 2.0)
        self.assertTrue(strategy.jitter)
    
    def test_custom_strategy(self):
        """測試自定義重試策略"""
        strategy = RetryStrategy(
            max_retries=3,
            base_delay=0.5,
            max_delay=10.0,
            backoff_multiplier=1.5,
            jitter=False
        )
        
        self.assertEqual(strategy.max_retries, 3)
        self.assertEqual(strategy.base_delay, 0.5)
        self.assertEqual(strategy.max_delay, 10.0)
        self.assertEqual(strategy.backoff_multiplier, 1.5)
        self.assertFalse(strategy.jitter)
    
    def test_delay_calculation(self):
        """測試延遲時間計算"""
        strategy = RetryStrategy(
            base_delay=0.1,
            backoff_multiplier=2.0,
            max_delay=5.0,
            jitter=False
        )
        
        # 測試指數退避
        self.assertAlmostEqual(strategy.calculate_delay(0), 0.1)
        self.assertAlmostEqual(strategy.calculate_delay(1), 0.2) 
        self.assertAlmostEqual(strategy.calculate_delay(2), 0.4)
        self.assertAlmostEqual(strategy.calculate_delay(3), 0.8)
        
        # 測試最大延遲限制
        self.assertLessEqual(strategy.calculate_delay(10), 5.0)
    
    def test_jitter_effect(self):
        """測試抖動效果"""
        strategy = RetryStrategy(
            base_delay=1.0,
            jitter=True,
            jitter_range=0.2
        )
        
        delays = [strategy.calculate_delay(0) for _ in range(100)]
        
        # 檢查延遲時間有變化（抖動效果）
        unique_delays = set(delays)
        self.assertGreater(len(unique_delays), 1)
        
        # 檢查延遲時間範圍合理
        min_delay = min(delays)
        max_delay = max(delays)
        self.assertGreater(min_delay, 0.7)  # 基準值的80%左右
        self.assertLess(max_delay, 1.3)     # 基準值的120%左右


class TestIsRetryableError(unittest.TestCase):
    """測試錯誤類型判斷"""
    
    def test_retryable_operational_errors(self):
        """測試可重試的操作錯誤"""
        retryable_messages = [
            "database is locked",
            "database table is locked",
            "database schema has changed",
            "cannot commit transaction",
            "sql logic error",
            "busy",
            "locked"
        ]
        
        for message in retryable_messages:
            error = sqlite3.OperationalError(message)
            self.assertTrue(is_retryable_database_error(error))
    
    def test_non_retryable_errors(self):
        """測試不可重試的錯誤"""
        non_retryable_errors = [
            ValueError("Invalid parameter"),
            KeyError("Missing key"),
            sqlite3.OperationalError("syntax error"),
            sqlite3.OperationalError("no such table"),
            RuntimeError("General error")
        ]
        
        for error in non_retryable_errors:
            self.assertFalse(is_retryable_database_error(error))
    
    def test_temporary_errors(self):
        """測試暫時性錯誤"""
        temp_error = sqlite3.IntegrityError("temporary constraint violation")
        self.assertTrue(is_retryable_database_error(temp_error))
        
        retry_error = sqlite3.DatabaseError("please retry")
        self.assertTrue(is_retryable_database_error(retry_error))


class TestRetryDecorator(unittest.TestCase):
    """測試重試裝飾器"""
    
    def test_successful_operation_no_retry(self):
        """測試成功操作不重試"""
        call_count = 0
        
        @retry_on_database_locked(max_retries=3, log_attempts=False)
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_operation()
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)
    
    def test_eventual_success_after_retries(self):
        """測試重試後成功"""
        call_count = 0
        
        @retry_on_database_locked(max_retries=3, base_delay=0.01, log_attempts=False)
        def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "success"
        
        result = eventually_successful_operation()
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
    
    def test_max_retries_reached(self):
        """測試達到最大重試次數"""
        call_count = 0
        
        @retry_on_database_locked(max_retries=2, base_delay=0.01, log_attempts=False)
        def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database is locked")
        
        with self.assertRaises(DatabaseRetryError) as cm:
            always_failing_operation()
        
        self.assertEqual(call_count, 3)  # 初始嘗試 + 2次重試
        self.assertEqual(cm.exception.attempts, 3)
        self.assertIsInstance(cm.exception.original_error, sqlite3.OperationalError)
    
    def test_non_retryable_error_immediate_fail(self):
        """測試不可重試錯誤立即失敗"""
        call_count = 0
        
        @retry_on_database_locked(max_retries=3, log_attempts=False)
        def non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid parameter")
        
        with self.assertRaises(ValueError):
            non_retryable_error()
        
        self.assertEqual(call_count, 1)  # 只嘗試一次
    
    def test_custom_retry_strategy(self):
        """測試自定義重試策略"""
        call_count = 0
        strategy = RetryStrategy(max_retries=1, base_delay=0.01)
        
        @retry_on_database_locked(strategy=strategy, log_attempts=False)
        def custom_strategy_operation():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database is locked")
        
        with self.assertRaises(DatabaseRetryError):
            custom_strategy_operation()
        
        self.assertEqual(call_count, 2)  # 初始嘗試 + 1次重試


class TestAsyncRetryDecorator(unittest.TestCase):
    """測試非同步重試裝飾器"""
    
    def test_async_successful_operation(self):
        """測試非同步成功操作"""
        import asyncio
        
        call_count = 0
        
        @retry_on_database_locked(max_retries=3, log_attempts=False)
        async def async_successful_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "async_success"
        
        async def run_test():
            result = await async_successful_operation()
            return result
        
        result = asyncio.run(run_test())
        
        self.assertEqual(result, "async_success")
        self.assertEqual(call_count, 1)
    
    def test_async_eventual_success(self):
        """測試非同步重試後成功"""
        import asyncio
        
        call_count = 0
        
        @retry_on_database_locked(max_retries=3, base_delay=0.01, log_attempts=False)
        async def async_eventually_successful():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "async_success"
        
        async def run_test():
            result = await async_eventually_successful()
            return result
        
        result = asyncio.run(run_test())
        
        self.assertEqual(result, "async_success")
        self.assertEqual(call_count, 3)


class TestRetryOperationFunction(unittest.TestCase):
    """測試直接重試操作函數"""
    
    def test_direct_retry_success(self):
        """測試直接重試成功"""
        call_count = 0
        
        def operation_to_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise sqlite3.OperationalError("database is locked")
            return "direct_success"
        
        strategy = RetryStrategy(max_retries=2, base_delay=0.01, jitter=False)
        result = retry_database_operation(operation_to_retry, strategy=strategy)
        
        self.assertEqual(result, "direct_success")
        self.assertEqual(call_count, 2)
    
    def test_direct_retry_with_parameters(self):
        """測試帶參數的直接重試"""
        def operation_with_params(x, y, z=None):
            if z == "fail":
                raise sqlite3.OperationalError("database is locked")
            return x + y
        
        result = retry_database_operation(
            operation_with_params, 
            1, 2, 
            z="success",
            strategy=CommonRetryStrategies.CONSERVATIVE
        )
        
        self.assertEqual(result, 3)


class TestCommonRetryStrategies(unittest.TestCase):
    """測試常用重試策略"""
    
    def test_aggressive_strategy(self):
        """測試積極策略"""
        strategy = CommonRetryStrategies.AGGRESSIVE
        
        self.assertEqual(strategy.max_retries, 10)
        self.assertEqual(strategy.base_delay, 0.05)
        self.assertEqual(strategy.max_delay, 5.0)
        self.assertEqual(strategy.backoff_multiplier, 1.5)
    
    def test_balanced_strategy(self):
        """測試平衡策略"""
        strategy = CommonRetryStrategies.BALANCED
        
        self.assertEqual(strategy.max_retries, 5)
        self.assertEqual(strategy.base_delay, 0.1)
        self.assertEqual(strategy.max_delay, 30.0)
        self.assertEqual(strategy.backoff_multiplier, 2.0)
    
    def test_conservative_strategy(self):
        """測試保守策略"""
        strategy = CommonRetryStrategies.CONSERVATIVE
        
        self.assertEqual(strategy.max_retries, 3)
        self.assertEqual(strategy.base_delay, 0.5)
        self.assertEqual(strategy.max_delay, 60.0)
        self.assertEqual(strategy.backoff_multiplier, 3.0)


class TestRetryWithRealDatabase(unittest.TestCase):
    """使用真實資料庫測試重試機制"""
    
    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'retry_test.db')
        
        # 建立測試資料庫
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """測試後清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_access_with_retry(self):
        """測試併發存取的重試效果"""
        
        @retry_on_database_locked(
            max_retries=5, 
            base_delay=0.01, 
            backoff_multiplier=1.5,
            log_attempts=False
        )
        def insert_with_retry(thread_id, count):
            success_count = 0
            for i in range(count):
                conn = sqlite3.connect(self.db_path, timeout=1.0)
                try:
                    conn.execute(
                        "INSERT INTO test_table (value) VALUES (?)",
                        (f"thread_{thread_id}_value_{i}",)
                    )
                    conn.commit()
                    success_count += 1
                except Exception as e:
                    # 重新拋出讓重試機制處理
                    raise sqlite3.OperationalError(f"Insert failed: {e}")
                finally:
                    conn.close()
            
            return success_count
        
        # 使用多執行緒併發插入
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(insert_with_retry, i, 10) 
                for i in range(4)
            ]
            
            for future in futures:
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    print(f"Thread failed: {e}")
                    results.append(0)
        
        # 檢查結果
        total_insertions = sum(results)
        self.assertGreater(total_insertions, 0)
        
        # 驗證實際插入的資料數量
        conn = sqlite3.connect(self.db_path)
        actual_count = conn.execute("SELECT COUNT(*) FROM test_table").fetchone()[0]
        conn.close()
        
        self.assertEqual(actual_count, total_insertions)
        print(f"併發插入測試 - 成功插入: {total_insertions} 筆資料")


if __name__ == '__main__':
    # 設定測試日誌級別
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # 執行測試
    unittest.main(verbosity=2)