"""
子機器人資料庫錯誤處理和日誌系統
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供完整的錯誤處理和日誌記錄功能：
- 分層錯誤處理和恢復機制
- 結構化日誌記錄和審計追蹤
- 效能監控和告警系統
- 錯誤分析和趨勢統計
- 自動錯誤恢復和降級策略
- 安全事件記錄和分析
"""

import asyncio
import logging
import traceback
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, TypeVar
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import deque, defaultdict
from functools import wraps
import sys
import os

# 核心依賴
from core.base_service import BaseService
from src.core.errors import (
    SubBotError,
    SubBotCreationError,
    SubBotTokenError,
    SubBotChannelError,
    DatabaseError,
    SecurityError
)

logger = logging.getLogger('core.database.error_handler')

T = TypeVar('T')


class ErrorSeverity(Enum):
    """錯誤嚴重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """錯誤分類"""
    DATABASE = "database"
    SECURITY = "security"
    NETWORK = "network"
    VALIDATION = "validation"
    PERMISSION = "permission"
    RESOURCE = "resource"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    EXTERNAL = "external"


class LogLevel(Enum):
    """日誌級別"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RecoveryAction(Enum):
    """恢復動作"""
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    ABORT = "abort"
    ESCALATE = "escalate"


@dataclass
class ErrorContext:
    """錯誤上下文資訊"""
    operation: str
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    bot_id: Optional[str] = None
    channel_id: Optional[int] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorEvent:
    """錯誤事件記錄"""
    id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    message: str
    stack_trace: Optional[str]
    context: ErrorContext
    recovery_attempts: int = 0
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_method: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value,
            'category': self.category.value,
            'error_type': self.error_type,
            'message': self.message,
            'stack_trace': self.stack_trace,
            'context': asdict(self.context),
            'recovery_attempts': self.recovery_attempts,
            'recovery_actions': [action.value for action in self.recovery_actions],
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_method': self.resolution_method
        }


@dataclass
class LogEntry:
    """日誌條目"""
    timestamp: datetime
    level: LogLevel
    module: str
    operation: str
    message: str
    context: Optional[ErrorContext] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'module': self.module,
            'operation': self.operation,
            'message': self.message,
            'context': asdict(self.context) if self.context else None,
            'metadata': self.metadata
        }


class ErrorAnalyzer:
    """錯誤分析器"""
    
    def __init__(self):
        self.error_patterns = {}
        self.error_statistics = defaultdict(int)
        self.error_trends = defaultdict(list)
        self.error_correlations = defaultdict(list)
    
    def analyze_error(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """
        分析錯誤事件
        
        Args:
            error_event: 錯誤事件
            
        Returns:
            分析結果
        """
        analysis = {
            'severity_assessment': self._assess_severity(error_event),
            'category_confidence': self._verify_category(error_event),
            'pattern_match': self._find_pattern_match(error_event),
            'frequency_analysis': self._analyze_frequency(error_event),
            'correlation_analysis': self._analyze_correlations(error_event),
            'recommended_actions': self._recommend_actions(error_event)
        }
        
        # 更新統計
        self._update_statistics(error_event)
        
        return analysis
    
    def _assess_severity(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """評估錯誤嚴重性"""
        severity_factors = {
            'error_type': 1.0,
            'operation_impact': 1.0,
            'user_impact': 1.0,
            'system_impact': 1.0
        }
        
        # 基於錯誤類型
        if isinstance(error_event.error_type, str):
            if 'critical' in error_event.error_type.lower():
                severity_factors['error_type'] = 3.0
            elif 'security' in error_event.error_type.lower():
                severity_factors['error_type'] = 2.5
            elif 'database' in error_event.error_type.lower():
                severity_factors['error_type'] = 2.0
        
        # 基於操作影響
        critical_operations = ['create_subbot', 'delete_subbot', 'encrypt_token']
        if error_event.context.operation in critical_operations:
            severity_factors['operation_impact'] = 2.0
        
        # 計算綜合嚴重性分數
        total_score = sum(severity_factors.values()) / len(severity_factors)
        
        return {
            'score': total_score,
            'factors': severity_factors,
            'recommendation': (
                ErrorSeverity.CRITICAL if total_score >= 2.5
                else ErrorSeverity.HIGH if total_score >= 2.0
                else ErrorSeverity.MEDIUM if total_score >= 1.5
                else ErrorSeverity.LOW
            ).value
        }
    
    def _verify_category(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """驗證錯誤分類"""
        category_keywords = {
            ErrorCategory.DATABASE: ['database', 'sql', 'connection', 'query', 'transaction'],
            ErrorCategory.SECURITY: ['security', 'encrypt', 'token', 'permission', 'auth'],
            ErrorCategory.NETWORK: ['network', 'connection', 'timeout', 'socket'],
            ErrorCategory.VALIDATION: ['validation', 'invalid', 'format', 'required'],
            ErrorCategory.RESOURCE: ['memory', 'disk', 'cpu', 'resource', 'limit']
        }
        
        message_lower = error_event.message.lower()
        confidence_scores = {}
        
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            confidence_scores[category.value] = score
        
        # 找到最高信心分數
        max_score = max(confidence_scores.values()) if confidence_scores else 0
        suggested_category = max(confidence_scores.keys(), key=lambda k: confidence_scores[k]) if max_score > 0 else None
        
        return {
            'current_category': error_event.category.value,
            'suggested_category': suggested_category,
            'confidence_scores': confidence_scores,
            'classification_accurate': suggested_category == error_event.category.value if suggested_category else True
        }
    
    def _find_pattern_match(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """查找錯誤模式匹配"""
        # 簡化的模式匹配實現
        error_signature = f"{error_event.error_type}:{error_event.category.value}"
        
        pattern_info = {
            'signature': error_signature,
            'known_pattern': error_signature in self.error_patterns,
            'occurrence_count': self.error_statistics.get(error_signature, 0),
            'last_occurrence': None
        }
        
        if error_signature in self.error_trends:
            recent_occurrences = [
                event for event in self.error_trends[error_signature]
                if (datetime.now() - event).total_seconds() < 3600  # 最近1小時
            ]
            pattern_info['recent_occurrences'] = len(recent_occurrences)
            pattern_info['is_recurring'] = len(recent_occurrences) > 2
        
        return pattern_info
    
    def _analyze_frequency(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """分析錯誤頻率"""
        error_key = error_event.error_type
        now = datetime.now()
        
        # 時間窗口分析
        windows = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7)
        }
        
        frequency_analysis = {}
        
        for window_name, window_duration in windows.items():
            window_start = now - window_duration
            
            if error_key in self.error_trends:
                recent_errors = [
                    event for event in self.error_trends[error_key]
                    if event >= window_start
                ]
                frequency_analysis[window_name] = {
                    'count': len(recent_errors),
                    'rate_per_hour': len(recent_errors) / (window_duration.total_seconds() / 3600)
                }
        
        return frequency_analysis
    
    def _analyze_correlations(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """分析錯誤關聯"""
        correlations = {
            'context_correlations': [],
            'time_correlations': [],
            'operation_correlations': []
        }
        
        # 分析上下文關聯
        if error_event.context.user_id:
            user_errors = [
                event for events in self.error_correlations.values()
                for event in events
                if hasattr(event, 'context') and event.context.user_id == error_event.context.user_id
            ]
            if len(user_errors) > 1:
                correlations['context_correlations'].append({
                    'type': 'user_related',
                    'count': len(user_errors)
                })
        
        # 分析時間關聯
        time_window = timedelta(minutes=5)
        recent_errors = []
        
        for events in self.error_correlations.values():
            recent_errors.extend([
                event for event in events
                if abs((event.timestamp - error_event.timestamp).total_seconds()) <= time_window.total_seconds()
            ])
        
        if len(recent_errors) > 1:
            correlations['time_correlations'].append({
                'type': 'time_clustered',
                'count': len(recent_errors),
                'window_minutes': 5
            })
        
        return correlations
    
    def _recommend_actions(self, error_event: ErrorEvent) -> List[Dict[str, Any]]:
        """推薦恢復動作"""
        recommendations = []
        
        # 基於錯誤嚴重性的建議
        if error_event.severity == ErrorSeverity.CRITICAL:
            recommendations.append({
                'action': RecoveryAction.ESCALATE.value,
                'priority': 1,
                'description': '立即升級處理，通知管理員'
            })
        
        # 基於錯誤分類的建議
        category_actions = {
            ErrorCategory.DATABASE: [
                {'action': RecoveryAction.RETRY.value, 'description': '重試資料庫操作'},
                {'action': RecoveryAction.FALLBACK.value, 'description': '使用備用資料源'}
            ],
            ErrorCategory.SECURITY: [
                {'action': RecoveryAction.ESCALATE.value, 'description': '安全事件需要立即處理'},
                {'action': RecoveryAction.ABORT.value, 'description': '中止可疑操作'}
            ],
            ErrorCategory.NETWORK: [
                {'action': RecoveryAction.RETRY.value, 'description': '重試網路請求'},
                {'action': RecoveryAction.FALLBACK.value, 'description': '使用備用連接'}
            ]
        }
        
        if error_event.category in category_actions:
            for i, action in enumerate(category_actions[error_event.category]):
                action['priority'] = i + 2  # 優先級在嚴重性建議之後
                recommendations.append(action)
        
        return recommendations
    
    def _update_statistics(self, error_event: ErrorEvent):
        """更新錯誤統計"""
        error_key = f"{error_event.error_type}:{error_event.category.value}"
        
        # 更新計數統計
        self.error_statistics[error_key] += 1
        self.error_statistics[f"category:{error_event.category.value}"] += 1
        self.error_statistics[f"severity:{error_event.severity.value}"] += 1
        
        # 更新趨勢統計
        if error_key not in self.error_trends:
            self.error_trends[error_key] = deque(maxlen=1000)
        self.error_trends[error_key].append(error_event.timestamp)
        
        # 更新關聯統計
        if error_key not in self.error_correlations:
            self.error_correlations[error_key] = deque(maxlen=100)
        self.error_correlations[error_key].append(error_event)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """獲取錯誤總結"""
        now = datetime.now()
        
        # 最近24小時的統計
        recent_errors = []
        for events in self.error_correlations.values():
            recent_errors.extend([
                event for event in events
                if (now - event.timestamp).total_seconds() < 86400  # 24小時
            ])
        
        # 按嚴重性分組
        severity_breakdown = defaultdict(int)
        for event in recent_errors:
            severity_breakdown[event.severity.value] += 1
        
        # 按分類分組
        category_breakdown = defaultdict(int)
        for event in recent_errors:
            category_breakdown[event.category.value] += 1
        
        # 最常見錯誤
        error_type_counts = defaultdict(int)
        for event in recent_errors:
            error_type_counts[event.error_type] += 1
        
        top_errors = sorted(error_type_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'total_errors_24h': len(recent_errors),
            'severity_breakdown': dict(severity_breakdown),
            'category_breakdown': dict(category_breakdown),
            'top_errors': top_errors,
            'error_rate_per_hour': len(recent_errors) / 24,
            'analysis_timestamp': now.isoformat()
        }


class StructuredLogger:
    """結構化日誌記錄器"""
    
    def __init__(self, name: str, max_entries: int = 10000):
        self.name = name
        self.logger = logging.getLogger(name)
        self.max_entries = max_entries
        self.log_buffer = deque(maxlen=max_entries)
        self.log_statistics = defaultdict(int)
        
        # 配置格式器
        self._setup_logger()
    
    def _setup_logger(self):
        """設置日誌格式"""
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log(
        self,
        level: LogLevel,
        operation: str,
        message: str,
        context: Optional[ErrorContext] = None,
        **metadata
    ):
        """
        記錄結構化日誌
        
        Args:
            level: 日誌級別
            operation: 操作名稱
            message: 日誌訊息
            context: 錯誤上下文
            **metadata: 額外元資料
        """
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            module=self.name,
            operation=operation,
            message=message,
            context=context,
            metadata=metadata
        )
        
        # 添加到緩衝區
        self.log_buffer.append(log_entry)
        
        # 更新統計
        self.log_statistics[level.value] += 1
        self.log_statistics[f"operation:{operation}"] += 1
        
        # 輸出到標準日誌
        log_data = log_entry.to_dict()
        log_message = f"[{operation}] {message}"
        if context:
            log_message += f" | Context: {json.dumps(asdict(context), default=str)}"
        if metadata:
            log_message += f" | Metadata: {json.dumps(metadata, default=str)}"
        
        # 根據級別輸出
        if level == LogLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.logger.error(log_message)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_message)
    
    def debug(self, operation: str, message: str, context: Optional[ErrorContext] = None, **metadata):
        """記錄除錯日誌"""
        self.log(LogLevel.DEBUG, operation, message, context, **metadata)
    
    def info(self, operation: str, message: str, context: Optional[ErrorContext] = None, **metadata):
        """記錄資訊日誌"""
        self.log(LogLevel.INFO, operation, message, context, **metadata)
    
    def warning(self, operation: str, message: str, context: Optional[ErrorContext] = None, **metadata):
        """記錄警告日誌"""
        self.log(LogLevel.WARNING, operation, message, context, **metadata)
    
    def error(self, operation: str, message: str, context: Optional[ErrorContext] = None, **metadata):
        """記錄錯誤日誌"""
        self.log(LogLevel.ERROR, operation, message, context, **metadata)
    
    def critical(self, operation: str, message: str, context: Optional[ErrorContext] = None, **metadata):
        """記錄嚴重錯誤日誌"""
        self.log(LogLevel.CRITICAL, operation, message, context, **metadata)
    
    def get_recent_logs(
        self,
        limit: int = 100,
        level_filter: Optional[LogLevel] = None,
        operation_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        獲取最近的日誌
        
        Args:
            limit: 返回數量限制
            level_filter: 級別過濾
            operation_filter: 操作過濾
            
        Returns:
            日誌列表
        """
        logs = list(self.log_buffer)
        
        # 應用過濾器
        if level_filter:
            logs = [log for log in logs if log.level == level_filter]
        
        if operation_filter:
            logs = [log for log in logs if operation_filter in log.operation]
        
        # 排序並限制數量
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        logs = logs[:limit]
        
        return [log.to_dict() for log in logs]
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """獲取日誌統計"""
        return {
            'total_entries': len(self.log_buffer),
            'statistics': dict(self.log_statistics),
            'buffer_size': self.max_entries,
            'buffer_usage': len(self.log_buffer) / self.max_entries * 100
        }


class SubBotErrorHandler(BaseService):
    """
    子機器人錯誤處理系統
    
    提供完整的錯誤處理、分析、恢復和日誌記錄功能
    """
    
    def __init__(
        self,
        enable_auto_recovery: bool = True,
        max_recovery_attempts: int = 3,
        escalation_threshold: int = 5,
        log_retention_hours: int = 168  # 7天
    ):
        """
        初始化錯誤處理系統
        
        Args:
            enable_auto_recovery: 是否啟用自動恢復
            max_recovery_attempts: 最大恢復嘗試次數
            escalation_threshold: 升級閾值
            log_retention_hours: 日誌保留時間（小時）
        """
        super().__init__("SubBotErrorHandler")
        
        self.enable_auto_recovery = enable_auto_recovery
        self.max_recovery_attempts = max_recovery_attempts
        self.escalation_threshold = escalation_threshold
        self.log_retention_hours = log_retention_hours
        
        # 核心組件
        self.error_analyzer = ErrorAnalyzer()
        self.structured_logger = StructuredLogger(f"{self.name}.Logger")
        
        # 錯誤事件存儲
        self.error_events: Dict[str, ErrorEvent] = {}
        self.error_history = deque(maxlen=10000)
        
        # 恢復策略映射
        self.recovery_strategies: Dict[str, Callable] = {}
        
        # 告警配置
        self.alert_callbacks: List[Callable] = []
        
        # 統計資訊
        self._handler_stats = {
            'total_errors_handled': 0,
            'auto_recoveries': 0,
            'manual_recoveries': 0,
            'escalations': 0,
            'unresolved_errors': 0
        }
    
    async def _initialize(self) -> bool:
        """初始化錯誤處理系統"""
        try:
            self.logger.info("錯誤處理系統初始化中...")
            
            # 設置預設恢復策略
            self._setup_default_recovery_strategies()
            
            # 啟動清理任務
            asyncio.create_task(self._cleanup_expired_logs())
            
            self.logger.info("錯誤處理系統初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"錯誤處理系統初始化失敗: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 保存重要錯誤事件（如果需要持久化）
            await self._save_critical_errors()
            
            self.logger.info("錯誤處理系統清理完成")
        except Exception as e:
            self.logger.error(f"清理錯誤處理系統時發生錯誤: {e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """驗證權限"""
        return True  # 錯誤處理通常不需要特殊權限
    
    def _setup_default_recovery_strategies(self):
        """設置預設恢復策略"""
        self.recovery_strategies.update({
            'database_connection_error': self._recover_database_connection,
            'token_encryption_error': self._recover_token_encryption,
            'validation_error': self._recover_validation_error,
            'resource_exhaustion': self._recover_resource_exhaustion,
            'network_timeout': self._recover_network_timeout
        })
    
    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None
    ) -> ErrorEvent:
        """
        處理錯誤事件
        
        Args:
            error: 異常對象
            context: 錯誤上下文
            severity: 錯誤嚴重性（可選，會自動推斷）
            category: 錯誤分類（可選，會自動推斷）
            
        Returns:
            錯誤事件對象
        """
        try:
            # 生成錯誤ID
            error_id = f"err_{int(time.time())}_{hash(str(error)) % 10000:04d}"
            
            # 推斷嚴重性和分類
            if severity is None:
                severity = self._infer_severity(error, context)
            
            if category is None:
                category = self._infer_category(error, context)
            
            # 創建錯誤事件
            error_event = ErrorEvent(
                id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=category,
                error_type=type(error).__name__,
                message=str(error),
                stack_trace=traceback.format_exc() if sys.exc_info()[0] else None,
                context=context
            )
            
            # 分析錯誤
            analysis = self.error_analyzer.analyze_error(error_event)
            
            # 記錄日誌
            self.structured_logger.error(
                context.operation,
                f"錯誤處理: {error_event.message}",
                context,
                error_id=error_id,
                severity=severity.value,
                category=category.value,
                analysis=analysis
            )
            
            # 存儲錯誤事件
            self.error_events[error_id] = error_event
            self.error_history.append(error_event)
            
            # 嘗試自動恢復
            if self.enable_auto_recovery:
                await self._attempt_recovery(error_event, analysis)
            
            # 檢查是否需要告警
            await self._check_alert_conditions(error_event, analysis)
            
            # 更新統計
            self._handler_stats['total_errors_handled'] += 1
            if not error_event.resolved:
                self._handler_stats['unresolved_errors'] += 1
            
            return error_event
            
        except Exception as handling_error:
            # 錯誤處理器本身出錯 - 記錄但不再處理
            self.logger.critical(f"錯誤處理系統故障: {handling_error}")
            raise
    
    def _infer_severity(self, error: Exception, context: ErrorContext) -> ErrorSeverity:
        """推斷錯誤嚴重性"""
        # 基於異常類型
        if isinstance(error, (SubBotTokenError, SecurityError)):
            return ErrorSeverity.HIGH
        elif isinstance(error, (SubBotCreationError, DatabaseError)):
            return ErrorSeverity.MEDIUM
        elif isinstance(error, (SubBotChannelError, ValueError)):
            return ErrorSeverity.LOW
        
        # 基於錯誤訊息關鍵字
        message = str(error).lower()
        if any(keyword in message for keyword in ['critical', 'fatal', 'security', 'corruption']):
            return ErrorSeverity.CRITICAL
        elif any(keyword in message for keyword in ['error', 'failed', 'exception']):
            return ErrorSeverity.MEDIUM
        
        return ErrorSeverity.LOW
    
    def _infer_category(self, error: Exception, context: ErrorContext) -> ErrorCategory:
        """推斷錯誤分類"""
        # 基於異常類型
        if isinstance(error, DatabaseError):
            return ErrorCategory.DATABASE
        elif isinstance(error, (SubBotTokenError, SecurityError)):
            return ErrorCategory.SECURITY
        elif isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK
        elif isinstance(error, (ValueError, TypeError)):
            return ErrorCategory.VALIDATION
        elif isinstance(error, PermissionError):
            return ErrorCategory.PERMISSION
        elif isinstance(error, (MemoryError, OSError)):
            return ErrorCategory.RESOURCE
        elif isinstance(error, SubBotError):
            return ErrorCategory.BUSINESS_LOGIC
        
        # 基於上下文
        if context.operation.startswith('encrypt') or 'token' in context.operation:
            return ErrorCategory.SECURITY
        elif context.operation.startswith('db_') or 'database' in context.operation:
            return ErrorCategory.DATABASE
        
        return ErrorCategory.SYSTEM
    
    async def _attempt_recovery(self, error_event: ErrorEvent, analysis: Dict[str, Any]):
        """嘗試自動恢復"""
        if error_event.recovery_attempts >= self.max_recovery_attempts:
            self.structured_logger.warning(
                error_event.context.operation,
                f"已達最大恢復嘗試次數，停止自動恢復: {error_event.id}",
                error_event.context,
                error_id=error_event.id
            )
            return
        
        # 獲取推薦的恢復動作
        recommended_actions = analysis.get('recommended_actions', [])
        
        for action_info in recommended_actions:
            action = RecoveryAction(action_info['action'])
            
            try:
                # 執行恢復動作
                recovery_success = await self._execute_recovery_action(error_event, action)
                
                # 更新錯誤事件
                error_event.recovery_attempts += 1
                error_event.recovery_actions.append(action)
                
                if recovery_success:
                    error_event.resolved = True
                    error_event.resolved_at = datetime.now()
                    error_event.resolution_method = f"auto_recovery_{action.value}"
                    
                    self._handler_stats['auto_recoveries'] += 1
                    self._handler_stats['unresolved_errors'] -= 1
                    
                    self.structured_logger.info(
                        error_event.context.operation,
                        f"自動恢復成功: {error_event.id} 使用策略: {action.value}",
                        error_event.context,
                        error_id=error_event.id,
                        recovery_action=action.value
                    )
                    break
                
            except Exception as recovery_error:
                self.structured_logger.warning(
                    error_event.context.operation,
                    f"恢復動作失敗: {action.value} - {recovery_error}",
                    error_event.context,
                    error_id=error_event.id,
                    recovery_action=action.value,
                    recovery_error=str(recovery_error)
                )
    
    async def _execute_recovery_action(self, error_event: ErrorEvent, action: RecoveryAction) -> bool:
        """執行恢復動作"""
        # 基於錯誤類型和恢復動作選擇策略
        strategy_key = f"{error_event.error_type.lower()}_{action.value}"
        
        # 嘗試特定策略
        if strategy_key in self.recovery_strategies:
            return await self.recovery_strategies[strategy_key](error_event)
        
        # 嘗試通用策略
        generic_key = action.value
        if generic_key in self.recovery_strategies:
            return await self.recovery_strategies[generic_key](error_event)
        
        # 執行預設動作
        return await self._execute_default_recovery_action(error_event, action)
    
    async def _execute_default_recovery_action(self, error_event: ErrorEvent, action: RecoveryAction) -> bool:
        """執行預設恢復動作"""
        if action == RecoveryAction.RETRY:
            # 簡單延遲重試
            await asyncio.sleep(1.0 * (error_event.recovery_attempts + 1))
            return False  # 實際重試需要在呼叫層處理
        
        elif action == RecoveryAction.FALLBACK:
            # 降級處理
            return await self._enable_fallback_mode(error_event)
        
        elif action == RecoveryAction.DEGRADE:
            # 功能降級
            return await self._degrade_service(error_event)
        
        elif action == RecoveryAction.ESCALATE:
            # 升級處理
            return await self._escalate_error(error_event)
        
        elif action == RecoveryAction.ABORT:
            # 中止操作
            return True  # 標記為已處理，但實際中止需要呼叫層處理
        
        return False
    
    # 具體恢復策略實現
    
    async def _recover_database_connection(self, error_event: ErrorEvent) -> bool:
        """恢復資料庫連接"""
        try:
            # 這裡可以實現重新連接邏輯
            # 例如：重新初始化資料庫管理器
            self.structured_logger.info(
                error_event.context.operation,
                "嘗試重新建立資料庫連接",
                error_event.context
            )
            
            # 實際實現需要與資料庫管理器配合
            return False  # 暫時返回false，需要具體實現
        except Exception as e:
            self.structured_logger.error(
                error_event.context.operation,
                f"資料庫連接恢復失敗: {e}",
                error_event.context
            )
            return False
    
    async def _recover_token_encryption(self, error_event: ErrorEvent) -> bool:
        """恢復Token加密錯誤"""
        try:
            # 可能的恢復策略：
            # 1. 重新生成加密密鑰
            # 2. 使用備用加密算法
            # 3. 清理損壞的Token資料
            
            self.structured_logger.info(
                error_event.context.operation,
                "嘗試恢復Token加密功能",
                error_event.context
            )
            
            # 實際實現需要與Token管理器配合
            return False
        except Exception as e:
            self.structured_logger.error(
                error_event.context.operation,
                f"Token加密恢復失敗: {e}",
                error_event.context
            )
            return False
    
    async def _recover_validation_error(self, error_event: ErrorEvent) -> bool:
        """恢復驗證錯誤"""
        # 驗證錯誤通常不需要自動恢復，記錄即可
        self.structured_logger.info(
            error_event.context.operation,
            "驗證錯誤不支援自動恢復",
            error_event.context
        )
        return True  # 標記為已處理
    
    async def _recover_resource_exhaustion(self, error_event: ErrorEvent) -> bool:
        """恢復資源耗盡錯誤"""
        try:
            # 清理快取、釋放資源等
            self.structured_logger.info(
                error_event.context.operation,
                "嘗試釋放系統資源",
                error_event.context
            )
            
            # 實際實現：清理快取、關閉非必要連接等
            return False
        except Exception as e:
            self.structured_logger.error(
                error_event.context.operation,
                f"資源恢復失敗: {e}",
                error_event.context
            )
            return False
    
    async def _recover_network_timeout(self, error_event: ErrorEvent) -> bool:
        """恢復網路超時錯誤"""
        try:
            # 增加超時時間、重試等
            self.structured_logger.info(
                error_event.context.operation,
                "嘗試恢復網路連接",
                error_event.context
            )
            
            # 實際實現需要與網路組件配合
            return False
        except Exception as e:
            self.structured_logger.error(
                error_event.context.operation,
                f"網路恢復失敗: {e}",
                error_event.context
            )
            return False
    
    async def _enable_fallback_mode(self, error_event: ErrorEvent) -> bool:
        """啟用降級模式"""
        self.structured_logger.info(
            error_event.context.operation,
            "啟用系統降級模式",
            error_event.context
        )
        # 實際實現：禁用非核心功能、使用簡化邏輯等
        return True
    
    async def _degrade_service(self, error_event: ErrorEvent) -> bool:
        """降級服務"""
        self.structured_logger.info(
            error_event.context.operation,
            "執行服務降級",
            error_event.context
        )
        # 實際實現：降低服務品質、限制功能等
        return True
    
    async def _escalate_error(self, error_event: ErrorEvent) -> bool:
        """升級錯誤處理"""
        self.structured_logger.critical(
            error_event.context.operation,
            f"錯誤升級處理: {error_event.id}",
            error_event.context
        )
        
        self._handler_stats['escalations'] += 1
        
        # 觸發告警
        await self._trigger_alerts(error_event, "escalation")
        
        return True
    
    async def _check_alert_conditions(self, error_event: ErrorEvent, analysis: Dict[str, Any]):
        """檢查告警條件"""
        should_alert = False
        alert_reason = ""
        
        # 嚴重錯誤立即告警
        if error_event.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            should_alert = True
            alert_reason = f"high_severity_{error_event.severity.value}"
        
        # 安全相關錯誤告警
        elif error_event.category == ErrorCategory.SECURITY:
            should_alert = True
            alert_reason = "security_incident"
        
        # 頻繁錯誤告警
        elif analysis.get('frequency_analysis', {}).get('1h', {}).get('count', 0) > self.escalation_threshold:
            should_alert = True
            alert_reason = "high_frequency"
        
        if should_alert:
            await self._trigger_alerts(error_event, alert_reason)
    
    async def _trigger_alerts(self, error_event: ErrorEvent, alert_type: str):
        """觸發告警"""
        alert_data = {
            'error_event': error_event.to_dict(),
            'alert_type': alert_type,
            'timestamp': datetime.now().isoformat()
        }
        
        # 執行所有註冊的告警回調
        for callback in self.alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                self.structured_logger.error(
                    "alert_system",
                    f"告警回調執行失敗: {e}",
                    error_event.context
                )
    
    async def _cleanup_expired_logs(self):
        """清理過期日誌"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小時清理一次
                
                cutoff_time = datetime.now() - timedelta(hours=self.log_retention_hours)
                
                # 清理錯誤事件歷史
                initial_count = len(self.error_history)
                self.error_history = deque(
                    [event for event in self.error_history if event.timestamp > cutoff_time],
                    maxlen=self.error_history.maxlen
                )
                
                cleaned_count = initial_count - len(self.error_history)
                
                if cleaned_count > 0:
                    self.structured_logger.info(
                        "cleanup_task",
                        f"清理了 {cleaned_count} 個過期錯誤事件",
                        metadata={'retention_hours': self.log_retention_hours}
                    )
                
            except Exception as e:
                self.structured_logger.error(
                    "cleanup_task",
                    f"日誌清理任務失敗: {e}"
                )
    
    async def _save_critical_errors(self):
        """保存嚴重錯誤（持久化）"""
        try:
            critical_errors = [
                event for event in self.error_history
                if event.severity == ErrorSeverity.CRITICAL and not event.resolved
            ]
            
            if critical_errors:
                self.structured_logger.info(
                    "persistence",
                    f"需要持久化 {len(critical_errors)} 個嚴重錯誤",
                    metadata={'critical_errors_count': len(critical_errors)}
                )
                
                # 實際實現：保存到文件或資料庫
                
        except Exception as e:
            self.structured_logger.error(
                "persistence",
                f"保存嚴重錯誤失敗: {e}"
            )
    
    # 公開API方法
    
    def register_recovery_strategy(self, error_pattern: str, strategy: Callable):
        """註冊自定義恢復策略"""
        self.recovery_strategies[error_pattern] = strategy
        self.structured_logger.info(
            "strategy_registration",
            f"註冊恢復策略: {error_pattern}"
        )
    
    def register_alert_callback(self, callback: Callable):
        """註冊告警回調"""
        self.alert_callbacks.append(callback)
        self.structured_logger.info(
            "alert_registration",
            f"註冊告警回調: {callback.__name__}"
        )
    
    def get_error_event(self, error_id: str) -> Optional[ErrorEvent]:
        """獲取錯誤事件"""
        return self.error_events.get(error_id)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """獲取錯誤總結"""
        return self.error_analyzer.get_error_summary()
    
    def get_handler_statistics(self) -> Dict[str, Any]:
        """獲取處理器統計"""
        stats = self._handler_stats.copy()
        stats.update({
            'error_analyzer': self.error_analyzer.get_error_summary(),
            'structured_logger': self.structured_logger.get_log_statistics(),
            'recovery_strategies_count': len(self.recovery_strategies),
            'alert_callbacks_count': len(self.alert_callbacks)
        })
        return stats
    
    async def manual_resolve_error(self, error_id: str, resolution_method: str) -> bool:
        """手動解決錯誤"""
        if error_id in self.error_events:
            error_event = self.error_events[error_id]
            error_event.resolved = True
            error_event.resolved_at = datetime.now()
            error_event.resolution_method = f"manual_{resolution_method}"
            
            self._handler_stats['manual_recoveries'] += 1
            self._handler_stats['unresolved_errors'] -= 1
            
            self.structured_logger.info(
                error_event.context.operation,
                f"手動解決錯誤: {error_id}",
                error_event.context,
                resolution_method=resolution_method
            )
            
            return True
        
        return False


# 裝飾器支援

def error_handler(
    severity: Optional[ErrorSeverity] = None,
    category: Optional[ErrorCategory] = None,
    operation_name: Optional[str] = None
):
    """
    錯誤處理裝飾器
    
    Args:
        severity: 錯誤嚴重性
        category: 錯誤分類
        operation_name: 操作名稱
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # 獲取錯誤處理器實例
            handler = await get_error_handler()
            
            # 構建上下文
            context = ErrorContext(
                operation=operation_name or func.__name__,
                additional_data={'function': func.__qualname__}
            )
            
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 處理錯誤
                await handler.handle_error(e, context, severity, category)
                raise  # 重新拋出異常
        
        return wrapper
    return decorator


# 全域實例
_error_handler: Optional[SubBotErrorHandler] = None


async def get_error_handler() -> SubBotErrorHandler:
    """
    獲取全域錯誤處理器實例
    
    Returns:
        錯誤處理器實例
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = SubBotErrorHandler()
        await _error_handler.initialize()
    return _error_handler