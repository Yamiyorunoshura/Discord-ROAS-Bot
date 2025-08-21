"""
部署服務資料模型
Task ID: 11 - 建立文件和部署準備

定義部署系統相關的資料模型
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class EnvironmentType(Enum):
    """環境類型枚舉"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStatus(Enum):
    """部署狀態枚舉"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class DeploymentStrategy(Enum):
    """部署策略枚舉"""
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    RECREATE = "recreate"
    CANARY = "canary"


@dataclass
class EnvironmentConfig:
    """環境配置資料模型"""
    name: str
    environment_type: EnvironmentType
    docker_compose_file: str
    env_variables: Dict[str, str]
    database_url: str
    redis_url: Optional[str] = None
    log_level: str = "INFO"
    debug_mode: bool = False
    max_workers: int = 4
    health_check_url: str = "http://localhost:8000/health"
    backup_enabled: bool = True
    monitoring_enabled: bool = True
    custom_config: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.custom_config is None:
            self.custom_config = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class DeploymentConfig:
    """部署配置資料模型"""
    id: str
    environment: str
    version: str
    strategy: DeploymentStrategy
    docker_image: str
    config_data: Dict[str, Any]
    pre_deploy_scripts: List[str] = None
    post_deploy_scripts: List[str] = None
    rollback_scripts: List[str] = None
    health_checks: List[Dict[str, Any]] = None
    timeout_seconds: int = 600
    auto_rollback: bool = True
    notification_webhooks: List[str] = None
    created_at: Optional[datetime] = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.pre_deploy_scripts is None:
            self.pre_deploy_scripts = []
        if self.post_deploy_scripts is None:
            self.post_deploy_scripts = []
        if self.rollback_scripts is None:
            self.rollback_scripts = []
        if self.health_checks is None:
            self.health_checks = []
        if self.notification_webhooks is None:
            self.notification_webhooks = []
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class DeploymentExecution:
    """部署執行記錄資料模型"""
    id: str
    deployment_config_id: str
    status: DeploymentStatus
    version: str
    environment: str
    started_by: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    logs: List[str] = None
    error_message: Optional[str] = None
    rollback_version: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class HealthCheckResult:
    """健康檢查結果資料模型"""
    service_name: str
    endpoint_url: str
    status_code: int
    response_time_ms: float
    is_healthy: bool
    message: str
    details: Dict[str, Any] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class BackupInfo:
    """備份信息資料模型"""
    id: str
    environment: str
    backup_type: str  # database, files, config
    file_path: str
    size_bytes: int
    checksum: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DeploymentMetrics:
    """部署指標資料模型"""
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    average_deployment_time: float
    rollback_count: int
    environments_count: int
    last_deployment_time: Optional[datetime] = None
    success_rate: float = 0.0
    
    def __post_init__(self):
        if self.total_deployments > 0:
            self.success_rate = self.successful_deployments / self.total_deployments


@dataclass
class ContainerInfo:
    """容器信息資料模型"""
    container_id: str
    image: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    ports: Dict[str, str] = None
    environment_vars: Dict[str, str] = None
    resource_usage: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.ports is None:
            self.ports = {}
        if self.environment_vars is None:
            self.environment_vars = {}
        if self.resource_usage is None:
            self.resource_usage = {}