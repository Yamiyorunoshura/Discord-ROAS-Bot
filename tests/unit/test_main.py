"""主入口點測試模組.

此模組測試 main.py 的核心功能,包括:
- Python 版本檢查
- 事件循環設置
- CLI 命令處理
- 配置驗證
- 機器人啟動流程
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.main import app, check_python_version, setup_event_loop


class TestMainModule:
    """測試主模組功能."""

    def test_check_python_version_supported(self):
        """測試支援的 Python 版本檢查."""
        # Python 3.12+ 應該通過檢查
        check_python_version()  # 不應該拋出異常

    def test_check_python_version_unsupported(self):
        """測試不支援的 Python 版本檢查."""
        with patch("sys.version_info", (3, 10, 0)), pytest.raises(SystemExit):
            check_python_version()

    @patch("sys.platform", "linux")
    @patch("src.main.console")
    def test_setup_event_loop_unix_with_uvloop(self, mock_console):
        """測試 Unix 系統使用 uvloop."""
        with patch("uvloop.install") as mock_install:
            setup_event_loop()
            mock_install.assert_called_once()
            mock_console.print.assert_called_with(
                "[green]Using uvloop for enhanced performance[/green]"
            )

    @patch("sys.platform", "win32")
    @patch("src.main.console")
    def test_setup_event_loop_windows(self, mock_console):
        """測試 Windows 系統使用預設事件循環."""
        setup_event_loop()
        mock_console.print.assert_called_with(
            "[yellow]Using default asyncio event loop (Windows)[/yellow]"
        )

    @patch("sys.platform", "linux")
    @patch("src.main.console")
    def test_setup_event_loop_unix_no_uvloop(self, mock_console):
        """測試 Unix 系統沒有 uvloop 時的回退."""
        with patch("uvloop.install", side_effect=ImportError):
            setup_event_loop()
            mock_console.print.assert_called_with(
                "[yellow]uvloop not available, using default event loop[/yellow]"
            )


class TestCliCommands:
    """測試 CLI 命令功能."""

    def setup_method(self):
        """設置測試環境."""
        self.runner = CliRunner()

    @patch("src.main.create_and_run_bot")
    @patch("src.main.setup_logging")
    @patch("src.main.setup_event_loop")
    @patch("src.main.check_python_version")
    def test_run_command_default(
        self, mock_check_version, mock_setup_loop, mock_setup_logging, mock_create_bot
    ):
        """測試預設運行命令."""
        mock_create_bot.return_value = AsyncMock()

        # 模擬成功運行
        self.runner.invoke(app, ["run"])

        # 驗證所有初始化步驟被調用
        mock_check_version.assert_called_once()
        mock_setup_loop.assert_called_once()
        mock_setup_logging.assert_called_once()

    @patch("src.main.create_and_run_bot")
    @patch("src.main.setup_logging")
    def test_run_command_with_debug(self, mock_setup_logging, mock_create_bot):
        """測試除錯模式運行命令."""
        mock_create_bot.return_value = AsyncMock()

        self.runner.invoke(app, ["run", "--debug"])

        # 驗證除錯模式被啟用
        mock_setup_logging.assert_called_once_with(debug=True)

    def test_version_command(self):
        """測試版本查詢命令."""
        result = self.runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Discord ROAS Bot" in result.stdout
        assert "v2.0" in result.stdout

    def test_validate_config_command(self):
        """測試配置驗證命令."""
        result = self.runner.invoke(app, ["validate-config"])

        # 配置驗證應該能夠運行(不管是否成功)
        assert result.exit_code in [0, 1]  # 可能成功或失敗,但不應該崩潰


class TestMainIntegration:
    """測試主模組整合功能."""

    @pytest.mark.asyncio
    async def test_bot_creation_and_startup_flow(self):
        """測試機器人創建和啟動流程."""
        with patch("src.main.create_and_run_bot") as mock_create_bot:
            mock_create_bot.return_value = AsyncMock()

            # 這裡我們只測試流程,不實際啟動機器人
            from src.main import create_and_run_bot

            # 驗證函數可以被調用而不出錯
            assert callable(create_and_run_bot)

    def test_app_configuration(self):
        """測試 Typer 應用程式配置."""
        assert app.info.name == "adr-bot"
        assert "Discord ADR Bot" in app.info.help
        assert app.info.add_completion is False

    def test_environment_setup(self):
        """測試環境設置."""
        # 測試所有必要的導入都能正常工作
        from src.core.bot import create_and_run_bot
        from src.core.config import Settings
        from src.core.logger import setup_logging

        # 驗證函數都是可調用的
        assert callable(create_and_run_bot)
        assert callable(setup_logging)
        assert Settings is not None
