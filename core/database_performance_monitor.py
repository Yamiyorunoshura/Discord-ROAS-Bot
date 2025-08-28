"""
Database Performance Monitor - 資料庫效能監控和基準系統
Task ID: 1 - 核心架構和基礎設施建置

提供全面的資料庫效能監控、指標收集和性能基準管理，
確保資料庫操作符合效能要求並提供早期警示機制。
"""

import time
import asyncio
import statistics
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import logging
import json

from .database_manager import DatabaseManager
from .security_manager import get_security_manager

logger = logging.getLogger('core.database_performance_monitor')


@dataclass
class QueryMetrics:
    """查詢效能指標"""
    query_hash: str
    query_type: str  # SELECT, INSERT, UPDATE, DELETE
    execution_count: int = 0
    total_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    error_count: int = 0
    last_execution: Optional[datetime] = None
    execution_times: List[float] = field(default_factory=list)
    
    def add_execution(self, execution_time: float, success: bool = True):
        """新增執行記錄"""
        self.execution_count += 1
        self.total_execution_time += execution_time
        self.min_execution_time = min(self.min_execution_time, execution_time)
        self.max_execution_time = max(self.max_execution_time, execution_time)
        self.avg_execution_time = self.total_execution_time / self.execution_count
        self.last_execution = datetime.now()
        
        # 保留最近100次執行時間用於統計分析
        self.execution_times.append(execution_time)
        if len(self.execution_times) > 100:
            self.execution_times.pop(0)
        
        if not success:
            self.error_count += 1
    
    @property
    def p95_execution_time(self) -> float:
        """95百分位執行時間"""
        if not self.execution_times:
            return 0.0
        return statistics.quantiles(self.execution_times, n=20)[18]  # 95th percentile
    
    @property
    def error_rate(self) -> float:
        """錯誤率"""
        if self.execution_count == 0:
            return 0.0
        return self.error_count / self.execution_count


@dataclass
class DatabaseHealthMetrics:
    """資料庫健康指標"""
    timestamp: datetime
    connection_count: int
    active_connections: int
    total_queries: int
    slow_queries: int
    error_queries: int
    avg_response_time: float
    p95_response_time: float
    database_size_bytes: int
    index_usage_rate: float
    cache_hit_rate: float = 0.0  # SQLite 不直接支援但可估算


class DatabasePerformanceMonitor:
    """
    資料庫效能監控器
    
    提供即時效能監控、指標收集和性能基準管理
    與 DatabaseManager 整合，自動追蹤所有資料庫操作
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化效能監控器
        
        參數：
            db_manager: 資料庫管理器實例
        """
        self.db_manager = db_manager
        self.metrics: Dict[str, QueryMetrics] = {}
        self.health_history: List[DatabaseHealthMetrics] = []
        self.performance_baselines: Dict[str, float] = {}
        
        # 效能閾值設定
        self.thresholds = {
            'slow_query_threshold': 100.0,  # 100ms
            'p95_threshold': 100.0,  # 100ms (符合任務需求)
            'error_rate_threshold': 0.01,  # 1%
            'connection_threshold': 50  # 50個連線
        }
        
        # 監控狀態
        self.monitoring_enabled = True
        self.alert_callbacks: List[callable] = []
        
        # 初始化基準
        self._load_performance_baselines()
    
    @asynccontextmanager
    async def monitor_query(self, query: str, query_type: str = "UNKNOWN"):
        """
        查詢效能監控上下文管理器
        
        參數：
            query: SQL 查詢語句
            query_type: 查詢類型
        """
        if not self.monitoring_enabled:
            yield
            return
        
        query_hash = get_security_manager().generate_checksum(query)
        start_time = time.perf_counter()
        success = True
        
        try:
            yield
        except Exception as e:
            success = False
            logger.error(f"監控查詢執行失敗: {e}")
            raise
        finally:
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000  # 轉換為毫秒
            
            # 記錄指標
            self._record_query_metrics(query_hash, query_type, execution_time, success)
            
            # 檢查效能閾值
            self._check_performance_thresholds(query_hash, execution_time)
    
    def _record_query_metrics(self, query_hash: str, query_type: str, 
                            execution_time: float, success: bool):
        """記錄查詢效能指標"""
        if query_hash not in self.metrics:
            self.metrics[query_hash] = QueryMetrics(
                query_hash=query_hash,
                query_type=query_type
            )
        
        self.metrics[query_hash].add_execution(execution_time, success)
    
    def _check_performance_thresholds(self, query_hash: str, execution_time: float):
        """檢查效能閾值並觸發告警"""
        # 慢查詢檢查
        if execution_time > self.thresholds['slow_query_threshold']:
            self._trigger_alert('slow_query', {
                'query_hash': query_hash,
                'execution_time': execution_time,
                'threshold': self.thresholds['slow_query_threshold']
            })
        
        # P95 檢查
        metrics = self.metrics[query_hash]
        if metrics.p95_execution_time > self.thresholds['p95_threshold']:
            self._trigger_alert('p95_exceeded', {
                'query_hash': query_hash,
                'p95_time': metrics.p95_execution_time,
                'threshold': self.thresholds['p95_threshold']
            })
        
        # 錯誤率檢查
        if metrics.error_rate > self.thresholds['error_rate_threshold']:
            self._trigger_alert('high_error_rate', {
                'query_hash': query_hash,
                'error_rate': metrics.error_rate,
                'threshold': self.thresholds['error_rate_threshold']
            })
    
    def _trigger_alert(self, alert_type: str, details: Dict[str, Any]):
        """觸發效能告警"""
        alert_data = {
            'type': alert_type,
            'timestamp': datetime.now().isoformat(),
            'details': details
        }
        
        logger.warning(f"資料庫效能告警: {alert_type} - {details}")
        
        # 呼叫註冊的告警回調
        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logger.error(f"告警回調執行失敗: {e}")
    
    async def collect_health_metrics(self) -> DatabaseHealthMetrics:
        """收集資料庫健康指標"""
        try:
            # 基礎統計
            total_queries = sum(m.execution_count for m in self.metrics.values())
            slow_queries = sum(1 for m in self.metrics.values() 
                             if m.avg_execution_time > self.thresholds['slow_query_threshold'])
            error_queries = sum(m.error_count for m in self.metrics.values())
            
            # 計算平均響應時間
            all_execution_times = []
            for metrics in self.metrics.values():
                all_execution_times.extend(metrics.execution_times)
            
            avg_response_time = statistics.mean(all_execution_times) if all_execution_times else 0.0
            p95_response_time = (statistics.quantiles(all_execution_times, n=20)[18] 
                               if len(all_execution_times) > 10 else 0.0)
            
            # 資料庫大小
            db_size = await self._get_database_size()
            
            # 索引使用率（估算）
            index_usage_rate = await self._estimate_index_usage()
            
            # 連線數統計
            connection_count = len(self.db_manager.connection_pool.connections)
            active_connections = sum(self.db_manager.connection_pool.connection_counts.values())
            
            metrics = DatabaseHealthMetrics(
                timestamp=datetime.now(),
                connection_count=connection_count,
                active_connections=active_connections,
                total_queries=total_queries,
                slow_queries=slow_queries,
                error_queries=error_queries,
                avg_response_time=avg_response_time,
                p95_response_time=p95_response_time,
                database_size_bytes=db_size,
                index_usage_rate=index_usage_rate
            )
            
            # 保存健康歷史記錄（保留最近24小時）
            self.health_history.append(metrics)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.health_history = [h for h in self.health_history if h.timestamp > cutoff_time]
            
            return metrics
            
        except Exception as e:
            logger.error(f"收集健康指標失敗: {e}")
            raise
    
    async def _get_database_size(self) -> int:
        """獲取資料庫大小（位元組）"""
        try:
            import os
            return os.path.getsize(self.db_manager.db_name)
        except Exception:
            return 0
    
    async def _estimate_index_usage(self) -> float:
        """估算索引使用率"""
        try:
            # 透過 EXPLAIN QUERY PLAN 分析最近的查詢來估算
            # 這是一個簡化的實作，實際應用中需要更複雜的分析
            indexed_queries = 0
            total_analyzed_queries = 0
            
            for query_hash, metrics in self.metrics.items():
                if metrics.query_type == 'SELECT' and metrics.execution_count > 0:
                    total_analyzed_queries += 1
                    # 如果平均執行時間低於閾值，假設使用了索引
                    if metrics.avg_execution_time < 10.0:  # 10ms
                        indexed_queries += 1
            
            if total_analyzed_queries == 0:
                return 100.0  # 預設假設索引使用率良好
            
            return (indexed_queries / total_analyzed_queries) * 100.0
            
        except Exception:
            return 0.0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """獲取效能摘要報告"""
        if not self.metrics:
            return {
                'status': 'no_data',
                'message': '暫無效能資料'
            }
        
        # 整體統計
        total_queries = sum(m.execution_count for m in self.metrics.values())
        total_errors = sum(m.error_count for m in self.metrics.values())
        avg_response_times = [m.avg_execution_time for m in self.metrics.values()]
        p95_response_times = [m.p95_execution_time for m in self.metrics.values()]
        
        # 慢查詢分析
        slow_queries = [m for m in self.metrics.values() 
                       if m.avg_execution_time > self.thresholds['slow_query_threshold']]
        
        # 效能等級評估
        overall_p95 = max(p95_response_times) if p95_response_times else 0.0
        error_rate = total_errors / total_queries if total_queries > 0 else 0.0
        
        performance_grade = self._calculate_performance_grade(overall_p95, error_rate)
        
        return {
            'status': 'active',
            'performance_grade': performance_grade,
            'summary': {
                'total_queries': total_queries,
                'total_errors': total_errors,
                'error_rate': f"{error_rate:.2%}",
                'avg_response_time': f"{statistics.mean(avg_response_times):.2f}ms" if avg_response_times else "0ms",
                'p95_response_time': f"{overall_p95:.2f}ms",
                'slow_queries_count': len(slow_queries),
                'unique_query_patterns': len(self.metrics)
            },
            'thresholds': self.thresholds,
            'slow_queries': [
                {
                    'query_hash': q.query_hash[:16],
                    'query_type': q.query_type,
                    'avg_time': f"{q.avg_execution_time:.2f}ms",
                    'execution_count': q.execution_count
                }
                for q in slow_queries[:10]  # 顯示前10個慢查詢
            ],
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_performance_grade(self, p95_time: float, error_rate: float) -> str:
        """計算效能等級"""
        if p95_time <= 50.0 and error_rate <= 0.001:
            return 'A+'  # 優秀
        elif p95_time <= 100.0 and error_rate <= 0.01:
            return 'A'   # 良好（符合任務要求）
        elif p95_time <= 200.0 and error_rate <= 0.05:
            return 'B'   # 可接受
        elif p95_time <= 500.0 and error_rate <= 0.1:
            return 'C'   # 需要關注
        else:
            return 'D'   # 需要立即優化
    
    def set_performance_baseline(self, metric_name: str, baseline_value: float):
        """設定效能基準值"""
        self.performance_baselines[metric_name] = baseline_value
        self._save_performance_baselines()
        logger.info(f"設定效能基準 {metric_name}: {baseline_value}")
    
    def _load_performance_baselines(self):
        """載入效能基準值"""
        try:
            baselines_file = os.path.join(
                os.path.dirname(self.db_manager.db_name), 
                '..', 'data', 'performance_baselines.json'
            )
            
            if os.path.exists(baselines_file):
                with open(baselines_file, 'r', encoding='utf-8') as f:
                    self.performance_baselines = json.load(f)
                logger.info(f"載入效能基準: {len(self.performance_baselines)} 項")
            else:
                # 設定預設基準值
                self.performance_baselines = {
                    'p95_response_time': 100.0,  # 100ms（任務要求）
                    'avg_response_time': 50.0,   # 50ms
                    'error_rate': 0.01,          # 1%
                    'index_usage_rate': 90.0     # 90%
                }
                logger.info("使用預設效能基準值")
                
        except Exception as e:
            logger.error(f"載入效能基準失敗: {e}")
    
    def _save_performance_baselines(self):
        """儲存效能基準值"""
        try:
            baselines_file = os.path.join(
                os.path.dirname(self.db_manager.db_name), 
                '..', 'data', 'performance_baselines.json'
            )
            
            os.makedirs(os.path.dirname(baselines_file), exist_ok=True)
            
            with open(baselines_file, 'w', encoding='utf-8') as f:
                json.dump(self.performance_baselines, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"儲存效能基準失敗: {e}")
    
    def register_alert_callback(self, callback: callable):
        """註冊告警回調函數"""
        self.alert_callbacks.append(callback)
    
    def enable_monitoring(self):
        """啟用效能監控"""
        self.monitoring_enabled = True
        logger.info("資料庫效能監控已啟用")
    
    def disable_monitoring(self):
        """停用效能監控"""
        self.monitoring_enabled = False
        logger.info("資料庫效能監控已停用")
    
    async def reset_metrics(self):
        """重置所有效能指標"""
        self.metrics.clear()
        self.health_history.clear()
        logger.info("效能指標已重置")


# 全域效能監控器實例
_performance_monitor: Optional[DatabasePerformanceMonitor] = None


def get_performance_monitor(db_manager: DatabaseManager) -> DatabasePerformanceMonitor:
    """
    獲取全域效能監控器實例
    
    參數：
        db_manager: 資料庫管理器實例
        
    返回：
        效能監控器實例
    """
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = DatabasePerformanceMonitor(db_manager)
    return _performance_monitor