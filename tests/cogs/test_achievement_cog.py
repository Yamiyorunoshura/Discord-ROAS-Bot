"""
成就Cog整合測試
Task ID: 7 - 實作成就系統使用者介面

測試覆蓋：
- F4: 成就面板Cog整合測試
- Discord斜線指令整合測試
- 端到端使用者流程測試
- 系統整合和效能測試
"""

import pytest
import asyncio
import discord
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

# Mock discord.py components
discord.Interaction = Mock
discord.User = Mock
discord.Guild = Mock
discord.Member = Mock
discord.Embed = Mock
discord.Color = Mock
discord.app_commands = Mock()
discord.app_commands.describe = Mock()
discord.app_commands.command = Mock()
discord.app_commands.choices = Mock()
discord.app_commands.Choice = Mock
discord.app_commands.Group = Mock
discord.app_commands.Command = Mock

from cogs.achievement import AchievementCog
from panels.achievement.achievement_panel import AchievementPanel
from services.achievement.achievement_service import AchievementService
from core.exceptions import ServiceError


class TestAchievementCogIntegration:
    """測試成就Cog整合功能 (F4)"""
    
    @pytest.fixture
    def mock_bot(self):
        """模擬Discord Bot"""
        bot = Mock()
        bot.tree = Mock()
        bot.tree.sync = AsyncMock()
        return bot
    
    @pytest.fixture
    def mock_achievement_service(self):
        """模擬成就服務"""
        service = Mock(spec=AchievementService)
        service.name = "achievement_service"
        service.is_initialized = True
        return service
    
    @pytest.fixture
    def mock_achievement_panel(self):
        """模擬成就面板"""
        panel = Mock(spec=AchievementPanel)
        panel.show_user_achievements = AsyncMock()
        panel.show_achievement_details = AsyncMock()
        panel.show_admin_panel = AsyncMock()
        return panel
    
    @pytest.fixture
    def achievement_cog(self, mock_bot, mock_achievement_service, mock_achievement_panel):
        """建立成就Cog實例"""
        cog = AchievementCog(mock_bot)
        cog.achievement_service = mock_achievement_service
        cog.achievement_panel = mock_achievement_panel
        return cog
    
    @pytest.fixture
    def mock_interaction(self):
        """模擬Discord互動"""
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        return interaction
    
    def test_cog_initialization(self, achievement_cog, mock_bot):
        """測試Cog初始化"""
        assert achievement_cog.bot == mock_bot
        assert hasattr(achievement_cog, 'achievement_service')
        assert hasattr(achievement_cog, 'achievement_panel')
    
    @pytest.mark.asyncio
    async def test_cog_setup(self, mock_bot, mock_achievement_service):
        """測試Cog設定"""
        # 設置服務註冊表
        from core.service_startup_manager import service_registry
        service_registry.register_service("AchievementService", mock_achievement_service)
        
        try:
            # 在實際實作中這會載入服務和面板依賴
            cog = AchievementCog(mock_bot)
            await cog.cog_load()
            
            # 驗證依賴載入
            assert cog.achievement_service is not None
            assert cog.achievement_panel is not None
        finally:
            # 清理註冊表
            service_registry._services.clear()
    
    @pytest.mark.asyncio
    async def test_slash_command_achievement_view(
        self, 
        achievement_cog, 
        mock_interaction
    ):
        """測試/achievement view斜線指令"""
        await achievement_cog.achievement_view(mock_interaction)
        
        # 驗證面板方法調用
        achievement_cog.achievement_panel.show_user_achievements.assert_called_once_with(
            mock_interaction
        )
    
    @pytest.mark.asyncio
    async def test_slash_command_achievement_details(
        self,
        achievement_cog,
        mock_interaction
    ):
        """測試/achievement details斜線指令"""
        achievement_id = "msg_100"
        
        await achievement_cog.achievement_details(mock_interaction, achievement_id)
        
        # 驗證面板方法調用
        achievement_cog.achievement_panel.show_achievement_details.assert_called_once_with(
            mock_interaction, achievement_id
        )
    
    @pytest.mark.asyncio
    async def test_slash_command_achievement_admin(
        self,
        achievement_cog,
        mock_interaction
    ):
        """測試/achievement admin斜線指令"""
        await achievement_cog.achievement_admin(mock_interaction)
        
        # 驗證面板方法調用
        achievement_cog.achievement_panel.show_admin_panel.assert_called_once_with(
            mock_interaction
        )
    
    @pytest.mark.asyncio
    async def test_command_error_handling(
        self,
        achievement_cog,
        mock_interaction
    ):
        """測試指令錯誤處理"""
        # 模擬面板拋出錯誤
        achievement_cog.achievement_panel.show_user_achievements.side_effect = ServiceError(
            "服務不可用", service_name="achievement_service"
        )
        
        await achievement_cog.achievement_view(mock_interaction)
        
        # 應該發送錯誤訊息而不是拋出異常
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_command_response_time(
        self,
        achievement_cog,
        mock_interaction
    ):
        """測試指令響應時間 (<1秒)"""
        import time
        
        start_time = time.time()
        await achievement_cog.achievement_view(mock_interaction)
        end_time = time.time()
        
        response_time = end_time - start_time
        # 效能要求：<1秒
        assert response_time < 1.0
    
    @pytest.mark.asyncio
    async def test_concurrent_command_handling(
        self,
        achievement_cog
    ):
        """測試並發指令處理"""
        async def simulate_command():
            interaction = Mock()
            interaction.user = Mock()
            interaction.user.id = 12345
            interaction.guild = Mock()
            interaction.guild.id = 67890
            interaction.response = Mock()
            interaction.response.is_done.return_value = False
            interaction.response.send_message = AsyncMock()
            
            await achievement_cog.achievement_view(interaction)
        
        # 建立多個並發指令
        tasks = [simulate_command() for _ in range(10)]
        
        # 執行並發測試
        await asyncio.gather(*tasks)
        
        # 驗證所有指令都被正確處理
        assert achievement_cog.achievement_panel.show_user_achievements.call_count == 10


class TestAchievementSystemEndToEnd:
    """端到端系統測試"""
    
    @pytest.fixture
    def mock_bot(self):
        bot = Mock()
        bot.tree = Mock()
        return bot
    
    @pytest.fixture
    def full_system(self, mock_bot):
        """完整系統設定"""
        # 在實際實作中會設定真實的服務和面板實例
        achievement_service = Mock(spec=AchievementService)
        achievement_service.is_initialized = True
        achievement_service.name = "achievement_service"
        
        achievement_panel = AchievementPanel()
        achievement_panel.add_service(achievement_service)
        
        achievement_cog = AchievementCog(mock_bot)
        achievement_cog.achievement_service = achievement_service
        achievement_cog.achievement_panel = achievement_panel
        
        return {
            "bot": mock_bot,
            "service": achievement_service,
            "panel": achievement_panel,
            "cog": achievement_cog
        }
    
    @pytest.mark.asyncio
    async def test_user_achievement_workflow(self, full_system):
        """測試完整的使用者成就查看流程"""
        cog = full_system["cog"]
        service = full_system["service"]
        
        # 模擬使用者成就資料
        user_achievements = [
            {
                "achievement_id": "first_msg",
                "achievement_name": "初來乍到",
                "achievement_description": "發送第一則訊息",
                "achievement_type": "milestone",
                "current_progress": {"message_count": 1},
                "completed": True,
                "completed_at": datetime.now(),
                "last_updated": datetime.now()
            }
        ]
        
        service.list_user_achievements.return_value = user_achievements
        
        # 建立模擬互動
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        # 執行完整流程
        await cog.achievement_view(interaction)
        
        # 驗證服務調用
        service.list_user_achievements.assert_called_once_with(12345, 67890, False)
        
        # 驗證回應發送
        interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_admin_achievement_management_workflow(self, full_system):
        """測試完整的管理員成就管理流程"""
        cog = full_system["cog"]
        service = full_system["service"]
        
        # 模擬管理員權限
        service.validate_permissions.return_value = True
        
        # 建立管理員互動
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 99999  # 管理員ID
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        # 執行管理員流程
        await cog.achievement_admin(interaction)
        
        # 驗證權限檢查
        service.validate_permissions.assert_called_once_with(
            99999, 67890, "manage_achievements"
        )
        
        # 驗證回應發送
        interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_achievement_creation_workflow(self, full_system):
        """測試成就建立工作流程"""
        panel = full_system["panel"]
        service = full_system["service"]
        
        # 模擬成功建立成就
        created_achievement = Mock()
        created_achievement.id = "new_achievement"
        created_achievement.name = "新成就"
        service.create_achievement.return_value = created_achievement
        
        # 建立管理員互動
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 99999
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.send_message = AsyncMock()
        
        # 模擬表單資料
        form_data = {
            "name": "新成就",
            "description": "測試成就描述",
            "achievement_type": "milestone",
            "trigger_type": "message_count",
            "target_value": "100"
        }
        
        # 執行建立流程
        await panel.handle_achievement_creation(interaction, form_data)
        
        # 驗證成就建立
        service.create_achievement.assert_called_once()
        
        # 驗證成功訊息
        interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_system_performance_under_load(self, full_system):
        """測試系統負載效能"""
        cog = full_system["cog"]
        service = full_system["service"]
        
        service.list_user_achievements.return_value = []
        
        async def simulate_user_request(user_id: int):
            interaction = Mock()
            interaction.user = Mock()
            interaction.user.id = user_id
            interaction.guild = Mock()
            interaction.guild.id = 67890
            interaction.response = Mock()
            interaction.response.is_done.return_value = False
            interaction.response.send_message = AsyncMock()
            
            await cog.achievement_view(interaction)
        
        # 模擬50個並發使用者請求
        tasks = [simulate_user_request(i) for i in range(50)]
        
        import time
        start_time = time.time()
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 效能要求：支援50個並發請求
        assert total_time < 10.0  # 10秒內處理50個請求
        assert service.list_user_achievements.call_count == 50


class TestAchievementSystemErrorRecovery:
    """測試系統錯誤恢復能力"""
    
    @pytest.fixture
    def unstable_system(self):
        """不穩定的系統（模擬各種故障）"""
        service = Mock(spec=AchievementService)
        service.name = "achievement_service"
        service.is_initialized = True
        
        panel = AchievementPanel()
        panel.add_service(service)
        
        bot = Mock()
        cog = AchievementCog(bot)
        cog.achievement_service = service
        cog.achievement_panel = panel
        
        return {"service": service, "panel": panel, "cog": cog}
    
    @pytest.mark.asyncio
    async def test_service_temporary_unavailable(self, unstable_system):
        """測試服務暫時不可用的恢復"""
        service = unstable_system["service"]
        cog = unstable_system["cog"]
        
        # 模擬服務暫時故障後恢復
        call_count = 0
        def mock_list_achievements(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ServiceError("服務暫時不可用")
            return []
        
        service.list_user_achievements.side_effect = mock_list_achievements
        
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        
        # 第一次調用應該失敗但優雅處理
        await cog.achievement_view(interaction)
        interaction.response.send_message.assert_called_once()
        
        # 重置mock以便第二次調用
        interaction.response.send_message.reset_mock()
        
        # 第二次調用應該失敗但優雅處理
        await cog.achievement_view(interaction)
        interaction.response.send_message.assert_called_once()
        
        # 重置mock以便第三次調用
        interaction.response.send_message.reset_mock()
        
        # 第三次調用應該成功
        await cog.achievement_view(interaction)
        interaction.response.send_message.assert_called_once()
        
        # 驗證服務調用次數
        assert service.list_user_achievements.call_count == 3
    
    @pytest.mark.asyncio
    async def test_discord_api_rate_limit_handling(self, unstable_system):
        """測試Discord API速率限制處理"""
        cog = unstable_system["cog"]
        service = unstable_system["service"]
        
        service.list_user_achievements.return_value = []
        
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        
        # 模擬Discord API速率限制
        interaction.response.send_message.side_effect = discord.HTTPException(
            Mock(), "Too Many Requests"
        )
        
        # 系統應該優雅處理而不崩潰
        with pytest.raises(discord.HTTPException):
            await cog.achievement_view(interaction)
        
        # 驗證服務仍然被調用（錯誤發生在Discord層面）
        service.list_user_achievements.assert_called_once()


# 測試執行標記
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,    # 整合測試標記
    pytest.mark.e2e,           # 端到端測試標記
    pytest.mark.performance,    # 效能測試標記
    pytest.mark.achievement    # 成就系統標記
]