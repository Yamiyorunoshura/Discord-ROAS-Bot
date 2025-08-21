"""
歡迎服務測試
Task ID: 9 - 重構現有模組以符合新架構
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
import discord

from services.welcome.welcome_service import WelcomeService
from services.welcome.models import WelcomeSettings, WelcomeImage
from core.database_manager import DatabaseManager


@pytest.fixture
async def mock_db_manager():
    """模擬資料庫管理器"""
    db_manager = Mock(spec=DatabaseManager)
    db_manager.execute = AsyncMock()
    db_manager.fetchone = AsyncMock()
    db_manager.fetchall = AsyncMock()
    return db_manager


@pytest.fixture
def welcome_config():
    """歡迎服務配置"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield {
            'bg_dir': temp_dir,
            'fonts_dir': 'fonts',
            'default_font': 'fonts/test.ttf',
        }


@pytest.fixture
async def welcome_service(mock_db_manager, welcome_config):
    """建立歡迎服務實例"""
    service = WelcomeService(mock_db_manager, welcome_config)
    await service.initialize()
    return service


@pytest.fixture
def mock_member():
    """模擬 Discord 成員"""
    member = Mock(spec=discord.Member)
    member.id = 123456789
    member.name = "TestUser"
    member.display_name = "Test User"
    member.mention = "<@123456789>"
    
    # 模擬頭像
    avatar = Mock()
    avatar.url = "https://cdn.discordapp.com/avatars/123456789/test.png"
    member.display_avatar = avatar
    
    # 模擬伺服器
    guild = Mock(spec=discord.Guild)
    guild.id = 987654321
    guild.name = "Test Guild"
    member.guild = guild
    
    return member


class TestWelcomeService:
    """歡迎服務測試類別"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_db_manager, welcome_config):
        """測試服務初始化"""
        service = WelcomeService(mock_db_manager, welcome_config)
        result = await service.initialize()
        
        assert result is True
        assert service.is_initialized
        assert service._session is not None
    
    @pytest.mark.asyncio
    async def test_get_settings_default(self, welcome_service, mock_db_manager):
        """測試獲取預設設定"""
        # 模擬沒有找到資料庫記錄
        mock_db_manager.fetchone.return_value = None
        
        settings = await welcome_service.get_settings(123456789)
        
        assert isinstance(settings, WelcomeSettings)
        assert settings.guild_id == 123456789
        assert settings.title == "歡迎 {member.name}!"
        assert settings.description == "很高興見到你～"
    
    @pytest.mark.asyncio
    async def test_get_settings_from_database(self, welcome_service, mock_db_manager):
        """測試從資料庫獲取設定"""
        # 模擬資料庫返回
        mock_row = {
            'guild_id': 123456789,
            'channel_id': 987654321,
            'title': "自訂標題",
            'description': "自訂內容",
            'message': "自訂訊息",
            'avatar_x': 50,
            'avatar_y': 100,
            'title_y': 80,
            'description_y': 140,
            'title_font_size': 40,
            'desc_font_size': 24,
            'avatar_size': 200
        }
        mock_db_manager.fetchone.return_value = mock_row
        
        settings = await welcome_service.get_settings(123456789)
        
        assert settings.guild_id == 123456789
        assert settings.channel_id == 987654321
        assert settings.title == "自訂標題"
        assert settings.description == "自訂內容"
    
    @pytest.mark.asyncio
    async def test_update_setting(self, welcome_service, mock_db_manager):
        """測試更新設定"""
        # 模擬設定存在檢查
        mock_db_manager.fetchone.return_value = {'guild_id': 123456789}
        
        result = await welcome_service.update_setting(123456789, "title", "新標題")
        
        assert result is True
        mock_db_manager.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_generate_welcome_image_basic(self, welcome_service, mock_member):
        """測試基本歡迎圖片生成"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 模擬頭像下載
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read.return_value = b"fake_image_data"
            mock_get.return_value.__aenter__.return_value = mock_response
            
            with patch('PIL.Image.open') as mock_image_open:
                # 模擬 PIL Image
                mock_img = Mock()
                mock_img.convert.return_value = mock_img
                mock_img.thumbnail = Mock()
                mock_img.size = (100, 100)
                mock_image_open.return_value = mock_img
                
                welcome_image = await welcome_service.generate_welcome_image(
                    mock_member.guild.id, mock_member
                )
                
                assert isinstance(welcome_image, WelcomeImage)
                assert welcome_image.guild_id == mock_member.guild.id
                assert welcome_image.member_id == mock_member.id
    
    @pytest.mark.asyncio
    async def test_process_member_join_no_channel(self, welcome_service, mock_member):
        """測試處理成員加入 - 未設定頻道"""
        # 模擬獲取設定（未設定頻道）
        with patch.object(welcome_service, 'get_settings') as mock_get_settings:
            mock_settings = WelcomeSettings(guild_id=mock_member.guild.id, channel_id=None)
            mock_get_settings.return_value = mock_settings
            
            result = await welcome_service.process_member_join(mock_member)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_process_member_join_success(self, welcome_service, mock_member):
        """測試處理成員加入 - 成功"""
        # 模擬獲取設定
        with patch.object(welcome_service, 'get_settings') as mock_get_settings:
            mock_settings = WelcomeSettings(guild_id=mock_member.guild.id, channel_id=123)
            mock_get_settings.return_value = mock_settings
            
            # 模擬頻道
            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_member.guild.get_channel.return_value = mock_channel
            
            # 模擬圖片生成
            with patch.object(welcome_service, 'generate_welcome_image') as mock_gen_img:
                mock_welcome_image = WelcomeImage(
                    image=Image.new("RGBA", (800, 450)),
                    guild_id=mock_member.guild.id,
                    member_id=mock_member.id
                )
                mock_gen_img.return_value = mock_welcome_image
                
                result = await welcome_service.process_member_join(mock_member)
                
                assert result is True
                mock_channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_background(self, welcome_service, mock_db_manager):
        """測試更新背景圖片"""
        result = await welcome_service.update_background(123456789, "test_bg.png")
        
        assert result is True
        mock_db_manager.execute.assert_called_with(
            "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
            (123456789, "test_bg.png")
        )
    
    def test_render_template_basic(self, welcome_service, mock_member):
        """測試範本渲染 - 基本替換"""
        template = "歡迎 {member.name} 加入 {guild.name}!"
        result = welcome_service._render_template(template, mock_member)
        
        assert result == "歡迎 TestUser 加入 Test Guild!"
    
    def test_render_template_mention(self, welcome_service, mock_member):
        """測試範本渲染 - 提及替換"""
        template = "歡迎 {member.mention} 加入伺服器!"
        result = welcome_service._render_template(template, mock_member)
        
        assert result == "歡迎 <@123456789> 加入伺服器!"
    
    def test_render_template_no_member(self, welcome_service):
        """測試範本渲染 - 無成員"""
        template = "歡迎 {member.name} 加入!"
        result = welcome_service._render_template(template, None)
        
        assert result == "歡迎 {member.name} 加入!"
    
    @pytest.mark.asyncio
    async def test_cleanup(self, welcome_service):
        """測試清理資源"""
        await welcome_service._cleanup()
        
        assert welcome_service._session is None or welcome_service._session.closed
    
    def test_clear_cache_specific_guild(self, welcome_service):
        """測試清除特定伺服器快取"""
        # 添加一些測試快取
        welcome_service._image_cache["123_456"] = Mock()
        welcome_service._image_cache["789_012"] = Mock()
        welcome_service._settings_cache[123] = Mock()
        welcome_service._settings_cache[789] = Mock()
        
        welcome_service.clear_cache(123)
        
        # 檢查快取是否正確清除
        assert "789_012" in welcome_service._image_cache
        assert 789 in welcome_service._settings_cache
    
    def test_clear_cache_all(self, welcome_service):
        """測試清除所有快取"""
        # 添加一些測試快取
        welcome_service._image_cache["123_456"] = Mock()
        welcome_service._settings_cache[123] = Mock()
        
        welcome_service.clear_cache(None)
        
        # 檢查所有快取都被清除