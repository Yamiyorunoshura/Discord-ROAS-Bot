"""
跨平台虛擬環境管理器測試
測試 Windows、macOS、Linux 的兼容性
"""

import os
import platform
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cogs.core.venv_manager import VirtualEnvironmentManager


class TestCrossPlatformVirtualEnvironmentManager(unittest.TestCase):
    """跨平台虛擬環境管理器測試類"""

    def setUp(self):
        """設置測試環境"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.venv_manager = VirtualEnvironmentManager(str(self.project_root))

    def tearDown(self):
        """清理測試環境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_platform_detection(self):
        """測試平台檢測"""
        # 測試平台檢測是否正確
        detected_platform = self.venv_manager.platform
        actual_platform = platform.system().lower()

        self.assertEqual(detected_platform, actual_platform)
        self.assertIn(detected_platform, ['windows', 'darwin', 'linux'])

    def test_python_executable_paths_windows(self):
        """測試 Windows 平台的 Python 執行檔路徑"""
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 模擬 Windows 環境
        with patch.object(self.venv_manager, 'platform', 'windows'):
            # 創建 Windows 結構
            scripts_dir = fake_venv / "Scripts"
            scripts_dir.mkdir()

            # 測試不同的 Python 執行檔名稱
            python_exe = scripts_dir / "python.exe"
            python_exe.touch()

            result = self.venv_manager._get_python_executable(fake_venv)
            self.assertEqual(result, python_exe)

    def test_python_executable_paths_unix(self):
        """測試 Unix 系統（macOS/Linux）的 Python 執行檔路徑"""
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 模擬 Unix 環境
        with patch.object(self.venv_manager, 'platform', 'darwin'):
            # 創建 Unix 結構
            bin_dir = fake_venv / "bin"
            bin_dir.mkdir()

            # 測試不同的 Python 執行檔名稱
            python_exe = bin_dir / "python"
            python_exe.touch()

            result = self.venv_manager._get_python_executable(fake_venv)
            self.assertEqual(result, python_exe)

    def test_site_packages_paths_windows(self):
        """測試 Windows 平台的 site-packages 路徑"""
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 模擬 Windows 環境
        with patch.object(self.venv_manager, 'platform', 'windows'):
            # 創建 Windows 結構
            lib_dir = fake_venv / "Lib" / "site-packages"
            lib_dir.mkdir(parents=True)

            result = self.venv_manager._get_site_packages_path(fake_venv)
            self.assertEqual(result, lib_dir)

    def test_site_packages_paths_unix(self):
        """測試 Unix 系統的 site-packages 路徑"""
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 模擬 Unix 環境
        with patch.object(self.venv_manager, 'platform', 'darwin'):
            # 創建 Unix 結構
            python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            lib_dir = fake_venv / "lib" / python_version / "site-packages"
            lib_dir.mkdir(parents=True)

            result = self.venv_manager._get_site_packages_path(fake_venv)
            self.assertEqual(result, lib_dir)

    def test_valid_venv_structure_windows(self):
        """測試 Windows 平台的有效虛擬環境結構"""
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 模擬 Windows 環境
        with patch.object(self.venv_manager, 'platform', 'windows'):
            # 創建完整的 Windows 虛擬環境結構
            (fake_venv / "pyvenv.cfg").write_text("home = C:\\Python\\python.exe\n")

            scripts_dir = fake_venv / "Scripts"
            scripts_dir.mkdir()
            (scripts_dir / "python.exe").touch()

            lib_dir = fake_venv / "Lib" / "site-packages"
            lib_dir.mkdir(parents=True)

            result = self.venv_manager._is_valid_venv(fake_venv)
            self.assertTrue(result)

    def test_valid_venv_structure_unix(self):
        """測試 Unix 系統的有效虛擬環境結構"""
        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 模擬 Unix 環境
        with patch.object(self.venv_manager, 'platform', 'darwin'):
            # 創建完整的 Unix 虛擬環境結構
            (fake_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

            bin_dir = fake_venv / "bin"
            bin_dir.mkdir()
            (bin_dir / "python").touch()

            python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            lib_dir = fake_venv / "lib" / python_version / "site-packages"
            lib_dir.mkdir(parents=True)

            result = self.venv_manager._is_valid_venv(fake_venv)
            self.assertTrue(result)

    def test_environment_variables_setup(self):
        """測試環境變數設置"""
        # 如果已經在虛擬環境中，跳過這個測試
        if self.venv_manager.is_in_virtual_env():
            self.skipTest("已在虛擬環境中運行，跳過環境變數設置測試")

        fake_venv = self.project_root / "venv"
        fake_venv.mkdir()

        # 創建虛擬環境結構
        (fake_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

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
            python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            lib_dir = fake_venv / "lib" / python_version / "site-packages"
            lib_dir.mkdir(parents=True)

        # 保存原始環境變數
        original_venv = os.environ.get("VIRTUAL_ENV")
        original_path = os.environ.get("PATH")

        try:
            # 測試激活虛擬環境
            success, message = self.venv_manager.activate_virtual_env(fake_venv)

            if success:
                # 檢查環境變數是否正確設置
                self.assertEqual(os.environ.get("VIRTUAL_ENV"), str(fake_venv))

                # 檢查 PATH 是否包含虛擬環境的執行檔目錄
                current_path = os.environ.get("PATH", "")
                if sys.platform == "win32":
                    expected_dir = str(fake_venv / "Scripts")
                else:
                    expected_dir = str(fake_venv / "bin")

                self.assertIn(expected_dir, current_path)

        finally:
            # 恢復原始環境變數
            if original_venv:
                os.environ["VIRTUAL_ENV"] = original_venv
            elif "VIRTUAL_ENV" in os.environ:
                del os.environ["VIRTUAL_ENV"]

            if original_path:
                os.environ["PATH"] = original_path

class TestCrossPlatformVirtualEnvironmentManagerAsync(unittest.IsolatedAsyncioTestCase):
    """跨平台異步測試類"""

    async def asyncSetUp(self):
        """異步設置"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.venv_manager = VirtualEnvironmentManager(str(self.project_root))

    async def asyncTearDown(self):
        """異步清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('asyncio.create_subprocess_exec')
    async def test_create_venv_command_windows(self, mock_subprocess):
        """測試 Windows 平台的虛擬環境創建命令"""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # 模擬 Windows 環境
        with patch.object(self.venv_manager, 'platform', 'windows'):
            venv_path = self.project_root / "test_venv"
            success, message = await self.venv_manager.create_virtual_env(venv_path)

            # 檢查是否調用了正確的命令
            mock_subprocess.assert_called_once()

            # 獲取實際調用的參數
            call_args = mock_subprocess.call_args[0]

            # Windows 不應該包含 --copies 參數
            self.assertNotIn("--copies", call_args)

    @patch('asyncio.create_subprocess_exec')
    async def test_create_venv_command_unix(self, mock_subprocess):
        """測試 Unix 系統的虛擬環境創建命令"""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # 模擬 Unix 環境
        with patch.object(self.venv_manager, 'platform', 'darwin'):
            venv_path = self.project_root / "test_venv"
            success, message = await self.venv_manager.create_virtual_env(venv_path)

            # 檢查是否調用了正確的命令
            mock_subprocess.assert_called_once()

            # 獲取實際調用的參數
            call_args = mock_subprocess.call_args[0]

            # Unix 系統應該包含 --copies 參數
            self.assertIn("--copies", call_args)

    @patch('asyncio.create_subprocess_exec')
    async def test_remove_directory_windows(self, mock_subprocess):
        """測試 Windows 平台的目錄刪除"""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # 模擬 Windows 環境
        with patch.object(self.venv_manager, 'platform', 'windows'):
            test_path = self.project_root / "test_dir"
            test_path.mkdir()

            await self.venv_manager._remove_directory(test_path)

            # 檢查是否使用了 Windows 的 rmdir 命令
            mock_subprocess.assert_called_once()

            # 獲取實際調用的參數
            call_args = mock_subprocess.call_args[0]

            self.assertEqual(call_args[0], "rmdir")
            self.assertIn("/s", call_args)
            self.assertIn("/q", call_args)

    @patch('asyncio.create_subprocess_exec')
    async def test_remove_directory_unix(self, mock_subprocess):
        """測試 Unix 系統的目錄刪除"""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # 模擬 Unix 環境
        with patch.object(self.venv_manager, 'platform', 'darwin'):
            test_path = self.project_root / "test_dir"
            test_path.mkdir()

            await self.venv_manager._remove_directory(test_path)

            # 檢查是否使用了 Unix 的 rm 命令
            mock_subprocess.assert_called_once()

            # 獲取實際調用的參數
            call_args = mock_subprocess.call_args[0]

            self.assertEqual(call_args[0], "rm")
            self.assertIn("-rf", call_args)

class TestEnvironmentIntegration(unittest.TestCase):
    """環境集成測試"""

    def test_current_environment_detection(self):
        """測試當前環境檢測的準確性"""
        venv_manager = VirtualEnvironmentManager()

        # 測試環境資訊獲取
        env_info = venv_manager.get_environment_info()

        # 驗證基本資訊
        self.assertIsInstance(env_info['platform'], str)
        self.assertIsInstance(env_info['python_version'], str)
        self.assertIsInstance(env_info['is_in_virtual_env'], bool)

        # 驗證 Python 版本格式
        version_parts = env_info['python_version'].split('.')
        self.assertEqual(len(version_parts), 2)
        self.assertTrue(all(part.isdigit() for part in version_parts))

        # 驗證平台名稱
        self.assertIn(env_info['platform'], ['windows', 'darwin', 'linux'])

    def test_requirements_file_detection(self):
        """測試 requirements 文件檢測"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            venv_manager = VirtualEnvironmentManager(str(project_root))

            # 測試沒有 requirements 文件的情況
            self.assertFalse(any(req_file.exists() for req_file in venv_manager.requirements_files))

            # 創建 requirements.txt
            req_file = project_root / "requirements.txt"
            req_file.write_text("discord.py>=2.0.0\n")

            # 重新創建管理器實例
            venv_manager = VirtualEnvironmentManager(str(project_root))

            # 測試檢測到 requirements 文件
            self.assertTrue(any(req_file.exists() for req_file in venv_manager.requirements_files))

if __name__ == "__main__":
    # 運行測試
    unittest.main(verbosity=2)
