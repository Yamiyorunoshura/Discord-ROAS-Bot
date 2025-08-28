"""
智能部署協調器
Task ID: 2 - 自動化部署和啟動系統開發

部署協調器作為頂級編排服務，負責：
- 統一的部署決策邏輯和智能降級控制
- 協調Docker和UV Python部署管理器
- 環境適應性檢測和最佳策略選擇
- 部署失敗時的自動降級和恢復
- 跨平台部署一致性保證
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable

from src.core.errors import (
    DeploymentError, ServiceStartupError, EnvironmentError, 
    create_error
)
from src.services.environment_detector import (
    EnvironmentDetector, EnvironmentType, EnvironmentStatus,
    SystemInfo
)
from src.services.docker_deployment_manager import (
    DockerDeploymentManager, DockerDeploymentConfig, DockerProfile,
    DockerServiceStatus, DockerDeploymentResult
)
from src.services.uv_deployment_manager import (
    UVDeploymentManager, UVEnvironmentConfig, ApplicationConfig,
    ServiceMode, UVServiceStatus, UVDeploymentResult
)
from core.base_service import BaseService, ServiceType

# 監控整合（延遲導入避免循環依賴）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.services.deployment_monitor_integration import DeploymentMonitorIntegration


logger = logging.getLogger('services.deployment_coordinator')


class DeploymentStrategy(Enum):
    """部署策略枚舉"""
    DOCKER_PREFERRED = "docker_preferred"    # 優先Docker，失敗時降級
    UV_PREFERRED = "uv_preferred"            # 優先UV，失敗時降級
    DOCKER_ONLY = "docker_only"             # 僅Docker，不降級
    UV_ONLY = "uv_only"                     # 僅UV，不降級
    AUTO_DETECT = "auto_detect"             # 自動檢測最佳策略
    MANUAL = "manual"                       # 手動指定


class DeploymentMode(Enum):
    """當前部署模式"""
    DOCKER = "docker"
    UV_PYTHON = "uv_python"
    NOT_DEPLOYED = "not_deployed"
    FAILED = "failed"


class CoordinatorStatus(Enum):
    """協調器狀態"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DEPLOYING = "deploying"
    RUNNING = "running"
    DEGRADING = "degrading"  # 降級中
    FAILED = "failed"
    STOPPING = "stopping"


@dataclass
class DeploymentPlan:
    """部署計劃"""
    strategy: DeploymentStrategy
    primary_mode: DeploymentMode
    fallback_modes: List[DeploymentMode] = field(default_factory=list)
    confidence_score: float = 0.0  # 0-100
    estimated_time: int = 0  # 秒
    risk_factors: List[str] = field(default_factory=list)
    requirements: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


@dataclass
class DeploymentExecution:
    """部署執行狀態"""
    plan: DeploymentPlan
    current_mode: DeploymentMode
    attempts: Dict[DeploymentMode, int] = field(default_factory=dict)
    results: Dict[DeploymentMode, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    total_time: float = 0.0
    success: bool = False
    error_messages: List[str] = field(default_factory=list)


class DeploymentCoordinator(BaseService):
    """
    智能部署協調器
    
    作為頂級部署編排服務，智能協調各種部署方式，
    提供統一的部署接口和自動降級機制
    """
    
    def __init__(self, project_root: Optional[str] = None):
        super().__init__()
        
        self.service_metadata = {
            'service_type': ServiceType.DEPLOYMENT,
            'service_name': 'deployment_coordinator',
            'version': '2.4.4',
            'capabilities': {
                'intelligent_fallback': True,
                'multi_deployment_modes': True,
                'auto_recovery': True,
                'cross_platform': True,
                'environment_adaptation': True,
                'deployment_orchestration': True,
                'monitoring_integration': True
            }
        }
        
        # 部署管理器
        self.environment_detector = EnvironmentDetector()
        self.docker_manager = DockerDeploymentManager(project_root)
        self.uv_manager = UVDeploymentManager(project_root)
        
        # 監控整合 (延遲初始化)
        self.monitor_integration: Optional["DeploymentMonitorIntegration"] = None
        self.monitoring_enabled = True
        
        # 當前狀態
        self.coordinator_status = CoordinatorStatus.IDLE
        self.current_deployment_mode = DeploymentMode.NOT_DEPLOYED
        self.current_execution: Optional[DeploymentExecution] = None
        self.current_deployment_id: Optional[str] = None
        
        # 配置和策略
        self.deployment_strategy = DeploymentStrategy.AUTO_DETECT
        self.max_fallback_attempts = 3
        self.retry_delay = 10  # 重試間隔（秒）
        self.health_check_interval = 60  # 健康檢查間隔
        
        # 策略權重配置
        self.strategy_weights = {
            'docker_availability': 40,      # Docker可用性權重
            'uv_availability': 30,          # UV可用性權重  
            'system_resources': 15,         # 系統資源權重
            'user_preference': 10,          # 用戶偏好權重
            'historical_success': 5         # 歷史成功率權重
        }
        
        # 部署歷史和統計
        self.deployment_history: List[Dict[str, Any]] = []
        self.success_rates: Dict[DeploymentMode, float] = {
            DeploymentMode.DOCKER: 0.0,
            DeploymentMode.UV_PYTHON: 0.0
        }
        
        # 監控和自動恢復
        self.monitoring_task: Optional[asyncio.Task] = None
        self.auto_recovery_enabled = True
        self._consecutive_failures = 0
        self._last_health_check = None
    
    async def start(self) -> None:
        """啟動部署協調器"""
        try:
            logger.info("啟動部署協調器...")
            
            # 啟動環境檢測服務
            await self.environment_detector.start()
            
            # 啟動部署管理器
            await self.docker_manager.start()
            await self.uv_manager.start()
            
            # 計算初始成功率
            await self._calculate_historical_success_rates()
            
            # 啟動監控
            await self._start_monitoring()
            
            self.is_initialized = True
            logger.info("部署協調器啟動完成")
            
        except Exception as e:
            logger.error(f"部署協調器啟動失敗: {e}")
            raise ServiceStartupError(
                service_name='deployment_coordinator',
                startup_mode='coordination',
                reason=str(e)
            )
    
    async def stop(self) -> None:
        """停止部署協調器"""
        try:
            logger.info("停止部署協調器...")
            
            # 停止當前部署
            if self.current_deployment_mode != DeploymentMode.NOT_DEPLOYED:
                await self.stop_deployment()
            
            # 停止監控
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # 停止部署管理器
            await self.uv_manager.stop()
            await self.docker_manager.stop()
            await self.environment_detector.stop()
            
            self.is_initialized = False
            logger.info("部署協調器已停止")
            
        except Exception as e:
            logger.error(f"停止部署協調器失敗: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 檢查協調器狀態
            coordinator_healthy = self.is_initialized
            
            # 檢查子服務健康狀態
            env_health = await self.environment_detector.health_check()
            docker_health = await self.docker_manager.health_check()
            uv_health = await self.uv_manager.health_check()
            
            # 檢查當前部署狀態
            deployment_healthy = await self._check_current_deployment_health()
            
            # 綜合健康評估
            overall_health = "healthy"
            issues = []
            
            if not coordinator_healthy:
                overall_health = "unhealthy"
                issues.append("協調器未初始化")
            
            if env_health.get('status') != 'healthy':
                overall_health = "degraded"
                issues.append("環境檢測服務不健康")
            
            if (self.current_deployment_mode == DeploymentMode.DOCKER and 
                docker_health.get('status') != 'healthy'):
                overall_health = "degraded"
                issues.append("Docker部署不健康")
            
            if (self.current_deployment_mode == DeploymentMode.UV_PYTHON and 
                uv_health.get('status') != 'healthy'):
                overall_health = "degraded"
                issues.append("UV部署不健康")
            
            if not deployment_healthy:
                overall_health = "degraded"
                issues.append("當前部署不健康")
            
            return {
                'service_name': 'deployment_coordinator',
                'status': overall_health,
                'coordinator_status': self.coordinator_status.value,
                'current_deployment_mode': self.current_deployment_mode.value,
                'deployment_strategy': self.deployment_strategy.value,
                'subsystem_health': {
                    'environment_detector': env_health.get('status', 'unknown'),
                    'docker_manager': docker_health.get('status', 'unknown'),
                    'uv_manager': uv_health.get('status', 'unknown')
                },
                'deployment_healthy': deployment_healthy,
                'consecutive_failures': self._consecutive_failures,
                'success_rates': dict(self.success_rates),
                'issues': issues,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"部署協調器健康檢查失敗: {e}")
            return {
                'service_name': 'deployment_coordinator',
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    # ========== 核心部署協調方法 ==========
    
    async def deploy(
        self,
        strategy: Optional[DeploymentStrategy] = None,
        docker_config: Optional[DockerDeploymentConfig] = None,
        uv_env_config: Optional[UVEnvironmentConfig] = None,
        uv_app_config: Optional[ApplicationConfig] = None,
        force_mode: Optional[DeploymentMode] = None
    ) -> Dict[str, Any]:
        """
        智能部署協調
        
        Args:
            strategy: 部署策略
            docker_config: Docker部署配置
            uv_env_config: UV環境配置
            uv_app_config: UV應用配置
            force_mode: 強制指定部署模式
        """
        if strategy:
            self.deployment_strategy = strategy
        
        # 生成部署ID
        import uuid
        deployment_id = f"deploy_{uuid.uuid4().hex[:12]}"
        self.current_deployment_id = deployment_id
        
        logger.info(f"開始智能部署協調，ID: {deployment_id}，策略: {self.deployment_strategy.value}")
        
        self.coordinator_status = CoordinatorStatus.ANALYZING
        
        # 開始監控
        if self.monitor_integration and self.monitoring_enabled:
            deployment_config = {
                'strategy': self.deployment_strategy.value,
                'force_mode': force_mode.value if force_mode else None,
                'docker_config': docker_config.__dict__ if docker_config else None,
                'uv_env_config': uv_env_config.__dict__ if uv_env_config else None,
                'uv_app_config': uv_app_config.__dict__ if uv_app_config else None,
            }
            await self.monitor_integration.start_deployment_monitoring(
                deployment_id=deployment_id,
                deployment_config=deployment_config
            )
        
        try:
            # 1. 環境分析和部署計劃生成
            logger.info("分析環境並生成部署計劃...")
            await self._log_deployment_step("environment_analysis", "started", {"phase": "planning"})
            
            deployment_plan = await self._analyze_and_plan_deployment(force_mode)
            
            await self._log_deployment_step("environment_analysis", "completed", {
                "plan": {
                    "primary_mode": deployment_plan.primary_mode.value,
                    "confidence_score": deployment_plan.confidence_score,
                    "fallback_modes": [m.value for m in deployment_plan.fallback_modes]
                }
            })
            
            # 2. 執行部署計劃
            logger.info(f"執行部署計劃，主要模式: {deployment_plan.primary_mode.value}")
            self.coordinator_status = CoordinatorStatus.DEPLOYING
            
            await self._log_deployment_step("deployment_execution", "started", {
                "primary_mode": deployment_plan.primary_mode.value
            })
            
            execution = DeploymentExecution(
                plan=deployment_plan,
                current_mode=deployment_plan.primary_mode
            )
            self.current_execution = execution
            
            # 3. 嘗試部署
            result = await self._execute_deployment_plan(
                execution, 
                docker_config, 
                uv_env_config, 
                uv_app_config
            )
            
            # 4. 更新狀態和歷史
            if result['success']:
                self.coordinator_status = CoordinatorStatus.RUNNING
                self.current_deployment_mode = execution.current_mode
                logger.info(f"部署成功，模式: {self.current_deployment_mode.value}")
                
                await self._log_deployment_step("deployment_execution", "completed", {
                    "final_mode": self.current_deployment_mode.value,
                    "execution_time": result.get('execution_summary', {}).get('total_time', 0)
                })
            else:
                self.coordinator_status = CoordinatorStatus.FAILED
                self.current_deployment_mode = DeploymentMode.FAILED
                error_message = result.get('error_message', 'Unknown error')
                logger.error(f"部署失敗: {error_message}")
                
                await self._log_deployment_step("deployment_execution", "failed", {
                    "error_message": error_message,
                    "detailed_errors": result.get('detailed_errors', [])
                })
                
                await self._log_deployment_error(
                    error_type="DEPLOYMENT_FAILURE",
                    error_message=error_message,
                    error_details=result.get('detailed_errors', []),
                    is_critical=True
                )
            
            # 記錄部署歷史
            await self._record_deployment_execution(execution)
            
            # 添加部署ID到結果
            result['deployment_id'] = deployment_id
            
            return result
            
        except Exception as e:
            self.coordinator_status = CoordinatorStatus.FAILED
            self.current_deployment_mode = DeploymentMode.FAILED
            self._consecutive_failures += 1
            
            logger.error(f"部署協調失敗: {e}")
            
            await self._log_deployment_error(
                error_type="COORDINATOR_FAILURE",
                error_message=str(e),
                is_critical=True
            )
            
            return {
                'success': False,
                'deployment_id': deployment_id,
                'deployment_mode': DeploymentMode.FAILED.value,
                'error_message': str(e),
                'coordinator_status': self.coordinator_status.value,
                'timestamp': datetime.now().isoformat()
            }
        finally:
            # 停止監控
            if self.monitor_integration and self.monitoring_enabled:
                await self.monitor_integration.stop_deployment_monitoring(deployment_id)
    
    async def stop_deployment(self, force: bool = False) -> Dict[str, Any]:
        """停止當前部署"""
        logger.info(f"停止當前部署，模式: {self.current_deployment_mode.value}")
        
        self.coordinator_status = CoordinatorStatus.STOPPING
        
        try:
            success = False
            
            if self.current_deployment_mode == DeploymentMode.DOCKER:
                success = await self.docker_manager.stop_deployment(force)
            elif self.current_deployment_mode == DeploymentMode.UV_PYTHON:
                success = await self.uv_manager.stop_deployment(force)
            else:
                success = True  # 沒有運行中的部署
            
            if success:
                self.coordinator_status = CoordinatorStatus.IDLE
                self.current_deployment_mode = DeploymentMode.NOT_DEPLOYED
                self.current_execution = None
                logger.info("部署已停止")
            else:
                self.coordinator_status = CoordinatorStatus.FAILED
                logger.error("停止部署失敗")
            
            return {
                'success': success,
                'previous_deployment_mode': self.current_deployment_mode.value,
                'coordinator_status': self.coordinator_status.value,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.coordinator_status = CoordinatorStatus.FAILED
            logger.error(f"停止部署異常: {e}")
            
            return {
                'success': False,
                'error_message': str(e),
                'coordinator_status': self.coordinator_status.value,
                'timestamp': datetime.now().isoformat()
            }
    
    async def restart_deployment(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """重啟當前部署"""
        logger.info(f"重啟部署，當前模式: {self.current_deployment_mode.value}")
        
        try:
            # 停止當前部署
            stop_result = await self.stop_deployment()
            if not stop_result['success']:
                return stop_result
            
            # 等待清理完成
            await asyncio.sleep(2)
            
            # 使用相同配置重新部署
            if self.current_execution:
                return await self._execute_deployment_plan(
                    self.current_execution,
                    None, None, None,  # 使用默認配置
                    force_rebuild=force_rebuild
                )
            else:
                # 沒有執行記錄，使用默認策略重新部署
                return await self.deploy()
            
        except Exception as e:
            logger.error(f"重啟部署失敗: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    # ========== 智能分析和計劃生成 ==========
    
    async def _analyze_and_plan_deployment(
        self, 
        force_mode: Optional[DeploymentMode] = None
    ) -> DeploymentPlan:
        """分析環境並生成部署計劃"""
        try:
            # 如果強制指定模式，直接返回計劃
            if force_mode and force_mode != DeploymentMode.NOT_DEPLOYED:
                return DeploymentPlan(
                    strategy=DeploymentStrategy.MANUAL,
                    primary_mode=force_mode,
                    confidence_score=100.0,
                    rationale=f"用戶強制指定部署模式: {force_mode.value}"
                )
            
            # 獲取環境狀態
            environments = await self.environment_detector.detect_all_environments()
            system_info = await self.environment_detector.detect_system_info()
            
            # 計算每種部署模式的可行性分數
            docker_score = await self._calculate_deployment_score(
                DeploymentMode.DOCKER, environments, system_info
            )
            uv_score = await self._calculate_deployment_score(
                DeploymentMode.UV_PYTHON, environments, system_info
            )
            
            logger.debug(f"部署分數 - Docker: {docker_score:.1f}, UV: {uv_score:.1f}")
            
            # 根據策略選擇主要模式
            plan = await self._generate_deployment_plan(
                docker_score, uv_score, environments, system_info
            )
            
            logger.info(f"生成部署計劃: {plan.rationale}")
            return plan
            
        except Exception as e:
            logger.error(f"分析和計劃生成失敗: {e}")
            # 返回保守的降級計劃
            return DeploymentPlan(
                strategy=DeploymentStrategy.UV_PREFERRED,
                primary_mode=DeploymentMode.UV_PYTHON,
                fallback_modes=[],
                confidence_score=30.0,
                rationale=f"分析失敗，使用保守方案: {str(e)}"
            )
    
    async def _calculate_deployment_score(
        self,
        mode: DeploymentMode,
        environments: Dict[EnvironmentType, Any],
        system_info: SystemInfo
    ) -> float:
        """計算部署模式的可行性分數（0-100）"""
        score = 0.0
        
        try:
            if mode == DeploymentMode.DOCKER:
                # Docker可用性檢查
                docker_env = environments.get(EnvironmentType.DOCKER)
                if docker_env and docker_env.status == EnvironmentStatus.AVAILABLE:
                    score += self.strategy_weights['docker_availability']
                    score += docker_env.health_score * 0.4  # 健康分數加權
                elif docker_env and docker_env.status in [EnvironmentStatus.OUTDATED, EnvironmentStatus.PERMISSION_DENIED]:
                    score += self.strategy_weights['docker_availability'] * 0.6  # 部分可用
                
                # 系統資源檢查（Docker需要更多資源）
                if system_info.available_memory_gb >= 4:
                    score += self.strategy_weights['system_resources']
                elif system_info.available_memory_gb >= 2:
                    score += self.strategy_weights['system_resources'] * 0.6
                
                # 磁盤空間檢查
                if system_info.available_disk_gb >= 10:
                    score += 5
                elif system_info.available_disk_gb >= 5:
                    score += 2
                
                # 歷史成功率
                if self.success_rates[DeploymentMode.DOCKER] > 0:
                    score += self.strategy_weights['historical_success'] * (self.success_rates[DeploymentMode.DOCKER] / 100)
                
            elif mode == DeploymentMode.UV_PYTHON:
                # Python可用性檢查
                python_env = environments.get(EnvironmentType.PYTHON)
                if python_env and python_env.status == EnvironmentStatus.AVAILABLE:
                    score += self.strategy_weights['uv_availability'] * 0.7  # Python權重
                    score += python_env.health_score * 0.3
                
                # UV可用性檢查
                uv_env = environments.get(EnvironmentType.UV_PYTHON)
                if uv_env and uv_env.status == EnvironmentStatus.AVAILABLE:
                    score += self.strategy_weights['uv_availability'] * 0.3  # UV權重
                elif uv_env and uv_env.status == EnvironmentStatus.NOT_FOUND:
                    # UV不存在但可以安裝
                    score += self.strategy_weights['uv_availability'] * 0.2
                
                # 系統資源檢查（UV需要較少資源）
                score += self.strategy_weights['system_resources']  # UV對資源要求較低
                
                # 啟動速度優勢
                score += 5  # UV通常啟動更快
                
                # 歷史成功率
                if self.success_rates[DeploymentMode.UV_PYTHON] > 0:
                    score += self.strategy_weights['historical_success'] * (self.success_rates[DeploymentMode.UV_PYTHON] / 100)
            
            # 平台特定調整
            if system_info.os_type.value == 'windows':
                if mode == DeploymentMode.UV_PYTHON:
                    score += 10  # Windows上UV更可靠
                elif mode == DeploymentMode.DOCKER:
                    score -= 5   # Windows Docker可能有問題
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.debug(f"計算{mode.value}分數失敗: {e}")
            return 0.0
    
    async def _generate_deployment_plan(
        self,
        docker_score: float,
        uv_score: float,
        environments: Dict[EnvironmentType, Any],
        system_info: SystemInfo
    ) -> DeploymentPlan:
        """生成部署計劃"""
        
        # 根據策略決定主要模式
        if self.deployment_strategy == DeploymentStrategy.DOCKER_ONLY:
            primary_mode = DeploymentMode.DOCKER
            fallback_modes = []
            confidence = docker_score
            
        elif self.deployment_strategy == DeploymentStrategy.UV_ONLY:
            primary_mode = DeploymentMode.UV_PYTHON
            fallback_modes = []
            confidence = uv_score
            
        elif self.deployment_strategy == DeploymentStrategy.DOCKER_PREFERRED:
            if docker_score >= 60:
                primary_mode = DeploymentMode.DOCKER
                fallback_modes = [DeploymentMode.UV_PYTHON] if uv_score >= 40 else []
                confidence = docker_score
            else:
                primary_mode = DeploymentMode.UV_PYTHON
                fallback_modes = []
                confidence = uv_score
                
        elif self.deployment_strategy == DeploymentStrategy.UV_PREFERRED:
            if uv_score >= 60:
                primary_mode = DeploymentMode.UV_PYTHON
                fallback_modes = [DeploymentMode.DOCKER] if docker_score >= 40 else []
                confidence = uv_score
            else:
                primary_mode = DeploymentMode.DOCKER
                fallback_modes = []
                confidence = docker_score
                
        else:  # AUTO_DETECT
            if docker_score > uv_score and docker_score >= 60:
                primary_mode = DeploymentMode.DOCKER
                fallback_modes = [DeploymentMode.UV_PYTHON] if uv_score >= 40 else []
                confidence = docker_score
            elif uv_score >= 60:
                primary_mode = DeploymentMode.UV_PYTHON
                fallback_modes = [DeploymentMode.DOCKER] if docker_score >= 40 else []
                confidence = uv_score
            elif docker_score > uv_score:
                primary_mode = DeploymentMode.DOCKER
                fallback_modes = [DeploymentMode.UV_PYTHON]
                confidence = docker_score
            else:
                primary_mode = DeploymentMode.UV_PYTHON
                fallback_modes = [DeploymentMode.DOCKER]
                confidence = uv_score
        
        # 生成風險因素
        risk_factors = []
        
        if confidence < 40:
            risk_factors.append("環境可行性評分較低")
        
        if primary_mode == DeploymentMode.DOCKER:
            docker_env = environments.get(EnvironmentType.DOCKER)
            if not docker_env or docker_env.status != EnvironmentStatus.AVAILABLE:
                risk_factors.append("Docker環境不可用或不健康")
            
            if system_info.available_memory_gb < 2:
                risk_factors.append("系統可用記憶體不足")
        
        if primary_mode == DeploymentMode.UV_PYTHON:
            python_env = environments.get(EnvironmentType.PYTHON)
            if not python_env or python_env.status != EnvironmentStatus.AVAILABLE:
                risk_factors.append("Python環境不可用")
            
            uv_env = environments.get(EnvironmentType.UV_PYTHON)
            if not uv_env or uv_env.status == EnvironmentStatus.NOT_FOUND:
                risk_factors.append("需要安裝UV包管理器")
        
        # 預估部署時間
        if primary_mode == DeploymentMode.DOCKER:
            estimated_time = 180 + (120 if not fallback_modes else 0)  # 3-5分鐘
        else:
            estimated_time = 120 + (60 if not fallback_modes else 0)   # 2-3分鐘
        
        # 生成說明
        rationale = f"選擇{primary_mode.value}作為主要部署模式（評分: {confidence:.1f}）"
        if fallback_modes:
            rationale += f"，備用模式: {[m.value for m in fallback_modes]}"
        
        return DeploymentPlan(
            strategy=self.deployment_strategy,
            primary_mode=primary_mode,
            fallback_modes=fallback_modes,
            confidence_score=confidence,
            estimated_time=estimated_time,
            risk_factors=risk_factors,
            rationale=rationale
        )
    
    # ========== 部署執行和降級邏輯 ==========
    
    async def _execute_deployment_plan(
        self,
        execution: DeploymentExecution,
        docker_config: Optional[DockerDeploymentConfig],
        uv_env_config: Optional[UVEnvironmentConfig],
        uv_app_config: Optional[ApplicationConfig],
        force_rebuild: bool = False
    ) -> Dict[str, Any]:
        """執行部署計劃"""
        
        modes_to_try = [execution.plan.primary_mode] + execution.plan.fallback_modes
        
        for mode in modes_to_try:
            execution.current_mode = mode
            
            # 檢查是否已經嘗試過這個模式
            if execution.attempts.get(mode, 0) >= self.max_fallback_attempts:
                logger.warning(f"跳過{mode.value}，已達到最大嘗試次數")
                continue
            
            execution.attempts[mode] = execution.attempts.get(mode, 0) + 1
            
            logger.info(f"嘗試{mode.value}部署（第{execution.attempts[mode]}次）...")
            
            try:
                if mode == DeploymentMode.DOCKER:
                    result = await self._execute_docker_deployment(docker_config, force_rebuild)
                elif mode == DeploymentMode.UV_PYTHON:
                    result = await self._execute_uv_deployment(uv_env_config, uv_app_config)
                else:
                    raise DeploymentError(
                        message=f"不支援的部署模式: {mode.value}",
                        deployment_mode=mode.value
                    )
                
                execution.results[mode] = result
                
                if result['success']:
                    # 部署成功
                    execution.success = True
                    execution.total_time = (datetime.now() - execution.start_time).total_seconds()
                    
                    logger.info(f"{mode.value}部署成功")
                    return {
                        'success': True,
                        'deployment_mode': mode.value,
                        'result': result,
                        'execution_summary': {
                            'total_time': execution.total_time,
                            'attempts': dict(execution.attempts),
                            'plan_confidence': execution.plan.confidence_score
                        },
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    # 部署失敗，記錄錯誤並嘗試下個模式
                    error_msg = result.get('error_message', 'Unknown error')
                    execution.error_messages.append(f"{mode.value}: {error_msg}")
                    
                    logger.warning(f"{mode.value}部署失敗: {error_msg}")
                    
                    # 如果有下個模式可嘗試，等待一段時間
                    if modes_to_try.index(mode) < len(modes_to_try) - 1:
                        logger.info(f"等待{self.retry_delay}秒後嘗試降級...")
                        await asyncio.sleep(self.retry_delay)
                
            except Exception as e:
                error_msg = str(e)
                execution.error_messages.append(f"{mode.value}: {error_msg}")
                
                logger.error(f"{mode.value}部署異常: {error_msg}")
                
                # 如果有下個模式可嘗試，等待一段時間
                if modes_to_try.index(mode) < len(modes_to_try) - 1:
                    logger.info(f"等待{self.retry_delay}秒後嘗試降級...")
                    await asyncio.sleep(self.retry_delay)
        
        # 所有模式都失敗
        execution.total_time = (datetime.now() - execution.start_time).total_seconds()
        
        return {
            'success': False,
            'deployment_mode': DeploymentMode.FAILED.value,
            'error_message': '所有部署模式都失敗',
            'detailed_errors': execution.error_messages,
            'execution_summary': {
                'total_time': execution.total_time,
                'attempts': dict(execution.attempts),
                'plan_confidence': execution.plan.confidence_score
            },
            'timestamp': datetime.now().isoformat()
        }
    
    async def _execute_docker_deployment(
        self, 
        config: Optional[DockerDeploymentConfig],
        force_rebuild: bool = False
    ) -> Dict[str, Any]:
        """執行Docker部署"""
        try:
            if not config:
                config = DockerDeploymentConfig()
            
            if force_rebuild:
                config.force_rebuild = True
            
            result = await self.docker_manager.deploy(config)
            
            return {
                'success': result.success,
                'deployment_time': result.deployment_time,
                'containers': len(result.containers),
                'health_score': sum(c.health == 'healthy' for c in result.containers) / len(result.containers) * 100 if result.containers else 0,
                'error_message': result.error_message,
                'warnings': result.warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'error_message': str(e)
            }
    
    async def _execute_uv_deployment(
        self,
        env_config: Optional[UVEnvironmentConfig],
        app_config: Optional[ApplicationConfig]
    ) -> Dict[str, Any]:
        """執行UV部署"""
        try:
            if not env_config:
                env_config = UVEnvironmentConfig()
            if not app_config:
                app_config = ApplicationConfig()
            
            result = await self.uv_manager.deploy(env_config, app_config)
            
            return {
                'success': result.success,
                'deployment_time': result.deployment_time,
                'venv_path': result.venv_path,
                'installed_packages': len(result.installed_packages),
                'process_pid': result.process_info.pid if result.process_info else None,
                'error_message': result.error_message,
                'warnings': result.warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'error_message': str(e)
            }
    
    # ========== 監控和自動恢復 ==========
    
    async def _start_monitoring(self) -> None:
        """啟動監控任務"""
        if self.monitoring_task and not self.monitoring_task.done():
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("部署協調器監控已啟動")
    
    async def _monitoring_loop(self) -> None:
        """監控循環"""
        while self.is_initialized:
            try:
                if self.current_deployment_mode != DeploymentMode.NOT_DEPLOYED:
                    # 檢查當前部署健康狀態
                    healthy = await self._check_current_deployment_health()
                    
                    if not healthy:
                        self._consecutive_failures += 1
                        logger.warning(f"檢測到部署不健康，連續失敗次數: {self._consecutive_failures}")
                        
                        # 觸發自動恢復
                        if self.auto_recovery_enabled and self._consecutive_failures >= 3:
                            logger.info("觸發自動恢復...")
                            try:
                                await self._perform_auto_recovery()
                                self._consecutive_failures = 0
                            except Exception as e:
                                logger.error(f"自動恢復失敗: {e}")
                    else:
                        # 恢復健康，重置計數器
                        if self._consecutive_failures > 0:
                            logger.info("部署恢復健康，重置失敗計數器")
                            self._consecutive_failures = 0
                
                # 記錄健康檢查時間
                self._last_health_check = datetime.now()
                
                # 等待下次檢查
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                logger.info("監控循環被取消")
                break
            except Exception as e:
                logger.error(f"監控循環異常: {e}")
                await asyncio.sleep(30)
    
    async def _check_current_deployment_health(self) -> bool:
        """檢查當前部署健康狀態"""
        try:
            if self.current_deployment_mode == DeploymentMode.DOCKER:
                status = await self.docker_manager.get_deployment_status()
                return status.get('is_healthy', False)
            elif self.current_deployment_mode == DeploymentMode.UV_PYTHON:
                status = await self.uv_manager.get_deployment_status()
                return status.get('is_application_running', False)
            else:
                return True  # 沒有部署被認為是健康的
                
        except Exception as e:
            logger.debug(f"檢查部署健康狀態失敗: {e}")
            return False
    
    async def _perform_auto_recovery(self) -> None:
        """執行自動恢復"""
        logger.info(f"開始自動恢復，當前模式: {self.current_deployment_mode.value}")
        
        try:
            # 首先嘗試重啟當前部署
            restart_result = await self.restart_deployment()
            
            if restart_result['success']:
                logger.info("重啟恢復成功")
                return
            
            # 重啟失敗，嘗試切換到備用模式
            if self.current_execution and self.current_execution.plan.fallback_modes:
                logger.info("嘗試切換到備用部署模式...")
                
                # 停止當前部署
                await self.stop_deployment(force=True)
                
                # 使用備用模式重新部署
                fallback_mode = self.current_execution.plan.fallback_modes[0]
                
                deploy_result = await self.deploy(force_mode=fallback_mode)
                
                if deploy_result['success']:
                    logger.info(f"切換到備用模式{fallback_mode.value}成功")
                else:
                    logger.error("備用模式部署也失敗")
            else:
                logger.warning("沒有可用的備用恢復模式")
                
        except Exception as e:
            logger.error(f"自動恢復過程失敗: {e}")
    
    # ========== 歷史統計和分析 ==========
    
    async def _calculate_historical_success_rates(self) -> None:
        """計算歷史成功率"""
        try:
            for mode in [DeploymentMode.DOCKER, DeploymentMode.UV_PYTHON]:
                successes = sum(1 for h in self.deployment_history 
                              if h.get('deployment_mode') == mode.value and h.get('success'))
                total = sum(1 for h in self.deployment_history 
                           if h.get('deployment_mode') == mode.value)
                
                if total > 0:
                    self.success_rates[mode] = (successes / total) * 100
                else:
                    self.success_rates[mode] = 0.0
            
            logger.debug(f"歷史成功率 - Docker: {self.success_rates[DeploymentMode.DOCKER]:.1f}%, UV: {self.success_rates[DeploymentMode.UV_PYTHON]:.1f}%")
            
        except Exception as e:
            logger.debug(f"計算歷史成功率失敗: {e}")
    
    async def _record_deployment_execution(self, execution: DeploymentExecution) -> None:
        """記錄部署執行歷史"""
        try:
            history_entry = {
                'timestamp': execution.start_time.isoformat(),
                'strategy': execution.plan.strategy.value,
                'deployment_mode': execution.current_mode.value,
                'success': execution.success,
                'total_time': execution.total_time,
                'confidence_score': execution.plan.confidence_score,
                'attempts': dict(execution.attempts),
                'error_messages': execution.error_messages,
                'risk_factors': execution.plan.risk_factors
            }
            
            self.deployment_history.append(history_entry)
            
            # 限制歷史記錄數量
            if len(self.deployment_history) > 100:
                self.deployment_history = self.deployment_history[-100:]
            
            # 重新計算成功率
            await self._calculate_historical_success_rates()
            
            logger.debug("已記錄部署執行歷史")
            
        except Exception as e:
            logger.debug(f"記錄部署歷史失敗: {e}")
    
    # ========== 公開API方法 ==========
    
    async def get_deployment_recommendations(self) -> Dict[str, Any]:
        """獲取部署建議"""
        try:
            # 獲取環境建議
            env_recommendations = await self.environment_detector.get_deployment_recommendations()
            
            # 獲取當前狀態
            health = await self.health_check()
            
            # 生成協調器特定的建議
            coordinator_recommendations = {
                'recommended_strategy': self.deployment_strategy.value,
                'current_deployment': {
                    'mode': self.current_deployment_mode.value,
                    'status': self.coordinator_status.value,
                    'health': health.get('status', 'unknown')
                },
                'success_rates': dict(self.success_rates),
                'recent_deployments': self.deployment_history[-5:] if self.deployment_history else [],
                'auto_recovery_enabled': self.auto_recovery_enabled,
                'consecutive_failures': self._consecutive_failures
            }
            
            # 合併建議
            combined_recommendations = {
                **env_recommendations,
                'coordinator_info': coordinator_recommendations,
                'generated_at': datetime.now().isoformat()
            }
            
            return combined_recommendations
            
        except Exception as e:
            logger.error(f"生成部署建議失敗: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    async def get_deployment_status(self) -> Dict[str, Any]:
        """獲取詳細部署狀態"""
        try:
            base_status = {
                'coordinator_status': self.coordinator_status.value,
                'current_deployment_mode': self.current_deployment_mode.value,
                'deployment_strategy': self.deployment_strategy.value,
                'consecutive_failures': self._consecutive_failures,
                'auto_recovery_enabled': self.auto_recovery_enabled,
                'last_health_check': self._last_health_check.isoformat() if self._last_health_check else None
            }
            
            # 獲取當前部署的詳細狀態
            if self.current_deployment_mode == DeploymentMode.DOCKER:
                docker_status = await self.docker_manager.get_deployment_status()
                base_status['deployment_details'] = docker_status
            elif self.current_deployment_mode == DeploymentMode.UV_PYTHON:
                uv_status = await self.uv_manager.get_deployment_status()
                base_status['deployment_details'] = uv_status
            
            # 添加當前執行信息
            if self.current_execution:
                base_status['current_execution'] = {
                    'plan_confidence': self.current_execution.plan.confidence_score,
                    'total_time': self.current_execution.total_time,
                    'attempts': dict(self.current_execution.attempts),
                    'success': self.current_execution.success
                }
            
            return base_status
            
        except Exception as e:
            logger.error(f"獲取部署狀態失敗: {e}")
            return {
                'error': str(e),
                'coordinator_status': self.coordinator_status.value,
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_deployment_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """獲取部署歷史"""
        return self.deployment_history[-limit:] if self.deployment_history else []
    
    def set_deployment_strategy(self, strategy: DeploymentStrategy) -> None:
        """設置部署策略"""
        self.deployment_strategy = strategy
        logger.info(f"部署策略已設置為: {strategy.value}")
    
    def set_auto_recovery_enabled(self, enabled: bool) -> None:
        """設置自動恢復開關"""
        self.auto_recovery_enabled = enabled
        logger.info(f"自動恢復已{'啟用' if enabled else '停用'}")
    
    def update_strategy_weights(self, weights: Dict[str, float]) -> None:
        """更新策略權重"""
        self.strategy_weights.update(weights)
        logger.info(f"策略權重已更新: {weights}")
    
    def set_monitor_integration(self, monitor: "DeploymentMonitorIntegration") -> None:
        """設置監控整合服務"""
        self.monitor_integration = monitor
        logger.info("監控整合服務已設置")
    
    def enable_monitoring(self, enabled: bool = True) -> None:
        """啟用/停用監控"""
        self.monitoring_enabled = enabled
        logger.info(f"部署監控已{'啟用' if enabled else '停用'}")
    
    async def _log_deployment_step(
        self, 
        step_name: str, 
        step_status: str, 
        step_details: Optional[Dict[str, Any]] = None,
        performance_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """記錄部署步驟（內部方法）"""
        if self.monitor_integration and self.monitoring_enabled and self.current_deployment_id:
            await self.monitor_integration.log_deployment_step(
                deployment_id=self.current_deployment_id,
                step_name=step_name,
                step_status=step_status,
                step_details=step_details,
                performance_data=performance_data
            )
    
    async def _log_deployment_error(
        self, 
        error_type: str, 
        error_message: str, 
        error_details: Optional[Dict[str, Any]] = None,
        is_critical: bool = False
    ) -> None:
        """記錄部署錯誤（內部方法）"""
        if self.monitor_integration and self.monitoring_enabled and self.current_deployment_id:
            await self.monitor_integration.log_deployment_error(
                deployment_id=self.current_deployment_id,
                error_type=error_type,
                error_message=error_message,
                error_details=error_details,
                is_critical=is_critical
            )