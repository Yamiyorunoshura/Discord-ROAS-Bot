"""
經濟系統 Cog 整合測試
Task ID: 3 - 實作經濟系統使用者介面

測試經濟系統 Discord Cog 的整合功能，包括：
- Cog 載入和初始化
- 斜線指令註冊和處理
- 服務依賴注入
- 錯誤處理和權限檢查
- 端到端指令流程
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
import discord
from discord.ext import commands

# 測試目標
from cogs.economy import EconomyCog
from panels.economy_panel import EconomyPanel
from services.economy.economy_service import EconomyService
from services.economy.models import Account, CurrencyConfig, AccountType
from core.exceptions import ServiceError
from core.base_service import service_registry


class TestEconomyCog:
    """EconomyCog 整合測試類別"""
    
    @pytest.fixture
    async def mock_bot(self):
        """建立模擬 Discord 機器人"""
        bot = Mock(spec=commands.Bot)
        bot.add_cog = AsyncMock()
        bot.remove_cog = AsyncMock()
        return bot
    
    @pytest.fixture
    async def mock_economy_service(self):
        """建立模擬經濟服務"""
        service = Mock(spec=EconomyService)
        service.name = "EconomyService"
        service.is_initialized = True
        service.initialize = AsyncMock()
        
        # 模擬基本功能
        service.get_account = AsyncMock(return_value=Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=1000.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))
        
        service.get_currency_config = AsyncMock(return_value=CurrencyConfig(guild_id=456))
        
        return service
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬 Discord 互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 123
        
        interaction.guild = Mock()
        interaction.guild.id = 456
        
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        
        interaction.data = {'name': 'economy'}
        
        return interaction
    
    @pytest.fixture
    def mock_admin_interaction(self, mock_interaction):
        """建立模擬管理員互動"""
        admin_member = Mock(spec=discord.Member)
        admin_member.id = 999
        admin_member.guild_permissions = Mock()
        admin_member.guild_permissions.administrator = True
        
        mock_interaction.user = admin_member
        mock_interaction.data = {'name': 'economy_admin'}
        
        return mock_interaction
    
    # ==========================================================================
    # Cog 初始化測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_cog_initialization(self, mock_bot):
        """測試 Cog 初始化"""
        cog = EconomyCog(mock_bot)
        
        assert cog.bot == mock_bot
        assert cog.economy_service is None
        assert cog.economy_panel is None
        assert not cog._initialized
    
    @pytest.mark.asyncio
    async def test_cog_load_success(self, mock_bot, mock_economy_service):
        """測試 Cog 載入成功"""
        cog = EconomyCog(mock_bot)
        
        # 模擬服務註冊表
        with patch.object(service_registry, 'get_service', return_value=mock_economy_service):
            with patch('panels.economy_panel.EconomyPanel') as mock_panel_class:
                mock_panel = Mock(spec=EconomyPanel)
                mock_panel.initialize = AsyncMock()
                mock_panel_class.return_value = mock_panel
                
                await cog.cog_load()
                
                assert cog._initialized
                assert cog.economy_service == mock_economy_service
                assert cog.economy_panel == mock_panel
                mock_panel.initialize.assert_called_once_with(mock_economy_service)
    
    @pytest.mark.asyncio
    async def test_cog_load_service_not_found(self, mock_bot):
        """測試 Cog 載入失敗（服務未找到）"""
        cog = EconomyCog(mock_bot)
        
        with patch.object(service_registry, 'get_service', return_value=None):
            with pytest.raises(ServiceError):
                await cog.cog_load()
            
            assert not cog._initialized
    
    @pytest.mark.asyncio
    async def test_cog_load_service_not_initialized(self, mock_bot, mock_economy_service):
        """測試 Cog 載入（服務未初始化）"""
        cog = EconomyCog(mock_bot)
        mock_economy_service.is_initialized = False
        
        with patch.object(service_registry, 'get_service', return_value=mock_economy_service):
            with patch('panels.economy_panel.EconomyPanel') as mock_panel_class:
                mock_panel = Mock(spec=EconomyPanel)
                mock_panel.initialize = AsyncMock()
                mock_panel_class.return_value = mock_panel
                
                await cog.cog_load()
                
                # 驗證服務初始化被調用
                mock_economy_service.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cog_unload(self, mock_bot):
        """測試 Cog 卸載"""
        cog = EconomyCog(mock_bot)
        cog._initialized = True
        
        await cog.cog_unload()
        
        assert not cog._initialized
    
    # ==========================================================================
    # 斜線指令測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_economy_command_success(self, mock_bot, mock_economy_service, mock_interaction):
        """測試 /economy 指令成功執行"""
        cog = EconomyCog(mock_bot)
        
        # 設定 Cog 為已初始化狀態
        cog._initialized = True
        cog.economy_service = mock_economy_service
        cog.economy_panel = Mock(spec=EconomyPanel)
        cog.economy_panel.handle_interaction = AsyncMock()
        
        await cog.economy_command(mock_interaction)
        
        cog.economy_panel.handle_interaction.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_economy_command_not_initialized(self, mock_bot, mock_interaction):
        """測試 /economy 指令在未初始化時執行"""
        cog = EconomyCog(mock_bot)
        cog._initialized = False
        
        with patch.object(cog, '_send_service_error') as mock_send_error:
            await cog.economy_command(mock_interaction)
            mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_balance_command_self(self, mock_bot, mock_economy_service, mock_interaction):
        """測試 /balance 指令（查詢自己）"""
        cog = EconomyCog(mock_bot)
        cog._initialized = True
        cog.economy_service = mock_economy_service
        cog.economy_panel = Mock(spec=EconomyPanel)
        cog.economy_panel.handle_interaction = AsyncMock()
        
        await cog.balance_command(mock_interaction, user=None)
        
        cog.economy_panel.handle_interaction.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_balance_command_other_user(self, mock_bot, mock_economy_service, mock_interaction):
        """測試 /balance 指令（查詢其他人）"""
        cog = EconomyCog(mock_bot)
        cog._initialized = True
        cog.economy_service = mock_economy_service
        cog.economy_panel = Mock(spec=EconomyPanel)
        cog.economy_panel.handle_interaction = AsyncMock()
        
        target_user = Mock(spec=discord.Member)
        target_user.id = 789
        
        await cog.balance_command(mock_interaction, user=target_user)
        
        # 驗證互動資料被正確設定
        assert 'options' in mock_interaction.data
        assert mock_interaction.data['options'][0]['value'] == target_user
        
        cog.economy_panel.handle_interaction.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_economy_admin_command(self, mock_bot, mock_economy_service, mock_admin_interaction):
        """測試 /economy_admin 指令"""
        cog = EconomyCog(mock_bot)
        cog._initialized = True
        cog.economy_service = mock_economy_service
        cog.economy_panel = Mock(spec=EconomyPanel)
        cog.economy_panel.handle_interaction = AsyncMock()
        
        await cog.economy_admin_command(mock_admin_interaction)
        
        cog.economy_panel.handle_interaction.assert_called_once_with(mock_admin_interaction)
    
    # ==========================================================================
    # 錯誤處理測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_send_service_error(self, mock_bot, mock_interaction):
        """測試發送服務錯誤訊息"""
        cog = EconomyCog(mock_bot)
        error = ServiceError("測試錯誤", service_name="TestService", operation="test")
        
        await cog._send_service_error(mock_interaction, error)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        
        # 驗證嵌入訊息
        assert 'embed' in call_args.kwargs
        embed = call_args.kwargs['embed']
        assert embed.title == "❌ 服務錯誤"
        assert call_args.kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_send_generic_error(self, mock_bot, mock_interaction):
        """測試發送通用錯誤訊息"""
        cog = EconomyCog(mock_bot)
        
        await cog._send_generic_error(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        
        # 驗證嵌入訊息
        assert 'embed' in call_args.kwargs
        embed = call_args.kwargs['embed']
        assert embed.title == "❌ 系統錯誤"
        assert call_args.kwargs['ephemeral'] is True
    
    @pytest.mark.asyncio
    async def test_send_service_error_response_done(self, mock_bot, mock_interaction):
        """測試在回應已完成時發送錯誤訊息"""
        cog = EconomyCog(mock_bot)
        mock_interaction.response.is_done.return_value = True
        
        error = ServiceError("測試錯誤", service_name="TestService", operation="test")
        await cog._send_service_error(mock_interaction, error)
        
        # 驗證使用 followup 發送
        mock_interaction.followup.send.assert_called_once()
        mock_interaction.response.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cog_app_command_error_cooldown(self, mock_bot, mock_interaction):
        """測試斜線指令冷卻錯誤處理"""
        cog = EconomyCog(mock_bot)
        
        from discord import app_commands
        cooldown_error = app_commands.CommandOnCooldown(None, 10.5)
        
        with patch.object(cog, '_send_cooldown_error') as mock_send:
            await cog.cog_app_command_error(mock_interaction, cooldown_error)
            mock_send.assert_called_once_with(mock_interaction, cooldown_error)
    
    @pytest.mark.asyncio
    async def test_cog_app_command_error_missing_permissions(self, mock_bot, mock_interaction):
        """測試斜線指令權限不足錯誤處理"""
        cog = EconomyCog(mock_bot)
        
        from discord import app_commands
        permission_error = app_commands.MissingPermissions(['administrator'])
        
        with patch.object(cog, '_send_permission_error') as mock_send:
            await cog.cog_app_command_error(mock_interaction, permission_error)
            mock_send.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_cog_app_command_error_bot_missing_permissions(self, mock_bot, mock_interaction):
        """測試機器人權限不足錯誤處理"""
        cog = EconomyCog(mock_bot)
        
        from discord import app_commands
        bot_permission_error = app_commands.BotMissingPermissions(['send_messages'])
        
        with patch.object(cog, '_send_bot_permission_error') as mock_send:
            await cog.cog_app_command_error(mock_interaction, bot_permission_error)
            mock_send.assert_called_once_with(mock_interaction, bot_permission_error)
    
    @pytest.mark.asyncio
    async def test_send_cooldown_error(self, mock_bot, mock_interaction):
        """測試發送冷卻錯誤訊息"""
        cog = EconomyCog(mock_bot)
        
        from discord import app_commands
        cooldown_error = app_commands.CommandOnCooldown(None, 5.5)
        
        await cog._send_cooldown_error(mock_interaction, cooldown_error)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        
        embed = call_args.kwargs['embed']
        assert embed.title == "⏱️ 指令冷卻中"
        assert "5.5" in embed.description
    
    @pytest.mark.asyncio
    async def test_send_permission_error(self, mock_bot, mock_interaction):
        """測試發送權限錯誤訊息"""
        cog = EconomyCog(mock_bot)
        
        await cog._send_permission_error(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        
        embed = call_args.kwargs['embed']
        assert embed.title == "🚫 權限不足"
    
    @pytest.mark.asyncio
    async def test_send_bot_permission_error(self, mock_bot, mock_interaction):
        """測試發送機器人權限錯誤訊息"""
        cog = EconomyCog(mock_bot)
        
        from discord import app_commands
        bot_permission_error = app_commands.BotMissingPermissions(['send_messages', 'embed_links'])
        
        await cog._send_bot_permission_error(mock_interaction, bot_permission_error)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        
        embed = call_args.kwargs['embed']
        assert embed.title == "🤖 機器人權限不足"
        assert "send_messages" in embed.description
        assert "embed_links" in embed.description
    
    # ==========================================================================
    # 統計指令測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_economy_stats_command(self, mock_bot):
        """測試經濟統計指令"""
        cog = EconomyCog(mock_bot)
        cog._initialized = True
        
        # 模擬面板和上下文
        mock_panel = Mock(spec=EconomyPanel)
        mock_panel.get_panel_info.return_value = {
            'name': 'EconomyPanel',
            'interaction_count': 10,
            'current_page': 0,
            'created_at': datetime.now().isoformat(),
            'last_interaction': datetime.now().isoformat(),
            'registered_handlers': ['handler1', 'handler2'],
            'services': ['economy']
        }
        cog.economy_panel = mock_panel
        
        mock_ctx = Mock(spec=commands.Context)
        mock_ctx.send = AsyncMock()
        
        await cog.economy_stats_command(mock_ctx)
        
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args
        
        # 驗證統計嵌入訊息
        assert 'embed' in call_args.kwargs
        embed = call_args.kwargs['embed']
        assert embed.title == "📊 經濟系統統計"
    
    @pytest.mark.asyncio
    async def test_economy_stats_command_not_initialized(self, mock_bot):
        """測試經濟統計指令在未初始化時執行"""
        cog = EconomyCog(mock_bot)
        cog._initialized = False
        
        mock_ctx = Mock(spec=commands.Context)
        mock_ctx.send = AsyncMock()
        
        await cog.economy_stats_command(mock_ctx)
        
        # 驗證發送錯誤訊息
        mock_ctx.send.assert_called_once_with("❌ 無法獲取統計資訊")


class TestCogSetupTeardown:
    """Cog 設定和清理測試"""
    
    @pytest.mark.asyncio
    async def test_setup_success(self):
        """測試 Cog 設定成功"""
        mock_bot = Mock(spec=commands.Bot)
        mock_bot.add_cog = AsyncMock()
        
        from panels.economy_cog import setup
        
        await setup(mock_bot)
        
        mock_bot.add_cog.assert_called_once()
        # 驗證添加的是 EconomyCog 實例
        call_args = mock_bot.add_cog.call_args
        cog_instance = call_args[0][0]
        assert isinstance(cog_instance, EconomyCog)
    
    @pytest.mark.asyncio
    async def test_teardown_success(self):
        """測試 Cog 清理成功"""
        mock_bot = Mock(spec=commands.Bot)
        mock_bot.remove_cog = AsyncMock()
        
        from panels.economy_cog import teardown
        
        await teardown(mock_bot)
        
        mock_bot.remove_cog.assert_called_once_with("EconomyCog")


# =============================================================================
# 端到端整合測試
# =============================================================================

class TestEconomyCogIntegration:
    """端到端整合測試"""
    
    @pytest.mark.asyncio
    async def test_full_economy_command_flow(self):
        """測試完整的經濟指令流程"""
        # 建立模擬環境
        mock_bot = Mock(spec=commands.Bot)
        mock_economy_service = Mock(spec=EconomyService)
        mock_economy_service.name = "EconomyService"
        mock_economy_service.is_initialized = True
        mock_economy_service.initialize = AsyncMock()
        
        # 建立 Cog
        cog = EconomyCog(mock_bot)
        
        # 模擬服務註冊和面板初始化
        with patch.object(service_registry, 'get_service', return_value=mock_economy_service):
            with patch('panels.economy_panel.EconomyPanel') as mock_panel_class:
                mock_panel = Mock(spec=EconomyPanel)
                mock_panel.initialize = AsyncMock()
                mock_panel.handle_interaction = AsyncMock()
                mock_panel_class.return_value = mock_panel
                
                # 載入 Cog
                await cog.cog_load()
                
                # 建立模擬互動
                mock_interaction = Mock(spec=discord.Interaction)
                mock_interaction.user = Mock()
                mock_interaction.user.id = 123
                mock_interaction.guild = Mock()
                mock_interaction.guild.id = 456
                mock_interaction.data = {'name': 'economy'}
                
                # 執行指令
                await cog.economy_command(mock_interaction)
                
                # 驗證整個流程
                assert cog._initialized
                assert cog.economy_service == mock_economy_service
                assert cog.economy_panel == mock_panel
                mock_panel.initialize.assert_called_once_with(mock_economy_service)
                mock_panel.handle_interaction.assert_called_once_with(mock_interaction)


# =============================================================================
# 測試執行輔助函數
# =============================================================================

if __name__ == "__main__":
    """直接執行測試"""
    pytest.main([__file__, "-v", "--tb=short"])