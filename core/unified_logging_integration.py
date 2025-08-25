#!/usr/bin/env python3
"""
統一日誌和錯誤處理整合系統
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組整合所有服務的錯誤處理和日誌記錄，提供統一的日誌格式、
分散式追蹤、錯誤聚合和智能分析功能。
"""

import asyncio
import json
import logging
import logging.handlers
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable, TextIO
from contextlib import contextmanager, asynccontextmanager
import threading
import queue
import traceback

from .error_handler import ErrorHandler, DeploymentError, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """日誌等級"""
    TRACE = "trace"
    DEBUG = "debug" 
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogSource(Enum):
    """日誌來源"""
    DISCORD_BOT = "discord-bot"
    REDIS = "redis"
    PROMETHEUS = "prometheus"
    GRAFANA = "grafana"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    INTEGRATION = "integration"
    SYSTEM = "system"


@dataclass
class LogContext:
    """日誌上下文"""
    trace_id: str
    span_id: str
    service_name: str
    component: str
    operation: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredLogEntry:
    """結構化日誌條目"""
    timestamp: datetime
    level: LogLevel
    source: LogSource
    message: str
    context: LogContext
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    duration_ms: Optional[float] = None
    error_code: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, Union[int, float]] = field(default_factory=dict)


@dataclass
class ErrorAggregation:
    """錯誤聚合統計"""
    error_type: str
    count: int
    first_occurrence: datetime
    last_occurrence: datetime
    affected_services: List[str]
    error_rate: float
    sample_messages: List[str]


@dataclass
class LogAnalysisReport:
    """日誌分析報告"""
    timestamp: datetime
    time_range_hours: int
    total_logs: int
    log_level_distribution: Dict[str, int]
    error_aggregations: List[ErrorAggregation]
    top_errors: List[str]
    service_error_rates: Dict[str, float]
    performance_issues: List[str]
    recommendations: List[str]


class StructuredLogger:
    """結構化日誌記錄器"""
    
    def __init__(self, service_name: str, component: str):
        self.service_name = service_name
        self.component = component
        self.context_stack: List[LogContext] = []
        
    def create_context(self, operation: str, trace_id: Optional[str] = None,
                      span_id: Optional[str] = None, **kwargs) -> LogContext:
        """創建日誌上下文"""
        return LogContext(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=span_id or str(uuid.uuid4())[:8],
            service_name=self.service_name,
            component=self.component,
            operation=operation,
            **kwargs
        )
    
    @contextmanager
    def context(self, operation: str, **kwargs):
        """日誌上下文管理器"""
        ctx = self.create_context(operation, **kwargs)
        self.context_stack.append(ctx)
        start_time = time.time()
        
        try:
            yield ctx
        finally:
            # 記錄操作完成
            duration_ms = (time.time() - start_time) * 1000
            if self.context_stack:
                self.context_stack.pop()
    
    def get_current_context(self) -> Optional[LogContext]:
        """獲取當前上下文"""
        return self.context_stack[-1] if self.context_stack else None
    
    def log(self, level: LogLevel, message: str, **kwargs) -> None:
        """記錄結構化日誌"""
        context = self.get_current_context()
        if not context:
            # 創建默認上下文
            context = self.create_context("default")
        
        entry = StructuredLogEntry(
            timestamp=datetime.now(),
            level=level,
            source=LogSource(self.service_name),
            message=message,
            context=context,
            **kwargs
        )
        
        # 發送到統一日誌處理器
        UnifiedLogHandler.get_instance().handle_log(entry)
    
    def trace(self, message: str, **kwargs):
        """記錄追蹤日誌"""
        self.log(LogLevel.TRACE, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """記錄除錯日誌"""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """記錄資訊日誌"""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """記錄警告日誌"""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """記錄錯誤日誌"""
        kwargs.update({
            'exception': str(exception) if exception else None,
            'stack_trace': traceback.format_exc() if exception else None
        })
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """記錄關鍵錯誤日誌"""
        kwargs.update({
            'exception': str(exception) if exception else None,
            'stack_trace': traceback.format_exc() if exception else None
        })
        self.log(LogLevel.CRITICAL, message, **kwargs)


class UnifiedLogHandler:
    """統一日誌處理器（單例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.project_root = Path.cwd()
        self.log_queue = queue.Queue(maxsize=10000)
        self.error_handler = ErrorHandler(self.project_root)
        
        # 日誌緩衝區
        self.log_buffer: List[StructuredLogEntry] = []
        self.buffer_lock = threading.Lock()
        
        # 統計數據
        self.stats = {
            'total_logs': 0,
            'error_count': 0,
            'last_flush': datetime.now()
        }
        
        # 啟動日誌處理線程
        self.processing_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.processing_thread.start()
        
        # 設置標準日誌處理器
        self._setup_standard_loggers()
    
    @classmethod
    def get_instance(cls):
        """獲取單例實例"""
        if cls._instance is None:
            cls()
        return cls._instance
    
    def handle_log(self, entry: StructuredLogEntry) -> None:
        """處理日誌條目"""
        try:
            self.log_queue.put_nowait(entry)
        except queue.Full:
            # 隊列滿了，記錄警告並丟棄最舊的日誌
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(entry)
            except queue.Empty:
                pass
    
    def _process_logs(self) -> None:
        """日誌處理線程"""
        while True:
            try:
                # 批量處理日誌
                batch = []
                deadline = time.time() + 1.0  # 1秒批處理超時
                
                while len(batch) < 100 and time.time() < deadline:
                    try:
                        entry = self.log_queue.get(timeout=0.1)
                        batch.append(entry)
                    except queue.Empty:
                        break
                
                if batch:
                    self._process_log_batch(batch)
                
            except Exception as e:
                # 日誌處理出錯，避免無限循環
                print(f"日誌處理異常: {e}", file=__import__('sys').stderr)
                time.sleep(1)
    
    def _process_log_batch(self, batch: List[StructuredLogEntry]) -> None:
        """處理日誌批次"""
        with self.buffer_lock:
            self.log_buffer.extend(batch)
            
            # 更新統計
            self.stats['total_logs'] += len(batch)
            error_count = sum(1 for entry in batch 
                            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL])
            self.stats['error_count'] += error_count
            
            # 寫入文件
            self._write_to_files(batch)
            
            # 錯誤處理
            self._handle_errors(batch)
            
            # 清理舊日誌
            if len(self.log_buffer) > 50000:
                self.log_buffer = self.log_buffer[-25000:]
    
    def _write_to_files(self, batch: List[StructuredLogEntry]) -> None:
        """寫入日誌文件"""
        # 按服務分組
        service_logs = {}
        for entry in batch:
            service = entry.source.value
            if service not in service_logs:
                service_logs[service] = []
            service_logs[service].append(entry)
        
        # 寫入各服務日誌文件
        for service, entries in service_logs.items():
            log_file = self.project_root / 'logs' / f'{service}-integration.log'
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    for entry in entries:
                        log_line = self._format_log_entry(entry)
                        f.write(log_line + '\n')
            except Exception as e:
                print(f"寫入日誌文件失敗 {log_file}: {e}", file=__import__('sys').stderr)
        
        # 寫入統一日誌文件（JSON格式）
        unified_log_file = self.project_root / 'logs' / 'unified-integration.jsonl'
        try:
            with open(unified_log_file, 'a', encoding='utf-8') as f:
                for entry in batch:
                    json_line = json.dumps(self._serialize_log_entry(entry), 
                                         ensure_ascii=False, default=str)
                    f.write(json_line + '\n')
        except Exception as e:
            print(f"寫入統一日誌文件失敗: {e}", file=__import__('sys').stderr)
    
    def _handle_errors(self, batch: List[StructuredLogEntry]) -> None:
        """處理錯誤日誌"""
        for entry in batch:
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                try:
                    # 創建部署錯誤
                    deployment_error = DeploymentError(
                        error_id=f"LOG-{entry.context.trace_id}",
                        timestamp=entry.timestamp,
                        category=self._map_to_error_category(entry),
                        severity=self._map_to_error_severity(entry.level),
                        title=f"{entry.source.value}: {entry.message[:100]}",
                        message=entry.message,
                        context={
                            'service': entry.source.value,
                            'component': entry.context.component,
                            'operation': entry.context.operation,
                            'trace_id': entry.context.trace_id
                        },
                        stack_trace=entry.stack_trace
                    )
                    
                    # 異步處理錯誤
                    asyncio.create_task(
                        self.error_handler.log_structured_error(deployment_error)
                    )
                    
                except Exception as e:
                    print(f"錯誤處理失敗: {e}", file=__import__('sys').stderr)
    
    def _format_log_entry(self, entry: StructuredLogEntry) -> str:
        """格式化日誌條目為可讀格式"""
        timestamp = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        level = entry.level.value.upper()
        service = entry.source.value
        component = entry.context.component
        operation = entry.context.operation
        trace_id = entry.context.trace_id[:8]
        
        # 基礎格式
        base_format = f"{timestamp} [{level}] {service}/{component} [{trace_id}] {operation}: {entry.message}"
        
        # 添加額外信息
        extras = []
        if entry.duration_ms:
            extras.append(f"duration={entry.duration_ms:.1f}ms")
        if entry.error_code:
            extras.append(f"code={entry.error_code}")
        if entry.metrics:
            metrics_str = ' '.join([f"{k}={v}" for k, v in entry.metrics.items()])
            extras.append(f"metrics=[{metrics_str}]")
        
        if extras:
            base_format += f" ({', '.join(extras)})"
        
        # 添加異常信息
        if entry.exception:
            base_format += f"\n  Exception: {entry.exception}"
        
        return base_format
    
    def _serialize_log_entry(self, entry: StructuredLogEntry) -> Dict[str, Any]:
        """序列化日誌條目為字典"""
        return {
            'timestamp': entry.timestamp.isoformat(),
            'level': entry.level.value,
            'source': entry.source.value,
            'message': entry.message,
            'context': {
                'trace_id': entry.context.trace_id,
                'span_id': entry.context.span_id,
                'service_name': entry.context.service_name,
                'component': entry.context.component,
                'operation': entry.context.operation,
                'user_id': entry.context.user_id,
                'request_id': entry.context.request_id,
                'session_id': entry.context.session_id,
                'metadata': entry.context.metadata
            },
            'exception': entry.exception,
            'stack_trace': entry.stack_trace,
            'duration_ms': entry.duration_ms,
            'error_code': entry.error_code,
            'tags': entry.tags,
            'metrics': entry.metrics
        }
    
    def _map_to_error_category(self, entry: StructuredLogEntry) -> ErrorCategory:
        """映射日誌條目到錯誤分類"""
        message_lower = entry.message.lower()
        
        if 'docker' in message_lower or 'container' in message_lower:
            return ErrorCategory.DOCKER
        elif 'network' in message_lower or 'connection' in message_lower:
            return ErrorCategory.NETWORK
        elif 'permission' in message_lower or 'access' in message_lower:
            return ErrorCategory.PERMISSION
        elif 'config' in message_lower:
            return ErrorCategory.CONFIGURATION
        elif 'memory' in message_lower or 'disk' in message_lower:
            return ErrorCategory.RESOURCE
        elif entry.source == LogSource.REDIS:
            return ErrorCategory.SERVICE
        elif entry.source == LogSource.DISCORD_BOT:
            return ErrorCategory.SERVICE
        else:
            return ErrorCategory.UNKNOWN
    
    def _map_to_error_severity(self, level: LogLevel) -> ErrorSeverity:
        """映射日誌等級到錯誤嚴重性"""
        if level == LogLevel.CRITICAL:
            return ErrorSeverity.CRITICAL
        elif level == LogLevel.ERROR:
            return ErrorSeverity.HIGH
        elif level == LogLevel.WARNING:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _setup_standard_loggers(self) -> None:
        """設置標準日誌記錄器"""
        # 為Python標準logging設置處理器
        class StructuredLogAdapter(logging.Handler):
            def __init__(self, log_handler, source: LogSource):
                super().__init__()
                self.log_handler = log_handler
                self.source = source
            
            def emit(self, record):
                try:
                    # 轉換為結構化日誌
                    level_map = {
                        logging.DEBUG: LogLevel.DEBUG,
                        logging.INFO: LogLevel.INFO,
                        logging.WARNING: LogLevel.WARNING,
                        logging.ERROR: LogLevel.ERROR,
                        logging.CRITICAL: LogLevel.CRITICAL
                    }
                    
                    level = level_map.get(record.levelno, LogLevel.INFO)
                    message = record.getMessage()
                    
                    # 創建上下文
                    context = LogContext(
                        trace_id=str(uuid.uuid4()),
                        span_id=str(uuid.uuid4())[:8],
                        service_name=self.source.value,
                        component=record.name,
                        operation="log"
                    )
                    
                    # 創建結構化日誌條目
                    entry = StructuredLogEntry(
                        timestamp=datetime.fromtimestamp(record.created),
                        level=level,
                        source=self.source,
                        message=message,
                        context=context,
                        exception=str(record.exc_info[1]) if record.exc_info else None,
                        stack_trace=self.format(record) if record.exc_info else None
                    )
                    
                    self.log_handler.handle_log(entry)
                    
                except Exception:
                    pass  # 避免日誌處理中的錯誤導致程序崩潰
        
        # 設置各服務的日誌適配器
        services = [
            ('discord-bot', LogSource.DISCORD_BOT),
            ('redis', LogSource.REDIS),
            ('prometheus', LogSource.PROMETHEUS),
            ('grafana', LogSource.GRAFANA),
            ('deployment', LogSource.DEPLOYMENT),
            ('monitoring', LogSource.MONITORING),
            ('integration', LogSource.INTEGRATION)
        ]
        
        for service_name, source in services:
            logger = logging.getLogger(service_name)
            adapter = StructuredLogAdapter(self, source)
            logger.addHandler(adapter)
            logger.setLevel(logging.INFO)
    
    def get_logs(self, service: Optional[str] = None, level: Optional[LogLevel] = None,
                hours: int = 24, limit: int = 1000) -> List[StructuredLogEntry]:
        """獲取日誌"""
        with self.buffer_lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            filtered_logs = []
            for entry in self.log_buffer:
                if entry.timestamp < cutoff_time:
                    continue
                if service and entry.source.value != service:
                    continue
                if level and entry.level != level:
                    continue
                
                filtered_logs.append(entry)
                
                if len(filtered_logs) >= limit:
                    break
            
            return filtered_logs
    
    def analyze_logs(self, hours: int = 24) -> LogAnalysisReport:
        """分析日誌"""
        with self.buffer_lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_logs = [
                entry for entry in self.log_buffer
                if entry.timestamp >= cutoff_time
            ]
        
        if not recent_logs:
            return LogAnalysisReport(
                timestamp=datetime.now(),
                time_range_hours=hours,
                total_logs=0,
                log_level_distribution={},
                error_aggregations=[],
                top_errors=[],
                service_error_rates={},
                performance_issues=[],
                recommendations=["無足夠日誌數據進行分析"]
            )
        
        # 統計日誌等級分布
        level_distribution = {}
        for entry in recent_logs:
            level = entry.level.value
            level_distribution[level] = level_distribution.get(level, 0) + 1
        
        # 錯誤聚合
        error_aggregations = self._aggregate_errors(recent_logs)
        
        # 頂級錯誤
        error_messages = [entry.message for entry in recent_logs 
                         if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        top_errors = list(set(error_messages))[:10]
        
        # 服務錯誤率
        service_error_rates = self._calculate_service_error_rates(recent_logs)
        
        # 性能問題
        performance_issues = self._identify_performance_issues(recent_logs)
        
        # 建議
        recommendations = self._generate_log_recommendations(
            recent_logs, error_aggregations, service_error_rates
        )
        
        return LogAnalysisReport(
            timestamp=datetime.now(),
            time_range_hours=hours,
            total_logs=len(recent_logs),
            log_level_distribution=level_distribution,
            error_aggregations=error_aggregations,
            top_errors=top_errors,
            service_error_rates=service_error_rates,
            performance_issues=performance_issues,
            recommendations=recommendations
        )
    
    def _aggregate_errors(self, logs: List[StructuredLogEntry]) -> List[ErrorAggregation]:
        """聚合錯誤"""
        error_groups = {}
        
        for entry in logs:
            if entry.level not in [LogLevel.ERROR, LogLevel.CRITICAL]:
                continue
            
            # 簡單的錯誤分組（基於消息的前100個字符）
            error_key = entry.message[:100]
            
            if error_key not in error_groups:
                error_groups[error_key] = {
                    'count': 0,
                    'first_occurrence': entry.timestamp,
                    'last_occurrence': entry.timestamp,
                    'services': set(),
                    'messages': []
                }
            
            group = error_groups[error_key]
            group['count'] += 1
            group['last_occurrence'] = max(group['last_occurrence'], entry.timestamp)
            group['first_occurrence'] = min(group['first_occurrence'], entry.timestamp)
            group['services'].add(entry.source.value)
            
            if len(group['messages']) < 3:
                group['messages'].append(entry.message)
        
        # 轉換為ErrorAggregation對象
        aggregations = []
        for error_key, group in error_groups.items():
            duration_hours = (group['last_occurrence'] - group['first_occurrence']).total_seconds() / 3600
            error_rate = group['count'] / max(duration_hours, 1)
            
            aggregations.append(ErrorAggregation(
                error_type=error_key,
                count=group['count'],
                first_occurrence=group['first_occurrence'],
                last_occurrence=group['last_occurrence'],
                affected_services=list(group['services']),
                error_rate=error_rate,
                sample_messages=group['messages']
            ))
        
        # 按錯誤數量排序
        return sorted(aggregations, key=lambda x: x.count, reverse=True)[:20]
    
    def _calculate_service_error_rates(self, logs: List[StructuredLogEntry]) -> Dict[str, float]:
        """計算服務錯誤率"""
        service_stats = {}
        
        for entry in logs:
            service = entry.source.value
            if service not in service_stats:
                service_stats[service] = {'total': 0, 'errors': 0}
            
            service_stats[service]['total'] += 1
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                service_stats[service]['errors'] += 1
        
        error_rates = {}
        for service, stats in service_stats.items():
            error_rates[service] = (stats['errors'] / stats['total']) * 100
        
        return error_rates
    
    def _identify_performance_issues(self, logs: List[StructuredLogEntry]) -> List[str]:
        """識別性能問題"""
        issues = []
        
        # 檢查慢操作
        slow_operations = []
        for entry in logs:
            if entry.duration_ms and entry.duration_ms > 5000:  # 5秒以上
                slow_operations.append(f"{entry.source.value}/{entry.context.operation}: {entry.duration_ms:.0f}ms")
        
        if slow_operations:
            issues.append(f"發現 {len(slow_operations)} 個慢操作")
            issues.extend(slow_operations[:5])  # 只顯示前5個
        
        # 檢查高頻錯誤
        error_count = sum(1 for entry in logs if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL])
        if error_count > len(logs) * 0.1:  # 錯誤率超過10%
            issues.append(f"錯誤率過高: {(error_count/len(logs)*100):.1f}%")
        
        return issues
    
    def _generate_log_recommendations(self, logs: List[StructuredLogEntry],
                                    error_aggregations: List[ErrorAggregation],
                                    service_error_rates: Dict[str, float]) -> List[str]:
        """生成日誌建議"""
        recommendations = []
        
        # 基於錯誤率的建議
        high_error_services = [
            service for service, rate in service_error_rates.items()
            if rate > 5  # 錯誤率超過5%
        ]
        
        if high_error_services:
            recommendations.append(f"檢查高錯誤率服務: {', '.join(high_error_services)}")
        
        # 基於錯誤聚合的建議
        if error_aggregations:
            top_error = error_aggregations[0]
            if top_error.count > 10:
                recommendations.append(f"優先處理頻繁錯誤: {top_error.error_type[:50]}...")
        
        # 基於日誌量的建議
        if len(logs) < 100:
            recommendations.append("日誌量較少，考慮增加日誌詳細程度")
        elif len(logs) > 10000:
            recommendations.append("日誌量過大，考慮提高日誌等級或增加過濾")
        
        if not recommendations:
            recommendations.append("日誌狀況正常")
        
        return recommendations
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計信息"""
        with self.buffer_lock:
            return {
                'total_logs': self.stats['total_logs'],
                'error_count': self.stats['error_count'],
                'buffer_size': len(self.log_buffer),
                'queue_size': self.log_queue.qsize(),
                'last_flush': self.stats['last_flush'].isoformat(),
                'thread_alive': self.processing_thread.is_alive()
            }


# 工廠方法和便利函數
def create_logger(service_name: str, component: str) -> StructuredLogger:
    """創建結構化日誌記錄器"""
    return StructuredLogger(service_name, component)


def get_log_handler() -> UnifiedLogHandler:
    """獲取統一日誌處理器"""
    return UnifiedLogHandler.get_instance()


# 裝飾器
def log_operation(logger: StructuredLogger, operation_name: str):
    """操作日誌記錄裝飾器"""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                with logger.context(operation_name) as ctx:
                    start_time = time.time()
                    try:
                        logger.info(f"開始操作: {operation_name}")
                        result = await func(*args, **kwargs)
                        duration_ms = (time.time() - start_time) * 1000
                        logger.info(f"操作完成: {operation_name}", 
                                  duration_ms=duration_ms)
                        return result
                    except Exception as e:
                        duration_ms = (time.time() - start_time) * 1000
                        logger.error(f"操作失敗: {operation_name}", 
                                   exception=e, duration_ms=duration_ms)
                        raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with logger.context(operation_name) as ctx:
                    start_time = time.time()
                    try:
                        logger.info(f"開始操作: {operation_name}")
                        result = func(*args, **kwargs)
                        duration_ms = (time.time() - start_time) * 1000
                        logger.info(f"操作完成: {operation_name}", 
                                  duration_ms=duration_ms)
                        return result
                    except Exception as e:
                        duration_ms = (time.time() - start_time) * 1000
                        logger.error(f"操作失敗: {operation_name}", 
                                   exception=e, duration_ms=duration_ms)
                        raise
            return sync_wrapper
    return decorator


# 命令行介面
async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 統一日誌分析工具')
    parser.add_argument('command', choices=['analyze', 'logs', 'stats', 'test'],
                       help='執行的命令')
    parser.add_argument('--service', '-s', help='指定服務名稱')
    parser.add_argument('--level', choices=['trace', 'debug', 'info', 'warning', 'error', 'critical'],
                       help='日誌等級過濾')
    parser.add_argument('--hours', type=int, default=24, help='時間範圍（小時）')
    parser.add_argument('--limit', type=int, default=1000, help='日誌數量限制')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        handler = get_log_handler()
        
        if args.command == 'analyze':
            report = handler.analyze_logs(args.hours)
            
            print(f"\n{'='*60}")
            print("📊 ROAS Bot v2.4.3 日誌分析報告")
            print(f"{'='*60}")
            print(f"分析時間範圍: {report.time_range_hours} 小時")
            print(f"總日誌數量: {report.total_logs}")
            
            if report.log_level_distribution:
                print(f"\n日誌等級分布:")
                for level, count in report.log_level_distribution.items():
                    print(f"  {level}: {count}")
            
            if report.error_aggregations:
                print(f"\n錯誤聚合 (前5名):")
                for i, agg in enumerate(report.error_aggregations[:5], 1):
                    print(f"  {i}. {agg.error_type[:60]}...")
                    print(f"     出現次數: {agg.count}, 錯誤率: {agg.error_rate:.2f}/小時")
                    print(f"     影響服務: {', '.join(agg.affected_services)}")
            
            if report.service_error_rates:
                print(f"\n服務錯誤率:")
                for service, rate in report.service_error_rates.items():
                    print(f"  {service}: {rate:.2f}%")
            
            if report.performance_issues:
                print(f"\n性能問題:")
                for issue in report.performance_issues:
                    print(f"  • {issue}")
            
            if report.recommendations:
                print(f"\n建議:")
                for rec in report.recommendations:
                    print(f"  • {rec}")
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(asdict(report), f, indent=2, ensure_ascii=False, default=str)
                print(f"\n報告已保存到: {args.output}")
            
            return 0
            
        elif args.command == 'logs':
            level_filter = LogLevel(args.level) if args.level else None
            logs = handler.get_logs(
                service=args.service,
                level=level_filter,
                hours=args.hours,
                limit=args.limit
            )
            
            print(f"找到 {len(logs)} 條日誌")
            
            for entry in logs[-20:]:  # 顯示最後20條
                timestamp = entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                level = entry.level.value.upper()
                service = entry.source.value
                print(f"[{timestamp}] [{level}] {service}: {entry.message}")
            
            return 0
            
        elif args.command == 'stats':
            stats = handler.get_stats()
            
            print("📈 日誌處理統計:")
            print(f"  總日誌數: {stats['total_logs']}")
            print(f"  錯誤數量: {stats['error_count']}")
            print(f"  緩衝區大小: {stats['buffer_size']}")
            print(f"  隊列大小: {stats['queue_size']}")
            print(f"  最後刷新: {stats['last_flush']}")
            print(f"  處理線程狀態: {'活躍' if stats['thread_alive'] else '停止'}")
            
            return 0
            
        elif args.command == 'test':
            # 測試日誌記錄
            test_logger = create_logger("test-service", "test-component")
            
            with test_logger.context("test-operation") as ctx:
                test_logger.info("測試資訊日誌")
                test_logger.warning("測試警告日誌")
                test_logger.error("測試錯誤日誌", error_code="TEST-001")
            
            # 等待日誌處理
            await asyncio.sleep(2)
            
            print("測試日誌已記錄")
            return 0
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))