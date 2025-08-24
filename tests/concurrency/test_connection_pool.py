"""
T2 - 高併發連線競爭修復
併發測試套件

專業的連線池併發測試和效能驗證框架
"""

import asyncio
import logging
import os
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import threading
import statistics
from pathlib import Path

# 添加系統路徑支持
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from services.connection_pool.connection_pool_manager import ConnectionPoolManager, PoolConfiguration
from services.connection_pool.models import ConnectionPoolStats

logger = logging.getLogger('tests.concurrency.connection_pool')


@dataclass
class TestResult:
    """測試結果資料結構"""
    test_name: str
    duration_seconds: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    operations_per_second: float
    average_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate_percentage: float
    concurrent_workers: int
    max_connections_used: int
    errors: List[str]
    timestamp: datetime
    
    def __post_init__(self):
        """計算衍生指標"""
        if self.total_operations > 0:
            self.error_rate_percentage = (self.failed_operations / self.total_operations) * 100
        else:
            self.error_rate_percentage = 0.0


class ConcurrencyTestResult:
    """併發測試結果聚合"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.summary_stats: Dict[str, Any] = {}
    
    def add_result(self, result: TestResult):
        """添加測試結果"""
        self.results.append(result)
        self._update_summary()
    
    def _update_summary(self):
        """更新總體統計"""
        if not self.results:
            return
        
        total_operations = sum(r.total_operations for r in self.results)
        total_successful = sum(r.successful_operations for r in self.results)
        total_failed = sum(r.failed_operations for r in self.results)
        
        response_times = []
        for result in self.results:
            # 這裡需要從實際測試中收集響應時間數據
            pass
        
        self.summary_stats = {
            'total_tests': len(self.results),
            'total_operations': total_operations,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'overall_success_rate': (total_successful / total_operations) if total_operations > 0 else 0,
            'overall_error_rate': (total_failed / total_operations * 100) if total_operations > 0 else 0,
            'average_throughput': statistics.mean([r.operations_per_second for r in self.results]),
            'max_throughput': max([r.operations_per_second for r in self.results]),
            'min_throughput': min([r.operations_per_second for r in self.results]),
            'average_response_time': statistics.mean([r.average_response_time_ms for r in self.results]),
        }


class ConnectionPoolTestSuite:
    """連線池測試套件"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化測試套件
        
        參數：
            db_path: 測試資料庫路徑，如果為None則使用臨時檔案
        """
        if db_path is None:
            # 使用臨時檔案進行測試
            self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            self.db_path = self.temp_db.name
            self.temp_db.close()
        else:
            self.db_path = db_path
        
        self.results = ConcurrencyTestResult()
        self.pool_manager: Optional[ConnectionPoolManager] = None
        
        logger.info(f"測試資料庫路徑：{self.db_path}")
    
    async def setup_test_environment(self, pool_config: Optional[PoolConfiguration] = None):
        """設置測試環境"""
        if pool_config is None:
            pool_config = PoolConfiguration(
                min_connections=2,
                max_connections=20,
                connection_timeout=30.0,
                acquire_timeout=10.0,
                enable_monitoring=True
            )
        
        self.pool_manager = ConnectionPoolManager(
            db_path=self.db_path,
            config=pool_config
        )
        
        await self.pool_manager.start()
        
        # 建立測試表格
        await self._create_test_tables()
        logger.info("測試環境設置完成")
    
    async def _create_test_tables(self):
        """建立測試表格"""
        async with self.pool_manager.connection() as conn:
            # 建立測試用戶表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 建立測試活動表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    points INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES test_users(id)
                )
            """)
            
            # 建立索引優化查詢
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_test_users_username ON test_users(username)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_test_activities_user_id ON test_activities(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_test_activities_timestamp ON test_activities(timestamp)")
            
            await conn.commit()
        
        logger.info("測試表格建立完成")
    
    async def run_concurrent_read_test(
        self,
        num_workers: int = 10,
        operations_per_worker: int = 100,
        test_duration: Optional[float] = None
    ) -> TestResult:
        """
        執行併發讀取測試
        
        參數：
            num_workers: 併發工作者數量
            operations_per_worker: 每個工作者的操作數量
            test_duration: 測試持續時間（秒），如果指定則忽略operations_per_worker
        """
        logger.info(f"開始併發讀取測試：{num_workers} 工作者，每工作者 {operations_per_worker} 操作")
        
        # 先插入一些測試資料
        await self._populate_test_data(1000)
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        total_operations = 0
        
        async def worker_read_task(worker_id: int):
            """工作者讀取任務"""
            nonlocal successful_operations, total_operations, response_times, errors
            
            worker_successful = 0
            worker_total = 0
            
            operations = operations_per_worker
            if test_duration:
                operations = float('inf')  # 無限循環直到時間到
            
            operation_count = 0
            while operation_count < operations:
                if test_duration and (time.time() - start_time) > test_duration:
                    break
                
                operation_start = time.time()
                try:
                    async with self.pool_manager.connection() as conn:
                        # 隨機查詢用戶資料
                        user_id = (worker_id * 1000 + operation_count) % 1000 + 1
                        async with conn.execute("SELECT * FROM test_users WHERE id = ?", (user_id,)) as cursor:
                            result = await cursor.fetchone()
                        
                        if result:
                            # 查詢相關活動
                            async with conn.execute(
                                "SELECT * FROM test_activities WHERE user_id = ? LIMIT 10",
                                (user_id,)
                            ) as cursor:
                                activities = await cursor.fetchall()
                        
                        worker_successful += 1
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                
                except Exception as e:
                    error_msg = f"Worker {worker_id} 操作失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                worker_total += 1
                operation_count += 1
            
            successful_operations += worker_successful
            total_operations += worker_total
        
        # 啟動所有工作者任務
        tasks = [worker_read_task(i) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計指標
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p50_response_time = statistics.median(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        # 獲取連線池統計
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = TestResult(
            test_name="concurrent_read_test",
            duration_seconds=duration,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=total_operations - successful_operations,
            operations_per_second=ops_per_second,
            average_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            error_rate_percentage=0,  # 會在 __post_init__ 中計算
            concurrent_workers=num_workers,
            max_connections_used=max_connections_used,
            errors=errors[:10],  # 只保留前10個錯誤
            timestamp=datetime.now()
        )
        
        self.results.add_result(result)
        
        logger.info(
            f"併發讀取測試完成：{successful_operations}/{total_operations} 成功，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"平均響應時間 {avg_response_time:.2f} ms，"
            f"錯誤率 {result.error_rate_percentage:.2f}%"
        )
        
        return result
    
    async def run_concurrent_write_test(
        self,
        num_workers: int = 10,
        operations_per_worker: int = 50,
        test_duration: Optional[float] = None
    ) -> TestResult:
        """
        執行併發寫入測試
        
        參數：
            num_workers: 併發工作者數量
            operations_per_worker: 每個工作者的操作數量
            test_duration: 測試持續時間（秒）
        """
        logger.info(f"開始併發寫入測試：{num_workers} 工作者，每工作者 {operations_per_worker} 操作")
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        total_operations = 0
        
        async def worker_write_task(worker_id: int):
            """工作者寫入任務"""
            nonlocal successful_operations, total_operations, response_times, errors
            
            worker_successful = 0
            worker_total = 0
            
            operations = operations_per_worker
            if test_duration:
                operations = float('inf')
            
            operation_count = 0
            while operation_count < operations:
                if test_duration and (time.time() - start_time) > test_duration:
                    break
                
                operation_start = time.time()
                try:
                    async with self.pool_manager.connection() as conn:
                        # 插入新用戶
                        username = f"user_{worker_id}_{operation_count}_{uuid.uuid4().hex[:8]}"
                        email = f"{username}@test.com"
                        
                        await conn.execute("""
                            INSERT INTO test_users (username, email, score) 
                            VALUES (?, ?, ?)
                        """, (username, email, operation_count))
                        
                        # 獲取新插入的用戶ID
                        user_id = conn.lastrowid
                        
                        # 插入相關活動
                        await conn.execute("""
                            INSERT INTO test_activities (user_id, activity_type, points)
                            VALUES (?, ?, ?)
                        """, (user_id, "signup", 10))
                        
                        await conn.commit()
                        
                        worker_successful += 1
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                
                except Exception as e:
                    error_msg = f"Worker {worker_id} 寫入失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                worker_total += 1
                operation_count += 1
            
            successful_operations += worker_successful
            total_operations += worker_total
        
        # 啟動所有工作者任務
        tasks = [worker_write_task(i) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計指標
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p50_response_time = statistics.median(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        # 獲取連線池統計
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = TestResult(
            test_name="concurrent_write_test",
            duration_seconds=duration,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=total_operations - successful_operations,
            operations_per_second=ops_per_second,
            average_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            error_rate_percentage=0,  # 會在 __post_init__ 中計算
            concurrent_workers=num_workers,
            max_connections_used=max_connections_used,
            errors=errors[:10],
            timestamp=datetime.now()
        )
        
        self.results.add_result(result)
        
        logger.info(
            f"併發寫入測試完成：{successful_operations}/{total_operations} 成功，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"平均響應時間 {avg_response_time:.2f} ms，"
            f"錯誤率 {result.error_rate_percentage:.2f}%"
        )
        
        return result
    
    async def run_mixed_workload_test(
        self,
        num_workers: int = 15,
        read_percentage: float = 70.0,
        test_duration: float = 30.0
    ) -> TestResult:
        """
        執行混合工作負載測試（讀寫混合）
        
        參數：
            num_workers: 併發工作者數量
            read_percentage: 讀取操作百分比（0-100）
            test_duration: 測試持續時間（秒）
        """
        logger.info(
            f"開始混合工作負載測試：{num_workers} 工作者，"
            f"讀取比例 {read_percentage}%，持續 {test_duration} 秒"
        )
        
        # 先插入一些基礎資料
        await self._populate_test_data(500)
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        total_operations = 0
        read_operations = 0
        write_operations = 0
        
        async def worker_mixed_task(worker_id: int):
            """工作者混合任務"""
            nonlocal successful_operations, total_operations, response_times, errors
            nonlocal read_operations, write_operations
            
            worker_successful = 0
            worker_total = 0
            
            operation_count = 0
            while (time.time() - start_time) < test_duration:
                operation_start = time.time()
                
                # 根據百分比決定執行讀取還是寫入
                import random
                is_read_operation = random.uniform(0, 100) < read_percentage
                
                try:
                    async with self.pool_manager.connection() as conn:
                        if is_read_operation:
                            # 讀取操作
                            user_id = random.randint(1, 500)
                            async with conn.execute(
                                "SELECT u.*, COUNT(a.id) as activity_count "
                                "FROM test_users u LEFT JOIN test_activities a ON u.id = a.user_id "
                                "WHERE u.id = ? GROUP BY u.id",
                                (user_id,)
                            ) as cursor:
                                result = await cursor.fetchone()
                            read_operations += 1
                        else:
                            # 寫入操作
                            username = f"mixed_{worker_id}_{operation_count}_{uuid.uuid4().hex[:6]}"
                            email = f"{username}@mixed.com"
                            score = random.randint(0, 1000)
                            
                            await conn.execute("""
                                INSERT OR IGNORE INTO test_users (username, email, score)
                                VALUES (?, ?, ?)
                            """, (username, email, score))
                            
                            await conn.commit()
                            write_operations += 1
                        
                        worker_successful += 1
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                
                except Exception as e:
                    error_msg = f"Worker {worker_id} 混合操作失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                worker_total += 1
                operation_count += 1
            
            successful_operations += worker_successful
            total_operations += worker_total
        
        # 啟動所有工作者任務
        tasks = [worker_mixed_task(i) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計指標
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p50_response_time = statistics.median(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        # 獲取連線池統計
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = TestResult(
            test_name="mixed_workload_test",
            duration_seconds=duration,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=total_operations - successful_operations,
            operations_per_second=ops_per_second,
            average_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            error_rate_percentage=0,  # 會在 __post_init__ 中計算
            concurrent_workers=num_workers,
            max_connections_used=max_connections_used,
            errors=errors[:10],
            timestamp=datetime.now()
        )
        
        self.results.add_result(result)
        
        logger.info(
            f"混合工作負載測試完成：{successful_operations}/{total_operations} 成功，"
            f"讀取操作 {read_operations}，寫入操作 {write_operations}，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"錯誤率 {result.error_rate_percentage:.2f}%"
        )
        
        return result
    
    async def run_stress_test(
        self,
        max_workers: int = 30,
        ramp_up_duration: float = 10.0,
        test_duration: float = 60.0
    ) -> TestResult:
        """
        執行壓力測試，逐步增加工作者數量
        
        參數：
            max_workers: 最大工作者數量
            ramp_up_duration: 漸增時間（秒）
            test_duration: 總測試時間（秒）
        """
        logger.info(
            f"開始壓力測試：最大 {max_workers} 工作者，"
            f"漸增時間 {ramp_up_duration}s，總時長 {test_duration}s"
        )
        
        # 先插入基礎資料
        await self._populate_test_data(1000)
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        total_operations = 0
        active_workers = []
        
        async def worker_stress_task(worker_id: int, start_delay: float):
            """壓力測試工作者任務"""
            nonlocal successful_operations, total_operations, response_times, errors
            
            # 等待指定時間後開始工作
            await asyncio.sleep(start_delay)
            
            worker_successful = 0
            worker_total = 0
            
            while (time.time() - start_time) < test_duration:
                operation_start = time.time()
                
                try:
                    async with self.pool_manager.connection() as conn:
                        # 執行複雜查詢
                        import random
                        if random.choice([True, False]):
                            # 複雜讀取
                            result = conn.fetchall("""
                                SELECT u.username, u.score, 
                                       COUNT(a.id) as activity_count,
                                       AVG(a.points) as avg_points
                                FROM test_users u 
                                LEFT JOIN test_activities a ON u.id = a.user_id
                                WHERE u.score > ?
                                GROUP BY u.id
                                ORDER BY u.score DESC
                                LIMIT 10
                            """, (random.randint(0, 500),))
                        else:
                            # 批量寫入
                            username = f"stress_{worker_id}_{uuid.uuid4().hex[:8]}"
                            email = f"{username}@stress.com"
                            score = random.randint(0, 1000)
                            
                            await conn.execute("""
                                INSERT OR IGNORE INTO test_users (username, email, score)
                                VALUES (?, ?, ?)
                            """, (username, email, score))
                            
                            await conn.commit()
                        
                        worker_successful += 1
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                
                except Exception as e:
                    error_msg = f"Stress Worker {worker_id} 失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                worker_total += 1
                
                # 短暫延遲避免過度占用
                await asyncio.sleep(0.001)
            
            successful_operations += worker_successful
            total_operations += worker_total
        
        # 計算每個工作者的啟動延遲
        ramp_up_interval = ramp_up_duration / max_workers if max_workers > 0 else 0
        
        # 啟動所有工作者任務，漸進式增加
        tasks = []
        for i in range(max_workers):
            start_delay = i * ramp_up_interval
            tasks.append(worker_stress_task(i, start_delay))
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計指標
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p50_response_time = statistics.median(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        # 獲取連線池統計
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = TestResult(
            test_name="stress_test",
            duration_seconds=duration,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=total_operations - successful_operations,
            operations_per_second=ops_per_second,
            average_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            error_rate_percentage=0,  # 會在 __post_init__ 中計算
            concurrent_workers=max_workers,
            max_connections_used=max_connections_used,
            errors=errors[:10],
            timestamp=datetime.now()
        )
        
        self.results.add_result(result)
        
        logger.info(
            f"壓力測試完成：{successful_operations}/{total_operations} 成功，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"P95響應時間 {p95_response_time:.2f} ms，"
            f"錯誤率 {result.error_rate_percentage:.2f}%"
        )
        
        return result
    
    async def _populate_test_data(self, num_users: int):
        """填充測試資料"""
        logger.info(f"填充測試資料：{num_users} 個用戶")
        
        async with self.pool_manager.connection() as conn:
            # 檢查是否已有資料
            async with conn.execute("SELECT COUNT(*) as count FROM test_users") as cursor:
                existing = await cursor.fetchone()
                if existing and existing['count'] >= num_users:
                    logger.info("測試資料已存在，跳過填充")
                    return
            
            # 批量插入用戶
            users_data = []
            for i in range(num_users):
                username = f"test_user_{i:06d}"
                email = f"{username}@test.com"
                score = i % 1000
                users_data.append((username, email, score))
            
            await conn.executemany("""
                INSERT OR IGNORE INTO test_users (username, email, score) 
                VALUES (?, ?, ?)
            """, users_data)
            
            # 批量插入活動
            activities_data = []
            for i in range(num_users * 2):  # 每個用戶2個活動
                user_id = (i // 2) + 1
                activity_type = ["login", "post", "comment", "like"][i % 4]
                points = (i % 50) + 1
                activities_data.append((user_id, activity_type, points))
            
            await conn.executemany("""
                INSERT OR IGNORE INTO test_activities (user_id, activity_type, points)
                VALUES (?, ?, ?)
            """, activities_data)
            
            await conn.commit()
        
        logger.info("測試資料填充完成")
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """生成效能報告"""
        if not self.results.results:
            return {"error": "無測試結果可生成報告"}
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "test_database": self.db_path,
            "summary": self.results.summary_stats,
            "test_results": []
        }
        
        for result in self.results.results:
            report["test_results"].append({
                "test_name": result.test_name,
                "timestamp": result.timestamp.isoformat(),
                "duration_seconds": result.duration_seconds,
                "concurrent_workers": result.concurrent_workers,
                "total_operations": result.total_operations,
                "successful_operations": result.successful_operations,
                "failed_operations": result.failed_operations,
                "operations_per_second": result.operations_per_second,
                "error_rate_percentage": result.error_rate_percentage,
                "response_times": {
                    "average_ms": result.average_response_time_ms,
                    "p50_ms": result.p50_response_time_ms,
                    "p95_ms": result.p95_response_time_ms,
                    "p99_ms": result.p99_response_time_ms
                },
                "max_connections_used": result.max_connections_used,
                "sample_errors": result.errors
            })
        
        # 添加效能評估
        report["performance_assessment"] = self._assess_performance()
        
        return report
    
    def _assess_performance(self) -> Dict[str, Any]:
        """評估效能表現"""
        if not self.results.results:
            return {}
        
        # 設定效能基準（基於T2任務要求）
        performance_thresholds = {
            "max_acceptable_error_rate": 1.0,  # 1%
            "min_required_throughput": 100,     # 100 ops/s
            "max_acceptable_p95_response": 50,  # 50ms
            "max_acceptable_avg_response": 25   # 25ms
        }
        
        assessment = {
            "thresholds": performance_thresholds,
            "results": {}
        }
        
        for result in self.results.results:
            test_assessment = {
                "pass": True,
                "issues": []
            }
            
            # 檢查錯誤率
            if result.error_rate_percentage > performance_thresholds["max_acceptable_error_rate"]:
                test_assessment["pass"] = False
                test_assessment["issues"].append(
                    f"錯誤率過高: {result.error_rate_percentage:.2f}% > {performance_thresholds['max_acceptable_error_rate']}%"
                )
            
            # 檢查吞吐量
            if result.operations_per_second < performance_thresholds["min_required_throughput"]:
                test_assessment["pass"] = False
                test_assessment["issues"].append(
                    f"吞吐量不足: {result.operations_per_second:.2f} < {performance_thresholds['min_required_throughput']} ops/s"
                )
            
            # 檢查響應時間
            if result.p95_response_time_ms > performance_thresholds["max_acceptable_p95_response"]:
                test_assessment["pass"] = False
                test_assessment["issues"].append(
                    f"P95響應時間過長: {result.p95_response_time_ms:.2f}ms > {performance_thresholds['max_acceptable_p95_response']}ms"
                )
            
            if result.average_response_time_ms > performance_thresholds["max_acceptable_avg_response"]:
                test_assessment["pass"] = False
                test_assessment["issues"].append(
                    f"平均響應時間過長: {result.average_response_time_ms:.2f}ms > {performance_thresholds['max_acceptable_avg_response']}ms"
                )
            
            assessment["results"][result.test_name] = test_assessment
        
        # 整體評估
        overall_pass = all(result["pass"] for result in assessment["results"].values())
        assessment["overall_assessment"] = {
            "pass": overall_pass,
            "grade": "PASS" if overall_pass else "FAIL"
        }
        
        return assessment
    
    async def cleanup(self):
        """清理測試環境"""
        if self.pool_manager:
            await self.pool_manager.stop()
        
        # 清理臨時資料庫檔案
        if hasattr(self, 'temp_db'):
            try:
                os.unlink(self.db_path)
                logger.info("臨時測試資料庫已清理")
            except OSError:
                logger.warning(f"無法刪除臨時資料庫檔案：{self.db_path}")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


class PerformanceBenchmark:
    """效能基準測試和報告生成器"""
    
    def __init__(self, results_dir: str):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[TestResult] = []
    
    def save_result(self, result: TestResult):
        """儲存測試結果"""
        self.results.append(result)
        
        # 儲存個別結果檔案
        result_file = self.results_dir / f"{result.test_name}_{int(result.timestamp.timestamp())}.json"
        result_data = {
            'test_name': result.test_name,
            'timestamp': result.timestamp.isoformat(),
            'duration_seconds': result.duration_seconds,
            'concurrent_workers': result.concurrent_workers,
            'total_operations': result.total_operations,
            'successful_operations': result.successful_operations,
            'failed_operations': result.failed_operations,
            'operations_per_second': result.operations_per_second,
            'error_rate_percentage': result.error_rate_percentage,
            'response_times': {
                'average_ms': result.average_response_time_ms,
                'p50_ms': result.p50_response_time_ms,
                'p95_ms': result.p95_response_time_ms,
                'p99_ms': result.p99_response_time_ms
            },
            'max_connections_used': result.max_connections_used,
            'sample_errors': result.errors
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(result_data, f, indent=2, ensure_ascii=False)
    
    def generate_report(self, results: Optional[List[TestResult]] = None) -> Dict[str, Any]:
        """生成綜合效能報告"""
        if results:
            test_results = results
        else:
            test_results = self.results
        
        if not test_results:
            return {"error": "無測試結果可生成報告"}
        
        # 統計總覽
        total_operations = sum(r.total_operations for r in test_results)
        total_successful = sum(r.successful_operations for r in test_results)
        total_failed = sum(r.failed_operations for r in test_results)
        
        # 效能指標彙總
        throughputs = [r.operations_per_second for r in test_results]
        response_times = [r.average_response_time_ms for r in test_results]
        error_rates = [r.error_rate_percentage for r in test_results]
        
        # T2標準驗證
        t2_criteria = {
            'max_error_rate': 1.0,  # 1%
            'max_p95_response_time': 50.0,  # 50ms
            'min_success_rate': 99.0  # 99%
        }
        
        tests_meeting_criteria = 0
        for result in test_results:
            meets_criteria = (
                result.error_rate_percentage <= t2_criteria['max_error_rate'] and
                result.p95_response_time_ms <= t2_criteria['max_p95_response_time'] and
                (result.successful_operations / result.total_operations * 100) >= t2_criteria['min_success_rate']
            )
            if meets_criteria:
                tests_meeting_criteria += 1
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "test_summary": {
                "total_tests": len(test_results),
                "tests_meeting_criteria": tests_meeting_criteria,
                "total_operations": total_operations,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "overall_success_rate": (total_successful / total_operations) if total_operations > 0 else 0,
                "overall_error_rate": (total_failed / total_operations) if total_operations > 0 else 0
            },
            "performance_metrics": {
                "average_throughput_ops_per_sec": statistics.mean(throughputs),
                "max_throughput_ops_per_sec": max(throughputs),
                "min_throughput_ops_per_sec": min(throughputs),
                "average_response_time_ms": statistics.mean(response_times),
                "average_error_rate": statistics.mean(error_rates)
            },
            "t2_compliance": {
                "criteria": t2_criteria,
                "tests_passing": tests_meeting_criteria,
                "tests_total": len(test_results),
                "compliance_rate": (tests_meeting_criteria / len(test_results)) * 100
            },
            "detailed_results": []
        }
        
        # 添加詳細結果
        for result in test_results:
            detailed = {
                "test_name": result.test_name,
                "timestamp": result.timestamp.isoformat(),
                "workers": result.concurrent_workers,
                "operations": result.total_operations,
                "success_rate": (result.successful_operations / result.total_operations * 100) if result.total_operations > 0 else 0,
                "error_rate": result.error_rate_percentage,
                "throughput": result.operations_per_second,
                "response_times": {
                    "avg": result.average_response_time_ms,
                    "p95": result.p95_response_time_ms,
                    "p99": result.p99_response_time_ms
                },
                "t2_compliance": {
                    "error_rate_ok": result.error_rate_percentage <= t2_criteria['max_error_rate'],
                    "response_time_ok": result.p95_response_time_ms <= t2_criteria['max_p95_response_time'],
                    "success_rate_ok": (result.successful_operations / result.total_operations * 100) >= t2_criteria['min_success_rate']
                }
            }
            report["detailed_results"].append(detailed)
        
        # 儲存綜合報告
        report_file = self.results_dir / f"performance_benchmark_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"效能報告已儲存: {report_file}")
        return report


# 輔助函數和測試套件包裝器
async def run_full_concurrency_test_suite() -> List[TestResult]:
    """執行完整的併發測試套件"""
    async with ConnectionPoolTestSuite() as suite:
        await suite.setup_test_environment()
        
        results = []
        
        # 10+ 工作者測試
        result_10 = await suite.run_concurrent_read_test(num_workers=10, operations_per_worker=100)
        results.append(result_10)
        
        # 15 工作者混合測試
        result_mixed = await suite.run_mixed_workload_test(num_workers=15, test_duration=30.0)
        results.append(result_mixed)
        
        # 20+ 工作者極限測試
        result_stress = await suite.run_stress_test(max_workers=20, test_duration=60.0)
        results.append(result_stress)
        
        return results


# ConcurrencyTestResult 已經在上面定義了，不需要別名