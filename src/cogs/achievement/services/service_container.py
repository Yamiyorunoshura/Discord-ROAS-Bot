"""成就系統服務容器和依賴注入配置.

此模組提供成就系統服務的容器化管理,包含:
- 服務依賴注入配置
- 服務生命週期管理
- 統一的服務工廠方法
- 錯誤處理和日誌記錄整合

遵循依賴注入和容器化設計原則,提供清晰的服務邊界和依賴關係.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..database.repository import AchievementRepository
from ..main.tracker import AchievementEventListener
from .achievement_service import AchievementService
from .admin_permission_service import AdminPermissionService
from .audit_logger import AuditLogger
from .cache_service import AchievementCacheService
from .progress_tracker import ProgressTracker
from .trigger_engine import TriggerEngine
from .user_admin_service import UserAchievementAdminService, UserSearchService

if TYPE_CHECKING:
    from discord.ext import commands

    from src.core.container import Container
    from src.core.database import DatabasePool

logger = logging.getLogger(__name__)

class AchievementServiceContainer:
    """成就系統服務容器.

    提供成就系統所有服務的容器化管理,包含:
    - 服務實例管理和生命週期
    - 依賴注入和配置
    - 統一的服務存取介面
    """

    def __init__(self, database_pool: DatabasePool, bot: commands.Bot | None = None):
        """初始化服務容器.

        Args:
            database_pool: 資料庫連線池
            bot: Discord 機器人實例(用於事件監聽器)
        """
        self._database_pool = database_pool
        self._bot = bot
        self._repository: AchievementRepository | None = None
        self._achievement_service: AchievementService | None = None
        self._admin_permission_service: AdminPermissionService | None = None
        self._progress_tracker: ProgressTracker | None = None
        self._trigger_engine: TriggerEngine | None = None
        self._event_listener: AchievementEventListener | None = None
        self._user_admin_service: UserAchievementAdminService | None = None
        self._user_search_service: UserSearchService | None = None
        self._audit_logger: AuditLogger | None = None
        self._cache_service: AchievementCacheService | None = None

        logger.info("AchievementServiceContainer 初始化完成")

    async def __aenter__(self) -> AchievementServiceContainer:
        """異步上下文管理器進入."""
        await self._initialize_services()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self._cleanup_services()

    async def _initialize_services(self) -> None:
        """初始化所有服務."""
        try:
            # 初始化 Repository
            self._repository = AchievementRepository(self._database_pool)

            # 初始化管理員權限服務
            self._admin_permission_service = AdminPermissionService()

            # 初始化快取服務
            self._cache_service = AchievementCacheService()

            # 初始化審計日誌服務
            self._audit_logger = AuditLogger(self._repository)

            # 初始化用戶搜尋服務
            if self._bot:
                self._user_search_service = UserSearchService(self._bot)

            # 初始化用戶管理服務
            self._user_admin_service = UserAchievementAdminService(
                repository=self._repository,
                permission_service=self._admin_permission_service,
                cache_service=self._cache_service,
                audit_logger=self._audit_logger,
            )

            # 初始化 AchievementService
            self._achievement_service = AchievementService(
                repository=self._repository, cache_service=self._cache_service
            )

            # 初始化 ProgressTracker
            self._progress_tracker = ProgressTracker(self._repository)

            # 初始化 TriggerEngine(需要 ProgressTracker 依賴)
            self._trigger_engine = TriggerEngine(
                repository=self._repository, progress_tracker=self._progress_tracker
            )

            # 初始化事件監聽器(如果有 bot 實例)
            if self._bot:
                self._event_listener = AchievementEventListener(self._bot)
                await self._event_listener.initialize(
                    self._achievement_service, self._database_pool
                )

            logger.info("成就系統服務初始化完成")

        except Exception as e:
            logger.error(
                "成就系統服務初始化失敗", extra={"error": str(e)}, exc_info=True
            )
            raise

    async def _cleanup_services(self) -> None:
        """清理所有服務."""
        try:
            # 清理事件監聽器
            if self._event_listener:
                await self._event_listener.cleanup()

            # 清理管理員權限服務
            if self._admin_permission_service:
                await self._admin_permission_service.cleanup()

            if self._achievement_service:
                await self._achievement_service.__aexit__(None, None, None)

            logger.info("成就系統服務清理完成")

        except Exception as e:
            logger.error("成就系統服務清理失敗", extra={"error": str(e)}, exc_info=True)

    @property
    def repository(self) -> AchievementRepository:
        """取得 Repository 實例."""
        if not self._repository:
            raise RuntimeError("服務容器尚未初始化")
        return self._repository

    @property
    def achievement_service(self) -> AchievementService:
        """取得 AchievementService 實例."""
        if not self._achievement_service:
            raise RuntimeError("服務容器尚未初始化")
        return self._achievement_service

    @property
    def admin_permission_service(self) -> AdminPermissionService:
        """取得 AdminPermissionService 實例."""
        if not self._admin_permission_service:
            raise RuntimeError("服務容器尚未初始化")
        return self._admin_permission_service

    @property
    def progress_tracker(self) -> ProgressTracker:
        """取得 ProgressTracker 實例."""
        if not self._progress_tracker:
            raise RuntimeError("服務容器尚未初始化")
        return self._progress_tracker

    @property
    def trigger_engine(self) -> TriggerEngine:
        """取得 TriggerEngine 實例."""
        if not self._trigger_engine:
            raise RuntimeError("服務容器尚未初始化")
        return self._trigger_engine

    @property
    def event_listener(self) -> AchievementEventListener | None:
        """取得 AchievementEventListener 實例."""
        return self._event_listener

    @property
    def user_admin_service(self) -> UserAchievementAdminService:
        """取得 UserAchievementAdminService 實例."""
        if not self._user_admin_service:
            raise RuntimeError("服務容器尚未初始化")
        return self._user_admin_service

    @property
    def user_search_service(self) -> UserSearchService | None:
        """取得 UserSearchService 實例."""
        return self._user_search_service

    @property
    def audit_logger(self) -> AuditLogger:
        """取得 AuditLogger 實例."""
        if not self._audit_logger:
            raise RuntimeError("服務容器尚未初始化")
        return self._audit_logger

    @property
    def cache_service(self) -> AchievementCacheService:
        """取得 AchievementCacheService 實例."""
        if not self._cache_service:
            raise RuntimeError("服務容器尚未初始化")
        return self._cache_service

class AchievementServiceFactory:
    """成就系統服務工廠.

    提供統一的服務創建和配置方法.
    """

    @staticmethod
    async def create_container(
        database_pool: DatabasePool,
    ) -> AchievementServiceContainer:
        """創建服務容器.

        Args:
            database_pool: 資料庫連線池

        Returns:
            已初始化的服務容器
        """
        container = AchievementServiceContainer(database_pool)
        await container.__aenter__()
        return container

    @staticmethod
    async def create_achievement_service(
        database_pool: DatabasePool,
    ) -> AchievementService:
        """創建 AchievementService 實例.

        Args:
            database_pool: 資料庫連線池

        Returns:
            AchievementService 實例
        """
        repository = AchievementRepository(database_pool)
        return AchievementService(repository=repository)

    @staticmethod
    async def create_progress_tracker(database_pool: DatabasePool) -> ProgressTracker:
        """創建 ProgressTracker 實例.

        Args:
            database_pool: 資料庫連線池

        Returns:
            ProgressTracker 實例
        """
        repository = AchievementRepository(database_pool)
        return ProgressTracker(repository)

    @staticmethod
    async def create_trigger_engine(database_pool: DatabasePool) -> TriggerEngine:
        """創建 TriggerEngine 實例.

        Args:
            database_pool: 資料庫連線池

        Returns:
            TriggerEngine 實例
        """
        repository = AchievementRepository(database_pool)
        progress_tracker = ProgressTracker(repository)
        return TriggerEngine(repository, progress_tracker)

# 整合到現有的依賴注入系統
async def register_achievement_services(
    container: Container, database_pool: DatabasePool
) -> None:
    """在主容器中註冊成就系統服務.

    Args:
        container: 主要的依賴注入容器
        database_pool: 資料庫連線池
    """
    try:
        # 創建成就服務容器
        achievement_container = await AchievementServiceFactory.create_container(
            database_pool
        )

        # 註冊到主容器
        container.register_singleton(
            "achievement_repository", achievement_container.repository
        )
        container.register_singleton(
            "achievement_service", achievement_container.achievement_service
        )
        container.register_singleton(
            "progress_tracker", achievement_container.progress_tracker
        )
        container.register_singleton(
            "trigger_engine", achievement_container.trigger_engine
        )
        container.register_singleton("achievement_container", achievement_container)

        logger.info("成就系統服務已註冊到主容器")

    except Exception as e:
        logger.error("成就系統服務註冊失敗", extra={"error": str(e)}, exc_info=True)
        raise

__all__ = [
    "AchievementServiceContainer",
    "AchievementServiceFactory",
    "register_achievement_services",
]
