"""
整合資料庫連線監控統計服務
T2 - 高併發連線競爭修復實施

整合連線池管理、查詢優化和監控功能，提供統一的資料庫服務介面
支援實時統計、效能分析、自動調優和故障診斷
"""

import asyncio
import logging
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, asdict

from .connection_pool import (
    ConnectionPoolManager, 
    ConnectionPoolConfig, 
    get_connection_pool,
    cleanup_all_pools
)
from .connection_pool_monitor import (
    ConnectionPoolMonitor,
    get_sync_global_monitor,
    cleanup_global_monitor
)
from .sqlite_query_optimizer import (
    SQLiteQueryOptimizer,
    QueryPriority,
    get_query_optimizer,
    cleanup_query_optimizer
)
from ..db.sqlite import OptimizedConnection, SQLiteConnectionFactory
from ..db.retry import retry_on_database_locked, CommonRetryStrategies

logger = logging.getLogger('src.services.database_service')


@dataclass 
class DatabaseServiceConfig:
    """資料庫服務配置"""
    # 連線池配置
    min_connections: int = 2
    max_connections: int = 20
    connection_timeout: float = 5.0
    max_idle_time_minutes: int = 30
    max_lifetime_hours: int = 4
    
    # 查詢優化配置
    max_concurrent_reads: int = 10
    max_concurrent_writes: int = 2
    query_cache_enabled: bool = True
    query_timeout: float = 30.0
    
    # 監控配置
    enable_monitoring: bool = True
    monitoring_interval_seconds: int = 60
    retention_days: int = 7
    auto_cleanup_enabled: bool = True
    
    # 自動調優配置
    auto_optimization_enabled: bool = True
    optimization_interval_minutes: int = 10
    slow_query_threshold_ms: float = 100.0


class DatabaseService:
    """
    整合資料庫服務
    
    提供高效能、高可用的資料庫連線管理和查詢優化服務
    整合連線池、查詢優化器和監控系統，支援自動調優和故障診斷
    """
    
    def __init__(self, db_path: str, config: Optional[DatabaseServiceConfig] = None):
        """
        初始化資料庫服務
        
        參數:
            db_path: 資料庫檔案路徑
            config: 服務配置
        """
        self.db_path = os.path.abspath(db_path)
        self.config = config or DatabaseServiceConfig()
        
        # 連線池管理器
        pool_config = ConnectionPoolConfig(
            min_connections=self.config.min_connections,
            max_connections=self.config.max_connections,
            connection_timeout=self.config.connection_timeout,
            max_idle_time=timedelta(minutes=self.config.max_idle_time_minutes),
            max_lifetime=timedelta(hours=self.config.max_lifetime_hours),
            dynamic_scaling=True
        )
        self._pool_manager = get_connection_pool(self.db_path, pool_config)
        
        # 查詢優化器
        self._query_optimizer = get_query_optimizer(
            max_concurrent_reads=self.config.max_concurrent_reads,
            max_concurrent_writes=self.config.max_concurrent_writes
        )
        
        # 監控器
        self._monitor: Optional[ConnectionPoolMonitor] = None
        if self.config.enable_monitoring:
            self._monitor = get_sync_global_monitor()
        
        # 服務狀態
        self._initialized = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._optimization_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        # 統計數據
        self._service_start_time = datetime.utcnow()
        self._total_queries = 0
        self._successful_queries = 0
        self._failed_queries = 0
        
        logger.info(f"資料庫服務已建立 - 資料庫: {self.db_path}")
    
    async def initialize(self):
        """初始化資料庫服務"""
        if self._initialized:
            return
        
        try:
            # 初始化連線池
            await self._pool_manager.initialize()
            
            # 啟動監控任務
            if self.config.enable_monitoring and self._monitor:
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            # 啟動自動優化任務
            if self.config.auto_optimization_enabled:
                self._optimization_task = asyncio.create_task(self._optimization_loop())
            
            self._initialized = True
            logger.info("資料庫服務已完成初始化")
            
        except Exception as e:
            logger.error(f"初始化資料庫服務失敗: {e}")
            raise
    
    async def execute_query(
        self,
        sql: str,
        params: tuple = (),
        priority: QueryPriority = QueryPriority.NORMAL,
        timeout: Optional[float] = None,
        enable_cache: bool = None
    ) -> Any:
        """
        執行優化查詢
        
        參數:
            sql: SQL查詢語句
            params: 查詢參數
            priority: 查詢優先級
            timeout: 查詢超時時間
            enable_cache: 是否啟用快取
            
        返回:
            查詢結果
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        timeout = timeout or self.config.query_timeout
        enable_cache = enable_cache if enable_cache is not None else self.config.query_cache_enabled
        
        try:
            self._total_queries += 1
            
            # 取得連線池連線
            async with self._pool_manager.get_async_connection(timeout) as connection:
                # 執行優化查詢
                result = await self._query_optimizer.execute_optimized_query(
                    connection=connection,
                    sql=sql,
                    params=params,
                    priority=priority,
                    timeout=timeout,
                    enable_cache=enable_cache
                )
            
            self._successful_queries += 1
            execution_time = (time.time() - start_time) * 1000
            
            logger.debug(f"查詢執行成功 - 耗時: {execution_time:.2f}ms")
            return result
            
        except Exception as e:
            self._failed_queries += 1
            execution_time = (time.time() - start_time) * 1000
            
            logger.error(f"查詢執行失敗 - 耗時: {execution_time:.2f}ms, 錯誤: {e}")
            raise
    
    async def execute_transaction(
        self,
        operations: List[tuple],
        timeout: Optional[float] = None
    ) -> List[Any]:
        """
        執行事務操作
        
        參數:
            operations: 操作列表，每個元素為(sql, params)
            timeout: 事務超時時間
            
        返回:
            所有操作的結果列表
        """
        if not self._initialized:
            await self.initialize()
        
        timeout = timeout or self.config.query_timeout * len(operations)
        results = []
        
        try:
            async with self._pool_manager.get_async_connection(timeout) as connection:
                # 開始事務
                await self._query_optimizer.execute_optimized_query(
                    connection=connection,
                    sql="BEGIN TRANSACTION",
                    priority=QueryPriority.HIGH,
                    timeout=timeout,
                    enable_cache=False
                )
                
                try:
                    # 執行所有操作
                    for sql, params in operations:
                        result = await self._query_optimizer.execute_optimized_query(
                            connection=connection,
                            sql=sql,
                            params=params,
                            priority=QueryPriority.HIGH,
                            timeout=timeout,
                            enable_cache=False
                        )
                        results.append(result)
                    
                    # 提交事務
                    await self._query_optimizer.execute_optimized_query(
                        connection=connection,
                        sql="COMMIT",
                        priority=QueryPriority.HIGH,
                        timeout=timeout,
                        enable_cache=False
                    )
                    
                    logger.debug(f"事務執行成功 - 操作數: {len(operations)}")
                    return results
                    
                except Exception:
                    # 回滾事務
                    await self._query_optimizer.execute_optimized_query(
                        connection=connection,
                        sql="ROLLBACK", 
                        priority=QueryPriority.CRITICAL,
                        timeout=timeout,
                        enable_cache=False
                    )
                    raise
                    
        except Exception as e:
            logger.error(f"事務執行失敗: {e}")
            raise
    
    def execute_sync_query(
        self,
        sql: str,
        params: tuple = (),
        timeout: Optional[float] = None
    ) -> Any:
        """
        同步執行查詢
        
        參數:
            sql: SQL查詢語句
            params: 查詢參數
            timeout: 查詢超時時間
            
        返回:
            查詢結果
        """
        # 使用同步連線池
        timeout = timeout or self.config.query_timeout
        
        try:
            with self._pool_manager.get_sync_connection(timeout) as connection:
                cursor = connection.execute(sql, params)
                
                if sql.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                else:
                    connection.commit()
                    return cursor.rowcount
                    
        except Exception as e:
            logger.error(f"同步查詢執行失敗: {e}")
            raise
    
    async def _monitoring_loop(self):
        """監控循環任務"""
        while not self._shutdown and self._monitor:
            try:
                await asyncio.sleep(self.config.monitoring_interval_seconds)
                
                # 收集連線池統計
                pool_stats = self._pool_manager.get_pool_stats()
                
                # 記錄到監控資料庫
                self._monitor.record_pool_statistics(pool_stats)
                
                # 自動清理過期記錄
                if self.config.auto_cleanup_enabled:
                    self._monitor.cleanup_old_records(self.config.retention_days)
                
            except Exception as e:
                logger.error(f"監控循環錯誤: {e}")
    
    async def _optimization_loop(self):
        """自動優化循環任務"""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.optimization_interval_minutes * 60)
                
                # 執行連線池優化
                await self._pool_manager.optimize_pool()
                
                # 清理查詢快取
                self._query_optimizer.clear_cache()
                
                # 分析慢查詢
                slow_queries = self._query_optimizer.get_slow_queries(
                    min_duration_ms=self.config.slow_query_threshold_ms
                )
                
                if slow_queries:
                    logger.info(f"發現 {len(slow_queries)} 個慢查詢，建議檢查索引")
                
            except Exception as e:
                logger.error(f"自動優化錯誤: {e}")
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """獲取服務統計資訊"""
        uptime = datetime.utcnow() - self._service_start_time
        
        # 連線池統計
        pool_stats = self._pool_manager.get_pool_stats()
        
        # 查詢優化器統計
        optimizer_stats = self._query_optimizer.get_optimization_stats()
        
        # 監控統計
        monitor_stats = {}
        if self._monitor:
            monitor_stats = self._monitor.get_monitor_database_stats()
        
        return {
            'service': {
                'db_path': self.db_path,
                'uptime_seconds': uptime.total_seconds(),
                'uptime_formatted': str(uptime),
                'initialized': self._initialized,
                'total_queries': self._total_queries,
                'successful_queries': self._successful_queries,
                'failed_queries': self._failed_queries,
                'success_rate_percent': (
                    (self._successful_queries / self._total_queries * 100) 
                    if self._total_queries > 0 else 100.0
                )
            },
            'connection_pool': pool_stats,
            'query_optimizer': optimizer_stats,
            'monitor': monitor_stats,
            'config': asdict(self.config)
        }
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        獲取效能報告
        
        參數:
            hours: 報告時間範圍(小時)
            
        返回:
            效能報告字典
        """
        if not self._monitor:
            return {'error': '監控功能未啟用'}
        
        try:
            # 獲取效能摘要
            summary = self._monitor.get_performance_summary(self.db_path, hours)
            
            # 獲取健康趨勢
            trends = self._monitor.get_connection_health_trends(self.db_path, hours)
            
            # 獲取慢查詢
            slow_queries = self._query_optimizer.get_slow_queries(
                min_duration_ms=self.config.slow_query_threshold_ms
            )
            
            return {
                'report_generated_at': datetime.utcnow(),
                'period_hours': hours,
                'performance_summary': summary,
                'health_trends': trends,
                'slow_queries': slow_queries,
                'recommendations': self._generate_recommendations(summary, slow_queries)
            }
            
        except Exception as e:
            logger.error(f"生成效能報告失敗: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(
        self, 
        summary: Dict[str, Any], 
        slow_queries: List[Dict[str, Any]]
    ) -> List[str]:
        """生成效能建議"""
        recommendations = []
        
        # 連線池建議
        if summary.get('avg_active_connections', 0) > self.config.max_connections * 0.8:
            recommendations.append("考慮增加最大連線數或優化查詢效率")
        
        # 錯誤率建議
        error_rate = summary.get('overall_error_rate', 0)
        if error_rate > 5.0:
            recommendations.append(f"錯誤率偏高({error_rate:.1f}%)，建議檢查查詢邏輯和資料完整性")
        
        # 慢查詢建議
        if len(slow_queries) > 5:
            recommendations.append("發現多個慢查詢，建議優化索引或重寫查詢")
        
        # 等待時間建議
        avg_wait_time = summary.get('avg_wait_time_ms', 0)
        if avg_wait_time > 50:
            recommendations.append(f"平均等待時間偏長({avg_wait_time:.1f}ms)，考慮增加連線池大小")
        
        if not recommendations:
            recommendations.append("系統效能良好，無需特殊優化")
        
        return recommendations
    
    async def health_check(self) -> Dict[str, Any]:
        """
        系統健康檢查
        
        返回:
            健康狀態資訊
        """
        try:
            # 測試基本連線
            test_result = await self.execute_query("SELECT 1 as health_check")
            
            # 獲取統計資訊
            stats = self.get_service_statistics()
            
            # 判斷健康狀態
            is_healthy = (
                self._initialized and
                test_result is not None and
                stats['service']['success_rate_percent'] > 90.0
            )
            
            return {
                'status': 'healthy' if is_healthy else 'degraded',
                'timestamp': datetime.utcnow(),
                'test_query_success': test_result is not None,
                'service_initialized': self._initialized,
                'success_rate': stats['service']['success_rate_percent'],
                'active_connections': stats['connection_pool']['active_connections'],
                'total_connections': stats['connection_pool']['total_connections'],
                'uptime_seconds': stats['service']['uptime_seconds']
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'timestamp': datetime.utcnow(), 
                'error': str(e),
                'test_query_success': False,
                'service_initialized': self._initialized
            }
    
    async def close(self):
        """關閉資料庫服務"""
        logger.info("正在關閉資料庫服務...")
        self._shutdown = True
        
        # 停止監控任務
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        # 停止優化任務
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
        
        # 關閉連線池
        await self._pool_manager.close()
        
        logger.info("資料庫服務已關閉")
    
    def __del__(self):
        """析構函數"""
        if not self._shutdown:
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.create_task(self.close())
            except:
                pass


# 全局服務實例管理
_service_instances: Dict[str, DatabaseService] = {}
_service_lock = threading.RLock()


def get_database_service(
    db_path: str, 
    config: Optional[DatabaseServiceConfig] = None
) -> DatabaseService:
    """
    獲取資料庫服務實例
    
    參數:
        db_path: 資料庫檔案路徑
        config: 服務配置
        
    返回:
        資料庫服務實例
    """
    abs_path = os.path.abspath(db_path)
    
    with _service_lock:
        if abs_path not in _service_instances:
            service = DatabaseService(abs_path, config)
            _service_instances[abs_path] = service
            logger.info(f"已創建資料庫服務實例: {abs_path}")
        
        return _service_instances[abs_path]


async def cleanup_all_database_services():
    """清理所有資料庫服務"""
    with _service_lock:
        for service in list(_service_instances.values()):
            await service.close()
        
        _service_instances.clear()
    
    # 清理全局組件
    await cleanup_all_pools()
    await cleanup_global_monitor()
    await cleanup_query_optimizer()
    
    logger.info("已清理所有資料庫服務")