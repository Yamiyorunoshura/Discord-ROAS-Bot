"""
降級部署管理器
Task ID: 2 - 自動化部署和啟動系統開發

Elena - API架構師
這個模組實現降級部署管理器，當Docker和UV都不可用時提供基本的Python部署支援：
- 標準Python環境檢測
- pip依賴安裝
- 基本應用程式啟動
- 與部署API的整合
"""

import asyncio
import logging
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from src.core.errors import (
    DeploymentError,
    EnvironmentError,
    DependencyInstallError,
    ServiceStartupError
)

logger = logging.getLogger('fallback_deployment_manager')


@dataclass
class FallbackEnvironmentInfo:
    """降級環境資訊"""
    python_executable: Optional[str]
    python_version: Optional[str]
    pip_available: bool
    venv_available: bool
    project_root: Path
    requirements_available: bool = False


class FallbackDeploymentManager:
    """
    降級部署管理器
    
    提供最基本的Python部署支援，作為Docker和UV不可用時的最後選擇
    """
    
    def __init__(self, project_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None):
        """
        初始化降級部署管理器
        
        Args:
            project_root: 專案根目錄
            config: 部署配置
        """
        self.project_root = project_root or Path.cwd()
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 環境資訊
        self._environment_info: Optional[FallbackEnvironmentInfo] = None
        self._python_executable: Optional[str] = None
        self._pip_executable: Optional[str] = None
        
        # 部署狀態
        self._deployment_id: Optional[str] = None
        self._is_deployed: bool = False
    
    async def detect_environment(self) -> Dict[str, Any]:
        """
        檢測降級部署環境
        
        Returns:
            環境檢測結果
        """
        try:
            self.logger.info("開始檢測降級部署環境...")
            
            # 檢測Python可執行文件
            python_executable = shutil.which('python3') or shutil.which('python')
            if not python_executable:
                raise EnvironmentError("未找到Python可執行文件")
            
            self._python_executable = python_executable
            
            # 檢測Python版本
            try:
                result = await self._run_command([python_executable, '--version'])
                python_version = result.stdout.strip() if result.returncode == 0 else None
            except Exception:
                python_version = None
            
            # 檢測pip可用性
            pip_available = False
            pip_executable = None
            try:
                # 嘗試python -m pip
                result = await self._run_command([python_executable, '-m', 'pip', '--version'])
                if result.returncode == 0:
                    pip_available = True
                    pip_executable = f"{python_executable} -m pip"
                else:
                    # 嘗試獨立的pip命令
                    pip_path = shutil.which('pip3') or shutil.which('pip')
                    if pip_path:
                        result = await self._run_command([pip_path, '--version'])
                        if result.returncode == 0:
                            pip_available = True
                            pip_executable = pip_path
            except Exception:
                pass
            
            self._pip_executable = pip_executable
            
            # 檢測venv可用性
            venv_available = False
            try:
                result = await self._run_command([python_executable, '-m', 'venv', '--help'])
                venv_available = result.returncode == 0
            except Exception:
                pass
            
            # 檢測依賴配置文件
            requirements_path = self.project_root / 'requirements.txt'
            pyproject_path = self.project_root / 'pyproject.toml'
            requirements_available = requirements_path.exists() or pyproject_path.exists()
            
            # 創建環境資訊
            self._environment_info = FallbackEnvironmentInfo(
                python_executable=python_executable,
                python_version=python_version,
                pip_available=pip_available,
                venv_available=venv_available,
                project_root=self.project_root,
                requirements_available=requirements_available
            )
            
            env_result = {
                'python_executable': python_executable,
                'python_version': python_version,
                'pip_available': pip_available,
                'pip_executable': pip_executable,
                'venv_available': venv_available,
                'requirements_available': requirements_available,
                'project_root': str(self.project_root),
                'detection_timestamp': datetime.now().isoformat()
            }
            
            self.logger.info("降級部署環境檢測完成")
            return env_result
            
        except Exception as e:
            self.logger.error(f"環境檢測失敗: {e}")
            raise EnvironmentError(f"降級環境檢測失敗: {str(e)}")
    
    async def install_dependencies(self) -> bool:
        """
        安裝依賴
        
        Returns:
            安裝是否成功
        """
        try:
            if not self._environment_info:
                await self.detect_environment()
            
            if not self._environment_info.pip_available:
                self.logger.warning("pip不可用，跳過依賴安裝")
                return True
            
            self.logger.info("開始安裝降級部署依賴...")
            
            # 檢查依賴配置文件
            requirements_path = self.project_root / 'requirements.txt'
            pyproject_path = self.project_root / 'pyproject.toml'
            
            if requirements_path.exists():
                # 安裝requirements.txt依賴
                success = await self._install_requirements_txt(requirements_path)
                if not success:
                    return False
                    
            elif pyproject_path.exists():
                # 嘗試安裝pyproject.toml依賴
                success = await self._install_pyproject_dependencies()
                if not success:
                    return False
            else:
                self.logger.info("未找到依賴配置文件，跳過依賴安裝")
            
            self.logger.info("降級部署依賴安裝完成")
            return True
            
        except Exception as e:
            self.logger.error(f"安裝依賴失敗: {e}")
            raise DependencyInstallError(f"降級依賴安裝失敗: {str(e)}")
    
    async def deploy(self) -> bool:
        """
        執行降級部署
        
        Returns:
            部署是否成功
        """
        try:
            self.logger.info("開始執行降級部署...")
            
            # 環境檢測
            await self.detect_environment()
            
            # 安裝依賴
            success = await self.install_dependencies()
            if not success:
                return False
            
            # 檢查應用程式入口點
            main_module = await self._find_main_module()
            if not main_module:
                self.logger.warning("未找到主應用程式入口點，但標記為部署成功")
            
            self._is_deployed = True
            self.logger.info("降級部署完成")
            return True
            
        except Exception as e:
            self.logger.error(f"降級部署失敗: {e}")
            raise DeploymentError(f"降級部署失敗: {str(e)}")
    
    async def start_application(self) -> bool:
        """
        啟動應用程式
        
        Returns:
            啟動是否成功
        """
        try:
            if not self._is_deployed:
                self.logger.warning("尚未部署，先執行部署")
                success = await self.deploy()
                if not success:
                    return False
            
            # 查找主模組
            main_module = await self._find_main_module()
            if not main_module:
                raise ServiceStartupError("未找到主應用程式入口點")
            
            self.logger.info(f"啟動應用程式: {main_module}")
            
            # 構建啟動命令
            if main_module.endswith('.py'):
                cmd = [self._python_executable, main_module]
            else:
                cmd = [self._python_executable, '-m', main_module]
            
            # 在後台啟動應用程式
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            # 等待應用程式啟動
            await asyncio.sleep(3)
            
            # 檢查程序是否還在運行
            if process.returncode is None:
                self.logger.info("應用程式啟動成功")
                return True
            else:
                stdout, stderr = await process.communicate()
                self.logger.error(f"應用程式啟動失敗，退出碼: {process.returncode}")
                if stderr:
                    self.logger.error(f"錯誤輸出: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"啟動應用程式失敗: {e}")
            raise ServiceStartupError(f"降級應用程式啟動失敗: {str(e)}")
    
    async def get_api_status(self) -> Dict[str, Any]:
        """
        獲取API狀態資訊
        
        Returns:
            API狀態字典
        """
        return {
            'manager_type': 'FALLBACK_DEPLOYMENT',
            'is_available': bool(self._environment_info and self._environment_info.python_executable),
            'python_executable': self._python_executable,
            'pip_available': self._environment_info.pip_available if self._environment_info else False,
            'venv_available': self._environment_info.venv_available if self._environment_info else False,
            'is_deployed': self._is_deployed,
            'deployment_id': self._deployment_id,
            'timestamp': datetime.now().isoformat()
        }
    
    async def get_deployment_status(self) -> Dict[str, Any]:
        """
        獲取部署狀態
        
        Returns:
            部署狀態資訊
        """
        return {
            'deployment_id': self._deployment_id,
            'manager_type': 'fallback',
            'is_deployed': self._is_deployed,
            'environment_info': {
                'python_executable': self._python_executable,
                'pip_executable': self._pip_executable
            } if self._environment_info else None,
            'timestamp': datetime.now().isoformat()
        }
    
    # ========== 內部方法 ==========
    
    async def _run_command(self, cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
        """執行命令並返回結果"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode() if stdout else '',
                stderr=stderr.decode() if stderr else ''
            )
            
        except asyncio.TimeoutError:
            if process:
                process.terminate()
                await process.wait()
            raise subprocess.TimeoutExpired(cmd, timeout)
    
    async def _install_requirements_txt(self, requirements_path: Path) -> bool:
        """安裝requirements.txt依賴"""
        try:
            self.logger.info(f"安裝requirements.txt依賴: {requirements_path}")
            
            cmd = self._pip_executable.split() + ['install', '-r', str(requirements_path)]
            result = await self._run_command(cmd, timeout=300)
            
            if result.returncode == 0:
                self.logger.info("requirements.txt依賴安裝成功")
                return True
            else:
                self.logger.error(f"requirements.txt依賴安裝失敗: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"安裝requirements.txt依賴異常: {e}")
            return False
    
    async def _install_pyproject_dependencies(self) -> bool:
        """嘗試安裝pyproject.toml依賴"""
        try:
            self.logger.info("嘗試安裝pyproject.toml依賴")
            
            # 嘗試使用pip install -e .
            cmd = self._pip_executable.split() + ['install', '-e', '.']
            result = await self._run_command(cmd, timeout=300)
            
            if result.returncode == 0:
                self.logger.info("pyproject.toml依賴安裝成功")
                return True
            else:
                self.logger.warning("pip install -e . 失敗，嘗試解析pyproject.toml")
                
                # 嘗試解析pyproject.toml手動安裝依賴
                return await self._parse_and_install_pyproject()
                
        except Exception as e:
            self.logger.error(f"安裝pyproject.toml依賴異常: {e}")
            return False
    
    async def _parse_and_install_pyproject(self) -> bool:
        """解析pyproject.toml並手動安裝依賴"""
        try:
            pyproject_path = self.project_root / 'pyproject.toml'
            
            # 嘗試解析pyproject.toml
            try:
                import toml
                config = toml.load(pyproject_path)
            except ImportError:
                self.logger.warning("toml模組不可用，無法解析pyproject.toml")
                return True  # 不視為錯誤
            
            # 獲取依賴列表
            dependencies = []
            
            # 檢查project.dependencies
            project_deps = config.get('project', {}).get('dependencies', [])
            dependencies.extend(project_deps)
            
            # 檢查tool.setuptools.install_requires（舊格式）
            tool_deps = config.get('tool', {}).get('setuptools', {}).get('install_requires', [])
            dependencies.extend(tool_deps)
            
            if dependencies:
                self.logger.info(f"找到 {len(dependencies)} 個依賴項")
                
                # 安裝每個依賴
                for dep in dependencies:
                    cmd = self._pip_executable.split() + ['install', dep]
                    result = await self._run_command(cmd, timeout=60)
                    if result.returncode != 0:
                        self.logger.warning(f"安裝依賴 {dep} 失敗: {result.stderr}")
                
                return True
            else:
                self.logger.info("pyproject.toml中未找到依賴項")
                return True
                
        except Exception as e:
            self.logger.error(f"解析pyproject.toml失敗: {e}")
            return False
    
    async def _find_main_module(self) -> Optional[str]:
        """查找主應用程式模組"""
        possible_main_modules = [
            'main.py',
            'app.py',
            'run.py',
            '__main__.py',
            'server.py',
            'start.py'
        ]
        
        for module_name in possible_main_modules:
            module_path = self.project_root / module_name
            if module_path.exists():
                self.logger.info(f"找到主模組: {module_name}")
                return module_name
        
        # 檢查是否是包結構
        init_file = self.project_root / '__init__.py'
        if init_file.exists():
            self.logger.info("檢測到包結構，使用 -m 模式啟動")
            return self.project_root.name
        
        self.logger.warning("未找到主應用程式模組")
        return None
    
    def _generate_deployment_id(self) -> str:
        """生成部署ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import hashlib
        random_part = hashlib.md5(f"{timestamp}_fallback_{id(self)}".encode()).hexdigest()[:8]
        return f"fallback_{timestamp}_{random_part}"


# 工廠函數
def create_fallback_deployment_manager(project_root: Optional[Path] = None) -> FallbackDeploymentManager:
    """
    創建降級部署管理器實例
    
    Args:
        project_root: 專案根目錄
        
    Returns:
        降級部署管理器實例
    """
    return FallbackDeploymentManager(project_root)