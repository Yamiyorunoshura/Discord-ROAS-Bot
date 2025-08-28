"""
權限管理和跨平台相容性處理服務
Task ID: 2 - 自動化部署和啟動系統開發

Daniel - DevOps 專家
提供跨平台的權限檢測、管理和相容性處理機制
支援 Linux、macOS、Windows 的不同權限模型
"""

import os
import platform
import subprocess
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

from core.base_service import BaseService, ServiceType
from src.core.errors import EnvironmentError, create_error


logger = logging.getLogger('services.permission_manager')


class PermissionLevel(Enum):
    """權限級別枚舉"""
    NONE = "none"           # 無權限
    READ = "read"           # 讀取權限
    WRITE = "write"         # 寫入權限
    EXECUTE = "execute"     # 執行權限
    ADMIN = "admin"         # 管理員權限
    SUDO = "sudo"           # Sudo 權限
    ROOT = "root"           # Root 權限


class PlatformType(Enum):
    """平台類型枚舉"""
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    WSL = "wsl"
    UNKNOWN = "unknown"


@dataclass
class PermissionInfo:
    """權限信息"""
    has_permission: bool
    level: PermissionLevel
    method: str = ""  # 獲取權限的方法
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class SystemCompatibility:
    """系統相容性信息"""
    platform: PlatformType
    os_version: str
    architecture: str
    shell_type: str
    package_managers: List[str] = field(default_factory=list)
    compatibility_issues: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)


class PermissionManager(BaseService):
    """
    權限管理器
    
    提供跨平台的權限檢測、管理和相容性處理
    """
    
    def __init__(self):
        super().__init__()
        
        self.service_metadata = {
            'service_type': ServiceType.UTILITY,
            'service_name': 'permission_manager',
            'version': '2.4.4',
            'capabilities': {
                'cross_platform_permissions': True,
                'privilege_elevation': True,
                'compatibility_checking': True,
                'automated_fixes': True,
                'security_validation': True
            }
        }
        
        # 檢測平台信息
        self.platform_info = self._detect_platform()
        self.current_user_info = self._get_current_user_info()
        
        # 權限快取
        self.permission_cache: Dict[str, PermissionInfo] = {}
        self.compatibility_cache: Optional[SystemCompatibility] = None
        
    async def start(self) -> None:
        """啟動權限管理服務"""
        try:
            logger.info("啟動權限管理服務...")
            
            # 檢測系統相容性
            self.compatibility_cache = await self._check_system_compatibility()
            
            # 檢測基本權限
            await self._initialize_permission_cache()
            
            self.is_initialized = True
            logger.info("權限管理服務啟動完成")
            
        except Exception as e:
            logger.error(f"權限管理服務啟動失敗: {e}")
            raise
    
    async def stop(self) -> None:
        """停止權限管理服務"""
        try:
            logger.info("停止權限管理服務...")
            self.permission_cache.clear()
            self.compatibility_cache = None
            self.is_initialized = False
            logger.info("權限管理服務已停止")
        except Exception as e:
            logger.error(f"停止權限管理服務失敗: {e}")
    
    # ========== 權限檢測方法 ==========
    
    async def check_permission(
        self, 
        permission_type: str,
        target_path: Optional[str] = None,
        use_cache: bool = True
    ) -> PermissionInfo:
        """
        檢查權限
        
        Args:
            permission_type: 權限類型 (admin, sudo, write, execute等)
            target_path: 目標路徑（可選）
            use_cache: 是否使用快取
            
        Returns:
            權限信息
        """
        try:
            cache_key = f"{permission_type}:{target_path or 'global'}"
            
            # 檢查快取
            if use_cache and cache_key in self.permission_cache:
                return self.permission_cache[cache_key]
            
            # 根據權限類型檢查
            if permission_type == 'admin':
                perm_info = await self._check_admin_permission()
            elif permission_type == 'sudo':
                perm_info = await self._check_sudo_permission()
            elif permission_type == 'write' and target_path:
                perm_info = await self._check_write_permission(target_path)
            elif permission_type == 'execute' and target_path:
                perm_info = await self._check_execute_permission(target_path)
            elif permission_type == 'docker':
                perm_info = await self._check_docker_permission()
            else:
                perm_info = PermissionInfo(
                    has_permission=False,
                    level=PermissionLevel.NONE,
                    error_message=f"不支援的權限類型: {permission_type}"
                )
            
            # 快取結果
            if use_cache:
                self.permission_cache[cache_key] = perm_info
            
            return perm_info
            
        except Exception as e:
            logger.error(f"權限檢查失敗: {e}")
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message=str(e)
            )
    
    async def request_elevation(
        self, 
        command: List[str],
        reason: str = "執行系統操作"
    ) -> Tuple[bool, str]:
        """
        請求權限提升
        
        Args:
            command: 要執行的命令
            reason: 請求原因
            
        Returns:
            (成功標誌, 輸出訊息)
        """
        try:
            logger.info(f"請求權限提升執行命令: {' '.join(command)}")
            logger.info(f"原因: {reason}")
            
            if self.platform_info == PlatformType.WINDOWS:
                return await self._request_windows_elevation(command, reason)
            else:
                return await self._request_unix_elevation(command, reason)
                
        except Exception as e:
            logger.error(f"權限提升請求失敗: {e}")
            return False, str(e)
    
    async def fix_permission_issues(
        self, 
        target_path: str,
        required_permissions: List[str]
    ) -> Dict[str, bool]:
        """
        修復權限問題
        
        Args:
            target_path: 目標路徑
            required_permissions: 需要的權限列表
            
        Returns:
            修復結果字典
        """
        try:
            logger.info(f"修復路徑權限: {target_path}")
            
            results = {}
            
            for permission in required_permissions:
                try:
                    if permission == 'write':
                        success = await self._fix_write_permission(target_path)
                    elif permission == 'execute':
                        success = await self._fix_execute_permission(target_path)
                    elif permission == 'read':
                        success = await self._fix_read_permission(target_path)
                    else:
                        success = False
                        logger.warning(f"不支援修復權限類型: {permission}")
                    
                    results[permission] = success
                    
                except Exception as e:
                    logger.error(f"修復 {permission} 權限失敗: {e}")
                    results[permission] = False
            
            return results
            
        except Exception as e:
            logger.error(f"修復權限問題失敗: {e}")
            return {perm: False for perm in required_permissions}
    
    # ========== 相容性檢查方法 ==========
    
    async def get_system_compatibility(self) -> SystemCompatibility:
        """獲取系統相容性信息"""
        if self.compatibility_cache is None:
            self.compatibility_cache = await self._check_system_compatibility()
        return self.compatibility_cache
    
    async def check_command_availability(self, commands: List[str]) -> Dict[str, bool]:
        """檢查命令可用性"""
        try:
            results = {}
            
            for command in commands:
                try:
                    if self.platform_info == PlatformType.WINDOWS:
                        # Windows 使用 where 命令
                        result = subprocess.run(
                            ['where', command],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        results[command] = result.returncode == 0
                    else:
                        # Unix 系統使用 which 命令
                        result = subprocess.run(
                            ['which', command],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        results[command] = result.returncode == 0
                        
                except Exception as e:
                    logger.debug(f"檢查命令 {command} 可用性失敗: {e}")
                    results[command] = False
            
            return results
            
        except Exception as e:
            logger.error(f"檢查命令可用性失敗: {e}")
            return {cmd: False for cmd in commands}
    
    async def suggest_compatibility_fixes(self) -> List[Dict[str, Any]]:
        """建議相容性修復方案"""
        try:
            compatibility = await self.get_system_compatibility()
            suggestions = []
            
            # 檢查各種相容性問題並提供建議
            for issue in compatibility.compatibility_issues:
                if "package manager" in issue.lower():
                    suggestions.append({
                        'issue': issue,
                        'category': 'package_manager',
                        'priority': 'high',
                        'solutions': await self._suggest_package_manager_solutions()
                    })
                elif "docker" in issue.lower():
                    suggestions.append({
                        'issue': issue,
                        'category': 'docker',
                        'priority': 'medium',
                        'solutions': await self._suggest_docker_solutions()
                    })
                elif "python" in issue.lower():
                    suggestions.append({
                        'issue': issue,
                        'category': 'python',
                        'priority': 'high',
                        'solutions': await self._suggest_python_solutions()
                    })
                elif "permission" in issue.lower():
                    suggestions.append({
                        'issue': issue,
                        'category': 'permission',
                        'priority': 'critical',
                        'solutions': await self._suggest_permission_solutions()
                    })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"建議相容性修復方案失敗: {e}")
            return []
    
    # ========== 內部方法 ==========
    
    def _detect_platform(self) -> PlatformType:
        """檢測平台類型"""
        try:
            system = platform.system().lower()
            
            if system == 'linux':
                # 檢查是否為 WSL
                if 'microsoft' in platform.release().lower() or os.path.exists('/proc/version'):
                    try:
                        with open('/proc/version', 'r') as f:
                            version_info = f.read().lower()
                            if 'microsoft' in version_info or 'wsl' in version_info:
                                return PlatformType.WSL
                    except:
                        pass
                return PlatformType.LINUX
            elif system == 'darwin':
                return PlatformType.MACOS
            elif system == 'windows':
                return PlatformType.WINDOWS
            else:
                return PlatformType.UNKNOWN
                
        except Exception as e:
            logger.error(f"檢測平台類型失敗: {e}")
            return PlatformType.UNKNOWN
    
    def _get_current_user_info(self) -> Dict[str, Any]:
        """獲取當前用戶信息"""
        try:
            user_info = {
                'username': os.getenv('USER') or os.getenv('USERNAME', 'unknown'),
                'uid': os.getuid() if hasattr(os, 'getuid') else None,
                'gid': os.getgid() if hasattr(os, 'getgid') else None,
                'home_dir': os.path.expanduser('~'),
                'is_root': False
            }
            
            # 檢查是否為 root 用戶
            if hasattr(os, 'getuid'):
                user_info['is_root'] = os.getuid() == 0
            elif self.platform_info == PlatformType.WINDOWS:
                # Windows 管理員檢查
                try:
                    import ctypes
                    user_info['is_root'] = ctypes.windll.shell32.IsUserAnAdmin()
                except:
                    user_info['is_root'] = False
            
            return user_info
            
        except Exception as e:
            logger.error(f"獲取用戶信息失敗: {e}")
            return {'username': 'unknown', 'is_root': False}
    
    async def _check_admin_permission(self) -> PermissionInfo:
        """檢查管理員權限"""
        try:
            if self.platform_info == PlatformType.WINDOWS:
                # Windows 管理員檢查
                try:
                    import ctypes
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                    return PermissionInfo(
                        has_permission=is_admin,
                        level=PermissionLevel.ADMIN if is_admin else PermissionLevel.NONE,
                        method="Windows UAC",
                        details={'is_elevated': is_admin}
                    )
                except ImportError:
                    return PermissionInfo(
                        has_permission=False,
                        level=PermissionLevel.NONE,
                        error_message="無法檢查 Windows 管理員權限"
                    )
            else:
                # Unix 系統 root 檢查
                is_root = os.getuid() == 0 if hasattr(os, 'getuid') else False
                return PermissionInfo(
                    has_permission=is_root,
                    level=PermissionLevel.ROOT if is_root else PermissionLevel.NONE,
                    method="Unix UID check",
                    details={'uid': os.getuid() if hasattr(os, 'getuid') else None}
                )
                
        except Exception as e:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message=str(e)
            )
    
    async def _check_sudo_permission(self) -> PermissionInfo:
        """檢查 sudo 權限"""
        try:
            if self.platform_info == PlatformType.WINDOWS:
                # Windows 沒有 sudo，檢查管理員權限
                return await self._check_admin_permission()
            
            # Unix 系統檢查 sudo
            try:
                result = subprocess.run(
                    ['sudo', '-n', 'true'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                has_sudo = result.returncode == 0
                return PermissionInfo(
                    has_permission=has_sudo,
                    level=PermissionLevel.SUDO if has_sudo else PermissionLevel.NONE,
                    method="sudo -n test",
                    details={'returncode': result.returncode}
                )
                
            except subprocess.TimeoutExpired:
                return PermissionInfo(
                    has_permission=False,
                    level=PermissionLevel.NONE,
                    error_message="sudo 檢查超時"
                )
            except FileNotFoundError:
                return PermissionInfo(
                    has_permission=False,
                    level=PermissionLevel.NONE,
                    error_message="sudo 命令不存在"
                )
                
        except Exception as e:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message=str(e)
            )
    
    async def _check_write_permission(self, path: str) -> PermissionInfo:
        """檢查寫入權限"""
        try:
            target_path = Path(path)
            
            # 如果路徑不存在，檢查父目錄
            if not target_path.exists():
                target_path = target_path.parent
                while not target_path.exists() and target_path != target_path.parent:
                    target_path = target_path.parent
            
            # 檢查權限
            has_write = os.access(target_path, os.W_OK)
            
            return PermissionInfo(
                has_permission=has_write,
                level=PermissionLevel.WRITE if has_write else PermissionLevel.READ,
                method="os.access",
                details={'path': str(target_path), 'exists': target_path.exists()}
            )
            
        except Exception as e:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message=str(e)
            )
    
    async def _check_execute_permission(self, path: str) -> PermissionInfo:
        """檢查執行權限"""
        try:
            target_path = Path(path)
            
            if not target_path.exists():
                return PermissionInfo(
                    has_permission=False,
                    level=PermissionLevel.NONE,
                    error_message=f"路徑不存在: {path}"
                )
            
            has_execute = os.access(target_path, os.X_OK)
            
            return PermissionInfo(
                has_permission=has_execute,
                level=PermissionLevel.EXECUTE if has_execute else PermissionLevel.READ,
                method="os.access",
                details={'path': str(target_path), 'is_file': target_path.is_file()}
            )
            
        except Exception as e:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message=str(e)
            )
    
    async def _check_docker_permission(self) -> PermissionInfo:
        """檢查 Docker 權限"""
        try:
            # 檢查 Docker 是否可用
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            has_permission = result.returncode == 0
            
            if not has_permission and "permission denied" in result.stderr.lower():
                return PermissionInfo(
                    has_permission=False,
                    level=PermissionLevel.NONE,
                    method="docker info",
                    error_message="Docker 權限不足，可能需要加入 docker 群組或使用 sudo",
                    details={'stderr': result.stderr}
                )
            
            return PermissionInfo(
                has_permission=has_permission,
                level=PermissionLevel.EXECUTE if has_permission else PermissionLevel.NONE,
                method="docker info",
                details={'returncode': result.returncode}
            )
            
        except FileNotFoundError:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message="Docker 未安裝"
            )
        except subprocess.TimeoutExpired:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message="Docker 檢查超時"
            )
        except Exception as e:
            return PermissionInfo(
                has_permission=False,
                level=PermissionLevel.NONE,
                error_message=str(e)
            )
    
    async def _check_system_compatibility(self) -> SystemCompatibility:
        """檢查系統相容性"""
        try:
            # 基本系統信息
            os_version = platform.platform()
            architecture = platform.machine()
            shell_type = os.getenv('SHELL', 'unknown').split('/')[-1]
            
            # 檢查套件管理器
            package_managers = []
            pm_commands = {
                'apt': 'apt --version',
                'yum': 'yum --version', 
                'dnf': 'dnf --version',
                'pacman': 'pacman --version',
                'brew': 'brew --version',
                'choco': 'choco --version',
                'scoop': 'scoop --version',
                'winget': 'winget --version'
            }
            
            available_commands = await self.check_command_availability(list(pm_commands.keys()))
            package_managers = [pm for pm, available in available_commands.items() if available]
            
            # 檢查相容性問題
            compatibility_issues = []
            recommended_actions = []
            
            # 平台特定檢查
            if self.platform_info == PlatformType.WINDOWS:
                if not package_managers:
                    compatibility_issues.append("沒有找到套件管理器 (chocolatey, scoop, winget)")
                    recommended_actions.append("安裝 Chocolatey 或 Scoop 套件管理器")
                
                # 檢查 WSL 可用性
                wsl_available = await self.check_command_availability(['wsl'])
                if not wsl_available['wsl']:
                    recommended_actions.append("考慮啟用 WSL 以獲得更好的開發體驗")
            
            elif self.platform_info in [PlatformType.LINUX, PlatformType.WSL]:
                if not package_managers:
                    compatibility_issues.append("沒有找到套件管理器")
                    recommended_actions.append("安裝適當的套件管理器")
                
                # 檢查基本工具
                essential_tools = await self.check_command_availability(['curl', 'wget', 'git', 'sudo'])
                for tool, available in essential_tools.items():
                    if not available:
                        compatibility_issues.append(f"缺少基本工具: {tool}")
                        recommended_actions.append(f"安裝 {tool}")
            
            elif self.platform_info == PlatformType.MACOS:
                if 'brew' not in package_managers:
                    compatibility_issues.append("沒有找到 Homebrew 套件管理器")
                    recommended_actions.append("安裝 Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            
            # 權限相關檢查
            admin_perm = await self.check_permission('admin')
            if not admin_perm.has_permission:
                sudo_perm = await self.check_permission('sudo')
                if not sudo_perm.has_permission:
                    compatibility_issues.append("缺少管理員權限或 sudo 權限")
                    if self.platform_info == PlatformType.WINDOWS:
                        recommended_actions.append("以管理員身分執行")
                    else:
                        recommended_actions.append("設置 sudo 權限或使用 root 用戶")
            
            return SystemCompatibility(
                platform=self.platform_info,
                os_version=os_version,
                architecture=architecture,
                shell_type=shell_type,
                package_managers=package_managers,
                compatibility_issues=compatibility_issues,
                recommended_actions=recommended_actions
            )
            
        except Exception as e:
            logger.error(f"系統相容性檢查失敗: {e}")
            return SystemCompatibility(
                platform=self.platform_info,
                os_version="unknown",
                architecture="unknown", 
                shell_type="unknown",
                compatibility_issues=[f"相容性檢查失敗: {str(e)}"],
                recommended_actions=["手動檢查系統配置"]
            )
    
    async def _initialize_permission_cache(self) -> None:
        """初始化權限快取"""
        try:
            # 預先檢查常用權限
            common_permissions = ['admin', 'sudo', 'docker']
            
            for perm_type in common_permissions:
                try:
                    perm_info = await self.check_permission(perm_type, use_cache=False)
                    cache_key = f"{perm_type}:global"
                    self.permission_cache[cache_key] = perm_info
                    logger.debug(f"快取權限 {perm_type}: {perm_info.has_permission}")
                except Exception as e:
                    logger.warning(f"初始化權限快取失敗 {perm_type}: {e}")
                    
        except Exception as e:
            logger.error(f"初始化權限快取失敗: {e}")
    
    # 權限修復方法
    async def _fix_write_permission(self, path: str) -> bool:
        """修復寫入權限"""
        try:
            if self.platform_info == PlatformType.WINDOWS:
                # Windows 權限修復較複雜，暫時跳過
                return False
            
            # Unix 系統嘗試修改權限
            target_path = Path(path)
            if target_path.exists():
                result = subprocess.run(
                    ['chmod', 'u+w', str(target_path)],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            logger.error(f"修復寫入權限失敗: {e}")
            return False
    
    async def _fix_execute_permission(self, path: str) -> bool:
        """修復執行權限"""
        try:
            if self.platform_info == PlatformType.WINDOWS:
                # Windows 執行權限通常由文件擴展名決定
                return Path(path).suffix.lower() in ['.exe', '.bat', '.cmd', '.ps1']
            
            # Unix 系統修改執行權限
            target_path = Path(path)
            if target_path.exists():
                result = subprocess.run(
                    ['chmod', '+x', str(target_path)],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            logger.error(f"修復執行權限失敗: {e}")
            return False
    
    async def _fix_read_permission(self, path: str) -> bool:
        """修復讀取權限"""
        try:
            if self.platform_info == PlatformType.WINDOWS:
                # Windows 讀取權限修復
                return True  # 大多數文件默認可讀
            
            # Unix 系統修改讀取權限
            target_path = Path(path)
            if target_path.exists():
                result = subprocess.run(
                    ['chmod', 'u+r', str(target_path)],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            logger.error(f"修復讀取權限失敗: {e}")
            return False
    
    # 權限提升方法
    async def _request_unix_elevation(self, command: List[str], reason: str) -> Tuple[bool, str]:
        """Unix 系統權限提升"""
        try:
            # 檢查 sudo 可用性
            sudo_perm = await self.check_permission('sudo')
            
            if not sudo_perm.has_permission:
                return False, "沒有 sudo 權限"
            
            # 構建 sudo 命令
            elevated_command = ['sudo'] + command
            
            # 執行命令
            result = subprocess.run(
                elevated_command,
                capture_output=True,
                text=True,
                timeout=300  # 5分鐘超時
            )
            
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            
            return success, output
            
        except subprocess.TimeoutExpired:
            return False, "命令執行超時"
        except Exception as e:
            return False, str(e)
    
    async def _request_windows_elevation(self, command: List[str], reason: str) -> Tuple[bool, str]:
        """Windows 系統權限提升"""
        try:
            # Windows 權限提升較複雜，這裡簡化處理
            # 實際應用中可能需要使用 UAC 提示或 PowerShell 的 -RunAs 參數
            
            # 檢查是否已經是管理員
            admin_perm = await self.check_permission('admin')
            if admin_perm.has_permission:
                # 已經是管理員，直接執行
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                success = result.returncode == 0
                output = result.stdout if success else result.stderr
                return success, output
            else:
                return False, "需要管理員權限，請以管理員身分重新執行"
                
        except subprocess.TimeoutExpired:
            return False, "命令執行超時"
        except Exception as e:
            return False, str(e)
    
    # 相容性修復建議方法
    async def _suggest_package_manager_solutions(self) -> List[str]:
        """建議套件管理器解決方案"""
        solutions = []
        
        if self.platform_info == PlatformType.WINDOWS:
            solutions.extend([
                "安裝 Chocolatey: Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))",
                "安裝 Scoop: Invoke-Expression (New-Object System.Net.WebClient).DownloadString('https://get.scoop.sh')",
                "使用內建 winget（Windows 10 1709+ / Windows 11）"
            ])
        elif self.platform_info == PlatformType.MACOS:
            solutions.append("安裝 Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        elif self.platform_info in [PlatformType.LINUX, PlatformType.WSL]:
            solutions.extend([
                "Ubuntu/Debian: sudo apt update && sudo apt install -y curl wget git",
                "CentOS/RHEL: sudo yum install -y curl wget git",
                "Fedora: sudo dnf install -y curl wget git",
                "Arch: sudo pacman -S curl wget git"
            ])
        
        return solutions
    
    async def _suggest_docker_solutions(self) -> List[str]:
        """建議 Docker 解決方案"""
        solutions = []
        
        if self.platform_info == PlatformType.WINDOWS:
            solutions.extend([
                "安裝 Docker Desktop for Windows",
                "確保啟用 Hyper-V 功能",
                "或使用 WSL2 後端"
            ])
        elif self.platform_info == PlatformType.MACOS:
            solutions.extend([
                "安裝 Docker Desktop for Mac",
                "或使用 Homebrew: brew install --cask docker"
            ])
        else:
            solutions.extend([
                "使用官方安裝腳本: curl -fsSL https://get.docker.com | sh",
                "將用戶加入 docker 群組: sudo usermod -aG docker $USER",
                "啟動 Docker 服務: sudo systemctl enable --now docker"
            ])
        
        return solutions
    
    async def _suggest_python_solutions(self) -> List[str]:
        """建議 Python 解決方案"""
        solutions = []
        
        if self.platform_info == PlatformType.WINDOWS:
            solutions.extend([
                "從 python.org 下載並安裝 Python 3.8+",
                "使用 Microsoft Store 安裝 Python",
                "或使用套件管理器: choco install python"
            ])
        elif self.platform_info == PlatformType.MACOS:
            solutions.extend([
                "使用 Homebrew: brew install python3",
                "或從 python.org 下載安裝"
            ])
        else:
            solutions.extend([
                "Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv",
                "CentOS/RHEL: sudo yum install python3 python3-pip",
                "Fedora: sudo dnf install python3 python3-pip",
                "Arch: sudo pacman -S python python-pip"
            ])
        
        return solutions
    
    async def _suggest_permission_solutions(self) -> List[str]:
        """建議權限解決方案"""
        solutions = []
        
        if self.platform_info == PlatformType.WINDOWS:
            solutions.extend([
                "以管理員身分執行 PowerShell 或命令提示符",
                "右鍵點擊程序選擇「以管理員身分執行」",
                "檢查 UAC 設定"
            ])
        else:
            solutions.extend([
                "使用 sudo 權限: sudo <command>",
                "將用戶加入 sudo 群組: sudo usermod -aG sudo $USER",
                "或聯繫系統管理員獲取必要權限"
            ])
        
        return solutions
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            return {
                'service_name': 'permission_manager',
                'status': 'healthy' if self.is_initialized else 'unhealthy',
                'platform': self.platform_info.value,
                'current_user': self.current_user_info['username'],
                'has_admin_permission': (await self.check_permission('admin')).has_permission,
                'has_sudo_permission': (await self.check_permission('sudo')).has_permission,
                'cached_permissions': len(self.permission_cache),
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'service_name': 'permission_manager',
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }


# 導出主要類別
__all__ = [
    'PermissionManager',
    'PermissionInfo',
    'SystemCompatibility', 
    'PermissionLevel',
    'PlatformType'
]