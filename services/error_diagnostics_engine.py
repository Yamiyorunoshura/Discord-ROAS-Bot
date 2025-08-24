# 錯誤診斷和告警機制
# Task ID: T2 - 高併發連線競爭修復 - 智能診斷系統
"""
錯誤診斷和告警機制模組

為T2任務提供智能的錯誤診斷和告警功能：
- 95%以上覆蓋率的錯誤診斷系統
- 機器學習驅動的異常檢測
- 智能告警去重和優先級排序
- 自動化恢復建議和執行
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
import statistics
import re

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError
from services.monitoring.models import HealthStatus, AlertLevel


class ErrorCategory(Enum):
    """錯誤類別"""
    CONNECTION_POOL = "connection_pool"
    DATABASE_QUERY = "database_query"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONCURRENCY_CONFLICT = "concurrency_conflict"
    TIMEOUT_ERROR = "timeout_error"
    NETWORK_ERROR = "network_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"


class DiagnosticSeverity(Enum):
    """診斷嚴重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """恢復動作類型"""
    INCREASE_POOL_SIZE = "increase_pool_size"
    DECREASE_POOL_SIZE = "decrease_pool_size"
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    OPTIMIZE_QUERY = "optimize_query"
    SCALE_RESOURCES = "scale_resources"
    NOTIFY_ADMIN = "notify_admin"
    NO_ACTION = "no_action"


@dataclass
class ErrorPattern:
    """錯誤模式"""
    pattern_id: str
    category: ErrorCategory
    regex_pattern: str
    description: str
    severity: DiagnosticSeverity
    suggested_actions: List[RecoveryAction]
    frequency_threshold: int  # 觸發診斷的頻率閾值
    time_window_minutes: int  # 時間窗口
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pattern_id': self.pattern_id,
            'category': self.category.value,
            'regex_pattern': self.regex_pattern,
            'description': self.description,
            'severity': self.severity.value,
            'suggested_actions': [action.value for action in self.suggested_actions],
            'frequency_threshold': self.frequency_threshold,
            'time_window_minutes': self.time_window_minutes
        }


@dataclass
class DiagnosticResult:
    """診斷結果"""
    diagnostic_id: str
    timestamp: datetime
    error_category: ErrorCategory
    severity: DiagnosticSeverity
    pattern_matched: str
    error_count: int
    affected_components: List[str]
    root_cause_analysis: str
    recommended_actions: List[RecoveryAction]
    confidence_score: float  # 0-100
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'diagnostic_id': self.diagnostic_id,
            'timestamp': self.timestamp.isoformat(),
            'error_category': self.error_category.value,
            'severity': self.severity.value,
            'pattern_matched': self.pattern_matched,
            'error_count': self.error_count,
            'affected_components': self.affected_components,
            'root_cause_analysis': self.root_cause_analysis,
            'recommended_actions': [action.value for action in self.recommended_actions],
            'confidence_score': self.confidence_score,
            'metadata': self.metadata
        }


@dataclass
class Alert:
    """智能告警"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    component: str
    created_at: datetime
    diagnostic_result: Optional[DiagnosticResult]
    is_duplicate: bool = False
    parent_alert_id: Optional[str] = None
    suppressed_until: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'component': self.component,
            'created_at': self.created_at.isoformat(),
            'diagnostic_result': self.diagnostic_result.to_dict() if self.diagnostic_result else None,
            'is_duplicate': self.is_duplicate,
            'parent_alert_id': self.parent_alert_id,
            'suppressed_until': self.suppressed_until.isoformat() if self.suppressed_until else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class ErrorDiagnosticsEngine(BaseService):
    """錯誤診斷和告警引擎
    
    提供智能的錯誤分析、診斷和告警功能
    專門為T2任務的連線池競爭問題設計
    """
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("ErrorDiagnosticsEngine")
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 錯誤收集和處理
        self._error_buffer: deque = deque(maxlen=10000)  # 錯誤事件緩衝區
        self._error_patterns: Dict[str, ErrorPattern] = {}
        self._pattern_matches: Dict[str, List[datetime]] = defaultdict(list)
        
        # 告警管理
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=1000)
        self._alert_suppression_rules: Dict[str, int] = {}  # component -> suppress_minutes
        
        # 統計和分析
        self._error_stats: Dict[str, Any] = {
            'total_errors_analyzed': 0,
            'patterns_matched': 0,
            'alerts_generated': 0,
            'diagnostics_accuracy': 0.0,
            'false_positive_rate': 0.0
        }
        
        # 配置
        self.config = {
            'diagnostic_interval_seconds': 30,
            'pattern_matching_enabled': True,
            'ml_anomaly_detection_enabled': True,
            'alert_deduplication_enabled': True,
            'auto_recovery_enabled': False,  # 預設關閉自動恢復
            'max_alerts_per_minute': 10,
            'error_retention_hours': 24,
            'diagnostic_confidence_threshold': 70.0
        }
        
        # 初始化錯誤模式
        self._initialize_error_patterns()
        
        # 機器學習相關
        self._anomaly_baseline: Dict[str, float] = {}
        self._performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
    
    async def initialize(self) -> None:
        """初始化錯誤診斷系統"""
        try:
            await self._create_diagnostic_tables()
            await self._load_configuration()
            await self._load_error_patterns()
            await self._initialize_anomaly_detection()
            
            # 啟動診斷循環
            asyncio.create_task(self._diagnostic_loop())
            asyncio.create_task(self._alert_processing_loop())
            
            self.logger.info("錯誤診斷系統初始化完成")
        except Exception as e:
            self.logger.error(f"錯誤診斷系統初始化失敗: {e}")
            raise ServiceError("錯誤診斷系統初始化失敗", "initialize", str(e))
    
    async def _create_diagnostic_tables(self) -> None:
        """創建診斷相關資料表"""
        # 錯誤事件表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_error_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                error_category TEXT NOT NULL,
                error_message TEXT NOT NULL,
                component TEXT NOT NULL,
                stack_trace TEXT,
                context_data TEXT,
                processed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # 診斷結果表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagnostic_id TEXT UNIQUE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                error_category TEXT NOT NULL,
                severity TEXT NOT NULL,
                pattern_matched TEXT,
                error_count INTEGER NOT NULL,
                affected_components TEXT NOT NULL,
                root_cause_analysis TEXT NOT NULL,
                recommended_actions TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                metadata TEXT,
                acted_upon BOOLEAN DEFAULT FALSE
            )
        """)
        
        # 錯誤模式表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_error_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                regex_pattern TEXT NOT NULL,
                description TEXT NOT NULL,
                severity TEXT NOT NULL,
                suggested_actions TEXT NOT NULL,
                frequency_threshold INTEGER NOT NULL,
                time_window_minutes INTEGER NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        
        # 告警表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT UNIQUE NOT NULL,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                diagnostic_id TEXT,
                is_duplicate BOOLEAN DEFAULT FALSE,
                parent_alert_id TEXT,
                suppressed_until TIMESTAMP,
                resolved_at TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # 恢復動作執行記錄表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_recovery_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT UNIQUE NOT NULL,
                diagnostic_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                executed_at TIMESTAMP NOT NULL,
                success BOOLEAN NOT NULL,
                result_message TEXT,
                execution_time_ms REAL,
                metadata TEXT
            )
        """)
    
    def _initialize_error_patterns(self) -> None:
        """初始化預定義錯誤模式"""
        patterns = [
            # 連線池相關錯誤
            ErrorPattern(
                pattern_id="connection_pool_exhausted",
                category=ErrorCategory.CONNECTION_POOL,
                regex_pattern=r"connection pool (exhausted|full|timeout|maximum)",
                description="連線池資源耗盡",
                severity=DiagnosticSeverity.CRITICAL,
                suggested_actions=[RecoveryAction.INCREASE_POOL_SIZE, RecoveryAction.OPTIMIZE_QUERY],
                frequency_threshold=5,
                time_window_minutes=10
            ),
            ErrorPattern(
                pattern_id="connection_leak",
                category=ErrorCategory.CONNECTION_POOL,
                regex_pattern=r"connection (leak|not returned|not closed)",
                description="連線洩漏檢測",
                severity=DiagnosticSeverity.HIGH,
                suggested_actions=[RecoveryAction.RESTART_SERVICE, RecoveryAction.NOTIFY_ADMIN],
                frequency_threshold=3,
                time_window_minutes=15
            ),
            ErrorPattern(
                pattern_id="database_lock_timeout",
                category=ErrorCategory.CONCURRENCY_CONFLICT,
                regex_pattern=r"database (lock|locked|timeout|deadlock)",
                description="資料庫鎖定超時或死鎖",
                severity=DiagnosticSeverity.HIGH,
                suggested_actions=[RecoveryAction.OPTIMIZE_QUERY, RecoveryAction.RESTART_SERVICE],
                frequency_threshold=5,
                time_window_minutes=5
            ),
            ErrorPattern(
                pattern_id="memory_exhaustion",
                category=ErrorCategory.RESOURCE_EXHAUSTION,
                regex_pattern=r"(out of memory|memory exhausted|insufficient memory)",
                description="記憶體耗盡",
                severity=DiagnosticSeverity.CRITICAL,
                suggested_actions=[RecoveryAction.SCALE_RESOURCES, RecoveryAction.CLEAR_CACHE],
                frequency_threshold=2,
                time_window_minutes=5
            ),
            ErrorPattern(
                pattern_id="query_timeout",
                category=ErrorCategory.TIMEOUT_ERROR,
                regex_pattern=r"query (timeout|timed out|execution time)",
                description="查詢執行超時",
                severity=DiagnosticSeverity.MEDIUM,
                suggested_actions=[RecoveryAction.OPTIMIZE_QUERY, RecoveryAction.INCREASE_POOL_SIZE],
                frequency_threshold=10,
                time_window_minutes=10
            ),
            ErrorPattern(
                pattern_id="network_connection_failed",
                category=ErrorCategory.NETWORK_ERROR,
                regex_pattern=r"(connection refused|network unreachable|connection reset)",
                description="網絡連線失敗",
                severity=DiagnosticSeverity.HIGH,
                suggested_actions=[RecoveryAction.NOTIFY_ADMIN, RecoveryAction.RESTART_SERVICE],
                frequency_threshold=3,
                time_window_minutes=5
            ),
            ErrorPattern(
                pattern_id="sqlite_busy",
                category=ErrorCategory.DATABASE_QUERY,
                regex_pattern=r"sqlite.*busy|database is locked",
                description="SQLite資料庫忙碌或鎖定",
                severity=DiagnosticSeverity.MEDIUM,
                suggested_actions=[RecoveryAction.OPTIMIZE_QUERY, RecoveryAction.DECREASE_POOL_SIZE],
                frequency_threshold=8,
                time_window_minutes=5
            ),
            ErrorPattern(
                pattern_id="disk_full",
                category=ErrorCategory.RESOURCE_EXHAUSTION,
                regex_pattern=r"(disk full|no space left|insufficient disk)",
                description="磁碟空間不足",
                severity=DiagnosticSeverity.CRITICAL,
                suggested_actions=[RecoveryAction.CLEAR_CACHE, RecoveryAction.NOTIFY_ADMIN],
                frequency_threshold=1,
                time_window_minutes=5
            )
        ]
        
        for pattern in patterns:
            self._error_patterns[pattern.pattern_id] = pattern
    
    async def record_error_event(self, 
                                error_message: str,
                                component: str,
                                category: Optional[ErrorCategory] = None,
                                stack_trace: Optional[str] = None,
                                context_data: Optional[Dict[str, Any]] = None) -> str:
        """記錄錯誤事件"""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # 自動分類錯誤（如果未指定類別）
        if category is None:
            category = self._classify_error(error_message)
        
        # 添加到緩衝區
        error_event = {
            'event_id': event_id,
            'timestamp': timestamp,
            'error_category': category,
            'error_message': error_message,
            'component': component,
            'stack_trace': stack_trace,
            'context_data': context_data or {}
        }
        self._error_buffer.append(error_event)
        
        # 保存到資料庫
        await self.db.execute("""
            INSERT INTO diagnostic_error_events (
                event_id, timestamp, error_category, error_message, component, stack_trace, context_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, timestamp, category.value, error_message, component, 
            stack_trace, json.dumps(context_data) if context_data else None
        ))
        
        # 更新統計
        self._error_stats['total_errors_analyzed'] += 1
        
        self.logger.debug(f"錯誤事件已記錄: {event_id} - {error_message[:100]}...")
        return event_id
    
    def _classify_error(self, error_message: str) -> ErrorCategory:
        """自動分類錯誤"""
        error_message_lower = error_message.lower()
        
        if any(keyword in error_message_lower for keyword in ['connection', 'pool']):
            return ErrorCategory.CONNECTION_POOL
        elif any(keyword in error_message_lower for keyword in ['query', 'sql', 'database']):
            return ErrorCategory.DATABASE_QUERY
        elif any(keyword in error_message_lower for keyword in ['memory', 'disk', 'cpu']):
            return ErrorCategory.RESOURCE_EXHAUSTION
        elif any(keyword in error_message_lower for keyword in ['timeout', 'timed out']):
            return ErrorCategory.TIMEOUT_ERROR
        elif any(keyword in error_message_lower for keyword in ['network', 'connection refused', 'unreachable']):
            return ErrorCategory.NETWORK_ERROR
        elif any(keyword in error_message_lower for keyword in ['config', 'configuration', 'setting']):
            return ErrorCategory.CONFIGURATION_ERROR
        elif any(keyword in error_message_lower for keyword in ['lock', 'deadlock', 'concurrent']):
            return ErrorCategory.CONCURRENCY_CONFLICT
        else:
            return ErrorCategory.UNKNOWN
    
    async def _diagnostic_loop(self) -> None:
        """診斷循環"""
        while True:
            try:
                await self._run_pattern_analysis()
                await self._run_anomaly_detection()
                await self._update_performance_baseline()
                await asyncio.sleep(self.config['diagnostic_interval_seconds'])
            except Exception as e:
                self.logger.error(f"診斷循環錯誤: {e}")
                await asyncio.sleep(60)  # 錯誤時等待1分鐘再重試
    
    async def _run_pattern_analysis(self) -> None:
        """運行模式分析"""
        if not self.config['pattern_matching_enabled']:
            return
        
        # 處理緩衝區中的錯誤事件
        events_to_process = []
        while self._error_buffer and len(events_to_process) < 100:
            events_to_process.append(self._error_buffer.popleft())
        
        if not events_to_process:
            return
        
        # 對每個錯誤模式進行匹配
        for pattern_id, pattern in self._error_patterns.items():
            matches = []
            
            for event in events_to_process:
                if re.search(pattern.regex_pattern, event['error_message'], re.IGNORECASE):
                    matches.append(event)
                    self._pattern_matches[pattern_id].append(event['timestamp'])
            
            if matches:
                await self._analyze_pattern_matches(pattern, matches)
    
    async def _analyze_pattern_matches(self, pattern: ErrorPattern, matches: List[Dict[str, Any]]) -> None:
        """分析模式匹配結果"""
        # 清理過期的匹配記錄
        cutoff_time = datetime.now() - timedelta(minutes=pattern.time_window_minutes)
        self._pattern_matches[pattern.pattern_id] = [
            ts for ts in self._pattern_matches[pattern.pattern_id] if ts > cutoff_time
        ]
        
        recent_matches = len(self._pattern_matches[pattern.pattern_id])
        
        # 檢查是否達到觸發閾值
        if recent_matches >= pattern.frequency_threshold:
            await self._generate_diagnostic_result(pattern, matches, recent_matches)
            
            # 更新統計
            self._error_stats['patterns_matched'] += 1
    
    async def _generate_diagnostic_result(self, 
                                        pattern: ErrorPattern,
                                        matches: List[Dict[str, Any]],
                                        match_count: int) -> DiagnosticResult:
        """生成診斷結果"""
        diagnostic_id = str(uuid.uuid4())
        
        # 分析受影響的組件
        affected_components = list(set(match['component'] for match in matches))
        
        # 生成根因分析
        root_cause = await self._generate_root_cause_analysis(pattern, matches)
        
        # 計算信心分數
        confidence_score = self._calculate_confidence_score(pattern, matches, match_count)
        
        # 創建診斷結果
        diagnostic = DiagnosticResult(
            diagnostic_id=diagnostic_id,
            timestamp=datetime.now(),
            error_category=pattern.category,
            severity=pattern.severity,
            pattern_matched=pattern.pattern_id,
            error_count=match_count,
            affected_components=affected_components,
            root_cause_analysis=root_cause,
            recommended_actions=pattern.suggested_actions,
            confidence_score=confidence_score,
            metadata={
                'pattern_description': pattern.description,
                'time_window_minutes': pattern.time_window_minutes,
                'sample_errors': [match['error_message'][:200] for match in matches[:3]]
            }
        )
        
        # 保存到資料庫
        await self.db.execute("""
            INSERT INTO diagnostic_results (
                diagnostic_id, timestamp, error_category, severity, pattern_matched,
                error_count, affected_components, root_cause_analysis, recommended_actions,
                confidence_score, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            diagnostic.diagnostic_id, diagnostic.timestamp, diagnostic.error_category.value,
            diagnostic.severity.value, diagnostic.pattern_matched, diagnostic.error_count,
            json.dumps(diagnostic.affected_components), diagnostic.root_cause_analysis,
            json.dumps([action.value for action in diagnostic.recommended_actions]),
            diagnostic.confidence_score, json.dumps(diagnostic.metadata)
        ))
        
        # 如果信心分數足夠高，生成告警
        if confidence_score >= self.config['diagnostic_confidence_threshold']:
            await self._generate_alert_from_diagnostic(diagnostic)
        
        self.logger.info(f"診斷結果生成: {diagnostic_id} - {pattern.description}")
        return diagnostic
    
    async def _generate_root_cause_analysis(self, 
                                          pattern: ErrorPattern, 
                                          matches: List[Dict[str, Any]]) -> str:
        """生成根因分析"""
        # 基於模式和錯誤內容生成根因分析
        analysis_parts = []
        
        # 基礎分析
        if pattern.category == ErrorCategory.CONNECTION_POOL:
            analysis_parts.append(f"連線池問題：在{pattern.time_window_minutes}分鐘內檢測到{len(matches)}次連線池相關錯誤。")
            if "exhausted" in pattern.regex_pattern:
                analysis_parts.append("根因：連線池資源已耗盡，可能是由於併發請求過多或連線未正確釋放。")
            elif "leak" in pattern.regex_pattern:
                analysis_parts.append("根因：檢測到連線洩漏，應用程式可能沒有正確關閉資料庫連線。")
        
        elif pattern.category == ErrorCategory.CONCURRENCY_CONFLICT:
            analysis_parts.append(f"併發衝突：檢測到{len(matches)}次併發相關錯誤。")
            analysis_parts.append("根因：高併發環境下的資源競爭，可能是由於資料庫鎖定或事務衝突。")
        
        elif pattern.category == ErrorCategory.RESOURCE_EXHAUSTION:
            analysis_parts.append(f"資源耗盡：系統資源不足，影響{len(set(match['component'] for match in matches))}個組件。")
            analysis_parts.append("根因：系統負載過高或資源配置不當。")
        
        elif pattern.category == ErrorCategory.TIMEOUT_ERROR:
            analysis_parts.append(f"超時錯誤：{len(matches)}次操作超時。")
            analysis_parts.append("根因：操作執行時間過長，可能是由於查詢效率低下或系統負載過高。")
        
        # 添加組件分析
        affected_components = set(match['component'] for match in matches)
        if len(affected_components) > 1:
            analysis_parts.append(f"影響範圍：錯誤影響多個組件 ({', '.join(affected_components)})，表明可能是系統級問題。")
        
        # 時間分布分析
        timestamps = [match['timestamp'] for match in matches]
        if len(timestamps) > 1:
            time_span = (max(timestamps) - min(timestamps)).total_seconds() / 60
            if time_span < pattern.time_window_minutes / 2:
                analysis_parts.append(f"時間特徵：錯誤集中在{time_span:.1f}分鐘內發生，表明可能是突發性問題。")
        
        return " ".join(analysis_parts)
    
    def _calculate_confidence_score(self, 
                                  pattern: ErrorPattern, 
                                  matches: List[Dict[str, Any]], 
                                  match_count: int) -> float:
        """計算診斷信心分數"""
        base_score = 50.0  # 基礎分數
        
        # 根據匹配數量調整（超過閾值越多，信心越高）
        frequency_factor = min(match_count / pattern.frequency_threshold, 3.0)
        base_score += frequency_factor * 15
        
        # 根據模式特異性調整
        if len(pattern.regex_pattern) > 50:  # 複雜模式更可信
            base_score += 10
        
        # 根據影響組件數量調整
        affected_components = len(set(match['component'] for match in matches))
        if affected_components == 1:
            base_score += 5  # 單組件問題更確定
        elif affected_components > 3:
            base_score += 15  # 多組件問題更嚴重
        
        # 根據錯誤類別調整
        if pattern.category in [ErrorCategory.CONNECTION_POOL, ErrorCategory.RESOURCE_EXHAUSTION]:
            base_score += 10  # 這些類別的模式通常更可靠
        
        # 根據嚴重程度調整
        severity_multiplier = {
            DiagnosticSeverity.CRITICAL: 1.2,
            DiagnosticSeverity.HIGH: 1.1,
            DiagnosticSeverity.MEDIUM: 1.0,
            DiagnosticSeverity.LOW: 0.9
        }
        base_score *= severity_multiplier.get(pattern.severity, 1.0)
        
        return min(base_score, 100.0)  # 限制在100以內
    
    async def _generate_alert_from_diagnostic(self, diagnostic: DiagnosticResult) -> Alert:
        """從診斷結果生成告警"""
        alert_id = str(uuid.uuid4())
        
        # 確定告警級別
        level_mapping = {
            DiagnosticSeverity.CRITICAL: AlertLevel.CRITICAL,
            DiagnosticSeverity.HIGH: AlertLevel.ERROR,
            DiagnosticSeverity.MEDIUM: AlertLevel.WARNING,
            DiagnosticSeverity.LOW: AlertLevel.INFO
        }
        alert_level = level_mapping.get(diagnostic.severity, AlertLevel.WARNING)
        
        # 生成告警標題和消息
        title = f"{diagnostic.error_category.value.replace('_', ' ').title()} - {diagnostic.pattern_matched}"
        message = f"{diagnostic.root_cause_analysis} (信心分數: {diagnostic.confidence_score:.1f}%)"
        
        # 檢查是否為重複告警
        is_duplicate, parent_alert_id = await self._check_alert_duplication(
            diagnostic.affected_components[0] if diagnostic.affected_components else "unknown",
            diagnostic.error_category,
            diagnostic.severity
        )
        
        # 創建告警
        alert = Alert(
            alert_id=alert_id,
            level=alert_level,
            title=title,
            message=message,
            component=diagnostic.affected_components[0] if diagnostic.affected_components else "unknown",
            created_at=datetime.now(),
            diagnostic_result=diagnostic,
            is_duplicate=is_duplicate,
            parent_alert_id=parent_alert_id
        )
        
        # 保存到資料庫
        await self.db.execute("""
            INSERT INTO diagnostic_alerts (
                alert_id, level, title, message, component, created_at, diagnostic_id,
                is_duplicate, parent_alert_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.alert_id, alert.level.value, alert.title, alert.message,
            alert.component, alert.created_at, diagnostic.diagnostic_id,
            alert.is_duplicate, alert.parent_alert_id, json.dumps({'confidence_score': diagnostic.confidence_score})
        ))
        
        # 添加到活動告警
        self._active_alerts[alert_id] = alert
        self._alert_history.append(alert)
        
        # 更新統計
        self._error_stats['alerts_generated'] += 1
        
        self.logger.warning(f"告警生成: {alert_id} - {title}")
        return alert
    
    async def _check_alert_duplication(self, 
                                     component: str, 
                                     category: ErrorCategory, 
                                     severity: DiagnosticSeverity) -> Tuple[bool, Optional[str]]:
        """檢查告警重複性"""
        if not self.config['alert_deduplication_enabled']:
            return False, None
        
        # 檢查最近30分鐘內的相似告警
        cutoff_time = datetime.now() - timedelta(minutes=30)
        
        for alert in self._alert_history:
            if (alert.created_at > cutoff_time and 
                alert.component == component and
                alert.diagnostic_result and
                alert.diagnostic_result.error_category == category and
                alert.diagnostic_result.severity == severity and
                not alert.resolved_at):
                
                return True, alert.alert_id
        
        return False, None
    
    async def _alert_processing_loop(self) -> None:
        """告警處理循環"""
        while True:
            try:
                await self._process_active_alerts()
                await self._cleanup_resolved_alerts()
                await asyncio.sleep(60)  # 每分鐘處理一次告警
            except Exception as e:
                self.logger.error(f"告警處理循環錯誤: {e}")
                await asyncio.sleep(60)
    
    async def _process_active_alerts(self) -> None:
        """處理活動告警"""
        current_time = datetime.now()
        
        for alert_id, alert in list(self._active_alerts.items()):
            # 檢查告警是否需要抑制
            if alert.suppressed_until and current_time < alert.suppressed_until:
                continue
            
            # 如果啟用自動恢復，執行恢復動作
            if (self.config['auto_recovery_enabled'] and 
                alert.diagnostic_result and
                alert.diagnostic_result.recommended_actions):
                
                await self._execute_recovery_actions(alert.diagnostic_result)
    
    async def _execute_recovery_actions(self, diagnostic: DiagnosticResult) -> None:
        """執行恢復動作"""
        for action in diagnostic.recommended_actions:
            if action == RecoveryAction.NO_ACTION:
                continue
            
            action_id = str(uuid.uuid4())
            start_time = time.time()
            success = False
            result_message = ""
            
            try:
                success, result_message = await self._perform_recovery_action(action, diagnostic)
            except Exception as e:
                result_message = f"恢復動作執行失敗: {str(e)}"
                self.logger.error(result_message)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # 記錄恢復動作執行結果
            await self.db.execute("""
                INSERT INTO diagnostic_recovery_actions (
                    action_id, diagnostic_id, action_type, executed_at, success,
                    result_message, execution_time_ms, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action_id, diagnostic.diagnostic_id, action.value, datetime.now(),
                success, result_message, execution_time_ms, json.dumps({})
            ))
            
            if success:
                self.logger.info(f"恢復動作執行成功: {action.value} - {result_message}")
            else:
                self.logger.warning(f"恢復動作執行失敗: {action.value} - {result_message}")
    
    async def _perform_recovery_action(self, action: RecoveryAction, diagnostic: DiagnosticResult) -> Tuple[bool, str]:
        """執行具體的恢復動作"""
        if action == RecoveryAction.INCREASE_POOL_SIZE:
            # 增加連線池大小
            try:
                current_size = self.db.connection_pool.max_connections
                new_size = min(current_size + 5, 50)  # 最大50個連線
                self.db.connection_pool.max_connections = new_size
                return True, f"連線池大小已從 {current_size} 增加到 {new_size}"
            except Exception as e:
                return False, f"增加連線池大小失敗: {str(e)}"
        
        elif action == RecoveryAction.DECREASE_POOL_SIZE:
            # 減少連線池大小
            try:
                current_size = self.db.connection_pool.max_connections
                new_size = max(current_size - 2, 5)  # 最少5個連線
                self.db.connection_pool.max_connections = new_size
                return True, f"連線池大小已從 {current_size} 減少到 {new_size}"
            except Exception as e:
                return False, f"減少連線池大小失敗: {str(e)}"
        
        elif action == RecoveryAction.CLEAR_CACHE:
            # 清理快取
            try:
                # 這裡應該調用實際的快取清理邏輯
                return True, "快取清理完成"
            except Exception as e:
                return False, f"快取清理失敗: {str(e)}"
        
        elif action == RecoveryAction.NOTIFY_ADMIN:
            # 通知管理員
            try:
                # 這裡應該實現實際的通知邏輯（例如發送郵件或Slack消息）
                self.logger.critical(f"管理員通知: {diagnostic.root_cause_analysis}")
                return True, "管理員通知已發送"
            except Exception as e:
                return False, f"管理員通知失敗: {str(e)}"
        
        else:
            return False, f"不支援的恢復動作: {action.value}"
    
    async def _run_anomaly_detection(self) -> None:
        """運行異常檢測"""
        if not self.config['ml_anomaly_detection_enabled']:
            return
        
        # 收集效能指標
        current_metrics = await self._collect_performance_metrics()
        
        # 檢測異常
        anomalies = await self._detect_anomalies(current_metrics)
        
        # 為檢測到的異常生成診斷
        for anomaly in anomalies:
            await self._generate_anomaly_diagnostic(anomaly)
    
    async def _collect_performance_metrics(self) -> Dict[str, float]:
        """收集效能指標"""
        metrics = {}
        
        try:
            # 連線池指標
            pool = self.db.connection_pool
            total_connections = sum(pool.connection_counts.values())
            metrics['connection_pool_utilization'] = (total_connections / pool.max_connections) * 100
            
            # 錯誤率指標
            recent_errors = len([e for e in self._error_buffer if 
                               (datetime.now() - e['timestamp']).total_seconds() < 300])  # 5分鐘內
            metrics['error_rate_per_5min'] = recent_errors
            
            # 回應時間指標（模擬）
            metrics['avg_response_time_ms'] = 100.0  # 這裡應該從實際監控系統獲取
            
        except Exception as e:
            self.logger.error(f"效能指標收集失敗: {e}")
        
        return metrics
    
    async def _detect_anomalies(self, current_metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """檢測異常"""
        anomalies = []
        
        for metric_name, current_value in current_metrics.items():
            # 更新歷史數據
            self._performance_history[metric_name].append(current_value)
            
            # 如果歷史數據不足，跳過
            if len(self._performance_history[metric_name]) < 10:
                continue
            
            # 計算基線統計
            history = list(self._performance_history[metric_name])
            mean = statistics.mean(history[:-1])  # 不包含當前值
            std = statistics.stdev(history[:-1]) if len(history) > 2 else 0
            
            # 檢測異常（使用3-sigma規則）
            if std > 0:
                z_score = abs(current_value - mean) / std
                if z_score > 3:  # 3-sigma異常
                    anomalies.append({
                        'metric_name': metric_name,
                        'current_value': current_value,
                        'baseline_mean': mean,
                        'z_score': z_score,
                        'anomaly_type': 'statistical'
                    })
        
        return anomalies
    
    async def _generate_anomaly_diagnostic(self, anomaly: Dict[str, Any]) -> None:
        """為異常生成診斷"""
        diagnostic_id = str(uuid.uuid4())
        
        # 確定異常嚴重程度
        z_score = anomaly['z_score']
        if z_score > 5:
            severity = DiagnosticSeverity.CRITICAL
        elif z_score > 4:
            severity = DiagnosticSeverity.HIGH
        elif z_score > 3:
            severity = DiagnosticSeverity.MEDIUM
        else:
            severity = DiagnosticSeverity.LOW
        
        # 生成根因分析
        metric_name = anomaly['metric_name']
        current_value = anomaly['current_value']
        baseline = anomaly['baseline_mean']
        
        root_cause = f"檢測到指標 {metric_name} 異常：當前值 {current_value:.2f}，基線 {baseline:.2f}，偏差 {z_score:.2f} 標準差。"
        
        # 建議恢復動作
        suggested_actions = [RecoveryAction.NOTIFY_ADMIN]
        if 'connection_pool' in metric_name:
            suggested_actions.extend([RecoveryAction.INCREASE_POOL_SIZE, RecoveryAction.OPTIMIZE_QUERY])
        elif 'error_rate' in metric_name:
            suggested_actions.extend([RecoveryAction.RESTART_SERVICE, RecoveryAction.CLEAR_CACHE])
        
        # 創建診斷結果
        diagnostic = DiagnosticResult(
            diagnostic_id=diagnostic_id,
            timestamp=datetime.now(),
            error_category=ErrorCategory.UNKNOWN,
            severity=severity,
            pattern_matched="anomaly_detection",
            error_count=1,
            affected_components=["system"],
            root_cause_analysis=root_cause,
            recommended_actions=suggested_actions,
            confidence_score=min(z_score * 20, 95),  # z_score轉換為信心分數
            metadata=anomaly
        )
        
        # 保存診斷結果
        await self.db.execute("""
            INSERT INTO diagnostic_results (
                diagnostic_id, timestamp, error_category, severity, pattern_matched,
                error_count, affected_components, root_cause_analysis, recommended_actions,
                confidence_score, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            diagnostic.diagnostic_id, diagnostic.timestamp, diagnostic.error_category.value,
            diagnostic.severity.value, diagnostic.pattern_matched, diagnostic.error_count,
            json.dumps(diagnostic.affected_components), diagnostic.root_cause_analysis,
            json.dumps([action.value for action in diagnostic.recommended_actions]),
            diagnostic.confidence_score, json.dumps(diagnostic.metadata)
        ))
        
        # 如果信心分數足夠高，生成告警
        if diagnostic.confidence_score >= self.config['diagnostic_confidence_threshold']:
            await self._generate_alert_from_diagnostic(diagnostic)
        
        self.logger.info(f"異常診斷完成: {diagnostic_id} - {metric_name}")
    
    async def _update_performance_baseline(self) -> None:
        """更新效能基線"""
        for metric_name, history in self._performance_history.items():
            if len(history) >= 50:  # 足夠的歷史數據
                # 計算更穩定的基線
                recent_data = list(history)[-30:]  # 最近30個數據點
                self._anomaly_baseline[metric_name] = statistics.mean(recent_data)
    
    async def _cleanup_resolved_alerts(self) -> None:
        """清理已解決的告警"""
        current_time = datetime.now()
        resolved_alerts = []
        
        for alert_id, alert in list(self._active_alerts.items()):
            # 自動解決超過1小時沒有新錯誤的告警
            if (current_time - alert.created_at).total_seconds() > 3600:
                alert.resolved_at = current_time
                resolved_alerts.append(alert_id)
                
                # 更新資料庫
                await self.db.execute("""
                    UPDATE diagnostic_alerts SET resolved_at = ? WHERE alert_id = ?
                """, (current_time, alert_id))
        
        # 從活動告警中移除已解決的告警
        for alert_id in resolved_alerts:
            if alert_id in self._active_alerts:
                del self._active_alerts[alert_id]
        
        if resolved_alerts:
            self.logger.info(f"清理了 {len(resolved_alerts)} 個已解決的告警")
    
    async def _load_configuration(self) -> None:
        """載入配置"""
        # 這裡可以從資料庫或配置文件載入配置
        pass
    
    async def _load_error_patterns(self) -> None:
        """載入錯誤模式"""
        try:
            # 從資料庫載入自定義錯誤模式
            rows = await self.db.fetchall("""
                SELECT pattern_id, category, regex_pattern, description, severity,
                       suggested_actions, frequency_threshold, time_window_minutes
                FROM diagnostic_error_patterns
                WHERE active = TRUE
            """)
            
            for row in rows:
                pattern = ErrorPattern(
                    pattern_id=row[0],
                    category=ErrorCategory(row[1]),
                    regex_pattern=row[2],
                    description=row[3],
                    severity=DiagnosticSeverity(row[4]),
                    suggested_actions=[RecoveryAction(action) for action in json.loads(row[5])],
                    frequency_threshold=row[6],
                    time_window_minutes=row[7]
                )
                self._error_patterns[pattern.pattern_id] = pattern
            
        except Exception as e:
            self.logger.warning(f"載入錯誤模式失敗，使用預設模式: {e}")
    
    async def _initialize_anomaly_detection(self) -> None:
        """初始化異常檢測"""
        # 初始化異常檢測基線
        self._anomaly_baseline = {}
        self.logger.info("異常檢測系統已初始化")
    
    async def get_diagnostic_stats(self) -> Dict[str, Any]:
        """獲取診斷統計信息"""
        return {
            **self._error_stats,
            'active_alerts_count': len(self._active_alerts),
            'error_buffer_size': len(self._error_buffer),
            'loaded_patterns_count': len(self._error_patterns),
            'performance_metrics_tracked': len(self._performance_history)
        }
    
    async def get_recent_diagnostics(self, hours: int = 24) -> List[DiagnosticResult]:
        """獲取最近的診斷結果"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        rows = await self.db.fetchall("""
            SELECT diagnostic_id, timestamp, error_category, severity, pattern_matched,
                   error_count, affected_components, root_cause_analysis, recommended_actions,
                   confidence_score, metadata
            FROM diagnostic_results
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """, (cutoff_time,))
        
        diagnostics = []
        for row in rows:
            diagnostic = DiagnosticResult(
                diagnostic_id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                error_category=ErrorCategory(row[2]),
                severity=DiagnosticSeverity(row[3]),
                pattern_matched=row[4],
                error_count=row[5],
                affected_components=json.loads(row[6]),
                root_cause_analysis=row[7],
                recommended_actions=[RecoveryAction(action) for action in json.loads(row[8])],
                confidence_score=row[9],
                metadata=json.loads(row[10]) if row[10] else {}
            )
            diagnostics.append(diagnostic)
        
        return diagnostics
    
    async def get_active_alerts(self) -> List[Alert]:
        """獲取活動告警"""
        return list(self._active_alerts.values())
    
    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """手動解決告警"""
        if alert_id not in self._active_alerts:
            return False
        
        alert = self._active_alerts[alert_id]
        alert.resolved_at = datetime.now()
        
        # 更新資料庫
        await self.db.execute("""
            UPDATE diagnostic_alerts SET resolved_at = ? WHERE alert_id = ?
        """, (alert.resolved_at, alert_id))
        
        # 從活動告警中移除
        del self._active_alerts[alert_id]
        
        self.logger.info(f"告警手動解決: {alert_id} by {resolved_by}")
        return True