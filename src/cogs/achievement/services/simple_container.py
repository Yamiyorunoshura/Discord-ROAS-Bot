"""服務容器快速存取包裝器.

此模組提供服務容器的簡化存取介面,
主要用於 UI 組件中快速獲取所需服務.
"""

from __future__ import annotations

import logging

from src.core.database import get_database_pool

from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)


class ServiceContainer:
    """簡化的服務容器包裝器."""

    def __init__(self):
        """初始化服務容器包裝器."""
        self._repository: AchievementRepository | None = None

    async def get_repository(self) -> AchievementRepository:
        """獲取 Repository 實例."""
        if not self._repository:
            try:
                # 獲取資料庫連線池
                pool = await get_database_pool("achievement")

                # 建立 Repository
                self._repository = AchievementRepository(pool)

                logger.debug("Repository 實例已建立")

            except Exception as e:
                logger.error(f"建立 Repository 實例失敗: {e}")
                raise

        return self._repository
