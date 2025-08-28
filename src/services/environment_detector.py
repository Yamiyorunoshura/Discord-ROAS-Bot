"""
環境檢測服務
Task ID: 2 - 自動化部署和啟動系統開發

智能環境檢測器，能夠：
- 檢測Docker、Python、UV環境的可用性和版本
- 跨平台系統檢測（Linux、macOS、Windows）
- 權限和依賴檢查
- 環境健康評估和建議
"""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from src.core.errors import EnvironmentError, DependencyInstallError, create_error
from src.core.service_registry import ExtendedServiceRegistry
from core.base_service import BaseService, ServiceType


logger = logging.getLogger('services.environment_detector')


class OperatingSystem(Enum):
    """操作系統枚舉"""
    LINUX = "linux"
    MACOS = "darwin" 
    WINDOWS = "windows"
    UNKNOWN = "unknown"


class EnvironmentType(Enum):
    """環境類型枚舉"""
    DOCKER = "docker"
    UV_PYTHON = "uv_python"
    PYTHON = "python"
    NODE = "node"
    UNKNOWN = "unknown"


class EnvironmentStatus(Enum):
    """環境狀態枚舉"""
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    OUTDATED = "outdated"
    CORRUPTED = "corrupted"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


@dataclass
class SystemInfo:
    """系統信息"""
    os_type: OperatingSystem
    os_version: str
    architecture: str
    python_version: str
    available_memory_gb: float
    available_disk_gb: float
    cpu_cores: int
    is_admin: bool = False
    shell_type: str = "unknown"
    package_managers: List[str] = field(default_factory=list)


@dataclass
class EnvironmentCheckResult:
    """環境檢測結果"""
    env_type: EnvironmentType
    status: EnvironmentStatus
    version: Optional[str] = None
    path: Optional[str] = None
    health_score: float = 0.0  # 0-100分
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    check_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InstallationResult:
    """安裝結果"""
    success: bool
    environment: EnvironmentType
    version_installed: Optional[str] = None
    installation_time: float = 0.0
    install_method: str = "unknown"
    error_message: Optional[str] = None
    post_install_actions: List[str] = field(default_factory=list)


class EnvironmentDetector(BaseService):
    """
    環境檢測器服務
    
    負責檢測和管理各種開發環境的可用性和健康狀態
    """
    
    def __init__(self):
        super().__init__()
        self.service_metadata = {
            'service_type': ServiceType.DEPLOYMENT,
            'service_name': 'environment_detector',
            'version': '2.4.4',
            'capabilities': {
                'docker_detection': True,
                'python_detection': True,
                'uv_detection': True,
                'cross_platform': True,
                'auto_installation': True,
                'health_assessment': True
            }
        }
        
        self.system_info: Optional[SystemInfo] = None
        self.cache_timeout = 300  # 5分鐘緩存
        self._cache: Dict[str, Any] = {}
        self._last_system_scan = None
        
        # 版本需求定義
        self.version_requirements = {
            EnvironmentType.DOCKER: {
                'min_version': '20.10.0',
                'recommended_version': '24.0.0',
                'compose_min_version': '2.0.0'
            },
            EnvironmentType.PYTHON: {
                'min_version': '3.9.0',
                'recommended_version': '3.11.0'
            },
            EnvironmentType.UV_PYTHON: {
                'min_version': '0.1.0',
                'recommended_version': '0.2.0'
            }
        }
        
        # 平台特定的安裝命令
        self.install_commands = {
            OperatingSystem.LINUX: {
                EnvironmentType.DOCKER: [
                    "curl -fsSL https://get.docker.com -o get-docker.sh",
                    "sudo sh get-docker.sh",
                    "sudo usermod -aG docker $USER"
                ],
                EnvironmentType.UV_PYTHON: [
                    "curl -LsSf https://astral.sh/uv/install.sh | sh"
                ]
            },
            OperatingSystem.MACOS: {
                EnvironmentType.DOCKER: [
                    "brew install --cask docker"
                ],
                EnvironmentType.UV_PYTHON: [
                    "curl -LsSf https://astral.sh/uv/install.sh | sh"
                ]
            },
            OperatingSystem.WINDOWS: {
                EnvironmentType.DOCKER: [
                    "powershell -Command \"Invoke-WebRequest -UseBasicParsing -Uri https://get.docker.com/builds/Windows/x86_64/docker-latest.zip -OutFile docker.zip; Expand-Archive docker.zip -DestinationPath $Env:ProgramFiles; [Environment]::SetEnvironmentVariable('Path', $env:Path + ';' + $Env:ProgramFiles + '\\docker', [EnvironmentVariableTarget]::Machine)\""
                ],
                EnvironmentType.UV_PYTHON: [
                    "powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
                ]
            }
        }
    
    async def start(self) -> None:
        """啟動環境檢測服務"""
        try:
            logger.info("啟動環境檢測服務...")
            
            # 執行初始系統掃描
            await self.detect_system_info()
            
            # 執行初始環境掃描
            await self.detect_all_environments()
            
            self.is_initialized = True
            logger.info("環境檢測服務啟動完成")
            
        except Exception as e:
            logger.error(f"環境檢測服務啟動失敗: {e}")
            raise create_error(
                'ServiceStartupError',
                service_name='environment_detector',
                startup_mode='async',
                reason=str(e)
            )
    
    async def stop(self) -> None:
        """停止環境檢測服務"""
        try:
            logger.info("停止環境檢測服務...")
            self._cache.clear()
            self.is_initialized = False
            logger.info("環境檢測服務已停止")
            
        except Exception as e:
            logger.error(f"停止環境檢測服務失敗: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 檢查系統信息是否可用
            if not self.system_info:
                await self.detect_system_info()
            
            # 快速環境檢測
            docker_status = await self._quick_check_docker()
            python_status = await self._quick_check_python()
            uv_status = await self._quick_check_uv()
            
            health_status = "healthy"
            issues = []
            
            if docker_status.status != EnvironmentStatus.AVAILABLE:
                issues.append(f"Docker不可用: {docker_status.status.value}")
            
            if python_status.status != EnvironmentStatus.AVAILABLE:
                issues.append(f"Python不可用: {python_status.status.value}")
            
            if len(issues) >= 2:  # 如果大部分環境都不可用
                health_status = "degraded"
            
            return {
                'service_name': 'environment_detector',
                'status': health_status,
                'system_os': self.system_info.os_type.value if self.system_info else 'unknown',
                'available_environments': {
                    'docker': docker_status.status.value,
                    'python': python_status.status.value,
                    'uv': uv_status.status.value
                },
                'issues': issues,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"環境檢測服務健康檢查失敗: {e}")
            return {
                'service_name': 'environment_detector',
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    # ========== 系統信息檢測 ==========
    
    async def detect_system_info(self, force_refresh: bool = False) -> SystemInfo:
        """
        檢測系統信息
        
        Args:
            force_refresh: 是否強制刷新緩存
        """
        cache_key = 'system_info'
        
        if not force_refresh and cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if (datetime.now() - cached_data['timestamp']).seconds < self.cache_timeout:
                logger.debug("使用緩存的系統信息")
                return cached_data['data']
        
        try:
            logger.info("檢測系統信息...")
            
            # 檢測操作系統
            system_name = platform.system().lower()
            os_type = OperatingSystem.UNKNOWN
            if system_name == 'linux':
                os_type = OperatingSystem.LINUX
            elif system_name == 'darwin':
                os_type = OperatingSystem.MACOS
            elif system_name == 'windows':
                os_type = OperatingSystem.WINDOWS
            
            # 檢測系統版本和架構
            os_version = platform.release()
            architecture = platform.machine()
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            
            # 檢測系統資源
            available_memory_gb = await self._get_available_memory()
            available_disk_gb = await self._get_available_disk()
            cpu_cores = os.cpu_count() or 1
            
            # 檢測管理員權限
            is_admin = await self._check_admin_privileges()
            
            # 檢測shell類型
            shell_type = os.environ.get('SHELL', 'unknown')
            if os.name == 'nt':  # Windows
                shell_type = 'powershell' if 'powershell' in os.environ.get('PSModulePath', '') else 'cmd'
            
            # 檢測包管理器
            package_managers = await self._detect_package_managers(os_type)
            
            system_info = SystemInfo(
                os_type=os_type,
                os_version=os_version,
                architecture=architecture,
                python_version=python_version,
                available_memory_gb=available_memory_gb,
                available_disk_gb=available_disk_gb,
                cpu_cores=cpu_cores,
                is_admin=is_admin,
                shell_type=shell_type,
                package_managers=package_managers
            )
            
            # 緩存結果
            self._cache[cache_key] = {
                'data': system_info,
                'timestamp': datetime.now()
            }
            
            self.system_info = system_info
            self._last_system_scan = datetime.now()
            
            logger.info(f"系統檢測完成: {os_type.value} {os_version} ({architecture})")
            return system_info
            
        except Exception as e:
            logger.error(f"檢測系統信息失敗: {e}")
            raise EnvironmentError(
                environment_type="system",
                check_failed=f"系統信息檢測失敗: {str(e)}"
            )
    
    async def _get_available_memory(self) -> float:
        """獲取可用內存（GB）"""
        try:
            if platform.system() == "Windows":
                import psutil
                return psutil.virtual_memory().available / (1024**3)
            else:
                # Linux/macOS使用free或vm_stat
                result = await self._run_command("free -g | grep '^Mem:' | awk '{print $7}'", shell=True)
                if result.returncode == 0:
                    return float(result.stdout.strip())
                else:
                    # macOS fallback
                    result = await self._run_command("vm_stat | grep 'Pages free' | awk '{print $3}' | sed 's/\\.//'", shell=True)
                    if result.returncode == 0:
                        pages = int(result.stdout.strip())
                        return (pages * 4096) / (1024**3)  # 假設4KB頁面
                    
                    return 4.0  # 默認假設4GB可用
        except Exception as e:
            logger.debug(f"獲取內存信息失敗: {e}")
            return 4.0  # 默認假設
    
    async def _get_available_disk(self) -> float:
        """獲取可用磁盤空間（GB）"""
        try:
            if platform.system() == "Windows":
                import psutil
                return psutil.disk_usage('.').free / (1024**3)
            else:
                result = await self._run_command("df -BG . | tail -1 | awk '{print $4}' | sed 's/G//'", shell=True)
                if result.returncode == 0:
                    return float(result.stdout.strip())
                else:
                    return 10.0  # 默認假設10GB可用
        except Exception as e:
            logger.debug(f"獲取磁盤信息失敗: {e}")
            return 10.0  # 默認假設
    
    async def _check_admin_privileges(self) -> bool:
        """檢查管理員權限"""
        try:
            if platform.system() == "Windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                # Linux/macOS檢查sudo權限
                result = await self._run_command("sudo -n true", shell=True)
                return result.returncode == 0
        except Exception:
            return False
    
    async def _detect_package_managers(self, os_type: OperatingSystem) -> List[str]:
        """檢測可用的包管理器"""
        managers = []
        
        package_manager_commands = {
            OperatingSystem.LINUX: ['apt', 'yum', 'dnf', 'pacman', 'zypper'],
            OperatingSystem.MACOS: ['brew', 'port'],
            OperatingSystem.WINDOWS: ['choco', 'winget', 'scoop']
        }
        
        commands_to_check = package_manager_commands.get(os_type, [])
        
        for cmd in commands_to_check:
            if shutil.which(cmd):
                managers.append(cmd)
        
        return managers
    
    # ========== 環境檢測方法 ==========
    
    async def detect_all_environments(self, force_refresh: bool = False) -> Dict[EnvironmentType, EnvironmentCheckResult]:
        """
        檢測所有支援的環境
        
        Args:
            force_refresh: 是否強制刷新緩存
        """
        cache_key = 'all_environments'
        
        if not force_refresh and cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if (datetime.now() - cached_data['timestamp']).seconds < self.cache_timeout:
                logger.debug("使用緩存的環境檢測結果")
                return cached_data['data']
        
        logger.info("開始全面環境檢測...")
        
        results = {}
        
        # 並行檢測各種環境
        tasks = [
            self.detect_docker(),
            self.detect_python(),
            self.detect_uv()
        ]
        
        try:
            docker_result, python_result, uv_result = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 處理結果，包括異常情況
            if isinstance(docker_result, EnvironmentCheckResult):
                results[EnvironmentType.DOCKER] = docker_result
            else:
                logger.error(f"Docker檢測異常: {docker_result}")
                results[EnvironmentType.DOCKER] = EnvironmentCheckResult(
                    env_type=EnvironmentType.DOCKER,
                    status=EnvironmentStatus.UNKNOWN,
                    issues=[f"檢測異常: {str(docker_result)}"]
                )
            
            if isinstance(python_result, EnvironmentCheckResult):
                results[EnvironmentType.PYTHON] = python_result
            else:
                logger.error(f"Python檢測異常: {python_result}")
                results[EnvironmentType.PYTHON] = EnvironmentCheckResult(
                    env_type=EnvironmentType.PYTHON,
                    status=EnvironmentStatus.UNKNOWN,
                    issues=[f"檢測異常: {str(python_result)}"]
                )
            
            if isinstance(uv_result, EnvironmentCheckResult):
                results[EnvironmentType.UV_PYTHON] = uv_result
            else:
                logger.error(f"UV檢測異常: {uv_result}")
                results[EnvironmentType.UV_PYTHON] = EnvironmentCheckResult(
                    env_type=EnvironmentType.UV_PYTHON,
                    status=EnvironmentStatus.UNKNOWN,
                    issues=[f"檢測異常: {str(uv_result)}"]
                )
            
            # 緩存結果
            self._cache[cache_key] = {
                'data': results,
                'timestamp': datetime.now()
            }
            
            # 日誌報告
            available_envs = [env_type.value for env_type, result in results.items() 
                            if result.status == EnvironmentStatus.AVAILABLE]
            logger.info(f"環境檢測完成，可用環境: {available_envs}")
            
            return results
            
        except Exception as e:
            logger.error(f"環境檢測失敗: {e}")
            raise EnvironmentError(
                environment_type="all",
                check_failed=f"全面環境檢測失敗: {str(e)}"
            )
    
    async def detect_docker(self) -> EnvironmentCheckResult:
        """檢測Docker環境"""
        logger.debug("檢測Docker環境...")
        
        try:
            # 檢查Docker命令是否可用
            docker_path = shutil.which('docker')
            if not docker_path:
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.DOCKER,
                    status=EnvironmentStatus.NOT_FOUND,
                    issues=["Docker命令不存在"],
                    recommendations=["安裝Docker Desktop或Docker Engine"]
                )
            
            # 檢查Docker版本
            version_result = await self._run_command([docker_path, '--version'])
            if version_result.returncode != 0:
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.DOCKER,
                    status=EnvironmentStatus.CORRUPTED,
                    path=docker_path,
                    issues=["Docker命令執行失敗"],
                    recommendations=["重新安裝Docker"]
                )
            
            # 解析版本信息
            version_output = version_result.stdout.strip()
            docker_version = self._extract_version(version_output, r'Docker version (\d+\.\d+\.\d+)')
            
            # 檢查Docker守護程序是否運行
            daemon_result = await self._run_command([docker_path, 'info'])
            if daemon_result.returncode != 0:
                issues = ["Docker守護程序未運行"]
                recommendations = ["啟動Docker Desktop或Docker服務"]
                
                # Windows特殊檢查
                if self.system_info and self.system_info.os_type == OperatingSystem.WINDOWS:
                    recommendations.append("確保Docker Desktop已啟動且正在運行")
                
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.DOCKER,
                    status=EnvironmentStatus.PERMISSION_DENIED,
                    version=docker_version,
                    path=docker_path,
                    issues=issues,
                    recommendations=recommendations,
                    health_score=30.0
                )
            
            # 檢查Docker Compose
            compose_version = None
            compose_result = await self._run_command([docker_path, 'compose', 'version'])
            if compose_result.returncode == 0:
                compose_output = compose_result.stdout.strip()
                compose_version = self._extract_version(compose_output, r'Docker Compose version v?(\d+\.\d+\.\d+)')
            
            # 計算健康分數
            health_score = self._calculate_docker_health_score(
                docker_version, 
                compose_version,
                daemon_result.stdout
            )
            
            # 生成建議
            recommendations = []
            issues = []
            
            if docker_version:
                min_version = self.version_requirements[EnvironmentType.DOCKER]['min_version']
                if not self._is_version_compatible(docker_version, min_version):
                    issues.append(f"Docker版本過舊 (當前: {docker_version}, 需要: >={min_version})")
                    recommendations.append("升級Docker到最新版本")
                    health_score = min(health_score, 60.0)
            
            if not compose_version:
                issues.append("Docker Compose不可用")
                recommendations.append("安裝或啟用Docker Compose")
                health_score = min(health_score, 80.0)
            
            status = EnvironmentStatus.AVAILABLE if health_score >= 70 else EnvironmentStatus.OUTDATED
            
            return EnvironmentCheckResult(
                env_type=EnvironmentType.DOCKER,
                status=status,
                version=docker_version,
                path=docker_path,
                health_score=health_score,
                issues=issues,
                recommendations=recommendations,
                metadata={
                    'compose_version': compose_version,
                    'daemon_info': daemon_result.stdout[:500] if daemon_result.stdout else None
                }
            )
            
        except Exception as e:
            logger.error(f"Docker檢測失敗: {e}")
            return EnvironmentCheckResult(
                env_type=EnvironmentType.DOCKER,
                status=EnvironmentStatus.UNKNOWN,
                issues=[f"檢測異常: {str(e)}"],
                recommendations=["檢查Docker安裝狀態"]
            )
    
    async def detect_python(self) -> EnvironmentCheckResult:
        """檢測Python環境"""
        logger.debug("檢測Python環境...")
        
        try:
            # 使用當前運行的Python
            python_path = sys.executable
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            
            # 檢查Python版本兼容性
            min_version = self.version_requirements[EnvironmentType.PYTHON]['min_version']
            version_compatible = self._is_version_compatible(python_version, min_version)
            
            # 檢查關鍵庫是否可用
            critical_libraries = ['asyncio', 'sqlite3', 'json', 'pathlib']
            missing_libraries = []
            
            for lib in critical_libraries:
                try:
                    __import__(lib)
                except ImportError:
                    missing_libraries.append(lib)
            
            # 檢查pip是否可用
            pip_available = False
            pip_version = None
            try:
                import pip
                pip_available = True
                pip_version = pip.__version__
            except ImportError:
                try:
                    result = await self._run_command([python_path, '-m', 'pip', '--version'])
                    if result.returncode == 0:
                        pip_available = True
                        pip_version = self._extract_version(result.stdout, r'pip (\d+\.\d+\.?\d*)')
                except Exception:
                    pass
            
            # 計算健康分數
            health_score = 100.0
            issues = []
            recommendations = []
            
            if not version_compatible:
                issues.append(f"Python版本不兼容 (當前: {python_version}, 需要: >={min_version})")
                recommendations.append(f"升級Python到 {min_version} 或更高版本")
                health_score -= 40.0
            
            if missing_libraries:
                issues.append(f"缺少關鍵庫: {', '.join(missing_libraries)}")
                recommendations.append("重新安裝Python標準庫")
                health_score -= 20.0
            
            if not pip_available:
                issues.append("pip不可用")
                recommendations.append("安裝pip包管理器")
                health_score -= 30.0
            
            # 檢查虛擬環境支持
            venv_support = True
            try:
                import venv
            except ImportError:
                venv_support = False
                issues.append("venv模組不可用")
                recommendations.append("確保Python完整安裝包含venv模組")
                health_score -= 10.0
            
            status = EnvironmentStatus.AVAILABLE
            if health_score < 60:
                status = EnvironmentStatus.CORRUPTED
            elif health_score < 80:
                status = EnvironmentStatus.OUTDATED
            
            return EnvironmentCheckResult(
                env_type=EnvironmentType.PYTHON,
                status=status,
                version=python_version,
                path=python_path,
                health_score=health_score,
                issues=issues,
                recommendations=recommendations,
                metadata={
                    'pip_version': pip_version,
                    'pip_available': pip_available,
                    'venv_support': venv_support,
                    'missing_libraries': missing_libraries
                }
            )
            
        except Exception as e:
            logger.error(f"Python檢測失敗: {e}")
            return EnvironmentCheckResult(
                env_type=EnvironmentType.PYTHON,
                status=EnvironmentStatus.UNKNOWN,
                issues=[f"檢測異常: {str(e)}"],
                recommendations=["檢查Python安裝狀態"]
            )
    
    async def detect_uv(self) -> EnvironmentCheckResult:
        """檢測UV Python包管理器"""
        logger.debug("檢測UV環境...")
        
        try:
            # 檢查UV命令是否可用
            uv_path = shutil.which('uv')
            if not uv_path:
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.UV_PYTHON,
                    status=EnvironmentStatus.NOT_FOUND,
                    issues=["UV命令不存在"],
                    recommendations=["安裝UV Python包管理器: curl -LsSf https://astral.sh/uv/install.sh | sh"]
                )
            
            # 檢查UV版本
            version_result = await self._run_command([uv_path, '--version'])
            if version_result.returncode != 0:
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.UV_PYTHON,
                    status=EnvironmentStatus.CORRUPTED,
                    path=uv_path,
                    issues=["UV命令執行失敗"],
                    recommendations=["重新安裝UV"]
                )
            
            # 解析版本信息
            version_output = version_result.stdout.strip()
            uv_version = self._extract_version(version_output, r'uv (\d+\.\d+\.?\d*)')
            
            # 檢查UV功能
            help_result = await self._run_command([uv_path, '--help'])
            has_venv_support = 'venv' in help_result.stdout if help_result.returncode == 0 else False
            has_pip_support = 'pip' in help_result.stdout if help_result.returncode == 0 else False
            
            # 計算健康分數
            health_score = 100.0
            issues = []
            recommendations = []
            
            if uv_version:
                min_version = self.version_requirements[EnvironmentType.UV_PYTHON]['min_version']
                if not self._is_version_compatible(uv_version, min_version):
                    issues.append(f"UV版本過舊 (當前: {uv_version}, 建議: >={min_version})")
                    recommendations.append("升級UV到最新版本")
                    health_score -= 20.0
            
            if not has_venv_support:
                issues.append("UV不支援虛擬環境管理")
                recommendations.append("升級UV到支援venv的版本")
                health_score -= 30.0
            
            if not has_pip_support:
                issues.append("UV不支援pip相容模式")
                recommendations.append("升級UV到支援pip的版本")
                health_score -= 20.0
            
            status = EnvironmentStatus.AVAILABLE
            if health_score < 60:
                status = EnvironmentStatus.OUTDATED
            
            return EnvironmentCheckResult(
                env_type=EnvironmentType.UV_PYTHON,
                status=status,
                version=uv_version,
                path=uv_path,
                health_score=health_score,
                issues=issues,
                recommendations=recommendations,
                metadata={
                    'venv_support': has_venv_support,
                    'pip_support': has_pip_support
                }
            )
            
        except Exception as e:
            logger.error(f"UV檢測失敗: {e}")
            return EnvironmentCheckResult(
                env_type=EnvironmentType.UV_PYTHON,
                status=EnvironmentStatus.UNKNOWN,
                issues=[f"檢測異常: {str(e)}"],
                recommendations=["檢查UV安裝狀態"]
            )
    
    # ========== 快速檢查方法（用於健康檢查） ==========
    
    async def _quick_check_docker(self) -> EnvironmentCheckResult:
        """快速Docker檢查"""
        try:
            docker_path = shutil.which('docker')
            if not docker_path:
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.DOCKER,
                    status=EnvironmentStatus.NOT_FOUND
                )
            
            result = await self._run_command([docker_path, 'version', '--format', '{{.Server.Version}}'], timeout=5)
            status = EnvironmentStatus.AVAILABLE if result.returncode == 0 else EnvironmentStatus.PERMISSION_DENIED
            
            return EnvironmentCheckResult(
                env_type=EnvironmentType.DOCKER,
                status=status,
                path=docker_path
            )
        except Exception:
            return EnvironmentCheckResult(
                env_type=EnvironmentType.DOCKER,
                status=EnvironmentStatus.UNKNOWN
            )
    
    async def _quick_check_python(self) -> EnvironmentCheckResult:
        """快速Python檢查"""
        try:
            return EnvironmentCheckResult(
                env_type=EnvironmentType.PYTHON,
                status=EnvironmentStatus.AVAILABLE,
                version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                path=sys.executable,
                health_score=100.0
            )
        except Exception:
            return EnvironmentCheckResult(
                env_type=EnvironmentType.PYTHON,
                status=EnvironmentStatus.UNKNOWN
            )
    
    async def _quick_check_uv(self) -> EnvironmentCheckResult:
        """快速UV檢查"""
        try:
            uv_path = shutil.which('uv')
            if not uv_path:
                return EnvironmentCheckResult(
                    env_type=EnvironmentType.UV_PYTHON,
                    status=EnvironmentStatus.NOT_FOUND
                )
            
            result = await self._run_command([uv_path, '--version'], timeout=3)
            status = EnvironmentStatus.AVAILABLE if result.returncode == 0 else EnvironmentStatus.CORRUPTED
            
            return EnvironmentCheckResult(
                env_type=EnvironmentType.UV_PYTHON,
                status=status,
                path=uv_path
            )
        except Exception:
            return EnvironmentCheckResult(
                env_type=EnvironmentType.UV_PYTHON,
                status=EnvironmentStatus.UNKNOWN
            )
    
    # ========== 自動安裝方法 ==========
    
    async def auto_install_environment(
        self, 
        env_type: EnvironmentType,
        force: bool = False
    ) -> InstallationResult:
        """
        自動安裝指定環境
        
        Args:
            env_type: 環境類型
            force: 是否強制重新安裝
        """
        logger.info(f"開始自動安裝 {env_type.value}...")
        
        start_time = datetime.now()
        
        try:
            # 確保系統信息已加載
            if not self.system_info:
                await self.detect_system_info()
            
            # 檢查是否已安裝
            if not force:
                existing_result = await self._quick_environment_check(env_type)
                if existing_result.status == EnvironmentStatus.AVAILABLE:
                    logger.info(f"{env_type.value} 已安裝且可用，跳過安裝")
                    return InstallationResult(
                        success=True,
                        environment=env_type,
                        version_installed=existing_result.version,
                        installation_time=0.0,
                        install_method="already_installed"
                    )
            
            # 獲取安裝命令
            install_commands = self.install_commands.get(self.system_info.os_type, {}).get(env_type)
            
            if not install_commands:
                raise DependencyInstallError(
                    dependency_name=env_type.value,
                    install_method="auto",
                    reason=f"不支援在 {self.system_info.os_type.value} 上安裝 {env_type.value}"
                )
            
            # 檢查權限需求
            requires_admin = env_type == EnvironmentType.DOCKER and self.system_info.os_type != OperatingSystem.MACOS
            
            if requires_admin and not self.system_info.is_admin:
                raise DependencyInstallError(
                    dependency_name=env_type.value,
                    install_method="auto",
                    reason="需要管理員權限才能安裝"
                )
            
            # 執行安裝命令
            install_method = "script"
            installed_version = None
            
            for i, command in enumerate(install_commands):
                logger.info(f"執行安裝步驟 {i+1}/{len(install_commands)}: {command[:100]}...")
                
                try:
                    if command.startswith('curl') or command.startswith('powershell'):
                        # 使用shell執行
                        result = await self._run_command(command, shell=True, timeout=600)
                    else:
                        # 分割命令並執行
                        cmd_parts = command.split()
                        result = await self._run_command(cmd_parts, timeout=600)
                    
                    if result.returncode != 0:
                        error_msg = f"安裝命令失敗 (退出碼: {result.returncode})"
                        if result.stderr:
                            error_msg += f": {result.stderr[:200]}"
                        
                        raise DependencyInstallError(
                            dependency_name=env_type.value,
                            install_method=install_method,
                            reason=error_msg
                        )
                    
                    logger.info(f"安裝步驟 {i+1} 完成")
                    
                except asyncio.TimeoutError:
                    raise DependencyInstallError(
                        dependency_name=env_type.value,
                        install_method=install_method,
                        reason="安裝超時"
                    )
            
            # 等待安裝生效
            await asyncio.sleep(2)
            
            # 驗證安裝結果
            verification_result = await self._quick_environment_check(env_type)
            
            if verification_result.status != EnvironmentStatus.AVAILABLE:
                raise DependencyInstallError(
                    dependency_name=env_type.value,
                    install_method=install_method,
                    reason=f"安裝後驗證失敗: {verification_result.status.value}"
                )
            
            installed_version = verification_result.version
            installation_time = (datetime.now() - start_time).total_seconds()
            
            # 生成後續行動建議
            post_install_actions = []
            
            if env_type == EnvironmentType.DOCKER:
                post_install_actions.extend([
                    "重新登入或執行 'newgrp docker' 以生效群組權限",
                    "啟動Docker Desktop (如果使用桌面版)",
                    "運行 'docker run hello-world' 測試安裝"
                ])
            elif env_type == EnvironmentType.UV_PYTHON:
                post_install_actions.extend([
                    "重新加載shell配置或重新啟動終端",
                    "運行 'uv --version' 確認安裝",
                    "考慮設置UV配置文件"
                ])
            
            logger.info(f"{env_type.value} 安裝成功，版本: {installed_version}")
            
            return InstallationResult(
                success=True,
                environment=env_type,
                version_installed=installed_version,
                installation_time=installation_time,
                install_method=install_method,
                post_install_actions=post_install_actions
            )
            
        except Exception as e:
            installation_time = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"{env_type.value} 安裝失敗: {e}")
            
            return InstallationResult(
                success=False,
                environment=env_type,
                installation_time=installation_time,
                install_method=install_method,
                error_message=str(e)
            )
    
    async def _quick_environment_check(self, env_type: EnvironmentType) -> EnvironmentCheckResult:
        """快速環境檢查"""
        if env_type == EnvironmentType.DOCKER:
            return await self._quick_check_docker()
        elif env_type == EnvironmentType.PYTHON:
            return await self._quick_check_python()
        elif env_type == EnvironmentType.UV_PYTHON:
            return await self._quick_check_uv()
        else:
            return EnvironmentCheckResult(
                env_type=env_type,
                status=EnvironmentStatus.UNKNOWN
            )
    
    # ========== 工具方法 ==========
    
    async def _run_command(
        self,
        command: Union[str, List[str]],
        shell: bool = False,
        timeout: int = 30,
        cwd: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        """
        異步運行命令
        
        Args:
            command: 命令字符串或命令列表
            shell: 是否使用shell
            timeout: 超時秒數
            cwd: 工作目錄
        """
        try:
            if isinstance(command, str) and not shell:
                command = command.split()
            
            process = await asyncio.create_subprocess_exec(
                *command if isinstance(command, list) else command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=shell,
                cwd=cwd
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8', errors='ignore'),
                stderr=stderr.decode('utf-8', errors='ignore')
            )
            
        except asyncio.TimeoutError:
            logger.error(f"命令執行超時: {command}")
            raise
        except Exception as e:
            logger.error(f"命令執行異常: {command}, 錯誤: {e}")
            raise
    
    def _extract_version(self, text: str, pattern: str) -> Optional[str]:
        """從文本中提取版本號"""
        import re
        
        match = re.search(pattern, text)
        return match.group(1) if match else None
    
    def _is_version_compatible(self, current: str, minimum: str) -> bool:
        """檢查版本兼容性"""
        try:
            def parse_version(v):
                return tuple(map(int, v.split('.')))
            
            current_tuple = parse_version(current)
            minimum_tuple = parse_version(minimum)
            
            return current_tuple >= minimum_tuple
        except Exception:
            return False
    
    def _calculate_docker_health_score(
        self, 
        docker_version: Optional[str], 
        compose_version: Optional[str],
        daemon_info: str
    ) -> float:
        """計算Docker健康分數"""
        score = 100.0
        
        # 版本檢查
        if not docker_version:
            score -= 50.0
        elif not self._is_version_compatible(docker_version, self.version_requirements[EnvironmentType.DOCKER]['min_version']):
            score -= 30.0
        
        if not compose_version:
            score -= 20.0
        elif not self._is_version_compatible(compose_version, self.version_requirements[EnvironmentType.DOCKER]['compose_min_version']):
            score -= 10.0
        
        # 守護程序健康檢查
        if daemon_info:
            if 'WARNING' in daemon_info.upper():
                score -= 10.0
            if 'ERROR' in daemon_info.upper():
                score -= 20.0
        
        return max(0.0, score)
    
    # ========== 公開API方法 ==========
    
    async def get_deployment_recommendations(self) -> Dict[str, Any]:
        """
        獲取部署建議
        
        基於當前環境狀態提供最佳部署策略建議
        """
        try:
            # 獲取所有環境狀態
            environments = await self.detect_all_environments()
            
            # 評估部署選項
            deployment_options = []
            
            docker_result = environments.get(EnvironmentType.DOCKER)
            if docker_result and docker_result.status == EnvironmentStatus.AVAILABLE:
                deployment_options.append({
                    'method': 'docker',
                    'priority': 1,
                    'confidence': docker_result.health_score,
                    'description': 'Docker容器化部署（推薦）',
                    'requirements_met': True,
                    'estimated_setup_time': '2-5分鐘',
                    'advantages': [
                        '隔離性好',
                        '依賴管理簡單',
                        '跨平台一致性',
                        '易於維護和更新'
                    ]
                })
            else:
                deployment_options.append({
                    'method': 'docker',
                    'priority': 3,
                    'confidence': 0.0,
                    'description': 'Docker容器化部署（需要安裝）',
                    'requirements_met': False,
                    'estimated_setup_time': '5-15分鐘',
                    'blocking_issues': docker_result.issues if docker_result else ['Docker未安裝'],
                    'installation_needed': True
                })
            
            uv_result = environments.get(EnvironmentType.UV_PYTHON)
            python_result = environments.get(EnvironmentType.PYTHON)
            
            if (uv_result and uv_result.status == EnvironmentStatus.AVAILABLE and
                python_result and python_result.status == EnvironmentStatus.AVAILABLE):
                deployment_options.append({
                    'method': 'uv_python',
                    'priority': 2,
                    'confidence': min(uv_result.health_score, python_result.health_score),
                    'description': 'UV Python虛擬環境部署',
                    'requirements_met': True,
                    'estimated_setup_time': '1-3分鐘',
                    'advantages': [
                        '啟動快速',
                        '資源使用少',
                        '直接訪問系統資源',
                        '調試方便'
                    ]
                })
            else:
                missing = []
                if not (uv_result and uv_result.status == EnvironmentStatus.AVAILABLE):
                    missing.append('UV')
                if not (python_result and python_result.status == EnvironmentStatus.AVAILABLE):
                    missing.append('Python')
                
                deployment_options.append({
                    'method': 'uv_python',
                    'priority': 4,
                    'confidence': 0.0,
                    'description': 'UV Python虛擬環境部署（需要安裝）',
                    'requirements_met': False,
                    'estimated_setup_time': '3-10分鐘',
                    'blocking_issues': [f"缺少: {', '.join(missing)}"],
                    'installation_needed': True
                })
            
            # 排序部署選項
            deployment_options.sort(key=lambda x: (x['requirements_met'], -x['priority'], -x['confidence']), reverse=True)
            
            # 生成總體建議
            recommended_method = deployment_options[0] if deployment_options else None
            
            system_summary = "系統摘要：\n"
            if self.system_info:
                system_summary += f"- 作業系統: {self.system_info.os_type.value} {self.system_info.os_version}\n"
                system_summary += f"- 架構: {self.system_info.architecture}\n"
                system_summary += f"- 可用記憶體: {self.system_info.available_memory_gb:.1f}GB\n"
                system_summary += f"- Python版本: {self.system_info.python_version}\n"
            
            return {
                'system_info': self.system_info.__dict__ if self.system_info else {},
                'environment_status': {
                    env_type.value: {
                        'status': result.status.value,
                        'version': result.version,
                        'health_score': result.health_score,
                        'issues': result.issues
                    }
                    for env_type, result in environments.items()
                },
                'deployment_options': deployment_options,
                'recommended_method': recommended_method['method'] if recommended_method else None,
                'system_summary': system_summary,
                'next_steps': self._generate_next_steps(deployment_options, environments),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"生成部署建議失敗: {e}")
            raise EnvironmentError(
                environment_type="deployment_planning",
                check_failed=f"部署建議生成失敗: {str(e)}"
            )
    
    def _generate_next_steps(
        self, 
        deployment_options: List[Dict[str, Any]], 
        environments: Dict[EnvironmentType, EnvironmentCheckResult]
    ) -> List[str]:
        """生成下一步建議"""
        steps = []
        
        # 尋找最佳可用選項
        best_available = None
        for option in deployment_options:
            if option['requirements_met']:
                best_available = option
                break
        
        if best_available:
            method = best_available['method']
            if method == 'docker':
                steps.extend([
                    "運行 'bash scripts/start.sh' 啟動Docker部署",
                    "等待容器構建和啟動完成",
                    "檢查服務健康狀態"
                ])
            elif method == 'uv_python':
                steps.extend([
                    "運行降級模式部署腳本",
                    "等待虛擬環境創建和依賴安裝",
                    "啟動Python應用程序"
                ])
        else:
            # 沒有可用選項，建議安裝
            docker_result = environments.get(EnvironmentType.DOCKER)
            if not docker_result or docker_result.status != EnvironmentStatus.AVAILABLE:
                steps.append("安裝Docker: 運行 'bash scripts/auto_install.sh docker'")
            
            uv_result = environments.get(EnvironmentType.UV_PYTHON)
            if not uv_result or uv_result.status != EnvironmentStatus.AVAILABLE:
                steps.append("安裝UV: 運行 'bash scripts/auto_install.sh uv'")
            
            steps.append("重新運行環境檢測")
        
        return steps
    
    async def generate_environment_report(self) -> str:
        """生成環境檢測報告"""
        try:
            # 獲取所有檢測結果
            system_info = await self.detect_system_info()
            environments = await self.detect_all_environments()
            recommendations = await self.get_deployment_recommendations()
            
            report = []
            report.append("=" * 60)
            report.append("ROAS Bot v2.4.4 環境檢測報告")
            report.append("=" * 60)
            report.append(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # 系統信息
            report.append("系統信息:")
            report.append("-" * 20)
            report.append(f"操作系統: {system_info.os_type.value} {system_info.os_version}")
            report.append(f"架構: {system_info.architecture}")
            report.append(f"CPU核心: {system_info.cpu_cores}")
            report.append(f"可用記憶體: {system_info.available_memory_gb:.1f} GB")
            report.append(f"可用磁碟: {system_info.available_disk_gb:.1f} GB")
            report.append(f"Python版本: {system_info.python_version}")
            report.append(f"管理員權限: {'是' if system_info.is_admin else '否'}")
            if system_info.package_managers:
                report.append(f"包管理器: {', '.join(system_info.package_managers)}")
            report.append("")
            
            # 環境檢測結果
            report.append("環境檢測結果:")
            report.append("-" * 20)
            
            for env_type, result in environments.items():
                status_icon = {
                    EnvironmentStatus.AVAILABLE: "✅",
                    EnvironmentStatus.NOT_FOUND: "❌", 
                    EnvironmentStatus.OUTDATED: "⚠️",
                    EnvironmentStatus.CORRUPTED: "🔴",
                    EnvironmentStatus.PERMISSION_DENIED: "🚫",
                    EnvironmentStatus.UNKNOWN: "❓"
                }.get(result.status, "❓")
                
                report.append(f"{status_icon} {env_type.value.upper()}:")
                report.append(f"   狀態: {result.status.value}")
                if result.version:
                    report.append(f"   版本: {result.version}")
                if result.path:
                    report.append(f"   路徑: {result.path}")
                if result.health_score > 0:
                    report.append(f"   健康分數: {result.health_score:.1f}/100")
                
                if result.issues:
                    report.append("   問題:")
                    for issue in result.issues:
                        report.append(f"     - {issue}")
                
                if result.recommendations:
                    report.append("   建議:")
                    for rec in result.recommendations:
                        report.append(f"     - {rec}")
                report.append("")
            
            # 部署建議
            report.append("部署建議:")
            report.append("-" * 20)
            
            recommended = recommendations.get('recommended_method')
            if recommended:
                report.append(f"推薦部署方式: {recommended}")
            
            for option in recommendations.get('deployment_options', []):
                priority_icon = "🥇" if option['priority'] == 1 else "🥈" if option['priority'] == 2 else "🥉"
                available_icon = "✅" if option['requirements_met'] else "❌"
                
                report.append(f"{priority_icon} {available_icon} {option['description']}")
                report.append(f"   預估設置時間: {option['estimated_setup_time']}")
                if 'advantages' in option:
                    report.append("   優勢:")
                    for adv in option['advantages']:
                        report.append(f"     + {adv}")
                if 'blocking_issues' in option:
                    report.append("   阻塞問題:")
                    for issue in option['blocking_issues']:
                        report.append(f"     - {issue}")
                report.append("")
            
            # 下一步行動
            next_steps = recommendations.get('next_steps', [])
            if next_steps:
                report.append("建議行動:")
                report.append("-" * 20)
                for i, step in enumerate(next_steps, 1):
                    report.append(f"{i}. {step}")
                report.append("")
            
            report.append("=" * 60)
            report.append("報告結束")
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"生成環境報告失敗: {e}")
            return f"環境報告生成失敗: {str(e)}"