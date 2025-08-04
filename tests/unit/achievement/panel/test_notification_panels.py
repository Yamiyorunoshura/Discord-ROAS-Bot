"""通知偏好面板測試模組.

測試通知偏好管理面板的所有功能,包括:
- 通知偏好設定面板
- 通知類型選擇
- 全域通知設定
- UI 互動處理
"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.cogs.achievement.database.models import (
    GlobalNotificationSettings,
    NotificationPreference,
)
from src.cogs.achievement.panel.global_notification_settings import (
    GlobalNotificationSettingsView,
    RateLimitModal,
    create_global_notification_settings_panel,
)
from src.cogs.achievement.panel.notification_preferences import (
    NotificationPreferencesView,
    NotificationTypeSelect,
    create_notification_preferences_panel,
)


class TestNotificationPreferencesView:
    """NotificationPreferencesView 測試類別."""

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        repository = AsyncMock()
        repository.get_notification_preferences.return_value = NotificationPreference(
            user_id=123456789,
            guild_id=987654321,
            dm_notifications=True,
            server_announcements=True,
            notification_types=[],
        )
        repository.update_notification_preferences.return_value = True
        repository.create_notification_preferences.return_value = (
            NotificationPreference(
                id=1,
                user_id=123456789,
                guild_id=987654321,
                dm_notifications=True,
                server_announcements=True,
                notification_types=[],
            )
        )
        return repository

    @pytest.fixture
    def mock_interaction(self):
        """模擬 Discord 互動."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.edit_message = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 123456789
        return interaction

    @pytest.fixture
    def preferences_view(self, mock_repository):
        """建立通知偏好視圖實例."""
        return NotificationPreferencesView(
            user_id=123456789, guild_id=987654321, repository=mock_repository
        )

    @pytest.mark.asyncio
    async def test_preferences_view_initialization(self, preferences_view):
        """測試通知偏好視圖初始化."""
        assert preferences_view.user_id == 123456789
        assert preferences_view.guild_id == 987654321
        assert preferences_view.preferences.dm_notifications is True
        assert preferences_view.preferences.server_announcements is True

    @pytest.mark.asyncio
    async def test_toggle_dm_notifications(
        self, preferences_view, mock_interaction, mock_repository
    ):
        """測試切換私訊通知設定."""
        # 模擬按鈕點擊
        button = MagicMock(spec=discord.ui.Button)

        # 初始狀態為開啟
        assert preferences_view.preferences.dm_notifications is True

        # 點擊切換按鈕
        await preferences_view.toggle_dm_notifications(mock_interaction, button)

        # 驗證設定被切換
        assert preferences_view.preferences.dm_notifications is False

        # 驗證資料庫更新被調用
        mock_repository.get_notification_preferences.assert_called_once()

        # 驗證回應被發送
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_server_announcements(
        self, preferences_view, mock_interaction, mock_repository
    ):
        """測試切換伺服器公告設定."""
        button = MagicMock(spec=discord.ui.Button)

        # 初始狀態為開啟
        assert preferences_view.preferences.server_announcements is True

        # 點擊切換按鈕
        await preferences_view.toggle_server_announcements(mock_interaction, button)

        # 驗證設定被切換
        assert preferences_view.preferences.server_announcements is False

        # 驗證資料庫更新被調用
        mock_repository.get_notification_preferences.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_preferences(
        self, preferences_view, mock_interaction, mock_repository
    ):
        """測試重置通知偏好."""
        button = MagicMock(spec=discord.ui.Button)

        # 修改一些設定
        preferences_view.preferences.dm_notifications = False
        preferences_view.preferences.notification_types = ["rare", "epic"]

        # 點擊重置按鈕
        await preferences_view.reset_preferences(mock_interaction, button)

        # 驗證設定被重置為預設值
        assert preferences_view.preferences.dm_notifications is True
        assert preferences_view.preferences.server_announcements is True
        assert preferences_view.preferences.notification_types == []

    @pytest.mark.asyncio
    async def test_configure_notification_types(
        self, preferences_view, mock_interaction
    ):
        """測試開啟通知類型設定."""
        button = MagicMock(spec=discord.ui.Button)

        # 點擊通知類型設定按鈕
        await preferences_view.configure_notification_types(mock_interaction, button)

        # 驗證新的選擇視圖被發送
        mock_interaction.response.send_message.assert_called_once()

        # 驗證呼叫參數包含 embed 和 view
        call_args = mock_interaction.response.send_message.call_args
        assert "embed" in call_args.kwargs
        assert "view" in call_args.kwargs
        assert call_args.kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_create_preferences_embed(self, preferences_view):
        """測試建立偏好設定 embed."""
        embed = preferences_view._create_preferences_embed()

        # 驗證 embed 結構
        assert embed.title == "🔔 通知偏好設定"
        assert len(embed.fields) >= 3  # 至少包含私訊、公告、類型篩選欄位

        # 驗證欄位內容
        field_names = [field.name for field in embed.fields]
        assert "💬 私訊通知" in field_names
        assert "📢 伺服器公告" in field_names
        assert "🎯 通知類型" in field_names

    @pytest.mark.asyncio
    async def test_save_preferences_create_new(self, preferences_view, mock_repository):
        """測試儲存新的偏好設定."""
        # 設定為不存在現有偏好
        mock_repository.get_notification_preferences.return_value = None

        # 儲存偏好
        await preferences_view._save_preferences()

        # 驗證建立新偏好被調用
        mock_repository.create_notification_preferences.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_preferences_update_existing(
        self, preferences_view, mock_repository
    ):
        """測試更新現有偏好設定."""
        existing_preference = NotificationPreference(
            id=1,
            user_id=123456789,
            guild_id=987654321,
            dm_notifications=False,
            server_announcements=False,
            notification_types=["rare"],
        )
        mock_repository.get_notification_preferences.return_value = existing_preference

        # 儲存偏好
        await preferences_view._save_preferences()

        # 驗證更新偏好被調用
        mock_repository.update_notification_preferences.assert_called_once()


class TestNotificationTypeSelect:
    """NotificationTypeSelect 測試類別."""

    @pytest.fixture
    def sample_preferences(self):
        """範例通知偏好."""
        return NotificationPreference(
            user_id=123456789,
            guild_id=987654321,
            dm_notifications=True,
            server_announcements=True,
            notification_types=["milestone", "rare"],
        )

    @pytest.fixture
    def mock_interaction(self):
        """模擬 Discord 互動."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.edit_message = AsyncMock()
        return interaction

    @pytest.fixture
    def notification_type_select(self, sample_preferences):
        """建立通知類型選擇實例."""
        return NotificationTypeSelect(sample_preferences)

    @pytest.mark.asyncio
    async def test_type_select_initialization(
        self, notification_type_select, sample_preferences
    ):
        """測試通知類型選擇初始化."""
        assert notification_type_select.preferences == sample_preferences
        assert len(notification_type_select.options) == 8  # 8種通知類型

        # 檢查預設選中的選項
        selected_options = [
            option for option in notification_type_select.options if option.default
        ]
        selected_values = [option.value for option in selected_options]
        assert "milestone" in selected_values
        assert "rare" in selected_values

    @pytest.mark.asyncio
    async def test_type_select_callback(
        self, notification_type_select, mock_interaction
    ):
        """測試通知類型選擇回調."""
        # 模擬選擇新的類型
        notification_type_select.values = ["counter", "epic", "legendary"]

        # 模擬 view 的 save_preferences 方法
        mock_view = MagicMock()
        mock_view.save_preferences = AsyncMock()
        notification_type_select.view = mock_view

        # 執行回調
        await notification_type_select.callback(mock_interaction)

        # 驗證偏好被更新
        assert notification_type_select.preferences.notification_types == [
            "counter",
            "epic",
            "legendary",
        ]

        # 驗證保存方法被調用
        mock_view.save_preferences.assert_called_once()

        # 驗證回應被發送
        mock_interaction.response.edit_message.assert_called_once()


class TestGlobalNotificationSettingsView:
    """GlobalNotificationSettingsView 測試類別."""

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        repository = AsyncMock()
        repository.get_global_notification_settings.return_value = (
            GlobalNotificationSettings(
                guild_id=987654321,
                announcement_enabled=True,
                announcement_channel_id=555666777,
                rate_limit_seconds=60,
                important_achievements_only=False,
            )
        )
        repository.update_global_notification_settings.return_value = True
        repository.create_global_notification_settings.return_value = (
            GlobalNotificationSettings(
                id=1,
                guild_id=987654321,
                announcement_enabled=True,
                announcement_channel_id=555666777,
                rate_limit_seconds=60,
                important_achievements_only=False,
            )
        )
        return repository

    @pytest.fixture
    def mock_interaction(self):
        """模擬 Discord 互動."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.edit_message = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.send_modal = AsyncMock()

        # 模擬 guild
        interaction.guild = MagicMock()
        interaction.guild.id = 987654321
        interaction.guild.name = "測試伺服器"
        interaction.guild.get_channel = MagicMock(return_value=None)

        return interaction

    @pytest.fixture
    def global_settings_view(self, mock_repository):
        """建立全域設定視圖實例."""
        return GlobalNotificationSettingsView(
            guild_id=987654321, repository=mock_repository
        )

    @pytest.mark.asyncio
    async def test_global_settings_view_initialization(self, global_settings_view):
        """測試全域設定視圖初始化."""
        assert global_settings_view.guild_id == 987654321
        assert global_settings_view.settings.announcement_enabled is False  # 預設值
        assert global_settings_view.settings.rate_limit_seconds == 60

    @pytest.mark.asyncio
    async def test_toggle_announcements(
        self, global_settings_view, mock_interaction, mock_repository
    ):
        """測試切換公告功能."""
        button = MagicMock(spec=discord.ui.Button)

        # 初始狀態為關閉
        assert global_settings_view.settings.announcement_enabled is False

        # 點擊切換按鈕
        await global_settings_view.toggle_announcements(mock_interaction, button)

        # 驗證設定被切換
        assert global_settings_view.settings.announcement_enabled is True

        # 驗證資料庫更新被調用
        mock_repository.get_global_notification_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_important_filter(
        self, global_settings_view, mock_interaction, mock_repository
    ):
        """測試切換重要成就篩選."""
        button = MagicMock(spec=discord.ui.Button)

        # 初始狀態為關閉
        assert global_settings_view.settings.important_achievements_only is False

        # 點擊切換按鈕
        await global_settings_view.toggle_important_filter(mock_interaction, button)

        # 驗證設定被切換
        assert global_settings_view.settings.important_achievements_only is True

    @pytest.mark.asyncio
    async def test_set_announcement_channel(
        self, global_settings_view, mock_interaction
    ):
        """測試設定公告頻道."""
        button = MagicMock(spec=discord.ui.Button)

        # 點擊設定頻道按鈕
        await global_settings_view.set_announcement_channel(mock_interaction, button)

        # 驗證頻道選擇視圖被發送
        mock_interaction.response.send_message.assert_called_once()

        # 驗證呼叫參數
        call_args = mock_interaction.response.send_message.call_args
        assert "embed" in call_args.kwargs
        assert "view" in call_args.kwargs
        assert call_args.kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_configure_rate_limit(self, global_settings_view, mock_interaction):
        """測試設定頻率限制."""
        button = MagicMock(spec=discord.ui.Button)

        # 點擊頻率限制設定按鈕
        await global_settings_view.configure_rate_limit(mock_interaction, button)

        # 驗證模態框被發送
        mock_interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_settings(
        self, global_settings_view, mock_interaction, mock_repository
    ):
        """測試重置全域設定."""
        button = MagicMock(spec=discord.ui.Button)

        # 修改一些設定
        global_settings_view.settings.announcement_enabled = True
        global_settings_view.settings.rate_limit_seconds = 120
        global_settings_view.settings.important_achievements_only = True

        # 點擊重置按鈕
        await global_settings_view.reset_settings(mock_interaction, button)

        # 驗證設定被重置為預設值
        assert global_settings_view.settings.announcement_channel_id is None
        assert global_settings_view.settings.announcement_enabled is False
        assert global_settings_view.settings.rate_limit_seconds == 60
        assert global_settings_view.settings.important_achievements_only is False

    @pytest.mark.asyncio
    async def test_create_settings_embed(self, global_settings_view, mock_interaction):
        """測試建立設定 embed."""
        embed = global_settings_view._create_settings_embed(mock_interaction.guild)

        # 驗證 embed 結構
        assert embed.title == "🔧 全域通知設定"
        assert len(embed.fields) >= 4  # 至少包含頻道、公告、頻率、篩選欄位

        # 驗證欄位內容
        field_names = [field.name for field in embed.fields]
        assert "📢 公告頻道" in field_names
        assert "🔔 伺服器公告" in field_names
        assert "⏱️ 頻率限制" in field_names
        assert "🎯 重要成就篩選" in field_names


class TestRateLimitModal:
    """RateLimitModal 測試類別."""

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        repository = AsyncMock()
        repository.get_global_notification_settings.return_value = (
            GlobalNotificationSettings(
                guild_id=987654321, announcement_enabled=True, rate_limit_seconds=60
            )
        )
        repository.update_global_notification_settings.return_value = True
        return repository

    @pytest.fixture
    def mock_interaction(self):
        """模擬 Discord 互動."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    @pytest.fixture
    def sample_settings(self):
        """範例全域設定."""
        return GlobalNotificationSettings(
            guild_id=987654321, announcement_enabled=True, rate_limit_seconds=60
        )

    @pytest.mark.asyncio
    async def test_rate_limit_modal_valid_input(
        self, sample_settings, mock_repository, mock_interaction
    ):
        """測試頻率限制模態框有效輸入."""
        modal = RateLimitModal(sample_settings, mock_repository)

        # 設定輸入值
        modal.rate_limit_input.value = "120"

        # 提交模態框
        await modal.on_submit(mock_interaction)

        # 驗證設定被更新
        assert sample_settings.rate_limit_seconds == 120

        # 驗證資料庫更新被調用
        mock_repository.update_global_notification_settings.assert_called_once()

        # 驗證成功回應被發送
        mock_interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_modal_invalid_input(
        self, sample_settings, mock_repository, mock_interaction
    ):
        """測試頻率限制模態框無效輸入."""
        modal = RateLimitModal(sample_settings, mock_repository)

        # 設定無效輸入值
        modal.rate_limit_input.value = "5"  # 小於最小值 10

        # 提交模態框
        await modal.on_submit(mock_interaction)

        # 驗證設定未被更新
        assert sample_settings.rate_limit_seconds == 60  # 保持原值

        # 驗證錯誤回應被發送
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "❌" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_rate_limit_modal_non_numeric_input(
        self, sample_settings, mock_repository, mock_interaction
    ):
        """測試頻率限制模態框非數字輸入."""
        modal = RateLimitModal(sample_settings, mock_repository)

        # 設定非數字輸入值
        modal.rate_limit_input.value = "invalid"

        # 提交模態框
        await modal.on_submit(mock_interaction)

        # 驗證設定未被更新
        assert sample_settings.rate_limit_seconds == 60  # 保持原值

        # 驗證錯誤回應被發送
        mock_interaction.response.send_message.assert_called_once()


class TestPanelCreationFunctions:
    """面板創建函數測試類別."""

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        repository = AsyncMock()
        repository.get_notification_preferences.return_value = None
        repository.get_global_notification_settings.return_value = None
        return repository

    @pytest.mark.asyncio
    async def test_create_notification_preferences_panel(self, mock_repository):
        """測試建立通知偏好面板."""
        embed, view = await create_notification_preferences_panel(
            user_id=123456789, guild_id=987654321, repository=mock_repository
        )

        # 驗證返回值
        assert embed is not None
        assert isinstance(view, NotificationPreferencesView)
        assert view.user_id == 123456789
        assert view.guild_id == 987654321

    @pytest.mark.asyncio
    async def test_create_global_notification_settings_panel(self, mock_repository):
        """測試建立全域通知設定面板."""
        embed, view = await create_global_notification_settings_panel(
            guild_id=987654321, repository=mock_repository
        )

        # 驗證返回值
        assert embed is not None
        assert isinstance(view, GlobalNotificationSettingsView)
        assert view.guild_id == 987654321

    @pytest.mark.asyncio
    async def test_create_preferences_panel_with_error(self):
        """測試建立偏好面板時發生錯誤."""
        # 模擬會出錯的 repository
        mock_repository = AsyncMock()
        mock_repository.get_notification_preferences.side_effect = Exception(
            "Database error"
        )

        embed, view = await create_notification_preferences_panel(
            user_id=123456789, guild_id=987654321, repository=mock_repository
        )

        # 驗證錯誤處理
        assert embed is not None
        assert "載入失敗" in embed.title
        assert view is None
