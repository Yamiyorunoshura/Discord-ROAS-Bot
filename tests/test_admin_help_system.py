"""測試管理面板幫助系統.

此模組測試 AdminHelpSystem 的所有功能:
- 幫助概覽顯示
- 各種幫助視圖
- 導航功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from src.cogs.achievement.panel.admin_help_system import (
    AdminHelpSystem,
    HelpOverviewView,
    FeatureGuideView,
    QuickStartView,
    BestPracticesView,
    FAQView,
    SecurityGuideView,
)


@pytest.fixture
def mock_admin_panel():
    """創建模擬的管理面板."""
    panel = MagicMock()
    panel.admin_user_id = 987654321
    return panel


@pytest.fixture
def help_system(mock_admin_panel):
    """創建幫助系統實例."""
    return AdminHelpSystem(mock_admin_panel)


@pytest.fixture
def mock_interaction():
    """創建模擬的 Discord 互動."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


class TestAdminHelpSystem:
    """測試管理面板幫助系統."""

    @pytest.mark.asyncio
    async def test_show_help_overview_success(self, help_system, mock_interaction):
        """測試成功顯示幫助概覽."""
        # 執行測試
        await help_system.show_help_overview(mock_interaction)

        # 驗證結果
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert call_args.kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_show_help_overview_error(self, help_system, mock_interaction):
        """測試顯示幫助概覽時發生錯誤."""
        # 設置模擬拋出異常
        mock_interaction.response.send_message.side_effect = Exception("Discord error")

        # 執行測試
        await help_system.show_help_overview(mock_interaction)

        # 驗證結果
        # 由於異常被捕獲,應該會發送錯誤訊息
        assert mock_interaction.response.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_create_help_overview_embed(self, help_system):
        """測試創建幫助概覽 Embed."""
        # 執行測試
        embed = await help_system._create_help_overview_embed()

        # 驗證結果
        assert embed.title == "📚 管理面板使用指南"
        assert "Discord ROAS Bot" in embed.description
        assert len(embed.fields) >= 3  # 至少有主要功能、使用指南、快速操作三個欄位

    @pytest.mark.asyncio
    async def test_create_quick_start_embed(self, help_system):
        """測試創建快速開始 Embed."""
        # 創建 HelpOverviewView 實例來測試其方法
        view = HelpOverviewView(help_system)

        # 執行測試
        embed = await view._create_quick_start_embed()

        # 驗證結果
        assert embed.title == "🚀 快速開始指南"
        assert "歡迎使用成就系統管理面板" in embed.description
        assert len(embed.fields) >= 4  # 至少有4個步驟

    @pytest.mark.asyncio
    async def test_create_feature_guide_embed(self, help_system):
        """測試創建功能詳解 Embed."""
        # 創建 HelpOverviewView 實例來測試其方法
        view = HelpOverviewView(help_system)

        # 執行測試
        embed = await view._create_feature_guide_embed()

        # 驗證結果
        assert embed.title == "📋 功能詳解"
        assert "詳細介紹管理面板的各項功能" in embed.description
        assert len(embed.fields) >= 3  # 至少有成就管理、用戶管理、條件設置

    @pytest.mark.asyncio
    async def test_create_best_practices_embed(self, help_system):
        """測試創建最佳實踐 Embed."""
        # 創建 HelpOverviewView 實例來測試其方法
        view = HelpOverviewView(help_system)

        # 執行測試
        embed = await view._create_best_practices_embed()

        # 驗證結果
        assert embed.title == "💡 最佳實踐建議"
        assert "遵循這些建議可以更好地使用管理面板" in embed.description
        assert len(embed.fields) >= 3  # 至少有成就設計、用戶管理、安全管理

    @pytest.mark.asyncio
    async def test_create_faq_embed(self, help_system):
        """測試創建常見問題 Embed."""
        # 創建 HelpOverviewView 實例來測試其方法
        view = HelpOverviewView(help_system)

        # 執行測試
        embed = await view._create_faq_embed()

        # 驗證結果
        assert embed.title == "❓ 常見問題解答"
        assert "以下是使用管理面板時的常見問題" in embed.description
        assert len(embed.fields) >= 3  # 至少有3個常見問題

    @pytest.mark.asyncio
    async def test_create_security_guide_embed(self, help_system):
        """測試創建安全須知 Embed."""
        # 創建 HelpOverviewView 實例來測試其方法
        view = HelpOverviewView(help_system)

        # 執行測試
        embed = await view._create_security_guide_embed()

        # 驗證結果
        assert embed.title == "🔒 安全須知"
        assert "使用管理面板時請注意以下安全事項" in embed.description
        assert len(embed.fields) >= 3  # 至少有重要提醒、禁止行為、審計日誌


class TestHelpOverviewView:
    """測試幫助概覽視圖."""

    @pytest.fixture
    def help_overview_view(self, help_system):
        """創建幫助概覽視圖."""
        return HelpOverviewView(help_system)

    @pytest.mark.asyncio
    async def test_quick_start_guide_button(self, help_overview_view, mock_interaction):
        """測試快速開始指南按鈕."""
        # 執行測試
        await help_overview_view.quick_start_guide(mock_interaction, MagicMock())

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_feature_guide_button(self, help_overview_view, mock_interaction):
        """測試功能詳解按鈕."""
        # 執行測試
        await help_overview_view.feature_guide(mock_interaction, MagicMock())

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_best_practices_button(self, help_overview_view, mock_interaction):
        """測試最佳實踐按鈕."""
        # 執行測試
        await help_overview_view.best_practices(mock_interaction, MagicMock())

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_faq_button(self, help_overview_view, mock_interaction):
        """測試常見問題按鈕."""
        # 執行測試
        await help_overview_view.faq(mock_interaction, MagicMock())

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_security_guide_button(self, help_overview_view, mock_interaction):
        """測試安全須知按鈕."""
        # 執行測試
        await help_overview_view.security_guide(mock_interaction, MagicMock())

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()


class TestFeatureGuideView:
    """測試功能詳解視圖."""

    @pytest.fixture
    def feature_guide_view(self, help_system):
        """創建功能詳解視圖."""
        return FeatureGuideView(help_system)

    @pytest.mark.asyncio
    async def test_feature_select_achievements(
        self, feature_guide_view, mock_interaction
    ):
        """測試選擇成就管理功能."""
        # 設置模擬選擇
        mock_select = MagicMock()
        mock_select.values = ["achievements"]

        # 執行測試
        await feature_guide_view.feature_select(mock_interaction, mock_select)

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_feature_select_users(self, feature_guide_view, mock_interaction):
        """測試選擇用戶管理功能."""
        # 設置模擬選擇
        mock_select = MagicMock()
        mock_select.values = ["users"]

        # 執行測試
        await feature_guide_view.feature_select(mock_interaction, mock_select)

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_feature_select_criteria(self, feature_guide_view, mock_interaction):
        """測試選擇條件設置功能."""
        # 設置模擬選擇
        mock_select = MagicMock()
        mock_select.values = ["criteria"]

        # 執行測試
        await feature_guide_view.feature_select(mock_interaction, mock_select)

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_feature_detail_embed_achievements(self, feature_guide_view):
        """測試創建成就管理詳細說明 Embed."""
        # 執行測試
        embed = await feature_guide_view._create_feature_detail_embed("achievements")

        # 驗證結果
        assert embed.title == "🏆 成就管理詳解"
        assert "創建成就" in embed.description
        assert "編輯成就" in embed.description
        assert "批量操作" in embed.description

    @pytest.mark.asyncio
    async def test_create_feature_detail_embed_users(self, feature_guide_view):
        """測試創建用戶管理詳細說明 Embed."""
        # 執行測試
        embed = await feature_guide_view._create_feature_detail_embed("users")

        # 驗證結果
        assert embed.title == "👥 用戶管理詳解"
        assert "搜尋用戶" in embed.description
        assert "查看用戶資料" in embed.description
        assert "手動操作" in embed.description

    @pytest.mark.asyncio
    async def test_create_feature_detail_embed_criteria(self, feature_guide_view):
        """測試創建條件設置詳細說明 Embed."""
        # 執行測試
        embed = await feature_guide_view._create_feature_detail_embed("criteria")

        # 驗證結果
        assert embed.title == "🎯 條件設置詳解"
        assert "訊息數量條件" in embed.description
        assert "關鍵字條件" in embed.description
        assert "時間條件" in embed.description
        assert "複合條件" in embed.description

    @pytest.mark.asyncio
    async def test_back_to_overview_button(self, feature_guide_view, mock_interaction):
        """測試返回概覽按鈕."""
        # 執行測試
        await feature_guide_view.back_to_overview(mock_interaction, MagicMock())

        # 驗證結果
        mock_interaction.response.edit_message.assert_called_once()


class TestNavigationViews:
    """測試導航視圖."""

    @pytest.mark.asyncio
    async def test_quick_start_view_back_button(self, help_system, mock_interaction):
        """測試快速開始視圖返回按鈕."""
        view = QuickStartView(help_system)
        await view.back_to_overview(mock_interaction, MagicMock())
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_best_practices_view_back_button(self, help_system, mock_interaction):
        """測試最佳實踐視圖返回按鈕."""
        view = BestPracticesView(help_system)
        await view.back_to_overview(mock_interaction, MagicMock())
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_faq_view_back_button(self, help_system, mock_interaction):
        """測試常見問題視圖返回按鈕."""
        view = FAQView(help_system)
        await view.back_to_overview(mock_interaction, MagicMock())
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_security_guide_view_back_button(self, help_system, mock_interaction):
        """測試安全須知視圖返回按鈕."""
        view = SecurityGuideView(help_system)
        await view.back_to_overview(mock_interaction, MagicMock())
        mock_interaction.response.edit_message.assert_called_once()
