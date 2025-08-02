"""通知系統核心測試模組.

測試 AchievementNotifier 類別的所有功能，包括：
- 私訊通知發送
- 伺服器公告發送
- 通知偏好處理
- 頻率限制機制
- 錯誤處理和重試
- 統計和監控功能
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
    GlobalNotificationSettings,
    NotificationEvent,
    NotificationPreference,
    UserAchievement,
)
from src.cogs.achievement.main.notifier import (
    AchievementNotifier,
    NotificationData,
    NotificationResult,
    NotificationStatus,
    NotificationType,
    create_notification_handler,
)


class TestAchievementNotifier:
    """AchievementNotifier 測試類別."""

    @pytest.fixture
    def mock_bot(self):
        """模擬 Discord 機器人."""
        bot = MagicMock(spec=commands.Bot)
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock()
        return bot

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        repository = AsyncMock()

        # 設定預設回傳值
        repository.get_notification_preferences.return_value = NotificationPreference(
            user_id=123456789,
            guild_id=987654321,
            dm_notifications=True,
            server_announcements=True,
            notification_types=[]
        )

        repository.get_global_notification_settings.return_value = GlobalNotificationSettings(
            guild_id=987654321,
            announcement_enabled=True,
            announcement_channel_id=555666777,
            rate_limit_seconds=60
        )

        repository.mark_achievement_notified.return_value = True
        repository.create_notification_event.return_value = NotificationEvent(
            id=1,
            user_id=123456789,
            guild_id=987654321,
            achievement_id=1,
            notification_type="dm",
            sent_at=datetime.now(),
            delivery_status="sent"
        )

        return repository

    @pytest.fixture
    def sample_achievement(self):
        """範例成就資料."""
        return Achievement(
            id=1,
            name="測試成就",
            description="這是一個測試成就",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100},
            points=50,
            badge_url="https://example.com/badge.png",
            is_active=True,
            role_reward=None,
            is_hidden=False
        )

    @pytest.fixture
    def sample_user_achievement(self):
        """範例用戶成就記錄."""
        return UserAchievement(
            id=1,
            user_id=123456789,
            achievement_id=1,
            earned_at=datetime.now(),
            notified=False
        )

    @pytest.fixture
    async def notifier(self, mock_bot, mock_repository):
        """建立 AchievementNotifier 實例."""
        notifier = AchievementNotifier(
            bot=mock_bot,
            repository=mock_repository,
            max_concurrent_notifications=5,
            notification_timeout=10.0,
            default_retry_limit=2,
            rate_limit_window=30
        )
        await notifier.start()
        yield notifier
        await notifier.stop()

    # =============================================================================
    # 基本功能測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_notifier_initialization(self, mock_bot, mock_repository):
        """測試通知器初始化."""
        notifier = AchievementNotifier(
            bot=mock_bot,
            repository=mock_repository
        )

        assert notifier._bot == mock_bot
        assert notifier._repository == mock_repository
        assert not notifier._is_processing
        assert notifier._notification_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_notifier_start_stop(self, mock_bot, mock_repository):
        """測試通知器啟動和停止."""
        notifier = AchievementNotifier(
            bot=mock_bot,
            repository=mock_repository
        )

        # 測試啟動
        await notifier.start()
        assert notifier._is_processing
        assert notifier._batch_processor_task is not None

        # 測試停止
        await notifier.stop()
        assert not notifier._is_processing

    # =============================================================================
    # 私訊通知測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_send_direct_message_notification_success(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試成功發送私訊通知."""
        # 模擬用戶和私訊發送
        mock_user = MagicMock(spec=discord.User)
        mock_user.send = AsyncMock()
        notifier._bot.get_user.return_value = mock_user

        # 發送通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.DIRECT_MESSAGE
        )

        # 驗證結果
        assert result.dm_status == NotificationStatus.SENT
        assert result.notification_data.user_id == 123456789

        # 驗證私訊發送被調用
        mock_user.send.assert_called_once()

        # 驗證 embed 參數
        call_args = mock_user.send.call_args
        assert 'embed' in call_args.kwargs
        embed = call_args.kwargs['embed']
        assert embed.title == "🎉 成就解鎖！"
        assert sample_achievement.name in embed.description

    @pytest.mark.asyncio
    async def test_send_direct_message_notification_user_not_found(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試用戶不存在時的私訊通知處理."""
        # 模擬用戶不存在
        notifier._bot.get_user.return_value = None
        notifier._bot.fetch_user.side_effect = discord.NotFound(
            MagicMock(), "User not found"
        )

        # 發送通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.DIRECT_MESSAGE
        )

        # 驗證失敗結果
        assert result.dm_status == NotificationStatus.FAILED
        assert "用戶不存在" in result.dm_error

    @pytest.mark.asyncio
    async def test_send_direct_message_notification_forbidden(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試無法發送私訊時的處理."""
        # 模擬私訊被禁止
        mock_user = MagicMock(spec=discord.User)
        mock_user.send = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "Cannot send messages to this user")
        )
        notifier._bot.get_user.return_value = mock_user

        # 發送通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.DIRECT_MESSAGE
        )

        # 驗證失敗結果
        assert result.dm_status == NotificationStatus.FAILED
        assert "無法向用戶發送私訊" in result.dm_error

    # =============================================================================
    # 伺服器公告測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_send_server_announcement_notification_success(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試成功發送伺服器公告通知."""
        # 模擬頻道和訊息發送
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.send = AsyncMock()
        notifier._bot.get_channel.return_value = mock_channel

        # 模擬用戶（用於提及）
        mock_user = MagicMock(spec=discord.User)
        mock_user.mention = "<@123456789>"
        notifier._bot.get_user.return_value = mock_user

        # 發送公告通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.SERVER_ANNOUNCEMENT
        )

        # 驗證結果
        assert result.announcement_status == NotificationStatus.SENT

        # 驗證頻道訊息發送被調用
        mock_channel.send.assert_called_once()

        # 驗證訊息內容
        call_args = mock_channel.send.call_args
        assert 'content' in call_args.kwargs
        assert 'embed' in call_args.kwargs
        assert "<@123456789>" in call_args.kwargs['content']
        assert sample_achievement.name in call_args.kwargs['content']

    @pytest.mark.asyncio
    async def test_send_server_announcement_notification_disabled(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement,
        mock_repository
    ):
        """測試伺服器公告功能未啟用時的處理."""
        # 設定公告功能為關閉
        mock_repository.get_global_notification_settings.return_value = GlobalNotificationSettings(
            guild_id=987654321,
            announcement_enabled=False,
            announcement_channel_id=555666777
        )

        # 發送公告通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.SERVER_ANNOUNCEMENT
        )

        # 驗證失敗結果
        assert result.announcement_status == NotificationStatus.FAILED
        assert "伺服器公告功能未啟用" in result.announcement_error

    # =============================================================================
    # 通知偏好測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_notification_preferences_dm_disabled(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement,
        mock_repository
    ):
        """測試私訊通知被關閉時的處理."""
        # 設定私訊通知為關閉
        mock_repository.get_notification_preferences.return_value = NotificationPreference(
            user_id=123456789,
            guild_id=987654321,
            dm_notifications=False,
            server_announcements=True,
            notification_types=[]
        )

        # 嘗試發送私訊通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.DIRECT_MESSAGE
        )

        # 驗證私訊通知被跳過（保持 PENDING 狀態）
        assert result.dm_status == NotificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_notification_preferences_announcements_disabled(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement,
        mock_repository
    ):
        """測試伺服器公告被關閉時的處理."""
        # 設定伺服器公告為關閉
        mock_repository.get_notification_preferences.return_value = NotificationPreference(
            user_id=123456789,
            guild_id=987654321,
            dm_notifications=True,
            server_announcements=False,
            notification_types=[]
        )

        # 嘗試發送公告通知
        result = await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.SERVER_ANNOUNCEMENT
        )

        # 驗證公告通知被跳過（保持 PENDING 狀態）
        assert result.announcement_status == NotificationStatus.PENDING

    # =============================================================================
    # 頻率限制測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_rate_limiting(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試頻率限制機制."""
        # 快速發送多個通知
        results = []
        for _i in range(6):  # 超過限制（5個/分鐘）
            result = await notifier.notify_achievement(
                user_id=123456789,
                guild_id=987654321,
                achievement=sample_achievement,
                user_achievement=sample_user_achievement,
                notification_type=NotificationType.DIRECT_MESSAGE
            )
            results.append(result)

        # 檢查是否有請求被頻率限制
        rate_limited_count = sum(
            1 for result in results
            if result.dm_status == NotificationStatus.FAILED and "頻率限制" in (result.dm_error or "")
        )

        assert rate_limited_count > 0

    # =============================================================================
    # 批量通知測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_batch_notification_processing(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試批量通知處理."""
        # 建立多個通知資料
        notifications = []
        for i in range(3):
            notification_data = NotificationData(
                user_id=123456789 + i,
                guild_id=987654321,
                achievement=sample_achievement,
                user_achievement=sample_user_achievement,
                notification_type=NotificationType.DIRECT_MESSAGE
            )
            notifications.append(notification_data)

        # 批量發送通知
        results = await notifier.batch_notify_achievements(notifications)

        # 驗證結果
        assert len(results) == 3
        for result in results:
            assert isinstance(result, NotificationResult)

    # =============================================================================
    # 統計和監控測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_notification_stats(self, notifier):
        """測試通知統計功能."""
        # 取得初始統計
        stats = notifier.get_notification_stats()

        # 驗證統計結構
        assert "total_notifications" in stats
        assert "successful_dm" in stats
        assert "successful_announcements" in stats
        assert "failed_dm" in stats
        assert "failed_announcements" in stats
        assert "is_processing" in stats
        assert "queue_size" in stats

    @pytest.mark.asyncio
    async def test_reset_stats(self, notifier):
        """測試重置統計功能."""
        # 重置統計
        notifier.reset_stats()

        # 驗證統計被重置
        stats = notifier.get_notification_stats()
        assert stats["total_notifications"] == 0
        assert stats["successful_dm"] == 0
        assert stats["successful_announcements"] == 0

    # =============================================================================
    # 錯誤處理和重試測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_notification_timeout(
        self,
        mock_bot,
        mock_repository,
        sample_achievement,
        sample_user_achievement
    ):
        """測試通知發送超時處理."""
        # 建立短超時的通知器
        notifier = AchievementNotifier(
            bot=mock_bot,
            repository=mock_repository,
            notification_timeout=0.1  # 很短的超時時間
        )

        await notifier.start()

        try:
            # 模擬長時間的操作
            mock_user = MagicMock(spec=discord.User)
            mock_user.send = AsyncMock(side_effect=lambda **kwargs: asyncio.sleep(1))
            mock_bot.get_user.return_value = mock_user

            # 發送通知
            result = await notifier.notify_achievement(
                user_id=123456789,
                guild_id=987654321,
                achievement=sample_achievement,
                user_achievement=sample_user_achievement,
                notification_type=NotificationType.DIRECT_MESSAGE
            )

            # 驗證超時錯誤
            assert result.dm_status == NotificationStatus.FAILED
            assert "超時" in result.dm_error

        finally:
            await notifier.stop()

    # =============================================================================
    # 整合測試
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_notification_handler_integration(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement
    ):
        """測試通知處理器橋接函數整合."""
        # 建立通知處理器
        handler = await create_notification_handler(notifier)

        # 準備測試資料
        notification_data = {
            "user_id": 123456789,
            "guild_id": 987654321,
            "achievement": sample_achievement,
            "user_achievement": sample_user_achievement,
            "trigger_reason": "測試觸發",
            "source_event": "test_event"
        }

        # 模擬用戶
        mock_user = MagicMock(spec=discord.User)
        mock_user.send = AsyncMock()
        notifier._bot.get_user.return_value = mock_user

        # 呼叫處理器
        await handler(notification_data)

        # 驗證通知被發送
        mock_user.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_event_recording(
        self,
        notifier,
        sample_achievement,
        sample_user_achievement,
        mock_repository
    ):
        """測試通知事件記錄功能."""
        # 模擬成功的私訊發送
        mock_user = MagicMock(spec=discord.User)
        mock_user.send = AsyncMock()
        notifier._bot.get_user.return_value = mock_user

        # 發送通知
        await notifier.notify_achievement(
            user_id=123456789,
            guild_id=987654321,
            achievement=sample_achievement,
            user_achievement=sample_user_achievement,
            notification_type=NotificationType.DIRECT_MESSAGE
        )

        # 驗證事件記錄被調用
        mock_repository.create_notification_event.assert_called_once()

        # 驗證成就標記為已通知
        mock_repository.mark_achievement_notified.assert_called_once_with(
            sample_user_achievement.id
        )
