"""通知系統整合服務測試模組.

測試通知系統整合和管理功能，包括：
- NotificationIntegrationService
- NotificationServiceManager
- 服務生命週期管理
- 健康檢查和監控
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ext import commands

from src.cogs.achievement.main.notification_integration import (
    NotificationIntegrationService,
    NotificationServiceManager,
    get_notification_manager,
    get_notification_service,
    initialize_notification_integration,
    shutdown_notification_integration,
)
from src.cogs.achievement.main.notifier import AchievementNotifier
from src.cogs.achievement.services.achievement_awarder import AchievementAwarder


class TestNotificationIntegrationService:
    """NotificationIntegrationService 測試類別."""

    @pytest.fixture
    def mock_bot(self):
        """模擬 Discord 機器人."""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        return AsyncMock()

    @pytest.fixture
    def mock_achievement_awarder(self):
        """模擬成就頒發器."""
        awarder = MagicMock(spec=AchievementAwarder)
        awarder.add_notification_handler = MagicMock()
        awarder.get_award_stats.return_value = {
            "notification_handlers": 1,
            "total_awards": 10,
            "successful_awards": 8
        }
        return awarder

    @pytest.fixture
    async def integration_service(self, mock_bot, mock_repository, mock_achievement_awarder):
        """建立通知整合服務實例."""
        service = NotificationIntegrationService(
            bot=mock_bot,
            repository=mock_repository,
            achievement_awarder=mock_achievement_awarder
        )
        yield service
        # 清理
        if service.is_initialized():
            await service.shutdown()

    @pytest.mark.asyncio
    async def test_service_initialization(
        self,
        integration_service,
        mock_achievement_awarder
    ):
        """測試服務初始化."""
        assert not integration_service.is_initialized()
        assert integration_service.get_notifier() is None

        # 使用 patch 來模擬 AchievementNotifier
        with patch('src.cogs.achievement.main.notification_integration.AchievementNotifier') as mock_notifier_class:
            mock_notifier = MagicMock(spec=AchievementNotifier)
            mock_notifier.start = AsyncMock()
            mock_notifier_class.return_value = mock_notifier

            with patch('src.cogs.achievement.main.notification_integration.create_notification_handler') as mock_create_handler:
                mock_handler = AsyncMock()
                mock_create_handler.return_value = mock_handler

                # 初始化服務
                await integration_service.initialize()

                # 驗證初始化狀態
                assert integration_service.is_initialized()
                assert integration_service.get_notifier() is not None

                # 驗證通知處理器被添加到頒發器
                mock_achievement_awarder.add_notification_handler.assert_called_once_with(mock_handler)

    @pytest.mark.asyncio
    async def test_service_shutdown(self, integration_service):
        """測試服務關閉."""
        # 先初始化服務
        with patch('src.cogs.achievement.main.notification_integration.AchievementNotifier') as mock_notifier_class:
            mock_notifier = MagicMock(spec=AchievementNotifier)
            mock_notifier.start = AsyncMock()
            mock_notifier.stop = AsyncMock()
            mock_notifier_class.return_value = mock_notifier

            with patch('src.cogs.achievement.main.notification_integration.create_notification_handler'):
                await integration_service.initialize()

                # 驗證初始化
                assert integration_service.is_initialized()

                # 關閉服務
                await integration_service.shutdown()

                # 驗證關閉狀態
                assert not integration_service.is_initialized()
                mock_notifier.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_notification_stats(self, integration_service):
        """測試取得通知統計."""
        # 未初始化時
        stats = await integration_service.get_notification_stats()
        assert "error" in stats

        # 初始化後
        with patch('src.cogs.achievement.main.notification_integration.AchievementNotifier') as mock_notifier_class:
            mock_notifier = MagicMock(spec=AchievementNotifier)
            mock_notifier.start = AsyncMock()
            mock_notifier.get_notification_stats.return_value = {
                "total_notifications": 5,
                "successful_dm": 3,
                "successful_announcements": 2
            }
            mock_notifier_class.return_value = mock_notifier

            with patch('src.cogs.achievement.main.notification_integration.create_notification_handler'):
                await integration_service.initialize()

                stats = await integration_service.get_notification_stats()
                assert stats["total_notifications"] == 5
                assert stats["successful_dm"] == 3

    @pytest.mark.asyncio
    async def test_health_check(
        self,
        integration_service,
        mock_achievement_awarder
    ):
        """測試健康檢查."""
        # 未初始化時的健康檢查
        health = await integration_service.health_check()
        assert health["service_initialized"] is False
        assert health["notifier_available"] is False
        assert health["awarder_integration"] is True  # 基於模擬的頒發器統計

        # 初始化後的健康檢查
        with patch('src.cogs.achievement.main.notification_integration.AchievementNotifier') as mock_notifier_class:
            mock_notifier = MagicMock(spec=AchievementNotifier)
            mock_notifier.start = AsyncMock()
            mock_notifier.get_notification_stats.return_value = {
                "is_processing": True,
                "queue_size": 2,
                "active_notifications": 1,
                "success_rate": 0.85
            }
            mock_notifier_class.return_value = mock_notifier

            with patch('src.cogs.achievement.main.notification_integration.create_notification_handler'):
                await integration_service.initialize()

                health = await integration_service.health_check()
                assert health["service_initialized"] is True
                assert health["notifier_available"] is True
                assert health["notifier_processing"] is True
                assert health["queue_size"] == 2
                assert health["success_rate"] == 0.85


class TestNotificationServiceManager:
    """NotificationServiceManager 測試類別."""

    @pytest.fixture
    def mock_bot(self):
        """模擬 Discord 機器人."""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫存取庫."""
        return AsyncMock()

    @pytest.fixture
    def mock_achievement_awarder(self):
        """模擬成就頒發器."""
        awarder = MagicMock(spec=AchievementAwarder)
        awarder.add_notification_handler = MagicMock()
        awarder.get_award_stats.return_value = {"notification_handlers": 1}
        return awarder

    @pytest.fixture
    async def service_manager(self):
        """建立通知服務管理器實例."""
        manager = NotificationServiceManager()
        yield manager
        # 清理所有服務
        await manager.shutdown_all()

    @pytest.mark.asyncio
    async def test_manager_initialization(self, service_manager):
        """測試管理器初始化."""
        assert len(service_manager._services) == 0
        assert service_manager._global_stats["total_services"] == 0
        assert service_manager._global_stats["active_services"] == 0

    @pytest.mark.asyncio
    async def test_create_service(
        self,
        service_manager,
        mock_bot,
        mock_repository,
        mock_achievement_awarder
    ):
        """測試建立服務."""
        guild_id = 123456789

        with patch('src.cogs.achievement.main.notification_integration.NotificationIntegrationService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.initialize = AsyncMock()
            mock_service_class.return_value = mock_service

            # 建立服務
            service = await service_manager.create_service(
                guild_id=guild_id,
                bot=mock_bot,
                repository=mock_repository,
                achievement_awarder=mock_achievement_awarder
            )

            # 驗證服務被建立和註冊
            assert service is not None
            assert guild_id in service_manager._services
            assert service_manager._global_stats["total_services"] == 1
            assert service_manager._global_stats["active_services"] == 1

            # 驗證服務被初始化
            mock_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_service(
        self,
        service_manager,
        mock_bot,
        mock_repository,
        mock_achievement_awarder
    ):
        """測試取得服務."""
        guild_id = 123456789

        # 不存在的服務
        service = await service_manager.get_service(guild_id)
        assert service is None

        # 建立服務後取得
        with patch('src.cogs.achievement.main.notification_integration.NotificationIntegrationService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.initialize = AsyncMock()
            mock_service_class.return_value = mock_service

            await service_manager.create_service(
                guild_id=guild_id,
                bot=mock_bot,
                repository=mock_repository,
                achievement_awarder=mock_achievement_awarder
            )

            service = await service_manager.get_service(guild_id)
            assert service is not None

    @pytest.mark.asyncio
    async def test_remove_service(
        self,
        service_manager,
        mock_bot,
        mock_repository,
        mock_achievement_awarder
    ):
        """測試移除服務."""
        guild_id = 123456789

        # 移除不存在的服務
        result = await service_manager.remove_service(guild_id)
        assert result is False

        # 建立服務後移除
        with patch('src.cogs.achievement.main.notification_integration.NotificationIntegrationService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.initialize = AsyncMock()
            mock_service.shutdown = AsyncMock()
            mock_service_class.return_value = mock_service

            await service_manager.create_service(
                guild_id=guild_id,
                bot=mock_bot,
                repository=mock_repository,
                achievement_awarder=mock_achievement_awarder
            )

            # 移除服務
            result = await service_manager.remove_service(guild_id)
            assert result is True
            assert guild_id not in service_manager._services
            assert service_manager._global_stats["active_services"] == 0

            # 驗證服務被關閉
            mock_service.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_all(
        self,
        service_manager,
        mock_bot,
        mock_repository,
        mock_achievement_awarder
    ):
        """測試關閉所有服務."""
        # 建立多個服務
        guild_ids = [123456789, 987654321, 555666777]

        with patch('src.cogs.achievement.main.notification_integration.NotificationIntegrationService') as mock_service_class:
            mock_services = []
            for guild_id in guild_ids:
                mock_service = MagicMock()
                mock_service.initialize = AsyncMock()
                mock_service.shutdown = AsyncMock()
                mock_services.append(mock_service)
                mock_service_class.return_value = mock_service

                await service_manager.create_service(
                    guild_id=guild_id,
                    bot=mock_bot,
                    repository=mock_repository,
                    achievement_awarder=mock_achievement_awarder
                )

            # 驗證服務被建立
            assert len(service_manager._services) == 3
            assert service_manager._global_stats["active_services"] == 3

            # 關閉所有服務
            await service_manager.shutdown_all()

            # 驗證所有服務被清理
            assert len(service_manager._services) == 0
            assert service_manager._global_stats["active_services"] == 0

    @pytest.mark.asyncio
    async def test_get_global_stats(
        self,
        service_manager,
        mock_bot,
        mock_repository,
        mock_achievement_awarder
    ):
        """測試取得全域統計."""
        # 初始統計
        stats = await service_manager.get_global_stats()
        assert stats["total_services"] == 0
        assert stats["active_services"] == 0
        assert "services" in stats

        # 建立服務後的統計
        guild_id = 123456789

        with patch('src.cogs.achievement.main.notification_integration.NotificationIntegrationService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.initialize = AsyncMock()
            mock_service.get_notification_stats = AsyncMock(return_value={
                "total_notifications": 10,
                "successful_dm": 6,
                "successful_announcements": 4
            })
            mock_service_class.return_value = mock_service

            await service_manager.create_service(
                guild_id=guild_id,
                bot=mock_bot,
                repository=mock_repository,
                achievement_awarder=mock_achievement_awarder
            )

            stats = await service_manager.get_global_stats()
            assert stats["total_services"] == 1
            assert stats["active_services"] == 1
            assert stats["total_notifications"] == 10
            assert len(stats["services"]) == 1
            assert stats["services"][0]["guild_id"] == guild_id

    @pytest.mark.asyncio
    async def test_health_check_all(
        self,
        service_manager,
        mock_bot,
        mock_repository,
        mock_achievement_awarder
    ):
        """測試所有服務的健康檢查."""
        # 空管理器的健康檢查
        health = await service_manager.health_check_all()
        assert health["manager_status"] == "healthy"
        assert health["total_services"] == 0
        assert health["healthy_services"] == 0
        assert len(health["unhealthy_services"]) == 0

        # 建立服務後的健康檢查
        guild_ids = [123456789, 987654321]

        with patch('src.cogs.achievement.main.notification_integration.NotificationIntegrationService') as mock_service_class:
            mock_services = []
            for i, guild_id in enumerate(guild_ids):
                mock_service = MagicMock()
                mock_service.initialize = AsyncMock()

                # 第一個服務健康，第二個不健康
                if i == 0:
                    mock_service.health_check = AsyncMock(return_value={
                        "service_initialized": True,
                        "notifier_available": True
                    })
                else:
                    mock_service.health_check = AsyncMock(return_value={
                        "service_initialized": False,
                        "notifier_available": False
                    })

                mock_services.append(mock_service)
                mock_service_class.return_value = mock_service

                await service_manager.create_service(
                    guild_id=guild_id,
                    bot=mock_bot,
                    repository=mock_repository,
                    achievement_awarder=mock_achievement_awarder
                )

            health = await service_manager.health_check_all()
            assert health["total_services"] == 2
            assert health["healthy_services"] == 1
            assert len(health["unhealthy_services"]) == 1
            assert health["manager_status"] == "degraded"


class TestModuleFunctions:
    """模組層級函數測試類別."""

    @pytest.mark.asyncio
    async def test_get_notification_manager(self):
        """測試取得全域通知管理器."""
        # 第一次呼叫應該建立新實例
        manager1 = await get_notification_manager()
        assert isinstance(manager1, NotificationServiceManager)

        # 第二次呼叫應該返回相同實例
        manager2 = await get_notification_manager()
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_initialize_notification_integration(self):
        """測試初始化通知整合."""
        guild_id = 123456789
        mock_bot = MagicMock(spec=commands.Bot)
        mock_repository = AsyncMock()
        mock_awarder = MagicMock(spec=AchievementAwarder)

        with patch('src.cogs.achievement.main.notification_integration.get_notification_manager') as mock_get_manager:
            mock_manager = MagicMock(spec=NotificationServiceManager)
            mock_manager.create_service = AsyncMock()
            mock_get_manager.return_value = mock_manager

            # 初始化整合
            await initialize_notification_integration(
                guild_id=guild_id,
                bot=mock_bot,
                repository=mock_repository,
                achievement_awarder=mock_awarder
            )

            # 驗證管理器的建立服務方法被調用
            mock_manager.create_service.assert_called_once_with(
                guild_id, mock_bot, mock_repository, mock_awarder
            )

    @pytest.mark.asyncio
    async def test_shutdown_notification_integration(self):
        """測試關閉通知整合."""
        guild_id = 123456789

        with patch('src.cogs.achievement.main.notification_integration.get_notification_manager') as mock_get_manager:
            mock_manager = MagicMock(spec=NotificationServiceManager)
            mock_manager.remove_service = AsyncMock(return_value=True)
            mock_get_manager.return_value = mock_manager

            # 關閉整合
            result = await shutdown_notification_integration(guild_id)

            # 驗證結果和調用
            assert result is True
            mock_manager.remove_service.assert_called_once_with(guild_id)

    @pytest.mark.asyncio
    async def test_get_notification_service(self):
        """測試取得通知服務."""
        guild_id = 123456789

        with patch('src.cogs.achievement.main.notification_integration.get_notification_manager') as mock_get_manager:
            mock_manager = MagicMock(spec=NotificationServiceManager)
            mock_service = MagicMock(spec=NotificationIntegrationService)
            mock_manager.get_service = AsyncMock(return_value=mock_service)
            mock_get_manager.return_value = mock_manager

            # 取得服務
            service = await get_notification_service(guild_id)

            # 驗證結果和調用
            assert service is mock_service
            mock_manager.get_service.assert_called_once_with(guild_id)
