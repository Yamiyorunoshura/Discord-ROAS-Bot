"""成就通知系統整合服務.

此模組負責將通知系統與現有的成就頒發和觸發系統整合，提供：
- 通知系統初始化和配置
- 與 AchievementAwarder 的整合
- 與成就主 Cog 的整合
- 效能優化和監控
- 生命週期管理
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .notifier import AchievementNotifier, create_notification_handler

if TYPE_CHECKING:

    from discord.ext import commands

    from ..database.repository import AchievementRepository
    from ..services.achievement_awarder import AchievementAwarder

logger = logging.getLogger(__name__)


class NotificationIntegrationService:
    """通知系統整合服務.

    負責管理通知系統的整合和生命週期。
    """

    def __init__(
        self,
        bot: commands.Bot,
        repository: AchievementRepository,
        achievement_awarder: AchievementAwarder
    ):
        """初始化通知整合服務.

        Args:
            bot: Discord 機器人實例
            repository: 成就資料存取庫
            achievement_awarder: 成就頒發器
        """
        self.bot = bot
        self.repository = repository
        self.achievement_awarder = achievement_awarder
        self.notifier: AchievementNotifier | None = None
        self._initialized = False

        logger.info("NotificationIntegrationService 初始化完成")

    async def initialize(self) -> None:
        """初始化通知系統整合."""
        if self._initialized:
            logger.warning("通知系統已初始化，跳過重複初始化")
            return

        try:
            # 1. 初始化 AchievementNotifier
            self.notifier = AchievementNotifier(
                bot=self.bot,
                repository=self.repository,
                max_concurrent_notifications=10,
                notification_timeout=15.0,
                default_retry_limit=3,
                rate_limit_window=60
            )

            # 2. 啟動通知系統
            await self.notifier.start()

            # 3. 建立通知處理器橋接函數
            notification_handler = await create_notification_handler(self.notifier)

            # 4. 註冊到 AchievementAwarder
            self.achievement_awarder.add_notification_handler(notification_handler)

            self._initialized = True

            logger.info("通知系統整合初始化完成")

        except Exception as e:
            logger.error(f"通知系統整合初始化失敗: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """關閉通知系統整合."""
        if not self._initialized:
            return

        try:
            # 停止通知系統
            if self.notifier:
                await self.notifier.stop()

            self._initialized = False

            logger.info("通知系統整合已關閉")

        except Exception as e:
            logger.error(f"通知系統關閉失敗: {e}", exc_info=True)

    def get_notifier(self) -> AchievementNotifier | None:
        """取得通知器實例.

        Returns:
            AchievementNotifier 實例，如果未初始化則返回 None
        """
        return self.notifier

    def is_initialized(self) -> bool:
        """檢查是否已初始化.

        Returns:
            True 如果已初始化，否則 False
        """
        return self._initialized

    async def get_notification_stats(self) -> dict:
        """取得通知統計資訊.

        Returns:
            統計資訊字典
        """
        if not self.notifier:
            return {"error": "通知系統未初始化"}

        return self.notifier.get_notification_stats()

    async def reset_notification_stats(self) -> None:
        """重置通知統計."""
        if self.notifier:
            self.notifier.reset_stats()

    async def health_check(self) -> dict:
        """執行通知系統健康檢查.

        Returns:
            健康檢查結果
        """
        health_status = {
            "service_initialized": self._initialized,
            "notifier_available": self.notifier is not None,
            "notifier_processing": False,
            "awarder_integration": False,
            "last_error": None
        }

        try:
            if self.notifier:
                stats = self.notifier.get_notification_stats()
                health_status["notifier_processing"] = stats.get("is_processing", False)
                health_status["queue_size"] = stats.get("queue_size", 0)
                health_status["active_notifications"] = stats.get("active_notifications", 0)
                health_status["success_rate"] = stats.get("success_rate", 0.0)

            # 檢查與 AchievementAwarder 的整合
            awarder_stats = self.achievement_awarder.get_award_stats()
            health_status["awarder_integration"] = awarder_stats.get("notification_handlers", 0) > 0

        except Exception as e:
            health_status["last_error"] = str(e)
            logger.error(f"通知系統健康檢查失敗: {e}")

        return health_status


class NotificationServiceManager:
    """通知服務管理器.

    提供高層級的通知服務管理功能。
    """

    def __init__(self):
        """初始化通知服務管理器."""
        self._services: dict[int, NotificationIntegrationService] = {}
        self._global_stats = {
            "total_services": 0,
            "active_services": 0,
            "total_notifications": 0,
            "start_time": None
        }

        logger.info("NotificationServiceManager 初始化完成")

    async def create_service(
        self,
        guild_id: int,
        bot: commands.Bot,
        repository: AchievementRepository,
        achievement_awarder: AchievementAwarder
    ) -> NotificationIntegrationService:
        """為指定伺服器建立通知服務.

        Args:
            guild_id: 伺服器 ID
            bot: Discord 機器人實例
            repository: 成就資料存取庫
            achievement_awarder: 成就頒發器

        Returns:
            通知整合服務實例
        """
        if guild_id in self._services:
            logger.warning(f"伺服器 {guild_id} 的通知服務已存在")
            return self._services[guild_id]

        try:
            # 建立服務
            service = NotificationIntegrationService(
                bot=bot,
                repository=repository,
                achievement_awarder=achievement_awarder
            )

            # 初始化服務
            await service.initialize()

            # 註冊服務
            self._services[guild_id] = service
            self._global_stats["total_services"] += 1
            self._global_stats["active_services"] += 1

            if self._global_stats["start_time"] is None:
                from datetime import datetime
                self._global_stats["start_time"] = datetime.now()

            logger.info(f"為伺服器 {guild_id} 建立通知服務")

            return service

        except Exception as e:
            logger.error(f"建立伺服器 {guild_id} 通知服務失敗: {e}", exc_info=True)
            raise

    async def get_service(self, guild_id: int) -> NotificationIntegrationService | None:
        """取得指定伺服器的通知服務.

        Args:
            guild_id: 伺服器 ID

        Returns:
            通知整合服務實例，如果不存在則返回 None
        """
        return self._services.get(guild_id)

    async def remove_service(self, guild_id: int) -> bool:
        """移除指定伺服器的通知服務.

        Args:
            guild_id: 伺服器 ID

        Returns:
            True 如果成功移除，否則 False
        """
        if guild_id not in self._services:
            return False

        try:
            service = self._services[guild_id]
            await service.shutdown()

            del self._services[guild_id]
            self._global_stats["active_services"] -= 1

            logger.info(f"已移除伺服器 {guild_id} 的通知服務")
            return True

        except Exception as e:
            logger.error(f"移除伺服器 {guild_id} 通知服務失敗: {e}", exc_info=True)
            return False

    async def shutdown_all(self) -> None:
        """關閉所有通知服務."""
        try:
            # 並發關閉所有服務
            shutdown_tasks = []
            for _guild_id, service in self._services.items():
                task = asyncio.create_task(service.shutdown())
                shutdown_tasks.append(task)

            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)

            # 清理服務列表
            self._services.clear()
            self._global_stats["active_services"] = 0

            logger.info("所有通知服務已關閉")

        except Exception as e:
            logger.error(f"關閉所有通知服務失敗: {e}", exc_info=True)

    async def get_global_stats(self) -> dict:
        """取得全域統計資訊.

        Returns:
            全域統計資訊字典
        """
        stats = dict(self._global_stats)

        # 收集各服務的統計
        service_stats = []
        total_notifications = 0

        for guild_id, service in self._services.items():
            try:
                service_stat = await service.get_notification_stats()
                service_stat["guild_id"] = guild_id
                service_stats.append(service_stat)

                total_notifications += service_stat.get("total_notifications", 0)

            except Exception as e:
                logger.error(f"取得伺服器 {guild_id} 統計失敗: {e}")

        stats["services"] = service_stats
        stats["total_notifications"] = total_notifications

        return stats

    async def health_check_all(self) -> dict:
        """執行所有服務的健康檢查.

        Returns:
            健康檢查結果
        """
        results = {
            "manager_status": "healthy",
            "total_services": len(self._services),
            "healthy_services": 0,
            "unhealthy_services": [],
            "service_details": []
        }

        for guild_id, service in self._services.items():
            try:
                health = await service.health_check()
                health["guild_id"] = guild_id
                results["service_details"].append(health)

                if health["service_initialized"] and health["notifier_available"]:
                    results["healthy_services"] += 1
                else:
                    results["unhealthy_services"].append(guild_id)

            except Exception as e:
                results["unhealthy_services"].append(guild_id)
                logger.error(f"伺服器 {guild_id} 健康檢查失敗: {e}")

        # 設定管理器狀態
        if results["unhealthy_services"]:
            results["manager_status"] = "degraded"

        return results


# 全域通知服務管理器實例
_notification_manager: NotificationServiceManager | None = None


async def get_notification_manager() -> NotificationServiceManager:
    """取得全域通知服務管理器.

    Returns:
        NotificationServiceManager 實例
    """
    global _notification_manager

    if _notification_manager is None:
        _notification_manager = NotificationServiceManager()

    return _notification_manager


async def initialize_notification_integration(
    guild_id: int,
    bot: commands.Bot,
    repository: AchievementRepository,
    achievement_awarder: AchievementAwarder
) -> NotificationIntegrationService:
    """初始化指定伺服器的通知系統整合.

    Args:
        guild_id: 伺服器 ID
        bot: Discord 機器人實例
        repository: 成就資料存取庫
        achievement_awarder: 成就頒發器

    Returns:
        通知整合服務實例
    """
    manager = await get_notification_manager()
    return await manager.create_service(guild_id, bot, repository, achievement_awarder)


async def shutdown_notification_integration(guild_id: int) -> bool:
    """關閉指定伺服器的通知系統整合.

    Args:
        guild_id: 伺服器 ID

    Returns:
        True 如果成功關閉，否則 False
    """
    manager = await get_notification_manager()
    return await manager.remove_service(guild_id)


async def get_notification_service(guild_id: int) -> NotificationIntegrationService | None:
    """取得指定伺服器的通知服務.

    Args:
        guild_id: 伺服器 ID

    Returns:
        通知整合服務實例，如果不存在則返回 None
    """
    manager = await get_notification_manager()
    return await manager.get_service(guild_id)


__all__ = [
    "NotificationIntegrationService",
    "NotificationServiceManager",
    "get_notification_manager",
    "get_notification_service",
    "initialize_notification_integration",
    "shutdown_notification_integration",
]
