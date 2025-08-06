"""
資料同步模組依賴注入容器配置

註冊和解析sync_data模組的所有服務依賴
"""

import asyncio

from ...core.dependency_container import DependencyContainer
from ..cache.cache import ISyncDataCache, SyncDataCacheService
from ..config.config import ISyncDataConfig, SyncDataConfigService
from ..database.database import ISyncDataDatabase, SyncDataDatabaseService
from ..service.sync_service import ISyncDataService, SyncDataService


async def configure_sync_data_container(container: DependencyContainer) -> None:
    """
    配置sync_data模組的依賴注入容器

    Args:
        container: 依賴注入容器實例
    """
    # 註冊配置服務
    config_service = SyncDataConfigService()
    container.register_singleton(ISyncDataConfig, config_service)

    # 註冊快取服務
    cache_service = SyncDataCacheService(
        min_sync_interval=config_service.min_sync_interval
    )
    container.register_singleton(ISyncDataCache, cache_service)

    # 註冊資料庫服務
    def create_database_service():
        return SyncDataDatabaseService()

    container.register_singleton(ISyncDataDatabase, create_database_service)

    # 註冊核心同步服務
    def create_sync_service():
        db_service = container.resolve_sync(ISyncDataDatabase)
        cache_service = container.resolve_sync(ISyncDataCache)
        config_service = container.resolve_sync(ISyncDataConfig)

        return SyncDataService(
            db_service=db_service,
            cache_service=cache_service,
            config_service=config_service,
        )

    container.register_singleton(ISyncDataService, create_sync_service)


def create_sync_data_container() -> DependencyContainer:
    """
    創建獨立的sync_data模組依賴注入容器

    Returns:
        DependencyContainer: 配置完成的容器實例
    """
    container = DependencyContainer()
    # 這裡需要使用同步版本的配置
    asyncio.run(configure_sync_data_container(container))
    return container


# 為測試提供的便利函數
def get_test_container() -> DependencyContainer:
    """
    獲取測試用的依賴注入容器

    Returns:
        DependencyContainer: 測試容器實例
    """
    return create_sync_data_container()
