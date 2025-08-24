# 連線池監控服務
# Task ID: T2 - 高併發連線競爭修復 - 基礎設施監控支援
"""
連線池監控服務模組

這個模組為T2任務提供專業的連線池監控和統計功能：
- 實時連線使用統計和監控
- 連線競爭錯誤診斷和告警
- 動態調整建議和自動恢復機制
- 與現有監控系統的無縫整合
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError
from services.monitoring.models import HealthStatus, AlertLevel, PerformanceMetric
from services.monitoring.monitoring_service import MonitoringService


class ConnectionPoolStatus(Enum):
    """連線池狀態枚舉"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    SATURATED = "saturated"
    RECOVERING = "recovering"


class ConnectionEventType(Enum):
    """連線事件類型"""
    ACQUIRED = "acquired"
    RELEASED = "released"
    TIMEOUT = "timeout"
    ERROR = "error"
    CREATED = "created"
    DESTROYED = "destroyed"


@dataclass
class ConnectionPoolStats:
    """連線池統計信息"""
    timestamp: datetime
    active_connections: int
    max_connections: int
    waiting_requests: int
    total_acquired: int
    total_released: int
    timeout_count: int
    error_count: int
    avg_wait_time_ms: float
    p95_wait_time_ms: float
    pool_utilization: float  # 使用率百分比
    
    @property
    def status(self) -> ConnectionPoolStatus:
        """基於統計數據計算連線池狀態"""
        if self.error_count > 10:  # 過多錯誤
            return ConnectionPoolStatus.CRITICAL
        elif self.pool_utilization >= 95:  # 接近飽和
            return ConnectionPoolStatus.SATURATED
        elif self.pool_utilization >= 80 or self.timeout_count > 5:  # 高使用率或超時
            return ConnectionPoolStatus.WARNING
        else:
            return ConnectionPoolStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'active_connections': self.active_connections,
            'max_connections': self.max_connections,
            'waiting_requests': self.waiting_requests,
            'total_acquired': self.total_acquired,
            'total_released': self.total_released,
            'timeout_count': self.timeout_count,
            'error_count': self.error_count,
            'avg_wait_time_ms': self.avg_wait_time_ms,
            'p95_wait_time_ms': self.p95_wait_time_ms,
            'pool_utilization': self.pool_utilization,
            'status': self.status.value
        }


@dataclass 
class ConnectionEvent:
    """連線事件記錄"""
    event_id: str
    event_type: ConnectionEventType
    timestamp: datetime
    connection_id: Optional[str]
    wait_time_ms: Optional[float]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'connection_id': self.connection_id,
            'wait_time_ms': self.wait_time_ms,
            'error_message': self.error_message,
            'metadata': self.metadata or {}
        }


@dataclass
class DiagnosticResult:
    """診斷結果"""
    diagnostic_id: str
    timestamp: datetime
    pool_status: ConnectionPoolStatus
    issues_detected: List[str]
    recommendations: List[str]
    severity_score: int  # 1-100，100表示最嚴重
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'diagnostic_id': self.diagnostic_id,
            'timestamp': self.timestamp.isoformat(),
            'pool_status': self.pool_status.value,
            'issues_detected': self.issues_detected,
            'recommendations': self.recommendations,
            'severity_score': self.severity_score,
            'metadata': self.metadata
        }


class ConnectionPoolMonitor(BaseService):
    """連線池監控服務
    
    提供全面的連線池監控、診斷和自動恢復功能
    專門為T2任務的高併發連線競爭問題設計
    """
    
    def __init__(self, db_manager: DatabaseManager, monitoring_service: MonitoringService):
        super().__init__("ConnectionPoolMonitor")
        self.db = db_manager
        self.monitoring_service = monitoring_service
        self.logger = logging.getLogger(__name__)
        
        # 監控狀態
        self._is_monitoring = False
        self._stats_history: List[ConnectionPoolStats] = []
        self._events_buffer: List[ConnectionEvent] = []
        self._wait_times: List[float] = []
        
        # 統計計數器
        self._total_acquired = 0
        self._total_released = 0
        self._timeout_count = 0
        self._error_count = 0
        self._waiting_requests = 0
        
        # 配置參數
        self.config = {
            'stats_interval_seconds': 30,  # 統計間隔
            'history_retention_minutes': 60,  # 歷史數據保留時間
            'diagnostic_interval_minutes': 5,  # 診斷間隔
            'max_wait_time_threshold_ms': 1000,  # 等待時間閾值
            'error_rate_threshold': 0.05,  # 錯誤率閾值（5%）
            'utilization_warning_threshold': 0.8,  # 使用率警告閾值
            'utilization_critical_threshold': 0.95  # 使用率危險閾值
        }
        
        # 診斷規則
        self._diagnostic_rules = [
            self._diagnose_high_utilization,
            self._diagnose_frequent_timeouts,
            self._diagnose_error_rate,
            self._diagnose_wait_time_anomalies,
            self._diagnose_connection_leaks
        ]
        
    async def initialize(self) -> None:
        """初始化連線池監控服務"""
        try:
            await self._create_monitoring_tables()
            await self._load_configuration()
            self.logger.info("連線池監控服務初始化完成")
        except Exception as e:
            self.logger.error(f"連線池監控服務初始化失敗: {e}")
            raise ServiceError("連線池監控服務初始化失敗", "initialize", str(e))
    
    async def _create_monitoring_tables(self) -> None:
        """創建監控相關資料表"""
        # 連線池統計表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS connection_pool_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                active_connections INTEGER NOT NULL,
                max_connections INTEGER NOT NULL,
                waiting_requests INTEGER NOT NULL,
                total_acquired INTEGER NOT NULL,
                total_released INTEGER NOT NULL,
                timeout_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                avg_wait_time_ms REAL NOT NULL,
                p95_wait_time_ms REAL NOT NULL,
                pool_utilization REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        
        # 連線事件表  
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS connection_pool_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                connection_id TEXT,
                wait_time_ms REAL,
                error_message TEXT,
                metadata TEXT
            )
        """)
        
        # 診斷結果表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS connection_pool_diagnostics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagnostic_id TEXT UNIQUE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                pool_status TEXT NOT NULL,
                issues_detected TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                severity_score INTEGER NOT NULL,
                metadata TEXT
            )
        """)
        
        # 配置表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS connection_pool_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
    
    async def start_monitoring(self) -> None:
        """開始監控連線池"""
        if self._is_monitoring:
            self.logger.warning("連線池監控已在運行中")
            return
        
        self._is_monitoring = True
        self.logger.info("開始連線池監控")
        
        # 啟動監控任務
        asyncio.create_task(self._stats_collection_loop())
        asyncio.create_task(self._diagnostic_loop())
        asyncio.create_task(self._event_processing_loop())
    
    async def stop_monitoring(self) -> None:
        """停止監控"""
        self._is_monitoring = False
        self.logger.info("連線池監控已停止")
    
    def record_connection_acquired(self, connection_id: str, wait_time_ms: float) -> None:
        """記錄連線取得事件"""
        self._total_acquired += 1
        self._wait_times.append(wait_time_ms)
        
        event = ConnectionEvent(
            event_id=str(uuid.uuid4()),
            event_type=ConnectionEventType.ACQUIRED,
            timestamp=datetime.now(),
            connection_id=connection_id,
            wait_time_ms=wait_time_ms
        )
        self._events_buffer.append(event)
    
    def record_connection_released(self, connection_id: str) -> None:
        """記錄連線釋放事件"""
        self._total_released += 1
        
        event = ConnectionEvent(
            event_id=str(uuid.uuid4()),
            event_type=ConnectionEventType.RELEASED,
            timestamp=datetime.now(),
            connection_id=connection_id
        )
        self._events_buffer.append(event)
    
    def record_connection_timeout(self, wait_time_ms: float) -> None:
        """記錄連線超時事件"""
        self._timeout_count += 1
        
        event = ConnectionEvent(
            event_id=str(uuid.uuid4()),
            event_type=ConnectionEventType.TIMEOUT,
            timestamp=datetime.now(),
            wait_time_ms=wait_time_ms
        )
        self._events_buffer.append(event)
    
    def record_connection_error(self, error_message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """記錄連線錯誤事件"""
        self._error_count += 1
        
        event = ConnectionEvent(
            event_id=str(uuid.uuid4()),
            event_type=ConnectionEventType.ERROR,
            timestamp=datetime.now(),
            error_message=error_message,
            metadata=metadata
        )
        self._events_buffer.append(event)
    
    def set_waiting_requests(self, count: int) -> None:
        """設置等待中的請求數量"""
        self._waiting_requests = count
    
    async def _stats_collection_loop(self) -> None:
        """統計收集循環"""
        while self._is_monitoring:
            try:
                await self._collect_and_save_stats()
                await asyncio.sleep(self.config['stats_interval_seconds'])
            except Exception as e:
                self.logger.error(f"統計收集循環錯誤: {e}")
                await asyncio.sleep(30)  # 錯誤時等待30秒再重試
    
    async def _diagnostic_loop(self) -> None:
        """診斷循環"""
        while self._is_monitoring:
            try:
                await self._run_diagnostics()
                await asyncio.sleep(self.config['diagnostic_interval_minutes'] * 60)
            except Exception as e:
                self.logger.error(f"診斷循環錯誤: {e}")
                await asyncio.sleep(300)  # 錯誤時等待5分鐘再重試
    
    async def _event_processing_loop(self) -> None:
        """事件處理循環"""
        while self._is_monitoring:
            try:
                await self._process_events_buffer()
                await asyncio.sleep(10)  # 每10秒處理一次事件緩衝區
            except Exception as e:
                self.logger.error(f"事件處理循環錯誤: {e}")
                await asyncio.sleep(30)
    
    async def _collect_and_save_stats(self) -> None:
        """收集並保存統計信息"""
        try:
            # 從連線池獲取當前狀態
            pool_stats = await self._get_current_pool_stats()
            
            # 保存到歷史記錄
            self._stats_history.append(pool_stats)
            
            # 清理舊的歷史數據
            cutoff_time = datetime.now() - timedelta(minutes=self.config['history_retention_minutes'])
            self._stats_history = [s for s in self._stats_history if s.timestamp > cutoff_time]
            
            # 保存到資料庫
            await self._save_stats_to_db(pool_stats)
            
            # 檢查是否需要發送警報
            await self._check_and_send_alerts(pool_stats)
            
        except Exception as e:
            self.logger.error(f"統計收集失敗: {e}")
    
    async def _get_current_pool_stats(self) -> ConnectionPoolStats:
        """獲取當前連線池統計信息"""
        # 從資料庫管理器獲取連線池狀態
        pool = self.db.connection_pool
        active_connections = sum(pool.connection_counts.values())
        max_connections = pool.max_connections
        
        # 計算等待時間統計
        avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0
        p95_wait_time_ms = self._calculate_p95(self._wait_times) if self._wait_times else 0
        
        # 計算使用率
        pool_utilization = (active_connections / max_connections) * 100 if max_connections > 0 else 0
        
        stats = ConnectionPoolStats(
            timestamp=datetime.now(),
            active_connections=active_connections,
            max_connections=max_connections,
            waiting_requests=self._waiting_requests,
            total_acquired=self._total_acquired,
            total_released=self._total_released,
            timeout_count=self._timeout_count,
            error_count=self._error_count,
            avg_wait_time_ms=avg_wait_time_ms,
            p95_wait_time_ms=p95_wait_time_ms,
            pool_utilization=pool_utilization
        )
        
        # 清空等待時間記錄，避免記憶體增長
        if len(self._wait_times) > 1000:
            self._wait_times = self._wait_times[-500:]  # 保留最近500個記錄
        
        return stats
    
    def _calculate_p95(self, values: List[float]) -> float:
        """計算95百分位數"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * 0.95)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    async def _save_stats_to_db(self, stats: ConnectionPoolStats) -> None:
        """保存統計信息到資料庫"""
        await self.db.execute("""
            INSERT INTO connection_pool_stats (
                timestamp, active_connections, max_connections, waiting_requests,
                total_acquired, total_released, timeout_count, error_count,
                avg_wait_time_ms, p95_wait_time_ms, pool_utilization, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stats.timestamp, stats.active_connections, stats.max_connections, 
            stats.waiting_requests, stats.total_acquired, stats.total_released,
            stats.timeout_count, stats.error_count, stats.avg_wait_time_ms,
            stats.p95_wait_time_ms, stats.pool_utilization, stats.status.value
        ))
    
    async def _process_events_buffer(self) -> None:
        """處理事件緩衝區"""
        if not self._events_buffer:
            return
        
        # 批量保存事件到資料庫
        events_to_save = self._events_buffer.copy()
        self._events_buffer.clear()
        
        for event in events_to_save:
            await self.db.execute("""
                INSERT INTO connection_pool_events (
                    event_id, event_type, timestamp, connection_id,
                    wait_time_ms, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.event_type.value, event.timestamp,
                event.connection_id, event.wait_time_ms, event.error_message,
                json.dumps(event.metadata) if event.metadata else None
            ))
    
    async def _check_and_send_alerts(self, stats: ConnectionPoolStats) -> None:
        """檢查並發送警報"""
        alerts = []
        
        # 高使用率警報
        if stats.pool_utilization >= self.config['utilization_critical_threshold'] * 100:
            alerts.append({
                'level': AlertLevel.CRITICAL,
                'title': '連線池使用率危險',
                'message': f'連線池使用率達到 {stats.pool_utilization:.1f}%，超過危險閾值'
            })
        elif stats.pool_utilization >= self.config['utilization_warning_threshold'] * 100:
            alerts.append({
                'level': AlertLevel.WARNING,
                'title': '連線池使用率偏高',
                'message': f'連線池使用率達到 {stats.pool_utilization:.1f}%，超過警告閾值'
            })
        
        # 超時警報
        if stats.timeout_count > 10:
            alerts.append({
                'level': AlertLevel.ERROR,
                'title': '連線超時頻繁',
                'message': f'檢測到 {stats.timeout_count} 次連線超時'
            })
        
        # 錯誤率警報
        total_requests = stats.total_acquired + stats.error_count
        if total_requests > 0:
            error_rate = stats.error_count / total_requests
            if error_rate > self.config['error_rate_threshold']:
                alerts.append({
                    'level': AlertLevel.ERROR,
                    'title': '連線錯誤率過高',
                    'message': f'連線錯誤率達到 {error_rate:.2%}，超過閾值'
                })
        
        # 發送警報
        for alert_data in alerts:
            await self.monitoring_service._send_alert(alert_data)
    
    async def _run_diagnostics(self) -> None:
        """運行診斷檢查"""
        try:
            issues = []
            recommendations = []
            severity_score = 0
            
            # 獲取最新統計
            latest_stats = self._stats_history[-1] if self._stats_history else None
            if not latest_stats:
                return
            
            # 運行所有診斷規則
            for diagnostic_rule in self._diagnostic_rules:
                try:
                    rule_result = await diagnostic_rule(latest_stats)
                    if rule_result:
                        issues.extend(rule_result.get('issues', []))
                        recommendations.extend(rule_result.get('recommendations', []))
                        severity_score = max(severity_score, rule_result.get('severity', 0))
                except Exception as e:
                    self.logger.error(f"診斷規則執行失敗: {e}")
            
            # 創建診斷結果
            if issues:
                diagnostic = DiagnosticResult(
                    diagnostic_id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    pool_status=latest_stats.status,
                    issues_detected=issues,
                    recommendations=recommendations,
                    severity_score=severity_score,
                    metadata={'stats': latest_stats.to_dict()}
                )
                
                await self._save_diagnostic_result(diagnostic)
                
                # 如果嚴重度高，發送警報
                if severity_score >= 70:
                    await self._send_diagnostic_alert(diagnostic)
        
        except Exception as e:
            self.logger.error(f"診斷檢查失敗: {e}")
    
    async def _diagnose_high_utilization(self, stats: ConnectionPoolStats) -> Optional[Dict[str, Any]]:
        """診斷高使用率問題"""
        if stats.pool_utilization >= 90:
            return {
                'issues': ['連線池使用率過高，可能影響效能'],
                'recommendations': [
                    '考慮增加最大連線數',
                    '檢查是否有連線洩漏',
                    '優化查詢效率減少連線持有時間'
                ],
                'severity': 80
            }
        elif stats.pool_utilization >= 75:
            return {
                'issues': ['連線池使用率偏高'],
                'recommendations': ['監控趨勢，準備擴容'],
                'severity': 50
            }
        return None
    
    async def _diagnose_frequent_timeouts(self, stats: ConnectionPoolStats) -> Optional[Dict[str, Any]]:
        """診斷頻繁超時問題"""
        if stats.timeout_count > 20:
            return {
                'issues': ['連線取得超時頻繁'],
                'recommendations': [
                    '增加連線池大小',
                    '檢查資料庫性能',
                    '優化應用程式連線使用模式'
                ],
                'severity': 75
            }
        elif stats.timeout_count > 10:
            return {
                'issues': ['偶發連線超時'],
                'recommendations': ['持續監控超時趨勢'],
                'severity': 40
            }
        return None
    
    async def _diagnose_error_rate(self, stats: ConnectionPoolStats) -> Optional[Dict[str, Any]]:
        """診斷錯誤率問題"""
        total_requests = stats.total_acquired + stats.error_count
        if total_requests > 0:
            error_rate = stats.error_count / total_requests
            if error_rate > 0.1:  # 10% 錯誤率
                return {
                    'issues': [f'連線錯誤率過高: {error_rate:.2%}'],
                    'recommendations': [
                        '檢查資料庫連線穩定性',
                        '檢查網絡連通性',
                        '檢查資料庫資源使用情況'
                    ],
                    'severity': 85
                }
            elif error_rate > 0.05:  # 5% 錯誤率
                return {
                    'issues': [f'連線錯誤率偏高: {error_rate:.2%}'],
                    'recommendations': ['加強錯誤監控和日誌分析'],
                    'severity': 60
                }
        return None
    
    async def _diagnose_wait_time_anomalies(self, stats: ConnectionPoolStats) -> Optional[Dict[str, Any]]:
        """診斷等待時間異常"""
        if stats.p95_wait_time_ms > 2000:  # P95 等待時間超過2秒
            return {
                'issues': ['連線等待時間過長'],
                'recommendations': [
                    '增加連線池大小',
                    '優化資料庫查詢性能',
                    '檢查是否有長時間運行的事務'
                ],
                'severity': 70
            }
        elif stats.avg_wait_time_ms > 1000:  # 平均等待時間超過1秒
            return {
                'issues': ['連線平均等待時間較長'],
                'recommendations': ['監控等待時間趨勢'],
                'severity': 45
            }
        return None
    
    async def _diagnose_connection_leaks(self, stats: ConnectionPoolStats) -> Optional[Dict[str, Any]]:
        """診斷連線洩漏問題"""
        if stats.total_acquired > 0 and stats.total_released > 0:
            leak_rate = (stats.total_acquired - stats.total_released) / stats.total_acquired
            if leak_rate > 0.1:  # 10% 以上的連線未釋放
                return {
                    'issues': ['疑似連線洩漏'],
                    'recommendations': [
                        '檢查應用程式碼是否正確釋放連線',
                        '檢查是否有異常中斷的事務',
                        '啟用連線超時自動釋放機制'
                    ],
                    'severity': 90
                }
        return None
    
    async def _save_diagnostic_result(self, diagnostic: DiagnosticResult) -> None:
        """保存診斷結果"""
        await self.db.execute("""
            INSERT INTO connection_pool_diagnostics (
                diagnostic_id, timestamp, pool_status, issues_detected,
                recommendations, severity_score, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            diagnostic.diagnostic_id, diagnostic.timestamp, diagnostic.pool_status.value,
            json.dumps(diagnostic.issues_detected), json.dumps(diagnostic.recommendations),
            diagnostic.severity_score, json.dumps(diagnostic.metadata)
        ))
    
    async def _send_diagnostic_alert(self, diagnostic: DiagnosticResult) -> None:
        """發送診斷警報"""
        level = AlertLevel.CRITICAL if diagnostic.severity_score >= 80 else AlertLevel.WARNING
        
        alert_data = {
            'level': level,
            'title': '連線池診斷警報',
            'message': f'檢測到 {len(diagnostic.issues_detected)} 個問題，嚴重度: {diagnostic.severity_score}',
            'metadata': diagnostic.to_dict()
        }
        
        await self.monitoring_service._send_alert(alert_data)
    
    async def get_real_time_stats(self) -> Optional[ConnectionPoolStats]:
        """獲取實時統計信息"""
        return await self._get_current_pool_stats()
    
    async def get_stats_history(self, hours: int = 24) -> List[ConnectionPoolStats]:
        """獲取歷史統計信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        rows = await self.db.fetchall("""
            SELECT timestamp, active_connections, max_connections, waiting_requests,
                   total_acquired, total_released, timeout_count, error_count,
                   avg_wait_time_ms, p95_wait_time_ms, pool_utilization, status
            FROM connection_pool_stats
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """, (cutoff_time,))
        
        stats_list = []
        for row in rows:
            stats = ConnectionPoolStats(
                timestamp=datetime.fromisoformat(row[0]),
                active_connections=row[1],
                max_connections=row[2],
                waiting_requests=row[3],
                total_acquired=row[4],
                total_released=row[5],
                timeout_count=row[6],
                error_count=row[7],
                avg_wait_time_ms=row[8],
                p95_wait_time_ms=row[9],
                pool_utilization=row[10]
            )
            stats_list.append(stats)
        
        return stats_list
    
    async def get_recent_diagnostics(self, hours: int = 24) -> List[DiagnosticResult]:
        """獲取最近的診斷結果"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        rows = await self.db.fetchall("""
            SELECT diagnostic_id, timestamp, pool_status, issues_detected,
                   recommendations, severity_score, metadata
            FROM connection_pool_diagnostics
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """, (cutoff_time,))
        
        diagnostics = []
        for row in rows:
            diagnostic = DiagnosticResult(
                diagnostic_id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                pool_status=ConnectionPoolStatus(row[2]),
                issues_detected=json.loads(row[3]),
                recommendations=json.loads(row[4]),
                severity_score=row[5],
                metadata=json.loads(row[6])
            )
            diagnostics.append(diagnostic)
        
        return diagnostics
    
    async def _load_configuration(self) -> None:
        """載入配置"""
        try:
            config_rows = await self.db.fetchall("SELECT key, value FROM connection_pool_config")
            for key, value in config_rows:
                if key in self.config:
                    self.config[key] = json.loads(value)
        except Exception as e:
            self.logger.warning(f"載入連線池監控配置失敗，使用預設配置: {e}")
    
    async def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置"""
        for key, value in config.items():
            if key in self.config:
                self.config[key] = value
                await self.db.execute("""
                    INSERT OR REPLACE INTO connection_pool_config (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, json.dumps(value), datetime.now()))
        
        self.logger.info("連線池監控配置已更新")
    
    async def cleanup_old_data(self, retention_days: int = 7) -> Dict[str, Any]:
        """清理過期數據"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # 清理統計數據
        stats_deleted = await self.db.execute("""
            DELETE FROM connection_pool_stats WHERE timestamp < ?
        """, (cutoff_date,))
        
        # 清理事件數據
        events_deleted = await self.db.execute("""
            DELETE FROM connection_pool_events WHERE timestamp < ?
        """, (cutoff_date,))
        
        # 清理診斷數據
        diagnostics_deleted = await self.db.execute("""
            DELETE FROM connection_pool_diagnostics WHERE timestamp < ?
        """, (cutoff_date,))
        
        return {
            'stats_deleted': stats_deleted,
            'events_deleted': events_deleted,
            'diagnostics_deleted': diagnostics_deleted,
            'cutoff_date': cutoff_date.isoformat()
        }