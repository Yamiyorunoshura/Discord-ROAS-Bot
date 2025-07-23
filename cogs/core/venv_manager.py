"""
智能虛擬環境管理器
- 自動檢測虛擬環境
- 跨平台虛擬環境創建
- 智能依賴包管理
- 環境健康檢查
- 錯誤恢復機制
"""

import os
import sys
import site
import subprocess
import platform
import logging
import asyncio
import json
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# 使用統一的核心模塊
from .error_handler import ErrorCodes, create_error_handler
from .logger import setup_module_logger

# 設置模塊日誌記錄器
logger = setup_module_logger("venv_manager")
error_handler = create_error_handler("venv_manager", logger)

class VirtualEnvironmentManager:
    """
    智能虛擬環境管理器
    
    功能：
    - 自動檢測和創建虛擬環境
    - 跨平台兼容性（Windows/macOS/Linux）
    - 智能依賴包管理
    - 環境健康檢查
    - 錯誤恢復和回退機制
    """
    
    def __init__(self, project_root: str | None = None):
        """
        初始化虛擬環境管理器
        
        Args:
            project_root: 專案根目錄路徑，預設為當前工作目錄
        """
        self.project_root = Path(project_root or os.getcwd())
        self.platform = platform.system().lower()
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
        # 虛擬環境相關路徑
        self.venv_candidates = [
            self.project_root / "venv",
            self.project_root / ".venv",
            self.project_root / "env",
            self.project_root / ".env"
        ]
        
        # 當前虛擬環境狀態
        self.current_venv: Path | None = None
        self.is_activated = False
        self.activation_method = None
        
        # 依賴管理
        self.requirements_files = [
            self.project_root / "requirements.txt",
            self.project_root / "requirement.txt",
            self.project_root / "deps.txt"
        ]
        
        # 初始化檢查
        self._initial_check()
    
    def _initial_check(self) -> None:
        """初始化檢查當前環境狀態"""
        try:
            # 檢查是否已在虛擬環境中
            if self.is_in_virtual_env():
                self.is_activated = True
                self.activation_method = "pre_activated"
                logger.info("【虛擬環境】已在虛擬環境中運行")
            else:
                logger.info("【虛擬環境】當前使用系統 Python 環境")
                
        except Exception as exc:
            logger.error(f"【虛擬環境】初始化檢查失敗: {exc}")
    
    def is_in_virtual_env(self) -> bool:
        """
        檢查是否在虛擬環境中
        
        Returns:
            bool: 是否在虛擬環境中
        """
        # 檢查 sys.prefix 和 sys.base_prefix
        if sys.prefix != sys.base_prefix:
            return True
            
        # 檢查 VIRTUAL_ENV 環境變數
        if os.environ.get("VIRTUAL_ENV"):
            return True
            
        # 檢查 pyvenv.cfg 文件
        pyvenv_cfg = Path(sys.prefix) / "pyvenv.cfg"
        if pyvenv_cfg.exists():
            return True
            
        return False
    
    def detect_existing_venv(self) -> Path | None:
        """
        檢測現有的虛擬環境
        
        Returns:
            Path | None: 虛擬環境路徑，如果未找到則返回 None
        """
        for venv_path in self.venv_candidates:
            if self._is_valid_venv(venv_path):
                logger.info(f"【虛擬環境】檢測到現有虛擬環境: {venv_path}")
                return venv_path
        
        logger.info("【虛擬環境】未檢測到現有虛擬環境")
        return None
    
    def _is_valid_venv(self, venv_path: Path) -> bool:
        """
        檢查路徑是否為有效的虛擬環境
        
        Args:
            venv_path: 虛擬環境路徑
            
        Returns:
            bool: 是否為有效的虛擬環境
        """
        if not venv_path.exists():
            return False
            
        # 檢查 pyvenv.cfg 文件
        pyvenv_cfg = venv_path / "pyvenv.cfg"
        if not pyvenv_cfg.exists():
            return False
            
        # 檢查 Python 執行檔
        python_exe = self._get_python_executable(venv_path)
        if not python_exe or not python_exe.exists():
            return False
            
        # 檢查 site-packages 目錄
        site_packages = self._get_site_packages_path(venv_path)
        if not site_packages or not site_packages.exists():
            return False
            
        return True
    
    def _get_python_executable(self, venv_path: Path) -> Path | None:
        """
        獲取虛擬環境中的 Python 執行檔路徑
        
        Args:
            venv_path: 虛擬環境路徑
            
        Returns:
            Path | None: Python 執行檔路徑
        """
        if self.platform == "windows":
            candidates = [
                venv_path / "Scripts" / "python.exe",
                venv_path / "Scripts" / "python3.exe"
            ]
        else:
            candidates = [
                venv_path / "bin" / "python",
                venv_path / "bin" / "python3",
                venv_path / "bin" / f"python{self.python_version}"
            ]
        
        for candidate in candidates:
            if candidate.exists():
                return candidate
                
        return None
    
    def _get_site_packages_path(self, venv_path: Path) -> Path | None:
        """
        獲取虛擬環境中的 site-packages 路徑
        
        Args:
            venv_path: 虛擬環境路徑
            
        Returns:
            Path | None: site-packages 路徑
        """
        if self.platform == "windows":
            return venv_path / "Lib" / "site-packages"
        else:
            # 尋找 Python 版本目錄
            lib_dir = venv_path / "lib"
            if not lib_dir.exists():
                return None
                
            # 尋找 Python 版本目錄 (如 python3.10)
            for item in lib_dir.iterdir():
                if item.is_dir() and item.name.startswith("python"):
                    site_packages = item / "site-packages"
                    if site_packages.exists():
                        return site_packages
                        
        return None
    
    async def create_virtual_env(self, venv_path: Path | None = None) -> Tuple[bool, str]:
        """
        創建虛擬環境
        
        Args:
            venv_path: 虛擬環境路徑，預設為 project_root/venv
            
        Returns:
            Tuple[bool, str]: (是否成功, 訊息)
        """
        if venv_path is None:
            venv_path = self.project_root / "venv"
            
        try:
            logger.info(f"【虛擬環境】開始創建虛擬環境: {venv_path}")
            
            # 確保父目錄存在
            venv_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果目錄已存在，先刪除
            if venv_path.exists():
                logger.warning(f"【虛擬環境】目錄已存在，正在刪除: {venv_path}")
                await self._remove_directory(venv_path)
            
            # 創建虛擬環境
            cmd = [sys.executable, "-m", "venv", str(venv_path)]
            
            # 在某些系統上可能需要額外的參數
            if self.platform != "windows":
                cmd.append("--copies")  # 複製文件而不是符號連結
            
            logger.info(f"【虛擬環境】執行命令: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"【虛擬環境】虛擬環境創建成功: {venv_path}")
                self.current_venv = venv_path
                return True, f"虛擬環境創建成功: {venv_path}"
            else:
                error_msg = stderr.decode() if stderr else "未知錯誤"
                logger.error(f"【虛擬環境】創建失敗: {error_msg}")
                return False, f"虛擬環境創建失敗: {error_msg}"
                
        except Exception as exc:
            logger.error(f"【虛擬環境】創建虛擬環境時發生異常: {exc}")
            return False, f"創建虛擬環境時發生異常: {exc}"
    
    async def _remove_directory(self, path: Path) -> None:
        """
        安全地刪除目錄
        
        Args:
            path: 要刪除的目錄路徑
        """
        try:
            if self.platform == "windows":
                # Windows 上使用 rmdir 命令
                cmd = ["rmdir", "/s", "/q", str(path)]
            else:
                # Unix 系統使用 rm 命令
                cmd = ["rm", "-rf", str(path)]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
        except Exception as exc:
            logger.error(f"【虛擬環境】刪除目錄失敗 {path}: {exc}")
    
    def activate_virtual_env(self, venv_path: Path | None = None) -> Tuple[bool, str]:
        """
        激活虛擬環境
        
        Args:
            venv_path: 虛擬環境路徑
            
        Returns:
            Tuple[bool, str]: (是否成功, 訊息)
        """
        try:
            # 如果已經在虛擬環境中，跳過
            if self.is_in_virtual_env():
                return True, "已在虛擬環境中"
            
            # 檢測現有虛擬環境
            if venv_path is None:
                venv_path = self.detect_existing_venv()
                
            if venv_path is None:
                return False, "未找到虛擬環境"
            
            # 獲取 site-packages 路徑
            site_packages = self._get_site_packages_path(venv_path)
            if not site_packages:
                return False, f"無法找到 site-packages 目錄: {venv_path}"
            
            # 將虛擬環境的 site-packages 添加到 Python 路徑
            site_packages_str = str(site_packages)
            if site_packages_str not in sys.path:
                sys.path.insert(0, site_packages_str)
            
            # 設置環境變數
            os.environ["VIRTUAL_ENV"] = str(venv_path)
            
            # 更新 PATH 環境變數
            if self.platform == "windows":
                scripts_dir = venv_path / "Scripts"
            else:
                scripts_dir = venv_path / "bin"
                
            if scripts_dir.exists():
                current_path = os.environ.get("PATH", "")
                if str(scripts_dir) not in current_path:
                    os.environ["PATH"] = f"{scripts_dir}{os.pathsep}{current_path}"
            
            # 重新初始化 site 模組
            importlib.reload(site)
            
            self.current_venv = venv_path
            self.is_activated = True
            self.activation_method = "runtime_activated"
            
            logger.info(f"【虛擬環境】虛擬環境激活成功: {venv_path}")
            return True, f"虛擬環境激活成功: {venv_path}"
            
        except Exception as exc:
            logger.error(f"【虛擬環境】激活虛擬環境失敗: {exc}")
            return False, f"激活虛擬環境失敗: {exc}"
    
    async def install_requirements(self, requirements_file: Path | None = None) -> Tuple[bool, str]:
        """
        安裝依賴包
        
        Args:
            requirements_file: requirements 文件路徑
            
        Returns:
            Tuple[bool, str]: (是否成功, 訊息)
        """
        try:
            # 尋找 requirements 文件
            if requirements_file is None:
                for req_file in self.requirements_files:
                    if req_file.exists():
                        requirements_file = req_file
                        break
            
            if requirements_file is None or not requirements_file.exists():
                return False, "未找到 requirements 文件"
            
            logger.info(f"【虛擬環境】開始安裝依賴包: {requirements_file}")
            
            # 獲取 pip 執行檔
            pip_cmd = self._get_pip_command()
            if not pip_cmd:
                return False, "無法找到 pip 命令"
            
            # 安裝依賴包
            cmd = pip_cmd + ["install", "-r", str(requirements_file)]
            
            logger.info(f"【虛擬環境】執行命令: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("【虛擬環境】依賴包安裝成功")
                return True, "依賴包安裝成功"
            else:
                error_msg = stderr.decode() if stderr else "未知錯誤"
                logger.error(f"【虛擬環境】依賴包安裝失敗: {error_msg}")
                return False, f"依賴包安裝失敗: {error_msg}"
                
        except Exception as exc:
            logger.error(f"【虛擬環境】安裝依賴包時發生異常: {exc}")
            return False, f"安裝依賴包時發生異常: {exc}"
    
    def _get_pip_command(self) -> List[str | None]:
        """
        獲取 pip 命令
        
        Returns:
            List[str | None]: pip 命令列表
        """
        if self.current_venv:
            # 使用虛擬環境中的 pip
            python_exe = self._get_python_executable(self.current_venv)
            if python_exe:
                return [str(python_exe), "-m", "pip"]
        
        # 使用系統 pip
        return [sys.executable, "-m", "pip"]
    
    async def health_check(self) -> Dict[str, Any]:
        """
        環境健康檢查
        
        Returns:
            Dict[str, Any]: 健康檢查結果
        """
        result = {
            "healthy": True,
            "issues": [],
            "info": {},
            "recommendations": []
        }
        
        try:
            # 檢查虛擬環境狀態
            result["info"]["in_virtual_env"] = self.is_in_virtual_env()
            result["info"]["current_venv"] = str(self.current_venv) if self.current_venv else None
            result["info"]["activation_method"] = self.activation_method
            result["info"]["python_version"] = self.python_version
            result["info"]["platform"] = self.platform
            
            # 檢查 Python 版本
            if sys.version_info < (3, 8):
                result["healthy"] = False
                result["issues"].append("Python 版本過低，建議使用 3.8 以上版本")
            
            # 檢查虛擬環境
            if not self.is_in_virtual_env():
                result["issues"].append("未使用虛擬環境")
                result["recommendations"].append("建議使用虛擬環境以避免依賴衝突")
            
            # 檢查依賴包
            missing_packages = await self._check_critical_packages()
            if missing_packages:
                result["healthy"] = False
                result["issues"].append(f"缺少關鍵依賴包: {', '.join(missing_packages)}")
                result["recommendations"].append("執行 pip install -r requirements.txt 安裝依賴包")
            
            # 檢查 requirements 文件
            req_file_exists = any(req_file.exists() for req_file in self.requirements_files)
            if not req_file_exists:
                result["issues"].append("未找到 requirements 文件")
                result["recommendations"].append("建議創建 requirements.txt 文件管理依賴")
            
            logger.info(f"【虛擬環境】健康檢查完成，狀態: {'健康' if result['healthy'] else '有問題'}")
            
        except Exception as exc:
            logger.error(f"【虛擬環境】健康檢查失敗: {exc}")
            result["healthy"] = False
            result["issues"].append(f"健康檢查失敗: {exc}")
        
        return result
    
    async def _check_critical_packages(self) -> List[str]:
        """
        檢查關鍵依賴包
        
        Returns:
            List[str]: 缺少的關鍵依賴包列表
        """
        critical_packages = [
            "discord.py",
            "aiohttp",
            "asyncio",
            "sqlite3"
        ]
        
        missing_packages = []
        
        for package in critical_packages:
            try:
                if package == "sqlite3":
                    import sqlite3
                elif package == "discord.py":
                    import discord
                elif package == "aiohttp":
                    import aiohttp
                elif package == "asyncio":
                    import asyncio
            except ImportError:
                missing_packages.append(package)
        
        return missing_packages
    
    async def auto_setup(self) -> Dict[str, Any]:
        """
        自動設置虛擬環境
        
        Returns:
            Dict[str, Any]: 設置結果
        """
        result = {
            "success": False,
            "steps": [],
            "errors": [],
            "final_state": {}
        }
        
        try:
            logger.info("【虛擬環境】開始自動設置虛擬環境")
            
            # 步驟 1: 檢查現有虛擬環境
            existing_venv = self.detect_existing_venv()
            if existing_venv:
                result["steps"].append(f"檢測到現有虛擬環境: {existing_venv}")
                
                # 嘗試激活現有虛擬環境
                success, message = self.activate_virtual_env(existing_venv)
                if success:
                    result["steps"].append(f"激活現有虛擬環境: {message}")
                else:
                    result["errors"].append(f"激活現有虛擬環境失敗: {message}")
            else:
                result["steps"].append("未檢測到現有虛擬環境")
                
                # 步驟 2: 創建新的虛擬環境
                success, message = await self.create_virtual_env()
                if success:
                    result["steps"].append(f"創建虛擬環境: {message}")
                    
                    # 激活新創建的虛擬環境
                    success, message = self.activate_virtual_env(self.current_venv)
                    if success:
                        result["steps"].append(f"激活虛擬環境: {message}")
                    else:
                        result["errors"].append(f"激活虛擬環境失敗: {message}")
                else:
                    result["errors"].append(f"創建虛擬環境失敗: {message}")
                    return result
            
            # 步驟 3: 安裝依賴包
            success, message = await self.install_requirements()
            if success:
                result["steps"].append(f"安裝依賴包: {message}")
            else:
                result["errors"].append(f"安裝依賴包失敗: {message}")
            
            # 步驟 4: 健康檢查
            health_result = await self.health_check()
            result["final_state"] = health_result
            
            if health_result["healthy"]:
                result["success"] = True
                result["steps"].append("環境設置完成，健康檢查通過")
                logger.info("【虛擬環境】自動設置完成，環境健康")
            else:
                result["steps"].append("環境設置完成，但健康檢查發現問題")
                result["errors"].extend(health_result["issues"])
                logger.warning("【虛擬環境】自動設置完成，但存在問題")
            
        except Exception as exc:
            logger.error(f"【虛擬環境】自動設置失敗: {exc}")
            result["errors"].append(f"自動設置失敗: {exc}")
        
        return result
    
    def get_environment_info(self) -> Dict[str, Any]:
        """
        獲取環境資訊
        
        Returns:
            Dict[str, Any]: 環境資訊
        """
        return {
            "project_root": str(self.project_root),
            "platform": self.platform,
            "python_version": self.python_version,
            "python_executable": sys.executable,
            "is_in_virtual_env": self.is_in_virtual_env(),
            "current_venv": str(self.current_venv) if self.current_venv else None,
            "is_activated": self.is_activated,
            "activation_method": self.activation_method,
            "sys_prefix": sys.prefix,
            "sys_base_prefix": sys.base_prefix,
            "virtual_env_var": os.environ.get("VIRTUAL_ENV"),
            "python_path": sys.path[:5]  # 只顯示前5個路徑
        }

# 導入 importlib 模組
import importlib 