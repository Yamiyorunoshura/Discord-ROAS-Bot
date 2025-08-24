"""
T2 - 高併發連線競爭修復
連線池管理資料模型

定義連線池監控和統計相關的資料結構
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any, List
from datetime import datetime
from enum import Enum


class ConnectionStatus(Enum):
    """連線狀態枚舉"""
    IDLE = "idle"           # 空閒
    ACTIVE = "active"       # 活躍使用中
    WAITING = "waiting"     # 等待獲取連線
    ERROR = "error"         # 錯誤狀態
    CLOSED = "closed"       # 已關閉


@dataclass
class ConnectionInfo:
    """個別連線資訊"""
    connection_id: str
    status: ConnectionStatus
    created_at: datetime
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    errors_count: int = 0


@dataclass
class ConnectionPoolStats:
    """連線池統計資料"""
    timestamp: datetime
    active_connections: int
    idle_connections: int
    waiting_requests: int
    max_connections: int
    total_connections_created: int
    total_requests_served: int
    average_wait_time_ms: float
    error_count: int
    success_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'active_connections': self.active_connections,
            'idle_connections': self.idle_connections,
            'waiting_requests': self.waiting_requests,
            'max_connections': self.max_connections,
            'total_connections_created': self.total_connections_created,
            'total_requests_served': self.total_requests_served,
            'average_wait_time_ms': self.average_wait_time_ms,
            'error_count': self.error_count,
            'success_rate': self.success_rate
        }


@dataclass
class PoolConfiguration:
    """連線池配置"""
    min_connections: int = 2
    max_connections: int = 20
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0
    acquire_timeout: float = 10.0
    retry_attempts: int = 3
    enable_monitoring: bool = True
    stats_collection_interval: int = 60
    
    def validate(self) -> List[str]:
        """驗證配置參數"""
        errors = []
        
        if self.min_connections < 0:
            errors.append("min_connections 不能為負數")
        
        if self.max_connections <= 0:
            errors.append("max_connections 必須為正數")
        
        if self.min_connections > self.max_connections:
            errors.append("min_connections 不能大於 max_connections")
        
        if self.connection_timeout <= 0:
            errors.append("connection_timeout 必須為正數")
        
        if self.acquire_timeout <= 0:
            errors.append("acquire_timeout 必須為正數")
        
        return errors


@dataclass
class LoadMetrics:
    """負載指標"""
    cpu_usage: float
    memory_usage_mb: float
    active_requests: int
    queue_length: int
    average_response_time_ms: float
    timestamp: datetime
    
    def calculate_load_score(self) -> float:
        """計算綜合負載分數 (0-100)"""
        # 加權計算負載分數
        weights = {
            'cpu': 0.3,
            'memory': 0.2,
            'requests': 0.3,
            'queue': 0.2
        }
        
        # 正規化各指標到0-100範圍
        cpu_score = min(self.cpu_usage, 100)
        memory_score = min(self.memory_usage_mb / 10, 100)  # 假設1GB為滿載
        requests_score = min(self.active_requests * 5, 100)  # 20個請求為滿載
        queue_score = min(self.queue_length * 10, 100)      # 10個排隊為滿載
        
        return (
            cpu_score * weights['cpu'] +
            memory_score * weights['memory'] +
            requests_score * weights['requests'] +
            queue_score * weights['queue']
        )


@dataclass
class PerformanceMetrics:
    """效能指標"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    throughput_rps: float
    error_rate: float
    
    @classmethod
    def create_empty(cls) -> 'PerformanceMetrics':
        """創建空的效能指標"""
        return cls(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            total_response_time_ms=0.0,
            min_response_time_ms=0.0,
            max_response_time_ms=0.0,
            p50_response_time_ms=0.0,
            p95_response_time_ms=0.0,
            p99_response_time_ms=0.0,
            throughput_rps=0.0,
            error_rate=0.0
        )