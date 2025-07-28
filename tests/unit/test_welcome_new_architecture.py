"""
歡迎系統新架構測試模組

測試重構後的歡迎系統,包括依賴注入、配置管理和UI組件
"""

import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest
import pytest_asyncio
from discord.ext import commands

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 先導入依賴注入系統
from typing import Any, Protocol

from cogs.core.dependency_container import DependencyContainer

# 然後導入歡迎系統的新組件
from cogs.welcome.config.welcome_config import WelcomeConfig
from cogs.welcome.panel.main_view import SettingsView, UIComponentFactory


class IWelcomeDatabase(Protocol):
    async def get_settings(self, guild_id: int) -> dict[str, Any]: ...
    async def update_setting(self, guild_id: int, key: str, value: Any) -> None: ...
    async def get_background_path(self, guild_id: int) -> str | None: ...
    async def update_welcome_background(self, guild_id: int, path: str) -> None: ...
    async def exists(self, guild_id: int) -> bool: ...


class IWelcomeRenderer(Protocol):
    async def generate_welcome_image(
        self,
        member: discord.Member,
        settings: dict[str, Any],
        bg_path: str | None = None,
    ) -> io.BytesIO | None: ...
    def render_message(
        self,
        member: discord.Member,
        guild: discord.Guild,
        channel: discord.TextChannel | None,
        template: str,
    ) -> str: ...


class IWelcomeCache(Protocol):
    def get(self, guild_id: int) -> io.BytesIO | None: ...
    def set(self, guild_id: int, image: io.BytesIO) -> None: ...
    def clear(self, guild_id: int | None = None) -> None: ...


class IWelcomeConfig(Protocol):
    @property
    def background_dir(self) -> str: ...
    @property
    def cache_timeout(self) -> int: ...
    @property
    def max_cache_size(self) -> int: ...


class MockWelcomeDatabase:
    """模擬歡迎系統資料庫"""

    def __init__(self):
        self._data = {}
        self._backgrounds = {}

    async def get_settings(self, guild_id: int) -> dict:
        return self._data.get(
            guild_id,
            {
                "channel_id": None,
                "title": "歡迎 {member.display_name}",
                "description": "歡迎加入 {guild.name}",
                "message": "歡迎 {member.mention} 加入 {guild.name}!",
                "avatar_size": 100,
                "avatar_x": 50,
                "avatar_y": 50,
                "title_y": 60,
                "description_y": 120,
            },
        )

    async def update_setting(self, guild_id: int, key: str, value) -> None:
        if guild_id not in self._data:
            self._data[guild_id] = {}
        self._data[guild_id][key] = value

    async def get_background_path(self, guild_id: int) -> str:
        return self._backgrounds.get(guild_id)

    async def update_welcome_background(self, guild_id: int, path: str) -> None:
        self._backgrounds[guild_id] = path

    async def exists(self, guild_id: int) -> bool:
        return guild_id in self._data


class MockWelcomeRenderer:
    """模擬歡迎系統渲染器"""

    async def generate_welcome_image(
        self, member: discord.Member, settings: dict, bg_path: str | None = None
    ) -> io.BytesIO:
        # 生成模擬圖片
        return io.BytesIO(b"fake_image_data")

    def render_message(
        self,
        member: discord.Member,
        guild: discord.Guild,
        channel: discord.TextChannel,
        template: str,
    ) -> str:
        # 簡單的模板渲染
        return template.format(member=member, guild=guild, channel=channel)


class MockWelcomeCache:
    """模擬歡迎系統快取"""

    def __init__(self, timeout: int = 3600, max_size: int = 50):
        self._cache = {}
        self.timeout = timeout
        self.max_size = max_size

    def get(self, guild_id: int) -> io.BytesIO:
        return self._cache.get(guild_id)

    def set(self, guild_id: int, image: io.BytesIO) -> None:
        self._cache[guild_id] = image

    def clear(self, guild_id: int | None = None) -> None:
        if guild_id is None:
            self._cache.clear()
        else:
            self._cache.pop(guild_id, None)


class TestWelcomeConfig:
    """測試歡迎系統配置"""

    def test_init_with_defaults(self):
        """測試使用預設值初始化配置"""
        config = WelcomeConfig()

        assert config.background_dir is not None
        assert config.cache_timeout == 3600  # 預設1小時
        assert config.max_cache_size == 50  # 預設50個項目

    def test_init_with_custom_values(self):
        """測試使用自訂值初始化配置"""
        config = WelcomeConfig(
            background_dir="/custom/path", cache_timeout=7200, max_cache_size=100
        )

        assert config.background_dir == "/custom/path"
        assert config.cache_timeout == 7200
        assert config.max_cache_size == 100

    def test_update_config(self):
        """測試動態更新配置"""
        config = WelcomeConfig()

        config.update_config(cache_timeout=1800)
        assert config.cache_timeout == 1800

    def test_to_dict(self):
        """測試轉換為字典格式"""
        config = WelcomeConfig(
            background_dir="/test", cache_timeout=3600, max_cache_size=25
        )

        result = config.to_dict()
        expected = {
            "background_dir": "/test",
            "cache_timeout": 3600,
            "max_cache_size": 25,
        }

        assert result == expected


# 創建簡化的WelcomeCog用於測試
class TestWelcomeCog:
    """簡化的WelcomeCog用於測試"""

    def __init__(self, bot, container=None):
        self.bot = bot
        self._container = container
        self._initialized = False
        self._db = None
        self._renderer = None
        self._cache = None
        self._config = None

    async def initialize(self):
        """初始化服務"""
        if self._initialized:
            return

        if self._container:
            self._db = await self._container.resolve(IWelcomeDatabase)
            self._renderer = await self._container.resolve(IWelcomeRenderer)
            self._cache = await self._container.resolve(IWelcomeCache)
            self._config = await self._container.resolve(IWelcomeConfig)
            self._initialized = True

    @property
    def db(self):
        if not self._db:
            raise RuntimeError("歡迎系統尚未初始化")
        return self._db

    @property
    def renderer(self):
        if not self._renderer:
            raise RuntimeError("歡迎系統尚未初始化")
        return self._renderer

    @property
    def cache(self):
        if not self._cache:
            raise RuntimeError("歡迎系統尚未初始化")
        return self._cache

    @property
    def config(self):
        if not self._config:
            raise RuntimeError("歡迎系統尚未初始化")
        return self._config

    async def _get_welcome_channel(self, guild_id):
        """獲取歡迎頻道"""
        try:
            settings = await self.db.get_settings(guild_id)
            channel_id = settings.get("channel_id")

            if not channel_id:
                return None

            channel = self.bot.get_channel(channel_id)
            return channel if isinstance(channel, discord.TextChannel) else None
        except Exception:
            return None

    async def _generate_welcome_image(self, guild_id, member, force_refresh=False):
        """生成歡迎圖片"""
        try:
            if not force_refresh:
                cached = self.cache.get(guild_id)
                if cached:
                    return cached

            settings = await self.db.get_settings(guild_id)
            bg_path = await self.db.get_background_path(guild_id)

            image = await self.renderer.generate_welcome_image(
                member, settings, bg_path
            )

            if image:
                self.cache.set(guild_id, image)
                return self.cache.get(guild_id)

            return None
        except Exception:
            return None

    def clear_image_cache(self, guild_id=None):
        """清除圖片快取"""
        self.cache.clear(guild_id)


class TestUIComponentFactory:
    """測試UI組件工廠"""

    @pytest.fixture
    def factory(self):
        """創建UI組件工廠"""
        return UIComponentFactory()

    @pytest.fixture
    def mock_cog(self):
        """創建模擬的WelcomeCog"""
        mock_cog = Mock()
        return mock_cog

    def test_create_modal_channel(self, factory, mock_cog):
        """測試創建頻道設定對話框"""
        with patch("cogs.welcome.panel.components.modals.SetChannelModal") as MockModal:
            factory.create_modal("channel", mock_cog)
            MockModal.assert_called_once_with(mock_cog, None)

    def test_create_modal_invalid_type(self, factory, mock_cog):
        """測試創建無效類型的對話框"""
        with pytest.raises(ValueError, match="未知的對話框類型"):
            factory.create_modal("invalid_type", mock_cog)


class TestWelcomeCogNewArchitecture:
    """測試重構後的歡迎系統Cog"""

    @pytest_asyncio.fixture
    async def mock_container(self):
        """創建模擬的依賴注入容器"""
        container = Mock()

        # 設置模擬服務
        container.resolve = AsyncMock()
        container.resolve.side_effect = lambda service_type: {
            IWelcomeDatabase: MockWelcomeDatabase(),
            IWelcomeRenderer: MockWelcomeRenderer(),
            IWelcomeCache: MockWelcomeCache(),
            IWelcomeConfig: WelcomeConfig(),
        }[service_type]

        return container

    @pytest_asyncio.fixture
    async def mock_bot(self):
        """創建模擬機器人"""
        bot = Mock(spec=commands.Bot)
        bot.get_channel = Mock(return_value=None)
        return bot

    @pytest_asyncio.fixture
    async def welcome_cog(self, mock_bot, mock_container):
        """創建重構後的歡迎系統Cog"""
        cog = TestWelcomeCog(mock_bot, mock_container)
        await cog.initialize()
        return cog

    @pytest.mark.asyncio
    async def test_initialization(self, welcome_cog):
        """測試Cog初始化"""
        assert welcome_cog._initialized is True
        assert welcome_cog._db is not None
        assert welcome_cog._renderer is not None
        assert welcome_cog._cache is not None
        assert welcome_cog._config is not None

    @pytest.mark.asyncio
    async def test_property_access_before_init(self, mock_bot):
        """測試初始化前訪問屬性會拋出錯誤"""
        cog = TestWelcomeCog(mock_bot)

        with pytest.raises(RuntimeError, match="歡迎系統尚未初始化"):
            _ = cog.db

    @pytest.mark.asyncio
    async def test_get_welcome_channel_success(self, welcome_cog):
        """測試成功獲取歡迎頻道"""
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.id = 123456789

        welcome_cog.bot.get_channel.return_value = mock_channel

        # 設置模擬數據庫返回
        await welcome_cog.db.update_setting(12345, "channel_id", 123456789)

        channel = await welcome_cog._get_welcome_channel(12345)
        assert channel is not None
        assert channel.id == 123456789

    @pytest.mark.asyncio
    async def test_get_welcome_channel_not_set(self, welcome_cog):
        """測試歡迎頻道未設定"""
        channel = await welcome_cog._get_welcome_channel(12345)
        assert channel is None

    @pytest.mark.asyncio
    async def test_generate_welcome_image_success(self, welcome_cog):
        """測試成功生成歡迎圖片"""
        mock_member = Mock(spec=discord.Member)
        mock_member.guild.id = 12345
        mock_member.id = 987654321
        mock_member.display_name = "TestUser"

        image = await welcome_cog._generate_welcome_image(12345, mock_member)
        assert image is not None
        assert isinstance(image, io.BytesIO)

    @pytest.mark.asyncio
    async def test_generate_welcome_image_with_cache(self, welcome_cog):
        """測試使用快取生成歡迎圖片"""
        mock_member = Mock(spec=discord.Member)
        mock_member.guild.id = 12345

        # 預先設定快取
        cached_image = io.BytesIO(b"cached_data")
        welcome_cog.cache.set(12345, cached_image)

        image = await welcome_cog._generate_welcome_image(12345, mock_member)
        assert image is not None
        assert image.getvalue() == b"cached_data"

    def test_clear_image_cache(self, welcome_cog):
        """測試清除圖片快取"""
        # 設定快取
        welcome_cog.cache.set(12345, io.BytesIO(b"data1"))
        welcome_cog.cache.set(67890, io.BytesIO(b"data2"))

        # 清除特定快取
        welcome_cog.clear_image_cache(12345)
        assert welcome_cog.cache.get(12345) is None
        assert welcome_cog.cache.get(67890) is not None

        # 清除所有快取
        welcome_cog.clear_image_cache()
        assert welcome_cog.cache.get(67890) is None


class TestSettingsViewNewArchitecture:
    """測試重構後的設定面板視圖"""

    @pytest.fixture
    def mock_cog(self):
        """創建模擬的WelcomeCog"""
        cog = Mock()
        cog.db = MockWelcomeDatabase()
        cog.renderer = MockWelcomeRenderer()
        cog.cache = MockWelcomeCache()
        cog.config = WelcomeConfig()
        return cog

    @pytest.fixture
    def mock_ui_factory(self):
        """創建模擬的UI工廠"""
        factory = Mock()
        factory.create_modal = Mock()
        return factory

    @pytest.fixture
    def settings_view(self, mock_cog, mock_ui_factory):
        """創建設定面板視圖"""
        return SettingsView(mock_cog, mock_ui_factory)

    def test_initialization(self, settings_view, mock_cog, mock_ui_factory):
        """測試視圖初始化"""
        assert settings_view.cog == mock_cog
        assert settings_view.ui_factory == mock_ui_factory
        assert settings_view.panel_msg is None


class TestIntegration:
    """整合測試"""

    @pytest.mark.asyncio
    async def test_full_dependency_injection_flow(self):
        """測試完整的依賴注入流程"""
        # 創建依賴注入容器
        container = DependencyContainer()
        await container.initialize()

        # 註冊測試服務
        container.register_instance(IWelcomeConfig, WelcomeConfig())
        container.register_instance(IWelcomeDatabase, MockWelcomeDatabase())
        container.register_instance(IWelcomeRenderer, MockWelcomeRenderer())
        container.register_instance(IWelcomeCache, MockWelcomeCache())

        # 創建並初始化Cog
        bot = Mock(spec=commands.Bot)
        cog = TestWelcomeCog(bot, container)
        await cog.initialize()

        # 驗證所有服務都已正確解析
        assert cog._initialized is True
        assert isinstance(cog.db, MockWelcomeDatabase)
        assert isinstance(cog.renderer, MockWelcomeRenderer)
        assert isinstance(cog.cache, MockWelcomeCache)
        assert isinstance(cog.config, WelcomeConfig)

    @pytest.mark.asyncio
    async def test_error_handling_in_services(self):
        """測試服務中的錯誤處理"""
        # 創建會拋出錯誤的模擬服務
        error_db = Mock()
        error_db.get_settings = AsyncMock(side_effect=Exception("Database error"))

        container = DependencyContainer()
        await container.initialize()
        container.register_instance(IWelcomeDatabase, error_db)
        container.register_instance(IWelcomeConfig, WelcomeConfig())
        container.register_instance(IWelcomeRenderer, MockWelcomeRenderer())
        container.register_instance(IWelcomeCache, MockWelcomeCache())

        bot = Mock(spec=commands.Bot)
        cog = TestWelcomeCog(bot, container)
        await cog.initialize()

        # 測試錯誤處理 - 獲取歡迎頻道應該返回None而不是拋出錯誤
        result = await cog._get_welcome_channel(12345)
        assert result is None
