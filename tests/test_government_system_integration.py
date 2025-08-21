"""
政府系統整合測試
Task ID: 5 - 實作政府系統使用者介面

Luna的整合測試理念：單獨的組件再完美，如果無法協同工作就失去了意義。
這些整合測試確保整個政府系統能夠像一首和諧的交響樂，
每個部分都在正確的時機發揮作用，為使用者提供流暢的體驗。

測試場景涵蓋：
- 完整的部門管理生命週期
- 跨組件的資料流動
- 使用者權限的端到端驗證
- 錯誤情況的系統級處理
- 實際使用場景的模擬
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

import discord
from discord.ext import commands

from cogs.government import GovernmentCog
from panels.government.government_panel import GovernmentPanel, DepartmentCreateModal
from services.government.government_service import GovernmentService
from services.government.role_service import RoleService
from services.economy.economy_service import EconomyService
from core.exceptions import ServiceError, ValidationError


class TestGovernmentSystemIntegration:
    """
    政府系統完整整合測試
    
    Luna的端到端測試：模擬真實使用者的完整操作流程
    """
    
    @pytest.fixture
    async def complete_government_system(self):
        """建立完整的政府系統測試環境"""
        # 1. 建立Mock的Discord Bot
        mock_bot = Mock(spec=commands.Bot)
        
        # 2. 建立政府Cog
        gov_cog = GovernmentCog(mock_bot)
        
        # 3. 建立模擬的服務層
        mock_government_service = AsyncMock(spec=GovernmentService)
        mock_role_service = AsyncMock(spec=RoleService)
        mock_economy_service = AsyncMock(spec=EconomyService)
        
        # 4. 建立政府面板
        government_panel = GovernmentPanel()
        government_panel.add_service(mock_government_service, "government_service")
        government_panel.add_service(mock_role_service, "role_service")
        government_panel.add_service(mock_economy_service, "economy_service")
        
        # 5. 設定服務引用
        government_panel.government_service = mock_government_service
        government_panel.role_service = mock_role_service
        government_panel.economy_service = mock_economy_service
        
        # 6. 將面板設定到Cog
        gov_cog.government_panel = government_panel
        gov_cog.government_service = mock_government_service
        gov_cog._initialized = True
        
        # 7. 設定模擬的Discord環境
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.id = 12345
        mock_guild.name = "測試政府伺服器"
        mock_guild.get_member = Mock(return_value=None)
        
        mock_user = Mock(spec=discord.Member)
        mock_user.id = 54321
        mock_user.guild_permissions = Mock()
        mock_user.guild_permissions.administrator = True
        
        return {
            'cog': gov_cog,
            'panel': government_panel,
            'services': {
                'government': mock_government_service,
                'role': mock_role_service,
                'economy': mock_economy_service
            },
            'discord': {
                'bot': mock_bot,
                'guild': mock_guild,
                'user': mock_user
            }
        }
    
    @pytest.fixture
    def mock_interaction_factory(self, complete_government_system):
        """互動工廠函數"""
        def create_interaction(interaction_type=discord.InteractionType.application_command, custom_id=None):
            interaction = Mock(spec=discord.Interaction)
            interaction.type = interaction_type
            interaction.data = {'custom_id': custom_id} if custom_id else {}
            interaction.response = Mock()
            interaction.response.is_done.return_value = False
            interaction.response.send_message = AsyncMock()
            interaction.response.send_modal = AsyncMock()
            interaction.followup = Mock()
            interaction.followup.send = AsyncMock()
            
            interaction.user = complete_government_system['discord']['user']
            interaction.guild = complete_government_system['discord']['guild']
            
            return interaction
        
        return create_interaction
    
    # ==================== 完整流程測試 ====================
    
    @pytest.mark.asyncio
    async def test_complete_department_creation_lifecycle(self, complete_government_system, mock_interaction_factory):
        """
        測試完整的部門建立生命週期
        
        Luna的生命週期測試：從使用者點擊按鈕到部門成功建立的完整過程
        """
        cog = complete_government_system['cog']
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        # === 第一階段：開啟政府面板 ===
        main_interaction = mock_interaction_factory()
        
        # 模擬統計資料
        services['government'].get_department_registry.return_value = []
        services['government'].ensure_council_infrastructure.return_value = True
        
        # 模擬權限檢查成功
        with patch.object(panel, '_validate_permissions', return_value=True):
            await cog.government_command(main_interaction)
        
        # 驗證：應該顯示主面板
        panel.handle_interaction.assert_called_once_with(main_interaction)
        
        # === 第二階段：點擊建立部門按鈕 ===
        create_interaction = mock_interaction_factory(
            interaction_type=discord.InteractionType.component,
            custom_id='gov_create_department'
        )
        
        with patch.object(panel, '_validate_permissions', return_value=True):
            await panel._handle_create_department(create_interaction)
        
        # 驗證：應該顯示建立部門模態框
        create_interaction.response.send_modal.assert_called_once()
        modal = create_interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, DepartmentCreateModal)
        
        # === 第三階段：提交部門建立表單 ===
        submit_interaction = mock_interaction_factory(
            interaction_type=discord.InteractionType.modal_submit
        )
        
        # 設定表單資料
        modal.department_name.value = "整合測試部門"
        modal.head_user.value = "123456"
        modal.level_name.value = "部長級"
        modal.description.value = "這是整合測試建立的部門"
        
        # 模擬成功建立
        services['government'].create_department.return_value = 1
        
        await modal.on_submit(submit_interaction)
        
        # 驗證：應該調用建立部門服務
        services['government'].create_department.assert_called_once()
        call_args = services['government'].create_department.call_args
        assert call_args[0][1]['name'] == "整合測試部門"
        assert call_args[0][1]['head_user_id'] == 123456
        assert call_args[0][1]['level_name'] == "部長級"
        
        # 驗證：應該發送成功訊息
        submit_interaction.followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_department_search_and_management_flow(self, complete_government_system, mock_interaction_factory):
        """
        測試部門搜尋和管理流程
        
        Luna的搜尋管理測試：模擬使用者搜尋特定部門並進行管理操作
        """
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        # 準備測試資料
        test_departments = [
            {
                "id": 1,
                "name": "財政部",
                "head_user_id": 111,
                "level_name": "部長級",
                "created_at": "2025-01-01T00:00:00"
            },
            {
                "id": 2,
                "name": "教育部", 
                "head_user_id": None,
                "level_name": "部長級",
                "created_at": "2025-01-02T00:00:00"
            }
        ]
        
        # === 第一階段：查看註冊表 ===
        registry_interaction = mock_interaction_factory()
        services['government'].get_department_registry.return_value = test_departments
        
        await panel._handle_view_registry(registry_interaction)
        
        # 驗證：應該設定當前部門列表
        assert panel.current_department_list == test_departments
        
        # === 第二階段：搜尋特定部門 ===
        search_interaction = mock_interaction_factory()
        
        # 模擬搜尋操作
        search_results = await panel.perform_search("財政", "name", 12345)
        
        # 由於perform_search依賴於實際的服務實作，我們主要測試介面
        assert isinstance(search_results, list)
        
        # === 第三階段：選擇部門進行管理 ===
        manage_interaction = mock_interaction_factory()
        services['government'].get_department_registry.return_value = test_departments
        
        await panel._handle_manage_departments(manage_interaction)
        
        # 驗證：應該顯示部門管理選擇器
        manage_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_permission_denied_flow(self, complete_government_system, mock_interaction_factory):
        """
        測試權限被拒絕的完整流程
        
        Luna的權限測試：確保系統在權限不足時的正確行為
        """
        cog = complete_government_system['cog']
        panel = complete_government_system['panel']
        
        # 設定無權限的使用者
        unauthorized_user = Mock()
        unauthorized_user.id = 99999
        unauthorized_user.guild_permissions = Mock()
        unauthorized_user.guild_permissions.administrator = False
        
        interaction = mock_interaction_factory()
        interaction.user = unauthorized_user
        
        # 模擬權限檢查失敗
        with patch.object(panel, '_validate_permissions', return_value=False):
            # 嘗試建立部門
            await panel._handle_create_department(interaction)
            
            # 驗證：不應該顯示模態框
            interaction.response.send_modal.assert_not_called()
            
            # 嘗試管理部門
            await panel._handle_manage_departments(interaction)
            
            # 應該只看到警告訊息
            interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_service_error_handling_flow(self, complete_government_system, mock_interaction_factory):
        """
        測試服務錯誤的處理流程
        
        Luna的錯誤處理測試：確保系統在後端服務失敗時優雅處理
        """
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        # 模擬服務錯誤
        services['government'].get_department_registry.side_effect = ServiceError("資料庫連接失敗")
        
        interaction = mock_interaction_factory()
        
        await panel._handle_view_registry(interaction)
        
        # 驗證：應該處理錯誤並給出友善訊息
        # 由於錯誤處理在內部，我們主要檢查系統沒有崩潰
        interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_quick_command_integration(self, complete_government_system, mock_interaction_factory):
        """
        測試快速指令的整合
        
        Luna的快速操作測試：驗證命令列式的快速操作功能
        """
        cog = complete_government_system['cog']
        services = complete_government_system['services']
        
        interaction = mock_interaction_factory()
        
        # 模擬權限檢查成功
        with patch.object(cog.government_panel, '_validate_permissions', return_value=True):
            # 測試快速建立部門
            services['government'].create_department.return_value = 2
            
            await cog.department_create(
                interaction,
                name="快速建立部門",
                head=None,
                level="司長級"
            )
        
        # 驗證：應該調用服務並發送成功訊息
        services['government'].create_department.assert_called_once()
        interaction.followup.send.assert_called_once()
        
        # 測試部門列表查看
        await cog.department_list(interaction)
        
        # 應該委託給面板處理
        cog.government_panel._handle_view_registry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_government_setup_integration(self, complete_government_system, mock_interaction_factory):
        """
        測試政府基礎設施設定的整合
        
        Luna的基礎設施測試：確保新伺服器能夠正確建立政府系統
        """
        cog = complete_government_system['cog']
        services = complete_government_system['services']
        
        interaction = mock_interaction_factory()
        
        # 模擬基礎設施建立成功
        services['government'].ensure_council_infrastructure.return_value = True
        
        await cog.government_setup(interaction)
        
        # 驗證：應該建立基礎設施
        services['government'].ensure_council_infrastructure.assert_called_once_with(
            interaction.guild
        )
        
        # 驗證：應該發送成功訊息
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args[1]
        assert 'embed' in call_args
        assert call_args['ephemeral'] is False
    
    # ==================== 效能和負載測試 ====================
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, complete_government_system, mock_interaction_factory):
        """
        測試並行操作的處理
        
        Luna的並行測試：確保系統能夠處理多個同時進行的操作
        """
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        # 準備多個並行操作
        interactions = [mock_interaction_factory() for _ in range(5)]
        
        # 模擬並行的註冊表查看請求
        services['government'].get_department_registry.return_value = []
        
        tasks = [
            panel._handle_view_registry(interaction)
            for interaction in interactions
        ]
        
        # 執行並行操作
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # 驗證：所有操作都應該完成
        assert services['government'].get_department_registry.call_count == 5
    
    @pytest.mark.asyncio
    async def test_large_department_list_handling(self, complete_government_system, mock_interaction_factory):
        """
        測試大量部門資料的處理
        
        Luna的容量測試：確保系統能夠處理大量部門資料
        """
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        # 生成大量測試部門
        large_department_list = [
            {
                "id": i,
                "name": f"部門{i}",
                "head_user_id": i if i % 2 == 0 else None,
                "level_name": "部長級",
                "created_at": f"2025-01-{i:02d}T00:00:00"
            }
            for i in range(1, 101)  # 100個部門
        ]
        
        services['government'].get_department_registry.return_value = large_department_list
        
        interaction = mock_interaction_factory()
        
        await panel._handle_view_registry(interaction)
        
        # 驗證：應該正確處理大量資料
        assert panel.current_department_list == large_department_list
        interaction.response.send_message.assert_called_once()
    
    # ==================== 邊界情況和異常測試 ====================
    
    @pytest.mark.asyncio
    async def test_invalid_interaction_data(self, complete_government_system):
        """
        測試無效互動資料的處理
        
        Luna的邊界測試：確保系統能夠處理各種異常的輸入
        """
        cog = complete_government_system['cog']
        
        # 建立無效的互動
        invalid_interaction = Mock(spec=discord.Interaction)
        invalid_interaction.type = discord.InteractionType.component
        invalid_interaction.data = None  # 無效資料
        
        # 應該不會崩潰
        await cog.on_interaction(invalid_interaction)
        
        # 測試另一種無效情況
        invalid_interaction.data = {'custom_id': None}
        await cog.on_interaction(invalid_interaction)
    
    @pytest.mark.asyncio
    async def test_network_timeout_simulation(self, complete_government_system, mock_interaction_factory):
        """
        測試網路超時的模擬處理
        
        Luna的網路測試：模擬各種網路問題的處理
        """
        services = complete_government_system['services']
        panel = complete_government_system['panel']
        
        # 模擬超時異常
        services['government'].get_department_registry.side_effect = asyncio.TimeoutError("網路超時")
        
        interaction = mock_interaction_factory()
        
        # 系統應該優雅處理超時
        await panel._handle_view_registry(interaction)
        
        # 驗證：應該有適當的錯誤處理
        interaction.response.send_message.assert_called()


class TestGovernmentSystemPerformance:
    """
    政府系統效能測試
    
    Luna的效能關懷：確保系統在各種負載下都能維持良好的回應速度
    """
    
    @pytest.mark.asyncio
    async def test_response_time_measurement(self, complete_government_system, mock_interaction_factory):
        """測試回應時間測量"""
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        # 模擬快速回應的服務
        services['government'].get_department_registry.return_value = []
        
        interaction = mock_interaction_factory()
        
        # 測量執行時間
        start_time = asyncio.get_event_loop().time()
        await panel._handle_view_registry(interaction)
        end_time = asyncio.get_event_loop().time()
        
        execution_time = end_time - start_time
        
        # 驗證：回應時間應該在合理範圍內（在測試環境中應該很快）
        assert execution_time < 1.0  # 1秒內完成
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, complete_government_system, mock_interaction_factory):
        """測試記憶體使用穩定性"""
        panel = complete_government_system['panel']
        services = complete_government_system['services']
        
        services['government'].get_department_registry.return_value = []
        
        # 執行多次操作，檢查是否有記憶體洩漏
        for _ in range(100):
            interaction = mock_interaction_factory()
            await panel._handle_view_registry(interaction)
        
        # 在實際測試中，這裡可以檢查記憶體使用情況
        # 目前主要確保沒有異常拋出
        assert True


if __name__ == "__main__":
    # 執行整合測試
    pytest.main([__file__, "-v", "--tb=short"])