"""
歡迎面板測試
Task ID: 9 - 重構現有模組以符合新架構
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import discord

from panels.welcome.welcome_panel import WelcomePanel
from services.welcome.welcome_service import WelcomeService
from services.welcome.models import WelcomeSettings


@pytest.fixture
def mock_welcome_service():
    """模擬歡迎服務"""
    service = Mock(spec=WelcomeService)
    service.get_settings = AsyncMock()
    service.update_setting = AsyncMock()
    service.generate_welcome_image = AsyncMock()
    service.update_background = AsyncMock()
    service._render_template = Mock()
    return service


@pytest.fixture
def welcome_panel(mock_welcome_service):
    """建立歡迎面板實例"""
    config = {
        'bg_dir': 'data/backgrounds',
        'fonts_dir': 'fonts',
        'default_font': 'fonts/test.ttf',
    }
    return WelcomePanel(mock_welcome_service, config)


@pytest.fixture
def mock_interaction():
    """模擬 Discord 互動"""
    interaction = Mock(spec=discord.Interaction)
    interaction.response = Mock()
    interaction.followup = Mock()
    interaction.user = Mock()
    interaction.user.id = 123456789
    interaction.channel = Mock()
    interaction.channel.id = 987654321
    
    # 模擬伺服器
    guild = Mock(spec=discord.Guild)
    guild.id = 555666777
    guild.name = "Test Guild"
    interaction.guild = guild
    
    return interaction


class TestWelcomePanel:
    """歡迎面板測試類別"""
    
    def test_panel_initialization(self, mock_welcome_service):
        """測試面板初始化"""
        config = {'bg_dir': 'test_dir'}
        panel = WelcomePanel(mock_welcome_service, config)
        
        assert panel.name == "WelcomePanel"
        assert panel.title == "🎉 歡迎訊息設定面板"
        assert panel.welcome_service == mock_welcome_service
        assert panel.config == config
    
    @pytest.mark.asyncio
    async def test_show_settings_panel_success(self, welcome_panel, mock_interaction):
        """測試顯示設定面板 - 成功"""
        # 模擬服務返回設定
        mock_settings = WelcomeSettings(guild_id=555666777)
        welcome_panel.welcome_service.get_settings.return_value = mock_settings
        
        with patch.object(welcome_panel, '_build_settings_embed') as mock_build_embed:
            mock_embed = Mock()
            mock_build_embed.return_value = mock_embed
            
            await welcome_panel.show_settings_panel(mock_interaction)
            
            mock_interaction.response.send_message.assert_called_once()
            mock_build_embed.assert_called_once_with(mock_interaction.guild)
    
    @pytest.mark.asyncio
    async def test_show_settings_panel_no_guild(self, welcome_panel, mock_interaction):
        """測試顯示設定面板 - 無伺服器"""
        mock_interaction.guild = None
        
        with patch.object(welcome_panel, 'send_error') as mock_send_error:
            await welcome_panel.show_settings_panel(mock_interaction)
            
            mock_send_error.assert_called_once_with(mock_interaction, "此功能只能在伺服器中使用")
    
    @pytest.mark.asyncio
    async def test_preview_welcome_message_success(self, welcome_panel, mock_interaction):
        """測試預覽歡迎訊息 - 成功"""
        # 模擬成員
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 123456789
        mock_interaction.user = mock_member
        
        # 模擬服務返回
        mock_welcome_image = Mock()
        mock_welcome_image.to_bytes.return_value = b"fake_image_data"
        welcome_panel.welcome_service.generate_welcome_image.return_value = mock_welcome_image
        
        mock_settings = WelcomeSettings(guild_id=555666777, message="歡迎 {member.name}!")
        welcome_panel.welcome_service.get_settings.return_value = mock_settings
        welcome_panel.welcome_service._render_template.return_value = "歡迎 TestUser!"
        
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()
        
        await welcome_panel.preview_welcome_message(mock_interaction)
        
        mock_interaction.response.defer.assert_called_once_with(thinking=True)
        welcome_panel.welcome_service.generate_welcome_image.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_preview_welcome_message_no_guild(self, welcome_panel, mock_interaction):
        """測試預覽歡迎訊息 - 無伺服器"""
        mock_interaction.guild = None
        
        with patch.object(welcome_panel, 'send_error') as mock_send_error:
            await welcome_panel.preview_welcome_message(mock_interaction)
            
            mock_send_error.assert_called_once_with(mock_interaction, "此功能只能在伺服器中使用")
    
    @pytest.mark.asyncio
    async def test_handle_setting_update_success(self, welcome_panel, mock_interaction):
        """測試處理設定更新 - 成功"""
        welcome_panel.welcome_service.update_setting.return_value = True
        
        with patch.object(welcome_panel, 'send_success') as mock_send_success:
            with patch.object(welcome_panel, '_refresh_settings_panel') as mock_refresh:
                with patch.object(welcome_panel, 'preview_welcome_message') as mock_preview:
                    await welcome_panel.handle_setting_update(mock_interaction, "title", "新標題")
                    
                    welcome_panel.welcome_service.update_setting.assert_called_once_with(
                        555666777, "title", "新標題"
                    )
                    mock_send_success.assert_called_once()
                    mock_refresh.assert_called_once()
                    mock_preview.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_setting_update_failure(self, welcome_panel, mock_interaction):
        """測試處理設定更新 - 失敗"""
        welcome_panel.welcome_service.update_setting.return_value = False
        
        with patch.object(welcome_panel, 'send_error') as mock_send_error:
            await welcome_panel.handle_setting_update(mock_interaction, "title", "新標題")
            
            mock_send_error.assert_called_once_with(mock_interaction, "更新設定失敗")
    
    @pytest.mark.asyncio
    async def test_handle_background_upload_success(self, welcome_panel, mock_interaction):
        """測試處理背景圖片上傳 - 成功"""
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.followup.send = AsyncMock()
        mock_interaction.client = Mock()
        
        # 模擬等待訊息
        mock_message = Mock()
        mock_attachment = Mock()
        mock_attachment.filename = "test.png"
        mock_attachment.read = AsyncMock(return_value=b"fake_image_data")
        mock_message.attachments = [mock_attachment]
        mock_interaction.client.wait_for.return_value = mock_message
        
        welcome_panel.welcome_service.update_background.return_value = True
        
        with patch('builtins.open', mock_open_func()) as mock_file:
            with patch.object(welcome_panel, '_refresh_settings_panel') as mock_refresh:
                with patch.object(welcome_panel, 'preview_welcome_message') as mock_preview:
                    await welcome_panel.handle_background_upload(mock_interaction)
                    
                    welcome_panel.welcome_service.update_background.assert_called_once()
                    mock_interaction.followup.send.assert_called()
    
    @pytest.mark.asyncio
    async def test_build_settings_embed(self, welcome_panel, mock_interaction):
        """測試建構設定面板 embed"""
        mock_settings = WelcomeSettings(
            guild_id=555666777,
            channel_id=123,
            title="測試標題",
            description="測試內容",
            message="測試訊息",
            avatar_x=30,
            avatar_y=80,
            title_y=60,
            description_y=120,
            title_font_size=36,
            desc_font_size=22,
            avatar_size=176
        )
        welcome_panel.welcome_service.get_settings.return_value = mock_settings
        
        with patch.object(welcome_panel, 'create_embed') as mock_create_embed:
            mock_embed = Mock()
            mock_embed.add_field = Mock()
            mock_embed.set_footer = Mock()
            mock_create_embed.return_value = mock_embed
            
            embed = await welcome_panel._build_settings_embed(mock_interaction.guild)
            
            welcome_panel.welcome_service.get_settings.assert_called_once_with(555666777)
            mock_create_embed.assert_called_once()
            # 檢查是否添加了必要的欄位
            assert mock_embed.add_field.call_count >= 10  # 至少應該有10個欄位


def mock_open_func():
    """模擬 open 函數"""
    from unittest.mock import mock_open
    return mock_open()