# 監控系統模型
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import json

class HealthStatus(Enum):
    """健康狀態枚舉"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class MonitoringType(Enum):
    """監控類型枚舉"""
    HEALTH_CHECK = "health_check"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    SERVICE = "service"
    DATABASE = "database"
    API = "api"

class AlertLevel(Enum):
    """警報級別枚舉"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MaintenanceType(Enum):
    """維護類型枚舉"""
    LOG_CLEANUP = "log_cleanup"
    DATABASE_OPTIMIZATION = "database_optimization"
    BACKUP_MANAGEMENT = "backup_management"
    CACHE_CLEANUP = "cache_cleanup"
    SYSTEM_UPDATE = "system_update"

@dataclass
class HealthCheckResult:
    """健康檢查結果"""
    component: str
    status: HealthStatus
    message: str
    checked_at: datetime
    response_time_ms: float
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'component': self.component,
            'status': self.status.value,
            'message': self.message,
            'checked_at': self.checked_at.isoformat(),
            'response_time_ms': self.response_time_ms,
            'details': self.details or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthCheckResult':
        """從字典創建實例"""
        return cls(
            component=data['component'],
            status=HealthStatus(data['status']),
            message=data['message'],
            checked_at=datetime.fromisoformat(data['checked_at']),
            response_time_ms=data['response_time_ms'],
            details=data.get('details')
        )

@dataclass
class SystemHealth:
    """系統整體健康狀態"""
    overall_status: HealthStatus
    checked_at: datetime
    components: List[HealthCheckResult]
    total_checks: int
    healthy_count: int
    warning_count: int
    critical_count: int
    scan_duration_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'overall_status': self.overall_status.value,
            'checked_at': self.checked_at.isoformat(),
            'components': [c.to_dict() for c in self.components],
            'total_checks': self.total_checks,
            'healthy_count': self.healthy_count,
            'warning_count': self.warning_count,
            'critical_count': self.critical_count,
            'scan_duration_ms': self.scan_duration_ms
        }

@dataclass
class PerformanceMetric:
    """效能指標"""
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    component: str
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    @property
    def status(self) -> HealthStatus:
        """根據閾值計算狀態"""
        if self.threshold_critical and self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.threshold_warning and self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'metric_name': self.metric_name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'component': self.component,
            'threshold_warning': self.threshold_warning,
            'threshold_critical': self.threshold_critical,
            'status': self.status.value
        }

@dataclass
class PerformanceReport:
    """效能報告"""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    metrics: List[PerformanceMetric]
    summary: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'report_id': self.report_id,
            'generated_at': self.generated_at.isoformat(),
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'metrics': [m.to_dict() for m in self.metrics],
            'summary': self.summary
        }

@dataclass
class MaintenanceTask:
    """維護任務"""
    task_id: str
    task_type: MaintenanceType
    title: str
    description: str
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "scheduled"  # scheduled, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value,
            'title': self.title,
            'description': self.description,
            'scheduled_at': self.scheduled_at.isoformat(),
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'result': self.result,
            'error_message': self.error_message
        }

@dataclass
class Alert:
    """警報"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    component: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'alert_id': self.alert_id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'component': self.component,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'metadata': self.metadata or {}
        }

@dataclass
class MonitoringConfig:
    """監控配置"""
    health_check_interval: int = 60  # 秒
    performance_monitoring_interval: int = 300  # 秒
    maintenance_schedule: Dict[str, str] = None  # cron expressions
    alert_thresholds: Dict[str, Dict[str, float]] = None
    notification_webhooks: List[str] = None
    retention_days: int = 30
    
    def __post_init__(self):
        if self.maintenance_schedule is None:
            self.maintenance_schedule = {
                'log_cleanup': '0 2 * * *',  # 每天2點
                'database_optimization': '0 3 * * 0',  # 每週日3點
                'backup_management': '0 1 * * *'  # 每天1點
            }
        
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                'cpu_usage': {'warning': 70.0, 'critical': 90.0},
                'memory_usage': {'warning': 80.0, 'critical': 95.0},
                'disk_usage': {'warning': 85.0, 'critical': 95.0},
                'response_time': {'warning': 1000.0, 'critical': 5000.0},  # ms
                'error_rate': {'warning': 5.0, 'critical': 10.0}  # %
            }
        
        if self.notification_webhooks is None:
            self.notification_webhooks = []
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'health_check_interval': self.health_check_interval,
            'performance_monitoring_interval': self.performance_monitoring_interval,
            'maintenance_schedule': self.maintenance_schedule,
            'alert_thresholds': self.alert_thresholds,
            'notification_webhooks': self.notification_webhooks,
            'retention_days': self.retention_days
        }