"""
核心模塊初始化文件
- 統一導出所有核心功能
- 提供統一的錯誤處理和日誌記錄
- 提供優化的啟動流程
"""

from discord.ext import commands
from .error_handler import ErrorHandler, ErrorCodes, create_error_handler, error_handler
from .logger import DiscordBotLogger, get_logger_manager, setup_module_logger
from .startup import StartupManager, ModuleInfo, create_startup_manager

__all__ = [
    'ErrorHandler',
    'ErrorCodes', 
    'create_error_handler',
    'error_handler',
    'DiscordBotLogger',
    'get_logger_manager',
    'setup_module_logger',
    'StartupManager',
    'ModuleInfo',
    'create_startup_manager'
] 

async def setup(bot: commands.Bot):
    """
    設置核心模組
    
    功能：
    - 註冊核心功能到 Bot 實例
    - 初始化全局錯誤處理器
    - 設置日誌管理器
    """
    # 創建並註冊錯誤處理器
    error_handler_instance = create_error_handler("core")
    setattr(bot, 'error_handler', error_handler_instance)
    
    # 創建並註冊日誌管理器
    logger_manager = get_logger_manager()
    setattr(bot, 'logger_manager', logger_manager)
    
    # 創建並註冊啟動管理器
    startup_manager = create_startup_manager(bot)
    setattr(bot, 'startup_manager', startup_manager)
    
    print("✅ [核心] 核心模組已載入") 