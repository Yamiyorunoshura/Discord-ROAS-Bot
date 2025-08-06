"""
核心模塊初始化文件
- 統一導出所有核心功能
- 提供統一的錯誤處理和日誌記錄
- 提供優化的啟動流程
"""

from discord.ext import commands

from .error_handler import ErrorCodes, ErrorHandler, create_error_handler, error_handler
from .logger import DiscordBotLogger, get_logger_manager, setup_module_logger
from .startup import ModuleInfo, StartupManager, create_startup_manager

__all__ = [
    "DiscordBotLogger",
    "ErrorCodes",
    "ErrorHandler",
    "ModuleInfo",
    "StartupManager",
    "create_error_handler",
    "create_startup_manager",
    "error_handler",
    "get_logger_manager",
    "setup_module_logger",
]


async def setup(bot: commands.Bot):
    """
    設置核心模組

    功能:
    - 註冊核心功能到 Bot 實例
    - 初始化全局錯誤處理器
    - 設置日誌管理器
    """
    # 創建並註冊錯誤處理器
    error_handler_instance = create_error_handler("core")
    bot.error_handler = error_handler_instance

    # 創建並註冊日誌管理器
    logger_manager = get_logger_manager()
    bot.logger_manager = logger_manager

    # 創建並註冊啟動管理器
    startup_manager = create_startup_manager(bot)
    bot.startup_manager = startup_manager

    # 核心模組載入完成 - 使用日誌記錄而非 print
