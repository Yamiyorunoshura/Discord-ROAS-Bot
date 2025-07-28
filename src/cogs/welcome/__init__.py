"""
歡迎系統模組初始化檔案 - 重構版本

此模組負責處理新成員加入時的歡迎訊息和圖片
採用依賴注入架構,提供更好的可測試性和可維護性
"""

from ..core.dependency_container import get_global_container
from ..core.logger import setup_module_logger
from .main.main import WelcomeCog
from .services import register_welcome_services

logger = setup_module_logger("welcome")


async def setup(bot):
    """
    設置 Cog - 使用依賴注入架構

    Args:
        bot: Discord Bot 實例
    """
    try:
        # 獲取全局依賴注入容器
        container = await get_global_container()

        # 註冊歡迎系統服務
        await register_welcome_services(container)

        # 創建並初始化 WelcomeCog
        welcome_cog = WelcomeCog(bot)
        await welcome_cog.initialize()

        # 添加到bot
        await bot.add_cog(welcome_cog)

        logger.info("歡迎系統 Cog 設置完成")

    except Exception as e:
        logger.error(f"歡迎系統 Cog 設置失敗: {e}")
        raise
