"""
T2 - 高併發連線競爭修復 - 高級效能監控系統
Task ID: T2

專業級效能監控和分析平台：
- 實時效能指標收集
- 智慧異常檢測與告警
- 效能趨勢分析與預測
- 自動化效能基準測試
- 資源利用率最佳化建議

作者: Ethan - 效能優化專家
"""

import asyncio
import logging
import json
import time
import statistics
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import os
import sqlite3
import aiosqlite


logger = logging.getLogger('performance_monitor')


@dataclass
class PerformanceAlert:
    """效能警報"""
    alert_id: str
    severity: str                # "critical", "warning", "info"
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: datetime
    resolved: bool = False


@dataclass
class ResourceMetrics:
    """資源使用指標"""
    timestamp: datetime
    memory_usage_mb: float
    cpu_usage_percent: float
    active_connections: int
    idle_connections: int
    pending_requests: int
    successful_operations: int
    failed_operations: int
    average_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    throughput_ops_per_second: float
    error_rate_percent: float


@dataclass  
class PerformanceBenchmark:
    """效能基準"""
    benchmark_name: str
    target_response_time_ms: float
    target_throughput_ops: float
    target_error_rate_percent: float
    target_availability_percent: float
    created_at: datetime
    last_measured_at: Optional[datetime] = None
    current_performance_score: float = 0.0


class PerformanceDataStore:
    """效能數據存儲"""
    
    def __init__(self, db_path: str = "performance_metrics.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化效能數據庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 創建效能指標表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                memory_usage_mb REAL,
                cpu_usage_percent REAL,
                active_connections INTEGER,
                idle_connections INTEGER,
                pending_requests INTEGER,
                successful_operations INTEGER,
                failed_operations INTEGER,
                average_response_time_ms REAL,
                p95_response_time_ms REAL,
                p99_response_time_ms REAL,
                throughput_ops_per_second REAL,
                error_rate_percent REAL
            )
        """)
        
        # 創建警報表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT UNIQUE,
                severity TEXT,
                message TEXT,
                metric_name TEXT,
                current_value REAL,
                threshold_value REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT 0
            )
        """)
        
        # 創建基準測試表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_name TEXT,
                target_response_time_ms REAL,
                target_throughput_ops REAL,
                target_error_rate_percent REAL,
                target_availability_percent REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_measured_at TIMESTAMP,
                current_performance_score REAL DEFAULT 0.0
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"效能數據庫初始化完成: {self.db_path}")
    
    async def store_metrics(self, metrics: ResourceMetrics):
        """存儲效能指標"""
        try:
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("""
                INSERT INTO performance_metrics (
                    memory_usage_mb, cpu_usage_percent, active_connections,
                    idle_connections, pending_requests, successful_operations,
                    failed_operations, average_response_time_ms, p95_response_time_ms,
                    p99_response_time_ms, throughput_ops_per_second, error_rate_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.memory_usage_mb, metrics.cpu_usage_percent,
                metrics.active_connections, metrics.idle_connections,
                metrics.pending_requests, metrics.successful_operations,
                metrics.failed_operations, metrics.average_response_time_ms,
                metrics.p95_response_time_ms, metrics.p99_response_time_ms,
                metrics.throughput_ops_per_second, metrics.error_rate_percent
            ))
            await conn.commit()
            await conn.close()
        except Exception as e:
            logger.error(f"存儲效能指標失敗: {e}")
    
    async def store_alert(self, alert: PerformanceAlert):
        """存儲效能警報"""
        try:
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("""
                INSERT OR REPLACE INTO performance_alerts (
                    alert_id, severity, message, metric_name,
                    current_value, threshold_value, resolved
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.severity, alert.message,
                alert.metric_name, alert.current_value,
                alert.threshold_value, alert.resolved
            ))
            await conn.commit()
            await conn.close()
        except Exception as e:
            logger.error(f"存儲效能警報失敗: {e}")


class AdvancedPerformanceMonitor:
    """
    高級效能監控系統
    
    核心功能：
    1. 實時效能指標收集
    2. 智慧異常檢測
    3. 自動化告警系統
    4. 效能趨勢分析
    5. 基準測試管理
    6. 效能優化建議
    """
    
    def __init__(
        self,
        collection_interval: int = 5,
        retention_hours: int = 24,
        alert_thresholds: Optional[Dict] = None
    ):
        self.collection_interval = collection_interval
        self.retention_hours = retention_hours
        
        # 數據存儲
        self.data_store = PerformanceDataStore()
        
        # 實時數據緩存
        self.metrics_history: deque = deque(maxlen=1440)  # 24小時數據(5秒間隔)
        self.alert_history: deque = deque(maxlen=1000)
        
        # 告警閾值
        self.alert_thresholds = alert_thresholds or {
            'response_time_ms': {'warning': 100, 'critical': 500},
            'error_rate_percent': {'warning': 5, 'critical': 15},
            'queue_length': {'warning': 5, 'critical': 20},
            'cpu_usage_percent': {'warning': 70, 'critical': 90},
            'memory_usage_mb': {'warning': 500, 'critical': 1000}
        }
        
        # 效能基準
        self.benchmarks: Dict[str, PerformanceBenchmark] = {}
        
        # 監控狀態
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._alert_callbacks: List[Callable] = []
        
        # 統計資料
        self.total_alerts_generated = 0
        self.monitoring_start_time = None
        
        logger.info("高級效能監控系統已初始化")
    
    async def start_monitoring(self):
        """啟動效能監控"""
        if self._monitoring_active:
            logger.warning("效能監控已經在運行中")
            return
        
        self._monitoring_active = True
        self.monitoring_start_time = datetime.now()
        
        # 啟動監控任務
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"效能監控已啟動，收集間隔: {self.collection_interval}秒")
    
    async def stop_monitoring(self):
        """停止效能監控"""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("效能監控已停止")
    
    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """添加警報回調函數"""
        self._alert_callbacks.append(callback)
    
    def create_benchmark(
        self,
        name: str,
        target_response_time_ms: float,
        target_throughput_ops: float,
        target_error_rate_percent: float,
        target_availability_percent: float = 99.9
    ) -> PerformanceBenchmark:
        """創建效能基準"""
        benchmark = PerformanceBenchmark(
            benchmark_name=name,
            target_response_time_ms=target_response_time_ms,
            target_throughput_ops=target_throughput_ops,
            target_error_rate_percent=target_error_rate_percent,
            target_availability_percent=target_availability_percent,
            created_at=datetime.now()
        )
        
        self.benchmarks[name] = benchmark
        logger.info(f"創建效能基準: {name}")
        
        return benchmark
    
    async def collect_metrics_from_pool(self, pool_manager) -> ResourceMetrics:
        """從連線池收集效能指標"""
        try:
            # 獲取連線池統計
            pool_stats = pool_manager.get_pool_stats()
            performance_metrics = await pool_manager.get_performance_metrics()
            
            # 估算系統資源使用（可擴展為實際監控）
            memory_usage = len(pool_manager._connections) * 10.0  # 估算
            cpu_usage = min(pool_stats['active_connections'] * 5, 100)  # 估算
            
            return ResourceMetrics(
                timestamp=datetime.now(),
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                active_connections=pool_stats['active_connections'],
                idle_connections=pool_stats['idle_connections'],
                pending_requests=pool_stats['waiting_requests'],
                successful_operations=pool_stats['total_requests_served'],
                failed_operations=pool_stats['error_count'],
                average_response_time_ms=pool_stats['average_wait_time_ms'],
                p95_response_time_ms=performance_metrics.p95_response_time_ms,
                p99_response_time_ms=performance_metrics.p99_response_time_ms,
                throughput_ops_per_second=performance_metrics.throughput_rps,
                error_rate_percent=performance_metrics.error_rate
            )
            
        except Exception as e:
            logger.error(f"收集效能指標失敗: {e}")
            return self._create_empty_metrics()
    
    def analyze_performance_trends(self, hours: int = 1) -> Dict[str, Any]:
        """分析效能趨勢"""
        if not self.metrics_history:
            return {'status': 'insufficient_data'}
        
        # 獲取指定時間範圍的數據
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]
        
        if len(recent_metrics) < 10:
            return {'status': 'insufficient_recent_data'}
        
        # 計算趨勢指標
        response_times = [m.average_response_time_ms for m in recent_metrics]
        throughputs = [m.throughput_ops_per_second for m in recent_metrics]
        error_rates = [m.error_rate_percent for m in recent_metrics]
        
        return {
            'status': 'success',
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'trends': {
                'response_time': {
                    'current_avg': statistics.mean(response_times[-5:]) if len(response_times) >= 5 else 0,
                    'previous_avg': statistics.mean(response_times[-10:-5]) if len(response_times) >= 10 else 0,
                    'trend': self._calculate_trend(response_times),
                    'volatility': statistics.stdev(response_times) if len(response_times) > 1 else 0
                },
                'throughput': {
                    'current_avg': statistics.mean(throughputs[-5:]) if len(throughputs) >= 5 else 0,
                    'previous_avg': statistics.mean(throughputs[-10:-5]) if len(throughputs) >= 10 else 0,
                    'trend': self._calculate_trend(throughputs),
                    'volatility': statistics.stdev(throughputs) if len(throughputs) > 1 else 0
                },
                'error_rate': {
                    'current_avg': statistics.mean(error_rates[-5:]) if len(error_rates) >= 5 else 0,
                    'previous_avg': statistics.mean(error_rates[-10:-5]) if len(error_rates) >= 10 else 0,
                    'trend': self._calculate_trend(error_rates),
                    'spike_count': len([r for r in error_rates[-10:] if r > 5])
                }
            }
        }
    
    def generate_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """生成效能優化建議"""
        recommendations = []
        
        if not self.metrics_history:
            return [{'type': 'info', 'message': '需要更多數據來生成建議'}]
        
        recent_metrics = list(self.metrics_history)[-10:]  # 最近10個數據點
        
        # 分析響應時間
        avg_response_time = statistics.mean([m.average_response_time_ms for m in recent_metrics])
        if avg_response_time > 100:
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'metric': 'response_time',
                'current_value': avg_response_time,
                'message': f'響應時間過高 ({avg_response_time:.1f}ms)，建議增加連線池大小或優化查詢',
                'suggestions': [
                    '檢查慢查詢並進行優化',
                    '增加連線池最大大小',
                    '啟用連線複用',
                    '考慮實施查詢快取'
                ]
            })
        
        # 分析錯誤率
        avg_error_rate = statistics.mean([m.error_rate_percent for m in recent_metrics])
        if avg_error_rate > 5:
            recommendations.append({
                'type': 'reliability',
                'priority': 'critical',
                'metric': 'error_rate',
                'current_value': avg_error_rate,
                'message': f'錯誤率過高 ({avg_error_rate:.1f}%)，需要調查根本原因',
                'suggestions': [
                    '檢查錯誤日誌',
                    '驗證連線參數設定',
                    '增加重試機制',
                    '檢查資料庫健康狀況'
                ]
            })
        
        # 分析資源使用
        avg_memory = statistics.mean([m.memory_usage_mb for m in recent_metrics])
        if avg_memory > 500:
            recommendations.append({
                'type': 'resource',
                'priority': 'medium',
                'metric': 'memory_usage',
                'current_value': avg_memory,
                'message': f'記憶體使用較高 ({avg_memory:.1f}MB)，建議檢查連線洩漏',
                'suggestions': [
                    '檢查連線釋放邏輯',
                    '監控連線生命週期',
                    '設定合理的連線超時',
                    '定期清理不活躍連線'
                ]
            })
        
        # 分析吞吐量
        recent_throughputs = [m.throughput_ops_per_second for m in recent_metrics]
        if recent_throughputs and statistics.mean(recent_throughputs) < 10:
            recommendations.append({
                'type': 'performance',
                'priority': 'medium',
                'metric': 'throughput',
                'current_value': statistics.mean(recent_throughputs),
                'message': '吞吐量較低，考慮調整連線池配置',
                'suggestions': [
                    '增加最小連線數',
                    '調整連線獲取超時時間',
                    '並行處理更多請求',
                    '最佳化業務邏輯處理時間'
                ]
            })
        
        return recommendations
    
    async def run_performance_benchmark(
        self, 
        benchmark_name: str,
        test_duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """運行效能基準測試"""
        
        if benchmark_name not in self.benchmarks:
            raise ValueError(f"找不到基準測試: {benchmark_name}")
        
        benchmark = self.benchmarks[benchmark_name]
        logger.info(f"開始執行基準測試: {benchmark_name}")
        
        # 記錄測試開始時間
        start_time = datetime.now()
        
        # 收集測試期間的指標
        test_metrics = []
        end_time = start_time + timedelta(seconds=test_duration_seconds)
        
        while datetime.now() < end_time:
            if self.metrics_history:
                test_metrics.append(self.metrics_history[-1])
            await asyncio.sleep(1)
        
        if not test_metrics:
            return {'status': 'no_data', 'benchmark': benchmark_name}
        
        # 計算測試結果
        avg_response_time = statistics.mean([m.average_response_time_ms for m in test_metrics])
        avg_throughput = statistics.mean([m.throughput_ops_per_second for m in test_metrics])
        avg_error_rate = statistics.mean([m.error_rate_percent for m in test_metrics])
        
        # 計算效能分數
        response_time_score = min(benchmark.target_response_time_ms / max(avg_response_time, 1), 1) * 100
        throughput_score = min(avg_throughput / max(benchmark.target_throughput_ops, 1), 1) * 100
        error_rate_score = max(0, 100 - (avg_error_rate - benchmark.target_error_rate_percent) * 10)
        
        overall_score = (response_time_score + throughput_score + error_rate_score) / 3
        
        # 更新基準測試結果
        benchmark.last_measured_at = datetime.now()
        benchmark.current_performance_score = overall_score
        
        result = {
            'status': 'completed',
            'benchmark_name': benchmark_name,
            'test_duration_seconds': test_duration_seconds,
            'results': {
                'response_time_ms': {
                    'measured': avg_response_time,
                    'target': benchmark.target_response_time_ms,
                    'score': response_time_score
                },
                'throughput_ops': {
                    'measured': avg_throughput,
                    'target': benchmark.target_throughput_ops,
                    'score': throughput_score
                },
                'error_rate_percent': {
                    'measured': avg_error_rate,
                    'target': benchmark.target_error_rate_percent,
                    'score': error_rate_score
                },
                'overall_score': overall_score
            },
            'verdict': 'pass' if overall_score >= 80 else 'fail'
        }
        
        logger.info(f"基準測試完成: {benchmark_name}, 分數: {overall_score:.1f}")
        return result
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """獲取監控狀態"""
        uptime = datetime.now() - self.monitoring_start_time if self.monitoring_start_time else timedelta(0)
        
        return {
            'monitoring_active': self._monitoring_active,
            'uptime_seconds': uptime.total_seconds(),
            'collection_interval': self.collection_interval,
            'metrics_collected': len(self.metrics_history),
            'alerts_generated': self.total_alerts_generated,
            'benchmarks_configured': len(self.benchmarks),
            'alert_callbacks_registered': len(self._alert_callbacks)
        }
    
    # 私有方法
    
    async def _monitoring_loop(self):
        """監控主循環"""
        while self._monitoring_active:
            try:
                await asyncio.sleep(self.collection_interval)
                
                if not self._monitoring_active:
                    break
                
                # 這裡需要從外部傳入連線池管理器實例
                # 實際使用時需要調整
                logger.debug("監控循環執行中...")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"監控循環錯誤: {e}")
    
    async def _check_alerts(self, metrics: ResourceMetrics):
        """檢查並生成警報"""
        alerts = []
        
        # 檢查響應時間
        if metrics.average_response_time_ms > self.alert_thresholds['response_time_ms']['critical']:
            alerts.append(self._create_alert(
                'response_time_critical',
                'critical',
                f'響應時間過高: {metrics.average_response_time_ms:.1f}ms',
                'response_time_ms',
                metrics.average_response_time_ms,
                self.alert_thresholds['response_time_ms']['critical']
            ))
        elif metrics.average_response_time_ms > self.alert_thresholds['response_time_ms']['warning']:
            alerts.append(self._create_alert(
                'response_time_warning',
                'warning',
                f'響應時間偏高: {metrics.average_response_time_ms:.1f}ms',
                'response_time_ms',
                metrics.average_response_time_ms,
                self.alert_thresholds['response_time_ms']['warning']
            ))
        
        # 檢查錯誤率
        if metrics.error_rate_percent > self.alert_thresholds['error_rate_percent']['critical']:
            alerts.append(self._create_alert(
                'error_rate_critical',
                'critical',
                f'錯誤率過高: {metrics.error_rate_percent:.1f}%',
                'error_rate_percent',
                metrics.error_rate_percent,
                self.alert_thresholds['error_rate_percent']['critical']
            ))
        
        # 處理警報
        for alert in alerts:
            await self._handle_alert(alert)
    
    def _create_alert(
        self, 
        alert_id: str, 
        severity: str, 
        message: str, 
        metric_name: str,
        current_value: float,
        threshold_value: float
    ) -> PerformanceAlert:
        """創建效能警報"""
        return PerformanceAlert(
            alert_id=alert_id,
            severity=severity,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            timestamp=datetime.now()
        )
    
    async def _handle_alert(self, alert: PerformanceAlert):
        """處理效能警報"""
        # 存儲警報
        await self.data_store.store_alert(alert)
        
        # 添加到歷史記錄
        self.alert_history.append(alert)
        self.total_alerts_generated += 1
        
        # 調用回調函數
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"警報回調執行失敗: {e}")
        
        logger.warning(f"效能警報: [{alert.severity}] {alert.message}")
    
    def _create_empty_metrics(self) -> ResourceMetrics:
        """創建空的效能指標"""
        return ResourceMetrics(
            timestamp=datetime.now(),
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0,
            active_connections=0,
            idle_connections=0,
            pending_requests=0,
            successful_operations=0,
            failed_operations=0,
            average_response_time_ms=0.0,
            p95_response_time_ms=0.0,
            p99_response_time_ms=0.0,
            throughput_ops_per_second=0.0,
            error_rate_percent=0.0
        )
    
    def _calculate_trend(self, data: List[float]) -> str:
        """計算數據趨勢"""
        if len(data) < 4:
            return 'stable'
        
        mid_point = len(data) // 2
        first_half = statistics.mean(data[:mid_point])
        second_half = statistics.mean(data[mid_point:])
        
        if second_half > first_half * 1.1:
            return 'increasing'
        elif second_half < first_half * 0.9:
            return 'decreasing'
        else:
            return 'stable'