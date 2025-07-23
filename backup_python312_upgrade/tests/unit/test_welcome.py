"""
歡迎系統測試模組

測試 WelcomeCog、WelcomeDB、WelcomeRenderer 和 WelcomeCache 的功能
"""

import pytest
import pytest_asyncio
import asyncio
import io
import os
import tempfile
import discord
from discord.ext import commands
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from PIL import Image

# 導入要測試的模組
from cogs.welcome.main.main import WelcomeCog
from cogs.welcome.database.database import WelcomeDB
from cogs.welcome.main.renderer import WelcomeRenderer, TemplateStyle, DefaultTemplate, AvatarDownloader, FontManager, LayoutCalculator, TemplateManager
from cogs.welcome.main.cache import WelcomeCache


class TestWelcomeRenderer:
    """測試歡迎系統渲染器"""
    
    @pytest.fixture
    def renderer(self):
        """創建渲染器實例"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield WelcomeRenderer(temp_dir)
    
    def test_init(self):
        """測試渲染器初始化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            renderer = WelcomeRenderer(temp_dir)
            assert renderer.welcome_bg_dir == temp_dir
            assert renderer.avatar_downloader is not None
            assert renderer.font_manager is not None
            assert renderer.layout_calculator is not None
            assert renderer.template_manager is not None
    
    @pytest.mark.asyncio
    async def test_generate_welcome_image_success(self, renderer):
        """測試歡迎圖片生成成功"""
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 123456789
        mock_member.display_avatar.replace.return_value.url = "https://example.com/avatar.png"
        mock_member.display_name = "TestUser"
        mock_member.guild.name = "TestGuild"
        
        # 模擬頭像物件
        mock_avatar = Mock()
        mock_avatar.key = "test_avatar_key"
        mock_member.avatar = mock_avatar
        
        settings = {
            "title": "歡迎 {member.display_name}",
            "description": "歡迎加入 {guild.name}",
            "avatar_size": 100,
            "avatar_x": 50,
            "avatar_y": 50,
            "title_y": 60,
            "description_y": 120
        }
        
        # 模擬 AvatarDownloader.get_avatar 方法
        test_avatar = Image.new('RGBA', (256, 256), (255, 0, 0, 255))
        with patch.object(renderer.avatar_downloader, 'get_avatar', return_value=test_avatar):
            result = await renderer.generate_welcome_image(mock_member, settings)
            assert result is not None
            assert isinstance(result, io.BytesIO)
    
    def test_render_message(self, renderer):
        """測試訊息渲染"""
        mock_member = Mock(spec=discord.Member)
        mock_member.display_name = "TestUser"
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.name = "TestGuild"
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.name = "welcome"
        
        template = "歡迎 {member.display_name} 加入 {guild.name}"
        result = renderer.render_message(mock_member, mock_guild, mock_channel, template)
        assert "TestUser" in result
        assert "TestGuild" in result


class TestAvatarDownloader:
    """測試頭像下載器"""
    
    @pytest.fixture
    def downloader(self):
        """創建下載器實例"""
        return AvatarDownloader()
    
    @pytest.mark.asyncio
    async def test_get_session(self, downloader):
        """測試HTTP會話獲取"""
        session = await downloader.get_session()
        assert session is not None
        assert not session.closed
        
        # 測試重複調用返回同一個會話
        session2 = await downloader.get_session()
        assert session2 is session
    
    @pytest.mark.asyncio
    async def test_get_avatar_success(self, downloader):
        """測試頭像獲取成功"""
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 123456789
        mock_member.display_avatar.replace.return_value.url = "https://example.com/avatar.png"
        
        # 模擬頭像物件
        mock_avatar = Mock()
        mock_avatar.key = "test_avatar_key"
        mock_member.avatar = mock_avatar
        
        # 模擬成功的頭像下載
        test_image_data = b"fake_avatar_data"
        with patch.object(downloader, 'download_with_retry', return_value=test_image_data):
            with patch.object(downloader, 'process_avatar') as mock_process:
                test_avatar = Image.new('RGBA', (256, 256), (255, 0, 0, 255))
                mock_process.return_value = test_avatar
                
                result = await downloader.get_avatar(mock_member)
                assert result is not None
                assert isinstance(result, Image.Image)
    
    @pytest.mark.asyncio
    async def test_get_avatar_failure_fallback(self, downloader):
        """測試頭像獲取失敗時的預設回退"""
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 123456789
        mock_member.display_avatar.replace.return_value.url = "https://example.com/avatar.png"
        
        # 模擬頭像物件
        mock_avatar = Mock()
        mock_avatar.key = "test_avatar_key"
        mock_member.avatar = mock_avatar
        
        # 模擬下載失敗
        with patch.object(downloader, 'download_with_retry', return_value=None):
            with patch.object(downloader, 'get_default_avatar') as mock_default:
                test_avatar = Image.new('RGBA', (256, 256), (128, 128, 128, 255))
                mock_default.return_value = test_avatar
                
                result = await downloader.get_avatar(mock_member)
                assert result is not None
                assert isinstance(result, Image.Image)
                mock_default.assert_called_once()


class TestFontManager:
    """測試字體管理器"""
    
    @pytest.fixture
    def font_manager(self):
        """創建字體管理器實例"""
        return FontManager()
    
    def test_get_font(self, font_manager):
        """測試字體獲取"""
        font = font_manager.get_font(24)
        assert font is not None
        
        # 測試快取
        font2 = font_manager.get_font(24)
        assert font2 is font


class TestLayoutCalculator:
    """測試佈局計算器"""
    
    @pytest.fixture
    def calculator(self):
        """創建佈局計算器實例"""
        return LayoutCalculator()
    
    def test_calculate_layout(self, calculator):
        """測試佈局計算"""
        template = DefaultTemplate()
        layout = calculator.calculate_layout(template, "TestUser", "TestGuild")
        
        assert layout.canvas_size is not None
        assert layout.avatar_position is not None
        assert layout.avatar_size > 0
        assert layout.title_position is not None
        assert layout.description_position is not None


class TestTemplateManager:
    """測試模板管理器"""
    
    @pytest.fixture
    def template_manager(self):
        """創建模板管理器實例"""
        return TemplateManager()
    
    def test_get_template(self, template_manager):
        """測試模板獲取"""
        template = template_manager.get_template(TemplateStyle.DEFAULT)
        assert template is not None
        assert template.name == "default"
        
        # 測試不同模板風格
        minimal_template = template_manager.get_template(TemplateStyle.MINIMAL)
        assert minimal_template.name == "minimal"
        
        neon_template = template_manager.get_template(TemplateStyle.NEON)
        assert neon_template.name == "neon"


class TestWelcomeCache:
    """測試歡迎系統快取"""
    
    @pytest.fixture
    def cache(self):
        """創建快取實例"""
        return WelcomeCache(timeout=60, max_size=5)
    
    def test_init(self):
        """測試快取初始化"""
        cache = WelcomeCache(timeout=120, max_size=10)
        assert cache.timeout == 120
        assert cache.max_size == 10
        assert cache._cache == {}
    
    def test_set_and_get(self, cache):
        """測試設定和獲取快取"""
        guild_id = 12345
        image_data = io.BytesIO(b"test_image_data")
        
        # 設定快取
        cache.set(guild_id, image_data)
        
        # 獲取快取
        result = cache.get(guild_id)
        assert result is not None
        assert isinstance(result, io.BytesIO)
        assert result.getvalue() == b"test_image_data"
    
    def test_get_nonexistent(self, cache):
        """測試獲取不存在的快取"""
        result = cache.get(99999)
        assert result is None
    
    def test_cache_expiry(self, cache):
        """測試快取過期"""
        cache.timeout = 0.1  # 設定很短的過期時間
        guild_id = 12345
        image_data = io.BytesIO(b"test_image_data")
        
        cache.set(guild_id, image_data)
        
        # 等待過期
        import time
        time.sleep(0.2)
        
        result = cache.get(guild_id)
        assert result is None
    
    def test_max_size_limit(self, cache):
        """測試快取大小限制"""
        cache.max_size = 2
        
        # 添加超過最大大小的項目
        for i in range(3):
            image_data = io.BytesIO(f"test_image_data_{i}".encode())
            cache.set(i, image_data)
        
        # 檢查只保留最新的項目
        assert len(cache._cache) == 2
        assert cache.get(0) is None  # 最舊的應該被移除
        assert cache.get(1) is not None
        assert cache.get(2) is not None
    
    def test_clear_specific(self, cache):
        """測試清除特定快取"""
        guild_id1 = 12345
        guild_id2 = 67890
        
        cache.set(guild_id1, io.BytesIO(b"data1"))
        cache.set(guild_id2, io.BytesIO(b"data2"))
        
        cache.clear(guild_id1)
        
        assert cache.get(guild_id1) is None
        assert cache.get(guild_id2) is not None
    
    def test_clear_all(self, cache):
        """測試清除所有快取"""
        cache.set(12345, io.BytesIO(b"data1"))
        cache.set(67890, io.BytesIO(b"data2"))
        
        cache.clear()
        
        assert cache.get(12345) is None
        assert cache.get(67890) is None
        assert len(cache._cache) == 0


class TestWelcomeDB:
    """測試歡迎系統資料庫"""
    
    @pytest_asyncio.fixture
    async def db(self):
        """創建資料庫實例"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            db = WelcomeDB(temp_path)
            await db.init_db()
            yield db
        finally:
            # 清理
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
    
    @pytest.mark.asyncio
    async def test_init_db(self, db):
        """測試資料庫初始化"""
        # 資料庫應該已經初始化
        pool = await db._get_pool()
        assert pool is not None
        
        # 測試資料表是否存在
        async with pool.get_connection_context(db.db_path) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            table_names = [table[0] for table in tables]
            assert 'welcome_settings' in table_names
    
    @pytest.mark.asyncio
    async def test_get_settings_default(self, db):
        """測試獲取預設設定"""
        guild_id = 12345
        settings = await db.get_settings(guild_id)
        
        # 應該返回預設設定
        assert settings is not None
        assert isinstance(settings, dict)
    
    @pytest.mark.asyncio
    async def test_update_setting(self, db):
        """測試更新設定"""
        guild_id = 12345
        await db.update_setting(guild_id, "channel_id", 123456789)
        
        settings = await db.get_settings(guild_id)
        assert settings["channel_id"] == 123456789
    
    @pytest.mark.asyncio
    async def test_exists(self, db):
        """測試檢查設定是否存在"""
        guild_id = 12345
        
        # 初始狀態應該不存在
        exists = await db.exists(guild_id)
        assert not exists
        
        # 更新設定後應該存在
        await db.update_setting(guild_id, "channel_id", 123456789)
        exists = await db.exists(guild_id)
        assert exists
    
    @pytest.mark.asyncio
    async def test_background_operations(self, db):
        """測試背景操作"""
        guild_id = 12345
        
        # 測試並發操作 - 使用實際存在的欄位
        tasks = []
        test_values = [
            ("title", "Test Title"),
            ("description", "Test Description"),
            ("message", "Test Message"),
            ("avatar_x", 100),
            ("avatar_y", 200)
        ]
        
        for key, value in test_values:
            task = asyncio.create_task(
                db.update_setting(guild_id, key, value)
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # 驗證所有設定都已保存
        settings = await db.get_settings(guild_id)
        for key, value in test_values:
            assert settings[key] == value


class TestWelcomeCog:
    """測試歡迎系統主要功能"""
    
    @pytest.fixture
    def mock_bot(self):
        """創建模擬機器人"""
        bot = Mock(spec=commands.Bot)
        bot.get_channel = Mock(return_value=None)
        return bot
    
    @pytest.fixture
    def welcome_cog(self, mock_bot):
        """創建歡迎系統 Cog"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 創建測試用的背景目錄
            bg_dir = os.path.join(temp_dir, "backgrounds")
            os.makedirs(bg_dir, exist_ok=True)
            
            # 創建測試用的資料庫
            db_path = os.path.join(temp_dir, "test.db")
            
            # 模擬配置
            with patch('cogs.welcome.main.main.WELCOME_BG_DIR', bg_dir):
                with patch('config.WELCOME_DB_PATH', db_path):
                    cog = WelcomeCog(mock_bot)
                    yield cog
    
    @pytest.mark.asyncio
    async def test_get_welcome_channel_success(self, welcome_cog):
        """測試獲取歡迎頻道成功"""
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.id = 123456789
        
        welcome_cog.bot.get_channel.return_value = mock_channel
        
        with patch.object(welcome_cog.db, 'get_settings', return_value={"channel_id": 123456789}):
            channel = await welcome_cog._get_welcome_channel(12345)
            assert channel is not None
            assert channel.id == 123456789
    
    @pytest.mark.asyncio
    async def test_get_welcome_channel_not_set(self, welcome_cog):
        """測試歡迎頻道未設定"""
        with patch.object(welcome_cog.db, 'get_settings', return_value={"channel_id": None}):
            channel = await welcome_cog._get_welcome_channel(12345)
            assert channel is None
    
    @pytest.mark.asyncio
    async def test_generate_welcome_image_with_cache(self, welcome_cog):
        """測試生成歡迎圖片（有快取）"""
        mock_member = Mock(spec=discord.Member)
        mock_member.guild.id = 12345
        
        cached_image = io.BytesIO(b"cached_image_data")
        welcome_cog.cache.set(12345, cached_image)
        
        result = await welcome_cog._generate_welcome_image(12345, mock_member)
        assert result is not None
        assert isinstance(result, io.BytesIO)
    
    @pytest.mark.asyncio
    async def test_generate_welcome_image_no_cache(self, welcome_cog):
        """測試生成歡迎圖片（無快取）"""
        mock_member = Mock(spec=discord.Member)
        mock_member.guild.id = 12345
        mock_member.id = 987654321
        mock_member.display_name = "TestUser"
        
        # 模擬頭像物件
        mock_avatar = Mock()
        mock_avatar.key = "test_avatar_key"
        mock_member.avatar = mock_avatar
        
        settings = {"title": "Welcome", "description": "Test"}
        
        # 模擬渲染器生成圖片和數據庫操作
        test_image = io.BytesIO(b"generated_image_data")
        with patch.object(welcome_cog.renderer, 'generate_welcome_image', return_value=test_image):
            with patch.object(welcome_cog.db, 'get_settings', return_value=settings):
                with patch.object(welcome_cog.db, 'get_background_path', return_value=None):
                    result = await welcome_cog._generate_welcome_image(12345, mock_member)
                    assert result is not None
                    assert isinstance(result, io.BytesIO)
    
    @pytest.mark.asyncio
    async def test_on_member_join(self, welcome_cog):
        """測試成員加入事件"""
        mock_member = Mock(spec=discord.Member)
        mock_member.guild.id = 12345
        mock_member.display_name = "TestUser"
        
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()
        
        with patch.object(welcome_cog, '_get_welcome_channel', return_value=mock_channel):
            with patch.object(welcome_cog.db, 'get_settings', return_value={"message": "Welcome!"}):
                with patch.object(welcome_cog, '_generate_welcome_image', return_value=io.BytesIO(b"image")):
                    await welcome_cog.on_member_join(mock_member)
                    mock_channel.send.assert_called_once()
    
    def test_safe_int(self, welcome_cog):
        """測試安全整數轉換"""
        assert welcome_cog._safe_int("123", 0) == 123
        assert welcome_cog._safe_int("invalid", 0) == 0
        assert welcome_cog._safe_int(None, 42) == 42
    
    def test_clear_image_cache(self, welcome_cog):
        """測試清除圖片快取"""
        # 設定一些快取
        welcome_cog.cache.set(12345, io.BytesIO(b"data1"))
        welcome_cog.cache.set(67890, io.BytesIO(b"data2"))
        
        # 清除特定快取
        welcome_cog.clear_image_cache(12345)
        assert welcome_cog.cache.get(12345) is None
        assert welcome_cog.cache.get(67890) is not None
        
        # 清除所有快取
        welcome_cog.clear_image_cache()
        assert welcome_cog.cache.get(67890) is None


class TestWelcomeIntegration:
    """測試歡迎系統整合功能"""
    
    @pytest.mark.asyncio
    async def test_full_welcome_flow(self):
        """測試完整的歡迎流程"""
        # 這個測試需要完整的環境設定
        # 暫時跳過，留待後續完善
        pass 