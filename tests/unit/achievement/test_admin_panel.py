"""測試成就系統管理面板控制器.

這個測試模組涵蓋 AdminPanel 和 AdminPanelView 的所有核心功能:
- 管理面板初始化和狀態管理
- 導航系統和權限檢查
- UI 組件互動和錯誤處理
- 會話管理和超時處理
- 統計數據載入和緩存機制
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from src.cogs.achievement.panel.admin_panel import (
    AdminPanel,
    AdminPanelState,
    AdminPanelView,
)


@pytest.fixture
def mock_bot():
    """創建模擬的 Discord Bot."""
    bot = AsyncMock()
    bot.get_guild.return_value = Mock(member_count=1250)
    return bot


@pytest.fixture
def mock_achievement_service():
    """創建模擬的成就服務."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_admin_permission_service():
    """創建模擬的管理員權限服務."""
    service = AsyncMock()

    # 默認權限檢查通過
    permission_result = Mock()
    permission_result.allowed = True
    permission_result.reason = "Admin access granted"
    service.check_admin_permission.return_value = permission_result

    return service


@pytest.fixture
def mock_interaction():
    """創建模擬的 Discord Interaction."""
    interaction = AsyncMock()
    interaction.guild = Mock()
    interaction.guild.get_member.return_value = Mock(spec=discord.Member)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.message = Mock()
    interaction.message.id = 123456789
    return interaction


@pytest.fixture
def admin_panel(mock_bot, mock_achievement_service, mock_admin_permission_service):
    """創建 AdminPanel 實例."""
    return AdminPanel(
        bot=mock_bot,
        achievement_service=mock_achievement_service,
        admin_permission_service=mock_admin_permission_service,
        guild_id=987654321,
        admin_user_id=123456789,
    )


class TestAdminPanel:
    """測試 AdminPanel 控制器."""

    def test_init(
        self,
        admin_panel,
        mock_bot,
        mock_achievement_service,
        mock_admin_permission_service,
    ):
        """測試管理面板初始化."""
        assert admin_panel.bot is mock_bot
        assert admin_panel.achievement_service is mock_achievement_service
        assert admin_panel.admin_permission_service is mock_admin_permission_service
        assert admin_panel.guild_id == 987654321
        assert admin_panel.admin_user_id == 123456789
        assert admin_panel.current_state == AdminPanelState.INITIALIZING
        assert admin_panel.current_view is None
        assert admin_panel.session_timeout == timedelta(minutes=15)
        assert admin_panel._cached_stats is None

    @pytest.mark.asyncio
    async def test_start_success(self, admin_panel, mock_interaction):
        """測試成功啟動管理面板."""
        with (
            patch.object(admin_panel, "_load_system_stats") as mock_load_stats,
            patch.object(admin_panel, "_create_overview_embed") as mock_create_embed,
        ):
            # 設置模擬返回值
            mock_stats = {"total_users": 100, "total_achievements": 25}
            mock_load_stats.return_value = mock_stats
            mock_embed = Mock(spec=discord.Embed)
            mock_create_embed.return_value = mock_embed

            # 執行啟動
            await admin_panel.start(mock_interaction)

            # 驗證狀態更新
            assert admin_panel.current_state == AdminPanelState.OVERVIEW
            assert admin_panel.current_interaction is mock_interaction
            assert isinstance(admin_panel.current_view, AdminPanelView)

            # 驗證方法調用
            mock_load_stats.assert_called_once()
            mock_create_embed.assert_called_once_with(mock_stats)
            mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_failure(self, admin_panel, mock_interaction):
        """測試啟動管理面板失敗."""
        with (
            patch.object(admin_panel, "_load_system_stats") as mock_load_stats,
            patch.object(admin_panel, "_handle_error") as mock_handle_error,
        ):
            # 設置異常
            mock_load_stats.side_effect = Exception("載入統計失敗")

            # 執行啟動
            await admin_panel.start(mock_interaction)

            # 驗證錯誤處理
            mock_handle_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_navigation_success(self, admin_panel, mock_interaction):
        """測試成功處理導航."""
        admin_panel.current_state = AdminPanelState.OVERVIEW

        with (
            patch.object(admin_panel, "_is_session_expired", return_value=False),
            patch.object(admin_panel, "_create_state_content") as mock_create_content,
        ):
            # 設置模擬返回值
            mock_embed = Mock(spec=discord.Embed)
            mock_view = Mock(spec=AdminPanelView)
            mock_create_content.return_value = (mock_embed, mock_view)

            # 執行導航
            await admin_panel.handle_navigation(
                mock_interaction, AdminPanelState.ACHIEVEMENTS
            )

            # 驗證狀態更新
            assert admin_panel.current_state == AdminPanelState.ACHIEVEMENTS
            assert admin_panel.current_view is mock_view

            # 驗證權限檢查
            admin_panel.admin_permission_service.check_admin_permission.assert_called_once()

            # 驗證UI更新
            mock_interaction.response.edit_message.assert_called_once_with(
                embed=mock_embed, view=mock_view
            )

    @pytest.mark.asyncio
    async def test_handle_navigation_session_expired(
        self, admin_panel, mock_interaction
    ):
        """測試導航時會話過期."""
        with (
            patch.object(admin_panel, "_is_session_expired", return_value=True),
            patch.object(admin_panel, "_handle_session_expired") as mock_handle_expired,
        ):
            # 執行導航
            await admin_panel.handle_navigation(
                mock_interaction, AdminPanelState.ACHIEVEMENTS
            )

            # 驗證會話過期處理
            mock_handle_expired.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_handle_navigation_permission_denied(
        self, admin_panel, mock_interaction
    ):
        """測試導航時權限被拒絕."""
        # 設置權限檢查失敗
        permission_result = Mock()
        permission_result.allowed = False
        permission_result.reason = "Insufficient permissions"
        admin_panel.admin_permission_service.check_admin_permission.return_value = (
            permission_result
        )

        with patch.object(admin_panel, "_is_session_expired", return_value=False):
            # 執行導航
            await admin_panel.handle_navigation(
                mock_interaction, AdminPanelState.ACHIEVEMENTS
            )

            # 驗證權限拒絕處理
            admin_panel.admin_permission_service.handle_permission_denied.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_navigation_no_member(self, admin_panel, mock_interaction):
        """測試導航時無法獲取成員資訊."""
        mock_interaction.guild.get_member.return_value = None

        with (
            patch.object(admin_panel, "_is_session_expired", return_value=False),
            patch.object(admin_panel, "_handle_error") as mock_handle_error,
        ):
            # 執行導航
            await admin_panel.handle_navigation(
                mock_interaction, AdminPanelState.ACHIEVEMENTS
            )

            # 驗證錯誤處理
            mock_handle_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_panel_success(self, admin_panel, mock_interaction):
        """測試成功關閉管理面板."""
        admin_panel.created_at = datetime.utcnow() - timedelta(minutes=5)
        admin_panel.last_activity = datetime.utcnow() - timedelta(minutes=1)

        # 執行關閉
        await admin_panel.close_panel(mock_interaction)

        # 驗證狀態更新
        assert admin_panel.current_state == AdminPanelState.CLOSED

        # 驗證UI更新
        mock_interaction.response.edit_message.assert_called_once()
        args, kwargs = mock_interaction.response.edit_message.call_args
        assert "embed" in kwargs
        assert kwargs["view"] is None

    @pytest.mark.asyncio
    async def test_close_panel_failure(self, admin_panel, mock_interaction):
        """測試關閉管理面板失敗."""
        # 設置異常
        mock_interaction.response.edit_message.side_effect = Exception("編輯訊息失敗")

        # 執行關閉
        await admin_panel.close_panel(mock_interaction)

        # 驗證狀態仍然更新
        assert admin_panel.current_state == AdminPanelState.CLOSED

    @pytest.mark.asyncio
    async def test_create_state_content_overview(self, admin_panel):
        """測試創建概覽狀態內容."""
        with (
            patch.object(admin_panel, "_load_system_stats") as mock_load_stats,
            patch.object(admin_panel, "_create_overview_embed") as mock_create_embed,
        ):
            mock_stats = {"total_users": 100}
            mock_embed = Mock(spec=discord.Embed)
            mock_load_stats.return_value = mock_stats
            mock_create_embed.return_value = mock_embed

            # 執行創建內容
            embed, view = await admin_panel._create_state_content(
                AdminPanelState.OVERVIEW
            )

            # 驗證結果
            assert embed is mock_embed
            assert isinstance(view, AdminPanelView)
            mock_load_stats.assert_called_once()
            mock_create_embed.assert_called_once_with(mock_stats)

    @pytest.mark.asyncio
    async def test_create_state_content_achievements(self, admin_panel):
        """測試創建成就管理狀態內容."""
        with patch.object(
            admin_panel, "_create_achievements_embed"
        ) as mock_create_embed:
            mock_embed = Mock(spec=discord.Embed)
            mock_create_embed.return_value = mock_embed

            # 執行創建內容
            embed, view = await admin_panel._create_state_content(
                AdminPanelState.ACHIEVEMENTS
            )

            # 驗證結果
            assert embed is mock_embed
            assert isinstance(view, AdminPanelView)
            mock_create_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_state_content_users(self, admin_panel):
        """測試創建用戶管理狀態內容."""
        with patch.object(admin_panel, "_create_users_embed") as mock_create_embed:
            mock_embed = Mock(spec=discord.Embed)
            mock_create_embed.return_value = mock_embed

            # 執行創建內容
            embed, view = await admin_panel._create_state_content(AdminPanelState.USERS)

            # 驗證結果
            assert embed is mock_embed
            assert isinstance(view, AdminPanelView)
            mock_create_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_state_content_settings(self, admin_panel):
        """測試創建系統設定狀態內容."""
        with patch.object(admin_panel, "_create_settings_embed") as mock_create_embed:
            mock_embed = Mock(spec=discord.Embed)
            mock_create_embed.return_value = mock_embed

            # 執行創建內容
            embed, view = await admin_panel._create_state_content(
                AdminPanelState.SETTINGS
            )

            # 驗證結果
            assert embed is mock_embed
            assert isinstance(view, AdminPanelView)
            mock_create_embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_state_content_unknown(self, admin_panel):
        """測試創建未知狀態內容."""
        with patch.object(admin_panel, "_create_error_embed") as mock_create_embed:
            mock_embed = Mock(spec=discord.Embed)
            mock_create_embed.return_value = mock_embed

            # 使用未定義的狀態
            unknown_state = AdminPanelState.ERROR

            # 執行創建內容
            embed, view = await admin_panel._create_state_content(unknown_state)

            # 驗證結果
            assert embed is mock_embed
            assert isinstance(view, AdminPanelView)

    @pytest.mark.asyncio
    async def test_create_overview_embed(self, admin_panel):
        """測試創建概覽 Embed."""
        stats = {
            "total_users": 1250,
            "total_achievements": 25,
            "unlocked_achievements": 128,
            "unlock_rate": 12.8,
        }

        # 執行創建 embed
        embed = await admin_panel._create_overview_embed(stats)

        # 驗證 embed 屬性
        assert isinstance(embed, discord.Embed)
        assert embed.title == "🛠️ 成就系統管理面板"
        assert embed.color == 0xFF6B35  # 橙色主題
        assert len(embed.fields) == 6  # 6個統計欄位

    @pytest.mark.asyncio
    async def test_create_achievements_embed(self, admin_panel):
        """測試創建成就管理 Embed."""
        embed = await admin_panel._create_achievements_embed()

        assert isinstance(embed, discord.Embed)
        assert embed.title == "🏆 成就管理"
        assert "Story 4.2" in embed.description
        assert embed.color == 0xFF6B35

    @pytest.mark.asyncio
    async def test_create_users_embed(self, admin_panel):
        """測試創建用戶管理 Embed."""
        embed = await admin_panel._create_users_embed()

        assert isinstance(embed, discord.Embed)
        assert embed.title == "👤 用戶管理"
        assert "Story 4.3" in embed.description
        assert embed.color == 0xFF6B35

    @pytest.mark.asyncio
    async def test_create_settings_embed(self, admin_panel):
        """測試創建系統設定 Embed."""
        embed = await admin_panel._create_settings_embed()

        assert isinstance(embed, discord.Embed)
        assert embed.title == "⚙️ 系統設定"
        assert embed.color == 0xFF6B35

    @pytest.mark.asyncio
    async def test_create_error_embed(self, admin_panel):
        """測試創建錯誤 Embed."""
        title = "測試錯誤"
        description = "這是一個測試錯誤"

        embed = await admin_panel._create_error_embed(title, description)

        assert isinstance(embed, discord.Embed)
        assert embed.title == title
        assert description in embed.description

    @pytest.mark.asyncio
    async def test_load_system_stats_with_cache(self, admin_panel):
        """測試載入系統統計(有快取)."""
        # 設置快取
        cached_stats = {"total_users": 100, "cached": True}
        admin_panel._cached_stats = cached_stats
        admin_panel._cache_expires_at = datetime.utcnow() + timedelta(minutes=1)

        # 執行載入
        stats = await admin_panel._load_system_stats()

        # 驗證返回快取數據
        assert stats is cached_stats

    @pytest.mark.asyncio
    async def test_load_system_stats_without_cache(self, admin_panel):
        """測試載入系統統計(無快取)."""
        with (
            patch.object(admin_panel, "_get_total_users", return_value=1250),
            patch.object(admin_panel, "_get_total_achievements", return_value=25),
            patch.object(admin_panel, "_get_unlocked_achievements", return_value=128),
        ):
            # 執行載入
            stats = await admin_panel._load_system_stats()

            # 驗證統計數據
            assert stats["total_users"] == 1250
            assert stats["total_achievements"] == 25
            assert stats["unlocked_achievements"] == 128
            assert abs(stats["unlock_rate"] - 512.0) < 0.1  # 128/25*100

            # 驗證快取設置
            assert admin_panel._cached_stats is stats
            assert admin_panel._cache_expires_at is not None

    @pytest.mark.asyncio
    async def test_load_system_stats_exception(self, admin_panel):
        """測試載入系統統計異常處理."""
        with patch.object(
            admin_panel, "_get_total_users", side_effect=Exception("數據庫錯誤")
        ):
            # 執行載入
            stats = await admin_panel._load_system_stats()

            # 驗證返回默認值
            assert stats["total_users"] == 0
            assert stats["total_achievements"] == 0
            assert stats["unlocked_achievements"] == 0
            assert stats["unlock_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_total_users(self, admin_panel, mock_bot):
        """測試獲取總用戶數."""
        # 執行獲取
        user_count = await admin_panel._get_total_users()

        # 驗證結果
        assert user_count == 1250  # mock_bot 設置的 member_count

    @pytest.mark.asyncio
    async def test_get_total_users_no_guild(self, admin_panel, mock_bot):
        """測試獲取總用戶數(無伺服器)."""
        mock_bot.get_guild.return_value = None

        # 執行獲取
        user_count = await admin_panel._get_total_users()

        # 驗證結果
        assert user_count == 0

    @pytest.mark.asyncio
    async def test_get_total_achievements(self, admin_panel):
        """測試獲取總成就數."""
        # 執行獲取
        achievement_count = await admin_panel._get_total_achievements()

        # 驗證結果(示例數據)
        assert achievement_count == 25

    @pytest.mark.asyncio
    async def test_get_unlocked_achievements(self, admin_panel):
        """測試獲取已解鎖成就數."""
        # 執行獲取
        unlocked_count = await admin_panel._get_unlocked_achievements()

        # 驗證結果(示例數據)
        assert unlocked_count == 128

    def test_is_session_expired_not_expired(self, admin_panel):
        """測試會話未過期."""
        admin_panel.last_activity = datetime.utcnow() - timedelta(minutes=10)

        # 使用 asyncio.run 來執行異步函數
        result = asyncio.run(admin_panel._is_session_expired())

        assert not result

    def test_is_session_expired_expired(self, admin_panel):
        """測試會話已過期."""
        admin_panel.last_activity = datetime.utcnow() - timedelta(minutes=20)

        # 使用 asyncio.run 來執行異步函數
        result = asyncio.run(admin_panel._is_session_expired())

        assert result

    @pytest.mark.asyncio
    async def test_handle_session_expired(self, admin_panel, mock_interaction):
        """測試處理會話過期."""
        # 執行處理
        await admin_panel._handle_session_expired(mock_interaction)

        # 驗證狀態更新
        assert admin_panel.current_state == AdminPanelState.CLOSED

        # 驗證UI更新
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_not_responded(self, admin_panel, mock_interaction):
        """測試處理錯誤(未回應)."""
        mock_interaction.response.is_done.return_value = False

        # 執行錯誤處理
        await admin_panel._handle_error(mock_interaction, "測試錯誤", "錯誤詳情")

        # 驗證狀態更新
        assert admin_panel.current_state == AdminPanelState.ERROR

        # 驗證使用 response.edit_message
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_already_responded(self, admin_panel, mock_interaction):
        """測試處理錯誤(已回應)."""
        mock_interaction.response.is_done.return_value = True

        # 執行錯誤處理
        await admin_panel._handle_error(mock_interaction, "測試錯誤", "錯誤詳情")

        # 驗證狀態更新
        assert admin_panel.current_state == AdminPanelState.ERROR

        # 驗證使用 followup.edit_message
        mock_interaction.followup.edit_message.assert_called_once()


class TestAdminPanelView:
    """測試 AdminPanelView UI 組件."""

    @pytest.fixture
    def admin_panel_view(self, admin_panel):
        """創建 AdminPanelView 實例."""
        return AdminPanelView(admin_panel)

    def test_view_init(self, admin_panel_view, admin_panel):
        """測試視圖初始化."""
        assert admin_panel_view.panel is admin_panel
        assert admin_panel_view.timeout == 900  # 15分鐘

    @pytest.mark.asyncio
    async def test_navigation_select_overview(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試導航選擇 - 概覽."""
        # 模擬選擇
        select = Mock()
        select.values = ["overview"]

        with patch.object(admin_panel, "handle_navigation") as mock_navigate:
            # 執行選擇
            await admin_panel_view.navigation_select(mock_interaction, select)

            # 驗證導航調用
            mock_navigate.assert_called_once_with(
                mock_interaction, AdminPanelState.OVERVIEW
            )

    @pytest.mark.asyncio
    async def test_navigation_select_achievements(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試導航選擇 - 成就管理."""
        select = Mock()
        select.values = ["achievements"]

        with patch.object(admin_panel, "handle_navigation") as mock_navigate:
            await admin_panel_view.navigation_select(mock_interaction, select)
            mock_navigate.assert_called_once_with(
                mock_interaction, AdminPanelState.ACHIEVEMENTS
            )

    @pytest.mark.asyncio
    async def test_navigation_select_users(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試導航選擇 - 用戶管理."""
        select = Mock()
        select.values = ["users"]

        with patch.object(admin_panel, "handle_navigation") as mock_navigate:
            await admin_panel_view.navigation_select(mock_interaction, select)
            mock_navigate.assert_called_once_with(
                mock_interaction, AdminPanelState.USERS
            )

    @pytest.mark.asyncio
    async def test_navigation_select_settings(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試導航選擇 - 系統設定."""
        select = Mock()
        select.values = ["settings"]

        with patch.object(admin_panel, "handle_navigation") as mock_navigate:
            await admin_panel_view.navigation_select(mock_interaction, select)
            mock_navigate.assert_called_once_with(
                mock_interaction, AdminPanelState.SETTINGS
            )

    @pytest.mark.asyncio
    async def test_navigation_select_invalid(self, admin_panel_view, mock_interaction):
        """測試導航選擇 - 無效選項."""
        select = Mock()
        select.values = ["invalid_option"]

        # 執行選擇
        await admin_panel_view.navigation_select(mock_interaction, select)

        # 驗證錯誤回應
        mock_interaction.response.send_message.assert_called_once_with(
            "❌ 無效的選擇", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_navigation_select_exception(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試導航選擇異常處理."""
        select = Mock()
        select.values = ["overview"]

        with patch.object(
            admin_panel, "handle_navigation", side_effect=Exception("導航錯誤")
        ):
            # 執行選擇
            await admin_panel_view.navigation_select(mock_interaction, select)

            # 驗證錯誤回應
            mock_interaction.response.send_message.assert_called_once_with(
                "❌ 處理導航時發生錯誤", ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_refresh_button(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試重新整理按鈕."""
        button = Mock()
        admin_panel.current_state = AdminPanelState.OVERVIEW
        admin_panel._cached_stats = {"old": "data"}
        admin_panel._cache_expires_at = datetime.utcnow()

        with patch.object(admin_panel, "handle_navigation") as mock_navigate:
            # 執行重新整理
            await admin_panel_view.refresh_button(mock_interaction, button)

            # 驗證緩存清除
            assert admin_panel._cached_stats is None
            assert admin_panel._cache_expires_at is None

            # 驗證重新載入
            mock_navigate.assert_called_once_with(
                mock_interaction, AdminPanelState.OVERVIEW
            )

    @pytest.mark.asyncio
    async def test_refresh_button_exception(
        self, admin_panel_view, admin_panel, mock_interaction
    ):
        """測試重新整理按鈕異常處理."""
        button = Mock()

        with patch.object(
            admin_panel, "handle_navigation", side_effect=Exception("重新整理錯誤")
        ):
            # 執行重新整理
            await admin_panel_view.refresh_button(mock_interaction, button)

            # 驗證錯誤回應
            mock_interaction.response.send_message.assert_called_once_with(
                "❌ 重新整理時發生錯誤", ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_close_button(self, admin_panel_view, admin_panel, mock_interaction):
        """測試關閉按鈕."""
        button = Mock()

        with patch.object(admin_panel, "close_panel") as mock_close:
            # 執行關閉
            await admin_panel_view.close_button(mock_interaction, button)

            # 驗證關閉調用
            mock_close.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_on_timeout(self, admin_panel_view, admin_panel):
        """測試視圖超時處理."""
        # 執行超時處理
        await admin_panel_view.on_timeout()

        # 驗證狀態更新
        assert admin_panel.current_state == AdminPanelState.CLOSED

    @pytest.mark.asyncio
    async def test_on_error(self, admin_panel_view, mock_interaction):
        """測試視圖錯誤處理."""
        error = Exception("UI 錯誤")
        item = Mock()

        # 執行錯誤處理
        await admin_panel_view.on_error(mock_interaction, error, item)

        # 驗證錯誤回應
        mock_interaction.response.send_message.assert_called_once_with(
            "❌ 處理互動時發生錯誤,請稍後再試", ephemeral=True
        )


class TestAdminPanelState:
    """測試 AdminPanelState 枚舉."""

    def test_all_states_defined(self):
        """測試所有狀態都有定義."""
        expected_states = {
            "INITIALIZING": "initializing",
            "OVERVIEW": "overview",
            "ACHIEVEMENTS": "achievements",
            "USERS": "users",
            "SETTINGS": "settings",
            "ERROR": "error",
            "CLOSED": "closed",
        }

        for state_name, state_value in expected_states.items():
            state = getattr(AdminPanelState, state_name)
            assert state.value == state_value

    def test_state_enum_uniqueness(self):
        """測試狀態值的唯一性."""
        all_values = [state.value for state in AdminPanelState]
        assert len(all_values) == len(set(all_values))
