"""
歡迎系統整合測試
Task ID: 9 - 重構現有模組以符合新架構

測試 WelcomeService 和 WelcomePanel 的整合運作
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
import discord

from services.welcome.welcome_service import WelcomeService
from services.welcome.models import WelcomeSettings
from panels.welcome.welcome_panel import WelcomePanel
from core.database_manager import DatabaseManager


@pytest.fixture
async def integrated_welcome_system():
    """建立完整的歡迎系統（服務+面板）"""
    # 建立模擬資料庫管理器
    db_manager = Mock(spec=DatabaseManager)
    db_manager.execute = AsyncMock()
    db_manager.fetchone = AsyncMock()
    
    # 建立臨時目錄
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'bg_dir': temp_dir,
            'fonts_dir': 'fonts',
            'default_font': 'fonts/test.ttf',
        }
        
        # 建立服務和面板
        service = WelcomeService(db_manager, config)
        await service.initialize()
        
        panel = WelcomePanel(service, config)
        
        yield {
            'service': service,
            'panel': panel,
            'db_manager': db_manager,
            'config': config
        }
        
        # 清理
        await service.cleanup()


@pytest.fixture
def mock_guild_and_member():
    """模擬伺服器和成員"""
    guild = Mock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    
    member = Mock(spec=discord.Member)
    member.id = 987654321
    member.name = "TestUser"
    member.display_name = "Test User"
    member.mention = "<@987654321>"
    member.guild = guild
    
    # 模擬頭像
    avatar = Mock()
    avatar.url = "https://cdn.discordapp.com/avatars/987654321/test.png"
    member.display_avatar = avatar
    
    # 模擬頻道
    channel = Mock(spec=discord.TextChannel)
    channel.id = 555777999
    channel.send = AsyncMock()
    guild.get_channel.return_value = channel
    
    return {'guild': guild, 'member': member, 'channel': channel}


class TestWelcomeSystemIntegration:
    """歡迎系統整合測試"""
    
    @pytest.mark.asyncio
    async def test_complete_welcome_flow(self, integrated_welcome_system, mock_guild_and_member):
        """測試完整的歡迎流程"""
        system = integrated_welcome_system
        service = system['service']
        panel = system['panel']
        db_manager = system['db_manager']
        
        guild = mock_guild_and_member['guild']
        member = mock_guild_and_member['member']
        channel = mock_guild_and_member['channel']
        
        # 1. 設定歡迎頻道
        db_manager.fetchone.return_value = {'guild_id': guild.id}  # 設定存在檢查
        result = await service.update_setting(guild.id, "channel_id", channel.id)
        assert result is True
        
        # 2. 模擬獲取設定
        mock_settings_row = {
            'guild_id': guild.id,
            'channel_id': channel.id,
            'title': "歡迎 {member.name}!",
            'description': "很高興見到你～",
            'message': "歡迎 {member.mention} 加入 {guild.name}！",
            'avatar_x': 30,
            'avatar_y': 80,
            'title_y': 60,
            'description_y': 120,
            'title_font_size': 36,
            'desc_font_size': 22,
            'avatar_size': 176
        }
        db_manager.fetchone.side_effect = [mock_settings_row, None]  # 設定 + 背景
        
        # 3. 模擬頭像下載和圖片生成
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read.return_value = b"fake_avatar_data"
            mock_get.return_value.__aenter__.return_value = mock_response
            
            with patch('PIL.Image.open') as mock_image_open:
                with patch('PIL.Image.new') as mock_image_new:
                    # 模擬背景圖片
                    mock_bg_img = Mock()
                    mock_bg_img.convert.return_value = mock_bg_img
                    mock_bg_img.size = (800, 450)
                    mock_image_new.return_value = mock_bg_img
                    
                    # 模擬頭像圖片
                    mock_avatar_img = Mock()
                    mock_avatar_img.convert.return_value = mock_avatar_img
                    mock_avatar_img.thumbnail = Mock()
                    mock_avatar_img.size = (100, 100)
                    mock_image_open.return_value = mock_avatar_img
                    
                    with patch('PIL.ImageDraw.Draw') as mock_draw:
                        mock_draw_obj = Mock()
                        mock_draw.return_value = mock_draw_obj
                        
                        with patch('PIL.ImageFont.truetype') as mock_font:
                            mock_font.return_value = Mock()
                            
                            # 4. 處理成員加入
                            result = await service.process_member_join(member)
                            assert result is True
                            
                            # 驗證頻道發送訊息被調用
                            channel.send.assert_called_once()
                            call_args = channel.send.call_args
                            assert "歡迎 <@987654321> 加入 Test Guild！" in call_args[1]['content']
    
    @pytest.mark.asyncio
    async def test_settings_panel_to_service_integration(self, integrated_welcome_system):
        """測試設定面板與服務的整合"""
        system = integrated_welcome_system
        service = system['service']
        panel = system['panel']
        db_manager = system['db_manager']
        
        # 模擬 Discord 互動
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.guild.id = 123456789
        interaction.user = Mock()
        
        # 1. 模擬面板處理設定更新
        db_manager.fetchone.return_value = {'guild_id': 123456789}  # 設定存在檢查
        
        with patch.object(panel, 'send_success') as mock_success:
            with patch.object(panel, '_refresh_settings_panel') as mock_refresh:
                with patch.object(panel, 'preview_welcome_message') as mock_preview:
                    await panel.handle_setting_update(interaction, "title", "新標題")
                    
                    # 驗證服務被正確調用
                    db_manager.execute.assert_called()
                    mock_success.assert_called_once()
                    mock_refresh.assert_called_once()
                    mock_preview.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_background_upload_integration(self, integrated_welcome_system):
        """測試背景圖片上傳整合"""
        system = integrated_welcome_system
        service = system['service']
        panel = system['panel']
        db_manager = system['db_manager']
        
        # 模擬 Discord 互動
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.guild.id = 123456789
        interaction.user = Mock()
        interaction.user.id = 987654321
        interaction.channel = Mock()
        interaction.channel.id = 555777999
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.client = Mock()
        
        # 模擬上傳的檔案
        mock_message = Mock()
        mock_attachment = Mock()
        mock_attachment.filename = "test_background.png"
        mock_attachment.read = AsyncMock(return_value=b"fake_image_data")
        mock_message.attachments = [mock_attachment]
        interaction.client.wait_for.return_value = mock_message
        
        # 模擬檔案寫入
        with patch('builtins.open', create=True) as mock_open:
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            with patch.object(panel, '_refresh_settings_panel') as mock_refresh:
                with patch.object(panel, 'preview_welcome_message') as mock_preview:
                    await panel.handle_background_upload(interaction)
                    
                    # 驗證服務被調用
                    db_manager.execute.assert_called_with(
                        "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
                        (123456789, f"welcome_bg_{123456789}.png")
                    )
                    
                    # 驗證檔案被寫入
                    mock_file.write.assert_called_once_with(b"fake_image_data")
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, integrated_welcome_system):
        """測試錯誤處理整合"""
        system = integrated_welcome_system
        service = system['service']
        panel = system['panel']
        db_manager = system['db_manager']
        
        # 模擬 Discord 互動
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = None  # 無伺服器，應該觸發錯誤
        
        with patch.object(panel, 'send_error') as mock_send_error:
            await panel.show_settings_panel(interaction)
            
            mock_send_error.assert_called_once_with(interaction, "此功能只能在伺服器中使用")
    
    @pytest.mark.asyncio  
    async def test_cache_consistency_integration(self, integrated_welcome_system):
        """測試快取一致性整合"""
        system = integrated_welcome_system
        service = system['service']
        db_manager = system['db_manager']
        
        guild_id = 123456789
        
        # 1. 先獲取設定（會被快取）
        mock_settings_row = {
            'guild_id': guild_id,
            'channel_id': 555,
            'title': "原始標題",
            'description': "原始內容",
            'message': "原始訊息",
            'avatar_x': 30,
            'avatar_y': 80,
            'title_y': 60,
            'description_y': 120,
            'title_font_size': 36,
            'desc_font_size': 22,
            'avatar_size': 176
        }
        db_manager.fetchone.side_effect = [mock_settings_row, None]  # 設定 + 背景
        
        settings1 = await service.get_settings(guild_id)
        assert settings1.title == "原始標題"
        
        # 2. 更新設定（應該清除快取）
        db_manager.fetchone.side_effect = [{'guild_id': guild_id}]  # 設定存在檢查
        await service.update_setting(guild_id, "title", "新標題")
        
        # 3. 再次獲取設定（應該從資料庫重新讀取）
        updated_settings_row = mock_settings_row.copy()
        updated_settings_row['title'] = "新標題"
        db_manager.fetchone.side_effect = [updated_settings_row, None]  # 更新後的設定 + 背景
        
        settings2 = await service.get_settings(guild_id)
        assert settings2.title == "新標題"
    
    @pytest.mark.asyncio
    async def test_service_dependency_integration(self, integrated_welcome_system):
        """測試服務依賴整合"""
        system = integrated_welcome_system
        service = system['service']
        db_manager = system['db_manager']
        
        # 驗證服務正確設定了資料庫依賴
        assert service.get_dependency("database") == db_manager
        assert service.is_initialized is True
        
        # 驗證服務能正確運作
        db_manager.fetchone.return_value = None
        settings = await service.get_settings(123456789)
        assert isinstance(settings, WelcomeSettings)
        assert settings.guild_id == 123456789