"""
SQLite併發查詢優化器
T2 - 高併發連線競爭修復實施

針對SQLite在高併發環境下的限制，提供專業的查詢優化、鎖定管理和併發控制
實現查詢路由、讀寫分離優化、查詢重寫和效能調校功能
"""

import sqlite3
import asyncio
import logging
import threading
import time
import hashlib
import queue
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..db.sqlite import OptimizedConnection
from ..db.retry import retry_on_database_locked, CommonRetryStrategies

logger = logging.getLogger('src.services.sqlite_optimizer')


class QueryType(Enum):
    """查詢類型枚舉"""
    READ = "read"         # 純讀取查詢
    WRITE = "write"       # 寫入查詢
    MIXED = "mixed"       # 混合查詢
    DDL = "ddl"           # 資料定義語言
    TRANSACTION = "transaction"  # 事務操作


class QueryPriority(Enum):
    """查詢優先級枚舉"""
    LOW = 1
    NORMAL = 2  
    HIGH = 3
    CRITICAL = 4


@dataclass
class QueryMetrics:
    """查詢效能指標"""
    query_hash: str
    query_type: QueryType
    execution_count: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    last_executed: Optional[datetime] = None
    error_count: int = 0
    lock_wait_count: int = 0
    
    def update_metrics(self, duration_ms: float, had_lock_wait: bool = False):
        """更新效能指標"""
        self.execution_count += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.execution_count
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.last_executed = datetime.utcnow()
        
        if had_lock_wait:
            self.lock_wait_count += 1
    
    def increment_error(self):
        """增加錯誤計數"""
        self.error_count += 1


@dataclass
class QueryRequest:
    """查詢請求數據結構"""
    sql: str
    params: Tuple = ()
    query_type: QueryType = QueryType.READ
    priority: QueryPriority = QueryPriority.NORMAL
    timeout: float = 30.0
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def age_seconds(self) -> float:
        """請求存活時間"""
        return (datetime.utcnow() - self.submitted_at).total_seconds()
    
    @property
    def query_hash(self) -> str:
        """查詢雜湊值"""
        return hashlib.md5(self.sql.encode()).hexdigest()[:16]


class SQLiteQueryOptimizer:
    """
    SQLite併發查詢優化器
    
    提供查詢路由、優先級管理、讀寫分離和併發控制優化
    專門解決SQLite在高併發環境下的效能瓶頸問題
    """
    
    def __init__(self, max_concurrent_reads: int = 10, max_concurrent_writes: int = 2):
        """
        初始化查詢優化器
        
        參數:
            max_concurrent_reads: 最大併發讀取數
            max_concurrent_writes: 最大併發寫入數  
        """
        self.max_concurrent_reads = max_concurrent_reads
        self.max_concurrent_writes = max_concurrent_writes
        
        # 讀寫分離控制
        self._read_semaphore = asyncio.Semaphore(max_concurrent_reads)
        self._write_semaphore = asyncio.Semaphore(max_concurrent_writes)
        self._write_lock = asyncio.Lock()  # 寫入互斥鎖
        
        # 查詢佇列和調度
        self._read_queue: asyncio.Queue = asyncio.Queue()
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._priority_queues: Dict[QueryPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in QueryPriority
        }
        
        # 效能監控
        self._query_metrics: Dict[str, QueryMetrics] = {}
        self._metrics_lock = threading.RLock()
        
        # 查詢快取
        self._query_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_lock = threading.RLock()
        
        # 工作執行緒池
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent_reads + max_concurrent_writes)
        
        # 調度器控制
        self._scheduler_running = False
        self._scheduler_tasks: List[asyncio.Task] = []
        
        logger.info(f"SQLite查詢優化器已初始化 - 讀取併發: {max_concurrent_reads}, 寫入併發: {max_concurrent_writes}")
    
    def start_scheduler(self):
        """啟動查詢調度器"""
        if self._scheduler_running:
            return
        
        self._scheduler_running = True
        
        # 啟動讀取調度器
        read_task = asyncio.create_task(self._read_scheduler())
        self._scheduler_tasks.append(read_task)
        
        # 啟動寫入調度器  
        write_task = asyncio.create_task(self._write_scheduler())
        self._scheduler_tasks.append(write_task)
        
        # 啟動優先級調度器
        priority_task = asyncio.create_task(self._priority_scheduler())
        self._scheduler_tasks.append(priority_task)
        
        logger.info("查詢調度器已啟動")
    
    async def stop_scheduler(self):
        """停止查詢調度器"""
        self._scheduler_running = False
        
        # 取消所有調度任務
        for task in self._scheduler_tasks:
            task.cancel()
        
        # 等待所有任務結束
        await asyncio.gather(*self._scheduler_tasks, return_exceptions=True)
        
        self._scheduler_tasks.clear()
        self._executor.shutdown(wait=True)
        
        logger.info("查詢調度器已停止")
    
    def classify_query(self, sql: str) -> QueryType:
        """
        分類查詢類型
        
        參數:
            sql: SQL查詢字串
            
        返回:
            查詢類型
        """
        sql_upper = sql.strip().upper()
        
        # DDL操作
        if any(sql_upper.startswith(ddl) for ddl in ['CREATE', 'ALTER', 'DROP']):
            return QueryType.DDL
        
        # 事務操作
        if any(sql_upper.startswith(trans) for trans in ['BEGIN', 'COMMIT', 'ROLLBACK']):
            return QueryType.TRANSACTION
        
        # 寫入操作
        if any(sql_upper.startswith(write) for write in ['INSERT', 'UPDATE', 'DELETE', 'REPLACE']):
            return QueryType.WRITE
        
        # 讀取操作
        if sql_upper.startswith('SELECT'):
            # 檢查是否包含寫入子句
            if any(keyword in sql_upper for keyword in ['INSERT', 'UPDATE', 'DELETE']):
                return QueryType.MIXED
            return QueryType.READ
        
        # 預設為混合類型
        return QueryType.MIXED
    
    def optimize_query(self, sql: str, params: Tuple = ()) -> Tuple[str, Tuple]:
        """
        優化SQL查詢
        
        參數:
            sql: 原始SQL
            params: 查詢參數
            
        返回:
            優化後的(SQL, 參數)
        """
        optimized_sql = sql.strip()
        
        # 移除多餘空白
        import re
        optimized_sql = re.sub(r'\s+', ' ', optimized_sql)
        
        # SELECT查詢優化
        if self.classify_query(optimized_sql) == QueryType.READ:
            optimized_sql = self._optimize_select_query(optimized_sql)
        
        # 寫入查詢優化
        elif self.classify_query(optimized_sql) == QueryType.WRITE:
            optimized_sql = self._optimize_write_query(optimized_sql)
        
        return optimized_sql, params
    
    def _optimize_select_query(self, sql: str) -> str:
        """優化SELECT查詢"""
        # 添加LIMIT如果沒有
        if 'LIMIT' not in sql.upper() and 'COUNT(' not in sql.upper():
            # 對於可能返回大量結果的查詢添加合理的LIMIT
            if 'ORDER BY' in sql.upper():
                return f"{sql} LIMIT 1000"
            
        # 使用索引提示
        sql_upper = sql.upper()
        if 'WHERE' in sql_upper and 'INDEX' not in sql_upper:
            # 這裡可以添加自動索引提示邏輯
            pass
        
        return sql
    
    def _optimize_write_query(self, sql: str) -> str:
        """優化寫入查詢"""
        sql_upper = sql.upper()
        
        # INSERT優化
        if sql_upper.startswith('INSERT'):
            # 使用OR IGNORE減少錯誤
            if 'OR IGNORE' not in sql_upper and 'OR REPLACE' not in sql_upper:
                # 可以考慮添加OR IGNORE，但需要業務邏輯判斷
                pass
        
        return sql
    
    def _get_query_cache_key(self, sql: str, params: Tuple) -> str:
        """生成查詢快取鍵"""
        content = f"{sql}:{str(params)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """獲取快取結果"""
        with self._cache_lock:
            if cache_key in self._query_cache:
                result, cached_at = self._query_cache[cache_key]
                if datetime.utcnow() - cached_at < self._cache_ttl:
                    return result
                else:
                    # 過期快取清理
                    del self._query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Any):
        """快取查詢結果"""
        with self._cache_lock:
            self._query_cache[cache_key] = (result, datetime.utcnow())
            
            # 限制快取大小
            if len(self._query_cache) > 1000:
                # 清理最舊的快取項目
                oldest_key = min(self._query_cache.keys(), 
                               key=lambda k: self._query_cache[k][1])
                del self._query_cache[oldest_key]
    
    async def execute_optimized_query(
        self, 
        connection: OptimizedConnection, 
        sql: str, 
        params: Tuple = (),
        priority: QueryPriority = QueryPriority.NORMAL,
        timeout: float = 30.0,
        enable_cache: bool = True
    ) -> Any:
        """
        執行優化查詢
        
        參數:
            connection: 資料庫連線
            sql: SQL查詢
            params: 查詢參數
            priority: 查詢優先級
            timeout: 執行超時
            enable_cache: 是否啟用快取
            
        返回:
            查詢結果
        """
        # 分類查詢類型
        query_type = self.classify_query(sql)
        
        # 創建查詢請求
        request = QueryRequest(
            sql=sql,
            params=params,
            query_type=query_type,
            priority=priority,
            timeout=timeout
        )
        
        # 優化查詢
        optimized_sql, optimized_params = self.optimize_query(sql, params)
        request.sql = optimized_sql
        request.params = optimized_params
        
        # 讀取查詢快取檢查
        if enable_cache and query_type == QueryType.READ:
            cache_key = self._get_query_cache_key(optimized_sql, optimized_params)
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                logger.debug(f"快取命中 - 查詢: {request.query_hash}")
                return cached_result
        
        # 根據查詢類型選擇執行路徑
        if query_type == QueryType.READ:
            result = await self._execute_read_query(connection, request)
        elif query_type in [QueryType.WRITE, QueryType.MIXED, QueryType.DDL]:
            result = await self._execute_write_query(connection, request)
        else:
            result = await self._execute_transaction_query(connection, request)
        
        # 快取讀取結果
        if enable_cache and query_type == QueryType.READ and result is not None:
            cache_key = self._get_query_cache_key(optimized_sql, optimized_params)
            self._cache_result(cache_key, result)
        
        return result
    
    async def _execute_read_query(self, connection: OptimizedConnection, request: QueryRequest) -> Any:
        """執行讀取查詢"""
        async with self._read_semaphore:
            return await self._execute_with_metrics(connection, request)
    
    async def _execute_write_query(self, connection: OptimizedConnection, request: QueryRequest) -> Any:
        """執行寫入查詢"""
        async with self._write_lock:  # 寫入互斥
            async with self._write_semaphore:
                return await self._execute_with_metrics(connection, request)
    
    async def _execute_transaction_query(self, connection: OptimizedConnection, request: QueryRequest) -> Any:
        """執行事務查詢"""
        async with self._write_lock:  # 事務需要寫入鎖
            return await self._execute_with_metrics(connection, request)
    
    async def _execute_with_metrics(self, connection: OptimizedConnection, request: QueryRequest) -> Any:
        """帶效能監控的查詢執行"""
        start_time = time.time()
        had_lock_wait = False
        
        try:
            # 使用執行緒池執行同步查詢
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._sync_execute_query,
                connection,
                request
            )
            
            # 更新效能指標
            duration_ms = (time.time() - start_time) * 1000
            self._update_query_metrics(request, duration_ms, had_lock_wait)
            
            return result
            
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower():
                had_lock_wait = True
            
            duration_ms = (time.time() - start_time) * 1000
            self._update_query_metrics(request, duration_ms, had_lock_wait, error=True)
            
            logger.warning(f"查詢執行失敗 - {request.query_hash}: {e}")
            raise
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._update_query_metrics(request, duration_ms, had_lock_wait, error=True)
            
            logger.error(f"查詢執行錯誤 - {request.query_hash}: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.AGGRESSIVE)
    def _sync_execute_query(self, connection: OptimizedConnection, request: QueryRequest) -> Any:
        """同步執行查詢"""
        try:
            if request.query_type == QueryType.READ:
                cursor = connection.execute(request.sql, request.params)
                return cursor.fetchall()
            else:
                cursor = connection.execute(request.sql, request.params)
                connection.commit()
                return cursor.rowcount
                
        except Exception as e:
            logger.debug(f"同步查詢執行失敗: {e}")
            raise
    
    def _update_query_metrics(
        self, 
        request: QueryRequest, 
        duration_ms: float, 
        had_lock_wait: bool, 
        error: bool = False
    ):
        """更新查詢效能指標"""
        with self._metrics_lock:
            query_hash = request.query_hash
            
            if query_hash not in self._query_metrics:
                self._query_metrics[query_hash] = QueryMetrics(
                    query_hash=query_hash,
                    query_type=request.query_type
                )
            
            metrics = self._query_metrics[query_hash]
            
            if error:
                metrics.increment_error()
            else:
                metrics.update_metrics(duration_ms, had_lock_wait)
    
    async def _read_scheduler(self):
        """讀取查詢調度器"""
        while self._scheduler_running:
            try:
                # 這裡可以實現更複雜的讀取調度邏輯
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"讀取調度器錯誤: {e}")
    
    async def _write_scheduler(self):
        """寫入查詢調度器"""
        while self._scheduler_running:
            try:
                # 這裡可以實現寫入查詢的批處理和調度
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"寫入調度器錯誤: {e}")
    
    async def _priority_scheduler(self):
        """優先級調度器"""
        while self._scheduler_running:
            try:
                # 這裡可以實現基於優先級的查詢調度
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"優先級調度器錯誤: {e}")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """獲取優化統計資訊"""
        with self._metrics_lock:
            total_queries = sum(m.execution_count for m in self._query_metrics.values())
            total_errors = sum(m.error_count for m in self._query_metrics.values())
            total_lock_waits = sum(m.lock_wait_count for m in self._query_metrics.values())
            
            if total_queries > 0:
                avg_duration = sum(m.avg_duration_ms * m.execution_count for m in self._query_metrics.values()) / total_queries
                error_rate = (total_errors / total_queries) * 100
                lock_wait_rate = (total_lock_waits / total_queries) * 100
            else:
                avg_duration = 0.0
                error_rate = 0.0
                lock_wait_rate = 0.0
            
            return {
                'total_queries': total_queries,
                'unique_queries': len(self._query_metrics),
                'average_duration_ms': avg_duration,
                'total_errors': total_errors,
                'error_rate_percent': error_rate,
                'lock_waits': total_lock_waits,
                'lock_wait_rate_percent': lock_wait_rate,
                'cache_entries': len(self._query_cache),
                'concurrent_reads_limit': self.max_concurrent_reads,
                'concurrent_writes_limit': self.max_concurrent_writes,
                'scheduler_running': self._scheduler_running
            }
    
    def get_slow_queries(self, min_duration_ms: float = 100.0, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取慢查詢列表"""
        with self._metrics_lock:
            slow_queries = [
                {
                    'query_hash': metrics.query_hash,
                    'query_type': metrics.query_type.value,
                    'execution_count': metrics.execution_count,
                    'avg_duration_ms': metrics.avg_duration_ms,
                    'max_duration_ms': metrics.max_duration_ms,
                    'error_count': metrics.error_count,
                    'lock_wait_count': metrics.lock_wait_count,
                    'last_executed': metrics.last_executed
                }
                for metrics in self._query_metrics.values()
                if metrics.avg_duration_ms >= min_duration_ms
            ]
            
            # 按平均執行時間降序排列
            slow_queries.sort(key=lambda x: x['avg_duration_ms'], reverse=True)
            return slow_queries[:limit]
    
    def clear_cache(self):
        """清空查詢快取"""
        with self._cache_lock:
            cleared_count = len(self._query_cache)
            self._query_cache.clear()
            logger.info(f"已清空 {cleared_count} 個快取項目")
    
    def clear_metrics(self):
        """清空效能指標"""
        with self._metrics_lock:
            cleared_count = len(self._query_metrics)
            self._query_metrics.clear()
            logger.info(f"已清空 {cleared_count} 個查詢指標")


# 全局查詢優化器實例
_global_optimizer: Optional[SQLiteQueryOptimizer] = None
_optimizer_lock = threading.RLock()


def get_query_optimizer(
    max_concurrent_reads: int = 10, 
    max_concurrent_writes: int = 2
) -> SQLiteQueryOptimizer:
    """
    獲取全局查詢優化器實例
    
    參數:
        max_concurrent_reads: 最大併發讀取數
        max_concurrent_writes: 最大併發寫入數
        
    返回:
        查詢優化器實例
    """
    global _global_optimizer
    
    with _optimizer_lock:
        if _global_optimizer is None:
            _global_optimizer = SQLiteQueryOptimizer(
                max_concurrent_reads=max_concurrent_reads,
                max_concurrent_writes=max_concurrent_writes
            )
            _global_optimizer.start_scheduler()
            logger.info("全局查詢優化器已初始化")
        
        return _global_optimizer


async def cleanup_query_optimizer():
    """清理全局查詢優化器"""
    global _global_optimizer
    
    with _optimizer_lock:
        if _global_optimizer:
            await _global_optimizer.stop_scheduler()
            _global_optimizer = None
            logger.info("全局查詢優化器已清理")