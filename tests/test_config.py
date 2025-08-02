"""
新架構測試配置 - 修復測試環境和導入問題

此模組提供新架構的測試環境配置,包括:
- 修復導入路徑問題
- 設置依賴注入測試環境
- 提供模擬服務和工具
- 建立覆蓋率測試機制

符合 TASK-005: 測試環境建立與修復的要求
"""

import asyncio
import os
import sys
import tempfile
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# 添加src目錄到Python路徑以解決導入問題
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import contextlib

import discord
from discord.ext import commands

# 導入歡迎模組 - 使用正確的導入路徑
from src.cogs.welcome.config.welcome_config import WelcomeConfig
from src.cogs.welcome.database.database import WelcomeDB as WelcomeRepository
from src.core.config import Settings

# 導入新架構的核心模組
from src.core.database import DatabasePool
from src.core.logger import BotLogger
from src.core.monitor import PerformanceMonitor


class TestContainer:
    """測試用的依賴注入容器"""

    def __init__(self):
        self._services = {}
        self._setup_test_services()

    def _setup_test_services(self):
        """設置測試服務"""
        # 創建模擬日誌服務
        self._services[BotLogger] = MagicMock(spec=BotLogger)
        self._services[BotLogger].info = MagicMock()
        self._services[BotLogger].error = MagicMock()
        self._services[BotLogger].debug = MagicMock()
        self._services[BotLogger].warning = MagicMock()

        # 創建模擬性能監控服務
        self._services[PerformanceMonitor] = MagicMock(spec=PerformanceMonitor)
        self._services[PerformanceMonitor].track_operation = MagicMock()

        # 創建模擬設定服務
        self._services[Settings] = MagicMock(spec=Settings)

        # 創建模擬數據庫服務
        self._services[DatabasePool] = MagicMock(spec=DatabasePool)

    def get(self, service_type):
        """獲取服務實例"""
        return self._services.get(service_type)

    def register(self, service_type, instance):
        """註冊服務實例"""
        self._services[service_type] = instance


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """創建事件循環用於測試"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """設置測試環境變數"""
    # 設置環境變數
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # 創建測試目錄
    test_dirs = [
        "/tmp/test_project/data",
        "/tmp/test_project/logs",
        "/tmp/test_project/dbs",
        "/tmp/test_project/data/backgrounds",
        "/tmp/test_project/fonts",
    ]

    for dir_path in test_dirs:
        os.makedirs(dir_path, exist_ok=True)

    # 設置測試路徑
    monkeypatch.setenv("PROJECT_ROOT", "/tmp/test_project")
    monkeypatch.setenv("WELCOME_BG_DIR", "/tmp/test_project/data/backgrounds")
    monkeypatch.setenv("FONTS_DIR", "/tmp/test_project/fonts")


@pytest_asyncio.fixture
async def test_container() -> AsyncGenerator[TestContainer, None]:
    """提供測試用的依賴注入容器"""
    container = TestContainer()
    yield container


@pytest.fixture
def mock_discord_guild() -> discord.Guild:
    """模擬Discord伺服器"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "測試伺服器"
    guild.member_count = 100
    guild.owner_id = 111111111
    guild.get_member.return_value = None
    guild.get_channel.return_value = None
    guild.get_role.return_value = None
    guild.channels = []
    guild.roles = []
    guild.members = []

    # 機器人成員
    guild.me = MagicMock(spec=discord.Member)
    guild.me.guild_permissions = discord.Permissions.all()

    return guild


@pytest.fixture
def mock_discord_user() -> discord.User:
    """模擬Discord用戶"""
    user = MagicMock(spec=discord.User)
    user.id = 987654321
    user.name = "測試用戶"
    user.display_name = "測試用戶"
    user.discriminator = "0001"
    user.bot = False
    user.mention = f"<@{user.id}>"

    # 頭像設置
    user.display_avatar = MagicMock()
    user.display_avatar.url = "https://cdn.discordapp.com/avatars/987654321/avatar.png"
    user.display_avatar.replace.return_value.url = user.display_avatar.url

    return user


@pytest.fixture
def mock_discord_member(mock_discord_guild, mock_discord_user) -> discord.Member:
    """模擬Discord成員"""
    member = MagicMock(spec=discord.Member)
    member.id = mock_discord_user.id
    member.name = mock_discord_user.name
    member.display_name = mock_discord_user.display_name
    member.discriminator = mock_discord_user.discriminator
    member.bot = False
    member.guild = mock_discord_guild
    member.mention = mock_discord_user.mention
    member.display_avatar = mock_discord_user.display_avatar

    # 權限設置
    member.guild_permissions = MagicMock(spec=discord.Permissions)
    member.guild_permissions.administrator = False
    member.guild_permissions.manage_guild = False

    return member


@pytest.fixture
def mock_discord_channel(mock_discord_guild) -> discord.TextChannel:
    """模擬Discord文字頻道"""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 555666777
    channel.name = "測試頻道"
    channel.guild = mock_discord_guild
    channel.type = discord.ChannelType.text
    channel.mention = f"<#{channel.id}>"

    # 異步方法
    channel.send = AsyncMock()
    channel.edit = AsyncMock()
    channel.delete = AsyncMock()

    # 權限檢查
    channel.permissions_for = MagicMock(return_value=discord.Permissions.all())

    return channel


@pytest.fixture
def mock_discord_interaction(
    mock_discord_guild, mock_discord_member
) -> discord.Interaction:
    """模擬Discord互動"""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.guild = mock_discord_guild
    interaction.user = mock_discord_member
    interaction.guild_id = mock_discord_guild.id
    interaction.id = 333444555
    interaction.token = "test_token"

    # 響應方法
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done.return_value = False

    # 跟進方法
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()

    return interaction


@pytest.fixture
def mock_discord_bot() -> commands.Bot:
    """模擬Discord機器人"""
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 111111111
    bot.user.name = "測試機器人"
    bot.user.bot = True

    # 異步方法
    bot.add_cog = AsyncMock()
    bot.load_extension = AsyncMock()
    bot.get_guild = MagicMock()
    bot.get_channel = MagicMock()
    bot.get_user = MagicMock()

    return bot


@pytest_asyncio.fixture
async def test_database() -> AsyncGenerator[str, None]:
    """提供測試數據庫"""
    # 使用臨時文件創建測試數據庫
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        yield db_path
    finally:
        # 清理數據庫文件
        with contextlib.suppress(FileNotFoundError):
            os.unlink(db_path)


@pytest_asyncio.fixture
async def welcome_config(test_container) -> WelcomeConfig:
    """提供歡迎配置實例"""
    # 創建真實的配置實例,但使用測試容器
    settings = test_container.get(Settings)
    logger = test_container.get(BotLogger)

    config = WelcomeConfig(settings, logger)
    return config


@pytest_asyncio.fixture
async def welcome_repository(test_container, test_database) -> WelcomeRepository:
    """提供歡迎資料庫存取層實例"""
    # 創建模擬的數據庫服務
    db_service = MagicMock(spec=DatabasePool)
    db_service.get_connection = AsyncMock()

    # 模擬數據庫連接上下文
    mock_connection = AsyncMock()
    mock_connection.execute = AsyncMock()
    mock_connection.commit = AsyncMock()
    mock_connection.fetchone = AsyncMock()
    mock_connection.fetchall = AsyncMock()

    db_service.get_connection.return_value.__aenter__.return_value = mock_connection
    db_service.get_connection.return_value.__aexit__.return_value = None

    # 註冊到容器
    test_container.register(DatabasePool, db_service)

    # 創建存取層實例
    logger = test_container.get(BotLogger)
    monitor = test_container.get(PerformanceMonitor)
    config = await welcome_config(test_container)

    repository = WelcomeRepository(db_service, logger, monitor, config)
    return repository


class TestDataFactory:
    """測試數據工廠"""

    @staticmethod
    def create_welcome_settings(guild_id: int = 123456789) -> dict[str, Any]:
        """創建歡迎設定測試數據"""
        return {
            "guild_id": guild_id,
            "enabled": True,
            "channel_id": 555666777,
            "message": "歡迎 {member.mention} 加入 {guild.name}!",
            "title": "歡迎加入",
            "description": "感謝您的加入!",
            "enable_image": True,
            "avatar_size": 128,
            "avatar_x": 100,
            "avatar_y": 100,
            "title_y": 200,
            "desc_y": 240,
            "title_font_size": 36,
            "desc_font_size": 24,
        }

    @staticmethod
    def create_guild_config_data(guild_id: int = 123456789) -> dict[str, Any]:
        """創建伺服器配置測試數據"""
        settings = TestDataFactory.create_welcome_settings(guild_id)
        return {
            "guild_id": guild_id,
            "message_settings": {
                "enabled": settings["enabled"],
                "channel_id": settings["channel_id"],
                "message": settings["message"],
                "title": settings["title"],
                "description": settings["description"],
            },
            "image_settings": {
                "enable_image": settings["enable_image"],
                "avatar_size": settings["avatar_size"],
                "avatar_x": settings["avatar_x"],
                "avatar_y": settings["avatar_y"],
                "title_y": settings["title_y"],
                "desc_y": settings["desc_y"],
                "title_font_size": settings["title_font_size"],
                "desc_font_size": settings["desc_font_size"],
                "background_path": None,
            },
        }


@pytest.fixture
def test_data_factory() -> TestDataFactory:
    """提供測試數據工廠"""
    return TestDataFactory()


class AsyncContextManager:
    """異步上下文管理器幫助類"""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_async_context_mock(return_value=None):
    """創建異步上下文管理器模擬"""
    return AsyncContextManager(return_value)


class TestAssertions:
    """測試斷言幫助類"""

    @staticmethod
    def assert_discord_id_valid(discord_id: int):
        """驗證Discord ID格式"""
        assert isinstance(discord_id, int), "Discord ID必須是整數"
        assert discord_id > 0, "Discord ID必須大於0"
        assert len(str(discord_id)) >= 17, "Discord ID長度不足"

    @staticmethod
    def assert_settings_valid(settings: dict[str, Any]):
        """驗證設定數據格式"""
        assert isinstance(settings, dict), "設定必須是字典"
        assert "guild_id" in settings, "設定必須包含guild_id"
        TestAssertions.assert_discord_id_valid(settings["guild_id"])

    @staticmethod
    async def assert_async_no_exception(coro):
        """驗證異步函數不拋出異常"""
        try:
            result = await coro
            return result
        except Exception as e:
            pytest.fail(f"異步函數拋出了異常: {e}")

    @staticmethod
    def assert_mock_called_with_partial(mock, **expected_kwargs):
        """驗證Mock被調用且包含期望的參數"""
        assert mock.called, "Mock應該被調用"
        call_args = mock.call_args
        if call_args:
            _, actual_kwargs = call_args
            for key, expected_value in expected_kwargs.items():
                assert key in actual_kwargs, f"期望參數 {key} 不存在"
                assert actual_kwargs[key] == expected_value, f"參數 {key} 值不匹配"


@pytest.fixture
def test_assertions() -> TestAssertions:
    """提供測試斷言幫助類"""
    return TestAssertions()


class PerformanceMonitor:
    """性能監控幫助類"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """開始監控"""

        self.start_time = time.perf_counter()

    def stop(self):
        """停止監控"""

        self.end_time = time.perf_counter()

    @property
    def elapsed(self) -> float:
        """獲取耗時"""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    def assert_performance(self, max_time: float):
        """斷言性能在接受範圍內"""
        assert self.elapsed <= max_time, (
            f"執行時間 {self.elapsed:.3f}s 超過限制 {max_time:.3f}s"
        )


@pytest.fixture
def performance_monitor() -> PerformanceMonitor:
    """提供性能監控"""
    return PerformanceMonitor()


# 測試標記配置
def pytest_configure(config):
    """配置pytest標記"""
    config.addinivalue_line("markers", "unit: 單元測試")
    config.addinivalue_line("markers", "integration: 整合測試")
    config.addinivalue_line("markers", "slow: 慢速測試")
    config.addinivalue_line("markers", "database: 數據庫測試")
    config.addinivalue_line("markers", "network: 網路測試")
    config.addinivalue_line("markers", "performance: 性能測試")
    config.addinivalue_line("markers", "security: 安全測試")


# 測試收集鉤子
def pytest_collection_modifyitems(config, items):
    """修改測試收集項目"""
    for item in items:
        # 為所有異步測試添加asyncio標記
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)

        # 為包含數據庫操作的測試添加database標記
        if "database" in item.name.lower() or "db" in item.name.lower():
            item.add_marker(pytest.mark.database)

        # 為包含網路操作的測試添加network標記
        if "network" in item.name.lower() or "http" in item.name.lower():
            item.add_marker(pytest.mark.network)


# 測試運行配置
def pytest_runtest_setup(item):
    """測試運行前設置"""
    # 檢查是否需要跳過慢速測試
    if item.get_closest_marker("slow") and not item.config.getoption("--runslow"):
        pytest.skip("需要 --runslow 選項來運行慢速測試")


def pytest_addoption(parser):
    """添加命令行選項"""
    parser.addoption(
        "--runslow", action="store_true", default=False, help="運行標記為slow的測試"
    )
    parser.addoption(
        "--runintegration", action="store_true", default=False, help="運行整合測試"
    )
