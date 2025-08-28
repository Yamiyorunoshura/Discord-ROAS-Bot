"""
Docker部署管理器
Task ID: 2 - 自動化部署和啟動系統開發

Docker部署管理器，負責：
- Docker環境的自動檢測和安裝
- Docker Compose服務的管理和監控
- 容器健康檢查和故障恢復
- 跨平台Docker部署支援
- 與現有Docker配置的無縫整合
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import yaml
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from src.core.errors import (
    DeploymentError, ServiceStartupError, DependencyInstallError, 
    create_error
)
from src.services.environment_detector import (
    EnvironmentDetector, EnvironmentType, EnvironmentStatus, 
    OperatingSystem, InstallationResult
)
from core.base_service import BaseService, ServiceType


logger = logging.getLogger('services.docker_deployment')


class DockerServiceStatus(Enum):
    """Docker服務狀態"""
    NOT_STARTED = "not_started"
    BUILDING = "building"
    STARTING = "starting" 
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DEGRADED = "degraded"
    RESTARTING = "restarting"


class DockerProfile(Enum):
    """Docker Compose配置檔案"""
    DEFAULT = "default"
    DEV = "dev"
    PROD = "prod"
    MONITORING = "monitoring"
    DEV_TOOLS = "dev-tools"


@dataclass
class ContainerInfo:
    """容器信息"""
    name: str
    image: str
    status: str
    health: str = "unknown"
    ports: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    restart_count: int = 0
    memory_usage: str = "unknown"
    cpu_usage: str = "unknown"


@dataclass
class DockerDeploymentConfig:
    """Docker部署配置"""
    profile: DockerProfile = DockerProfile.DEFAULT
    compose_file: str = "docker/compose.yaml"
    env_file: Optional[str] = None
    project_name: Optional[str] = None
    build_args: Dict[str, str] = field(default_factory=dict)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    volumes: Dict[str, str] = field(default_factory=dict)
    force_rebuild: bool = False
    detached: bool = True
    pull_latest: bool = True
    timeout: int = 300  # 5分鐘超時
    health_check_interval: int = 30  # 30秒健康檢查間隔
    max_restart_attempts: int = 3


@dataclass
class DockerDeploymentResult:
    """Docker部署結果"""
    success: bool
    status: DockerServiceStatus
    containers: List[ContainerInfo] = field(default_factory=list)
    deployment_time: float = 0.0
    build_time: float = 0.0
    start_time: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    health_check_results: Dict[str, Any] = field(default_factory=dict)
    resource_usage: Dict[str, Any] = field(default_factory=dict)


class DockerDeploymentManager(BaseService):
    """
    Docker部署管理器
    
    管理Docker容器的完整生命週期，包括環境檢測、自動安裝、
    容器構建、服務啟動、健康監控和故障恢復
    """
    
    def __init__(self, project_root: Optional[str] = None):
        super().__init__()
        
        self.service_metadata = {
            'service_type': ServiceType.DEPLOYMENT,
            'service_name': 'docker_deployment_manager',
            'version': '2.4.4',
            'capabilities': {
                'auto_installation': True,
                'health_monitoring': True,
                'multi_profile_support': True,
                'cross_platform': True,
                'service_management': True,
                'volume_management': True
            }
        }
        
        # 路徑配置
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.compose_file = self.project_root / "docker" / "compose.yaml"
        self.default_env_file = self.project_root / ".env"
        
        # 服務狀態
        self.current_status = DockerServiceStatus.NOT_STARTED
        self.current_config: Optional[DockerDeploymentConfig] = None
        self.deployed_containers: List[ContainerInfo] = []
        self.deployment_history: List[Dict[str, Any]] = []
        
        # 依賴服務
        self.environment_detector = EnvironmentDetector()
        
        # 監控配置
        self.health_check_task: Optional[asyncio.Task] = None
        self.monitoring_enabled = True
        self.auto_restart_enabled = True
        
        # 緩存和狀態
        self._last_health_check = None
        self._consecutive_failures = 0
        self._restart_count = 0
        
        # 資源限制
        self.resource_limits = {
            'memory_threshold_mb': 1024,  # 1GB
            'cpu_threshold_percent': 80,
            'disk_threshold_gb': 2
        }
    
    async def start(self) -> None:
        """啟動Docker部署管理器"""
        try:
            logger.info("啟動Docker部署管理器...")
            
            # 啟動環境檢測服務
            await self.environment_detector.start()
            
            # 檢測Docker環境
            docker_result = await self.environment_detector.detect_docker()
            
            if docker_result.status != EnvironmentStatus.AVAILABLE:
                logger.warning(f"Docker環境不可用: {docker_result.status.value}")
                # 不拋出異常，允許管理器啟動但標記為降級狀態
                self.current_status = DockerServiceStatus.DEGRADED
            
            # 驗證配置文件
            await self._validate_configuration()
            
            # 啟動健康檢查監控
            if self.monitoring_enabled:
                await self._start_health_monitoring()
            
            self.is_initialized = True
            logger.info("Docker部署管理器啟動完成")
            
        except Exception as e:
            logger.error(f"Docker部署管理器啟動失敗: {e}")
            raise ServiceStartupError(
                service_name='docker_deployment_manager',
                startup_mode='docker',
                reason=str(e)
            )
    
    async def stop(self) -> None:
        """停止Docker部署管理器"""
        try:
            logger.info("停止Docker部署管理器...")
            
            # 停止健康檢查監控
            if self.health_check_task and not self.health_check_task.done():
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # 停止環境檢測服務
            await self.environment_detector.stop()
            
            self.is_initialized = False
            logger.info("Docker部署管理器已停止")
            
        except Exception as e:
            logger.error(f"停止Docker部署管理器失敗: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 檢查Docker環境
            docker_available = await self._is_docker_available()
            
            # 檢查容器狀態
            container_health = await self._check_containers_health()
            
            # 檢查資源使用
            resource_status = await self._check_resource_usage()
            
            # 綜合健康狀態
            overall_health = "healthy"
            issues = []
            
            if not docker_available:
                overall_health = "degraded"
                issues.append("Docker不可用")
            
            if container_health and container_health.get('unhealthy_count', 0) > 0:
                overall_health = "degraded"
                issues.append(f"有 {container_health['unhealthy_count']} 個不健康容器")
            
            if resource_status and resource_status.get('critical_resources'):
                overall_health = "degraded"
                issues.extend([f"資源告警: {res}" for res in resource_status['critical_resources']])
            
            return {
                'service_name': 'docker_deployment_manager',
                'status': overall_health,
                'current_deployment_status': self.current_status.value,
                'docker_available': docker_available,
                'deployed_containers': len(self.deployed_containers),
                'container_health': container_health,
                'resource_status': resource_status,
                'issues': issues,
                'consecutive_failures': self._consecutive_failures,
                'restart_count': self._restart_count,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Docker部署管理器健康檢查失敗: {e}")
            return {
                'service_name': 'docker_deployment_manager',
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    # ========== 部署管理方法 ==========
    
    async def deploy(self, config: Optional[DockerDeploymentConfig] = None) -> DockerDeploymentResult:
        """
        執行Docker部署
        
        Args:
            config: 部署配置，None時使用默認配置
        """
        if not config:
            config = DockerDeploymentConfig()
        
        logger.info(f"開始Docker部署，profile: {config.profile.value}")
        
        start_time = datetime.now()
        result = DockerDeploymentResult(
            success=False,
            status=DockerServiceStatus.NOT_STARTED
        )
        
        try:
            # 更新當前配置和狀態
            self.current_config = config
            self.current_status = DockerServiceStatus.BUILDING
            
            # 1. 環境檢查
            logger.info("檢查Docker環境...")
            docker_ready = await self._ensure_docker_ready()
            
            if not docker_ready:
                raise DeploymentError(
                    message="Docker環境不可用",
                    deployment_mode="docker"
                )
            
            # 2. 配置驗證
            logger.info("驗證部署配置...")
            await self._validate_deployment_config(config)
            
            # 3. 停止現有服務（如果存在）
            if self.deployed_containers:
                logger.info("停止現有容器...")
                await self._stop_services(config)
            
            # 4. 拉取最新映像（如果需要）
            if config.pull_latest:
                logger.info("拉取最新Docker映像...")
                build_start = datetime.now()
                await self._pull_images(config)
                result.build_time = (datetime.now() - build_start).total_seconds()
            
            # 5. 構建服務（如果需要）
            if config.force_rebuild or await self._needs_rebuild(config):
                logger.info("構建Docker映像...")
                build_start = datetime.now()
                await self._build_services(config)
                result.build_time += (datetime.now() - build_start).total_seconds()
            
            # 6. 啟動服務
            logger.info("啟動Docker服務...")
            self.current_status = DockerServiceStatus.STARTING
            start_service_time = datetime.now()
            
            await self._start_services(config)
            result.start_time = (datetime.now() - start_service_time).total_seconds()
            
            # 7. 等待服務就緒和健康檢查
            logger.info("等待服務就緒...")
            await self._wait_for_services_ready(config)
            
            # 8. 收集容器信息
            self.deployed_containers = await self._get_containers_info(config)
            result.containers = self.deployed_containers
            
            # 9. 執行健康檢查
            health_results = await self._perform_health_checks(config)
            result.health_check_results = health_results
            
            # 10. 檢查資源使用
            resource_usage = await self._check_resource_usage()
            result.resource_usage = resource_usage or {}
            
            # 計算總部署時間
            result.deployment_time = (datetime.now() - start_time).total_seconds()
            
            # 判斷部署成功
            healthy_containers = sum(1 for container in self.deployed_containers 
                                   if container.health in ['healthy', 'running'])
            
            if healthy_containers == len(self.deployed_containers) and self.deployed_containers:
                result.success = True
                result.status = DockerServiceStatus.RUNNING
                self.current_status = DockerServiceStatus.RUNNING
                logger.info(f"Docker部署成功，{healthy_containers} 個容器運行中")
            else:
                result.status = DockerServiceStatus.DEGRADED
                self.current_status = DockerServiceStatus.DEGRADED
                result.warnings.append(f"部分容器不健康: {healthy_containers}/{len(self.deployed_containers)}")
                logger.warning(f"Docker部署部分成功: {healthy_containers}/{len(self.deployed_containers)} 容器健康")
            
            # 記錄部署歷史
            await self._record_deployment_history(config, result)
            
            return result
            
        except Exception as e:
            # 部署失敗處理
            result.success = False
            result.status = DockerServiceStatus.FAILED
            result.error_message = str(e)
            result.deployment_time = (datetime.now() - start_time).total_seconds()
            
            self.current_status = DockerServiceStatus.FAILED
            self._consecutive_failures += 1
            
            logger.error(f"Docker部署失敗: {e}")
            
            # 嘗試收集失敗狀態下的容器信息
            try:
                result.containers = await self._get_containers_info(config)
                result.logs = await self._get_deployment_logs(config)
            except Exception as log_error:
                logger.debug(f"收集失敗日誌時出錯: {log_error}")
            
            # 記錄失敗歷史
            await self._record_deployment_history(config, result)
            
            # 重新拋出部署異常
            raise DeploymentError(
                message=f"Docker部署失敗: {str(e)}",
                deployment_mode="docker",
                details=result.__dict__
            )
    
    async def stop_deployment(self, force: bool = False) -> bool:
        """
        停止當前部署
        
        Args:
            force: 是否強制停止
        """
        logger.info(f"停止Docker部署，強制模式: {force}")
        
        try:
            self.current_status = DockerServiceStatus.STOPPING
            
            if self.current_config:
                success = await self._stop_services(self.current_config, force)
                
                if success:
                    self.current_status = DockerServiceStatus.STOPPED
                    self.deployed_containers = []
                    logger.info("Docker部署已停止")
                    return True
                else:
                    self.current_status = DockerServiceStatus.FAILED
                    logger.error("停止Docker部署失敗")
                    return False
            else:
                logger.warning("沒有活躍的部署配置")
                return True
                
        except Exception as e:
            logger.error(f"停止Docker部署異常: {e}")
            self.current_status = DockerServiceStatus.FAILED
            return False
    
    async def restart_deployment(self, force_rebuild: bool = False) -> DockerDeploymentResult:
        """
        重啟部署
        
        Args:
            force_rebuild: 是否強制重建
        """
        logger.info(f"重啟Docker部署，強制重建: {force_rebuild}")
        
        try:
            self.current_status = DockerServiceStatus.RESTARTING
            self._restart_count += 1
            
            if self.current_config:
                # 先停止現有服務
                await self.stop_deployment()
                
                # 等待一段時間確保清理完成
                await asyncio.sleep(2)
                
                # 更新配置
                config = self.current_config
                config.force_rebuild = config.force_rebuild or force_rebuild
                
                # 重新部署
                return await self.deploy(config)
            else:
                raise DeploymentError(
                    message="沒有可重啟的部署配置",
                    deployment_mode="docker"
                )
                
        except Exception as e:
            logger.error(f"重啟Docker部署失敗: {e}")
            self.current_status = DockerServiceStatus.FAILED
            raise
    
    # ========== Docker環境管理 ==========
    
    async def install_docker(self, force: bool = False) -> InstallationResult:
        """
        自動安裝Docker
        
        Args:
            force: 是否強制重新安裝
        """
        logger.info(f"開始安裝Docker，強制模式: {force}")
        
        try:
            result = await self.environment_detector.auto_install_environment(
                EnvironmentType.DOCKER,
                force=force
            )
            
            if result.success:
                logger.info(f"Docker安裝成功，版本: {result.version_installed}")
                
                # 執行後續配置
                await self._post_docker_installation_setup()
            else:
                logger.error(f"Docker安裝失敗: {result.error_message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Docker安裝異常: {e}")
            return InstallationResult(
                success=False,
                environment=EnvironmentType.DOCKER,
                error_message=str(e)
            )
    
    async def _post_docker_installation_setup(self) -> None:
        """Docker安裝後的設置"""
        try:
            # 檢查當前用戶是否在docker群組中（Linux）
            system_info = await self.environment_detector.detect_system_info()
            
            if system_info.os_type == OperatingSystem.LINUX:
                # 檢查docker群組權限
                result = await self._run_command(['groups'])
                if result.returncode == 0 and 'docker' not in result.stdout:
                    logger.info("檢測到需要添加用戶到docker群組")
                    
                    # 嘗試添加用戶到docker群組
                    try:
                        await self._run_command(['sudo', 'usermod', '-aG', 'docker', os.getenv('USER', 'root')])
                        logger.info("已添加用戶到docker群組，需要重新登入以生效")
                    except Exception as e:
                        logger.warning(f"添加用戶到docker群組失敗: {e}")
            
            # 測試Docker安裝
            await self._test_docker_installation()
            
        except Exception as e:
            logger.warning(f"Docker後續設置失敗: {e}")
    
    async def _test_docker_installation(self) -> None:
        """測試Docker安裝"""
        try:
            # 運行hello-world容器測試
            result = await self._run_command(['docker', 'run', '--rm', 'hello-world'], timeout=60)
            
            if result.returncode == 0:
                logger.info("Docker安裝測試成功")
            else:
                logger.warning(f"Docker安裝測試失敗: {result.stderr}")
                
        except Exception as e:
            logger.warning(f"Docker安裝測試異常: {e}")
    
    async def _ensure_docker_ready(self) -> bool:
        """確保Docker環境就緒"""
        try:
            # 檢查Docker是否可用
            if not await self._is_docker_available():
                logger.info("Docker不可用，嘗試自動安裝...")
                
                install_result = await self.install_docker()
                if not install_result.success:
                    return False
            
            # 檢查Docker Compose
            if not await self._is_docker_compose_available():
                logger.error("Docker Compose不可用")
                return False
            
            # 檢查Docker daemon
            if not await self._is_docker_daemon_running():
                logger.info("嘗試啟動Docker daemon...")
                if not await self._start_docker_daemon():
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Docker環境準備失敗: {e}")
            return False
    
    async def _is_docker_available(self) -> bool:
        """檢查Docker是否可用"""
        try:
            result = await self._run_command(['docker', '--version'], timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    async def _is_docker_compose_available(self) -> bool:
        """檢查Docker Compose是否可用"""
        try:
            result = await self._run_command(['docker', 'compose', 'version'], timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    async def _is_docker_daemon_running(self) -> bool:
        """檢查Docker daemon是否運行"""
        try:
            result = await self._run_command(['docker', 'info'], timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    async def _start_docker_daemon(self) -> bool:
        """嘗試啟動Docker daemon"""
        try:
            system_info = await self.environment_detector.detect_system_info()
            
            if system_info.os_type == OperatingSystem.LINUX:
                # Linux: 使用systemctl
                result = await self._run_command(['sudo', 'systemctl', 'start', 'docker'])
                if result.returncode == 0:
                    await asyncio.sleep(5)  # 等待服務啟動
                    return await self._is_docker_daemon_running()
            
            elif system_info.os_type == OperatingSystem.MACOS:
                # macOS: 啟動Docker Desktop
                result = await self._run_command(['open', '/Applications/Docker.app'])
                if result.returncode == 0:
                    logger.info("已嘗試啟動Docker Desktop，請等待啟動完成...")
                    await asyncio.sleep(30)  # 等待Docker Desktop啟動
                    return await self._is_docker_daemon_running()
            
            elif system_info.os_type == OperatingSystem.WINDOWS:
                # Windows: 啟動Docker Desktop
                result = await self._run_command(['powershell', '-Command', 'Start-Process', '"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"'])
                if result.returncode == 0:
                    logger.info("已嘗試啟動Docker Desktop，請等待啟動完成...")
                    await asyncio.sleep(30)
                    return await self._is_docker_daemon_running()
            
            return False
            
        except Exception as e:
            logger.error(f"啟動Docker daemon失敗: {e}")
            return False
    
    # ========== Docker Compose操作 ==========
    
    async def _build_services(self, config: DockerDeploymentConfig) -> None:
        """構建Docker服務"""
        cmd = [
            'docker', 'compose',
            '-f', str(self.compose_file),
            '--profile', config.profile.value,
            'build'
        ]
        
        if config.force_rebuild:
            cmd.append('--no-cache')
        
        if config.env_file:
            cmd.extend(['--env-file', config.env_file])
        
        logger.debug(f"執行構建命令: {' '.join(cmd)}")
        
        result = await self._run_command(cmd, timeout=config.timeout)
        
        if result.returncode != 0:
            raise DeploymentError(
                message=f"Docker構建失敗: {result.stderr}",
                deployment_mode="docker"
            )
    
    async def _pull_images(self, config: DockerDeploymentConfig) -> None:
        """拉取Docker映像"""
        cmd = [
            'docker', 'compose',
            '-f', str(self.compose_file),
            '--profile', config.profile.value,
            'pull',
            '--ignore-pull-failures'
        ]
        
        if config.env_file:
            cmd.extend(['--env-file', config.env_file])
        
        logger.debug(f"執行拉取命令: {' '.join(cmd)}")
        
        result = await self._run_command(cmd, timeout=config.timeout)
        
        # 拉取失敗不拋出異常，因為使用了 --ignore-pull-failures
        if result.returncode != 0:
            logger.warning(f"部分映像拉取失敗: {result.stderr}")
    
    async def _start_services(self, config: DockerDeploymentConfig) -> None:
        """啟動Docker服務"""
        cmd = [
            'docker', 'compose',
            '-f', str(self.compose_file),
            '--profile', config.profile.value,
            'up'
        ]
        
        if config.detached:
            cmd.append('-d')
        
        if config.env_file:
            cmd.extend(['--env-file', config.env_file])
        
        if config.project_name:
            cmd.extend(['-p', config.project_name])
        
        logger.debug(f"執行啟動命令: {' '.join(cmd)}")
        
        result = await self._run_command(cmd, timeout=config.timeout)
        
        if result.returncode != 0:
            raise DeploymentError(
                message=f"Docker服務啟動失敗: {result.stderr}",
                deployment_mode="docker"
            )
    
    async def _stop_services(self, config: DockerDeploymentConfig, force: bool = False) -> bool:
        """停止Docker服務"""
        try:
            cmd = [
                'docker', 'compose',
                '-f', str(self.compose_file),
                '--profile', config.profile.value
            ]
            
            if config.env_file:
                cmd.extend(['--env-file', config.env_file])
            
            if config.project_name:
                cmd.extend(['-p', config.project_name])
            
            if force:
                cmd.extend(['kill'])
            else:
                cmd.extend(['down'])
            
            logger.debug(f"執行停止命令: {' '.join(cmd)}")
            
            result = await self._run_command(cmd, timeout=60)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"停止Docker服務失敗: {e}")
            return False
    
    async def _wait_for_services_ready(self, config: DockerDeploymentConfig) -> None:
        """等待服務就緒"""
        logger.info("等待服務就緒...")
        
        max_wait_time = 120  # 2分鐘
        check_interval = 5   # 5秒檢查一次
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                # 檢查容器狀態
                containers = await self._get_containers_info(config)
                
                if not containers:
                    logger.debug("尚未檢測到容器")
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
                    continue
                
                # 檢查所有容器是否就緒
                all_ready = True
                for container in containers:
                    if container.status not in ['running', 'Up']:
                        logger.debug(f"容器 {container.name} 狀態: {container.status}")
                        all_ready = False
                        break
                    
                    # 如果容器有健康檢查，等待健康狀態
                    if container.health not in ['healthy', 'unknown']:
                        if container.health == 'starting':
                            logger.debug(f"容器 {container.name} 健康檢查啟動中...")
                            all_ready = False
                            break
                        elif container.health == 'unhealthy':
                            logger.warning(f"容器 {container.name} 不健康")
                            # 不healthy的容器也允許繼續，可能是配置問題
                
                if all_ready:
                    logger.info("所有服務已就緒")
                    return
                
            except Exception as e:
                logger.debug(f"檢查服務狀態時出錯: {e}")
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        logger.warning(f"等待服務就緒超時 ({max_wait_time}秒)")
    
    # ========== 容器信息和監控 ==========
    
    async def _get_containers_info(self, config: DockerDeploymentConfig) -> List[ContainerInfo]:
        """獲取容器信息"""
        try:
            # 使用docker compose ps獲取容器信息
            cmd = [
                'docker', 'compose',
                '-f', str(self.compose_file),
                '--profile', config.profile.value,
                'ps',
                '--format', 'json'
            ]
            
            if config.env_file:
                cmd.extend(['--env-file', config.env_file])
            
            if config.project_name:
                cmd.extend(['-p', config.project_name])
            
            result = await self._run_command(cmd, timeout=30)
            
            if result.returncode != 0:
                logger.warning(f"獲取容器信息失敗: {result.stderr}")
                return []
            
            containers = []
            
            # 解析JSON輸出
            try:
                container_data = json.loads(result.stdout) if result.stdout.strip() else []
                if not isinstance(container_data, list):
                    container_data = [container_data]
                
                for data in container_data:
                    container = ContainerInfo(
                        name=data.get('Name', 'unknown'),
                        image=data.get('Image', 'unknown'),
                        status=data.get('State', 'unknown'),
                        health=data.get('Health', 'unknown'),
                        ports=data.get('Publishers', [])
                    )
                    
                    # 嘗試獲取更詳細的容器信息
                    detailed_info = await self._get_detailed_container_info(container.name)
                    if detailed_info:
                        container.created_at = detailed_info.get('created_at')
                        container.started_at = detailed_info.get('started_at')
                        container.restart_count = detailed_info.get('restart_count', 0)
                        container.memory_usage = detailed_info.get('memory_usage', 'unknown')
                        container.cpu_usage = detailed_info.get('cpu_usage', 'unknown')
                    
                    containers.append(container)
                
                return containers
                
            except json.JSONDecodeError as e:
                logger.error(f"解析容器JSON信息失敗: {e}")
                # fallback到文本解析
                return await self._parse_containers_text_output(config)
                
        except Exception as e:
            logger.error(f"獲取容器信息異常: {e}")
            return []
    
    async def _get_detailed_container_info(self, container_name: str) -> Optional[Dict[str, Any]]:
        """獲取容器詳細信息"""
        try:
            cmd = ['docker', 'inspect', container_name, '--format', '{{json .}}']
            result = await self._run_command(cmd, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                created_time = None
                started_time = None
                
                if data.get('Created'):
                    created_time = datetime.fromisoformat(data['Created'].replace('Z', '+00:00'))
                
                if data.get('State', {}).get('StartedAt'):
                    started_time = datetime.fromisoformat(data['State']['StartedAt'].replace('Z', '+00:00'))
                
                return {
                    'created_at': created_time,
                    'started_at': started_time,
                    'restart_count': data.get('RestartCount', 0),
                    'memory_usage': 'unknown',  # 需要額外的stats命令
                    'cpu_usage': 'unknown'
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"獲取容器 {container_name} 詳細信息失敗: {e}")
            return None
    
    async def _parse_containers_text_output(self, config: DockerDeploymentConfig) -> List[ContainerInfo]:
        """解析文本格式的容器輸出（fallback）"""
        try:
            cmd = [
                'docker', 'compose',
                '-f', str(self.compose_file),
                '--profile', config.profile.value,
                'ps'
            ]
            
            if config.env_file:
                cmd.extend(['--env-file', config.env_file])
            
            result = await self._run_command(cmd, timeout=30)
            
            if result.returncode != 0:
                return []
            
            containers = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳過標題行
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        container = ContainerInfo(
                            name=parts[0],
                            image=parts[1],
                            status=' '.join(parts[3:]) if len(parts) > 3 else 'unknown'
                        )
                        containers.append(container)
            
            return containers
            
        except Exception as e:
            logger.error(f"解析容器文本輸出失敗: {e}")
            return []
    
    # ========== 健康檢查和監控 ==========
    
    async def _perform_health_checks(self, config: DockerDeploymentConfig) -> Dict[str, Any]:
        """執行健康檢查"""
        health_results = {
            'overall_health': 'unknown',
            'container_health': {},
            'service_health': {},
            'check_timestamp': datetime.now().isoformat()
        }
        
        try:
            # 檢查容器健康狀態
            containers = await self._get_containers_info(config)
            
            healthy_count = 0
            total_count = len(containers)
            
            for container in containers:
                container_health = 'unknown'
                
                if container.status in ['running', 'Up']:
                    if container.health in ['healthy', 'unknown']:
                        container_health = 'healthy'
                        healthy_count += 1
                    elif container.health == 'starting':
                        container_health = 'starting'
                    else:
                        container_health = 'unhealthy'
                else:
                    container_health = 'stopped'
                
                health_results['container_health'][container.name] = {
                    'status': container_health,
                    'container_status': container.status,
                    'health_status': container.health
                }
            
            # 計算整體健康狀態
            if total_count == 0:
                health_results['overall_health'] = 'no_containers'
            elif healthy_count == total_count:
                health_results['overall_health'] = 'healthy'
            elif healthy_count > 0:
                health_results['overall_health'] = 'degraded'
            else:
                health_results['overall_health'] = 'unhealthy'
            
            health_results['healthy_containers'] = healthy_count
            health_results['total_containers'] = total_count
            
            # 執行服務特定的健康檢查
            service_checks = await self._perform_service_specific_health_checks(containers)
            health_results['service_health'] = service_checks
            
            return health_results
            
        except Exception as e:
            logger.error(f"健康檢查失敗: {e}")
            health_results['overall_health'] = 'error'
            health_results['error'] = str(e)
            return health_results
    
    async def _perform_service_specific_health_checks(self, containers: List[ContainerInfo]) -> Dict[str, Any]:
        """執行服務特定的健康檢查"""
        service_health = {}
        
        try:
            # 檢查Redis服務
            redis_container = next((c for c in containers if 'redis' in c.name.lower()), None)
            if redis_container:
                redis_health = await self._check_redis_health(redis_container)
                service_health['redis'] = redis_health
            
            # 檢查主應用服務
            app_container = next((c for c in containers if 'discord-bot' in c.name or 'app' in c.name), None)
            if app_container:
                app_health = await self._check_app_health(app_container)
                service_health['discord_bot'] = app_health
            
            # 檢查監控服務（如果有）
            prometheus_container = next((c for c in containers if 'prometheus' in c.name.lower()), None)
            if prometheus_container:
                prometheus_health = await self._check_prometheus_health(prometheus_container)
                service_health['prometheus'] = prometheus_health
            
            return service_health
            
        except Exception as e:
            logger.error(f"服務特定健康檢查失敗: {e}")
            return {'error': str(e)}
    
    async def _check_redis_health(self, container: ContainerInfo) -> Dict[str, Any]:
        """檢查Redis健康狀態"""
        try:
            # 使用docker exec執行redis-cli ping
            cmd = ['docker', 'exec', container.name, 'redis-cli', 'ping']
            result = await self._run_command(cmd, timeout=5)
            
            if result.returncode == 0 and 'PONG' in result.stdout:
                return {
                    'status': 'healthy',
                    'response_time': 'fast',
                    'last_check': datetime.now().isoformat()
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': result.stderr or 'No PONG response',
                    'last_check': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def _check_app_health(self, container: ContainerInfo) -> Dict[str, Any]:
        """檢查主應用健康狀態"""
        try:
            # 檢查容器日誌中的錯誤
            cmd = ['docker', 'logs', '--tail', '50', container.name]
            result = await self._run_command(cmd, timeout=10)
            
            if result.returncode == 0:
                logs = result.stdout.lower()
                
                # 分析日誌中的健康指標
                if 'error' in logs or 'exception' in logs:
                    error_lines = [line for line in result.stdout.split('\n') 
                                 if 'error' in line.lower() or 'exception' in line.lower()]
                    recent_errors = error_lines[-3:] if error_lines else []
                    
                    return {
                        'status': 'degraded',
                        'recent_errors': recent_errors,
                        'last_check': datetime.now().isoformat()
                    }
                elif 'ready' in logs or 'started' in logs:
                    return {
                        'status': 'healthy',
                        'last_check': datetime.now().isoformat()
                    }
                else:
                    return {
                        'status': 'unknown',
                        'last_check': datetime.now().isoformat()
                    }
            else:
                return {
                    'status': 'error',
                    'error': 'Cannot access container logs',
                    'last_check': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def _check_prometheus_health(self, container: ContainerInfo) -> Dict[str, Any]:
        """檢查Prometheus健康狀態"""
        try:
            # 檢查Prometheus健康端點
            cmd = ['docker', 'exec', container.name, 'wget', '-q', '-O-', 'http://localhost:9090/-/healthy']
            result = await self._run_command(cmd, timeout=5)
            
            if result.returncode == 0:
                return {
                    'status': 'healthy',
                    'last_check': datetime.now().isoformat()
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': result.stderr,
                    'last_check': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error', 
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    async def _check_containers_health(self) -> Optional[Dict[str, Any]]:
        """檢查所有容器健康狀態"""
        if not self.deployed_containers:
            return None
        
        healthy_count = 0
        unhealthy_count = 0
        starting_count = 0
        
        for container in self.deployed_containers:
            if container.health == 'healthy' or (container.health == 'unknown' and container.status == 'running'):
                healthy_count += 1
            elif container.health == 'starting':
                starting_count += 1
            else:
                unhealthy_count += 1
        
        return {
            'total_containers': len(self.deployed_containers),
            'healthy_count': healthy_count,
            'unhealthy_count': unhealthy_count,
            'starting_count': starting_count,
            'health_percentage': (healthy_count / len(self.deployed_containers)) * 100
        }
    
    async def _check_resource_usage(self) -> Optional[Dict[str, Any]]:
        """檢查資源使用情況"""
        try:
            if not self.deployed_containers:
                return None
            
            # 使用docker stats獲取資源使用
            container_names = [c.name for c in self.deployed_containers]
            cmd = ['docker', 'stats', '--no-stream', '--format', 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}'] + container_names
            
            result = await self._run_command(cmd, timeout=10)
            
            if result.returncode != 0:
                return None
            
            lines = result.stdout.strip().split('\n')[1:]  # 跳過標題行
            resource_info = {}
            critical_resources = []
            
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 3:
                    container_name = parts[0]
                    cpu_usage = parts[1].replace('%', '')
                    mem_usage = parts[2]
                    
                    try:
                        cpu_percent = float(cpu_usage)
                        if cpu_percent > self.resource_limits['cpu_threshold_percent']:
                            critical_resources.append(f"{container_name}: CPU {cpu_percent}%")
                    except ValueError:
                        pass
                    
                    resource_info[container_name] = {
                        'cpu_usage': parts[1],
                        'memory_usage': mem_usage
                    }
            
            return {
                'containers': resource_info,
                'critical_resources': critical_resources,
                'check_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"檢查資源使用失敗: {e}")
            return None
    
    # ========== 監控和自動恢復 ==========
    
    async def _start_health_monitoring(self) -> None:
        """啟動健康監控"""
        if self.health_check_task and not self.health_check_task.done():
            return
        
        self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
        logger.info("健康監控已啟動")
    
    async def _health_monitoring_loop(self) -> None:
        """健康監控循環"""
        while self.is_initialized and self.monitoring_enabled:
            try:
                if self.current_config and self.current_status in [DockerServiceStatus.RUNNING, DockerServiceStatus.DEGRADED]:
                    # 執行健康檢查
                    health_results = await self._perform_health_checks(self.current_config)
                    self._last_health_check = health_results
                    
                    # 檢查是否需要自動恢復
                    if self.auto_restart_enabled:
                        await self._check_auto_recovery(health_results)
                
                # 等待下次檢查
                await asyncio.sleep(self.current_config.health_check_interval if self.current_config else 30)
                
            except asyncio.CancelledError:
                logger.info("健康監控循環被取消")
                break
            except Exception as e:
                logger.error(f"健康監控循環異常: {e}")
                await asyncio.sleep(30)  # 出錯時等待30秒再重試
    
    async def _check_auto_recovery(self, health_results: Dict[str, Any]) -> None:
        """檢查自動恢復條件"""
        try:
            overall_health = health_results.get('overall_health')
            
            if overall_health == 'unhealthy':
                self._consecutive_failures += 1
                logger.warning(f"檢測到不健康狀態，連續失敗次數: {self._consecutive_failures}")
                
                # 達到重啟閾值
                if (self._consecutive_failures >= self.current_config.max_restart_attempts and 
                    self._restart_count < self.current_config.max_restart_attempts):
                    
                    logger.info("觸發自動重啟恢復...")
                    try:
                        await self.restart_deployment()
                        self._consecutive_failures = 0  # 重置失敗計數
                        logger.info("自動重啟完成")
                    except Exception as e:
                        logger.error(f"自動重啟失敗: {e}")
            
            elif overall_health in ['healthy', 'degraded']:
                # 恢復健康，重置計數器
                if self._consecutive_failures > 0:
                    logger.info("服務已恢復健康，重置失敗計數器")
                    self._consecutive_failures = 0
            
        except Exception as e:
            logger.error(f"自動恢復檢查異常: {e}")
    
    # ========== 配置和驗證 ==========
    
    async def _validate_configuration(self) -> None:
        """驗證配置文件"""
        try:
            # 檢查compose文件是否存在
            if not self.compose_file.exists():
                raise DeploymentError(
                    message=f"Docker Compose文件不存在: {self.compose_file}",
                    deployment_mode="docker"
                )
            
            # 驗證compose文件語法
            cmd = ['docker', 'compose', '-f', str(self.compose_file), 'config']
            result = await self._run_command(cmd, timeout=30)
            
            if result.returncode != 0:
                raise DeploymentError(
                    message=f"Docker Compose文件語法錯誤: {result.stderr}",
                    deployment_mode="docker"
                )
            
            logger.debug("Docker配置文件驗證通過")
            
        except Exception as e:
            if isinstance(e, DeploymentError):
                raise
            else:
                raise DeploymentError(
                    message=f"配置驗證失敗: {str(e)}",
                    deployment_mode="docker"
                )
    
    async def _validate_deployment_config(self, config: DockerDeploymentConfig) -> None:
        """驗證部署配置"""
        try:
            # 檢查環境文件
            if config.env_file:
                env_path = Path(config.env_file)
                if not env_path.exists():
                    raise DeploymentError(
                        message=f"環境文件不存在: {config.env_file}",
                        deployment_mode="docker"
                    )
            
            # 檢查profile是否有效
            result = await self._run_command([
                'docker', 'compose', '-f', str(self.compose_file),
                '--profile', config.profile.value, 'config'
            ], timeout=30)
            
            if result.returncode != 0:
                raise DeploymentError(
                    message=f"無效的profile配置: {config.profile.value}",
                    deployment_mode="docker"
                )
            
            logger.debug("部署配置驗證通過")
            
        except Exception as e:
            if isinstance(e, DeploymentError):
                raise
            else:
                raise DeploymentError(
                    message=f"部署配置驗證失敗: {str(e)}",
                    deployment_mode="docker"
                )
    
    async def _needs_rebuild(self, config: DockerDeploymentConfig) -> bool:
        """檢查是否需要重建"""
        try:
            # 檢查是否有本地構建的映像
            cmd = [
                'docker', 'compose', '-f', str(self.compose_file),
                '--profile', config.profile.value, 'images'
            ]
            
            if config.env_file:
                cmd.extend(['--env-file', config.env_file])
            
            result = await self._run_command(cmd, timeout=30)
            
            # 如果沒有映像或命令失敗，需要構建
            if result.returncode != 0 or not result.stdout.strip():
                return True
            
            # 檢查映像是否過期（簡單檢查）
            # 這裡可以添加更複雜的邏輯來檢查源碼變更
            return False
            
        except Exception as e:
            logger.debug(f"檢查重建需求時出錯: {e}")
            # 出錯時選擇重建以確保安全
            return True
    
    # ========== 日誌和歷史記錄 ==========
    
    async def _get_deployment_logs(self, config: DockerDeploymentConfig) -> List[str]:
        """獲取部署日誌"""
        logs = []
        
        try:
            cmd = [
                'docker', 'compose', '-f', str(self.compose_file),
                '--profile', config.profile.value, 'logs', '--tail', '100'
            ]
            
            if config.env_file:
                cmd.extend(['--env-file', config.env_file])
            
            result = await self._run_command(cmd, timeout=30)
            
            if result.returncode == 0:
                logs = result.stdout.split('\n')[-50:]  # 最近50行
            else:
                logs = [f"獲取日誌失敗: {result.stderr}"]
            
        except Exception as e:
            logs = [f"獲取日誌異常: {str(e)}"]
        
        return logs
    
    async def _record_deployment_history(
        self, 
        config: DockerDeploymentConfig, 
        result: DockerDeploymentResult
    ) -> None:
        """記錄部署歷史"""
        try:
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'profile': config.profile.value,
                'success': result.success,
                'status': result.status.value,
                'deployment_time': result.deployment_time,
                'build_time': result.build_time,
                'start_time': result.start_time,
                'container_count': len(result.containers),
                'error_message': result.error_message,
                'warnings': result.warnings,
                'force_rebuild': config.force_rebuild
            }
            
            self.deployment_history.append(history_entry)
            
            # 限制歷史記錄數量
            if len(self.deployment_history) > 50:
                self.deployment_history = self.deployment_history[-50:]
            
            logger.debug("已記錄部署歷史")
            
        except Exception as e:
            logger.debug(f"記錄部署歷史失敗: {e}")
    
    # ========== 工具方法 ==========
    
    async def _run_command(
        self,
        command: List[str],
        shell: bool = False,
        timeout: int = 30,
        cwd: Optional[str] = None
    ):
        """執行命令的工具方法"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=shell,
                cwd=cwd or str(self.project_root)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return type('Result', (), {
                'returncode': process.returncode,
                'stdout': stdout.decode('utf-8', errors='ignore'),
                'stderr': stderr.decode('utf-8', errors='ignore')
            })()
            
        except asyncio.TimeoutError:
            logger.error(f"命令執行超時: {' '.join(command)}")
            raise
        except Exception as e:
            logger.error(f"命令執行異常: {' '.join(command)}, 錯誤: {e}")
            raise
    
    # ========== 公開API方法 ==========
    
    async def get_deployment_status(self) -> Dict[str, Any]:
        """獲取部署狀態"""
        return {
            'current_status': self.current_status.value,
            'deployed_containers': len(self.deployed_containers),
            'containers': [
                {
                    'name': c.name,
                    'image': c.image,
                    'status': c.status,
                    'health': c.health,
                    'restart_count': c.restart_count
                }
                for c in self.deployed_containers
            ],
            'last_health_check': self._last_health_check,
            'consecutive_failures': self._consecutive_failures,
            'restart_count': self._restart_count,
            'monitoring_enabled': self.monitoring_enabled,
            'auto_restart_enabled': self.auto_restart_enabled
        }
    
    async def get_deployment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取部署歷史"""
        return self.deployment_history[-limit:] if self.deployment_history else []
    
    async def get_container_logs(self, container_name: str, lines: int = 100) -> str:
        """獲取指定容器的日誌"""
        try:
            cmd = ['docker', 'logs', '--tail', str(lines), container_name]
            result = await self._run_command(cmd, timeout=30)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"獲取日誌失敗: {result.stderr}"
                
        except Exception as e:
            return f"獲取日誌異常: {str(e)}"
    
    def set_monitoring_enabled(self, enabled: bool) -> None:
        """設置監控開關"""
        self.monitoring_enabled = enabled
        logger.info(f"健康監控已{'啟用' if enabled else '停用'}")
    
    def set_auto_restart_enabled(self, enabled: bool) -> None:
        """設置自動重啟開關"""
        self.auto_restart_enabled = enabled
        logger.info(f"自動重啟已{'啟用' if enabled else '停用'}")