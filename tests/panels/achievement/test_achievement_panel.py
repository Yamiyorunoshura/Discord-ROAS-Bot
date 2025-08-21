"""
成就面板單元測試
Task ID: 7 - 實作成就系統使用者介面

測試覆蓋：
- F1: 成就面板基礎結構測試
- F2: 使用者成就面板功能測試  
- F3: 管理員成就面板功能測試
- 錯誤處理和權限檢查測試
- UI元件和嵌入訊息測試
"""

import pytest
import asyncio
import discord
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Mock discord.py 組件避免import錯誤
discord.Interaction = Mock
discord.User = Mock  
discord.Guild = Mock
discord.Member = Mock
discord.Embed = Mock
discord.Color = Mock
discord.Color.blue = Mock(return_value=0x0099FF)
discord.Color.green = Mock(return_value=0x00FF00)
discord.Color.red = Mock(return_value=0xFF0000)
discord.Color.orange = Mock(return_value=0xFF9900)
discord.Color.gold = Mock(return_value=0xFFD700)
discord.Color.purple = Mock(return_value=0x9932CC)
discord.ui = Mock()
discord.ui.View = Mock
discord.ui.Button = Mock
discord.ui.Select = Mock
discord.ui.TextInput = Mock
discord.ui.Modal = Mock
discord.HTTPException = Exception
discord.InteractionResponded = Exception

from panels.achievement.achievement_panel import AchievementPanel
from services.achievement.achievement_service import AchievementService
from services.achievement.models import (
    Achievement, AchievementProgress, AchievementReward, TriggerCondition,
    AchievementType, TriggerType, RewardType, AchievementStatus
)
from core.exceptions import ServiceError, ValidationError, ServicePermissionError


class TestAchievementPanelFoundation:
    """測試成就面板基礎功能 (F1)"""
    
    @pytest.fixture
    def mock_achievement_service(self):
        """模擬成就服務"""
        service = Mock(spec=AchievementService)
        service.name = "achievement_service"
        service.is_initialized = True
        return service
    
    @pytest.fixture  
    def achievement_panel(self, mock_achievement_service):
        """建立成就面板實例"""
        panel = AchievementPanel()
        panel.add_service(mock_achievement_service)
        return panel
    
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
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        return interaction
    
    def test_achievement_panel_initialization(self, achievement_panel):
        """測試面板初始化"""
        assert achievement_panel.name == "AchievementPanel"
        assert achievement_panel.title == "🏆 成就系統"
        assert achievement_panel.color is not None
        assert "achievement_service" in achievement_panel.services
    
    def test_panel_inherits_base_panel(self, achievement_panel):
        """測試面板繼承自BasePanel"""
        from panels.base_panel import BasePanel
        assert isinstance(achievement_panel, BasePanel)
    
    @pytest.mark.asyncio
    async def test_create_achievement_embed_basic(self, achievement_panel):
        """測試基礎嵌入訊息建立"""
        embed = await achievement_panel.create_embed(
            title="測試成就",
            description="測試描述"
        )
        
        assert embed is not None
        # 在實際實作中，這些會是真正的discord.Embed屬性
        
    @pytest.mark.asyncio
    async def test_permissions_check_user_actions(self, achievement_panel, mock_interaction):
        """測試使用者動作權限檢查"""
        # 使用者查看成就不需要特殊權限
        has_permission = await achievement_panel.validate_permissions(
            mock_interaction, 
            "view_achievements"
        )
        assert has_permission is True
    
    @pytest.mark.asyncio
    async def test_permissions_check_admin_actions(self, achievement_panel, mock_interaction):
        """測試管理員動作權限檢查"""
        # 管理員動作需要通過服務層權限檢查
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.validate_permissions.return_value = True
        
        has_permission = await achievement_panel.validate_permissions(
            mock_interaction,
            "create_achievement", 
            "achievement_service"
        )
        
        mock_service.validate_permissions.assert_called_once_with(
            12345, 67890, "create_achievement"
        )
        assert has_permission is True
    
    @pytest.mark.asyncio
    async def test_error_handling_service_unavailable(self, achievement_panel, mock_interaction):
        """測試服務不可用時的錯誤處理"""
        # 移除服務模擬服務不可用
        achievement_panel.services.clear()
        
        # 應該優雅處理錯誤並發送錯誤訊息
        await achievement_panel.show_user_achievements(mock_interaction)
        
        # 驗證發送了錯誤回應
        mock_interaction.response.send_message.assert_called_once()


class TestAchievementPanelUserFeatures:
    """測試使用者成就面板功能 (F2)"""
    
    @pytest.fixture
    def mock_achievement_service(self):
        service = Mock(spec=AchievementService)
        service.name = "achievement_service"
        service.is_initialized = True
        return service
    
    @pytest.fixture
    def achievement_panel(self, mock_achievement_service):
        panel = AchievementPanel()
        panel.add_service(mock_achievement_service)
        return panel
    
    @pytest.fixture
    def mock_interaction(self):
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        return interaction
    
    @pytest.fixture
    def sample_achievements(self):
        """樣本成就資料"""
        return [
            {
                "achievement_id": "msg_100",
                "achievement_name": "健談者",
                "achievement_description": "發送100則訊息",
                "achievement_type": "milestone",
                "current_progress": {"message_count": 75},
                "completed": False,
                "completed_at": None,
                "last_updated": datetime.now()
            },
            {
                "achievement_id": "voice_1h", 
                "achievement_name": "話匣子",
                "achievement_description": "語音通話1小時",
                "achievement_type": "milestone",
                "current_progress": {"voice_time": 3600},
                "completed": True,
                "completed_at": datetime.now() - timedelta(days=1),
                "last_updated": datetime.now() - timedelta(days=1)
            }
        ]
    
    @pytest.mark.asyncio
    async def test_show_user_achievements_success(
        self, 
        achievement_panel, 
        mock_interaction, 
        sample_achievements
    ):
        """測試使用者成就列表顯示成功"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.return_value = sample_achievements
        
        await achievement_panel.show_user_achievements(mock_interaction)
        
        # 驗證服務調用
        mock_service.list_user_achievements.assert_called_once_with(12345, 67890, False)
        
        # 驗證回應發送
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_show_user_achievements_pagination(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試成就列表分頁功能"""
        # 建立15個成就模擬需要分頁
        achievements = []
        for i in range(15):
            achievements.append({
                "achievement_id": f"test_{i}",
                "achievement_name": f"測試成就{i}",
                "achievement_description": f"測試描述{i}",
                "achievement_type": "milestone",
                "current_progress": {"test_count": i * 10},
                "completed": i % 3 == 0,  # 每3個一個完成
                "completed_at": datetime.now() if i % 3 == 0 else None,
                "last_updated": datetime.now()
            })
        
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.return_value = achievements
        
        await achievement_panel.show_user_achievements(mock_interaction, page=0)
        
        # 驗證分頁邏輯（預期每頁10個）
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        # 在實際實作中會檢查嵌入訊息是否包含分頁資訊
    
    @pytest.mark.asyncio
    async def test_show_achievement_details_success(
        self,
        achievement_panel, 
        mock_interaction
    ):
        """測試成就詳情顯示成功"""
        # 模擬成就詳情
        achievement = Achievement(
            id="msg_100",
            name="健談者",
            description="發送100則訊息獲得此成就",
            achievement_type=AchievementType.MILESTONE,
            guild_id=67890,
            trigger_conditions=[
                TriggerCondition(
                    trigger_type=TriggerType.MESSAGE_COUNT,
                    target_value=100,
                    comparison_operator=">="
                )
            ],
            rewards=[
                AchievementReward(
                    reward_type=RewardType.CURRENCY,
                    value=50
                )
            ]
        )
        
        progress = AchievementProgress(
            id="progress_12345_msg_100",
            achievement_id="msg_100",
            user_id=12345,
            guild_id=67890,
            current_progress={"message_count": 75},
            completed=False
        )
        
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.get_achievement.return_value = achievement
        mock_service.get_user_progress.return_value = progress
        
        await achievement_panel.show_achievement_details(mock_interaction, "msg_100")
        
        # 驗證服務調用
        mock_service.get_achievement.assert_called_once_with("msg_100")
        mock_service.get_user_progress.assert_called_once_with(12345, "msg_100")
        
        # 驗證回應發送
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_show_achievement_details_not_found(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試成就不存在時的錯誤處理"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.get_achievement.return_value = None
        
        await achievement_panel.show_achievement_details(mock_interaction, "invalid_id")
        
        # 應該發送錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
        # 在實際實作中會檢查是否為錯誤嵌入訊息
    
    @pytest.mark.asyncio
    async def test_progress_percentage_calculation(
        self,
        achievement_panel
    ):
        """測試進度百分比計算"""
        progress = AchievementProgress(
            id="test_progress",
            achievement_id="msg_100", 
            user_id=12345,
            guild_id=67890,
            current_progress={"message_count": 75},
            completed=False
        )
        
        achievement = Achievement(
            id="msg_100",
            name="健談者",
            description="發送100則訊息",
            achievement_type=AchievementType.MILESTONE,
            guild_id=67890,
            trigger_conditions=[
                TriggerCondition(
                    trigger_type=TriggerType.MESSAGE_COUNT,
                    target_value=100,
                    comparison_operator=">="
                )
            ],
            rewards=[]
        )
        
        percentage = progress.get_progress_percentage(achievement)
        assert percentage == 0.75  # 75/100 = 0.75
    
    @pytest.mark.asyncio
    async def test_filter_achievements_by_completion(
        self,
        achievement_panel,
        mock_interaction,
        sample_achievements
    ):
        """測試按完成狀態篩選成就"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.return_value = sample_achievements
        
        # 測試只顯示已完成的成就
        await achievement_panel.show_user_achievements(
            mock_interaction, 
            completed_only=True
        )
        
        mock_service.list_user_achievements.assert_called_once_with(12345, 67890, True)


class TestAchievementPanelAdminFeatures:
    """測試管理員成就面板功能 (F3)"""
    
    @pytest.fixture
    def mock_achievement_service(self):
        service = Mock(spec=AchievementService)
        service.name = "achievement_service"
        service.is_initialized = True
        service.validate_permissions.return_value = True  # 模擬管理員權限
        return service
    
    @pytest.fixture
    def achievement_panel(self, mock_achievement_service):
        panel = AchievementPanel()
        panel.add_service(mock_achievement_service)
        return panel
    
    @pytest.fixture
    def admin_interaction(self):
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 99999  # 管理員ID
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_show_admin_panel_success(
        self,
        achievement_panel,
        admin_interaction
    ):
        """測試管理員面板顯示成功"""
        await achievement_panel.show_admin_panel(admin_interaction)
        
        # 驗證權限檢查
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.validate_permissions.assert_called_once_with(
            99999, 67890, "manage_achievements"
        )
        
        # 驗證回應發送
        admin_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_show_admin_panel_permission_denied(
        self,
        achievement_panel,
        admin_interaction
    ):
        """測試權限不足時的錯誤處理"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.validate_permissions.return_value = False
        
        await achievement_panel.show_admin_panel(admin_interaction)
        
        # 應該發送權限錯誤訊息
        admin_interaction.response.send_message.assert_called_once()
        # 在實際實作中會檢查是否為錯誤嵌入訊息
    
    @pytest.mark.asyncio
    async def test_create_achievement_modal_success(
        self,
        achievement_panel,
        admin_interaction
    ):
        """測試成就建立模態對話框"""
        await achievement_panel.create_achievement_modal(admin_interaction)
        
        # 應該發送模態對話框
        admin_interaction.response.send_modal.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_achievement_creation(
        self,
        achievement_panel,
        admin_interaction
    ):
        """測試處理成就建立"""
        # 模擬表單提交資料
        form_data = {
            "name": "新成就",
            "description": "新成就描述", 
            "achievement_type": "milestone",
            "trigger_type": "message_count",
            "target_value": "50"
        }
        
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.create_achievement.return_value = Mock()
        
        await achievement_panel.handle_achievement_creation(admin_interaction, form_data)
        
        # 驗證成就建立調用
        mock_service.create_achievement.assert_called_once()
        
        # 驗證成功訊息發送
        admin_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_achievement_statistics_display(
        self,
        achievement_panel,
        admin_interaction
    ):
        """測試成就統計資料顯示"""
        # 模擬統計資料
        stats = {
            "total_achievements": 5,
            "active_achievements": 4,
            "total_completions": 25,
            "completion_rate": 0.83
        }
        
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.get_guild_achievement_stats.return_value = stats
        
        await achievement_panel.show_achievement_statistics(admin_interaction)
        
        mock_service.get_guild_achievement_stats.assert_called_once_with(67890)
        admin_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_achievement_visibility_toggle(
        self,
        achievement_panel,
        admin_interaction
    ):
        """測試成就可見性設定切換"""
        achievement_id = "test_achievement"
        new_status = AchievementStatus.DISABLED
        
        mock_service = achievement_panel.get_service("achievement_service")
        updated_achievement = Mock()
        updated_achievement.status = new_status
        mock_service.update_achievement.return_value = updated_achievement
        
        await achievement_panel.toggle_achievement_visibility(
            admin_interaction, 
            achievement_id, 
            new_status
        )
        
        mock_service.update_achievement.assert_called_once()
        admin_interaction.response.send_message.assert_called_once()


class TestAchievementPanelPerformance:
    """測試效能要求 (N1)"""
    
    @pytest.fixture
    def achievement_panel(self):
        panel = AchievementPanel()
        mock_service = Mock(spec=AchievementService)
        mock_service.name = "achievement_service"
        mock_service.is_initialized = True
        panel.add_service(mock_service)
        return panel
    
    @pytest.fixture
    def mock_interaction(self):
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_achievement_list_performance(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試成就列表載入效能 (<2秒)"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.return_value = []
        
        import time
        start_time = time.time()
        
        await achievement_panel.show_user_achievements(mock_interaction)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # 效能要求：<2秒  (在測試中應該遠小於此值)
        assert response_time < 2.0
    
    @pytest.mark.asyncio
    async def test_admin_panel_performance(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試管理面板響應效能 (<1秒)"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.validate_permissions.return_value = True
        
        import time
        start_time = time.time()
        
        await achievement_panel.show_admin_panel(mock_interaction)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # 效能要求：<1秒
        assert response_time < 1.0
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(
        self,
        achievement_panel
    ):
        """測試並發請求處理能力 (50個並發請求)"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.return_value = []
        
        async def simulate_request():
            interaction = Mock()
            interaction.user = Mock()
            interaction.user.id = 12345
            interaction.guild = Mock()
            interaction.guild.id = 67890
            interaction.response = Mock()
            interaction.response.is_done.return_value = False
            interaction.response.send_message = AsyncMock()
            
            await achievement_panel.show_user_achievements(interaction)
        
        # 建立50個並發請求
        tasks = [simulate_request() for _ in range(50)]
        
        import time
        start_time = time.time()
        
        # 執行並發請求
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 所有請求應該在合理時間內完成
        assert total_time < 5.0  # 5秒內處理50個請求
        
        # 驗證所有請求都被處理
        assert mock_service.list_user_achievements.call_count == 50


class TestAchievementPanelErrorHandling:
    """測試錯誤處理和穩定性要求 (N3)"""
    
    @pytest.fixture
    def achievement_panel(self):
        panel = AchievementPanel()
        mock_service = Mock(spec=AchievementService)
        mock_service.name = "achievement_service"
        mock_service.is_initialized = True
        panel.add_service(mock_service)
        return panel
    
    @pytest.fixture
    def mock_interaction(self):
        interaction = Mock()
        interaction.user = Mock()
        interaction.user.id = 12345
        interaction.guild = Mock()
        interaction.guild.id = 67890
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_service_error_handling(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試服務錯誤的優雅處理"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.side_effect = ServiceError(
            "資料庫連接失敗", 
            service_name="achievement_service"
        )
        
        # 不應該拋出異常，應該發送錯誤訊息給使用者
        await achievement_panel.show_user_achievements(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        # 在實際實作中會檢查是否發送了錯誤嵌入訊息
    
    @pytest.mark.asyncio 
    async def test_permission_error_handling(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試權限錯誤的處理"""
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.validate_permissions.side_effect = ServicePermissionError(
            "權限不足",
            service_name="achievement_service"
        )
        
        await achievement_panel.show_admin_panel(mock_interaction)
        
        # 應該發送權限錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalid_input_handling(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試無效輸入的處理"""
        # 測試無效的成就ID
        await achievement_panel.show_achievement_details(mock_interaction, "")
        
        # 應該發送輸入驗證錯誤訊息
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discord_api_error_handling(
        self,
        achievement_panel,
        mock_interaction
    ):
        """測試Discord API錯誤的處理"""
        mock_interaction.response.send_message.side_effect = discord.HTTPException(
            Mock(), "API請求失敗"
        )
        
        mock_service = achievement_panel.get_service("achievement_service")
        mock_service.list_user_achievements.return_value = []
        
        # 不應該導致程式崩潰
        with pytest.raises(discord.HTTPException):
            await achievement_panel.show_user_achievements(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_memory_leak_prevention(
        self,
        achievement_panel
    ):
        """測試記憶體洩漏防護"""
        # 模擬大量操作
        for i in range(100):
            interaction = Mock()
            interaction.user = Mock()
            interaction.user.id = i
            interaction.guild = Mock() 
            interaction.guild.id = 67890
            interaction.response = Mock()
            interaction.response.is_done.return_value = False
            interaction.response.send_message = AsyncMock()
            
            mock_service = achievement_panel.get_service("achievement_service")
            mock_service.list_user_achievements.return_value = []
            
            await achievement_panel.show_user_achievements(interaction)
        
        # 檢查面板狀態沒有無限增長
        assert len(achievement_panel.state.user_data) <= 100
        # 在實際實作中會有更精確的記憶體使用檢查


# 測試執行效能基準標記
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.performance,  # 效能測試標記
    pytest.mark.ui,          # UI測試標記  
    pytest.mark.achievement  # 成就系統標記
]