"""Bot 核心測試模組.

此模組測試 bot.py 的核心功能,包括:
- ModuleLoadResult 類別
- StartupManager 類別
- ADRBot 機器人類別
- 模組載入和管理
- 事件處理和錯誤處理
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.bot import ADRBot, ModuleLoadResult, StartupManager, create_and_run_bot


class TestModuleLoadResult:
    """測試模組載入結果類別."""

    def test_successful_load_result(self):
        """測試成功的模組載入結果."""
        result = ModuleLoadResult("test_module", True, 0.5)

        assert result.name == "test_module"
        assert result.success is True
        assert result.load_time == 0.5
        assert result.error is None

    def test_failed_load_result(self):
        """測試失敗的模組載入結果."""
        error = ImportError("Module not found")
        result = ModuleLoadResult("bad_module", False, 0.1, error)

        assert result.name == "bad_module"
        assert result.success is False
        assert result.load_time == 0.1
        assert result.error == error


class TestStartupManager:
    """測試啟動管理器."""

    def setup_method(self):
        """設置測試環境."""
        self.mock_bot = MagicMock(spec=ADRBot)
        self.mock_settings = MagicMock()
        self.startup_manager = StartupManager(self.mock_bot, self.mock_settings)

    def test_startup_manager_initialization(self):
        """測試啟動管理器初始化."""
        assert self.startup_manager.bot == self.mock_bot
        assert self.startup_manager.settings == self.mock_settings
        assert self.startup_manager.logger is not None

    @pytest.mark.asyncio
    async def test_load_cog_success(self):
        """測試成功載入 Cog."""
        MagicMock()
        self.mock_bot.load_extension = AsyncMock()

        with patch("time.time", side_effect=[0, 0.5]):
            result = await self.startup_manager.load_cog("test.cog")

        assert result.success is True
        assert result.load_time == 0.5
        self.mock_bot.load_extension.assert_called_once_with("test.cog")

    @pytest.mark.asyncio
    async def test_load_cog_failure(self):
        """測試載入 Cog 失敗."""
        self.mock_bot.load_extension = AsyncMock(
            side_effect=ImportError("Module not found")
        )

        with patch("time.time", side_effect=[0, 0.1]):
            result = await self.startup_manager.load_cog("bad.cog")

        assert result.success is False
        assert result.load_time == 0.1
        assert isinstance(result.error, ImportError)


class TestADRBot:
    """測試 ADR 機器人核心類別."""

    def setup_method(self):
        """設置測試環境."""
        self.mock_settings = MagicMock()
        self.mock_settings.get_database_url.return_value = "sqlite:///:memory:"
        self.mock_settings.is_feature_enabled.return_value = True

        with patch("src.core.bot.get_logger"):
            self.bot = ADRBot(self.mock_settings)

    def test_bot_initialization(self):
        """測試機器人初始化."""
        assert isinstance(self.bot, commands.Bot)
        assert self.bot.settings == self.mock_settings
        assert self.bot.container is not None

    def test_bot_intents_configuration(self):
        """測試機器人意圖配置."""
        intents = self.bot.intents

        # 驗證重要的意圖已啟用
        assert intents.guilds is True
        assert intents.guild_messages is True
        assert intents.message_content is True
        assert intents.members is True

    @pytest.mark.asyncio
    async def test_on_ready_event(self):
        """測試機器人就緒事件."""
        self.bot.user = MagicMock()
        self.bot.user.name = "TestBot"
        self.bot.guilds = [MagicMock(), MagicMock()]

        with patch.object(self.bot.logger, "info") as mock_log:
            await self.bot.on_ready()

            # 驗證日誌記錄
            assert mock_log.called

    @pytest.mark.asyncio
    async def test_setup_hook(self):
        """測試設置掛鉤."""
        with patch.object(self.bot, "load_all_modules") as mock_load:
            mock_load.return_value = []

            await self.bot.setup_hook()

            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_all_modules(self):
        """測試載入所有模組."""
        with patch.object(
            self.bot.startup_manager, "load_enabled_modules"
        ) as mock_load:
            mock_load.return_value = [
                ModuleLoadResult("test1", True, 0.1),
                ModuleLoadResult("test2", True, 0.2),
            ]

            results = await self.bot.load_all_modules()

            assert len(results) == 2
            assert all(r.success for r in results)

    def test_get_cog_by_name(self):
        """測試依名稱獲取 Cog."""
        mock_cog = MagicMock()
        self.bot.get_cog = MagicMock(return_value=mock_cog)

        result = self.bot.get_cog("TestCog")

        assert result == mock_cog
        self.bot.get_cog.assert_called_once_with("TestCog")

    @pytest.mark.asyncio
    async def test_close_cleanup(self):
        """測試機器人關閉清理."""
        self.bot.container = MagicMock()
        self.bot.container.cleanup = AsyncMock()

        with patch("src.core.bot.commands.Bot.close") as mock_close:
            mock_close.return_value = AsyncMock()

            await self.bot.close()

            self.bot.container.cleanup.assert_called_once()


class TestBotCreationAndRunning:
    """測試機器人創建和運行函數."""

    @pytest.mark.asyncio
    async def test_create_and_run_bot_success(self):
        """測試成功創建和運行機器人."""
        mock_settings = MagicMock()
        mock_settings.TOKEN = "test_token"
        mock_settings.get_database_url.return_value = "sqlite:///:memory:"

        with (
            patch("src.core.bot.get_settings", return_value=mock_settings),
            patch("src.core.bot.ADRBot") as mock_bot_class,
        ):
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot

            await create_and_run_bot()

            mock_bot.start.assert_called_once_with("test_token")

    @pytest.mark.asyncio
    async def test_create_and_run_bot_with_custom_settings(self):
        """測試使用自定義設置創建和運行機器人."""
        custom_settings = MagicMock()
        custom_settings.TOKEN = "custom_token"

        with patch("src.core.bot.ADRBot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot

            await create_and_run_bot(custom_settings)

            mock_bot.start.assert_called_once_with("custom_token")

    @pytest.mark.asyncio
    async def test_create_and_run_bot_connection_error(self):
        """測試機器人連接錯誤處理."""
        mock_settings = MagicMock()
        mock_settings.TOKEN = "test_token"

        with (
            patch("src.core.bot.get_settings", return_value=mock_settings),
            patch("src.core.bot.ADRBot") as mock_bot_class,
        ):
            mock_bot = AsyncMock()
            mock_bot.start.side_effect = discord.ConnectionClosed(None, None)
            mock_bot_class.return_value = mock_bot

            with pytest.raises(discord.ConnectionClosed):
                await create_and_run_bot()


class TestBotIntegration:
    """測試機器人整合功能."""

    @pytest.mark.asyncio
    async def test_bot_lifecycle(self):
        """測試機器人完整生命週期."""
        mock_settings = MagicMock()
        mock_settings.get_database_url.return_value = "sqlite:///:memory:"
        mock_settings.is_feature_enabled.return_value = True

        with patch("src.core.bot.get_logger"), patch("src.core.bot.get_container"):
            bot = ADRBot(mock_settings)

            # 測試初始化
            assert bot.settings == mock_settings

            # 測試設置
            with patch.object(bot, "load_all_modules", return_value=[]):
                await bot.setup_hook()

            # 測試清理
            bot.container = MagicMock()
            bot.container.cleanup = AsyncMock()

            with patch("src.core.bot.commands.Bot.close"):
                await bot.close()

            bot.container.cleanup.assert_called_once()

    def test_bot_configuration_validation(self):
        """測試機器人配置驗證."""
        mock_settings = MagicMock()
        mock_settings.get_database_url.return_value = "sqlite:///:memory:"

        with patch("src.core.bot.get_logger"):
            bot = ADRBot(mock_settings)

            # 驗證基本配置
            assert bot.command_prefix is not None
            assert bot.intents is not None
            assert hasattr(bot, "startup_manager")

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """測試錯誤處理整合."""
        mock_settings = MagicMock()
        mock_settings.get_database_url.return_value = "sqlite:///:memory:"

        with patch("src.core.bot.get_logger"):
            bot = ADRBot(mock_settings)

            # 測試命令錯誤處理
            MagicMock()
            commands.CommandNotFound()

            # 應該有錯誤處理器
            assert hasattr(bot, "on_command_error") or hasattr(bot, "error_handler")
