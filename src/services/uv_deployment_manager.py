"""
UV Python部署管理器
Task ID: 2 - 自動化部署和啟動系統開發

UV Python部署管理器，作為Docker的降級替代方案：
- UV虛擬環境的創建和管理
- Python依賴的自動安裝和更新
- 應用程序的直接啟動和監控
- 本地服務的替代方案（內嵌資料庫、記憶體快取等）
- 跨平台Python環境支援
"""

import asyncio
import json
import logging
import os
import platform
import psutil
import shutil
import signal
import subprocess
import sys
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


logger = logging.getLogger('services.uv_deployment')


class UVServiceStatus(Enum):
    """UV部署服務狀態"""
    NOT_STARTED = "not_started"
    PREPARING = "preparing"
    INSTALLING_DEPS = "installing_dependencies"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DEGRADED = "degraded"


class ServiceMode(Enum):
    """服務運行模式"""
    STANDALONE = "standalone"        # 完全獨立運行
    LOCAL_SERVICES = "local_services"  # 使用本地服務（Redis等）
    EMBEDDED = "embedded"            # 內嵌服務（SQLite、記憶體快取）


@dataclass
class UVEnvironmentConfig:
    """UV環境配置"""
    venv_name: str = "roas-bot-env"
    python_version: Optional[str] = None  # 指定Python版本，None為使用系統Python
    requirements_file: str = "pyproject.toml"
    extra_dependencies: List[str] = field(default_factory=list)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    service_mode: ServiceMode = ServiceMode.EMBEDDED
    enable_dev_dependencies: bool = False
    cache_dir: Optional[str] = None
    index_url: Optional[str] = None
    trusted_host: List[str] = field(default_factory=list)


@dataclass
class ApplicationConfig:
    """應用程序配置"""
    main_module: str = "main.py"
    working_directory: Optional[str] = None
    startup_timeout: int = 60
    shutdown_timeout: int = 30
    auto_restart: bool = True
    max_restart_attempts: int = 3
    restart_delay: int = 5
    health_check_interval: int = 30
    log_level: str = "INFO"
    log_file: Optional[str] = None


@dataclass
class ProcessInfo:
    """進程信息"""
    pid: int
    name: str
    status: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    created_time: Optional[datetime] = None
    command_line: List[str] = field(default_factory=list)


@dataclass
class UVDeploymentResult:
    """UV部署結果"""
    success: bool
    status: UVServiceStatus
    venv_path: Optional[str] = None
    python_path: Optional[str] = None
    installed_packages: List[str] = field(default_factory=list)
    process_info: Optional[ProcessInfo] = None
    deployment_time: float = 0.0
    dependency_install_time: float = 0.0
    startup_time: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    service_endpoints: Dict[str, str] = field(default_factory=dict)


class UVDeploymentManager(BaseService):
    """
    UV Python部署管理器
    
    管理基於UV的Python虛擬環境部署，提供Docker的輕量級替代方案
    """
    
    def __init__(self, project_root: Optional[str] = None):
        super().__init__()
        
        self.service_metadata = {
            'service_type': ServiceType.DEPLOYMENT,
            'service_name': 'uv_deployment_manager',
            'version': '2.4.4',
            'capabilities': {
                'virtual_environment': True,
                'dependency_management': True,
                'process_monitoring': True,
                'embedded_services': True,
                'cross_platform': True,
                'auto_recovery': True
            }
        }
        
        # 路徑配置
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.venv_base_dir = self.project_root / ".venvs"
        self.logs_dir = self.project_root / "logs"
        
        # 服務狀態
        self.current_status = UVServiceStatus.NOT_STARTED
        self.current_env_config: Optional[UVEnvironmentConfig] = None
        self.current_app_config: Optional[ApplicationConfig] = None
        self.current_venv_path: Optional[Path] = None
        self.application_process: Optional[asyncio.subprocess.Process] = None
        self.process_info: Optional[ProcessInfo] = None
        
        # 依賴服務
        self.environment_detector = EnvironmentDetector()
        
        # 監控配置
        self.monitoring_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.monitoring_enabled = True
        self.auto_restart_enabled = True
        
        # 狀態追踪
        self._consecutive_failures = 0
        self._restart_count = 0
        self._last_health_check = None
        self.deployment_history: List[Dict[str, Any]] = []
        
        # 內嵌服務
        self.embedded_services = {
            'redis': None,  # 可以使用fake_redis或記憶體實現
            'database': None  # SQLite路徑
        }
    
    async def start(self) -> None:
        """啟動UV部署管理器"""
        try:
            logger.info("啟動UV部署管理器...")
            
            # 啟動環境檢測服務
            await self.environment_detector.start()
            
            # 檢查Python和UV環境
            await self._verify_uv_environment()
            
            # 創建必要目錄
            self.venv_base_dir.mkdir(exist_ok=True)
            self.logs_dir.mkdir(exist_ok=True)
            
            self.is_initialized = True
            logger.info("UV部署管理器啟動完成")
            
        except Exception as e:
            logger.error(f"UV部署管理器啟動失敗: {e}")
            raise ServiceStartupError(
                service_name='uv_deployment_manager',
                startup_mode='uv_python',
                reason=str(e)
            )
    
    async def stop(self) -> None:
        """停止UV部署管理器"""
        try:
            logger.info("停止UV部署管理器...")
            
            # 停止應用程序
            if self.application_process:
                await self._stop_application()
            
            # 停止監控任務
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            if self.health_check_task and not self.health_check_task.done():
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # 停止環境檢測服務
            await self.environment_detector.stop()
            
            self.is_initialized = False
            logger.info("UV部署管理器已停止")
            
        except Exception as e:
            logger.error(f"停止UV部署管理器失敗: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 檢查UV環境
            uv_available = await self._is_uv_available()
            python_available = await self._is_python_available()
            
            # 檢查應用程序狀態
            app_running = await self._is_application_running()
            
            # 檢查虛擬環境
            venv_healthy = await self._check_venv_health()
            
            # 檢查進程資源使用
            resource_status = await self._check_process_resources()
            
            # 綜合健康狀態
            overall_health = "healthy"
            issues = []
            
            if not uv_available:
                overall_health = "degraded"
                issues.append("UV不可用")
            
            if not python_available:
                overall_health = "degraded"
                issues.append("Python不可用")
            
            if not app_running and self.current_status == UVServiceStatus.RUNNING:
                overall_health = "degraded"
                issues.append("應用程序未運行")
            
            if not venv_healthy:
                overall_health = "degraded"
                issues.append("虛擬環境不健康")
            
            return {
                'service_name': 'uv_deployment_manager',
                'status': overall_health,
                'current_deployment_status': self.current_status.value,
                'uv_available': uv_available,
                'python_available': python_available,
                'application_running': app_running,
                'venv_healthy': venv_healthy,
                'venv_path': str(self.current_venv_path) if self.current_venv_path else None,
                'process_info': self.process_info.__dict__ if self.process_info else None,
                'resource_status': resource_status,
                'issues': issues,
                'consecutive_failures': self._consecutive_failures,
                'restart_count': self._restart_count,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"UV部署管理器健康檢查失敗: {e}")
            return {
                'service_name': 'uv_deployment_manager',
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    # ========== 部署管理方法 ==========
    
    async def deploy(
        self,
        env_config: Optional[UVEnvironmentConfig] = None,
        app_config: Optional[ApplicationConfig] = None
    ) -> UVDeploymentResult:
        """
        執行UV Python部署
        
        Args:
            env_config: 環境配置
            app_config: 應用配置
        """
        if not env_config:
            env_config = UVEnvironmentConfig()
        if not app_config:
            app_config = ApplicationConfig()
        
        logger.info(f"開始UV Python部署，模式: {env_config.service_mode.value}")
        
        start_time = datetime.now()
        result = UVDeploymentResult(
            success=False,
            status=UVServiceStatus.NOT_STARTED
        )
        
        try:
            # 更新當前配置
            self.current_env_config = env_config
            self.current_app_config = app_config
            
            # 1. 環境檢查和準備
            logger.info("檢查UV和Python環境...")
            self.current_status = UVServiceStatus.PREPARING
            
            await self._ensure_uv_ready()
            
            # 2. 創建或更新虛擬環境
            logger.info("準備虛擬環境...")
            venv_path = await self._setup_virtual_environment(env_config)
            result.venv_path = str(venv_path)
            result.python_path = str(venv_path / "bin" / "python" if platform.system() != "Windows" 
                                   else venv_path / "Scripts" / "python.exe")
            
            # 3. 安裝依賴
            logger.info("安裝Python依賴...")
            self.current_status = UVServiceStatus.INSTALLING_DEPS
            
            deps_start = datetime.now()
            installed_packages = await self._install_dependencies(venv_path, env_config)
            result.dependency_install_time = (datetime.now() - deps_start).total_seconds()
            result.installed_packages = installed_packages
            
            # 4. 設置內嵌服務（如果需要）
            if env_config.service_mode == ServiceMode.EMBEDDED:
                logger.info("設置內嵌服務...")
                await self._setup_embedded_services(env_config)
                result.service_endpoints = await self._get_service_endpoints()
            
            # 5. 停止現有應用（如果運行中）
            if self.application_process:
                logger.info("停止現有應用程序...")
                await self._stop_application()
            
            # 6. 啟動應用程序
            logger.info("啟動應用程序...")
            self.current_status = UVServiceStatus.STARTING
            
            app_start = datetime.now()
            process = await self._start_application(venv_path, app_config)
            result.startup_time = (datetime.now() - app_start).total_seconds()
            
            self.application_process = process
            
            # 7. 等待應用就緒
            logger.info("等待應用程序就緒...")
            await self._wait_for_application_ready(app_config)
            
            # 8. 收集進程信息
            self.process_info = await self._get_process_info()
            result.process_info = self.process_info
            
            # 9. 啟動監控
            if self.monitoring_enabled:
                await self._start_monitoring()
            
            # 計算總部署時間
            result.deployment_time = (datetime.now() - start_time).total_seconds()
            
            # 檢查部署成功
            if await self._is_application_running():
                result.success = True
                result.status = UVServiceStatus.RUNNING
                self.current_status = UVServiceStatus.RUNNING
                logger.info(f"UV Python部署成功，PID: {process.pid if process else 'unknown'}")
            else:
                result.status = UVServiceStatus.FAILED
                self.current_status = UVServiceStatus.FAILED
                result.error_message = "應用程序啟動後未能正常運行"
                logger.error("應用程序啟動後未能正常運行")
            
            # 記錄部署歷史
            await self._record_deployment_history(env_config, app_config, result)
            
            return result
            
        except Exception as e:
            # 部署失敗處理
            result.success = False
            result.status = UVServiceStatus.FAILED
            result.error_message = str(e)
            result.deployment_time = (datetime.now() - start_time).total_seconds()
            
            self.current_status = UVServiceStatus.FAILED
            self._consecutive_failures += 1
            
            logger.error(f"UV Python部署失敗: {e}")
            
            # 嘗試收集失敗日誌
            try:
                result.logs = await self._get_application_logs()
            except Exception as log_error:
                logger.debug(f"收集失敗日誌時出錯: {log_error}")
            
            # 記錄失敗歷史
            await self._record_deployment_history(env_config, app_config, result)
            
            # 重新拋出部署異常
            raise DeploymentError(
                message=f"UV Python部署失敗: {str(e)}",
                deployment_mode="uv_python",
                details=result.__dict__
            )
    
    async def stop_deployment(self, force: bool = False) -> bool:
        """
        停止當前部署
        
        Args:
            force: 是否強制停止
        """
        logger.info(f"停止UV Python部署，強制模式: {force}")
        
        try:
            self.current_status = UVServiceStatus.STOPPING
            
            # 停止監控
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
            
            # 停止應用程序
            if self.application_process:
                success = await self._stop_application(force)
                
                if success:
                    self.current_status = UVServiceStatus.STOPPED
                    self.application_process = None
                    self.process_info = None
                    logger.info("UV Python部署已停止")
                    return True
                else:
                    self.current_status = UVServiceStatus.FAILED
                    logger.error("停止UV Python部署失敗")
                    return False
            else:
                self.current_status = UVServiceStatus.STOPPED
                logger.info("沒有運行中的應用程序")
                return True
                
        except Exception as e:
            logger.error(f"停止UV Python部署異常: {e}")
            self.current_status = UVServiceStatus.FAILED
            return False
    
    async def restart_deployment(self, reinstall_deps: bool = False) -> UVDeploymentResult:
        """
        重啟部署
        
        Args:
            reinstall_deps: 是否重新安裝依賴
        """
        logger.info(f"重啟UV Python部署，重裝依賴: {reinstall_deps}")
        
        try:
            self._restart_count += 1
            
            # 先停止現有部署
            await self.stop_deployment()
            
            # 等待清理完成
            await asyncio.sleep(2)
            
            # 準備配置
            env_config = self.current_env_config or UVEnvironmentConfig()
            app_config = self.current_app_config or ApplicationConfig()
            
            # 如果需要重裝依賴，清除現有虛擬環境
            if reinstall_deps and self.current_venv_path and self.current_venv_path.exists():
                logger.info("清除現有虛擬環境...")
                shutil.rmtree(self.current_venv_path)
            
            # 重新部署
            return await self.deploy(env_config, app_config)
            
        except Exception as e:
            logger.error(f"重啟UV Python部署失敗: {e}")
            self.current_status = UVServiceStatus.FAILED
            raise
    
    # ========== UV環境管理 ==========
    
    async def install_uv(self, force: bool = False) -> InstallationResult:
        """
        自動安裝UV
        
        Args:
            force: 是否強制重新安裝
        """
        logger.info(f"開始安裝UV，強制模式: {force}")
        
        try:
            result = await self.environment_detector.auto_install_environment(
                EnvironmentType.UV_PYTHON,
                force=force
            )
            
            if result.success:
                logger.info(f"UV安裝成功，版本: {result.version_installed}")
                
                # 執行後續配置
                await self._post_uv_installation_setup()
            else:
                logger.error(f"UV安裝失敗: {result.error_message}")
            
            return result
            
        except Exception as e:
            logger.error(f"UV安裝異常: {e}")
            return InstallationResult(
                success=False,
                environment=EnvironmentType.UV_PYTHON,
                error_message=str(e)
            )
    
    async def _post_uv_installation_setup(self) -> None:
        """UV安裝後的設置"""
        try:
            # 測試UV安裝
            result = await self._run_command(['uv', '--version'])
            if result.returncode == 0:
                logger.info(f"UV安裝測試成功: {result.stdout.strip()}")
                
                # 設置UV配置（如果需要）
                await self._configure_uv_settings()
            else:
                logger.warning("UV安裝測試失敗")
                
        except Exception as e:
            logger.warning(f"UV後續設置失敗: {e}")
    
    async def _configure_uv_settings(self) -> None:
        """配置UV設置"""
        try:
            # 可以在這裡設置UV的全局配置
            # 例如：設置鏡像源、快取目錄等
            logger.debug("UV配置設置完成")
        except Exception as e:
            logger.debug(f"UV配置設置失敗: {e}")
    
    async def _verify_uv_environment(self) -> None:
        """驗證UV環境"""
        try:
            # 檢查UV
            uv_result = await self.environment_detector.detect_uv()
            if uv_result.status != EnvironmentStatus.AVAILABLE:
                logger.warning(f"UV環境不可用: {uv_result.status.value}")
            
            # 檢查Python
            python_result = await self.environment_detector.detect_python()
            if python_result.status != EnvironmentStatus.AVAILABLE:
                raise DeploymentError(
                    message=f"Python環境不可用: {python_result.status.value}",
                    deployment_mode="uv_python"
                )
            
            logger.debug("UV環境驗證完成")
            
        except Exception as e:
            if isinstance(e, DeploymentError):
                raise
            else:
                raise DeploymentError(
                    message=f"UV環境驗證失敗: {str(e)}",
                    deployment_mode="uv_python"
                )
    
    async def _ensure_uv_ready(self) -> None:
        """確保UV環境就緒"""
        try:
            # 檢查UV是否可用
            if not await self._is_uv_available():
                logger.info("UV不可用，嘗試自動安裝...")
                
                install_result = await self.install_uv()
                if not install_result.success:
                    raise DeploymentError(
                        message="UV安裝失敗",
                        deployment_mode="uv_python"
                    )
            
            # 檢查Python
            if not await self._is_python_available():
                raise DeploymentError(
                    message="Python不可用",
                    deployment_mode="uv_python"
                )
            
        except Exception as e:
            if isinstance(e, DeploymentError):
                raise
            else:
                raise DeploymentError(
                    message=f"UV環境準備失敗: {str(e)}",
                    deployment_mode="uv_python"
                )
    
    async def _is_uv_available(self) -> bool:
        """檢查UV是否可用"""
        try:
            result = await self._run_command(['uv', '--version'])
            return result.returncode == 0
        except Exception:
            return False
    
    async def _is_python_available(self) -> bool:
        """檢查Python是否可用"""
        try:
            result = await self._run_command([sys.executable, '--version'])
            return result.returncode == 0
        except Exception:
            return False
    
    # ========== 虛擬環境管理 ==========
    
    async def _setup_virtual_environment(self, config: UVEnvironmentConfig) -> Path:
        """設置虛擬環境"""
        try:
            venv_path = self.venv_base_dir / config.venv_name
            self.current_venv_path = venv_path
            
            # 檢查虛擬環境是否已存在
            if venv_path.exists():
                logger.info(f"虛擬環境已存在: {venv_path}")
                
                # 檢查虛擬環境健康狀態
                if await self._check_venv_health():
                    logger.info("現有虛擬環境健康，重複使用")
                    return venv_path
                else:
                    logger.info("現有虛擬環境不健康，重新創建")
                    shutil.rmtree(venv_path)
            
            # 創建新虛擬環境
            logger.info(f"創建虛擬環境: {venv_path}")
            
            cmd = ['uv', 'venv', str(venv_path)]
            
            # 指定Python版本（如果需要）
            if config.python_version:
                cmd.extend(['--python', config.python_version])
            
            result = await self._run_command(cmd)
            
            if result.returncode != 0:
                raise DeploymentError(
                    message=f"創建虛擬環境失敗: {result.stderr}",
                    deployment_mode="uv_python"
                )
            
            logger.info(f"虛擬環境創建成功: {venv_path}")
            return venv_path
            
        except Exception as e:
            if isinstance(e, DeploymentError):
                raise
            else:
                raise DeploymentError(
                    message=f"設置虛擬環境失敗: {str(e)}",
                    deployment_mode="uv_python"
                )
    
    async def _check_venv_health(self) -> bool:
        """檢查虛擬環境健康狀態"""
        try:
            if not self.current_venv_path or not self.current_venv_path.exists():
                return False
            
            # 檢查Python解釋器是否可用
            python_exe = self._get_venv_python_path(self.current_venv_path)
            
            if not python_exe.exists():
                return False
            
            # 測試Python解釋器
            result = await self._run_command([str(python_exe), '--version'])
            
            return result.returncode == 0
            
        except Exception as e:
            logger.debug(f"檢查虛擬環境健康狀態失敗: {e}")
            return False
    
    def _get_venv_python_path(self, venv_path: Path) -> Path:
        """獲取虛擬環境中的Python路徑"""
        if platform.system() == "Windows":
            return venv_path / "Scripts" / "python.exe"
        else:
            return venv_path / "bin" / "python"
    
    def _get_venv_pip_path(self, venv_path: Path) -> Path:
        """獲取虛擬環境中的pip路徑"""
        if platform.system() == "Windows":
            return venv_path / "Scripts" / "pip.exe"
        else:
            return venv_path / "bin" / "pip"
    
    # ========== 依賴管理 ==========
    
    async def _install_dependencies(self, venv_path: Path, config: UVEnvironmentConfig) -> List[str]:
        """安裝依賴"""
        try:
            python_exe = self._get_venv_python_path(venv_path)
            installed_packages = []
            
            # 設置環境變數
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = str(venv_path)
            env['PATH'] = f"{venv_path / 'bin' if platform.system() != 'Windows' else venv_path / 'Scripts'}{os.pathsep}{env['PATH']}"
            
            # 1. 升級pip和基礎工具
            logger.info("升級pip和基礎工具...")
            upgrade_cmd = [str(python_exe), '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel']
            result = await self._run_command(upgrade_cmd, env=env)
            
            if result.returncode != 0:
                logger.warning(f"升級基礎工具失敗: {result.stderr}")
            
            # 2. 安裝主要依賴
            if Path(config.requirements_file).exists():
                logger.info(f"安裝主要依賴: {config.requirements_file}")
                
                if config.requirements_file.endswith('.toml'):
                    # 使用UV安裝pyproject.toml
                    install_cmd = ['uv', 'pip', 'install', '-r', config.requirements_file]
                    if config.enable_dev_dependencies:
                        install_cmd.extend(['--dev'])
                else:
                    # 使用pip安裝requirements.txt
                    install_cmd = [str(python_exe), '-m', 'pip', 'install', '-r', config.requirements_file]
                
                # 添加索引URL（如果指定）
                if config.index_url:
                    install_cmd.extend(['-i', config.index_url])
                
                # 添加信任的主機
                for host in config.trusted_host:
                    install_cmd.extend(['--trusted-host', host])
                
                result = await self._run_command(install_cmd, env=env, timeout=600)  # 10分鐘超時
                
                if result.returncode != 0:
                    raise DependencyInstallError(
                        dependency_name=config.requirements_file,
                        install_method="uv/pip",
                        reason=f"依賴安裝失敗: {result.stderr}"
                    )
            
            # 3. 安裝額外依賴
            if config.extra_dependencies:
                logger.info(f"安裝額外依賴: {config.extra_dependencies}")
                
                install_cmd = ['uv', 'pip', 'install'] + config.extra_dependencies
                
                if config.index_url:
                    install_cmd.extend(['-i', config.index_url])
                
                result = await self._run_command(install_cmd, env=env, timeout=300)
                
                if result.returncode != 0:
                    logger.warning(f"部分額外依賴安裝失敗: {result.stderr}")
            
            # 4. 獲取已安裝包列表
            logger.info("獲取已安裝包列表...")
            list_cmd = [str(python_exe), '-m', 'pip', 'list', '--format=json']
            result = await self._run_command(list_cmd, env=env)
            
            if result.returncode == 0:
                try:
                    packages_data = json.loads(result.stdout)
                    installed_packages = [f"{pkg['name']}=={pkg['version']}" for pkg in packages_data]
                except json.JSONDecodeError:
                    logger.debug("解析已安裝包列表失敗")
            
            logger.info(f"依賴安裝完成，總計 {len(installed_packages)} 個包")
            return installed_packages
            
        except Exception as e:
            if isinstance(e, DependencyInstallError):
                raise
            else:
                raise DependencyInstallError(
                    dependency_name="all_dependencies",
                    install_method="uv/pip",
                    reason=f"依賴安裝異常: {str(e)}"
                )
    
    # ========== 內嵌服務管理 ==========
    
    async def _setup_embedded_services(self, config: UVEnvironmentConfig) -> None:
        """設置內嵌服務"""
        try:
            if config.service_mode == ServiceMode.EMBEDDED:
                logger.info("設置內嵌服務...")
                
                # 設置SQLite資料庫
                await self._setup_embedded_database()
                
                # 設置記憶體快取（替代Redis）
                await self._setup_embedded_cache()
                
                logger.info("內嵌服務設置完成")
            
        except Exception as e:
            logger.warning(f"設置內嵌服務失敗: {e}")
    
    async def _setup_embedded_database(self) -> None:
        """設置內嵌資料庫（SQLite）"""
        try:
            db_dir = self.project_root / "data"
            db_dir.mkdir(exist_ok=True)
            
            db_path = db_dir / "discord_data.db"
            self.embedded_services['database'] = str(db_path)
            
            # 設置環境變數
            os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
            
            logger.debug(f"內嵌資料庫設置: {db_path}")
            
        except Exception as e:
            logger.warning(f"設置內嵌資料庫失敗: {e}")
    
    async def _setup_embedded_cache(self) -> None:
        """設置內嵌快取（記憶體替代Redis）"""
        try:
            # 在環境變數中設置使用記憶體快取
            os.environ['REDIS_URL'] = "memory://"
            os.environ['USE_EMBEDDED_CACHE'] = "true"
            
            logger.debug("內嵌快取設置完成")
            
        except Exception as e:
            logger.warning(f"設置內嵌快取失敗: {e}")
    
    async def _get_service_endpoints(self) -> Dict[str, str]:
        """獲取服務端點"""
        endpoints = {}
        
        try:
            if self.embedded_services.get('database'):
                endpoints['database'] = self.embedded_services['database']
            
            endpoints['cache'] = "embedded_memory_cache"
            
            return endpoints
            
        except Exception as e:
            logger.debug(f"獲取服務端點失敗: {e}")
            return {}
    
    # ========== 應用程序管理 ==========
    
    async def _start_application(
        self, 
        venv_path: Path, 
        config: ApplicationConfig
    ) -> asyncio.subprocess.Process:
        """啟動應用程序"""
        try:
            python_exe = self._get_venv_python_path(venv_path)
            working_dir = Path(config.working_directory) if config.working_directory else self.project_root
            
            # 準備命令
            cmd = [str(python_exe), config.main_module]
            
            # 準備環境變數
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = str(venv_path)
            env['PATH'] = f"{venv_path / 'bin' if platform.system() != 'Windows' else venv_path / 'Scripts'}{os.pathsep}{env['PATH']}"
            env['LOG_LEVEL'] = config.log_level
            
            # 添加用戶自定義環境變數
            if self.current_env_config:
                env.update(self.current_env_config.environment_variables)
            
            # 設置日誌文件
            log_file = None
            if config.log_file:
                log_file = open(config.log_file, 'w')
            
            # 啟動進程
            logger.info(f"啟動應用程序: {' '.join(cmd)}")
            logger.debug(f"工作目錄: {working_dir}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(working_dir),
                env=env,
                stdout=log_file or asyncio.subprocess.PIPE,
                stderr=log_file or asyncio.subprocess.STDOUT,
                start_new_session=True
            )
            
            logger.info(f"應用程序啟動成功，PID: {process.pid}")
            return process
            
        except Exception as e:
            raise ServiceStartupError(
                service_name='discord_bot_app',
                startup_mode='uv_python',
                reason=f"啟動應用程序失敗: {str(e)}"
            )
    
    async def _stop_application(self, force: bool = False) -> bool:
        """停止應用程序"""
        try:
            if not self.application_process:
                return True
            
            logger.info(f"停止應用程序，PID: {self.application_process.pid}")
            
            if force:
                # 強制終止
                self.application_process.terminate()
                try:
                    await asyncio.wait_for(self.application_process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.application_process.kill()
                    await self.application_process.wait()
            else:
                # 優雅停止
                self.application_process.terminate()
                
                try:
                    await asyncio.wait_for(
                        self.application_process.wait(), 
                        timeout=self.current_app_config.shutdown_timeout if self.current_app_config else 30
                    )
                except asyncio.TimeoutError:
                    logger.warning("優雅停止超時，強制終止進程")
                    self.application_process.kill()
                    await self.application_process.wait()
            
            logger.info("應用程序已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止應用程序失敗: {e}")
            return False
    
    async def _wait_for_application_ready(self, config: ApplicationConfig) -> None:
        """等待應用程序就緒"""
        logger.info("等待應用程序就緒...")
        
        max_wait_time = config.startup_timeout
        check_interval = 2
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                # 檢查進程是否還在運行
                if self.application_process and self.application_process.returncode is not None:
                    raise ServiceStartupError(
                        service_name='discord_bot_app',
                        startup_mode='uv_python',
                        reason=f"應用程序意外退出，退出碼: {self.application_process.returncode}"
                    )
                
                # 檢查應用程序是否響應
                if await self._is_application_responsive():
                    logger.info("應用程序已就緒")
                    return
                
            except Exception as e:
                logger.debug(f"檢查應用狀態時出錯: {e}")
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        logger.warning(f"等待應用程序就緒超時 ({max_wait_time}秒)")
    
    async def _is_application_running(self) -> bool:
        """檢查應用程序是否運行"""
        try:
            if not self.application_process:
                return False
            
            # 檢查進程是否還存在
            return self.application_process.returncode is None
            
        except Exception as e:
            logger.debug(f"檢查應用程序運行狀態失敗: {e}")
            return False
    
    async def _is_application_responsive(self) -> bool:
        """檢查應用程序是否響應"""
        try:
            # 這裡可以實現更具體的應用健康檢查
            # 例如：檢查HTTP端點、檢查日誌文件等
            
            # 簡單檢查：進程是否還在運行
            return await self._is_application_running()
            
        except Exception as e:
            logger.debug(f"檢查應用程序響應性失敗: {e}")
            return False
    
    # ========== 進程監控 ==========
    
    async def _get_process_info(self) -> Optional[ProcessInfo]:
        """獲取進程信息"""
        try:
            if not self.application_process:
                return None
            
            pid = self.application_process.pid
            
            try:
                process = psutil.Process(pid)
                
                return ProcessInfo(
                    pid=pid,
                    name=process.name(),
                    status=process.status(),
                    cpu_percent=process.cpu_percent(),
                    memory_mb=process.memory_info().rss / 1024 / 1024,
                    created_time=datetime.fromtimestamp(process.create_time()),
                    command_line=process.cmdline()
                )
            except psutil.NoSuchProcess:
                return None
            
        except Exception as e:
            logger.debug(f"獲取進程信息失敗: {e}")
            return None
    
    async def _check_process_resources(self) -> Optional[Dict[str, Any]]:
        """檢查進程資源使用"""
        try:
            if not self.process_info:
                return None
            
            pid = self.process_info.pid
            
            try:
                process = psutil.Process(pid)
                
                cpu_percent = process.cpu_percent(interval=1)
                memory_info = process.memory_info()
                
                return {
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory_info.rss / 1024 / 1024,
                    'memory_percent': process.memory_percent(),
                    'open_files': len(process.open_files()),
                    'connections': len(process.connections()),
                    'status': process.status(),
                    'check_time': datetime.now().isoformat()
                }
            except psutil.NoSuchProcess:
                return {'status': 'not_found'}
            
        except Exception as e:
            logger.debug(f"檢查進程資源失敗: {e}")
            return None
    
    async def _start_monitoring(self) -> None:
        """啟動監控"""
        if self.monitoring_task and not self.monitoring_task.done():
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("應用程序監控已啟動")
    
    async def _monitoring_loop(self) -> None:
        """監控循環"""
        while self.is_initialized and self.monitoring_enabled:
            try:
                if self.current_status == UVServiceStatus.RUNNING:
                    # 更新進程信息
                    self.process_info = await self._get_process_info()
                    
                    # 檢查進程是否還在運行
                    if not await self._is_application_running():
                        logger.warning("檢測到應用程序意外停止")
                        self._consecutive_failures += 1
                        
                        # 觸發自動重啟（如果啟用）
                        if (self.auto_restart_enabled and 
                            self._consecutive_failures <= (self.current_app_config.max_restart_attempts if self.current_app_config else 3)):
                            
                            logger.info("觸發自動重啟...")
                            try:
                                await asyncio.sleep(self.current_app_config.restart_delay if self.current_app_config else 5)
                                await self.restart_deployment()
                                self._consecutive_failures = 0
                            except Exception as e:
                                logger.error(f"自動重啟失敗: {e}")
                        else:
                            self.current_status = UVServiceStatus.FAILED
                    else:
                        # 應用程序正常運行，重置失敗計數
                        if self._consecutive_failures > 0:
                            logger.info("應用程序恢復正常，重置失敗計數")
                            self._consecutive_failures = 0
                
                # 等待下次檢查
                await asyncio.sleep(self.current_app_config.health_check_interval if self.current_app_config else 30)
                
            except asyncio.CancelledError:
                logger.info("監控循環被取消")
                break
            except Exception as e:
                logger.error(f"監控循環異常: {e}")
                await asyncio.sleep(30)
    
    # ========== 日誌和歷史 ==========
    
    async def _get_application_logs(self, lines: int = 100) -> List[str]:
        """獲取應用程序日誌"""
        logs = []
        
        try:
            # 如果有日誌文件，從文件讀取
            if self.current_app_config and self.current_app_config.log_file:
                log_path = Path(self.current_app_config.log_file)
                if log_path.exists():
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        logs = f.readlines()[-lines:]
                    logs = [line.strip() for line in logs]
            
            # 否則嘗試從進程輸出讀取
            # 注意：這在實際應用中可能需要更複雜的日誌管理
            
        except Exception as e:
            logs = [f"獲取日誌失敗: {str(e)}"]
        
        return logs
    
    async def _record_deployment_history(
        self,
        env_config: UVEnvironmentConfig,
        app_config: ApplicationConfig,
        result: UVDeploymentResult
    ) -> None:
        """記錄部署歷史"""
        try:
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'success': result.success,
                'status': result.status.value,
                'service_mode': env_config.service_mode.value,
                'venv_name': env_config.venv_name,
                'deployment_time': result.deployment_time,
                'dependency_install_time': result.dependency_install_time,
                'startup_time': result.startup_time,
                'installed_packages_count': len(result.installed_packages),
                'process_pid': result.process_info.pid if result.process_info else None,
                'error_message': result.error_message,
                'warnings': result.warnings
            }
            
            self.deployment_history.append(history_entry)
            
            # 限制歷史記錄數量
            if len(self.deployment_history) > 30:
                self.deployment_history = self.deployment_history[-30:]
            
            logger.debug("已記錄部署歷史")
            
        except Exception as e:
            logger.debug(f"記錄部署歷史失敗: {e}")
    
    # ========== 工具方法 ==========
    
    async def _run_command(
        self,
        command: List[str],
        shell: bool = False,
        timeout: int = 30,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ):
        """執行命令"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=shell,
                cwd=cwd or str(self.project_root),
                env=env
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
            'venv_path': str(self.current_venv_path) if self.current_venv_path else None,
            'process_info': self.process_info.__dict__ if self.process_info else None,
            'service_mode': self.current_env_config.service_mode.value if self.current_env_config else None,
            'embedded_services': self.embedded_services,
            'consecutive_failures': self._consecutive_failures,
            'restart_count': self._restart_count,
            'monitoring_enabled': self.monitoring_enabled,
            'auto_restart_enabled': self.auto_restart_enabled,
            'is_application_running': await self._is_application_running()
        }
    
    async def get_deployment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取部署歷史"""
        return self.deployment_history[-limit:] if self.deployment_history else []
    
    async def get_application_logs(self, lines: int = 100) -> List[str]:
        """獲取應用程序日誌"""
        return await self._get_application_logs(lines)
    
    async def get_installed_packages(self) -> List[str]:
        """獲取已安裝的包列表"""
        try:
            if not self.current_venv_path:
                return []
            
            python_exe = self._get_venv_python_path(self.current_venv_path)
            
            cmd = [str(python_exe), '-m', 'pip', 'list', '--format=json']
            result = await self._run_command(cmd)
            
            if result.returncode == 0:
                packages_data = json.loads(result.stdout)
                return [f"{pkg['name']}=={pkg['version']}" for pkg in packages_data]
            else:
                return []
                
        except Exception as e:
            logger.error(f"獲取已安裝包失敗: {e}")
            return []
    
    def set_monitoring_enabled(self, enabled: bool) -> None:
        """設置監控開關"""
        self.monitoring_enabled = enabled
        logger.info(f"應用程序監控已{'啟用' if enabled else '停用'}")
    
    def set_auto_restart_enabled(self, enabled: bool) -> None:
        """設置自動重啟開關"""
        self.auto_restart_enabled = enabled
        logger.info(f"自動重啟已{'啟用' if enabled else '停用'}")