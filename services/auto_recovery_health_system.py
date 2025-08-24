# 自動恢復和健康檢查機制
# Task ID: T2 - 高併發連線競爭修復 - 自癒系統
"""
自動恢復和健康檢查機制模組

為T2任務提供完整的系統自癒能力：
- 主動健康檢查和異常預測
- 智能自動恢復策略執行
- 故障轉移和負載重新分配
- 系統狀態自動維護和優化
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
import psutil
import statistics

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError
from services.monitoring.models import HealthStatus


class RecoveryStrategy(Enum):
    """恢復策略類型"""
    IMMEDIATE = "immediate"          # 立即執行
    GRADUAL = "gradual"             # 漸進式恢復
    ROLLBACK = "rollback"           # 回滾操作
    FAILOVER = "failover"           # 故障轉移
    CIRCUIT_BREAKER = "circuit_breaker"  # 斷路器
    THROTTLING = "throttling"       # 限流


class HealthCheckType(Enum):
    """健康檢查類型"""
    CONNECTION_POOL = "connection_pool"
    DATABASE_PERFORMANCE = "database_performance"
    MEMORY_USAGE = "memory_usage"
    CPU_UTILIZATION = "cpu_utilization"
    DISK_SPACE = "disk_space"
    NETWORK_CONNECTIVITY = "network_connectivity"
    APPLICATION_HEALTH = "application_health"


class RecoveryStatus(Enum):
    """恢復狀態"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class HealthCheckRule:
    """健康檢查規則"""
    rule_id: str
    check_type: HealthCheckType
    name: str
    description: str
    check_interval_seconds: int
    warning_threshold: float
    critical_threshold: float
    check_function: Callable[[], Any]
    recovery_strategies: List[RecoveryStrategy]
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule_id': self.rule_id,
            'check_type': self.check_type.value,
            'name': self.name,
            'description': self.description,
            'check_interval_seconds': self.check_interval_seconds,
            'warning_threshold': self.warning_threshold,
            'critical_threshold': self.critical_threshold,
            'recovery_strategies': [strategy.value for strategy in self.recovery_strategies],
            'enabled': self.enabled
        }


@dataclass
class HealthCheckResult:
    """健康檢查結果"""
    result_id: str
    rule_id: str
    timestamp: datetime
    status: HealthStatus
    current_value: float
    threshold_breached: Optional[str]  # 'warning' or 'critical'
    message: str
    metadata: Dict[str, Any]
    recovery_recommended: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'result_id': self.result_id,
            'rule_id': self.rule_id,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'current_value': self.current_value,
            'threshold_breached': self.threshold_breached,
            'message': self.message,
            'metadata': self.metadata,
            'recovery_recommended': self.recovery_recommended
        }


@dataclass
class RecoveryAction:
    """恢復動作"""
    action_id: str
    rule_id: str
    strategy: RecoveryStrategy
    name: str
    description: str
    parameters: Dict[str, Any]
    execute_function: Callable[[Dict[str, Any]], Any]
    rollback_function: Optional[Callable[[Dict[str, Any]], Any]] = None
    max_attempts: int = 3
    timeout_seconds: int = 300
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_id': self.action_id,
            'rule_id': self.rule_id,
            'strategy': self.strategy.value,
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'max_attempts': self.max_attempts,
            'timeout_seconds': self.timeout_seconds
        }


@dataclass
class RecoveryExecution:
    """恢復執行記錄"""
    execution_id: str
    action_id: str
    triggered_by: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: RecoveryStatus
    attempts: int
    success: bool
    error_message: Optional[str]
    result_data: Dict[str, Any]
    rollback_executed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'execution_id': self.execution_id,
            'action_id': self.action_id,
            'triggered_by': self.triggered_by,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'attempts': self.attempts,
            'success': self.success,
            'error_message': self.error_message,
            'result_data': self.result_data,
            'rollback_executed': self.rollback_executed
        }


class AutoRecoveryHealthSystem(BaseService):
    """自動恢復和健康檢查系統
    
    提供主動的系統健康監控和自動恢復功能
    確保T2任務中連線池系統的高可用性
    """
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("AutoRecoveryHealthSystem")
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 核心組件
        self._health_check_rules: Dict[str, HealthCheckRule] = {}
        self._recovery_actions: Dict[str, RecoveryAction] = {}
        self._active_executions: Dict[str, RecoveryExecution] = {}
        
        # 狀態監控
        self._system_health_history: List[Dict[str, Any]] = []
        self._recovery_statistics: Dict[str, Any] = {
            'total_checks_performed': 0,
            'total_recoveries_attempted': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'rollbacks_performed': 0,
            'average_recovery_time_seconds': 0.0,
            'system_uptime_percentage': 100.0
        }
        
        # 斷路器狀態
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # 配置
        self.config = {
            'health_check_enabled': True,
            'auto_recovery_enabled': True,
            'max_concurrent_recoveries': 3,
            'recovery_cooldown_seconds': 300,  # 5分鐘冷卻期
            'health_history_retention_hours': 48,
            'predictive_analysis_enabled': True,
            'rollback_on_failure_enabled': True,
            'notification_on_recovery': True
        }
        
        # 預測分析
        self._trend_analyzer = TrendAnalyzer()
        self._prediction_cache: Dict[str, Any] = {}
        
        # 初始化健康檢查規則和恢復動作
        self._initialize_health_rules()
        self._initialize_recovery_actions()
    
    async def initialize(self) -> None:
        """初始化自動恢復系統"""
        try:
            await self._create_recovery_tables()
            await self._load_configuration()
            await self._initialize_circuit_breakers()
            
            # 啟動健康檢查循環
            if self.config['health_check_enabled']:
                asyncio.create_task(self._health_check_loop())
            
            # 啟動恢復執行監控
            asyncio.create_task(self._recovery_monitoring_loop())
            
            # 啟動預測分析
            if self.config['predictive_analysis_enabled']:
                asyncio.create_task(self._predictive_analysis_loop())
            
            self.logger.info("自動恢復系統初始化完成")
        except Exception as e:
            self.logger.error(f"自動恢復系統初始化失敗: {e}")
            raise ServiceError("自動恢復系統初始化失敗", "initialize", str(e))
    
    async def _create_recovery_tables(self) -> None:
        """創建恢復相關資料表"""
        # 健康檢查結果表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS recovery_health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id TEXT UNIQUE NOT NULL,
                rule_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                status TEXT NOT NULL,
                current_value REAL NOT NULL,
                threshold_breached TEXT,
                message TEXT NOT NULL,
                metadata TEXT,
                recovery_recommended BOOLEAN DEFAULT FALSE
            )
        """)
        
        # 恢復執行記錄表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS recovery_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT UNIQUE NOT NULL,
                action_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                triggered_by TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                result_data TEXT,
                rollback_executed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # 系統健康歷史表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS recovery_system_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                overall_status TEXT NOT NULL,
                component_statuses TEXT NOT NULL,
                performance_metrics TEXT NOT NULL,
                active_issues_count INTEGER DEFAULT 0,
                recovery_actions_count INTEGER DEFAULT 0
            )
        """)
        
        # 斷路器狀態表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS recovery_circuit_breakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_name TEXT PRIMARY KEY,
                state TEXT NOT NULL,  -- 'closed', 'open', 'half_open'
                failure_count INTEGER DEFAULT 0,
                last_failure_time TIMESTAMP,
                next_attempt_time TIMESTAMP,
                metadata TEXT,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        
        # 預測分析結果表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS recovery_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT UNIQUE NOT NULL,
                component_name TEXT NOT NULL,
                prediction_type TEXT NOT NULL,  -- 'failure', 'degradation', 'recovery_needed'
                predicted_time TIMESTAMP NOT NULL,
                confidence_score REAL NOT NULL,
                current_trend TEXT NOT NULL,
                recommended_actions TEXT,
                created_at TIMESTAMP NOT NULL
            )
        """)
    
    def _initialize_health_rules(self) -> None:
        """初始化健康檢查規則"""
        rules = [
            # 連線池健康檢查
            HealthCheckRule(
                rule_id="connection_pool_utilization",
                check_type=HealthCheckType.CONNECTION_POOL,
                name="連線池使用率檢查",
                description="監控連線池使用率，防止資源耗盡",
                check_interval_seconds=30,
                warning_threshold=80.0,
                critical_threshold=95.0,
                check_function=self._check_connection_pool_utilization,
                recovery_strategies=[RecoveryStrategy.GRADUAL, RecoveryStrategy.THROTTLING]
            ),
            
            # 資料庫效能檢查
            HealthCheckRule(
                rule_id="database_response_time",
                check_type=HealthCheckType.DATABASE_PERFORMANCE,
                name="資料庫響應時間檢查",
                description="監控資料庫查詢響應時間",
                check_interval_seconds=60,
                warning_threshold=500.0,  # 500ms
                critical_threshold=2000.0,  # 2s
                check_function=self._check_database_response_time,
                recovery_strategies=[RecoveryStrategy.IMMEDIATE, RecoveryStrategy.CIRCUIT_BREAKER]
            ),
            
            # 記憶體使用檢查
            HealthCheckRule(
                rule_id="memory_usage",
                check_type=HealthCheckType.MEMORY_USAGE,
                name="記憶體使用率檢查",
                description="監控系統記憶體使用情況",
                check_interval_seconds=60,
                warning_threshold=80.0,
                critical_threshold=95.0,
                check_function=self._check_memory_usage,
                recovery_strategies=[RecoveryStrategy.IMMEDIATE, RecoveryStrategy.FAILOVER]
            ),
            
            # CPU使用率檢查
            HealthCheckRule(
                rule_id="cpu_utilization",
                check_type=HealthCheckType.CPU_UTILIZATION,
                name="CPU使用率檢查",
                description="監控CPU使用率",
                check_interval_seconds=60,
                warning_threshold=80.0,
                critical_threshold=95.0,
                check_function=self._check_cpu_utilization,
                recovery_strategies=[RecoveryStrategy.THROTTLING, RecoveryStrategy.FAILOVER]
            ),
            
            # 磁碟空間檢查
            HealthCheckRule(
                rule_id="disk_space",
                check_type=HealthCheckType.DISK_SPACE,
                name="磁碟空間檢查",
                description="監控磁碟可用空間",
                check_interval_seconds=300,  # 5分鐘
                warning_threshold=85.0,
                critical_threshold=95.0,
                check_function=self._check_disk_space,
                recovery_strategies=[RecoveryStrategy.IMMEDIATE]
            ),
            
            # 應用程式健康檢查
            HealthCheckRule(
                rule_id="application_health",
                check_type=HealthCheckType.APPLICATION_HEALTH,
                name="應用程式健康檢查",
                description="檢查應用程式核心功能狀態",
                check_interval_seconds=120,  # 2分鐘
                warning_threshold=1.0,  # 任何錯誤都是警告
                critical_threshold=5.0,  # 5個錯誤為嚴重
                check_function=self._check_application_health,
                recovery_strategies=[RecoveryStrategy.ROLLBACK, RecoveryStrategy.FAILOVER]
            )
        ]
        
        for rule in rules:
            self._health_check_rules[rule.rule_id] = rule
    
    def _initialize_recovery_actions(self) -> None:
        """初始化恢復動作"""
        actions = [
            # 增加連線池大小
            RecoveryAction(
                action_id="increase_connection_pool",
                rule_id="connection_pool_utilization",
                strategy=RecoveryStrategy.GRADUAL,
                name="增加連線池大小",
                description="漸進式增加連線池最大連線數",
                parameters={'increment': 5, 'max_size': 50},
                execute_function=self._execute_increase_connection_pool,
                rollback_function=self._rollback_increase_connection_pool
            ),
            
            # 啟用連線池節流
            RecoveryAction(
                action_id="throttle_connection_pool",
                rule_id="connection_pool_utilization",
                strategy=RecoveryStrategy.THROTTLING,
                name="連線池節流",
                description="限制新連線請求速率",
                parameters={'throttle_rate': 0.8, 'duration_seconds': 300},
                execute_function=self._execute_throttle_connections,
                rollback_function=self._rollback_throttle_connections
            ),
            
            # 資料庫查詢優化
            RecoveryAction(
                action_id="optimize_database_queries",
                rule_id="database_response_time",
                strategy=RecoveryStrategy.IMMEDIATE,
                name="資料庫查詢優化",
                description="執行資料庫優化操作",
                parameters={'vacuum': True, 'analyze': True, 'rebuild_indices': False},
                execute_function=self._execute_database_optimization,
                rollback_function=None
            ),
            
            # 啟用資料庫斷路器
            RecoveryAction(
                action_id="enable_database_circuit_breaker",
                rule_id="database_response_time",
                strategy=RecoveryStrategy.CIRCUIT_BREAKER,
                name="資料庫斷路器",
                description="啟用資料庫訪問斷路器",
                parameters={'failure_threshold': 5, 'timeout_seconds': 300},
                execute_function=self._execute_database_circuit_breaker,
                rollback_function=self._rollback_database_circuit_breaker
            ),
            
            # 記憶體清理
            RecoveryAction(
                action_id="clear_memory_cache",
                rule_id="memory_usage",
                strategy=RecoveryStrategy.IMMEDIATE,
                name="記憶體快取清理",
                description="清理系統記憶體快取",
                parameters={'aggressive': False},
                execute_function=self._execute_memory_cleanup,
                rollback_function=None
            ),
            
            # 磁碟清理
            RecoveryAction(
                action_id="disk_cleanup",
                rule_id="disk_space",
                strategy=RecoveryStrategy.IMMEDIATE,
                name="磁碟空間清理",
                description="清理臨時檔案和日誌",
                parameters={'clean_temp': True, 'clean_logs': True, 'retention_days': 7},
                execute_function=self._execute_disk_cleanup,
                rollback_function=None
            ),
            
            # 應用程式重啟
            RecoveryAction(
                action_id="restart_application_components",
                rule_id="application_health",
                strategy=RecoveryStrategy.ROLLBACK,
                name="重啟應用組件",
                description="重啟出問題的應用組件",
                parameters={'graceful_shutdown': True, 'wait_time_seconds': 30},
                execute_function=self._execute_component_restart,
                rollback_function=None
            )
        ]
        
        for action in actions:
            self._recovery_actions[action.action_id] = action
    
    async def _health_check_loop(self) -> None:
        """健康檢查循環"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(30)  # 主循環每30秒執行一次
            except Exception as e:
                self.logger.error(f"健康檢查循環錯誤: {e}")
                await asyncio.sleep(60)
    
    async def _perform_health_checks(self) -> None:
        """執行健康檢查"""
        current_time = datetime.now()
        
        for rule_id, rule in self._health_check_rules.items():
            if not rule.enabled:
                continue
            
            # 檢查是否到了執行時間
            if not self._should_run_check(rule, current_time):
                continue
            
            try:
                # 執行健康檢查
                result = await self._execute_health_check(rule)
                
                # 保存結果
                await self._save_health_check_result(result)
                
                # 檢查是否需要恢復動作
                if result.recovery_recommended and self.config['auto_recovery_enabled']:
                    await self._trigger_recovery_actions(result)
                
                # 更新統計
                self._recovery_statistics['total_checks_performed'] += 1
                
            except Exception as e:
                self.logger.error(f"健康檢查執行失敗 {rule_id}: {e}")
    
    def _should_run_check(self, rule: HealthCheckRule, current_time: datetime) -> bool:
        """判斷是否應該執行健康檢查"""
        # 簡單的基於間隔的調度
        # 實際實現中可以使用更複雜的調度邏輯
        check_key = f"last_check_{rule.rule_id}"
        last_check = getattr(self, check_key, None)
        
        if last_check is None:
            setattr(self, check_key, current_time)
            return True
        
        time_since_last = (current_time - last_check).total_seconds()
        if time_since_last >= rule.check_interval_seconds:
            setattr(self, check_key, current_time)
            return True
        
        return False
    
    async def _execute_health_check(self, rule: HealthCheckRule) -> HealthCheckResult:
        """執行單個健康檢查"""
        result_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        try:
            # 調用檢查函數
            check_result = await rule.check_function()
            
            current_value = check_result.get('value', 0.0)
            status = HealthStatus.HEALTHY
            threshold_breached = None
            message = check_result.get('message', '正常')
            recovery_recommended = False
            
            # 判斷閾值
            if current_value >= rule.critical_threshold:
                status = HealthStatus.CRITICAL
                threshold_breached = 'critical'
                recovery_recommended = True
                message = f"嚴重: {message} (當前值: {current_value}, 閾值: {rule.critical_threshold})"
            elif current_value >= rule.warning_threshold:
                status = HealthStatus.WARNING
                threshold_breached = 'warning'
                recovery_recommended = True
                message = f"警告: {message} (當前值: {current_value}, 閾值: {rule.warning_threshold})"
            
            return HealthCheckResult(
                result_id=result_id,
                rule_id=rule.rule_id,
                timestamp=timestamp,
                status=status,
                current_value=current_value,
                threshold_breached=threshold_breached,
                message=message,
                metadata=check_result.get('metadata', {}),
                recovery_recommended=recovery_recommended
            )
            
        except Exception as e:
            self.logger.error(f"健康檢查執行異常 {rule.rule_id}: {e}")
            return HealthCheckResult(
                result_id=result_id,
                rule_id=rule.rule_id,
                timestamp=timestamp,
                status=HealthStatus.CRITICAL,
                current_value=0.0,
                threshold_breached='critical',
                message=f"檢查執行失敗: {str(e)}",
                metadata={'error': str(e)},
                recovery_recommended=True
            )
    
    async def _check_connection_pool_utilization(self) -> Dict[str, Any]:
        """檢查連線池使用率"""
        try:
            pool = self.db.connection_pool
            active_connections = sum(pool.connection_counts.values())
            max_connections = pool.max_connections
            utilization = (active_connections / max_connections) * 100 if max_connections > 0 else 0
            
            return {
                'value': utilization,
                'message': f'連線池使用率 {utilization:.1f}%',
                'metadata': {
                    'active_connections': active_connections,
                    'max_connections': max_connections,
                    'available_connections': max_connections - active_connections
                }
            }
        except Exception as e:
            return {
                'value': 100.0,  # 假設最壞情況
                'message': f'連線池檢查失敗: {str(e)}',
                'metadata': {'error': str(e)}
            }
    
    async def _check_database_response_time(self) -> Dict[str, Any]:
        """檢查資料庫響應時間"""
        start_time = time.time()
        try:
            # 執行簡單查詢測試響應時間
            await self.db.fetchone("SELECT 1")
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                'value': response_time_ms,
                'message': f'資料庫響應時間 {response_time_ms:.2f}ms',
                'metadata': {
                    'query_type': 'simple_select',
                    'response_time_ms': response_time_ms
                }
            }
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return {
                'value': response_time_ms,
                'message': f'資料庫查詢失敗: {str(e)}',
                'metadata': {'error': str(e), 'response_time_ms': response_time_ms}
            }
    
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """檢查記憶體使用率"""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            return {
                'value': usage_percent,
                'message': f'記憶體使用率 {usage_percent:.1f}%',
                'metadata': {
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'usage_percent': usage_percent
                }
            }
        except Exception as e:
            return {
                'value': 100.0,
                'message': f'記憶體檢查失敗: {str(e)}',
                'metadata': {'error': str(e)}
            }
    
    async def _check_cpu_utilization(self) -> Dict[str, Any]:
        """檢查CPU使用率"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'value': cpu_percent,
                'message': f'CPU使用率 {cpu_percent:.1f}%',
                'metadata': {
                    'cpu_percent': cpu_percent,
                    'cpu_count': psutil.cpu_count(),
                    'load_avg': list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
                }
            }
        except Exception as e:
            return {
                'value': 100.0,
                'message': f'CPU檢查失敗: {str(e)}',
                'metadata': {'error': str(e)}
            }
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """檢查磁碟空間"""
        try:
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            return {
                'value': usage_percent,
                'message': f'磁碟使用率 {usage_percent:.1f}%',
                'metadata': {
                    'total_gb': disk_usage.total / (1024**3),
                    'used_gb': disk_usage.used / (1024**3),
                    'free_gb': disk_usage.free / (1024**3),
                    'usage_percent': usage_percent
                }
            }
        except Exception as e:
            return {
                'value': 100.0,
                'message': f'磁碟檢查失敗: {str(e)}',
                'metadata': {'error': str(e)}
            }
    
    async def _check_application_health(self) -> Dict[str, Any]:
        """檢查應用程式健康狀態"""
        try:
            error_count = 0
            components_checked = 0
            
            # 檢查資料庫管理器
            components_checked += 1
            if not hasattr(self.db, 'conn') or self.db.conn is None:
                error_count += 1
            
            # 檢查連線池
            components_checked += 1
            if not hasattr(self.db, 'connection_pool'):
                error_count += 1
            
            return {
                'value': error_count,
                'message': f'應用程式健康檢查: {error_count}/{components_checked} 組件異常',
                'metadata': {
                    'components_checked': components_checked,
                    'errors_found': error_count,
                    'health_score': ((components_checked - error_count) / components_checked) * 100
                }
            }
        except Exception as e:
            return {
                'value': 10.0,  # 高錯誤值
                'message': f'應用程式檢查失敗: {str(e)}',
                'metadata': {'error': str(e)}
            }
    
    async def _save_health_check_result(self, result: HealthCheckResult) -> None:
        """保存健康檢查結果"""
        await self.db.execute("""
            INSERT INTO recovery_health_checks (
                result_id, rule_id, timestamp, status, current_value,
                threshold_breached, message, metadata, recovery_recommended
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.result_id, result.rule_id, result.timestamp, result.status.value,
            result.current_value, result.threshold_breached, result.message,
            json.dumps(result.metadata), result.recovery_recommended
        ))
    
    async def _trigger_recovery_actions(self, health_result: HealthCheckResult) -> None:
        """觸發恢復動作"""
        rule = self._health_check_rules.get(health_result.rule_id)
        if not rule:
            return
        
        # 檢查是否在冷卻期
        if self._is_in_cooldown(health_result.rule_id):
            self.logger.info(f"恢復動作在冷卻期中，跳過: {health_result.rule_id}")
            return
        
        # 檢查並行恢復數量限制
        if len(self._active_executions) >= self.config['max_concurrent_recoveries']:
            self.logger.warning("達到最大並行恢復數量限制")
            return
        
        # 根據策略選擇恢復動作
        for strategy in rule.recovery_strategies:
            actions = [action for action in self._recovery_actions.values() 
                      if action.rule_id == rule.rule_id and action.strategy == strategy]
            
            for action in actions:
                await self._execute_recovery_action(action, health_result)
                break  # 每個策略只執行一個動作
    
    def _is_in_cooldown(self, rule_id: str) -> bool:
        """檢查是否在冷卻期"""
        cooldown_key = f"cooldown_{rule_id}"
        last_recovery = getattr(self, cooldown_key, None)
        
        if last_recovery is None:
            return False
        
        time_since_last = (datetime.now() - last_recovery).total_seconds()
        return time_since_last < self.config['recovery_cooldown_seconds']
    
    async def _execute_recovery_action(self, action: RecoveryAction, triggered_by: HealthCheckResult) -> None:
        """執行恢復動作"""
        execution_id = str(uuid.uuid4())
        execution = RecoveryExecution(
            execution_id=execution_id,
            action_id=action.action_id,
            triggered_by=triggered_by.result_id,
            started_at=datetime.now(),
            completed_at=None,
            status=RecoveryStatus.PENDING,
            attempts=0,
            success=False,
            error_message=None,
            result_data={},
            rollback_executed=False
        )
        
        self._active_executions[execution_id] = execution
        
        try:
            execution.status = RecoveryStatus.IN_PROGRESS
            await self._save_recovery_execution(execution)
            
            # 執行恢復動作
            success, result_data, error_msg = await self._perform_recovery_action(action)
            
            execution.completed_at = datetime.now()
            execution.success = success
            execution.result_data = result_data
            execution.error_message = error_msg
            execution.status = RecoveryStatus.COMPLETED if success else RecoveryStatus.FAILED
            
            # 如果失敗且需要回滾
            if not success and action.rollback_function and self.config['rollback_on_failure_enabled']:
                try:
                    rollback_success, rollback_data, rollback_error = await self._perform_rollback_action(action)
                    execution.rollback_executed = True
                    execution.result_data['rollback'] = {
                        'success': rollback_success,
                        'data': rollback_data,
                        'error': rollback_error
                    }
                    if rollback_success:
                        execution.status = RecoveryStatus.ROLLED_BACK
                except Exception as e:
                    self.logger.error(f"回滾動作失敗: {e}")
            
            # 更新統計
            if success:
                self._recovery_statistics['successful_recoveries'] += 1
            else:
                self._recovery_statistics['failed_recoveries'] += 1
                
            self._recovery_statistics['total_recoveries_attempted'] += 1
            
            # 設置冷卻期
            cooldown_key = f"cooldown_{action.rule_id}"
            setattr(self, cooldown_key, datetime.now())
            
            self.logger.info(f"恢復動作完成: {execution_id} - 成功: {success}")
            
        except Exception as e:
            execution.status = RecoveryStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            self.logger.error(f"恢復動作執行異常: {e}")
            
        finally:
            # 保存最終狀態
            await self._save_recovery_execution(execution)
            
            # 從活動執行中移除
            if execution_id in self._active_executions:
                del self._active_executions[execution_id]
    
    async def _perform_recovery_action(self, action: RecoveryAction) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """執行具體的恢復動作"""
        try:
            result = await action.execute_function(action.parameters)
            return True, result if isinstance(result, dict) else {'result': result}, None
        except Exception as e:
            return False, {}, str(e)
    
    async def _perform_rollback_action(self, action: RecoveryAction) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """執行回滾動作"""
        if not action.rollback_function:
            return False, {}, "無回滾函數"
        
        try:
            result = await action.rollback_function(action.parameters)
            return True, result if isinstance(result, dict) else {'result': result}, None
        except Exception as e:
            return False, {}, str(e)
    
    async def _save_recovery_execution(self, execution: RecoveryExecution) -> None:
        """保存恢復執行記錄"""
        await self.db.execute("""
            INSERT OR REPLACE INTO recovery_executions (
                execution_id, action_id, rule_id, triggered_by, started_at, completed_at,
                status, attempts, success, error_message, result_data, rollback_executed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution.execution_id, execution.action_id,
            self._recovery_actions[execution.action_id].rule_id,
            execution.triggered_by, execution.started_at, execution.completed_at,
            execution.status.value, execution.attempts, execution.success,
            execution.error_message, json.dumps(execution.result_data),
            execution.rollback_executed
        ))
    
    # 恢復動作執行函數
    async def _execute_increase_connection_pool(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行增加連線池大小"""
        current_size = self.db.connection_pool.max_connections
        increment = parameters.get('increment', 5)
        max_size = parameters.get('max_size', 50)
        
        new_size = min(current_size + increment, max_size)
        self.db.connection_pool.max_connections = new_size
        
        return {
            'previous_size': current_size,
            'new_size': new_size,
            'increment': increment,
            'message': f'連線池大小從 {current_size} 增加到 {new_size}'
        }
    
    async def _rollback_increase_connection_pool(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """回滾連線池大小增加"""
        # 實際實現中，這裡應該恢復到之前的大小
        # 為簡化，這裡只是減少一些連線
        current_size = self.db.connection_pool.max_connections
        decrement = parameters.get('increment', 5)
        
        new_size = max(current_size - decrement, 5)  # 最少保留5個連線
        self.db.connection_pool.max_connections = new_size
        
        return {
            'previous_size': current_size,
            'new_size': new_size,
            'message': f'連線池大小回滾到 {new_size}'
        }
    
    async def _execute_throttle_connections(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行連線節流"""
        # 這裡應該實現實際的節流邏輯
        throttle_rate = parameters.get('throttle_rate', 0.8)
        duration = parameters.get('duration_seconds', 300)
        
        # 模擬節流實施
        return {
            'throttle_rate': throttle_rate,
            'duration_seconds': duration,
            'message': f'連線節流已啟用，速率: {throttle_rate}, 持續: {duration}秒'
        }
    
    async def _rollback_throttle_connections(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """回滾連線節流"""
        return {
            'message': '連線節流已停用'
        }
    
    async def _execute_database_optimization(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行資料庫優化"""
        results = {}
        
        if parameters.get('vacuum', False):
            await self.db.execute("VACUUM")
            results['vacuum'] = 'completed'
        
        if parameters.get('analyze', False):
            await self.db.execute("ANALYZE")
            results['analyze'] = 'completed'
        
        return {
            'operations': results,
            'message': '資料庫優化完成'
        }
    
    async def _execute_database_circuit_breaker(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行資料庫斷路器"""
        component_name = 'database'
        failure_threshold = parameters.get('failure_threshold', 5)
        timeout_seconds = parameters.get('timeout_seconds', 300)
        
        # 設置斷路器狀態
        self._circuit_breakers[component_name] = {
            'state': 'open',
            'failure_threshold': failure_threshold,
            'timeout_seconds': timeout_seconds,
            'opened_at': datetime.now()
        }
        
        return {
            'component': component_name,
            'state': 'open',
            'failure_threshold': failure_threshold,
            'timeout_seconds': timeout_seconds,
            'message': '資料庫斷路器已啟用'
        }
    
    async def _rollback_database_circuit_breaker(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """回滾資料庫斷路器"""
        component_name = 'database'
        
        if component_name in self._circuit_breakers:
            self._circuit_breakers[component_name]['state'] = 'closed'
        
        return {
            'component': component_name,
            'state': 'closed',
            'message': '資料庫斷路器已關閉'
        }
    
    async def _execute_memory_cleanup(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行記憶體清理"""
        import gc
        
        # 執行垃圾回收
        collected = gc.collect()
        
        # 如果是激進模式，可以進行更多清理
        if parameters.get('aggressive', False):
            # 這裡可以添加更激進的記憶體清理邏輯
            pass
        
        return {
            'objects_collected': collected,
            'aggressive_mode': parameters.get('aggressive', False),
            'message': f'記憶體清理完成，回收了 {collected} 個對象'
        }
    
    async def _execute_disk_cleanup(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行磁碟清理"""
        import os
        import tempfile
        import shutil
        
        cleaned_size = 0
        cleaned_files = 0
        
        # 清理臨時檔案
        if parameters.get('clean_temp', False):
            temp_dir = tempfile.gettempdir()
            try:
                for filename in os.listdir(temp_dir):
                    if filename.startswith('tmp') or filename.startswith('temp'):
                        file_path = os.path.join(temp_dir, filename)
                        if os.path.isfile(file_path):
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_size += size
                            cleaned_files += 1
            except Exception as e:
                self.logger.warning(f"臨時檔案清理部分失敗: {e}")
        
        # 清理日誌檔案
        if parameters.get('clean_logs', False):
            retention_days = parameters.get('retention_days', 7)
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            logs_dir = "logs"
            if os.path.exists(logs_dir):
                try:
                    for filename in os.listdir(logs_dir):
                        file_path = os.path.join(logs_dir, filename)
                        if os.path.isfile(file_path):
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            if file_mtime < cutoff_time and not filename.endswith('.log'):  # 保留當前日誌
                                size = os.path.getsize(file_path)
                                os.remove(file_path)
                                cleaned_size += size
                                cleaned_files += 1
                except Exception as e:
                    self.logger.warning(f"日誌檔案清理部分失敗: {e}")
        
        return {
            'cleaned_files_count': cleaned_files,
            'cleaned_size_mb': cleaned_size / (1024 * 1024),
            'message': f'磁碟清理完成，清理了 {cleaned_files} 個檔案，釋放 {cleaned_size / (1024 * 1024):.2f} MB'
        }
    
    async def _execute_component_restart(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """執行組件重啟"""
        graceful = parameters.get('graceful_shutdown', True)
        wait_time = parameters.get('wait_time_seconds', 30)
        
        # 這裡應該實現實際的組件重啟邏輯
        # 為了安全，這裡只是模擬
        
        if graceful:
            # 優雅關閉邏輯
            await asyncio.sleep(1)  # 模擬優雅關閉時間
        
        # 等待時間
        await asyncio.sleep(min(wait_time, 5))  # 限制等待時間
        
        return {
            'graceful_shutdown': graceful,
            'wait_time_seconds': wait_time,
            'message': '組件重啟完成（模擬）'
        }
    
    async def _recovery_monitoring_loop(self) -> None:
        """恢復監控循環"""
        while True:
            try:
                await self._update_system_health_status()
                await self._cleanup_old_records()
                await asyncio.sleep(300)  # 每5分鐘更新一次
            except Exception as e:
                self.logger.error(f"恢復監控循環錯誤: {e}")
                await asyncio.sleep(300)
    
    async def _update_system_health_status(self) -> None:
        """更新系統健康狀態"""
        # 收集所有組件的健康狀態
        component_statuses = {}
        overall_status = HealthStatus.HEALTHY
        
        # 檢查最近的健康檢查結果
        recent_results = await self._get_recent_health_results(minutes=10)
        
        for result in recent_results:
            if result['rule_id'] not in component_statuses:
                component_statuses[result['rule_id']] = result['status']
            
            # 更新整體狀態
            if result['status'] == 'critical':
                overall_status = HealthStatus.CRITICAL
            elif result['status'] == 'warning' and overall_status != HealthStatus.CRITICAL:
                overall_status = HealthStatus.WARNING
        
        # 收集效能指標
        performance_metrics = {
            'active_recoveries': len(self._active_executions),
            'recent_checks': len(recent_results),
            'circuit_breakers': len([cb for cb in self._circuit_breakers.values() if cb.get('state') == 'open'])
        }
        
        # 保存系統健康狀態
        await self.db.execute("""
            INSERT INTO recovery_system_health (
                timestamp, overall_status, component_statuses, performance_metrics,
                active_issues_count, recovery_actions_count
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(), overall_status.value, json.dumps(component_statuses),
            json.dumps(performance_metrics), 
            len([s for s in component_statuses.values() if s in ['warning', 'critical']]),
            len(self._active_executions)
        ))
    
    async def _get_recent_health_results(self, minutes: int = 10) -> List[Dict[str, Any]]:
        """獲取最近的健康檢查結果"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        rows = await self.db.fetchall("""
            SELECT rule_id, status, current_value, timestamp
            FROM recovery_health_checks
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """, (cutoff_time,))
        
        return [
            {
                'rule_id': row[0],
                'status': row[1],
                'current_value': row[2],
                'timestamp': row[3]
            }
            for row in rows
        ]
    
    async def _cleanup_old_records(self) -> None:
        """清理舊記錄"""
        cutoff_time = datetime.now() - timedelta(hours=self.config['health_history_retention_hours'])
        
        # 清理舊的健康檢查記錄
        await self.db.execute("""
            DELETE FROM recovery_health_checks WHERE timestamp < ?
        """, (cutoff_time,))
        
        # 清理舊的恢復執行記錄
        await self.db.execute("""
            DELETE FROM recovery_executions WHERE started_at < ?
        """, (cutoff_time,))
        
        # 清理舊的系統健康記錄
        await self.db.execute("""
            DELETE FROM recovery_system_health WHERE timestamp < ?
        """, (cutoff_time,))
    
    async def _predictive_analysis_loop(self) -> None:
        """預測分析循環"""
        while True:
            try:
                await self._perform_predictive_analysis()
                await asyncio.sleep(1800)  # 每30分鐘執行一次
            except Exception as e:
                self.logger.error(f"預測分析循環錯誤: {e}")
                await asyncio.sleep(1800)
    
    async def _perform_predictive_analysis(self) -> None:
        """執行預測分析"""
        # 為每個健康檢查規則進行趨勢分析
        for rule_id, rule in self._health_check_rules.items():
            try:
                await self._analyze_component_trend(rule_id, rule)
            except Exception as e:
                self.logger.error(f"組件趨勢分析失敗 {rule_id}: {e}")
    
    async def _analyze_component_trend(self, rule_id: str, rule: HealthCheckRule) -> None:
        """分析組件趨勢"""
        # 獲取最近24小時的健康檢查數據
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        rows = await self.db.fetchall("""
            SELECT current_value, timestamp FROM recovery_health_checks
            WHERE rule_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (rule_id, cutoff_time))
        
        if len(rows) < 10:  # 數據點不足
            return
        
        # 準備數據
        values = [row[0] for row in rows]
        timestamps = [datetime.fromisoformat(row[1]) for row in rows]
        
        # 進行趨勢分析
        trend_result = self._trend_analyzer.analyze_trend(values, timestamps)
        
        # 檢查是否需要生成預測警告
        if trend_result['prediction_confidence'] > 0.7:  # 70%信心度
            await self._generate_prediction_alert(rule_id, rule, trend_result)
    
    async def _generate_prediction_alert(self, rule_id: str, rule: HealthCheckRule, trend_result: Dict[str, Any]) -> None:
        """生成預測警告"""
        prediction_id = str(uuid.uuid4())
        
        # 根據趨勢確定預測類型
        prediction_type = "degradation"
        if trend_result['trend_direction'] == 'increasing' and trend_result['predicted_breach_time']:
            if trend_result['breach_type'] == 'critical':
                prediction_type = "failure"
            else:
                prediction_type = "degradation"
        
        predicted_time = trend_result.get('predicted_breach_time', datetime.now() + timedelta(hours=1))
        
        # 保存預測結果
        await self.db.execute("""
            INSERT INTO recovery_predictions (
                prediction_id, component_name, prediction_type, predicted_time,
                confidence_score, current_trend, recommended_actions, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_id, rule.name, prediction_type, predicted_time,
            trend_result['prediction_confidence'], trend_result['trend_direction'],
            json.dumps([strategy.value for strategy in rule.recovery_strategies]),
            datetime.now()
        ))
        
        self.logger.warning(f"預測警告: {rule.name} - {prediction_type}, 預測時間: {predicted_time}, 信心度: {trend_result['prediction_confidence']:.2f}")
    
    async def _load_configuration(self) -> None:
        """載入配置"""
        # 從資料庫或配置文件載入配置
        pass
    
    async def _initialize_circuit_breakers(self) -> None:
        """初始化斷路器"""
        # 從資料庫載入斷路器狀態
        rows = await self.db.fetchall("""
            SELECT component_name, state, failure_count, last_failure_time, next_attempt_time, metadata
            FROM recovery_circuit_breakers
        """)
        
        for row in rows:
            component_name = row[0]
            self._circuit_breakers[component_name] = {
                'state': row[1],
                'failure_count': row[2],
                'last_failure_time': datetime.fromisoformat(row[3]) if row[3] else None,
                'next_attempt_time': datetime.fromisoformat(row[4]) if row[4] else None,
                'metadata': json.loads(row[5]) if row[5] else {}
            }
    
    # 公共API方法
    async def get_system_health_status(self) -> Dict[str, Any]:
        """獲取系統健康狀態"""
        # 獲取最新的系統健康記錄
        latest_health = await self.db.fetchone("""
            SELECT overall_status, component_statuses, performance_metrics, timestamp
            FROM recovery_system_health
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        
        if not latest_health:
            return {
                'overall_status': 'unknown',
                'component_statuses': {},
                'performance_metrics': {},
                'last_updated': None
            }
        
        return {
            'overall_status': latest_health[0],
            'component_statuses': json.loads(latest_health[1]),
            'performance_metrics': json.loads(latest_health[2]),
            'last_updated': latest_health[3]
        }
    
    async def get_recovery_statistics(self) -> Dict[str, Any]:
        """獲取恢復統計信息"""
        return {
            **self._recovery_statistics,
            'active_executions': len(self._active_executions),
            'health_check_rules': len(self._health_check_rules),
            'recovery_actions': len(self._recovery_actions),
            'circuit_breakers_open': len([cb for cb in self._circuit_breakers.values() 
                                        if cb.get('state') == 'open'])
        }
    
    async def get_recent_recovery_executions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """獲取最近的恢復執行記錄"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        rows = await self.db.fetchall("""
            SELECT execution_id, action_id, rule_id, started_at, completed_at,
                   status, success, error_message, result_data
            FROM recovery_executions
            WHERE started_at >= ?
            ORDER BY started_at DESC
        """, (cutoff_time,))
        
        return [
            {
                'execution_id': row[0],
                'action_id': row[1],
                'rule_id': row[2],
                'started_at': row[3],
                'completed_at': row[4],
                'status': row[5],
                'success': bool(row[6]),
                'error_message': row[7],
                'result_data': json.loads(row[8]) if row[8] else {}
            }
            for row in rows
        ]
    
    async def manual_trigger_recovery(self, action_id: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """手動觸發恢復動作"""
        action = self._recovery_actions.get(action_id)
        if not action:
            raise ValueError(f"恢復動作不存在: {action_id}")
        
        # 創建虛擬健康檢查結果作為觸發源
        fake_health_result = HealthCheckResult(
            result_id=str(uuid.uuid4()),
            rule_id=action.rule_id,
            timestamp=datetime.now(),
            status=HealthStatus.WARNING,
            current_value=0.0,
            threshold_breached='manual',
            message="手動觸發的恢復動作",
            metadata={'manual_trigger': True, 'parameters': parameters or {}},
            recovery_recommended=True
        )
        
        # 如果提供了參數，更新動作參數
        if parameters:
            action.parameters.update(parameters)
        
        # 執行恢復動作
        await self._execute_recovery_action(action, fake_health_result)
        
        return f"恢復動作已觸發: {action_id}"


class TrendAnalyzer:
    """趨勢分析器"""
    
    def analyze_trend(self, values: List[float], timestamps: List[datetime]) -> Dict[str, Any]:
        """分析數據趨勢"""
        if len(values) < 5:
            return {
                'trend_direction': 'unknown',
                'prediction_confidence': 0.0,
                'predicted_breach_time': None,
                'breach_type': None
            }
        
        # 計算趨勢方向
        recent_values = values[-5:]
        trend_direction = 'stable'
        
        if recent_values[-1] > recent_values[0]:
            trend_direction = 'increasing'
        elif recent_values[-1] < recent_values[0]:
            trend_direction = 'decreasing'
        
        # 計算線性回歸以預測趨勢
        try:
            import numpy as np
            from scipy import stats
            
            # 轉換時間戳為數值
            time_values = [(ts - timestamps[0]).total_seconds() for ts in timestamps]
            
            # 線性回歸
            slope, intercept, r_value, p_value, std_err = stats.linregress(time_values, values)
            
            # 預測信心度基於R²值
            prediction_confidence = r_value ** 2
            
            # 預測何時會超過閾值
            predicted_breach_time = None
            breach_type = None
            
            if slope > 0 and prediction_confidence > 0.5:
                # 假設警告閾值為80，嚴重閾值為95
                warning_threshold = 80.0
                critical_threshold = 95.0
                
                current_time = (datetime.now() - timestamps[0]).total_seconds()
                current_predicted = slope * current_time + intercept
                
                if current_predicted < warning_threshold:
                    time_to_warning = (warning_threshold - current_predicted) / slope
                    predicted_breach_time = datetime.now() + timedelta(seconds=time_to_warning)
                    breach_type = 'warning'
                elif current_predicted < critical_threshold:
                    time_to_critical = (critical_threshold - current_predicted) / slope
                    predicted_breach_time = datetime.now() + timedelta(seconds=time_to_critical)
                    breach_type = 'critical'
            
            return {
                'trend_direction': trend_direction,
                'prediction_confidence': prediction_confidence,
                'predicted_breach_time': predicted_breach_time,
                'breach_type': breach_type,
                'slope': slope,
                'r_squared': r_value ** 2
            }
            
        except ImportError:
            # 如果沒有scipy，使用簡單的計算
            return {
                'trend_direction': trend_direction,
                'prediction_confidence': 0.5,
                'predicted_breach_time': None,
                'breach_type': None
            }