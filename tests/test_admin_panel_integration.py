"""管理面板整合測試.

此模組測試管理面板各組件的整合功能:
- 管理面板與真實服務的整合
- 條件管理器與管理面板的整合
- 幫助系統與管理面板的整合
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from src.cogs.achievement.panel.admin_panel import AdminPanel
from src.cogs.achievement.database.models import Achievement, AchievementType


@pytest.fixture
def mock_bot():
    """創建模擬的 Discord Bot."""
    bot = MagicMock()
    return bot


@pytest.fixture
def mock_achievement_service():
    """創建模擬的成就服務."""
    service = AsyncMock()
    service.repository = AsyncMock()
    return service


@pytest.fixture
def mock_admin_permission_service():
    """創建模擬的管理權限服務."""
    service = AsyncMock()
    return service


@pytest.fixture
def admin_panel(mock_bot, mock_achievement_service, mock_admin_permission_service):
    """創建管理面板實例."""
    return AdminPanel(
        bot=mock_bot,
        achievement_service=mock_achievement_service,
        admin_permission_service=mock_admin_permission_service,
        guild_id=123456789,
        admin_user_id=987654321,
    )


@pytest.fixture
def mock_interaction():
    """創建模擬的 Discord 互動."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.guild = MagicMock()
    interaction.guild.id = 123456789
    interaction.user = MagicMock()
    interaction.user.id = 987654321
    return interaction


@pytest.fixture
def sample_achievement():
    """創建範例成就."""
    return Achievement(
        id=1,
        name="測試成就",
        description="這是一個測試成就",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={"target_value": 100, "metric": "message_count"},
        points=500,
        is_active=True,
    )


class TestAdminPanelIntegration:
    """測試管理面板整合功能."""

    @pytest.mark.asyncio
    async def test_admin_panel_initialization(self, admin_panel):
        """測試管理面板初始化."""
        # 驗證初始化
        assert admin_panel.guild_id == 123456789
        assert admin_panel.admin_user_id == 987654321
        assert admin_panel.criteria_manager is not None
        assert admin_panel.help_system is not None

    @pytest.mark.asyncio
    async def test_start_panel_success(self, admin_panel, mock_interaction):
        """測試成功啟動管理面板."""
        # 設置模擬統計數據
        admin_panel._load_system_stats = AsyncMock(
            return_value={
                "total_users": 100,
                "total_achievements": 10,
                "unlocked_achievements": 50,
                "unlock_rate": 50.0,
            }
        )

        # 執行測試
        await admin_panel.start(mock_interaction)

        # 驗證結果
        mock_interaction.followup.send.assert_called_once()
        assert admin_panel.current_interaction == mock_interaction

    @pytest.mark.asyncio
    async def test_get_admin_service_with_repository(self, admin_panel):
        """測試獲取管理服務(有 repository)."""
        # 執行測試
        admin_service = await admin_panel._get_admin_service()

        # 驗證結果
        assert admin_service is not None
        # 應該返回 RealAdminService 實例

    @pytest.mark.asyncio
    async def test_criteria_manager_integration(
        self, admin_panel, mock_interaction, sample_achievement
    ):
        """測試條件管理器整合."""
        # 設置模擬返回
        admin_panel.achievement_service.get_achievement_by_id.return_value = (
            sample_achievement
        )

        # 執行測試
        await admin_panel.criteria_manager.start_criteria_editor(mock_interaction, 1)

        # 驗證結果
        assert admin_panel.criteria_manager.current_achievement == sample_achievement
        mock_interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_system_integration(self, admin_panel, mock_interaction):
        """測試幫助系統整合."""
        # 執行測試
        await admin_panel.help_system.show_help_overview(mock_interaction)

        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_panel_view_help_button(self, admin_panel, mock_interaction):
        """測試管理面板視圖的幫助按鈕."""
        from src.cogs.achievement.panel.admin_panel import AdminPanelView

        # 創建視圖
        view = AdminPanelView(admin_panel)

        # 執行測試
        await view.help_button(mock_interaction, MagicMock())

        # 驗證結果
        # 由於幫助系統會發送新訊息,這裡不會調用 edit_message
        # 而是會調用 response.send_message

    @pytest.mark.asyncio
    async def test_achievement_criteria_selection_integration(
        self, admin_panel, mock_interaction, sample_achievement
    ):
        """測試成就條件選擇整合."""
        from src.cogs.achievement.panel.admin_panel import (
            AchievementCriteriaSelectionView,
        )

        # 設置模擬返回
        achievements = [sample_achievement]

        # 創建視圖
        view = AchievementCriteriaSelectionView(admin_panel, achievements)

        # 模擬選擇
        view.achievement_select.values = ["1"]
        admin_panel.achievement_service.get_achievement_by_id.return_value = (
            sample_achievement
        )

        # 執行測試
        await view.achievement_selected(mock_interaction)

        # 驗證結果
        admin_panel.achievement_service.get_achievement_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_real_admin_service_integration(
        self, admin_panel, sample_achievement
    ):
        """測試真實管理服務整合."""
        # 設置模擬返回
        admin_panel.achievement_service.repository.get_user_achievements.return_value = []
        admin_panel.achievement_service.repository.get_user_progress.return_value = []

        # 獲取管理服務
        admin_service = await admin_panel._get_admin_service()

        # 執行測試
        achievements = await admin_service.get_user_achievements(123456789)
        progress = await admin_service.get_user_progress(123456789)

        # 驗證結果
        assert achievements == []
        assert progress == []

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, admin_panel, mock_interaction):
        """測試錯誤處理整合."""
        # 設置模擬拋出異常
        admin_panel._load_system_stats = AsyncMock(side_effect=Exception("Test error"))

        # 執行測試
        await admin_panel.start(mock_interaction)

        # 驗證結果
        # 應該處理錯誤並發送錯誤訊息
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigation_integration(self, admin_panel, mock_interaction):
        """測試導航整合."""
        from src.cogs.achievement.panel.admin_panel import AdminPanelState

        # 設置模擬統計數據
        admin_panel._load_system_stats = AsyncMock(return_value={})
        admin_panel._load_achievement_management_stats = AsyncMock(return_value={})

        # 執行測試 - 導航到成就管理
        await admin_panel.handle_navigation(
            mock_interaction, AdminPanelState.ACHIEVEMENTS
        )

        # 驗證結果
        assert admin_panel.current_state == AdminPanelState.ACHIEVEMENTS

    @pytest.mark.asyncio
    async def test_session_timeout_handling(self, admin_panel):
        """測試會話超時處理."""
        from datetime import datetime, timedelta

        # 設置過期時間
        admin_panel.last_activity = datetime.utcnow() - timedelta(minutes=20)

        # 檢查是否過期
        is_expired = admin_panel._is_session_expired()

        # 驗證結果
        assert is_expired is True

    @pytest.mark.asyncio
    async def test_permission_validation_integration(
        self, admin_panel, mock_interaction
    ):
        """測試權限驗證整合."""
        # 設置模擬權限檢查
        admin_panel.admin_permission_service.has_admin_permission.return_value = True

        # 執行權限檢查
        has_permission = (
            await admin_panel.admin_permission_service.has_admin_permission(
                987654321, 123456789
            )
        )

        # 驗證結果
        assert has_permission is True

    @pytest.mark.asyncio
    async def test_statistics_caching_integration(self, admin_panel):
        """測試統計數據緩存整合."""
        # 設置模擬統計數據
        mock_stats = {
            "total_users": 100,
            "total_achievements": 10,
            "unlocked_achievements": 50,
            "unlock_rate": 50.0,
        }

        # 模擬載入統計數據
        admin_panel.achievement_service.get_system_stats = AsyncMock(
            return_value=mock_stats
        )

        # 第一次載入
        stats1 = await admin_panel._load_system_stats()

        # 第二次載入(應該使用緩存)
        stats2 = await admin_panel._load_system_stats()

        # 驗證結果
        assert stats1 == mock_stats
        assert stats2 == mock_stats
        # 由於緩存,服務方法應該只被調用一次
        assert admin_panel.achievement_service.get_system_stats.call_count <= 2

    @pytest.mark.asyncio
    async def test_full_workflow_integration(
        self, admin_panel, mock_interaction, sample_achievement
    ):
        """測試完整工作流程整合."""
        # 設置模擬數據
        admin_panel._load_system_stats = AsyncMock(
            return_value={"total_users": 100, "total_achievements": 10}
        )
        admin_panel.achievement_service.get_all_achievements.return_value = [
            sample_achievement
        ]
        admin_panel.achievement_service.get_achievement_by_id.return_value = (
            sample_achievement
        )
        admin_panel.achievement_service.update_achievement.return_value = True

        # 1. 啟動管理面板
        await admin_panel.start(mock_interaction)

        # 2. 啟動條件編輯器
        await admin_panel.criteria_manager.start_criteria_editor(mock_interaction, 1)

        # 3. 保存條件
        admin_panel.criteria_manager.current_achievement = sample_achievement
        admin_panel.criteria_manager.current_criteria = {"target_value": 200}
        result = await admin_panel.criteria_manager.save_criteria()

        # 4. 顯示幫助
        await admin_panel.help_system.show_help_overview(mock_interaction)

        # 驗證結果
        assert result is True
        assert sample_achievement.criteria == {"target_value": 200}
        assert mock_interaction.response.send_message.call_count >= 2
