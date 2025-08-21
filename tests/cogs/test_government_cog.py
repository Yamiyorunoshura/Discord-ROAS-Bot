"""
政府系統Cog測試套件
Task ID: 5 - 實作政府系統使用者介面

Luna的Cog測試理念：Discord Cog是使用者與系統的第一接觸點，
必須確保每個指令都能正確響應，每個互動都有適當的回饋。
這些測試保護著使用者的每一次操作體驗。

測試覆蓋範圍：
- 斜線指令的註冊和執行
- 互動事件的正確路由
- 權限檢查和錯誤處理
- 與面板的整合
- Cog的生命週期管理
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import discord
from discord.ext import commands
from discord import app_commands

from cogs.government import GovernmentCog
from panels.government.government_panel import GovernmentPanel
from services.government.government_service import GovernmentService
from core.exceptions import ServiceError, ValidationError


class TestGovernmentCog:
    """
    政府系統Cog核心功能測試
    
    Luna的Cog測試：確保Discord指令系統與政府面板的完美整合
    """
    
    @pytest.fixture
    def mock_bot(self):
        """創建模擬的Discord bot"""
        bot = Mock(spec=commands.Bot)
        bot.add_cog = AsyncMock()
        return bot
    
    @pytest.fixture
    async def government_cog(self, mock_bot):
        """創建政府系統Cog測試實例"""
        cog = GovernmentCog(mock_bot)
        
        # 模擬初始化成功
        cog._initialized = True
        
        # 模擬政府面板
        mock_panel = Mock(spec=GovernmentPanel)
        mock_panel.handle_interaction = AsyncMock()
        mock_panel._validate_permissions = AsyncMock(return_value=True)
        cog.government_panel = mock_panel
        
        # 模擬政府服務
        mock_service = Mock(spec=GovernmentService)
        mock_service.create_department = AsyncMock(return_value=1)
        mock_service.ensure_council_infrastructure = AsyncMock(return_value=True)
        cog.government_service = mock_service
        
        return cog
    
    @pytest.fixture
    def mock_interaction(self):
        """創建模擬的Discord互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        
        # 模擬使用者和伺服器
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.guild.name = "測試伺服器"
        
        return interaction
    
    # ==================== Cog生命週期測試 ====================
    
    def test_cog_initialization(self, mock_bot):
        """測試Cog初始化"""
        cog = GovernmentCog(mock_bot)
        
        assert cog.bot == mock_bot
        assert cog._initialized is False
        assert cog.government_panel is None
        assert cog.logger is not None
    
    @pytest.mark.asyncio
    async def test_cog_load_success(self, mock_bot):
        """測試Cog載入成功"""
        cog = GovernmentCog(mock_bot)
        
        # 模擬服務初始化
        with patch.object(cog, '_initialize_services') as mock_init_services, \
             patch.object(cog, '_initialize_panel') as mock_init_panel:
            
            await cog.cog_load()
            
            mock_init_services.assert_called_once()
            mock_init_panel.assert_called_once()
            assert cog._initialized is True
    
    @pytest.mark.asyncio
    async def test_cog_unload(self, government_cog):
        """測試Cog卸載"""
        await government_cog.cog_unload()
        
        assert government_cog._initialized is False
        assert government_cog.government_panel is None
    
    # ==================== 主指令測試 ====================
    
    @pytest.mark.asyncio
    async def test_government_command_success(self, government_cog, mock_interaction):
        """測試政府主指令成功執行"""
        await government_cog.government_command(mock_interaction)
        
        # 檢查是否委託給面板處理
        government_cog.government_panel.handle_interaction.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_government_command_not_initialized(self, mock_bot, mock_interaction):
        """測試政府主指令在未初始化時的處理"""
        cog = GovernmentCog(mock_bot)
        # 不設定 _initialized 為 True
        
        await cog.government_command(mock_interaction)
        
        # 應該發送錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert call_args['ephemeral'] is True
        assert "尚未完全初始化" in call_args['content']
    
    @pytest.mark.asyncio
    async def test_government_command_exception_handling(self, government_cog, mock_interaction):
        """測試政府主指令異常處理"""
        # 模擬面板拋出異常
        government_cog.government_panel.handle_interaction.side_effect = Exception("測試異常")
        
        await government_cog.government_command(mock_interaction)
        
        # 應該發送錯誤嵌入訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert 'embed' in call_args
        assert call_args['ephemeral'] is True
    
    # ==================== 部門快速操作指令測試 ====================
    
    @pytest.mark.asyncio
    async def test_department_create_command_success(self, government_cog, mock_interaction):
        """測試部門建立指令成功"""
        # 模擬建立部門
        await government_cog.department_create(
            mock_interaction,
            name="測試部門",
            head=None,
            level="部長級"
        )
        
        # 檢查是否調用了政府服務
        government_cog.government_service.create_department.assert_called_once()
        
        # 檢查回應
        mock_interaction.response.send_message.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_department_create_command_permission_denied(self, government_cog, mock_interaction):
        """測試部門建立指令權限不足"""
        # 模擬權限不足
        government_cog.government_panel._validate_permissions.return_value = False
        
        await government_cog.department_create(
            mock_interaction,
            name="測試部門"
        )
        
        # 不應該調用建立服務
        government_cog.government_service.create_department.assert_not_called()
        
        # 應該發送權限錯誤
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_department_create_command_with_head(self, government_cog, mock_interaction):
        """測試帶部長的部門建立指令"""
        # 模擬部長使用者
        mock_head = Mock(spec=discord.Member)
        mock_head.id = 54321
        mock_head.mention = "<@54321>"
        
        await government_cog.department_create(
            mock_interaction,
            name="測試部門",
            head=mock_head,
            level="部長級"
        )
        
        # 檢查傳入的資料
        call_args = government_cog.government_service.create_department.call_args
        department_data = call_args[0][1]
        assert department_data['head_user_id'] == 54321
    
    @pytest.mark.asyncio
    async def test_department_list_command(self, government_cog, mock_interaction):
        """測試部門列表指令"""
        await government_cog.department_list(mock_interaction)
        
        # 應該委託給面板的註冊表查看功能
        government_cog.government_panel._handle_view_registry.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_department_info_command_success(self, government_cog, mock_interaction):
        """測試部門詳情指令成功"""
        # 模擬部門資料
        mock_department = {
            "id": 1,
            "name": "測試部門",
            "head_user_id": 123,
            "level_name": "部長級",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
            "account_id": 456
        }
        government_cog.government_service.get_department_by_id.return_value = mock_department
        
        await government_cog.department_info(mock_interaction, department_id=1)
        
        # 檢查是否查詢了部門
        government_cog.government_service.get_department_by_id.assert_called_once_with(1)
        
        # 檢查是否發送了嵌入訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert 'embed' in call_args
        assert call_args['ephemeral'] is False
    
    @pytest.mark.asyncio
    async def test_department_info_command_not_found(self, government_cog, mock_interaction):
        """測試部門詳情指令找不到部門"""
        # 模擬找不到部門
        government_cog.government_service.get_department_by_id.return_value = None
        
        await government_cog.department_info(mock_interaction, department_id=999)
        
        # 應該發送找不到部門的訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert call_args['ephemeral'] is True
        assert "找不到" in call_args['content']
    
    # ==================== 管理指令測試 ====================
    
    @pytest.mark.asyncio
    async def test_government_setup_command_success(self, government_cog, mock_interaction):
        """測試政府設定指令成功"""
        await government_cog.government_setup(mock_interaction)
        
        # 檢查是否調用了基礎設施建立
        government_cog.government_service.ensure_council_infrastructure.assert_called_once_with(
            mock_interaction.guild
        )
        
        # 檢查回應
        mock_interaction.response.send_message.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_government_setup_command_failure(self, government_cog, mock_interaction):
        """測試政府設定指令失敗"""
        # 模擬建立失敗
        government_cog.government_service.ensure_council_infrastructure.return_value = False
        
        await government_cog.government_setup(mock_interaction)
        
        # 應該發送失敗訊息
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[1]
        assert call_args['ephemeral'] is True
    
    # ==================== 事件處理測試 ====================
    
    @pytest.mark.asyncio
    async def test_on_interaction_government_component(self, government_cog):
        """測試政府組件互動事件處理"""
        # 模擬政府按鈕互動
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.type = discord.InteractionType.component
        mock_interaction.data = {'custom_id': 'gov_create_department'}
        
        await government_cog.on_interaction(mock_interaction)
        
        # 應該委託給面板處理
        government_cog.government_panel.handle_interaction.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_on_interaction_government_modal(self, government_cog):
        """測試政府模態框互動事件處理"""
        # 模擬政府模態框提交
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.type = discord.InteractionType.modal_submit
        mock_interaction.data = {'custom_id': 'government_create_modal'}
        
        await government_cog.on_interaction(mock_interaction)
        
        # 應該委託給面板處理
        government_cog.government_panel.handle_interaction.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_on_interaction_non_government(self, government_cog):
        """測試非政府相關的互動事件"""
        # 模擬非政府互動
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.type = discord.InteractionType.component
        mock_interaction.data = {'custom_id': 'other_button'}
        
        await government_cog.on_interaction(mock_interaction)
        
        # 不應該委託給面板處理
        government_cog.government_panel.handle_interaction.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_interaction_not_initialized(self, mock_bot):
        """測試未初始化時的互動處理"""
        cog = GovernmentCog(mock_bot)
        # 不設定初始化狀態
        
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.type = discord.InteractionType.component
        mock_interaction.data = {'custom_id': 'gov_test'}
        mock_interaction.response.send_message = AsyncMock()
        
        await cog.on_interaction(mock_interaction)
        
        # 應該發送系統不可用訊息
        mock_interaction.response.send_message.assert_called_once()
    
    # ==================== 錯誤處理測試 ====================
    
    @pytest.mark.asyncio
    async def test_cog_app_command_error_permissions(self, government_cog, mock_interaction):
        """測試應用程式指令權限錯誤處理"""
        error = app_commands.MissingPermissions(['administrator'])
        
        await government_cog.cog_app_command_error(mock_interaction, error)
        
        # 應該發送權限錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert "沒有執行此指令的權限" in call_args['content']
    
    @pytest.mark.asyncio
    async def test_cog_app_command_error_invoke_error(self, government_cog, mock_interaction):
        """測試應用程式指令調用錯誤處理"""
        error = app_commands.CommandInvokeError(None, Exception("測試錯誤"))
        
        await government_cog.cog_app_command_error(mock_interaction, error)
        
        # 應該發送通用錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert "指令執行時發生錯誤" in call_args['content']
    
    @pytest.mark.asyncio
    async def test_cog_app_command_error_unknown(self, government_cog, mock_interaction):
        """測試未知錯誤處理"""
        error = Exception("未知錯誤")
        
        await government_cog.cog_app_command_error(mock_interaction, error)
        
        # 應該發送未知錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[1]
        assert "發生未知錯誤" in call_args['content']
    
    # ==================== 整合測試 ====================
    
    @pytest.mark.asyncio
    async def test_complete_command_flow(self, government_cog, mock_interaction):
        """測試完整的指令執行流程"""
        # 模擬完整的部門建立流程
        
        # 1. 執行主指令
        await government_cog.government_command(mock_interaction)
        government_cog.government_panel.handle_interaction.assert_called_with(mock_interaction)
        
        # 2. 重置mock
        government_cog.government_panel.handle_interaction.reset_mock()
        
        # 3. 執行快速建立指令
        await government_cog.department_create(
            mock_interaction,
            name="整合測試部門",
            head=None,
            level="部長級"
        )
        
        # 檢查是否正確調用了服務
        government_cog.government_service.create_department.assert_called()
    
    @pytest.mark.asyncio
    async def test_service_error_propagation(self, government_cog, mock_interaction):
        """測試服務錯誤的正確傳播"""
        # 模擬服務錯誤
        government_cog.government_service.create_department.side_effect = ServiceError("測試服務錯誤")
        
        await government_cog.department_create(
            mock_interaction,
            name="錯誤測試部門"
        )
        
        # 應該捕獲並處理錯誤
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[1]
        assert call_args['ephemeral'] is True


class TestGovernmentCogSetup:
    """
    政府系統Cog設定功能測試
    
    Luna的設定測試：確保Cog能夠正確載入到Discord bot中
    """
    
    @pytest.mark.asyncio
    async def test_setup_function(self):
        """測試setup函數"""
        from cogs.government import setup
        
        mock_bot = Mock(spec=commands.Bot)
        mock_bot.add_cog = AsyncMock()
        
        await setup(mock_bot)
        
        # 檢查是否添加了Cog
        mock_bot.add_cog.assert_called_once()
        
        # 檢查添加的是否為GovernmentCog實例
        call_args = mock_bot.add_cog.call_args[0]
        assert isinstance(call_args[0], GovernmentCog)


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])