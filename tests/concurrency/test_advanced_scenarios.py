"""
T2 - 高併發連線競爭修復
進階併發測試場景

提供進階併發測試場景，包含：
- 複雜讀寫混合模式
- 事務併發壓力測試  
- 連線池耗盡和恢復測試
- 突發負載模式測試
"""

import asyncio
import logging
import os
import sys
import tempfile
import time
import uuid
import statistics
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

# 添加系統路徑支持
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from services.connection_pool.connection_pool_manager import ConnectionPoolManager
from services.connection_pool.models import PoolConfiguration
from test_connection_pool import TestResult, ConcurrencyTestResult

logger = logging.getLogger('tests.concurrency.advanced_scenarios')


@dataclass
class AdvancedTestResult:
    """進階測試結果資料結構"""
    test_name: str
    scenario_type: str
    duration_seconds: float
    total_operations: int
    read_operations: int
    write_operations: int
    transaction_operations: int
    successful_operations: int
    failed_operations: int
    deadlock_count: int
    timeout_count: int
    connection_errors: int
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    operations_per_second: float
    concurrent_workers: int
    max_connections_used: int
    memory_usage_mb: float
    peak_memory_mb: float
    errors: List[str]
    timestamp: datetime
    
    @property
    def success_rate(self) -> float:
        """計算成功率"""
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations
    
    @property
    def error_rate(self) -> float:
        """計算錯誤率"""
        if self.total_operations == 0:
            return 0.0
        return self.failed_operations / self.total_operations


class AdvancedConcurrencyTestSuite:
    """進階併發測試套件"""
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化進階測試套件"""
        if db_path is None:
            self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            self.db_path = self.temp_db.name
            self.temp_db.close()
        else:
            self.db_path = db_path
        
        self.pool_manager: Optional[ConnectionPoolManager] = None
        self.results: List[AdvancedTestResult] = []
        
        logger.info(f"進階測試資料庫路徑：{self.db_path}")
    
    async def setup(self):
        """設置測試環境"""
        config = PoolConfiguration(
            min_connections=3,
            max_connections=25,
            connection_timeout=30.0,
            acquire_timeout=15.0,
            enable_monitoring=True
        )
        
        self.pool_manager = ConnectionPoolManager(
            db_path=self.db_path,
            config=config
        )
        
        await self.pool_manager.start()
        await self._create_advanced_test_tables()
        logger.info("進階測試環境設置完成")
    
    async def _create_advanced_test_tables(self):
        """建立進階測試表格"""
        async with self.pool_manager.connection() as conn:
            # 用戶表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    balance DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 交易表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # 產品表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    stock INTEGER DEFAULT 0,
                    category TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 訂單表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    total_amount DECIMAL(10,2) NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
            
            # 建立索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            
            await conn.commit()
        
        logger.info("進階測試表格建立完成")
    
    async def test_mixed_read_write_operations(
        self,
        num_workers: int = 20,
        test_duration: float = 60.0,
        read_write_ratio: float = 0.7  # 70% 讀取，30% 寫入
    ) -> AdvancedTestResult:
        """測試混合讀寫操作"""
        logger.info(f"開始混合讀寫測試：{num_workers} 工作者，持續 {test_duration} 秒")
        
        # 先填充基礎資料
        await self._populate_advanced_test_data(1000)
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        failed_operations = 0
        read_operations = 0
        write_operations = 0
        
        async def worker_mixed_task(worker_id: int):
            """混合讀寫工作者"""
            nonlocal successful_operations, failed_operations, read_operations, write_operations
            nonlocal response_times, errors
            
            operation_count = 0
            while (time.time() - start_time) < test_duration:
                operation_start = time.time()
                
                try:
                    import random
                    is_read = random.random() < read_write_ratio
                    
                    async with self.pool_manager.connection() as conn:
                        if is_read:
                            # 複雜讀取操作
                            user_id = random.randint(1, 1000)
                            async with conn.execute("""
                                SELECT u.username, u.balance, 
                                       COUNT(t.id) as transaction_count,
                                       COUNT(o.id) as order_count,
                                       SUM(t.amount) as total_transactions
                                FROM users u 
                                LEFT JOIN transactions t ON u.id = t.user_id
                                LEFT JOIN orders o ON u.id = o.user_id
                                WHERE u.id = ?
                                GROUP BY u.id
                            """, (user_id,)) as cursor:
                                result = await cursor.fetchone()
                            
                            read_operations += 1
                        else:
                            # 寫入操作
                            operation_type = random.choice(['user_update', 'transaction_insert', 'order_create'])
                            
                            if operation_type == 'user_update':
                                user_id = random.randint(1, 1000)
                                new_balance = random.uniform(0, 1000)
                                await conn.execute("""
                                    UPDATE users SET balance = ?, updated_at = CURRENT_TIMESTAMP 
                                    WHERE id = ?
                                """, (new_balance, user_id))
                                
                            elif operation_type == 'transaction_insert':
                                user_id = random.randint(1, 1000)
                                amount = random.uniform(1, 100)
                                await conn.execute("""
                                    INSERT INTO transactions (user_id, transaction_type, amount, description)
                                    VALUES (?, ?, ?, ?)
                                """, (user_id, 'credit', amount, f'Transaction by worker {worker_id}'))
                                
                            elif operation_type == 'order_create':
                                user_id = random.randint(1, 1000)
                                product_id = random.randint(1, 100)
                                quantity = random.randint(1, 5)
                                price = random.uniform(10, 100)
                                total = quantity * price
                                
                                await conn.execute("""
                                    INSERT INTO orders (user_id, product_id, quantity, total_amount)
                                    VALUES (?, ?, ?, ?)
                                """, (user_id, product_id, quantity, total))
                            
                            await conn.commit()
                            write_operations += 1
                        
                        successful_operations += 1
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                
                except Exception as e:
                    failed_operations += 1
                    error_msg = f"Worker {worker_id} 操作失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                operation_count += 1
                
                # 短暫延遲避免過度占用
                await asyncio.sleep(0.001)
        
        # 啟動工作者
        tasks = [worker_mixed_task(i) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計
        total_operations = successful_operations + failed_operations
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        # 獲取連線池統計
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = AdvancedTestResult(
            test_name="mixed_read_write_operations",
            scenario_type="mixed_workload",
            duration_seconds=duration,
            total_operations=total_operations,
            read_operations=read_operations,
            write_operations=write_operations,
            transaction_operations=0,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            deadlock_count=0,
            timeout_count=0,
            connection_errors=0,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            operations_per_second=ops_per_second,
            concurrent_workers=num_workers,
            max_connections_used=max_connections_used,
            memory_usage_mb=0.0,  # TODO: 實際記憶體監控
            peak_memory_mb=0.0,
            errors=errors[:10],
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        
        logger.info(
            f"混合讀寫測試完成：{successful_operations}/{total_operations} 成功，"
            f"讀取 {read_operations}，寫入 {write_operations}，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"錯誤率 {result.error_rate:.2%}"
        )
        
        return result
    
    async def test_transaction_stress(
        self,
        num_workers: int = 15,
        test_duration: float = 45.0
    ) -> AdvancedTestResult:
        """測試事務併發壓力"""
        logger.info(f"開始事務併發測試：{num_workers} 工作者，持續 {test_duration} 秒")
        
        await self._populate_advanced_test_data(500)
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        failed_operations = 0
        transaction_operations = 0
        deadlock_count = 0
        timeout_count = 0
        
        async def worker_transaction_task(worker_id: int):
            """事務壓力工作者"""
            nonlocal successful_operations, failed_operations, transaction_operations
            nonlocal deadlock_count, timeout_count, response_times, errors
            
            while (time.time() - start_time) < test_duration:
                operation_start = time.time()
                
                try:
                    async with self.pool_manager.connection() as conn:
                        # 開始事務
                        await conn.execute("BEGIN IMMEDIATE")
                        
                        try:
                            import random
                            # 模擬複雜事務：轉帳操作
                            from_user_id = random.randint(1, 500)
                            to_user_id = random.randint(1, 500)
                            if from_user_id == to_user_id:
                                continue
                            
                            amount = random.uniform(1, 50)
                            
                            # 檢查餘額
                            async with conn.execute("SELECT balance FROM users WHERE id = ?", (from_user_id,)) as cursor:
                                from_balance_row = await cursor.fetchone()
                                if not from_balance_row or from_balance_row['balance'] < amount:
                                    await conn.execute("ROLLBACK")
                                    continue
                            
                            # 扣除發送方餘額
                            await conn.execute("""
                                UPDATE users SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ? AND balance >= ?
                            """, (amount, from_user_id, amount))
                            
                            # 增加接收方餘額
                            await conn.execute("""
                                UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (amount, to_user_id))
                            
                            # 記錄交易
                            await conn.execute("""
                                INSERT INTO transactions (user_id, transaction_type, amount, description)
                                VALUES (?, ?, ?, ?)
                            """, (from_user_id, 'debit', -amount, f'Transfer to user {to_user_id}'))
                            
                            await conn.execute("""
                                INSERT INTO transactions (user_id, transaction_type, amount, description)
                                VALUES (?, ?, ?, ?)
                            """, (to_user_id, 'credit', amount, f'Transfer from user {from_user_id}'))
                            
                            # 提交事務
                            await conn.commit()
                            transaction_operations += 1
                            successful_operations += 1
                            
                        except Exception as tx_error:
                            await conn.execute("ROLLBACK")
                            
                            error_str = str(tx_error).lower()
                            if 'deadlock' in error_str or 'locked' in error_str:
                                deadlock_count += 1
                            elif 'timeout' in error_str:
                                timeout_count += 1
                            
                            raise tx_error
                        
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                
                except Exception as e:
                    failed_operations += 1
                    error_msg = f"Transaction Worker {worker_id} 失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                # 短暫延遲
                await asyncio.sleep(0.005)
        
        # 啟動工作者
        tasks = [worker_transaction_task(i) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計
        total_operations = successful_operations + failed_operations
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = AdvancedTestResult(
            test_name="transaction_stress",
            scenario_type="transaction_concurrency",
            duration_seconds=duration,
            total_operations=total_operations,
            read_operations=0,
            write_operations=transaction_operations * 4,  # 每個事務包含多個寫入
            transaction_operations=transaction_operations,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            deadlock_count=deadlock_count,
            timeout_count=timeout_count,
            connection_errors=0,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            operations_per_second=ops_per_second,
            concurrent_workers=num_workers,
            max_connections_used=max_connections_used,
            memory_usage_mb=0.0,
            peak_memory_mb=0.0,
            errors=errors[:10],
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        
        logger.info(
            f"事務併發測試完成：{successful_operations}/{total_operations} 成功，"
            f"事務數 {transaction_operations}，死鎖 {deadlock_count}，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"錯誤率 {result.error_rate:.2%}"
        )
        
        return result
    
    async def test_connection_pool_exhaustion(
        self,
        max_workers: int = 30,
        test_duration: float = 30.0
    ) -> AdvancedTestResult:
        """測試連線池耗盡場景"""
        logger.info(f"開始連線池耗盡測試：{max_workers} 工作者，持續 {test_duration} 秒")
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        failed_operations = 0
        connection_errors = 0
        timeout_count = 0
        
        async def worker_exhaustion_task(worker_id: int):
            """連線池耗盡測試工作者"""
            nonlocal successful_operations, failed_operations, connection_errors
            nonlocal timeout_count, response_times, errors
            
            while (time.time() - start_time) < test_duration:
                operation_start = time.time()
                
                try:
                    # 故意持有連線較長時間來製造壓力
                    connection = await self.pool_manager.get_connection()
                    
                    try:
                        # 模擬較長時間的操作
                        await asyncio.sleep(0.1)  # 100ms 的模擬操作
                        
                        async with connection.execute("SELECT COUNT(*) as count FROM users") as cursor:
                            result = await cursor.fetchone()
                        
                        successful_operations += 1
                        operation_time = (time.time() - operation_start) * 1000
                        response_times.append(operation_time)
                        
                    finally:
                        await self.pool_manager.release_connection(connection)
                
                except TimeoutError:
                    timeout_count += 1
                    failed_operations += 1
                    errors.append(f"Worker {worker_id} 連線獲取超時")
                    
                except Exception as e:
                    failed_operations += 1
                    error_str = str(e).lower()
                    if 'connection' in error_str or 'pool' in error_str:
                        connection_errors += 1
                    
                    error_msg = f"Pool Worker {worker_id} 失敗：{str(e)}"
                    errors.append(error_msg)
                    logger.debug(error_msg)
                
                # 避免過度競爭
                await asyncio.sleep(0.01)
        
        # 啟動工作者
        tasks = [worker_exhaustion_task(i) for i in range(max_workers)]
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計
        total_operations = successful_operations + failed_operations
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = AdvancedTestResult(
            test_name="connection_pool_exhaustion",
            scenario_type="resource_stress",
            duration_seconds=duration,
            total_operations=total_operations,
            read_operations=successful_operations,
            write_operations=0,
            transaction_operations=0,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            deadlock_count=0,
            timeout_count=timeout_count,
            connection_errors=connection_errors,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            operations_per_second=ops_per_second,
            concurrent_workers=max_workers,
            max_connections_used=max_connections_used,
            memory_usage_mb=0.0,
            peak_memory_mb=0.0,
            errors=errors[:10],
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        
        logger.info(
            f"連線池耗盡測試完成：{successful_operations}/{total_operations} 成功，"
            f"連線錯誤 {connection_errors}，超時 {timeout_count}，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"錯誤率 {result.error_rate:.2%}"
        )
        
        return result
    
    async def test_load_burst_patterns(
        self,
        test_duration: float = 45.0,
        burst_intervals: int = 5
    ) -> AdvancedTestResult:
        """測試突發負載模式"""
        logger.info(f"開始突發負載測試：持續 {test_duration} 秒，{burst_intervals} 個突發週期")
        
        await self._populate_advanced_test_data(200)
        
        start_time = time.time()
        response_times = []
        errors = []
        successful_operations = 0
        failed_operations = 0
        
        burst_duration = test_duration / burst_intervals
        
        async def burst_phase(burst_id: int, workers: int):
            """單個突發階段"""
            nonlocal successful_operations, failed_operations, response_times, errors
            
            logger.info(f"突發階段 {burst_id + 1}: {workers} 工作者")
            
            async def burst_worker(worker_id: int):
                """突發工作者"""
                burst_start = time.time()
                burst_ops = 0
                
                while (time.time() - burst_start) < burst_duration:
                    operation_start = time.time()
                    
                    try:
                        async with self.pool_manager.connection() as conn:
                            import random
                            
                            # 隨機選擇操作類型
                            op_type = random.choice(['read_heavy', 'write_heavy', 'mixed'])
                            
                            if op_type == 'read_heavy':
                                # 重讀取操作
                                async with conn.execute("""
                                    SELECT u.*, 
                                           COUNT(t.id) as tx_count,
                                           AVG(t.amount) as avg_amount
                                    FROM users u
                                    LEFT JOIN transactions t ON u.id = t.user_id
                                    WHERE u.status = 'active'
                                    GROUP BY u.id
                                    ORDER BY u.balance DESC
                                    LIMIT 20
                                """) as cursor:
                                    results = await cursor.fetchall()
                                    
                            elif op_type == 'write_heavy':
                                # 重寫入操作
                                user_id = random.randint(1, 200)
                                for _ in range(3):  # 批量寫入
                                    await conn.execute("""
                                        INSERT INTO transactions (user_id, transaction_type, amount)
                                        VALUES (?, ?, ?)
                                    """, (user_id, 'burst_test', random.uniform(1, 20)))
                                await conn.commit()
                                
                            else:
                                # 混合操作
                                async with conn.execute("SELECT COUNT(*) FROM users") as cursor:
                                    count = await cursor.fetchone()
                                
                                await conn.execute("""
                                    INSERT INTO transactions (user_id, transaction_type, amount)
                                    VALUES (?, ?, ?)
                                """, (random.randint(1, 200), 'mixed_burst', 5.0))
                                await conn.commit()
                            
                            successful_operations += 1
                            burst_ops += 1
                            operation_time = (time.time() - operation_start) * 1000
                            response_times.append(operation_time)
                    
                    except Exception as e:
                        failed_operations += 1
                        error_msg = f"Burst {burst_id} Worker {worker_id} 失敗：{str(e)}"
                        errors.append(error_msg)
                        logger.debug(error_msg)
                    
                    # 短暫延遲
                    await asyncio.sleep(0.002)
                
                logger.debug(f"突發工作者 {worker_id} 完成 {burst_ops} 操作")
            
            # 階梯式增加工作者數量
            worker_counts = [5, 10, 15, 20, 25]
            current_workers = worker_counts[burst_id % len(worker_counts)]
            
            # 啟動突發工作者
            tasks = [burst_worker(i) for i in range(current_workers)]
            await asyncio.gather(*tasks)
            
            # 突發間隔
            if burst_id < burst_intervals - 1:
                await asyncio.sleep(1.0)  # 突發間的冷卻時間
        
        # 執行突發週期
        for burst_id in range(burst_intervals):
            await burst_phase(burst_id, (burst_id + 1) * 5)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 計算統計
        total_operations = successful_operations + failed_operations
        ops_per_second = total_operations / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else avg_response_time
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else avg_response_time
        
        pool_stats = self.pool_manager.get_pool_stats()
        max_connections_used = pool_stats['active_connections'] + pool_stats['idle_connections']
        
        result = AdvancedTestResult(
            test_name="load_burst_patterns",
            scenario_type="burst_load",
            duration_seconds=duration,
            total_operations=total_operations,
            read_operations=total_operations // 3,  # 估算
            write_operations=total_operations - (total_operations // 3),
            transaction_operations=0,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            deadlock_count=0,
            timeout_count=0,
            connection_errors=0,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            operations_per_second=ops_per_second,
            concurrent_workers=25,  # 最大工作者數
            max_connections_used=max_connections_used,
            memory_usage_mb=0.0,
            peak_memory_mb=0.0,
            errors=errors[:15],
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        
        logger.info(
            f"突發負載測試完成：{successful_operations}/{total_operations} 成功，"
            f"{burst_intervals} 個突發週期，"
            f"吞吐量 {ops_per_second:.2f} ops/s，"
            f"錯誤率 {result.error_rate:.2%}"
        )
        
        return result
    
    async def _populate_advanced_test_data(self, num_users: int):
        """填充進階測試資料"""
        logger.info(f"填充進階測試資料：{num_users} 個用戶")
        
        async with self.pool_manager.connection() as conn:
            # 檢查是否已有資料
            async with conn.execute("SELECT COUNT(*) as count FROM users") as cursor:
                existing = await cursor.fetchone()
                if existing and existing['count'] >= num_users:
                    logger.info("進階測試資料已存在，跳過填充")
                    return
            
            # 批量插入用戶
            users_data = []
            for i in range(num_users):
                username = f"adv_user_{i:06d}"
                email = f"{username}@advanced.test"
                balance = 100.0 + (i % 500)
                status = 'active' if i % 10 != 0 else 'inactive'
                users_data.append((username, email, balance, status))
            
            # 使用 executemany 批量插入
            await conn.executemany("""
                INSERT OR IGNORE INTO users (username, email, balance, status) 
                VALUES (?, ?, ?, ?)
            """, users_data)
            
            # 插入產品資料
            products_data = []
            categories = ['electronics', 'books', 'clothing', 'home', 'sports']
            for i in range(100):
                name = f"Product_{i:03d}"
                price = 10.0 + (i % 200)
                stock = 100 + (i % 50)
                category = categories[i % len(categories)]
                products_data.append((name, price, stock, category))
            
            await conn.executemany("""
                INSERT OR IGNORE INTO products (name, price, stock, category)
                VALUES (?, ?, ?, ?)
            """, products_data)
            
            await conn.commit()
        
        logger.info("進階測試資料填充完成")
    
    async def cleanup(self):
        """清理測試環境"""
        if self.pool_manager:
            await self.pool_manager.stop()
        
        # 清理臨時資料庫檔案
        if hasattr(self, 'temp_db'):
            try:
                os.unlink(self.db_path)
                logger.info("進階測試臨時資料庫已清理")
            except OSError:
                logger.warning(f"無法刪除進階測試臨時資料庫檔案：{self.db_path}")


class AdvancedPerformanceAnalyzer:
    """進階效能分析器"""
    
    def __init__(self):
        self.analysis_results = {}
    
    def analyze_advanced_results(self, results: List[AdvancedTestResult]) -> Dict[str, Any]:
        """分析進階測試結果"""
        if not results:
            return {"error": "無測試結果可分析"}
        
        # 按測試類型分組
        by_scenario = {}
        for result in results:
            if result.scenario_type not in by_scenario:
                by_scenario[result.scenario_type] = []
            by_scenario[result.scenario_type].append(result)
        
        # 總體效能分析
        total_operations = sum(r.total_operations for r in results)
        total_successful = sum(r.successful_operations for r in results)
        total_failed = sum(r.failed_operations for r in results)
        
        success_rates = [r.success_rate for r in results]
        response_times = [r.avg_response_time_ms for r in results]
        p95_times = [r.p95_response_time_ms for r in results]
        
        # T2 標準驗證
        t2_passing = 0
        for result in results:
            if (result.error_rate <= 0.01 and 
                result.p95_response_time_ms <= 50.0 and
                result.success_rate >= 0.99):
                t2_passing += 1
        
        analysis = {
            "analysis_timestamp": datetime.now().isoformat(),
            "overall_performance": {
                "scenarios_total": len(results),
                "scenarios_passing": t2_passing,
                "t2_compliance_rate": (t2_passing / len(results)) * 100,
                "total_operations": total_operations,
                "overall_success_rate": (total_successful / total_operations) * 100 if total_operations > 0 else 0,
                "overall_error_rate": (total_failed / total_operations) * 100 if total_operations > 0 else 0,
                "average_success_rate": statistics.mean(success_rates) * 100,
                "average_response_time_ms": statistics.mean(response_times),
                "average_p95_response_time_ms": statistics.mean(p95_times)
            },
            "scenario_analysis": {},
            "performance_insights": [],
            "recommendations": []
        }
        
        # 按場景分析
        for scenario_type, scenario_results in by_scenario.items():
            scenario_analysis = self._analyze_scenario(scenario_type, scenario_results)
            analysis["scenario_analysis"][scenario_type] = scenario_analysis
        
        # 生成洞察和建議
        analysis["performance_insights"] = self._generate_insights(results, analysis)
        analysis["recommendations"] = self._generate_recommendations(results, analysis)
        
        return analysis
    
    def _analyze_scenario(self, scenario_type: str, results: List[AdvancedTestResult]) -> Dict[str, Any]:
        """分析特定場景"""
        if not results:
            return {}
        
        success_rates = [r.success_rate for r in results]
        error_rates = [r.error_rate for r in results]
        response_times = [r.avg_response_time_ms for r in results]
        throughputs = [r.operations_per_second for r in results]
        
        return {
            "test_count": len(results),
            "average_success_rate": statistics.mean(success_rates) * 100,
            "average_error_rate": statistics.mean(error_rates) * 100,
            "average_response_time_ms": statistics.mean(response_times),
            "average_throughput": statistics.mean(throughputs),
            "max_throughput": max(throughputs),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "special_metrics": self._get_special_metrics(scenario_type, results)
        }
    
    def _get_special_metrics(self, scenario_type: str, results: List[AdvancedTestResult]) -> Dict[str, Any]:
        """獲取場景特定指標"""
        if scenario_type == "transaction_concurrency":
            return {
                "total_transactions": sum(r.transaction_operations for r in results),
                "total_deadlocks": sum(r.deadlock_count for r in results),
                "total_timeouts": sum(r.timeout_count for r in results),
                "deadlock_rate": sum(r.deadlock_count for r in results) / sum(r.total_operations for r in results) * 100
            }
        elif scenario_type == "resource_stress":
            return {
                "total_connection_errors": sum(r.connection_errors for r in results),
                "total_timeouts": sum(r.timeout_count for r in results),
                "max_connections_used": max(r.max_connections_used for r in results)
            }
        elif scenario_type == "mixed_workload":
            return {
                "total_read_ops": sum(r.read_operations for r in results),
                "total_write_ops": sum(r.write_operations for r in results),
                "read_write_ratio": sum(r.read_operations for r in results) / sum(r.write_operations for r in results) if sum(r.write_operations for r in results) > 0 else 0
            }
        else:
            return {}
    
    def _generate_insights(self, results: List[AdvancedTestResult], analysis: Dict[str, Any]) -> List[str]:
        """生成效能洞察"""
        insights = []
        
        overall = analysis["overall_performance"]
        
        if overall["t2_compliance_rate"] == 100:
            insights.append("🎉 所有進階測試都符合 T2 效能標準")
        elif overall["t2_compliance_rate"] >= 80:
            insights.append(f"✅ {overall['t2_compliance_rate']:.1f}% 的測試符合 T2 標準，整體表現良好")
        else:
            insights.append(f"⚠️ 僅 {overall['t2_compliance_rate']:.1f}% 的測試符合 T2 標準，需要優化")
        
        if overall["average_response_time_ms"] > 30:
            insights.append(f"📈 平均響應時間 {overall['average_response_time_ms']:.1f}ms 偏高，建議優化")
        
        if overall["overall_error_rate"] > 2:
            insights.append(f"🚨 錯誤率 {overall['overall_error_rate']:.2f}% 超過建議值，需要檢查穩定性")
        
        # 場景特定洞察
        for scenario_type, scenario_data in analysis["scenario_analysis"].items():
            if scenario_type == "transaction_concurrency":
                special = scenario_data.get("special_metrics", {})
                if special.get("deadlock_rate", 0) > 1:
                    insights.append(f"⚡ 事務並發死鎖率 {special['deadlock_rate']:.2f}% 較高，建議優化事務邏輯")
            
            elif scenario_type == "resource_stress":
                if scenario_data["average_error_rate"] > 5:
                    insights.append("💥 資源壓力測試錯誤率較高，連線池配置可能需要調整")
        
        return insights
    
    def _generate_recommendations(self, results: List[AdvancedTestResult], analysis: Dict[str, Any]) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        overall = analysis["overall_performance"]
        
        # 基於整體效能的建議
        if overall["average_p95_response_time_ms"] > 50:
            recommendations.append("調整連線池大小，增加 max_connections 參數")
            recommendations.append("優化資料庫查詢，添加必要的索引")
        
        if overall["overall_error_rate"] > 1:
            recommendations.append("增加重試機制和錯誤處理邏輯")
            recommendations.append("檢查連線超時設定，適當增加 acquire_timeout")
        
        # 基於場景的建議
        for scenario_type, scenario_data in analysis["scenario_analysis"].items():
            if scenario_type == "transaction_concurrency":
                special = scenario_data.get("special_metrics", {})
                if special.get("deadlock_rate", 0) > 0.5:
                    recommendations.append("優化事務邏輯，減少長時間持有鎖")
                    recommendations.append("考慮使用樂觀鎖替代悲觀鎖")
            
            elif scenario_type == "resource_stress" and scenario_data["average_error_rate"] > 3:
                recommendations.append("增加連線池監控和動態調整機制")
                recommendations.append("實施連線池預熱策略")
            
            elif scenario_type == "burst_load":
                if scenario_data["max_response_time"] > 100:
                    recommendations.append("實施請求排隊和限流機制")
                    recommendations.append("考慮使用連線池彈性擴縮容")
        
        # 通用建議
        if len(recommendations) == 0:
            recommendations.append("系統效能表現良好，可考慮進一步調整以達到極致效能")
        
        return recommendations


# 輔助函數
async def run_advanced_concurrency_tests() -> List[AdvancedTestResult]:
    """執行進階併發測試套件"""
    suite = AdvancedConcurrencyTestSuite()
    
    try:
        await suite.setup()
        
        results = []
        
        # 混合讀寫測試
        result1 = await suite.test_mixed_read_write_operations(num_workers=20, test_duration=60.0)
        results.append(result1)
        
        # 事務併發測試
        result2 = await suite.test_transaction_stress(num_workers=15, test_duration=45.0)
        results.append(result2)
        
        # 連線池耗盡測試
        result3 = await suite.test_connection_pool_exhaustion(max_workers=30, test_duration=30.0)
        results.append(result3)
        
        # 突發負載測試
        result4 = await suite.test_load_burst_patterns(test_duration=45.0, burst_intervals=5)
        results.append(result4)
        
        return results
        
    finally:
        await suite.cleanup()