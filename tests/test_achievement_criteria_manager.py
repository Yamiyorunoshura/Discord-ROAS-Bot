"""測試成就條件管理器.

此模組測試 AchievementCriteriaManager 的所有功能：
- 條件編輯器啟動
- 條件設置和保存
- 各種條件類型
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from src.cogs.achievement.panel.achievement_criteria_manager import AchievementCriteriaManager
from src.cogs.achievement.database.models import Achievement, AchievementType


@pytest.fixture
def mock_admin_panel():
    """創建模擬的管理面板."""
    panel = MagicMock()
    panel.admin_user_id = 987654321
    return panel


@pytest.fixture
def mock_achievement_service():
    """創建模擬的成就服務."""
    service = AsyncMock()
    return service


@pytest.fixture
def criteria_manager(mock_admin_panel, mock_achievement_service):
    """創建條件管理器實例."""
    return AchievementCriteriaManager(mock_admin_panel, mock_achievement_service)


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
        is_active=True
    )


@pytest.fixture
def mock_interaction():
    """創建模擬的 Discord 互動."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


class TestAchievementCriteriaManager:
    """測試成就條件管理器."""

    @pytest.mark.asyncio
    async def test_start_criteria_editor_success(self, criteria_manager, mock_interaction, sample_achievement):
        """測試成功啟動條件編輯器."""
        # 設置模擬返回
        criteria_manager.achievement_service.get_achievement_by_id.return_value = sample_achievement
        
        # 執行測試
        await criteria_manager.start_criteria_editor(mock_interaction, 1)
        
        # 驗證結果
        assert criteria_manager.current_achievement == sample_achievement
        assert criteria_manager.current_criteria == sample_achievement.criteria
        criteria_manager.achievement_service.get_achievement_by_id.assert_called_once_with(1)
        mock_interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_criteria_editor_achievement_not_found(self, criteria_manager, mock_interaction):
        """測試啟動條件編輯器時成就不存在."""
        # 設置模擬返回
        criteria_manager.achievement_service.get_achievement_by_id.return_value = None
        
        # 執行測試
        await criteria_manager.start_criteria_editor(mock_interaction, 999)
        
        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "❌ 找不到指定的成就" in str(call_args)

    @pytest.mark.asyncio
    async def test_start_criteria_editor_error(self, criteria_manager, mock_interaction):
        """測試啟動條件編輯器時發生錯誤."""
        # 設置模擬拋出異常
        criteria_manager.achievement_service.get_achievement_by_id.side_effect = Exception("Service error")
        
        # 執行測試
        await criteria_manager.start_criteria_editor(mock_interaction, 1)
        
        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "❌ 啟動條件編輯器時發生錯誤" in str(call_args)

    @pytest.mark.asyncio
    async def test_save_criteria_success(self, criteria_manager, sample_achievement):
        """測試成功保存條件."""
        # 設置初始狀態
        criteria_manager.current_achievement = sample_achievement
        criteria_manager.current_criteria = {"target_value": 200, "metric": "message_count"}
        
        # 設置模擬返回
        criteria_manager.achievement_service.update_achievement.return_value = True
        
        # 執行測試
        result = await criteria_manager.save_criteria()
        
        # 驗證結果
        assert result is True
        assert sample_achievement.criteria == criteria_manager.current_criteria
        criteria_manager.achievement_service.update_achievement.assert_called_once_with(sample_achievement)

    @pytest.mark.asyncio
    async def test_save_criteria_error(self, criteria_manager, sample_achievement):
        """測試保存條件時發生錯誤."""
        # 設置初始狀態
        criteria_manager.current_achievement = sample_achievement
        criteria_manager.current_criteria = {"target_value": 200}
        
        # 設置模擬拋出異常
        criteria_manager.achievement_service.update_achievement.side_effect = Exception("Update error")
        
        # 執行測試
        result = await criteria_manager.save_criteria()
        
        # 驗證結果
        assert result is False

    @pytest.mark.asyncio
    async def test_create_criteria_overview_embed(self, criteria_manager, sample_achievement):
        """測試創建條件概覽 Embed."""
        # 設置初始狀態
        criteria_manager.current_achievement = sample_achievement
        criteria_manager.current_criteria = {
            "target_value": 100,
            "metric": "message_count",
            "time_window": "7d"
        }
        
        # 執行測試
        embed = await criteria_manager._create_criteria_overview_embed()
        
        # 驗證結果
        assert embed.title == "🎯 成就條件編輯器"
        assert sample_achievement.name in embed.description
        assert "3 個條件" in embed.description

    @pytest.mark.asyncio
    async def test_create_criteria_overview_embed_no_criteria(self, criteria_manager, sample_achievement):
        """測試創建條件概覽 Embed（無條件）."""
        # 設置初始狀態
        criteria_manager.current_achievement = sample_achievement
        criteria_manager.current_criteria = {}
        
        # 執行測試
        embed = await criteria_manager._create_criteria_overview_embed()
        
        # 驗證結果
        assert embed.title == "🎯 成就條件編輯器"
        assert "0 個條件" in embed.description


class TestCriteriaEditorView:
    """測試條件編輯器視圖."""

    @pytest.fixture
    def criteria_editor_view(self, criteria_manager):
        """創建條件編輯器視圖."""
        from src.cogs.achievement.panel.achievement_criteria_manager import CriteriaEditorView
        return CriteriaEditorView(criteria_manager)

    @pytest.mark.asyncio
    async def test_message_count_criteria_button(self, criteria_editor_view, mock_interaction):
        """測試訊息數量條件按鈕."""
        # 執行測試
        await criteria_editor_view.message_count_criteria(mock_interaction, MagicMock())
        
        # 驗證結果
        mock_interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_keyword_criteria_button(self, criteria_editor_view, mock_interaction):
        """測試關鍵字條件按鈕."""
        # 執行測試
        await criteria_editor_view.keyword_criteria(mock_interaction, MagicMock())
        
        # 驗證結果
        mock_interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_time_criteria_button(self, criteria_editor_view, mock_interaction):
        """測試時間條件按鈕."""
        # 執行測試
        await criteria_editor_view.time_criteria(mock_interaction, MagicMock())
        
        # 驗證結果
        mock_interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_complex_criteria_button(self, criteria_editor_view, mock_interaction):
        """測試複合條件按鈕."""
        # 執行測試
        await criteria_editor_view.complex_criteria(mock_interaction, MagicMock())
        
        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_and_save_button(self, criteria_editor_view, mock_interaction):
        """測試預覽並保存按鈕."""
        # 執行測試
        await criteria_editor_view.preview_and_save(mock_interaction, MagicMock())
        
        # 驗證結果
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()


class TestMessageCountCriteriaModal:
    """測試訊息數量條件模態框."""

    @pytest.fixture
    def message_count_modal(self, criteria_manager):
        """創建訊息數量條件模態框."""
        from src.cogs.achievement.panel.achievement_criteria_manager import MessageCountCriteriaModal
        return MessageCountCriteriaModal(criteria_manager)

    @pytest.mark.asyncio
    async def test_on_submit_valid_input(self, message_count_modal, mock_interaction, criteria_manager):
        """測試提交有效輸入."""
        # 設置模擬輸入
        message_count_modal.target_value.value = "100"
        message_count_modal.time_window.value = "7d"
        
        # 設置初始狀態
        criteria_manager.current_criteria = {}
        
        # 執行測試
        await message_count_modal.on_submit(mock_interaction)
        
        # 驗證結果
        assert criteria_manager.current_criteria["target_value"] == 100
        assert criteria_manager.current_criteria["metric"] == "message_count"
        assert criteria_manager.current_criteria["time_window"] == "7d"
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_submit_invalid_input(self, message_count_modal, mock_interaction):
        """測試提交無效輸入."""
        # 設置模擬輸入
        message_count_modal.target_value.value = "invalid"
        message_count_modal.time_window.value = ""
        
        # 執行測試
        await message_count_modal.on_submit(mock_interaction)
        
        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "❌ 請輸入有效的數字" in str(call_args)


class TestKeywordCriteriaModal:
    """測試關鍵字條件模態框."""

    @pytest.fixture
    def keyword_modal(self, criteria_manager):
        """創建關鍵字條件模態框."""
        from src.cogs.achievement.panel.achievement_criteria_manager import KeywordCriteriaModal
        return KeywordCriteriaModal(criteria_manager)

    @pytest.mark.asyncio
    async def test_on_submit_valid_input(self, keyword_modal, mock_interaction, criteria_manager):
        """測試提交有效輸入."""
        # 設置模擬輸入
        keyword_modal.keywords.value = "謝謝, 感謝, 讚"
        keyword_modal.keyword_count.value = "10"
        
        # 設置初始狀態
        criteria_manager.current_criteria = {}
        
        # 執行測試
        await keyword_modal.on_submit(mock_interaction)
        
        # 驗證結果
        assert criteria_manager.current_criteria["keywords"] == ["謝謝", "感謝", "讚"]
        assert criteria_manager.current_criteria["keyword_count"] == 10
        assert criteria_manager.current_criteria["metric"] == "keyword_usage"
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_submit_empty_keywords(self, keyword_modal, mock_interaction):
        """測試提交空關鍵字."""
        # 設置模擬輸入
        keyword_modal.keywords.value = ""
        keyword_modal.keyword_count.value = "10"
        
        # 執行測試
        await keyword_modal.on_submit(mock_interaction)
        
        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "❌ 請至少輸入一個關鍵字" in str(call_args)


class TestTimeCriteriaModal:
    """測試時間條件模態框."""

    @pytest.fixture
    def time_modal(self, criteria_manager):
        """創建時間條件模態框."""
        from src.cogs.achievement.panel.achievement_criteria_manager import TimeCriteriaModal
        return TimeCriteriaModal(criteria_manager)

    @pytest.mark.asyncio
    async def test_on_submit_valid_input(self, time_modal, mock_interaction, criteria_manager):
        """測試提交有效輸入."""
        # 設置模擬輸入
        time_modal.consecutive_days.value = "7"
        time_modal.activity_type.value = "message"
        
        # 設置初始狀態
        criteria_manager.current_criteria = {}
        
        # 執行測試
        await time_modal.on_submit(mock_interaction)
        
        # 驗證結果
        assert criteria_manager.current_criteria["consecutive_days"] == 7
        assert criteria_manager.current_criteria["daily_activity_type"] == "message"
        assert criteria_manager.current_criteria["metric"] == "consecutive_activity"
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_submit_invalid_days(self, time_modal, mock_interaction):
        """測試提交無效天數."""
        # 設置模擬輸入
        time_modal.consecutive_days.value = "0"
        time_modal.activity_type.value = "message"
        
        # 執行測試
        await time_modal.on_submit(mock_interaction)
        
        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "❌ 連續天數必須大於0" in str(call_args)
