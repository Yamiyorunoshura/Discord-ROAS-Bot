"""
歡迎系統服務註冊器

負責註冊所有歡迎系統相關的服務到依賴注入容器
"""

from ...core.dependency_container import DependencyContainer, ServiceLifetime
from ...core.logger import setup_module_logger

# 匯入服務類別
from ..config.welcome_config import WelcomeConfig
from ..database.database import WelcomeDB
from ..main.cache import WelcomeCache
from ..main.main import (
    IWelcomeCache,
    IWelcomeConfig,
    IWelcomeDatabase,
    IWelcomeRenderer,
)
from ..main.renderer import WelcomeRenderer

logger = setup_module_logger("welcome.services")


class WelcomeServiceRegistrar:
    """歡迎系統服務註冊器"""

    def __init__(self, container: DependencyContainer):
        """
        初始化服務註冊器

        Args:
            container: 依賴注入容器
        """
        self.container = container
        logger.info("歡迎系統服務註冊器初始化完成")

    async def register_all_services(self) -> None:
        """註冊所有歡迎系統服務"""
        try:
            await self._register_config_service()
            await self._register_database_service()
            await self._register_cache_service()
            await self._register_renderer_service()

            logger.info("所有歡迎系統服務註冊完成")

        except Exception as e:
            logger.error(f"服務註冊過程中發生錯誤: {e}")
            raise

    async def _register_config_service(self) -> None:
        """註冊配置服務"""
        # 註冊為單例服務
        self.container.register_factory(
            IWelcomeConfig, lambda: WelcomeConfig(), ServiceLifetime.SINGLETON
        )

        logger.debug("配置服務已註冊")

    async def _register_database_service(self) -> None:
        """註冊資料庫服務"""
        # 註冊為單例服務
        self.container.register_factory(
            IWelcomeDatabase, lambda: WelcomeDB(), ServiceLifetime.SINGLETON
        )

        logger.debug("資料庫服務已註冊")

    async def _register_cache_service(self) -> None:
        """註冊快取服務"""
        # 直接創建快取實例,避免異步工廠方法中的循環依賴
        config = WelcomeConfig()
        cache_instance = WelcomeCache(
            timeout=config.cache_timeout, max_size=config.max_cache_size
        )

        self.container.register_instance(IWelcomeCache, cache_instance)

        logger.debug("快取服務已註冊")

    async def _register_renderer_service(self) -> None:
        """註冊渲染器服務"""
        # 直接創建渲染器實例,避免異步工廠方法中的循環依賴
        config = WelcomeConfig()
        renderer_instance = WelcomeRenderer(config.background_dir)

        self.container.register_instance(IWelcomeRenderer, renderer_instance)

        logger.debug("渲染器服務已註冊")


async def register_welcome_services(container: DependencyContainer) -> None:
    """
    便利函數:註冊所有歡迎系統服務

    Args:
        container: 依賴注入容器
    """
    registrar = WelcomeServiceRegistrar(container)
    await registrar.register_all_services()
    logger.info("歡迎系統所有服務註冊完成")
