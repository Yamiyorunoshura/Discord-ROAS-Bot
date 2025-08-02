"""
虛擬環境管理器單元測試
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cogs.core.venv_manager import VirtualEnvironmentManager


class TestVirtualEnvironmentManager(unittest.TestCase):
    """虛擬環境管理器測試類"""

    def setUp(self):
        """設置測試環境"""
        # 創建臨時目錄作為測試項目根目錄
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

        # 創建測試用的 requirements.txt
        self.requirements_file = self.project_root / "requirements.txt"
        self.requirements_file.write_text("discord.py>=2.0.0\naiohttp>=3.8.0\n")

        # 初始化管理器
        self.venv_manager = VirtualEnvironmentManager(str(self.project_root))

    def tearDown(self):
        """清理測試環境"""
        # 刪除臨時目錄
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """測試初始化"""
        self.assertEqual(self.venv_manager.project_root, self.project_root)
        self.assertIn("venv", [p.name for p in self.venv_manager.venv_candidates])
        self.assertTrue(self.requirements_file.exists())

    def test_is_in_virtual_env(self):
        """測試虛擬環境檢測"""
        # 這個測試會根據當前運行環境而變化
        result = self.venv_manager.is_in_virtual_env()
        self.assertIsInstance(result, bool)

    def test_detect_existing_venv_none(self):
        """測試檢測不存在的虛擬環境"""
        result = self.venv_manager.detect_existing_venv()
        self.assertIsNone(result)

    def test_detect_existing_venv_exists(self):
        """測試檢測存在的虛擬環境"""
        # 創建一個假的虛擬環境結構
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 創建 pyvenv.cfg
        (fake_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        # 創建 Python 執行檔目錄結構
        if sys.platform == "win32":
            scripts_dir = fake_venv / "Scripts"
            scripts_dir.mkdir()
            (scripts_dir / "python.exe").touch()

            lib_dir = fake_venv / "Lib" / "site-packages"
            lib_dir.mkdir(parents=True)
        else:
            bin_dir = fake_venv / "bin"
            bin_dir.mkdir()
            (bin_dir / "python").touch()

            lib_dir = fake_venv / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            lib_dir.mkdir(parents=True)

        result = self.venv_manager.detect_existing_venv()
        self.assertEqual(result, fake_venv)

    def test_get_environment_info(self):
        """測試獲取環境資訊"""
        info = self.venv_manager.get_environment_info()

        required_keys = [
            "project_root", "platform", "python_version", "python_executable",
            "is_in_virtual_env", "current_venv", "is_activated", "activation_method"
        ]

        for key in required_keys:
            self.assertIn(key, info)

        self.assertEqual(info["project_root"], str(self.project_root))
        self.assertIsInstance(info["python_version"], str)
        self.assertIsInstance(info["is_in_virtual_env"], bool)

    @patch('subprocess.run')
    def test_get_pip_command_system(self, mock_run):
        """測試獲取系統 pip 命令"""
        # 沒有當前虛擬環境時應該使用系統 pip
        self.venv_manager.current_venv = None

        pip_cmd = self.venv_manager._get_pip_command()
        self.assertEqual(pip_cmd, [sys.executable, "-m", "pip"])

    async def test_health_check(self):
        """測試健康檢查"""
        result = await self.venv_manager.health_check()

        required_keys = ["healthy", "issues", "info", "recommendations"]
        for key in required_keys:
            self.assertIn(key, result)

        self.assertIsInstance(result["healthy"], bool)
        self.assertIsInstance(result["issues"], list)
        self.assertIsInstance(result["info"], dict)
        self.assertIsInstance(result["recommendations"], list)

    async def test_check_critical_packages(self):
        """測試檢查關鍵依賴包"""
        missing = await self.venv_manager._check_critical_packages()
        self.assertIsInstance(missing, list)

        # discord.py 可能不在測試環境中，但 asyncio 和 sqlite3 應該存在
        # 這個測試主要確保方法能正常運行而不拋出異常

class TestVirtualEnvironmentManagerAsync(unittest.IsolatedAsyncioTestCase):
    """異步測試類"""

    async def asyncSetUp(self):
        """異步設置"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.venv_manager = VirtualEnvironmentManager(str(self.project_root))

    async def asyncTearDown(self):
        """異步清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_auto_setup_no_venv(self):
        """測試自動設置（無現有虛擬環境）"""
        # 這個測試可能會實際創建虛擬環境，所以我們模擬一些方法
        with patch.object(self.venv_manager, 'create_virtual_env') as mock_create, \
             patch.object(self.venv_manager, 'activate_virtual_env') as mock_activate, \
             patch.object(self.venv_manager, 'install_requirements') as mock_install:

            mock_create.return_value = (True, "虛擬環境創建成功")
            mock_activate.return_value = (True, "虛擬環境激活成功")
            mock_install.return_value = (False, "未找到 requirements 文件")

            result = await self.venv_manager.auto_setup()

            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("steps", result)
            self.assertIn("errors", result)

    @patch('asyncio.create_subprocess_exec')
    async def test_create_virtual_env_success(self, mock_subprocess):
        """測試成功創建虛擬環境"""
        # 模擬成功的子程序執行
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        venv_path = self.project_root / "test_venv"
        success, message = await self.venv_manager.create_virtual_env(venv_path)

        self.assertTrue(success)
        self.assertIn("成功", message)

    @patch('asyncio.create_subprocess_exec')
    async def test_create_virtual_env_failure(self, mock_subprocess):
        """測試創建虛擬環境失敗"""
        # 模擬失敗的子程序執行
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Error creating venv")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        venv_path = self.project_root / "test_venv"
        success, message = await self.venv_manager.create_virtual_env(venv_path)

        self.assertFalse(success)
        self.assertIn("失敗", message)

def run_async_test(coro):
    """運行異步測試的輔助函數"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

if __name__ == "__main__":
    # 運行測試
    unittest.main(verbosity=2)
