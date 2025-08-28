"""
自動化部署和啟動系統 - 部署服務
Task ID: 2 - 自動化部署和啟動系統開發

Noah Chen - 基礎設施專家
這個模組實作完整的自動化部署和啟動系統，包括：
- 環境檢測器(EnvironmentDetector)
- Docker部署管理器(DockerDeploymentManager)
- UV部署管理器(UVDeploymentManager)
- 部署協調器(DeploymentOrchestrator)
- 部署監控和日誌系統(DeploymentMonitor)
"""

import asyncio
import logging
import os
import platform
import subprocess
import shutil
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# 導入現有的核心模組
from core.base_service import BaseService, ServiceType
from src.core.errors import (
    DeploymentError, EnvironmentError, DependencyInstallError, 
    ServiceStartupError, ConfigurationError
)
from src.core.config import AppConfig, get_config
from src.core.service_registry import extended_service_registry


logger = logging.getLogger('deployment_service')


class DeploymentMode(Enum):
    """部署模式枚舉"""
    DOCKER = "docker"
    UV_PYTHON = "uv"
    FALLBACK = "fallback"
    AUTO = "auto"


class DeploymentStatus(Enum):
    """部署狀態枚舉"""
    PENDING = "pending"
    INSTALLING = "installing"
    CONFIGURING = "configuring"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    DEGRADED = "degraded"
    STOPPED = "stopped"


class SystemPlatform(Enum):
    """系統平台枚舉"""
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


@dataclass
class EnvironmentInfo:
    """環境資訊數據類"""
    platform: SystemPlatform
    architecture: str
    python_version: Optional[str] = None
    docker_available: bool = False
    docker_version: Optional[str] = None
    uv_available: bool = False
    uv_version: Optional[str] = None
    package_manager: Optional[str] = None
    sudo_available: bool = False
    permissions: Dict[str, bool] = field(default_factory=dict)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class DeploymentResult:
    """部署結果數據類"""
    mode: DeploymentMode
    status: DeploymentStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: Optional[timedelta] = None
    error_logs: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)


class DeploymentManager(ABC):
    """部署管理器基礎抽象類"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
    
    @abstractmethod
    async def check_dependencies(self) -> bool:
        """檢查依賴是否可用"""
        pass
    
    @abstractmethod
    async def install_dependencies(self) -> bool:
        """安裝依賴"""
        pass
    
    @abstractmethod
    async def start_services(self) -> bool:
        """啟動服務"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        pass
    
    @abstractmethod
    async def stop_services(self) -> bool:
        """停止服務"""
        pass


class EnvironmentDetector:
    """
    智能環境檢測器
    
    負責檢測系統環境、依賴可用性、權限狀態等
    支援Linux、macOS、Windows跨平台檢測
    """
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger('EnvironmentDetector')
        self._cache: Optional[EnvironmentInfo] = None
        self._cache_ttl = timedelta(minutes=5)
        
    async def detect_all_environments(self, force_refresh: bool = False) -> EnvironmentInfo:
        """
        檢測所有環境資訊
        
        Args:
            force_refresh: 是否強制重新檢測
            
        Returns:
            EnvironmentInfo: 完整的環境資訊
        """
        # 檢查快取
        if not force_refresh and self._cache:
            if datetime.now() - self._cache.detected_at < self._cache_ttl:
                self.logger.debug("使用快取的環境檢測結果")
                return self._cache
        
        try:
            self.logger.info("開始環境檢測...")
            
            # 檢測系統平台和架構
            platform_info = await self._detect_platform()
            
            # 檢測Python環境
            python_info = await self._detect_python()
            
            # 檢測Docker環境
            docker_info = await self._detect_docker()
            
            # 檢測UV環境
            uv_info = await self._detect_uv()
            
            # 檢測包管理器
            package_manager = await self._detect_package_manager(platform_info)
            
            # 檢測權限
            permissions = await self._check_permissions()
            
            # 收集環境變數
            env_vars = await self._collect_relevant_env_vars()
            
            # 構建環境資訊
            env_info = EnvironmentInfo(
                platform=platform_info['platform'],
                architecture=platform_info['architecture'],
                python_version=python_info.get('version'),
                docker_available=docker_info['available'],
                docker_version=docker_info.get('version'),
                uv_available=uv_info['available'],
                uv_version=uv_info.get('version'),
                package_manager=package_manager,
                sudo_available=permissions.get('sudo', False),
                permissions=permissions,
                environment_variables=env_vars,
                detected_at=datetime.now()
            )
            
            # 更新快取
            self._cache = env_info
            
            self.logger.info(f"環境檢測完成: {env_info.platform.value}, Python: {env_info.python_version}, "
                           f"Docker: {env_info.docker_available}, UV: {env_info.uv_available}")
            
            return env_info
            
        except Exception as e:
            self.logger.error(f"環境檢測失敗: {e}")
            raise EnvironmentError(
                environment_type="all",
                check_failed="complete_detection",
                details={"error": str(e)},
                cause=e
            )
    
    async def _detect_platform(self) -> Dict[str, Any]:
        """檢測系統平台"""
        try:
            system = platform.system().lower()
            architecture = platform.machine().lower()
            
            if system == 'linux':
                platform_type = SystemPlatform.LINUX
            elif system == 'darwin':
                platform_type = SystemPlatform.MACOS
            elif system == 'windows':
                platform_type = SystemPlatform.WINDOWS
            else:
                platform_type = SystemPlatform.UNKNOWN
                
            return {
                'platform': platform_type,
                'architecture': architecture,
                'system_info': {
                    'system': system,
                    'release': platform.release(),
                    'version': platform.version(),
                    'machine': platform.machine(),
                    'processor': platform.processor()
                }
            }
            
        except Exception as e:
            raise EnvironmentError(
                environment_type="platform",
                check_failed="platform_detection",
                details={"error": str(e)},
                cause=e
            )
    
    async def _detect_python(self) -> Dict[str, Any]:
        """檢測Python環境"""
        try:
            import sys
            
            python_info = {
                'available': True,
                'version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'executable': sys.executable,
                'path': sys.path[:3],  # 只取前3個路徑避免日誌過長
                'version_info': {
                    'major': sys.version_info.major,
                    'minor': sys.version_info.minor,
                    'micro': sys.version_info.micro
                }
            }
            
            # 檢查Python版本是否符合要求
            if sys.version_info < (3, 9):
                python_info['warning'] = f"Python版本 {python_info['version']} 可能不完全支援，建議升級到3.9+"
                
            return python_info
            
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    async def _detect_docker(self) -> Dict[str, Any]:
        """檢測Docker環境"""
        try:
            # 檢查Docker命令是否可用
            result = await self._run_command(['docker', '--version'], timeout=10)
            
            if result['returncode'] == 0:
                version_output = result['stdout'].strip()
                
                # 檢查Docker Compose
                compose_result = await self._run_command(['docker', 'compose', 'version'], timeout=10)
                compose_available = compose_result['returncode'] == 0
                
                # 檢查Docker服務狀態
                service_result = await self._run_command(['docker', 'info'], timeout=15)
                service_running = service_result['returncode'] == 0
                
                return {
                    'available': True,
                    'version': version_output,
                    'compose_available': compose_available,
                    'compose_version': compose_result['stdout'].strip() if compose_available else None,
                    'service_running': service_running,
                    'service_info': service_result['stdout'][:500] if service_running else None  # 限制日誌長度
                }
            else:
                return {
                    'available': False,
                    'error': result['stderr'].strip()
                }
                
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    async def _detect_uv(self) -> Dict[str, Any]:
        """檢測UV包管理器"""
        try:
            result = await self._run_command(['uv', '--version'], timeout=10)
            
            if result['returncode'] == 0:
                version_output = result['stdout'].strip()
                return {
                    'available': True,
                    'version': version_output
                }
            else:
                return {
                    'available': False,
                    'error': result['stderr'].strip()
                }
                
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    async def _detect_package_manager(self, platform_info: Dict[str, Any]) -> Optional[str]:
        """檢測系統包管理器"""
        platform_type = platform_info['platform']
        
        package_managers = {
            SystemPlatform.LINUX: ['apt', 'yum', 'dnf', 'pacman', 'zypper'],
            SystemPlatform.MACOS: ['brew', 'port'],
            SystemPlatform.WINDOWS: ['choco', 'winget', 'scoop']
        }
        
        if platform_type not in package_managers:
            return None
            
        for manager in package_managers[platform_type]:
            try:
                result = await self._run_command([manager, '--version'], timeout=5)
                if result['returncode'] == 0:
                    return manager
            except:
                continue
                
        return None
    
    async def _check_permissions(self) -> Dict[str, bool]:
        """檢查系統權限"""
        permissions = {}
        
        try:
            # 檢查sudo權限（Unix-like系統）
            if os.name == 'posix':
                try:
                    result = await self._run_command(['sudo', '-n', 'true'], timeout=5)
                    permissions['sudo'] = result['returncode'] == 0
                except:
                    permissions['sudo'] = False
            else:
                # Windows管理員權限檢查
                try:
                    import ctypes
                    permissions['admin'] = ctypes.windll.shell32.IsUserAnAdmin() != 0
                except:
                    permissions['admin'] = False
            
            # 檢查Docker socket權限（Linux）
            if os.path.exists('/var/run/docker.sock'):
                try:
                    permissions['docker_socket'] = os.access('/var/run/docker.sock', os.R_OK | os.W_OK)
                except:
                    permissions['docker_socket'] = False
            
            # 檢查寫入權限
            try:
                test_dir = Path.cwd() / '.deployment_test'
                test_dir.mkdir(exist_ok=True)
                (test_dir / 'test.txt').write_text('test')
                (test_dir / 'test.txt').unlink()
                test_dir.rmdir()
                permissions['write_access'] = True
            except:
                permissions['write_access'] = False
                
        except Exception as e:
            self.logger.warning(f"權限檢查部分失敗: {e}")
            
        return permissions
    
    async def _collect_relevant_env_vars(self) -> Dict[str, str]:
        """收集相關環境變數"""
        relevant_vars = [
            'PATH', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV',
            'DOCKER_HOST', 'DOCKER_CONTEXT',
            'ROAS_ENVIRONMENT', 'ROAS_CONFIG_DIR',
            'UV_CACHE_DIR', 'PIP_CACHE_DIR'
        ]
        
        env_vars = {}
        for var in relevant_vars:
            value = os.getenv(var)
            if value:
                # 對於路徑變數，只保留前3個路徑避免過長
                if var in ['PATH', 'PYTHONPATH'] and ':' in value:
                    paths = value.split(':')[:3]
                    env_vars[var] = ':'.join(paths) + ('...' if len(value.split(':')) > 3 else '')
                else:
                    env_vars[var] = value
                    
        return env_vars
    
    async def _run_command(self, cmd: List[str], timeout: int = 30) -> Dict[str, Any]:
        """
        執行系統命令
        
        Args:
            cmd: 命令列表
            timeout: 超時時間（秒）
            
        Returns:
            執行結果字典
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                return {
                    'returncode': process.returncode,
                    'stdout': stdout.decode('utf-8', errors='ignore'),
                    'stderr': stderr.decode('utf-8', errors='ignore')
                }
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': f'Command timeout after {timeout}s'
                }
                
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            }
    
    async def auto_install_dependencies(self, 
                                      target_env: str,
                                      env_info: Optional[EnvironmentInfo] = None) -> bool:
        """
        自動安裝依賴
        
        Args:
            target_env: 目標環境 ('docker', 'uv', 'python')
            env_info: 環境資訊（可選，不提供則重新檢測）
            
        Returns:
            安裝是否成功
        """
        if not env_info:
            env_info = await self.detect_all_environments()
            
        try:
            self.logger.info(f"開始安裝 {target_env} 環境依賴...")
            
            if target_env == 'docker':
                return await self._install_docker(env_info)
            elif target_env == 'uv':
                return await self._install_uv(env_info)
            elif target_env == 'python':
                return await self._install_python(env_info)
            else:
                raise ValueError(f"不支援的目標環境: {target_env}")
                
        except Exception as e:
            self.logger.error(f"安裝 {target_env} 依賴失敗: {e}")
            raise DependencyInstallError(
                dependency_name=target_env,
                install_method="auto_install",
                reason=str(e),
                cause=e
            )
    
    async def _install_docker(self, env_info: EnvironmentInfo) -> bool:
        """安裝Docker"""
        if env_info.docker_available:
            self.logger.info("Docker已經可用，跳過安裝")
            return True
            
        self.logger.info(f"在 {env_info.platform.value} 上安裝Docker...")
        
        try:
            if env_info.platform == SystemPlatform.LINUX:
                return await self._install_docker_linux(env_info)
            elif env_info.platform == SystemPlatform.MACOS:
                return await self._install_docker_macos(env_info)
            elif env_info.platform == SystemPlatform.WINDOWS:
                return await self._install_docker_windows(env_info)
            else:
                self.logger.error(f"不支援在 {env_info.platform.value} 上安裝Docker")
                return False
                
        except Exception as e:
            self.logger.error(f"Docker安裝失敗: {e}")
            return False
    
    async def _install_docker_linux(self, env_info: EnvironmentInfo) -> bool:
        """在Linux上安裝Docker"""
        package_manager = env_info.package_manager
        
        if not package_manager:
            self.logger.error("未檢測到支援的包管理器")
            return False
            
        if not env_info.permissions.get('sudo', False):
            self.logger.error("需要sudo權限來安裝Docker")
            return False
            
        try:
            if package_manager == 'apt':
                # Ubuntu/Debian安裝流程
                commands = [
                    ['sudo', 'apt', 'update'],
                    ['sudo', 'apt', 'install', '-y', 'apt-transport-https', 'ca-certificates', 'curl', 'gnupg', 'lsb-release'],
                    ['curl', '-fsSL', 'https://download.docker.com/linux/ubuntu/gpg', '|', 'sudo', 'gpg', '--dearmor', '-o', '/usr/share/keyrings/docker-archive-keyring.gpg'],
                    ['sudo', 'apt', 'update'],
                    ['sudo', 'apt', 'install', '-y', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-compose-plugin']
                ]
                
                for cmd in commands:
                    result = await self._run_command(cmd, timeout=300)  # 5分鐘超時
                    if result['returncode'] != 0:
                        self.logger.error(f"命令執行失敗: {' '.join(cmd)}, 錯誤: {result['stderr']}")
                        return False
                        
            elif package_manager in ['yum', 'dnf']:
                # RedHat/CentOS/Fedora安裝流程
                cmd_tool = package_manager
                commands = [
                    ['sudo', cmd_tool, 'install', '-y', 'yum-utils'],
                    ['sudo', 'yum-config-manager', '--add-repo', 'https://download.docker.com/linux/centos/docker-ce.repo'],
                    ['sudo', cmd_tool, 'install', '-y', 'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-compose-plugin']
                ]
                
                for cmd in commands:
                    result = await self._run_command(cmd, timeout=300)
                    if result['returncode'] != 0:
                        self.logger.error(f"命令執行失敗: {' '.join(cmd)}, 錯誤: {result['stderr']}")
                        return False
            else:
                self.logger.error(f"不支援的包管理器: {package_manager}")
                return False
                
            # 啟動並啟用Docker服務
            service_commands = [
                ['sudo', 'systemctl', 'start', 'docker'],
                ['sudo', 'systemctl', 'enable', 'docker']
            ]
            
            for cmd in service_commands:
                result = await self._run_command(cmd, timeout=60)
                if result['returncode'] != 0:
                    self.logger.warning(f"服務命令可能失敗: {' '.join(cmd)}, 錯誤: {result['stderr']}")
            
            # 驗證安裝
            await asyncio.sleep(5)  # 等待服務啟動
            docker_info = await self._detect_docker()
            
            if docker_info['available']:
                self.logger.info("Docker安裝成功")
                return True
            else:
                self.logger.error("Docker安裝後仍無法使用")
                return False
                
        except Exception as e:
            self.logger.error(f"Linux Docker安裝失敗: {e}")
            return False
    
    async def _install_docker_macos(self, env_info: EnvironmentInfo) -> bool:
        """在macOS上安裝Docker"""
        package_manager = env_info.package_manager
        
        if package_manager == 'brew':
            try:
                # 使用Homebrew安裝
                commands = [
                    ['brew', 'install', '--cask', 'docker']
                ]
                
                for cmd in commands:
                    result = await self._run_command(cmd, timeout=600)  # 10分鐘超時
                    if result['returncode'] != 0:
                        self.logger.error(f"命令執行失敗: {' '.join(cmd)}, 錯誤: {result['stderr']}")
                        return False
                
                # 提示用戶手動啟動Docker Desktop
                self.logger.info("Docker已安裝，請手動啟動Docker Desktop應用程式")
                
                # 等待用戶啟動Docker Desktop（最多等待2分鐘）
                for i in range(24):  # 24 * 5秒 = 2分鐘
                    await asyncio.sleep(5)
                    docker_info = await self._detect_docker()
                    if docker_info['available'] and docker_info['service_running']:
                        self.logger.info("Docker Desktop已啟動並可用")
                        return True
                    if i == 0:
                        self.logger.info("等待Docker Desktop啟動中...")
                
                self.logger.warning("Docker Desktop可能需要手動啟動")
                return False
                
            except Exception as e:
                self.logger.error(f"macOS Docker安裝失敗: {e}")
                return False
        else:
            self.logger.error("在macOS上需要Homebrew來安裝Docker")
            return False
    
    async def _install_docker_windows(self, env_info: EnvironmentInfo) -> bool:
        """在Windows上安裝Docker"""
        self.logger.info("Windows Docker安裝需要手動下載Docker Desktop")
        self.logger.info("請訪問 https://www.docker.com/products/docker-desktop 下載並安裝")
        
        # 在Windows上，我們無法自動安裝Docker Desktop，只能提供指引
        return False
    
    async def _install_uv(self, env_info: EnvironmentInfo) -> bool:
        """安裝UV包管理器"""
        if env_info.uv_available:
            self.logger.info("UV已經可用，跳過安裝")
            return True
            
        try:
            self.logger.info("安裝UV包管理器...")
            
            # 使用官方安裝腳本
            if env_info.platform in [SystemPlatform.LINUX, SystemPlatform.MACOS]:
                # Unix-like系統使用curl安裝
                cmd = ['curl', '-LsSf', 'https://astral.sh/uv/install.sh', '|', 'sh']
                result = await self._run_command(['sh', '-c', ' '.join(cmd)], timeout=300)
                
                if result['returncode'] != 0:
                    # 嘗試使用pip安裝
                    self.logger.info("嘗試使用pip安裝UV...")
                    pip_cmd = ['pip', 'install', 'uv']
                    result = await self._run_command(pip_cmd, timeout=180)
                    
                    if result['returncode'] != 0:
                        self.logger.error(f"UV安裝失敗: {result['stderr']}")
                        return False
                        
            elif env_info.platform == SystemPlatform.WINDOWS:
                # Windows使用PowerShell安裝
                cmd = ['powershell', '-c', 'irm https://astral.sh/uv/install.ps1 | iex']
                result = await self._run_command(cmd, timeout=300)
                
                if result['returncode'] != 0:
                    # 嘗試使用pip安裝
                    pip_cmd = ['pip', 'install', 'uv']
                    result = await self._run_command(pip_cmd, timeout=180)
                    
                    if result['returncode'] != 0:
                        self.logger.error(f"UV安裝失敗: {result['stderr']}")
                        return False
                        
            # 驗證安裝
            await asyncio.sleep(2)
            uv_info = await self._detect_uv()
            
            if uv_info['available']:
                self.logger.info("UV安裝成功")
                return True
            else:
                self.logger.error("UV安裝後仍無法使用")
                return False
                
        except Exception as e:
            self.logger.error(f"UV安裝失敗: {e}")
            return False
    
    async def _install_python(self, env_info: EnvironmentInfo) -> bool:
        """安裝或升級Python"""
        if env_info.python_version:
            version_parts = env_info.python_version.split('.')
            if len(version_parts) >= 2:
                major, minor = int(version_parts[0]), int(version_parts[1])
                if major >= 3 and minor >= 9:
                    self.logger.info(f"Python {env_info.python_version} 已滿足要求")
                    return True
        
        self.logger.info("需要安裝或升級Python到3.9+")
        
        # Python安裝比較複雜，通常需要用戶手動處理
        # 這裡提供安裝指引
        if env_info.platform == SystemPlatform.LINUX:
            if env_info.package_manager == 'apt':
                self.logger.info("建議執行: sudo apt update && sudo apt install python3.9 python3.9-pip")
            elif env_info.package_manager in ['yum', 'dnf']:
                self.logger.info("建議執行: sudo dnf install python3.9 python3-pip")
                
        elif env_info.platform == SystemPlatform.MACOS:
            if env_info.package_manager == 'brew':
                self.logger.info("建議執行: brew install python@3.9")
            else:
                self.logger.info("請訪問 https://www.python.org/downloads/ 下載Python")
                
        elif env_info.platform == SystemPlatform.WINDOWS:
            self.logger.info("請訪問 https://www.python.org/downloads/ 下載Python")
            
        # 對於自動化部署，我們暫不自動安裝Python
        return False
    
    def get_recommended_deployment_mode(self, env_info: EnvironmentInfo) -> DeploymentMode:
        """
        根據環境資訊推薦部署模式
        
        Args:
            env_info: 環境資訊
            
        Returns:
            推薦的部署模式
        """
        if env_info.docker_available:
            return DeploymentMode.DOCKER
        elif env_info.uv_available and env_info.python_version:
            return DeploymentMode.UV_PYTHON
        elif env_info.python_version:
            return DeploymentMode.FALLBACK
        else:
            # 如果都不可用，但可以安裝，推薦UV模式
            return DeploymentMode.UV_PYTHON
    
    def get_environment_summary(self, env_info: EnvironmentInfo) -> Dict[str, Any]:
        """
        獲取環境摘要
        
        Args:
            env_info: 環境資訊
            
        Returns:
            環境摘要字典
        """
        return {
            'platform': env_info.platform.value,
            'architecture': env_info.architecture,
            'python_available': env_info.python_version is not None,
            'python_version': env_info.python_version,
            'docker_available': env_info.docker_available,
            'docker_version': env_info.docker_version,
            'uv_available': env_info.uv_available,
            'uv_version': env_info.uv_version,
            'package_manager': env_info.package_manager,
            'permissions': env_info.permissions,
            'recommended_mode': self.get_recommended_deployment_mode(env_info).value,
            'detected_at': env_info.detected_at.isoformat()
        }


class DockerDeploymentManager(DeploymentManager):
    """
    Docker部署管理器
    
    負責Docker容器的構建、啟動、監控和管理
    支援Docker Compose多服務編排
    """
    
    def __init__(self, config: AppConfig, env_info: EnvironmentInfo):
        super().__init__(config)
        self.env_info = env_info
        self.compose_file_path = Path.cwd() / "docker" / "compose.yaml"
        self.project_name = "roas-bot"
        self.services_status: Dict[str, str] = {}
        
        # 驗證Docker環境
        if not env_info.docker_available:
            raise EnvironmentError(
                environment_type="docker",
                check_failed="docker_not_available",
                details={"message": "Docker環境不可用"}
            )
    
    async def check_dependencies(self) -> bool:
        """
        檢查Docker依賴是否可用
        
        Returns:
            bool: 依賴是否可用
        """
        try:
            # 檢查Docker命令
            result = await self._run_command(['docker', '--version'], timeout=10)
            if result['returncode'] != 0:
                self.logger.error(f"Docker命令不可用: {result['stderr']}")
                return False
                
            # 檢查Docker Compose
            result = await self._run_command(['docker', 'compose', 'version'], timeout=10)
            if result['returncode'] != 0:
                self.logger.error(f"Docker Compose不可用: {result['stderr']}")
                return False
                
            # 檢查Docker服務狀態
            result = await self._run_command(['docker', 'info'], timeout=15)
            if result['returncode'] != 0:
                self.logger.error(f"Docker服務未運行: {result['stderr']}")
                return False
                
            # 檢查Compose文件
            if not self.compose_file_path.exists():
                self.logger.error(f"Docker Compose文件不存在: {self.compose_file_path}")
                return False
                
            self.logger.info("Docker依賴檢查通過")
            return True
            
        except Exception as e:
            self.logger.error(f"檢查Docker依賴失敗: {e}")
            return False
    
    async def install_dependencies(self) -> bool:
        """
        安裝Docker依賴（如果需要）
        
        Returns:
            bool: 安裝是否成功
        """
        try:
            # 如果Docker已可用，無需安裝
            if await self.check_dependencies():
                return True
                
            self.logger.info("Docker依賴不完整，嘗試安裝...")
            
            # 根據平台安裝Docker
            if self.env_info.platform == SystemPlatform.LINUX:
                return await self._install_docker_linux()
            elif self.env_info.platform == SystemPlatform.MACOS:
                return await self._install_docker_macos()
            elif self.env_info.platform == SystemPlatform.WINDOWS:
                return await self._install_docker_windows()
            else:
                self.logger.error(f"不支援的平台: {self.env_info.platform}")
                return False
                
        except Exception as e:
            self.logger.error(f"安裝Docker依賴失敗: {e}")
            raise DependencyInstallError(
                dependency_name="docker",
                install_method="auto",
                reason=str(e),
                cause=e
            )
    
    async def start_services(self) -> bool:
        """
        啟動Docker服務
        
        Returns:
            bool: 啟動是否成功
        """
        try:
            self.logger.info("啟動Docker服務...")
            
            # 確保依賴可用
            if not await self.check_dependencies():
                self.logger.error("Docker依賴檢查失敗，無法啟動服務")
                return False
            
            # 停止現有容器（如果有）
            await self._stop_existing_containers()
            
            # 構建鏡像（如果需要）
            if not await self._build_images():
                return False
                
            # 啟動服務
            if not await self._start_compose_services():
                return False
                
            # 等待服務就緒
            if not await self._wait_for_services_ready(timeout=120):
                self.logger.error("服務啟動超時")
                return False
                
            self.logger.info("Docker服務啟動成功")
            return True
            
        except Exception as e:
            self.logger.error(f"啟動Docker服務失敗: {e}")
            raise ServiceStartupError(
                service_name="DockerServices",
                startup_mode="docker",
                reason=str(e),
                cause=e
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Docker服務健康檢查
        
        Returns:
            健康檢查結果
        """
        try:
            health_info = {
                'manager': 'DockerDeploymentManager',
                'status': 'healthy',
                'services': {},
                'containers': {},
                'resources': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # 檢查Docker守護進程
            result = await self._run_command(['docker', 'info', '--format', '{{json .}}'], timeout=10)
            if result['returncode'] == 0:
                try:
                    docker_info = json.loads(result['stdout'])
                    health_info['docker_daemon'] = {
                        'status': 'running',
                        'containers_running': docker_info.get('ContainersRunning', 0),
                        'images': docker_info.get('Images', 0)
                    }
                except json.JSONDecodeError:
                    health_info['docker_daemon'] = {'status': 'unknown'}
            else:
                health_info['docker_daemon'] = {'status': 'stopped'}
                health_info['status'] = 'unhealthy'
            
            # 檢查Compose服務狀態
            compose_status = await self._get_compose_status()
            health_info['services'] = compose_status['services']
            
            # 統計健康服務數量
            healthy_services = sum(1 for svc in compose_status['services'].values() 
                                 if svc.get('status') == 'running')
            total_services = len(compose_status['services'])
            
            if total_services == 0:
                health_info['status'] = 'no_services'
            elif healthy_services == total_services:
                health_info['status'] = 'healthy'
            elif healthy_services > 0:
                health_info['status'] = 'degraded'
            else:
                health_info['status'] = 'unhealthy'
                
            health_info['service_summary'] = {
                'total': total_services,
                'healthy': healthy_services,
                'unhealthy': total_services - healthy_services
            }
            
            return health_info
            
        except Exception as e:
            return {
                'manager': 'DockerDeploymentManager',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def stop_services(self) -> bool:
        """
        停止Docker服務
        
        Returns:
            bool: 停止是否成功
        """
        try:
            self.logger.info("停止Docker服務...")
            
            # 使用docker-compose停止服務
            result = await self._run_command([
                'docker', 'compose',
                '-f', str(self.compose_file_path),
                '-p', self.project_name,
                'down'
            ], timeout=60)
            
            if result['returncode'] != 0:
                self.logger.error(f"停止服務失敗: {result['stderr']}")
                return False
                
            # 清理資源（可選）
            await self._cleanup_resources()
            
            self.logger.info("Docker服務已停止")
            return True
            
        except Exception as e:
            self.logger.error(f"停止Docker服務失敗: {e}")
            return False
    
    async def _install_docker_linux(self) -> bool:
        """在Linux上安裝Docker"""
        package_manager = self.env_info.package_manager
        
        if not package_manager:
            self.logger.error("未檢測到支援的包管理器")
            return False
            
        if not self.env_info.permissions.get('sudo', False):
            self.logger.error("需要sudo權限來安裝Docker")
            return False
            
        try:
            self.logger.info(f"使用 {package_manager} 安裝Docker...")
            
            if package_manager == 'apt':
                commands = [
                    ['sudo', 'apt', 'update'],
                    ['sudo', 'apt', 'install', '-y', 'docker.io', 'docker-compose-plugin'],
                    ['sudo', 'systemctl', 'enable', 'docker'],
                    ['sudo', 'systemctl', 'start', 'docker']
                ]
            elif package_manager in ['yum', 'dnf']:
                commands = [
                    ['sudo', package_manager, 'install', '-y', 'docker', 'docker-compose'],
                    ['sudo', 'systemctl', 'enable', 'docker'],
                    ['sudo', 'systemctl', 'start', 'docker']
                ]
            else:
                self.logger.error(f"不支援的包管理器: {package_manager}")
                return False
                
            for cmd in commands:
                result = await self._run_command(cmd, timeout=300)
                if result['returncode'] != 0:
                    self.logger.error(f"命令失敗: {' '.join(cmd)}, 錯誤: {result['stderr']}")
                    return False
                    
            # 驗證安裝
            await asyncio.sleep(5)
            return await self.check_dependencies()
            
        except Exception as e:
            self.logger.error(f"Linux Docker安裝失敗: {e}")
            return False
    
    async def _install_docker_macos(self) -> bool:
        """在macOS上安裝Docker"""
        if self.env_info.package_manager == 'brew':
            try:
                result = await self._run_command(['brew', 'install', '--cask', 'docker'], timeout=600)
                if result['returncode'] != 0:
                    self.logger.error(f"安裝Docker失敗: {result['stderr']}")
                    return False
                    
                self.logger.info("Docker已安裝，請手動啟動Docker Desktop")
                return False  # 需要用戶手動啟動
                
            except Exception as e:
                self.logger.error(f"macOS Docker安裝失敗: {e}")
                return False
        else:
            self.logger.error("在macOS上需要Homebrew來安裝Docker")
            return False
    
    async def _install_docker_windows(self) -> bool:
        """在Windows上安裝Docker"""
        self.logger.error("Windows上需要手動安裝Docker Desktop")
        return False
    
    async def _stop_existing_containers(self) -> None:
        """停止現有容器"""
        try:
            result = await self._run_command([
                'docker', 'compose',
                '-f', str(self.compose_file_path),
                '-p', self.project_name,
                'down'
            ], timeout=30)
            
            if result['returncode'] == 0:
                self.logger.info("已停止現有容器")
            else:
                self.logger.debug(f"停止現有容器時出現警告: {result['stderr']}")
                
        except Exception as e:
            self.logger.debug(f"停止現有容器失敗: {e}")
    
    async def _build_images(self) -> bool:
        """構建Docker鏡像"""
        try:
            self.logger.info("構建Docker鏡像...")
            
            result = await self._run_command([
                'docker', 'compose',
                '-f', str(self.compose_file_path),
                '-p', self.project_name,
                'build', '--no-cache'
            ], timeout=600)  # 10分鐘超時
            
            if result['returncode'] != 0:
                self.logger.error(f"構建鏡像失敗: {result['stderr']}")
                return False
                
            self.logger.info("Docker鏡像構建成功")
            return True
            
        except Exception as e:
            self.logger.error(f"構建Docker鏡像失敗: {e}")
            return False
    
    async def _start_compose_services(self) -> bool:
        """啟動Compose服務"""
        try:
            self.logger.info("啟動Docker Compose服務...")
            
            result = await self._run_command([
                'docker', 'compose',
                '-f', str(self.compose_file_path),
                '-p', self.project_name,
                'up', '-d'
            ], timeout=300)  # 5分鐘超時
            
            if result['returncode'] != 0:
                self.logger.error(f"啟動服務失敗: {result['stderr']}")
                return False
                
            self.logger.info("Docker Compose服務啟動成功")
            return True
            
        except Exception as e:
            self.logger.error(f"啟動Docker Compose服務失敗: {e}")
            return False
    
    async def _wait_for_services_ready(self, timeout: int = 120) -> bool:
        """等待服務就緒"""
        try:
            self.logger.info("等待服務就緒...")
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < timeout:
                status = await self._get_compose_status()
                
                # 檢查所有服務是否都在運行
                all_running = True
                for service_name, service_info in status['services'].items():
                    if service_info.get('status') != 'running':
                        all_running = False
                        break
                        
                if all_running and len(status['services']) > 0:
                    self.logger.info("所有服務已就緒")
                    return True
                    
                # 等待一段時間再檢查
                await asyncio.sleep(5)
                
            self.logger.error(f"等待服務就緒超時 ({timeout}秒)")
            return False
            
        except Exception as e:
            self.logger.error(f"等待服務就緒失敗: {e}")
            return False
    
    async def _get_compose_status(self) -> Dict[str, Any]:
        """獲取Compose服務狀態"""
        try:
            result = await self._run_command([
                'docker', 'compose',
                '-f', str(self.compose_file_path),
                '-p', self.project_name,
                'ps', '--format', 'json'
            ], timeout=30)
            
            if result['returncode'] != 0:
                return {'services': {}}
                
            services = {}
            try:
                # 解析JSON輸出
                lines = result['stdout'].strip().split('\n')
                for line in lines:
                    if line.strip():
                        service_info = json.loads(line)
                        service_name = service_info.get('Service', 'unknown')
                        services[service_name] = {
                            'name': service_info.get('Name', ''),
                            'status': service_info.get('State', 'unknown'),
                            'ports': service_info.get('Publishers', []),
                            'health': service_info.get('Health', 'unknown')
                        }
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.debug(f"解析服務狀態失敗: {e}")
                
            return {'services': services}
            
        except Exception as e:
            self.logger.debug(f"獲取Compose狀態失敗: {e}")
            return {'services': {}}
    
    async def _cleanup_resources(self) -> None:
        """清理資源"""
        try:
            # 清理未使用的鏡像
            await self._run_command(['docker', 'image', 'prune', '-f'], timeout=60)
            
            # 清理未使用的網絡
            await self._run_command(['docker', 'network', 'prune', '-f'], timeout=30)
            
            # 清理未使用的卷（謹慎操作）
            # await self._run_command(['docker', 'volume', 'prune', '-f'], timeout=30)
            
            self.logger.info("資源清理完成")
            
        except Exception as e:
            self.logger.debug(f"資源清理失敗: {e}")
    
    async def _run_command(self, cmd: List[str], timeout: int = 30) -> Dict[str, Any]:
        """執行系統命令"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                return {
                    'returncode': process.returncode,
                    'stdout': stdout.decode('utf-8', errors='ignore'),
                    'stderr': stderr.decode('utf-8', errors='ignore')
                }
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': f'Command timeout after {timeout}s'
                }
                
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            }
    
    def get_service_logs(self, service_name: Optional[str] = None, tail: int = 100) -> Dict[str, Any]:
        """獲取服務日誌（同步方法）"""
        try:
            cmd = [
                'docker', 'compose',
                '-f', str(self.compose_file_path),
                '-p', self.project_name,
                'logs', '--tail', str(tail)
            ]
            
            if service_name:
                cmd.append(service_name)
                
            # 使用同步方式執行
            import subprocess
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                'success': result.returncode == 0,
                'logs': result.stdout if result.returncode == 0 else result.stderr,
                'service': service_name or 'all'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'service': service_name or 'all'
            }


class UVDeploymentManager(DeploymentManager):
    """
    UV Python部署管理器
    
    負貮Python環境的設置、依賴安裝、應用程式啟動
    使用UV為主要的包管理器，支援pip fallback
    """
    
    def __init__(self, config: AppConfig, env_info: EnvironmentInfo):
        super().__init__(config)
        self.env_info = env_info
        self.project_root = Path.cwd()
        self.venv_path = self.project_root / ".venv"
        self.requirements_file = self.project_root / "requirements.txt"
        self.pyproject_file = self.project_root / "pyproject.toml"
        self.main_module = "main.py"  # 主應用程式檔案
        
        # 驗證Python環境
        if not env_info.python_version:
            raise EnvironmentError(
                environment_type="python",
                check_failed="python_not_available",
                details={"message": "Python環境不可用"}
            )
    
    async def check_dependencies(self) -> bool:
        """
        檢查UV和Python依賴
        
        Returns:
            bool: 依賴是否可用
        """
        try:
            # 檢查Python版本
            if not self.env_info.python_version:
                self.logger.error("Python不可用")
                return False
                
            # 檢查Python版本是否符合要求
            version_parts = self.env_info.python_version.split('.')
            if len(version_parts) >= 2:
                major, minor = int(version_parts[0]), int(version_parts[1])
                if major < 3 or (major == 3 and minor < 9):
                    self.logger.error(f"Python版本 {self.env_info.python_version} 不符合要求，需要Python 3.9+")
                    return False
            
            # 檢查UV是否可用
            uv_available = self.env_info.uv_available
            if not uv_available:
                # 檢查pip是否可用作為備選
                pip_result = await self._run_command(['pip', '--version'], timeout=10)
                if pip_result['returncode'] != 0:
                    self.logger.error("UV和pip都不可用")
                    return False
                else:
                    self.logger.warning("UV不可用，將使用pip作為備選")
            
            # 檢查專案檔案
            if not self.pyproject_file.exists() and not self.requirements_file.exists():
                self.logger.error("找不到pyproject.toml或requirements.txt檔案")
                return False
                
            # 檢查主應用程式檔案
            main_file = self.project_root / self.main_module
            if not main_file.exists():
                # 嘗試尋找其他常見的主檔案
                possible_main_files = ['app.py', 'run.py', 'bot.py', 'start.py']
                found_main = False
                for filename in possible_main_files:
                    if (self.project_root / filename).exists():
                        self.main_module = filename
                        found_main = True
                        break
                        
                if not found_main:
                    self.logger.error("找不到主應用程式檔案")
                    return False
            
            self.logger.info("UV/Python依賴檢查通過")
            return True
            
        except Exception as e:
            self.logger.error(f"檢查UV依賴失敗: {e}")
            return False
    
    async def install_dependencies(self) -> bool:
        """
        安裝Python依賴
        
        Returns:
            bool: 安裝是否成功
        """
        try:
            # 確保基本依賴可用
            if not await self.check_dependencies():
                self.logger.error("基本依賴檢查失敗，無法安裝")
                return False
                
            self.logger.info("安裝Python依賴...")
            
            # 安裝UV（如果不可用）
            if not self.env_info.uv_available:
                if not await self._install_uv():
                    self.logger.warning("UV安裝失敗，將使用pip模式")
            
            # 設置虛擬環境
            if not await self._setup_virtual_environment():
                return False
                
            # 安裝依賴包
            if not await self._install_python_dependencies():
                return False
                
            self.logger.info("Python依賴安裝成功")
            return True
            
        except Exception as e:
            self.logger.error(f"安裝Python依賴失敗: {e}")
            raise DependencyInstallError(
                dependency_name="python_dependencies",
                install_method="uv",
                reason=str(e),
                cause=e
            )
    
    async def start_services(self) -> bool:
        """
        啟動Python應用程式
        
        Returns:
            bool: 啟動是否成功
        """
        try:
            self.logger.info("啟動Python應用程式...")
            
            # 確保依賴已安裝
            if not await self.check_dependencies():
                self.logger.error("依賴檢查失敗，無法啟動")
                return False
                
            # 確保虛擬環境存在
            if not self.venv_path.exists():
                if not await self._setup_virtual_environment():
                    return False
                    
                if not await self._install_python_dependencies():
                    return False
            
            # 啟動應用程式
            return await self._start_application()
            
        except Exception as e:
            self.logger.error(f"啟動Python應用程式失敗: {e}")
            raise ServiceStartupError(
                service_name="PythonApplication",
                startup_mode="uv",
                reason=str(e),
                cause=e
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        UV/Python環境健康檢查
        
        Returns:
            健康檢查結果
        """
        try:
            health_info = {
                'manager': 'UVDeploymentManager',
                'status': 'healthy',
                'python_info': {},
                'virtual_env': {},
                'dependencies': {},
                'application': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # 檢查Python環境
            python_result = await self._run_command(['python', '--version'], timeout=10)
            if python_result['returncode'] == 0:
                health_info['python_info'] = {
                    'status': 'available',
                    'version': python_result['stdout'].strip(),
                    'executable': 'python'
                }
            else:
                health_info['python_info'] = {'status': 'unavailable'}
                health_info['status'] = 'unhealthy'
            
            # 檢查UV可用性
            uv_result = await self._run_command(['uv', '--version'], timeout=10)
            if uv_result['returncode'] == 0:
                health_info['uv_info'] = {
                    'status': 'available',
                    'version': uv_result['stdout'].strip()
                }
            else:
                # 檢查pip作為備選
                pip_result = await self._run_command(['pip', '--version'], timeout=10)
                if pip_result['returncode'] == 0:
                    health_info['uv_info'] = {
                        'status': 'pip_fallback',
                        'pip_version': pip_result['stdout'].strip()
                    }
                else:
                    health_info['uv_info'] = {'status': 'unavailable'}
                    health_info['status'] = 'degraded'
            
            # 檢查虛擬環境
            if self.venv_path.exists():
                health_info['virtual_env'] = {
                    'status': 'exists',
                    'path': str(self.venv_path),
                    'python_executable': str(self.venv_path / 'bin' / 'python') if os.name == 'posix' else str(self.venv_path / 'Scripts' / 'python.exe')
                }
                
                # 檢查虛擬環境中的Python
                venv_python = self._get_venv_python_path()
                venv_result = await self._run_command([str(venv_python), '--version'], timeout=10)
                if venv_result['returncode'] == 0:
                    health_info['virtual_env']['python_version'] = venv_result['stdout'].strip()
                else:
                    health_info['virtual_env']['status'] = 'corrupted'
                    health_info['status'] = 'degraded'
            else:
                health_info['virtual_env'] = {'status': 'missing'}
                health_info['status'] = 'degraded'
            
            # 檢查主應用程式檔案
            main_file = self.project_root / self.main_module
            if main_file.exists():
                health_info['application'] = {
                    'main_file': str(main_file),
                    'status': 'ready'
                }
            else:
                health_info['application'] = {
                    'main_file': str(main_file),
                    'status': 'missing'
                }
                health_info['status'] = 'degraded'
            
            return health_info
            
        except Exception as e:
            return {
                'manager': 'UVDeploymentManager',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def stop_services(self) -> bool:
        """
        停止Python應用程式
        
        Returns:
            bool: 停止是否成功
        """
        try:
            self.logger.info("停止Python應用程式...")
            
            # 目前UV模式下，應用程式通常是由外部進程控制
            # 這裡主要做清理工作
            
            # 清理臨時檔案
            await self._cleanup_temp_files()
            
            self.logger.info("Python應用程式已停止")
            return True
            
        except Exception as e:
            self.logger.error(f"停止Python應用程式失敗: {e}")
            return False
    
    async def _install_uv(self) -> bool:
        """安裝UV包管理器"""
        try:
            self.logger.info("嘗試安裝UV...")
            
            if self.env_info.platform in [SystemPlatform.LINUX, SystemPlatform.MACOS]:
                # Unix-like系統使用curl安裝
                result = await self._run_command([
                    'sh', '-c', 
                    'curl -LsSf https://astral.sh/uv/install.sh | sh'
                ], timeout=300)
                
                if result['returncode'] == 0:
                    # 更新環境資訊
                    await asyncio.sleep(2)
                    uv_result = await self._run_command(['uv', '--version'], timeout=10)
                    if uv_result['returncode'] == 0:
                        self.logger.info("UV安裝成功")
                        return True
                        
            # 嘗試使用pip安裝
            pip_result = await self._run_command(['pip', 'install', 'uv'], timeout=180)
            if pip_result['returncode'] == 0:
                await asyncio.sleep(2)
                uv_result = await self._run_command(['uv', '--version'], timeout=10)
                if uv_result['returncode'] == 0:
                    self.logger.info("UV安裝成功（通過pip）")
                    return True
                    
            self.logger.warning("UV安裝失敗")
            return False
            
        except Exception as e:
            self.logger.error(f"UV安裝失敗: {e}")
            return False
    
    async def _setup_virtual_environment(self) -> bool:
        """設置虛擬環境"""
        try:
            self.logger.info("設置虛擬環境...")
            
            # 如果虛擬環境已存在，先檢查是否有效
            if self.venv_path.exists():
                if await self._validate_virtual_environment():
                    self.logger.info("虛擬環境已存在且有效")
                    return True
                else:
                    self.logger.info("清理無效的虛擬環境")
                    await self._remove_virtual_environment()
            
            # 優先使用UV創建虛擬環境
            if self.env_info.uv_available:
                result = await self._run_command([
                    'uv', 'venv', str(self.venv_path)
                ], timeout=120)
                
                if result['returncode'] == 0:
                    self.logger.info("使用UV創建虛擬環境成功")
                    return True
                else:
                    self.logger.warning(f"UV創建虛擬環境失敗: {result['stderr']}")
            
            # 使用venv作為備選
            result = await self._run_command([
                'python', '-m', 'venv', str(self.venv_path)
            ], timeout=120)
            
            if result['returncode'] == 0:
                self.logger.info("使用venv創建虛擬環境成功")
                return True
            else:
                self.logger.error(f"創建虛擬環境失敗: {result['stderr']}")
                return False
                
        except Exception as e:
            self.logger.error(f"設置虛擬環境失敗: {e}")
            return False
    
    async def _install_python_dependencies(self) -> bool:
        """安裝Python依賴包"""
        try:
            self.logger.info("安裝Python依賴包...")
            
            # 優先使用UV
            if self.env_info.uv_available and self.pyproject_file.exists():
                result = await self._run_command([
                    'uv', 'sync'
                ], timeout=600, cwd=str(self.project_root))
                
                if result['returncode'] == 0:
                    self.logger.info("使用UV sync安裝依賴成功")
                    return True
                else:
                    self.logger.warning(f"UV sync失敗: {result['stderr']}")
            
            # 使用pip安裝
            venv_python = self._get_venv_python_path()
            venv_pip = self._get_venv_pip_path()
            
            # 優先嘗試pyproject.toml
            if self.pyproject_file.exists():
                result = await self._run_command([
                    str(venv_pip), 'install', '-e', '.'
                ], timeout=600, cwd=str(self.project_root))
                
                if result['returncode'] == 0:
                    self.logger.info("使用pip install -e .安裝依賴成功")
                    return True
                else:
                    self.logger.warning(f"pip install -e .失敗: {result['stderr']}")
            
            # 使用requirements.txt
            if self.requirements_file.exists():
                result = await self._run_command([
                    str(venv_pip), 'install', '-r', str(self.requirements_file)
                ], timeout=600)
                
                if result['returncode'] == 0:
                    self.logger.info("使用requirements.txt安裝依賴成功")
                    return True
                else:
                    self.logger.error(f"pip install -r requirements.txt失敗: {result['stderr']}")
                    return False
            
            self.logger.error("找不到有效的依賴文件")
            return False
            
        except Exception as e:
            self.logger.error(f"安裝Python依賴包失敗: {e}")
            return False
    
    async def _start_application(self) -> bool:
        """啟動應用程式"""
        try:
            self.logger.info(f"啟動應用程式: {self.main_module}")
            
            venv_python = self._get_venv_python_path()
            main_file = self.project_root / self.main_module
            
            # 檢查主檔案是否存在
            if not main_file.exists():
                self.logger.error(f"主應用程式檔案不存在: {main_file}")
                return False
            
            # 在UV模式下，我們通常不能直接在背景啟動應用程式
            # 因為這會導致部署系統的進程結束
            # 這裡我們只做基本驗證
            
            # 驗證應用程式能否正常導入
            result = await self._run_command([
                str(venv_python), '-c', 
                f"import sys; sys.path.insert(0, '{self.project_root}'); "
                f"try: exec(open('{main_file}').read())\nexcept SystemExit: pass\nexcept KeyboardInterrupt: pass"
            ], timeout=30, cwd=str(self.project_root))
            
            if result['returncode'] in [0, 130]:  # 0=正常, 130=KeyboardInterrupt
                self.logger.info("應用程式驗證成功，準備就緒")
                return True
            else:
                self.logger.error(f"應用程式驗證失敗: {result['stderr']}")
                return False
                
        except Exception as e:
            self.logger.error(f"啟動應用程式失敗: {e}")
            return False
    
    async def _validate_virtual_environment(self) -> bool:
        """驗證虛擬環境是否有效"""
        try:
            venv_python = self._get_venv_python_path()
            if not venv_python.exists():
                return False
                
            result = await self._run_command([str(venv_python), '--version'], timeout=10)
            return result['returncode'] == 0
            
        except Exception:
            return False
    
    async def _remove_virtual_environment(self) -> None:
        """移除虛擬環境"""
        try:
            if self.venv_path.exists():
                import shutil
                shutil.rmtree(str(self.venv_path))
                self.logger.info("已移除舊的虛擬環境")
        except Exception as e:
            self.logger.warning(f"移除虛擬環境失敗: {e}")
    
    async def _cleanup_temp_files(self) -> None:
        """清理臨時檔案"""
        try:
            # 清理Python緩存
            for cache_dir in [self.project_root / '__pycache__']:
                if cache_dir.exists():
                    import shutil
                    shutil.rmtree(str(cache_dir))
            
            # 清理.pyc檔案
            for pyc_file in self.project_root.rglob('*.pyc'):
                try:
                    pyc_file.unlink()
                except Exception:
                    pass
                    
            self.logger.debug("臨時檔案清理完成")
            
        except Exception as e:
            self.logger.debug(f"清理臨時檔案失敗: {e}")
    
    def _get_venv_python_path(self) -> Path:
        """獲取虛擬環境Python執行檔路徑"""
        if os.name == 'posix':  # Unix-like系統
            return self.venv_path / 'bin' / 'python'
        else:  # Windows
            return self.venv_path / 'Scripts' / 'python.exe'
    
    def _get_venv_pip_path(self) -> Path:
        """獲取虛擬環境pip執行檔路徑"""
        if os.name == 'posix':  # Unix-like系統
            return self.venv_path / 'bin' / 'pip'
        else:  # Windows
            return self.venv_path / 'Scripts' / 'pip.exe'
    
    async def _run_command(self, cmd: List[str], timeout: int = 30, cwd: Optional[str] = None) -> Dict[str, Any]:
        """執行系統命令"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                return {
                    'returncode': process.returncode,
                    'stdout': stdout.decode('utf-8', errors='ignore'),
                    'stderr': stderr.decode('utf-8', errors='ignore')
                }
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': f'Command timeout after {timeout}s'
                }
                
        except Exception as e:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            }
    
    def run_application_sync(self) -> Dict[str, Any]:
        """
        同步啟動應用程式（為外部呼叫提供）
        
        Returns:
            啟動結果資訊
        """
        try:
            venv_python = self._get_venv_python_path()
            main_file = self.project_root / self.main_module
            
            if not venv_python.exists():
                return {
                    'success': False,
                    'error': '虛擬環境不存在',
                    'command': None
                }
                
            if not main_file.exists():
                return {
                    'success': False,
                    'error': f'主應用程式檔案不存在: {main_file}',
                    'command': None
                }
            
            command = [str(venv_python), str(main_file)]
            
            return {
                'success': True,
                'command': command,
                'working_directory': str(self.project_root),
                'python_path': str(venv_python),
                'main_file': str(main_file)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': None
            }


class DeploymentOrchestrator:
    """
    部署協調器和降級控制
    
    負責智能選擇部署模式、管理部署流程、處理失敗降級
    實現自動化的Docker到UV降級機制
    """
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger('DeploymentOrchestrator')
        
        # 部署管理器字典
        self.deployment_managers: Dict[DeploymentMode, DeploymentManager] = {}
        
        # 部署狀態追蹤
        self.current_result: Optional[DeploymentResult] = None
        self.deployment_attempts: List[Dict[str, Any]] = []
        
        # 部署優先級設定
        self.deployment_priority = [
            DeploymentMode.DOCKER,      # 首選Docker
            DeploymentMode.UV_PYTHON,   # 備選UV
            DeploymentMode.FALLBACK     # 最後備選
        ]
        
        # 部署配置
        self.deployment_config = {
            'max_retry_attempts': 3,
            'retry_delay_seconds': 5,
            'fallback_enabled': True,
            'health_check_timeout': 120,
            'deployment_timeout': 600  # 10分鐘
        }
    
    async def initialize(self, env_info: EnvironmentInfo) -> None:
        """
        初始化部署協調器
        
        Args:
            env_info: 環境檢測結果
        """
        try:
            self.logger.info("初始化部署協調器...")
            
            # 根據環境資訊初始化部署管理器
            await self._initialize_deployment_managers(env_info)
            
            # 調整部署優先級
            self._adjust_deployment_priority(env_info)
            
            self.logger.info(f"部署協調器初始化完成，可用管理器: {list(self.deployment_managers.keys())}")
            
        except Exception as e:
            self.logger.error(f"初始化部署協調器失敗: {e}")
            raise DeploymentError(
                message="部署協調器初始化失敗",
                deployment_mode="orchestrator",
                details={"error": str(e)},
                cause=e
            )
    
    async def deploy_with_fallback(self, 
                                 preferred_mode: DeploymentMode = DeploymentMode.AUTO,
                                 force_mode: bool = False) -> DeploymentResult:
        """
        智能部署與降級控制
        
        Args:
            preferred_mode: 偏好的部署模式
            force_mode: 是否強制使用指定模式
            
        Returns:
            部署結果
        """
        start_time = datetime.now()
        
        try:
            self.logger.info(f"開始智能部署，偏好模式: {preferred_mode.value}")
            
            # 清理上次部署記錄
            self.deployment_attempts.clear()
            
            # 決定部署順序
            deployment_sequence = self._determine_deployment_sequence(preferred_mode, force_mode)
            
            self.logger.info(f"部署嘗試順序: {[mode.value for mode in deployment_sequence]}")
            
            last_error = None
            
            # 按順序嘗試部署
            for mode in deployment_sequence:
                if mode not in self.deployment_managers:
                    self.logger.warning(f"部署管理器 {mode.value} 不可用，跳過")
                    continue
                
                try:
                    self.logger.info(f"嘗試 {mode.value} 部署...")
                    
                    result = await self._attempt_deployment(mode)
                    
                    if result.status == DeploymentStatus.RUNNING:
                        # 部署成功
                        result.duration = datetime.now() - start_time
                        result.end_time = datetime.now()
                        
                        self.current_result = result
                        self.logger.info(f"{mode.value} 部署成功！")
                        
                        return result
                    elif result.status in [DeploymentStatus.FAILED, DeploymentStatus.DEGRADED]:
                        # 部署失敗，記錄並嘗試下一個
                        last_error = result
                        self.deployment_attempts.append({
                            'mode': mode.value,
                            'status': result.status.value,
                            'error': result.message,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        self.logger.warning(f"{mode.value} 部署失敗: {result.message}")
                        
                        if not self.deployment_config['fallback_enabled'] or force_mode:
                            break
                            
                except Exception as e:
                    error_msg = f"{mode.value} 部署發生異常: {str(e)}"
                    self.logger.error(error_msg)
                    
                    self.deployment_attempts.append({
                        'mode': mode.value,
                        'status': 'exception',
                        'error': error_msg,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    last_error = DeploymentResult(
                        mode=mode,
                        status=DeploymentStatus.FAILED,
                        message=error_msg,
                        start_time=start_time,
                        end_time=datetime.now(),
                        duration=datetime.now() - start_time,
                        error_logs=[str(e)]
                    )
                    
                    if not self.deployment_config['fallback_enabled'] or force_mode:
                        break
            
            # 所有部署嘗試都失敗
            failure_result = DeploymentResult(
                mode=preferred_mode,
                status=DeploymentStatus.FAILED,
                message=f"所有部署模式都失敗",
                details={
                    'attempts': self.deployment_attempts,
                    'last_error': last_error.message if last_error else 'Unknown error',
                    'tried_modes': [attempt['mode'] for attempt in self.deployment_attempts]
                },
                start_time=start_time,
                end_time=datetime.now(),
                duration=datetime.now() - start_time,
                error_logs=[attempt['error'] for attempt in self.deployment_attempts]
            )
            
            self.current_result = failure_result
            return failure_result
            
        except Exception as e:
            self.logger.error(f"部署協調器異常: {e}")
            
            error_result = DeploymentResult(
                mode=preferred_mode,
                status=DeploymentStatus.FAILED,
                message=f"部署協調器異常: {str(e)}",
                start_time=start_time,
                end_time=datetime.now(),
                duration=datetime.now() - start_time,
                error_logs=[str(e)]
            )
            
            self.current_result = error_result
            return error_result
    
    async def _attempt_deployment(self, mode: DeploymentMode) -> DeploymentResult:
        """
        嘗試特定模式的部署
        
        Args:
            mode: 部署模式
            
        Returns:
            部署結果
        """
        start_time = datetime.now()
        manager = self.deployment_managers[mode]
        
        try:
            # 初始化結果
            result = DeploymentResult(
                mode=mode,
                status=DeploymentStatus.PENDING,
                message=f"Starting {mode.value} deployment",
                start_time=start_time
            )
            
            # 檢查依賴
            result.status = DeploymentStatus.INSTALLING
            result.message = f"Checking {mode.value} dependencies"
            
            if not await manager.check_dependencies():
                self.logger.info(f"{mode.value} 依賴不完整，嘗試安裝...")
                
                if not await manager.install_dependencies():
                    return DeploymentResult(
                        mode=mode,
                        status=DeploymentStatus.FAILED,
                        message=f"{mode.value} 依賴安裝失敗",
                        start_time=start_time,
                        end_time=datetime.now(),
                        duration=datetime.now() - start_time
                    )
            
            # 啟動服務
            result.status = DeploymentStatus.STARTING
            result.message = f"Starting {mode.value} services"
            
            if not await manager.start_services():
                return DeploymentResult(
                    mode=mode,
                    status=DeploymentStatus.FAILED,
                    message=f"{mode.value} 服務啟動失敗",
                    start_time=start_time,
                    end_time=datetime.now(),
                    duration=datetime.now() - start_time
                )
            
            # 健康檢查
            result.status = DeploymentStatus.CONFIGURING
            result.message = f"Health checking {mode.value} services"
            
            # 等待服務就緒
            health_check_start = datetime.now()
            timeout = self.deployment_config['health_check_timeout']
            
            while (datetime.now() - health_check_start).seconds < timeout:
                health_info = await manager.health_check()
                
                if health_info.get('status') == 'healthy':
                    # 部署成功
                    result.status = DeploymentStatus.RUNNING
                    result.message = f"{mode.value} deployment successful"
                    result.end_time = datetime.now()
                    result.duration = result.end_time - start_time
                    result.details = health_info
                    
                    return result
                    
                elif health_info.get('status') in ['unhealthy', 'error']:
                    # 健康檢查失敗
                    return DeploymentResult(
                        mode=mode,
                        status=DeploymentStatus.DEGRADED,
                        message=f"{mode.value} health check failed: {health_info.get('error', 'Unknown')}",
                        details=health_info,
                        start_time=start_time,
                        end_time=datetime.now(),
                        duration=datetime.now() - start_time
                    )
                
                # 等待一段時間再檢查
                await asyncio.sleep(5)
            
            # 健康檢查超時
            return DeploymentResult(
                mode=mode,
                status=DeploymentStatus.DEGRADED,
                message=f"{mode.value} health check timeout",
                start_time=start_time,
                end_time=datetime.now(),
                duration=datetime.now() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"{mode.value} 部署嘗試失敗: {e}")
            
            return DeploymentResult(
                mode=mode,
                status=DeploymentStatus.FAILED,
                message=f"{mode.value} deployment failed: {str(e)}",
                start_time=start_time,
                end_time=datetime.now(),
                duration=datetime.now() - start_time,
                error_logs=[str(e)]
            )
    
    async def _initialize_deployment_managers(self, env_info: EnvironmentInfo) -> None:
        """初始化部署管理器"""
        try:
            # 初始化Docker管理器（如果Docker可用）
            if env_info.docker_available:
                try:
                    docker_manager = DockerDeploymentManager(self.config, env_info)
                    self.deployment_managers[DeploymentMode.DOCKER] = docker_manager
                    self.logger.info("初始化Docker部署管理器成功")
                except Exception as e:
                    self.logger.warning(f"初始化Docker部署管理器失敗: {e}")
            
            # 初始化UV管理器（如果Python可用）
            if env_info.python_version:
                try:
                    uv_manager = UVDeploymentManager(self.config, env_info)
                    self.deployment_managers[DeploymentMode.UV_PYTHON] = uv_manager
                    self.logger.info("初始化UV部署管理器成功")
                except Exception as e:
                    self.logger.warning(f"初始化UV部署管理器失敗: {e}")
            
            # TODO: 初始化Fallback管理器（簡單的pip模式）
            # 目前先省略，如果需要可以再實作
            
            if not self.deployment_managers:
                raise EnvironmentError(
                    environment_type="all",
                    check_failed="no_available_managers",
                    details={"message": "沒有可用的部署管理器"}
                )
                
        except Exception as e:
            self.logger.error(f"初始化部署管理器失敗: {e}")
            raise
    
    def _adjust_deployment_priority(self, env_info: EnvironmentInfo) -> None:
        """根據環境調整部署優先級"""
        available_modes = list(self.deployment_managers.keys())
        
        # 根據可用性調整優先級
        if DeploymentMode.DOCKER not in available_modes:
            # 如果Docker不可用，優先使用UV
            self.deployment_priority = [
                mode for mode in self.deployment_priority 
                if mode in available_modes
            ]
        
        self.logger.info(f"調整後的部署優先級: {[mode.value for mode in self.deployment_priority]}")
    
    def _determine_deployment_sequence(self, 
                                     preferred_mode: DeploymentMode,
                                     force_mode: bool) -> List[DeploymentMode]:
        """
        決定部署順序
        
        Args:
            preferred_mode: 偏好模式
            force_mode: 是否強制
            
        Returns:
            部署模式序列
        """
        if force_mode and preferred_mode != DeploymentMode.AUTO:
            # 強制模式，只嘗試指定模式
            return [preferred_mode] if preferred_mode in self.deployment_managers else []
        
        if preferred_mode == DeploymentMode.AUTO:
            # 自動模式，使用預設優先級
            return [mode for mode in self.deployment_priority if mode in self.deployment_managers]
        
        # 偏好模式優先，但允許降級
        sequence = []
        
        if preferred_mode in self.deployment_managers:
            sequence.append(preferred_mode)
        
        # 添加其他可用模式作為備選
        for mode in self.deployment_priority:
            if mode != preferred_mode and mode in self.deployment_managers:
                sequence.append(mode)
        
        return sequence
    
    async def stop_current_deployment(self) -> bool:
        """
        停止當前部署
        
        Returns:
            停止是否成功
        """
        try:
            if not self.current_result:
                self.logger.info("沒有進行中的部署")
                return True
                
            mode = self.current_result.mode
            if mode in self.deployment_managers:
                manager = self.deployment_managers[mode]
                success = await manager.stop_services()
                
                if success:
                    self.current_result.status = DeploymentStatus.STOPPED
                    self.current_result.end_time = datetime.now()
                    self.logger.info(f"{mode.value} 部署已停止")
                
                return success
            
            return True
            
        except Exception as e:
            self.logger.error(f"停止部署失敗: {e}")
            return False
    
    def get_deployment_status(self) -> Optional[DeploymentResult]:
        """獲取當前部署狀態"""
        return self.current_result
    
    def get_deployment_attempts(self) -> List[Dict[str, Any]]:
        """獲取部署嘗試歷史"""
        return self.deployment_attempts.copy()
    
    def get_available_deployment_modes(self) -> List[DeploymentMode]:
        """獲取可用的部署模式"""
        return list(self.deployment_managers.keys())
    
    async def health_check_all_managers(self) -> Dict[str, Any]:
        """
        檢查所有部署管理器的健康狀態
        
        Returns:
            所有管理器的健康狀態
        """
        health_status = {
            'orchestrator': 'healthy',
            'managers': {},
            'summary': {
                'total_managers': len(self.deployment_managers),
                'healthy_managers': 0,
                'unhealthy_managers': 0
            },
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            for mode, manager in self.deployment_managers.items():
                try:
                    manager_health = await manager.health_check()
                    health_status['managers'][mode.value] = manager_health
                    
                    if manager_health.get('status') in ['healthy', 'running']:
                        health_status['summary']['healthy_managers'] += 1
                    else:
                        health_status['summary']['unhealthy_managers'] += 1
                        
                except Exception as e:
                    health_status['managers'][mode.value] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    health_status['summary']['unhealthy_managers'] += 1
            
            # 決定整體狀態
            if health_status['summary']['unhealthy_managers'] == 0:
                health_status['orchestrator'] = 'healthy'
            elif health_status['summary']['healthy_managers'] > 0:
                health_status['orchestrator'] = 'degraded'
            else:
                health_status['orchestrator'] = 'unhealthy'
                
            return health_status
            
        except Exception as e:
            return {
                'orchestrator': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


class DeploymentService(BaseService):
    """
    自動化部署服務主類
    
    整合環境檢測、部署管理、監控等功能
    實現完整的自動化部署和啟動系統
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """初始化部署服務"""
        super().__init__()
        
        # 設置服務元數據
        self.service_metadata = {
            'service_type': ServiceType.DEPLOYMENT,
            'service_name': 'DeploymentService',
            'version': '2.4.4',
            'description': '自動化部署和啟動系統',
            'capabilities': [
                'environment_detection',
                'docker_deployment', 
                'uv_deployment',
                'fallback_deployment',
                'deployment_monitoring'
            ],
            'dependencies': ['ConfigManager', 'DatabaseManager']
        }
        
        self.config = config or get_config()
        self.logger = logging.getLogger('DeploymentService')
        
        # 初始化組件
        self.environment_detector = EnvironmentDetector(self.config)
        self.deployment_managers: Dict[DeploymentMode, DeploymentManager] = {}
        
        # 部署狀態追蹤
        self.current_deployment: Optional[DeploymentResult] = None
        self.deployment_history: List[DeploymentResult] = []
        
        # 監控和統計
        self.start_time = datetime.now()
        self.total_deployments = 0
        self.successful_deployments = 0
    
    async def start(self) -> None:
        """啟動部署服務"""
        try:
            self.logger.info("啟動部署服務...")
            
            # 檢測環境
            env_info = await self.environment_detector.detect_all_environments()
            self.logger.info(f"環境檢測完成: {env_info.platform.value}")
            
            # 初始化部署管理器（稍後實現）
            await self._initialize_deployment_managers(env_info)
            
            # 註冊到服務註冊中心
            await self._register_to_service_registry()
            
            self._initialized = True
            self.logger.info("部署服務啟動成功")
            
        except Exception as e:
            self.logger.error(f"部署服務啟動失敗: {e}")
            raise ServiceStartupError(
                service_name="DeploymentService",
                startup_mode="initialization",
                reason=str(e),
                cause=e
            )
    
    async def stop(self) -> None:
        """停止部署服務"""
        try:
            self.logger.info("停止部署服務...")
            
            # 停止當前部署（如果有）
            if self.current_deployment and self.current_deployment.status in [
                DeploymentStatus.INSTALLING,
                DeploymentStatus.CONFIGURING,
                DeploymentStatus.STARTING
            ]:
                self.logger.info("停止進行中的部署...")
                # 這裡應該實現部署停止邏輯
            
            # 清理資源
            self.deployment_managers.clear()
            self._initialized = False
            
            self.logger.info("部署服務已停止")
            
        except Exception as e:
            self.logger.error(f"停止部署服務失敗: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            health_info = {
                'service_name': 'DeploymentService',
                'status': 'healthy',
                'uptime': str(datetime.now() - self.start_time),
                'total_deployments': self.total_deployments,
                'successful_deployments': self.successful_deployments,
                'success_rate': (self.successful_deployments / max(1, self.total_deployments)) * 100,
                'current_deployment': {
                    'mode': self.current_deployment.mode.value if self.current_deployment else None,
                    'status': self.current_deployment.status.value if self.current_deployment else None
                },
                'available_managers': list(self.deployment_managers.keys()),
                'timestamp': datetime.now().isoformat()
            }
            
            # 檢查環境檢測器狀態
            try:
                env_info = await self.environment_detector.detect_all_environments()
                health_info['environment_detector'] = 'healthy'
                health_info['detected_environment'] = {
                    'platform': env_info.platform.value,
                    'docker_available': env_info.docker_available,
                    'uv_available': env_info.uv_available
                }
            except Exception as e:
                health_info['environment_detector'] = 'unhealthy'
                health_info['environment_error'] = str(e)
                health_info['status'] = 'degraded'
            
            return health_info
            
        except Exception as e:
            return {
                'service_name': 'DeploymentService',
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _initialize_deployment_managers(self, env_info: EnvironmentInfo) -> None:
        """初始化部署管理器"""
        # 這裡將在後續實現具體的部署管理器
        # 目前先創建占位符
        self.logger.info("初始化部署管理器...")
        
        # 稍後將實現:
        # - DockerDeploymentManager
        # - UVDeploymentManager  
        # - FallbackDeploymentManager
        
        pass
    
    async def _register_to_service_registry(self) -> None:
        """註冊到服務註冊中心"""
        try:
            service_name = await extended_service_registry.register_deployment_service(
                service=self,
                deployment_mode="auto",
                name="DeploymentService",
                environment_config=self.config.__dict__,
                auto_restart=True
            )
            
            self.logger.info(f"已註冊到服務註冊中心: {service_name}")
            
        except Exception as e:
            self.logger.error(f"註冊到服務註冊中心失敗: {e}")
            # 不要因為註冊失敗而終止服務啟動
    
    # 部署相關的公共API方法將在後續實現
    async def deploy(self, mode: DeploymentMode = DeploymentMode.AUTO) -> DeploymentResult:
        """執行部署（稍後實現）"""
        pass
    
    async def get_environment_info(self) -> EnvironmentInfo:
        """獲取環境資訊"""
        return await self.environment_detector.detect_all_environments()
    
    async def get_deployment_status(self) -> Optional[DeploymentResult]:
        """獲取當前部署狀態"""
        return self.current_deployment
    
    async def get_deployment_history(self, limit: int = 10) -> List[DeploymentResult]:
        """獲取部署歷史"""
        return self.deployment_history[-limit:] if self.deployment_history else []


class DeploymentService(BaseService):
    """
    自動化部署服務主類
    
    整合環境檢測、部署管理、監控等功能
    實現完整的自動化部署和啟動系統
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """初始化部署服務"""
        super().__init__()
        
        # 設置服務元數據
        self.service_metadata = {
            'service_type': ServiceType.DEPLOYMENT,
            'service_name': 'DeploymentService',
            'version': '2.4.4',
            'description': '自動化部署和啟動系統',
            'capabilities': [
                'environment_detection',
                'docker_deployment', 
                'uv_deployment',
                'fallback_deployment',
                'deployment_orchestration',
                'deployment_monitoring'
            ],
            'dependencies': ['ConfigManager', 'DatabaseManager']
        }
        
        self.config = config or get_config()
        self.logger = logging.getLogger('DeploymentService')
        
        # 初始化組件
        self.environment_detector = EnvironmentDetector(self.config)
        self.deployment_orchestrator = DeploymentOrchestrator(self.config)
        
        # 部署狀態追蹤
        self.current_deployment: Optional[DeploymentResult] = None
        self.deployment_history: List[DeploymentResult] = []
        
        # 監控和統計
        self.start_time = datetime.now()
        self.total_deployments = 0
        self.successful_deployments = 0
        
        # 環境資訊緩存
        self.cached_env_info: Optional[EnvironmentInfo] = None
    
    async def start(self) -> None:
        """啟動部署服務"""
        try:
            self.logger.info("啟動部署服務...")
            
            # 檢測環境
            env_info = await self.environment_detector.detect_all_environments()
            self.cached_env_info = env_info
            self.logger.info(f"環境檢測完成: {env_info.platform.value}")
            
            # 初始化部署協調器
            await self.deployment_orchestrator.initialize(env_info)
            
            # 記錄環境資訊
            self.logger.info(
                f"可用部署模式: {[mode.value for mode in self.deployment_orchestrator.get_available_deployment_modes()]}"
            )
            
            # 記錄環境詳細資訊
            env_summary = self.environment_detector.get_environment_summary(env_info)
            self.logger.info(
                f"環境摘要: Python={env_summary['python_version']}, "
                f"Docker={env_summary['docker_available']}, "
                f"UV={env_summary['uv_available']}, "
                f"推薦模式={env_summary['recommended_mode']}"
            )
            
            # 註冊到服務註冊中心
            await self._register_to_service_registry()
            
            self._initialized = True
            self.logger.info("部署服務啟動成功")
            
        except Exception as e:
            self.logger.error(f"部署服務啟動失敗: {e}")
            raise ServiceStartupError(
                service_name="DeploymentService",
                startup_mode="initialization",
                reason=str(e),
                cause=e
            )
    
    async def stop(self) -> None:
        """停止部署服務"""
        try:
            self.logger.info("停止部署服務...")
            
            # 停止當前部署（如果有）
            if self.current_deployment and self.current_deployment.status in [
                DeploymentStatus.INSTALLING,
                DeploymentStatus.CONFIGURING,
                DeploymentStatus.STARTING
            ]:
                self.logger.info("停止進行中的部署...")
                await self.deployment_orchestrator.stop_current_deployment()
            
            # 清理資源
            self.cached_env_info = None
            self._initialized = False
            
            self.logger.info("部署服務已停止")
            
        except Exception as e:
            self.logger.error(f"停止部署服務失敗: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            health_info = {
                'service_name': 'DeploymentService',
                'status': 'healthy',
                'uptime': str(datetime.now() - self.start_time),
                'total_deployments': self.total_deployments,
                'successful_deployments': self.successful_deployments,
                'success_rate': (self.successful_deployments / max(1, self.total_deployments)) * 100,
                'current_deployment': None,
                'environment_detector': 'unknown',
                'deployment_orchestrator': 'unknown',
                'available_deployment_modes': [],
                'timestamp': datetime.now().isoformat()
            }
            
            # 獲取當前部署狀態
            current_deployment = self.deployment_orchestrator.get_deployment_status()
            if current_deployment:
                health_info['current_deployment'] = {
                    'mode': current_deployment.mode.value,
                    'status': current_deployment.status.value,
                    'message': current_deployment.message
                }
            
            # 檢查環境檢測器狀態
            try:
                env_info = await self.environment_detector.detect_all_environments()
                health_info['environment_detector'] = 'healthy'
                health_info['detected_environment'] = {
                    'platform': env_info.platform.value,
                    'docker_available': env_info.docker_available,
                    'uv_available': env_info.uv_available,
                    'python_version': env_info.python_version
                }
            except Exception as e:
                health_info['environment_detector'] = 'unhealthy'
                health_info['environment_error'] = str(e)
                health_info['status'] = 'degraded'
            
            # 檢查部署協調器狀態
            try:
                orchestrator_health = await self.deployment_orchestrator.health_check_all_managers()
                health_info['deployment_orchestrator'] = orchestrator_health['orchestrator']
                health_info['deployment_managers'] = orchestrator_health['managers']
                health_info['available_deployment_modes'] = [
                    mode.value for mode in self.deployment_orchestrator.get_available_deployment_modes()
                ]
                
                # 整體狀態評估
                if orchestrator_health['orchestrator'] == 'unhealthy':
                    health_info['status'] = 'unhealthy'
                elif orchestrator_health['orchestrator'] == 'degraded':
                    health_info['status'] = 'degraded'
                    
            except Exception as e:
                health_info['deployment_orchestrator'] = 'error'
                health_info['orchestrator_error'] = str(e)
                health_info['status'] = 'degraded'
            
            return health_info
            
        except Exception as e:
            return {
                'service_name': 'DeploymentService',
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _register_to_service_registry(self) -> None:
        """註冊到服務註冊中心"""
        try:
            service_name = await extended_service_registry.register_deployment_service(
                service=self,
                deployment_mode="auto",
                name="DeploymentService",
                environment_config={
                    'available_modes': [mode.value for mode in self.deployment_orchestrator.get_available_deployment_modes()],
                    'config_summary': {
                        'environment': self.config.environment.value,
                        'debug': self.config.debug
                    }
                },
                auto_restart=True
            )
            
            self.logger.info(f"已註冊到服務註冊中心: {service_name}")
            
        except Exception as e:
            self.logger.error(f"註冊到服務註冊中心失敗: {e}")
            # 不要因為註冊失敗而終止服務啟動
    
    # ==========公共API方法==========
    
    async def deploy(self, 
                   mode: DeploymentMode = DeploymentMode.AUTO,
                   force_mode: bool = False) -> DeploymentResult:
        """
        執行部署
        
        Args:
            mode: 部署模式
            force_mode: 是否強制使用指定模式
            
        Returns:
            部署結果
        """
        try:
            self.logger.info(f"開始部署，模式: {mode.value}，強制: {force_mode}")
            
            # 統計計數
            self.total_deployments += 1
            
            # 執行部署
            result = await self.deployment_orchestrator.deploy_with_fallback(mode, force_mode)
            
            # 更新結果
            self.current_deployment = result
            self.deployment_history.append(result)
            
            # 限制歷史記錄數量
            if len(self.deployment_history) > 50:
                self.deployment_history = self.deployment_history[-50:]
            
            # 更新統計
            if result.status == DeploymentStatus.RUNNING:
                self.successful_deployments += 1
                self.logger.info(f"部署成功！模式: {result.mode.value}")
            else:
                self.logger.error(f"部署失敗: {result.message}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"部署失敗: {e}")
            
            # 創建錯誤結果
            error_result = DeploymentResult(
                mode=mode,
                status=DeploymentStatus.FAILED,
                message=f"部署異常: {str(e)}",
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration=timedelta(0),
                error_logs=[str(e)]
            )
            
            self.current_deployment = error_result
            self.deployment_history.append(error_result)
            
            return error_result
    
    async def stop_deployment(self) -> bool:
        """
        停止當前部署
        
        Returns:
            停止是否成功
        """
        try:
            self.logger.info("停止當前部署...")
            
            success = await self.deployment_orchestrator.stop_current_deployment()
            
            if success:
                self.logger.info("部署已停止")
            else:
                self.logger.error("停止部署失敗")
            
            return success
            
        except Exception as e:
            self.logger.error(f"停止部署失敗: {e}")
            return False
    
    async def get_environment_info(self, force_refresh: bool = False) -> EnvironmentInfo:
        """
        獲取環境資訊
        
        Args:
            force_refresh: 是否強制重新檢測
            
        Returns:
            環境資訊
        """
        if force_refresh or not self.cached_env_info:
            self.cached_env_info = await self.environment_detector.detect_all_environments(force_refresh)
        
        return self.cached_env_info
    
    async def get_deployment_status(self) -> Optional[DeploymentResult]:
        """獲取當前部署狀態"""
        return self.deployment_orchestrator.get_deployment_status()
    
    async def get_deployment_history(self, limit: int = 10) -> List[DeploymentResult]:
        """
        獲取部署歷史
        
        Args:
            limit: 返回記錄數量限制
            
        Returns:
            部署歷史記錄
        """
        return self.deployment_history[-limit:] if self.deployment_history else []
    
    def get_available_deployment_modes(self) -> List[DeploymentMode]:
        """獲取可用的部署模式"""
        return self.deployment_orchestrator.get_available_deployment_modes()
    
    def get_deployment_attempts(self) -> List[Dict[str, Any]]:
        """獲取最近一次部署的嘗試歷史"""
        return self.deployment_orchestrator.get_deployment_attempts()
    
    async def install_dependencies(self, target_env: str) -> bool:
        """
        安裝特定環境的依賴
        
        Args:
            target_env: 目標環境 ('docker', 'uv', 'python')
            
        Returns:
            安裝是否成功
        """
        try:
            env_info = await self.get_environment_info()
            return await self.environment_detector.auto_install_dependencies(target_env, env_info)
            
        except Exception as e:
            self.logger.error(f"安裝 {target_env} 依賴失敗: {e}")
            return False
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """
        獲取服務統計資訊
        
        Returns:
            服務統計資訊
        """
        return {
            'service_name': 'DeploymentService',
            'version': '2.4.4',
            'uptime': str(datetime.now() - self.start_time),
            'start_time': self.start_time.isoformat(),
            'total_deployments': self.total_deployments,
            'successful_deployments': self.successful_deployments,
            'failed_deployments': self.total_deployments - self.successful_deployments,
            'success_rate': (self.successful_deployments / max(1, self.total_deployments)) * 100,
            'available_modes': [mode.value for mode in self.get_available_deployment_modes()],
            'deployment_history_size': len(self.deployment_history),
            'current_deployment_active': self.current_deployment is not None,
            'environment_cached': self.cached_env_info is not None,
            'timestamp': datetime.now().isoformat()
        }


# 導出主要類別
__all__ = [
    'DeploymentService',
    'EnvironmentDetector', 
    'DockerDeploymentManager',
    'UVDeploymentManager',
    'DeploymentOrchestrator',
    'DeploymentManager',
    'DeploymentMode',
    'DeploymentStatus',
    'SystemPlatform',
    'EnvironmentInfo',
    'DeploymentResult'
]